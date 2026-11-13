"""The World and its Sockets (roadmap step 12, design "The Socket", "The World").

The World stage makes a :class:`World`: the terrain grid (or none, for a dungeon or city),
the water level, regions, the Spawn, and the :class:`Socket` s it offers: typed attach points
that rooms and Sites are built off. This module holds the types, their JSON form and the
stage itself (:func:`world_for`, :func:`world_of`).

The JSON form is versioned (:data:`VERSION`) and its text is stable (sorted keys, one
layout), so a recorded World diffs cleanly. Unlike a RoomContext, **no number is rounded**:
floats are written as Python's ``repr`` writes them (the shortest text that reads back to the
same float, ``-0.0`` included), because the Attach stage makes float comparisons on the
grid's heights and the footprint's points, and a rounded value moves a room (Req 1.5).

How the grids are written (``grid[i][j]`` is fine cell ``(i, j)``, and its vertex sits at the
cell's centre, ``origin + (i + 0.5, j + 0.5) * res``, as the TER's grid vertices do):

- **heights**: one list of floats per row, one row to a line. JSON has no NaN, so a missing
  height (NaN) is written ``null`` and read back as NaN; an infinite height is refused.
  ``bowl_heights`` (written only when it differs from ``heights``) is the same form.
- **masks** (Rim seal, playable interior): one string per row, ``#`` set and ``.`` not, as
  ``room_context`` writes them.
- **cell types**: one string per row, one character per cell, and the ``node_codes`` legend
  (code -> name, only the codes used) beside it; :data:`NODE_CODES` is the code table.

A file of another version is refused on read, naming the file and both versions (Req 5.3).

Loading a World imports nothing from ``generators.wilderness`` or
``generators.outdoor_dungeon``, so a test can load one without them: only :func:`world_for`
imports them, inside the call.
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
ROW_KEYS = frozenset({"heights", "bowl_heights", "node_type", "rim_seal", "playable_interior"})
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
    """A World's terrain grid: ``heights`` (float64, exact; NaN for none) on the vertices at
    the centres of fine cells, ``origin + (i + 0.5, j + 0.5) * res``: the TER's grid, after
    the water bed sinks. Also the cell types (``node_type``, strings), the Rim seal and
    playable-interior masks, and the water level (``None`` for no water).

    ``bowl_heights`` is the bowl's grid BEFORE the water bed sinks (``land.bowl.heights``,
    what ``outdoor_dungeon.keep_clear_shapes`` digs the Apron on), or ``None`` when it is
    the same as ``heights`` (no water quads); :attr:`undrowned` reads whichever applies.
    It is optional so a file written without it still loads."""
    origin: Tuple[float, float]
    res: float
    heights: np.ndarray
    node_type: np.ndarray
    rim_seal: np.ndarray
    playable_interior: np.ndarray
    water_level: Optional[float] = None
    bowl_heights: Optional[np.ndarray] = None

    def __post_init__(self) -> None:
        self.origin = (float(self.origin[0]), float(self.origin[1]))
        self.res = float(self.res)
        self.heights = np.asarray(self.heights, dtype=np.float64)
        self.node_type = np.asarray(self.node_type, dtype=object)
        self.rim_seal = np.asarray(self.rim_seal, dtype=bool)
        self.playable_interior = np.asarray(self.playable_interior, dtype=bool)
        if self.water_level is not None:
            self.water_level = float(self.water_level)
        if self.bowl_heights is not None:
            self.bowl_heights = np.asarray(self.bowl_heights, dtype=np.float64)
            if self.bowl_heights.shape != self.heights.shape:
                raise ValueError(f"bowl_heights is not {self.heights.shape}")

    @property
    def undrowned(self) -> np.ndarray:
        """The grid before the water bed sinks: ``bowl_heights``, else ``heights``."""
        return self.heights if self.bowl_heights is None else self.bowl_heights

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Terrain):
            return NotImplemented
        return (self.to_dict() == other.to_dict()
                and _same_floats(self.heights, other.heights)
                and _same_floats(self.undrowned, other.undrowned))

    def to_dict(self) -> dict:
        types, legend = _types_out(self.node_type)
        d = {"origin": _plain(self.origin), "res": self.res,
             "shape": list(self.heights.shape), "heights": _heights_out(self.heights),
             "cell_shape": list(self.node_type.shape), "node_type": types, "node_codes": legend,
             "rim_seal": _mask_out(self.rim_seal),
             "playable_interior": _mask_out(self.playable_interior),
             "water_level": self.water_level}
        if self.bowl_heights is not None:
            d["bowl_heights"] = _heights_out(self.bowl_heights)
        return d

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Terrain":
        shape, cells = tuple(d["shape"]), tuple(d["cell_shape"])
        bowl = d.get("bowl_heights")
        return cls(origin=tuple(d["origin"]), res=d["res"],
                   heights=_heights_in(d["heights"], shape),
                   node_type=_types_in(d["node_type"], d["node_codes"], cells),
                   rim_seal=_mask_in(d["rim_seal"], cells, "rim_seal"),
                   playable_interior=_mask_in(d["playable_interior"], cells, "playable_interior"),
                   water_level=d.get("water_level"),
                   bowl_heights=None if bowl is None else _heights_in(bowl, shape))


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


# -- the World stage ---------------------------------------------------------

#: What a ``root`` Socket accepts: a dungeon or city with no world around it.
ROOT_ACCEPTS = ("dungeon", "city")


def _landform(value) -> Any:
    """A Landform from a Landform, its dict form, or ``None``."""
    if value is None or not isinstance(value, Mapping):
        return value
    from generators.wilderness.matrix import Landform
    return Landform.from_dict(dict(value))


def world_for(zone_type: str, seed: Optional[int], *, biome: Optional[str] = None,
              edges: Optional[Mapping[str, str]] = None, zone_size: Optional[float] = None,
              landform: Any = None) -> World:
    """The World stage (design "The World"): the World of a zone of ``zone_type`` from its
    seed and the world controls alone (no room, Site or Decor input), the same text for the
    same inputs.

    A dungeon or city gets no terrain and one ``root`` Socket. A wilderness or outdoor
    dungeon gets the landscape of ``synthesize_landscape``, read as the build reads it:

    - ``terrain``: the PLACED Landform's landscape (``landscape_for`` of the spec, which the
      TER, planning and Sites all read). ``heights`` are exactly the TER's grid vertex Zs
      (``grid_heights``: after the water bed sinks); ``bowl_heights`` the grid before, when
      it differs; the cell types, Rim seal and playable-interior masks are the synth's.
    - ``spawn`` and ``regions``: what ``wilderness_spec`` records in the spec (the safe
      point before any Apron lowers it), from the same landscape as ``terrain`` (task 20).
    - Sockets, in attach order: an outdoor dungeon's ``hill0`` (``hillside``, from
      ``outdoor_dungeon.hillside_socket``), then ``ground`` (Sites; its ``keep_clear`` is
      empty until an Attachment adds to it).

    ``landform`` is the request (a ``Landform`` or its dict): an outdoor dungeon's defaults
    to ``DEFAULT_HOST_HILL`` and its ``zone_size`` to ``OUTDOOR_DUNGEON_ZONE_SIZE``. A
    request without an approach side draws one from the matrix's stream, which a placed
    Landform (side and centre set) doesn't, so the two make different landscapes. The World
    is made on the PLACED Landform: it is placed once, then asked for again as placed (a
    placed Landform places to itself), and everything here reads that one landscape. The
    ``recipe`` records the placed Landform, so asking with the request or with what it
    places gives the same World."""
    from generators.zone_types import DEFINED_ZONE_TYPES, LANDSCAPE_ZONE_TYPES

    if zone_type not in DEFINED_ZONE_TYPES:
        raise ValueError(f"unknown zone type {zone_type!r}; expected one of {DEFINED_ZONE_TYPES}")
    if zone_type not in LANDSCAPE_ZONE_TYPES:
        return World(recipe={"zone_type": zone_type, "seed": seed},
                     sockets=[Socket("root", "root", accepts=ROOT_ACCEPTS)])

    from dataclasses import asdict

    from generators.wilderness.biome import load_biome_kit
    from generators.wilderness.build import (DEFAULT_BIOME, grid_heights, landscape_for,
                                             normalise_edges, synthesize_landscape,
                                             wilderness_spec)
    from generators.wilderness.matrix import DEFAULT_HOST_HILL, OUTDOOR_DUNGEON_ZONE_SIZE

    if seed is None:
        raise ValueError(f"a {zone_type} World needs a seed")
    biome = biome or DEFAULT_BIOME
    edges = normalise_edges(edges)
    request = _landform(landform)
    if zone_type == "outdoor_dungeon":
        request = request if request is not None else DEFAULT_HOST_HILL
        zone_size = zone_size if zone_size else OUTDOOR_DUNGEON_ZONE_SIZE
    zone_size = float(zone_size) if zone_size else None
    placed = None
    if request is not None:
        placed = synthesize_landscape(seed, edges, biome, request, zone_size).matrix.landform
    # The spec's own fields (regions, Spawn, water) as plan_to_spec makes them, on the
    # placed Landform's landscape: the one the TER, planning and Sites read.
    spec = wilderness_spec("world", seed, edges, biome, landform=placed, zone_size=zone_size)
    land = landscape_for(spec)
    heights = grid_heights(land, load_biome_kit(biome))
    bowl = np.asarray(land.bowl.heights, dtype=np.float64)
    terrain = Terrain(origin=land.synth.origin, res=land.synth.resolution, heights=heights,
                      node_type=land.synth.node_type, rim_seal=land.synth.rim_seal_mask,
                      playable_interior=land.synth.playable_interior_mask,
                      water_level=float(land.matrix.water_level),
                      bowl_heights=None if _same_floats(bowl, heights) else bowl)
    spawn = tuple(float(v) for v in spec.safe_point)
    sockets = []
    if zone_type == "outdoor_dungeon":
        from generators.outdoor_dungeon import hillside_socket
        sockets.append(Socket("hill0", "hillside", **hillside_socket(land, heights)))
    sockets.append(Socket("ground", "ground", x=spawn[0], y=spawn[1], z=spawn[2],
                          accepts=("site",),
                          ground={"masks": ["rim_seal", "playable_interior"],
                                  "spawn": list(spawn), "keep_clear": []}))
    recipe = {"zone_type": zone_type, "seed": seed, "biome": biome, "edges": edges,
              "zone_size": zone_size,
              "landform": None if placed is None else placed.to_dict()}
    return World(recipe=recipe, terrain=terrain, regions=[asdict(r) for r in spec.regions],
                 spawn=spawn, sockets=sockets)


def world_of(spec) -> World:
    """The World a spec was made on, from its zone type, seed and ``wilderness`` payload
    (``biome``, ``edges``, ``zone_size``, ``landform``); the spec is not changed.

    The payload records the PLACED Landform, which places to itself, so it is asked for as
    it is: the World is the landscape ``landscape_for`` reads, whatever the request was."""
    payload = spec.wilderness or {}
    if spec.zone_type not in ("wilderness", "outdoor_dungeon") or not payload:
        return world_for(spec.zone_type, spec.seed)
    return world_for(spec.zone_type, spec.seed, biome=payload.get("biome"),
                     edges=payload.get("edges"), zone_size=payload.get("zone_size"),
                     landform=payload.get("landform"))


__all__ = ["KINDS", "NODE_CODES", "ROOT_ACCEPTS", "Socket", "Terrain", "VERSION", "World",
           "dumps", "load", "save", "world_for", "world_of"]
