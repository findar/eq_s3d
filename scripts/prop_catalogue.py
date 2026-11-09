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
KEPT = ("observed", "tags")
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

    def textures(self, mesh_b: int, files: dict) -> list:
        """The mesh's material list as [{name, w, h, format, frames}], one per material
        that has a bitmap (invisible materials have none)."""
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
    args = ap.parse_args(argv)
    if args.cmd == "build":
        cat = build(args.eq_path, args.out, args.archives, args.jobs)
        report(cat)
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
