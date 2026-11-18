"""
ai/llm_edits.py
---------------
The optional LLM edit interpreter (zone-generator-edits Req 1.5, design "Ops").

``LLMEditInterpreter`` asks an LLM to turn feedback text into edit ops from ``ai.edits.OPS``,
grounded in the version's saved spec (its rooms' ids, roles, types and kinds). Its answer is
accepted only as a JSON object ``{"ops": [...]}`` whose ops all pass the op schema; they are then
re-validated and clamped by ``ai.edits.validate`` exactly like the rule interpreter's. A target
that names no room (or several) is a note, as for the rule interpreter; any other failure (no
key, a missing SDK, a network error, bad JSON, a schema failure, or no answer within
``TIMEOUT`` seconds) gives the rule interpreter's ops, notes and name instead.

Key handling mirrors ``ai/llm_planner.py``: ``OPENAI_API_KEY`` first, then
``ANTHROPIC_API_KEY``, read through ``core.env.env_value``; ``EQ_S3D_PLANNER=rule`` forces the
rule interpreter. The provider SDK is imported only inside a provider call, so without a key
nothing imports one. Callers pick an interpreter with ``get_edit_interpreter()``.
"""

from __future__ import annotations

import json
import threading
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from core.env import env_value
from .edits import OPS, RuleEditInterpreter, _clean, validate

#: The interpreter's name, recorded in the version's ``edit`` block.
LLM = "llm"

#: Seconds to wait for an answer before falling back to the rule interpreter (Req 1.5).
TIMEOUT = 15.0

#: How many rooms the prompt lists (a spec has at most a few dozen).
_MAX_ROOMS = 80

#: A client is ``(system, user, timeout) -> raw response text``.
Client = Callable[[str, str, float], str]


_SYSTEM_PROMPT = """You edit EverQuest-style zones from a designer's feedback.
Turn the feedback into a JSON object {{"ops": [...]}} where each op is an object
{{"op": <name>, ...parameters}} using ONLY these ops and parameters:
{ops}

Parameter kinds: "room" names one room of the zone below (use its id); a number has a range
lo..hi; a choice must be one of the listed words. Leave out optional parameters you don't need.
"by" is the fraction of the room's size added or taken away.
If the feedback asks for nothing these ops can do, return {{"ops": []}}.

The zone's rooms (id, pacing role, room type, kind):
{rooms}
The zone's decor level: {decor}

Respond with ONLY the JSON object, no prose.
"""


def _describe_ops() -> str:
    lines = []
    for name, params in OPS.items():
        parts = []
        for key, p in params.items():
            if p.kind == "room":
                kind = "room"
            elif p.kind in ("float", "int"):
                kind = f"{p.kind} {p.lo:g}..{p.hi:g}"
            else:
                kind = "one of " + "|".join(p.choices)
            parts.append(f"{key} ({kind}{'' if p.required else ', optional'})")
        lines.append(f"- {name}: " + (", ".join(parts) if parts else "no parameters"))
    return "\n".join(lines)


def _describe_rooms(spec_doc: Mapping[str, Any]) -> str:
    rooms = spec_doc.get("rooms") if isinstance(spec_doc, Mapping) else None
    lines = []
    for r in (rooms or [])[:_MAX_ROOMS]:
        if not isinstance(r, Mapping) or not isinstance(r.get("id"), str):
            continue
        fields = [str(r.get(k) or "-") for k in ("role", "semantic_type", "kind")]
        lines.append(f"- {r['id']}: " + ", ".join(fields))
    return "\n".join(lines) or "- (none)"


def system_prompt(spec_doc: Mapping[str, Any]) -> str:
    """The system prompt for one spec: the op vocabulary and the rooms it can target."""
    decor = spec_doc.get("decor") if isinstance(spec_doc, Mapping) else None
    return _SYSTEM_PROMPT.format(ops=_describe_ops(), rooms=_describe_rooms(spec_doc),
                                 decor=decor or "normal")


def _parse(text: Any) -> Any:
    """The JSON object in a response, markdown fences stripped. Raises on anything else."""
    if not isinstance(text, str):
        raise ValueError("the response is not text")
    t = text.strip()
    if t.startswith("```"):
        t = t[t.find("{"):t.rfind("}") + 1]
    data = json.loads(t)
    if not isinstance(data, dict) or not isinstance(data.get("ops"), list):
        raise ValueError('the response is not {"ops": [...]}')
    return data["ops"]


class _Timeout(Exception):
    pass


def _call_with_timeout(fn: Callable[[], str], timeout: float) -> str:
    """``fn()`` on a daemon thread; raises ``_Timeout`` if it has not answered in ``timeout``
    seconds (the thread is abandoned, never joined)."""
    box: Dict[str, Any] = {}

    def run():
        try:
            box["value"] = fn()
        except BaseException as e:      # handed back to the caller below
            box["error"] = e

    t = threading.Thread(target=run, name="llm-edits", daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise _Timeout(f"no answer within {timeout:g} s")
    if "error" in box:
        raise box["error"]
    return box.get("value")


class LLMEditInterpreter:
    """Feedback text -> edit ops through an LLM, with the rule interpreter as the fallback.

    ``client`` replaces the provider call (tests): ``client(system, user, timeout)`` returns
    the response text. Without one, the provider is picked by whichever key is set."""

    name = LLM

    def __init__(self, client: Optional[Client] = None, timeout: float = TIMEOUT,
                 fallback: Optional[RuleEditInterpreter] = None):
        self.openai_key = env_value("OPENAI_API_KEY")
        self.anthropic_key = env_value("ANTHROPIC_API_KEY")
        self.client = client
        self.timeout = timeout
        self.fallback = fallback or RuleEditInterpreter()
        #: Why the last ``interpret`` fell back (an exception type, never its text), or None.
        self.last_error: Optional[str] = None

    def available(self) -> bool:
        return self.client is not None or bool(self.openai_key or self.anthropic_key)

    def interpret(self, text: Any, spec_doc: Mapping[str, Any]) -> Tuple[List[Dict[str, Any]], List[str], str]:
        """``(ops, notes, name)``: validated ops from the LLM with name ``"llm"``, or the rule
        interpreter's result (name ``"rule"``) on any failure. Never raises."""
        self.last_error = None
        if not isinstance(spec_doc, Mapping):
            spec_doc = {}
        cleaned = _clean(text)
        if not cleaned.strip():
            return self.fallback.interpret(text, spec_doc)
        try:
            system = system_prompt(spec_doc)
            raw = _call_with_timeout(lambda: self._call(system, cleaned), self.timeout)
            ops = _parse(raw)
            good, bad = validate(ops, spec_doc)
            schema = [b for b in bad if b.get("why") == "schema"]
            if schema:
                raise ValueError(f"{len(schema)} op(s) fail the op schema")
            return good, [b["reason"] for b in bad], self.name
        except Exception as e:
            from .planner import _redacted_error
            self.last_error = _redacted_error(e)
            print(f"[edits] {self.name} interpreter failed ({self.last_error}); "
                  f"falling back to the rule interpreter")
            return self.fallback.interpret(text, spec_doc)

    # ------------------------------------------------------------------

    def _call(self, system: str, user: str) -> str:
        if self.client is not None:
            return self.client(system, user, self.timeout)
        if self.openai_key:
            return self._call_openai(system, user)
        if self.anthropic_key:
            return self._call_anthropic(system, user)
        raise RuntimeError("No LLM API key available")

    def _call_openai(self, system: str, user: str) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=self.openai_key, timeout=self.timeout, max_retries=0)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        return resp.choices[0].message.content

    def _call_anthropic(self, system: str, user: str) -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=self.anthropic_key, timeout=self.timeout,
                                     max_retries=0)
        resp = client.messages.create(
            model="claude-3-5-haiku-latest",
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
            temperature=0,
        )
        return resp.content[0].text


def get_edit_interpreter():
    """The interpreter an edit uses: ``LLMEditInterpreter`` when an LLM key is set (and
    ``EQ_S3D_PLANNER`` isn't ``rule``), else ``RuleEditInterpreter``. Both have
    ``interpret(text, spec_doc) -> (ops, notes, name)``."""
    if (env_value("EQ_S3D_PLANNER") or "").lower() == "rule":
        return RuleEditInterpreter()
    llm = LLMEditInterpreter()
    return llm if llm.available() else RuleEditInterpreter()
