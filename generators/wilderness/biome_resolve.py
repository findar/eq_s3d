"""
generators/wilderness/biome_resolve.py
---------------------------------------
Biome resolution for the wilderness generator (Requirement 1).

Prompt -> resolved Biome, reusing the EXISTING planner seam
(``ai.planner.make_plan`` / ``ai.planner.get_planner``) rather than a new
parser. The planner seam already:

  * runs the rule planner by default, zero-key, with no external service
    (Req 1.2);
  * accepts an LLM-proposed plan through the same ``make_plan`` drop-in, with
    the rule planner as the automatic fallback on any failure (Req 1.3).

A wilderness prompt routes to the ``wilderness`` zone type via the rule-planner
lexicon (``ai/rule_planner.py``); this module turns that into a resolved Biome.

The v1 biome set is ``{"plains"}`` — the Karanas. A prompt naming a biome
outside that set falls back to ``plains`` and the substitution (``requested``
vs ``resolved``) is recorded on the intent object for the sidecar (Req 1.4).

Per wave-1 partitioning the resolved biome is carried on the wilderness
**intent object** (``WildernessIntent``) here, NOT on a new ``ZoneSpec`` field —
the defaulted ``ZoneSpec.biome`` field is added in wave 5's data-model task
(12.2). Downstream (wave 5) reads the intent's ``biome`` and ``substitution``
to populate the spec and sidecar (Req 1.5).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

from ai.schema import ZonePlan
from ai.planner import make_plan

# ---------------------------------------------------------------------------
# The v1 biome vocabulary
# ---------------------------------------------------------------------------

# The only biome shipped in v1 is the Karanas (plains). Further biomes
# (desert, forest, coast, tundra) are a named fast-follow (requirements.md
# "Out of scope"); every out-of-set name resolves to `plains` (Req 1.4).
DEFAULT_BIOME = "plains"
V1_BIOMES = frozenset({DEFAULT_BIOME})

# Biome keyword lexicon: prompt wording -> biome. v1 only maps to `plains`, but
# the structure supports fast-follow biomes being added as their kits land.
# Order is specific -> general; the first biome with any keyword hit wins. Only
# a biome present in ``V1_BIOMES`` is actually resolvable — a hit on a
# not-yet-shipped biome is treated as an out-of-set request and falls back to
# `plains` with a substitution record (Req 1.4).
_BIOME_WORDS: Dict[str, List[str]] = {
    "plains": ["karana", "karanas", "plains", "plain", "grassland",
               "grasslands", "prairie", "steppe", "steppes", "savanna",
               "savannah", "pasture", "meadow", "meadows", "moor", "moors",
               "heath", "grassy", "field", "fields", "open plain",
               "rolling hills"],
    # Fast-follow biomes (NOT in V1_BIOMES yet). Listed so an explicit request
    # for one is recognised as out-of-set and recorded as a substitution to
    # `plains`, rather than silently reading as a plains prompt.
    "desert": ["desert", "dunes", "sand sea", "arid", "oasis", "wasteland"],
    "forest": ["forest", "woodland", "woods", "jungle", "rainforest"],
    "coast": ["coast", "coastal", "shoreline", "beach", "seaside", "strand"],
    "tundra": ["tundra", "frozen waste", "snowfield", "arctic", "permafrost"],
}


@dataclass
class BiomeSubstitution:
    """Record of a biome fallback (Req 1.4), for the ``.zone.json`` sidecar.

    Emitted ONLY when the ``requested`` biome differs from the ``resolved``
    one — i.e. a prompt named a biome outside the v1 set and we fell back to
    ``plains``. ``requested`` is the biome the prompt actually named.
    """
    requested: str
    resolved: str

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass
class WildernessIntent:
    """The resolved wilderness intent carried between biome resolution and the
    Design_Matrix construction (wave-1 partition: the biome lives here, not on
    ``ZoneSpec`` yet — see module docstring).

    ``biome`` is always a member of ``V1_BIOMES`` (v1: always ``plains``).
    ``requested_biome`` is what the prompt named (may be out-of-set).
    ``substitution`` is non-``None`` iff a fallback happened (Req 1.4); wave 5
    writes it to the sidecar.
    """
    biome: str
    requested_biome: str
    substitution: Optional[BiomeSubstitution] = None
    # The validated plan this intent was resolved from, retained so downstream
    # stages and provenance can read the planner's decisions.
    plan: Optional[ZonePlan] = field(default=None, repr=False)

    @property
    def substituted(self) -> bool:
        """Whether a biome fallback occurred (requested != resolved)."""
        return self.substitution is not None

    def sidecar_record(self) -> Dict[str, object]:
        """The biome metadata for the ``.zone.json`` sidecar (consumed in
        wave 5). Always carries the resolved ``biome``; carries a
        ``substitution`` block only when a fallback happened (Req 1.4)."""
        rec: Dict[str, object] = {"biome": self.biome}
        if self.substitution is not None:
            rec["substitution"] = self.substitution.to_dict()
        return rec


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def _named_biome(prompt: str) -> Optional[str]:
    """The biome a prompt names via the lexicon, or ``None`` if none match.

    Whole-word matching (so "coast" doesn't fire inside "coastal mountain" is
    fine, but "plain" must not fire inside "complaint") keeps the fallback
    record honest. The first biome with any keyword hit wins, in lexicon order.
    """
    text = (prompt or "").lower()
    for biome, words in _BIOME_WORDS.items():
        for w in words:
            # Word-boundary match for single tokens; substring is acceptable
            # for multi-word phrases ("open plain", "rolling hills").
            if " " in w:
                if w in text:
                    return biome
            elif re.search(rf"\b{re.escape(w)}\b", text):
                return biome
    return None


def resolve_biome(plan: ZonePlan) -> WildernessIntent:
    """Resolve the Biome for a wilderness plan into a ``WildernessIntent``.

    The prompt is read from the (validated) ``plan`` the planner produced, so
    this works identically whether the plan came from the rule planner (Req
    1.2) or an LLM drop-in (Req 1.3) — the planner seam already chose. The
    lexicon finds the biome the prompt named:

      * a v1 biome (``plains``)         -> resolved as-is, no substitution;
      * an out-of-set biome             -> fall back to ``plains`` and record
                                           the substitution (Req 1.4);
      * no biome named at all           -> default to ``plains`` (the only v1
                                           biome), no substitution — nothing
                                           was swapped away.

    (Req 1.1: a plains/Karana prompt resolves to the ``plains`` biome.)
    """
    requested = _named_biome(plan.prompt)

    if requested is None:
        # No biome named: default to plains. This is the lead biome, not a
        # substitution away from anything the user asked for.
        return WildernessIntent(biome=DEFAULT_BIOME,
                                requested_biome=DEFAULT_BIOME,
                                substitution=None,
                                plan=plan)

    if requested in V1_BIOMES:
        return WildernessIntent(biome=requested,
                                requested_biome=requested,
                                substitution=None,
                                plan=plan)

    # Out-of-set biome: fall back to plains and record the swap (Req 1.4).
    return WildernessIntent(
        biome=DEFAULT_BIOME,
        requested_biome=requested,
        substitution=BiomeSubstitution(requested=requested,
                                       resolved=DEFAULT_BIOME),
        plan=plan,
    )


def resolve_wilderness_intent(prompt: str, name: str = "zone") -> WildernessIntent:
    """Prompt -> ``WildernessIntent`` through the existing planner seam.

    Goes through ``ai.planner.make_plan`` so the LLM drop-in (Req 1.3) and the
    zero-key rule-planner default + automatic fallback (Req 1.2) are inherited
    unchanged — no new provider plumbing here. The resolved plan's prompt then
    drives biome resolution.
    """
    plan = make_plan(prompt, name=name)
    return resolve_biome(plan)
