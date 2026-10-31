"""
generators/eqmap.py
-------------------
EverQuest in-client map files (``maps/<name>.txt``): the coordinate
convention, the Grounding_Check that proves it against stock RoF2 zones, the
record formatter, the parser and the writer (M2 Requirements 4, 5.2, 6).

The map convention is **negate + swap**: map ``(mx, my, mz) = (-y, -x, z)``,
measured against the stock maps of the Reference_Zones (design research
finding 2). It is its own inverse, so ``map_to_world`` is the same formula.

``build_map_file`` (outline -> layers) is added on top of this by task 6.

The grammar (stock files, design research finding 1)::

    L x1, y1, z1, x2, y2, z2, r, g, b
    P x, y, z, r, g, b, size, text

We write the single-space form, 4 decimals, CR LF; the parser accepts any
spacing after commas, integer or decimal coordinates, CR LF or LF and blank
lines, and skips (with its 1-based line number) anything malformed.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from core.paths import OutputRoot
from core.pfs import PfsArchive
from core.ter import TerFile

# ---------------------------------------------------------------------------
# Convention
# ---------------------------------------------------------------------------

# name -> (swap, sx, sy). A candidate maps map (mx, my) back to world as
# (a, b) = (my, mx) if swap else (mx, my); world (x, y) = (sx * a, sy * b).
CANDIDATES: dict[str, tuple[bool, int, int]] = {
    f"{'swap' if swap else 'keep'}_{'neg' if sx < 0 else 'pos'}_{'neg' if sy < 0 else 'pos'}":
        (swap, sx, sy)
    for swap in (False, True) for sx in (1, -1) for sy in (1, -1)
}
MAP_CONVENTION = "swap_neg_neg"                 # pinned by the Grounding_Check test
REFERENCE_ZONES = ("tutoriala", "bazaar")       # fast default-run zone, slow thorough zone

# A Floor_Face has a unit geometric normal with n_z >= cos 40 deg (glossary).
FLOOR_MIN_NZ = math.cos(math.radians(40.0))
# Wall edges are sampled at no more than this spacing for the Grounding_Check.
SAMPLE_SPACING = 1.0


def world_to_map(x: float, y: float, z: float) -> tuple[float, float, float]:
    """World (TER) coordinates -> EQ map coordinates: ``(-y, -x, z)``."""
    return (-y, -x, z)


def map_to_world(mx: float, my: float, mz: float) -> tuple[float, float, float]:
    """EQ map coordinates -> world: ``(-my, -mx, mz)`` (the same involution)."""
    return (-my, -mx, mz)


def candidate_to_world(name: str, mx: float, my: float) -> tuple[float, float]:
    """Map ``(mx, my)`` back to world XY under candidate ``name``."""
    swap, sx, sy = CANDIDATES[name]
    a, b = (my, mx) if swap else (mx, my)
    return (sx * a, sy * b)


def candidate_to_map(name: str, x: float, y: float) -> tuple[float, float]:
    """World XY -> map ``(mx, my)`` under candidate ``name`` (inverse of
    :func:`candidate_to_world`)."""
    swap, sx, sy = CANDIDATES[name]
    a, b = sx * x, sy * y
    return (b, a) if swap else (a, b)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

def _check_colour(r: int, g: int, b: int) -> None:
    for c in (r, g, b):
        if isinstance(c, bool) or not isinstance(c, int) or not 0 <= c <= 255:
            raise ValueError(f"colour channel {c!r} is not an int in 0-255")


def _check_finite(*vals: float) -> None:
    for v in vals:
        if not math.isfinite(v):
            raise ValueError(f"coordinate {v!r} is not finite")


@dataclass(frozen=True)
class MapLine:
    x1: float
    y1: float
    z1: float
    x2: float
    y2: float
    z2: float
    r: int
    g: int
    b: int

    def __post_init__(self) -> None:
        _check_finite(self.x1, self.y1, self.z1, self.x2, self.y2, self.z2)
        _check_colour(self.r, self.g, self.b)


@dataclass(frozen=True)
class MapLabel:
    x: float
    y: float
    z: float
    r: int
    g: int
    b: int
    size: int
    text: str

    def __post_init__(self) -> None:
        _check_finite(self.x, self.y, self.z)
        _check_colour(self.r, self.g, self.b)
        if self.size not in (1, 2, 3) or isinstance(self.size, bool):
            raise ValueError(f"label size {self.size!r} not in {{1, 2, 3}}")
        if not self.text:
            raise ValueError("label text is empty")
        # Printable ASCII only: no newline (it would split the record) and no
        # other control character (the parser strips surrounding whitespace).
        if any(not 32 <= ord(ch) <= 126 for ch in self.text):
            raise ValueError(f"label text {self.text!r} is not printable ASCII")


@dataclass
class MapLayer:
    index: int                    # 0 = <name>.txt, 1..3 = <name>_N.txt
    lines: list[MapLine] = field(default_factory=list)
    labels: list[MapLabel] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not 0 <= self.index <= 3:
            raise ValueError(f"layer index {self.index} not in 0-3")


_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass
class MapFile:
    name: str                     # Build_Name
    layers: list[MapLayer]        # 1..4, coordinates already in map convention

    def __post_init__(self) -> None:
        if not _SAFE_NAME.match(self.name) or self.name in (".", ".."):
            raise ValueError(f"map name {self.name!r} is not a plain file stem")
        if not 1 <= len(self.layers) <= 4:
            raise ValueError(f"{len(self.layers)} layers; expected 1-4")
        idx = [l.index for l in self.layers]
        if len(set(idx)) != len(idx) or 0 not in idx:
            raise ValueError(f"layer indices {idx} must be distinct and include 0")

    def filename(self, index: int) -> str:
        return f"{self.name}.txt" if index == 0 else f"{self.name}_{index}.txt"


@dataclass
class ParseResult:
    layer: MapLayer
    skipped: list[int]            # 1-based line numbers of malformed lines
    # 1-based line numbers of well-formed ``P`` records with empty text. Stock
    # kael.txt ships one; there is nothing to show, so it is dropped without
    # counting as malformed (Req 6.4: stock files parse with zero skipped).
    empty_labels: list[int] = field(default_factory=list)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)


@dataclass
class GroundingResult:
    medians_3d: dict[str, float]
    medians_xy: dict[str, float]
    chosen: str
    ratio: float                  # chosen / runner-up (3D)
    endpoints: int


# ---------------------------------------------------------------------------
# Format
# ---------------------------------------------------------------------------

def _fmt(v: float) -> str:
    s = f"{v:.4f}"
    return "0.0000" if s == "-0.0000" else s


def format_map_layer(layer: MapLayer) -> str:
    """The layer as map-file text: ``L`` records then ``P`` records, single
    spaces, 4 decimals, every line terminated by CR LF."""
    out: list[str] = []
    for l in layer.lines:
        out.append(
            f"L {_fmt(l.x1)}, {_fmt(l.y1)}, {_fmt(l.z1)}, "
            f"{_fmt(l.x2)}, {_fmt(l.y2)}, {_fmt(l.z2)}, {l.r}, {l.g}, {l.b}"
        )
    for p in layer.labels:
        out.append(
            f"P {_fmt(p.x)}, {_fmt(p.y)}, {_fmt(p.z)}, "
            f"{p.r}, {p.g}, {p.b}, {p.size}, {p.text.replace(' ', '_')}"
        )
    return "".join(s + "\r\n" for s in out)


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------

_FLOAT = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
_INT = re.compile(r"^[+-]?\d+$")


def _num(s: str) -> float:
    s = s.strip()
    if not _FLOAT.match(s):
        raise ValueError(f"not a number: {s!r}")
    return float(s)


def _int(s: str) -> int:
    s = s.strip()
    if not _INT.match(s):
        raise ValueError(f"not an integer: {s!r}")
    return int(s)


def _parse_record(line: str) -> MapLine | MapLabel | None:
    kind, rest = line[0], line[1:]
    if kind == "L":
        f = rest.split(",")
        if len(f) != 9:
            raise ValueError(f"L record has {len(f)} fields")
        return MapLine(*(_num(v) for v in f[:6]), *(_int(v) for v in f[6:]))
    if kind == "P":
        f = rest.split(",", 7)
        if len(f) != 8:
            raise ValueError(f"P record has {len(f)} fields")
        nums = [_num(v) for v in f[:3]] + [_int(v) for v in f[3:7]]
        text = f[7].strip()
        if not text:
            MapLabel(*nums, "_")    # still validate colour and size
            return None
        return MapLabel(*nums, text)
    raise ValueError(f"unknown record {kind!r}")


def parse_map_layer(text: str, index: int = 0) -> ParseResult:
    """Parse map-file text into a layer. Never raises on content: a malformed
    non-blank line is skipped and its 1-based number recorded. A well-formed
    label with empty text is dropped and listed in ``empty_labels``."""
    layer = MapLayer(index)
    skipped: list[int] = []
    empty: list[int] = []
    for n, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            rec = _parse_record(line)
        except ValueError:
            skipped.append(n)
            continue
        if rec is None:
            empty.append(n)
            continue
        (layer.lines if isinstance(rec, MapLine) else layer.labels).append(rec)
    return ParseResult(layer, skipped, empty)


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def write_map_files(mf: MapFile, maps_dir: Path, root: OutputRoot) -> list[Path]:
    """Write each layer of ``mf`` into ``maps_dir`` (confined to ``root``) as
    ASCII; return the written paths in layer order."""
    paths = []
    for layer in sorted(mf.layers, key=lambda l: l.index):
        data = format_map_layer(layer).encode("ascii")
        paths.append(root.write_bytes(str(Path(maps_dir) / mf.filename(layer.index)), data))
    return paths


# ---------------------------------------------------------------------------
# Grounding_Check
# ---------------------------------------------------------------------------

def _wall_samples(ter: TerFile, spacing: float = SAMPLE_SPACING) -> np.ndarray:
    """Points every <= ``spacing`` u along the edges of the TER's
    non-Floor_Faces (degenerate faces skipped)."""
    verts = np.array([(v.x, v.y, v.z) for v in ter.vertices], dtype=np.float64)
    faces = np.array([(p.v1, p.v2, p.v3) for p in ter.polygons], dtype=np.int64)
    if len(faces) == 0:
        return np.zeros((0, 3))
    tri = verts[faces]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(n, axis=1)
    ok = ln > 1e-12
    nz = np.zeros(len(faces))
    nz[ok] = n[ok, 2] / ln[ok]
    walls = tri[ok & (nz < FLOOR_MIN_NZ)]
    if len(walls) == 0:
        return np.zeros((0, 3))
    a = np.concatenate([walls[:, 0], walls[:, 1], walls[:, 2]])
    b = np.concatenate([walls[:, 1], walls[:, 2], walls[:, 0]])
    # Shared edges sample twice; harmless for a nearest-point query.
    counts = np.ceil(np.linalg.norm(b - a, axis=1) / spacing).astype(np.int64) + 1
    seg = np.repeat(np.arange(len(a)), counts)
    starts = np.cumsum(counts) - counts
    t = (np.arange(counts.sum()) - np.repeat(starts, counts)) / np.repeat(np.maximum(counts - 1, 1), counts)
    return a[seg] + (b[seg] - a[seg]) * t[:, None]


def ground_convention(ter: TerFile, layer: MapLayer) -> GroundingResult:
    """Score the 8 sign/swap candidates: median 3D (and XY) distance from the
    layer's line endpoints, converted back to world with each candidate and Z
    unchanged, to the nearest sampled non-Floor_Face edge of ``ter``."""
    from scipy.spatial import cKDTree

    walls = _wall_samples(ter)
    if len(walls) == 0:
        raise ValueError("TER has no non-Floor_Face to ground against")
    ends = [(l.x1, l.y1, l.z1) for l in layer.lines if (l.x1, l.y1, l.z1) != (l.x2, l.y2, l.z2)]
    ends += [(l.x2, l.y2, l.z2) for l in layer.lines if (l.x1, l.y1, l.z1) != (l.x2, l.y2, l.z2)]
    if not ends:
        raise ValueError("map layer has no non-degenerate line to ground with")
    e = np.array(ends, dtype=np.float64)
    tree3, tree2 = cKDTree(walls), cKDTree(walls[:, :2])

    med3: dict[str, float] = {}
    medxy: dict[str, float] = {}
    for name, (swap, sx, sy) in CANDIDATES.items():
        a, b = (e[:, 1], e[:, 0]) if swap else (e[:, 0], e[:, 1])
        pts = np.column_stack([sx * a, sy * b, e[:, 2]])
        med3[name] = float(np.median(tree3.query(pts)[0]))
        medxy[name] = float(np.median(tree2.query(pts[:, :2])[0]))

    best, runner = sorted(med3, key=med3.__getitem__)[:2]
    if med3[runner] > 0:
        ratio = med3[best] / med3[runner]
    else:
        ratio = 1.0  # two candidates tie at zero: no separation at all
    return GroundingResult(med3, medxy, best, ratio, len(ends))


def _read_ter(eqg_bytes: bytes, zone: str) -> TerFile:
    arc = PfsArchive.from_bytes(eqg_bytes)
    data = arc.get(f"ter_{zone}.ter") or arc.get(f"{zone}.ter")
    if data is None:
        ters = arc.get_by_extension("ter")
        if not ters:
            raise ValueError(f"no .ter in {zone}.eqg")
        data = ters[0].data
    return TerFile.from_bytes(data, name=zone)


def load_reference(eq_path: Path, zone: str) -> tuple[TerFile, MapLayer]:
    """Read a Reference_Zone's TER and stock map (layer 0) from the EQ
    install through read-only handles; nothing under ``eq_path`` is written.
    Raises ``FileNotFoundError`` when either file is missing."""
    eq_path = Path(eq_path)
    with open(eq_path / f"{zone}.eqg", "rb") as fh:
        eqg = fh.read()
    with open(eq_path / "maps" / f"{zone}.txt", "rb") as fh:
        text = fh.read().decode("latin-1")
    return _read_ter(eqg, zone), parse_map_layer(text).layer
