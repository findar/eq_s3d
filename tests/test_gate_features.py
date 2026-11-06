"""Room layouts task 2 (Requirement 2; design F1): the gate judges Features before any generator
places one. The walk surface can't see a solid on an unbroken floor, so the gate reads walls
from the mesh. Rooms and solids here are built by hand, so each break is the one named.
"""

import json

import analyzer.traverse as T
from analyzer.traverse import AgentModel, build_walk_surface, check_features, outline_checks
from generators.room_features import POI, Feature
from generators.geometry import MeshBuilder, _ensure_materials
from generators.zone_spec import CorridorSpec, RoomSpec, ZoneSpec

AGENT = AgentModel()
H = 40.0


def _spec(features=(), pois=(), doors=("E", "W")):
    a = RoomSpec("a", 0.0, 0.0, width=100.0, depth=60.0, height=H, open_walls=list(doors),
                 features=list(features), pois=list(pois))
    rooms, cors = [a], []
    for side, sign in (("E", 1), ("W", -1)):
        if side in doors:
            b = RoomSpec(f"b{side}", sign * 200.0, 0.0, width=100.0, depth=60.0, height=H,
                         open_walls=["W" if side == "E" else "E"])
            rooms.append(b)
            cors.append(CorridorSpec(f"c{side}", sign * 50.0, 0.0, sign * 150.0, 0.0, width=18.0, height=30.0,
                                     from_room="a", to_room=b.id))
    spec = ZoneSpec(name="f", zone_type="dungeon", safe_point=(0.0, 0.0, 1.0))
    spec.rooms, spec.corridors = rooms, cors
    _ensure_materials(spec)
    return spec


def _solid(mb, mat, x0, y0, x1, y1, top=H):
    """A closed block by hand."""
    for a, b, n in (((x0, y0), (x1, y0), (0, -1, 0)), ((x1, y0), (x1, y1), (1, 0, 0)),
                    ((x1, y1), (x0, y1), (0, 1, 0)), ((x0, y1), (x0, y0), (-1, 0, 0))):
        mb.add_quad((*b, 0), (*b, top), (*a, top), (*a, 0), normal=n, material=mat)
    mb.add_quad((x0, y0, top), (x1, y0, top), (x1, y1, top), (x0, y1, top), normal=(0, 0, 1), material=mat)


def _verdict(spec, solids=(), extra=None):
    mb = MeshBuilder()
    held, spec.rooms[0].features = spec.rooms[0].features, []    # these solids are by hand
    for r in spec.rooms:
        mb.add_room(r, spec)
    spec.rooms[0].features = held
    for c in spec.corridors:
        mb.add_corridor(c, spec)
    mat = mb.material_id(spec.materials[spec.rooms[0].wall_material])
    for s in solids:
        _solid(mb, mat, *s)
    if extra:
        extra(mb, mat)
    surf = build_walk_surface(mb.to_ter("f"), AGENT)
    return check_features(surf, spec.rooms[0], spec, AGENT)


PILLAR = Feature("pillar", [(10.0, 10.0), (14.0, 10.0), (14.0, 14.0), (10.0, 14.0)])


def test_a_room_with_a_pillar_clear_of_the_way_passes():
    v = _verdict(_spec([PILLAR]), solids=[(10.0, 10.0, 14.0, 14.0)])
    assert v.ok, v.reason


def test_a_wall_of_solids_between_two_doors_fails():
    v = _verdict(_spec([PILLAR]), solids=[(-2.0, -30.0, 2.0, 30.0)])
    assert not v.ok and "are cut off from each other" in v.reason, v.reason


def test_a_gap_a_player_cannot_fit_through_fails():
    """Two solids 3 u apart: the floor's unbroken, and a walk surface would pass it."""
    v = _verdict(_spec([PILLAR]), solids=[(-2.0, -30.0, 2.0, -1.5), (-2.0, 1.5, 2.0, 30.0)])
    assert not v.ok and "are cut off from each other" in v.reason, v.reason


def test_a_gap_a_player_fits_through_passes():
    v = _verdict(_spec([PILLAR]), solids=[(-2.0, -30.0, 2.0, -6.0), (-2.0, 6.0, 2.0, 30.0)])
    assert v.ok, v.reason


def test_a_solid_on_a_door_blocks_it():
    v = _verdict(_spec([PILLAR]), solids=[(35.0, -14.0, 50.0, 14.0)])
    assert not v.ok and "E -9.0..9.0" in v.reason, v.reason


def test_floor_walled_off_from_the_doors_fails():
    v = _verdict(_spec([PILLAR]), solids=[(-30.0, 8.0, 30.0, 12.0), (-30.0, 8.0, -26.0, 30.0), (26.0, 8.0, 30.0, 30.0)])
    assert not v.ok and v.reason.startswith("floor walled off"), v.reason


DAIS = Feature("dais", [(-20.0, 10.0), (20.0, 10.0), (20.0, 26.0), (-20.0, 26.0)], height=8.0, steps_side="S")


def test_a_dais_with_no_way_up_fails():
    v = _verdict(_spec([DAIS]), solids=[(-20.0, 10.0, 20.0, 26.0, 8.0)])
    assert not v.ok and v.reason == "dais 0 can't be walked onto", v.reason


def _steps(mb, mat):
    """Risers of 2 u up the dais's south side, each tread welded onto nothing: seam contact."""
    for k in range(4):
        y0, y1 = 2.0 + 2 * k, 4.0 + 2 * k
        z = 2.0 * (k + 1)
        mb.add_quad((-6.0, y0, z), (6.0, y0, z), (6.0, y1, z), (-6.0, y1, z), normal=(0, 0, 1), material=mat)


def test_a_dais_with_steps_passes():
    v = _verdict(_spec([DAIS]), solids=[(-20.0, 10.0, 20.0, 26.0, 8.0)], extra=_steps)
    assert v.ok, v.reason


def test_a_poi_on_a_cut_off_dais_is_unreachable():
    poi = POI("boss", 0.0, 18.0, 8.0)
    v = _verdict(_spec([], [poi]), solids=[(-20.0, 10.0, 20.0, 26.0, 8.0)])
    assert not v.ok and v.reason == "POI boss can't be reached", v.reason


def test_a_poi_on_the_floor_passes():
    v = _verdict(_spec([], [POI("treasure", 0.0, -20.0, 0.0)]))
    assert v.ok, v.reason


def test_the_verdict_reaches_the_report(monkeypatch):
    spec = _spec([PILLAR])
    mb = MeshBuilder()
    for r in spec.rooms:
        mb.add_room(r, spec)
    for c in spec.corridors:
        mb.add_corridor(c, spec)
    _solid(mb, mb.material_id(spec.materials[spec.rooms[0].wall_material]), -2.0, -30.0, 2.0, 30.0)
    ter = mb.to_ter("f")
    monkeypatch.setattr(T, "load_ter_from_eqg", lambda _p: (ter, "f"))
    report = T.validate("f.eqg", spec=spec, agent=AGENT)
    assert not report.passed and "cut off" in report.summary()


def test_an_empty_plain_room_is_not_judged():
    spec = _spec()
    mb = MeshBuilder()
    for r in spec.rooms:
        mb.add_room(r, spec)
    assert outline_checks(build_walk_surface(mb.to_ter("f"), AGENT), spec, AGENT) == []


def test_features_round_trip_and_are_absent_when_empty():
    spec = _spec([PILLAR], [POI("boss", 1.0, 2.0, 3.0, feature=0)])
    d = spec.to_dict()
    assert "features" not in d["rooms"][1] and "pois" not in d["rooms"][1]
    again = ZoneSpec.from_dict(json.loads(json.dumps(d)))
    assert again.rooms[0].features == spec.rooms[0].features and again.rooms[0].pois == spec.rooms[0].pois
