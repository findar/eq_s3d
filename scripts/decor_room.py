r"""Decorate one room and write a GLB of it alone (roadmap step 11, Req 13.5; design "Looking
at one room").

Reads one RoomContext (a recording of ``tests/fixtures/rooms/``, or any file
``generators/room_context.save`` wrote), places its Props (``generators/decor/placement.py``)
and writes ``<out>/<recording>_<room>.glb``: the room's floor (reached floor grey, the Spine
and the doors' Throats tinted), its wall faces as they were sampled from the built walls, its
Features, a marker on each POI, and the Props. ``<out>/<recording>_<room>.decor.json`` holds
the Props and the drops. A look in seconds instead of a zone build.

Props are the client's own models, read from the install (``EQ_PATH``, or ``--eq-path``;
``F:\everquest_rof2`` here), each coloured by its textures' mean colour. Without the install
(or with ``--boxes``) each Prop is a box of the catalogue's measured size, coloured by its
Category, and the script says so.

Usage::

    python scripts/decor_room.py tests/fixtures/rooms/war_city_troll.json --out output/decor_room
    python scripts/decor_room.py <file> --room room_6 --control dense --decor-seed 3
    python scripts/decor_room.py <file> --any-use       # preview: count use = "review" models too

Until the tag review (task 4) lands, only a few models are ``use = "yes"`` and rooms come out
sparse; ``--any-use`` lets every static catalogued model in, for a look only.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from generators.decor.catalogue import Catalogue, load as load_catalogue  # noqa: E402
from generators.decor.placement import Decorated, Prop, check, place  # noqa: E402
from generators.decor.rules import CONTROLS, DEFAULT_CONTROL, load_decor  # noqa: E402
from generators.room_context import WALL_STEP, RoomContext, load  # noqa: E402

DEFAULT_EQ = Path(r"F:\everquest_rof2")
#: Box colours by Category, for Props drawn without the install.
CATEGORY_RGB: Dict[str, Tuple[int, int, int]] = {
    "light": (255, 170, 40), "container": (170, 120, 70), "furniture": (130, 80, 40), "hanging": (190, 40, 40),
    "structure": (120, 120, 140), "debris": (150, 150, 140), "plant": (60, 150, 60), "other": (200, 0, 200)}
FLOOR_RGB = (150, 150, 150)
SPINE_RGB = (175, 160, 120)
THROAT_RGB = (160, 150, 135)
WALL_RGB = (110, 105, 100)
FEATURE_RGB = (95, 95, 110)
POI_RGB = (220, 30, 30)

Part = Tuple[np.ndarray, np.ndarray, np.ndarray]        # vertices (V, 3), faces (F, 3), colours (V, 4)


# ---------------------------------------------------------------------------
# The room
# ---------------------------------------------------------------------------

def _quads(corners: List[np.ndarray], rgb: List[Tuple[int, int, int]]) -> Part:
    """Quads (each 4 corners, counter-clockwise from the side that sees it), both sides drawn."""
    if not corners:
        return np.zeros((0, 3)), np.zeros((0, 3), np.int64), np.zeros((0, 4), np.uint8)
    v = np.concatenate(corners)
    n = len(corners)
    base = np.arange(n)[:, None] * 4
    f = np.concatenate([base + [0, 1, 2], base + [0, 2, 3], base + [0, 2, 1], base + [0, 3, 2]])
    col = np.repeat(np.array([(*c, 255) for c in rgb], np.uint8), 4, axis=0)
    return v, f, col


def room_parts(ctx: RoomContext) -> Part:
    from generators.decor.placement import Room
    r = Room(ctx)
    h = ctx.cell / 2
    corners, rgb = [], []
    throat = r.keep & ~ctx.spine
    for i, j in np.argwhere(~np.isnan(ctx.floor)):
        x, y, z = r.xs[i], r.ys[j], ctx.floor[i, j]
        corners.append(np.array([[x - h, y - h, z], [x + h, y - h, z], [x + h, y + h, z], [x - h, y + h, z]]))
        rgb.append(SPINE_RGB if ctx.spine[i, j] else THROAT_RGB if throat[i, j] else FLOOR_RGB)
    half = WALL_STEP / 2 + 0.1
    for w in ctx.walls:
        tx, ty = -w.ny * half, w.nx * half
        corners.append(np.array([[w.x - tx, w.y - ty, w.bottom], [w.x + tx, w.y + ty, w.bottom],
                                 [w.x + tx, w.y + ty, w.top], [w.x - tx, w.y - ty, w.top]]))
        rgb.append(WALL_RGB)
    parts = [_quads(corners, rgb)]
    zs = ctx.floor[~np.isnan(ctx.floor)]
    z0 = float(zs.min()) if len(zs) else 0.0
    for f in ctx.features:
        plan = np.asarray(f.get("plan") or [], float)
        if len(plan) < 3:
            continue
        top = z0 + float(f.get("height") or 1.0)
        parts.append(_prism(plan, z0, top, FEATURE_RGB))
    for p in ctx.pois:
        parts.append(_box(p["x"], p["y"], p["z"], 0.0, 1.2, 1.2, 6.0, POI_RGB))
    return _merge(parts)


def _prism(plan: np.ndarray, z0: float, z1: float, rgb) -> Part:
    n = len(plan)
    bottom = np.c_[plan, np.full(n, z0)]
    top = np.c_[plan, np.full(n, z1)]
    v = np.vstack([bottom, top])
    faces = [[n, n + k, n + k + 1] for k in range(1, n - 1)]
    for k in range(n):
        a, b = k, (k + 1) % n
        faces += [[a, b, n + b], [a, n + b, n + a]]
    f = np.array(faces, np.int64)
    f = np.vstack([f, f[:, ::-1]])
    return v, f, np.tile(np.array([*rgb, 255], np.uint8), (len(v), 1))


def _box(x, y, z, yaw, w, d, h, rgb, below=0.0) -> Part:
    lx = np.array([-1, 1, 1, -1, -1, 1, 1, -1]) * w / 2
    ly = np.array([-1, -1, 1, 1, -1, -1, 1, 1]) * d / 2
    lz = np.array([0, 0, 0, 0, 1, 1, 1, 1]) * (h + below) - below
    c, s = math.cos(yaw), math.sin(yaw)
    v = np.c_[x + c * lx - s * ly, y + s * lx + c * ly, z + lz]
    f = np.array([[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5],
                  [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]], np.int64)
    return v, f, np.tile(np.array([*rgb, 255], np.uint8), (8, 1))


def _merge(parts: List[Part]) -> Part:
    parts = [p for p in parts if len(p[0])]
    if not parts:
        return np.zeros((0, 3)), np.zeros((0, 3), np.int64), np.zeros((0, 4), np.uint8)
    vs, fs, cs, base = [], [], [], 0
    for v, f, c in parts:
        vs.append(v)
        fs.append(f + base)
        cs.append(c)
        base += len(v)
    return np.vstack(vs), np.vstack(fs), np.vstack(cs)


# ---------------------------------------------------------------------------
# The Props
# ---------------------------------------------------------------------------

def _mean_rgb(dds: bytes) -> Tuple[int, int, int]:
    """A texture's mean colour over its texels that aren't clear. The import writes
    uncompressed A8R8G8B8 (``generators/textures/dds.rgba_to_dds``: a 128-byte header, then B,
    G, R, A), read here directly: PIL decodes it a pixel at a time."""
    h, w = struct.unpack_from("<II", dds, 12)
    body = np.frombuffer(dds, np.uint8, count=w * h * 4, offset=128) if len(dds) >= 128 + w * h * 4 else None
    if body is None:
        return (160, 160, 160)
    bgra = body.reshape(-1, 4)
    keep = bgra[:, 3] > 16
    px = bgra[keep] if keep.any() else bgra
    b, g, r = px[:, :3].mean(axis=0)
    return int(r), int(g), int(b)


class Meshes:
    """Each catalogue entry's mesh in model space with per-vertex colours, from the install, or
    None when it can't be read (the Prop is drawn as a box)."""

    def __init__(self, eq_path: Optional[Path]):
        self.importer = None
        self.failed: Dict[str, str] = {}
        self._cache: Dict[str, Optional[Part]] = {}
        self._rgb: Dict[str, Tuple[int, int, int]] = {}
        if eq_path is not None:
            from generators.decor.stock import Importer
            self.importer = Importer(eq_path)

    def get(self, key: str) -> Optional[Part]:
        if self.importer is None:
            return None
        if key not in self._cache:
            try:
                m = self.importer.get(key)
            except Exception as e:  # noqa: BLE001 - named in the report, drawn as a box
                self.failed[key] = str(e)
                self._cache[key] = None
                return None
            v = np.array([(p.x, p.y, p.z) for p in m.ter.vertices], float)
            f = np.array([(p.v1, p.v2, p.v3) for p in m.ter.polygons], np.int64)
            mats = np.array([p.material for p in m.ter.polygons], np.int64)
            col = np.full((len(v), 4), 200, np.uint8)
            for mat in m.ter.materials:
                name = _diffuse(mat)
                if name in m.textures:
                    if name not in self._rgb:
                        self._rgb[name] = _mean_rgb(m.textures[name])
                    col[f[mats == mat.index].ravel()] = (*self._rgb[name], 255)
            self._cache[key] = (v, f, col)
        return self._cache[key]


def _diffuse(mat) -> Optional[str]:
    """A material's diffuse texture's file name."""
    for prop in mat.properties:
        if prop.value_s.lower().endswith(".dds"):
            return prop.value_s
    return None


def prop_parts(props: List[Prop], meshes: Meshes) -> Tuple[Part, int]:
    parts, boxes = [], 0
    for p in props:
        mesh = meshes.get(p.key)
        if mesh is None:
            boxes += 1
            parts.append(_box(p.x, p.y, p.z, p.yaw, p.w, p.d, p.h, CATEGORY_RGB.get(p.category, (200, 0, 200)),
                              p.below))
            continue
        v, f, col = mesh
        c, s = math.cos(p.yaw), math.sin(p.yaw)
        rot = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
        parts.append(((v * p.scale) @ rot.T + (p.x, p.y, p.z), np.vstack([f, f[:, ::-1]]), col))
    return _merge(parts), boxes


def write_glb(path: Path, meshes: Dict[str, Part]) -> Path:
    import trimesh
    scene = trimesh.Scene()
    for name, (v, f, col) in meshes.items():
        if not len(v):
            continue
        m = trimesh.Trimesh(vertices=v.astype(np.float32), faces=f.astype(np.int64), process=False)
        m.visual.vertex_colors = col
        scene.add_geometry(m, node_name=name, geom_name=name)
    path.parent.mkdir(parents=True, exist_ok=True)
    scene.export(str(path))
    return path


# ---------------------------------------------------------------------------
# The command
# ---------------------------------------------------------------------------

def any_use(cat: Catalogue) -> Catalogue:
    """Every static model with a kind counts as usable: a preview before the tag review."""
    models = {k: (replace(m, tags=replace(m.tags, use="yes")) if m.tags.use == "review" else m)
              for k, m in cat.models.items()}
    return Catalogue(models=models, kinds=cat.kinds, sets=cat.sets)


def eq_path_of(arg: Optional[str]) -> Optional[Path]:
    if arg:
        p = Path(arg)
        return p if p.is_dir() else None
    from generators.decor.stock import eq_path_from_env
    found = eq_path_from_env()
    if found is not None:
        return found
    return DEFAULT_EQ if DEFAULT_EQ.is_dir() else None


def pick(rooms: List[RoomContext], room: Optional[str]) -> RoomContext:
    if room is None:
        return rooms[0]
    for c in rooms:
        if c.id == room:
            return c
    raise SystemExit(f"no room {room!r}; the file holds {', '.join(c.id for c in rooms)}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("context", help="a RoomContext recording (tests/fixtures/rooms/<name>.json)")
    ap.add_argument("--out", default="output/decor_room", help="folder for the GLB (default output/decor_room)")
    ap.add_argument("--room", help="the room's id (default: the file's first)")
    ap.add_argument("--control", default=DEFAULT_CONTROL, choices=CONTROLS)
    ap.add_argument("--decor-seed", type=int, help="salt the decor stream (default: the room's seed)")
    ap.add_argument("--any-use", action="store_true", help='count use = "review" models as usable (preview only)')
    ap.add_argument("--boxes", action="store_true", help="draw every Prop as a box, without the install")
    ap.add_argument("--eq-path", help="the EverQuest install (default EQ_PATH, else F:\\everquest_rof2)")
    args = ap.parse_args(argv)

    t0 = time.perf_counter()
    path = Path(args.context)
    _recipe, rooms = load(path)
    ctx = pick(rooms, args.room)
    rules = load_decor()
    cat = load_catalogue()
    if args.any_use:
        cat = any_use(cat)
    dec: Decorated = place(ctx, rules, cat, args.control, args.decor_seed)
    problems = check(ctx, dec)

    eq = None if args.boxes else eq_path_of(args.eq_path)
    meshes = Meshes(eq)
    props, boxes = prop_parts(dec.props, meshes)
    out = Path(args.out)
    stem = f"{path.stem}_{ctx.id}"
    glb = write_glb(out / f"{stem}.glb", {"room": room_parts(ctx), "props": props})
    (out / f"{stem}.decor.json").write_text(json.dumps(dec.to_dict(), indent=1) + "\n", encoding="utf-8")
    took = time.perf_counter() - t0

    kinds = {}
    for p in dec.props:
        kinds[p.kind] = kinds.get(p.kind, 0) + 1
    print(f"{ctx.id}: {ctx.room_type or ctx.kind or ctx.source} ({ctx.race or '-'}, {ctx.theme or '-'}, "
          f"{ctx.zone_type}), Sets {', '.join(dec.sets)}{', bare' if dec.bare else ''}")
    print(f"  {len(dec.props)} Props: " + ", ".join(f"{k} x{n}" for k, n in sorted(kinds.items())))
    if dec.drops:
        reasons = {}
        for x in dec.drops:
            reasons[x.reason] = reasons.get(x.reason, 0) + 1
        print(f"  {len(dec.drops)} dropped: " + ", ".join(f"{r} x{n}" for r, n in sorted(reasons.items())))
    usable = len(cat.usable())
    if usable < 200 and not args.any_use:
        print(f"  note: only {usable} models are use = \"yes\" (the tag review is in progress); "
              "--any-use previews with every catalogued model")
    if eq is None:
        why = "--boxes" if args.boxes else "no EverQuest install (EQ_PATH)"
        print(f"  note: {why}: Props drawn as boxes of their measured size")
    elif boxes:
        print(f"  note: {boxes} Props drawn as boxes: " + "; ".join(sorted(set(meshes.failed.values()))[:3]))
    print("  room check: " + ("ok" if not problems else "; ".join(problems)))
    print(f"  wrote {glb} in {took:.1f} s")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
