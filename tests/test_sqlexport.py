"""The SQL script (step 17 task 4, Requirement 3; umbrella 10.1-10.3, 10.5-10.8, 10.10 as
amended by A1).

The script is applied to an in-memory SQLite database of the pinned ``zone``/``doors`` columns
(archive decision 4) and the four spawn tables, seeded with stock rows for ``arena`` and two other
short names. SQLite says ``BEGIN`` where MySQL says ``START TRANSACTION``; that keyword is the only
thing the test adapts.
"""

from __future__ import annotations

import math
import re
import sqlite3

import pytest

from generators.sqlexport import (
    DOORS_COLUMNS, KEYITEM_PLACEHOLDER_BASE, LOCKPICK_UNPICKABLE, QUARTER_TURN,
    UNDERWORLD_MARGIN, ZONE_COLUMNS, SqlExportError, export_sql,
)
from generators.zone_spec import CorridorSpec, GateSpec, RoomSpec, ZoneSpec

SHORT = "arena"
OTHERS = ("freporte", "qeynos")
ZONE_IDS = {"arena": 77, "freporte": 10, "qeynos": 1}
MIN_Z = -12.0

#: The pinned spawn tables' columns (EQEmu/Server base repositories, 2026-11-16).
SPAWN_COLUMNS = {
    "spawn2": "id spawngroupID zone version x y z heading respawntime variance pathgrid "
              "path_when_zone_idle _condition cond_value animation min_expansion max_expansion "
              "content_flags content_flags_disabled",
    "grid": "id zoneid type type2",
    "grid_entries": "gridid zoneid number x y z heading pause centerpoint",
    "ground_spawns": "id zoneid version max_x max_y max_z min_x min_y heading name item "
                     "max_allowed comment respawn_timer fix_z min_expansion max_expansion "
                     "content_flags content_flags_disabled",
}


def _spec(gates: bool = True) -> ZoneSpec:
    """Three rooms in an L: an X-running corridor (width 50) and a Y-running one (width 30)."""
    spec = ZoneSpec(name="gen_test")
    spec.safe_point = (12.5, -40.25, 3.0)
    spec.rooms = [
        RoomSpec("a", 0, 0, width=200, depth=200, height=80),
        RoomSpec("b", 400, 0, width=200, depth=200, height=80),
        RoomSpec("c", 400, 400, width=200, depth=200, height=80),
    ]
    spec.corridors = [
        CorridorSpec("corr_0", 100, 0, 300, 0, width=50, from_room="a", to_room="b"),
        CorridorSpec("corr_1", 400, 100, 400, 300, from_z=0, to_z=20, width=30,
                     from_room="b", to_room="c"),
    ]
    if gates:
        spec.gates = [   # listed out of tier order on purpose
            GateSpec("gate_1", "corr_1", 400, 200, 10, "b", 400, 0, 5, tier=1),
            GateSpec("gate_0", "corr_0", 200, 0, 0, "a", 0, 0, 5, tier=0),
        ]
    return spec


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:", isolation_level=None)
    zcols = ", ".join(("id INTEGER PRIMARY KEY AUTOINCREMENT" if c == "id" else c)
                      for c in ZONE_COLUMNS)
    con.execute(f"CREATE TABLE zone ({zcols})")
    dcols = ", ".join(("id INTEGER PRIMARY KEY AUTOINCREMENT" if c == "id"
                       else f"{c} DEFAULT {d!r}" if isinstance(d, str) else f"{c} DEFAULT {d}")
                      for c, d in DOORS_COLUMNS)
    con.execute(f"CREATE TABLE doors ({dcols})")
    for table, cols in SPAWN_COLUMNS.items():
        con.execute(f"CREATE TABLE {table} ({', '.join(cols.split())})")
    for short in (SHORT, *OTHERS):
        zid = ZONE_IDS[short]
        for version in (0, 1):
            con.execute("INSERT INTO zone (zoneidnumber, version, short_name, long_name, "
                        "safe_x, safe_y, safe_z, safe_heading, underworld, fog_red, sky) "
                        "VALUES (?, ?, ?, ?, 1, 2, 3, 64, -5000, 7, 2)",
                        (zid, version, short, short.title()))
        for doorid in (1, 2, 3):
            for version in (0, 1):
                con.execute("INSERT INTO doors (doorid, zone, version, name, pos_x, pos_y, pos_z) "
                            "VALUES (?, ?, ?, 'ARENADOOR200', ?, ?, 0)",
                            (doorid, short, version, doorid * 10.0, -doorid * 10.0))
        for version in (0, 1):
            con.execute("INSERT INTO spawn2 (spawngroupID, zone, version, x, y, z) "
                        "VALUES (5, ?, ?, 1, 2, 3)", (short, version))
            con.execute("INSERT INTO ground_spawns (zoneid, version, name, item) "
                        "VALUES (?, ?, 'x', 13)", (zid, version))
        con.execute("INSERT INTO grid (id, zoneid, type, type2) VALUES (1, ?, 0, 0)", (zid,))
        con.execute("INSERT INTO grid_entries (gridid, zoneid, number, x, y, z) "
                    "VALUES (1, ?, 1, 0, 0, 0)", (zid,))
    return con


def _apply(con: sqlite3.Connection, sql: str) -> None:
    assert sql.count("START TRANSACTION;") == 1
    con.executescript(sql.replace("START TRANSACTION;", "BEGIN;"))


def _dump(con, table, where="1=1", args=()):
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(f"SELECT * FROM {table} WHERE {where} ORDER BY rowid",
                                         args)]
    con.row_factory = None
    for r in rows:
        r.pop("id", None)
    return rows


def _others(con):
    out = {}
    for short in OTHERS:
        zid = ZONE_IDS[short]
        out[short] = (_dump(con, "zone", "short_name=?", (short,)),
                      _dump(con, "doors", "zone=?", (short,)),
                      _dump(con, "spawn2", "zone=?", (short,)),
                      *(_dump(con, t, "zoneid=?", (zid,))
                        for t in ("grid", "grid_entries", "ground_spawns")))
    return out


def _statements(sql: str):
    return [ln for ln in sql.splitlines() if ln and not ln.startswith("--")]


# ---------------------------------------------------------------------------


@pytest.mark.parametrize("times", [1, 2])
def test_apply_once_and_twice_without_spawn_cleanup(times):
    con = _db()
    before_others = _others(con)
    before_zone = _dump(con, "zone", "short_name=?", (SHORT,))
    before_spawns = [_dump(con, t, "zoneid=?", (77,)) for t in ("grid", "grid_entries",
                                                                 "ground_spawns")]
    sql = export_sql(_spec(), SHORT, bounds_min_z=MIN_Z)
    for _ in range(times):
        _apply(con, sql)

    zone = _dump(con, "zone", "short_name=? AND version=0", (SHORT,))
    assert len(zone) == 1
    z = zone[0]
    assert (z["safe_x"], z["safe_y"], z["safe_z"]) == (12.5, -40.25, 3.0)
    assert z["underworld"] == MIN_Z - UNDERWORLD_MARGIN
    # Nothing else in the row changed: zone id, heading, fog, sky stay stock.
    expected = dict(before_zone[0], safe_x=12.5, safe_y=-40.25, safe_z=3.0,
                    underworld=MIN_Z - UNDERWORLD_MARGIN)
    assert z == expected
    assert _dump(con, "zone", "short_name=? AND version=1", (SHORT,)) == [before_zone[1]]
    assert con.execute("SELECT COUNT(*) FROM zone").fetchone()[0] == 6

    doors = _dump(con, "doors", "zone=? AND version=0", (SHORT,))
    assert len(doors) == 2                                  # one per Gate, only ours
    assert [d["doorid"] for d in doors] == [1, 2]          # by tier
    assert {d["name"] for d in doors} == {"OBJ_BBDOOR1"}
    assert [d["keyitem"] for d in doors] == [KEYITEM_PLACEHOLDER_BASE,
                                             KEYITEM_PLACEHOLDER_BASE + 1]
    assert all(d["lockpick"] == LOCKPICK_UNPICKABLE for d in doors)
    assert [d["pos_z"] for d in doors] == [0.0, 0.0]          # each at its doorway's floor
    assert len(_dump(con, "doors", "zone=? AND version=1", (SHORT,))) == 3

    assert _others(con) == before_others
    # Without spawn cleanup the spawn tables are never named, and arena's spawns stay.
    for table in SPAWN_COLUMNS:
        assert table not in sql
    assert len(_dump(con, "spawn2", "zone=?", (SHORT,))) == 2
    assert [_dump(con, t, "zoneid=?", (77,)) for t in ("grid", "grid_entries",
                                                        "ground_spawns")] == before_spawns


@pytest.mark.parametrize("times", [1, 2])
def test_spawn_cleanup_empties_only_the_targets_spawns(times):
    con = _db()
    before_others = _others(con)
    sql = export_sql(_spec(), SHORT, bounds_min_z=MIN_Z, clear_spawns=True)
    for _ in range(times):
        _apply(con, sql)
    assert _dump(con, "spawn2", "zone=? AND version=0", (SHORT,)) == []
    assert len(_dump(con, "spawn2", "zone=? AND version=1", (SHORT,))) == 1
    assert _dump(con, "ground_spawns", "zoneid=77 AND version=0") == []
    assert _dump(con, "grid", "zoneid=77") == []
    assert _dump(con, "grid_entries", "zoneid=77") == []
    assert _others(con) == before_others
    assert len(_dump(con, "doors", "zone=? AND version=0", (SHORT,))) == 2


def _slab(d, door_width=10.0):
    """A door row's hinge and far end in plan. The hinge is at the row's position; turned by
    -heading (EQ: clockwise, 512 a turn, task 4's convention, unverified in the client) the
    slab's far end (local -y, door width x scale) lands on the opposite jamb."""
    reach = door_width * d["size"] / 100.0
    a = -d["heading"] * 2 * math.pi / 512.0           # local (0, -reach) turned by a
    near = (d["pos_x"], d["pos_y"])
    return near, (d["pos_x"] + reach * math.sin(a), d["pos_y"] - reach * math.cos(a))


def test_doors_span_the_doorway_from_one_jamb():
    con = _db()
    _apply(con, export_sql(_spec(), SHORT, bounds_min_z=MIN_Z))
    doors = _dump(con, "doors", "zone=? AND version=0", (SHORT,))
    # Both locks sit midway, so each door takes the from end's doorway: corr_0 leaves room a
    # through its E wall (x 100, along X, width 50); corr_1 leaves b through its N wall
    # (y 100, along Y, width 30) on the ramp's low end.
    for d, (mx, my, width, heading) in zip(doors, [(100, 0, 50, 0.0),
                                                  (400, 100, 30, QUARTER_TURN)]):
        assert d["heading"] == heading
        assert d["size"] == round(100 * width / 10.0)
        assert (d["opentype"], d["incline"]) == (0, 0)
        near, far = _slab(d)
        mid = ((near[0] + far[0]) / 2, (near[1] + far[1]) / 2)
        assert mid == pytest.approx((mx, my))
        assert math.dist(near, far) == pytest.approx(width)
    # A lock nearer the far end moves the door there, onto that doorway's own floor.
    spec = _spec()
    spec.gates[0].lock_y = 280                        # gate_1, on corr_1 near room c
    _apply(con, export_sql(spec, SHORT, bounds_min_z=MIN_Z))
    d = _dump(con, "doors", "zone=? AND version=0 AND doorid=2", (SHORT,))[0]
    near, far = _slab(d)
    assert ((near[0] + far[0]) / 2, near[1], far[1]) == pytest.approx((400, 300, 300))
    assert d["pos_z"] == 20.0
    # A wider door model makes a smaller scale.
    sql = export_sql(_spec(), SHORT, bounds_min_z=MIN_Z, door_width=25.0, door_model="OBJ_X")
    assert "'OBJ_X'" in sql and ", 200, " in sql            # 100 * 50 / 25


def test_no_gates_gets_the_delete_and_no_inserts():
    con = _db()
    sql = export_sql(_spec(gates=False), SHORT, bounds_min_z=MIN_Z)
    assert "DELETE FROM doors WHERE zone='arena' AND version=0;" in sql
    assert "INSERT" not in sql
    _apply(con, sql)
    assert _dump(con, "doors", "zone=? AND version=0", (SHORT,)) == []


def test_header_is_comments_naming_the_short_name_and_one_transaction_wraps_it():
    sql = export_sql(_spec(), SHORT, bounds_min_z=MIN_Z, clear_spawns=True)
    lines = sql.splitlines()
    first = next(i for i, ln in enumerate(lines) if not ln.startswith("--"))
    header = lines[:first]
    assert header and all(ln.startswith("-- ") for ln in header)
    assert any("arena" in ln for ln in header)
    assert any("back up" in ln for ln in header)
    assert any("keyitem" in ln and str(KEYITEM_PLACEHOLDER_BASE + 1) in ln for ln in header)
    stmts = _statements(sql)
    assert stmts[0] == "START TRANSACTION;" and stmts[-1] == "COMMIT;"
    assert sum(s in ("START TRANSACTION;", "COMMIT;", "BEGIN;") for s in stmts) == 2
    assert all(s.endswith(";") for s in stmts)
    # Exactly one zone UPDATE, by short name and version 0; no zone insert, no zone id set.
    assert [s for s in stmts if s.startswith("UPDATE zone")] == [stmts[1]]
    assert stmts[1].endswith("WHERE short_name='arena' AND version=0;")
    assert "INSERT INTO zone" not in sql
    assert not re.search(r"SET[^;]*zoneidnumber", sql)


def test_only_pinned_columns_are_written():
    sql = export_sql(_spec(), SHORT, bounds_min_z=MIN_Z)
    assert len(DOORS_COLUMNS) == 37 and len(ZONE_COLUMNS) == 99
    pinned = {c for c, _ in DOORS_COLUMNS}
    for m in re.finditer(r"INSERT INTO doors \(([^)]*)\)", sql):
        cols = [c.strip() for c in m.group(1).split(",")]
        assert set(cols) <= pinned and "id" not in cols
    sets = re.search(r"UPDATE zone SET (.*) WHERE", sql).group(1)
    assert [p.split("=")[0] for p in sets.split(", ")] == ["safe_x", "safe_y", "safe_z",
                                                           "underworld"]


@pytest.mark.parametrize("mutate, field", [
    (lambda s: setattr(s, "safe_point", (0.0, math.nan, 0.0)), "safe_point[1]"),
    (lambda s: setattr(s.gates[0], "lock_x", math.inf), "gates[gate_1].lock_x"),
    (lambda s: setattr(s.corridors[0], "width", -math.inf), "corridors[corr_0].width"),
])
def test_non_finite_value_writes_no_script_and_names_the_field(mutate, field):
    spec = _spec()
    mutate(spec)
    with pytest.raises(SqlExportError) as err:
        export_sql(spec, SHORT, bounds_min_z=MIN_Z)
    assert err.value.field == field and field in str(err.value)
    with pytest.raises(SqlExportError, match="bounds_min_z"):
        export_sql(_spec(), SHORT, bounds_min_z=math.nan)


def test_unknown_short_name_is_refused_by_name():
    with pytest.raises(SqlExportError, match="notazone") as err:
        export_sql(_spec(), "notazone", bounds_min_z=MIN_Z)
    assert err.value.field == "shortname"
    with pytest.raises(SqlExportError):
        export_sql(_spec(), "arena'; DROP TABLE zone; --", bounds_min_z=MIN_Z)
    assert "short_name='arena'" in export_sql(_spec(), " ARENA ", bounds_min_z=MIN_Z)


# ---------------------------------------------------------------------------
# Amendment A3 (task 12): on generated dungeons each door stands in a doorway the geometry cut.

SWEEP_SEEDS = range(40)


def _doorways(spec):
    """Every doorway geometry cuts, as (room, along_x, plane, c0, c1, floor) with
    ``geometry._door_openings``: c0..c1 the span along the wall, floor its ceiling less the
    corridor's height (every corridor here is one height)."""
    from generators.geometry import _door_openings

    height = {c.height for c in spec.corridors}
    assert len(height) == 1
    h = height.pop()
    out = []
    for room in spec.rooms:
        (x0, y0, _), (x1, y1, _) = room.bounds
        planes = {"E": (True, x1), "W": (True, x0), "N": (False, y1), "S": (False, y0)}
        for side, cuts in _door_openings(room, spec).items():
            along_x, plane = planes[side]
            out += [(room.id, along_x, plane, c0, c1, top - h) for c0, c1, top in cuts]
    return out


def test_doors_stand_in_their_corridors_doorways_on_40_dungeons():
    from generators.layout import LayoutGenerator

    placed = 0
    for seed in SWEEP_SEEDS:
        spec = LayoutGenerator(zone_type="dungeon", seed=seed).generate(
            "sweep", room_count=12, locks=3)
        sql = export_sql(spec, SHORT, bounds_min_z=MIN_Z)
        con = _db()
        _apply(con, sql)
        doors = _dump(con, "doors", "zone=? AND version=0", (SHORT,))
        gates = sorted(spec.gates, key=lambda g: (g.tier, g.id))
        assert len(doors) == len(gates) == 3, seed
        corridors = {c.id: c for c in spec.corridors}
        doorways = _doorways(spec)
        for d, g in zip(doors, gates):
            cor = corridors[g.corridor_id]
            near, far = _slab(d)
            along_x = d["heading"] == 0.0
            plane = near[0] if along_x else near[1]
            span = sorted((near[1], far[1]) if along_x else (near[0], far[0]))
            assert abs((far[0] if along_x else far[1]) - plane) < 1e-6, seed
            hits = [w for w in doorways
                    if w[0] in (cor.from_room, cor.to_room) and w[1] == along_x
                    and abs(w[2] - plane) <= 1.0                         # on the doorway's line
                    and abs(w[3] - span[0]) <= 1.0 and abs(w[4] - span[1]) <= 1.0   # jamb to jamb
                    and abs(w[5] - d["pos_z"]) <= 0.01]                 # on its floor
            assert hits, (seed, g.id, d)
            placed += 1
        # The Gates' locks are still where the layout put them, for the map and the sidecar.
        for g in gates:
            cor = corridors[g.corridor_id]
            assert (g.lock_x, g.lock_y) == ((cor.from_x + cor.to_x) / 2,
                                            (cor.from_y + cor.to_y) / 2)
    assert placed == 3 * len(SWEEP_SEEDS)