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

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators.builder import ZoneBuilder
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
GOLDENS = {
    # Plain dungeon with elevation (moderate verticality).
    "dungeon": (
        dict(zone_type="dungeon", room_count=8, layout="classic"), 7,
        "a3a6e9b1ff09cc68b0a83869d5968edcf7fef465386c7365fbe076db22ec5732",
        "4b483b3a713d88d656e96da3150a54578401adc0e19a327d23dc2afbd6f9d1e1"),
    # Flat dungeon (no elevation pass).
    "dungeon_flat": (
        dict(zone_type="dungeon", room_count=6, elevation=False,
             layout="classic"), 3,
        "8bd24445db6d130d1e6302515742dc2eede008b4422b2729ab12f3ed50362efa",
        "e8c65bbc2df78b3a8c4d2c5258143df24872d08287a613fb64459517bd917314"),
    # Themed dungeon with locks, race scale and dramatic elevation.
    "temple_locks": (
        dict(zone_type="dungeon", room_count=9, locks=2, dungeon_theme="temple",
             dungeon_race="troll", verticality="dramatic",
             layout="classic"), 11,
        "c85faeb2f301fa8a8b8d236dbe623d757b684e39e11d8fbaced806117fa618f5",
        "c5e9125f3a11aa7c040ded8d3010496a90550090f0f7e876b9b82fcb6243388c"),
    "city": (
        dict(zone_type="city", room_count=7), 5,
        "6a22604a597e2b805346bbad1d1dad640c408015592d8e8adb3c0c4c1e7ce170",
        "2467f660f243c0e8061e643049622d3542ab51d891e20019b70e95c840c75ff5"),
    # Recaptured once, deliberately, by wilderness POIs task 7: the default
    # (Sites normal) build now packs Site Structures. Moved by tasks 15 and 10
    # (Site recipes and weights), by site-sockets task 6 (Sites on points)
    # and task 16 (the kind first, then the point).
    "wilderness": (
        dict(zone_type="wilderness"), 4,
        "a948f132378258b14e6606cc06faf248f712cca2b7317e627ce5dda6c56fcc62",
        "ac09fbe8d07be5b586c978cdcbedab2a27d7d42d6528927ab9e8bcb95cf119e5"),
    # Envelope-confined dungeon under a hill, with a lock. Recaptured once,
    # deliberately, by graph-layout task 12: the Envelope is now the hill's
    # disc clipped to the bowl's interior (no room under the map's edge).
    # Recaptured once more by world-sockets task 20: the spec's Spawn,
    # regions and materials now come from the placed hill's landscape. And by site-sockets
    # task 7 (Sites keep off the dungeon's rooms, not the hill; one at Normal and Dense).
    "outdoor_dungeon": (
        dict(zone_type="outdoor_dungeon", room_count=5, locks=1,
             layout="classic"), 3,
        "e9c7e4dc2365d3ebe140f41c4f18c73ca37a2be312b0f8777be90fbe954956d7",
        "64ef46885fcafcf07b370e1e09063c740e795ea38a8083f75a6010c85547b1e0"),
}


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
