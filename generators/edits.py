"""
generators/edits.py
-------------------
Applying an edit (zone-generator-edits Req 2, design "Applying"): ``apply_edits(doc, ops, seed,
version)`` turns a version's saved spec (``<name>.spec.json``: ``ZoneSpec.to_dict`` plus
``decor_layers``) and a list of ops (``ai.edits``) into the edited spec dict, the Affected_Set,
the notes, and how the next version is built.

    op               spec change                                         how
    set_purpose      the room's ``semantic_type``                        partial
    reroll_room      ``room_decor_seeds[room]`` (a drawn seed)           partial
    reroll_decor     ``decor_seed`` (drawn), clearing room decor seeds   partial
    set_decor_level  ``decor``                                           partial
    add_lock         ``gates`` (the layout's gating rule)                partial
    remove_lock      ``gates``                                           partial
    regenerate       none: a new zone from the parent's request,         full
                     at ``EditResult.seed``
    resize ops       one room's box, its corridors' ends, the rooms'     full
                     walls and features (``generators.resize``)

``partial`` means the parent's saved stages (its TER and textures) build the edited spec; a
partial edit that turns out to change the TER is caught by the build's ``StaleStages`` and built
in full by the caller (archive decision 4). Every random draw comes from
``random.Random(f"{seed}:{version}:{i}")`` (``i``: the op's index), so the same edit of the same
version gives the same result and a retry with the next ``seed`` draws afresh.

Everything here is pure: the input dict is never changed, and nothing is built or written.
"""

from __future__ import annotations

import copy
import random
from dataclasses import asdict, dataclass, field
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from ai.edits import validate_op
from ai.schema import SEED_MAX
from generators import layout as _layout
from generators.rebuild import room_seeds_after

__all__ = ["EditResult", "FULL", "PARTIAL", "RESIZE_OPS", "UNSUPPORTED", "apply_edits",
           "gate_graph", "solvable"]

PARTIAL = "partial"
FULL = "full"

#: The resize ops: ``_resize`` applies them through ``generators.resize``.
RESIZE_OPS = ("widen_room", "narrow_room", "taller_room", "lower_room")

#: Ops ``ai.edits`` recognises that no build applies yet (amendment A3).
UNSUPPORTED = ("add_room", "remove_room", "add_region", "remove_region", "set_verticality",
               "set_topology")


@dataclass
class EditResult:
    """What ``apply_edits`` made of an edit.

    ``doc``: the edited spec dict (a deep copy; the input is unchanged). ``affected_rooms`` /
    ``affected_corridors``: the Affected_Set, in the spec's order. ``notes``: one line per op
    applied or rejected, in op order. ``how``: ``"partial"`` (the parent's stages build it),
    ``"full"`` (a full build), or ``None`` when no op applied. ``changed``: the spec fields the
    applied ops changed (the version block's ``changed``), in op order. ``applied``: the ops
    applied (validated, with any drawn seed filled in). ``rejected``: ``{op, reason}`` for each
    op that didn't apply. ``seed``: ``regenerate``'s new zone seed, else ``None``."""
    doc: Dict[str, Any]
    affected_rooms: List[str] = field(default_factory=list)
    affected_corridors: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    how: Optional[str] = None
    changed: List[str] = field(default_factory=list)
    applied: List[Dict[str, Any]] = field(default_factory=list)
    rejected: List[Dict[str, Any]] = field(default_factory=list)
    seed: Optional[int] = None

    @property
    def affected(self) -> Dict[str, List[str]]:
        """The Affected_Set as the sidecar's ``edit`` block holds it."""
        return {"rooms": list(self.affected_rooms), "corridors": list(self.affected_corridors)}


class _Rejected(Exception):
    """An op that can't apply to this spec; its message is the note."""


@dataclass
class _Done:
    """One applied op: the fields it changed, its Affected_Set and its note."""
    changed: Sequence[str]
    note: str
    rooms: Sequence[str] = ()
    corridors: Sequence[str] = ()
    how: str = PARTIAL
    op: Optional[Dict[str, Any]] = None     # the op as applied, when it differs from the input


# ---------------------------------------------------------------------------
# Spec helpers
# ---------------------------------------------------------------------------

def _rooms(doc: Mapping[str, Any]) -> List[Dict[str, Any]]:
    return [r for r in doc.get("rooms") or () if isinstance(r, dict)]


def _room(doc: Mapping[str, Any], room_id: str) -> Dict[str, Any]:
    for r in _rooms(doc):
        if r.get("id") == room_id:
            return r
    raise _Rejected(f"no room {room_id!r}")


def _all_room_ids(doc: Mapping[str, Any]) -> List[str]:
    return [str(r.get("id")) for r in _rooms(doc)]


def _draw_seed(rng: random.Random, old: Optional[int] = None) -> int:
    s = rng.randint(0, SEED_MAX)
    while s == old:
        s = rng.randint(0, SEED_MAX)
    return s


# ---------------------------------------------------------------------------
# The gating rule on a saved spec
# ---------------------------------------------------------------------------

@dataclass
class _Graph:
    ids: List[str]                       # room ids, by index
    depths: List[int]
    entrance: int
    edges: List[Tuple[int, int]]         # one per corridor joining two rooms, in corridor order
    edge_corr: List[str]                 # the corridor id of each edge
    #: edge index -> (upper, lower) for a corridor with a ``drop`` (``layout.drop_arc``)
    oneway: Dict[int, Tuple[int, int]] = field(default_factory=dict)


def gate_graph(doc: Mapping[str, Any]) -> _Graph:
    """The room graph the layout gated: rooms by index, the corridors joining two rooms as
    edges (in corridor order, as the layout made them), and the entrance (the room whose role is
    ``entrance``, else the shallowest). A corridor with a ``drop`` is one-way, from the room
    whose ``floor_z`` is higher to the other (``layout.drop_arc``)."""
    rooms = _rooms(doc)
    ids = [str(r.get("id")) for r in rooms]
    index = {rid: i for i, rid in enumerate(ids)}
    depths = [int(r.get("graph_depth") or 0) for r in rooms]
    entrance = next((i for i, r in enumerate(rooms) if r.get("role") == "entrance"), None)
    if entrance is None:
        entrance = min(range(len(rooms)), key=lambda i: depths[i]) if rooms else 0
    edges, corr, drops = [], [], []
    for c in doc.get("corridors") or ():
        a, b = index.get(c.get("from_room")), index.get(c.get("to_room"))
        if a is None or b is None or a == b:
            continue
        edges.append((a, b))
        corr.append(str(c.get("id")))
        drops.append(_layout.corridor_drop(c))
    floors = [float(r.get("floor_z") or 0.0) for r in rooms]
    return _Graph(ids, depths, entrance, edges, corr, _layout.gate_oneway(edges, drops, floors))


def _directed_solvable(g: _Graph, gates: Sequence[Mapping[str, Any]]) -> bool:
    """``solvable`` on a graph with one-way edges: ``layout.gate_solvable`` (no state the
    player can reach is stranded short of a room)."""
    edge_of = {cid: k for k, cid in enumerate(g.edge_corr)}
    index = {rid: i for i, rid in enumerate(g.ids)}
    locks: Dict[int, Set[str]] = {}
    keys: Dict[int, Set[str]] = {}
    for gt in gates:
        gid = str(gt.get("id"))
        k = edge_of.get(str(gt.get("corridor_id")))
        if k is not None:
            locks.setdefault(k, set()).add(gid)
        r = index.get(gt.get("key_room_id"))
        if r is not None:
            keys.setdefault(r, set()).add(gid)
    return _layout.gate_solvable(g.edges, g.entrance, locks, keys, g.oneway)


def _reach(g: _Graph, gates: Sequence[Mapping[str, Any]], keyed: bool = True) -> Set[int]:
    """The rooms a player reaches from the entrance: through an ungated corridor, or a gated one
    once every key it needs is picked up (``keyed=False``: gates ignored)."""
    locks: Dict[str, List[str]] = {}
    if keyed:
        for gt in gates:
            locks.setdefault(str(gt.get("corridor_id")), []).append(str(gt.get("id")))
    key_room = {str(gt.get("id")): gt.get("key_room_id") for gt in gates}
    reached = {g.entrance}
    while True:
        held = {gid for gid, room in key_room.items() if room in {g.ids[i] for i in reached}}
        grown = False
        for (a, b), cid in zip(g.edges, g.edge_corr):
            if (a in reached) == (b in reached):
                continue
            if all(gid in held for gid in locks.get(cid, ())):
                reached |= {a, b}
                grown = True
        if not grown:
            return reached


def solvable(doc: Mapping[str, Any], gates: Optional[Sequence[Mapping[str, Any]]] = None) -> bool:
    """Every key before its lock: with ``gates`` (default: the spec's), the player reaches every
    room the entrance reaches with no gates at all. With a drop corridor (one-way, step 31), every
    state the player can reach (room, keys held) must still reach every such room: no key past a
    drop with no way back to its lock."""
    g = gate_graph(doc)
    if not g.ids:
        return True
    gates = list(doc.get("gates") or ()) if gates is None else list(gates)
    if g.oneway:
        return _directed_solvable(g, gates)
    return _reach(g, gates) == _reach(g, gates, keyed=False)


def _tree(g: _Graph):
    return _layout.gate_tree(g.edges, g.entrance, g.oneway)


def _way_in(g: _Graph, parent: Mapping[int, Optional[int]], room: int) -> Optional[str]:
    """The corridor of ``room``'s tree edge in (the last one joining the pair, as the layout's
    ``corr_by_pair`` keeps; of those, one walkable from the parent into ``room``), or ``None``
    for the entrance or a room it can't reach."""
    par = parent.get(room)
    if par is None:
        return None
    found = None
    for k, ((a, b), cid) in enumerate(zip(g.edges, g.edge_corr)):
        if {a, b} == {room, par} and g.oneway.get(k, (par, room)) == (par, room):
            found = cid
    return found


def _add_lock(doc: Dict[str, Any], op: Mapping[str, Any], rng: random.Random) -> _Done:
    target = op["target"]
    g = gate_graph(doc)
    n = len(g.ids)
    room = g.ids.index(target)
    if n < 3 or not g.edges:
        raise _Rejected("add_lock: a zone needs 3 rooms joined by corridors to take a lock")
    if room == g.entrance:
        raise _Rejected(f"add_lock: {target} is the entrance; it has no way in to lock")
    parent, _order, children = _tree(g)
    corr_id = _way_in(g, parent, room)
    if corr_id is None:
        raise _Rejected(f"add_lock: {target} can't be reached from the entrance")
    gates = [dict(x) for x in doc.get("gates") or ()]
    if any(x.get("corridor_id") == corr_id for x in gates):
        raise _Rejected(f"add_lock: the way into {target} ({corr_id}) is already locked")
    far = _layout.gate_subtree(children, room)
    if not _layout.gate_lockable(far, n):
        raise _Rejected(f"add_lock: a lock on the way into {target} would shut off every room "
                        f"but the entrance")
    # Keys go in front of every lock there is (the layout's rule, with every existing lock as
    # one placed before this one).
    locked_far: Set[int] = set()
    for x in gates:
        i = g.edge_corr.index(x["corridor_id"]) if x.get("corridor_id") in g.edge_corr else None
        if i is None:
            continue
        a, b = g.edges[i]
        child = a if parent.get(a) == b else b if parent.get(b) == a else None
        if child is not None:
            locked_far |= _layout.gate_subtree(children, child)
    key = _layout.gate_key_room(g.depths, g.entrance, far, locked_far)
    tier = max((int(x.get("tier") or 0) for x in gates), default=-1) + 1
    taken = {x.get("id") for x in gates}
    k = tier
    while f"gate_{k}" in taken:
        k += 1
    cor = next(c for c in doc["corridors"] if str(c.get("id")) == corr_id)

    def make(i: int) -> Dict[str, Any]:
        return asdict(_layout.gate_spec(f"gate_{k}", SimpleNamespace(**cor),
                                        SimpleNamespace(**_room(doc, g.ids[i])), tier))

    gate = make(key)
    if g.oneway:
        # One-way edges: the first key room (the layout's order) that strands no one.
        for cand in _layout.gate_key_rooms(key, g.depths, g.entrance, far, locked_far):
            trial = make(cand)
            if _directed_solvable(g, gates + [trial]):
                gate = trial
                break
    key_room = _room(doc, gate["key_room_id"])
    if not solvable(doc, gates + [gate]):
        raise _Rejected(f"add_lock: no key room for a lock on the way into {target} keeps "
                        f"every key before its lock")
    doc["gates"] = gates + [gate]
    return _Done(["gates"], f"locked the way into {target} ({corr_id}); its key is in "
                            f"{key_room['id']}")


def _remove_lock(doc: Dict[str, Any], op: Mapping[str, Any], rng: random.Random) -> _Done:
    gates = [dict(x) for x in doc.get("gates") or ()]
    target = op.get("target")
    if not gates:
        raise _Rejected("remove_lock: the zone has no locks")
    if target is None:
        doc["gates"] = []
        return _Done(["gates"], f"removed every lock ({len(gates)})")
    g = gate_graph(doc)
    parent, _order, _children = _tree(g)
    way_in = _way_in(g, parent, g.ids.index(target))
    drop = [x for x in gates if way_in is not None and x.get("corridor_id") == way_in]
    if not drop:
        # No lock on its way in: the locks on any corridor at the room.
        touching = {str(c.get("id")) for c in doc.get("corridors") or ()
                    if target in (c.get("from_room"), c.get("to_room"))}
        drop = [x for x in gates if x.get("corridor_id") in touching]
    if not drop:
        raise _Rejected(f"remove_lock: no lock at {target}")
    gone = {x.get("id") for x in drop}
    doc["gates"] = [x for x in gates if x.get("id") not in gone]
    return _Done(["gates"], f"removed the lock on {', '.join(sorted(str(x['corridor_id']) for x in drop))} "
                            f"at {target}")


# ---------------------------------------------------------------------------
# The other ops
# ---------------------------------------------------------------------------

def _a(word: str) -> str:
    """``word`` with its article: "an ossuary", "a crypt"."""
    return f"{'an' if word[:1].lower() in 'aeiou' else 'a'} {word}"


def _set_purpose(doc: Dict[str, Any], op: Mapping[str, Any], rng: random.Random) -> _Done:
    room = _room(doc, op["target"])
    if room.get("semantic_type") == op["type"]:
        raise _Rejected(f"set_purpose: {room['id']} is already {_a(op['type'])}")
    room["semantic_type"] = op["type"]
    return _Done(["semantic_type"], f"{room['id']} is now {_a(op['type'])}", rooms=[room["id"]])


def _reroll_room(doc: Dict[str, Any], op: Mapping[str, Any], rng: random.Random) -> _Done:
    rid = _room(doc, op["target"])["id"]
    old = (doc.get("room_decor_seeds") or {}).get(rid)
    seed = _draw_seed(rng, old)
    seeds = room_seeds_after(doc.get("room_decor_seeds"),
                             {"room_decor": {"room": rid, "decor_seed": seed}})
    doc["room_decor_seeds"] = seeds
    return _Done(["room_decor_seeds"], f"new decor for {rid} (seed {seed})", rooms=[rid],
                 op={**op, "decor_seed": seed})


def _reroll_decor(doc: Dict[str, Any], op: Mapping[str, Any], rng: random.Random) -> _Done:
    seed = _draw_seed(rng, doc.get("decor_seed"))
    doc["decor_seed"] = seed
    seeds = room_seeds_after(doc.get("room_decor_seeds"), {"decor_seed": seed})
    doc.pop("room_decor_seeds", None)       # rebuild._apply's rule: the key only when set
    if seeds:
        doc["room_decor_seeds"] = seeds
    return _Done(["decor_seed"], f"new decor everywhere (decor seed {seed})",
                 rooms=_all_room_ids(doc), op={**op, "decor_seed": seed})


def _set_decor_level(doc: Dict[str, Any], op: Mapping[str, Any], rng: random.Random) -> _Done:
    if doc.get("decor") == op["level"]:
        raise _Rejected(f"set_decor_level: decor is already {op['level']}")
    doc["decor"] = op["level"]
    return _Done(["decor"], f"decor level {op['level']}", rooms=_all_room_ids(doc))


def _regenerate(doc: Dict[str, Any], op: Mapping[str, Any], rng: random.Random) -> _Done:
    seed = op.get("seed")
    if seed is None:
        seed = _draw_seed(rng, doc.get("seed"))
    return _Done(["seed"], f"a new zone from the same request (seed {seed})",
                 rooms=_all_room_ids(doc),
                 corridors=[str(c.get("id")) for c in doc.get("corridors") or ()],
                 how=FULL, op={**op, "seed": int(seed)})


def _resize(doc: Dict[str, Any], op: Mapping[str, Any], rng: random.Random) -> _Done:
    """The resize ops (task 7, archive decision 6): ``generators.resize.resize_room`` changes
    the room's box and its corridors; the note gives the size asked for and applied. Nothing
    fits: rejected."""
    from generators.resize import OPS, resize_room
    res = resize_room(doc, op["target"], op["op"], op["by"])
    if not res.applied:
        raise _Rejected(res.notes[0])
    doc.clear()
    doc.update(res.doc)
    changed = ["width", "depth"] if OPS[op["op"]][2] == "plan" else ["height"]
    return _Done(changed, "; ".join(res.notes), rooms=res.affected["rooms"],
                 corridors=res.affected["corridors"], how=FULL)


def _unsupported(doc: Dict[str, Any], op: Mapping[str, Any], rng: random.Random) -> _Done:
    raise _Rejected(f"{op['op']} is not yet supported")


#: op -> how it changes the spec.
_APPLY: Dict[str, Callable[[Dict[str, Any], Mapping[str, Any], random.Random], _Done]] = {
    "set_purpose": _set_purpose,
    "reroll_room": _reroll_room,
    "reroll_decor": _reroll_decor,
    "set_decor_level": _set_decor_level,
    "add_lock": _add_lock,
    "remove_lock": _remove_lock,
    "regenerate": _regenerate,
    **{name: _resize for name in RESIZE_OPS},
    **{name: _unsupported for name in UNSUPPORTED},
}


# ---------------------------------------------------------------------------
# apply_edits
# ---------------------------------------------------------------------------

def apply_edits(doc: Mapping[str, Any], ops: Sequence[Any], seed: int, version: int) -> EditResult:
    """Apply ``ops`` in order to a copy of ``doc`` (a version's saved spec dict). ``seed`` and
    ``version`` (the parent's number) salt the random draws: op ``i`` draws from
    ``random.Random(f"{seed}:{version}:{i}")``.

    Each op is checked again against the spec as edited so far (``ai.edits.validate_op``); one
    that is invalid, names no room, or can't apply is rejected with a note and the rest still
    apply. ``regenerate`` builds a new zone, so the other ops of its edit are rejected
    ("skipped"). The input is never changed; the same arguments give the same result."""
    out = copy.deepcopy(dict(doc))
    result = EditResult(doc=out)
    ops = list(ops or ())
    regen = next((i for i, op in enumerate(ops)
                  if isinstance(op, Mapping) and op.get("op") == "regenerate"), None)
    rooms: Set[str] = set()
    corridors: Set[str] = set()
    for i, raw in enumerate(ops):
        good, reason, _why = validate_op(raw, out)
        if good is None:
            result.rejected.append({"op": raw, "reason": reason})
            result.notes.append(reason)
            continue
        if regen is not None and i != regen:
            reason = f"{good['op']}: skipped, the edit regenerates the zone"
            result.rejected.append({"op": good, "reason": reason})
            result.notes.append(reason)
            continue
        work = copy.deepcopy(out)
        try:
            done = _APPLY[good["op"]](work, good, random.Random(f"{seed}:{version}:{i}"))
        except _Rejected as exc:
            result.rejected.append({"op": good, "reason": str(exc)})
            result.notes.append(str(exc))
            continue
        out.clear()
        out.update(work)
        result.applied.append(done.op or good)
        result.notes.append(done.note)
        for name in done.changed:
            if name not in result.changed:
                result.changed.append(name)
        rooms.update(done.rooms)
        corridors.update(done.corridors)
        if done.how == FULL or result.how is None:
            result.how = done.how
        if good["op"] == "regenerate":
            result.seed = int((done.op or good)["seed"])
    result.affected_rooms = [r for r in _all_room_ids(out) if r in rooms]
    result.affected_corridors = [str(c.get("id")) for c in out.get("corridors") or ()
                                 if str(c.get("id")) in corridors]
    return result
