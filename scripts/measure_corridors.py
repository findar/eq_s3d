"""
scripts/measure_corridors.py
----------------------------
Repro / measurement harness for the corridor-connection task.

For a given seed it generates a dungeon, builds the per-corridor mesh, and for
each corridor reports:

  - the wall-facing axis of each opening (E/W vs N/S),
  - whether the pair is same-axis (parallel walls), cross-axis, or collinear,
  - the corridor floor Z at EACH opening vs that room's floor_z, measured with a
    NEAREST-vertex probe (not a wide window — a wide window gave a misleading
    "ramp gap" reading before), and
  - the ramp slope (degrees) / stair step height for elevation corridors.

Usage::

    python -m scripts.measure_corridors 1955208177
    python -m scripts.measure_corridors            # sweeps the pinned seeds
"""

from __future__ import annotations

import math
import sys
from typing import Optional

from generators.layout import LayoutGenerator
from generators.geometry import MeshBuilder, _ensure_materials
from generators.zone_spec import ZoneSpec, RoomSpec, CorridorSpec


PINNED = [1955208177, 1516796975, 678358326, 481893615]

# A player is ~6u tall; a comfortable step is <= ~a player step. Grades over
# ~35deg read as a cliff in the viewer.
WALKABLE_GRADE_DEG = 35.0
MAX_STEP_RISE = 12.0


def _wall_axis(room: RoomSpec, toward: RoomSpec) -> str:
    dx = toward.center_x - room.center_x
    dy = toward.center_y - room.center_y
    if abs(dx) >= abs(dy):
        return "E" if dx > 0 else "W"
    return "N" if dy > 0 else "S"


def _opening_point(room: RoomSpec, toward: RoomSpec):
    dx = toward.center_x - room.center_x
    dy = toward.center_y - room.center_y
    hw, hd = room.width / 2, room.depth / 2
    inset = 2.0
    if abs(dx) >= abs(dy):
        return room.center_x + (hw - inset) * (1 if dx > 0 else -1), room.center_y
    return room.center_x, room.center_y + (hd - inset) * (1 if dy > 0 else -1)


def _floor_z_at(mb: MeshBuilder, px: float, py: float, wall: str,
                tol: float = 1.5) -> Optional[float]:
    """
    Floor (+Z normal) height where the corridor meets an opening.

    The opening sits on a wall plane; the corridor's end stub meets it
    PERPENDICULARLY, so the floor vertices that actually land on the opening
    share the wall's run coordinate (x for an E/W wall, y for an N/S wall). A
    plain nearest-XY probe can instead latch onto a nearby stair-tread edge of
    the middle jog and read a false gap, so constrain the probe to the wall
    line and then take the nearest vertex along it.
    """
    on_x_wall = wall in ("E", "W")   # vertical plane at constant x
    best_d = float("inf")
    best_z = None
    for v in mb.vertices:
        if v.nz <= 0.5:
            continue
        if on_x_wall:
            if abs(v.x - px) > tol:
                continue
            d = (v.y - py) ** 2
        else:
            if abs(v.y - py) > tol:
                continue
            d = (v.x - px) ** 2
        if d < best_d:
            best_d = d
            best_z = v.z
    return best_z


def _max_floor_slope(mb: MeshBuilder) -> float:
    """
    Steepest slope (|rise| / horizontal run) of any floor (+Z) triangle in the
    mesh — the grade the player actually walks. Flat treads/landings read 0.
    """
    worst = 0.0
    for p in mb.polygons:
        vs = [mb.vertices[p.v1], mb.vertices[p.v2], mb.vertices[p.v3]]
        # Floor-ish triangle: all three normals point mostly up.
        if any(v.nz <= 0.5 for v in vs):
            continue
        zspan = max(v.z for v in vs) - min(v.z for v in vs)
        if zspan < 1e-6:
            continue
        hx = max(v.x for v in vs) - min(v.x for v in vs)
        hy = max(v.y for v in vs) - min(v.y for v in vs)
        run = math.hypot(hx, hy)
        if run > 1e-6:
            worst = max(worst, zspan / run)
    return worst


def measure_seed(seed: int) -> int:
    spec = LayoutGenerator(theme="dungeon", seed=seed).generate("meas", room_count=9)
    _ensure_materials(spec)
    rooms = {r.id: r for r in spec.rooms}

    print(f"\n=== seed {seed} : {len(spec.rooms)} rooms, "
          f"{len(spec.corridors)} corridors ===")
    problems = 0
    for cor in spec.corridors:
        a = rooms.get(cor.from_room)
        b = rooms.get(cor.to_room)
        if a is None or b is None:
            continue

        mb = MeshBuilder()
        mb.add_corridor(cor, spec)

        wa = _wall_axis(a, b)
        wb = _wall_axis(b, a)
        a_is_x = wa in ("E", "W")
        b_is_x = wb in ("E", "W")
        if a_is_x == b_is_x:
            kind = "same-axis"
        else:
            kind = "cross-axis"

        oax, oay = _opening_point(a, b)
        obx, oby = _opening_point(b, a)
        za = _floor_z_at(mb, oax, oay, wa)
        zb = _floor_z_at(mb, obx, oby, wb)
        gap_a = None if za is None else abs(za - a.floor_z)
        gap_b = None if zb is None else abs(zb - b.floor_z)

        # Elevation metrics, measured from the ACTUAL mesh (not the straight-
        # line endpoint delta, which ignores where the rise really rides).
        dz = cor.to_z - cor.from_z
        if abs(dz) > 0.5:
            if cor.steps > 0:
                step_rise = abs(dz) / cor.steps
                elev = f"stairs dz={dz:+.0f} {cor.steps}steps {step_rise:.1f}u/step"
                bad_elev = step_rise > MAX_STEP_RISE
            else:
                grade = math.degrees(math.atan(_max_floor_slope(mb)))
                elev = f"ramp dz={dz:+.0f} {grade:.0f}deg"
                bad_elev = grade > WALKABLE_GRADE_DEG
        else:
            elev = "flat"
            bad_elev = False

        flags = []
        if gap_a is not None and gap_a > 2.0:
            flags.append(f"GAP@{a.id}={gap_a:.0f}u")
        if gap_b is not None and gap_b > 2.0:
            flags.append(f"GAP@{b.id}={gap_b:.0f}u")
        if bad_elev:
            flags.append("STEEP")
        if flags:
            problems += 1
        flagstr = ("  <<< " + ", ".join(flags)) if flags else ""

        print(f"  {cor.id}: {a.id}[{wa}]->{b.id}[{wb}] {kind:10s} {elev}")
        print(f"       floorZ @{a.id}={za} (room {a.floor_z:.0f}) "
              f"@{b.id}={zb} (room {b.floor_z:.0f}){flagstr}")

    print(f"  -> {problems} corridor(s) with problems")
    return problems


def main() -> None:
    seeds = [int(s) for s in sys.argv[1:]] or PINNED
    total = 0
    for s in seeds:
        total += measure_seed(s)
    print(f"\nTOTAL problem corridors across {len(seeds)} seed(s): {total}")


if __name__ == "__main__":
    main()
