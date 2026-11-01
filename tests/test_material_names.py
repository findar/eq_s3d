"""Material names by set and surface (placeholder textures spec task 1).

X3 (Req 1.5, 7.1): renaming materials changes no geometry and no material
assignment. The goldens below hash each pinned build's TER vertices and each
polygon's (v1, v2, v3, flags, material index), leaving out every name, shader
and texture string; they were recorded on the code BEFORE the rename.
"""

import hashlib
import re
import struct

import pytest

from ai.expand import plan_to_spec
from ai.planner import make_plan
from ai.schema import ZonePlan
from core.pfs import PfsArchive
from analyzer.rof2check import KNOWN_SHADERS
from core.ter import PROP_DIFFUSE, TerFile
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


NAME_RE = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*$")


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    d = tmp_path_factory.mktemp("names")
    return {label: _build_ter(d, label) for label in CASES}


@pytest.mark.parametrize("label", sorted(CASES))
def test_x1_names_are_well_formed_and_name_their_texture(built, label):
    _, arc, ter = built[label]
    names = [m.name for m in ter.materials]
    assert len(names) == len(set(names))
    packed = {n.lower() for n in arc.list_files()}
    for mat in ter.materials:
        assert NAME_RE.match(mat.name) and len(mat.name) <= 40, mat.name
        diffuse = next(p.value_s for p in mat.properties if p.name == PROP_DIFFUSE)
        assert diffuse == f"{mat.name}.dds" and diffuse in packed


EXPECTED_NAMES = {
    "dungeon_plain": {"dungeon_floor", "dungeon_wall", "dungeon_ceiling"},
    "dungeon_gnoll_temple": {"gnoll_dungeon_floor", "gnoll_dungeon_wall",
                             "gnoll_dungeon_ceiling", "gnoll_temple_floor",
                             "gnoll_temple_wall"},
    "dungeon_kobold_tomb_lava": {"kobold_dungeon_floor", "kobold_dungeon_wall",
                                 "kobold_dungeon_ceiling", "kobold_lava_floor",
                                 "kobold_lava_wall"},
    "dungeon_temple_no_race": {"dungeon_floor", "dungeon_wall", "dungeon_ceiling",
                               "temple_floor", "temple_wall"},
    "city": {"city_floor", "city_wall", "city_ceiling"},
}


@pytest.mark.parametrize("label", sorted(EXPECTED_NAMES))
def test_x2_room_graph_sets_and_surfaces(built, label):
    _, _, ter = built[label]
    assert {m.name for m in ter.materials} == EXPECTED_NAMES[label]


def test_x2_wilderness_keeps_its_names(built):
    _, arc, ter = built["wilderness"]
    names = {m.name for m in ter.materials}
    assert names - {"liquid_water"} and all(n.startswith("wild_") for n in names - {"liquid_water"})
    assert {n for n in arc.list_files() if n.endswith(".mod")} >= {"veg_broadleaf.mod"}


@pytest.mark.parametrize("label", sorted(CASES))
def test_x4_no_placeholder_shader(built, label):
    _, arc, ter = built[label]
    meshes = [ter] + [TerFile.from_bytes(arc.get(n)) for n in arc.list_files() if n.endswith(".mod")]
    for mesh in meshes:
        assert all(m.shader in KNOWN_SHADERS for m in mesh.materials)
    assert "<fixed-function>" not in KNOWN_SHADERS
