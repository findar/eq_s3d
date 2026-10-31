"""
tests/test_eqmap.py
-------------------
EQ map core (M2 task 1): the pinned map convention (Property 8), the
Grounding_Check on synthetic meshes (Property 9) and on stock RoF2 zones, the
format round-trip (Property 10), parser tolerance (Property 11) and the stock
``maps/*.txt`` parse. Map layers from the outline (M2 task 6): the files
mirror the outline (Property 12) and lie on the walkable floor (Property 13).

The stock-zone tests read the install named by ``EQ_PATH``
(``core.env.env_value``) and skip when it is unset or the zone's files are
missing. This module's strategies live here, not in ``tests/strategies.py``.
"""

from __future__ import annotations

import math
import os
import tempfile
from pathlib import Path

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from analyzer.traverse import AgentModel, build_walk_surface, flood_reachable, seed_face_for
from core.env import env_value
from core.paths import OutputRoot
from core.ter import Polygon, TerFile, Vertex
from generators.eqmap import (
    BAND_COLOURS,
    BOSS_COLOUR,
    CANDIDATES,
    ENTRANCE_COLOUR,
    LABEL_SIZE,
    MAP_CONVENTION,
    REFERENCE_ZONES,
    MapFile,
    MapLabel,
    MapLayer,
    MapLine,
    build_map_file,
    candidate_to_map,
    candidate_to_world,
    format_map_layer,
    ground_convention,
    load_reference,
    map_to_world,
    parse_map_layer,
    world_to_map,
    write_map_files,
)
from generators.mapgeom import DepthBand, OutlineSet, Polyline, extract_outline, floor_faces
from generators.zone_spec import RoomSpec, ZoneSpec
from tests.pbt_helpers import build_settings, scaled
from tests.strategies import box_zone_types, room_counts_wide, seeds, verticality_all
from tests.test_properties_mapgeom import BoxBuild

TOL = 0.00005 + 1e-9          # 4 dp rounding plus float re-read


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

coords = st.floats(-30000, 30000, allow_nan=False, allow_infinity=False)
colours = st.integers(0, 255)
# Printable ASCII with commas and spaces, non-empty after stripping.
label_texts = st.text(st.characters(min_codepoint=32, max_codepoint=126),
                      min_size=1, max_size=24).filter(lambda s: s.strip())


@st.composite
def map_layers(draw, rounded: bool = False):
    c = coords.map(lambda v: round(v, 4)) if rounded else coords
    lines = draw(st.lists(st.builds(MapLine, c, c, c, c, c, c, colours, colours, colours),
                          max_size=12))
    labels = draw(st.lists(st.builds(MapLabel, c, c, c, colours, colours, colours,
                                     st.sampled_from([1, 2, 3]), label_texts),
                           max_size=6))
    return MapLayer(0, lines, labels)


GARBAGE = (
    "Q 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 0, 0, 0",              # unknown record letter
    "L 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 0, 0",                 # wrong field count
    "L 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 0, 0, 0, 0",
    "P 1.0, 2.0, 3.0, 0, 0, 0, 2",
    "L 1.0, two, 3.0, 4.0, 5.0, 6.0, 0, 0, 0",              # non-numeric field
    "P 1.0, 2.0, 3.0, 0, x, 0, 2, Label",
    "L 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 256, 0, 0",            # colour 256
    "P 1.0, 2.0, 3.0, 0, 0, 256, 2, Label",
    "P 1.0, 2.0, 3.0, 0, 0, 0, 4, Label",                   # size 4
    "P 1.0, 2.0, 3.0, 0, 0, 0, 4,   ",                      # empty label, bad size
)
# An empty label with otherwise valid fields is NOT garbage: stock kael.txt
# ships one (Req 6.4), so it is dropped into ParseResult.empty_labels instead.


def garbage_lines():
    return st.sampled_from(GARBAGE)


@st.composite
def asymmetric_wall_meshes(draw):
    """20-200 vertical wall quads in a box with no mirror or swap symmetry.

    The box sits in one quadrant with its |x| and |y| ranges disjoint, so each
    of the 7 non-identity sign/swap candidates moves it at least ``gap`` u
    away from itself."""
    size, gap = 300.0, 400.0
    ax = draw(st.floats(100, 3000))
    ay = draw(st.sampled_from([ax + size + gap, max(0.0, ax - size - gap)]))
    if ay < 100:
        ay = ax + size + gap
    qx, qy = draw(st.sampled_from([1, -1])), draw(st.sampled_from([1, -1]))
    n = draw(st.integers(20, 200))
    ter = TerFile(name="synthetic")
    edges = []
    for _ in range(n):
        x0 = qx * (ax + draw(st.floats(0, size)))
        y0 = qy * (ay + draw(st.floats(0, size)))
        x1 = qx * (ax + draw(st.floats(0, size)))
        y1 = qy * (ay + draw(st.floats(0, size)))
        if abs(x1 - x0) + abs(y1 - y0) < 1:
            x1 += qx * 2
        z0 = draw(st.floats(-50, 50))
        z1 = z0 + draw(st.floats(5, 40))
        i = len(ter.vertices)
        ter.vertices += [Vertex(x0, y0, z0), Vertex(x1, y1, z0),
                         Vertex(x1, y1, z1), Vertex(x0, y0, z1)]
        ter.polygons += [Polygon(i, i + 1, i + 2), Polygon(i, i + 2, i + 3)]
        edges += [((x0, y0, z0), (x1, y1, z0)), ((x0, y0, z1), (x1, y1, z1))]
    return ter, edges


def _layers_close(got: MapLayer, want: MapLayer) -> None:
    assert len(got.lines) == len(want.lines)
    assert len(got.labels) == len(want.labels)
    for g, w in zip(got.lines, want.lines):
        for a in ("x1", "y1", "z1", "x2", "y2", "z2"):
            assert abs(getattr(g, a) - getattr(w, a)) <= TOL, (a, g, w)
        assert (g.r, g.g, g.b) == (w.r, w.g, w.b)
    for g, w in zip(got.labels, want.labels):
        for a in ("x", "y", "z"):
            assert abs(getattr(g, a) - getattr(w, a)) <= TOL, (a, g, w)
        assert (g.r, g.g, g.b, g.size) == (w.r, w.g, w.b, w.size)
        assert g.text == w.text.replace(" ", "_")


# ---------------------------------------------------------------------------
# Property 8: convention
# ---------------------------------------------------------------------------

finite = st.floats(allow_nan=False, allow_infinity=False)


@settings(max_examples=scaled(200))
@given(finite, finite, finite)
def test_convention_round_trip(x, y, z):
    """Feature: zone-generator-m2-true-layout-artifacts, Property 8: Map
    coordinate convention (umbrella P24). Requirements 4.3, 4.4."""
    mx, my, mz = world_to_map(x, y, z)
    assert (mx, my) == candidate_to_map(MAP_CONVENTION, x, y)
    assert mz == z
    assert map_to_world(mx, my, mz) == (x, y, z)
    # With |x| != |y|, both non-zero, every other candidate maps differently,
    # so a missed negate or swap fails. (x = -y would let keep_pos_neg alias.)
    if x != 0 and y != 0 and abs(x) != abs(y):
        for name in CANDIDATES:
            if name != MAP_CONVENTION:
                assert candidate_to_map(name, x, y) != (mx, my), name


def test_convention_is_negate_and_swap():
    assert world_to_map(3.0, 5.0, 7.0) == (-5.0, -3.0, 7.0)
    assert map_to_world(-5.0, -3.0, 7.0) == (3.0, 5.0, 7.0)
    assert len(CANDIDATES) == 8
    for name in CANDIDATES:
        assert candidate_to_world(name, *candidate_to_map(name, 3.0, -5.0)) == (3.0, -5.0)


# ---------------------------------------------------------------------------
# Property 9: the Grounding_Check recovers a known candidate
# ---------------------------------------------------------------------------

@settings(max_examples=scaled(100), deadline=None)
@given(st.sampled_from(sorted(CANDIDATES)), asymmetric_wall_meshes())
def test_grounding_recovers_candidate(name, mesh):
    """Feature: zone-generator-m2-true-layout-artifacts, Property 9: The
    Grounding_Check recovers a known convention (M2-P6). Requirements 4.1, 4.2."""
    ter, edges = mesh
    lines = []
    for (x1, y1, z1), (x2, y2, z2) in edges:
        mx1, my1 = candidate_to_map(name, x1, y1)
        mx2, my2 = candidate_to_map(name, x2, y2)
        lines.append(MapLine(mx1, my1, z1, mx2, my2, z2, 0, 0, 0))
    r = ground_convention(ter, MapLayer(0, lines))
    assert r.chosen == name
    assert r.medians_3d[name] <= 0.5
    assert r.ratio <= 0.25
    assert r.endpoints == 2 * len(lines)


# ---------------------------------------------------------------------------
# Grounding_Check against stock RoF2 zones
# ---------------------------------------------------------------------------

def _install_or_skip(zone: str | None = None) -> Path:
    eq = env_value("EQ_PATH")
    if not eq:
        pytest.skip("EQ_PATH is not set (no EQ install to read)")
    eq_path = Path(eq)
    if zone is not None:
        for p in (eq_path / f"{zone}.eqg", eq_path / "maps" / f"{zone}.txt"):
            if not p.is_file():
                pytest.skip(f"reference zone file missing: {p}")
    elif not (eq_path / "maps").is_dir():
        pytest.skip(f"no maps/ folder under {eq_path}")
    return eq_path


def _snapshot(eq_path: Path) -> dict:
    """Names, sizes and mtimes of every entry in the install root and maps/."""
    snap = {}
    for d in (eq_path, eq_path / "maps"):
        with os.scandir(d) as it:
            for e in it:
                s = e.stat(follow_symlinks=False)
                snap[e.path] = (s.st_size, s.st_mtime_ns)
    return snap


def _check_grounding(zone: str) -> None:
    eq_path = _install_or_skip(zone)
    before = _snapshot(eq_path)
    ter, layer = load_reference(eq_path, zone)
    r = ground_convention(ter, layer)
    assert _snapshot(eq_path) == before, "the EQ install changed"
    meds = ", ".join(f"{k} {v:.2f}" for k, v in sorted(r.medians_3d.items(), key=lambda kv: kv[1]))
    assert r.chosen == MAP_CONVENTION, meds
    assert r.medians_3d[r.chosen] <= 5.0, meds
    assert r.ratio <= 0.25, meds


def test_grounding_reference():
    """Grounding_Check on the fast Reference_Zone (Req 4.1, 4.2, 4.5, 4.6)."""
    _check_grounding(REFERENCE_ZONES[0])


@pytest.mark.slow
def test_grounding_bazaar():
    """Grounding_Check on bazaar, the thorough Reference_Zone."""
    _check_grounding(REFERENCE_ZONES[1])


# ---------------------------------------------------------------------------
# Property 10: format round-trip
# ---------------------------------------------------------------------------

_STRICT_L = r"L (-?\d+\.\d{4}), (-?\d+\.\d{4}), (-?\d+\.\d{4}), (-?\d+\.\d{4}), " \
            r"(-?\d+\.\d{4}), (-?\d+\.\d{4}), (\d{1,3}), (\d{1,3}), (\d{1,3})"
_STRICT_P = r"P (-?\d+\.\d{4}), (-?\d+\.\d{4}), (-?\d+\.\d{4}), (\d{1,3}), (\d{1,3}), " \
            r"(\d{1,3}), ([123]), ([!-~]+)"


@settings(max_examples=scaled(200))
@given(map_layers())
def test_format_round_trip(layer):
    """Feature: zone-generator-m2-true-layout-artifacts, Property 10: Map
    format round-trip (umbrella P23). Requirements 5.2, 6.2."""
    import re

    text = format_map_layer(layer)
    assert text.isascii()
    assert text == "" or text.endswith("\r\n")
    rows = text.split("\r\n")[:-1] if text else []
    assert len(rows) == len(layer.lines) + len(layer.labels)
    for row in rows:
        assert "\n" not in row and "\r" not in row
        m = re.fullmatch(_STRICT_L, row) or re.fullmatch(_STRICT_P, row)
        assert m, row
        assert "-0.0000" not in row
        assert all(int(g) <= 255 for g in m.groups()[6 if row[0] == "L" else 3:][:3])
    got = parse_map_layer(text)
    assert got.skipped == []
    _layers_close(got.layer, layer)


def test_reader_vectors():
    """Stock-spelled records parse to their fields and re-emit equal values."""
    text = ("L 2881.0, -2022.0, -295.0, 2885.0, -2027.0, -295.0, 128, 255, 0\r\n"
            "P 5531.2642, -168.7061, -299.5485, 128, 255, 0, 2, Gargoyle_Island\r\n")
    r = parse_map_layer(text)
    assert r.skipped == []
    assert r.layer.lines == [MapLine(2881.0, -2022.0, -295.0, 2885.0, -2027.0, -295.0, 128, 255, 0)]
    assert r.layer.labels == [MapLabel(5531.2642, -168.7061, -299.5485, 128, 255, 0, 2,
                                       "Gargoyle_Island")]
    again = parse_map_layer(format_map_layer(r.layer))
    assert again.layer == r.layer


def test_negative_zero_and_labels():
    layer = MapLayer(0, [MapLine(-0.0, -0.00001, 0.0, 1.0, 2.0, 3.0, 0, 0, 0)],
                     [MapLabel(0.0, 0.0, 0.0, 0, 0, 0, 2, "Boss, the big one")])
    text = format_map_layer(layer)
    assert text == ("L 0.0000, 0.0000, 0.0000, 1.0000, 2.0000, 3.0000, 0, 0, 0\r\n"
                    "P 0.0000, 0.0000, 0.0000, 0, 0, 0, 2, Boss,_the_big_one\r\n")
    assert parse_map_layer(text).layer.labels[0].text == "Boss,_the_big_one"


@pytest.mark.parametrize("kw", [
    dict(r=256), dict(g=-1), dict(size=4), dict(text=""), dict(text="café"),
    dict(text="two\nlines"), dict(x=float("nan")),
])
def test_label_validation(kw):
    base = dict(x=0.0, y=0.0, z=0.0, r=0, g=0, b=0, size=2, text="Entrance")
    with pytest.raises(ValueError):
        MapLabel(**{**base, **kw})


def test_map_file_validation():
    with pytest.raises(ValueError):
        MapFile("z", [])
    with pytest.raises(ValueError):
        MapFile("z", [MapLayer(1)])
    with pytest.raises(ValueError):
        MapFile("z", [MapLayer(0), MapLayer(0)])
    with pytest.raises(ValueError):
        MapFile("../z", [MapLayer(0)])
    with pytest.raises(ValueError):
        MapLayer(4)


# ---------------------------------------------------------------------------
# Property 11: parser tolerance
# ---------------------------------------------------------------------------

def _stock_num(v: float, draw) -> str:
    if v == int(v) and draw(st.booleans()):
        return str(int(v))
    return f"{v:.4f}"


@settings(max_examples=scaled(200))
@given(map_layers(rounded=True), st.data())
def test_parser_tolerance(layer, data):
    """Feature: zone-generator-m2-true-layout-artifacts, Property 11: The parser
    tolerates stock spelling and skips only garbage (M2-P7). Requirements 6.1, 6.3."""
    draw = data.draw
    sep = lambda: "," + " " * draw(st.integers(0, 2))  # noqa: E731
    records = []
    for l in layer.lines:
        nums = [_stock_num(v, draw) for v in (l.x1, l.y1, l.z1, l.x2, l.y2, l.z2)]
        fields = nums + [str(l.r), str(l.g), str(l.b)]
        records.append("L " + "".join(f + sep() for f in fields[:-1]) + fields[-1])
    for p in layer.labels:
        fields = [_stock_num(v, draw) for v in (p.x, p.y, p.z)] + \
                 [str(p.r), str(p.g), str(p.b), str(p.size)]
        records.append("P " + "".join(f + sep() for f in fields) +
                       " " * draw(st.integers(0, 2)) + p.text.replace(" ", "_"))
    # Garbage at random positions, blank lines between records.
    out, bad = [], []
    for rec in records + [None]:
        for _ in range(draw(st.integers(0, 1))):
            out.append("")
        if draw(st.integers(0, 3)) == 0:
            out.append(draw(garbage_lines()))
            bad.append(len(out))
        if rec is not None:
            out.append(rec)
    eol = draw(st.sampled_from(["\r\n", "\n"]))
    got = parse_map_layer(eol.join(out) + eol)
    assert got.skipped == bad
    assert got.skipped_count == len(bad)
    _layers_close(got.layer, layer)


@pytest.mark.parametrize("line", GARBAGE)
def test_each_garbage_kind_is_skipped(line):
    r = parse_map_layer(f"\r\n{line}\r\nL 0, 0, 0, 1, 1, 1, 0, 0, 0\r\n")
    assert r.skipped == [2]
    assert len(r.layer.lines) == 1


def test_empty_label_is_dropped_not_skipped():
    r = parse_map_layer("P 1.0, 2.0, 3.0, 0, 0, 0, 3,  \r\nP 1, 2, 3, 0, 0, 0, 2, A\r\n")
    assert r.skipped == [] and r.empty_labels == [1]
    assert [l.text for l in r.layer.labels] == ["A"]


@pytest.mark.slow
def test_stock_maps_parse():
    """Every stock maps/*.txt parses with zero skipped lines (Req 6.4)."""
    eq_path = _install_or_skip()
    files = sorted((eq_path / "maps").glob("*.txt"))
    if not files:
        pytest.skip(f"no maps/*.txt under {eq_path}")
    records = 0
    for f in files:
        r = parse_map_layer(f.read_bytes().decode("latin-1"))
        assert r.skipped == [], (f.name, r.skipped[:5])
        records += len(r.layer.lines) + len(r.layer.labels)
    assert records > 0


# ---------------------------------------------------------------------------
# write_map_files
# ---------------------------------------------------------------------------

def test_write_map_files(tmp_path):
    root = OutputRoot(tmp_path)
    l0 = MapLayer(0, [MapLine(1, 2, 3, 4, 5, 6, 0, 0, 0)], [MapLabel(0, 0, 0, 0, 160, 0, 2, "Entrance")])
    l2 = MapLayer(2, [MapLine(1, 2, 3, 4, 5, 6, 0, 0, 240)])
    paths = write_map_files(MapFile("gen_1_abc", [l2, l0]), tmp_path / "v1" / "maps", root)
    assert [p.name for p in paths] == ["gen_1_abc.txt", "gen_1_abc_2.txt"]
    assert paths[0].read_bytes() == format_map_layer(l0).encode("ascii")
    assert paths[1].read_bytes() == format_map_layer(l2).encode("ascii")
    assert sorted(p.name for p in (tmp_path / "v1" / "maps").iterdir()) == \
        ["gen_1_abc.txt", "gen_1_abc_2.txt"]


# ---------------------------------------------------------------------------
# Build (Properties 12, 13)
# ---------------------------------------------------------------------------

BAND_STEP = 100.0             # synthetic band height


@st.composite
def synthetic_outlines(draw):
    """``(outline, spec)``: 1-4 depth bands stacked BAND_STEP apart with the
    Main_Band anywhere among them, 0-6 polylines per band on a 0.5 u grid
    inside the band's height range, and rooms (one entrance, 0-3 climax, some
    standard) with floors anywhere in the bands' range."""
    k = draw(st.integers(1, 4))
    main = draw(st.integers(0, k - 1))
    order = [main] + [i for i in range(k) if i != main]    # band index -> slab
    index = {slab: order.index(slab) for slab in range(k)}
    bands = []
    for slab in range(k):
        lo = -math.inf if slab == 0 else slab * BAND_STEP
        hi = math.inf if slab == k - 1 else (slab + 1) * BAND_STEP
        role = "main" if slab == main else ("above" if slab > main else "below")
        bands.append(DepthBand(index[slab], lo, hi, slab * BAND_STEP + 50.0, role, slab - main))
    grid = st.integers(-2000, 2000).map(lambda v: v / 2)
    polylines = []
    for slab in range(k):
        zs = st.integers(int(slab * BAND_STEP) * 2 + 1,
                         int((slab + 1) * BAND_STEP) * 2 - 1).map(lambda v: v / 2)
        for _ in range(draw(st.integers(0, 6))):
            pts = [(draw(grid), draw(grid), draw(zs))]
            for _ in range(draw(st.integers(1, 6))):
                q = (draw(grid), draw(grid), draw(zs))
                if q != pts[-1]:
                    pts.append(q)
            if len(pts) >= 2:
                polylines.append(Polyline(tuple(pts), draw(st.sampled_from(["wall", "ledge"])),
                                          index[slab]))
    roles = ["entrance"] + ["climax"] * draw(st.integers(0, 3)) + \
        ["standard"] * draw(st.integers(0, 3))
    rooms = [RoomSpec(f"room_{i}", draw(grid), draw(grid),
                      floor_z=float(draw(st.integers(0, int(k * BAND_STEP) - 1))), role=r)
             for i, r in enumerate(draw(st.permutations(roles)))]
    outline = OutlineSet(tuple(polylines), tuple(sorted(bands, key=lambda b: b.index)),
                         (0, 0, 0, 0, 0, 0), 0, True)
    return outline, ZoneSpec(name="synthetic", rooms=rooms)


@st.composite
def box_builds(draw) -> BoxBuild:
    return BoxBuild(draw(box_zone_types), draw(room_counts_wide), draw(seeds),
                    draw(verticality_all))


def _close(a, b) -> bool:
    return all(abs(u - v) <= TOL for u, v in zip(a, b))


def _check_mirror(outline: OutlineSet, spec, name: str, tmp: Path) -> None:
    mf = build_map_file(outline, spec, name)
    assert mf == build_map_file(outline, spec, name)
    paths = write_map_files(mf, tmp / "maps", OutputRoot(tmp))
    by_band = sorted(outline.bands, key=lambda b: b.index)
    want = [f"{name}.txt"] + [f"{name}_{b.index}.txt" for b in by_band[1:]]
    assert [p.name for p in paths] == want
    assert sorted(p.name for p in (tmp / "maps").iterdir()) == sorted(want)
    # Layer order: the other bands by ascending median floor Z.
    assert [b.median_z for b in by_band[1:]] == sorted(b.median_z for b in by_band[1:])

    colours = {}
    labels = []
    for band, path in zip(by_band, paths):
        res = parse_map_layer(path.read_bytes().decode("ascii"), band.index)
        assert res.skipped == [] and res.empty_labels == []
        segs = [(p, q) for pl in outline.polylines if pl.band == band.index
                for p, q in zip(pl.points, pl.points[1:])]
        assert len(res.layer.lines) == len(segs)
        for l, (p, q) in zip(res.layer.lines, segs):
            a, b = (l.x1, l.y1, l.z1), (l.x2, l.y2, l.z2)
            assert a != b, "degenerate L record"
            assert _close(map_to_world(*a), p) and _close(map_to_world(*b), q)
            assert (l.r, l.g, l.b) == BAND_COLOURS[band.offset]
        colours[band.index] = BAND_COLOURS[band.offset]
        labels += [(band, p) for p in res.layer.labels]
    assert colours[0] == (0, 0, 0)
    others = [c for i, c in colours.items() if i != 0]
    assert (0, 0, 0) not in others and len(set(others)) == len(others)

    entrance = [r for r in spec.rooms if r.role == "entrance"]
    climax = [r for r in spec.rooms if r.role == "climax"]
    assert len(entrance) == 1
    assert sorted(p.text for _, p in labels) == sorted(["Entrance"] + ["Boss"] * len(climax))
    for band, p in labels:
        assert p.size == LABEL_SIZE == 2
        assert (p.r, p.g, p.b) == (ENTRANCE_COLOUR if p.text == "Entrance" else BOSS_COLOUR)
        world = map_to_world(p.x, p.y, p.z)
        rooms = entrance if p.text == "Entrance" else climax
        room = next(r for r in rooms
                    if _close(world, (r.center_x, r.center_y, r.floor_z + 2)))
        holder = next((b for b in by_band if b.contains(room.floor_z)), by_band[0])
        assert band.index == holder.index


@settings(max_examples=scaled(100), deadline=None,
          suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
@given(synthetic_outlines())
def test_map_files_mirror_outline(case):
    """Feature: zone-generator-m2-true-layout-artifacts, Property 12: The map
    files mirror the outline (M2-P8).

    For synthetic outlines with 1-4 bands: the written files are
    ``<name>.txt`` for the Main_Band and ``<name>_1.txt`` .. ``_k.txt`` for the
    other bands in ascending median floor Z, and no others; each file holds one
    ``L`` per consecutive polyline point pair, none degenerate, mapping back to
    the segment within 0.00005, in the band's colour (black for the Main_Band,
    the others distinct and non-black); one ``Entrance`` label and one ``Boss``
    per climax room, size 2, in the file of the band holding the room's floor.
    The box-build half is ``test_map_files_mirror_outline_builds``.

    Validates: Requirements 5.1, 5.3, 5.5, 5.7
    """
    outline, spec = case
    with tempfile.TemporaryDirectory() as d:
        _check_mirror(outline, spec, "gen_1_abc", Path(d))


@pytest.mark.slow
@build_settings(10)
@given(world=box_builds())
def test_map_files_mirror_outline_builds(world):
    """Feature: zone-generator-m2-true-layout-artifacts, Property 12: The map
    files mirror the outline (M2-P8), on 10 box builds.

    Validates: Requirements 5.1, 5.3, 5.5, 5.7
    """
    outline = extract_outline(world.ter, world.safe_point)
    with tempfile.TemporaryDirectory() as d:
        _check_mirror(outline, world.spec, "gen_1_abc", Path(d))


@pytest.mark.slow
@build_settings(15)
@given(world=box_builds())
def test_map_records_on_floor(world):
    """Feature: zone-generator-m2-true-layout-artifacts, Property 13: Map
    records lie on the walkable floor (umbrella P25).

    For box builds: every ``L`` endpoint mapped back to world lies inside the
    Floor_Region's XY bounding box plus 0.5 u with Z in
    ``[min floor Z, max floor Z + 6]``; every ``P`` label lies inside its
    room's footprint with Z in ``[floor_z, floor_z + 6]``.

    Validates: Requirements 5.4, 5.6
    """
    ter, spec = world.ter, world.spec
    mf = build_map_file(extract_outline(ter, world.safe_point), spec, "gen_1_abc")
    # The Floor_Region, independently of mapgeom: reachable Floor_Faces.
    surf = build_walk_surface(ter, AgentModel())
    reach = np.zeros(len(ter.polygons), bool)
    reach[list(flood_reachable(surf, seed_face_for(surf, world.safe_point)))] = True
    region = floor_faces(ter) & reach
    V = np.array([(v.x, v.y, v.z) for v in ter.vertices])
    F = np.array([(p.v1, p.v2, p.v3) for p in ter.polygons])
    pts = V[F[region]].reshape(-1, 3)
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    for layer in mf.layers:
        for l in layer.lines:
            for end in ((l.x1, l.y1, l.z1), (l.x2, l.y2, l.z2)):
                x, y, z = map_to_world(*end)
                assert lo[0] - 0.5 <= x <= hi[0] + 0.5 and lo[1] - 0.5 <= y <= hi[1] + 0.5, end
                assert lo[2] - 1e-6 <= z <= hi[2] + 6, end
        for p in layer.labels:
            x, y, z = map_to_world(p.x, p.y, p.z)
            role = "entrance" if p.text == "Entrance" else "climax"
            assert any(r.role == role
                       and abs(x - r.center_x) <= r.width / 2
                       and abs(y - r.center_y) <= r.depth / 2
                       and r.floor_z <= z <= r.floor_z + 6 for r in spec.rooms), p


def test_build_labels_and_bytes():
    """One ``Entrance`` and one ``Boss`` per climax room, all size 2, and no
    other label; equal input gives equal bytes with no ``-0`` in them."""
    rooms = [RoomSpec("a", 0.0, -0.0, floor_z=-0.0, role="entrance"),
             RoomSpec("b", 300.0, 0.0, role="climax"),
             RoomSpec("c", 600.0, 0.0, role="climax"),
             RoomSpec("d", 900.0, 0.0, role="hub"),
             RoomSpec("e", 1200.0, 0.0, role="deadend")]
    spec = ZoneSpec(name="labels", rooms=rooms)
    band = DepthBand(0, -math.inf, math.inf, 0.0, "main", 0)
    outline = OutlineSet((Polyline(((0.0, 0.0, 0.0), (0.0, 10.0, -0.0)), "wall", 0),),
                         (band,), (0, 0, 0, 0, 0, 0), 0, True)
    mf = build_map_file(outline, spec, "labels")
    (layer,) = mf.layers
    assert sorted(p.text for p in layer.labels) == ["Boss", "Boss", "Entrance"]
    assert {p.size for p in layer.labels} == {LABEL_SIZE}
    text = format_map_layer(layer)
    assert text == format_map_layer(build_map_file(outline, spec, "labels").layers[0])
    assert "-0.0000" not in text
    assert text.splitlines()[0] == "L 0.0000, 0.0000, 0.0000, -10.0000, 0.0000, 0.0000, 0, 0, 0"
