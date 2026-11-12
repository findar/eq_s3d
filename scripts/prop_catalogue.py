r"""Catalogue every stock model (step 11, task 1).

``build`` reads every actor in every ``*_obj*.s3d`` of the install. An actor definition
(WLD fragment 0x14, ``NAME_ACTORDEF``) points at its mesh through a mesh reference
(0x2D -> 0x36), or at a skeleton (0x11 -> 0x10) whose bones carry the meshes. Each mesh
names its textures through its material list (0x31 -> 0x30 -> 0x05 -> 0x04 -> 0x03).

One catalogue entry per **distinct model**: the same name with the same mesh bytes in
several archives is one entry (its ``archives`` list them all); the same name with a
different mesh is a **variant**, keyed ``NAME@zone`` (the variant found in the most
archives keeps the bare ``NAME``). The mesh hash covers each mesh's data after its
fragment references (centre, bounds, vertices, UVs, normals, colours, polygons with
flags, texture groups), so it doesn't depend on where the fragment sits in its file.

Each entry holds:

- ``source``: the archive the import reads (the first of ``archives``), and ``wld``;
- ``measured``: ``site_survey.measure_model`` over all its meshes (triangles, plan
  ``w`` x ``d``, height ``h`` and depth ``below`` the origin, solid share, solid
  footprint, walk-in), the mesh hash, ``animation`` (``static``, ``skeletal`` or
  ``vertex``) and its textures (file, size, format, frames);
- ``placed``: how often each zone's ``objects.wld`` places it (the client joins a
  placement to a model by name within the zone's own archives, design finding 0).

Task 2 adds ``observed`` (``put_observed``, from ``decor_survey.py --write``: how stock
places the model, over every zone that places it), task 3 ``tags``; ``build`` keeps both
when it rebuilds.

The file is metadata only (no mesh or texture bytes) and stable: sorted keys, one model
per line, rounded floats, so rebuilds diff cleanly. Actors that don't parse, placed
names with no model in their zone, and zones without an ``objects.wld`` are listed in
the file and printed.

Usage::

    python scripts/prop_catalogue.py build --eq-path F:\everquest_rof2
    python scripts/prop_catalogue.py build --eq-path F:\everquest_rof2 --archives befallen
    python scripts/prop_catalogue.py tag
    python scripts/prop_catalogue.py screen --eq-path F:\everquest_rof2
    python scripts/prop_catalogue.py wallside --eq-path F:\everquest_rof2
    python scripts/prop_catalogue.py outline --eq-path F:\everquest_rof2
    python scripts/prop_catalogue.py sheet --eq-path F:\everquest_rof2 --out output/prop_sheet

``tag`` (task 3) proposes every entry's Tags with a confidence and a reason (``auto_tags``);
reviewed Tags live in ``rules/decor/tags.toml`` and win when ``generators/decor/catalogue.py``
loads the two. ``screen`` (room-decor task 20) judges which floor and raised models the
wilderness Footprint gate takes on open ground and writes each one's ``open_ground``, the only
field it touches (``build`` keeps it). ``sheet`` writes a local HTML contact sheet for the review: it shows the
client's art, so it lives under ``output/`` and is never committed or published.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core.pfs import PfsArchive  # noqa: E402
from core.wld import _parse_mesh  # noqa: E402
from room_feature_survey import placed_objects  # noqa: E402
from site_survey import WLD_PASSABLE, _frags, _name, measure_model  # noqa: E402

OUT = ROOT / "rules" / "decor" / "catalogue.json"
FORMAT = 1
#: Fields later tasks own; a rebuild carries them over by key.
KEPT = ("observed", "tags", "open_ground", "wall_side", "outline")
#: ``<zone>_obj.s3d``, ``<zone>_obj2.s3d`` and ``<zone>_2_obj.s3d`` all serve ``<zone>``.
OBJ_ARCHIVE = re.compile(r"(.+?)(_2)?_obj(\d*)\.s3d", re.IGNORECASE)
MAX_AREA = 1.0e6     # u^2 of surface past which the footprint raster isn't drawn


# --- reading one archive ------------------------------------------------------------------


def _image_size(data: bytes):
    """(format, width, height) of a BMP or DDS file, whatever its extension says."""
    if data[:2] == b"BM" and len(data) >= 26:
        w, h = struct.unpack_from("<ii", data, 18)
        return "bmp", w, abs(h)
    if data[:4] == b"DDS " and len(data) >= 20:
        h, w = struct.unpack_from("<II", data, 12)
        return "dds", w, h
    return "unknown", 0, 0


class _Wld:
    """One WLD's fragments, indexed 1-based as fragment references count them."""

    def __init__(self, data: bytes):
        self.data = data
        (version,) = struct.unpack_from("<I", data, 4)
        self.old = version == 0x00015500
        self.frags = [None]  # 1-based
        self.strings = b""
        for fid, b, size, s in _frags(data):
            self.frags.append((fid, b, size))
            self.strings = s

    def frag(self, ref: int, *want: int):
        if ref <= 0 or ref >= len(self.frags):
            raise ValueError(f"reference {ref} out of range")
        fid, b, size = self.frags[ref]
        if want and fid not in want:
            raise ValueError(f"reference {ref} is 0x{fid:02X}, not "
                             + "/".join(f"0x{w:02X}" for w in want))
        return fid, b, size

    def name(self, b: int) -> str:
        return _name(self.strings, struct.unpack_from("<i", self.data, b)[0])

    def i32(self, pos: int, n: int = 1):
        return struct.unpack_from(f"<{n}i", self.data, pos)

    # --- actors ---

    def actor_meshes(self, b: int):
        """(mesh fragment refs, animation) of the 0x14 actor at ``b``. Components are
        mesh references (0x2D), skeleton references (0x11), or something else (a 2D
        sprite 0x06/0x07, a camera 0x09), which raises."""
        flags, _cb, n_actions, n_comp, _bounds = struct.unpack_from("<IiIIi", self.data, b + 4)
        pos = b + 24
        if flags & 1:
            pos += 4
        if flags & 2:
            pos += 28
        for _ in range(n_actions):
            (pairs,) = self.i32(pos)
            pos += 4 + 8 * pairs
        meshes, animation = [], "static"
        for ref in self.i32(pos, n_comp):
            fid, cb, _s = self.frag(ref)
            if fid == 0x2D:
                meshes.append(self._mesh_ref(cb))
            elif fid == 0x11:
                (sk,) = self.i32(cb + 4)
                meshes.extend(self._skeleton_meshes(sk))
                animation = "skeletal"
            else:
                raise ValueError(f"component 0x{fid:02X} is not a mesh or a skeleton")
        if not meshes:
            raise ValueError("no mesh")
        return meshes, animation

    def _mesh_ref(self, b: int) -> int:
        (ref,) = self.i32(b + 4)
        fid, _b, _s = self.frag(ref)
        if fid != 0x36:
            raise ValueError(f"mesh reference points at 0x{fid:02X} (legacy mesh)"
                             if fid == 0x2C else f"mesh reference points at 0x{fid:02X}")
        return ref

    def _skeleton_meshes(self, ref: int) -> list:
        """The 0x36 refs of a skeleton (0x10): each bone's mesh reference, then the
        trailing mesh-reference list (flag bit 9)."""
        _fid, b, _s = self.frag(ref, 0x10)
        flags, n_bones, _poly = struct.unpack_from("<IIi", self.data, b + 4)
        pos = b + 16
        if flags & 1:
            pos += 12
        if flags & 2:
            pos += 4
        refs = []
        for _ in range(n_bones):
            _nm, _fl, _track, mref, n_child = self.i32(pos, 5)
            pos += 20 + 4 * n_child
            if mref > 0 and self.frags[mref][0] == 0x2D:
                refs.append(mref)
        if flags & 0x200:
            (n,) = self.i32(pos)
            refs.extend(r for r in self.i32(pos + 4, n) if r > 0)
        out = []
        for r in refs:
            m = self._mesh_ref(self.frag(r, 0x2D)[1])
            if m not in out:
                out.append(m)
        return out

    # --- textures ---

    def material_bitmaps(self, mesh_b: int) -> list:
        """The mesh's material list, one per material index: its bitmap names (a frame
        each), or None for a material without a bitmap (invisible)."""
        (mat_list,) = self.i32(mesh_b + 8)
        if mat_list <= 0:
            return []
        _f, lb, _s = self.frag(mat_list, 0x31)
        (n,) = self.i32(lb + 8)
        out = []
        for mref in self.i32(lb + 12, n):
            _f, mb, _s = self.frag(mref, 0x30)
            (bref,) = self.i32(mb + 24)
            if bref <= 0:
                out.append(None)
                continue
            _f, rb, _s = self.frag(bref, 0x05)
            (info,) = self.i32(rb + 4)
            _f, ib, _s = self.frag(info, 0x04)
            iflags, count = struct.unpack_from("<Ii", self.data, ib + 4)
            pos = ib + 12
            if iflags & 4:
                pos += 4
            if iflags & 8:
                pos += 4
            names = []
            for nref in self.i32(pos, count):
                _f, nb, _s = self.frag(nref, 0x03)
                names.append(self._bitmap_name(nb))
            out.append(names)
        return out

    def textures(self, mesh_b: int, files: dict) -> list:
        """The mesh's material list as [{name, w, h, format, frames}], one per material
        that has a bitmap (invisible materials have none)."""
        out = []
        for names in self.material_bitmaps(mesh_b):
            if names is None:
                continue
            first = names[0] if names else ""
            fmt, w, h = _image_size(files.get(first.lower(), b""))
            if first.lower() not in files:
                fmt = "missing"
            out.append({"name": first.lower(), "w": w, "h": h, "format": fmt,
                        "frames": len(names)})
        return out

    def _bitmap_name(self, b: int) -> str:
        (ln,) = struct.unpack_from("<H", self.data, b + 8)
        raw = bytes(c ^ k for c, k in zip(self.data[b + 10:b + 10 + ln],
                                         _XOR * (ln // 8 + 1)))
        return raw.rstrip(b"\0").decode("latin1")


_XOR = bytes([0x95, 0x3A, 0xC5, 0x2A, 0x95, 0x7A, 0x95, 0x6A])


def read_archive(path: Path):
    """Every actor in one ``_obj*.s3d``: (records, failures). A record carries the
    measured fields; a failure is (archive, actor, reason)."""
    arc_name = path.name.lower()
    records, failures = [], []
    try:
        arc = PfsArchive.from_file(path)
    except Exception as e:  # noqa: BLE001 - reported, not fatal
        return [], [(arc_name, "", f"archive: {e}")]
    files = {f.name.lower(): f.data for f in arc.files}
    wlds = sorted(n for n in files if n.endswith(".wld"))
    if not wlds:
        failures.append((arc_name, "", "no .wld in archive"))
    for wname in wlds:
        try:
            wld = _Wld(files[wname])
        except Exception as e:  # noqa: BLE001
            failures.append((arc_name, "", f"{wname}: {e}"))
            continue
        for fid, b, _size in wld.frags[1:]:
            if fid != 0x14:
                continue
            name = wld.name(b).upper().replace("_ACTORDEF", "")
            try:
                records.append(_record(wld, b, name, arc_name, wname, files))
            except Exception as e:  # noqa: BLE001
                failures.append((arc_name, name, str(e)))
    return records, failures


def _record(wld: _Wld, b: int, name: str, arc_name: str, wname: str, files: dict) -> dict:
    refs, animation = wld.actor_meshes(b)
    h = hashlib.sha1()
    verts, faces, passable, textures, mesh_names = [], [], [], [], []
    off = 0
    uvs = True
    for ref in refs:
        _f, mb, size = wld.frags[ref]
        h.update(wld.data[mb + 24:mb + size])
        (anim_ref,) = wld.i32(mb + 12)
        if anim_ref > 0 and animation == "static":
            animation = "vertex"
        m = _parse_mesh(wld.data, mb, mb + size, wld.old)
        if m is None:
            raise ValueError(f"mesh {wld.name(mb)} does not parse")
        mesh_names.append(wld.name(mb))
        if not m.polygons:
            continue
        uvs = uvs and bool(m.uvs)
        v = np.array(m.vertices, float)
        pol = np.array([p[:3] for p in m.polygons], int)
        ok = (pol < len(v)).all(1)
        if not ok.all():
            raise ValueError(f"mesh {wld.name(mb)}: {int((~ok).sum())} triangles index "
                             "past the vertices")
        verts.append(v)
        faces.append(pol + off)
        passable.append((np.array([p[3] for p in m.polygons]) & WLD_PASSABLE) != 0)
        off += len(v)
        for t in wld.textures(mb, files):
            if t not in textures:
                textures.append(t)
    if not faces:
        raise ValueError("no triangles")
    meas = _measure(np.concatenate(verts), np.concatenate(faces), np.concatenate(passable))
    tex = hashlib.sha1()
    for t in textures:
        tex.update(t["name"].encode() + b"\0" + files.get(t["name"], b""))
    return {
        "name": name, "archive": arc_name, "wld": wname, "meshes": mesh_names,
        "mesh_hash": h.hexdigest()[:16], "texture_hash": tex.hexdigest()[:16],
        "animation": animation, "textures": textures,
        "measured": {
            "tris": meas["tris"], "w": round(meas["w"], 2), "d": round(meas["d"], 2),
            "h": round(meas["h"], 2), "below": round(meas["below"], 2),
            "solid_share": round(meas["solid_share"], 3),
            "footprint": _r(meas["footprint"], 1),
            "walk_in": meas["walk_in"], "walk_in_area": _r(meas["walk_in_area"], 1),
            "uvs": uvs,
        },
    }


def _r(v, n):
    return None if v is None else round(v, n)


def _measure(verts, faces, passable) -> dict:
    """``measure_model``, except for a model with more than ``MAX_AREA`` u^2 of surface
    (sky domes and mountain backdrops: its 0.5 u surface samples run to tens of millions
    of points), whose footprint and walk-in are left unmeasured (None)."""
    tri = verts[faces]
    area = 0.5 * np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    if area.sum() <= MAX_AREA:
        try:
            return measure_model(verts, faces, passable)
        except MemoryError:
            pass
    lo, hi = verts.min(0), verts.max(0)
    return {"tris": int(len(faces)), "w": float(hi[0] - lo[0]), "d": float(hi[1] - lo[1]),
            "h": float(hi[2]), "below": float(-lo[2]),
            "solid_share": float(area[~passable].sum() / max(area.sum(), 1e-9)),
            "footprint": None, "walk_in": None, "walk_in_area": None}


# --- placements -----------------------------------------------------------------------------


def read_placements(args):
    """(zone, Counter of placed names) from ``<zone>.s3d``'s objects.wld, or a reason."""
    eq_path, zone = args
    if not (eq_path / f"{zone}.s3d").exists():
        return zone, None, "no <zone>.s3d"
    try:
        objs = placed_objects(eq_path, zone)
    except Exception as e:  # noqa: BLE001
        return zone, None, f"objects.wld: {e}"
    return zone, Counter(o[3].upper() for o in objs), None


# --- build ------------------------------------------------------------------------------------


def _zone_of(archive: str) -> str:
    m = OBJ_ARCHIVE.fullmatch(archive)
    return m.group(1) if m else archive


def _join_order(archive: str):
    """The order a zone's archives are searched for a placed name: ``_obj``, ``_obj2``...,
    then ``_2_obj``."""
    m = OBJ_ARCHIVE.fullmatch(archive)
    return (bool(m.group(2)), int(m.group(3) or 0)) if m else (True, 99)


def build(eq_path: Path, out: Path, only: str | None = None, jobs: int | None = None) -> dict:
    archives = sorted(p for p in eq_path.glob("*.s3d") if OBJ_ARCHIVE.fullmatch(p.name))
    if only:
        archives = [p for p in archives if re.search(only, p.name, re.IGNORECASE)]
    with ProcessPoolExecutor(jobs) as pool:
        results = list(pool.map(read_archive, archives, chunksize=1))
        zones = sorted({_zone_of(p.name.lower()) for p in archives})
        placements = list(pool.map(read_placements, [(eq_path, z) for z in zones]))

    records = [r for rs, _f in results for r in rs]
    failures = sorted({f for _r, fs in results for f in fs})

    # one model per (name, mesh hash); variants keyed NAME@zone
    groups = defaultdict(list)
    for r in records:
        groups[(r["name"], r["mesh_hash"])].append(r)
    by_name = defaultdict(list)
    for (name, _h), rs in groups.items():
        rs.sort(key=lambda r: (r["archive"], r["wld"]))
        by_name[name].append(rs)
    models, key_of = {}, {}   # key_of[(archive, NAME)] -> catalogue key
    for name, variants in by_name.items():
        variants.sort(key=lambda rs: (-len({r["archive"] for r in rs}), rs[0]["archive"]))
        for i, rs in enumerate(variants):
            key = name
            if i:
                key = f"{name}@{_zone_of(rs[0]['archive'])}"
                if key in models:
                    key = f"{name}@{rs[0]['archive'].removesuffix('.s3d')}"
            first = rs[0]
            entry = {k: first[k] for k in ("name", "mesh_hash", "animation", "textures",
                                           "measured", "meshes")}
            entry["source"] = {"archive": first["archive"], "wld": first["wld"]}
            entry["archives"] = sorted({r["archive"] for r in rs})
            entry["texture_sets"] = len({r["texture_hash"] for r in rs})
            entry["variants"] = len(variants)
            entry["placed"] = {"total": 0, "zones": {}}
            models[key] = entry
            for r in rs:
                key_of.setdefault((r["archive"], name), key)

    # placements: by name within the zone's own archives, in _join_order
    arcs_of = defaultdict(list)
    for p in archives:
        arcs_of[_zone_of(p.name.lower())].append(p.name.lower())
    unresolved, no_objects = [], []
    placed_total = 0
    for zone, counts, why in placements:
        if counts is None:
            no_objects.append({"zone": zone, "reason": why})
            continue
        for name, n in counts.items():
            placed_total += n
            key = next((key_of[(a, name)] for a in sorted(arcs_of[zone], key=_join_order)
                        if (a, name) in key_of), None)
            if key is None:
                unresolved.append({"zone": zone, "name": name, "count": n})
                continue
            pl = models[key]["placed"]
            pl["total"] += n
            pl["zones"][zone] = pl["zones"].get(zone, 0) + n

    # carry later tasks' fields over
    if out.exists() and not only:
        try:
            old = json.loads(out.read_text(encoding="utf-8")).get("models", {})
        except (OSError, ValueError):
            old = {}
        for key, entry in models.items():
            for k in KEPT:
                if k in old.get(key, {}):
                    entry[k] = old[key][k]

    names_varied = sorted(n for n, v in by_name.items() if len(v) > 1)
    counts = {
        "archives": len(archives),
        "actors": len(records) + sum(1 for f in failures if f[1]),
        "actors_read": len(records),
        "names": len({r["name"] for r in records} | {f[1] for f in failures if f[1]}),
        "models": len(models),
        "names_with_variants": len(names_varied),
        "variants": len(models) - len(by_name),
        "animated": sum(1 for m in models.values() if m["animation"] != "static"),
        "skeletal": sum(1 for m in models.values() if m["animation"] == "skeletal"),
        "vertex_animated": sum(1 for m in models.values() if m["animation"] == "vertex"),
        "texture_animated": sum(1 for m in models.values()
                                if any(t["frames"] > 1 for t in m["textures"])),
        "same_mesh_other_textures": sum(1 for m in models.values() if m["texture_sets"] > 1),
        "failures": len(failures),
        "zones_placed": sum(1 for _z, c, _w in placements if c is not None),
        "placements": placed_total,
        "placements_resolved": placed_total - sum(u["count"] for u in unresolved),
        "unresolved_names": len(unresolved),
        "models_placed": sum(1 for m in models.values() if m["placed"]["total"]),
    }
    cat = {
        "format": FORMAT,
        "counts": counts,
        "failures": [{"archive": a, "actor": n, "reason": r} for a, n, r in failures],
        "unresolved": sorted(unresolved, key=lambda u: (u["zone"], u["name"])),
        "no_objects": no_objects,
        "models": models,
    }
    write(cat, out)
    return cat


def write(cat: dict, out: Path) -> None:
    """Sorted, one model (and one failure or unresolved name) per line."""
    def one(v):
        return json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

    lines = ["{", f' "format": {cat["format"]},', f' "counts": {one(cat["counts"])},']
    for k in ("failures", "unresolved", "no_objects"):
        rows = cat[k]
        lines.append(f' "{k}": [' + ("" if rows else "],"))
        for i, r in enumerate(rows):
            lines.append("  " + one(r) + ("," if i < len(rows) - 1 else ""))
        if rows:
            lines.append(" ],")
    lines.append(' "models": {')
    keys = sorted(cat["models"])
    for i, k in enumerate(keys):
        lines.append(f"  {one(k)}: {one(cat['models'][k])}" + ("," if i < len(keys) - 1 else ""))
    lines += [" }", "}"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def load(path: Path = OUT) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def put_observed(cat: dict, observed: dict, out: Path = OUT) -> None:
    """Replace every entry's ``observed`` (task 2, ``decor_survey.observe_all``) and
    write the file; an entry nothing places has none. Every other field is kept."""
    unknown = sorted(set(observed) - set(cat["models"]))
    if unknown:
        raise KeyError(f"observed fields for models not in the catalogue: {unknown[:5]}")
    for key, entry in cat["models"].items():
        if key in observed:
            entry["observed"] = observed[key]
        else:
            entry.pop("observed", None)
    write(cat, out)


# --- screen: the open-ground screen (room-decor task 20) -----------------------------------------
#
# Many stock models are open shells wound any way: the wilderness Footprint gate (which reads a
# solid by its winding, with no room gate's "inside one model's plan is its inside" rule) takes
# them as Enterables with no opening, or as ground cut off from Spawn (most carts, a third of the
# rocks). ``screen`` judges every floor and raised model once, at the scale placement gives it,
# and writes ``open_ground`` (true: the gate takes it on open ground; false: it doesn't). Wall,
# ceiling and skeletal models get none. Placement puts at a Site only models screened true.

#: The fine raster a model is judged on alone (u), and how far it reaches past the model.
JUDGE_STEP = 0.5
JUDGE_PAD = 12.0
#: The Mounts a Site's Props take; only these are screened.
SCREENED_MOUNTS = ("floor", "raised")


def open_ground(ter, scale: float) -> bool:
    """Whether the wilderness Footprint gate takes this model (its TER, model space) at
    ``scale`` on open ground, whatever its yaw or the raster's offset.

    Judged on a fine raster: the ground a player (half-width 1.5 u) stands on beside it must
    all lie within reach of open ground a body twice as wide (3 u: a strip the gate's 2 u
    raster always keeps joined, at any angle) reaches from outside; a pocket fails. And the
    gate's own opening measure must not find it Enterable. The model is judged standing on its
    bottom, as placement stands it (task 13), not on its origin. A Prop stands at the lowest of its
    ground, so it may sit up to ``placement.FLAT`` below the ground round it, which moves
    the gate's band up its model: the ground stood on is read with the band's least (its
    floor raised by ``FLAT``), the way out with its most (its head raised by ``FLAT``), and
    the opening at both heights."""
    from scipy.ndimage import binary_dilation, label

    from analyzer.footprints import (PLAYER_HALF_WIDTH, HEAD_HEIGHT, collidable_triangles,
                                     coverage, flat_raster, measure_opening)
    from analyzer.traverse import AgentModel
    from generators.decor.placement import FLAT, LIFT

    local = collidable_triangles(ter)
    if not len(local):
        return True
    # Placement stands a model on its bottom, LIFT over the ground (room-decor task 13).
    bottom = min(p.z for p in ter.vertices)
    local = local - np.array([0.0, 0.0, bottom - LIFT / scale])
    tris = local * scale
    low = AgentModel().max_step_up
    # Where the band's floor or head crosses a corner of the model as it sinks, and between.
    zs = np.unique(np.round(tris[:, :, 2], 2))
    events = {round(z - edge + d, 2) for z in zs for edge in (low, HEAD_HEIGHT) for d in (-0.02, 0.02)}
    sinks = sorted({0.0, FLAT / 2, FLAT} | {e for e in events if 0.0 < e < FLAT})
    for dz in (0.0, FLAT / 2, FLAT):
        if measure_opening(local - np.array([0.0, 0.0, dz / scale]), scale).enterable:
            return False
    reach = float(np.abs(tris[:, :, :2]).max()) + JUDGE_PAD
    ground = flat_raster(-reach, -reach, reach, reach, JUDGE_STEP)
    owners = np.zeros(len(tris), dtype=np.int32)
    grow = int(np.ceil((PLAYER_HALF_WIDTH + JUDGE_STEP) / JUDGE_STEP))
    for dz in sinks:
        def free(radius):
            return ~coverage(ground, tris, owners, radius, low + dz, HEAD_HEIGHT + dz).covered
        stand, wide = free(PLAYER_HALF_WIDTH), free(2 * PLAYER_HALF_WIDTH)
        labels, _ = label(wide)
        border = set(np.unique(np.r_[labels[0], labels[-1], labels[:, 0], labels[:, -1]])) - {0}
        near = binary_dilation(np.isin(labels, list(border)), iterations=grow)
        if (stand & ~near).any():
            return False
    return True


_SCREEN = {}


def _screen_init(eq_path: str) -> None:
    from generators.decor.catalogue import load as load_merged
    from generators.decor.stock import Importer

    _SCREEN["models"] = load_merged().models
    _SCREEN["importer"] = Importer(eq_path)


def _screen_keys(keys) -> dict:
    """``open_ground`` for these keys (one source archive's), in a worker."""
    from generators.decor.placement import size_of
    from generators.decor.stock import NotImportable

    models, importer = _SCREEN["models"], _SCREEN["importer"]
    out = {}
    for key in keys:
        try:
            ter = importer.get(key).ter
        except NotImportable:
            out[key] = False
            continue
        out[key] = open_ground(ter, size_of(models[key]).scale)
    importer._files.clear()
    importer._wlds.clear()
    importer._models.clear()
    return out


def screen_keys(cat: dict) -> list:
    """The entries ``screen`` judges: every model (whatever its ``use``) whose Mount, after
    ``tags.toml``, is a Site's (floor or raised), skeletal ones aside."""
    from generators.decor.catalogue import load as load_merged

    merged = load_merged().models
    return sorted(k for k in cat["models"] if k in merged and merged[k].animation != "skeletal"
                  and merged[k].tags.mount in SCREENED_MOUNTS)


def screen(cat: dict, eq_path: Path, out: Path | None = OUT, jobs: int | None = None,
           keys=None) -> dict:
    """Judge ``keys`` (default ``screen_keys``) and write each entry's ``open_ground``; every
    other entry loses its own. Only that field changes."""
    keys = screen_keys(cat) if keys is None else sorted(keys)
    by_archive = defaultdict(list)
    for k in keys:
        by_archive[cat["models"][k]["source"]["archive"]].append(k)
    chunks = sorted(by_archive.values(), key=len, reverse=True)
    flags = {}
    with ProcessPoolExecutor(jobs, initializer=_screen_init, initargs=(str(eq_path),)) as pool:
        for got in pool.map(_screen_keys, chunks):
            flags.update(got)
    for key, entry in cat["models"].items():
        if key in flags:
            entry["open_ground"] = flags[key]
        else:
            entry.pop("open_ground", None)
    if out is not None:
        write(cat, out)
    return cat


# --- outline: a floor model's plan as the gate reads it (room-decor task 23) ----------------------
#
# The room gate reads a placed model by its mesh: its collidable triangles cover the floor, and a
# pocket inside the plan hull of one model's triangles is that model's own inside. Placement read
# every model as its measured rectangle, which reaches past a round model's body: a rock stood on
# floor its body doesn't cover and sank into the floor under it, and floor between a rock and a
# wall read as rock to placement and as a cut-off pocket to the gate. ``outline`` measures that
# hull once, in the model's own frame about the middle of its plan (the bounding box of all its
# vertices, where placement centres a floor Prop; ``builder._at_origin``), model units, and
# writes it as ``outline`` = [[x, y], ...] counter-clockwise. A model with no collidable
# triangle gets none (it blocks nothing).

#: Decimals an outline point keeps (model units).
OUTLINE_DECIMALS = 2


def outline_of(ter):
    """The plan hull of a model's collidable triangles about the middle of its plan (model
    units, counter-clockwise), or None when it has no collidable triangle."""
    from analyzer.footprints import _hull, collidable_triangles

    tris = collidable_triangles(ter)
    if not len(tris):
        return None
    xs = [p.x for p in ter.vertices]
    ys = [p.y for p in ter.vertices]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    hull = _hull(tris[..., :2].reshape(-1, 2) - np.array([cx, cy]))
    if len(hull) < 3:
        return None
    return [[round(float(x), OUTLINE_DECIMALS), round(float(y), OUTLINE_DECIMALS)] for x, y in hull]


def _outline_keys(keys) -> dict:
    """{key: outline} for these keys (one source archive's), in a worker (as ``_screen_keys``)."""
    from generators.decor.stock import NotImportable

    importer = _SCREEN["importer"]
    out = {}
    for key in keys:
        try:
            ter = importer.get(key).ter
        except NotImportable:
            continue
        hull = outline_of(ter)
        if hull is not None:
            out[key] = hull
    importer._files.clear()
    importer._wlds.clear()
    importer._models.clear()
    return out


def outlines(cat: dict, eq_path: Path, out: Path | None = OUT, jobs: int | None = None,
             keys=None) -> dict:
    """Measure ``keys`` (default ``screen_keys``: floor and raised models, skeletal aside) and
    write each entry's ``outline``; every other entry loses its own. Only that field changes."""
    keys = screen_keys(cat) if keys is None else sorted(keys)
    by_archive = defaultdict(list)
    for k in keys:
        by_archive[cat["models"][k]["source"]["archive"]].append(k)
    got = {}
    with ProcessPoolExecutor(jobs, initializer=_screen_init, initargs=(str(eq_path),)) as pool:
        for part in pool.map(_outline_keys, sorted(by_archive.values(), key=len, reverse=True)):
            got.update(part)
    for key, entry in cat["models"].items():
        if key in got:
            entry["outline"] = got[key]
        else:
            entry.pop("outline", None)
    if out is not None:
        write(cat, out)
    return cat


def outline_report(cat: dict) -> None:
    rows = {k: e for k, e in cat["models"].items() if "outline" in e}
    share = []
    for e in rows.values():
        m = e.get("measured", {})
        pts = np.array(e["outline"], dtype=np.float64)
        x, y = pts[:, 0], pts[:, 1]
        area = 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))
        box = float(m.get("w", 0.0)) * float(m.get("d", 0.0))
        if box > 0:
            share.append(area / box)
    print(f"outlines: {len(rows)} models")
    if share:
        q = np.percentile(share, [10, 50, 90])
        print(f"  hull area / measured rectangle: p10 {q[0]:.2f}  p50 {q[1]:.2f}  p90 {q[2]:.2f}")


# --- wallside: which side of a wall model faces its wall (room-decor task 13) ---------------------
#
# Placement hangs a wall Prop with one side of the model to the wall. Which side that is differs by
# model (stock's TORCHPOINT has the wall at its -X, WALLTORCH200 at its +X, GKTORCH701 at its +Y),
# so ``wallside`` measures it from stock: for every stock placement of a wall model whose origin
# is within ``SIDE_REACH`` of a zone wall, the plan direction from the origin to the nearest wall
# point, turned into the model's frame (WLD yaw is 512ths of a turn, counter-clockwise: the only
# reading under which a model's placements agree), votes for one of the four sides. It writes
# ``wall_side`` = {side, n, share, standoff (stock's origin off the wall, p50, model units),
# back (the model's own reach from its origin to that side, model units)}; the side is ``-x``
# (archive decision 21) where stock never hangs the model on a wall.

#: How near a wall a stock placement's origin must be to vote (u), and the wall sampling (u).
SIDE_REACH = 8.0
SIDE_STEP = 0.5
#: The sides, as the model-frame unit vector pointing at the wall.
SIDES = {"-x": (-1.0, 0.0), "+x": (1.0, 0.0), "-y": (0.0, -1.0), "+y": (0.0, 1.0)}


def wall_side_keys(cat: dict) -> list:
    """The entries ``wallside`` measures: every model (whatever its ``use``) whose Mount,
    after ``tags.toml``, is wall, skeletal ones aside."""
    from generators.decor.catalogue import load as load_merged

    merged = load_merged().models
    return sorted(k for k in cat["models"] if k in merged and merged[k].animation != "skeletal"
                  and merged[k].tags.mount == "wall")


def _side_of(dx: float, dy: float, yaw_deg: float) -> str:
    t = -np.radians(yaw_deg)
    lx, ly = dx * np.cos(t) - dy * np.sin(t), dx * np.sin(t) + dy * np.cos(t)
    if abs(lx) >= abs(ly):
        return "+x" if lx > 0 else "-x"
    return "+y" if ly > 0 else "-y"


def _zone_sides(args) -> dict:
    """{key: [(side, distance)]} for the wanted models' placements in one zone, in a worker."""
    from scipy.spatial import cKDTree

    from core.ter import FLAG_PASSABLE
    from decor_survey import placements
    from dungeon_topology_survey import _samples
    from outdoor_dungeon_survey import load_mesh

    eq_path, zone, names = args
    objs = [o for o in placements(Path(eq_path), zone) if o.name in names]
    if not objs:
        return {}
    try:
        mesh = load_mesh(Path(eq_path), zone)
    except Exception:  # noqa: BLE001 - no terrain: nothing to measure against
        return {}
    v = np.array([(p.x, p.y, p.z) for p in mesh.vertices], dtype=np.float64)
    f = np.array([(p.v1, p.v2, p.v3) for p in mesh.polygons if not p.flags & FLAG_PASSABLE],
                 dtype=np.int64).reshape(-1, 3)
    tri = v[f]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    a = np.linalg.norm(n, axis=1)
    ok = a > 1e-9
    tri, n = tri[ok], n[ok] / a[ok, None]
    tri = tri[np.abs(n[:, 2]) < 0.7]
    p = np.array([(o.x, o.y, o.z) for o in objs])
    lo, hi = tri.min(axis=1), tri.max(axis=1)
    near = np.zeros(len(tri), bool)
    for q in p:
        near |= np.all((lo <= q + SIDE_REACH) & (hi >= q - SIDE_REACH), axis=1)
    if not near.any():
        return {}
    pts = _samples(tri[near], SIDE_STEP)
    d, i = cKDTree(pts).query(p, distance_upper_bound=SIDE_REACH)
    out = defaultdict(list)
    for o, dist, k in zip(objs, d, i):
        if not np.isfinite(dist):
            continue
        dx, dy = pts[k, 0] - o.x, pts[k, 1] - o.y
        if np.hypot(dx, dy) < 0.05:
            continue
        out[names[o.name]].append((_side_of(dx, dy, o.yaw), float(np.hypot(dx, dy) / max(o.scale, 1e-6))))
    return dict(out)


def _back_keys(keys) -> dict:
    """{key: {side: reach}} from each model's own vertices, in a worker (as ``_screen_keys``)."""
    from generators.decor.stock import NotImportable

    importer = _SCREEN["importer"]
    out = {}
    for key in keys:
        try:
            ter = importer.get(key).ter
        except NotImportable:
            continue
        v = np.array([(q.x, q.y) for q in ter.vertices], dtype=np.float64).reshape(-1, 2)
        out[key] = {s: float(max(0.0, (v @ np.array(u)).max())) for s, u in SIDES.items()}
    importer._files.clear()
    importer._wlds.clear()
    importer._models.clear()
    return out


def wall_sides(cat: dict, eq_path: Path, out: Path | None = OUT, jobs: int | None = None,
               keys=None) -> dict:
    """Measure ``keys`` (default ``wall_side_keys``) and write each entry's ``wall_side``;
    every other entry loses its own. Only that field changes."""
    from decor_survey import model_index

    keys = wall_side_keys(cat) if keys is None else sorted(keys)
    wanted = set(keys)
    index = {zk: k for zk, k in model_index(cat).items() if k in wanted}
    by_zone = defaultdict(dict)
    for (zone, name), k in index.items():
        by_zone[zone][name] = k
    votes = defaultdict(list)
    by_archive = defaultdict(list)
    for k in keys:
        by_archive[cat["models"][k]["source"]["archive"]].append(k)
    backs = {}
    with ProcessPoolExecutor(jobs, initializer=_screen_init, initargs=(str(eq_path),)) as pool:
        for got in pool.map(_zone_sides, [(str(eq_path), z, by_zone[z]) for z in sorted(by_zone)]):
            for k, rows in got.items():
                votes[k] += rows
        for got in pool.map(_back_keys, sorted(by_archive.values(), key=len, reverse=True)):
            backs.update(got)
    for key, entry in cat["models"].items():
        entry.pop("wall_side", None)
        if key not in wanted or key not in backs:
            continue
        rows = votes.get(key, [])
        count = Counter(s for s, _ in rows)
        side, n = count.most_common(1)[0] if rows else ("-x", 0)
        dist = [d for s, d in rows if s == side]
        entry["wall_side"] = {"side": side, "n": len(rows),
                              "share": round(n / len(rows), 2) if rows else 0.0,
                              "standoff": round(float(np.median(dist)), 2) if dist else None,
                              "back": round(backs[key][side], 2)}
    if out is not None:
        write(cat, out)
    return cat


def wall_side_report(cat: dict) -> None:
    rows = {k: e["wall_side"] for k, e in cat["models"].items() if "wall_side" in e}
    print(f"wall sides: {len(rows)} models, {sum(1 for r in rows.values() if r['n'])} measured on stock")
    print("  by side:", dict(Counter(r["side"] for r in rows.values() if r["n"]).most_common()))
    for k, r in sorted(rows.items(), key=lambda kv: -kv[1]["n"])[:25]:
        print(f"  {k:<24} {r['side']} n={r['n']:<4} share={r['share']:.2f} "
              f"standoff={r['standoff']} back={r['back']}")


def screen_report(cat: dict) -> None:
    from generators.decor.catalogue import load as load_merged

    merged = load_merged().models
    flags = {k: e["open_ground"] for k, e in cat["models"].items() if "open_ground" in e}
    usable = {k: v for k, v in flags.items() if merged[k].tags.use == "yes"}
    print(f"screened {len(flags)}: open ground {sum(flags.values())}, refused "
          f"{len(flags) - sum(flags.values())}; of them usable {len(usable)}: open ground "
          f"{sum(usable.values())}, refused {len(usable) - sum(usable.values())}")


# --- tag: the auto-tagger (task 3) ---------------------------------------------------------------
#
# Every Tag of every entry, from its name, its geometry and where stock placed it, each with a
# confidence (0-1) and a short reason. Placements are the strongest evidence for Mount and
# suits; a name prefix and the zones a model is placed in give the Set. ``use`` is ``review``
# except clear rejects (skeletal, doorway gates, never placed, terrain, huge); tags.toml's
# ``accept = "proposed"`` lets the ``review`` ones in (decision 25), and its lines correct them.
# ``condition`` is ``unknown``: only feedback sets ``pristine`` or ``ruined``.

#: Kinds by name, first match wins, over the name with its digits, a trailing variant letter
#: and any ``@zone`` stripped. Specific patterns come before the words they contain.
KIND_RULES = [(k, re.compile(p)) for k, p in (
    ("glow", r"GLOW"), ("light_pole", r"LIGHTPOLE"), ("bones", r"RIBCAGE"),
    ("bone_pile", r"BONEPILE"), ("tool", r"FISHPOLE"), ("bench", r"STONEBENCH"),
    ("workbench", r"WORKBENCH|SHARPEN"), ("bookcase", r"BOOKCASE|BOOKSHELF"),
    ("book", r"BOOK|BOKPILE|SCROLL|PAPER"), ("candelabra", r"CANDELABRA|CANDEL"),
    ("candle", r"CANDL"), ("chandelier", r"CHANDEL"), ("lantern", r"LANTERN|LANTRN|(?<!P)LANT$"),
    ("lamp", r"LAMP"), ("torch", r"TORCH"), ("tiki", r"TIKI"), ("brazier", r"BRAZ"),
    ("fire", r"FIRE|FLAME|BURNER"), ("light", r"LIGHT|SCONCE"),
    ("barrel", r"BARREL|BARL"), ("keg", r"KEG|^TAP$"), ("crate", r"CRATE|AKASTACK"),
    ("chest", r"CHEST|TRUNK"), ("urn", r"URN"), ("vase", r"VASE"), ("jar", r"JAR"),
    ("bucket", r"BUCKET"), ("sack", r"SACK|BAG$"), ("basket", r"BASKET"),
    ("box", r"BOX"), ("pot", r"^POT$"),
    ("fur_stack", r"FURSTACK"), ("rug", r"RUG|CARPET|MAT$"), ("bed", r"BED|BUNK|PALLET|PAWPAL|COT$|FURPILE"),
    ("throne", r"THRONE"), ("desk", r"DESK"), ("table", r"TABLE|TABL|COUNTER"),
    ("stool", r"STOOL"), ("chair", r"CHAIR|SEAT"), ("bench", r"BENCH|PEW"),
    ("couch", r"COUCH|DIVAN|SOFA"), ("shelf", r"SHELF"), ("dresser", r"DRESSER|DRAWER|CABINET|WARDROBE"),
    ("anvil", r"ANVIL"), ("forge", r"FORGE"), ("loom", r"LOOM"), ("altar", r"ALTAR"),
    ("podium", r"PODIUM|LECTERN"), ("rack", r"RACK"),
    ("banner", r"BANNER|BANN|PENN|FLAG|TAPEST|DRAPE|CURTAIN"), ("sign", r"SIGN"),
    ("hook", r"HOOK"), ("chain", r"CHAIN"), ("shackle", r"SHAKLE|SHACKLE|MANACLE"),
    ("rope", r"ROPE|NET$"), ("wall_gizmo", r"WALLGIZ|CORNERGIZ"),
    ("spike", r"HEADSTAKE|SPIKEHEAD|PUNGEE|SPIKE|STAKE|SPEARDOWN"),
    ("trophy", r"HEAD$|CLAW"), ("statue", r"STATUE|STATU$|DRAGSTAT|STONEMAN|ININICE|INICE$"),
    ("pillar", r"PILLAR|PILLR|PILL$|COLUMN|COLL$"), ("ladder", r"LADDER"),
    ("cage", r"CAGE|CELL$"), ("door", r"DOOR|GATE$"), ("plank", r"PLANK|PLNK|BOARD"),
    ("beam", r"BEAM"), ("fountain", r"FOUNT|WELL$"), ("stair", r"STAIR"),
    ("stocks", r"STOCKS"), ("gallows", r"GALLOWS"), ("tent", r"TENT|LEAN|CANOPY|HUT$"),
    ("cart", r"CART|WAGON"), ("boat", r"BOAT|SHIP$"), ("fence", r"FENCE|RAIL"),
    ("post", r"POST$|POLE$"), ("building", r"HOUSE|TEMPLE|TOWER"),
    ("machine", r"GEAR|VENT$|CLOCK|BALLIST"), ("lever", r"LEVER|LEVBASE|TOGGLE"),
    ("grate", r"GRATE"), ("effect", r"STEAM|SMOKE|MIST$"),
    ("corpse", r"CORPSE|BODY|SKELET|CARCASS|DEAD[A-Z]+O?CK|WRAPPED|BURIAL"),
    ("bones", r"BONE|RIBS"), ("skull", r"SKULL|SCULL"), ("web", r"WEB"),
    ("mushroom", r"MUSHROOM|SHROOM"), ("crystal", r"CRYSTAL|CRYS|VELIUMCHIPS"),
    ("gem", r"GEM|RUBY|EMERALD|JEWEL"), ("stalactite", r"STAL"), ("slime", r"SLIME"),
    ("food", r"MEAT|HAUNCH|FOOD|JERKY|BREAD|FISH$"),
    ("tableware", r"BOWL|DISH|PLATE|CUP|MUG|BOTTLE|GOBLET|^PAN$"),
    ("tool", r"PICK|SHOVEL|SAW$|RAKE|TOOL|CHISEL|SLEDGE|HAMMER|FISHPOLE"),
    ("weapon", r"SWORD|SHIELD|ARMOR|HELM|AXE$|SPEAR"), ("hay", r"HAY"),
    ("log", r"LOG$|LOGS|STUMP|WOOD$"), ("mound", r"MOUND|DIRT|MUD$"),
    ("terrain", r"DUNE|GROUND$"), ("brick", r"BRICK"), ("ice", r"ICE$"),
    ("rock", r"ROCK|BOULDER|STONE|RUBBLE|BLOCK"),
    ("tree", r"TREE|PINE|CEDAR|OAK$|PALM"), ("bush", r"BUSH|SHRUB|HEDGE"),
    ("vine", r"VINE|IVY"), ("grass", r"GRASS"), ("reed", r"REED|CATTAIL"), ("root", r"ROOT"),
    ("cactus", r"CACTUS"), ("plant", r"PLANT|FLOWER|FERN|LILY|WEED|KELP|CORAL|DILL"),
    ("creature", r"^DCAT$|^DRAGON$"),
)]
#: Doorway gates whose name the door pattern misses (the user's list, decision 25: DOOR1,
#: DOOR620X20, GRATE, KSDOOR101, KSDOOR102R). Kind ``door`` is proposed ``use = "no"``: doors
#: are runtime records (M6). Add any the user names.
DOOR_NAMES = {"GRATE"}
#: Short words that also turn up inside longer names: a match on one is less sure.
LOOSE = {"keg", "pot", "jar", "rope", "ice", "log", "tableware", "post", "box", "rug", "light",
         "trophy", "statue", "plant", "terrain", "effect", "mound"}

#: A name prefix gives the Set when what follows it names a kind (PALLET isn't Paineel's).
SET_PREFIXES = (
    ("PAW", "gnoll"), ("GUK", "froglok"), ("OGG", "ogre"), ("OG", "ogre"), ("GROB", "troll"),
    ("CB", "iksar"), ("KS", "iksar"), ("SB", "iksar"), ("KN", "iksar"), ("IK", "iksar"),
    ("KUR", "iksar"), ("AKA", "gnome"), ("PA", "erudite"), ("ER", "erudite"),
    ("FEL", "high_elf"), ("KAL", "dwarf"), ("HAL", "barbarian"), ("NER", "dark_elf"),
    ("DARK", "dark_elf"), ("GOB", "goblin"), ("PER", "goblin"), ("CC", "coldain"),
    ("BH", "undead"), ("QEY", "human"), ("FRE", "human"), ("FREEPORT", "human"),
    ("GIANT", "giant"),
)
#: The culture of a zone's people, for the Set a model's placements suggest.
ZONE_SETS = {
    "gnoll": "paw blackburrow", "goblin": "runnyeye soldunga permafrost",
    "kobold": "soldungb", "froglok": "guktop gukbottom guka gukb gukc gukd guke gukf gukg gukh",
    "iksar": "cabeast cabwest kaesora sebilis kurn karnor dalnir charasis",
    "ogre": "oggok feerrott", "troll": "grobb innothule", "dark_elf": "neriaka neriakb neriakc",
    "high_elf": "felwithea felwitheb", "wood_elf": "gfaydark", "dwarf": "kaladima kaladimb",
    "gnome": "akanon steamfont", "halfling": "rivervale", "barbarian": "halas everfrost",
    "erudite": "erudnext erudnint paineel", "human": "qeynos qeynos2 qrg freportw freportn freporte",
    "undead": "befallen unrest", "coldain": "thurgadina thurgadinb crystal",
    "vah_shir": "sharvahl", "giant": "kael",
    "planar": "airplane fearplane hateplaneb growthplane mischiefplane bothunder codecay hohonora "
              "hohonorb nightmareb poair podisease poeartha poearthb pofire poinnovation pojustice "
              "poknowledge ponightmare postorms potactics potimea potimeb potorment potranquility "
              "povalor powater solrotower",
}
ZONE_SET = {z: s for s, zs in ZONE_SETS.items() for z in zs.split()}
#: The expansion each archive's zone shipped with; anything else is ``later``.
ZONE_ERAS = {
    "classic": "akanon arena befallen beholder blackburrow butcher cauldron cazicthule crushbone "
               "eastkarana ecommons erudnext erudnint erudsxing everfrost fearplane feerrott "
               "felwithea felwitheb freporte freportn freportw gfaydark grobb gukbottom guktop halas "
               "hateplaneb highkeep hole innothule kaladima kaladimb kedge kithicor lakerathe "
               "lavastorm lfaydark mistmoore najena nektulos neriaka neriakb neriakc northkarana nro "
               "oasis oggok oot paineel paw permafrost qcat qey2hh1 qeynos qeynos2 qeytoqrg qrg "
               "rathemtn rivervale runnyeye soldunga soldungb soltemple southkarana sro steamfont "
               "tox unrest airplane",
    "kunark": "burningwood cabeast cabwest charasis chardok chardokb citymist dalnir dreadlands "
              "droga emeraldjungle fieldofbone firiona frontiermtns kaesora karnor kurn "
              "lakeofillomen nurga overthere sebilis skyfire swampofnohope timorous trakanon "
              "veeshan warslikswood kerraridge stonebrunt warrens",
    "velious": "cobaltscar crystal eastwastes frozenshadow greatdivide growthplane iceclad kael "
               "mischiefplane necropolis sirens skyshrine sleeper templeveeshan thurgadina "
               "thurgadinb velketor wakening westwastes",
    "luclin": "acrylia akheva dawnshroud echo fungusgrove griegsend grimling hollowshade katta "
              "letalis maiden mseru netherbian nexus paludal scarlet shadeweaver shadowhaven "
              "sharvahl sseru ssratemple tenebrous thedeep thegrey umbral twilight vexthal",
    "pop": "bothunder codecay hohonora hohonorb nightmareb poair podisease poeartha poearthb pofire "
           "poinnovation pojustice poknowledge ponightmare postorms potactics potimea potimeb "
           "potorment potranquility povalor powater solrotower jaggedpine",
}
ZONE_ERA = {z: e for e, zs in ZONE_ERAS.items() for z in zs.split()}
#: Where a kind attaches when nothing better says (placements win).
KIND_MOUNT = {
    "torch": "wall", "lamp": "wall", "sign": "wall", "banner": "wall", "shackle": "wall",
    "trophy": "wall", "wall_gizmo": "wall", "hook": "ceiling", "chain": "ceiling",
    "chandelier": "ceiling", "glow": None, "lantern": None, "web": None, "stalactite": None,
    "root": None, "effect": None,
}
#: Room types (and themes) a kind suits, before any review.
KIND_SUITS = {
    "bed": ("barracks",), "fur_stack": ("barracks", "warren"),
    "table": ("barracks", "guard_post"), "chair": ("barracks", "guard_post", "throne"),
    "stool": ("barracks", "guard_post"), "bench": ("barracks", "guard_post", "shrine"),
    "couch": ("throne",), "throne": ("throne", "inner_sanctum"), "rug": ("throne", "entry_hall"),
    "altar": ("shrine", "ritual_chamber", "inner_sanctum", "sacrifice_chamber", "temple"),
    "candle": ("shrine", "ritual_chamber", "inner_sanctum"),
    "candelabra": ("shrine", "ritual_chamber", "inner_sanctum", "throne"),
    "brazier": ("shrine", "ritual_chamber", "summoning_hall", "throne"),
    "chandelier": ("throne", "entry_hall"),
    "bookcase": ("laboratory", "wizard_lair"), "book": ("laboratory", "wizard_lair"),
    "podium": ("shrine", "laboratory"), "desk": ("laboratory",), "jar": ("laboratory",),
    "shelf": ("laboratory", "storeroom"),
    "barrel": ("storeroom",), "keg": ("storeroom",), "crate": ("storeroom",),
    "box": ("storeroom",), "sack": ("storeroom",), "basket": ("storeroom",),
    "chest": ("vault", "storeroom"), "gem": ("vault",), "urn": ("ossuary", "shrine", "tomb"),
    "anvil": ("forge", "lava_forge"), "forge": ("forge", "lava_forge"), "workbench": ("forge",),
    "tool": ("forge", "mine_delve"), "rack": ("armory",), "weapon": ("armory",),
    "shackle": ("prison_cell",), "cage": ("prison_cell",), "stocks": ("prison_cell",),
    "chain": ("prison_cell",), "hook": ("prison_cell", "sacrifice_chamber"),
    "spike": ("sacrifice_chamber", "gatehouse"),
    "bones": ("ossuary", "tomb", "dragon_lair"), "bone_pile": ("ossuary", "tomb", "dragon_lair"),
    "skull": ("ossuary", "tomb"), "corpse": ("ossuary", "tomb", "sacrifice_chamber"),
    "web": ("collapsed_gallery", "tomb"), "rock": ("collapsed_gallery", "warren"),
    "crystal": ("collapsed_gallery", "ice_keep"), "mushroom": ("warren", "sump"),
    "slime": ("sump",), "food": ("storeroom", "barracks"), "torch": ("passage", "entry_hall", "gatehouse"),
    "lamp": ("passage", "entry_hall"), "lantern": ("passage", "entry_hall"),
    "tiki": ("entry_hall", "shrine"), "banner": ("throne", "entry_hall", "gatehouse"),
    "statue": ("shrine", "entry_hall", "temple"), "trophy": ("throne", "barracks"),
    "fire": ("warren", "barracks"),
}
HUGE = 100.0      # a model past this (u, plan or height at stock's median scale) is no Prop
TERRAIN = 400.0   # u² one can walk inside: a model that big is ground, not a Prop
SOLID, PASSABLE = 0.95, 0.05


def _base(name: str) -> str:
    return re.sub(r"\d+[A-Z]?$", "", name.upper().split("@")[0])


def _set_prefix(base: str):
    """(set, rest) when the name starts with a culture's prefix and the rest names a kind."""
    for pre, s in sorted(SET_PREFIXES, key=lambda p: -len(p[0])):
        rest = base[len(pre):]
        if base.startswith(pre) and len(rest) >= 3 and any(rx.search(rest) for _k, rx in KIND_RULES):
            return s, rest
    return None, base


def _kind(base: str):
    """(kind, confidence, reason) from the name."""
    from generators.decor.catalogue import KINDS
    _s, rest = _set_prefix(base)
    for kind, rx in KIND_RULES:
        m = rx.search(rest) or rx.search(base)
        if not m:
            continue
        word = rest if rx.search(rest) else base
        left = len(word) - (m.end() - m.start())
        conf = 0.85 if left == 0 else 0.75 if left <= 3 else 0.6
        if kind in LOOSE:
            conf -= 0.15
        assert kind in KINDS, kind
        return kind, conf, f"name {m.group(0) or word}"
    return None, 0.0, "name matches no kind"


def _obs_mount(obs):
    """(mount, share, n) from the placements, unknown Mounts left out."""
    if not obs:
        return None, 0.0, 0
    shares = {m: s for m, s in obs.get("mount", {}).items() if m != "unknown"}
    if not shares:
        return None, 0.0, 0
    n = round(obs["n"] * sum(shares.values()))
    top = max(shares, key=shares.get)
    return top, shares[top] / sum(shares.values()), n


def _mount(kind, obs, meas):
    top, share, n = _obs_mount(obs)
    prior = KIND_MOUNT.get(kind, "floor") if kind else None
    if top is None and prior is None:
        h, below = meas.get("h", 0.0), meas.get("below", 0.0)
        if below > 0.6 * max(h + below, 1e-6):
            return "ceiling", 0.35, "hangs below its origin"
        return "floor", 0.3, "stands on its origin"
    if top is None:
        return prior, 0.45, f"usual for a {kind}"
    c = share * n / (n + 2)
    if prior is None or prior == top:
        conf = 1 - (1 - c) * (0.6 if prior == top else 1.0)
        return top, round(conf, 2), f"placed {share:.0%} {top} (n={n})"
    if c >= 0.5:
        return top, round(c * 0.9, 2), f"placed {share:.0%} {top} (n={n}); a {kind} is usually {prior}"
    return prior, 0.4, f"a {kind} is usually {prior}; placed {share:.0%} {top} (n={n})"


def _set(base, entry):
    pre, _rest = _set_prefix(base)
    zones = entry["placed"]["zones"]
    total = sum(zones.values())
    by_set = Counter()
    for z, n in zones.items():
        by_set[ZONE_SET.get(z)] += n
    mapped = {s: n for s, n in by_set.items() if s}
    top = max(mapped, key=mapped.get) if mapped else None
    if pre:
        share = by_set.get(pre, 0) / total if total else 0.0
        if not total:
            return pre, 0.7, f"prefix {base[:len(base) - len(_rest)]}"
        if share >= 0.3:
            return pre, 0.9, f"prefix, and {share:.0%} placed in {pre} zones"
        return pre, 0.55, f"prefix; but placed {share:.0%} in {pre} zones"
    if not total:
        zs = {_zone_of(a) for a in entry["archives"]}
        sets = {ZONE_SET.get(z) for z in zs}
        if len(zs) == 1 and None not in sets:
            return sets.pop(), 0.3, "unplaced; only in a culture's archive"
        return "neutral", 0.3, "unplaced, no prefix"
    cultures = len([s for s in by_set if s]) + (1 if None in by_set else 0)
    if len(zones) >= 4 or cultures >= 3:
        return "neutral", 0.8, f"placed in {len(zones)} zones of {cultures} peoples"
    if top and mapped[top] / total >= 0.9:
        return top, 0.5, f"placed only in {top} zones ({len(zones)})"
    return "neutral", 0.5, f"placed in {len(zones)} zones, no single people"


def _era(entry):
    eras = {ZONE_ERA.get(_zone_of(a), "later") for a in entry["archives"]}
    from generators.decor.catalogue import ERAS
    first = min(eras, key=ERAS.index)
    conf = 0.9 if len(eras) == 1 else 0.75
    if first == "later":
        conf = 0.5
    return first, conf, "archives of " + ", ".join(sorted(eras, key=ERAS.index))


def _collision(meas):
    s = meas.get("solid_share", 0.0)
    if s >= SOLID:
        return "solid", 1.0, f"{s:.0%} of its surface solid"
    if s <= PASSABLE:
        return "passable", 1.0, f"{s:.0%} of its surface solid"
    return "partial", 1.0, f"{s:.0%} of its surface solid"


def _suits(kind, obs):
    from generators.decor.catalogue import SUITS
    out, why = [], []
    if obs and obs.get("types"):
        n = sum(obs["types"].values())
        zt = [t for t, c in obs["types"].items() if c >= 2 or c / n >= 0.2]
        out += zt
        why.append("placed in " + "/".join(zt))
    for s in KIND_SUITS.get(kind, ()):
        if s in SUITS and s not in out:
            out.append(s)
    if kind in KIND_SUITS:
        why.append(f"a {kind}")
    n = obs["n"] if obs else 0
    conf = 0.35 + 0.2 * (kind in KIND_SUITS) + (0.25 if n >= 20 else 0.2 if n >= 5 else 0.1 if n else 0)
    return out, round(conf, 2), "; ".join(why) or "nothing to go on"


def _use(entry, kind):
    meas = entry["measured"]
    obs = entry.get("observed") or {}
    scale = (obs.get("scale") or [1, 1, 1])[1] or 1.0
    size = max(meas.get("w", 0), meas.get("d", 0), meas.get("h", 0) + meas.get("below", 0)) * scale
    if entry["animation"] == "skeletal":
        return "no", 1.0, "animated (skeletal); the import refuses skeletal models"
    if kind == "door":
        return "no", 0.9, "a doorway gate; doors are runtime records (M6)"
    if meas.get("uvs") is False:
        return "no", 1.0, "a mesh without UVs (the import refuses it)"
    if not entry["placed"]["total"]:
        return "no", 0.8, "stock never places it"
    if kind == "terrain" or (meas.get("walk_in_area") or 0) > TERRAIN:
        return "no", 0.8, "walk-in or terrain (a building, tent or ground, not a Prop)"
    if size > HUGE:
        return "no", 0.8, f"huge ({size:.0f} u at stock's scale)"
    if entry["animation"] == "vertex":
        return "review", 0.5, "awaits review (vertex-animated: imports frozen in its rest pose)"
    return "review", 0.5, "awaits review"


def _condition():
    """Proposed ``unknown``: no stock name marks a ruined or pristine version (decision 25's
    probe); feedback sets it."""
    return "unknown", 0.5, "names say nothing of it; set by feedback"


def auto_tags(key: str, entry: dict) -> dict:
    """The proposed Tags of one catalogue entry: values, ``conf`` and ``why`` per Tag."""
    from decor_survey import category as name_category
    from generators.decor.catalogue import KINDS
    base = _base(key)
    obs = entry.get("observed")
    meas = entry["measured"]
    kind, kconf, kwhy = _kind(base)
    if key.split("@")[0].upper() in DOOR_NAMES and kind != "door":
        kind, kconf, kwhy = "door", 0.9, "a doorway gate by name (decision 25)"
    survey_cat = name_category(key)
    if kind is None:
        kind, kconf, kwhy = survey_cat, 0.2, f"no kind in the name; Category {survey_cat} by name"
    cat = KINDS[kind]
    cconf = min(1.0, max(kconf, 0.2) + (0.1 if cat == survey_cat else -0.1))
    cwhy = f"the kind {kind}" + ("" if cat == survey_cat else f" (the survey's name pattern says {survey_cat})")
    vals = {
        "category": (cat, cconf, cwhy), "kind": (kind, kconf, kwhy),
        "mount": _mount(kind, obs, meas), "set": _set(base, entry), "era": _era(entry),
        "collision": _collision(meas), "suits": _suits(kind, obs), "condition": _condition(),
        "use": _use(entry, kind),
    }
    tags = {f: v[0] for f, v in vals.items()}
    tags["conf"] = {f: round(float(v[1]), 2) for f, v in vals.items()}
    tags["why"] = {f: v[2] for f, v in vals.items()}
    return tags


def tag(cat: dict, out: Path | None = OUT) -> dict:
    """Propose every entry's Tags and write the catalogue (when ``out``)."""
    for key, entry in cat["models"].items():
        entry["tags"] = auto_tags(key, entry)
    if out is not None:
        write(cat, out)
    return cat


def tag_report(cat: dict) -> None:
    from generators.decor.catalogue import TAG_FIELDS
    models = cat["models"]
    print(f"tagged {len(models)} models")
    bands = Counter()
    for m in models.values():
        low = min(m["tags"]["conf"][f] for f in TAG_FIELDS if f not in ("use", "condition"))
        bands["<0.4" if low < 0.4 else "0.4-0.6" if low < 0.6 else "0.6-0.8" if low < 0.8 else ">=0.8"] += 1
    print("  lowest Tag confidence: " + ", ".join(f"{b} {bands[b]}" for b in
                                                    ("<0.4", "0.4-0.6", "0.6-0.8", ">=0.8")))
    for f in ("category", "mount", "set", "use"):
        c = Counter(m["tags"][f] for m in models.values())
        print(f"  {f}: " + ", ".join(f"{k} {v}" for k, v in c.most_common()))
    why = Counter(m["tags"]["why"]["use"].split(" (")[0] for m in models.values() if m["tags"]["use"] == "no")
    print("  use = no: " + ", ".join(f"{k} {v}" for k, v in why.most_common()))


# --- sheet: the local review sheet (task 3) --------------------------------------------------------
#
# One card per model: a textured thumbnail (top and side views, from a small numpy rasteriser),
# its measures, where stock placed it, its Tags with confidence and reason, and the tags.toml
# line that sets them. Grouped by proposed kind, lowest confidence first. It shows the client's
# art: it's written under output/ and never committed or published.

THUMB = 150           # each view's side (px); drawn at twice that and shrunk
LIGHT_DIR = np.array([0.4, -0.5, 0.75]) / np.linalg.norm([0.4, -0.5, 0.75])


def load_model(files: dict, wld: "_Wld", name: str):
    """(vertices, triangles, uvs per triangle corner, texture name per triangle) of the
    actor ``name`` in a parsed WLD. Skeletal meshes come in their bones' own frames
    (unposed)."""
    for fid, b, _size in wld.frags[1:]:
        if fid == 0x14 and wld.name(b).upper().replace("_ACTORDEF", "") == name:
            break
    else:
        raise KeyError(f"{name}: no actor")
    refs, _anim = wld.actor_meshes(b)
    verts, faces, uvs, texs = [], [], [], []
    off = 0
    for ref in refs:
        _f, mb, size = wld.frags[ref]
        m = _parse_mesh(wld.data, mb, mb + size, wld.old)
        if m is None or not m.polygons:
            continue
        v = np.array(m.vertices, float)
        pol = np.array([p[:3] for p in m.polygons], int)
        uv = np.array(m.uvs, float) if m.uvs else np.zeros((len(v), 2))
        mats = wld.material_bitmaps(mb)
        pt = m.polygon_textures or [0] * len(pol)
        for t in pt:
            names = mats[t] if 0 <= t < len(mats) else None
            texs.append(names[0].lower() if names else None)
        verts.append(v)
        faces.append(pol + off)
        uvs.append(uv)
        off += len(v)
    if not faces:
        raise ValueError(f"{name}: no triangles")
    v = np.concatenate(verts)
    f = np.concatenate(faces)
    return v, f, np.concatenate(uvs)[f], texs


def _image(data: bytes):
    """A texture file as an RGBA array (BMP or DDS, whatever its extension says), or None."""
    from io import BytesIO
    from PIL import Image
    try:
        im = Image.open(BytesIO(data))
        return np.asarray(im.convert("RGBA"))
    except Exception:  # noqa: BLE001 - an unreadable texture draws grey
        return None


def _view(name: str) -> np.ndarray:
    """Rows: screen right, screen up, towards the viewer (EQ is Z up)."""
    if name == "top":
        return np.array([[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]])
    az, el = np.radians(-35.0), np.radians(18.0)
    right = np.array([np.cos(az), np.sin(az), 0.0])
    fwd = np.array([-np.sin(az), np.cos(az), 0.0])       # into the screen, level
    toward = -(np.cos(el) * fwd) + np.array([0, 0, np.sin(el)])
    up = np.cross(toward, right)
    return np.array([right, up, toward])


def rasterise(verts, faces, uvs, texs, images: dict, view: str, size: int = THUMB):
    """An RGBA image (``size`` square) of the model from ``view`` (``top`` or ``side``):
    orthographic, z-buffered, textured (nearest texel, alpha-tested), lit by its normal from
    both sides (stock meshes are open and wound either way)."""
    from PIL import Image
    big = size * 2
    rot = _view(view)
    p = verts @ rot.T
    lo, hi = p[:, :2].min(0), p[:, :2].max(0)
    span = max(float((hi - lo).max()), 1e-6)
    scale = (big - 8) / span
    sx = (p[:, 0] - (lo[0] + hi[0]) / 2) * scale + big / 2
    sy = big / 2 - (p[:, 1] - (lo[1] + hi[1]) / 2) * scale
    depth = p[:, 2]
    col = np.zeros((big, big, 4), np.uint8)
    zbuf = np.full((big, big), -np.inf)
    tri = verts[faces]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    nn = np.linalg.norm(n, axis=1)
    shade = 0.45 + 0.55 * np.abs((n / np.maximum(nn, 1e-12)[:, None]) @ LIGHT_DIR)
    order = np.argsort(depth[faces].mean(1))   # far first: fewer overwrites
    for i in order:
        if nn[i] < 1e-12:
            continue
        tex = texs[i]
        if tex is None:
            continue   # an invisible material
        img = images.get(tex)
        a, b, c = faces[i]
        x = np.array([sx[a], sx[b], sx[c]])
        y = np.array([sy[a], sy[b], sy[c]])
        x0, x1 = max(int(np.floor(x.min())), 0), min(int(np.ceil(x.max())), big - 1)
        y0, y1 = max(int(np.floor(y.min())), 0), min(int(np.ceil(y.max())), big - 1)
        if x1 < x0 or y1 < y0:
            continue
        den = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
        if abs(den) < 1e-9:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        w0 = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / den
        w1 = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / den
        w2 = 1 - w0 - w1
        inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not inside.any():
            continue
        z = w0 * depth[a] + w1 * depth[b] + w2 * depth[c]
        zb = zbuf[y0:y1 + 1, x0:x1 + 1]
        draw = inside & (z > zb)
        if not draw.any():
            continue
        if img is None:
            rgba = np.broadcast_to(np.array([150, 150, 150, 255], np.uint8), draw.shape + (4,))
        else:
            u = w0 * uvs[i, 0, 0] + w1 * uvs[i, 1, 0] + w2 * uvs[i, 2, 0]
            v = w0 * uvs[i, 0, 1] + w1 * uvs[i, 1, 1] + w2 * uvs[i, 2, 1]
            th, tw = img.shape[:2]
            tx = (np.floor(u * tw).astype(np.int64)) % tw
            ty = (np.floor(v * th).astype(np.int64)) % th
            rgba = img[ty, tx]
            draw &= rgba[..., 3] >= 128
        if not draw.any():
            continue
        lit = np.clip(rgba[..., :3].astype(float) * shade[i], 0, 255).astype(np.uint8)
        block = col[y0:y1 + 1, x0:x1 + 1]
        block[draw, :3] = lit[draw]
        block[draw, 3] = 255
        zb[draw] = z[draw]
    return Image.fromarray(col, "RGBA").resize((size, size), Image.LANCZOS)


def _thumb_name(key: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", key) + ".png"


def render_archive(args):
    """Render every wanted model of one archive: [(key, file or None, error or None)]."""
    from PIL import Image
    path, wanted, out_dir = args      # wanted: [(key, name, wld)]
    done = []
    try:
        arc = PfsArchive.from_file(path)
    except Exception as e:  # noqa: BLE001
        return [(k, None, f"archive: {e}") for k, _n, _w in wanted]
    files = {f.name.lower(): f.data for f in arc.files}
    wlds = {}
    for key, name, wname in wanted:
        try:
            if wname not in wlds:
                wlds[wname] = _Wld(files[wname])
            v, f, uv, texs = load_model(files, wlds[wname], name)
            images = {t: _image(files[t]) for t in set(texs) if t and t in files}
            top = rasterise(v, f, uv, texs, images, "top")
            side = rasterise(v, f, uv, texs, images, "side")
            both = Image.new("RGBA", (THUMB * 2 + 6, THUMB), (0, 0, 0, 0))
            both.paste(top, (0, 0))
            both.paste(side, (THUMB + 6, 0))
            fname = _thumb_name(key)
            both.save(out_dir / fname, optimize=True)
            done.append((key, fname, None))
        except Exception as e:  # noqa: BLE001 - one bad model doesn't stop the sheet
            done.append((key, None, str(e)))
    return done


def sheet_keys(cat: dict, everything: bool = False) -> list:
    """The entries the sheet shows: those placed in finding 1's dungeons and cities (archive
    decision 4: 581 names), or every placed one."""
    from decor_survey import CITIES
    from wall_survey import STYLES
    zones = set(STYLES) | set(CITIES)
    return sorted(k for k, m in cat["models"].items()
                  if m["placed"]["total"] and (everything or set(m["placed"]["zones"]) & zones))


def _card(key: str, raw: dict, model, thumb, error) -> dict:
    from generators.decor.catalogue import TAG_FIELDS, review_line
    t = model.tags
    values = {f: (list(getattr(t, f)) if f == "suits" else getattr(t, f)) for f in TAG_FIELDS}
    obs = raw.get("observed") or {}
    zones = sorted((obs.get("zones") or {}).items(), key=lambda kv: -kv[1]["n"])
    return {
        "key": key, "name": raw["name"], "thumb": thumb, "error": error,
        "anim": raw["animation"], "m": raw["measured"],
        "tex": [f'{x["name"]} {x["w"]}x{x["h"]}' + (f' ({x["frames"]} frames)' if x["frames"] > 1 else "")
                for x in raw["textures"]],
        "archives": len(raw["archives"]), "texsets": raw.get("texture_sets", 1),
        "placed": raw["placed"]["total"],
        "obs": {k: obs.get(k) for k in ("n", "types", "over", "wall", "under", "scale", "mount", "near")},
        "zones": [[z, v["n"], v["type"], v["mount"], v.get("over"), v.get("wall")] for z, v in zones[:8]],
        "more_zones": max(len(zones) - 8, 0),
        "tags": values, "conf": dict(t.confidence), "why": dict(t.why),
        "reviewed": list(t.reviewed), "note": t.note, "low": round(t.lowest, 2),
        "line": review_line(key, values),
    }


def write_sheet(eq_path: Path, out: Path, catalogue: Path = OUT, tags: Path | None = None,
                everything: bool = False, jobs: int | None = None) -> Path:
    """Render the thumbnails and write ``out/index.html``; returns its path."""
    from generators.decor import catalogue as dc
    tags = tags or catalogue.parent / dc.TAGS_FILE
    merged = dc.load(catalogue, tags)
    cat = load(catalogue)
    keys = sheet_keys(cat, everything)
    img_dir = out / "img"
    img_dir.mkdir(parents=True, exist_ok=True)
    by_arc = defaultdict(list)
    for k in keys:
        m = cat["models"][k]
        by_arc[m["source"]["archive"]].append((k, m["name"], m["source"]["wld"]))
    jobs_in = [(eq_path / a, w, img_dir) for a, w in sorted(by_arc.items())]
    rendered = {}
    with ProcessPoolExecutor(jobs) as pool:
        for rows in pool.map(render_archive, jobs_in, chunksize=1):
            for k, fname, err in rows:
                rendered[k] = (fname, err)
    cards = [_card(k, cat["models"][k], merged.models[k], *rendered.get(k, (None, "not rendered")))
             for k in keys]
    meta = {"kinds": dict(sorted(merged.kinds.items())), "sets": list(merged.sets),
            "fields": list(dc.TAG_FIELDS), "count": len(cards),
            "names": len({c["name"] for c in cards}),
            "failed": sum(1 for c in cards if not c["thumb"])}
    page = out / "index.html"
    blob = json.dumps({"meta": meta, "cards": cards}, ensure_ascii=False, separators=(",", ":"))
    page.write_text(SHEET_HTML.replace("__DATA__", blob.replace("</", "<\\/")), encoding="utf-8")
    print(f"{len(cards)} entries ({meta['names']} names), {meta['failed']} without a thumbnail")
    for c in cards:
        if c["error"]:
            print(f"  {c['key']}: {c['error']}")
    return page


SHEET_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Prop review sheet</title>
<style>
:root{--bg:#f6f5f2;--card:#fff;--ink:#1d1d1b;--mute:#6b6a65;--line:#e2e0da;--accent:#2f6fb0;
--lo:#c0392b;--mid:#d68910;--hi:#1e8449;--chip:#efeee9;--code:#f1f0ec;--thumb:#2a2b30}
@media (prefers-color-scheme:dark){:root{--bg:#17181b;--card:#202226;--ink:#e8e6e1;--mute:#9a988f;
--line:#33353a;--accent:#6aa5e0;--lo:#e2685a;--mid:#e8a33c;--hi:#52be80;--chip:#2b2d32;--code:#1a1b1e;--thumb:#111214}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 16px}
h1{font-size:17px;margin:0 0 6px}
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.bar input,.bar select{font:inherit;padding:5px 8px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--ink)}
.bar input[type=search]{min-width:200px;flex:1;max-width:340px}
.stat{color:var(--mute);font-size:13px}
main{padding:12px 16px 120px}
h2{font-size:15px;margin:22px 0 8px;display:flex;gap:10px;align-items:baseline}
h2 small{color:var(--mute);font-weight:normal}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px;display:flex;flex-direction:column;gap:6px}
.card.rev{border-color:var(--hi)}
.thumb{background:var(--thumb);border-radius:6px;display:flex;justify-content:center;min-height:80px}
.thumb img{max-width:100%;image-rendering:auto}
.thumb .err{color:#ccc;padding:20px;font-size:12px}
.title{display:flex;justify-content:space-between;gap:6px;align-items:baseline}
.title b{font-size:15px;word-break:break-all}
.badge{font-size:11px;padding:1px 6px;border-radius:9px;background:var(--chip);color:var(--mute);white-space:nowrap}
.badge.no{background:var(--lo);color:#fff}.badge.yes{background:var(--hi);color:#fff}
.meas,.obs{font-size:12px;color:var(--mute)}
table.tags{width:100%;border-collapse:collapse;font-size:12.5px}
table.tags td{padding:2px 4px;border-top:1px solid var(--line);vertical-align:top}
table.tags td:first-child{color:var(--mute);width:62px}
table.tags td.v{font-weight:600;width:110px;word-break:break-word}
table.tags td.why{color:var(--mute);font-size:11.5px}
.conf{display:inline-block;width:30px;text-align:right;font-variant-numeric:tabular-nums;font-size:11px;font-weight:600}
.c-lo{color:var(--lo)}.c-mid{color:var(--mid)}.c-hi{color:var(--hi)}
.rv{color:var(--hi);font-size:11px}
code.line{display:block;background:var(--code);border-radius:5px;padding:5px 6px;font-size:11px;word-break:break-all;white-space:pre-wrap}
.acts{display:flex;gap:6px;flex-wrap:wrap}
button{font:inherit;font-size:12.5px;padding:3px 10px;border-radius:6px;border:1px solid var(--line);background:var(--chip);color:var(--ink);cursor:pointer}
button:hover{border-color:var(--accent)}
button.yes{border-color:var(--hi)}button.no{border-color:var(--lo)}
details summary{cursor:pointer;color:var(--mute);font-size:12px}
#tray{position:fixed;left:0;right:0;bottom:0;background:var(--card);border-top:1px solid var(--line);padding:8px 16px;z-index:6;max-height:40vh;display:flex;flex-direction:column;gap:6px}
#tray textarea{width:100%;min-height:52px;max-height:28vh;font:11.5px ui-monospace,Consolas,monospace;background:var(--code);color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:6px}
#tray .row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.hidden{display:none}
@media (max-width:600px),(max-height:600px){header{position:static}#tray{max-height:30vh}}
@media (max-width:420px){.grid{grid-template-columns:1fr}}
#tray.min textarea{display:none}
</style></head><body>
<header>
<h1>Prop review sheet <span class="stat" id="stat"></span></h1>
<div class="bar">
<input type="search" id="q" placeholder="Search name, kind, zone, reason...">
<select id="fkind"><option value="">every kind</option></select>
<select id="fset"><option value="">every Set</option></select>
<select id="fcat"><option value="">every Category</option></select>
<select id="fuse"><option value="">any use</option><option>review</option><option>yes</option><option>no</option></select>
<select id="frev"><option value="">reviewed or not</option><option value="0">not reviewed</option><option value="1">reviewed</option></select>
<select id="sort"><option value="conf">lowest confidence first</option><option value="use">by use</option><option value="placed">most placed first</option><option value="name">by name</option></select>
</div>
</header>
<main id="main"></main>
<div id="tray"><div class="row"><b>Lines for rules/decor/tags.toml</b><span class="stat">paste under <code>[models]</code></span>
<button id="copyall">Copy all</button><button id="clear">Clear</button><button id="fold">Hide</button><span class="stat" id="traystat"></span></div>
<textarea id="lines" spellcheck="false" placeholder="Press yes / no on a card (or edit its line) to collect it here."></textarea></div>
<script id="data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);
const $=id=>document.getElementById(id);
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const store={get(k,d){try{const v=localStorage.getItem(k);return v==null?d:v}catch(e){return d}},set(k,v){try{localStorage.setItem(k,v)}catch(e){}}};
const cls=c=>c<0.45?'c-lo':c<0.7?'c-mid':'c-hi';
const fmt=v=>v==null?'-':Array.isArray(v)?v.join(' / '):v;
function fill(sel,vals){for(const v of vals){const o=document.createElement('option');o.value=v;o.textContent=v;sel.appendChild(o)}}
const kinds=[...new Set(D.cards.map(c=>c.tags.kind))].sort(), sets=[...new Set(D.cards.map(c=>c.tags.set))].sort(),
cats=[...new Set(D.cards.map(c=>c.tags.category))].sort();
fill($('fkind'),kinds);fill($('fset'),sets);fill($('fcat'),cats);
for(const id of ['q','fkind','fset','fcat','fuse','frev','sort']){const el=$(id);el.value=store.get('ps.'+id,el.value);el.addEventListener('input',()=>{store.set('ps.'+id,el.value);draw()})}
$('lines').value=store.get('ps.lines','');
function trayStat(){const n=$('lines').value.split('\n').filter(l=>l.trim()).length;$('traystat').textContent=n+' line'+(n==1?'':'s');store.set('ps.lines',$('lines').value)}
$('lines').addEventListener('input',trayStat);trayStat();
function addLine(key,line){const ls=$('lines').value.split('\n').filter(l=>l.trim()&&!l.startsWith(JSON.stringify(key)+' ='));ls.push(line);$('lines').value=ls.join('\n')+'\n';trayStat()}
const fold=v=>{$('tray').classList.toggle('min',v);$('fold').textContent=v?'Show':'Hide';store.set('ps.fold',v?'1':'')};
$('fold').onclick=()=>fold(!$('tray').classList.contains('min'));fold(store.get('ps.fold','')=='1');
$('copyall').onclick=()=>{navigator.clipboard&&navigator.clipboard.writeText($('lines').value)};
$('clear').onclick=()=>{if(confirm('Clear the collected lines?')){$('lines').value='';trayStat()}};
function text(c){return [c.key,c.name,c.tags.kind,c.tags.category,c.tags.set,c.tags.mount,c.tags.suits.join(' '),Object.values(c.why).join(' '),c.zones.map(z=>z[0]).join(' '),c.note].join(' ').toLowerCase()}
D.cards.forEach(c=>c._t=text(c));
function card(c){
 const m=c.m,o=c.obs;
 const rows=D.meta.fields.map(f=>`<tr><td>${f}</td><td class="v">${esc(fmt(c.tags[f]))}${c.reviewed.includes(f)?' <span class="rv">reviewed</span>':''}</td><td><span class="conf ${cls(c.conf[f])}">${c.conf[f].toFixed(2)}</span></td><td class="why">${esc(c.why[f]||'')}</td></tr>`).join('');
 const mounts=o.mount?Object.entries(o.mount).map(([k,v])=>k+' '+Math.round(v*100)+'%').join(', '):'';
 const zones=c.zones.map(z=>`${z[0]} ${z[1]} (${z[2]}, ${z[3]}${z[4]!=null?', over '+z[4]:''}${z[5]!=null?', wall '+z[5]:''})`).join('; ')+(c.more_zones?`; +${c.more_zones} more zones`:'');
 return `<div class="card${c.reviewed.length?' rev':''}" data-key="${esc(c.key)}">
 <div class="thumb">${c.thumb?`<img loading="lazy" src="img/${esc(c.thumb)}" alt="${esc(c.key)}: top and side views" title="top | side">`:`<div class="err">no thumbnail: ${esc(c.error)}</div>`}</div>
 <div class="title"><b>${esc(c.key)}</b><span><span class="badge ${c.tags.use}">use ${c.tags.use}</span> <span class="badge">low ${c.low.toFixed(2)}</span></span></div>
 <div class="meas">${m.w} x ${m.d} x ${m.h} u (below ${m.below}) · ${m.tris} tris · solid ${Math.round(m.solid_share*100)}%${m.walk_in?' · walk-in '+m.walk_in_area+' u²':''} · ${c.anim}${c.archives>1?' · in '+c.archives+' archives, '+c.texsets+' texture sets':''}</div>
 <div class="obs">placed ${c.placed}${o.n?` · ${mounts} · over floor ${fmt(o.over)} · wall ${fmt(o.wall)} · under ceiling ${Math.round((o.under||0)*100)}% · scale ${fmt(o.scale)}`:''}${o.near&&o.near.length?' · near '+o.near.join(', '):''}</div>
 <details><summary>zones and textures</summary><div class="obs">${esc(zones)}</div><div class="obs">${esc(c.tex.join(', '))}</div></details>
 <table class="tags">${rows}</table>
 ${c.note?`<div class="obs">note: ${esc(c.note)}</div>`:''}
 <code class="line" contenteditable="true" spellcheck="false">${esc(c.line)}</code>
 <div class="acts"><button class="yes" data-use="yes">yes</button><button class="no" data-use="no">no</button><button data-use="">add as edited</button><button data-copy="1">copy</button></div>
 </div>`}
function draw(){
 const q=$('q').value.trim().toLowerCase().split(/\s+/).filter(Boolean),fk=$('fkind').value,fs=$('fset').value,fc=$('fcat').value,fu=$('fuse').value,fr=$('frev').value,sort=$('sort').value;
 const shown=D.cards.filter(c=>(!fk||c.tags.kind==fk)&&(!fs||c.tags.set==fs)&&(!fc||c.tags.category==fc)&&(!fu||c.tags.use==fu)&&(!fr||(c.reviewed.length>0)==(fr=='1'))&&q.every(w=>c._t.includes(w)));
 const useOrd={review:0,yes:1,no:2};
 const cmp={conf:(a,b)=>a.low-b.low||b.placed-a.placed,use:(a,b)=>useOrd[a.tags.use]-useOrd[b.tags.use]||a.low-b.low,placed:(a,b)=>b.placed-a.placed,name:(a,b)=>a.key<b.key?-1:1}[sort];
 const groups={};for(const c of shown)(groups[c.tags.kind]=groups[c.tags.kind]||[]).push(c);
 const order=Object.entries(groups).map(([k,cs])=>[k,cs.sort(cmp)]);
 order.sort(sort=='name'?((a,b)=>a[0]<b[0]?-1:1):sort=='placed'?((a,b)=>b[1].reduce((s,c)=>s+c.placed,0)-a[1].reduce((s,c)=>s+c.placed,0)):((a,b)=>cmp(a[1][0],b[1][0])));
 $('main').innerHTML=order.map(([k,cs])=>`<h2>${esc(k)} <small>${esc(D.meta.kinds[k]||'')} · ${cs.length} model${cs.length==1?'':'s'}</small></h2><div class="grid">${cs.map(card).join('')}</div>`).join('')||'<p class="stat">Nothing matches.</p>';
 const rev=D.cards.filter(c=>c.reviewed.length).length;
 $('stat').textContent=`${shown.length} of ${D.meta.count} entries (${D.meta.names} names) · ${rev} reviewed`;
}
$('main').addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;const el=b.closest('.card'),c=D.cards.find(x=>x.key==el.dataset.key),code=el.querySelector('code.line');
 if(b.dataset.copy){navigator.clipboard&&navigator.clipboard.writeText(code.textContent);return}
 let line=code.textContent.trim();if(b.dataset.use){line=line.replace(/use = "[a-z]+"/,'use = "'+b.dataset.use+'"');code.textContent=line}
 addLine(c.key,line);b.textContent='added';setTimeout(()=>{b.textContent=b.dataset.use||'add as edited'},900)});
draw();
</script></body></html>
"""


def report(cat: dict) -> None:
    c = cat["counts"]
    print(f"{c['archives']} archives, {c['actors']} actors ({c['actors_read']} read), "
          f"{c['names']} names")
    print(f"{c['models']} models: {c['names_with_variants']} names have more than one mesh "
          f"({c['variants']} variants beyond the first)")
    print(f"animated {c['animated']} (skeletal {c['skeletal']}, vertex "
          f"{c['vertex_animated']}); animated textures on {c['texture_animated']}; "
          f"same mesh with other textures {c['same_mesh_other_textures']}")
    print(f"placements: {c['placements']} in {c['zones_placed']} zones, "
          f"{c['placements_resolved']} resolved to a model; {c['models_placed']} models placed")
    print(f"failures: {c['failures']}")
    reasons = Counter(re.sub(r"\d+", "N", f["reason"]) for f in cat["failures"])
    for r, n in reasons.most_common():
        print(f"  {n:5d}  {r}")
    print(f"placed names with no model in their zone: {c['unresolved_names']} "
          f"({c['placements'] - c['placements_resolved']} placements)")
    for u in sorted(cat["unresolved"], key=lambda u: -u["count"])[:15]:
        print(f"  {u['zone']:<16} {u['name']:<24} x{u['count']}")
    if cat["no_objects"]:
        print(f"zones without placements: {len(cat['no_objects'])}")
        for z in cat["no_objects"]:
            print(f"  {z['zone']:<24} {z['reason']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="read the install and write the catalogue")
    b.add_argument("--eq-path", type=Path, required=True)
    b.add_argument("--out", type=Path, default=OUT)
    b.add_argument("--archives", help="regex: only these archives (a partial catalogue)")
    b.add_argument("--jobs", type=int, default=None)
    t = sub.add_parser("tag", help="propose every entry's Tags into the catalogue")
    t.add_argument("--catalogue", type=Path, default=OUT)
    sc = sub.add_parser("screen", help="judge which floor models the wilderness gate takes on "
                                       "open ground (writes only open_ground)")
    sc.add_argument("--eq-path", type=Path, required=True)
    sc.add_argument("--catalogue", type=Path, default=OUT)
    sc.add_argument("--jobs", type=int, default=None)
    ws = sub.add_parser("wallside", help="measure which side of each wall model faces its wall "
                                         "on stock (writes only wall_side)")
    ws.add_argument("--eq-path", type=Path, required=True)
    ws.add_argument("--catalogue", type=Path, default=OUT)
    ws.add_argument("--jobs", type=int, default=None)
    ol = sub.add_parser("outline", help="measure each floor and raised model's plan hull, as the "
                                        "room gate reads it (writes only outline)")
    ol.add_argument("--eq-path", type=Path, required=True)
    ol.add_argument("--catalogue", type=Path, default=OUT)
    ol.add_argument("--jobs", type=int, default=None)
    sh = sub.add_parser("sheet", help="write the local HTML review sheet")
    sh.add_argument("--eq-path", type=Path, required=True)
    sh.add_argument("--out", type=Path, default=ROOT / "output" / "prop_sheet")
    sh.add_argument("--catalogue", type=Path, default=OUT)
    sh.add_argument("--tags", type=Path, default=OUT.parent / "tags.toml")
    sh.add_argument("--all", action="store_true",
                    help="every placed model, not only finding 1's dungeons and cities")
    sh.add_argument("--jobs", type=int, default=None)
    args = ap.parse_args(argv)
    if args.cmd == "build":
        cat = build(args.eq_path, args.out, args.archives, args.jobs)
        report(cat)
        print(f"wrote {args.out}")
    elif args.cmd == "tag":
        cat = tag(load(args.catalogue), args.catalogue)
        tag_report(cat)
        print(f"wrote {args.catalogue}")
    elif args.cmd == "screen":
        cat = screen(load(args.catalogue), args.eq_path, args.catalogue, args.jobs)
        screen_report(cat)
        print(f"wrote {args.catalogue}")
    elif args.cmd == "wallside":
        cat = wall_sides(load(args.catalogue), args.eq_path, args.catalogue, args.jobs)
        wall_side_report(cat)
        print(f"wrote {args.catalogue}")
    elif args.cmd == "outline":
        cat = outlines(load(args.catalogue), args.eq_path, args.catalogue, args.jobs)
        outline_report(cat)
        print(f"wrote {args.catalogue}")
    elif args.cmd == "sheet":
        page = write_sheet(args.eq_path, args.out, args.catalogue, args.tags, args.all, args.jobs)
        print(f"wrote {page}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
