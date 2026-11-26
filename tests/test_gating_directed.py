"""Advisory gates on the directed room graph (district races task 3, requirement 3).

A corridor with a ``drop`` (step 31) is one-way, from the room whose floor is higher to the
other. No layout makes one yet (task 7 adds ``CorridorSpec.drop``), so these graphs are built by
hand: ``solvable`` must accept a key fetched round a one-way loop, refuse one the player can only
fetch by climbing back up a drop, and the layout's gating must never place such a key.
"""

from __future__ import annotations

from generators.edits import solvable
from generators.layout import LayoutGenerator
from generators.zone_spec import CorridorSpec, RoomSpec, ZoneSpec


def _doc(rooms, corridors, gates):
    """A saved spec: ``rooms`` as (id, floor_z, graph_depth), the first the entrance;
    ``corridors`` as (from, to, drop); ``gates`` as (corridor index, key room)."""
    return {
        "rooms": [{"id": r, "floor_z": z, "graph_depth": d,
                   "role": "entrance" if i == 0 else "standard"}
                  for i, (r, z, d) in enumerate(rooms)],
        "corridors": [{"id": f"corr_{k}", "from_room": a, "to_room": b,
                       **({"drop": drop} if drop else {})}
                      for k, (a, b, drop) in enumerate(corridors)],
        "gates": [{"id": f"gate_{t}", "corridor_id": f"corr_{k}", "key_room_id": key}
                  for t, (k, key) in enumerate(gates)],
    }


def test_key_past_a_one_way_loop_is_solvable():
    # e drops into the key room; a flush passage leads on round to b and back up to e. The
    # lock on the way to c opens once the player has come round.
    rooms = [("e", 50.0, 0), ("k", 0.0, 1), ("b", 20.0, 2), ("c", 50.0, 1)]
    corridors = [("e", "k", 30.0), ("k", "b", 0), ("b", "e", 0), ("e", "c", 0)]
    assert solvable(_doc(rooms, corridors, [(3, "k")]))
    # The corridor's own order doesn't matter: the floors set the way down.
    corridors[0] = ("k", "e", 30.0)
    assert solvable(_doc(rooms, corridors, [(3, "k")]))


def test_key_that_needs_climbing_a_drop_is_not():
    # The key is up beside the entrance; the lock is down past a drop, and the way back up
    # runs through the lock. Drop without the key and the player is stranded.
    rooms = [("e", 50.0, 0), ("k", 50.0, 1), ("l", 0.0, 1), ("t", 20.0, 1)]
    corridors = [("e", "k", 0), ("e", "l", 30.0), ("l", "t", 0), ("t", "e", 0)]
    gates = [(2, "k")]
    assert not solvable(_doc(rooms, corridors, gates))
    # The same zone with a flush corridor in place of the drop: walk back up for the key.
    corridors[1] = ("e", "l", 0)
    assert solvable(_doc(rooms, corridors, gates))


def _gate(drops):
    """One lock from the layout's gating on a hand-built loop: e drops to l, l climbs flush to
    t, t drops back to e; k and m hang off e. The lock goes on t's way in (l -> t)."""
    floors = {"e": 50.0, "l": 0.0, "t": 80.0, "k": 50.0, "m": 50.0}
    depth = {"e": 0, "l": 2, "t": 3, "k": 1, "m": 2}
    names = list(floors)
    edges = [(0, 1), (1, 2), (2, 0), (0, 3), (3, 4)]
    spec = ZoneSpec(name="t")
    spec.rooms = [RoomSpec(id=r, center_x=100.0 * i, center_y=0.0, floor_z=floors[r],
                           graph_depth=depth[r]) for i, r in enumerate(names)]
    for k, (i, j) in enumerate(edges):
        spec.corridors.append(CorridorSpec(id=f"corr_{k}", from_x=0, from_y=0, to_x=1, to_y=0,
                                           from_room=names[i], to_room=names[j]))
        if k in drops:
            spec.corridors[k].drop = 30.0          # task 7's field, set by hand
    LayoutGenerator._apply_gating(None, spec, spec.rooms, edges, 0, n_locks=1)
    doc = spec.to_dict()
    for k in drops:
        doc["corridors"][k]["drop"] = 30.0
    return doc


def test_the_layout_never_keys_a_lock_past_a_drop():
    # Two-way, t's way in is straight from e, and the key goes in the shallowest room: k.
    two_way = _gate(drops=())
    assert [(g["corridor_id"], g["key_room_id"]) for g in two_way["gates"]] == [("corr_2", "k")]
    # With the drops, a player who drops to l without k's key is stranded (l's only way on is
    # the lock), so the key goes in l itself.
    one_way = _gate(drops=(0, 2))
    assert [(g["corridor_id"], g["key_room_id"]) for g in one_way["gates"]] == [("corr_1", "l")]
    assert solvable(one_way)
    one_way["gates"][0]["key_room_id"] = "k"
    assert not solvable(one_way)

