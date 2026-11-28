"""
tests/test_layout_engine.py
---------------------------
Graph-layout task 2 (Req 2.2): the LayoutEngine seam changes nothing.

sha256 goldens of the Zone_Spec JSON and the ``.eqg`` contents for pinned
builds of every zone type, captured on the code BEFORE the room-and-graph step
moved behind ``generators/layout_engine.py``. The Zone_Spec golden catches a
change in rng order (the moved code must draw from the generator's rng exactly
as before); the ``.eqg`` golden catches the rest.

The ``.eqg`` is hashed without its last 4 bytes: the PFS footer holds the
write time (lessons-learned "Two `.eqg` writes are never byte-identical").

A mismatch is a regression in the seam, never a reason to recapture. (As in
``tests/test_hygiene.py``, a numpy/scipy bump can move float output on its
own; rule that out before suspecting the code.)
"""

import hashlib
import json
from collections.abc import Mapping

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators.builder import ZoneBuilder
from generators.decor.stock import eq_path_from_env
from generators.layout import LayoutGenerator


def _spec_hash(spec) -> str:
    return hashlib.sha256(
        json.dumps(spec.to_dict(), sort_keys=True).encode()).hexdigest()


# label -> (ZonePlan fields, seed, Zone_Spec sha256, .eqg[:-4] sha256).
# The Zone_Spec is hashed as the layout leaves it: the build adds to it.
# The room-graph cases name ``layout="classic"`` since task 21 made graph the
# default: these goldens pin the classic engine. Every room-graph golden
# (not wilderness) was recaptured once, deliberately, by verticality step 7
# task 17: rooms and corridors moved to stock scale for their race.
_GOLDENS = {
    # Plain dungeon with elevation (moderate verticality).
    "dungeon": (
        dict(zone_type="dungeon", room_count=8, layout="classic"), 7,
        "547ceb208d39eb3e7a947775307c4e21ca6fb0aa8b78bfd57badd8d9d2855ae9",
        "7200816d4f9ae2bc673a6da3e80dcba97686808f6c062f796618d6acdacf72a4"),
    # Flat dungeon (no elevation pass).
    "dungeon_flat": (
        dict(zone_type="dungeon", room_count=6, elevation=False,
             layout="classic"), 3,
        "cdd9513050d466df626a3d88dd99b151481e62d3ccc34c95689ef3dd8fc94a4c",
        "4397f34e2dd6eb89682b9755dfee02a84355162b9c54c24c0f814e6f3c680b12"),
    # Themed dungeon with locks, race scale and dramatic elevation.
    "temple_locks": (
        dict(zone_type="dungeon", room_count=9, locks=2, dungeon_theme="temple",
             dungeon_race="troll", verticality="dramatic",
             layout="classic"), 11,
        "1476e3cd5cd67f00878c235f1a7586b5d03656a6c80edfdf79fb1489cebaf2ad",
        "1793b59d3b3522182e51d99c1ebc99e31e7c1c87f45e7391af4c7caa6c3e25c1"),
    "city": (
        dict(zone_type="city", room_count=7), 5,
        "ef1fb7f01756116367490ffad5c8e4f6c7194f2affbeab3b3ec5348d6a72f3fd",
        "c80ad210ae2ed20442e7ebbcee412521496e124d7954003ac8b1e421171f0c8c"),
    # Recaptured once, deliberately, by wilderness POIs task 7: the default
    # (Sites normal) build now packs Site Structures. Moved by tasks 15 and 10
    # (Site recipes and weights), by site-sockets task 6 (Sites on points)
    # and task 16 (the kind first, then the point), and by step 35 task 2 (the lava patch
    # is drawn only for a lava theme).
    "wilderness": (
        dict(zone_type="wilderness"), 4,
        "290ff9c47da0acb17cc4475e19f2704b7fb76f749101694640a7c2a64c4420fb",
        "f02fc97f6997a0c91fc2c5a168e4c4a4358ef1ab05e8d9b19fbe029651bf1468"),
    # Envelope-confined dungeon under a hill, with a lock. Recaptured once,
    # deliberately, by graph-layout task 12: the Envelope is now the hill's
    # disc clipped to the bowl's interior (no room under the map's edge).
    # Recaptured once more by world-sockets task 20: the spec's Spawn,
    # regions and materials now come from the placed hill's landscape. And by site-sockets
    # task 7 (Sites keep off the dungeon's rooms, not the hill; one at Normal and Dense), and by
    # step 35 task 2 (the lava patch is drawn only for a lava theme), and by step 35 task 5 (the
    # wide, flaring Mouth, in width and height: the Entrance records it, its floor 4.3 u lower;
    # rooms unchanged), and by step 35 task 12 (seed 3's host draws a scarp: the way in is
    # a cliff opening).
    "outdoor_dungeon": (
        dict(zone_type="outdoor_dungeon", room_count=5, locks=1,
             layout="classic"), 3,
        "c3844b0c3078bacb99106d79bf24e9d92ecac26a617ef3ac67673d218d501c0b",
        "31d7cb5fa760235e8bb916dcc0c66a0b1c88f2bf1028306de5785f809a3cee45"),
}

# The .eqg goldens above are the bytes with no install. With one (EQ_PATH), a
# build with Gates also packs the Door model (export spec task 5): recaptured
# once, deliberately, for exactly the labels with locks. Builds with no Gates
# don't move.
WITH_INSTALL = {
    "temple_locks": "6642a351b56a4d0e433b9c2d4a44fcb9f969823625f51a7a9e71721c8ed8b21f",
    "outdoor_dungeon": "e2dbeb591f34bfb4859fa656371429f246a6bdf0b6c691ec65afd9da2d6cad04",
}


class _Goldens(Mapping):
    """``GOLDENS[label]``: the entry, with the with-install ``.eqg`` hash when
    ``EQ_PATH`` names an install AT THE TIME OF THE LOOKUP, so a test that points
    ``EQ_PATH`` at nothing first still reads the no-install bytes."""

    def __getitem__(self, label):
        fields, seed, spec_golden, eqg_golden = _GOLDENS[label]
        if label in WITH_INSTALL and eq_path_from_env() is not None:
            eqg_golden = WITH_INSTALL[label]
        return fields, seed, spec_golden, eqg_golden

    def __iter__(self):
        return iter(_GOLDENS)

    def __len__(self):
        return len(_GOLDENS)


GOLDENS = _Goldens()


@pytest.mark.parametrize("label", sorted(GOLDENS))
def test_build_matches_golden(tmp_path, label):
    fields, seed, spec_golden, eqg_golden = GOLDENS[label]
    spec = plan_to_spec(ZonePlan(name=f"g_{label}", **fields).validate(), seed=seed)
    assert _spec_hash(spec) == spec_golden, "Zone_Spec changed"
    result = ZoneBuilder(spec).build(output_dir=tmp_path, write_glb=False)
    eqg = result.eqg_path.read_bytes()
    assert hashlib.sha256(eqg[:-4]).hexdigest() == eqg_golden, ".eqg changed"


def test_heightfield_layout_matches_golden():
    """The room layout on the heightfield path (no corridor clearance, the
    half-width separation gap), which the wilderness build above never uses."""
    spec = LayoutGenerator("wilderness", seed=9).generate("g_hf", room_count=7)
    assert _spec_hash(spec) == (
        "2d7a22328be50d0760b17d21c4b6a1ef190aef1a625f95b84f90fb0bc8104a93")


class _StubEngine:
    """Three rooms in a row, sized by the engine, entered from the east end,
    rising then level: Job B's three touch points in one layout."""
    name = "stub"
    sizes_rooms = True

    def generate(self, ctx, room_count, envelope):
        from generators.layout_engine import EngineResult, Edge
        from generators.zone_spec import RoomSpec
        rooms = [RoomSpec(id=f"room_{k}", center_x=-1200.0 + 1200.0 * k, center_y=0.0,
                          floor_z=0.0, width=100.0, depth=100.0, height=ctx.ceiling)
                 for k in range(3)]
        ctx.separate(rooms)
        return EngineResult(rooms=rooms,
                            edges=[Edge(2, 1, "below"), Edge(1, 0, "level")],
                            entry=(5000.0, 0.0))


def test_engine_touch_points():
    """The engine's entry picks the entrance, ``sizes_rooms`` skips the role
    bias, and edge relations steer elevation (room 1 below room 2 on every
    seed, room 0 level with room 1)."""
    for seed in range(5):
        gen = LayoutGenerator("dungeon", seed=seed, engine=_StubEngine())
        spec = gen.generate("stub", room_count=3, add_lights=False)
        r0, r1, r2 = spec.rooms
        assert r2.role == "entrance" and r0.role == "climax"
        assert all(r.width == 100.0 and r.depth == 100.0 for r in spec.rooms)
        assert r1.floor_z < r2.floor_z - 1.0
        assert abs(r0.floor_z - r1.floor_z) < 1e-6
