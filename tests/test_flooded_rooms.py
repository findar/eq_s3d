"""A flooded room's water fills its floor (flooded-rooms spec, Requirements 1-3).

Before step 24 a flooded room had one water region, a centred box 0.76 of the room, and no
visible water, so the viewer showed a square in the room's middle.
"""

import functools

import numpy as np
import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from core.ter import FLAG_PASSABLE
from generators.geometry import build_mesh
from generators.semantics import FLOOD_MATERIAL, flood_level

BUILDS = [("cave", "graph", 731402518, 12, "moderate"), ("cave", "graph", 23, 12, "dramatic"),
          ("cave", "classic", 731402518, 12, "moderate"), ("sunken_ruin", "graph", 5, 14, "moderate"),
          ("sunken_ruin", "classic", 7, 10, "flat")]


@functools.lru_cache(maxsize=None)
def _built(theme, layout, seed, rooms, verticality):
    plan = ZonePlan.from_controls({"zone_type": "dungeon", "dungeon_theme": theme, "layout": layout,
                                   "room_count": rooms, "verticality": verticality}, [])
    plan.name = f"fl_{theme}{seed}"
    spec = plan_to_spec(plan, seed=seed, warnings=[])
    return spec, build_mesh(spec).to_ter("fl")


def _poly_area(pts):
    x, y = np.array(pts, dtype=float).T
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def _floor_area(room):
    """The floor's area as the mesh builds it: each Cell fanned from its centre."""
    if room.outline is None:
        return room.width * room.depth
    area = 0.0
    for cell in room.outline.cells:
        pts = [room.outline.verts[i] for i in cell]
        c = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
        area += sum(_poly_area([c, a, b]) for a, b in zip(pts, pts[1:] + pts[:1]))
    return area


@pytest.mark.parametrize("build", BUILDS, ids=lambda b: f"{b[0]}-{b[1]}-{b[2]}")
def test_water_fills_each_flooded_room(build):
    spec, ter = _built(*build)
    flooded = [r for r in spec.rooms if flood_level(r, spec) is not None]
    assert flooded, "the build has no flooded room to check"
    mat = next(m.index for m in ter.materials if m.name == FLOOD_MATERIAL)
    water = [p for p in ter.polygons if p.material == mat]
    assert all(p.flags & FLAG_PASSABLE for p in water)
    V = np.array([(v.x, v.y, v.z) for v in ter.vertices])
    for room in flooded:
        level = flood_level(room, spec)
        (x0, y0, z0), (x1, y1, z1) = room.bounds
        # In the room's box, Z too: a stacked build's rooms on other Levels can
        # overlap it in plan (random placement task 11: sunken_ruin graph 5's
        # room_4 over room_8).
        mine = [p for p in water
                if all(x0 - 0.01 <= V[i, 0] <= x1 + 0.01 and y0 - 0.01 <= V[i, 1] <= y1 + 0.01
                       and z0 - 0.01 <= V[i, 2] <= z1 + 0.01
                       for i in (p.v1, p.v2, p.v3))]
        assert mine, f"{room.id} has no water surface"
        zs = V[[i for p in mine for i in (p.v1, p.v2, p.v3)], 2]
        assert np.allclose(zs, level), f"{room.id}'s water is not flat at its water line"
        area = sum(_poly_area(V[[p.v1, p.v2, p.v3], :2]) for p in mine)
        # float32 vertices: a few parts in a million.
        assert area == pytest.approx(_floor_area(room), rel=1e-5), f"{room.id}'s water misses floor"


@pytest.mark.parametrize("build", BUILDS, ids=lambda b: f"{b[0]}-{b[1]}-{b[2]}")
def test_water_region_matches_the_water(build):
    spec, _ = _built(*build)
    regions = {(round(g.center_x, 3), round(g.center_y, 3)): g for g in spec.regions if g.kind == "water"}
    for room in spec.rooms:
        level = flood_level(room, spec)
        if level is None:
            continue
        g = regions[(round(room.center_x, 3), round(room.center_y, 3))]
        assert (g.extent_x, g.extent_y) == pytest.approx((room.width / 2, room.depth / 2))
        assert g.center_z + g.extent_z == pytest.approx(level)
        assert g.center_z - g.extent_z < room.floor_z


def test_decor_reads_the_floor_under_the_water():
    """Decor's room grid is the floor, not the water over it (a flooded room's surface is
    non-collidable). Reading the water lifted Props and the treasure POI 3.6 u off the floor,
    and the room gate failed them (footprint_cut, poi_unreached) on 30 cave builds."""
    from generators.room_context import contexts
    spec, ter = _built("cave", "graph", 731402518, 12, "moderate")
    by_id = {c.id: c for c in contexts(spec, ter)}
    for room in spec.rooms:
        level = flood_level(room, spec)
        if level is None:
            continue
        floor = by_id[room.id].floor
        assert np.nanmax(floor) < level - 0.5 or np.nanmin(floor) < level - 0.5
        assert np.nanmin(floor) == pytest.approx(room.floor_z, abs=0.5)
