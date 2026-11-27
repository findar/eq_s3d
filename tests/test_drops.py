"""District races task 7: flush or a drop, and one-way loops (Req 7, 8).

A link between two Districts of an intrusion zone is flush unless a salted draw (chance
``DROP_SHARE``) makes it a drop: ``CorridorSpec.drop`` u, the corridor's end at its LOWER room
raised by that much, the wall below the opening kept, so the gate reads a one-way link. A drop
is kept only while the directed room graph stays strongly connected; an intruder whose every
link would drop first gets a flush return from its room farthest from the landings.
"""

import math
import random
import statistics

import pytest

from analyzer.traverse import AgentModel, build_walk_surface, find_drops, shell_report, _RoomFloors
from generators import layout as L
from generators.districts import INTRUSION
from generators.geometry import build_mesh, door_sills, drop_end
from generators.layout import LayoutGenerator, gate_oneway
from generators.zone_spec import CorridorSpec, RoomSpec, ZoneSpec

PLAN = [{"purpose": "fortress", "race": "giant"}, {"purpose": "warren", "race": "goblin"}]


def test_drop_limits_match_the_gate():
    assert L.MAX_DROP == AgentModel().max_drop
    assert AgentModel().max_step_up < L.MIN_DROP < L.DROP_P50 < L.MAX_DROP
    assert L.DROP_SHARE == pytest.approx(0.1)


def test_drop_heights_follow_stock():
    """Drawn as stock spreads them (p50 24 u, p90 84 u), inside MIN_DROP..MAX_DROP."""
    rng = random.Random(7)
    hs = [LayoutGenerator._drop_height(rng) for _ in range(4000)]
    assert all(L.MIN_DROP <= h <= L.MAX_DROP for h in hs)
    assert 17.0 < statistics.median(hs) < 24.0       # truncated at 80 u, so under stock's 24


def test_drop_written_only_when_set():
    cor = CorridorSpec("corr_0", 0.0, 0.0, 10.0, 0.0)
    assert "drop" not in ZoneSpec(name="t", corridors=[cor]).to_dict()["corridors"][0]
    cor.drop = 12.5
    doc = ZoneSpec(name="t", corridors=[cor]).to_dict()
    assert doc["corridors"][0]["drop"] == 12.5
    assert ZoneSpec.from_dict(doc).corridors[0].drop == 12.5


def _pair(back: bool):
    """Rooms ``a`` (entrance) and ``b`` side by side, both floors at 0; ``corr_0`` runs from
    ``a`` and enters ``b`` 20 u up its wall. ``back`` adds a flush corridor beside it."""
    a = RoomSpec("a", 50.0, 50.0, width=100.0, depth=100.0, height=60.0, floor_z=0.0)
    b = RoomSpec("b", 210.0, 50.0, width=100.0, depth=100.0, height=60.0, floor_z=0.0)
    a.role, b.role = "entrance", "normal"
    a.open_walls, b.open_walls = ["E"], ["W"]
    cors = [CorridorSpec("corr_0", 100.0, 70.0, 160.0, 70.0, from_z=0.0, to_z=20.0, width=14.0,
                         height=20.0, from_room="a", to_room="b", drop=20.0)]
    if back:
        cors.append(CorridorSpec("corr_1", 100.0, 25.0, 160.0, 25.0, width=14.0, height=20.0,
                                 from_room="a", to_room="b"))
    spec = ZoneSpec(name="drop", zone_type="dungeon", rooms=[a, b], corridors=cors)
    spec.safe_point = (50.0, 50.0, 5.0)
    return spec


def test_geometry_keeps_the_wall_under_a_drop():
    spec = _pair(back=False)
    b = spec.rooms[1]
    assert drop_end(spec.corridors[0], {r.id: r for r in spec.rooms}) == "to"
    sills = door_sills(b, spec)
    assert list(sills) == ["W"] and sills["W"][0][2] == pytest.approx(20.0)
    assert door_sills(spec.rooms[0], spec) == {}
    ter = build_mesh(spec).to_ter("drop")
    # A wall face in b's west plane, across the opening (y 63..77), from the floor to the sill.
    under = [p for p in ter.polygons
             if all(abs(ter.vertices[i].x - 160.0) < 1e-6 for i in (p.v1, p.v2, p.v3))
             and min(ter.vertices[i].y for i in (p.v1, p.v2, p.v3)) >= 63.0 - 1e-6
             and max(ter.vertices[i].y for i in (p.v1, p.v2, p.v3)) <= 77.0 + 1e-6
             and max(ter.vertices[i].z for i in (p.v1, p.v2, p.v3)) <= 20.0 + 1e-6]
    assert under


def test_the_gate_reads_the_drop_one_way():
    """Drop only: ``b`` is reached by falling and stranded; the gate's drop pass links the
    corridor (with ``a``) down onto ``b`` and nothing back. With a flush way back both pass."""
    agent = AgentModel()
    spec = _pair(back=False)
    ter = build_mesh(spec).to_ter("drop")
    surf = build_walk_surface(ter, agent)
    floors = _RoomFloors(surf, spec.rooms)
    comp = surf.component
    ca = {int(comp[f]) for f in floors(spec.rooms[0])}
    cb = {int(comp[f]) for f in floors(spec.rooms[1])}
    assert not ca & cb
    links = {(int(comp[u]), int(comp[v])) for u, vs in find_drops(surf, agent).items() for v in vs}
    assert any(u in ca and v in cb for u, v in links)
    assert not any(u in cb and v in ca for u, v in links)
    rooms = {r.room_id: r for r in shell_report(ter, spec, agent).rooms}
    assert rooms["a"].reachable and not rooms["b"].reachable
    assert rooms["b"].reason.startswith("stranded")

    spec = _pair(back=True)
    rep = shell_report(build_mesh(spec).to_ter("drop"), spec, agent)
    assert all(r.reachable for r in rep.rooms)


def _intrusion(seed, layout="classic", rooms=16):
    gen = LayoutGenerator("dungeon", seed=seed, engine=layout)
    spec = gen.generate("t", room_count=rooms, districts=True, district_plan=PLAN,
                        district_relationship=INTRUSION, elevation=True)
    return gen, spec


def _directed(spec):
    idx = {r.id: k for k, r in enumerate(spec.rooms)}
    edges = [(idx[c.from_room], idx[c.to_room]) for c in spec.corridors]
    drops = [c.drop for c in spec.corridors]
    return edges, gate_oneway(edges, drops, [r.floor_z for r in spec.rooms])


@pytest.mark.parametrize("layout", ["classic", "graph"])
def test_intrusion_drops(layout):
    """Over a few seeds: some cross links drop, none inside a District; each drop's lower
    end is its lower room's floor plus the drop and its upper end flush; every zone's
    directed graph is strongly connected and no pair is left with drops alone."""
    placed = cross = 0
    for seed in range(2000, 2012):
        gen, spec = _intrusion(seed, layout)
        by = {r.id: r for r in spec.rooms}
        for c in spec.corridors:
            a, b = by[c.from_room], by[c.to_room]
            if a.district == b.district:
                assert not c.drop
                continue
            cross += 1
            if not c.drop:
                continue
            placed += 1
            assert L.MIN_DROP <= c.drop <= L.MAX_DROP
            end = drop_end(c, by)
            lower, upper = (b, a) if end == "to" else (a, b)
            low_z, up_z = (c.to_z, c.from_z) if end == "to" else (c.from_z, c.to_z)
            assert low_z == pytest.approx(lower.floor_z + c.drop)
            assert up_z == pytest.approx(upper.floor_z)
            assert lower.floor_z <= upper.floor_z
            assert c.drop + c.height <= lower.height - L.DROP_LINTEL + 1e-6
        edges, oneway = _directed(spec)
        assert LayoutGenerator._strongly_connected(len(spec.rooms), edges, oneway)
        flush = {frozenset((by[c.from_room].district, by[c.to_room].district)) for c in spec.corridors
                 if not c.drop}
        pairs = {frozenset((by[c.from_room].district, by[c.to_room].district)) for c in spec.corridors}
        assert pairs <= flush           # every pair keeps a flush link (a return, if need be)
    assert placed >= 1 and placed <= 0.3 * cross


def test_no_intrusion_no_drop():
    for rel in ("sequential", "factional"):
        gen = LayoutGenerator("dungeon", seed=2004, engine="graph")
        spec = gen.generate("t", room_count=16, districts=True, district_plan=PLAN,
                            district_relationship=rel)
        assert not any(c.drop for c in spec.corridors)
        assert all("drop" not in c for c in spec.to_dict()["corridors"])


def test_drop_draw_leaves_the_layout_rng_alone(monkeypatch):
    """The drops draw from their own salted rng: with the share at 0 the rooms, floors and
    every corridor but the drops' own heights are as with it on."""
    _gen, on = _intrusion(2006)
    monkeypatch.setattr(L, "DROP_SHARE", 0.0)
    _gen, off = _intrusion(2006)
    assert not any(c.drop for c in off.corridors)
    assert [(r.id, r.center_x, r.center_y, r.floor_z) for r in on.rooms] == \
        [(r.id, r.center_x, r.center_y, r.floor_z) for r in off.rooms]


def test_landing_is_clear_for_decor():
    """A drop door's clear zone widens over its landing, and no wall face of the wall under
    the opening reaches decor."""
    from generators.room_context import contexts
    spec = _pair(back=True)
    ter = build_mesh(spec).to_ter("drop")
    ctx = {c.id: c for c in contexts(spec, ter)}
    b = ctx["b"]
    door = next(d for d in b.doors if d.c0 <= 70.0 <= d.c1)
    x0, y0, x1, y1 = door.clear
    assert x0 <= 161.0 <= x1 and y0 < 63.0 - 1.0 and y1 > 77.0 + 1.0
    under = [w for w in b.walls if abs(w.x - 160.0) < 0.5 and 63.0 < w.y < 77.0 and w.bottom < 20.0]
    assert not under
    plain = next(d for d in b.doors if d.c0 <= 25.0 <= d.c1)
    assert plain.clear[1] == pytest.approx(25.0 - 7.0) and plain.clear[3] == pytest.approx(25.0 + 7.0)


# --- The corridor check (analyzer.traverse.corridor_continuity) -----------------------------

def _corridors(spec):
    from analyzer.traverse import corridor_continuity
    agent = AgentModel()
    surf = build_walk_surface(build_mesh(spec).to_ter("drop"), agent)
    return {c.corridor_id: c for c in corridor_continuity(surf, spec, agent)}


def test_corridor_check_walks_a_drop_one_way():
    """A drop corridor passes from its upper room when its end falls onto the lower room's
    floor; the flush one beside it keeps the two-way check."""
    got = _corridors(_pair(back=True))
    assert got["corr_0"].connected, got["corr_0"].reason
    assert got["corr_1"].connected, got["corr_1"].reason


def test_corridor_check_fails_a_walled_off_drop():
    """(a) The same drop with its opening walled off (the lower room's wall left whole):
    no fall onto the room, so it fails."""
    spec = _pair(back=True)
    spec.rooms[1].open_walls = []
    spec.corridors = spec.corridors[:1]
    got = _corridors(spec)
    assert not got["corr_0"].connected
    assert got["corr_0"].reason == "drop: no fall onto its lower room"


def test_corridor_check_flush_unchanged():
    """(b) A flush corridor raised at one end with no ``drop`` is the old two-way check: a
    gap, as before."""
    spec = _pair(back=False)
    spec.corridors[0].drop = 0.0
    got = _corridors(spec)
    assert not got["corr_0"].connected and got["corr_0"].reason == "gap"


def _alongside():
    """A Z-corridor from ``a`` dropping 6 u into ``b`` whose jog runs down ``b``'s west wall
    0.5 u off it, crossing ``b``'s floor height on the way (the seed 2035 classic 24 corr_20
    shape)."""
    a = RoomSpec("a", 50.0, 150.0, width=100.0, depth=100.0, height=60.0, floor_z=0.0)
    b = RoomSpec("b", 165.0, 50.0, width=100.0, depth=100.0, height=60.0, floor_z=0.0)
    a.role, b.role = "entrance", "normal"
    a.open_walls, b.open_walls = ["E"], ["W"]
    cor = CorridorSpec("corr_0", 98.0, 150.0, 117.0, 50.0, from_z=0.0, to_z=6.0, width=14.0,
                       height=20.0, from_room="a", to_room="b", drop=6.0)
    spec = ZoneSpec(name="along", zone_type="dungeon", rooms=[a, b], corridors=[cor])
    spec.safe_point = (50.0, 150.0, 5.0)
    return spec


def test_a_drop_alongside_its_lower_room_is_refused():
    """The gate's seam reach (2 u, no wall test) joins the jog to ``b``'s floor through the
    wall: the corridor check says so rather than pass a way back the player hasn't, and the
    layout never places such a drop (``_drop_seams_clear``)."""
    spec = _alongside()
    got = _corridors(spec)
    assert not got["corr_0"].connected and got["corr_0"].reason == "drop walks both ways"
    assert not LayoutGenerator._drop_seams_clear(spec.rooms, spec.corridors[0], spec.rooms[1])
    assert LayoutGenerator._drop_seams_clear(_pair(False).rooms, _pair(False).corridors[0],
                                             _pair(False).rooms[1])


def test_map_marks_a_drop():
    from generators.mapview import render_map_svg
    svg = render_map_svg(_pair(back=True))
    assert svg.count('class="drop"') == 1 and "drop (one way)" in svg
    plain = _pair(back=True)
    plain.corridors[0].drop = 0.0
    assert 'class="drop"' not in render_map_svg(plain)


@pytest.mark.parametrize("form", ["breach", "frame"])
def test_a_door_line_stands_at_the_flush_end(form):
    """The gate walks a Transition's line through, a few u each way, so one at a drop's lower
    door would step off the ledge: it stands at the flush end (seed 1968221380, corr_7, a
    Threshold that drew both a drop and a breach: "no floor through the breach")."""
    from generators.transitions import draw_transition
    from generators.wall_styles import load_styles

    class Only:
        def weights(self, *_):
            return {f: float(f == form) for f in ("none", "seam", "frame", "breach")}

    # A breach into b (its host) asks for b's door; a frame between one style, a's door.
    asks_b = form == "breach"

    def line_x(drop):
        low = -drop
        a = RoomSpec("a", 0.0, 0.0, width=100.0, depth=60.0, height=60.0, open_walls=["E"],
                     floor_z=0.0 if asks_b else low)
        b = RoomSpec("b", 200.0, 0.0, width=100.0, depth=60.0, height=60.0, open_walls=["W"],
                     floor_z=low if asks_b else 0.0)
        cor = CorridorSpec("c", 50.0, 0.0, 150.0, 0.0, width=18.0, height=30.0,
                           from_room="a", to_room="b", drop=drop)
        styles = load_styles()
        kw = {"breach_host": "b"} if asks_b else {}
        rec = draw_transition(cor, {"a": a, "b": b}, styles["built"], styles["built"], [],
                              Only(), 1, 6.0, **kw)
        assert rec["form"] == form
        return rec["x"]

    flush, dropped = line_x(0.0), line_x(20.0)
    assert (flush > 100.0) == asks_b            # at the door it asks for
    assert (dropped > 100.0) != asks_b          # that door is the drop's: the other one
