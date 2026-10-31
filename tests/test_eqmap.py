"""
tests/test_eqmap.py
-------------------
EQ map core (M2 task 1): the pinned map convention (Property 8), the
Grounding_Check on synthetic meshes (Property 9) and on stock RoF2 zones, the
format round-trip (Property 10), parser tolerance (Property 11) and the stock
``maps/*.txt`` parse.

The stock-zone tests read the install named by ``EQ_PATH``
(``core.env.env_value``) and skip when it is unset or the zone's files are
missing. This task's strategies live here, not in ``tests/strategies.py``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from core.env import env_value
from core.paths import OutputRoot
from core.ter import Polygon, TerFile, Vertex
from generators.eqmap import (
    CANDIDATES,
    MAP_CONVENTION,
    REFERENCE_ZONES,
    MapFile,
    MapLabel,
    MapLayer,
    MapLine,
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
from tests.pbt_helpers import scaled

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
