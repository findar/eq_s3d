r"""The room view (decor-rules Req 4, design "The room view"): one room of a build re-decorated
on its own and drawn alone.

``decorate_room`` takes a build's saved RoomContexts (``<name>.rooms.json``,
``room_context.load``) and decorates one exactly as the build does (Req 4.2): the same
placement entry (``placement.place`` on the room's own stream, salted by the decor seed), the
zone's cap on bare rooms (``builder.BareCap``, replayed over the rooms before it when the room
draws bare) and the same import, check and settling (``builder.settle_room``, onto the built
wall mesh when one is given). With the build's seed, Decor level and layers it gives the
build's Props, as the sidecar's ``rooms[].props`` holds them.

It answers a GLB of the room alone (its floor, the Spine and the doors' Throats tinted, its wall
faces as they were sampled, its Features, a marker on each POI, and each Prop as its own node
``prop_<n>``, ``n`` its index in the report) and a report (``props``, ``pois``, ``drops``,
``seed``, ``control``, ``layers``, ``took_ms``, ...).

Props are the client's own models read from the install, each coloured by its textures' mean
colour. Without the install each Prop is a box of the catalogue's measured size, coloured by
its Category, placed as placement put it (nothing to settle it with), and the report says so.

``load_build`` reads a build folder once (its RoomContexts, its sidecar's decor block and the
built TER's wall mesh, from the ``.eqg``); the Server keeps it per build so a reroll is quick.
The rule files are never cached here: ``decorate_room`` reads them on every call.
"""

from __future__ import annotations

import math
import struct
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from generators.decor.catalogue import Catalogue
from generators.decor.placement import Prop, check, place
from generators.room_context import WALL_STEP, RoomContext

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
#: Why the Props are boxes, in the report's ``notes``.
NO_INSTALL_NOTE = "no EverQuest install (EQ_PATH): Props drawn as boxes of their measured size, as placed"

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
    """The room alone: floor cells, sampled wall faces, Features and a marker on each POI."""
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
    None when it can't be read (the Prop is drawn as a box). ``eq_path`` None: no install,
    every Prop a box. The importer is the build's shared one (``builder._importer``)."""

    def __init__(self, eq_path: Optional[Path]):
        self.importer = None
        self.failed: Dict[str, str] = {}
        self._cache: Dict[str, Optional[Part]] = {}
        self._rgb: Dict[str, Tuple[int, int, int]] = {}
        if eq_path is not None:
            from generators.builder import _importer
            self.importer = _importer(eq_path)

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


_MESHES: Dict[str, Meshes] = {}


def meshes_for(eq_path: Optional[Path]) -> Meshes:
    """One ``Meshes`` per install per process, so a room's models are read once."""
    key = str(eq_path)
    if key not in _MESHES:
        _MESHES[key] = Meshes(eq_path)
    return _MESHES[key]


def _diffuse(mat) -> Optional[str]:
    """A material's diffuse texture's file name."""
    for prop in mat.properties:
        if prop.value_s.lower().endswith(".dds"):
            return prop.value_s
    return None


def prop_part(p: Prop, meshes: Meshes) -> Tuple[Part, bool]:
    """One Prop's model scaled, turned and moved (or its box: then True)."""
    mesh = meshes.get(p.key)
    if mesh is None:
        return _box(p.x, p.y, p.z, p.yaw, p.w, p.d, p.h, CATEGORY_RGB.get(p.category, (200, 0, 200)),
                    p.below), True
    v, f, col = mesh
    c, s = math.cos(p.yaw), math.sin(p.yaw)
    rot = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
    return ((v * p.scale) @ rot.T + (p.x, p.y, p.z), np.vstack([f, f[:, ::-1]]), col), False


def prop_parts(props: List[Prop], meshes: Meshes) -> Tuple[Part, int]:
    """Every Prop merged into one part, and how many were drawn as boxes."""
    parts, boxes = [], 0
    for p in props:
        part, boxed = prop_part(p, meshes)
        parts.append(part)
        boxes += boxed
    return _merge(parts), boxes


def glb_bytes(meshes: Dict[str, Part]) -> bytes:
    """A GLB with one node per named part (empty parts left out)."""
    import trimesh
    scene = trimesh.Scene()
    for name, (v, f, col) in meshes.items():
        if not len(v):
            continue
        m = trimesh.Trimesh(vertices=v.astype(np.float32), faces=f.astype(np.int64), process=False)
        m.visual.vertex_colors = col
        scene.add_geometry(m, node_name=name, geom_name=name)
    return scene.export(file_type="glb")


def write_glb(path: Path, meshes: Dict[str, Part]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(glb_bytes(meshes))
    return path


# ---------------------------------------------------------------------------
# Helpers the command line shares
# ---------------------------------------------------------------------------

def any_use(cat: Catalogue) -> Catalogue:
    """Every static model with a kind counts as usable: a preview before the tag review."""
    models = {k: (replace(m, tags=replace(m.tags, use="yes")) if m.tags.use == "review" else m)
              for k, m in cat.models.items()}
    return Catalogue(models=models, kinds=cat.kinds, sets=cat.sets)


def eq_path_of(arg: Optional[str] = None) -> Optional[Path]:
    """The install: ``arg``, else ``EQ_PATH``, else ``F:\\everquest_rof2`` (None: none there)."""
    if arg:
        p = Path(arg)
        return p if p.is_dir() else None
    from generators.decor.stock import eq_path_from_env
    found = eq_path_from_env()
    if found is not None:
        return found
    return DEFAULT_EQ if DEFAULT_EQ.is_dir() else None


# ---------------------------------------------------------------------------
# Decorating one room
# ---------------------------------------------------------------------------

class NoRoom(KeyError):
    """The contexts hold no room of that id."""


_CATALOGUES: Dict[tuple, Catalogue] = {}


def shipped_catalogue() -> Catalogue:
    """The shipped catalogue (what a build loads), read again whenever its file or
    ``tags.toml`` changes on disk: fresh as the rules are, without its half-second load on a
    reroll."""
    from generators.decor.catalogue import CATALOGUE_FILE, DECOR_DIR, TAGS_FILE, load

    def stamp(p: Path):
        try:
            st = p.stat()
        except OSError:
            return None
        return st.st_mtime_ns, st.st_size
    key = (stamp(DECOR_DIR / CATALOGUE_FILE), stamp(DECOR_DIR / TAGS_FILE))
    if key not in _CATALOGUES:
        _CATALOGUES.clear()
        _CATALOGUES[key] = load()
    return _CATALOGUES[key]


def _decorated(contexts: Sequence[RoomContext], k: int, rules, catalogue, control: str,
               seed: Optional[int]):
    """Room ``k`` placed as ``builder.decor_for`` places it: on its own stream, under the
    zone's bare cap. The cap only matters when the room draws bare, so only then are the rooms
    before it replayed (each on its own stream with the same seed) to find what is left of it."""
    from generators.builder import BareCap
    ctx = contexts[k]
    d = place(ctx, rules, catalogue, control, seed)
    if not (d.bare and ctx.source == "room"):
        return d, 0
    cap = BareCap(contexts, rules, control)
    replayed = 0
    for c in contexts[:k]:
        if c.source == "room":
            cap.place(c, rules, catalogue, control, seed)
            replayed += 1
    return cap.place(ctx, rules, catalogue, control, seed), replayed


def decorate_room(contexts: Sequence[RoomContext], room_id: str, *, seed: Optional[int],
                  control: str, layers: Sequence[str] = (), eq_path: Optional[Path] = None,
                  mesh=None, rules_dir: Optional[Path] = None, catalogue: Optional[Catalogue] = None,
                  preview_any_use: bool = False) -> Tuple[bytes, dict]:
    """Decorate room ``room_id`` of a build's ``contexts`` (all of them, in build order) and
    draw it alone: (GLB bytes, report).

    ``seed`` salts the decor stream (None: each context's own seed, as a build with no decor
    seed); ``control`` is the Decor level; ``layers`` the decor layers to merge on, in merge
    order (a build's are its sidecar's ``decor.layers``). The rules are read from
    ``rules_dir`` (default ``ai.schema.RULES_DECOR_DIR``) on every call; a failing rule file
    raises ``RuleSetError``. ``eq_path`` is the install (None: boxes, said in the report);
    ``mesh`` the built TER's ``room_context._Mesh`` that wall Props settle onto (None: they
    stay where placement put them). Raises ``NoRoom`` for an id the contexts don't hold."""
    from ai import schema
    from generators.builder import settle_room
    from generators.decor.rules import load_decor

    t0 = time.perf_counter()
    ids = [c.id for c in contexts]
    if room_id not in ids:
        raise NoRoom(room_id)
    k = ids.index(room_id)
    ctx = contexts[k]
    rules = load_decor(Path(rules_dir) if rules_dir is not None else schema.RULES_DECOR_DIR,
                       layers=tuple(layers))
    cat = catalogue if catalogue is not None else shipped_catalogue()
    if preview_any_use:
        cat = any_use(cat)
    d, replayed = _decorated(contexts, k, rules, cat, control, seed)
    notes: List[str] = []
    meshes = meshes_for(eq_path)
    if eq_path is not None:
        d, problems, _files = settle_room(ctx, d, cat, meshes.importer, mesh, {})
        if mesh is None:
            notes.append("no wall mesh: wall Props stand where placement put them")
    else:
        problems = check(ctx, d)
        notes.append(NO_INSTALL_NOTE)

    parts: Dict[str, Part] = {"room": room_parts(ctx)}
    boxes = 0
    for n, p in enumerate(d.props):
        parts[f"prop_{n}"], boxed = prop_part(p, meshes)
        boxes += boxed
    if eq_path is not None and boxes:
        notes.append(f"{boxes} Props drawn as boxes: "
                     + "; ".join(sorted({meshes.failed[p.key] for p in d.props if p.key in meshes.failed})[:3]))
    glb = glb_bytes(parts)

    pois = []
    for n, poi in enumerate(ctx.pois):
        pois.append({"index": n, "purpose": poi.get("purpose", ""), "name": poi.get("name", ""),
                     "x": poi.get("x"), "y": poi.get("y"), "z": poi.get("z"),
                     "dressing": [p.key for p in d.props if p.poi == n],
                     "props": [i for i, p in enumerate(d.props) if p.poi == n],
                     "dropped": [x.reason for x in d.drops if x.poi == n]})
    report = {
        "room": {"id": ctx.id, "source": ctx.source, "room_type": ctx.room_type, "kind": ctx.kind,
                 "theme": ctx.theme, "race": ctx.race, "zone_type": ctx.zone_type,
                 "box": list(ctx.box)},
        "seed": int(seed) if seed is not None else int(ctx.seed),
        "control": control,
        "layers": list(rules.layers),
        "sets": list(d.sets),
        "bare": d.bare,
        "props": [p.to_dict() for p in d.props],
        "pois": pois,
        "drops": [x.to_dict() for x in d.drops],
        "check": list(problems),
        "install": eq_path is not None,
        "bare_replayed": replayed,
        "notes": notes,
        "took_ms": 0,
    }
    report["took_ms"] = int(round((time.perf_counter() - t0) * 1000))
    return glb, report


# ---------------------------------------------------------------------------
# A build folder
# ---------------------------------------------------------------------------

@dataclass
class Build:
    """What the room view reads from a build folder: its RoomContexts in build order, the
    defaults its Decor ran with (sidecar ``decor`` block, else the rooms file's recipe) and the
    built TER's wall mesh (None when the ``.eqg`` can't be read)."""
    name: str
    contexts: List[RoomContext]
    control: str
    seed: Optional[int]
    layers: Tuple[str, ...]
    theme: str = ""
    race: str = ""
    mesh: Any = None
    recipe: Dict[str, Any] = field(default_factory=dict)


def _file(build_dir: Path, name: str, suffix: str) -> Path:
    for stem in dict.fromkeys((name, name.lower())):
        p = build_dir / f"{stem}{suffix}"
        if p.is_file():
            return p
    return build_dir / f"{name.lower()}{suffix}"


def wall_mesh(eqg: Path):
    """The ``room_context._Mesh`` of a built ``.eqg``'s terrain (its ``ter_`` model)."""
    from core.pfs import PfsArchive
    from core.ter import TerFile
    from generators.room_context import _Mesh
    arc = PfsArchive.from_bytes(eqg.read_bytes())
    name = next((f for f in arc.list_files() if f.lower().startswith("ter_") and f.lower().endswith(".ter")),
                None)
    if name is None:
        return None
    return _Mesh(TerFile.from_bytes(arc.get(name), name))


def load_build(build_dir: Path, name: str, with_mesh: bool = True) -> Build:
    """A build folder's room view inputs. Raises ``FileNotFoundError`` when it has no
    ``<name>.rooms.json`` (a build with Decor none, or made without the install)."""
    import json
    from generators.room_context import load
    rooms = _file(build_dir, name, ".rooms.json")
    if not rooms.is_file():
        raise FileNotFoundError(rooms.name)
    recipe, contexts = load(rooms)
    side_path = _file(build_dir, name, ".zone.json")
    side = json.loads(side_path.read_text(encoding="utf-8")) if side_path.is_file() else {}
    decor = side.get("decor") or {}
    content = side.get("content") or {}
    seed = decor.get("seed", recipe.get("decor_seed"))
    control = decor.get("control") or recipe.get("decor") or "normal"
    mesh = None
    eqg = _file(build_dir, name, ".eqg")
    if with_mesh and eqg.is_file():
        mesh = wall_mesh(eqg)
    return Build(name=name, contexts=contexts, control=control,
                 seed=int(seed) if seed is not None else None,
                 layers=tuple(decor.get("layers") or ()),
                 theme=content.get("dungeon_theme") or "", race=content.get("dungeon_race") or "",
                 mesh=mesh, recipe=dict(recipe))


__all__ = ["Build", "CATEGORY_RGB", "Meshes", "NoRoom", "any_use", "decorate_room", "eq_path_of", "glb_bytes",
           "load_build", "meshes_for", "prop_part", "prop_parts", "room_parts", "shipped_catalogue", "wall_mesh", "write_glb"]
