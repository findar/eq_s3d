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
GOLDENS = {
    # Plain dungeon with elevation (moderate verticality).
    "dungeon": (
        dict(zone_type="dungeon", room_count=8), 7,
        "b61698e1e6ca1968e04b0f4426ea439ed7cdc39b917dad0571a0a5090400bcee",
        "483e769eda2b5680538a1a7d9b67629c37447af969c3477945fcf7b4277ebb6c"),
    # Flat dungeon (no elevation pass).
    "dungeon_flat": (
        dict(zone_type="dungeon", room_count=6, elevation=False), 3,
        "ebd555a660198b83a9b8504517da4a7eb096ae9ebc2d66dd242f2687858821ff",
        "bf0d0ee0c03783266cb510ed254506a4944dabe37a690bc27caf41d9fdc902d9"),
    # Themed dungeon with locks, race scale and dramatic elevation.
    "temple_locks": (
        dict(zone_type="dungeon", room_count=9, locks=2, dungeon_theme="temple",
             dungeon_race="troll", verticality="dramatic"), 11,
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
    # Envelope-confined dungeon under a hill, with a lock.
    "outdoor_dungeon": (
        dict(zone_type="outdoor_dungeon", room_count=5, locks=1), 3,
        "67d927b8b9d08cff44ca8b102b5fd71bfdd85c6d861128be85863ed34b0ea10a",
        "956532446854e9f8198d782d77dbfa9ad3827d9b394f0372e5804caa4ef5abee"),
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
