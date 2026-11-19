"""The quality meter (zone-generator-quality step 19, umbrella Requirement 24).

Every generate passes the hard gates (walkable, joined, RoF2 format) or is redrawn; this module
judges whether the layout is worth looking at. ``measure`` reads the room graph from the
Zone_Spec alone (no mesh, no build) and checks each metric against its inclusive band.

The graph: the rooms are the nodes; a corridor is an edge when both ``from_room`` and
``to_room`` name rooms of the spec and differ (stubs and an outdoor dungeon's Mouth tunnels
aren't edges). Parallel corridors between one pair count once.

The bands are data (``BAND_TABLE``), keyed by zone type, layout (``classic`` or ``graph``),
room count, verticality (quality requirements A1) and the resolved District count (districts
spec Req 5), calibrated by the sweep (``scripts/quality_sweep.py``) so the generator's
ordinary output passes and only its dull tail fails.

The meter never marks a report degraded: ``degraded`` and ``reason`` are set by the pipeline
(``quality_degraded``, ``quality_outside_bands_pinned``, ``edit_outside_bands``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .outline import _area

# Inclusive; ``None`` is an unbounded side.
Band = Tuple[Optional[float], Optional[float]]

UNBOUNDED: Band = (None, None)

# The metrics, in the order they are reported (and listed when out of band).
METRICS: Tuple[str, ...] = (
    "cyclomatic",
    "max_degree",
    "dead_end_ratio",
    "critical_path_ratio",
    "branching_factor",
    "elevation_range",
    "elevation_levels",
    "role_diversity",
    "room_type_diversity",
    "size_cv",
    "district_balance",
)

# Below this many rooms a zone is whatever it is: every band is unbounded (umbrella 24.4).
MIN_BOUNDED_ROOMS = 4

# ``spec_key``'s verticality when the caller doesn't know it: the plan's default.
DEFAULT_VERTICALITY = "moderate"

# Height of one elevation bin (u) for ``elevation_levels``.
LEVEL_BIN = 8.0

# The band table. Key: (zone_type, layout, verticality, districts), ``districts`` the resolved
# District count (1 without Districts); value: rows ``(n_lo, n_hi, {metric: band})`` for room
# counts n_lo..n_hi inclusive, the first matching row winning. A metric a row leaves out is
# unbounded.
BandRow = Tuple[int, int, Dict[str, Band]]

# Calibrated by ``scripts/quality_sweep.py`` (task 2, archive decision 4): each bound sits on
# the metric's dull side (low loops, roles, size spread or height; high dead ends, hub degree
# or a climax at the end of one long path) at the nearest round value failing at most 1% of
# the row's Draws (0.5% for the outdoor dungeon, whose Draw builds a World), so a key fails
# a few percent at most. ``room_type_diversity`` (capped by the theme's room types over N),
# ``branching_factor`` (repeats ``max_degree``) and ``district_balance`` (one District; districted rows below)
# are unbounded; so is ``critical_path_ratio`` on a graph layout, whose climax sits near the
# entrance by design. Elevation is bounded only off ``flat``. Classic dungeon and city share
# one layout generator, and verticality moves rooms up and down, not the graph, so a layout
# has one topology table and an elevation table per verticality.
_CLASSIC: List[BandRow] = [
    (4, 5, {"size_cv": (0.2, None)}),
    (6, 9, {"size_cv": (0.25, None), "dead_end_ratio": (None, 0.7)}),
    (10, 15, {"role_diversity": (4.0, None), "size_cv": (0.3, None),
              "dead_end_ratio": (None, 0.6), "critical_path_ratio": (None, 0.9)}),
    (16, 22, {"size_cv": (0.3, None), "dead_end_ratio": (None, 0.45),
              "critical_path_ratio": (None, 0.75)}),
    (23, 30, {"role_diversity": (5.0, None), "size_cv": (0.3, None),
              "dead_end_ratio": (None, 0.4), "critical_path_ratio": (None, 0.7)}),
]
_GRAPH: List[BandRow] = [
    (4, 5, {"size_cv": (0.15, None)}),
    (6, 9, {"role_diversity": (4.0, None), "size_cv": (0.2, None)}),
    (10, 15, {"size_cv": (0.3, None), "max_degree": (None, 5.0),
              "dead_end_ratio": (None, 0.65)}),
    (16, 22, {"size_cv": (0.3, None), "dead_end_ratio": (None, 0.55)}),
    (23, 30, {"cyclomatic": (1.0, None), "role_diversity": (5.0, None),
              "size_cv": (0.35, None), "max_degree": (None, 5.0),
              "dead_end_ratio": (None, 0.45)}),
]
_OUTDOOR_CLASSIC: List[BandRow] = [
    (4, 9, {}),
    (10, 15, {"critical_path_ratio": (None, 0.85)}),
    (16, 22, {"dead_end_ratio": (None, 0.5)}),
    (23, 30, {"size_cv": (0.3, None), "dead_end_ratio": (None, 0.45)}),
]
_OUTDOOR_GRAPH: List[BandRow] = [
    (4, 22, {}),
    (23, 30, {"size_cv": (0.3, None), "max_degree": (None, 5.0)}),
]
# Elevation by verticality, merged into the topology rows of the same room range.
_CLASSIC_ELEVATION: Dict[str, Dict[Tuple[int, int], Dict[str, Band]]] = {
    "moderate": {
        (16, 22): {"elevation_range": (8.0, None), "elevation_levels": (2.0, None)},
        (23, 30): {"elevation_range": (15.0, None), "elevation_levels": (3.0, None)},
    },
    "dramatic": {
        (6, 9): {"elevation_range": (1.0, None)},
        (10, 15): {"elevation_range": (10.0, None), "elevation_levels": (2.0, None)},
        (16, 22): {"elevation_range": (20.0, None), "elevation_levels": (3.0, None)},
        (23, 30): {"elevation_range": (31.0, None), "elevation_levels": (5.0, None)},
    },
}
_GRAPH_ELEVATION: Dict[str, Dict[Tuple[int, int], Dict[str, Band]]] = {
    "moderate": {
        (10, 15): {"elevation_range": (7.0, None), "elevation_levels": (2.0, None)},
        (16, 22): {"elevation_range": (97.0, None)},
        (23, 30): {"elevation_range": (102.0, None)},
    },
    "dramatic": {
        (6, 9): {"elevation_range": (18.0, None), "elevation_levels": (2.0, None)},
        (10, 15): {"elevation_range": (101.0, None), "elevation_levels": (3.0, None)},
        (16, 22): {"elevation_range": (102.0, None)},
        (23, 30): {"elevation_range": (116.0, None)},
    },
}


# Districted dungeons (districts spec Req 5, archive decision 11): by resolved District count
# k, then layout, calibrated by ``quality_sweep.py --districts`` (7200 Draws) on decision 4's
# rule; a bound is kept where it fails some Draw, and ``district_balance`` is bounded on its
# low side in every row. Districts drop the cross-District loops, so ``cyclomatic`` reaches 0
# in every row and stays unbounded. k is 2 for 8-13 rooms and 3 from 14; a k = 2 zone of 14+
# rooms is a partition that found only one cut (under 2% of Draws), bounded on balance only.
_DISTRICTED: Dict[int, Dict[str, List[BandRow]]] = {
    2: {
        "classic": [
            (8, 9, {"size_cv": (0.25, None), "dead_end_ratio": (None, 0.7),
                    "district_balance": (0.5, None)}),
            (10, 13, {"size_cv": (0.3, None), "dead_end_ratio": (None, 0.6),
                      "critical_path_ratio": (None, 0.85), "district_balance": (0.4, None)}),
            (14, 30, {"district_balance": (0.6, None)}),
        ],
        "graph": [
            (8, 9, {"role_diversity": (4.0, None), "size_cv": (0.2, None),
                    "district_balance": (0.5, None)}),
            (10, 13, {"dead_end_ratio": (None, 0.65), "district_balance": (0.4, None)}),
            (14, 30, {"district_balance": (0.6, None)}),
        ],
    },
    3: {
        "classic": [
            (14, 15, {"dead_end_ratio": (None, 0.5), "critical_path_ratio": (None, 0.75),
                      "district_balance": (0.35, None)}),
            (16, 22, {"size_cv": (0.3, None), "critical_path_ratio": (None, 0.7),
                      "district_balance": (0.4, None)}),
            (23, 30, {"role_diversity": (5.0, None), "size_cv": (0.3, None),
                      "dead_end_ratio": (None, 0.45), "critical_path_ratio": (None, 0.6),
                      "district_balance": (0.4, None)}),
        ],
        "graph": [
            (14, 15, {"district_balance": (0.35, None)}),
            (16, 22, {"size_cv": (0.3, None), "max_degree": (None, 4.0),
                      "dead_end_ratio": (None, 0.55), "district_balance": (0.4, None)}),
            (23, 30, {"role_diversity": (5.0, None), "size_cv": (0.35, None),
                      "dead_end_ratio": (None, 0.45), "district_balance": (0.4, None)}),
        ],
    },
}
_DISTRICTED_ELEVATION: Dict[int, Dict[str, Dict[str, Dict[Tuple[int, int], Dict[str, Band]]]]] = {
    2: {
        "classic": {
            "moderate": {(10, 13): {"elevation_range": (2.0, None)}},
            "dramatic": {(8, 9): {"elevation_range": (2.0, None)},
                         (10, 13): {"elevation_range": (12.0, None)}},
        },
        "graph": {
            "dramatic": {(10, 13): {"elevation_range": (40.0, None),
                                    "elevation_levels": (3.0, None)}},
        },
    },
    3: {
        "classic": {
            "moderate": {(16, 22): {"elevation_range": (10.0, None),
                                    "elevation_levels": (2.0, None)},
                         (23, 30): {"elevation_range": (16.0, None),
                                    "elevation_levels": (3.0, None)}},
            "dramatic": {(14, 15): {"elevation_range": (15.0, None)},
                         (16, 22): {"elevation_range": (25.0, None),
                                    "elevation_levels": (4.0, None)},
                         (23, 30): {"elevation_range": (33.0, None),
                                    "elevation_levels": (5.0, None)}},
        },
        "graph": {
            "moderate": {(14, 15): {"elevation_range": (16.0, None)},
                         (16, 22): {"elevation_range": (32.0, None)},
                         (23, 30): {"elevation_range": (102.0, None)}},
            "dramatic": {(23, 30): {"elevation_range": (114.0, None),
                                    "elevation_levels": (4.0, None)}},
        },
    },
}


def _merge(rows: List[BandRow],
           elevation: Optional[Dict[Tuple[int, int], Dict[str, Band]]] = None) -> List[BandRow]:
    elevation = elevation or {}
    return [(lo, hi, {**bands, **elevation.get((lo, hi), {})}) for lo, hi, bands in rows]


BAND_TABLE: Dict[Tuple[str, str, str, int], List[BandRow]] = {}
for _v in ("flat", "moderate", "dramatic"):
    for _zt in ("dungeon", "city"):
        BAND_TABLE[(_zt, "classic", _v, 1)] = _merge(_CLASSIC, _CLASSIC_ELEVATION.get(_v))
    BAND_TABLE[("dungeon", "graph", _v, 1)] = _merge(_GRAPH, _GRAPH_ELEVATION.get(_v))
    BAND_TABLE[("outdoor_dungeon", "classic", _v, 1)] = _merge(_OUTDOOR_CLASSIC)
    BAND_TABLE[("outdoor_dungeon", "graph", _v, 1)] = _merge(_OUTDOOR_GRAPH)
    for _k, _rows in _DISTRICTED.items():
        for _layout in ("classic", "graph"):
            BAND_TABLE[("dungeon", _layout, _v, _k)] = _merge(
                _rows[_layout], _DISTRICTED_ELEVATION[_k][_layout].get(_v))
del _v, _zt, _k, _rows, _layout


@dataclass
class OutOfBand:
    metric: str
    value: float
    lo: Optional[float]
    hi: Optional[float]

    def to_dict(self) -> dict:
        return {"metric": self.metric, "value": self.value, "lo": self.lo, "hi": self.hi}


@dataclass
class QualityReport:
    metrics: Dict[str, float]
    out_of_band: List[OutOfBand] = field(default_factory=list)
    passed: bool = True
    score: float = 0.0
    degraded: bool = False
    reason: str = ""


# ---------------------------------------------------------------------------
# Keys and bands
# ---------------------------------------------------------------------------

def spec_layout(spec) -> str:
    """The layout engine the spec was laid out with: ``spec.layout["engine"]`` for a graph
    layout, ``classic`` when the spec has no layout record (classic and wilderness)."""
    if spec.layout is None:
        return "classic"
    return str(spec.layout.get("engine") or "graph")


def spec_districts(spec) -> int:
    """The resolved District count: ``len(spec.districts)``, 1 when it has none."""
    return len(spec.districts) or 1


def spec_key(spec, verticality: Optional[str] = None) -> Tuple[str, str, int, str, int]:
    """``(zone_type, layout, n_rooms, verticality, districts)``. The spec records its zone
    type, layout, rooms and Districts; it does NOT record verticality (that lives on the
    plan), so the caller passes it in; ``None`` is the plan's default, ``moderate``."""
    return (spec.zone_type, spec_layout(spec), len(spec.rooms),
            verticality or DEFAULT_VERTICALITY, spec_districts(spec))


def bands_for(zone_type: str, layout: str, n_rooms: int,
              verticality: Optional[str], districts: int = 1) -> Dict[str, Band]:
    """Every metric's band for the key: the first ``BAND_TABLE`` row whose room range holds
    ``n_rooms``; unbounded where no row (or the row) says otherwise, and all unbounded below
    ``MIN_BOUNDED_ROOMS`` rooms."""
    bands = {m: UNBOUNDED for m in METRICS}
    if n_rooms < MIN_BOUNDED_ROOMS:
        return bands
    rows = BAND_TABLE.get((zone_type, layout, verticality or DEFAULT_VERTICALITY, districts),
                          [])
    for n_lo, n_hi, row in rows:
        if n_lo <= n_rooms <= n_hi:
            bands.update({m: tuple(b) for m, b in row.items() if m in bands})
            break
    return bands


def bands_for_spec(spec, verticality: Optional[str] = None) -> Dict[str, Band]:
    """``bands_for`` the spec's key, with umbrella 24.4's spec-dependent unbounded cases:
    ``district_balance`` when the zone has fewer than two Districts, ``room_type_diversity``
    when it has no Purpose (``dungeon_theme``)."""
    bands = bands_for(*spec_key(spec, verticality))
    if len({r.district for r in spec.rooms}) < 2:
        bands["district_balance"] = UNBOUNDED
    if not spec.dungeon_theme:
        bands["room_type_diversity"] = UNBOUNDED
    return bands


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _degrees(spec) -> Tuple[Dict[str, int], int]:
    """Each room's degree and the edge count E."""
    ids = {r.id for r in spec.rooms}
    edges = set()
    for c in spec.corridors:
        a, b = c.from_room, c.to_room
        if a in ids and b in ids and a != b:
            edges.add(frozenset((a, b)))
    deg = {r.id: 0 for r in spec.rooms}
    for e in edges:
        for rid in e:
            deg[rid] += 1
    return deg, len(edges)


def floor_area(room) -> float:
    """The Outline's area when the room has one, else width x depth."""
    o = room.outline
    if o is not None and o.cells:
        return sum(_area([o.verts[i] for i in c]) for c in o.cells)
    return room.width * room.depth


def _climax(rooms) -> object:
    """The first room whose role is ``climax``, else the deepest (earliest on a tie)."""
    for r in rooms:
        if r.role == "climax":
            return r
    return max(rooms, key=lambda r: r.graph_depth)   # max keeps the first of equals


def compute_metrics(spec) -> Dict[str, float]:
    """The eleven metrics (``METRICS``) of the spec, rounded to 6 places."""
    rooms = spec.rooms
    n = len(rooms)
    if n == 0:
        return {m: 0.0 for m in METRICS}
    deg, e = _degrees(spec)
    d = list(deg.values())
    hubs = [x for x in d if x >= 2]
    zs = [r.floor_z for r in rooms]
    areas = [floor_area(r) for r in rooms]
    mean = sum(areas) / n
    sd = math.sqrt(sum((a - mean) ** 2 for a in areas) / n)
    counts: Dict[int, int] = {}
    for r in rooms:
        counts[r.district] = counts.get(r.district, 0) + 1
    out = {
        "cyclomatic": e - n + 1,
        "max_degree": max(d),
        "dead_end_ratio": sum(1 for x in d if x == 1) / n,
        "critical_path_ratio": _climax(rooms).graph_depth / (n - 1) if n > 1 else 0.0,
        "branching_factor": sum(hubs) / len(hubs) if hubs else 0.0,
        "elevation_range": max(zs) - min(zs),
        "elevation_levels": len({round(z / LEVEL_BIN) for z in zs}),
        "role_diversity": len({r.role for r in rooms if r.role}),
        "room_type_diversity": len({r.semantic_type for r in rooms if r.semantic_type}) / n,
        "size_cv": sd / mean if mean > 0 else 0.0,
        "district_balance": min(counts.values()) / max(counts.values()),
    }
    return {m: round(float(out[m]), 6) for m in METRICS}


# ---------------------------------------------------------------------------
# Judging
# ---------------------------------------------------------------------------

def _distance(value: float, band: Band) -> float:
    """How far ``value`` lies outside ``band`` over the band's normaliser (0 inside)."""
    lo, hi = band
    if lo is not None and value < lo:
        gap, bound = lo - value, lo
    elif hi is not None and value > hi:
        gap, bound = value - hi, hi
    else:
        return 0.0
    width = (hi - lo) if (lo is not None and hi is not None) else abs(bound)
    # At least the smallest float: a subnormal gap over the width can underflow to 0, which
    # would read an out-of-band value as a pass.
    return max(gap / max(1.0, width), math.ulp(0.0))


def evaluate(metrics: Dict[str, float], bands: Dict[str, Band]) -> QualityReport:
    """Judge ``metrics`` against ``bands`` (a metric with no band is unbounded): pass when
    every metric is inside its inclusive band; the out-of-band list in ``METRICS`` order
    (then any extra metric in its dict order); the score is the sum of the normalised
    distances, 0 exactly on a pass."""
    order = [m for m in METRICS if m in metrics] + [m for m in metrics if m not in METRICS]
    oob: List[OutOfBand] = []
    score = 0.0
    for m in order:
        band = bands.get(m, UNBOUNDED)
        dist = _distance(metrics[m], band)
        if dist > 0:
            oob.append(OutOfBand(m, metrics[m], band[0], band[1]))
            score += dist
    return QualityReport(metrics=dict(metrics), out_of_band=oob, passed=not oob, score=score)


def measure(spec, bands: Optional[Dict[str, Band]] = None,
            verticality: Optional[str] = None) -> QualityReport:
    """The spec's QualityReport. ``bands`` None: ``bands_for_spec(spec, verticality)``
    (the spec doesn't record verticality; the pipeline passes the plan's). Given bands are
    used as they are."""
    if bands is None:
        bands = bands_for_spec(spec, verticality)
    return evaluate(compute_metrics(spec), bands)


def quality_summary(report: QualityReport) -> dict:
    """The Quality_Block: ``{degraded, reason, score, metrics, out_of_band}`` (reason null
    when empty), the one shape the sidecar and every response carry."""
    return {
        "degraded": bool(report.degraded),
        "reason": report.reason or None,
        "score": report.score,
        "metrics": dict(report.metrics),
        "out_of_band": [o.to_dict() for o in report.out_of_band],
    }
