"""
tests/test_wilderness_bowl.py
-----------------------------
The ONE built-mesh property for the wilderness generator (spec
``zone-generator-wilderness``, wave 4) — Property 15: the bowl holds on the
*real built mesh*.

Unlike the matrix properties (``tests/test_wilderness_matrix.py``, pure data)
and the heightfield/erosion properties (``tests/test_wilderness_synth.py``, on
the synthesized field), this module drives the FULL project build path and runs
the project traversability agent on the REAL TER triangles the bowl assembly
produces:

    build_matrix -> rewrite_matrix -> synthesize_heightfield
                 -> assemble_bowl  -> check_bowl (builds the TER + floods it)

so it is a build-tier property: ``@pytest.mark.slow`` with the repo's
``build_settings(n)`` budget (design Testing Strategy: Property 15 is the one
slow built-mesh property; 10-25% budget). It is deterministic from the seed.

A separate, deterministic (NOT ``@given``) negative test proves the gate
actually DETECTS a leak: a deliberately breached mesh — a corridor flattened
through a sealed mountain Rim segment — is caught as a ``BowlLeak`` naming that
segment. Without that guard, "clean bowls pass" could be vacuously true.

Budgets follow the repo convention (``tests/pbt_helpers.build_settings`` scales
with the active Hypothesis profile registered in ``tests/conftest.py``).
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings

from tests.pbt_helpers import build_settings

# The bowl assembly + the built-mesh gate (wave 4, tasks 9.x / 10.2).
from generators.wilderness.bowl import (
    BowlLeak,
    BowlResult,
    ReachabilityFailure,
    ZonelineFailure,
    assemble_bowl,
    build_bowl_ter,
    check_bowl,
)
from generators.wilderness.rewrite import rewrite_matrix
from generators.wilderness.synth import synthesize_heightfield

# Reuse the SHARED matrix-suite scaffolding: the input-space strategies
# (biomes / edge_declarations / seeds, spanning the all-mountain sealed case,
# mixed river/zoneline, and the four-side default) and the build_matrix
# indirection + skip marker. No strategies are duplicated here.
from tests.test_wilderness_matrix import (
    biomes,
    build_matrix,
    edge_declarations,
    requires_build_matrix,
    seeds,
)


# ---------------------------------------------------------------------------
# Build-path helper (the project build path, through to the built mesh)
# ---------------------------------------------------------------------------
def _assemble(biome, edges, seed) -> tuple:
    """Run the full project build path to a built bowl, deterministically.

    ``build_matrix -> rewrite_matrix(.).matrix -> synthesize_heightfield ->
    assemble_bowl`` — the exact sequence the wave-3 synth suite and the wave-5
    backend use (the finalized matrix the synth runs on is the rewrite fixed
    point). Returns ``(bowl, synth, matrix)`` so the gate (and the negative
    probe) can run on the same built field. Seed-led: same seed -> same bowl.
    """
    matrix = rewrite_matrix(build_matrix(biome, edges, seed)).matrix
    synth = synthesize_heightfield(matrix, seed=seed)
    bowl = assemble_bowl(synth, matrix)
    return bowl, synth, matrix


# ---------------------------------------------------------------------------
# Property 15 — the bowl holds on the BUILT MESH (build-tier, slow)
# ---------------------------------------------------------------------------
# The single ``@pytest.mark.slow`` + ``build_settings(..)`` property in the
# wilderness suite: it builds the real TER (``build_bowl_ter``, run inside
# ``check_bowl``) and runs the project per-triangle traversability agent on it.
# build_settings(12) keeps the budget at the low end of the design's 10-25 band
# (each example is a full matrix -> rewrite -> synth -> assemble -> build-TER ->
# flood, the heaviest per-example work in the wilderness suite), matching how
# the other slow built-mesh properties (test_properties_build / _core /
# _pipeline) set n. Deterministic from the seed; deadline disabled by
# build_settings (a real build is slow).


@pytest.mark.slow
@requires_build_matrix
@build_settings(12)
@given(biome=biomes, edges=edge_declarations(), seed=seeds)
def test_property15_bowl_holds_on_built_mesh(biome, edges, seed):
    """Feature: zone-generator-wilderness, Property 15: The bowl holds on the
    built mesh — reachable interior, sealed Rim.

    Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.6, 12.1, 12.2.

    Over a plains-Karana spec with VARIED edge declarations (all-mountain
    sealed, mixed river/zoneline, single zoneline, four-side default) and
    seeds, build the REAL TER via the project build path and run the project
    traversability agent on it (``check_bowl`` -> ``build_bowl_ter`` ->
    ``build_walk_surface`` + flood). On that real built mesh:

      * every Playable_Region cell / POI anchor is reachable from Spawn by the
        agent, Scenic_Regions excluded — no ``ReachabilityFailure`` (Req 4.2,
        4.6, 12.1, 12.2);
      * no path from Spawn reaches an off-map marker except through a
        ``zoneline`` segment — no ``BowlLeak`` (a leak names the breached Rim
        segment) (Req 4.3, 4.4);
      * every ``zoneline`` gap is reachable from Spawn AND leads off-map — no
        ``ZonelineFailure`` (Req 4.5);
      * overall the result is a PASS.

    A genuine failure here is a REAL bowl bug (a leak or a stranded playable
    region), not a test to weaken: the failure objects name the offending
    segment / cell and ``result.summary()`` is attached for the 3D-pass diag.
    """
    bowl, synth, matrix = _assemble(biome, edges, seed)

    result = check_bowl(bowl, synth, matrix)

    # Fail LOUD and NAMED: a stranded playable cell, a breached Rim segment, or
    # a dead zoneline each surface with the offender named + the built-mesh diag.
    assert not result.unreachable, (
        f"stranded playable region(s) on the built mesh "
        f"(biome={biome!r}, seed={seed}, edges={[(e.side, e.edge_type) for e in edges]}):\n"
        + "\n".join(f"  - {u}" for u in result.unreachable)
        + f"\n{result.summary()}"
    )
    assert not result.leaks, (
        f"BOWL LEAK on the built mesh — the flood escaped a non-zoneline Rim "
        f"segment (biome={biome!r}, seed={seed}, "
        f"edges={[(e.side, e.edge_type) for e in edges]}):\n"
        + "\n".join(f"  - {leak}" for leak in result.leaks)
        + f"\n{result.summary()}"
    )
    assert not result.zoneline_failures, (
        f"zoneline gap not reachable-and-off-map on the built mesh "
        f"(biome={biome!r}, seed={seed}, edges={[(e.side, e.edge_type) for e in edges]}):\n"
        + "\n".join(f"  - {zf}" for zf in result.zoneline_failures)
        + f"\n{result.summary()}"
    )
    # The composite verdict (redundant with the three above, but asserts the
    # gate's own PASS flag is wired to exactly those three failure lists).
    assert result.passed, (
        f"bowl gate did not PASS on the built mesh despite no listed failures "
        f"(biome={biome!r}, seed={seed}):\n{result.summary()}"
    )


# ---------------------------------------------------------------------------
# Negative guard — the gate CATCHES a deliberately breached Rim (deterministic)
# ---------------------------------------------------------------------------
# Not inside the @given body and NOT slow: a handful of fixed seeds, each built
# ONCE, breached ONCE, re-checked ONCE. This proves Property 15 is not vacuous —
# a clean bowl passing only means something if a broken bowl fails. The breach
# mirrors 10.2's negative probe: flatten a walkable corridor from the interior
# OUT through a sealed `mountain` Rim segment so the Spawn flood escapes into
# that segment's off-map band, and assert the gate reports a BowlLeak naming it.

#: Fixed seeds for the deterministic negative probe. All-mountain edges so every
#: perimeter segment is a sealed `mountain` Rim (the breach target is unambiguous
#: and no zoneline provides a legitimate off-map escape).
_BREACH_SEEDS = (1, 7, 42, 1955208177)


def _all_mountain_edges():
    """Four-side all-``mountain`` declaration (fully sealed bowl) for the probe.

    Reuses the shared ``edge_declarations`` SIDES/EdgeConnection shape by asking
    build_matrix for a sealed bowl; built directly here (not drawn) so the
    negative test stays deterministic.
    """
    from generators.wilderness import EdgeConnection

    return [EdgeConnection(side=s, edge_type="mountain") for s in ("N", "E", "S", "W")]


def _breach_mountain_segment(bowl: BowlResult, synth, matrix) -> str:
    """Flatten a walkable corridor from the interior out through one sealed
    ``mountain`` Rim segment, in place on ``bowl.heights``. Returns the
    ``segment_id`` string the gate will use for that segment, so the test can
    assert the named leak matches the breach.

    The corridor is a strip of fine cells from near Spawn straight to the
    perimeter along a chosen mountain segment, pulled DOWN to the local interior
    floor level so the agent can walk it (the sealed rim's steep inner face is
    the only thing stopping the flood; remove it and the flood escapes). This is
    the built-mesh analogue of 10.2's negative probe.
    """
    node_type = synth.node_type
    heights = bowl.heights
    nx, ny = heights.shape
    res = float(synth.resolution)
    ox, oy = synth.origin

    # Pick the first mountain segment that owns fine perimeter cells.
    from generators.wilderness.bowl import _fine_cells_for_side

    target_seg = None
    for seg_idx, ec in enumerate(matrix.edges):
        if ec.edge_type != "mountain":
            continue
        if _fine_cells_for_side(synth, matrix, seg_idx):
            target_seg = (seg_idx, ec)
            break
    assert target_seg is not None, "no mountain segment with fine cells to breach"
    seg_idx, ec = target_seg
    seg_id = f"{ec.side}:{seg_idx}:{ec.edge_type}"

    # Interior floor level to flatten the corridor to: the median height over the
    # playable interior (what Spawn actually stands on).
    interior = np.asarray(synth.playable_interior_mask, dtype=bool)
    floor_z = float(np.median(heights[interior])) if interior.any() else float(np.median(heights))

    # Spawn fine-cell centre.
    factor = max(1, int(round(matrix.cell_size / res)))
    cx, cy = matrix.spawn
    si = min(max(int((cx + 0.5) * factor), 0), nx - 1)
    sj = min(max(int((cy + 0.5) * factor), 0), ny - 1)

    # The segment's perimeter fine cells; aim the corridor at their centroid.
    seg_cells = _fine_cells_for_side(synth, matrix, seg_idx)
    ti = int(round(np.mean([i for (i, _) in seg_cells])))
    tj = int(round(np.mean([j for (_, j) in seg_cells])))

    # Rasterise a straight fine-cell corridor Spawn -> segment and flatten it,
    # widened by one cell each side so the walk surface has a continuous ribbon.
    steps = max(abs(ti - si), abs(tj - sj)) + 1
    for t in np.linspace(0.0, 1.0, steps * 2):
        pi = int(round(si + (ti - si) * t))
        pj = int(round(sj + (tj - sj) * t))
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                qi, qj = pi + di, pj + dj
                if 0 <= qi < nx and 0 <= qj < ny:
                    heights[qi, qj] = floor_z
    return seg_id


@requires_build_matrix
@pytest.mark.parametrize("seed", _BREACH_SEEDS)
def test_breached_mountain_rim_is_caught_as_bowl_leak(seed):
    """A deliberately breached Rim is CAUGHT — Property 15's negative guard.

    Validates: Requirements 4.3, 4.4 (the gate DETECTS a leak, not just that
    clean bowls pass). Deterministic (fixed seeds, no @given). Builds a fully
    sealed all-mountain Karana, flattens a walkable corridor out through one
    ``mountain`` Rim segment, re-runs ``check_bowl`` on that breached mesh, and
    asserts the gate reports a ``BowlLeak`` naming exactly the breached segment.
    """
    edges = _all_mountain_edges()
    bowl, synth, matrix = _assemble("plains", edges, seed)

    # Sanity: the clean, sealed bowl passes BEFORE we breach it (so the leak we
    # assert below is caused by the breach, not a pre-existing failure).
    clean = check_bowl(bowl, synth, matrix)
    assert clean.passed, (
        f"clean all-mountain bowl should pass before breaching (seed={seed}):\n"
        f"{clean.summary()}"
    )

    breached_seg = _breach_mountain_segment(bowl, synth, matrix)
    result = check_bowl(bowl, synth, matrix)

    assert result.leaks, (
        f"breaching mountain segment {breached_seg!r} produced NO BowlLeak — "
        f"the gate failed to detect a hole walked through a sealed Rim "
        f"(seed={seed}):\n{result.summary()}"
    )
    leaked_ids = {leak.segment_id for leak in result.leaks}
    assert breached_seg in leaked_ids, (
        f"the reported leak(s) {sorted(leaked_ids)} do not name the breached "
        f"segment {breached_seg!r} (seed={seed}):\n{result.summary()}"
    )
    assert not result.passed, (
        f"a breached bowl must not PASS (seed={seed}):\n{result.summary()}"
    )
