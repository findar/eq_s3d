"""
tests/test_mapview_layers.py
----------------------------
The map's layers (district races task 18, Requirement 10): on the traced map (an outline
given) every mark but the walls, corridors and room fills sits in one ``g.map-layer`` the
viewer's dialog shows and hides, and the EQ export view draws exactly what the in-client
``maps/*.txt`` carries. Case p is the step 31 prompt case (seed 2020), layout only.
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET

import pytest

from ai.expand import plan_to_spec
from ai.rule_planner import RulePlanner
from ai.schema import ZonePlan
from generators.eqmap import build_map_file, format_map_layer, map_to_world, parse_map_layer
from generators.mapgeom import DepthBand, OutlineSet, Polyline
from generators.mapview import MAP_LAYERS, render_map_svg
from generators.semantics import room_race

_NS = "{http://www.w3.org/2000/svg}"
CASE_P = "a towering giant fortress the goblins tunnelled into, with 16 rooms"


def _outline(spec, bands=((0, 0),)):
    """A box round the rooms, one wall polyline per band (``(index, offset)``), so the EQ
    map has lines in each band's colour; the bands split Z at the rooms' median floor."""
    xs = [v for r in spec.rooms for v in (r.bounds[0][0], r.bounds[1][0])]
    ys = [v for r in spec.rooms for v in (r.bounds[0][1], r.bounds[1][1])]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    zs = sorted(r.floor_z for r in spec.rooms)
    cut = zs[len(zs) // 2] if len(bands) > 1 else math.inf
    dbs = [DepthBand(i, -math.inf if k == 0 else cut, cut if k == 0 and len(bands) > 1 else math.inf,
                     0.0, "main" if off == 0 else "above", off)
           for k, (i, off) in enumerate(bands)]
    lines = [Polyline(((x0 + 10 * k, y0, 0.0), (x1, y0 + 10 * k, 0.0), (x1, y1, 0.0), (x0, y1, 0.0)),
                      "wall", i) for k, (i, _off) in enumerate(bands)]
    return OutlineSet(tuple(lines), tuple(dbs), (x0, y0, 0.0, x1, y1, 0.0), 0, True)


@pytest.fixture(scope="module")
def case_p():
    return plan_to_spec(RulePlanner().plan(CASE_P).validate(), seed=2020)


def _layers(root):
    return {g.get("data-layer"): g for g in root.iter(_NS + "g") if g.get("class") == "map-layer"}


def test_each_layer_is_one_group_with_its_defaults(case_p):
    root = ET.fromstring(render_map_svg(case_p, outline=_outline(case_p)))
    groups = [g for g in root.iter(_NS + "g") if g.get("class") == "map-layer"]
    keys = [g.get("data-layer") for g in groups]
    assert len(keys) == len(set(keys))
    known = {k: on for k, _label, on in MAP_LAYERS}
    assert set(keys) - {"eq"} <= set(known)
    # Case p draws these; the defaults are Districts, Races, Links and Room IDs (and Sites).
    assert {"districts", "races", "links", "mixed", "gates", "ids", "eq"} <= set(keys)
    for g in groups:
        assert g.get("id") == f"layer-{g.get('data-layer')}" and g.get("data-label")
        if g.get("data-layer") != "eq":
            assert g.get("data-default") == str(int(known[g.get("data-layer")]))
            assert g.get("display") is None          # the server's file shows every layer
    assert _layers(root)["eq"].get("display") == "none"
    # The legend lists each row under its layer, base rows always.
    rows = [g.get("data-layer") for g in root.iter(_NS + "g") if g.get("class") == "legend-row"]
    assert rows.count("base") == 6 and set(rows) - {"base"} <= set(keys)


def test_races_layer_tags_every_room_and_link(case_p):
    root = ET.fromstring(render_map_svg(case_p, outline=_outline(case_p)))
    races = _layers(root)["races"]
    tags = {t.get("data-room"): t.text for t in races.iter(_NS + "text") if t.get("class") == "race-tag"}
    assert tags == {r.id: room_race(case_p, r) or "default" for r in case_p.rooms}
    assert {"giant", "goblin"} <= set(tags.values())
    links = [p for p in races.iter(_NS + "polyline") if p.get("class") == "race-link"]
    assert len(links) == len(case_p.corridors)
    # The links between Districts are marked apart, the drops with their height.
    lay = _layers(root)["links"]
    kinds = [p.get("class") for p in lay.iter(_NS + "polyline")]
    assert kinds.count("link link-threshold") == sum(c.threshold for c in case_p.corridors)
    drops = [c for c in case_p.corridors if c.drop]
    assert [t.text for t in lay.iter(_NS + "text")] == [f"{c.drop:.0f} u" for c in drops]


def test_a_zone_without_district_races_has_no_races_layer():
    spec = plan_to_spec(ZonePlan(name="m", zone_type="dungeon", room_count=8).validate(), seed=4)
    layers = _layers(ET.fromstring(render_map_svg(spec, outline=_outline(spec))))
    assert "races" not in layers and "ids" in layers and "eq" in layers
    # The plain schematic (no outline) has no layers at all.
    assert 'class="map-layer"' not in render_map_svg(spec)


def _eq_view(svg: str):
    """The EQ view's segments and labels, back in world XY (rounded to the SVG's 0.1 px)."""
    root = ET.fromstring(svg)
    a, b, s = (float(root.get(f"data-frame-{k}")) for k in "abs")
    eq = _layers(root)["eq"]
    segs, labels = [], []
    for p in eq.iter(_NS + "path"):
        rgb = tuple(int(v) for v in re.findall(r"\d+", p.get("stroke")))
        nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", p.get("d"))]
        for i in range(0, len(nums), 4):
            u1, v1, u2, v2 = nums[i:i + 4]
            segs.append((int(p.get("data-eq-layer")), rgb,
                         ((u1 - a) / s, (b - v1) / s, (u2 - a) / s, (b - v2) / s)))
    for t in eq.iter(_NS + "text"):
        labels.append((int(t.get("data-eq-layer")), t.text,
                       ((float(t.get("x")) - 4 - a) / s, (b - float(t.get("y")) + 4) / s)))
    return segs, labels, s


def test_eq_view_is_what_the_map_file_carries(case_p):
    """The EQ export view matches the ``.txt`` export: each file layer, written with
    ``format_map_layer`` and read back with ``parse_map_layer``, holds exactly the view's
    lines (in their colours) and labels, to the SVG's 0.1 px."""
    outline = _outline(case_p, bands=((0, 0), (1, 1)))
    segs, labels, s = _eq_view(render_map_svg(case_p, outline=outline))
    tol = 0.051 / s + 1e-6
    want_segs, want_labels = [], []
    for layer in build_map_file(outline, case_p, "casep").layers:
        parsed = parse_map_layer(format_map_layer(layer), layer.index)
        assert not parsed.skipped_count
        for ln in parsed.layer.lines:
            x1, y1, _ = map_to_world(ln.x1, ln.y1, ln.z1)
            x2, y2, _ = map_to_world(ln.x2, ln.y2, ln.z2)
            want_segs.append((layer.index, (ln.r, ln.g, ln.b), (x1, y1, x2, y2)))
        for lab in parsed.layer.labels:
            x, y, _ = map_to_world(lab.x, lab.y, lab.z)
            want_labels.append((layer.index, lab.text, (x, y)))
    assert {i for i, *_ in want_segs} == {0, 1}
    assert {t for _i, t, _p in want_labels} == {"Entrance", "Boss"}

    def same(got, want):
        assert len(got) == len(want)
        for (gi, gk, gp), (wi, wk, wp) in zip(sorted(got, key=lambda e: e[:2]), sorted(want, key=lambda e: e[:2])):
            assert (gi, gk) == (wi, wk)
            assert all(abs(p - q) <= tol + 0.0001 * abs(q) for p, q in zip(gp, wp))

    # Order within a (layer, colour) is the file's: draw order is kept.
    same(segs, want_segs)
    same(labels, want_labels)
