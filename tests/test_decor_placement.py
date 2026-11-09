"""Room decor task 8 (Reqs 5, 6, 8, 13.4, 13.5; design P5, P8, P13): placing Props in a room.

Every test here reads RoomContexts, from the recorded room corpus (``tests/fixtures/rooms/``)
or built by hand; none builds a zone. The models come from a FIXTURE catalogue (``fixture``):
until the tag review (task 4) lands, ``rules/decor/tags.toml`` marks only a few models
``use = "yes"``, so the live catalogue would leave most lines unmet by design.
"""

from __future__ import annotations

import ast
import math
from pathlib import Path

import numpy as np
import pytest

from generators.decor.catalogue import KINDS, Catalogue, Model, Tags
from generators.decor.placement import (CORRIDOR, FRAME, HEAD_HEIGHT, PLAYER_HALF_WIDTH, Decorated, Room, check,
                                        place, size_of)
from generators.decor.rules import MOUNTS_FILLING, NEUTRAL, asks, load_decor
from generators.room_context import Door, RoomContext, WallFace, load

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "rooms"
CORPUS = [c for path in sorted(FIXTURES.glob("*.json")) for c in load(path)[1]]

#: Plan (w along the model's X, d along Y), height, depth below the origin, collision, and for
#: wall models stock's height over the floor and distance off the wall. Stock-like figures.
SIZES = {
    "torch": (3.4, 0.9, 5.2, 0.0, "passable", 5.5, 2.3), "lantern": (1.0, 1.0, 2.2, 0.0, "passable", 7.0, 1.0),
    "lamp": (1.0, 1.0, 2.2, 0.0, "passable", 7.0, 1.0), "brazier": (3.0, 3.0, 4.0, 0.0, "solid", None, None),
    "tiki": (1.5, 1.5, 7.0, 0.0, "solid", None, None), "candle": (0.6, 0.6, 1.2, 0.0, "passable", None, None),
    "candelabra": (2.0, 2.0, 6.0, 0.0, "solid", None, None), "fire": (5.0, 5.0, 2.0, 0.0, "passable", None, None),
    "chain": (1.0, 1.0, 8.0, 0.0, "passable", None, None), "hook": (1.0, 1.0, 6.0, 0.0, "passable", None, None),
    "shackle": (1.0, 2.0, 3.0, 0.0, "partial", 5.0, 0.6), "banner": (0.6, 4.0, 8.0, 0.0, "passable", 10.0, 0.4),
    "sign": (0.4, 3.0, 2.0, 0.0, "passable", 9.0, 0.3),
    "barrel": (3.0, 3.0, 4.5, 0.0, "solid", None, None), "keg": (3.0, 3.0, 3.5, 0.0, "solid", None, None),
    "crate": (4.0, 4.0, 4.0, 0.0, "solid", None, None), "box": (3.0, 3.0, 2.5, 0.0, "solid", None, None),
    "chest": (2.6, 4.0, 3.0, 0.0, "solid", None, None), "urn": (2.0, 2.0, 3.0, 0.0, "solid", None, None),
    "vase": (1.5, 1.5, 2.5, 0.0, "solid", None, None), "sack": (2.0, 2.0, 2.0, 0.0, "partial", None, None),
    "basket": (2.0, 2.0, 1.5, 0.0, "partial", None, None), "bucket": (1.5, 1.5, 1.5, 0.0, "solid", None, None),
    "jar": (1.0, 1.0, 1.5, 0.0, "solid", None, None), "pot": (1.5, 1.5, 1.5, 0.0, "solid", None, None),
    "table": (8.0, 5.0, 4.0, 0.0, "solid", None, None), "desk": (4.0, 7.0, 4.0, 0.0, "solid", None, None),
    "chair": (3.0, 3.0, 5.0, 0.0, "solid", None, None), "stool": (2.0, 2.0, 3.0, 0.0, "solid", None, None),
    "bench": (3.0, 8.0, 2.5, 0.0, "solid", None, None), "throne": (5.0, 5.0, 9.0, 0.0, "solid", None, None),
    "couch": (4.0, 9.0, 4.0, 0.0, "solid", None, None), "bed": (8.0, 4.0, 3.0, 0.0, "solid", None, None),
    "bookcase": (2.0, 12.0, 12.0, 0.0, "solid", None, None), "shelf": (2.0, 8.0, 8.0, 0.0, "solid", None, None),
    "rack": (2.0, 8.0, 7.0, 0.0, "solid", None, None), "rug": (8.0, 6.0, 0.2, 0.0, "passable", None, None),
    "fur_stack": (6.0, 6.0, 2.0, 0.0, "partial", None, None), "forge": (8.0, 6.0, 6.0, 0.0, "solid", None, None),
    "anvil": (6.6, 4.2, 4.7, 0.0, "solid", None, None),
    "rock": (3.0, 3.0, 2.0, 0.0, "solid", None, None), "bones": (3.0, 2.0, 0.5, 0.0, "passable", None, None),
    "bone_pile": (4.0, 4.0, 1.5, 0.0, "solid", None, None), "skull": (1.0, 1.0, 1.0, 0.0, "solid", None, None),
    "web": (4.0, 4.0, 4.0, 0.0, "passable", None, None), "mushroom": (2.0, 2.0, 3.0, 0.0, "solid", None, None),
    "log": (8.0, 2.0, 2.0, 0.0, "solid", None, None), "slime": (4.0, 4.0, 0.3, 0.0, "passable", None, None),
    "gem": (0.6, 0.6, 0.6, 0.0, "passable", None, None), "trophy": (2.0, 2.0, 2.0, 0.0, "solid", None, None),
    "weapon": (4.0, 1.0, 0.5, 0.0, "passable", None, None), "tool": (3.0, 1.0, 0.5, 0.0, "passable", None, None),
    "book": (1.0, 1.0, 0.3, 0.0, "passable", None, None),
}
#: Cultures the fixture gives their own lights, furniture and hangings (neutral has every kind).
CULTURES = ("goblin", "kobold", "gnoll", "froglok", "iksar", "troll", "ogre", "giant", "dragon", "human",
            "undead", "erudite", "dark_elf", "coldain", "dwarf")
OWN_CATEGORIES = ("light", "furniture", "hanging")


def _model(key: str, kind: str, mount: str, set_: str) -> Model:
    w, d, h, below, collision, over, wall = SIZES.get(kind, (2.0, 2.0, 2.0, 0.0, "solid", None, None))
    observed = {"scale": [1.0, 1.0, 1.0]}
    if over is not None:
        observed.update(over=[over, over, over], wall=[wall, wall, wall])
    tags = Tags(category=KINDS[kind], kind=kind, mount=mount, set=set_, era="classic", collision=collision,
                suits=("dungeon",), use="yes")
    return Model(key=key, name=key, archive="x_obj.s3d", wld="x_obj.wld", animation="static",
                 measured={"w": w, "d": d, "h": h, "below": below}, observed=observed, placed={"z": 3},
                 textures=(), tags=tags)


def fixture_catalogue(rules) -> Catalogue:
    """A usable model for every kind every line asks for at its Mount: a neutral one, and for
    lights, furniture and hangings one in each culture of ``CULTURES``."""
    models = {}
    for _where, kinds, mount in asks(rules):
        mt = MOUNTS_FILLING[mount][0] if mount != "raised" else "floor"
        for kind in kinds:
            sets = (NEUTRAL,) + (CULTURES if KINDS[kind] in OWN_CATEGORIES else ())
            for s in sets:
                key = f"{kind.upper()}_{mt.upper()}_{s.upper()}"
                models[key] = _model(key, kind, mt, s)
    return Catalogue(models=models, kinds=dict(KINDS), sets=(NEUTRAL,) + CULTURES)


@pytest.fixture(scope="module")
def rules():
    return load_decor()


@pytest.fixture(scope="module")
def fixture(rules):
    return fixture_catalogue(rules)


@pytest.fixture(scope="module")
def decorated(rules, fixture):
    """Every corpus room decorated at Normal and Dense, from the fixture catalogue."""
    return [(c, place(c, rules, fixture, control), control) for c in CORPUS for control in ("normal", "dense")]


# --- hand-built contexts -----------------------------------------------------------------------

def _grid(x0, y0, x1, y1, cell=2.0):
    xs = np.arange(x0 + cell / 2, x1, cell)
    ys = np.arange(y0 + cell / 2, y1, cell)
    gx, gy = np.meshgrid(xs, ys, indexing="ij")
    return xs, ys, gx, gy


def _walls(x0, y0, x1, y1, bottom=0.0, top=30.0, step=4.0, lintel=None):
    """Wall faces round a box, every ``step``; a face over ``lintel`` = (side, c0, c1, top) has
    its bottom at the door's top."""
    out = []
    sides = (("S", (x0, y0), (x1, y0), (0.0, 1.0)), ("N", (x0, y1), (x1, y1), (0.0, -1.0)),
             ("W", (x0, y0), (x0, y1), (1.0, 0.0)), ("E", (x1, y0), (x1, y1), (-1.0, 0.0)))
    for side, (ax, ay), (bx, by), (nx, ny) in sides:
        run = math.hypot(bx - ax, by - ay)
        n = max(1, int(math.ceil(run / step)))
        for k in range(n):
            f = (k + 0.5) / n
            x, y = ax + (bx - ax) * f, ay + (by - ay) * f
            b = bottom(x, y) if callable(bottom) else bottom
            t = top(x, y) if callable(top) else top
            if lintel and lintel[0] == side and lintel[1] <= (x if side in "SN" else y) <= lintel[2]:
                b = lintel[3]
            out.append(WallFace(x, y, nx, ny, b, t))
    return out


def box_room(w=60.0, d=50.0, h=30.0, *, room_type="", kind="chamber", race="", theme="", zone_type="dungeon",
             pois=(), features=(), walls=None, ceiling=True, seed=7, source="room", spine_half=4.0):
    """A plain box room from (0, 0) to (w, d) with one door in its south wall, a Spine from the
    door to the middle, flat floor at 0 and a ceiling ``h`` up."""
    from generators.decor.placement import _in_polygon
    xs, ys, gx, gy = _grid(0.0, 0.0, w, d)
    c0, c1 = w / 2 - 6, w / 2 + 6
    door = Door("S", c0, c1, 14.0, [(c0, 0.0, c1, d / 2)], (c0, 0.0, c1, 8.0))
    spine = (np.abs(gx - w / 2) <= spine_half) & (gy <= d / 2 + spine_half)
    feats, solid = [], np.zeros(gx.shape, bool)
    for f in features:
        feats.append(dict(f))
        if f["kind"] != "dais":
            solid |= _in_polygon(gx, gy, f["plan"])
    return RoomContext(
        id="hand", source=source, zone_type=zone_type, theme=theme, race=race, room_type=room_type, kind=kind,
        style="built", seed=seed, body_height=6.0, scales={"clutter": 5, "finish": 5, "structure": 5},
        box=(0.0, 0.0, 0.0, w, d, h), cell=2.0, origin=(float(xs[0]), float(ys[0])), floor=np.zeros(gx.shape),
        reached=~solid, ceiling=np.full(gx.shape, h) if ceiling else None, spine=spine,
        walls=walls if walls is not None else _walls(0.0, 0.0, w, d, top=h, lintel=("S", c0, c1, 14.0)),
        doors=[door], features=feats, pois=[dict(p) for p in pois])


def corridor(length=160.0, width=10.0):
    xs, ys, gx, gy = _grid(0.0, 0.0, length, width)
    doors = [Door("W", 0.0, width, 14.0, [], (0.0, 0.0, 6.0, width)),
             Door("E", 0.0, width, 14.0, [], (length - 6.0, 0.0, length, width))]
    walls = [w for w in _walls(0.0, 0.0, length, width, top=16.0) if w.ny != 0.0]     # the long walls
    return RoomContext(
        id="corridor_3", source=CORRIDOR, zone_type="dungeon", theme="", race="", room_type="", kind="",
        style="", seed=3, body_height=6.0, scales={}, box=(0.0, 0.0, 0.0, length, width, 16.0), cell=2.0,
        origin=(float(xs[0]), float(ys[0])), floor=np.zeros(gx.shape), reached=np.ones(gx.shape, bool),
        ceiling=np.full(gx.shape, 16.0), spine=np.ones(gx.shape, bool), walls=walls, doors=doors)


HAND = [
    box_room(room_type="barracks", kind="chamber", race="goblin", theme="fortress"),
    box_room(room_type="storeroom", kind="chamber", race="gnoll"),
    box_room(room_type="throne", kind="deep", race="kobold", theme="warren", h=40.0,
             pois=[{"purpose": "boss", "name": "", "x": 30.0, "y": 44.0, "z": 0.0, "feature": None}]),
    box_room(room_type="shrine", kind="chamber", race="froglok", theme="tomb",
             features=[{"kind": "dais", "plan": [[38.0, 30.0], [54.0, 30.0], [54.0, 46.0], [38.0, 46.0]],
                        "height": 2.0, "steps_side": "W"}],
             pois=[{"purpose": "altar", "name": "", "x": 46.0, "y": 38.0, "z": 0.0, "feature": 0}]),
    box_room(room_type="forge", kind="hall", race="giant", theme="lava_forge", w=90.0, d=70.0),
    box_room(kind="hub", zone_type="city", w=70.0),
]


@pytest.fixture(scope="module")
def hand(rules, fixture):
    return [(c, place(c, rules, fixture, control), control) for c in HAND for control in ("normal", "dense")]


def _in(r, x, y):
    return r[0] <= x <= r[2] and r[1] <= y <= r[3]


def _rect_gap(r, x, y):
    x0, y0, x1, y1 = r
    return math.hypot(max(x0 - x, 0.0, x - x1), max(y0 - y, 0.0, y - y1))


def _cell(c, x, y):
    i = int(round((x - c.origin[0]) / c.cell))
    j = int(round((y - c.origin[1]) / c.cell))
    assert 0 <= i < c.floor.shape[0] and 0 <= j < c.floor.shape[1], (x, y)
    return i, j


def _footprint(ctx, p):
    """The grid cells a floor Prop stands on: those whose middles lie in its plan (w along its
    own X, d along Y, turned by its yaw), and the cell under its origin."""
    c, s = math.cos(p.yaw), math.sin(p.yaw)
    gx, gy = np.meshgrid(ctx.origin[0] + np.arange(ctx.floor.shape[0]) * ctx.cell,
                         ctx.origin[1] + np.arange(ctx.floor.shape[1]) * ctx.cell, indexing="ij")
    lx, ly = c * (gx - p.x) + s * (gy - p.y), -s * (gx - p.x) + c * (gy - p.y)
    inside = (np.abs(lx) <= p.w / 2) & (np.abs(ly) <= p.d / 2)
    inside[_cell(ctx, p.x, p.y)] = True
    return [tuple(int(v) for v in ij) for ij in np.argwhere(inside)]


# --- P5: placement keeps the room open --------------------------------------------------------------

def test_every_room_passes_its_own_check(decorated, hand):
    """Req 13.4: reached floor stays joined, doors and POIs reached, in every corpus room."""
    bad = [(c.id, c.room_type, check(c, d)) for c, d, _ in decorated + hand if check(c, d)]
    assert not bad
    assert sum(len(d.props) for _, d, _ in decorated) > 4 * len(decorated)


def test_floor_props_stand_on_reached_floor_off_spine_throats_and_features(decorated, hand):
    from generators.decor.placement import _in_polygon
    n = 0
    for c, d, _ in decorated + hand:
        for p in d.props:
            if p.mount != "floor":
                continue
            n += 1
            for i, j in _footprint(c, p):
                cx, cy = c.cell_xy(i, j)
                assert c.reached[i, j], (c.id, p)
                assert not c.spine[i, j], (c.id, p)
                for door in c.doors:
                    assert not _in(door.clear, cx, cy), (c.id, p)
                    if p.step != "dressing":            # Dressing may stand in a Throat
                        assert not any(_in(t, cx, cy) for t in door.throats), (c.id, p)
                for f in c.features:
                    on = _in_polygon(np.array([cx]), np.array([cy]), f["plan"])[0]
                    assert not on or (f["kind"] == "dais" and (p.at == "on_dais" or p.step == "dressing")), (c.id, p)
            i, j = _cell(c, p.x, p.y)
            if c.ceiling is not None and not np.isnan(c.ceiling[i, j]):
                assert p.z + p.h <= c.ceiling[i, j] + 1e-6
    assert n > 500


def test_wall_props_hang_on_a_wall_clear_of_doors_at_stock_height(decorated, hand):
    n = 0
    for c, d, _ in decorated + hand:
        for p in d.props:
            if p.mount != "wall":
                continue
            n += 1
            # the wall face it backs on: near it and facing the way it faces (front into the room)
            faces = [w for w in c.walls if math.cos(p.yaw - math.atan2(w.ny, w.nx)) > 0.999
                     and math.hypot(p.x - w.x, p.y - w.y) <= p.w + 1.5]
            assert faces, (c.id, p)
            w = min(faces, key=lambda w: math.hypot(p.x - w.x, p.y - w.y))
            assert w.bottom - 0.01 <= p.z - p.below and p.z + p.h <= w.top, (c.id, p, w)
            for door in c.doors:
                if door.clear:
                    assert _rect_gap(door.clear, w.x, w.y) >= FRAME, (c.id, p, door)
    assert n > 100


def test_wall_lights_keep_their_spacing(decorated):
    from generators.decor.placement import ROOM_LIGHT_GAP, _spacing
    for c, d, _ in decorated:
        lights = [p for p in d.props if p.mount == "wall" and p.light]
        for a in range(len(lights)):
            for b in range(a + 1, len(lights)):
                gap = math.hypot(lights[a].x - lights[b].x, lights[a].y - lights[b].y)
                assert gap >= _spacing(c) * ROOM_LIGHT_GAP - 1e-6, c.id


def test_ceiling_props_hang_clear_of_head_height(decorated, hand):
    n = 0
    for c, d, _ in decorated + hand:
        for p in d.props:
            if p.mount != "ceiling":
                continue
            n += 1
            i, j = _cell(c, p.x, p.y)
            assert p.z - p.below >= c.floor[i, j] + HEAD_HEIGHT - 1e-6
            assert abs(p.z + p.h - c.ceiling[i, j]) < 1e-6
            assert not p.blocks
    assert n > 0


def test_groups_are_placed_whole(decorated, hand):
    """Every Group a room holds has its anchor and at least one member (every shipped Group's
    members draw one or more), all from one line."""
    n = 0
    for c, d, _ in decorated + hand:
        ids = {}
        for p in d.props:
            if p.group is not None:
                ids.setdefault(p.group, []).append(p)
        for props in ids.values():
            n += 1
            assert len(props) >= 2, (c.id, props)
            assert len({p.line for p in props}) == 1
            assert sum(p.at in ("round", "row", "beside", "stack") for p in props) == len(props) - 1
    assert n > 10


def test_a_group_that_cant_fit_drops_whole(rules, fixture):
    # A 30 x 24 room whose Spine runs 8 u each side of its middle: no room for a seated table.
    c = box_room(w=30.0, d=24.0, room_type="guard_post", kind="chamber", spine_half=8.0)
    drops = []
    for seed in range(12):
        d = place(c, rules, fixture, "dense", decor_seed=seed)
        assert not [p for p in d.props if p.group is not None]
        assert check(c, d) == []
        drops += [x for x in d.drops if x.what == "group:table_set"]
    assert drops and {x.reason for x in drops} == {"no spot"}


def test_misfits_drop_with_a_reason_and_never_fail(rules, fixture):
    empty = Catalogue(models={}, kinds=dict(KINDS), sets=(NEUTRAL,))
    for c in CORPUS[:20] + HAND:
        d = place(c, rules, empty, "dense")
        assert d.props == []
        assert all(x.reason.startswith("no model") for x in d.drops)
    # A room all Spine: nothing stands on its floor, and that's recorded.
    c = box_room(room_type="storeroom", spine_half=100.0)
    d = place(c, rules, fixture, "dense")
    assert not [p for p in d.props if p.mount == "floor"]
    assert d.drops and {x.reason for x in d.drops} <= {"no spot"}


# --- Req 5: one culture per room -------------------------------------------------------------------

def test_a_room_keeps_to_one_culture(decorated, hand, rules):
    seen = set()
    for c, d, _ in decorated + hand:
        sets = rules.sets.sets_for(c.zone_type, c.race, c.theme)
        assert {p.set for p in d.props} <= set(sets), (c.id, sets)
        cultures = d.cultures()
        for a in cultures:
            for b in cultures:
                assert rules.sets.may_share(a, b), (c.id, cultures)
        seen.update(cultures)
    assert {"goblin", "kobold", "gnoll", "iksar", "troll"} <= seen


def test_two_cultures_share_a_room_only_where_allowed(rules, fixture):
    """A froglok tomb names froglok and undead models, which may not share: it takes one, its
    race's, which binds first. A goblin tomb may mix goblin and undead (``allows``)."""
    c = box_room(room_type="ossuary", kind="chamber", race="froglok", theme="tomb")
    got = set()
    for seed in range(20):
        cultures = place(c, rules, fixture, "dense", decor_seed=seed).cultures()
        assert len(cultures) <= 1
        got.update(cultures)
    assert got == {"froglok"}
    assert rules.sets.may_share("goblin", "undead") and not rules.sets.may_share("froglok", "undead")


# --- P8: POIs are dressed ----------------------------------------------------------------------------

def test_dressing_at_every_poi_that_asks(decorated, hand, rules):
    asked = 0
    for c, d, _ in decorated + hand:
        for k, poi in enumerate(c.pois):
            if not rules.dressing_for(poi["purpose"]):
                continue
            asked += 1
            mine = [p for p in d.props if p.poi == k]
            if c.source == "room":
                assert mine, (c.id, poi)
            elif not mine:      # never silent: what it asked for is dropped, named
                assert [x for x in d.drops if x.poi == k], (c.id, poi)
            for p in mine:
                assert p.step == "dressing"
                if p.mount == "floor":      # never on the POI's own spot: the player stands there
                    assert math.hypot(p.x - poi["x"], p.y - poi["y"]) >= min(p.w, p.d) / 2 + PLAYER_HALF_WIDTH
    assert asked > 100


def test_dressing_comes_first(decorated):
    order = ("dressing", "group", "prop", "debris")
    for _c, d, _ in decorated:
        steps = [p.step for p in d.props]
        assert steps == sorted(steps, key=order.index)


def test_pois_stay_on_reached_floor(decorated):
    from generators.decor.placement import POI_REACH
    for c, d, _ in decorated:
        room = Room(c)
        for p in d.props:
            if p.blocks:
                room.blocked[room.rect_cells(p.x, p.y, p.yaw, p.w, p.d, PLAYER_HALF_WIDTH, clip=True)] = True
        after = room._joined(room.blocked)
        for poi in c.pois:
            near = np.hypot(room.gx - poi["x"], room.gy - poi["y"]) <= POI_REACH + c.cell / 2
            if (near & room.before).any():
                assert (near & after).any(), (c.id, poi)


# --- the stream, the control, corridors, rough walls --------------------------------------------------

def test_same_inputs_same_props_and_the_context_is_untouched(rules, fixture):
    for c in CORPUS[::7]:
        text = c.to_json()
        a = place(c, rules, fixture)
        b = place(RoomContext.from_json(text), rules, fixture)
        assert [p.to_dict() for p in a.props] == [p.to_dict() for p in b.props]
        assert c.to_json() == text


def test_a_decor_seed_rerolls_props(rules, fixture):
    c = next(c for c in CORPUS if c.room_type == "barracks")
    rolls = {tuple((p.key, round(p.x, 1), round(p.y, 1)) for p in place(c, rules, fixture, decor_seed=s).props)
             for s in range(5)}
    assert len(rolls) > 1


def test_the_control_moves_the_count(rules, fixture):
    def total(control):
        return sum(len(place(c, rules, fixture, control).props) for c in CORPUS)
    assert total("none") == 0
    assert total("sparse") < total("normal") < total("dense")


def test_a_corridor_gets_wall_lights_by_spacing(rules, fixture):
    from generators.decor.placement import DEFAULT_LIGHT_SPACING
    c = corridor()
    d = place(c, rules, fixture)
    assert d.props and all(p.mount == "wall" and p.light for p in d.props)
    gaps = [math.hypot(a.x - b.x, a.y - b.y) for a in d.props for b in d.props if a is not b]
    assert not gaps or min(gaps) >= DEFAULT_LIGHT_SPACING - 1e-6
    assert len(d.props) >= int(160 / DEFAULT_LIGHT_SPACING) - 1
    assert check(c, d) == []


def test_wall_props_follow_a_rough_walls_own_height(rules, fixture):
    """Wall spots read each sampled wall face's own bottom and top: where the wall is low no
    banner hangs, and nothing hangs over the door (a lintel) or in its frame."""
    w, d = 60.0, 50.0
    c0, c1 = w / 2 - 6, w / 2 + 6
    walls = _walls(0.0, 0.0, w, d, top=lambda x, y: 9.0 if x < 12 else 30.0, lintel=("S", c0, c1, 14.0))
    c = box_room(w=w, d=d, walls=walls, room_type="throne", kind="deep")
    n = 0
    for seed in range(8):
        dec = place(c, rules, fixture, "dense", decor_seed=seed)
        for p in dec.props:
            if p.mount != "wall":
                continue
            n += 1
            assert p.x >= 12 - 2.5 or p.z + p.h <= 9.0, p
            assert not (c0 - FRAME <= p.x <= c1 + FRAME and p.y < 4.0), p
        assert check(c, dec) == []
    assert n > 8


# --- P13: placement reads only a RoomContext -----------------------------------------------------------

ALLOWED = {"generators.room_context", "generators.decor.rules", "generators.decor.catalogue"}


def test_placement_imports_nothing_from_the_room_stage_but_room_context():
    """P13: placement's own imports are the standard library, numpy and scipy, the decor
    package and ``generators/room_context.py``: never the room stage (layouts, geometry, the
    ZoneSpec, the builder), the gate or a mesh reader."""
    tree = ast.parse((ROOT / "generators" / "decor" / "placement.py").read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
    ours = {n for n in names if n.split(".")[0] in ("generators", "analyzer", "core", "ai", "server", "scripts")}
    assert ours <= ALLOWED, ours - ALLOWED
    assert "generators.room_context" in ours
    others = {n.split(".")[0] for n in names} - {"generators", "__future__", "math", "random", "dataclasses",
                                                  "typing"}
    assert others <= {"numpy", "scipy"}, others


def test_imports_place_takes_a_context_and_no_zone():
    import inspect
    assert list(inspect.signature(place).parameters) == ["context", "rules", "catalogue", "control", "decor_seed"]


def test_sizes_come_from_the_catalogue(fixture):
    sz = size_of(fixture.models["TORCH_WALL_NEUTRAL"])
    assert (sz.w, sz.d, sz.h, sz.over, sz.wall) == (3.4, 0.9, 5.2, 5.5, 2.3)


def test_a_decorated_room_is_plain_data(decorated):
    import json
    _c, d, _ = decorated[0]
    back = json.loads(json.dumps(d.to_dict()))
    assert back["room"] == d.room and len(back["props"]) == len(d.props)
    assert isinstance(d, Decorated)

