"""
The Envelope and the layout inside it (outdoor dungeon, task 2).

D1 (no Envelope, same layout) is pinned by the step 3 UV-free goldens in
``test_material_names.py``; here the explicit ``envelope=None`` path is checked
against the default call. D2 checks every room box and corridor leg against a
synthetic Envelope EXACTLY (a sloped plane over a disc: the plane's lowest
point over a rectangle is a corner, and a rectangle is inside a disc iff its
corners are), so the test does not lean on the Envelope's own sampling.
"""

from __future__ import annotations

import json
import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from generators.envelope import Envelope, EnvelopeFitError
from generators.layout import MIN_ENVELOPE_ROOMS, LayoutGenerator
from generators.routing import corridor_route, route_footprint
from tests.pbt_helpers import scaled
from tests.strategies import box_zone_types, seeds

CENTRE = (100.0, -50.0)
FLOOR = -600.0
COVER = 40.0


def _surface(x, y):
    return 300.0 + 0.15 * x - 0.05 * y


def _disc(radius: float) -> Envelope:
    return Envelope.disc(CENTRE, radius, floor_limit=FLOOR,
                         surface=_surface, rock_cover=COVER)


def _corners(x0, y0, x1, y1):
    return ((x0, y0), (x0, y1), (x1, y0), (x1, y1))


def _inside_exactly(env_radius, x0, y0, z0, x1, y1, z1, tol=1e-6):
    # The 64-gon inscribed in the disc: its inradius bounds what it covers.
    inner = env_radius * math.cos(math.pi / 64)
    for x, y in _corners(x0, y0, x1, y1):
        if math.hypot(x - CENTRE[0], y - CENTRE[1]) > inner + tol:
            return False
        if z1 > _surface(x, y) - COVER + tol:
            return False
    return z0 >= FLOOR - tol


def _boxes(spec):
    for r in spec.rooms:
        yield r.id, (r.center_x - r.width / 2, r.center_y - r.depth / 2, r.floor_z,
                     r.center_x + r.width / 2, r.center_y + r.depth / 2,
                     r.floor_z + r.height)
    rooms = {r.id: r for r in spec.rooms}
    for c in spec.corridors:
        z0, z1 = min(c.from_z, c.to_z), max(c.from_z, c.to_z) + c.height
        for x0, y0, x1, y1 in route_footprint(corridor_route(c, rooms), c.width / 2):
            yield c.id, (x0, y0, z0, x1, y1, z1)


# ---------------------------------------------------------------------------
# The Envelope itself
# ---------------------------------------------------------------------------

def test_contains_box_checks_footprint_floor_and_cover():
    env = _disc(500.0)
    top = _surface(100.0, -50.0) - COVER
    assert env.contains_box(50, -100, -100, 150, 0, top - 20)
    assert not env.contains_box(50, -100, -100, 150, 0, top + 20)      # pokes through
    assert not env.contains_box(50, -100, FLOOR - 1, 150, 0, 0)        # under the floor
    assert not env.contains_box(500, -100, -100, 700, 0, 0)            # off the hill
    assert env.top_at(0.0, 0.0) == pytest.approx(_surface(0, 0) - COVER)


def test_footprint_needs_three_points():
    with pytest.raises(ValueError):
        Envelope(((0, 0), (1, 1)), 0.0, _surface, 0.0)


# ---------------------------------------------------------------------------
# D1: no Envelope, no change
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("zone_type", ["dungeon", "city", "wilderness"])
def test_explicit_none_matches_default(zone_type):
    a = LayoutGenerator(zone_type, seed=7).generate("d1", room_count=6)
    b = LayoutGenerator(zone_type, seed=7).generate("d1", room_count=6, envelope=None)
    assert json.dumps(a.to_dict(), sort_keys=True) == json.dumps(b.to_dict(), sort_keys=True)


# ---------------------------------------------------------------------------
# D2: everything inside the Envelope
# ---------------------------------------------------------------------------

@settings(max_examples=scaled(20), deadline=None)
@given(s=seeds, zone_type=box_zone_types, n=st.integers(3, 8),
       elevation=st.booleans())
def test_rooms_and_corridors_lie_inside(s, zone_type, n, elevation):
    radius = 1600.0
    gen = LayoutGenerator(zone_type, seed=s)
    try:
        spec = gen.generate("d2", room_count=n, elevation=elevation,
                            envelope=_disc(radius))
    except EnvelopeFitError:
        return      # D2 is about what IS laid out; refusing to lay out is allowed
    assert len(spec.rooms) >= min(n, MIN_ENVELOPE_ROOMS)
    for part, box in _boxes(spec):
        assert _inside_exactly(radius, *box), (part, box)


def test_same_seed_same_layout_in_an_envelope():
    a = LayoutGenerator("dungeon", seed=11).generate("d", room_count=6, envelope=_disc(1600))
    b = LayoutGenerator("dungeon", seed=11).generate("d", room_count=6, envelope=_disc(1600))
    assert json.dumps(a.to_dict(), sort_keys=True) == json.dumps(b.to_dict(), sort_keys=True)


# ---------------------------------------------------------------------------
# Rooms that don't fit
# ---------------------------------------------------------------------------

def test_tight_envelope_drops_rooms_with_a_warning():
    # (Radii at stock room scale, step 7 task 17: rooms are ~4.5x smaller in
    # side than before, so this disc was 900 u and the one below 300 u.)
    gen = LayoutGenerator("dungeon", seed=1)
    spec = gen.generate("tight", room_count=6, envelope=_disc(180))
    assert MIN_ENVELOPE_ROOMS <= len(spec.rooms) < 6
    assert any(w.startswith("rooms_reduced:") for w in gen.warnings), gen.warnings
    for part, box in _boxes(spec):
        assert _inside_exactly(180, *box), (part, box)


def test_room_count_that_fits_has_no_warning():
    gen = LayoutGenerator("dungeon", seed=0)
    spec = gen.generate("roomy", room_count=6, envelope=_disc(2500))
    assert len(spec.rooms) == 6
    assert gen.warnings == []


def test_too_small_for_the_minimum_raises():
    with pytest.raises(EnvelopeFitError):
        LayoutGenerator("dungeon", seed=0).generate("tiny", room_count=6,
                                                    envelope=_disc(120))
