"""Material names by set and surface (placeholder textures spec task 1).

X3 (Req 1.5, 7.1): renaming materials changes no geometry and no material
assignment. The goldens below hash each pinned build's TER vertices and each
polygon's (v1, v2, v3, flags, material index), leaving out every name, shader
and texture string; they were recorded on the code BEFORE the rename.
"""

import hashlib
import struct

import pytest

from ai.expand import plan_to_spec
from ai.planner import make_plan
from ai.schema import ZonePlan
from core.pfs import PfsArchive
from core.ter import TerFile
from generators.builder import ZoneBuilder

# (label, how to build the spec) -> golden geometry hash
CASES = {
    "dungeon_plain": lambda: plan_to_spec(ZonePlan(name="names", zone_type="dungeon"), seed=7),
    "dungeon_gnoll_temple": lambda: plan_to_spec(
        make_plan("a gnoll temple dungeon with 8 rooms", name="names"), seed=7),
    "dungeon_kobold_tomb_lava": lambda: plan_to_spec(
        make_plan("a kobold tomb full of lava with 6 rooms", name="names"), seed=11),
    "dungeon_temple_no_race": lambda: plan_to_spec(
        make_plan("a temple dungeon with 6 rooms", name="names"), seed=5),
    "city": lambda: plan_to_spec(ZonePlan(name="names", zone_type="city"), seed=7),
    "wilderness": lambda: plan_to_spec(ZonePlan(name="names", zone_type="wilderness"),
                                       seed=7, edges={"N": "zoneline", "E": "river"}),
}

GOLDEN = {
    "city": "16b097ef17da109be29c67e9",
    "dungeon_gnoll_temple": "ba813d865338cc48cb7fdca6",
    "dungeon_kobold_tomb_lava": "ab3f7da6ae1bb48e9543d5f2",
    "dungeon_plain": "b8e6613ee91be1d5e7ac7c6b",
    "dungeon_temple_no_race": "01cc6c694af6fb7d0e83b854",
    "wilderness": "05eeaa80c532106f34201a6f",
}


def _build_ter(tmp_path, label):
    spec = CASES[label]()
    result = ZoneBuilder(spec).build(output_dir=tmp_path / label, write_glb=False)
    arc = PfsArchive.from_file(result.eqg_path)
    return spec, arc, TerFile.from_bytes(arc.get(f"ter_{spec.name}.ter"))


def geometry_hash(ter: TerFile) -> str:
    """sha256 over vertices and polygon (v1, v2, v3, flags, material); no names."""
    h = hashlib.sha256()
    for v in ter.vertices:
        h.update(struct.pack("<8fI", v.x, v.y, v.z, v.nx, v.ny, v.nz, v.u, v.v, v.color))
    for p in ter.polygons:
        h.update(struct.pack("<IIIIi", p.v1, p.v2, p.v3, p.flags, p.material))
    return h.hexdigest()[:24]


@pytest.mark.parametrize("label", sorted(CASES))
def test_x3_rename_moves_no_geometry(tmp_path, label):
    _, _, ter = _build_ter(tmp_path, label)
    assert geometry_hash(ter) == GOLDEN[label]
