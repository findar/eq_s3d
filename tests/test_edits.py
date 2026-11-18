"""
tests/test_edits.py
-------------------
Applying an edit (zone-generator-edits Req 2.1-2.6, task 3): ``generators.edits.apply_edits``.

Each spec-only op changes only its own fields of a copy (the input is unchanged), the same
arguments give the same result, and the Affected_Set is Req 2.2-2.3's. ``add_lock`` places its
lock and key by the layout's gating rule (``layout.gate_*``) and rejects a lock it can't place
solvably. And for each partial op, building the edited spec with the parent's saved stages
equals a full build of it, footer aside, on a Graph dungeon and a city (needs the install).
"""

from __future__ import annotations

import copy
import json

import pytest

import generators.edits as edits_mod
from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators.builder import ZoneBuilder
from generators.decor.stock import eq_path_from_env
from generators.edits import FULL, PARTIAL, apply_edits, gate_graph, solvable
from generators.layout import LayoutGenerator
from generators.rebuild import saved_stages
from generators.zone_spec import ZoneSpec

#: label -> (ZonePlan fields, seed). The graph dungeon has a lock to remove.
PLANS = {
    "graph": (dict(zone_type="dungeon", room_count=12, layout="graph", locks=1), 2),
    "city": (dict(zone_type="city"), 5),
    "temple_locks": (dict(zone_type="dungeon", room_count=9, locks=2, dungeon_theme="temple",
                          dungeon_race="troll", verticality="dramatic", layout="classic"), 11),
}


def _doc(label: str) -> dict:
    fields, seed = PLANS[label]
    spec = plan_to_spec(ZonePlan(name=f"ed_{label}", **fields).validate(), seed=seed)
    spec.decor = "normal"
    return {**spec.to_dict(), "decor_layers": []}


@pytest.fixture(scope="module")
def docs():
    return {label: _doc(label) for label in PLANS}


def _diff(a: dict, b: dict) -> set:
    """The top-level keys whose values differ."""
    return {k for k in set(a) | set(b) if a.get(k) != b.get(k)}


def _room_diff(a: dict, b: dict) -> dict:
    """room id -> the room keys that differ."""
    out = {}
    for ra, rb in zip(a["rooms"], b["rooms"]):
        keys = {k for k in set(ra) | set(rb) if ra.get(k) != rb.get(k)}
        if keys:
            out[ra["id"]] = keys
    return out


def _not_entrance(doc: dict, n: int = 2) -> str:
    return next(r["id"] for r in doc["rooms"][n:] if r.get("role") != "entrance")


# ---------------------------------------------------------------------------
# Each op: only its own fields
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label", ["graph", "city"])
def test_each_op_changes_only_its_fields(docs, label):
    doc = docs[label]
    before = copy.deepcopy(doc)
    room = _not_entrance(doc)
    every = [r["id"] for r in doc["rooms"]]
    cases = [
        ({"op": "set_purpose", "target": room, "type": "forge"},
         {"rooms"}, {room: {"semantic_type"}}, ["semantic_type"], [room]),
        ({"op": "reroll_room", "target": room},
         {"room_decor_seeds"}, {}, ["room_decor_seeds"], [room]),
        ({"op": "reroll_decor"}, {"decor_seed"}, {}, ["decor_seed"], every),
        ({"op": "set_decor_level", "level": "dense"}, {"decor"}, {}, ["decor"], every),
        ({"op": "add_lock", "target": room}, {"gates"}, {}, ["gates"], []),
    ]
    for op, keys, rooms, changed, affected in cases:
        res = apply_edits(doc, [op], seed=7, version=1)
        assert res.how == PARTIAL, (op, res.notes)
        assert _diff(doc, res.doc) == keys, op
        assert _room_diff(doc, res.doc) == rooms, op
        assert res.changed == changed and res.affected_rooms == affected, op
        assert res.affected_corridors == [] and not res.rejected, op
        # Every room and corridor keeps its id (Req 2.6).
        assert [r["id"] for r in res.doc["rooms"]] == every
        assert [c["id"] for c in res.doc["corridors"]] == [c["id"] for c in doc["corridors"]]
        # The same inputs, the same result (Req 2.1).
        assert apply_edits(doc, [op], seed=7, version=1) == res
    assert doc == before


def test_draws_are_salted_by_seed_version_and_index(docs):
    doc = docs["graph"]
    room = _not_entrance(doc)
    op = {"op": "reroll_room", "target": room}
    a = apply_edits(doc, [op], 7, 1).doc["room_decor_seeds"][room]
    assert apply_edits(doc, [op], 7, 1).doc["room_decor_seeds"][room] == a
    assert apply_edits(doc, [op], 8, 1).doc["room_decor_seeds"][room] != a
    assert apply_edits(doc, [op], 7, 2).doc["room_decor_seeds"][room] != a
    assert apply_edits(doc, [{"op": "set_decor_level", "level": "dense"}, op],
                       7, 1).doc["room_decor_seeds"][room] != a


def test_reroll_decor_clears_room_decor_seeds(docs):
    """Step 16's rule (``rebuild.room_seeds_after``): a new decor seed resets every room's."""
    doc = docs["graph"]
    room = _not_entrance(doc)
    res = apply_edits(doc, [{"op": "reroll_room", "target": room}, {"op": "reroll_decor"}], 7, 1)
    assert "room_decor_seeds" not in res.doc and res.doc["decor_seed"] != doc.get("decor_seed")
    assert res.changed == ["room_decor_seeds", "decor_seed"]
    assert [o["op"] for o in res.applied] == ["reroll_room", "reroll_decor"]
    assert all("decor_seed" in o for o in res.applied)          # the drawn seeds are recorded


def test_regenerate_is_full_with_a_new_seed_and_skips_the_rest(docs):
    doc = docs["graph"]
    res = apply_edits(doc, [{"op": "set_decor_level", "level": "dense"}, {"op": "regenerate"}],
                      7, 1)
    assert res.how == FULL and res.doc == doc and res.changed == ["seed"]
    assert isinstance(res.seed, int) and res.seed != doc["seed"]
    assert res.affected_rooms == [r["id"] for r in doc["rooms"]]
    assert res.affected_corridors == [c["id"] for c in doc["corridors"]]
    assert [r["op"]["op"] for r in res.rejected] == ["set_decor_level"]
    pinned = apply_edits(doc, [{"op": "regenerate", "seed": 42}], 7, 1)
    assert pinned.seed == 42 and pinned.applied == [{"op": "regenerate", "seed": 42}]


@pytest.mark.parametrize("op", [
    {"op": "add_room"}, {"op": "remove_room", "target": "room_1"},
    {"op": "add_region", "target": "room_1", "kind": "water"},
    {"op": "remove_region", "target": "room_1"}, {"op": "set_verticality", "level": "flat"},
    {"op": "set_topology", "shape": "looped"},
])
def test_ops_not_yet_supported_are_rejected_with_a_note(docs, op):
    doc = docs["graph"]
    res = apply_edits(doc, [op, {"op": "set_decor_level", "level": "sparse"}], 7, 1)
    assert res.notes[0] == f"{op['op']} is not yet supported"
    assert [r["op"]["op"] for r in res.rejected] == [op["op"]]
    assert res.how == PARTIAL and res.changed == ["decor"]       # the rest still apply


def test_bad_ops_are_rejected_and_nothing_applied(docs):
    doc = docs["city"]
    res = apply_edits(doc, [{"op": "nope"}, {"op": "set_purpose", "target": "room_99",
                                             "type": "forge"}, "x",
                            {"op": "set_decor_level", "level": doc["decor"]}], 7, 1)
    assert res.how is None and res.applied == [] and len(res.rejected) == 4
    assert res.doc == doc and res.changed == [] and res.affected_rooms == []


# ---------------------------------------------------------------------------
# Locks: the gating rule
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label", ["graph", "temple_locks"])
def test_the_lifted_rule_reproduces_the_layouts_gates(docs, label):
    """The saved spec's graph (``gate_graph``) is the one the layout gated: running the
    layout's gating again on it gives the saved Gates."""
    doc = docs[label]
    spec = ZoneSpec.from_dict(copy.deepcopy(doc))
    saved = spec.to_dict()["gates"]
    spec.gates = []
    g = gate_graph(doc)
    LayoutGenerator._apply_gating(None, spec, spec.rooms, g.edges, g.entrance,
                                  n_locks=PLANS[label][0]["locks"])
    assert spec.to_dict()["gates"] == saved
    assert solvable(doc)


@pytest.mark.parametrize("label", ["graph", "city", "temple_locks"])
def test_add_lock_keeps_every_key_before_its_lock(docs, label):
    doc = docs[label]
    g = gate_graph(doc)
    placed = 0
    for room in g.ids:
        res = apply_edits(doc, [{"op": "add_lock", "target": room}], 7, 1)
        if res.how is None:
            assert len(res.notes) == 1 and res.notes[0].startswith("add_lock: ")
            continue
        placed += 1
        new = res.doc["gates"][-1]
        assert res.doc["gates"][:-1] == doc["gates"]
        assert solvable(res.doc)
        assert new["key_room_id"] != room
        assert res.affected_rooms == [] and res.affected_corridors == []
        assert new["tier"] == max([x["tier"] for x in doc["gates"]], default=-1) + 1
        assert new["id"] not in {x["id"] for x in doc["gates"]}
    assert placed >= 2
    # Every room locked in turn, one edit: still solvable.
    res = apply_edits(doc, [{"op": "add_lock", "target": r} for r in g.ids], 7, 1)
    assert solvable(res.doc) and len(res.doc["gates"]) > len(doc["gates"])


def test_add_lock_rejects_the_entrance_and_a_locked_way_in(docs):
    doc = docs["graph"]
    entrance = next(r["id"] for r in doc["rooms"] if r["role"] == "entrance")
    res = apply_edits(doc, [{"op": "add_lock", "target": entrance}], 7, 1)
    assert res.how is None and "entrance" in res.notes[0]
    gate = doc["gates"][0]
    behind = next(c for c in doc["corridors"] if c["id"] == gate["corridor_id"])
    g = gate_graph(doc)
    deeper = max((behind["from_room"], behind["to_room"]),
                 key=lambda r: g.depths[g.ids.index(r)])
    res = apply_edits(doc, [{"op": "add_lock", "target": deeper}], 7, 1)
    assert res.how is None and "already locked" in res.notes[0]


def test_an_unsolvable_lock_is_rejected(docs, monkeypatch):
    """A key rule that puts the key behind its own lock: the solvability check refuses it."""
    doc = docs["city"]
    monkeypatch.setattr(edits_mod._layout, "gate_key_room",
                        lambda depths, entrance, far, locked: min(far))
    room = _not_entrance(doc)
    res = apply_edits(doc, [{"op": "add_lock", "target": room}], 7, 1)
    assert res.how is None and res.doc == doc
    assert "keeps every key before its lock" in res.notes[0]


def test_solvable_sees_a_deadlock(docs):
    doc = copy.deepcopy(docs["temple_locks"])
    assert solvable(doc)
    a, b = doc["gates"]
    # Each key behind the other's lock... or behind its own.
    g = gate_graph(doc)
    far_room = {}
    for gt in (a, b):
        c = next(c for c in doc["corridors"] if c["id"] == gt["corridor_id"])
        far_room[gt["id"]] = max((c["from_room"], c["to_room"]),
                                 key=lambda r: g.depths[g.ids.index(r)])
    a["key_room_id"] = far_room[a["id"]]
    assert not solvable(doc)


def test_remove_lock(docs):
    doc = docs["temple_locks"]
    every = apply_edits(doc, [{"op": "remove_lock"}], 7, 1)
    assert every.doc["gates"] == [] and every.changed == ["gates"] and every.how == PARTIAL
    gate = doc["gates"][0]
    cor = next(c for c in doc["corridors"] if c["id"] == gate["corridor_id"])
    g = gate_graph(doc)
    room = max((cor["from_room"], cor["to_room"]), key=lambda r: g.depths[g.ids.index(r)])
    one = apply_edits(doc, [{"op": "remove_lock", "target": room}], 7, 1)
    assert one.doc["gates"] == doc["gates"][1:] and one.affected_rooms == []
    assert _diff(doc, one.doc) == {"gates"}
    none = apply_edits(docs["city"], [{"op": "remove_lock"}], 7, 1)
    assert none.how is None and "no locks" in none.notes[0]


# ---------------------------------------------------------------------------
# A partial op built with the parent's stages equals a full build (needs the install)
# ---------------------------------------------------------------------------

def _ops(doc: dict) -> dict:
    room = _not_entrance(doc)
    lockable = next(r for r in gate_graph(doc).ids
                    if apply_edits(doc, [{"op": "add_lock", "target": r}], 7, 1).how)
    ops = {
        "set_purpose": {"op": "set_purpose", "target": room, "type": "forge"},
        "reroll_room": {"op": "reroll_room", "target": room},
        "reroll_decor": {"op": "reroll_decor"},
        "set_decor_level": {"op": "set_decor_level", "level": "dense"},
        "add_lock": {"op": "add_lock", "target": lockable},
    }
    if doc["gates"]:
        ops["remove_lock"] = {"op": "remove_lock"}
    return ops


@pytest.fixture(scope="module")
def parents(tmp_path_factory):
    """The graph dungeon and the city, each built once in full: the saved spec dict (as the
    pipeline writes it) and the build folder holding its stages."""
    if eq_path_from_env() is None:
        pytest.skip("EQ_PATH is not set (no EQ install to read)")
    out = {}
    for label in ("graph", "city"):
        fields, seed = PLANS[label]
        spec = plan_to_spec(ZonePlan(name=f"ed_{label}", **fields).validate(), seed=seed)
        spec.decor = "normal"
        folder = tmp_path_factory.mktemp(f"parent_{label}")
        ZoneBuilder(spec).build(output_dir=folder, write_glb=False)
        out[label] = ({**spec.to_dict(), "decor_layers": []}, folder)
    return out


def _build(doc: dict, folder, saved=None):
    spec = ZoneSpec.from_dict(json.loads(json.dumps({k: v for k, v in doc.items()
                                                     if k != "decor_layers"})))
    result = ZoneBuilder(spec).build(output_dir=folder, write_glb=False, saved=saved)
    side = json.loads(result.sidecar_path.read_text(encoding="utf-8"))
    return result.eqg_path.read_bytes()[:-4], side


_PARTIAL_OPS = ["set_purpose", "reroll_room", "reroll_decor", "set_decor_level", "add_lock"]


@pytest.mark.slow
@pytest.mark.parametrize("label, op_name", [("graph", o) for o in _PARTIAL_OPS + ["remove_lock"]]
                         + [("city", o) for o in _PARTIAL_OPS])     # the city has no lock
def test_a_partial_edit_equals_a_full_build(parents, tmp_path, label, op_name):
    doc, folder = parents[label]
    res = apply_edits(doc, [_ops(doc)[op_name]], 7, 1)
    assert res.how == PARTIAL and not res.rejected, res.notes
    name = doc["name"].lower()
    partial = _build(res.doc, tmp_path / "partial", saved_stages(folder, name))
    full = _build(res.doc, tmp_path / "full")
    assert partial == full
    parent = ((folder / f"{name}.eqg").read_bytes()[:-4],
              json.loads((folder / f"{name}.zone.json").read_text(encoding="utf-8")))
    assert partial != parent        # the edit did change the build
