"""The World and its Sockets (roadmap step 12, design "The Socket", "The World").

The World stage makes a :class:`World`: the terrain grid (or none, for a dungeon or city),
the water level, regions, the Spawn, and the :class:`Socket` s it offers: typed attach points
that rooms and Sites are built off. This module holds only the types and their JSON form; the
stage that makes a World is elsewhere.

The JSON form is versioned (:data:`VERSION`) and its text is stable (sorted keys, one
layout), so a recorded World diffs cleanly. Unlike a RoomContext, **no number is rounded**:
floats are written as Python's ``repr`` writes them (the shortest text that reads back to the
same float, ``-0.0`` included), because the Attach stage makes float comparisons on the
grid's heights and the footprint's points, and a rounded value moves a room (Req 1.5).

How the grids are written (``grid[i][j]`` is the cell or vertex at ``origin + (i, j) * res``):

- **heights**: one list of floats per row, one row to a line. JSON has no NaN, so a missing
  height (NaN) is written ``null`` and read back as NaN; an infinite height is refused.
- **masks** (Rim seal, playable interior): one string per row, ``#`` set and ``.`` not, as
  ``room_context`` writes them.
- **cell types**: one string per row, one character per cell, and the ``node_codes`` legend
  (code -> name, only the codes used) beside it; :data:`NODE_CODES` is the code table.

A file of another version is refused on read, naming the file and both versions (Req 5.3).

This module imports nothing from ``generators.wilderness`` or ``generators.outdoor_dungeon``,
so a test can load a World without them.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

VERSION = 1

#: Socket kinds. ``door`` is reserved (design question 3): it is read, but nothing makes one.
KINDS = ("root", "hillside", "ground", "door")

#: One character per cell type (the wilderness matrix's Node_Types).
NODE_CODES: Dict[str, str] = {
    "plains": "p", "river": "r", "cliff": "c", "mountain_rim": "m",
    "lava": "l", "zoneline_gap": "z", "water": "w",
}

#: Lists written one element to a line, each element whole on its line: a grid's rows.
ROW_KEYS = frozenset({"heights", "node_type", "rim_seal", "playable_interior"})
_SHORT = 100


# -- the stable text ---------------------------------------------------------

def _compact(v: Any) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _depth(v: Any) -> int:
    if isinstance(v, list):
        return 1 + max((_depth(x) for x in v), default=0)
    return 0


def dumps(obj: Any, indent: int = 0, rows: bool = False) -> str:
    """The stable JSON text: sorted keys, objects one key to a line, a short list on one
    line, a grid's rows one to a line. Floats as ``repr``. Parses as ordinary JSON."""
    pad, inner = " " * indent, " " * (indent + 1)
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        items = [f"{inner}{json.dumps(k)}: {dumps(obj[k], indent + 1, k in ROW_KEYS)}" for k in sorted(obj)]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    if isinstance(obj, list) and obj:
        text = _compact(obj)
        if rows:
            return "[\n" + ",\n".join(inner + _compact(x) for x in obj) + "\n" + pad + "]"
        if any(isinstance(x, dict) for x in obj) or _depth(obj) > 2 or (_depth(obj) == 2 and len(text) > _SHORT):
            return "[\n" + ",\n".join(inner + dumps(x, indent + 1) for x in obj) + "\n" + pad + "]"
        return text
    return _compact(obj)


def _plain(v: Any) -> Any:
    """Plain JSON data, every number kept exactly: tuples as lists, numpy values as Python's."""
    if isinstance(v, Mapping):
        return {str(k): _plain(x) for k, x in v.items()}
    if isinstance(v, np.ndarray):
        return _plain(v.tolist())
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        f = float(v)
        if not math.isfinite(f):
            raise ValueError(f"a World holds finite numbers only, not {f!r}")
        return f
    return v


def _check_version(d: Mapping[str, Any], what: str, source: Optional[str]) -> None:
    got = d.get("version")
    if got != VERSION:
        where = f"{source}: " if source else ""
        raise ValueError(f"{where}{what} version {got!r}; this reads version {VERSION}")


# -- grids -------------------------------------------------------------------

def _heights_out(a: np.ndarray) -> List[list]:
    a = np.asarray(a, dtype=np.float64)
    if np.isinf(a).any():
        raise ValueError("a height grid holds no infinite heights")
    return [[None if v != v else v for v in row] for row in a.tolist()]


def _heights_in(rows: Sequence[Sequence], shape) -> np.ndarray:
    _check_rows(rows, shape, "heights")
    out = np.full(tuple(shape), np.nan, dtype=np.float64)
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            if v is not None:
                out[i, j] = float(v)
    return out


def _mask_out(m: np.ndarray) -> List[str]:
    return ["".join(row) for row in np.where(np.asarray(m, dtype=bool), "#", ".")]


def _mask_in(rows: Sequence[str], shape, what: str) -> np.ndarray:
    _check_rows(rows, shape, what)
    out = np.zeros(tuple(shape), dtype=bool)
    for i, row in enumerate(rows):
        out[i] = [c == "#" for c in row]
    return out


def _types_out(t: np.ndarray) -> Tuple[List[str], Dict[str, str]]:
    t = np.asarray(t, dtype=object)
    unknown = sorted({str(v) for v in t.ravel()} - set(NODE_CODES))
    if unknown:
        raise ValueError(f"no code for cell type(s) {unknown}; add them to NODE_CODES")
    rows = ["".join(NODE_CODES[str(v)] for v in row) for row in t]
    used = sorted({str(v) for v in t.ravel()})
    return rows, {NODE_CODES[n]: n for n in used}


def _types_in(rows: Sequence[str], legend: Mapping[str, str], shape) -> np.ndarray:
    _check_rows(rows, shape, "node_type")
    out = np.empty(tuple(shape), dtype=object)
    for i, row in enumerate(rows):
        for j, c in enumerate(row):
            if c not in legend:
                raise ValueError(f"cell type code {c!r} at ({i}, {j}) is not in node_codes")
            out[i, j] = legend[c]
    return out


def _check_rows(rows: Sequence[Sequence], shape, what: str) -> None:
    if len(shape) != 2 or len(rows) != shape[0] or any(len(r) != shape[1] for r in rows):
        raise ValueError(f"{what} is not {tuple(shape)}")


def _same_floats(a: np.ndarray, b: np.ndarray) -> bool:
    """Equal float arrays, NaN equal to NaN and ``-0.0`` not equal to ``0.0``."""
    return (a.shape == b.shape and np.array_equal(a, b, equal_nan=True)
            and np.array_equal(np.signbit(a), np.signbit(b)))


# -- the Socket --------------------------------------------------------------

@dataclass
class Socket:
    """A typed attach point a World offers (design "The Socket").

    ``x, y, z`` is the attach point (a hillside's approach foot, ``z`` the open ground there;
    ground: the Spawn; root: the origin); ``yaw`` the way in faces, ``side`` its compass side
    (N, S, E, W, or "" where it has none); ``width, height`` the opening (0 where it doesn't
    apply); ``level`` the Level (0 today); ``accepts`` what may attach (``"dungeon"``,
    ``"city"``, ``"site"``); ``ground`` the kind's own data, plain JSON with exact numbers.
    """
    id: str
    kind: str
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    yaw: float = 0.0
    side: str = ""
    width: float = 0.0
    height: float = 0.0
    level: int = 0
    accepts: Tuple[str, ...] = ()
    ground: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"Socket {self.id!r}: kind {self.kind!r} is not one of {KINDS}")
        for k in ("x", "y", "z", "yaw", "width", "height"):
            setattr(self, k, _plain(float(getattr(self, k))))
        self.level = int(self.level)
        self.accepts = tuple(str(a) for a in self.accepts)
        self.ground = _plain(dict(self.ground))

    def to_dict(self) -> dict:
        return {"version": VERSION, "id": self.id, "kind": self.kind,
                "x": self.x, "y": self.y, "z": self.z, "yaw": self.yaw, "side": self.side,
                "width": self.width, "height": self.height, "level": self.level,
                "accepts": list(self.accepts), "ground": self.ground}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any], source: Optional[str] = None) -> "Socket":
        _check_version(d, "Socket", source)
        return cls(id=d["id"], kind=d["kind"], x=d["x"], y=d["y"], z=d["z"], yaw=d["yaw"],
                   side=d["side"], width=d["width"], height=d["height"], level=d["level"],
                   accepts=tuple(d["accepts"]), ground=d["ground"])


# -- the Terrain -------------------------------------------------------------

@dataclass(eq=False)
class Terrain:
    """A World's terrain grid: ``heights`` (float64, exact; NaN for none) on vertices at
    ``origin + (i, j) * res``, the cell types (``node_type``, strings), the Rim seal and
    playable-interior masks, and the water level (``None`` for no water)."""
    origin: Tuple[float, float]
    res: float
    heights: np.ndarray
    node_type: np.ndarray
    rim_seal: np.ndarray
    playable_interior: np.ndarray
    water_level: Optional[float] = None

    def __post_init__(self) -> None:
        self.origin = (float(self.origin[0]), float(self.origin[1]))
        self.res = float(self.res)
        self.heights = np.asarray(self.heights, dtype=np.float64)
        self.node_type = np.asarray(self.node_type, dtype=object)
        self.rim_seal = np.asarray(self.rim_seal, dtype=bool)
        self.playable_interior = np.asarray(self.playable_interior, dtype=bool)
        if self.water_level is not None:
            self.water_level = float(self.water_level)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Terrain):
            return NotImplemented
        return (self.to_dict() == other.to_dict()
                and _same_floats(self.heights, other.heights))

    def to_dict(self) -> dict:
        types, legend = _types_out(self.node_type)
        return {"origin": _plain(self.origin), "res": self.res,
                "shape": list(self.heights.shape), "heights": _heights_out(self.heights),
                "cell_shape": list(self.node_type.shape), "node_type": types, "node_codes": legend,
                "rim_seal": _mask_out(self.rim_seal),
                "playable_interior": _mask_out(self.playable_interior),
                "water_level": self.water_level}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Terrain":
        shape, cells = tuple(d["shape"]), tuple(d["cell_shape"])
        return cls(origin=tuple(d["origin"]), res=d["res"],
                   heights=_heights_in(d["heights"], shape),
                   node_type=_types_in(d["node_type"], d["node_codes"], cells),
                   rim_seal=_mask_in(d["rim_seal"], cells, "rim_seal"),
                   playable_interior=_mask_in(d["playable_interior"], cells, "playable_interior"),
                   water_level=d.get("water_level"))


# -- the World ---------------------------------------------------------------

@dataclass
class World:
    """The World stage's result (design "The World"): how it was made (``recipe``: zone type,
    seed, biome, edges, zone size, the Landform request), its terrain (``None`` for a dungeon
    or city), its regions (RegionSpec dicts), the Spawn before any Apron lowers it, and the
    Sockets it offers."""
    recipe: Dict[str, Any] = field(default_factory=dict)
    terrain: Optional[Terrain] = None
    regions: List[Dict[str, Any]] = field(default_factory=list)
    spawn: Tuple[float, ...] = (0.0, 0.0, 0.0)
    sockets: List[Socket] = field(default_factory=list)
    version: int = VERSION

    def __post_init__(self) -> None:
        self.recipe = _plain(dict(self.recipe))
        self.regions = [_plain(dict(r)) for r in self.regions]
        self.spawn = tuple(float(v) for v in self.spawn)
        self.sockets = list(self.sockets)
        ids = [s.id for s in self.sockets]
        if len(set(ids)) != len(ids):
            raise ValueError(f"Socket ids repeat: {ids}")

    def socket(self, id: str) -> Socket:
        for s in self.sockets:
            if s.id == id:
                return s
        raise KeyError(id)

    def to_dict(self) -> dict:
        return {"version": self.version, "recipe": self.recipe,
                "terrain": None if self.terrain is None else self.terrain.to_dict(),
                "regions": self.regions, "spawn": _plain(self.spawn),
                "sockets": [s.to_dict() for s in self.sockets]}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any], source: Optional[str] = None) -> "World":
        _check_version(d, "World", source)
        t = d.get("terrain")
        return cls(recipe=d["recipe"], terrain=None if t is None else Terrain.from_dict(t),
                   regions=d["regions"], spawn=tuple(d["spawn"]),
                   sockets=[Socket.from_dict(s, source) for s in d["sockets"]], version=d["version"])

    def to_json(self) -> str:
        return dumps(self.to_dict()) + "\n"

    @classmethod
    def from_json(cls, text: str, source: Optional[str] = None) -> "World":
        return cls.from_dict(json.loads(text), source)


def save(path, world: World) -> None:
    """Write ``world`` as its stable JSON text (``<name>.world.json``)."""
    Path(path).write_text(world.to_json(), encoding="utf-8", newline="\n")


def load(path) -> World:
    """Read a World file; another version is refused, naming the file and both versions."""
    return World.from_json(Path(path).read_text(encoding="utf-8"), source=str(path))


__all__ = ["KINDS", "NODE_CODES", "Socket", "Terrain", "VERSION", "World", "dumps", "load", "save"]
