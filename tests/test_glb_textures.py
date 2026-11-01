"""Textured GLB terrain (placeholder textures spec task 4, Req 6.1-6.3, X7).

The GLB's ``terrain`` node draws each material with the DDS packed in the
``.eqg`` and the TER's own UVs; its triangles are the TER's. Read straight from
the glTF (not through trimesh, which flips V on load) so the UVs compared are
the ones the viewer gets.
"""

import io
import json
import struct
import numpy as np
import pytest
from PIL import Image

from ai.expand import plan_to_spec
from ai.planner import make_plan
from ai.schema import ZonePlan
from core.eqg import EqgZone, dds_to_rgb
from core.pfs import PfsArchive
from core.ter import TerFile
from generators.builder import ZoneBuilder

SPECS = {
    "dungeon": lambda: plan_to_spec(make_plan("a gnoll temple dungeon with 8 rooms", name="glbt"), seed=7),
    "city": lambda: plan_to_spec(ZonePlan(name="glbt", zone_type="city"), seed=7),
    "wilderness": lambda: plan_to_spec(ZonePlan(name="glbt", zone_type="wilderness"), seed=7,
                                       edges={"N": "zoneline", "E": "river"}),
}

_COMPONENTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
_DTYPES = {5121: np.uint8, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}


def read_glb(data: bytes):
    (json_len,) = struct.unpack_from("<I", data, 12)
    doc = json.loads(data[20:20 + json_len])
    bin_start = 20 + json_len + 8
    return doc, data[bin_start:]


def accessor(doc, blob, idx):
    acc = doc["accessors"][idx]
    view = doc["bufferViews"][acc["bufferView"]]
    n = _COMPONENTS[acc["type"]]
    start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    arr = np.frombuffer(blob, dtype=_DTYPES[acc["componentType"]],
                        count=acc["count"] * n, offset=start)
    return arr.reshape(acc["count"], n) if n > 1 else arr


def image_of(doc, blob, material_idx):
    mat = doc["materials"][material_idx]
    tex = mat.get("pbrMetallicRoughness", {}).get("baseColorTexture")
    if tex is None:
        return None
    view = doc["bufferViews"][doc["images"][doc["textures"][tex["index"]]["source"]]["bufferView"]]
    png = blob[view.get("byteOffset", 0):view.get("byteOffset", 0) + view["byteLength"]]
    return np.array(Image.open(io.BytesIO(png)).convert("RGB"))


def terrain_primitives(doc, blob):
    """{material name: (corner positions (F,3,3), corner uvs (F,3,2) or None,
    image or None, has COLOR_0)} for the meshes under the ``terrain`` node."""
    terrain = next(n for n in doc["nodes"] if n.get("name") == "terrain")
    out = {}
    for child in terrain.get("children", []):
        mesh = doc["meshes"][doc["nodes"][child]["mesh"]]
        for prim in mesh["primitives"]:
            pos = accessor(doc, blob, prim["attributes"]["POSITION"])
            idx = accessor(doc, blob, prim["indices"]).reshape(-1, 3)
            uv = (accessor(doc, blob, prim["attributes"]["TEXCOORD_0"])
                  if "TEXCOORD_0" in prim["attributes"] else None)
            image = image_of(doc, blob, prim["material"]) if "material" in prim else None
            out[mesh["name"]] = (pos[idx], None if uv is None else uv[idx], image,
                                 "COLOR_0" in prim["attributes"])
    return out


def _by_position(tris, uvs):
    """{exact corner positions of a triangle: [its corner uvs, ...]}."""
    out = {}
    for t, uv in zip(tris, uvs):
        out.setdefault(tuple(np.asarray(t, dtype=np.float32).ravel().tolist()), []).append(uv)
    return out


@pytest.fixture(scope="module", params=sorted(SPECS))
def built(request, tmp_path_factory):
    spec = SPECS[request.param]()
    result = ZoneBuilder(spec).build(output_dir=tmp_path_factory.mktemp(request.param))
    arc = PfsArchive.from_file(result.eqg_path)
    ter = TerFile.from_bytes(arc.get("ter_glbt.ter"))
    doc, blob = read_glb(result.glb_path.read_bytes())
    return result, arc, ter, doc, blob


def test_x7_each_material_carries_its_packed_texture(built):
    result, arc, ter, doc, blob = built
    prims = terrain_primitives(doc, blob)
    assert set(prims) == {m.name for m in ter.materials if any(p.material == m.index for p in ter.polygons)}
    for mat in ter.materials:
        if mat.name not in prims:
            continue
        _, _, image, has_colour = prims[mat.name]
        expected = dds_to_rgb(arc.get(f"{mat.name}.dds"))
        assert image is not None and image.shape == expected.shape
        assert np.abs(image.astype(int) - expected.astype(int)).max() <= 2
        assert not has_colour
    assert not result.warnings


def test_x7_triangles_and_uvs_equal_the_ter(built):
    _, _, ter, doc, blob = built
    prims = terrain_primitives(doc, blob)
    assert sum(len(p[0]) for p in prims.values()) == len(ter.polygons)
    for mat in ter.materials:
        polys = [p for p in ter.polygons if p.material == mat.index]
        if not polys:
            continue
        want_pos = np.array([[[ter.vertices[i].x, ter.vertices[i].y, ter.vertices[i].z]
                              for i in (p.v1, p.v2, p.v3)] for p in polys])
        want_uv = np.array([[[ter.vertices[i].u, ter.vertices[i].v]
                             for i in (p.v1, p.v2, p.v3)] for p in polys])
        pos, uv, _, _ = prims[mat.name]
        got = _by_position(pos, uv)
        want = _by_position(want_pos, want_uv)
        assert set(got) == set(want), mat.name
        for key, uvs in want.items():
            assert len(got[key]) == len(uvs)
            for w, g in zip(sorted(uvs, key=lambda a: a.ravel().tolist()),
                            sorted(got[key], key=lambda a: a.ravel().tolist())):
                assert np.allclose(w, g, atol=1e-5), (mat.name, w, g)


def test_vegetation_node_keeps_base_colours(built):
    result, _, _, doc, blob = built
    veg = [n for n in doc["nodes"] if n.get("name") == "vegetation"]
    if result.spec.zone_type != "wilderness":
        assert not veg
        return
    prim = doc["meshes"][veg[0]["mesh"]]["primitives"][0]
    assert "COLOR_0" in prim["attributes"] and "TEXCOORD_0" not in prim["attributes"]


def test_undecodable_texture_falls_back_to_base_colour(tmp_path):
    spec = SPECS["city"]()
    result = ZoneBuilder(spec).build(output_dir=tmp_path / "src", write_glb=False)
    arc = PfsArchive.from_file(result.eqg_path)
    ter = TerFile.from_bytes(arc.get("ter_glbt.ter"))
    textures = {m.index: arc.get(f"{m.name}.dds") for m in ter.materials}
    broken = ter.materials[0]
    textures[broken.index] = b"DDS " + b"\0" * 200

    zone = EqgZone("glbt")
    zone.set_terrain(ter, pack=False)
    out = zone.write_glb(tmp_path / "out" / "glbt.glb", textures=textures)
    assert out is not None and out.exists()
    assert zone.glb_warnings == [f"texture_preview_fallback:{broken.name}"]
    doc, blob = read_glb(out.read_bytes())
    prims = terrain_primitives(doc, blob)
    _, _, image, has_colour = prims[broken.name]
    assert image is None and has_colour
    assert all(p[2] is not None for n, p in prims.items() if n != broken.name)


def test_without_textures_the_glb_has_no_images(tmp_path):
    spec = SPECS["city"]()
    result = ZoneBuilder(spec).build(output_dir=tmp_path / "src", write_glb=False)
    ter = TerFile.from_bytes(PfsArchive.from_file(result.eqg_path).get("ter_glbt.ter"))
    zone = EqgZone("glbt")
    zone.set_terrain(ter, pack=False)
    doc, _ = read_glb(zone.write_glb(tmp_path / "plain.glb").read_bytes())
    assert "images" not in doc and len(doc["meshes"]) == 1


@pytest.mark.parametrize("bad", [b"", b"PNG", b"DDS " + b"\0" * 124])
def test_dds_to_rgb_rejects_what_it_cannot_read(bad):
    with pytest.raises(ValueError):
        dds_to_rgb(bad)
