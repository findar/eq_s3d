"""Dungeon verticality task 9 (Requirement 9.2, 9.3; design V10): the gate
sweep on built multi-level zones.

Graph-layout zones are built through the real pipeline (build, walkability
gate, format check, retry on a fresh seed) over a fixed seed list, at each
Verticality setting:

- dungeon x each base set (``classic_eq``, ``warren``) x plain, ``temple``
  and ``fortress`` x several room counts;
- outdoor dungeon x ``classic_eq`` x ``temple`` and ``fortress``;
- a big race (ogre) and the dragon, in a dungeon on both sets and (the ogre)
  under a hill. Not the dragon under a hill: at ``flat`` it rarely plans
  (EnvelopeFitError, archive follow-up "Giant and dragon outdoor dungeons
  drop rooms"), and stacked its long U-route stairs run past the map edge
  under the boundary, which the bowl gate reads as a leak (reported from
  task 9; the fit is in ``generators/outdoor_dungeon.py``).

Every stacked build (``moderate``, ``dramatic``) must pass within the
pipeline's retry budget. The same plans are built at ``flat`` (step 6's graph
build) on the same attempt seeds (the pipeline draws them from
``random.Random(seed)``), and each stacked setting's first-attempt pass rate
must be no worse than flat's. The rates are printed (``-s`` shows them).

Also here: a stacked build is reproducible (the PFS footer's write time aside,
lessons-learned "Two .eqg writes are never byte-identical").

A passing sweep is necessary, not sufficient: nothing here is looked at in the
3D viewer (task 10 does that).
"""

import random

import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators.builder import ZoneBuilder, room_levels
from generators.pipeline import DEFAULT_MAX_ATTEMPTS, GenerationFailed, generate_validated

STACKED = ("moderate", "dramatic")

#: name -> (zone type, base set, theme, race, room counts, sweep seeds,
#: stacked settings). One parametrized case per theme so the default parallel
#: run spreads them over its workers.
SWEEPS = {
    **{f"dungeon-{rs}-{th or 'plain'}": ("dungeon", rs, th, "", (5, 10, 16), range(4), STACKED)
       for rs in ("classic_eq", "warren") for th in ("", "temple", "fortress")},
    **{f"outdoor_dungeon-classic_eq-{th}": ("outdoor_dungeon", "classic_eq", th, "", (3, 5, 8),
                                            range(3), STACKED)
       for th in ("temple", "fortress")},
    **{f"dungeon-{rs}-{race}": ("dungeon", rs, "", race, (8,), range(4), STACKED)
       for rs in ("classic_eq", "warren") for race in ("ogre", "dragon")},
    "outdoor_dungeon-classic_eq-ogre": ("outdoor_dungeon", "classic_eq", "temple", "ogre", (5,),
                                        range(4), ("moderate",)),
}


def _plan(zone_type, rule_set, theme, race, rooms, verticality, name="vsweep"):
    return ZonePlan(name=name, zone_type=zone_type, room_count=rooms, dungeon_theme=theme,
                    dungeon_race=race, layout="graph", rule_set=rule_set,
                    verticality=verticality).validate()


def _generate(tmp_path, plan, seed, max_attempts):
    """The pipeline's build -> gate -> retry loop; the attempts it took, or
    None when the budget ran out."""
    try:
        vb = generate_validated(lambda s: plan_to_spec(plan, seed=s),
                                zone_type=plan.zone_type, zone_id=plan.name,
                                output_dir=tmp_path, write_glb=False,
                                rng=random.Random(seed), failure_log=None,
                                max_attempts=max_attempts, timeout_s=600.0)
    except GenerationFailed:
        return None
    assert vb.validated
    return vb.attempts


@pytest.mark.slow
@pytest.mark.parametrize("sweep", sorted(SWEEPS))
def test_stacked_builds_pass_the_gate_no_worse_than_flat(tmp_path, sweep):
    zone_type, rule_set, theme, race, counts, seeds, stacked = SWEEPS[sweep]
    cases = [(n, s) for n in counts for s in seeds]
    runs = {v: {} for v in ("flat",) + stacked}
    failed = []
    for k, (rooms, seed) in enumerate(cases):
        for v in runs:
            # Flat is step 6's graph build: its first attempt is the bar.
            budget = 1 if v == "flat" else DEFAULT_MAX_ATTEMPTS
            a = _generate(tmp_path / f"{v}{k}",
                          _plan(zone_type, rule_set, theme, race, rooms, v), seed, budget)
            runs[v][rooms, seed] = a
            if a is None and v != "flat":
                failed.append((v, rooms, seed))
    first = {v: sum(a == 1 for a in r.values()) for v, r in runs.items()}
    retries = {v: sum(a - 1 for a in runs[v].values() if a) for v in stacked}
    print(f"\n{sweep}: first-attempt " +
          ", ".join(f"{v} {first[v]}/{len(cases)}" for v in runs) +
          "; retries " + ", ".join(f"{v} {retries[v]}" for v in stacked))
    assert not failed, f"stacked builds out of retries: {failed}"
    for v in stacked:
        assert first[v] >= first["flat"], (sweep, v, first)


@pytest.mark.slow
@pytest.mark.parametrize("zone_type, rule_set, theme, race, rooms, verticality, seed", [
    ("dungeon", "warren", "temple", "", 10, "dramatic", 21),
    ("dungeon", "classic_eq", "", "ogre", 8, "moderate", 3),
    ("outdoor_dungeon", "classic_eq", "fortress", "", 5, "moderate", 4),
])
def test_same_inputs_same_eqg(tmp_path, zone_type, rule_set, theme, race, rooms,
                              verticality, seed):
    """V10 / Req 9.3: a stacked build is reproducible (the PFS footer's write
    time aside)."""
    plan = _plan(zone_type, rule_set, theme, race, rooms, verticality, name="vrepro")
    eqgs = []
    for k in range(2):
        spec = plan_to_spec(plan, seed=seed)
        assert len(set(room_levels(spec).values())) > 1, "not a stacked build"
        result = ZoneBuilder(spec).build(output_dir=tmp_path / str(k), write_glb=False)
        eqgs.append(result.eqg_path.read_bytes())
    assert eqgs[0][:-4] == eqgs[1][:-4]
