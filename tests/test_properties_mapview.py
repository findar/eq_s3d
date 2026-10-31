"""
tests/test_properties_mapview.py
--------------------------------
Property tests for the map viewer's outline layer (``generators/mapview.py``).

Design reference: ``.kiro/specs/zone-generator-m2-true-layout-artifacts/design.md``,
"Map viewer outline layer", Decisions 10-11, Properties 14-15. Both run on
Zone_Specs alone (no builds); Property 15's outline is synthetic.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from hypothesis import given, settings
from hypothesis import strategies as st

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators.mapgeom import DepthBand, OutlineSet, Polyline
from generators.mapview import render_map_svg
from generators.routing import corridor_route
from generators.zone_spec import ZoneSpec

from tests import reference_mapview
from tests.pbt_helpers import scaled
from tests.strategies import seeds, spec_zone_types, verticality

_NS = "{http://www.w3.org/2000/svg}"


@st.composite
def zone_specs(draw) -> ZoneSpec:
    """A layout-only Zone_Spec: any zone type, seed, size, locks, verticality."""
    plan = ZonePlan(
        name="mapview",
        zone_type=draw(spec_zone_types),
        room_count=draw(st.integers(1, 30)),
        locks=draw(st.integers(0, 3)),
        elevation=draw(st.booleans()),
        verticality=draw(verticality),
    )
    return plan_to_spec(plan, seed=draw(seeds))


def _spec_extents(spec: ZoneSpec):
    xs, ys = [], []
    for r in spec.rooms:
        xs += [r.center_x - r.width / 2, r.center_x + r.width / 2]
        ys += [r.center_y - r.depth / 2, r.center_y + r.depth / 2]
    for c in spec.corridors:
        xs += [c.from_x, c.to_x]
        ys += [c.from_y, c.to_y]
    return xs, ys


@st.composite
def synthetic_outlines(draw, spec: ZoneSpec) -> OutlineSet:
    """1-4 bands and 0-12 wall/ledge polylines around (and past) the spec."""
    xs, ys = _spec_extents(spec)
    xs, ys = (xs or [0.0, 1000.0]), (ys or [0.0, 1000.0])   # roomless wilderness
    x0, x1 = int(min(xs)) - 300, int(max(xs)) + 300
    y0, y1 = int(min(ys)) - 300, int(max(ys)) + 300
    offsets = [0] + draw(st.lists(st.sampled_from([-3, -2, -1, 1, 2, 3]),
                                  max_size=3, unique=True))
    bands = tuple(
        DepthBand(index=i, z_lo=-1e9, z_hi=1e9, median_z=0.0,
                  role="main" if off == 0 else ("above" if off > 0 else "below"),
                  offset=off)
        for i, off in enumerate(offsets))
    polylines = []
    for _ in range(draw(st.integers(0, 12))):
        raw = draw(st.lists(st.tuples(st.integers(x0, x1), st.integers(y0, y1)),
                            min_size=2, max_size=6))
        pts = []
        for x, y in raw:
            if not pts or (pts[-1][0], pts[-1][1]) != (x, y):
                pts.append((float(x), float(y), 0.0))
        if len(pts) < 2:
            continue
        polylines.append(Polyline(points=tuple(pts),
                                  kind=draw(st.sampled_from(["wall", "ledge"])),
                                  band=draw(st.integers(0, len(bands) - 1))))
    # The Floor_Region bbox may reach past the schematic on any side.
    bx = sorted(draw(st.tuples(st.integers(x0, x1), st.integers(x0, x1))))
    by = sorted(draw(st.tuples(st.integers(y0, y1), st.integers(y0, y1))))
    for pl in polylines:
        for x, y, _ in pl.points:
            bx = [min(bx[0], x), max(bx[1], x)]
            by = [min(by[0], y), max(by[1], y)]
    bounds = (float(bx[0]), float(by[0]), 0.0, float(bx[1]), float(by[1]), 0.0)
    return OutlineSet(tuple(polylines), bands, bounds, 0, True)


sizes = st.integers(200, 1600)
paddings = st.integers(0, 90)


@settings(deadline=None, max_examples=scaled(100))
@given(spec=zone_specs(), size=sizes, padding=paddings)
def test_schematic_unchanged(spec, size, padding):
    """
    Property 14 (M2-P9): the schematic is unchanged without an outline.

    For any Zone_Spec and any size and padding, ``render_map_svg(spec, size,
    padding)`` is byte-identical to the frozen ``tests/reference_mapview.py``.

    Validates: M2 Req 7.2.
    """
    expected = reference_mapview.render_map_svg(spec, size, padding)
    assert render_map_svg(spec, size, padding) == expected
    assert render_map_svg(spec, size, padding, outline=None) == expected


def _path_points(d: str):
    nums = [float(v) for v in re.findall(r"-?\d+\.\d", d)]
    return list(zip(nums[0::2], nums[1::2]))


@settings(deadline=None, max_examples=scaled(100))
@given(data=st.data(), spec=zone_specs(), size=sizes, padding=paddings)
def test_outline_under_annotations(data, spec, size, padding):
    """
    Property 15 (M2-P10): the outline sits under the annotations.

    For any Zone_Spec and synthetic outline over it, the SVG has one outline
    ``<path>`` per polyline inside the first element after the background, a
    path is dashed exactly when its polyline is a ledge, every outline point
    projects inside the canvas north-up, every room ``<rect>`` has
    fill-opacity <= 0.35, each corridor is a ``<polyline>`` through its
    projected ``corridor_route`` waypoints, and the legend holds ``wall`` and
    ``ledge``.

    Validates: M2 Req 7.1, 7.3, 7.4, 7.5.
    """
    outline = data.draw(synthetic_outlines(spec))
    svg = render_map_svg(spec, size, padding, outline=outline)
    root = ET.fromstring(svg)
    kids = list(root)
    w, h = float(root.get("width")), float(root.get("height"))

    # Background, then the outline group before anything schematic.
    assert kids[0].tag == _NS + "rect" and kids[0].get("fill") == "#0f0f16"
    group = kids[1]
    assert group.tag == _NS + "g" and group.get("id") == "outline"
    paths = list(group)
    assert len(paths) == len(outline.polylines)
    assert all(p.tag == _NS + "path" for p in paths)

    # The frame, re-derived: union of rooms, corridor endpoints, outline bounds.
    xs, ys = _spec_extents(spec)
    xs += [outline.bounds[0], outline.bounds[3]]
    ys += [outline.bounds[1], outline.bounds[4]]
    min_x, max_y = min(xs), max(ys)
    scale = (size - 2 * padding) / max(max(xs) - min_x, 1.0, max(ys) - min(ys))

    def proj(x, y):
        return (float(f"{padding + (x - min_x) * scale:.1f}"),
                float(f"{padding + (max_y - y) * scale:.1f}"))

    for pl, el in zip(outline.polylines, paths):
        assert (el.get("stroke-dasharray") is not None) == (pl.kind == "ledge")
        assert el.get("fill") is None or el.get("fill") == "none"
        got = _path_points(el.get("d"))
        assert got == [proj(x, y) for x, y, _ in pl.points]
        for sx, sy in got:
            assert -0.05 <= sx <= w + 0.5 and -0.05 <= sy <= h + 0.5
        for (_, wy1, _), (_, wy2, _), (_, sy1), (_, sy2) in zip(
                pl.points, pl.points[1:], got, got[1:]):
            if wy1 - wy2 > 1.0:           # north up: larger world Y, smaller SVG Y
                assert sy1 < sy2

    # Room fills are lightened so the walls read through.
    room_rects = [k for k in kids[2:] if k.tag == _NS + "rect" and k.get("rx") == "4"]
    assert len(room_rects) == len(spec.rooms)
    assert all(float(k.get("fill-opacity")) <= 0.35 for k in room_rects)

    # Corridors follow their routes, and come after the outline group.
    rooms_by_id = {r.id: r for r in spec.rooms}
    polylines = [k for k in kids[2:] if k.tag == _NS + "polyline"]
    assert len(polylines) == len(spec.corridors)
    for c, el in zip(spec.corridors, polylines):
        want = [proj(x, y) for x, y in corridor_route(c, rooms_by_id).waypoints]
        got = [tuple(float(v) for v in p.split(",")) for p in el.get("points").split()]
        assert got == want

    legend = [t.text for g in kids if g.tag == _NS + "g" for t in g.iter(_NS + "text")]
    assert "wall" in legend and "ledge" in legend
