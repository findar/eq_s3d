"""
ai/edits.py
-----------
Edit ops and the rule-based edit interpreter (zone-generator-edits Req 1, design "Ops").

An edit is a list of ops, each a dict ``{op, target?, ...params}`` from the vocabulary in
``OPS``: umbrella Requirement 18.2's fifteen ops plus ``reroll_decor`` and ``set_decor_level``
(amendment A3). ``validate(ops, spec_doc)`` checks ops against their schema, clamps numbers into
range and resolves each ``target`` to one room id of the version's saved spec (its
``ZoneSpec.to_dict()``). ``RuleEditInterpreter.interpret(text, spec_doc)`` turns feedback text
("make the boss room bigger and lock the way into the crypt") into validated ops, notes and
its name, ``"rule"``.

Everything here is pure: no server, no build, no file. Which ops a build can apply yet is the
edit engine's call (``generators/edits.py``), not this module's: every op here is recognised.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from ai.schema import SEED_MAX, VALID_DECOR
from generators.semantics import ROOM_TYPES

#: The interpreter's name, recorded in the version's ``edit`` block.
RULE = "rule"

#: Feedback text is cut to this many characters after cleaning (umbrella 30.9).
MAX_TEXT = 2000

VERTICALITY = ("flat", "moderate", "dramatic")
TOPOLOGY = ("linear", "branching", "looped")
REGION_KINDS = ("water", "lava", "ice")


# ---------------------------------------------------------------------------
# The op schema
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Param:
    """One op parameter: ``room`` (a target, resolved to a room id), ``float`` / ``int`` (an
    inclusive range ``lo``..``hi``; a value outside is clamped) or ``choice`` (one of
    ``choices``). An optional parameter with a ``default`` is filled in when left out."""
    kind: str
    required: bool = True
    lo: float = 0.0
    hi: float = 0.0
    choices: Tuple[str, ...] = ()
    default: Any = None


def _room(required: bool = True) -> Param:
    return Param("room", required)


def _frac(lo: float, hi: float, default: float) -> Param:
    return Param("float", False, lo, hi, default=default)


_TYPES = tuple(sorted(ROOM_TYPES))

#: op -> its parameters, in the order a validated op lists them. ``by`` is the fraction of the
#: room's size added (widen, taller) or taken away (narrow, lower).
OPS: Dict[str, Dict[str, Param]] = {
    "widen_room": {"target": _room(), "by": _frac(0.1, 1.0, 0.25)},
    "narrow_room": {"target": _room(), "by": _frac(0.05, 0.5, 0.2)},
    "taller_room": {"target": _room(), "by": _frac(0.1, 1.0, 0.25)},
    "lower_room": {"target": _room(), "by": _frac(0.05, 0.4, 0.2)},
    "add_room": {"target": _room(False), "count": Param("int", False, 1, 3, default=1),
                 "type": Param("choice", False, choices=_TYPES)},
    "remove_room": {"target": _room()},
    "add_region": {"target": _room(), "kind": Param("choice", choices=REGION_KINDS)},
    "remove_region": {"target": _room(), "kind": Param("choice", False, choices=REGION_KINDS)},
    "set_purpose": {"target": _room(), "type": Param("choice", choices=_TYPES)},
    "set_verticality": {"level": Param("choice", False, choices=VERTICALITY),
                        "delta": Param("int", False, -1, 1)},
    "add_lock": {"target": _room()},
    "remove_lock": {"target": _room(False)},
    "reroll_room": {"target": _room()},
    "set_topology": {"shape": Param("choice", choices=TOPOLOGY)},
    "regenerate": {"seed": Param("int", False, 0, SEED_MAX)},
    "reroll_decor": {},
    "set_decor_level": {"level": Param("choice", choices=tuple(VALID_DECOR))},
}

#: Ops that need one of several optional parameters.
_ONE_OF = {"set_verticality": ("level", "delta")}

#: Shown when an edit gives no ops (umbrella 18.4).
HELP = ("Try: \"make the boss room bigger\", \"lock the way into the crypt\", "
        "\"redecorate the entrance\", \"less decor\", \"make room 3 a forge\", "
        "\"flood the hub\", \"flatter\", \"more loops\" or \"start over\". "
        "Edits: " + ", ".join(OPS) + ".")


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------

# Pacing-role words -> the role (design "Ops"; ordinals are out).
_ROLE_WORDS = {
    "boss": "climax", "climax": "climax", "final": "climax", "finale": "climax",
    "entrance": "entrance", "entry": "entrance", "start": "entrance",
    "starting": "entrance", "beginning": "entrance",
    "hub": "hub", "crossroads": "hub", "junction": "hub",
    "dead end": "deadend", "dead-end": "deadend", "deadend": "deadend",
}
_ROLES = frozenset(_ROLE_WORDS.values())

# Room-type words beyond the type names themselves.
_TYPE_WORDS = {
    "crypt": "ossuary", "tomb": "ossuary", "catacomb": "ossuary", "catacombs": "ossuary",
    "boneyard": "ossuary", "throne room": "throne", "lab": "laboratory",
    "prison": "prison_cell", "cell": "prison_cell", "jail": "prison_cell",
    "dungeon cell": "prison_cell", "arena": "battle_arena", "armoury": "armory",
    "store room": "storeroom", "storage": "storeroom", "sanctum": "inner_sanctum",
    "temple": "shrine", "chapel": "shrine", "smithy": "forge", "treasury": "vault",
    "guardroom": "guard_post", "guard room": "guard_post", "gate house": "gatehouse",
}

_ROOM_N = re.compile(r"\brooms?[ \t_#-]*(\d{1,4})\b")
_PRONOUN = re.compile(r"\b(?:it|its|that|there|this one)\b")


def _rooms(spec_doc: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    rooms = spec_doc.get("rooms") if isinstance(spec_doc, Mapping) else None
    return [r for r in (rooms or []) if isinstance(r, Mapping) and isinstance(r.get("id"), str)]


def _words(name: str) -> str:
    return name.replace("_", " ")


def _phrases(spec_doc: Mapping[str, Any]) -> Dict[str, str]:
    """Every phrase a target can be named by -> its canonical word (a room id, role, room type
    or rule-set kind)."""
    out: Dict[str, str] = {}
    rooms = _rooms(spec_doc)
    for kind in sorted({str(r.get("kind") or "") for r in rooms} - {""}):
        out[_words(kind).lower()] = kind
        out[_words(kind).lower() + "s"] = kind
    types = set(_TYPES) | {str(r.get("semantic_type") or "") for r in rooms}
    for t in sorted(types - {""}):
        out[_words(t).lower()] = t
        out[t.lower()] = t
    out.update(_TYPE_WORDS)
    out.update(_ROLE_WORDS)
    out.update({"dead ends": "deadend", "hubs": "hub"})
    for r in rooms:
        out[r["id"].lower()] = r["id"]
    return out


class _Mentions:
    """Finds target mentions in cleaned, lower-case text against one spec."""

    def __init__(self, spec_doc: Mapping[str, Any]):
        self.spec = spec_doc
        self.phrases = _phrases(spec_doc)
        alts = sorted(self.phrases, key=lambda p: (-len(p), p))
        body = "|".join(re.escape(p) for p in alts)
        self.pattern = re.compile(r"(?<![\w-])(?:" + body + r")(?![\w-])") if alts else None
        self.ids = {r["id"] for r in _rooms(spec_doc)}

    def find(self, text: str) -> List[Tuple[int, int, str]]:
        """``(start, end, surface)`` of each mention, in order, longest first where they
        overlap. ``room 3`` is a mention of ``room_3``."""
        found: List[Tuple[int, int, str]] = []
        for m in _ROOM_N.finditer(text):
            found.append((m.start(), m.end(), m.group(0)))
        if self.pattern is not None:
            for m in self.pattern.finditer(text):
                if not any(s <= m.start() < e for s, e, _ in found):
                    found.append((m.start(), m.end(), m.group(0)))
        return sorted(found)

    def canonical(self, surface: str) -> str:
        s = surface.strip().lower()
        m = _ROOM_N.fullmatch(s)
        if m:
            return f"room_{int(m.group(1))}"
        return self.phrases.get(s, s)


def resolve_target(ref: Any, spec_doc: Mapping[str, Any]) -> List[str]:
    """The room ids a target names: a room id first; then a pacing role ("boss room",
    "climax", "entrance", "hub", "dead end"); then a room type ("crypt" is an ossuary); then a
    rule-set kind ("chamber"). A phrase naming none gives ``[]``; several rooms is ambiguous
    and left to the caller."""
    if not isinstance(ref, str):
        return []
    rooms = _rooms(spec_doc)
    for r in rooms:
        if r["id"] == ref:
            return [r["id"]]
    text = _clean(ref).lower()
    mentions = _Mentions(spec_doc)
    found = mentions.find(text)
    if not found:
        return []
    word = mentions.canonical(found[0][2])
    if any(r["id"] == word for r in rooms):
        return [word]
    for field in ("role", "semantic_type", "kind"):
        if field == "role" and word not in _ROLES:
            continue
        ids = [r["id"] for r in rooms if r.get(field) == word]
        if ids:
            return ids
    return []


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _reject(op: Any, reason: str, why: str = "schema") -> Dict[str, Any]:
    return {"op": op, "reason": reason, "why": why}


def _number(name: str, value: Any, p: Param) -> Tuple[Optional[float], str]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None, f"{name} must be a number from {p.lo:g} to {p.hi:g}"
    if not math.isfinite(value):
        return None, f"{name} must be a finite number"
    v = min(max(float(value), p.lo), p.hi)
    if p.kind == "int":
        return int(round(v)), ""
    return round(v, 4), ""


def _choice(name: str, value: Any, p: Param) -> Tuple[Optional[str], str]:
    if isinstance(value, str):
        v = re.sub(r"[\s-]+", "_", value.strip().lower())
        if v in p.choices:
            return v, ""
        if p.choices is _TYPES:
            w = _TYPE_WORDS.get(_words(v))
            if w is not None:
                return w, ""
    return None, f"{name} {value!r} is not one of: {', '.join(p.choices)}"


def validate_op(op: Any, spec_doc: Mapping[str, Any]) -> Tuple[Optional[Dict[str, Any]], str, str]:
    """One op -> ``(good, "", "")`` or ``(None, reason, why)``; ``why`` is ``"schema"`` (an
    unknown op, a missing or bad parameter) or ``"target"`` (no room, or several)."""
    if not isinstance(op, Mapping):
        return None, f"an edit op is an object, not {type(op).__name__}", "schema"
    name = op.get("op")
    if not isinstance(name, str) or name not in OPS:
        return None, f"unknown op {name!r}; known: {', '.join(OPS)}", "schema"
    schema = OPS[name]
    extra = sorted(str(k) for k in op if k != "op" and k not in schema)
    if extra:
        return None, f"{name}: unknown parameter {', '.join(extra)}", "schema"
    out: Dict[str, Any] = {"op": name}
    for key, p in schema.items():
        value = op.get(key)
        if value is None:
            if p.required:
                return None, f"{name}: missing parameter {key}", "schema"
            if p.default is not None:
                out[key] = p.default
            continue
        if p.kind == "room":
            if not isinstance(value, str) or not value.strip():
                return None, f"{name}: {key} must name a room", "schema"
            ids = resolve_target(value, spec_doc)
            if not ids:
                return None, f"{name}: no room matches {value!r}", "target"
            if len(ids) > 1:
                return None, (f"{name}: {value!r} is ambiguous, it matches "
                              f"{len(ids)} rooms: {', '.join(ids)}"), "target"
            out[key] = ids[0]
        elif p.kind in ("float", "int"):
            v, why = _number(key, value, p)
            if v is None:
                return None, f"{name}: {why}", "schema"
            out[key] = v
        else:
            v, why = _choice(key, value, p)
            if v is None:
                return None, f"{name}: {why}", "schema"
            out[key] = v
    need = _ONE_OF.get(name)
    if need and not any(k in out for k in need):
        return None, f"{name}: needs one of {', '.join(need)}", "schema"
    if name == "set_verticality" and out.get("delta") == 0 and "level" not in out:
        return None, f"{name}: delta must be -1 or 1", "schema"
    return out, "", ""


def validate(ops: Any, spec_doc: Mapping[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """``(good, bad)``: the good ops clamped into range, defaults filled in and their targets
    resolved to room ids; each bad one as ``{op, reason, why}`` (``why``: ``"schema"`` or
    ``"target"``). Not a list is one bad entry."""
    if not isinstance(ops, (list, tuple)):
        return [], [_reject(ops, "edit ops are a list")]
    good: List[Dict[str, Any]] = []
    bad: List[Dict[str, Any]] = []
    for op in ops:
        ok, reason, why = validate_op(op, spec_doc)
        if ok is not None:
            good.append(ok)
        else:
            bad.append(_reject(op, reason, why))
    return good, bad


# ---------------------------------------------------------------------------
# The rule interpreter
# ---------------------------------------------------------------------------

def _clean(text: Any) -> str:
    """Control characters out (newline and tab stay), then cut to ``MAX_TEXT`` (Req 1.3)."""
    if not isinstance(text, str):
        return ""
    kept = "".join(c for c in text if c in "\n\t" or unicodedata.category(c) != "Cc")
    return kept[:MAX_TEXT]


def _normal(text: str) -> str:
    t = text.lower().replace("’", "'").replace("‘", "'")
    return re.sub(r"[ \t]+", " ", t)


_SPLIT = re.compile(r"\s*(?:[,;\n!?]|\.(?!\d)|\band then\b|\bthen\b|\band\b|\balso\b|\bplus\b)\s*")

_DECOR = r"(?:decor|decorations?|props?|clutter|furnishings?|furniture|dressing)"

# Size words -> how much: the default is the schema's.
_BIG = re.compile(r"\b(?:much|a lot|way|far|lots|huge|massive|enormous)\b")
_SMALL = re.compile(r"\b(?:a bit|a little|slightly|somewhat|a touch|a tad)\b")
_DOUBLE = re.compile(r"\b(?:twice|double|doubled)\b")
_HALF = re.compile(r"\b(?:half|halve|halved)\b")
_PERCENT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s?(?:%|percent\b)")


def _amount(clause: str, op: str) -> Dict[str, float]:
    p = OPS[op]["by"]
    m = _PERCENT.search(clause)
    if m:
        return {"by": float(m.group(1)) / 100.0}
    if _DOUBLE.search(clause):
        return {"by": 1.0}
    if _HALF.search(clause):
        return {"by": 0.5}
    if _BIG.search(clause):
        return {"by": p.hi}
    if _SMALL.search(clause):
        return {"by": p.lo}
    return {"by": p.default}


def _decor_step(spec_doc: Mapping[str, Any], step: int) -> str:
    now = spec_doc.get("decor") if isinstance(spec_doc, Mapping) else None
    levels = list(VALID_DECOR)
    i = levels.index(now) if now in levels else levels.index("normal")
    return levels[min(max(i + step, 0), len(levels) - 1)]


@dataclass
class _Clause:
    text: str
    targets: List[str]          # surfaces of the target mentions, in order


class RuleEditInterpreter:
    """Phrase rules over cleaned feedback text (design "Ops"). Clauses split on "and", ",",
    ";", ".", "then"; a clause with no target takes the one before it ("make the hub bigger
    and redecorate it"), and one with a target but no verb takes the verb before it
    ("redecorate the entrance and the boss room"). Text it can't read gives no ops."""

    name = RULE

    def interpret(self, text: Any, spec_doc: Mapping[str, Any]) -> Tuple[List[Dict[str, Any]], List[str], str]:
        """``(ops, notes, "rule")``: validated ops, the notes for ops it had to reject and for
        clauses it couldn't read. Never raises, for any string (Req 1.3); deterministic."""
        if not isinstance(spec_doc, Mapping):
            spec_doc = {}
        cleaned = _normal(_clean(text))
        if not cleaned.strip():
            return [], [], self.name
        mentions = _Mentions(spec_doc)
        raw: List[Dict[str, Any]] = []
        notes: List[str] = []
        last_target: Optional[str] = None
        last_op: Optional[Dict[str, Any]] = None
        for part in _SPLIT.split(cleaned):
            part = part.strip()
            if not part:
                continue
            clause = _Clause(part, [s for _, _, s in mentions.find(part)])
            if not clause.targets and _PRONOUN.search(part) and last_target:
                clause.targets = [last_target]
            op = self._read(clause, spec_doc, last_target)
            if op is None and clause.targets and last_op is not None and "target" in OPS[last_op["op"]]:
                op = dict(last_op, target=clause.targets[0])
            if op is not None and "target" not in op:
                p = OPS[op["op"]].get("target")
                guess = _named(part) if p is not None and p.required else None
                if guess:
                    op["target"] = guess    # names no room: the note names it (Req 1.2)
            if op is None:
                if re.search(r"[^\W\d_]", part) and not re.fullmatch(r"(?:please|thanks?|thank you|ok(?:ay)?)\W*", part):
                    notes.append(f"not understood: {part[:80]!r}")
                continue
            if op.get("target"):
                last_target = op["target"]
            elif clause.targets:
                last_target = clause.targets[0]
            raw.append(op)
            last_op = op
        good, bad = validate(raw, spec_doc)
        notes = [b["reason"] for b in bad] + notes
        return good, notes, self.name

    @staticmethod
    def _read(c: _Clause, spec_doc, last_target) -> Optional[Dict[str, Any]]:
        """The first rule that reads the clause (``_RULES`` order matters)."""
        for rule in _RULES:
            op = rule(c, spec_doc, last_target)
            if op is not None:
                return op
        return None


def _target(c: _Clause, last_target: Optional[str], skip: Iterable[str] = ()) -> Optional[str]:
    for t in c.targets:
        if t not in skip:
            return t
    return last_target


_NOT_ROOMS = frozenset({"way", "door", "doors", "path", "ceiling", "ceilings", "room", "rooms",
                        "decor", "props", "whole", "same", "other", "next", "most", "rest"})


def _named(clause: str) -> Optional[str]:
    """The last "the <word>" of a clause that names no known room, so its note can say what
    the text asked for ("lock the kitchen": no room matches 'kitchen')."""
    words = [w for w in re.findall(r"\bthe ([^\W\d_]{2,30})\b", clause) if w not in _NOT_ROOMS]
    return words[-1] if words else None


def _with_target(op: Dict[str, Any], target: Optional[str]) -> Dict[str, Any]:
    if target:
        op["target"] = target
    return op


def _regenerate(c, spec_doc, last):
    if re.search(r"\b(?:start (?:it )?over|start again|from scratch|regenerate|"
                 r"(?:re-?roll|redo|rebuild|remake) (?:the )?(?:whole )?(?:zone|dungeon|map|level|"
                 r"everything|thing|lot)|new (?:zone|dungeon|map|layout)|try again)\b", c.text):
        return {"op": "regenerate"}
    return None


def _decor(c, spec_doc, last):
    t = c.text
    if re.search(r"\bredecorat\w*|\bredress\w*|\b(?:new|different|fresh|other) " + _DECOR
                 + r"|\b(?:re-?roll|redo|reshuffle|shuffle) (?:the |its |their )?" + _DECOR, t):
        target = _target(c, None)
        return _with_target({"op": "reroll_room"}, target) if target else {"op": "reroll_decor"}
    m = re.search(r"\b(none|no|sparse|sparser|normal|default|dense|denser)\b(?: \w+)? " + _DECOR
                  + r"|" + _DECOR + r" (?:level )?(?:to |at )?(none|sparse|normal|dense)\b", t)
    if m:
        word = m.group(1) or m.group(2)
        level = {"no": "none", "sparser": "sparse", "denser": "dense", "default": "normal"}.get(word, word)
        return {"op": "set_decor_level", "level": level}
    if re.search(r"\b(?:remove|strip|clear|drop|get rid of)\b(?: \w+){0,2} " + _DECOR
                 + r"|\b(?:bare|empty) rooms\b", t):
        return {"op": "set_decor_level", "level": "none"}
    if re.search(r"\b(?:less|fewer|reduce|reduced|lower|thin(?: out)?)\b(?: \w+)? " + _DECOR
                 + r"|\b(?:sparser|less cluttered|declutter\w*)\b", t):
        return {"op": "set_decor_level", "level": _decor_step(spec_doc, -1)}
    if re.search(r"\b(?:more|extra|add|increase|lots of)\b(?: \w+)? " + _DECOR
                 + r"|\b(?:denser|busier|more cluttered)\b", t):
        return {"op": "set_decor_level", "level": _decor_step(spec_doc, +1)}
    m = re.search(r"\b(sparse|sparser|dense|denser)\b", t)
    if m and not c.targets:
        return {"op": "set_decor_level", "level": m.group(1).rstrip("r")}
    return None


def _lock(c, spec_doc, last):
    t = c.text
    if re.search(r"\bunlock\w*|\b(?:remove|take away|take out|drop|get rid of|no)\b(?: \w+){0,2} "
                 r"(?:locks?|locked doors?|gates?)\b|\bopen (?:it |that )?up\b", t):
        return _with_target({"op": "remove_lock"}, _target(c, None))
    if re.search(r"\b(?:lock|locks|locked|lock up)\b|\bgate (?:off|the)\b|\bkey(?:ed)?\b", t):
        return _with_target({"op": "add_lock"}, _target(c, last))
    return None


def _region(c, spec_doc, last):
    t = c.text
    m = re.search(r"\b(?:drain|dry(?: out| up)?|unflood|remove the (water|lava|ice)|"
                  r"no more (water|lava|ice)|thaw|defrost)\b", t)
    if m:
        kind = m.group(1) or m.group(2) or ("ice" if re.search(r"\b(?:thaw|defrost)\b", t) else None)
        if kind is None and re.search(r"\b(?:drain|dry|unflood)", t):
            kind = "water"
        op = {"op": "remove_region"}
        if kind:
            op["kind"] = kind
        return _with_target(op, _target(c, last))
    if re.search(r"\b(?:flood\w*|water|underwater|pool|submerge\w*|wet)\b", t):
        return _with_target({"op": "add_region", "kind": "water"}, _target(c, last))
    if re.search(r"\b(?:lava|magma|molten|fire pit)\b", t):
        return _with_target({"op": "add_region", "kind": "lava"}, _target(c, last))
    if re.search(r"\b(?:ice|icy|frozen|freeze|frost\w*)\b", t):
        return _with_target({"op": "add_region", "kind": "ice"}, _target(c, last))
    return None


def _purpose(c, spec_doc, last):
    t = c.text
    m = re.search(r"\b(?:make|turn|change|convert|use|rename)\b(.*?)\b(?:into|to|a|an|as)\s+(.+)$", t)
    if not m:
        m = re.search(r"^(.*?)\b(?:should be|becomes?|is now)\s+(?:a |an |the )?(.+)$", t)
    if not m:
        return None
    mentions = [s for s in c.targets]
    mentions_after = [s for s in mentions if s in m.group(2)]
    for kind_surface in mentions_after:
        v, _ = _choice("type", kind_surface, OPS["set_purpose"]["type"])
        if v is not None:
            target = _target(_Clause(m.group(1), [s for s in mentions if s in m.group(1)]), None)
            if target is None and (_PRONOUN.search(m.group(1)) or not m.group(1).strip()):
                target = last
            return _with_target({"op": "set_purpose", "type": v}, target)
    return None


def _add_room(c, spec_doc, last):
    t = c.text
    m = re.search(r"\b(?:add|another|extra|one more|new)\b(?: (\d|one|two|three|a|an|some))?"
                  r"(?: \w+)? (?:rooms?|chambers?)\b|\bmore (?:rooms|chambers)\b", t)
    if not m:
        return None
    count = {"one": 1, "a": 1, "an": 1, "two": 2, "three": 3, "some": 2}.get(m.group(1) or "", None)
    if count is None and m.group(1) and m.group(1).isdigit():
        count = int(m.group(1))
    if count is None and re.search(r"\bmore (?:rooms|chambers)\b", t):
        count = 2
    op: Dict[str, Any] = {"op": "add_room"}
    if count:
        op["count"] = count
    target = None
    a = re.search(r"\b(?:off|near|next to|beside|by|after|from|behind|past|to)\b(.*)$", t)
    if a:
        target = _target(_Clause(a.group(1), [s for s in c.targets if s in a.group(1)]), None)
    return _with_target(op, target)


def _remove_room(c, spec_doc, last):
    if re.search(r"\b(?:remove|delete|get rid of|drop|cut|lose)\b", c.text):
        target = _target(c, last)
        return _with_target({"op": "remove_room"}, target) if target else None
    return None


def _verticality(c, spec_doc, last):
    t = c.text
    if re.search(r"\b(?:completely|totally|all) flat\b|\bno (?:verticality|elevation|levels)\b", t):
        return {"op": "set_verticality", "level": "flat"}
    if re.search(r"\b(?:very|really|dramatic(?:ally)?|extreme(?:ly)?) (?:vertical|steep)\b|\bdramatic\b", t):
        return {"op": "set_verticality", "level": "dramatic"}
    if re.search(r"\b(?:flatter|flatten|less (?:vertical|verticality|elevation|steep|hilly)|level it out)\b", t):
        return {"op": "set_verticality", "delta": -1}
    if re.search(r"\b(?:more (?:vertical|verticality|elevation|levels|height changes)|hillier|steeper)\b", t):
        return {"op": "set_verticality", "delta": 1}
    return None


def _topology(c, spec_doc, last):
    t = c.text
    if re.search(r"\b(?:more loops|loops?|loopy|looped|interconnected|circular|circuit)\b", t):
        return {"op": "set_topology", "shape": "looped"}
    if re.search(r"\b(?:linear|one path|single path|straight line|no branches)\b", t):
        return {"op": "set_topology", "shape": "linear"}
    if re.search(r"\b(?:branch\w*|more side rooms|forks?)\b", t):
        return {"op": "set_topology", "shape": "branching"}
    return None


def _size(c, spec_doc, last):
    t = c.text
    target = _target(c, last)
    if re.search(r"\b(?:taller|higher|loftier|raise (?:the )?ceilings?|higher ceilings?|more headroom)\b", t):
        return _with_target({"op": "taller_room", **_amount(t, "taller_room")}, target)
    if re.search(r"\b(?:lower (?:the )?ceilings?|shorter|squatter|less tall|lower)\b", t):
        return _with_target({"op": "lower_room", **_amount(t, "lower_room")}, target)
    if re.search(r"\b(?:smaller|narrower|shrink|tighter|more cramped|cramped|reduce|tinier)\b", t):
        return _with_target({"op": "narrow_room", **_amount(t, "narrow_room")}, target)
    if re.search(r"\b(?:bigger|larger|wider|broader|enlarge|expand|grow|roomier|huge|"
                 r"more (?:room|space)|double (?:the )?size)\b", t):
        return _with_target({"op": "widen_room", **_amount(t, "widen_room")}, target)
    return None


def _reroll_room(c, spec_doc, last):
    if re.search(r"\b(?:re-?roll|redo|remake|rebuild|different|another take on|try another)\b", c.text):
        target = _target(c, last)
        return _with_target({"op": "reroll_room"}, target) if target else None
    return None


_RULES = (_regenerate, _decor, _lock, _region, _purpose, _add_room, _remove_room,
          _verticality, _topology, _size, _reroll_room)


def interpret(text: Any, spec_doc: Mapping[str, Any]) -> Tuple[List[Dict[str, Any]], List[str], str]:
    """``RuleEditInterpreter().interpret`` (the module's default interpreter)."""
    return RuleEditInterpreter().interpret(text, spec_doc)
