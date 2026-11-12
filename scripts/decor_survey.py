r"""Measure what fills stock rooms (step 11, task 2).

Reads the placed objects (``objects.wld`` instance fragments, 0x15: position, yaw,
scale) of finding 1's 15 dungeons and 15 cities, puts each in a room or a corridor with
step 9's chamber split (``room_feature_survey`` / ``dungeon_topology_survey.split``), and
reports per zone and room style:

- **Props per room** (p10/p50/p90 over the rooms, and the mean) and **per 1000 u²** of
  room floor; corridors (the split's passage, and chambers under ``MIN_ROOM`` a side)
  per 1000 u² of their own floor. In a city, rooms are the chambers with a ceiling
  over at least ``COVERED`` of their floor (buildings); the rest is open ground.
- **Category shares**, from the model's name (``category``; rough until task 3's tags).
- **Mount shares** (``surroundings``): ``floor`` when the model's bottom or origin is within
  ``FLOOR_TOL`` of the floor under it; ``raised`` when it rests on another object (a
  candle on a table, a stacked crate); ``wall`` when its origin is within ``WALL_NEAR``
  of a wall; ``ceiling`` when its top is within ``CEIL_GAP`` of the ceiling over it (or
  through it); else ``raised`` (a ledge the floor ray missed, or the air).
- **Lights' spacing**: each wall-mounted light's distance to its nearest wall-mounted
  light (p50), rooms and corridors together.
- **Groups**: the share of tables with a chair within ``REACH``, chairs per such table,
  and the share of beds with another bed within ``ROW_GAP`` (a row).
- **By doors**: a door is where a room's floor meets another room or a corridor; the
  share of doors with a light within ``DOOR_NEAR``, and the categories that stand there.
- **Light layout** (``--layout``, task 22): wall lights' height over the floor and its
  spread within a room; how a room's lights pair up by symmetry (straight across the room,
  mirrored along one wall, in opposite corners), against the same lights at random spots on
  the room's walls and floor; and which catalogue kinds rooms hold at most once.

It also works out every catalogue model's **observed** fields, over every zone that
places it (outdoor zones from the terrain under them, rooms or not): height over the
floor, distance to the nearest wall, under a ceiling or not, scale, mount, zone type,
and what stands near it. ``--write`` puts them in ``rules/decor/catalogue.json``
through ``prop_catalogue.put_observed``.

Floors, walls and ceilings come from the zone mesh only (``Surfaces``): a WLD floor
winds down (``floors_up=False``), a built one up. Placed objects aren't in the mesh, so
a candle on a table reads ``raised`` and nothing stands on a rug.

The measures take any mesh and any placements (``measure_zone``), so built zones are
judged by the same code (task 14).

Usage::

    python scripts/decor_survey.py --eq-path F:\everquest_rof2
    python scripts/decor_survey.py --eq-path F:\everquest_rof2 --zones paw,qeynos --no-observe
    python scripts/decor_survey.py --eq-path F:\everquest_rof2 --write
"""

from __future__ import annotations

import argparse
import math
import re
import struct
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from analyzer.traverse import AgentModel  # noqa: E402
from core.pfs import PfsArchive  # noqa: E402
from core.ter import FLAG_PASSABLE  # noqa: E402
from core.wld import _decode_string_hash  # noqa: E402
from dungeon_topology_survey import CELL, Floor, _samples, split  # noqa: E402
from outdoor_dungeon_survey import load_mesh  # noqa: E402
from room_feature_survey import MIN_ROOM  # noqa: E402
from wall_survey import STYLES, WIDTH, stock_faces  # noqa: E402

#: Finding 1's cities (Grobb has no ``.s3d`` in the install).
CITIES = ("qeynos2", "qeynos", "freportw", "freportn", "neriaka", "neriakb", "halas",
          "rivervale", "kaladima", "akanon", "erudnext", "felwithea", "oggok", "cabeast",
          "paineel")
#: Every city zone in the install, for the zone type of the catalogue's observed fields.
CITY_ZONES = frozenset(CITIES) | {
    "qeynos3", "qrg", "freporte", "freports", "neriakc", "neriakd", "kaladimb", "erudnint",
    "felwitheb", "grobb", "cabwest", "shadowhaven", "sharvahl", "thurgadina", "thurgadinb",
    "kelethin", "bazaar", "poknowledge", "potranquility", "nexus", "moor",
}
STYLE_ORDER = ("rough", "hewn", "built", "city")

WALL_NZ = 0.7       # a wall face's normal is at most this far up (as wall_survey)
FLAT_NZ = 0.1       # a floor or ceiling face's normal is at least this far up or down
WALL_STEP = 3.0     # wall faces are sampled this finely for the distance (u)
WALL_CAP = 100.0    # distances to a wall past this are stored as this (u)
SINK = 2.0          # a floor up to this far over an object's origin is still under it (u)
FLOOR_TOL = 1.5     # floor Mount: the model's bottom within this of the floor (u)
CEIL_GAP = 3.0      # ceiling Mount: the model's top within this of the ceiling (u)
WALL_NEAR = 3.5     # wall Mount: the origin within this of a wall (u, in 3D)
LID_TOL = 2.0       # ceilings this near the zone's top are a sky lid (u, as wall_survey)
SKY = 250.0         # and so are ceilings more than this over the floor (Crushbone's shell)
HEAD = 4.0          # a ceiling counts from this far over the floor (u)
COVERED = 0.5       # a city chamber under a ceiling on this share of its floor is a room
MIN_PIECE = 150     # a walked floor piece of at least this many nodes is surveyed (2400 u²)
MIN_PASSAGE = 12    # a passage piece of at least this many floor nodes is a corridor
TO_FLOOR = 14.0     # an object joins the walked floor node nearest it within this (u, 3D)
REACH = 12.0        # a chair this near a table sits at it (u, in plan)
ROW_GAP = 16.0      # a bed this near another bed is in a row (u, in plan)
DOOR_NEAR = 16.0    # what stands this near a door (u, in plan)
NEAR = 12.0         # observed "near": other objects within this (u, in plan)
DZ = 8.0            # and within this in height (u)

#: Categories by name, first match wins. Rough: task 3 tags the models properly.
CATEGORIES = (
    ("light", r"TORCH|LAMP|(?<!P)LANT|LANTRN|BRAZ|CANDL|CANDEL|CHANDEL|LIGHT|FIRE|FLAME|"
              r"SCONCE|TIKI|BURNER|GLOW"),
    ("container", r"BARREL|BARL|CRATE|BOX|KEG|CHEST|URN|SACK|BAG|BASKET|CASK|JAR|VASE|"
                  r"BUCKET|TRUNK|POT(\d|$)"),
    ("furniture", r"TABLE|TABL|DESK|CHAIR|BENCH|STOOL|BED|BUNK|PALLET|PAWPAL|DRESSER|"
                  r"DRAWER|BOOKCASE|BOOKSHELF|SHELF|COUCH|DIVAN|SOFA|THRONE|PEW|RUG|"
                  r"CARPET|MAT$|COT$|CABINET|WARDROBE|COUNTER|ANVIL|FORGE|LOOM|ALTAR|"
                  r"PODIUM|LECTERN|FURPILE|FURSTACK|TABAC|SEAT|DOCK|WORKBENCH|STAND"),
    ("hanging", r"BANNER|BANN|PENN|FLAG|HOOK|CHAIN|SHAKLE|SHACKLE|TAPEST|SIGN|PENNANT|DRAPE|"
                r"CURTAIN|NET$|ROPE|MANACLE|HANG|WALLGIZ"),
    ("structure", r"PILLAR|COLUMN|STATUE|LADDER|CAGE|ARCH|DOOR|GATE|BRIDGE|STAIR|FENCE|"
                  r"POST|PLANK|PLNK|BEAM|SUPPORT|SCAFFOLD|WALL|TOTEM|OBELISK|PEDEST|"
                  r"POLE|TOWER|HUT|TENT|WELL$|FOUNTAIN|PILLR|PILL$|PLATFORM|RAIL|LEAN|CART|"
                  r"WAGON|BOAT|SHIP|CANOPY|STOCKS|ANCHOR|CIRCLE|FOUNT|CELL$|GALLOWS"),
    ("debris", r"ROCK|BONE|SKULL|PILE|SLIME|CRYSTAL|RUBBLE|STAL|BRICK|BOULDER|STONE|WEB|"
               r"MUSHROOM|SHROOM|LOG$|LOGS|STUMP|DEBRIS|JUNK|CORPSE|BODY|SKELET|PUNGEE|"
               r"SPIKE|STAKE|MOUND|CHIPS|CRYS|HAUNCH|RUBY|EMERALD|SCULL|SHELL|BOWL|HEAD$|BOOK|BOK|PAPER|SCROLL|SWORD|SHIELD|ARMOR|HELM|AXE|"
               r"SPEAR|HAMMER|MOSS|GEM|COIN|FOOD|MEAT|BREAD|FISH|DISH|PLATE|CUP|MUG|"
               r"BOTTLE|GOBLET|ICE|SNOW|DIRT|MUD|BLOOD|TRASH|HAY|WOOD|RIBS|CARCASS|"
               r"SHOVEL|PICK|TOOL|SAW$|RAKE"),
    ("plant", r"TREE|BUSH|PLANT|FLOWER|FERN|GRASS|VINE|SHRUB|IVY|REED|HEDGE|LEAF|"
              r"CACTUS|PALM|PINE|OAK|CEDAR|ROOT|LILY|WEED|CATTAIL|KELP|CORAL|FLORA|SAPLING"),
)
CATEGORY_NAMES = tuple(c for c, _ in CATEGORIES) + ("other",)
_CAT_RE = [(c, re.compile(p)) for c, p in CATEGORIES]
TABLE = re.compile(r"TABLE|TABL|DESK|COUNTER|TABAC")
CHAIR = re.compile(r"CHAIR|STOOL|BENCH|PEW|COUCH|DIVAN|SOFA|THRONE|SEAT")
BED = re.compile(r"BED|BUNK|PALLET|PAWPAL|COT$|FURPILE")
MOUNTS = ("floor", "wall", "ceiling", "raised")


def category(name: str) -> str:
    """A model's Category from its name (digits and a trailing variant letter ignored)."""
    base = re.sub(r"\d+[A-Z]?$", "", name.upper().split("@")[0])
    for cat, rx in _CAT_RE:
        if rx.search(base):
            return cat
    return "other"


def base_name(name: str) -> str:
    """Finding 1's grouping: the name with its digits stripped."""
    return re.sub(r"\d+", "", name.upper().split("@")[0])


# --- placements -------------------------------------------------------------------------------


@dataclass
class Placed:
    x: float
    y: float
    z: float
    yaw: float     # degrees
    scale: float
    name: str


def placements(eq_path: Path, zone: str) -> list:
    """Every 0x15 instance in the zone's ``objects.wld``: name, object name, flags and a
    reference, then x, y, z, three rotations (512ths of a turn, yaw first) and the
    scale (the second of three floats; the first is always 0). As
    ``room_feature_survey.placed_objects``, plus yaw and scale."""
    path = eq_path / f"{zone}.s3d"
    if not path.exists():
        return []
    data = PfsArchive.from_file(path).get("objects.wld")
    if data is None:
        return []
    _magic, _version, count, _bsp, _u1, hash_size, _u2 = struct.unpack_from("<7I", data, 0)
    strings = _decode_string_hash(data[28:28 + hash_size])
    pos = 28 + hash_size
    out = []
    for _ in range(count):
        size, frag = struct.unpack_from("<II", data, pos)
        if frag == 0x15:
            _name, obj, _flags, _ref = struct.unpack_from("<iiIi", data, pos + 8)
            x, y, z, yaw, _p, _r, _s0, scale = struct.unpack_from("<8f", data, pos + 24)
            name = ""
            if obj < 0:
                name = strings[-obj:strings.find(b"\0", -obj)].decode("latin1")
            out.append(Placed(x, y, z, yaw * 360.0 / 512.0, scale,
                              name.replace("_ACTORDEF", "").upper()))
        pos += 8 + size
    return out


# --- the zone's surfaces ----------------------------------------------------------------------


class Columns:
    """Vertical rays through a set of non-vertical triangles: every height they cross at
    a point. Triangles are bucketed by plan cell; a query tests the triangles in its
    point's cell."""

    def __init__(self, tris: np.ndarray, cell: float = 32.0):
        self.tris, self.cell = tris, cell
        if not len(tris):
            self.keys = np.zeros(0, np.int64)
            self.idx = np.zeros(0, np.int64)
            return
        lo = np.floor(tris[:, :, :2].min(1) / cell).astype(np.int64)
        hi = np.floor(tris[:, :, :2].max(1) / cell).astype(np.int64)
        span = hi - lo + 1
        n = span.prod(1)
        tid = np.repeat(np.arange(len(tris)), n)
        start = np.repeat(np.cumsum(n) - n, n)
        k = np.arange(len(tid)) - start
        sx = np.repeat(span[:, 1], n)
        ci = np.repeat(lo[:, 0], n) + k // sx
        cj = np.repeat(lo[:, 1], n) + k % sx
        keys = self._key(ci, cj)
        order = np.argsort(keys, kind="stable")
        self.keys, self.idx = keys[order], tid[order]

    @staticmethod
    def _key(i, j):
        return (np.asarray(i, np.int64) + (1 << 30)) * (1 << 31) + (np.asarray(j, np.int64) + (1 << 30))

    def hits(self, xy: np.ndarray):
        """(point index, height) for every triangle over or under each point."""
        if not len(self.keys) or not len(xy):
            return np.zeros(0, np.int64), np.zeros(0)
        c = np.floor(xy / self.cell).astype(np.int64)
        q = self._key(c[:, 0], c[:, 1])
        a = np.searchsorted(self.keys, q, "left")
        b = np.searchsorted(self.keys, q, "right")
        n = b - a
        pi = np.repeat(np.arange(len(xy)), n)
        ti = self.idx[np.repeat(a, n) + (np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n))]
        t = self.tris[ti]
        p = xy[pi]
        (x1, y1), (x2, y2), (x3, y3) = t[:, 0, :2].T, t[:, 1, :2].T, t[:, 2, :2].T
        det = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        ok = np.abs(det) > 1e-9
        det = np.where(ok, det, 1.0)
        w1 = ((y2 - y3) * (p[:, 0] - x3) + (x3 - x2) * (p[:, 1] - y3)) / det
        w2 = ((y3 - y1) * (p[:, 0] - x3) + (x1 - x3) * (p[:, 1] - y3)) / det
        w3 = 1.0 - w1 - w2
        eps = -1e-6
        inside = ok & (w1 >= eps) & (w2 >= eps) & (w3 >= eps)
        z = w1 * t[:, 0, 2] + w2 * t[:, 1, 2] + w3 * t[:, 2, 2]
        return pi[inside], z[inside]

    def below(self, pts: np.ndarray, sink: float = SINK) -> np.ndarray:
        """The highest surface at or under each point (up to ``sink`` over it); nan for none."""
        pi, z = self.hits(pts[:, :2])
        keep = z <= pts[pi, 2] + sink
        out = np.full(len(pts), -np.inf)
        np.maximum.at(out, pi[keep], z[keep])
        out[np.isinf(out)] = np.nan
        return out

    def above(self, pts: np.ndarray, gap: float, lid: float = np.inf,
              reach: float = SKY) -> np.ndarray:
        """The lowest surface more than ``gap`` and at most ``reach`` over each point and
        under ``lid``; nan for none."""
        pi, z = self.hits(pts[:, :2])
        keep = (z > pts[pi, 2] + gap) & (z <= pts[pi, 2] + reach) & (z < lid)
        out = np.full(len(pts), np.inf)
        np.minimum.at(out, pi[keep], z[keep])
        out[np.isinf(out)] = np.nan
        return out


class Surfaces:
    """A zone mesh's solid floors, ceilings and walls, for rays and wall distances.
    ``floors_up``: generated floors wind up, WLD floors down."""

    def __init__(self, mesh, floors_up: bool = False):
        v = np.array([(p.x, p.y, p.z) for p in mesh.vertices], dtype=np.float64)
        f = np.array([(p.v1, p.v2, p.v3) for p in mesh.polygons
                      if not p.flags & FLAG_PASSABLE], dtype=np.int64).reshape(-1, 3)
        tri = v[f]
        n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        a = np.linalg.norm(n, axis=1)
        ok = a > 1e-9
        tri, n = tri[ok], n[ok] / a[ok, None]
        nz = n[:, 2] if floors_up else -n[:, 2]
        self.floor = Columns(tri[nz > FLAT_NZ])
        ceil = tri[nz < -FLAT_NZ]
        self.ceil = Columns(ceil)
        self.lid = float(ceil[:, :, 2].max()) - LID_TOL if len(ceil) else np.inf
        walls = tri[np.abs(n[:, 2]) < WALL_NZ]
        pts = _samples(walls, WALL_STEP) if len(walls) else np.zeros((1, 3)) + 1e9
        self.walls = cKDTree(pts)
        self.floor_tris = tri[nz > FLAT_NZ]

    def wall_distance(self, pts: np.ndarray) -> np.ndarray:
        d, _ = self.walls.query(pts, distance_upper_bound=WALL_CAP)
        return np.minimum(d, WALL_CAP)

    def covered(self, pts: np.ndarray) -> np.ndarray:
        """Whether a ceiling stands over each floor point (``HEAD`` up, under the lid)."""
        return np.isfinite(self.ceil.above(pts, HEAD, self.lid))


# --- one object's surroundings ---------------------------------------------------------------


def model_index(cat: dict) -> dict:
    """(zone, NAME) -> catalogue key, from each entry's placements."""
    out = {}
    for key, m in cat["models"].items():
        for zone in m["placed"]["zones"]:
            out[(zone, m["name"])] = key
    return out


def size_of(entry: dict | None):
    """(h, below, w, d) of a catalogue entry in model units, or None."""
    if entry is None:
        return None
    m = entry["measured"]
    return (m["h"], m["below"], m["w"], m["d"])


def surroundings(objs: list, surf: Surfaces, sizes) -> dict:
    """Per object: floor under it, its height over the floor (origin and bottom),
    distance to a wall, ceiling over it, gap from its top to the ceiling, and Mount.
    ``sizes`` gives each object's (h, below, w, d) in model units, or None if unknown.

    Mount, first match: ``floor`` (bottom or origin within ``FLOOR_TOL`` of the floor; a
    model may start over its origin), ``raised``
    (bottom on another object's top: a candle on a table, a stacked crate), ``wall``
    (origin within ``WALL_NEAR`` of a wall), ``ceiling`` (top within ``CEIL_GAP`` of the
    ceiling, or through it), else ``raised`` (a ledge the floor ray missed, or air).
    ``unknown`` where no solid floor face lies under the object at all (a third of the
    East Wastes' objects, beyond or over gaps in its mesh)."""
    if not objs:
        return {k: np.zeros(0) for k in ("floor", "over", "bottom", "wall", "ceil", "gap",
                                         "under")} | {"mount": np.zeros(0, "<U7"),
                                                      "stacked": np.zeros(0, bool)}
    p = np.array([(o.x, o.y, o.z) for o in objs], float)
    s = np.array([o.scale if o.scale > 0 else 1.0 for o in objs])
    hb = np.array([sz if sz is not None else (0.0, 0.0, 0.0, 0.0) for sz in sizes], float)
    top = p[:, 2] + hb[:, 0] * s
    bot = p[:, 2] - hb[:, 1] * s
    half = 0.5 * np.maximum(hb[:, 2], hb[:, 3]) * s
    floor = surf.floor.below(np.c_[p[:, :2], np.maximum(bot, p[:, 2])])
    ceil = surf.ceil.above(np.c_[p[:, :2], np.where(np.isfinite(floor), floor, p[:, 2])],
                           HEAD, surf.lid)
    wall = surf.wall_distance(p)
    over = p[:, 2] - floor
    bottom = bot - floor
    gap = ceil - top
    on_floor = np.isfinite(bottom) & (np.minimum(bottom, over) <= FLOOR_TOL)
    stacked = np.zeros(len(objs), bool)
    tree = cKDTree(p[:, :2])
    reach = min(float(half.max()), 60.0) + 1.0
    for i in np.nonzero(~on_floor)[0]:
        for j in tree.query_ball_point(p[i, :2], reach):
            if (j != i and abs(top[j] - bot[i]) <= FLOOR_TOL and top[j] < top[i]
                    and np.hypot(*(p[i, :2] - p[j, :2])) <= half[j] + 0.5 * half[i]):
                stacked[i] = True
                break
    on_wall = ~on_floor & ~stacked & (wall <= WALL_NEAR)
    hangs = ~on_floor & ~stacked & ~on_wall & np.isfinite(gap) & (gap <= CEIL_GAP)
    mount = np.full(len(objs), "raised", "<U7")
    mount[on_floor], mount[hangs], mount[on_wall] = "floor", "ceiling", "wall"
    mount[~np.isfinite(floor)] = "unknown"
    return {"floor": floor, "over": over, "bottom": bottom, "wall": wall, "ceil": ceil,
            "gap": gap, "under": np.isfinite(ceil), "mount": mount, "stacked": stacked}


def mount_shares(mount) -> dict:
    """Shares of the four Mounts among objects whose Mount is known."""
    n = max(int(np.isin(mount, MOUNTS).sum()), 1)
    return {m: float(np.sum(mount == m)) / n for m in MOUNTS}


def category_shares(names) -> dict:
    c = Counter(category(n) for n in names)
    n = max(len(names), 1)
    return {k: c[k] / n for k in CATEGORY_NAMES}


# --- rooms ------------------------------------------------------------------------------------


def floor_pieces(tris: np.ndarray, agent: AgentModel, min_nodes: int = MIN_PIECE) -> Floor:
    """Step 6's ``Floor`` keeps only the largest connected piece of the walked floor;
    Kaesora's temple, Guk's halls past the water and South Qeynos's town fall outside it.
    Build a ``Floor`` per piece of at least ``min_nodes`` nodes (largest first, dropping
    each piece's triangles before the next) and join them as one, so ``split`` sees all."""
    from dungeon_topology_survey import LAYER_GAP
    from scipy.sparse import block_diag
    pieces, rest = [], tris
    while len(rest):
        f = Floor(rest, agent)
        if f.n < min_nodes:
            break
        pieces.append(f)
        cols = defaultdict(list)
        for k, (i, j) in enumerate(f.ij):
            cols[(int(i), int(j))].append(f.z[k])
        cen = rest.mean(1)
        cij = np.floor(cen[:, :2] / CELL).astype(np.int64)
        taken = np.array([any(abs(z - c[2]) <= LAYER_GAP for z in cols.get((int(i), int(j)), ()))
                          for (i, j), c in zip(cij, cen)], bool)
        if not taken.any():
            break
        rest = rest[~taken]
    if len(pieces) == 1:
        return pieces[0]
    out = object.__new__(Floor)
    out.ij = np.concatenate([f.ij for f in pieces])
    out.z = np.concatenate([f.z for f in pieces])
    out.xy = np.concatenate([f.xy for f in pieces])
    out.n = len(out.z)
    out.graph = block_diag([f.graph for f in pieces], format="csr")
    out.boundary = np.concatenate([f.boundary for f in pieces])
    out.dist = np.concatenate([f.dist for f in pieces])
    out.pieces = len(pieces)
    return out


def doors(floor: Floor, chamber: np.ndarray, rooms: set) -> list:
    """Each door as an array of floor nodes: where a room's floor meets another room's,
    or a corridor's (a passage piece touching two rooms or more, or at least
    ``MIN_PASSAGE`` nodes; smaller pieces are alcoves the split left out). One room/other
    contact further splits where its nodes are more than two cells apart."""
    from dungeon_topology_survey import _sub_components
    lab = np.where(np.isin(chamber, list(rooms)), chamber, -1)
    plab = _sub_components(floor.graph, lab < 0)
    g = floor.graph.tocoo()
    a, b = lab[g.row], lab[g.col]
    pa, pb = plab[g.row], plab[g.col]
    touch = defaultdict(set)
    for r, q in zip(a[(a >= 0) & (b < 0)], pb[(a >= 0) & (b < 0)]):
        touch[int(q)].add(int(r))
    size = np.bincount(plab[plab >= 0]) if (plab >= 0).any() else np.zeros(0, int)
    corridor = {q for q in range(len(size)) if len(touch.get(q, ())) >= 2 or size[q] >= MIN_PASSAGE}
    contact = defaultdict(list)
    for k, (ra, rb, qb) in enumerate(zip(a, b, pb)):
        if ra < 0 or ra == rb:
            continue
        if rb >= 0:
            contact[(int(ra), "room", int(rb))].append(g.row[k])
        elif int(qb) in corridor:
            contact[(int(ra), "passage", int(qb))].append(g.row[k])
    out = []
    for nodes in contact.values():
        idx = np.unique(nodes)
        tree = cKDTree(np.c_[floor.xy[idx], floor.z[idx]])
        parent = np.arange(len(idx))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for i, j in tree.query_pairs(CELL * 2.01, output_type="ndarray"):
            parent[find(i)] = find(j)
        groups = defaultdict(list)
        for i in range(len(idx)):
            groups[find(i)].append(idx[i])
        out += [np.array(v) for v in groups.values()]
    return out


def measure_zone(mesh, agent: AgentModel, objs: list, sizes, floors_up: bool = False,
                 faces=None, city: bool = False) -> dict:
    """Every measure of one zone: ``objs`` are ``Placed``, ``sizes`` each one's
    (h, below, w, d) in model units (or None). ``faces`` is (floor, ceiling) triangles when
    the caller already has the walk surface's. ``city``: rooms are the covered chambers."""
    surf = Surfaces(mesh, floors_up)
    if faces is None:
        from analyzer.traverse import build_walk_surface
        ws = build_walk_surface(mesh, agent, floors_up=floors_up)
        up = ws.normals[:, 2] > 0 if floors_up else ws.normals[:, 2] < 0
        faces = (ws.verts[ws.faces][np.nonzero(ws.standable & up)[0]], None)
    floor = floor_pieces(faces[0], agent)
    chamber, nch = split(floor, WIDTH)
    area = np.bincount(chamber[chamber >= 0], minlength=nch) * CELL * CELL
    rooms = {c for c in range(nch) if area[c] >= MIN_ROOM * MIN_ROOM}
    covered_share = {}
    if city:
        cov = surf.covered(np.c_[floor.xy, floor.z])
        for c in list(rooms):
            covered_share[c] = float(cov[chamber == c].mean())
            if covered_share[c] < COVERED:
                rooms.discard(c)
    sur = surroundings(objs, surf, sizes)
    names = [o.name for o in objs]
    cats = np.array([category(n) for n in names])

    # each object to the walked floor node nearest it
    tree = cKDTree(np.c_[floor.xy, floor.z])
    p = np.array([(o.x, o.y, o.z) for o in objs], float).reshape(-1, 3)
    q = p.copy()
    if len(p):
        q[:, 2] = np.where(np.isfinite(sur["floor"]), sur["floor"], p[:, 2])
    d, node = tree.query(q, distance_upper_bound=TO_FLOOR) if len(p) else ([], [])
    node = np.asarray(node)
    on = np.isfinite(np.asarray(d, float))
    where = np.full(len(objs), -2)              # -2 off the walked floor, -1 corridor
    where[on] = [chamber[k] if chamber[k] in rooms else -1 for k in node[on]]

    room_list = sorted(rooms)
    per_room = np.array([np.sum(where == c) for c in room_list])
    room_area = float(sum(area[c] for c in room_list))
    corr_area = float(floor.n * CELL * CELL - room_area)   # passage, small chambers, open ground
    in_room = where >= 0
    in_corr = where == -1

    # lights on walls: nearest wall light
    wl = (cats == "light") & (sur["mount"] == "wall")
    spacing = []
    if wl.sum() >= 2:
        t = cKDTree(p[wl])
        dd, _ = t.query(p[wl], k=2)
        spacing = dd[:, 1]

    # groups
    tables = np.array([bool(TABLE.search(base_name(n))) for n in names])
    chairs = np.array([bool(CHAIR.search(base_name(n))) and not TABLE.search(base_name(n))
                       for n in names])
    beds = np.array([bool(BED.search(base_name(n))) for n in names])
    seated, per_table = 0, []
    if tables.any() and chairs.any():
        ct = cKDTree(p[chairs][:, :2])
        cz = p[chairs][:, 2]
        for x, y, z in p[tables]:
            near = [i for i in ct.query_ball_point((x, y), REACH) if abs(cz[i] - z) <= DZ]
            if near:
                seated += 1
                per_table.append(len(near))
    in_row = 0
    if beds.sum() >= 2:
        bt = cKDTree(p[beds][:, :2])
        dd, ii = bt.query(p[beds][:, :2], k=2)
        bz = p[beds][:, 2]
        in_row = int(np.sum((dd[:, 1] <= ROW_GAP) & (np.abs(bz[ii[:, 1]] - bz) <= DZ)))

    # doors
    door_groups = doors(floor, chamber, rooms)
    lit_doors, by_door = 0, Counter()
    if door_groups and len(p):
        ot = cKDTree(p[:, :2])
        seen = set()
        for g in door_groups:
            near = set()
            for k in g:
                for i in ot.query_ball_point(floor.xy[k], DOOR_NEAR):
                    if abs(p[i, 2] - floor.z[k]) <= 30:
                        near.add(i)
            if any(cats[i] == "light" for i in near):
                lit_doors += 1
            seen |= near
        by_door = Counter(cats[i] for i in seen)

    def pct(v, q):
        return float(np.percentile(v, q)) if len(v) else float("nan")

    return {
        "objects": len(objs),
        "rooms": len(room_list),
        "in_room": float(in_room.mean()) if len(objs) else 0.0,
        "in_corridor": float(in_corr.mean()) if len(objs) else 0.0,
        "off_floor": float((where == -2).mean()) if len(objs) else 0.0,
        "per_room": [pct(per_room, 10), pct(per_room, 50), pct(per_room, 90)],
        "per_room_mean": float(per_room.mean()) if len(per_room) else float("nan"),
        "empty_rooms": float((per_room == 0).mean()) if len(per_room) else float("nan"),
        "per_1000": 1000.0 * in_room.sum() / room_area if room_area else float("nan"),
        "corridor_per_1000": 1000.0 * in_corr.sum() / corr_area if corr_area else float("nan"),
        "room_area_p50": float(np.median([area[c] for c in room_list])) if room_list else 0.0,
        "category": category_shares([n for n, w in zip(names, where) if w >= -1]),
        "mount": mount_shares(sur["mount"][where >= -1]),
        "light_mount": mount_shares(sur["mount"][(where >= -1) & (cats == "light")]),
        "light_spacing": pct(spacing, 50),
        "tables": int(tables.sum()), "tables_seated": seated / max(int(tables.sum()), 1),
        "chairs_per_table": float(np.mean(per_table)) if per_table else float("nan"),
        "beds": int(beds.sum()), "beds_in_row": in_row / max(int(beds.sum()), 1),
        "doors": len(door_groups), "doors_lit": lit_doors / max(len(door_groups), 1),
        "by_door": {k: v / max(sum(by_door.values()), 1) for k, v in by_door.items()},
        "_where": where, "_sur": sur, "_names": names,
        "_floor": floor, "_chamber": chamber, "_surf": surf,
    }


# --- lights laid out as a set, kinds once a room (task 22) ------------------------------------

SYM_TOL = 6.0       # a light's mirror image this near another light pairs them (u, in plan)
SYM_OUT = 0.7       # a light this far out along an axis (share of the half-extent) is at a wall
SYM_RANDOM = 20     # random layouts per room for the baseline


def _room_frames(rxy: np.ndarray) -> list:
    """A room's axes two ways (its floor's principal axes, and the world's), each with the
    centre and half-extents of its floor (p2-p98) along them."""
    c = rxy.mean(0)
    _, _, vt = np.linalg.svd(rxy - c, full_matrices=False)
    out = []
    for ax in (vt, np.eye(2)):
        loc = (rxy - c) @ ax.T
        lo, hi = np.percentile(loc, 2, 0), np.percentile(loc, 98, 0)
        out.append((c + ((lo + hi) / 2) @ ax, ax, (hi - lo) / 2))
    return out


def _pairs(pts: np.ndarray, frame) -> np.ndarray:
    """Each light's partner, under the room's best of three symmetries (a mirror on either
    axis, or a half turn about the centre): ``across`` (mirrored onto the opposite wall),
    ``along`` (mirrored along one wall), ``corner`` (both out in a corner), ``turn`` (a half
    turn elsewhere), or "" for none."""
    c, ax, half = frame
    loc = (pts - c) @ ax.T
    tree = cKDTree(loc)
    best, lab = -1, None
    for flip in ((1, -1), (-1, 1), (-1, -1)):
        d, j = tree.query(loc * flip)
        ok = (d <= SYM_TOL) & (j != np.arange(len(loc)))
        out_ = np.abs(loc) >= SYM_OUT * np.maximum(half, 1.0)
        lb = np.full(len(loc), "", dtype="<U6")
        for i in np.nonzero(ok)[0]:
            if out_[i].all():
                lb[i] = "corner"
            elif flip == (-1, -1):
                lb[i] = "turn"
            else:
                k = 1 if flip == (1, -1) else 0         # the coordinate the mirror flips
                lb[i] = "across" if out_[i, k] else "along"
        if ok.sum() > best:
            best, lab = int(ok.sum()), lb
    return lab


def _evenness(pts: np.ndarray, frame) -> list:
    """Three lights or more out on one wall: the spread of their spacing (std / mean)."""
    c, ax, half = frame
    loc = (pts - c) @ ax.T
    out = []
    for k in (0, 1):
        for sgn in (-1, 1):
            on = loc[:, 1 - k] * sgn >= SYM_OUT * half[1 - k]
            if on.sum() >= 3:
                g = np.diff(np.sort(loc[on, k]))
                if g.mean() > 0:
                    out.append(float(g.std() / g.mean()))
    return out


def light_layout(m: dict, objs: list, kinds: list, seed: int = 0) -> dict:
    """Task 22's measures of one zone, from ``measure_zone``'s result ``m``: wall lights'
    height over the floor and its spread within a room; how a room's lights (wall and floor)
    pair up by symmetry, against the same lights at random spots on the room's walls and
    floor; and per catalogue kind, the rooms holding it and those holding two or more."""
    rng = np.random.default_rng(seed)
    where, sur, names = m["_where"], m["_sur"], m["_names"]
    floor, chamber, surf = m["_floor"], m["_chamber"], m["_surf"]
    cats = np.array([category(n) for n in names])
    mount = sur["mount"]
    p = np.array([(o.x, o.y, o.z) for o in objs], float).reshape(-1, 3)
    wpts = surf.walls.data
    out = {"over": [], "spread": [], "pairs": Counter(), "random": Counter(), "full": [], "full_random": [],
           "even": [], "kinds": defaultdict(lambda: [0, 0])}
    for room in sorted(set(where[where >= 0].tolist())):
        inr = where == room
        for k, n in Counter(k for k, i in zip(kinds, inr) if i and k).items():
            out["kinds"][k][0] += 1
            out["kinds"][k][1] += n >= 2
        wl = inr & (cats == "light") & (mount == "wall")
        o = sur["over"][wl]
        o = o[np.isfinite(o)]
        out["over"] += o.tolist()
        if len(o) >= 2:
            out["spread"].append(float(o.max() - o.min()))
        lt = inr & (cats == "light") & np.isin(mount, ("wall", "floor"))
        if lt.sum() < 2:
            continue
        nodes = chamber == room
        rxy, rz = floor.xy[nodes], floor.z[nodes]
        frames = _room_frames(rxy)
        pts = p[lt][:, :2]
        labs = [_pairs(pts, f) for f in frames]
        k = int(np.argmax([np.sum(lb != "") for lb in labs]))
        out["pairs"].update(labs[k].tolist())
        out["full"].append(bool(np.all(labs[k] != "")))
        on_wall = mount[lt] == "wall"
        if on_wall.sum() >= 3:
            out["even"] += _evenness(pts[on_wall], frames[k])
        # the baseline: the room's wall spots at a light's height, and its floor
        d, kk = cKDTree(rxy).query(wpts[:, :2], distance_upper_bound=4.0)
        near = np.isfinite(d)
        kk = np.where(near, kk, 0)
        near &= np.abs(wpts[:, 2] - (rz[kk] + 6.0)) <= 6.0
        rw = wpts[near][:, :2]
        for _ in range(SYM_RANDOM):
            bp = np.array([rw[rng.integers(len(rw))] if (w and len(rw)) else rxy[rng.integers(len(rxy))]
                           for w in on_wall])
            bl = [_pairs(bp, f) for f in frames]
            kb = int(np.argmax([np.sum(lb != "") for lb in bl]))
            out["random"].update(bl[kb].tolist())
            out["full_random"].append(bool(np.all(bl[kb] != "")))
    return out


def print_layout(rows: dict) -> None:
    """Task 22's figures over the surveyed zones, dungeons and cities apart."""
    def q(v):
        v = np.asarray(v, float)
        return " ".join(f"{x:.1f}" for x in np.percentile(v, (10, 25, 50, 75, 90))) + f" (n={len(v)})" \
            if len(v) else "-"

    print("\nLights laid out as a set (task 22):")
    kinds = defaultdict(lambda: [0, 0])
    for label, city in (("dungeon", False), ("city", True)):
        kept = [r["_layout"] for z, r in rows.items() if (z in CITIES) == city and "_layout" in r]
        if not kept:
            continue
        over = sum((k["over"] for k in kept), [])
        spread = np.array(sum((k["spread"] for k in kept), []))
        pairs, rand = sum((k["pairs"] for k in kept), Counter()), sum((k["random"] for k in kept), Counter())
        n, nr = max(sum(pairs.values()), 1), max(sum(rand.values()), 1)
        full = sum((k["full"] for k in kept), [])
        full_r = sum((k["full_random"] for k in kept), [])
        even = sum((k["even"] for k in kept), [])
        print(f"  {label}: wall lights' height over the floor p10-p90 {q(over)}")
        if len(spread):
            print(f"        within a room (2+ wall lights), its spread {q(spread)}; within 1 u "
                  f"{np.mean(spread <= 1):.2f}, 2 u {np.mean(spread <= 2):.2f}, 4 u {np.mean(spread <= 4):.2f}")
        print(f"        rooms with 2+ lights {len(full)}, {n} lights; paired (stock / random): "
              + ", ".join(f"{k or 'unpaired'} {pairs[k] / n:.2f}/{rand[k] / nr:.2f}"
                          for k in ("across", "along", "corner", "turn", ""))
              + f"; rooms all paired {np.mean(full) if full else 0:.2f}/{np.mean(full_r) if full_r else 0:.2f}")
        if even:
            print(f"        3+ wall lights on one wall: {len(even)}, spacing std/mean p50 "
                  f"{np.median(even):.2f}, under 0.2 {np.mean(np.array(even) < 0.2):.2f}")
        for k in kept:
            for kind, (a, b) in k["kinds"].items():
                kinds[kind][0] += a
                kinds[kind][1] += b
    once = sorted((k for k, (a, b) in kinds.items() if a >= 4 and b / a <= 0.1), key=lambda k: -kinds[k][0])
    print("  kinds in 4+ rooms, at most a tenth of them holding two or more: "
          + ", ".join(f"{k} {kinds[k][0]} ({kinds[k][1]})" for k in once))
    for k in ("forge", "throne", "chest"):
        if k in kinds:
            print(f"    {k}: {kinds[k][0]} rooms, {kinds[k][1]} with two or more")


# --- observed fields ---------------------------------------------------------------------------


def zone_type(zone: str, surf: Surfaces) -> str:
    """city by name; dungeon when a ceiling covers at least half the zone's floor area
    (floor triangle centroids, by area); outdoor otherwise."""
    if zone in CITY_ZONES:
        return "city"
    t = surf.floor_tris
    if not len(t):
        return "outdoor"
    a = 0.5 * np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1)
    cov = surf.covered(t.mean(1))
    return "dungeon" if a[cov].sum() >= 0.5 * a.sum() else "outdoor"


def _q(v, digits=1):
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    if not len(v):
        return None
    return [round(float(x), digits) for x in np.percentile(v, (10, 50, 90))]


def observe_zone(eq_path: Path, zone: str, index: dict, models: dict):
    """(zone type, {catalogue key: per-object rows}) for one zone."""
    objs = placements(eq_path, zone)
    if not objs:
        return None, {}
    try:
        mesh = load_mesh(eq_path, zone)
    except Exception:  # noqa: BLE001 - no terrain: nothing to measure against
        return None, {}
    surf = Surfaces(mesh, floors_up=False)
    ztype = zone_type(zone, surf)
    keys = [index.get((zone, o.name)) for o in objs]
    sizes = [size_of(models[k] if k else None) for k in keys]
    sur = surroundings(objs, surf, sizes)
    p = np.array([(o.x, o.y, o.z) for o in objs], float)
    tree = cKDTree(p[:, :2])
    rows = defaultdict(list)
    for i, (o, k) in enumerate(zip(objs, keys)):
        if k is None:
            continue
        near = [base_name(objs[j].name) for j in tree.query_ball_point(p[i, :2], NEAR)
                if j != i and abs(p[j, 2] - p[i, 2]) <= DZ]
        rows[k].append((sur["over"][i], sur["wall"][i], bool(sur["under"][i]), o.scale,
                        sur["mount"][i], near))
    return ztype, rows


def observed_entry(per_zone: dict, types: dict) -> dict:
    """One catalogue entry's ``observed``: per zone (count, zone type, medians, under
    share, mount) and over every zone (p10/p50/p90, mount shares, zone types, near)."""
    zones, allrows = {}, []
    for zone in sorted(per_zone):
        rows = per_zone[zone]
        allrows += rows
        over = np.array([r[0] for r in rows], float)
        wall = np.array([r[1] for r in rows], float)
        mounts = Counter(r[4] for r in rows)
        zones[zone] = {
            "n": len(rows), "type": types[zone],
            "over": _q(over)[1] if _q(over) else None,
            "wall": _q(wall)[1] if _q(wall) else None,
            "under": round(sum(r[2] for r in rows) / len(rows), 2),
            "scale": round(float(np.median([r[3] for r in rows])), 2),
            "mount": mounts.most_common(1)[0][0],
        }
    n = len(allrows)
    mounts = Counter(r[4] for r in allrows)
    near = Counter(x for r in allrows for x in set(r[5]))
    scales = [r[3] for r in allrows]
    return {
        "n": n,
        "types": _type_counts(zones),
        "over": _q([r[0] for r in allrows]),
        "wall": _q([r[1] for r in allrows]),
        "under": round(sum(r[2] for r in allrows) / n, 2),
        "scale": [round(float(min(scales)), 2), round(float(np.median(scales)), 2),
                  round(float(max(scales)), 2)],
        "mount": {m: round(mounts[m] / n, 2) for m in MOUNTS + ("unknown",) if mounts[m]},
        "near": [k for k, _ in near.most_common(3)],
        "zones": zones,
    }


def _type_counts(zones: dict) -> dict:
    c = Counter()
    for v in zones.values():
        c[v["type"]] += v["n"]
    return dict(sorted(c.items()))


def observe_all(eq_path: Path, cat: dict, jobs: int | None = None) -> tuple:
    """({catalogue key: observed}, {zone: zone type}) over every zone the catalogue's
    models are placed in."""
    from concurrent.futures import ProcessPoolExecutor
    index = model_index(cat)
    zones = sorted({z for z, _n in index})
    per_key = defaultdict(dict)
    types = {}
    with ProcessPoolExecutor(jobs) as pool:
        futs = {z: pool.submit(observe_zone, eq_path, z, index, cat["models"]) for z in zones}
        for z in zones:
            ztype, rows = futs[z].result()
            if ztype is None:
                continue
            types[z] = ztype
            for k, r in rows.items():
                per_key[k][z] = r
    return {k: observed_entry(v, types) for k, v in per_key.items()}, types


# --- report ------------------------------------------------------------------------------------


def _band(vals, fmt="{:.2f}") -> str:
    v = [x for x in vals if x == x]
    return (fmt.format(min(v)) + "-" + fmt.format(max(v))) if v else "-"


def survey(eq_path: Path, zones, cat: dict, cache: Path | None, layout: bool = False) -> dict:
    agent = AgentModel()
    index = model_index(cat)
    rows = {}
    for zone in zones:
        objs = placements(eq_path, zone)
        mesh = load_mesh(eq_path, zone)
        keys = [index.get((zone, o.name)) for o in objs]
        sizes = [size_of(cat["models"][k] if k else None) for k in keys]
        faces = stock_faces(eq_path, zone, mesh, agent, cache)
        r = measure_zone(mesh, agent, objs, sizes, floors_up=False, faces=faces,
                         city=zone in CITIES)
        r["style"] = "city" if zone in CITIES else STYLES.get(zone, "-")
        r["unknown"] = sum(1 for k in keys if k is None)
        if layout:
            r["_layout"] = light_layout(r, objs, [cat["models"][k]["tags"]["kind"] if k else "" for k in keys])
        rows[zone] = r
        print_zone(zone, r)
    return rows


def print_zone(zone: str, r: dict) -> None:
    c, m = r["category"], r["mount"]
    pr = r["per_room"]
    print(f"{zone:11} {r['style']:5} {r['objects']:4} obj {r['rooms']:3} rooms | room/corr/off "
          f"{r['in_room']:.2f}/{r['in_corridor']:.2f}/{r['off_floor']:.2f} | per room "
          f"{pr[0]:3.0f}/{pr[1]:3.0f}/{pr[2]:3.0f} mean {r['per_room_mean']:5.1f} empty "
          f"{r['empty_rooms']:.2f} | /1000u2 room {r['per_1000']:.2f} corr "
          f"{r['corridor_per_1000']:.2f}", flush=True)
    print("            cat " + " ".join(f"{k[:5]} {c[k]:.2f}" for k in CATEGORY_NAMES)
          + " | mount " + " ".join(f"{k} {m[k]:.2f}" for k in MOUNTS), flush=True)
    print(f"            lights wall {r['light_mount']['wall']:.2f} spacing "
          f"{r['light_spacing']:.0f} | tables {r['tables']} seated {r['tables_seated']:.2f} "
          f"chairs/table {r['chairs_per_table']:.1f} | beds {r['beds']} in a row "
          f"{r['beds_in_row']:.2f} | doors {r['doors']} lit {r['doors_lit']:.2f} by door "
          + ", ".join(f"{k} {v:.2f}" for k, v in sorted(r["by_door"].items(),
                                                       key=lambda kv: -kv[1])[:3]),
          flush=True)


def print_bands(rows: dict) -> None:
    print("\nBands by room style (min-max over the zones):")
    for style in STYLE_ORDER:
        kept = [r for r in rows.values() if r["style"] == style]
        if not kept:
            continue
        print(f"  {style:5} ({len(kept)} zones) per room p50 "
              f"{_band([r['per_room'][1] for r in kept], '{:.0f}')}, mean "
              f"{_band([r['per_room_mean'] for r in kept], '{:.1f}')}, /1000u2 "
              f"{_band([r['per_1000'] for r in kept])}, corridors "
              f"{_band([r['corridor_per_1000'] for r in kept])}, light spacing "
              f"{_band([r['light_spacing'] for r in kept], '{:.0f}')}, doors lit "
              f"{_band([r['doors_lit'] for r in kept])}")
        print("        cat " + ", ".join(f"{k} {_band([r['category'][k] for r in kept])}"
                                      for k in CATEGORY_NAMES))
        print("        mount " + ", ".join(f"{k} {_band([r['mount'][k] for r in kept])}"
                                        for k in MOUNTS))
        allobj = sum(r["objects"] for r in kept)
        pooled = Counter()
        for r in kept:
            for k, v in r["category"].items():
                pooled[k] += v * r["objects"]
        print("        pooled cat " + ", ".join(f"{k} {pooled[k] / allobj:.2f}"
                                             for k in CATEGORY_NAMES))


def print_leftovers(rows: dict, n: int = 40) -> None:
    c = Counter()
    for r in rows.values():
        for name in r["_names"]:
            if category(name) == "other":
                c[base_name(name)] += 1
    total = sum(r["objects"] for r in rows.values())
    print(f"\nUncategorised by name: {sum(c.values())} of {total} "
          f"({sum(c.values()) / max(total, 1):.1%}); commonest:")
    print("  " + ", ".join(f"{k} {v}" for k, v in c.most_common(n)))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--eq-path", required=True, type=Path)
    ap.add_argument("--zones", default=",".join(list(STYLES) + list(CITIES)))
    ap.add_argument("--catalogue", type=Path, default=ROOT / "rules" / "decor" / "catalogue.json")
    ap.add_argument("--cache", type=Path, default=ROOT / "output" / "decor_survey" / "cache",
                    help="keep each zone's walk-surface faces here")
    ap.add_argument("--no-observe", action="store_true",
                    help="skip the catalogue's observed fields (every placing zone)")
    ap.add_argument("--write", action="store_true",
                    help="write the observed fields into the catalogue")
    ap.add_argument("--jobs", type=int, default=None)
    ap.add_argument("--layout", action="store_true",
                    help="also measure how rooms lay their lights out and which kinds they hold once")
    args = ap.parse_args(argv)
    import prop_catalogue
    cat = prop_catalogue.load(args.catalogue)
    rows = survey(args.eq_path, args.zones.split(","), cat, args.cache, args.layout)
    print_bands(rows)
    if args.layout:
        print_layout(rows)
    print_leftovers(rows)
    if not args.no_observe:
        observed, types = observe_all(args.eq_path, cat, args.jobs)
        tc = Counter(types.values())
        print(f"\nObserved: {len(observed)} models over {len(types)} zones ("
              + ", ".join(f"{k} {v}" for k, v in sorted(tc.items())) + ")")
        mounts = Counter()
        for o in observed.values():
            for m, s in o["mount"].items():
                mounts[m] += s * o["n"]
        tot = sum(mounts.values())
        print("  placements by mount: " + ", ".join(f"{m} {mounts[m] / tot:.2f}"
                                                    for m in MOUNTS + ("unknown",)))
        if args.write:
            prop_catalogue.put_observed(cat, observed, args.catalogue)
            print(f"wrote observed fields to {args.catalogue}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
