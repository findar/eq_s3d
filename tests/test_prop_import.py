"""
tests/test_prop_import.py
-------------------------
Importing a catalogued stock model (room-decor spec task 6, Property 4): for a sample
across Categories, the imported ``.mod``'s triangles, UVs, flags and texture pixels equal
the stock model's, and the ``.mod`` round-trips through ``core.ter``.

The stock side is read independently of ``generators.decor.stock``: actor -> meshes and
mesh -> texture names through task 1's reader (``scripts/prop_catalogue._Wld``), geometry
through ``core.wld._parse_mesh``, pixels through Pillow. Needs the install: skips without
``EQ_PATH``, as the survey tests do.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from core.eqg import EqgZone, dds_to_rgb  # noqa: E402
from core.pfs import PfsArchive  # noqa: E402
from core.ter import FLAG_PASSABLE, PROP_DIFFUSE, TerFile  # noqa: E402
from core.wld import _parse_mesh  # noqa: E402
from core.zon import ZonFile, ZonObject  # noqa: E402
from generators.decor.stock import (SHADERS, TRANSLUCENT, USER_DEFINED,  # noqa: E402
                                    Importer, NotImportable, decode_texture,
                                    eq_path_from_env, material_class, texture_rgba)

#: One or two per Category: Category -> catalogue keys.
SAMPLE = {
    "torch": ["TORCH1", "GKTORCH702"],
    "table": ["DARKTABLE"],
    "chair": ["CHAIR"],
    "barrel": ["BARREL4"],
    "crate": ["CRATEA"],
    "web": ["CDWEB502"],
    "rock": ["LROCK314C", "SBROCK202"],          # SBROCK202's texture is a real BMP
    "bookcase": ["BOOKCASE200"],
    "hanging lantern": ["HLAMP", "LANTERN1"],     # fire1 is a 4-frame animated texture
    "plant": ["FFPLANT302@abysmal"],              # masked leaves and an invisible material
}
KEYS = [k for ks in SAMPLE.values() for k in ks]


@pytest.fixture(scope="module")
def importer() -> Importer:
    eq = eq_path_from_env()
    if eq is None:
        pytest.skip("EQ_PATH is not set (no EQ install to read)")
    imp = Importer(eq)
    missing = [k for k in KEYS if k not in imp.catalogue]
    if missing:
        pytest.skip(f"catalogue lacks {missing}")
    return imp


def _stock(importer: Importer, key: str):
    """The stock model read without the importer: [(vertices, polygons, uvs, textures per
    material (method, name))] per mesh, and the archive's files."""
    from prop_catalogue import _Wld

    entry = importer.catalogue[key]
    arc = PfsArchive.from_file(importer.eq_path / entry["source"]["archive"])
    files = {f.name.lower(): f.data for f in arc.files}
    wld = _Wld(files[entry["source"]["wld"]])
    actor = next(b for fid, b, _s in wld.frags[1:]
                 if fid == 0x14 and wld.name(b).upper() == entry["name"] + "_ACTORDEF")
    refs, animation = wld.actor_meshes(actor)
    assert animation == "static"
    meshes = []
    for ref in refs:
        _f, mb, size = wld.frags[ref]
        m = _parse_mesh(wld.data, mb, mb + size, wld.old)
        (ml,) = wld.i32(mb + 8)
        _f, lb, _s = wld.frag(ml, 0x31)
        (n,) = wld.i32(lb + 8)
        mats = []
        for mref in wld.i32(lb + 12, n):
            _f, b, _s = wld.frag(mref, 0x30)
            (method,) = struct.unpack_from("<I", wld.data, b + 8)
            mats.append(method)
        # textures() lists the materials that have a bitmap, in material order
        names = iter(t["name"] for t in wld.textures(mb, files))
        texs = []
        for mref in wld.i32(lb + 12, n):
            texs.append(next(names) if _has_bitmap(wld, mref) else None)
        meshes.append((m, list(zip(mats, texs))))
    return meshes, files


def _has_bitmap(wld, mref: int) -> bool:
    _f, b, _s = wld.frag(mref, 0x30)
    (bref,) = wld.i32(b + 24)
    return bref > 0


def _diffuse(ter: TerFile, i: int) -> str:
    return next(p.value_s for p in ter.materials[i].properties if p.name == PROP_DIFFUSE)


def _dds_rgba(dds: bytes) -> np.ndarray:
    h, w = struct.unpack_from("<II", dds, 12)
    bgra = np.frombuffer(dds[128:128 + 4 * w * h], np.uint8).reshape(h, w, 4)
    out = bgra[..., [2, 1, 0, 3]]
    assert np.array_equal(out[..., :3], dds_to_rgb(dds))
    return out


@pytest.mark.parametrize("key", KEYS)
def test_import_equals_stock(importer: Importer, key: str):
    """P4: triangles, UVs, flags and texture pixels equal the stock model's."""
    model = importer.get(key)
    ter = model.ter
    meshes, files = _stock(importer, key)
    f32 = lambda a: np.asarray(a, np.float32)  # noqa: E731

    verts = np.array([[v.x, v.y, v.z] for v in ter.vertices], np.float32)
    uvs = np.array([[v.u, v.v] for v in ter.vertices], np.float32)
    polys = iter(ter.polygons)
    base = 0
    checked = set()
    for mesh, mats in meshes:
        nv = len(mesh.vertices)
        assert np.array_equal(verts[base:base + nv], f32(mesh.vertices))
        assert np.array_equal(uvs[base:base + nv], f32(mesh.uvs))
        for (a, b, c, flag), t in zip(mesh.polygons, mesh.polygon_textures):
            p = next(polys)
            # same corners, the .mod's winding convention: (v1, v2, v3) -> (v1, v3, v2)
            assert (p.v1, p.v2, p.v3) == (base + a, base + c, base + b)
            assert bool(p.flags & FLAG_PASSABLE) == bool(flag & 0x10)
            method, tex = mats[t]
            cls = material_class(method) if tex else "boundary"
            assert ter.materials[p.material].shader == SHADERS[cls]
            if cls == "boundary" or (p.material, tex) in checked:
                continue
            checked.add((p.material, tex))
            got = _dds_rgba(model.textures[_diffuse(ter, p.material)])
            want, index = decode_texture(files[tex])
            assert np.array_equal(got[..., :3], want[..., :3]), f"{tex} RGB differs"
            a = want[..., 3].astype(np.float64)
            if cls == "translucent":
                a = np.round(a * TRANSLUCENT[method & ~USER_DEFINED])
            elif cls == "additive":
                a = np.minimum(a, want[..., :3].max(axis=2))
            elif cls == "masked" and index is not None:
                a[index == 0] = 0
            assert np.array_equal(got[..., 3], a.astype(np.uint8)), f"{tex} alpha differs"
        base += nv
    assert next(polys, None) is None
    assert len(ter.vertices) == base


@pytest.mark.parametrize("key", KEYS)
def test_mod_round_trips(importer: Importer, key: str):
    """P4: the ``.mod`` round-trips through the writer and reader exactly; one material
    per texture, every one naming a texture the import carries."""
    ter = importer.get(key).ter
    raw = ter.to_bytes()
    back = TerFile.from_bytes(raw, name=ter.name)
    assert back.to_bytes() == raw
    assert back.vertices == ter.vertices and back.polygons == ter.polygons
    assert back.materials == ter.materials
    textures = importer.get(key).textures
    named = [(_diffuse(ter, i), m.shader) for i, m in enumerate(ter.materials)]
    assert len(set(named)) == len(named)
    assert {n for n, _s in named} == set(textures)


def test_imports_once_per_mesh(importer: Importer):
    """Cached by mesh: a second ``get`` hands back the same import."""
    assert importer.get("BARREL4") is importer.get("BARREL4")


def test_animated_model_is_refused_named(importer: Importer):
    key = next(k for k, m in importer.catalogue.items() if m["animation"] == "skeletal")
    with pytest.raises(NotImportable, match=key.replace("@", ".")):
        importer.get(key)


def test_vertex_animated_model_imports_frozen(importer: Importer):
    """A waving banner imports in its rest pose and round-trips (archive decision 24)."""
    key = "PAFLAG101"
    assert importer.catalogue[key]["animation"] == "vertex"
    model = importer.get(key)
    assert model.ter.vertices and model.ter.polygons
    raw = model.ter.to_bytes()
    assert TerFile.from_bytes(raw, name=model.ter.name).to_bytes() == raw


def test_masked_bmp_index_zero_is_clear():
    """An 8-bit BMP under a masked material: palette index 0 is clear, the rest as is
    (no static Prop in the install has one; this pins the rule)."""
    from io import BytesIO

    from PIL import Image

    img = Image.new("P", (4, 2))
    img.putpalette([255, 0, 255, 10, 20, 30] + [0] * 762)
    img.putdata([0, 1, 1, 0, 1, 1, 1, 1])
    buf = BytesIO()
    img.save(buf, format="BMP")
    rgba = texture_rgba(buf.getvalue(), "masked", USER_DEFINED | 0x13)
    assert rgba[..., 3].tolist() == [[0, 255, 255, 0], [255, 255, 255, 255]]
    assert rgba[0, 1, :3].tolist() == [10, 20, 30]
    assert texture_rgba(buf.getvalue(), "opaque")[..., 3].min() == 255


def test_room_gate_reads_imported_models(importer: Importer, tmp_path: Path):
    """Smoke: imported models packed into an ``.eqg`` read back through the room gate's
    model reader (``analyzer.traverse.placed_models``) as they were written."""
    from analyzer.footprints import collidable_triangles
    from analyzer.traverse import placed_models

    keys = ["TORCH1", "CHAIR", "BARREL4", "CDWEB502", "FFPLANT302@abysmal"]
    eqg = EqgZone("stocktest")
    zon = ZonFile()
    zon.models.append("ter_stocktest.ter")
    for i, key in enumerate(keys):
        m = importer.get(key)
        eqg.add_model(m.model_file, m.ter.to_bytes())
        for fname, dds in m.textures.items():
            eqg.add_texture(fname, dds)
        zon.models.append(m.model_file)
        zon.objects.append(ZonObject(name=f"prop_{i}", model_id=len(zon.models) - 1,
                                     x=20.0 * i, y=0.0, z=0.0, scale=1.0))
    eqg.set_placement(zon)
    path = tmp_path / "stocktest.eqg"
    eqg.write(path)
    placed = placed_models(path)
    assert [p.model_name for p in placed] == [importer.get(k).model_file for k in keys]
    for p, key in zip(placed, keys):
        want = collidable_triangles(importer.get(key).ter)
        assert np.array_equal(collidable_triangles(p.model), want)
