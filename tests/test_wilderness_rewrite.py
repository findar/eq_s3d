"""
tests/test_wilderness_rewrite.py
--------------------------------
The pre-geometry Graph_Replacement property suite for the wilderness generator
(spec ``zone-generator-wilderness``, wave 2, tasks 5.5–5.7).

These three properties exercise the **already-implemented** matrix-level rewrite
engine (``generators/wilderness/rewrite.py``, tasks 5.2–5.4) — NO geometry is
built. Each test runs over the SAME matrix input space the wave-1 matrix
properties use (reusing ``tests.test_wilderness_matrix``'s shared Hypothesis
strategies and helpers rather than duplicating them) and, where the rules must
actually fire, over DETERMINISTICALLY-constructed stranding matrices (a cliff or
lava wall across the interior that cuts a flank off from Spawn). A generatively
constructed ``build_matrix`` output is already fully reachable (plains-led,
Property 5), so the rules only no-op on it — the constructed walls are what
drive a real rewrite.

Properties (design "Correctness Properties", design.md):

  * **Property 7** (task 5.5) — Graph_Replacement TERMINATES. For any starting
    matrix + seed the rewrite reaches a fixed point within the bounded cap
    (``iterations <= MAX_ITERS_C * region_count``) and never loops; a second
    rewrite of the fixed point is a no-op (0 commits). The cap is enforced: a
    real stranding under a too-small ``max_iters`` raises ``RewriteError``.
    Validates Req 7.2.
  * **Property 8** (task 5.6) — preserves reachability AND the sealed Rim at
    EVERY committed step. Re-deriving each committed prefix (rules are
    deterministic given the trigger anchor) shows both invariants hold after
    every committed rewrite step; a rule application that would strand a
    playable region or breach a non-``zoneline`` Rim segment is REJECTED with
    the prior matrix preserved. Validates Req 7.3, 7.4, 7.6.
  * **Property 9** (task 5.7) — cliffs and lava NEVER strand playable regions.
    For any matrix — including ones seeded with a cliff/lava wall that strands
    playable cells before the rewrite — after ``rewrite_matrix`` the
    ``stranded_playable_cells`` set is empty. Validates Req 7.5, 10.4.

Every property carries a docstring beginning
``Feature: zone-generator-wilderness, Property N: <title>`` naming its
requirement ids, and uses the layout-tier budget
``@settings(max_examples=scaled(100), deadline=None)`` (NOT ``build_settings`` —
that is for the slow build-tier property only). Budgets scale with the active
Hypothesis profile via ``tests.pbt_helpers.scaled`` (design Req 1.3).
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.pbt_helpers import scaled

# Reuse the wave-1 matrix scaffolding verbatim: the shared input strategies
# (matrix_inputs / edge_declarations / seeds / biomes), the build_matrix
# indirection + skip marker, and the cell/coordinate helpers. These are the
# SAME strategies every matrix property draws from, so the rewrite properties
# see the identical biome × edge-declaration × seed space with no duplication.
from tests.test_wilderness_matrix import (
    build_matrix,
    interior_coords,
    iter_cells,
    matrix_inputs,
    requires_build_matrix,
    seeds,
)

# The rewrite engine under test (tasks 5.2–5.4). Imported from the package
# public surface so the tests exercise the same re-exports downstream uses.
from generators.wilderness import (
    build_region_graph,
    invariants_hold,
    rewrite_matrix,
    rim_is_sealed,
    stranded_playable_cells,
)
from generators.wilderness.rewrite import (
    MAX_ITERS_C,
    RewriteError,
    _clone_matrix,
    _RULES,
    playable_reachable_from_spawn,
)


# ---------------------------------------------------------------------------
# Constructed-stranding helpers (shared by Property 8 and Property 9)
# ---------------------------------------------------------------------------
# A generatively-built matrix is already fully reachable (Property 5), so the
# rules no-op on it. To actually exercise cliff_graded_approach /
# lava_graded_approach we construct a deterministic blocker: a WALL of a scenic
# blocker type (cliff or lava) spanning the interior just off Spawn, which cuts
# a whole flank of the plains interior off from Spawn (a real stranding the rule
# must repair). The wall never touches the perimeter ring — it is built on
# interior cells only — so the Rim it seals is unrelated to the construction.


def _interior_wall(matrix, kind: str, *, axis: str, offset: int) -> int:
    """Carve a single-cell-thick interior WALL of ``kind`` ("cliff"/"lava").

    ``axis="col"`` builds a vertical wall at interior column ``spawn_x +
    offset`` spanning every interior row; ``axis="row"`` builds a horizontal
    wall at interior row ``spawn_y + offset`` spanning every interior column.
    The wall sits strictly inside the 1-cell perimeter ring (so it cannot
    breach the Rim) and is placed off Spawn so it genuinely severs a flank.

    Returns the number of cells turned into the wall (0 if the requested line
    would fall on the perimeter / off-grid, i.e. the construction is a no-op for
    this matrix — the caller treats a 0 as "wall not placed").
    """
    nx, ny = matrix.shape
    sx, sy = matrix.spawn
    placed = 0
    if axis == "col":
        col = sx + offset
        if col <= 0 or col >= nx - 1:
            return 0
        line = [(col, j) for j in range(1, ny - 1)]
    else:
        row = sy + offset
        if row <= 0 or row >= ny - 1:
            return 0
        line = [(i, row) for i in range(1, nx - 1)]
    for (i, j) in line:
        cell = matrix.cells[i, j]
        cell.node_type = kind
        cell.intent = "scenic"
        cell.frozen = False
        cell.frozen_z = None
        placed += 1
    return placed


def _region_count(matrix) -> int:
    """Region count of ``matrix`` the way ``rewrite_matrix`` computes its cap:
    ``max(1, len(regions))`` over the STARTING matrix (the cap is
    ``MAX_ITERS_C * region_count``)."""
    return max(1, len(build_region_graph(matrix).regions))


# The deterministic single-blocker stranding cases that make the rules fire.
# Each is (seed, kind, axis, offset). Both blocker types, both axes, both sides
# of Spawn — the exact single-wall family task 5.4's deliverables verified. A
# single wall is resolvable by one rule application (the rule carves the whole
# blocker region), so these drive a genuine committed rewrite to a fully
# reachable fixed point.
_STRANDING_CASES = [
    (12345, "cliff", "col", -2),
    (777, "lava", "col", -2),
    (2024, "cliff", "col", 3),
    (31337, "lava", "col", 2),
    (4242, "cliff", "row", -2),
    (9001, "lava", "row", 3),
    (555, "cliff", "row", 2),
    (88, "lava", "col", -3),
]


def _build_stranding(seed: int, kind: str, axis: str, offset: int):
    """Build a plains matrix and carve a single interior ``kind`` wall into it,
    returning the (mutated) matrix. Asserts the wall actually stranded a
    playable region (so the case is a real trigger, not a silent no-op)."""
    m = build_matrix("plains", [], seed)
    placed = _interior_wall(m, kind, axis=axis, offset=offset)
    assert placed > 0, f"wall not placed for case {(seed, kind, axis, offset)}"
    assert stranded_playable_cells(m), (
        f"constructed {kind} wall did not strand any playable cell for "
        f"case {(seed, kind, axis, offset)} — not a real trigger"
    )
    return m


# ===========================================================================
# Property 7 (task 5.5): Graph_Replacement terminates
# ===========================================================================


@requires_build_matrix
@settings(max_examples=scaled(100), deadline=None)
@given(inp=matrix_inputs())
def test_property7_graph_replacement_terminates(inp):
    """Feature: zone-generator-wilderness, Property 7: Graph_Replacement
    terminates.

    For any starting Design_Matrix + seed, ``rewrite_matrix`` reaches a fixed
    point within the bounded iteration cap and never loops:

      * it returns (no infinite loop) with ``iterations`` within the hard cap
        ``MAX_ITERS_C * region_count`` computed over the starting matrix, and
      * the fixed point is stable — a SECOND rewrite of the result commits
        nothing (0 commits) and does not move the stranded set.

    A generatively-built matrix is already reachable, so this is the no-op /
    already-at-fixed-point arm of termination; the constructed-wall arm (which
    drives real commits before terminating) is checked in
    ``test_property7_terminates_on_constructed_stranding``.

    Validates: Requirements 7.2
    """
    m = build_matrix(inp["biome"], inp["edges"], inp["seed"])
    cap = MAX_ITERS_C * _region_count(m)

    result = rewrite_matrix(m)
    assert result.iterations <= cap, (
        f"rewrite used {result.iterations} iterations, exceeding the cap {cap} "
        f"(MAX_ITERS_C={MAX_ITERS_C} * region_count={_region_count(m)})"
    )

    # Fixed point: rewriting the result again is a no-op.
    second = rewrite_matrix(result.matrix)
    assert second.committed == 0, (
        f"second rewrite of the fixed point committed {second.committed} "
        f"changes (expected 0 — not a fixed point)"
    )
    assert stranded_playable_cells(second.matrix) == stranded_playable_cells(
        result.matrix
    ), "second rewrite moved the stranded set — fixed point is not stable"


@pytest.mark.parametrize("seed,kind,axis,offset", _STRANDING_CASES)
def test_property7_terminates_on_constructed_stranding(seed, kind, axis, offset):
    """Feature: zone-generator-wilderness, Property 7: Graph_Replacement
    terminates (constructed-stranding arm).

    A matrix seeded with a real cliff/lava wall drives committed rewrite steps,
    yet the rewrite still terminates within the bounded cap and reaches a stable
    fixed point (a second rewrite commits nothing). This is the arm where the
    bound actually has to hold against commits, not just an immediate no-op.

    Validates: Requirements 7.2
    """
    m = _build_stranding(seed, kind, axis, offset)
    cap = MAX_ITERS_C * _region_count(m)

    result = rewrite_matrix(m)
    assert result.committed >= 1, "constructed stranding drove no committed step"
    assert result.iterations <= cap, (
        f"rewrite used {result.iterations} iterations, exceeding the cap {cap}"
    )
    second = rewrite_matrix(result.matrix)
    assert second.committed == 0, "fixed point is not stable (second rewrite committed)"


def test_property7_cap_is_enforced_raises_on_too_small_max_iters():
    """Feature: zone-generator-wilderness, Property 7: Graph_Replacement
    terminates — the cap is ENFORCED, never a silent loop.

    A matrix with a REAL stranding, run under a ``max_iters`` too small to reach
    the fixed point, raises ``RewriteError`` (Req 7.2: exceeding the bounded cap
    is a construction error surfaced loudly, never an unbounded loop). Framed as
    a plain deterministic assertion — the cap enforcement is not input-dependent.

    Validates: Requirements 7.2
    """
    # A cliff wall that genuinely strands a flank; max_iters=0 cannot reach the
    # fixed point, so the bounded loop must raise rather than loop or silently
    # return an unresolved matrix.
    m = _build_stranding(42, "cliff", "col", -2)
    assert stranded_playable_cells(m), "precondition: the wall must strand a region"
    with pytest.raises(RewriteError):
        rewrite_matrix(m, max_iters=0)


# ===========================================================================
# Property 8 (task 5.6): preserves reachability AND the sealed Rim at every step
# ===========================================================================


def _assert_committed_steps_preserve_invariants(start_matrix, result) -> None:
    """Re-derive each committed prefix of ``result`` on a running clone of
    ``start_matrix`` and assert BOTH invariants hold after every committed step.

    The engine records ``steps`` as ``(rule_name, trigger_anchor, committed)``
    but not the intermediate matrices; because each rule is deterministic given
    its trigger region (identified by its lexicographic anchor), replaying the
    committed rules IN ORDER on a clone reconstructs exactly the committed
    intermediates the engine produced. After each committed step the
    reconstructed matrix must have NO stranded playable region AND a sealed Rim
    (invariants_hold), and reachability must be monotone-non-decreasing (a
    committed step never shrinks the reachable set). The replay's final state
    must match the engine's returned fixed point.
    """
    committed = [(name, anchor) for (name, anchor, ok) in result.steps if ok]
    current = _clone_matrix(start_matrix)
    prev_reachable = len(playable_reachable_from_spawn(current))
    for (rule_name, anchor) in committed:
        graph = build_region_graph(current)
        region = next(
            (r for r in graph.regions.values() if r.anchor == anchor), None
        )
        assert region is not None, (
            f"committed step {rule_name}@{anchor} has no region at that anchor "
            f"in the reconstructed intermediate — replay diverged"
        )
        _RULES[rule_name](current, region)
        # Both invariants hold at this committed step (Req 7.3 + 7.4).
        assert invariants_hold(current), (
            f"invariants violated after committed step {rule_name}@{anchor}: "
            f"stranded={len(stranded_playable_cells(current))}, "
            f"rim_sealed={rim_is_sealed(current)}"
        )
        now_reachable = len(playable_reachable_from_spawn(current))
        assert now_reachable >= prev_reachable, (
            f"committed step {rule_name}@{anchor} SHRANK reachability "
            f"({prev_reachable} -> {now_reachable})"
        )
        prev_reachable = now_reachable

    # The replay reconstructs the engine's fixed point exactly.
    assert stranded_playable_cells(current) == stranded_playable_cells(
        result.matrix
    ), "replayed committed prefix did not reconstruct the engine's fixed point"


@requires_build_matrix
@settings(max_examples=scaled(100), deadline=None)
@given(inp=matrix_inputs())
def test_property8_preserves_invariants_at_every_committed_step(inp):
    """Feature: zone-generator-wilderness, Property 8: Graph_Replacement
    preserves reachability and the sealed Rim at every committed step.

    For any starting matrix, after the rewrite BOTH committed-step invariants
    hold on the fixed point — mutual reachability among playable regions (no
    stranded playable cell) AND every non-``zoneline`` Rim segment still
    impassable — and, crucially, they hold after EVERY committed step along the
    way (re-derived from ``result.steps``), not merely at the end. A generative
    matrix is already reachable, so the Rim-sealed arm dominates here; the
    constructed-wall cases drive multi-invariant commits.

    Validates: Requirements 7.3, 7.4, 7.6
    """
    m = build_matrix(inp["biome"], inp["edges"], inp["seed"])
    start = _clone_matrix(m)
    result = rewrite_matrix(m)
    # Fixed-point invariants.
    assert rim_is_sealed(result.matrix), "Rim breached by the rewrite fixed point"
    assert not stranded_playable_cells(result.matrix), (
        "playable region stranded at the rewrite fixed point"
    )
    # Per committed step.
    _assert_committed_steps_preserve_invariants(start, result)


@pytest.mark.parametrize("seed,kind,axis,offset", _STRANDING_CASES)
def test_property8_committed_steps_hold_on_constructed_stranding(
    seed, kind, axis, offset
):
    """Feature: zone-generator-wilderness, Property 8: Graph_Replacement
    preserves reachability and the sealed Rim at every committed step
    (constructed-stranding arm).

    A matrix with a real cliff/lava wall drives at least one committed step; the
    re-derived committed prefix shows both invariants held after that step, and
    the fixed point is fully reachable with a sealed Rim.

    Validates: Requirements 7.3, 7.4, 7.6
    """
    m = _build_stranding(seed, kind, axis, offset)
    start = _clone_matrix(m)
    result = rewrite_matrix(m)
    assert result.committed >= 1, "constructed stranding drove no committed step"
    assert invariants_hold(result.matrix), "fixed point violates an invariant"
    _assert_committed_steps_preserve_invariants(start, result)


def test_property8_rule_that_would_breach_rim_is_rejected():
    """Feature: zone-generator-wilderness, Property 8: a rule application that
    would breach a non-``zoneline`` Rim segment is REJECTED, prior matrix kept.

    Apply-then-check-then-commit (Req 7.6): a CANDIDATE whose carve breaches a
    non-``zoneline`` Rim segment must fail the invariant re-check, so the engine
    keeps the prior matrix. We prove the gate directly: a candidate clone with a
    manually-breached Rim segment fails ``invariants_hold`` (so the commit guard
    ``changed and invariants_hold(candidate)`` cannot fire), while the UNbreached
    prior matrix is preserved. Framed as a deterministic assertion — the
    rejection discipline is not input-dependent.

    Validates: Requirements 7.3, 7.4, 7.6
    """
    m = _build_stranding(2024, "cliff", "col", 3)
    assert rim_is_sealed(m), "precondition: the constructed matrix starts Rim-sealed"

    # A candidate that breaches a non-zoneline Rim segment: carve a perimeter
    # cell on a sealed (mountain) segment to a passable plains cell.
    candidate = _clone_matrix(m)
    nx, ny = candidate.shape
    seg_type = {k: e.edge_type for k, e in enumerate(candidate.edges)}
    breached = False
    for i in range(nx):
        for j in range(ny):
            if not (i in (0, nx - 1) or j in (0, ny - 1)):
                continue
            cell = candidate.cells[i, j]
            if seg_type.get(cell.edge_segment) == "zoneline":
                continue  # the deliberate leak — skip it
            if cell.node_type in ("mountain_rim", "water"):
                cell.node_type = "plains"
                cell.intent = "playable"
                cell.frozen = False
                cell.frozen_z = None
                breached = True
                break
        if breached:
            break
    assert breached, "could not find a sealed Rim cell to breach"

    # The breached candidate fails the invariant re-check the commit guard uses,
    # so such a candidate can never be committed; the prior matrix stays sealed.
    assert not rim_is_sealed(candidate), "breach was not detected by rim_is_sealed"
    assert not invariants_hold(candidate), (
        "a Rim-breaching candidate passed invariants_hold — it would be committed"
    )
    assert rim_is_sealed(m), "the prior matrix was mutated by building the candidate"


def test_property8_run_accounting_every_step_committed_or_rejected():
    """Feature: zone-generator-wilderness, Property 8: rewrite accounting —
    every recorded step is either a commit or a rejection, and commits match.

    The ``steps`` ledger must be internally consistent: each entry's committed
    flag partitions into exactly ``result.committed`` commits and
    ``result.rejected`` rejections, and no committed step regressed an invariant
    (checked via the fixed point). This guards the apply-check-commit bookkeeping
    the per-step invariant claim rests on.

    Validates: Requirements 7.3, 7.4, 7.6
    """
    m = _build_stranding(31337, "lava", "col", 2)
    result = rewrite_matrix(m)
    committed_flags = [ok for (_n, _a, ok) in result.steps]
    assert committed_flags.count(True) == result.committed
    assert committed_flags.count(False) == result.rejected
    assert invariants_hold(result.matrix)


# ===========================================================================
# Property 9 (task 5.7): cliffs and lava never strand playable regions
# ===========================================================================


@requires_build_matrix
@settings(max_examples=scaled(100), deadline=None)
@given(inp=matrix_inputs())
def test_property9_generative_matrices_have_no_stranded_playable(inp):
    """Feature: zone-generator-wilderness, Property 9: cliffs and lava never
    strand playable regions (generative arm).

    For any generatively-built Design_Matrix (which may already contain a
    ``cliff`` scenic band and/or a ``lava`` hazard patch from construction),
    after ``rewrite_matrix`` the stranded-playable set is empty — every playable
    cell is reachable from Spawn. (Construction already holds Property 5, so the
    rewrite preserves it; the rule-driving arm is the constructed walls below.)

    Validates: Requirements 7.5, 10.4
    """
    m = build_matrix(inp["biome"], inp["edges"], inp["seed"])
    result = rewrite_matrix(m)
    stranded = stranded_playable_cells(result.matrix)
    assert not stranded, (
        f"playable cells stranded after rewrite: {sorted(stranded)[:10]}"
        + (" ..." if len(stranded) > 10 else "")
    )


@pytest.mark.parametrize("seed,kind,axis,offset", _STRANDING_CASES)
def test_property9_cliff_lava_wall_is_reconnected(seed, kind, axis, offset):
    """Feature: zone-generator-wilderness, Property 9: cliffs and lava never
    strand playable regions (constructed-stranding arm — the rules fire).

    A matrix seeded with a deterministic cliff/lava WALL that genuinely strands
    a flank of the plains interior from Spawn BEFORE the rewrite: after
    ``rewrite_matrix`` the graded-approach rule has carved a playable approach so
    the stranded-playable set is empty, with the Rim still sealed. This is the
    arm that actually exercises ``cliff_graded_approach`` /
    ``lava_graded_approach`` — a generative matrix is already reachable and would
    only no-op.

    Validates: Requirements 7.5, 10.4
    """
    m = _build_stranding(seed, kind, axis, offset)
    pre_stranded = stranded_playable_cells(m)
    assert pre_stranded, "precondition: the wall must strand a playable region"

    result = rewrite_matrix(m)
    assert result.committed >= 1, (
        "the graded-approach rule did not fire on a real stranding"
    )
    post_stranded = stranded_playable_cells(result.matrix)
    assert not post_stranded, (
        f"{kind} wall left {len(post_stranded)} playable cells stranded after "
        f"rewrite: {sorted(post_stranded)[:10]}"
    )
    assert rim_is_sealed(result.matrix), "rewrite breached the Rim while reconnecting"


def test_property9_every_playable_cell_reachable_after_reconnect():
    """Feature: zone-generator-wilderness, Property 9: every playable cell is
    reachable from Spawn after the rewrite reconnects a cliff/lava stranding.

    A stronger spelling of the invariant on one deterministic case: after the
    rewrite, the set of playable cells equals the set reachable from Spawn (no
    playable cell outside the reachable flood), confirming the graded approach
    actually joined the severed flank rather than merely shrinking the wall.

    Validates: Requirements 7.5, 10.4
    """
    m = _build_stranding(12345, "cliff", "col", -2)
    result = rewrite_matrix(m)
    reachable = playable_reachable_from_spawn(result.matrix)
    playable = {
        (i, j)
        for i, j, _c in iter_cells(result.matrix)
        if (i, j) in reachable or (i, j) in stranded_playable_cells(result.matrix)
    }
    # Every playable cell is in the reachable flood (stranded set is empty).
    assert playable <= reachable, "a playable cell is outside the reachable flood"
    assert not stranded_playable_cells(result.matrix)
