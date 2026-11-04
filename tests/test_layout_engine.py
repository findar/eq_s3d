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
# default: these goldens pin the classic engine.
GOLDENS = {
    # Plain dungeon with elevation (moderate verticality).
    "dungeon": (
        dict(zone_type="dungeon", room_count=8, layout="classic"), 7,
        "b61698e1e6ca1968e04b0f4426ea439ed7cdc39b917dad0571a0a5090400bcee",
        "483e769eda2b5680538a1a7d9b67629c37447af969c3477945fcf7b4277ebb6c"),
    # Flat dungeon (no elevation pass).
    "dungeon_flat": (
        dict(zone_type="dungeon", room_count=6, elevation=False,
             layout="classic"), 3,
        "ebd555a660198b83a9b8504517da4a7eb096ae9ebc2d66dd242f2687858821ff",
        "bf0d0ee0c03783266cb510ed254506a4944dabe37a690bc27caf41d9fdc902d9"),
    # Themed dungeon with locks, race scale and dramatic elevation.
    "temple_locks": (
        dict(zone_type="dungeon", room_count=9, locks=2, dungeon_theme="temple",
             dungeon_race="troll", verticality="dramatic",
             layout="classic"), 11,
        "e6d8b333faf276b08de4c4b091d1001e6f3605f9b998d579665dc54412857889",
        "040e2dbfe27c87dfc51773a154361eb6fcb171afa1c420cd9c591002452b141d"),
    "city": (
        dict(zone_type="city", room_count=7), 5,
        "627faad8a385580f191612a5bb663c5ce4c9db59368ca521a0c260ea6de0b8d2",
        "0d4e257e73f914e7775a0923bba9191e942a406f6304b1d22dce96edb84f5983"),
    "wilderness": (
        dict(zone_type="wilderness"), 4,
        "a948f132378258b14e6606cc06faf248f712cca2b7317e627ce5dda6c56fcc62",
        "a2e1c432fcfa542dee2f319204dfff949655736144e41a2fb7f90a59b7ec55a4"),
    # Envelope-confined dungeon under a hill, with a lock. Recaptured once,
    # deliberately, by graph-layout task 12: the Envelope is now the hill's
    # disc clipped to the bowl's interior (no room under the map's edge).
    "outdoor_dungeon": (
        dict(zone_type="outdoor_dungeon", room_count=5, locks=1,
             layout="classic"), 3,
        "13d6b5aebbb9d5588e93710e1a56a9e70e83f55d96d20d5f70b922218c4a8f27",
        "3f157d1a9423443fd57bfb1cbb0d7e06c353a3df7defc40647f91001c093b5ee"),
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
                          floor_z=0.0, width=300.0, depth=300.0, height=ctx.ceiling)
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
        assert all(r.width == 300.0 and r.depth == 300.0 for r in spec.rooms)
        assert r1.floor_z < r2.floor_z - 1.0
        assert abs(r0.floor_z - r1.floor_z) < 1e-6
