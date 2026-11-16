"""
generators/sqlexport.py
-----------------------
The SQL_Exporter (export spec Requirement 3, umbrella Requirement 10 as amended
by A1): a reviewable MySQL script that points an EXISTING EQEmu zone's server
rows at an Export.

:func:`export_sql` returns the script text; it never opens a database
connection and never writes a file (the export writes ``<short>.sql``). The
script, inside one transaction:

* ``UPDATE zone`` sets the safe point and ``underworld`` of the short name's
  version-0 row, nothing else (archive decision 5). No zone id is used or
  changed (A1); rows are found by short name.
* ``DELETE FROM doors`` for the short name's version 0, then one ``INSERT``
  per Gate: the Door model at the lock, sized to span the corridor and turned
  across it (archive decisions 8 and 9).
* With spawn cleanup, deletes of the short name's ``spawn2``, ``grid``,
  ``grid_entries`` and ``ground_spawns`` rows (version 0 where the table has
  one). ``grid`` and ``grid_entries`` key on the zone id, which the script reads
  from the ``zone`` row by short name; without spawn cleanup those tables are
  never named.

Only finite numbers and a short name from the Known_Zone_List reach a
statement; anything else raises :class:`SqlExportError` naming the field, and
there is no script.

The columns written are a subset of the pinned EQEmu schema (archive decision
4), recorded below as :data:`DOORS_COLUMNS` and :data:`ZONE_COLUMNS` so the
test can build those tables.

Door placement. ``BBDOOR1`` is a 1 x 10 x 10.05 slab with its hinge edge at the
model origin, running along local -y (RESEARCH "Step 17", section 2). EQEmu
turns a door by ``-heading`` about Z, heading in 0-512 units (clockwise seen
from above), so:

* a corridor running along X gets heading 0 and the row sits at the doorway's
  +y jamb (``lock_y + width/2``), the slab reaching to the -y jamb;
* a corridor running along Y gets heading 128 (90 degrees) and the row sits at
  the +x jamb (``lock_x + width/2``), the slab reaching to the -x jamb.

``size`` is 100 per unit scale, so ``size = 100 * width / door_width``.
Which way the corridor runs at the lock is the leg of its planned route
(:func:`generators.routing.corridor_route`) nearest the lock.

``lockpick``. EQEmu ``zone/doors.cpp`` (master, 2026-11-16) treats it as the
Pick Lock skill a player needs: a door is unlocked only when key, lockpick and
guild are all 0 (``is_door_not_locked``, line 309), and a pick succeeds when
``GetLockpick() <= player_pick_lock_skill`` (line 427). No value is special, so
0 (or -1) would let anyone with the skill pick it; :data:`LOCKPICK_UNPICKABLE`
is the column's largest value (``int16_t``), above any skill.
"""

from __future__ import annotations

import math
import re
from typing import Dict, Iterable, List, Optional, Tuple

from .zone_spec import CorridorSpec, GateSpec, ZoneSpec

#: The pinned EQEmu ``doors`` columns (``common/repositories/base/
#: base_doors_repository.h``, EQEmu/Server master, 2026-11-16), in order, with
#: their repository defaults. ``id`` is the auto-increment key the INSERT omits.
DOORS_COLUMNS: Tuple[Tuple[str, object], ...] = (
    ("id", 0), ("doorid", 0), ("zone", ""), ("version", 0), ("name", ""),
    ("pos_y", 0.0), ("pos_x", 0.0), ("pos_z", 0.0), ("heading", 0.0),
    ("opentype", 0), ("guild", 0), ("lockpick", 0), ("keyitem", 0),
    ("nokeyring", 0), ("triggerdoor", 0), ("triggertype", 0),
    ("disable_timer", 0), ("doorisopen", 0), ("door_param", 0),
    ("dest_zone", "NONE"), ("dest_instance", 0), ("dest_x", 0.0),
    ("dest_y", 0.0), ("dest_z", 0.0), ("dest_heading", 0.0),
    ("invert_state", 0), ("incline", 0), ("size", 100), ("buffer", 0.0),
    ("client_version_mask", 4294967295), ("is_ldon_door", 0),
    ("close_timer_ms", 5000), ("dz_switch_id", 0), ("min_expansion", -1),
    ("max_expansion", -1), ("content_flags", ""), ("content_flags_disabled", ""),
)

#: The pinned EQEmu ``zone`` columns (``base_zone_repository.h``, same pin).
ZONE_COLUMNS: Tuple[str, ...] = tuple("""
id zoneidnumber version short_name long_name min_status map_file_name note
min_expansion max_expansion content_flags content_flags_disabled expansion
file_name safe_x safe_y safe_z safe_heading graveyard_id min_level max_level
timezone maxclients ruleset underworld minclip maxclip fog_minclip fog_maxclip
fog_blue fog_red fog_green sky ztype zone_exp_multiplier walkspeed time_type
fog_red1 fog_green1 fog_blue1 fog_minclip1 fog_maxclip1 fog_red2 fog_green2
fog_blue2 fog_minclip2 fog_maxclip2 fog_red3 fog_green3 fog_blue3 fog_minclip3
fog_maxclip3 fog_red4 fog_green4 fog_blue4 fog_minclip4 fog_maxclip4
fog_density flag_needed canbind cancombat canlevitate castoutdoor hotzone
insttype shutdowndelay peqzone bypass_expansion_check suspendbuffs
rain_chance1 rain_chance2 rain_chance3 rain_chance4 rain_duration1
rain_duration2 rain_duration3 rain_duration4 snow_chance1 snow_chance2
snow_chance3 snow_chance4 snow_duration1 snow_duration2 snow_duration3
snow_duration4 gravity type skylock fast_regen_hp fast_regen_mana
fast_regen_endurance npc_max_aggro_dist client_update_range
underworld_teleport_index lava_damage min_lava_damage idle_when_empty
seconds_before_idle shard_at_player_count
""".split())

#: The spawn tables spawn cleanup empties, with the columns it reads (same pin):
#: (table, column naming the zone, whether it has ``version``).
SPAWN_TABLES: Tuple[Tuple[str, str, bool], ...] = (
    ("spawn2", "zone", True),
    ("grid_entries", "zoneid", False),
    ("grid", "zoneid", False),
    ("ground_spawns", "zoneid", True),
)

DEFAULT_DOOR_MODEL = "OBJ_BBDOOR1"
DEFAULT_DOOR_WIDTH = 10.0

#: ``underworld`` sits this far below the build's lowest point.
UNDERWORLD_MARGIN = 100.0

#: ``lockpick``: the largest ``int16_t``, more Pick Lock skill than any player has.
LOCKPICK_UNPICKABLE = 32767

#: Placeholder ``keyitem`` per Gate tier (tier 0 → 990000, ...). The user sets real ids.
KEYITEM_PLACEHOLDER_BASE = 990000

#: EQ heading units for a quarter turn (512 = a full turn).
QUARTER_TURN = 128.0

_NAME_RE = re.compile(r"[a-z0-9_]{1,32}")
_MODEL_RE = re.compile(r"[A-Za-z0-9_]{1,32}")


class SqlExportError(ValueError):
    """No script: ``field`` names what was wrong (a short name, or a value's field)."""

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field


def _num(field: str, value) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise SqlExportError(field, f"{field} is not a number: {value!r}") from None
    if not math.isfinite(v):
        raise SqlExportError(field, f"{field} is not finite: {v!r}")
    return v


def _f(v: float) -> str:
    """A finite float as an SQL literal (no exponent, '-0' folded to '0')."""
    s = f"{v:.3f}"
    return "0.000" if s == "-0.000" else s


def _lit(v) -> str:
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    if isinstance(v, float):
        return _f(v)
    return str(int(v))


def _leg_along_x(cor: CorridorSpec, rooms: Dict, x: float, y: float) -> bool:
    """Whether the corridor runs along X where it passes nearest (x, y)."""
    from .routing import corridor_route

    route = corridor_route(cor, rooms)
    best, along = math.inf, route.axes[0]
    for k, ax in enumerate(route.axes):
        (x0, y0), (x1, y1) = route.waypoints[k], route.waypoints[k + 1]
        cx = min(max(x, min(x0, x1)), max(x0, x1))
        cy = min(max(y, min(y0, y1)), max(y0, y1))
        d = math.hypot(x - cx, y - cy)
        if d < best - 1e-9:
            best, along = d, ax
    return along


def _door_rows(spec: ZoneSpec, short: str, door_model: str,
               door_width: float) -> List[Dict[str, object]]:
    corridors = {c.id: c for c in spec.corridors}
    rooms = {r.id: r for r in spec.rooms}
    gates: List[GateSpec] = sorted(spec.gates, key=lambda g: (g.tier, g.id))
    rows = []
    for n, g in enumerate(gates, start=1):
        lx = _num(f"gates[{g.id}].lock_x", g.lock_x)
        ly = _num(f"gates[{g.id}].lock_y", g.lock_y)
        lz = _num(f"gates[{g.id}].lock_z", g.lock_z)
        cor = corridors.get(g.corridor_id)
        if cor is None:
            raise SqlExportError(f"gates[{g.id}].corridor_id",
                                 f"gate {g.id} names corridor {g.corridor_id!r}, "
                                 "which the spec doesn't have")
        width = _num(f"corridors[{cor.id}].width", cor.width)
        if width <= 0:
            raise SqlExportError(f"corridors[{cor.id}].width",
                                 f"corridors[{cor.id}].width is not positive: {width!r}")
        hw = width / 2
        if _leg_along_x(cor, rooms, lx, ly):
            heading, px, py = 0.0, lx, ly + hw
        else:
            heading, px, py = QUARTER_TURN, lx + hw, ly
        size = int(round(100.0 * width / door_width))
        size = min(max(size, 1), 65535)               # uint16_t
        row = {name: default for name, default in DOORS_COLUMNS if name != "id"}
        row.update(
            doorid=n, zone=short, version=0, name=door_model,
            pos_y=py, pos_x=px, pos_z=lz, heading=heading,
            opentype=0, incline=0, size=size,
            lockpick=LOCKPICK_UNPICKABLE,
            keyitem=KEYITEM_PLACEHOLDER_BASE + int(g.tier),
        )
        rows.append(row)
    return rows


def export_sql(spec: ZoneSpec, shortname: str, *, bounds_min_z: float,
               door_model: str = DEFAULT_DOOR_MODEL,
               door_width: float = DEFAULT_DOOR_WIDTH,
               clear_spawns: bool = False,
               known: Optional[Iterable[str]] = None) -> str:
    """The MySQL script taking over ``shortname`` with the build of ``spec``.

    ``bounds_min_z`` is the build's lowest Z; ``underworld`` goes
    :data:`UNDERWORLD_MARGIN` below it. ``known`` overrides the
    Known_Zone_List (tests); by default it is :func:`analyzer.zonelist.known_shortnames`.
    Raises :class:`SqlExportError` (naming the short name or the field) and
    returns no script when anything can't go into a statement.
    """
    short = (shortname or "").strip().lower()
    names = set(known) if known is not None else None
    if names is None:
        from analyzer.zonelist import known_shortnames
        names = set(known_shortnames())
    if short not in names or not _NAME_RE.fullmatch(short):
        raise SqlExportError("shortname", f"unknown short name {shortname!r}: "
                             "not on the Known_Zone_List")
    if not _MODEL_RE.fullmatch(door_model or ""):
        raise SqlExportError("door_model", f"door_model is not a model name: {door_model!r}")
    door_width = _num("door_width", door_width)
    if door_width <= 0:
        raise SqlExportError("door_width", f"door_width is not positive: {door_width!r}")

    sp = tuple(spec.safe_point)
    if len(sp) != 3:
        raise SqlExportError("safe_point", f"safe_point needs 3 values: {sp!r}")
    sx, sy, sz = (_num(f"safe_point[{i}]", v) for i, v in enumerate(sp))
    underworld = _num("bounds_min_z", bounds_min_z) - UNDERWORLD_MARGIN
    doors = _door_rows(spec, short, door_model, door_width)

    q = _lit(short)
    tiers = sorted({int(g.tier) for g in spec.gates})
    head = [
        f"-- eq_s3d export: takes over the EXISTING zone '{short}' (version 0).",
        f"-- Target short name: {short}. Rows are found by short name; no zone id is changed.",
        "-- This script CHANGES that zone's server rows. Before applying it, back up:",
        f"--   the zone row (zone WHERE short_name='{short}' AND version=0),",
        f"--   its doors rows (doors WHERE zone='{short}' AND version=0)"
        + ("," if clear_spawns else "."),
    ]
    if clear_spawns:
        head += [
            "--   and its spawn rows: spawn2 and ground_spawns (version 0), grid and",
            "--   grid_entries (by the zone row's zoneidnumber).",
        ]
    head += [
        "-- It sets the zone's safe point and underworld, replaces its doors with one",
        f"-- locked door per Gate ({len(doors)} here)"
        + (", and deletes its spawns." if clear_spawns else "; spawns are left alone."),
        "-- Fog, clip planes, sky and the rest of the zone row stay as they are.",
    ]
    if doors:
        head += ["-- KEY ITEMS: each door's keyitem is a PLACEHOLDER; set real key item ids:"]
        head += [f"--   tier {t}: keyitem {KEYITEM_PLACEHOLDER_BASE + t}" for t in tiers]
        head += ["-- Doors are unpickable (lockpick "
                 f"{LOCKPICK_UNPICKABLE}); only the key opens them."]
    head += ["-- Nothing here was run against a database; review it, then apply it yourself."]

    body = [
        "START TRANSACTION;",
        f"UPDATE zone SET safe_x={_f(sx)}, safe_y={_f(sy)}, safe_z={_f(sz)}, "
        f"underworld={_f(underworld)} WHERE short_name={q} AND version=0;",
        f"DELETE FROM doors WHERE zone={q} AND version=0;",
    ]
    for row in doors:
        cols = ", ".join(row)
        vals = ", ".join(_lit(v) for v in row.values())
        body.append(f"INSERT INTO doors ({cols}) VALUES ({vals});")
    if clear_spawns:
        zone_id = f"(SELECT zoneidnumber FROM zone WHERE short_name={q} AND version=0)"
        for table, col, has_version in SPAWN_TABLES:
            where = f"{col}={q}" if col == "zone" else f"{col} IN {zone_id}"
            if has_version:
                where += " AND version=0"
            body.append(f"DELETE FROM {table} WHERE {where};")
    body.append("COMMIT;")
    return "\n".join(head + body) + "\n"
