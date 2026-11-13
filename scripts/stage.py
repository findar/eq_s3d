r"""Run one stage of a zone from the previous stage's hand-off (world-sockets task 10, Req 5.4;
design "Testing in isolation").

A build writes its hand-offs into its build directory (``<name>.world.json``,
``<name>.attach.json``, ``<name>.rooms.json``). Each command here runs one stage from the
previous one's file, writes its own (the same text a full build writes for the same seeds) and
a GLB of that stage alone, and prints its time:

``world``   zone type, World inputs and a seed -> ``<name>.world.json`` and
            ``<name>.world.glb`` (the terrain, its Sockets marked as columns).
``attach``  a World file, plan fields and a rooms seed -> ``<name>.attach.json`` and
            ``<name>.attach.glb`` (the attached rooms alone, as the box mesh of the layout,
            and the Sites as their ground and Structures).
``rooms``   a World and Attachments -> ``ter_<name>.ter``, ``<name>.rooms.glb`` (that TER)
            and ``<name>.rooms.json`` (the RoomContexts; none with Decor ``none`` or no
            install, as a build).
``decor``   a rooms file -> ``<name>.decor.glb`` (every room and its Props) and
            ``<name>.decor.json``, as ``scripts/decor_room.py`` does for one room.

Plan fields are ``--plan key=value`` (any ``ZonePlan`` field: ``room_count=8``,
``dungeon_theme=crypt``, ``layout=classic``, ``sites=dense``, ...). ``attach`` and ``rooms``
read the same plan, so give both the same fields. The name defaults to the input file's.

Usage::

    python scripts/stage.py world sw --zone-type outdoor_dungeon --seed 3 --out output/stage
    python scripts/stage.py attach output/stage/sw.world.json --rooms-seed 9 --out output/stage
    python scripts/stage.py rooms output/stage/sw.attach.json --out output/stage
    python scripts/stage.py decor output/stage/sw.rooms.json --out output/stage

Every file is written through an ``OutputRoot`` on ``--out``, as builds write theirs.
"""

from __future__ import annotations

import time

_LAUNCH = time.perf_counter()

import argparse  # noqa: E402
import copy
import dataclasses
import json
import math
import sys
import typing
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from core.paths import OutputRoot  # noqa: E402
from generators import stages  # noqa: E402
from generators import world as world_mod  # noqa: E402

Part = Tuple[np.ndarray, np.ndarray, np.ndarray]        # vertices (V, 3), faces (F, 3), colours (V, 4)

SOCKET_RGB = {"root": (220, 30, 30), "hillside": (230, 140, 20), "ground": (40, 120, 230),
              "door": (160, 40, 200)}
WATER_RGB = (60, 110, 200)
RIM_RGB = (120, 115, 110)
SITE_GROUND_RGB = (200, 180, 120)
SITE_STRUCTURE_RGB = (150, 90, 50)
KEEP_CLEAR_RGB = (230, 60, 60)


# ---------------------------------------------------------------------------
# Meshes
# ---------------------------------------------------------------------------

def _empty() -> Part:
    return np.zeros((0, 3)), np.zeros((0, 3), np.int64), np.zeros((0, 4), np.uint8)


def _merge(parts: Sequence[Part]) -> Part:
    parts = [p for p in parts if len(p[0])]
    if not parts:
        return _empty()
    vs, fs, cs, base = [], [], [], 0
    for v, f, c in parts:
        vs.append(v)
        fs.append(f + base)
        cs.append(c)
        base += len(v)
    return np.vstack(vs), np.vstack(fs), np.vstack(cs)


def _box(x, y, z, yaw, w, d, h, rgb) -> Part:
    lx = np.array([-1, 1, 1, -1, -1, 1, 1, -1]) * w / 2
    ly = np.array([-1, -1, 1, 1, -1, -1, 1, 1]) * d / 2
    lz = np.array([0, 0, 0, 0, 1, 1, 1, 1]) * h
    c, s = math.cos(yaw), math.sin(yaw)
    v = np.c_[x + c * lx - s * ly, y + s * lx + c * ly, z + lz]
    f = np.array([[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5],
                  [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]], np.int64)
    return v, f, np.tile(np.array([*rgb, 255], np.uint8), (8, 1))


def _capsule(shape, z: float, h: float, rgb) -> Part:
    """A capsule ``(x0, y0, x1, y1, r)`` drawn as a thin slab: its run's box and two end discs
    (octagons)."""
    x0, y0, x1, y1, r = (float(v) for v in shape)
    parts = []
    length = math.hypot(x1 - x0, y1 - y0)
    if length > 1e-6:
        parts.append(_box((x0 + x1) / 2, (y0 + y1) / 2, z, math.atan2(y1 - y0, x1 - x0),
                          length, 2 * r, h, rgb))
    for cx, cy in ((x0, y0), (x1, y1)):
        parts.append(_box(cx, cy, z, math.pi / 8, 2 * r * 0.924, 2 * r * 0.924, h, rgb))
        parts.append(_box(cx, cy, z, 3 * math.pi / 8, 2 * r * 0.924, 2 * r * 0.924, h, rgb))
    return _merge(parts)


def ter_part(ter, colors: Dict[int, tuple]) -> Part:
    """A TER's mesh, each vertex coloured by its polygons' material's base colour."""
    if not ter.polygons:
        return _empty()
    v = np.array([(p.x, p.y, p.z) for p in ter.vertices], float)
    f = np.array([(q.v1, q.v2, q.v3) for q in ter.polygons], np.int64)
    col = np.full((len(v), 4), 160, np.uint8)
    col[:, 3] = 255
    for q in ter.polygons:
        rgb = colors.get(q.material)
        if rgb is not None:
            col[[q.v1, q.v2, q.v3], :3] = [int(c) for c in rgb[:3]]
    return v, np.vstack([f, f[:, ::-1]]), col


def spec_colors(spec, ter) -> Dict[int, tuple]:
    out = {}
    for m in ter.materials:
        mat = spec.materials.get(m.name)
        if mat is not None:
            out[m.index] = mat.color
    return out


def terrain_part(world) -> Part:
    """The World's height grid (vertex ``(i, j)`` at ``origin + (i + 0.5, j + 0.5) * res``),
    green-brown by height, grey on the Rim seal, blue under the water level."""
    t = world.terrain
    z = np.asarray(t.heights, float)
    nx, ny = z.shape
    ox, oy = t.origin
    gi, gj = np.meshgrid(np.arange(nx), np.arange(ny), indexing="ij")
    v = np.c_[ox + (gi.ravel() + 0.5) * t.res, oy + (gj.ravel() + 0.5) * t.res, z.ravel()]
    k = (gi[:-1, :-1] * ny + gj[:-1, :-1]).ravel()
    f = np.concatenate([np.c_[k, k + ny, k + ny + 1], np.c_[k, k + ny + 1, k + 1]])
    lo, hi = float(z.min()), float(z.max())
    s = (z.ravel() - lo) / max(hi - lo, 1e-6)
    rgb = np.c_[90 + 80 * s, 130 + 20 * s, 60 + 40 * s]
    rim = np.asarray(t.rim_seal, bool).ravel()
    rgb[rim] = RIM_RGB
    if t.water_level is not None:
        rgb[z.ravel() < t.water_level] = WATER_RGB
    col = np.c_[rgb, np.full(len(v), 255)].astype(np.uint8)
    return v, np.vstack([f, f[:, ::-1]]), col


def sockets_part(world) -> Part:
    """A column on each Socket's point, coloured by its kind; a ground Socket's Kept_Clear
    shapes as slabs."""
    parts = []
    for s in world.sockets:
        parts.append(_box(s.x, s.y, s.z, s.yaw, 8.0, 8.0, 120.0, SOCKET_RGB.get(s.kind, (255, 0, 255))))
        for shape in (s.ground or {}).get("keep_clear", []):
            parts.append(_capsule(shape, s.z, 2.0, KEEP_CLEAR_RGB))
    return _merge(parts)


def sites_part(placement) -> Part:
    """Each Site's ground (its clear capsules) and its Structures as boxes of their radius."""
    sites = placement["sites"] if isinstance(placement, dict) else \
        [dataclasses.asdict(s) for s in placement.sites]
    parts = []
    for site in sites:
        for c in site["clear"]:
            parts.append(_capsule((c["x0"], c["y0"], c["x1"], c["y1"], c["r"]), site["z"], 0.5,
                                  SITE_GROUND_RGB))
        for st in site["structures"]:
            r = float(st["radius"])
            parts.append(_box(st["x"], st["y"], st["z"], st["yaw"], 2 * r, 2 * r, 12.0,
                              SITE_STRUCTURE_RGB))
    return _merge(parts)


def glb_bytes(meshes: Dict[str, Part]) -> bytes:
    import trimesh
    scene = trimesh.Scene()
    for name, (v, f, col) in meshes.items():
        if not len(v):
            continue
        m = trimesh.Trimesh(vertices=v.astype(np.float32), faces=f.astype(np.int64), process=False)
        m.visual.vertex_colors = col
        scene.add_geometry(m, node_name=name, geom_name=name)
    if not scene.geometry:      # an empty GLB still opens
        scene.add_geometry(trimesh.Trimesh(vertices=np.zeros((3, 3), np.float32),
                                           faces=np.array([[0, 1, 2]]), process=False),
                           node_name="empty", geom_name="empty")
    return scene.export(file_type="glb")


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------

def _coerce(name: str, value: str, default, hint) -> object:
    hint = str(hint)
    if isinstance(default, bool) or "bool" in hint:
        return value.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(default, int) or "int" in hint:
        return None if value.strip().lower() in ("", "none") else int(value)
    if isinstance(default, list) or "List" in hint:
        return [x for x in value.split(",") if x]
    return value


def make_plan(name: str, zone_type: str, pairs: Sequence[str] = ()):
    """The ``ZonePlan`` of ``name`` / ``zone_type`` with ``key=value`` fields, validated."""
    from ai.schema import ZonePlan
    fields = {f.name: f for f in dataclasses.fields(ZonePlan)}
    hints = typing.get_type_hints(ZonePlan)
    kw = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        key = key.strip().replace("-", "_")
        if not sep or key not in fields or key in ("name", "zone_type"):
            raise SystemExit(f"--plan {pair!r}: expected key=value with key a ZonePlan field "
                             f"(not name or zone_type)")
        f = fields[key]
        default = f.default if f.default is not dataclasses.MISSING else \
            (f.default_factory() if f.default_factory is not dataclasses.MISSING else None)
        kw[key] = _coerce(key, value, default, hints[key])
    plan = ZonePlan(name=name, zone_type=zone_type, **kw)
    plan.validate()
    return plan


def _stem(path: Path, suffix: str) -> str:
    n = path.name
    return n[:-len(suffix)] if n.endswith(suffix) else path.stem


# ---------------------------------------------------------------------------
# The stages
# ---------------------------------------------------------------------------

def world_stage(zone_type: str, seed: int, biome: Optional[str] = None,
                edges: Optional[Dict[str, str]] = None, zone_size: Optional[float] = None):
    return world_mod.world_for(zone_type, seed, biome=biome, edges=edges, zone_size=zone_size)


def _tunnel_doors(world, entrance) -> dict:
    """``outdoor_dungeon.tunnel_doors`` from the World's grid instead of the landscape."""
    e = entrance
    origin, res = world.terrain.origin, float(world.terrain.res)

    def coord(k):
        return origin[1 - e.axis] + (k + 0.5) * res

    return {e.room_id: {e.side: [(coord(e.cross), coord(e.cross + 1), e.room_floor + e.height)]}}


def attach_stage(world, plan, rooms_seed: Optional[int] = None):
    """The Attachments of ``plan`` on ``world``, in attach order, as a build makes them, and
    the layout specs drawn in the GLB. ``rooms_seed`` lays the rooms out and places the
    Sites (``None``: the World's seed)."""
    from ai.expand import _dress_rooms, layout_block, layout_engine, plan_to_spec
    from generators.wilderness.build import DEFAULT_BIOME, DEFAULT_SITES

    seed = stages.rooms_seed(int(world.recipe["seed"]), rooms_seed)
    out, specs = [], []
    for socket in sorted(world.sockets, key=lambda s: stages.ORDER.index(s.kind)):
        if socket.kind == "root":
            spec = plan_to_spec(plan, seed=seed)
            att = stages.build_attachments(spec, world)[0]
            specs.append(spec)
        elif socket.kind == "hillside":
            fields = dict(name=plan.name, room_count=plan.room_count, verticality=plan.verticality,
                          locks=plan.locks, dungeon_theme=plan.dungeon_theme,
                          dungeon_race=plan.dungeon_race, elemental_tint=plan.elemental_tint or None)
            engine = layout_engine(plan.layout, plan.rule_set, plan.verticality, outdoor=True)
            att = stages.attach_rooms(world, socket, fields, seed, engine)
            lay = att.layout
            lay.layout = layout_block(lay.layout, lay)
            if lay.layout is not None:      # a grown dungeon draws its walls, as plan_to_spec
                _dress_rooms(lay, plan, seed, extra_doors=_tunnel_doors(world, att.entrance),
                             overlay="" if plan.dungeon_theme else "natural_cave")
            # The build opens the Tunnel's wall of the entrance room as it meshes the
            # dungeon (outdoor_dungeon._dungeon_mesh), so the file it writes has it open.
            e = att.entrance
            room = next(r for r in lay.rooms if r.id == e.room_id)
            if e.side not in room.open_walls:
                room.open_walls.append(e.side)
            specs.append(lay)
        elif socket.kind == "ground":
            ground = stages.apply_edits(world, out)
            att = stages.attach_sites(ground, ground.socket(socket.id), seed,
                                      biome=world.recipe.get("biome") or DEFAULT_BIOME,
                                      control=plan.sites or DEFAULT_SITES,
                                      inhabitant=plan.inhabitant or "")
        else:
            continue
        out.append(att)
    return out, specs


def _plain(d):
    return json.loads(world_mod.dumps(world_mod._plain(d)))


def zone_spec(world, attachments, plan):
    """The zone's spec for the Build: ``plan_to_spec`` on the World's seed and edges, with
    the rooms' Attachment from the file (its layout, and an outdoor dungeon's Entrance,
    Envelope and Spawn) wherever the plan's own differs (another rooms seed)."""
    from ai.expand import plan_to_spec
    from generators.decor.rules import DEFAULT_CONTROL
    from generators.zone_spec import ZoneSpec

    spec = plan_to_spec(plan, seed=int(world.recipe["seed"]), edges=world.recipe.get("edges"))
    if spec.decor is None:              # the pipeline's default (_with_decor)
        spec.decor = DEFAULT_CONTROL
    again = world_mod.world_of(spec)
    if again.to_json() != world.to_json():
        raise SystemExit("the plan doesn't make this World (another zone type, biome or "
                         "edges?); give the plan the World was made for")
    rooms = next((a for a in attachments if a.kind in ("root", "hillside")), None)
    if rooms is None:
        return spec
    mine = stages.Attachment(socket="", kind="", layout=spec).to_dict()["layout"]
    theirs = rooms.to_dict()["layout"]
    if mine == theirs:
        return spec
    d = spec.to_dict()
    d.update(copy.deepcopy(theirs))
    if rooms.kind == "hillside":
        env = rooms.envelope
        d["wilderness"] = dict(d["wilderness"])
        d["wilderness"]["dungeon"] = {
            "entrance": rooms.entrance.to_dict(), "rock_cover": env["rock_cover"],
            "floor_limit": env["floor_limit"], "rooms_requested": rooms.rooms_requested,
            "warnings": list(rooms.warnings)}
        d["safe_point"] = list(stages.apply_edits(world, [rooms]).spawn)
    return ZoneSpec.from_dict(d)


def rooms_stage(world, attachments, plan, eq_path=None, use_env: bool = True):
    """The Build's TER and RoomContexts from the World and its Attachments: ``(spec, ter,
    recipe, rooms)``. RoomContexts are made as the build makes them for decor: none with
    Decor ``none`` or without the install."""
    from generators.builder import ZoneBuilder, assign_texel_densities
    from generators.decor.stock import eq_path_from_env
    from generators.room_context import _Mesh, contexts, site_contexts

    spec = zone_spec(world, attachments, plan)
    name = spec.name.lower()
    assign_texel_densities(spec)
    ter, _backend, _warnings = ZoneBuilder(spec)._build_geometry(name, 2)

    control = spec.decor or "none"
    sited = spec.wilderness is not None and (spec.sites or "none") != "none"
    has_rooms = bool(spec.rooms)
    eq = eq_path if eq_path is not None else (eq_path_from_env() if use_env else None)
    rooms, decor_seed = [], None
    if control != "none" and (has_rooms or sited) and eq is not None:
        decor_seed = spec.decor_seed if spec.decor_seed is not None else int(spec.seed or 0)
        if has_rooms:
            rooms += contexts(spec, _Mesh(ter))
        if sited:
            rooms += site_contexts(spec, ter, _site_placement(world, attachments))
    recipe = {"name": spec.name, "zone_type": spec.zone_type, "seed": spec.seed,
              "decor": control, "decor_seed": decor_seed}
    return spec, ter, recipe, rooms


def _site_placement(world, attachments):
    """The ground Attachment's SitePlacement, made again from the World and the earlier
    Attachments' edits; it must equal the file's."""
    for k, a in enumerate(attachments):
        if a.kind != "ground":
            continue
        ground = stages.apply_edits(world, attachments[:k])
        again = stages.attach_sites(ground, ground.socket(a.socket), a.seed, **a.controls)
        if _plain(again.sites.to_dict()) != _plain(a.sites):
            raise SystemExit("the ground Attachment's Sites don't rerun from the World file")
        return again.sites
    return None


def decor_stage(recipe, rooms, control: Optional[str] = None, decor_seed: Optional[int] = None):
    """Each room placed as the build places it (the bare cap included): ``[(ctx, Decorated,
    problems)]``."""
    from generators.decor.catalogue import load as load_catalogue
    from generators.decor.placement import check, place
    from generators.decor.rules import BARE, DEFAULT_CONTROL, load_decor

    control = control or recipe.get("decor") or DEFAULT_CONTROL
    if control == "none":
        control = DEFAULT_CONTROL
    seed = decor_seed if decor_seed is not None else recipe.get("decor_seed")
    rules, cat = load_decor(), load_catalogue()
    bare_left = math.ceil(sum(
        rules.weights_for(c.zone_type, c.race, c.theme, c.kind, c.room_type, control)[BARE]
        for c in rooms if c.source == "room") - 1e-9)
    out = []
    for ctx in rooms:
        d = place(ctx, rules, cat, control, seed)
        if d.bare and ctx.source == "room":
            if bare_left > 0:
                bare_left -= 1
            else:
                d = place(ctx, rules, cat, control, seed, may_be_bare=False)
        out.append((ctx, d, check(ctx, d)))
    return control, seed, out


# ---------------------------------------------------------------------------
# The commands
# ---------------------------------------------------------------------------

def _edges(text: Optional[str]) -> Optional[Dict[str, str]]:
    if not text:
        return None
    out = {}
    for pair in text.split(","):
        side, sep, kind = pair.partition("=")
        if not sep:
            raise SystemExit(f"--edges {text!r}: expected N=zoneline,E=mountain,...")
        out[side.strip().upper()] = kind.strip()
    return out


def cmd_world(args) -> List[Path]:
    root = OutputRoot(Path(args.out))
    world = world_stage(args.zone_type, args.seed, args.biome, _edges(args.edges), args.zone_size)
    meshes = {"sockets": sockets_part(world)}
    if world.terrain is not None:
        meshes = {"terrain": terrain_part(world), **meshes}
    kinds = ", ".join(f"{s.id} ({s.kind})" for s in world.sockets)
    print(f"world {args.name}: {args.zone_type}, seed {args.seed}, Sockets {kinds}")
    return [root.write_text(f"{args.name}.world.json", world.to_json()),
            root.write_bytes(f"{args.name}.world.glb", glb_bytes(meshes))]


def cmd_attach(args) -> List[Path]:
    root = OutputRoot(Path(args.out))
    path = Path(args.world)
    world = world_mod.load(path)
    name = args.name or _stem(path, ".world.json")
    plan = make_plan(name, world.recipe["zone_type"], args.plan)
    attachments, specs = attach_stage(world, plan, args.rooms_seed)
    text = stages.attachments_json(attachments)
    out = [root.write_text(f"{name}.attach.json", text)]
    from generators.geometry import build_mesh
    meshes = {}
    for k, spec in enumerate(specs):
        spec = copy.deepcopy(spec)
        ter = build_mesh(spec).to_ter(name=f"ter_{name}")
        meshes[f"rooms{k}"] = ter_part(ter, spec_colors(spec, ter))
    for a in attachments:
        if a.kind == "ground":
            meshes[f"sites_{a.socket}"] = sites_part(a.sites)
    for a in attachments:
        what = (f"{len(a.sites.sites)} Sites" if a.kind == "ground" else
                f"{len(stages._layout_dict(a.layout)['rooms'])} rooms")
        print(f"attach {name}: {a.socket} ({a.kind}) seed {a.seed}: {what}"
              + (f"; warnings {', '.join(a.warnings)}" if a.warnings else ""))
    out.append(root.write_bytes(f"{name}.attach.glb", glb_bytes(meshes)))
    return out


def cmd_rooms(args) -> List[Path]:
    root = OutputRoot(Path(args.out))
    path = Path(args.attach)
    name = args.name or _stem(path, ".attach.json")
    wpath = Path(args.world) if args.world else path.with_name(f"{_stem(path, '.attach.json')}.world.json")
    world = world_mod.load(wpath)
    attachments = stages.load_attachments(path)
    plan = make_plan(name, world.recipe["zone_type"], args.plan)
    if args.decor:
        plan.decor = args.decor
    if args.decor_seed is not None:
        plan.decor_seed = args.decor_seed
    spec, ter, recipe, rooms = rooms_stage(world, attachments, plan)
    print(f"rooms {name}: TER {len(ter.vertices)} verts, {len(ter.polygons)} polys; "
          f"{len(rooms)} RoomContexts (Decor {recipe['decor']})")
    if not rooms and recipe["decor"] != "none":
        print("  note: no RoomContexts: no EverQuest install (EQ_PATH), as a build makes none")
    lower = spec.name.lower()
    return [root.write_bytes(f"ter_{lower}.ter", ter.to_bytes()),
            root.write_bytes(f"{lower}.rooms.glb", glb_bytes({"terrain": ter_part(ter, spec_colors(spec, ter))})),
            root.write_text(f"{lower}.rooms.json", stages.rooms_json(recipe, rooms))]


def cmd_decor(args) -> List[Path]:
    import decor_room as dr
    from generators.room_context import load

    root = OutputRoot(Path(args.out))
    path = Path(args.rooms)
    name = args.name or _stem(path, ".rooms.json")
    recipe, rooms = load(path)
    if not rooms:
        print(f"decor {name}: the rooms file holds no RoomContexts (Decor none, or no install "
              "when it was built)")
    control, seed, done = decor_stage(recipe, rooms, args.control, args.decor_seed)
    eq = None if args.boxes else dr.eq_path_of(args.eq_path)
    meshes = dr.Meshes(eq)
    room_parts, props, boxes = [], [], 0
    for ctx, d, _p in done:
        room_parts.append(dr.room_parts(ctx))
        part, n = dr.prop_parts(d.props, meshes)
        props.append(part)
        boxes += n
    doc = {"recipe": dict(recipe, decor=control, decor_seed=seed),
           "rooms": [{"id": ctx.id, "check": probs, **d.to_dict()} for ctx, d, probs in done]}
    n_props = sum(len(d.props) for _c, d, _p in done)
    problems = [f"{ctx.id}: {p}" for ctx, _d, probs in done for p in probs]
    print(f"decor {name}: {len(done)} rooms, {n_props} Props (Decor {control}, seed {seed}); "
          f"room check: {'ok' if not problems else '; '.join(problems)}")
    if eq is None and n_props:
        print("  note: Props drawn as boxes (no install, or --boxes)")
    elif boxes:
        print(f"  note: {boxes} Props drawn as boxes")
    return [root.write_bytes(f"{name}.decor.glb",
                             glb_bytes({"rooms": _merge(room_parts), "props": _merge(props)})),
            root.write_text(f"{name}.decor.json", json.dumps(doc, indent=1) + "\n")]


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="stage", required=True)

    w = sub.add_parser("world", help="zone type, World inputs and a seed -> <name>.world.json")
    w.add_argument("name")
    w.add_argument("--zone-type", required=True)
    w.add_argument("--seed", type=int, required=True)
    w.add_argument("--biome")
    w.add_argument("--edges", help="the Rim's declared sides, e.g. N=zoneline,E=zoneline")
    w.add_argument("--zone-size", type=float)
    w.set_defaults(run=cmd_world)

    def plan_args(p):
        p.add_argument("--name", help="the zone's name (default: the input file's)")
        p.add_argument("--plan", action="append", default=[], metavar="KEY=VALUE",
                       help="a ZonePlan field (repeatable)")

    a = sub.add_parser("attach", help="a World file -> <name>.attach.json")
    a.add_argument("world")
    plan_args(a)
    a.add_argument("--rooms-seed", type=int, help="lays out the rooms and places the Sites "
                   "(default: the World's seed)")
    a.set_defaults(run=cmd_attach)

    r = sub.add_parser("rooms", help="Attachments (and their World) -> the TER and <name>.rooms.json")
    r.add_argument("attach")
    r.add_argument("--world", help="the World file (default: <name>.world.json beside it)")
    plan_args(r)
    r.add_argument("--decor", help="the Decor control (default: the plan's, else normal)")
    r.add_argument("--decor-seed", type=int)
    r.set_defaults(run=cmd_rooms)

    d = sub.add_parser("decor", help="a rooms file -> the decorated rooms")
    d.add_argument("rooms")
    d.add_argument("--name")
    d.add_argument("--control", help="the Decor control (default: the file's)")
    d.add_argument("--decor-seed", type=int, help="default: the file's")
    d.add_argument("--boxes", action="store_true", help="draw every Prop as a box")
    d.add_argument("--eq-path", help="the EverQuest install (default EQ_PATH, else F:\\everquest_rof2)")
    d.set_defaults(run=cmd_decor)

    for p in (w, a, r, d):
        p.add_argument("--out", default="output/stage", help="folder for the files (default output/stage)")
    return ap


#: What each stage imports, loaded before its clock starts.
IMPORTS = {
    "world": ("trimesh", "generators.wilderness.build", "generators.outdoor_dungeon"),
    "attach": ("trimesh", "ai.expand", "generators.wilderness.build", "generators.outdoor_dungeon",
               "generators.geometry", "generators.sites.placement", "generators.room_layouts",
               "generators.room_scales", "generators.wall_styles"),
    "rooms": ("trimesh", "ai.expand", "generators.builder", "generators.room_context",
              "generators.decor.stock"),
    "decor": ("trimesh", "decor_room", "generators.decor.placement", "generators.decor.stock"),
}


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    # Load the stage's modules first, so its time is the stage's own work.
    import importlib
    for mod in IMPORTS[args.stage]:
        importlib.import_module(mod)
    t0 = time.perf_counter()
    written = args.run(args)
    took = time.perf_counter() - t0
    for p in written:
        print(f"  wrote {p}")
    print(f"  {args.stage} took {took:.2f} s ({time.perf_counter() - _LAUNCH:.1f} s since launch, "
          "imports included)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
