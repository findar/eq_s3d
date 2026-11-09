"""
generators/decor/stock.py
-------------------------
Import a catalogued stock model (room-decor spec task 6, Requirement 4).

A Prop is the client's own model, copied into the build (archive decision 1). The
catalogue (``rules/decor/catalogue.json``, task 1) names each model's source archive and
WLD; :class:`Importer` reads that archive from the install (``EQ_PATH``) at build time and
turns the model into an ``EQGM`` ``.mod`` plus its textures as DDS:

- **Geometry unchanged.** Vertices, triangles and UVs are the WLD mesh's own (0x36), in its
  own order: no remeshing, closing or welding, and no per-triangle rewinding. A static
  actor's meshes are concatenated. The WLD polygon flag 0x10 (passable) becomes
  ``FLAG_PASSABLE``; every other polygon is collidable, as stock (archive decision 6).
  Normals are the mesh's own (signed bytes / 128).
- **The two formats' conventions** (:data:`CONVENTIONS`): positions and UVs carry over as
  they are; the winding convention differs, so every triangle's second and third corners
  swap (WLD ``v1, v2, v3`` is ``.mod`` ``v1, v3, v2``). That converts the convention, not the
  mesh: a triangle stock wound oddly stays odd.
- **One material per texture.** Each WLD material (0x30) keeps its first texture frame
  (animated textures stand still) and maps to a shader by its render method
  (:func:`material_class`): opaque, masked (``Chroma``: palette index 0 of an 8-bit BMP is
  clear, a DXT texture's own alpha is kept), translucent (``Alpha``, the method's 25/50/75%
  opacity times the texel's alpha) or additive (``Alpha``, opacity = the texel's brightest
  channel, so black reads clear as an additive flame does). Invisible materials (method 0)
  get ``Boundary.fx`` and a small clear texture. Materials that come out the same (texture
  bytes and shader) are one.
- **Textures as DDS.** BMP or DDS (DXT1/3/5) are decoded and written as uncompressed
  A8R8G8B8 (``generators.textures.dds``), RGB unchanged. A texture's file name carries a hash
  of its bytes, because the same name ships different art in different zones (711 models).

Animated models (skeletal, vertex-animated) are refused, named (archive decision 13), as is
a model whose mesh in the install no longer matches the catalogue's hash.

:class:`Importer` caches each import by (mesh hash, source archive), and each archive it
opens, so a build reads every model it uses once.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

import numpy as np

from core.pfs import PfsArchive
from core.ter import (FLAG_PASSABLE, MAGIC_MODEL, SHADER_ALPHA, SHADER_BOUNDARY, SHADER_CHROMA,
                      SHADER_OPAQUE, Material, Polygon, TerFile, Vertex)
from core.wld import _decode_string_hash, _parse_mesh
from generators.textures.dds import rgba_to_dds

ROOT = Path(__file__).resolve().parents[2]
CATALOGUE = ROOT / "rules" / "decor" / "catalogue.json"

#: WLD polygon flag: the polygon is passable (not collidable).
WLD_PASSABLE = 0x10
#: WLD material render method: set on the "user defined" methods (0x80000001 diffuse...).
USER_DEFINED = 0x80000000

#: WLD -> ``.mod`` conventions, as checked in task 6 (commit message has the numbers):
#:
#: - **Winding is opposite.** A WLD triangle's front is clockwise seen from outside: in
#:   catalogued static models the face normal ``(v2 - v1) x (v3 - v1)`` points against the
#:   mesh's own vertex normals, and closed ones have negative volume; stock ``.eqg`` models
#:   are the reverse (normals agree, volume positive), as the generator's own models are.
#:   ``scripts/outdoor_dungeon_survey.py`` met the same thing ("WLD floors wind down").
#: - **Axes are the same** (x, y, z, z up, right-handed): stock signs read left to right
#:   with ``u`` running to the reader's right, so the WLD frame isn't mirrored.
#: - **UVs are the same**: ``v`` grows down the texture rows (row 0 at ``v = 0``) in both;
#:   a stock sign's lettering stands upright that way.
CONVENTIONS = "x, y, z and u, v copied; triangle (v1, v2, v3) becomes (v1, v3, v2)"

#: Opacity of the WLD's translucent render methods.
TRANSLUCENT = {0x02: 0.25, 0x05: 0.50, 0x09: 0.75}
MASKED = {0x13}
ADDITIVE = {0x0A, 0x0B}
SHADERS = {"opaque": SHADER_OPAQUE, "masked": SHADER_CHROMA, "translucent": SHADER_ALPHA,
           "additive": SHADER_ALPHA, "boundary": SHADER_BOUNDARY}
BOUNDARY_TEXTURE = "stock_boundary.dds"
BOUNDARY_SIZE = 4


class NotImportable(ValueError):
    """A catalogue entry the importer won't or can't turn into a ``.mod``; the message
    names the model and the reason."""


def material_class(method: int) -> str:
    """``opaque``, ``masked``, ``translucent``, ``additive`` or ``boundary`` for a WLD
    material's render method. The methods without the user-defined bit are bit fields
    whose low two bits are the draw style (0 = not drawn, 3 = solid)."""
    if not method & USER_DEFINED:
        return "boundary" if method & 3 == 0 else "opaque"
    low = method & ~USER_DEFINED
    if low == 0:
        return "boundary"
    if low in MASKED:
        return "masked"
    if low in TRANSLUCENT:
        return "translucent"
    if low in ADDITIVE:
        return "additive"
    return "opaque"


# ---------------------------------------------------------------------------
# Textures
# ---------------------------------------------------------------------------

def decode_texture(data: bytes) -> Tuple[np.ndarray, Optional[np.ndarray]]:
    """(RGBA (H, W, 4) uint8, top row first; palette indices (H, W) for an 8-bit BMP,
    else None) of a BMP or DDS file, whatever its extension says."""
    from PIL import Image

    with Image.open(io.BytesIO(data)) as img:
        img.load()
        index = np.array(img, dtype=np.uint8) if img.mode == "P" else None
        rgba = np.array(img.convert("RGBA"), dtype=np.uint8)
    return rgba, index


def texture_rgba(data: bytes, cls: str, method: int = 0) -> np.ndarray:
    """The RGBA the import writes for a texture under a material class: RGB as decoded,
    alpha by the class (module docstring)."""
    rgba, index = decode_texture(data)
    rgba = rgba.copy()
    a = rgba[..., 3]
    if cls == "masked" and index is not None:
        a[index == 0] = 0
    elif cls == "translucent":
        level = TRANSLUCENT[method & ~USER_DEFINED]
        rgba[..., 3] = np.round(a.astype(np.float64) * level).astype(np.uint8)
    elif cls == "additive":
        rgba[..., 3] = np.minimum(a, rgba[..., :3].max(axis=2))
    return rgba


def _texture_file(stem: str, dds: bytes) -> str:
    return f"{_slug(stem)}_{hashlib.sha1(dds).hexdigest()[:8]}.dds"


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", s.lower()).strip("_") or "x"


def boundary_texture() -> bytes:
    """The clear texture an invisible material names (every material needs a diffuse)."""
    n = BOUNDARY_SIZE
    return rgba_to_dds(np.zeros((n, n, 3), np.uint8), np.zeros((n, n), np.uint8))


# ---------------------------------------------------------------------------
# WLD
# ---------------------------------------------------------------------------

class _Wld:
    """One WLD's fragments, indexed 1-based as fragment references count them."""

    def __init__(self, data: bytes):
        self.data = data
        _m, version, count, _b, _u, hs, _u2 = struct.unpack_from("<7I", data, 0)
        self.old = version == 0x00015500
        self.strings = _decode_string_hash(data[28:28 + hs])
        self.frags: List[Optional[Tuple[int, int, int]]] = [None]
        self.actors: Dict[str, int] = {}
        pos = 28 + hs
        for _ in range(count):
            if pos + 8 > len(data):
                break
            size, fid = struct.unpack_from("<II", data, pos)
            self.frags.append((fid, pos + 8, size))
            if fid == 0x14:
                self.actors[self.name(pos + 8).upper().replace("_ACTORDEF", "")] = pos + 8
            pos += 8 + size

    def name(self, b: int) -> str:
        (ref,) = struct.unpack_from("<i", self.data, b)
        if ref >= 0:
            return ""
        return self.strings[-ref:self.strings.find(b"\0", -ref)].decode("latin1")

    def i32(self, pos: int, n: int = 1):
        return struct.unpack_from(f"<{n}i", self.data, pos)

    def frag(self, ref: int, *want: int) -> Tuple[int, int, int]:
        if ref <= 0 or ref >= len(self.frags):
            raise ValueError(f"reference {ref} out of range")
        fid, b, size = self.frags[ref]
        if want and fid not in want:
            raise ValueError(f"reference {ref} is 0x{fid:02X}, not "
                             + "/".join(f"0x{w:02X}" for w in want))
        return fid, b, size

    def actor_meshes(self, name: str) -> List[int]:
        """The 0x36 refs of a static actor; a skeleton or anything else raises."""
        b = self.actors.get(name.upper())
        if b is None:
            raise ValueError(f"no actor {name}_ACTORDEF")
        flags, _cb, n_actions, n_comp, _bounds = struct.unpack_from("<IiIIi", self.data, b + 4)
        pos = b + 24 + (4 if flags & 1 else 0) + (28 if flags & 2 else 0)
        for _ in range(n_actions):
            (pairs,) = self.i32(pos)
            pos += 4 + 8 * pairs
        out = []
        for ref in self.i32(pos, n_comp):
            fid, cb, _s = self.frag(ref)
            if fid != 0x2D:
                raise ValueError(f"component 0x{fid:02X} is not a mesh reference "
                                 "(skeletal or sprite actor)")
            (mref,) = self.i32(cb + 4)
            self.frag(mref, 0x36)
            out.append(mref)
        if not out:
            raise ValueError("no mesh")
        return out

    def materials(self, mesh_b: int) -> List[Tuple[int, Optional[str]]]:
        """The mesh's material list: (render method, first texture file name or None)."""
        (mat_list,) = self.i32(mesh_b + 8)
        if mat_list <= 0:
            return []
        _f, lb, _s = self.frag(mat_list, 0x31)
        (n,) = self.i32(lb + 8)
        out = []
        for mref in self.i32(lb + 12, n):
            _f, mb, _s = self.frag(mref, 0x30)
            (method,) = struct.unpack_from("<I", self.data, mb + 8)
            (bref,) = self.i32(mb + 24)
            name = None
            if bref > 0:
                _f, rb, _s = self.frag(bref, 0x05)
                (info,) = self.i32(rb + 4)
                _f, ib, _s = self.frag(info, 0x04)
                iflags, count = struct.unpack_from("<Ii", self.data, ib + 4)
                pos = ib + 12 + (4 if iflags & 4 else 0) + (4 if iflags & 8 else 0)
                if count > 0:
                    (nref,) = self.i32(pos)
                    _f, nb, _s = self.frag(nref, 0x03)
                    (ln,) = struct.unpack_from("<H", self.data, nb + 8)
                    raw = _decode_string_hash(self.data[nb + 10:nb + 10 + ln])
                    name = raw.rstrip(b"\0").decode("latin1").lower()
            out.append((method, name))
        return out

    def normals(self, mesh_b: int) -> Optional[np.ndarray]:
        """The mesh's vertex normals (V, 3), signed bytes / 128, or None if it has none
        per vertex."""
        vcount, tcount, ncount = struct.unpack_from("<HHH", self.data, mesh_b + 76)
        if ncount != vcount:
            return None
        pos = mesh_b + 96 + 6 * vcount + tcount * (4 if self.old else 8)
        raw = np.frombuffer(self.data, np.int8, 3 * ncount, pos).reshape(-1, 3)
        return raw.astype(np.float64) / 128.0


# ---------------------------------------------------------------------------
# The import
# ---------------------------------------------------------------------------

@dataclass
class StockModel:
    """One imported model: its ``.mod`` and the textures it names."""
    key: str
    model_file: str
    ter: TerFile
    textures: Dict[str, bytes] = field(default_factory=dict)
    archive: str = ""
    wld: str = ""
    mesh_hash: str = ""


def model_file(key: str) -> str:
    """The packed file name of a catalogue entry's model."""
    return f"stock_{_slug(key)}.mod"


def eq_path_from_env() -> Optional[Path]:
    """``EQ_PATH`` (environment or ``.env``), or None when unset or missing."""
    from core.env import env_value

    value = env_value("EQ_PATH")
    if not value or not Path(value).is_dir():
        return None
    return Path(value)


def load_catalogue(path: Path = CATALOGUE) -> Dict[str, dict]:
    """The catalogue's models, by key."""
    return json.loads(Path(path).read_text(encoding="utf-8"))["models"]


class Importer:
    """Imports catalogue entries from the install at ``eq_path``, caching each archive it
    reads and each model by (mesh hash, source archive)."""

    def __init__(self, eq_path: Path | str, catalogue: Optional[Mapping[str, dict]] = None):
        self.eq_path = Path(eq_path)
        self.catalogue = catalogue if catalogue is not None else load_catalogue()
        self._files: Dict[str, Dict[str, bytes]] = {}
        self._wlds: Dict[Tuple[str, str], _Wld] = {}
        self._models: Dict[Tuple[str, str], StockModel] = {}

    def archive_files(self, archive: str) -> Dict[str, bytes]:
        if archive not in self._files:
            arc = PfsArchive.from_file(self.eq_path / archive)
            self._files[archive] = {f.name.lower(): f.data for f in arc.files}
        return self._files[archive]

    def wld(self, archive: str, wld: str) -> _Wld:
        if (archive, wld) not in self._wlds:
            data = self.archive_files(archive).get(wld.lower())
            if data is None:
                raise NotImportable(f"{archive} holds no {wld}")
            self._wlds[(archive, wld)] = _Wld(data)
        return self._wlds[(archive, wld)]

    def get(self, key: str) -> StockModel:
        """The imported model for catalogue entry ``key`` (raises :class:`NotImportable`)."""
        entry = self.catalogue.get(key)
        if entry is None:
            raise NotImportable(f"{key}: not in the catalogue")
        if entry.get("animation", "static") != "static":
            raise NotImportable(f"{key}: animated ({entry['animation']}), static models only")
        archive, wld = entry["source"]["archive"], entry["source"]["wld"]
        cache = (entry["mesh_hash"], archive)
        hit = self._models.get(cache)
        if hit is None:
            try:
                hit = self._import(key, entry, archive, wld)
            except NotImportable:
                raise
            except Exception as e:  # noqa: BLE001 - named, as a refusal
                raise NotImportable(f"{key}: {e}") from e
            self._models[cache] = hit
        if hit.key != key:   # same mesh under another name
            hit = StockModel(key, model_file(key), _renamed(hit.ter, model_file(key)),
                             hit.textures, hit.archive, hit.wld, hit.mesh_hash)
        return hit

    def _import(self, key: str, entry: dict, archive: str, wld_name: str) -> StockModel:
        wld = self.wld(archive, wld_name)
        files = self.archive_files(archive)
        refs = wld.actor_meshes(entry["name"])
        h = hashlib.sha1()
        for ref in refs:
            _f, mb, size = wld.frags[ref]
            h.update(wld.data[mb + 24:mb + size])
        if h.hexdigest()[:16] != entry["mesh_hash"]:
            raise NotImportable(f"{key}: the mesh in {archive} doesn't match the catalogue "
                                "(rebuild the catalogue)")

        vertices: List[Vertex] = []
        polygons: List[Polygon] = []
        materials: List[Material] = []
        textures: Dict[str, bytes] = {}
        mat_of: Dict[Tuple[str, str], int] = {}   # (texture file, shader) -> material index
        for ref in refs:
            _f, mb, size = wld.frags[ref]
            (anim,) = wld.i32(mb + 12)
            if anim > 0:
                raise NotImportable(f"{key}: vertex-animated mesh, static models only")
            mesh = _parse_mesh(wld.data, mb, mb + size, wld.old)
            if mesh is None:
                raise NotImportable(f"{key}: mesh {wld.name(mb)} does not parse")
            if not mesh.polygons:
                continue
            if len(mesh.uvs) != len(mesh.vertices):
                raise NotImportable(f"{key}: mesh {wld.name(mb)} has no UV per vertex")
            if len(mesh.polygon_textures) != len(mesh.polygons):
                raise NotImportable(f"{key}: mesh {wld.name(mb)}'s texture groups don't "
                                    "cover its polygons")
            normals = wld.normals(mb)
            local = []
            for method, tex in wld.materials(mb):
                local.append(self._material(key, method, tex, files, materials, textures,
                                            mat_of))
            base = len(vertices)
            for i, (x, y, z) in enumerate(mesh.vertices):
                n = normals[i] if normals is not None else (0.0, 0.0, 1.0)
                u, v = mesh.uvs[i]
                vertices.append(Vertex(x=x, y=y, z=z, nx=float(n[0]), ny=float(n[1]),
                                       nz=float(n[2]), u=u, v=v))
            for (a, b, c, flag), t in zip(mesh.polygons, mesh.polygon_textures):
                if max(a, b, c) >= len(mesh.vertices):
                    raise NotImportable(f"{key}: a triangle indexes past the vertices")
                if t >= len(local):
                    raise NotImportable(f"{key}: a polygon names material {t} of {len(local)}")
                polygons.append(Polygon(base + a, base + c, base + b, material=local[t],
                                        flags=FLAG_PASSABLE if flag & WLD_PASSABLE else 0))
        if not polygons:
            raise NotImportable(f"{key}: no triangles")
        name = model_file(key)
        ter = TerFile(name=name, magic=MAGIC_MODEL, version=2, materials=materials,
                      vertices=vertices, polygons=polygons)
        # float32 now, so the model round-trips through core.ter exactly
        ter = TerFile.from_bytes(ter.to_bytes(), name=name)
        return StockModel(key, name, ter, textures, archive, wld_name, entry["mesh_hash"])

    @staticmethod
    def _material(key, method, tex, files, materials, textures, mat_of) -> int:
        cls = material_class(method)
        if tex is None or cls == "boundary":
            cls, fname, dds = "boundary", BOUNDARY_TEXTURE, boundary_texture()
            stem = "boundary"
        else:
            data = files.get(tex)
            if data is None:
                raise NotImportable(f"{key}: texture {tex} is not in the archive")
            rgba = texture_rgba(data, cls, method)
            dds = rgba_to_dds(rgba[..., :3], rgba[..., 3])
            stem = tex.rsplit(".", 1)[0]
            fname = _texture_file(stem, dds)
        shader = SHADERS[cls]
        idx = mat_of.get((fname, shader))
        if idx is None:
            idx = mat_of[(fname, shader)] = len(materials)
            mat = Material(index=idx, name=f"stock_{_slug(stem)}", shader=shader)
            mat.add_diffuse(fname)
            materials.append(mat)
            textures[fname] = dds
        return idx


def _renamed(ter: TerFile, name: str) -> TerFile:
    return TerFile(name=name, magic=ter.magic, version=ter.version, materials=ter.materials,
                   vertices=ter.vertices, polygons=ter.polygons)


def import_model(key: str, eq_path: Path | str,
                 catalogue: Optional[Mapping[str, dict]] = None) -> StockModel:
    """One entry's import, uncached beyond this call."""
    return Importer(eq_path, catalogue).get(key)
