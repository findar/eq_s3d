r"""Measure the places in stock wilderness (step 10, task 1).

Reads each Classic outdoor zone's placed objects (``objects.wld`` instances, 0x15) with
``room_feature_survey.placed_objects``, names each object by pattern (``kind_of``), and
groups the Structures and props into **Sites**: single-linkage clusters of objects no more
than ``GAP`` u apart. Trees, plants and rocks are scenery and never join a Site; a cluster
with no Structure in it (a lone torch, a crate) isn't a Site either.

Per zone:

- **ground**: the walkable ground (the largest network the traversal agent walks, as in
  ``outdoor_dungeon_survey``), in 1e6 u^2.
- **sites**: Sites per 1e6 u^2 of that ground.
- **structs**: Structures per Site (p50 / p90); props ride along and are counted apart.
- **radius**: a Site's radius (u): its farthest member from its centre (the mean of its
  Structures), p50 / p90. A lone Structure has radius 0.
- **spacing**: each Site's nearest-neighbour distance to another Site's centre, p50 / p10.
- **zoneline**, **water**: from each Site's centre to the nearest walkable ground inside a
  zoneline region (``DRNTP``) or a water region (``WT_``), p50. The regions come from the
  zone's BSP tree (0x21) and region-type fragments (0x29).
- **slope**: the ground under each Site's disc (radius at least ``MIN_DISC``), area-weighted
  mean slope in degrees, p50 / p90 over the Sites.

Spawn is NOT measured: stock safe points live in the server's database, not in the client
files. Zonelines stand in for it (that's where a player walks in).

Then the **Structure models**: for every Structure kind placed at least ``MIN_PLACED`` times
over the surveyed zones, the model is read from ``<zone>_obj.s3d`` (0x36 mesh
``<NAME>_DMSPRITEDEF``) and measured by ``measure_model``: triangles, footprint (plan size
and the solid area under head height), height, collidable share (by area: faces without the
WLD passable flag 0x10) and whether a player can walk in (``walk_in``).

Importable (task 11 judges built zones with the same code): ``kind_of``, ``cluster``,
``site_measures``, ``measure_model``, ``Site``.

``--plots DIR`` draws each zone: walkable ground grey, zonelines purple, water blue, trees as
green dots, each Site circled and labelled with its Structure count.

Usage::

    python scripts/site_survey.py --eq-path F:\everquest_rof2
    python scripts/site_survey.py --eq-path F:\everquest_rof2 --zones qeytoqrg \
        --plots output/site_survey --cache output/site_survey/cache
"""

from __future__ import annotations

import argparse
import math
import re
import struct
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from analyzer.traverse import AgentModel, build_walk_surface  # noqa: E402
from core.pfs import PfsArchive  # noqa: E402
from core.wld import _decode_string_hash, _parse_mesh  # noqa: E402
from outdoor_dungeon_survey import load_mesh  # noqa: E402
from room_feature_survey import placed_objects  # noqa: E402

# Classic (1999) outdoor zones in this install. qey2hh1 is West Karana's file name.
ZONES = ("qeytoqrg", "qey2hh1", "northkarana", "eastkarana", "southkarana", "lakerathe",
         "rathemtn", "ecommons", "nro", "sro", "oasis", "erudsxing", "tox", "butcher",
         "steamfont", "lfaydark", "gfaydark", "kithicor", "nektulos", "innothule",
         "feerrott", "everfrost", "cauldron", "beholder")
#: Zones that are mostly a town or a tree city: measured, but kept out of the bands.
TOWNS = {"gfaydark": "Kelethin's platforms", "butcher": "the Kaladim and Kelethin halls",
         "erudsxing": "a ferry stop, 0.2e6 u^2 of island"}

GAP = 100.0          # objects this close are one Site (u); 60 split farmsteads (a house,
                     # barn and corral stand 60-150 u apart, origin to origin), 150 joins
                     # neighbouring camps
PLAN_CELL = 16.0     # the walked ground is measured on a plan raster of this cell (u)
MIN_DISC = 30.0     # the slope is read under at least this radius (u)
MIN_PLACED = 3       # a Structure kind is modelled when placed this often in total
HEAD = 6.0           # player height (AgentModel.player_height)
HALF_WIDTH = 1.5     # player half-width (generators/wilderness/build.PLAYER_HALF_WIDTH)
WLD_PASSABLE = 0x10  # 0x36 polygon flag: non-solid
WALK_IN_MIN = 25.0   # u^2 of reached floor under a roof or inside walls: room to stand
                     # (a post's own cap reads as a few u^2 of "roof")

# --- naming -------------------------------------------------------------------------

#: Scenery: never part of a Site.
TREE = re.compile(r"TREE|PINE|CEDAR|PALM|REDWOOD|TRUNK|STUMP|VINE|FEDEAD|CACTUS|MUSHROOM"
                  r"|BUSH|PLANT|GRASS|SHRUB|WILLOW|FERN|LOG\d")
#: DTOW and BTOW are the Ro deserts' and Butcherblock's rock spires (to 300 u tall, up to
#: 450 u across), standing along the zone edges: scenery, not watchtowers. HALMOUND is
#: Everfrost's snow mounds (4 u tall, all passable).
ROCK = re.compile(r"ROCK|DUNE|DIRTPILE|^STEAM$|^DTOW\d|^BTOW\d|HALMOUND")

#: Structure kinds, tried in order; first match wins. Step 10's kinds of Structure.
STRUCTURES = (
    ("fire", r"CAMPFIRE|CENTFIRE|^BFIRE|^GFIRE|BONFIRE"),
    ("lean-to", r"LEANTO|CANOPY"),
    ("tent", r"TENT"),
    ("tower", r"FETOW|TOWER|LIGHTHOUSE"),
    ("hut", r"^HUT\d|SHAK|IGLOO"),
    ("house", r"HOUSE|HSE\d|BARN|INN$|SHOP|ARMORY|OUTPOST|NKFORT|FDINN|MRU\d"),
    ("ruin", r"RUIN|PERBRICK"),
    ("fence", r"CORRALL|WOODSUPPORT|^POST$|WALL"),
    ("stone", r"MONU|CAZMON|DOLMEN|BURIAL|TIKI|TOTEM|MCIRCLE|MILESTONE|^HAND$|EAGLE|EFCOL"),
    ("dock", r"DOCK|BRIDGE|FBOAT|DIVINGBRD|ELESTEP"),
)
_STRUCT = [(k, re.compile(p)) for k, p in STRUCTURES]

#: Props: furniture and loose things (step 11). They join Sites but aren't Structures.
PROPS = re.compile(
    r"CHAIR|TABLE|BED|BUNK|DRAWER|DRESSER|CRATE|BARREL|CHEST|TORCH|LAMP|LANT|LIGHT|POLE"
    r"|FLAG|BANNER|SIGN|ANVIL|FORGE|SHARPEN|HAYBALE|CART|WAGON|STOOL|BRAZ|LADDER|RUG|URN"
    r"|GRATE|LOOM|FLETCH|THRONE|BANDIT|DILLS|BONE|RARM|KEG|BUCKET|GALLOWS|FISH|GEAR|STACK"
    r"|BOOKCASE|CANDEL|TREB|BALLISTA|DCAT|MEAL|WMILL|WMBASE|SHAFT|MINECOVER|GDRAG|FIVESTEPS"
    r"|FPILLAR|FELE\d|^TO[A-Z]|^NB$|GOODS|SPARKLING|SOLDIERS|SCOUTS|CHAMPS|EMWAR|BOFK|BILRIOS"
    r"|PACKWEAR|TRUESHOT|HEARTWOOD|SLEEPY|SONGWEVER|PORTAUTH|NTHRONE|DOOR|HHCART|CRYSTAL"
    r"|PAWHOOK|BENCH|ERLANT|ERUDENT|RAIN")


def kind_of(name: str) -> str:
    """'tree', 'rock', a Structure kind (fire, lean-to, tent, tower, hut, house, ruin,
    fence, stone, dock), 'prop', or 'unknown'."""
    n = name.upper()
    if TREE.search(n):
        return "tree"
    if ROCK.search(n):
        return "rock"
    for k, rx in _STRUCT:
        if rx.search(n):
            return k
    if PROPS.search(n):
        return "prop"
    return "unknown"


SCENERY = {"tree", "rock"}
NOT_STRUCTURE = SCENERY | {"prop", "unknown"}

# --- Sites ----------------------------------------------------------------------------


@dataclass
class Site:
    centre: np.ndarray                  # (2,) mean of the Structures
    members: list                       # (x, y, z, name, kind)
    radius: float = 0.0

    @property
    def structures(self) -> list:
        return [m for m in self.members if m[4] not in NOT_STRUCTURE]

    @property
    def props(self) -> list:
        return [m for m in self.members if m[4] in ("prop", "unknown")]


def cluster(objs, gap: float = GAP) -> list:
    """Sites from placed objects ``(x, y, z, name)`` (or with a 5th field, the kind):
    single-linkage over everything that isn't scenery, kept when a cluster holds a
    Structure. Built zones pass their own ZON objects here (task 11)."""
    items = []
    for o in objs:
        k = o[4] if len(o) > 4 and isinstance(o[4], str) else kind_of(o[3])
        if k not in SCENERY:
            items.append((float(o[0]), float(o[1]), float(o[2]), o[3], k))
    if not items:
        return []
    xy = np.array([(i[0], i[1]) for i in items])
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, j in cKDTree(xy).query_pairs(gap):
        parent[find(i)] = find(j)
    groups = defaultdict(list)
    for i in range(len(items)):
        groups[find(i)].append(items[i])
    sites = []
    for g in groups.values():
        st = [m for m in g if m[4] not in NOT_STRUCTURE]
        if not st:
            continue
        c = np.mean([(m[0], m[1]) for m in st], axis=0)
        r = max(math.hypot(m[0] - c[0], m[1] - c[1]) for m in g)
        sites.append(Site(c, g, r))
    return sites


@dataclass
class Ground:
    """The walked ground: standable faces of the main network, plus every up face."""
    centroids: np.ndarray               # (F, 3) walked faces
    area: np.ndarray                    # (F,)
    slope: np.ndarray                   # (F,) degrees
    region: np.ndarray                  # (F,) BSP region (1-based, 0 = none)
    up_centroids: np.ndarray = field(default_factory=lambda: np.zeros((0, 3)))
    up_area: np.ndarray = field(default_factory=lambda: np.zeros(0))
    up_slope: np.ndarray = field(default_factory=lambda: np.zeros(0))
    #: The walked ground in plan: ``PLAN_CELL`` cells it covers, and each cell's BSP region.
    #: Summing face areas double counts where layers overlap (West Karana's walkable
    #: faces add up to 1.5 times its bounding box), so area comes from the cells.
    cells: np.ndarray = field(default_factory=lambda: np.zeros((0, 2), np.int64))
    cell_region: np.ndarray = field(default_factory=lambda: np.zeros(0, np.int64))
    cell_wet: np.ndarray | None = None  # (K,) bool: under water (left out of ``total``)

    @property
    def total(self) -> float:
        """Walkable DRY ground in plan: a lake or sea bed is walkable but no place for a
        Site."""
        if not len(self.cells):
            return float(self.area.sum())
        dry = len(self.cells) if self.cell_wet is None else int((~self.cell_wet).sum())
        return dry * PLAN_CELL * PLAN_CELL

    @property
    def cell_xy(self) -> np.ndarray:
        return (self.cells + 0.5) * PLAN_CELL


def site_measures(sites, ground: Ground, zonelines: np.ndarray, water: np.ndarray) -> dict:
    """Per-zone measures of ``sites`` on ``ground``. ``zonelines`` and ``water`` are (N, 2)
    points (empty when the zone has none). Arrays are per Site."""
    n = len(sites)
    c = np.array([s.centre for s in sites]).reshape(-1, 2)
    out = {
        "ground": ground.total,
        "sites": n,
        "per_area": n / (ground.total / 1e6) if ground.total else 0.0,
        "structs": np.array([len(s.structures) for s in sites]),
        "props": np.array([len(s.props) for s in sites]),
        "radius": np.array([s.radius for s in sites]),
        "spacing": np.zeros(0), "zoneline": np.zeros(0), "water": np.zeros(0),
        "slope": np.zeros(0),
    }
    if n >= 2:
        d, _ = cKDTree(c).query(c, k=2)
        out["spacing"] = d[:, 1]
    for key, pts in (("zoneline", zonelines), ("water", water)):
        if n and len(pts):
            out[key] = cKDTree(pts).query(c)[0]
    if n and len(ground.up_area):
        tree = cKDTree(ground.up_centroids[:, :2])
        sl = []
        for s in sites:
            idx = tree.query_ball_point(s.centre, max(s.radius, MIN_DISC))
            # the ground: the lowest up faces near the Site's own height (not a roof)
            z0 = np.median([m[2] for m in s.structures])
            idx = [i for i in idx if abs(ground.up_centroids[i, 2] - z0) < 40.0]
            if idx:
                a = ground.up_area[idx]
                sl.append(float((ground.up_slope[idx] * a).sum() / a.sum()))
            else:
                sl.append(float("nan"))
        out["slope"] = np.array(sl)
    return out


# --- the zone's ground and regions -------------------------------------------------------


def _frags(data: bytes):
    _m, _v, count, _b, _u, hs, _u2 = struct.unpack_from("<7I", data, 0)
    strings = _decode_string_hash(data[28:28 + hs])
    pos = 28 + hs
    for _ in range(count):
        if pos + 8 > len(data):
            return
        size, fid = struct.unpack_from("<II", data, pos)
        yield fid, pos + 8, size, strings
        pos += 8 + size


def _name(strings: bytes, ref: int) -> str:
    if ref >= 0:
        return ""
    return strings[-ref:strings.find(b"\0", -ref)].decode("latin1")


def regions(eq_path: Path, zone: str):
    """The zone's BSP tree (normals, distances, region, left, right) and region kinds:
    region index (1-based) -> 'zoneline' or 'water' (lava and the rest are ignored)."""
    data = PfsArchive.from_file(eq_path / f"{zone}.s3d").get(f"{zone}.wld")
    nodes, kinds = None, {}
    for fid, b, _size, s in _frags(data):
        if fid == 0x21:
            (n,) = struct.unpack_from("<I", data, b + 4)
            raw = np.frombuffer(data, dtype=np.dtype([("n", "<f4", 3), ("d", "<f4"),
                                                      ("r", "<u4"), ("l", "<u4"),
                                                      ("rt", "<u4")]),
                                count=n, offset=b + 8)
            nodes = raw
        elif fid == 0x29:
            nref, _flags, n = struct.unpack_from("<iII", data, b)
            nm = _name(s, nref)
            kind = ("zoneline" if nm.startswith("DRNTP")
                    else "water" if nm.startswith("WT") else None)
            if kind:
                for r in struct.unpack_from(f"<{n}I", data, b + 12):
                    kinds[r + 1] = kind
    return nodes, kinds


def region_of(nodes, points: np.ndarray) -> np.ndarray:
    """BSP leaf region (1-based, 0 = none) of each point: in front of a node's plane
    (n.p + d >= 0) goes left."""
    out = np.zeros(len(points), np.int64)
    if nodes is None or len(nodes) == 0:
        return out
    nrm, dist = nodes["n"].astype(np.float64), nodes["d"].astype(np.float64)
    reg, left, right = nodes["r"], nodes["l"], nodes["rt"]
    cur = np.zeros(len(points), np.int64)            # 0-based node index
    live = np.ones(len(points), bool)
    for _ in range(4096):
        if not live.any():
            break
        i = np.nonzero(live)[0]
        node = cur[i]
        leaf = reg[node] != 0
        out[i[leaf]] = reg[node[leaf]]
        live[i[leaf]] = False
        i, node = i[~leaf], node[~leaf]
        side = (points[i] * nrm[node]).sum(1) + dist[node] >= 0
        nxt = np.where(side, left[node], right[node]).astype(np.int64)
        dead = nxt == 0
        live[i[dead]] = False
        cur[i[~dead]] = nxt[~dead] - 1
    return out


def ground_of(eq_path: Path, zone: str, agent: AgentModel, cache: Path | None = None) -> Ground:
    """The walked ground of a stock zone (cached: ``build_walk_surface`` is slow)."""
    if cache is not None:
        f = cache / f"{zone}.npz"
        if f.exists():
            z = np.load(f)
            if "k" in z:
                return Ground(z["c"], z["a"], z["s"], z["r"], z["uc"], z["ua"], z["us"],
                              z["k"], z["kr"])
    mesh = load_mesh(eq_path, zone)
    surf = build_walk_surface(mesh, agent, floors_up=False)
    v, faces = surf.verts, surf.faces
    tri = v[faces]
    cr = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    area = 0.5 * np.linalg.norm(cr, axis=1)
    nz = -cr[:, 2] / np.maximum(2 * area, 1e-9)       # WLD floors wind down
    slope = np.degrees(np.arccos(np.clip(nz, -1, 1)))
    std = np.nonzero(surf.standable)[0]
    by = defaultdict(float)
    for fi in std:
        by[int(surf.component[fi])] += area[fi]
    main = max(by, key=by.get)
    walked = std[surf.component[std] == main]
    up = np.nonzero((nz > 0.05) & (area > 0))[0]
    nodes, _ = regions(eq_path, zone)
    cen = surf.centroids
    pts = _samples(tri[walked], PLAN_CELL / 2)
    ij = np.floor(pts[:, :2] / PLAN_CELL).astype(np.int64)
    cells, first = np.unique(ij, axis=0, return_index=True)
    g = Ground(cen[walked], area[walked], slope[walked],
               region_of(nodes, cen[walked] + [0, 0, 3.0]),
               cen[up], area[up], slope[up],
               cells, region_of(nodes, pts[first] + [0, 0, 3.0]))
    if cache is not None:
        cache.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cache / f"{zone}.npz", c=g.centroids, a=g.area, s=g.slope,
                            r=g.region, uc=g.up_centroids, ua=g.up_area, us=g.up_slope,
                            k=g.cells, kr=g.cell_region)
    return g


def placed(eq_path: Path, zone: str) -> list:
    """``placed_objects`` plus each instance's scale: (x, y, z, name, scale). The 0x15
    body after the position holds three rotations, a parameter, then the scales."""
    objs = placed_objects(eq_path, zone)
    data = PfsArchive.from_file(eq_path / f"{zone}.s3d").get("objects.wld")
    scales = []
    for fid, b, _size, _s in _frags(data):
        if fid == 0x15:
            scales.append(struct.unpack_from("<f", data, b + 16 + 12 + 12 + 4)[0])
    return [(*o, sc) for o, sc in zip(objs, scales)]


# --- Structure models -------------------------------------------------------------------


def model_meshes(eq_path: Path, zone: str) -> dict:
    """NAME -> (verts (V,3), faces (F,3), passable (F,)) from ``<zone>_obj.s3d``."""
    p = eq_path / f"{zone}_obj.s3d"
    if not p.exists():
        return {}
    data = PfsArchive.from_file(p).get(f"{zone}_obj.wld")
    if data is None:
        return {}
    (version,) = struct.unpack_from("<I", data, 4)
    out = {}
    for fid, b, size, s in _frags(data):
        if fid != 0x36:
            continue
        nm = _name(s, struct.unpack_from("<i", data, b)[0]).replace("_DMSPRITEDEF", "")
        m = _parse_mesh(data, b, b + size, version == 0x00015500)
        if m is None or not m.polygons:
            continue
        v = np.array(m.vertices, float)
        pol = np.array([p_[:3] for p_ in m.polygons], int)
        ok = (pol < len(v)).all(1)
        flags = np.array([p_[3] for p_ in m.polygons])[ok]
        out[nm] = (v, pol[ok], (flags & WLD_PASSABLE) != 0)
    return out


def _samples(tri: np.ndarray, step: float = 0.5) -> np.ndarray:
    """Points over each triangle, about ``step`` apart (barycentric grid)."""
    pts = []
    for t in tri:
        e = max(np.linalg.norm(t[1] - t[0]), np.linalg.norm(t[2] - t[0]),
                np.linalg.norm(t[2] - t[1]))
        k = max(1, int(math.ceil(e / step)))
        i, j = np.meshgrid(np.arange(k + 1), np.arange(k + 1), indexing="ij")
        m = i + j <= k
        u, w = i[m] / k, j[m] / k
        pts.append(t[0] + np.outer(u, t[1] - t[0]) + np.outer(w, t[2] - t[0]))
    return np.concatenate(pts) if pts else np.zeros((0, 3))


def measure_model(verts: np.ndarray, faces: np.ndarray, passable: np.ndarray,
                  scale: float = 1.0, ground: float = 0.0) -> dict:
    """Triangles, plan size, height, solid footprint under head height, collidable share
    and walk-in for one model at ``scale``. The ground is at ``ground`` (model z, before
    scaling); the origin is the ground for stock objects (checked on the plots).

    **Walk-in**: rasterise (1 u cells) every solid surface between 0.5 u and head height
    over the ground, grow it by the player's half-width, and flood the free cells from
    outside the model. The model is walk-in when the flood reaches at least ``2 x 2`` u
    of cells under the model's own roof (geometry over head height) or, without a roof,
    inside its walls (blocked on all four sides)."""
    v = verts * scale
    g = ground * scale
    tri = v[faces]
    cr = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    area = 0.5 * np.linalg.norm(cr, axis=1)
    solid = ~passable
    lo, hi = v.min(0), v.max(0)
    out = {"tris": int(len(faces)), "w": float(hi[0] - lo[0]), "d": float(hi[1] - lo[1]),
           "h": float(hi[2] - g), "below": float(g - lo[2]),
           "solid_share": float(area[solid].sum() / max(area.sum(), 1e-9))}
    pts = _samples(tri[solid]) if solid.any() else np.zeros((0, 3))
    band = pts[(pts[:, 2] > g + 0.5) & (pts[:, 2] < g + HEAD)]
    roof = _samples(tri)  # any surface over head height counts as cover (cloth too)
    roof = roof[roof[:, 2] >= g + HEAD]
    pad = 6
    x0, y0 = math.floor(lo[0]) - pad, math.floor(lo[1]) - pad
    nx, ny = int(math.ceil(hi[0])) + pad - x0, int(math.ceil(hi[1])) + pad - y0
    occ = np.zeros((nx, ny), bool)
    if len(band):
        occ[(band[:, 0] - x0).astype(int).clip(0, nx - 1),
            (band[:, 1] - y0).astype(int).clip(0, ny - 1)] = True
    out["footprint"] = float(occ.sum())
    cover = np.zeros_like(occ)
    if len(roof):
        cover[(roof[:, 0] - x0).astype(int).clip(0, nx - 1),
              (roof[:, 1] - y0).astype(int).clip(0, ny - 1)] = True
    # grow by the half-width (a disc)
    r = int(math.ceil(HALF_WIDTH))
    blocked = occ.copy()
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            if dx * dx + dy * dy <= HALF_WIDTH * HALF_WIDTH + 0.5 and (dx or dy):
                blocked |= np.roll(np.roll(occ, dx, 0), dy, 1)
    free = ~blocked
    reach = np.zeros_like(free)
    reach[0, :] = free[0, :]; reach[-1, :] = free[-1, :]
    reach[:, 0] |= free[:, 0]; reach[:, -1] |= free[:, -1]
    while True:
        grow = reach.copy()
        grow[1:, :] |= reach[:-1, :]; grow[:-1, :] |= reach[1:, :]
        grow[:, 1:] |= reach[:, :-1]; grow[:, :-1] |= reach[:, 1:]
        grow &= free
        if (grow == reach).all():
            break
        reach = grow
    walls = (np.maximum.accumulate(occ, 0) & np.maximum.accumulate(occ[::-1], 0)[::-1]
             & np.maximum.accumulate(occ, 1) & np.maximum.accumulate(occ[:, ::-1], 1)[:, ::-1])
    inside = (cover | walls) & ~occ
    out["inside"] = float((inside & free).sum())
    out["walk_in_area"] = float((inside & reach).sum())
    out["walk_in"] = bool(out["walk_in_area"] >= WALK_IN_MIN)
    out["closed"] = float((inside & free & ~reach).sum())    # free inside, not reached
    return out


# --- report -------------------------------------------------------------------------------


def _q(values, qs=(50, 90), fmt="{:.0f}") -> str:
    values = np.asarray(values, float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return "-"
    return "/".join(fmt.format(np.percentile(values, q)) for q in qs)


def plot(zone: str, ground: Ground, kinds: dict, objs, sites, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(14, 14), dpi=70)
    c = ground.cell_xy
    ax.scatter(c[:, 0], c[:, 1], s=1, c="#dddddd", linewidths=0)
    reg = np.array([kinds.get(int(r), "") for r in ground.cell_region])
    for k, col in (("water", "#7fb2e5"), ("zoneline", "#a040c0")):
        m = reg == k
        ax.scatter(c[m, 0], c[m, 1], s=2, c=col, linewidths=0)
    t = np.array([(o[0], o[1]) for o in objs if kind_of(o[3]) == "tree"]).reshape(-1, 2)
    ax.scatter(t[:, 0], t[:, 1], s=2, c="#4c9a4c", linewidths=0)
    r = np.array([(o[0], o[1]) for o in objs if kind_of(o[3]) == "rock"]).reshape(-1, 2)
    ax.scatter(r[:, 0], r[:, 1], s=3, c="#8a7a60", linewidths=0)
    for o in objs:
        k = kind_of(o[3])
        if k in SCENERY:
            continue
        col = "black" if k == "prop" else "red" if k == "unknown" else "tab:orange"
        ax.plot(o[0], o[1], "s" if k != "prop" else ".", ms=4 if k != "prop" else 3, c=col)
    for s in sites:
        ax.add_patch(plt.Circle(s.centre, max(s.radius, 15), fill=False, ec="tab:blue", lw=1))
        names = Counter(m[3] for m in s.structures).most_common(2)
        ax.annotate(f"{len(s.structures)} " + " ".join(n for n, _ in names),
                    s.centre, fontsize=7, color="navy")
    ax.set_aspect("equal")
    ax.set_title(f"{zone}: {len(sites)} Sites (blue), Structures orange, props black, "
                 f"unknown red; water blue, zonelines purple")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--eq-path", required=True, type=Path)
    ap.add_argument("--zones", default=",".join(ZONES))
    ap.add_argument("--gap", type=float, default=GAP)
    ap.add_argument("--plots", type=Path)
    ap.add_argument("--cache", type=Path, default=ROOT / "output" / "site_survey" / "cache")
    args = ap.parse_args(argv)
    agent = AgentModel()
    zones = [z for z in args.zones.split(",") if z]

    print(f"{'zone':12} {'ground':>6} {'sites':>5} {'/1e6':>5} | {'structs p50/90':>14} "
          f"{'props':>5} | {'radius':>7} | {'spacing p50/10':>14} | {'zoneline':>8} "
          f"{'water':>6} | {'slope p50/90':>12}")
    rows, placed_names, where, unknown = {}, Counter(), defaultdict(list), Counter()
    for zone in zones:
        objs = placed(args.eq_path, zone)
        ground = ground_of(args.eq_path, zone, agent, args.cache)
        _nodes, kinds = regions(args.eq_path, zone)
        reg = np.array([kinds.get(int(r), "") for r in ground.cell_region])
        zl = ground.cell_xy[reg == "zoneline"]
        wt = ground.cell_xy[reg == "water"]
        ground.cell_wet = reg == "water"
        sites = cluster(objs, args.gap)
        m = site_measures(sites, ground, zl, wt)
        m["kinds"] = Counter(st[4] for s in sites for st in s.structures)
        m["objs"] = len(objs)
        m["trees"] = sum(kind_of(o[3]) == "tree" for o in objs)
        rows[zone] = m
        for o in objs:
            k = kind_of(o[3])
            if k == "unknown":
                unknown[o[3]] += 1
            if k not in NOT_STRUCTURE:
                placed_names[o[3]] += 1
                where[o[3]].append((zone, o[4]))
        tag = f"  (town: {TOWNS[zone]})" if zone in TOWNS else ""
        print(f"{zone:12} {m['ground'] / 1e6:6.1f} {m['sites']:5d} {m['per_area']:5.1f} | "
              f"{_q(m['structs']):>14} {int(m['props'].sum()):5d} | {_q(m['radius'], (50,)):>7} | "
              f"{_q(m['spacing'], (50, 10)):>14} | {_q(m['zoneline'], (50,)):>8} "
              f"{_q(m['water'], (50,)):>6} | {_q(m['slope'], (50, 90), '{:.1f}'):>12}{tag}",
              flush=True)
        print("      Structures: " + ", ".join(f"{k} {c}" for k, c in m["kinds"].most_common()))
        if args.plots:
            plot(zone, ground, kinds, objs, sites, args.plots / f"{zone}.png")

    kept = {z: r for z, r in rows.items() if z not in TOWNS}
    if kept:
        def band(key, q=50):
            vals = [np.nanpercentile(r[key], q) for r in kept.values()
                    if np.isfinite(r[key]).any()]
            return (f"{np.percentile(vals, 10):.1f}-{np.percentile(vals, 90):.1f} "
                    f"(min {min(vals):.1f}, max {max(vals):.1f})") if vals else "-"
        per = [r["per_area"] for r in kept.values()]
        print(f"\nBands over {len(kept)} zones (towns left out), zone p10-p90:")
        print(f"  Sites per 1e6 u^2 {np.percentile(per, 10):.1f}-{np.percentile(per, 90):.1f} "
              f"(min {min(per):.1f}, max {max(per):.1f}, median {np.median(per):.1f})")
        print(f"  Structures per Site, zone p50 {band('structs')}; zone p90 {band('structs', 90)}")
        print(f"  Site radius p50 {band('radius')}; p90 {band('radius', 90)}")
        print(f"  spacing p50 {band('spacing')}; p10 {band('spacing', 10)}")
        print(f"  zoneline p50 {band('zoneline')}; water p50 {band('water')}")
        print(f"  slope p50 {band('slope')}; p90 {band('slope', 90)}")
        allst = np.concatenate([r["structs"] for r in kept.values()])
        print(f"  all Sites: {len(allst)}; lone (1 Structure) {np.mean(allst == 1):.0%}, "
              f"2-5 {np.mean((allst >= 2) & (allst <= 5)):.0%}, 6+ {np.mean(allst >= 6):.0%}")
    if unknown:
        print("\nUnnamed objects (not tree, rock, Structure or prop): "
              + ", ".join(f"{n} {c}" for n, c in unknown.most_common()))

    print(f"\nStructure models (placed >= {MIN_PLACED} times over the zones; size at the "
          "commonest scale):")
    print(f"{'model':12} {'kind':8} {'placed':>6} {'zone':12} {'scale':>5} {'tris':>5} "
          f"{'w x d':>11} {'h':>5} {'below':>5} {'solid ft':>8} {'solid':>5} {'walk-in':>7}")
    meshes: dict = {}
    for name, n in sorted(placed_names.items(), key=lambda kv: (kind_of(kv[0]), -kv[1])):
        if n < MIN_PLACED:
            continue
        sc = Counter(round(s, 2) for _z, s in where[name]).most_common(1)[0][0]
        mesh, zone = None, where[name][0][0]
        for z in dict.fromkeys(z for z, _s in where[name]):   # the first zone that has it
            if z not in meshes:
                meshes[z] = model_meshes(args.eq_path, z)
            if name in meshes[z]:
                mesh, zone = meshes[z][name], z
                break
        if mesh is None:
            print(f"{name:12} {kind_of(name):8} {n:6d} {zone:12} no static mesh (skeletal or missing)")
            continue
        r = measure_model(*mesh, scale=sc)
        print(f"{name:12} {kind_of(name):8} {n:6d} {zone:12} {sc:5.2f} {r['tris']:5d} "
              f"{r['w']:5.0f}x{r['d']:<5.0f} {r['h']:5.0f} {r['below']:5.1f} "
              f"{r['footprint']:8.0f} {r['solid_share']:5.0%} "
              f"{('yes ' + str(int(r['walk_in_area']))) if r['walk_in'] else 'no':>7}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
