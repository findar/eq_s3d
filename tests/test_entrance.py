"""Outdoor-dungeon task 5: the Entrance (Apron, Tunnel and Mouth) and the
merged TER. Properties D3 and D5 of the outdoor-dungeon design."""

import collections

import numpy as np
import pytest

from analyzer.traverse import (AgentModel, _faces_in_room, build_walk_surface,
                               flood_reachable, seed_face_for)
from generators import outdoor_dungeon as od
from generators.wilderness.build import build_wilderness_ter, wilderness_spec
from generators.wilderness.matrix import DEFAULT_HOST_HILL, OUTDOOR_DUNGEON_ZONE_SIZE

CASES = [(seed, edges) for seed in (0, 3, 7)
         for edges in (None, {"N": "zoneline"}, {"E": "river", "S": "zoneline"})]


def _build(seed, edges):
    host = wilderness_spec("hill", seed, edges, landform=DEFAULT_HOST_HILL,
                           zone_size=OUTDOOR_DUNGEON_ZONE_SIZE)
    ter = build_wilderness_ter(host, "hill", 1)
    dungeon, warnings = od.layout_in_envelope("d", seed * 7 + 1, od.host_envelope(host, ter))
    first = next(r.id for r in dungeon.rooms if r.role == "entrance")
    entrance = od.plan_entrance(host, ter, dungeon, room_id=first)
    merged = od.build_outdoor_ter(host, ter, dungeon, entrance, "zone")
    return host, ter, dungeon, entrance, merged


@pytest.fixture(scope="module", params=CASES, ids=lambda c: f"{c[0]}-{c[1]}")
def built(request):
    return _build(*request.param)


def _key(v):
    return (round(v.x, 3), round(v.y, 3), round(v.z, 3))


def test_terrain_unchanged_outside_apron_and_mouth(built):
    """D3: only the Apron trench's vertices move, and only down (its two
    edge vertices may sit exactly at the Apron floor); one terrain cell is
    cut for the Mouth."""
    host, ter, _dungeon, e, merged = built
    grid = od._host_grid(host, ter)
    before = grid.z
    after = np.array([v.z for v in merged.vertices[:grid.nx * grid.ny]]).reshape(before.shape)
    trench = np.zeros(before.shape, bool)
    for step in range(od.APRON_REACH + 1):
        k = e.portal + e.outward * (1 + step)
        for c in range(e.cross - 1, e.cross + 3):
            if 0 <= k < grid.size(e.axis) and 0 <= c < grid.size(1 - e.axis):
                trench[grid.ij(e.axis, k, c)] = True
    edge = [grid.ij(e.axis, e.portal + e.outward, c) for c in (e.cross, e.cross + 1)]
    assert np.array_equal(after[~trench], before[~trench])
    moved = after != before
    for ij in zip(*np.nonzero(moved)):
        assert ij in edge or after[ij] < before[ij]
    assert moved.any()
    # The terrain's triangles are all kept, by index, but the notch cell's two.
    kept = [(p.v1, p.v2, p.v3) for p in merged.polygons[:len(ter.polygons) - 2]]
    host_tris = [(p.v1, p.v2, p.v3) for p in ter.polygons]
    cut = [t for t in host_tris if t not in set(kept)]
    assert len(cut) == 2
    corners = {np.ravel_multi_index(grid.ij(e.axis, r, c), before.shape)
               for r in (e.portal, e.portal + e.outward) for c in (e.cross, e.cross + 1)}
    assert all(set(t) <= corners for t in cut)


def test_tunnel_floor_meets_apron_flush(built):
    """D5: the Apron's edge, the Mouth's floor and the Tunnel's end all sit at
    the Entrance floor, and the headwall keeps the Rock_Cover over the
    Tunnel."""
    host, ter, _dungeon, e, merged = built
    grid = od._host_grid(host, ter)
    for c in (e.cross, e.cross + 1):
        assert merged.vertices[np.ravel_multi_index(
            grid.ij(e.axis, e.portal + e.outward, c), (grid.nx, grid.ny))].z == e.floor
    floor_faces = [merged.polygons[k] for k in od.mouth_faces(ter)][:2]
    assert all(merged.vertices[i].z == e.floor
               for p in floor_faces for i in (p.v1, p.v2, p.v3))
    portal = grid.coord(e.axis, e.portal)
    lo, hi = grid.coord(1 - e.axis, e.cross), grid.coord(1 - e.axis, e.cross + 1)
    tunnel_end = [v for v in merged.vertices[len(ter.vertices) + 3 * od.MOUTH_FACES:]
                  if abs((v.x, v.y)[e.axis] - portal) < 1e-6
                  and lo - 1e-6 <= (v.x, v.y)[1 - e.axis] <= hi + 1e-6]
    assert tunnel_end and min(v.z for v in tunnel_end) == pytest.approx(e.floor)
    crest = min(grid.z[grid.ij(e.axis, e.portal, c)] for c in (e.cross, e.cross + 1))
    assert crest >= e.floor + e.height + od.ROCK_COVER - 1e-6


def test_mouth_is_stitched(built):
    """D5: every edge of the Mouth's triangles is shared with exactly one
    other triangle (terrain, the other Mouth pieces or the Tunnel's end), so
    nothing can be fallen or seen through around the portal."""
    _host, ter, _dungeon, _e, merged = built
    count = collections.Counter()
    for p in merged.polygons:
        ks = [_key(merged.vertices[i]) for i in (p.v1, p.v2, p.v3)]
        for a, b in ((0, 1), (1, 2), (2, 0)):
            count[frozenset((ks[a], ks[b]))] += 1
    for k in od.mouth_faces(ter):
        p = merged.polygons[k]
        ks = [_key(merged.vertices[i]) for i in (p.v1, p.v2, p.v3)]
        for a, b in ((0, 1), (1, 2), (2, 0)):
            assert count[frozenset((ks[a], ks[b]))] == 2, (k, ks[a], ks[b])


def test_every_room_reached_from_outdoors(built):
    """The walk agent gets from the outdoor Spawn through the Mouth to every
    room."""
    host, _ter, dungeon, _e, merged = built
    surf = build_walk_surface(merged, AgentModel())
    reached = flood_reachable(surf, seed_face_for(surf, host.safe_point))
    for room in dungeon.rooms:
        assert set(_faces_in_room(surf, room).tolist()) & reached, room.id


def test_tunnel_opens_into_the_entrance_room(built):
    """The way in is the start of the pacing ("Entrance first"): the
    Tunnel opens into the room tagged ``entrance``, at graph depth 0, and it
    is the only one. (The layout tags the room nearest the way in before the
    role bias and re-separation move rooms, by design, so after the final
    layout another room can sit nearer the approach foot.)"""
    _host, _, dungeon, entrance, _ = built
    room = next(r for r in dungeon.rooms if r.id == entrance.room_id)
    assert room.role == "entrance"
    assert room.graph_depth == 0
    assert [r.id for r in dungeon.rooms if r.role == "entrance"] == [room.id]


def test_no_landform_no_entrance():
    host = wilderness_spec("plain", 1, None)
    ter = build_wilderness_ter(host, "plain", 1)
    with pytest.raises(od.EntranceError):
        od.plan_entrance(host, ter, host)
