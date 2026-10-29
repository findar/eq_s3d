"""
tests/test_wilderness_synth.py
------------------------------
The matrix -> heightfield synthesis property suite for the wilderness generator
(spec ``zone-generator-wilderness``, wave 3). These five tests validate the
already-implemented synthesis pipeline in ``generators/wilderness/synth.py``
(Noise_Pass + hydraulic/thermal erosion + type-aware upsample + per-pass Rim
re-clamp) against Correctness Properties 10-14.

Each test drives the REAL pipeline the way the generator will: build a
Design_Matrix (``build_matrix``), run Graph_Replacement to its fixed point
(``rewrite_matrix`` — the finalized matrix is the rewrite fixed point), then
synthesize the heightfield (``synthesize_heightfield``). Determinism is seed-led
(same matrix + seed -> same field).

These are BUILD-A-HEIGHTFIELD checks but they are FAST: a full synthesize is
~40 ms (vectorised numpy throughout, task 7.3). That is comparably fast to the
layout-tier matrix properties, and the design's Testing Strategy places the
heightfield/erosion properties 10-14 at the "default profile >= 100 examples"
tier (NOT the slow built-mesh tier, which is Property 15 alone). So these use
the layout-tier budget ``@settings(max_examples=scaled(100))`` — the same tier
``tests/test_wilderness_matrix.py`` uses — NOT ``build_settings`` /
``@pytest.mark.slow``.

Shared Hypothesis strategies (``matrix_inputs``, ``edge_declarations``,
``seeds``, ``biomes``) and the budget helper ``scaled`` are REUSED from
``tests/test_wilderness_matrix`` and ``tests/pbt_helpers`` — not duplicated.

These are ANALYTICAL / NUMERIC checks on the synthesized height array. The 3D
VISUAL confirmation (eroded valleys read water-made, cliffs sharp, interior
open) is the human-gated task 8.2 per ``docs/ACCEPTANCE.md`` — NOT asserted
here.

Every test carries a docstring beginning
``Feature: zone-generator-wilderness, Property N: <title>`` naming the
requirement ids it validates.
"""

from __future__ import annotations

import math

import numpy as np
from hypothesis import given, settings

# Reuse the shared matrix input strategies + the layout-tier budget helper
# (do NOT duplicate them). ``matrix_inputs`` yields {biome, edges, seed} over
# the four-side default / all-mountain / mixed river+zoneline edge shapes.
from tests.pbt_helpers import scaled
from tests.test_wilderness_matrix import (
    matrix_inputs,
    requires_build_matrix,
    build_matrix,
)

from generators.wilderness.rewrite import rewrite_matrix
from generators.wilderness.synth import (
    DEFAULT_TER_RESOLUTION,
    EDGE_BLEND_CELLS,
    PLAINS_HEIGHT_SCALE,
    PLAINS_NOISE_SCALE,
    PLAINS_OCTAVES,
    ZONELINE_FLATNESS_TOL,
    _clamp_rivers_below_banks,
    _paint_fine_fields,
    _upsample_base,
    noise_pass,
    reclamp_rim,
    synthesize_heightfield,
)
from generators.field.terrain import TerrainSpec, _generate_heightfield

# The traversability agent's slope cap (Property 14). 40 deg -> the per-cell
# gradient bound tan(40 deg); a cell-to-cell height step within
# ``tan(40) * resolution`` is on a standable slope. Imported from the one agent
# model the project uses — NOT reinvented.
from analyzer.traverse import AgentModel

_NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))
# Axis-forward neighbours only, so each undirected cell pair is measured once.
_AXES = ((1, 0), (0, 1))


# ---------------------------------------------------------------------------
# Shared drivers — build the REAL pipeline the generator will use
# ---------------------------------------------------------------------------

def _finalized_matrix(inp):
    """Build a Design_Matrix and run Graph_Replacement to its fixed point.

    The finalized matrix the Noise_Pass/erosion run on is the rewrite fixed
    point (design pipeline), so every property drives the pipeline that way.
    Deterministic from the input seed.
    """
    m = build_matrix(inp["biome"], inp["edges"], inp["seed"])
    return rewrite_matrix(m).matrix, inp["seed"]


def _synth(inp):
    """Full synthesize of a finalized matrix: the ``SynthResult`` with the fine
    TER heightfield and its per-cell classification masks."""
    matrix, seed = _finalized_matrix(inp)
    return synthesize_heightfield(matrix, seed=seed)


def _noise_stage(inp, resolution=DEFAULT_TER_RESOLUTION):
    """Reconstruct the field exactly AFTER the Noise_Pass (before erosion).

    Properties 10 and 11 are defined "after the Noise_Pass completes"
    (Req 8.2-8.5), which is a distinct pipeline stage from the fully-eroded
    final field: ``synthesize_heightfield`` runs upsample -> Noise_Pass ->
    (re-clamp) -> hydraulic -> thermal. This replays the first two stages with
    the production functions (``_paint_fine_fields`` -> ``_upsample_base`` ->
    ``noise_pass`` -> ``reclamp_rim``) in the SAME order and with the SAME args
    ``synthesize_heightfield`` uses, so it measures the real Noise_Pass output,
    not a re-implementation of it.

    Returns ``(h, node_type, frozen_mask, frozen_z)``.
    """
    matrix, seed = _finalized_matrix(inp)
    node_type, frozen_mask, frozen_z, factor = _paint_fine_fields(matrix, resolution)
    base = _upsample_base(matrix, node_type, factor)
    h = noise_pass(base, node_type, frozen_mask, frozen_z, resolution, matrix.origin, seed)
    h = reclamp_rim(h, frozen_mask, frozen_z)  # matches synth's post-noise clamp
    return h, node_type, frozen_mask, frozen_z


def _unblended_candidate(inp, resolution=DEFAULT_TER_RESOLUTION):
    """The Noise_Pass candidate WITHOUT the edge-blend (frozen still masked).

    Property 10's blend assertion compares the blended adjacent-cell step to the
    frozen value against the step the SAME noise would produce with no edge
    blend — proving the blend actually ramps the approach down, not that the
    adjacent cell trivially equals the frozen value (it does not: the blend is a
    graded falloff over ``EDGE_BLEND_CELLS``, so a distance-1 neighbour keeps a
    fraction of the relief by design). Built from the production
    ``_generate_heightfield`` with the exact ``TerrainSpec`` ``noise_pass``
    constructs, so it is the real candidate minus only the blend step.
    """
    matrix, seed = _finalized_matrix(inp)
    node_type, frozen_mask, frozen_z, factor = _paint_fine_fields(matrix, resolution)
    base = _upsample_base(matrix, node_type, factor)
    nx, ny = base.shape
    spec = TerrainSpec(
        width=nx * resolution,
        depth=ny * resolution,
        resolution=resolution,
        seed=int(seed) & 0xFFFFFFFF,
        height_scale=PLAINS_HEIGHT_SCALE,
        noise_scale=PLAINS_NOISE_SCALE,
        octaves=PLAINS_OCTAVES,
    )
    relief = _generate_heightfield(spec, nx, ny)
    relief = relief - float(np.mean(relief))
    candidate = base + relief
    # Mask frozen cells (as the real pass does) but apply NO edge blend.
    candidate = np.where(frozen_mask, np.nan_to_num(frozen_z), candidate).astype(np.float32)
    candidate = _clamp_rivers_below_banks(candidate, node_type)
    return candidate, node_type, frozen_mask, frozen_z


# ---------------------------------------------------------------------------
# Property 10 (task 7.6) — noise masked out of frozen cells + blended at edges
# ---------------------------------------------------------------------------
@requires_build_matrix
@settings(max_examples=scaled(100), deadline=None)
@given(inp=matrix_inputs())
def test_property10_noise_masked_at_frozen_and_blended_at_soft_edges(inp):
    """Feature: zone-generator-wilderness, Property 10: Noise is masked out of
    frozen cells and blended at their edges.

    For any finalized matrix + seed, after the Noise_Pass:
      (a) every Frozen_Cell's synthesized height EQUALS its constraint height
          (``frozen_z``) exactly — the noise write is masked out of it
          (Req 8.2); and
      (b) terrain ADJACENT to a SOFT frozen feature (``zoneline_gap`` / ``river``
          — the features ``synth.py`` deliberately blends; the sharp rim / cliff
          / water steps are Property 13's concern, NOT blended) is blended TOWARD
          the frozen value: the adjacent cell's deviation from the frozen value
          falls within a blend tolerance that is strictly smaller than the step
          the un-blended noise would produce there — a graded approach, not a
          hard step (Req 8.3).

    Validates: Requirements 8.2, 8.3
    """
    h, node_type, frozen_mask, frozen_z = _noise_stage(inp)

    # (a) Every frozen cell equals its constraint height exactly (mask, Req 8.2).
    if frozen_mask.any():
        assert np.allclose(h[frozen_mask], frozen_z[frozen_mask], atol=1e-3), (
            "a Frozen_Cell's Noise_Pass height is not its constraint height "
            f"(max dev {float(np.max(np.abs(h[frozen_mask] - frozen_z[frozen_mask]))):.4f} u)"
        )

    # (b) Blend toward SOFT frozen features (zoneline_gap / river).
    soft = frozen_mask & ((node_type == "zoneline_gap") | (node_type == "river"))
    if not soft.any():
        return  # no soft frozen edge in this draw -> (b) is vacuous

    candidate, _nt2, _fm2, _fz2 = _unblended_candidate(inp)
    frozen_z0 = np.nan_to_num(frozen_z)

    # The design blend is a linear falloff over EDGE_BLEND_CELLS: a cell at
    # distance d keeps (d / band) of its candidate deviation from the frozen
    # value. A distance-1 (immediately adjacent) non-frozen cell therefore keeps
    # at most (1/band) of the candidate deviation -> the blended step is pulled
    # to within that fraction. We assert the adjacent-cell deviation (1) never
    # exceeds the un-blended candidate deviation, and (2) is within the design
    # falloff fraction of it (a real ramp-down, not a no-op).
    keep_frac = 1.0 / float(EDGE_BLEND_CELLS)
    blended_dev = []
    candidate_dev = []
    for di, dj in _NEIGHBOURS:
        nb_soft = np.roll(soft, shift=(di, dj), axis=(0, 1))
        nb_fz = np.roll(frozen_z0, shift=(di, dj), axis=(0, 1))
        adj = nb_soft & ~frozen_mask  # non-frozen cell touching a soft frozen one
        if adj.any():
            blended_dev.append(np.abs(h[adj] - nb_fz[adj]))
            candidate_dev.append(np.abs(candidate[adj] - nb_fz[adj]))

    if not blended_dev:
        return  # soft frozen cells exist but none has a non-frozen neighbour
    blended_dev = np.concatenate(blended_dev)
    candidate_dev = np.concatenate(candidate_dev)

    # (1) The blend never widens the step toward the frozen value.
    assert np.all(blended_dev <= candidate_dev + 1e-3), (
        "edge blend increased the step toward a soft frozen feature "
        "(blend must ramp the approach DOWN, never up)"
    )
    # (2) The blend ramps the adjacent cell to within the design falloff
    # fraction of the un-blended step — proving a real blend (no discontinuity),
    # not a trivially-satisfied inequality. (eps absorbs float32 + the
    # river-bank clamp, which can only lower a cell further toward the bank.)
    assert np.all(blended_dev <= keep_frac * candidate_dev + 0.5), (
        "terrain adjacent to a soft frozen feature was not blended toward the "
        f"frozen value within the design falloff ({keep_frac:.2f} of the raw "
        "step) — a step discontinuity remains at the edge"
    )


# ---------------------------------------------------------------------------
# Property 11 (task 7.7) — zoneline gaps flat, rivers at/below banks
# ---------------------------------------------------------------------------
@requires_build_matrix
@settings(max_examples=scaled(100), deadline=None)
@given(inp=matrix_inputs())
def test_property11_zonelines_flat_rivers_below_banks(inp):
    """Feature: zone-generator-wilderness, Property 11: Zoneline gaps stay flat,
    rivers stay at or below banks.

    For any synthesized heightfield, after the Noise_Pass:
      (a) every ``zoneline_gap`` cell is flat to within the stated tolerance
          ``ZONELINE_FLATNESS_TOL`` — the whole gap sits on one Z (Req 8.4); and
      (b) every ``river`` channel cell is at or below its adjacent (non-river)
          bank height, so terrain never rises through the river (Req 8.5).

    Validates: Requirements 8.4, 8.5
    """
    h, node_type, _frozen_mask, _frozen_z = _noise_stage(inp)

    # (a) Zoneline gaps are flat to tolerance.
    zg = node_type == "zoneline_gap"
    if zg.any():
        spread = float(h[zg].max() - h[zg].min())
        assert spread <= ZONELINE_FLATNESS_TOL, (
            f"zoneline_gap not flat: Z spread {spread:.3f} u exceeds tolerance "
            f"{ZONELINE_FLATNESS_TOL} u"
        )

    # (b) Every river cell is at or below its lowest non-river bank neighbour.
    river = node_type == "river"
    if river.any():
        bank_min = np.full(h.shape, np.inf, dtype=np.float64)
        for di, dj in _NEIGHBOURS:
            nb_h = np.roll(h, shift=(di, dj), axis=(0, 1))
            nb_river = np.roll(river, shift=(di, dj), axis=(0, 1))
            cand = np.where(~nb_river, nb_h, np.inf)
            bank_min = np.minimum(bank_min, cand)
        has_bank = np.isfinite(bank_min)
        over = river & has_bank & (h > bank_min + 0.5)  # 0.5 u float/clamp slack
        n_over = int(np.sum(over))
        assert n_over == 0, (
            f"{n_over} river cell(s) sit ABOVE their adjacent bank — terrain "
            "rises through the river (worst excess "
            f"{float(np.max((h - bank_min)[over])) if n_over else 0.0:.2f} u)"
        )


# ---------------------------------------------------------------------------
# Property 12 (task 7.8) — erosion never breaches the Rim
# ---------------------------------------------------------------------------
@requires_build_matrix
@settings(max_examples=scaled(100), deadline=None)
@given(inp=matrix_inputs())
def test_property12_erosion_never_breaches_the_rim(inp):
    """Feature: zone-generator-wilderness, Property 12: Erosion never breaches
    the Rim.

    For any synthesized heightfield + seed, after the full pipeline (noise ->
    hydraulic -> thermal, each followed by a Rim re-clamp), every non-``zoneline``
    sealed Rim cell (``rim_seal_mask``) remains impassable — snapped back to its
    ridge target ``frozen_z`` — so no erosion pass leaves a passable gully
    through a non-``zoneline`` Rim segment (Req 5.4, 5.5).

    ``synthesize_heightfield`` exposes no per-pass intermediate, so the
    invariant is asserted on the FINAL field — the strongest statement, since it
    proves the re-clamp survived EVERY subsequent pass (if any pass had left an
    un-restored breach, the final sealed-Rim cells would not equal their ridge
    target). To show the re-clamp is doing real work (not that erosion happens
    not to touch the Rim), we also confirm a sealed-Rim ridge target stands far
    ABOVE the eroded interior it borders — i.e. there genuinely IS a cliff the
    erosion+clamp held, not a flat no-op.

    Validates: Requirements 5.4, 5.5
    """
    res = _synth(inp)
    h = res.heights
    rim = res.rim_seal_mask
    frozen_z = res.frozen_z

    if not rim.any():
        return  # all-zoneline / no sealed Rim in this draw -> vacuous

    # Every sealed-Rim cell equals its ridge target exactly on the final field:
    # no pass left an un-restored incision through a non-zoneline Rim segment.
    dev = np.abs(h[rim] - frozen_z[rim])
    assert np.all(dev <= 1e-3), (
        "a non-zoneline sealed Rim cell was not re-clamped to its ridge target "
        f"on the final field (max dev {float(dev.max()):.4f} u) — a pass "
        "breached the Rim and the re-clamp did not restore it"
    )

    # The re-clamp is load-bearing: where a MOUNTAIN_RIM seals the edge it
    # towers over the interior it borders (a genuine impassable ridge the
    # erosion+clamp held, not a flat edge the erosion ignored). Measured on the
    # mountain_rim portion of the sealed Rim only — a `river`-sealed edge becomes
    # boundary `water` frozen at the (low) water level and is sealed by its
    # Invisible_Wall in wave 4, NOT by ridge height, so it is not a towering
    # wall here and is excluded from this demonstration.
    interior = res.playable_interior_mask
    mountain_rim = rim & (res.node_type == "mountain_rim")
    if interior.any() and mountain_rim.any():
        ridge_target = float(np.mean(frozen_z[mountain_rim]))
        interior_mean = float(np.mean(h[interior]))
        assert ridge_target - interior_mean > 100.0, (
            "sealed mountain_rim ridge target is not meaningfully above the "
            f"interior (ridge {ridge_target:.1f} u vs interior {interior_mean:.1f} "
            "u) — the erosion/re-clamp invariant would be vacuous"
        )


# ---------------------------------------------------------------------------
# Property 13 (task 7.9) — upsample smooths plains, preserves sharp edges
# ---------------------------------------------------------------------------
@requires_build_matrix
@settings(max_examples=scaled(100), deadline=None)
@given(inp=matrix_inputs())
def test_property13_upsample_smooths_plains_preserves_sharp_edges(inp):
    """Feature: zone-generator-wilderness, Property 13: Upsample smooths plains
    and preserves sharp cliff/rim/shore edges.

    For any synthesized heightfield:
      (a) height interpolates SMOOTHLY across ``plains`` <-> ``plains`` interior
          boundaries — no block facets from the coarse matrix grid (Req 9.1);
          AND
      (b) the height discontinuity across a ``cliff``/``mountain_rim`` <-> non
          boundary and the ``water`` <-> non shoreline is PRESERVED as a sharp
          step — the across-boundary step stays LARGE, not smoothed toward zero
          (Req 9.2, 9.3).

    Each claim is measured at the pipeline STAGE where the design's
    preservation statement is observable (Req 9.x are the type-aware UPSAMPLE's
    contract):

    * The smooth-plains interpolation and the ``cliff`` / ``mountain_rim``
      height STEPS are a property of the upsample itself (``_upsample_base`` —
      the exact stage Req 9.1/9.2 govern), so they are asserted on the upsample
      base. Downstream thermal erosion deliberately WEATHERS the non-frozen
      ``cliff`` scenic step (synth.py: "cliff is NOT frozen ... its surface is
      still noise-shaped"), so measuring the cliff step on the eroded final
      field would be reading a different, intended behaviour — not the upsample
      sharpness the property is about.
    * The ``water`` SHORELINE step is near zero in height at the upsample base
      (boundary water and the plains base both sit at ~``water_level``), so a
      height-magnitude floor there would be meaningless. The shoreline's
      preservation (Req 9.3) is instead that the smoother NEVER crosses the
      shoreline into the water cells — every ``water`` cell is held EXACTLY at
      ``water_level`` in the upsample base, un-pulled toward the plains base. If
      the smoothing had bled across the shoreline the water cells would drift;
      they do not, so the shoreline boundary is a hard, sharp transition.

    Validates: Requirements 9.1, 9.2, 9.3
    """
    matrix, seed = _finalized_matrix(inp)
    resolution = DEFAULT_TER_RESOLUTION

    # Upsample base (the stage Req 9.1/9.2 govern), rebuilt with the production
    # functions in synth's own order.
    node_type, _fm, _fz, factor = _paint_fine_fields(matrix, resolution)
    base = _upsample_base(matrix, node_type, factor)
    plains = node_type == "plains"

    # (a) Plains interior interpolates smoothly: plains<->plains steps in the
    # upsample base stay well within the walkable cap (no coarse-grid block
    # facet). The type-aware smoother collapses the block tiling to a continuous
    # surface, so this is comfortably under cap.
    cap_step = math.tan(math.radians(40.0)) * resolution
    plains_steps = []
    for di, dj in _AXES:
        nb_h = np.roll(base, shift=(di, dj), axis=(0, 1))
        nb_pl = np.roll(plains, shift=(di, dj), axis=(0, 1))
        both = plains & nb_pl
        if both.any():
            plains_steps.append(np.abs(base - nb_h)[both])
    if plains_steps:
        worst_plains = float(np.concatenate(plains_steps).max())
        assert worst_plains <= cap_step, (
            f"plains<->plains upsample step {worst_plains:.2f} u exceeds the "
            f"walkable cap {cap_step:.2f} u — the plains base is not smooth "
            "(block facets)"
        )

    def max_step_across(field, types, floor, msg):
        """Max |step| across a ``types`` cell and a plains neighbour; require it
        to clear ``floor`` so a smoothed-flat edge (step ~0) fails."""
        is_t = np.isin(node_type.astype(str), list(types))
        if not is_t.any():
            return
        steps = []
        for di, dj in _NEIGHBOURS:
            nb_pl = np.roll(plains, shift=(di, dj), axis=(0, 1))
            nb_h = np.roll(field, shift=(di, dj), axis=(0, 1))
            m = is_t & nb_pl
            if m.any():
                steps.append(np.abs(field - nb_h)[m])
        if not steps:
            return
        worst = float(np.concatenate(steps).max())
        assert worst >= floor, (
            f"{msg}: max step {worst:.2f} u fell below the sharpness floor "
            f"{floor} u — a sharp edge was smoothed away"
        )

    # (b) Sharp cliff / rim STEPS preserved by the upsample (crisp by
    # construction: rim base ~400 u, cliff base ~120 u, vs the smooth ~0 plains
    # base). Floors sit well below the true steps but far above the smooth-plains
    # cap, so only a genuinely-preserved sharp edge passes.
    max_step_across(base, {"mountain_rim"}, floor=300.0,
                    msg="mountain_rim<->plains upsample edge")
    max_step_across(base, {"cliff"}, floor=90.0,
                    msg="cliff<->plains upsample edge")

    # (b, shoreline) Sharp water shoreline: the smoother never crosses the
    # shoreline, so every water cell is held EXACTLY at water_level in the
    # upsample base (not averaged toward the plains base). This is the
    # preserved-sharp-transition guarantee for the shoreline (Req 9.3) — a
    # smoothing that bled across the boundary would drift these cells.
    water = node_type == "water"
    if water.any():
        water_dev = float(np.max(np.abs(base[water] - matrix.water_level)))
        assert water_dev <= 1e-3, (
            f"water cells drifted {water_dev:.4f} u from water_level in the "
            "upsample base — the smoother crossed the shoreline and softened it"
        )


# ---------------------------------------------------------------------------
# Property 14 (task 7.10) — interior slopes within the agent's cap
# ---------------------------------------------------------------------------
@requires_build_matrix
@settings(max_examples=scaled(100), deadline=None)
@given(inp=matrix_inputs())
def test_property14_interior_slopes_within_agent_cap(inp):
    """Feature: zone-generator-wilderness, Property 14: Interior slopes stay
    within the agent's cap.

    For the built wilderness heightfield, every walkable playable-interior cell
    pair (``playable_interior_mask``) has a local cell-to-cell gradient within
    the traversability agent's slope cap — i.e. the interior stays walkable
    undulation, not ungraded cliffs (Req 6.3, 12.4).

    The cap is derived from the project's one ``AgentModel`` (slope 40 deg): a
    cell-to-cell height step is within cap when
    ``|dz| <= tan(walkable_slope_deg) * resolution``. We only measure pairs
    where BOTH cells are playable interior (the Rim band is deliberately steep
    and excluded).

    Validates: Requirements 6.3, 12.4
    """
    res = _synth(inp)
    h = res.heights
    interior = res.playable_interior_mask
    resolution = res.resolution

    agent = AgentModel(walkable_slope_deg=40.0)
    # tan(slope) is the gradient bound; cap on a per-cell step is tan * cell.
    grad_cap = math.tan(math.radians(agent.walkable_slope_deg))
    step_cap = grad_cap * resolution

    worst = 0.0
    for di, dj in _AXES:
        nb_h = np.roll(h, shift=(di, dj), axis=(0, 1))
        nb_int = np.roll(interior, shift=(di, dj), axis=(0, 1))
        both = interior & nb_int
        if both.any():
            worst = max(worst, float(np.abs(h - nb_h)[both].max()))

    assert worst <= step_cap + 1e-3, (
        f"a playable-interior cell-to-cell step {worst:.2f} u exceeds the "
        f"agent's slope cap ({agent.walkable_slope_deg:.0f} deg -> "
        f"{step_cap:.2f} u/cell) — interior is not walkable"
    )
