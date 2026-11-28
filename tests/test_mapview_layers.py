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


# Step 32 task 3 (followups Req 2): the map's returns come from the layout's record, and the
# District labels keep clear of the legend.
_PLAN = [{"purpose": "fortress", "race": "giant"}, {"purpose": "warren", "race": "goblin"}]


def test_a_return_is_marked_from_the_layout_record(monkeypatch):
    """Classic 24 seed 2085 with every cross link drawn to drop: its goblins are entered by
    drops alone, so ``_add_return`` lays ``corr_25`` back out. The map marks that one return
    and no other; the old inference also took the flush ``corr_0`` (a pair whose one other
    link drops) for one."""
    from generators import layout as L
    from generators.districts import INTRUSION
    monkeypatch.setattr(L, "DROP_SHARE", 1.0)
    gen = L.LayoutGenerator("dungeon", seed=2085, engine="classic")
    spec = gen.generate("t", room_count=24, districts=True, district_plan=_PLAN,
                        district_relationship=INTRUSION, elevation=True)
    recorded = {f"corr_{r['edge']}" for r in gen.drop_returns}
    assert recorded == {"corr_25"}
    flagged = {c.id for c in spec.corridors if c.drop_return}
    assert flagged == recorded
    by = {r.id: r for r in spec.rooms}
    (ret,) = [c for c in spec.corridors if c.drop_return]
    assert not ret.drop and by[ret.from_room].district != by[ret.to_room].district
    # Every other link of its pair drops: the intruder's only flush way out.
    pair = {by[ret.from_room].district, by[ret.to_room].district}
    assert all(c.drop for c in spec.corridors if c is not ret
               and {by[c.from_room].district, by[c.to_room].district} == pair)
    # Written only when set, and read back.
    doc = spec.to_dict()
    assert [c["id"] for c in doc["corridors"] if "drop_return" in c] == ["corr_25"]
    from generators.zone_spec import ZoneSpec
    assert {c.id for c in ZoneSpec.from_dict(doc).corridors if c.drop_return} == recorded
    root = ET.fromstring(render_map_svg(spec, outline=_outline(spec)))
    marked = [p.find(_NS + "title").text for p in _layers(root)["links"].iter(_NS + "polyline")
              if p.get("class") == "link link-return"]
    assert marked == ["return (corr_25)"]
    rows = [t.text for g in root.iter(_NS + "g") if g.get("class") == "legend-row"
            for t in g.iter(_NS + "text")]
    assert "return (way back)" in rows


def test_a_zone_without_a_return_writes_no_flag(case_p):
    assert not any(c.drop_return for c in case_p.corridors)
    assert all("drop_return" not in c for c in case_p.to_dict()["corridors"])
    assert "link-return" not in render_map_svg(case_p, outline=_outline(case_p))


# Step 31's acceptance cases (docs/ACCEPTANCE.md "Step 31 — District races"): Controls
# cases (layout, rooms, relationship, seed), and the prompt case p.
_STEP31 = {"i": ("graph", 16, "intrusion", 2008), "d": ("graph", 24, "intrusion", 2044),
           "r": ("classic", 16, "intrusion", 2048), "v": ("graph", 24, "intrusion", 2013),
           "f": ("graph", 12, "factional", 2000), "p": None}


@pytest.mark.parametrize("case", sorted(_STEP31))
def test_district_labels_keep_clear_of_the_legend(case):
    from generators.mapview import district_label_box
    if _STEP31[case] is None:
        spec = plan_to_spec(RulePlanner().plan(CASE_P).validate(), seed=2027)
    else:
        layout, rooms, rel, seed = _STEP31[case]
        plan = ZonePlan.from_controls({"zone_type": "dungeon", "room_count": rooms,
                                       "verticality": "moderate", "layout": layout,
                                       "districts": True, "district_plan": _PLAN,
                                       "district_relationship": rel}, [])
        spec = plan_to_spec(plan, seed=seed)
    root = ET.fromstring(render_map_svg(spec, outline=_outline(spec)))
    w = float(root.get("width"))
    (box,) = [r for r in root.iter(_NS + "rect") if r.get("class") == "legend-box"]
    x0, y0 = float(box.get("x")), float(box.get("y"))
    legend = (x0, y0, x0 + float(box.get("width")), y0 + float(box.get("height")))
    labels = [t for t in root.iter(_NS + "text") if t.get("class") == "district-label"]
    assert len(labels) == len(spec.districts) >= 2
    for t in labels:
        b = district_label_box(float(t.get("x")), float(t.get("y")), t.text)
        assert not (b[0] < legend[2] and legend[0] < b[2] and b[1] < legend[3] and legend[1] < b[3]), \
            (t.text, b, legend)
        assert 0 <= b[0] and b[2] <= w
