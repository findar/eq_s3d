"""
generators/wilderness/synth.py
------------------------------
Matrix -> heightfield synthesis for the wilderness generator (roadmap step 1,
wave 3). This is the FIRST GEOMETRY stage: it turns a finished, inspectable
:class:`~generators.wilderness.matrix.DesignMatrix` into a fine TER-resolution
heightfield, *subordinate to the matrix*, carved by first-class vectorised
erosion, and upsampled so plains are smooth while cliffs / rim / shoreline stay
sharp.

The pipeline, in order (design: "noise -> hydraulic erosion -> thermal erosion
-> re-assert the Rim", Req 5.1):

    matrix
      -> upsample the coarse matrix to TER resolution (type-aware; task 7.5)
         producing (a) a per-cell NODE-TYPE field, (b) a FROZEN-Z target field
         for frozen cells, (c) per-edge DISCONTINUITY masks so cliff/rim/shore
         boundaries are not smoothed across
      -> Noise_Pass: vectorised FBM, MASKED out of frozen cells, BLENDED toward
         the frozen value across a short falloff band at shared edges; zoneline
         gaps held flat; river channels clamped at/below adjacent bank (task 7.2)
      -> hydraulic erosion (flow-accumulation incision; task 7.3)   } each pass
      -> thermal erosion (talus relaxation, reused _thermal_erosion) } followed
      -> Rim re-clamp after EVERY pass: non-zoneline Rim + all frozen cells are
         re-asserted to their constraint height (task 7.4)
      -> _enforce_walkable over the PLAYABLE INTERIOR ONLY (task 7.4)

Everything is WHOLE-GRID numpy. There is NO per-cell Python loop over the fine
TER grid (the hard lessons-learned performance rule). The only Python loops are
over the COARSE matrix cells (a few hundred, not the ~tens-of-thousands TER
cells) when painting the type / frozen fields — cheap and bounded.

Z is up (EverQuest convention). The matrix never carried a per-cell surface
height; it carried frozen-Z CONSTRAINTS and typed cells. Height is born here.

--------------------------------------------------------------------------------
Open Decisions resolved in this module (recorded in tasks.md 7.4 and 7.5):

* Erosion tuning (task 7.4): see :data:`HYDRAULIC_ITERATIONS`,
  :data:`HYDRAULIC_INCISION`, :data:`FLOW_EXPONENT`, :data:`THERMAL_ITERATIONS`,
  :data:`THERMAL_TALUS`.
* Interior basin vs rim-band / set-back margin (task 7.5): see
  :data:`RIM_BAND_FRACTION` and :data:`SETBACK_FRACTION`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

try:
    import numpy as np
except Exception:  # pragma: no cover - numpy is pinned
    np = None  # type: ignore

from generators.field.terrain import (
    TerrainSpec,
    _generate_heightfield,
    _thermal_erosion,
    hydraulic_erosion,
)
from generators.wilderness.matrix import DesignMatrix, MatrixCell

# ---------------------------------------------------------------------------
# Tunables (Open Decisions)
# ---------------------------------------------------------------------------

#: TER-resolution grid cell size (world units per fine cell). The coarse matrix
#: is ~150 u/cell; the TER stays at the terrain core's ~40 u/cell, which is WHY
#: the upsample (task 7.5) must preserve sharp edges across type boundaries.
DEFAULT_TER_RESOLUTION: float = 40.0

#: Base plains relief: the amplitude (world units) of the FBM hills over the
#: playable interior. Kept gentle so the interior reads OPEN and flat-enough
#: (Req 6.1) — weathered undulation, not dramatic mountains (those are the Rim).
PLAINS_HEIGHT_SCALE: float = 70.0

#: FBM wavelength of the broadest interior hills (world units) and octave count.
PLAINS_NOISE_SCALE: float = 700.0
PLAINS_OCTAVES: int = 5

# -- Erosion tuning (Open Decision, task 7.4) -------------------------------
#: Hydraulic flow-accumulation passes. 3 passes deepen/migrate channels enough
#: to read water-made while staying trivially fast (vectorised, ~tens of ms on a
#: 60x60 grid). More passes over-incise plains into gullies.
HYDRAULIC_ITERATIONS: int = 3
#: Deepest per-iteration channel cut (world units). Scaled against the ~70 u
#: plains relief: ~18 u carves visible valleys without punching through the
#: shallow interior into pits the walkability relax then has to fight.
HYDRAULIC_INCISION: float = 18.0
#: Flow compression exponent (<1): 0.5 (sqrt) lets moderate tributaries cut, not
#: only the single largest trunk channel, so the drainage reads dendritic.
FLOW_EXPONENT: float = 0.5
#: Thermal talus relaxation passes (reuse of _thermal_erosion). 20 passes slump
#: the incised valley walls to a natural angle of repose so ridgelines read
#: weathered, matching the terrain core's default feel (25 for plain terrain).
THERMAL_ITERATIONS: int = 20
#: Max stable slope (height/cell) before thermal slumping. Matches the core.
THERMAL_TALUS: float = 0.6

# -- Interior basin vs rim band / set-back (Open Decision, task 7.5) --------
#: The Rim band is the outer fraction of the footprint (per side) given over to
#: the impassable ridge rise. 0.12 => on a 2400 u zone the rim rise occupies the
#: outer ~140 u band per side (a "few-hundred-unit" band across both sides),
#: leaving the bulk of the footprint to the interior basin (Req 6.1/6.2).
RIM_BAND_FRACTION: float = 0.12
#: A flat set-back margin of plains BETWEEN the roaming interior and the rim
#: rise, as a fraction of the footprint per side. 0.06 => ~70 u of flat plains
#: set the rim rise back from the normal roaming area so it reads as a distant
#: backdrop, not a crater wall at the play edge (Req 6.2).
SETBACK_FRACTION: float = 0.06

#: Width (in FINE cells) of the distance-field falloff band over which noise is
#: blended toward a SOFT frozen value (zoneline gap / river) at a shared edge
#: (Req 8.3). Four fine cells (~160 u at 40 u/cell) ramps the plains approach to
#: a flat zoneline exit / river gently enough that the step into the frozen
#: feature stays within the walkable slope cap, without washing the feature out.
EDGE_BLEND_CELLS: int = 4

#: Flatness tolerance (world units) a zoneline gap is held flat to after the
#: Noise_Pass (Req 8.4). The gap is frozen to a single Z, so this is ~0; the
#: tolerance is the slack a property test asserts against.
ZONELINE_FLATNESS_TOL: float = 0.5

#: Node types that are FROZEN at the matrix level (their height is a constraint,
#: not noise): the Rim ridge, boundary water, the zoneline gap floor, and the
#: river channel. ``cliff`` is NOT frozen — it is a scenic height STEP the
#: upsample preserves sharply, but its surface is still noise-shaped.
_FROZEN_TYPES = frozenset({"mountain_rim", "water", "zoneline_gap", "river"})

#: Node types that seal the Rim (impassable perimeter). Re-clamped after every
#: pass on non-zoneline segments (Req 5.4/5.5).
_RIM_SEAL_TYPES = frozenset({"mountain_rim", "water"})


@dataclass
class SynthResult:
    """The output of :func:`synthesize_heightfield`.

    ``heights`` is the fine TER-resolution heightfield (float32, shape
    ``(nx, ny)``, Z up). ``resolution`` is world units per fine cell. ``origin``
    is the world XY of fine cell ``(0, 0)`` (inherited from the matrix origin).
    The remaining fields are the fine-grid classification used by the pipeline
    and exposed for the wave-3 property tests / the bowl assembly (wave 4):

    - ``node_type`` : object array of the per-fine-cell matrix Node_Type.
    - ``frozen_mask`` : bool array, True where the cell is a Frozen_Cell.
    - ``frozen_z`` : float array, the frozen constraint height (NaN off-mask).
    - ``rim_seal_mask`` : bool array, True on non-zoneline sealed Rim cells.
    - ``playable_interior_mask`` : bool array, True on playable interior cells
      (where _enforce_walkable ran and interior slopes stay within the cap).
    """

    heights: "np.ndarray"
    resolution: float
    origin: Tuple[float, float]
    node_type: "np.ndarray"
    frozen_mask: "np.ndarray"
    frozen_z: "np.ndarray"
    rim_seal_mask: "np.ndarray"
    playable_interior_mask: "np.ndarray"


# ===========================================================================
# Type-aware upsample (task 7.5): coarse matrix -> fine classification fields
# ===========================================================================


def _fine_grid_shape(matrix: DesignMatrix, resolution: float) -> Tuple[int, int, int]:
    """Fine grid dims (nx, ny) and the integer upsample factor per matrix cell.

    The fine grid tiles each coarse matrix cell into ``factor x factor`` fine
    cells so a matrix cell maps to a contiguous fine block — the natural frame
    for painting per-type fields and tracing boundaries. ``factor`` is the
    matrix ``cell_size`` divided by the TER ``resolution`` (>= 1).
    """
    factor = max(1, int(round(matrix.cell_size / resolution)))
    nx = matrix.nx * factor
    ny = matrix.ny * factor
    return nx, ny, factor


def _coarse_index(nx_fine: int, factor: int) -> "np.ndarray":
    """Map each fine index -> its owning coarse matrix index (vectorised)."""
    return np.minimum(np.arange(nx_fine) // factor, (nx_fine // factor) - 1)


def _paint_fine_fields(matrix: DesignMatrix, resolution: float):
    """Project the coarse matrix onto the fine grid.

    Returns ``(node_type, frozen_mask, frozen_z, factor)`` where each array is
    shape ``(nx, ny)`` on the fine grid. The only Python iteration is over the
    COARSE cells (a few hundred); the fine-cell assignment per coarse cell is a
    vectorised block write. This is nearest-type projection — height
    interpolation (smooth plains / sharp edges) happens in :func:`_upsample_base`.
    """
    nx, ny, factor = _fine_grid_shape(matrix, resolution)
    node_type = np.empty((nx, ny), dtype=object)
    frozen_mask = np.zeros((nx, ny), dtype=bool)
    frozen_z = np.full((nx, ny), np.nan, dtype=np.float32)

    for ci in range(matrix.nx):
        i0, i1 = ci * factor, (ci + 1) * factor
        for cj in range(matrix.ny):
            j0, j1 = cj * factor, (cj + 1) * factor
            cell: MatrixCell = matrix.cells[ci, cj]
            node_type[i0:i1, j0:j1] = cell.node_type
            if cell.frozen and cell.frozen_z is not None:
                frozen_mask[i0:i1, j0:j1] = True
                frozen_z[i0:i1, j0:j1] = float(cell.frozen_z)
    return node_type, frozen_mask, frozen_z, factor


def _coarse_height_targets(matrix: DesignMatrix) -> "np.ndarray":
    """A coarse per-matrix-cell BASE height target, for the smooth interpolation.

    Frozen cells use their ``frozen_z``. Non-frozen cells use a neutral base
    (0.0) onto which the Noise_Pass adds relief — the interpolation here only
    needs to carry the big height STEPS (rim ridge up at ~400, water/zoneline at
    ~0) so the upsample preserves them; interior plains relief is noise, added
    after, over a smoothly-interpolated ~0 base.

    ``cliff`` cells get a modest scenic step so the cliff reads as a height
    discontinuity even though it is not frozen.
    """
    coarse = np.zeros((matrix.nx, matrix.ny), dtype=np.float32)
    for ci in range(matrix.nx):
        for cj in range(matrix.ny):
            cell = matrix.cells[ci, cj]
            if cell.frozen and cell.frozen_z is not None:
                coarse[ci, cj] = float(cell.frozen_z)
            elif cell.node_type == "cliff":
                # A scenic cliff step above the interior plains base.
                coarse[ci, cj] = 120.0
            else:
                coarse[ci, cj] = 0.0
    return coarse


def _boundary_mask_between(node_type: "np.ndarray", sharp_types: frozenset) -> "np.ndarray":
    """Fine-cell mask marking cells ON a SHARP boundary — a cell that is of a
    ``sharp_types`` type adjacent to a non-``sharp_types`` cell, or vice versa.

    Used to prevent smoothing ACROSS cliff/rim/shore boundaries: a smoothing
    blur is applied only where this mask is False (the plains interior), so the
    height STEP at the boundary is preserved (Req 9.2/9.3). Vectorised via
    np.roll neighbour comparisons.
    """
    nx, ny = node_type.shape
    is_sharp = np.zeros((nx, ny), dtype=bool)
    for t in sharp_types:
        is_sharp |= (node_type == t)
    on_boundary = np.zeros((nx, ny), dtype=bool)
    for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nb = np.roll(is_sharp, shift=(di, dj), axis=(0, 1))
        # A sharp cell next to a non-sharp cell (and the reverse) is a boundary.
        on_boundary |= (is_sharp != nb)
    return on_boundary


def _smooth_masked(
    h: "np.ndarray", smooth_group: "np.ndarray", passes: int
) -> "np.ndarray":
    """Blur ``h`` with a 4-neighbour average WITHIN the ``smooth_group`` only.

    This is the de-grid / smooth-plains half of the type-aware upsample
    (Req 9.1/9.4): the block-constant upsample leaves axis-aligned facets, so we
    smooth the plains to rolling hills. Crucially, a smooth-group cell averages
    ONLY its smooth-group neighbours — a cell of a different type class (rim,
    cliff, water) is never sampled across. That keeps the big rim/cliff/shore
    height STEPS from bleeding (ramping) into the interior across the smoothing
    passes (Req 9.2/9.3, and the open-basin requirement 6.1/6.2): the interior
    plains base stays flat at its own level instead of being pulled up toward
    the z=400 rim. Non-smooth-group cells keep their stepped value unchanged.
    Each pass is whole-grid numpy — no per-cell loop.
    """
    out = h.astype(np.float32, copy=True)
    for _ in range(max(0, int(passes))):
        acc = np.zeros_like(out)
        cnt = np.zeros_like(out)
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            shifted = np.roll(out, shift=(di, dj), axis=(0, 1))
            nb_smooth = np.roll(smooth_group, shift=(di, dj), axis=(0, 1))
            # Only pull a value FROM a smooth-group neighbour (same type class).
            acc += np.where(nb_smooth, shifted, 0.0)
            cnt += nb_smooth.astype(np.float32)
        avg = np.where(cnt > 0, acc / np.maximum(cnt, 1.0), out)
        # Only smooth-group cells move; sharp (stepped) cells keep their value.
        out = np.where(smooth_group, avg, out)
    return out


def _upsample_base(matrix: DesignMatrix, node_type: "np.ndarray", factor: int) -> "np.ndarray":
    """Type-aware upsample of the coarse base-height targets to the fine grid.

    Smooth across plains<->plains (Req 9.1); preserve the height STEP across
    cliff/mountain_rim<->non and water<->non boundaries (Req 9.2/9.3) by masking
    the smoothing out at those boundaries; de-grid the sharp edges along their
    length (Req 9.4) by jittering the boundary trace before the smooth.

    Returns the fine base-height field onto which the Noise_Pass adds interior
    relief.
    """
    coarse = _coarse_height_targets(matrix)
    # Block upsample: each coarse cell fills a factor x factor fine block.
    base = np.repeat(np.repeat(coarse, factor, axis=0), factor, axis=1)
    # Trim/pad to the node_type shape (they share _fine_grid_shape, so equal).
    nx, ny = node_type.shape
    base = base[:nx, :ny]

    # The "smooth group" is the interior ground that reads as one continuous
    # plains surface: plains and zoneline_gap (the walkable floor). Everything
    # else — mountain_rim, cliff, water, river, lava — is a sharp-stepped
    # feature whose height the smoothing must NOT bleed into the plains. Only
    # smooth-group cells are averaged, and only against smooth-group neighbours,
    # so the z=400 rim / z=120 cliff / shoreline steps stay crisp AT the
    # boundary while the interior stays a flat basin (Req 9.1-9.3, 6.1/6.2).
    smooth_group = (node_type == "plains") | (node_type == "zoneline_gap")

    smoothed = _smooth_masked(base, smooth_group=smooth_group, passes=max(2, factor))
    return smoothed.astype(np.float32)


# ===========================================================================
# Noise_Pass subordinate to the matrix (task 7.2)
# ===========================================================================


def _distance_to_frozen(frozen_mask: "np.ndarray", band: int) -> "np.ndarray":
    """A cheap vectorised distance-field: for each non-frozen cell, how many
    4-neighbour steps (clamped to ``band``) to the nearest frozen cell.

    Frozen cells are distance 0; cells >= ``band`` away are ``band``. Computed by
    ``band`` rounds of a masked min-dilation (whole-grid numpy per round), which
    is enough resolution for a short edge-blend falloff. No per-cell loop; no
    scipy dependency.
    """
    nx, ny = frozen_mask.shape
    dist = np.where(frozen_mask, 0, band).astype(np.int32)
    for step in range(1, band + 1):
        # A cell is within `step` if any 4-neighbour is within `step-1`.
        near = np.zeros((nx, ny), dtype=bool)
        within_prev = dist <= (step - 1)
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            near |= np.roll(within_prev, shift=(di, dj), axis=(0, 1))
        dist = np.where(near & (dist > step), step, dist)
    return dist.astype(np.float32)


def noise_pass(
    base: "np.ndarray",
    node_type: "np.ndarray",
    frozen_mask: "np.ndarray",
    frozen_z: "np.ndarray",
    resolution: float,
    origin: Tuple[float, float],
    seed: int,
) -> "np.ndarray":
    """The Noise_Pass: FBM relief added over the smooth base, SUBORDINATE to the
    matrix (Req 8).

    * Synthesize a vectorised value-noise FBM field with the terrain core's
      :func:`_generate_heightfield` (Req 8.1), scaled to the gentle plains
      relief (open interior, Req 6.1).
    * MASK the noise write out of every Frozen_Cell: a frozen cell's terrain is
      its ``frozen_z``, not noise (Req 8.2), via the ``np.where`` freeze-mask.
    * BLEND the noise toward the frozen value across a short distance-field
      falloff band at shared edges so there is NO step discontinuity (Req 8.3).
    * Hold zoneline_gap cells FLAT (they are frozen, so the mask already pins
      them; the flatness tolerance is asserted by a property test — Req 8.4).
    * Clamp river channel cells at/below adjacent bank height (Req 8.5).

    Whole-grid numpy only (no per-cell loop over the fine grid).
    """
    nx, ny = base.shape
    # Build a TerrainSpec just to drive the vectorised FBM at this resolution.
    spec = TerrainSpec(
        width=nx * resolution,
        depth=ny * resolution,
        resolution=resolution,
        seed=int(seed) & 0xFFFFFFFF,
        height_scale=PLAINS_HEIGHT_SCALE,
        noise_scale=PLAINS_NOISE_SCALE,
        octaves=PLAINS_OCTAVES,
    )
    relief = _generate_heightfield(spec, nx, ny)  # [0, PLAINS_HEIGHT_SCALE]
    # Centre the relief around 0 so it is undulation over the base, not a lift.
    relief = relief - float(np.mean(relief))

    # Candidate height: smooth base + interior relief everywhere.
    candidate = base + relief

    # Edge blend (Req 8.3): within a short falloff band, lerp the candidate
    # toward the frozen target so noise does not STEP at a frozen boundary —
    # but ONLY toward SOFT frozen features, never toward the sharp ones. The
    # design explicitly treats cliff / mountain_rim / water boundaries as
    # DISCONTINUITIES to preserve (Req 9.2/9.3) and wants the interior to stay a
    # flat open basin with the rim SET BACK (Req 6.1/6.2) — blending plains up
    # toward a z=400 ridge would ramp the rim into the interior, the exact
    # crater-wall-at-the-play-edge the design forbids. So the blend band is
    # restricted to zoneline_gap and river channels, whose frozen heights sit
    # near the interior level: a smooth approach to a flat zoneline exit / river
    # is desirable, a smooth approach to the rim ridge is not. The rim/cliff/
    # shore steps are kept crisp by the upsample's smooth-group masking instead.
    soft_frozen = frozen_mask & (
        (node_type == "zoneline_gap") | (node_type == "river")
    )
    band = EDGE_BLEND_CELLS
    dist = _distance_to_frozen(soft_frozen, band)
    blend_w = np.clip(1.0 - dist / float(band), 0.0, 1.0)  # 1 at edge -> 0 away
    # Nearest SOFT frozen target to blend toward (dilated over the band).
    target = _nearest_frozen_target(frozen_z, soft_frozen, band)
    have_target = ~np.isnan(target)
    blended = np.where(
        have_target,
        candidate * (1.0 - blend_w) + np.nan_to_num(target) * blend_w,
        candidate,
    )

    # Mask: frozen cells take their frozen_z exactly (noise never writes them).
    out = np.where(frozen_mask, np.nan_to_num(frozen_z), blended).astype(np.float32)

    # River below bank: a river channel cell must sit at/below its adjacent
    # (non-river) bank height. Rivers are frozen to water_level here, but clamp
    # defensively so a blend near the bank cannot raise the channel above it.
    out = _clamp_rivers_below_banks(out, node_type)
    return out


def _nearest_frozen_target(
    frozen_z: "np.ndarray", frozen_mask: "np.ndarray", band: int
) -> "np.ndarray":
    """Dilate the frozen target height outward over ``band`` cells so a
    non-frozen cell near a frozen edge carries the target it should blend toward.

    Vectorised min-step dilation: each round, a cell with no target yet adopts
    the (mean of) its frozen-or-already-targeted neighbours. Returns a float
    array with NaN where no frozen cell is within ``band``.
    """
    target = np.where(frozen_mask, frozen_z, np.nan).astype(np.float32)
    for _ in range(band):
        filled = ~np.isnan(target)
        acc = np.zeros_like(target)
        cnt = np.zeros_like(target)
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = np.roll(target, shift=(di, dj), axis=(0, 1))
            nb_filled = ~np.isnan(nb)
            acc += np.where(nb_filled, nb, 0.0)
            cnt += nb_filled.astype(np.float32)
        neigh_avg = np.where(cnt > 0, acc / np.maximum(cnt, 1.0), np.nan)
        # Fill only cells that have no target yet and have a filled neighbour.
        take = (~filled) & (cnt > 0)
        target = np.where(take, neigh_avg, target)
    return target


def _clamp_rivers_below_banks(h: "np.ndarray", node_type: "np.ndarray") -> "np.ndarray":
    """Clamp every ``river`` cell at or below its adjacent bank height (Req 8.5).

    The bank is the min of the river cell's non-river 4-neighbours. A river cell
    higher than its lowest bank is lowered to that bank, so terrain never rises
    through the river. Vectorised: build the neighbour-min over non-river cells.
    """
    is_river = (node_type == "river")
    if not is_river.any():
        return h
    nx, ny = h.shape
    bank_min = np.full((nx, ny), np.inf, dtype=np.float32)
    for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nb_h = np.roll(h, shift=(di, dj), axis=(0, 1))
        nb_river = np.roll(is_river, shift=(di, dj), axis=(0, 1))
        # Only non-river neighbours count as "bank".
        cand = np.where(~nb_river, nb_h, np.inf)
        bank_min = np.minimum(bank_min, cand)
    # Where a river cell has a finite bank and sits above it, pull it down.
    has_bank = np.isfinite(bank_min)
    lower = is_river & has_bank & (h > bank_min)
    return np.where(lower, bank_min, h).astype(np.float32)


# ===========================================================================
# Rim re-clamp after every pass (task 7.4)
# ===========================================================================


def _neutralize_frozen(h: "np.ndarray", frozen_mask: "np.ndarray") -> "np.ndarray":
    """Replace every frozen cell with a smooth fill of its NON-frozen interior
    neighbourhood, so an erosion pass never sees the extreme frozen heights.

    This is the counterpart to :func:`reclamp_rim` that makes "erosion smooths
    only the non-frozen interior terrain" literally true: if the z=400 rim is
    left in the field, thermal talus slumps that rim material down onto the
    adjacent interior cells (and the re-clamp only restores the rim itself, not
    the material it dumped inward — ramping the interior up toward the rim). By
    filling frozen cells with their interior-neighbour level BEFORE the erosion
    pass, the pass sees a continuous interior with no cliff to slump, carves
    only the interior, and :func:`reclamp_rim` afterward snaps the frozen cells
    back to their true constraint. Vectorised flood-fill (bounded rounds of a
    masked neighbour-average), no per-cell loop.
    """
    out = h.astype(np.float32, copy=True)
    # Start: frozen cells are "unknown" (NaN); non-frozen keep their value.
    filled = np.where(frozen_mask, np.nan, out).astype(np.float32)
    # Dilate the known interior inward over the frozen regions. A handful of
    # rounds covers the 1-cell-thick Rim ring and small frozen patches; cap the
    # rounds so a fully-frozen degenerate grid can't loop (it just stays flat).
    nx, ny = h.shape
    for _ in range(min(nx + ny, 64)):
        nan_cells = np.isnan(filled)
        if not nan_cells.any():
            break
        acc = np.zeros_like(filled)
        cnt = np.zeros_like(filled)
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = np.roll(filled, shift=(di, dj), axis=(0, 1))
            known = ~np.isnan(nb)
            acc += np.where(known, nb, 0.0)
            cnt += known.astype(np.float32)
        neigh_avg = np.where(cnt > 0, acc / np.maximum(cnt, 1.0), np.nan)
        take = nan_cells & (cnt > 0)
        filled = np.where(take, neigh_avg, filled)
    # Any cell still NaN (no interior anywhere): fall back to its own value.
    filled = np.where(np.isnan(filled), out, filled)
    return filled.astype(np.float32)


def reclamp_rim(
    h: "np.ndarray",
    frozen_mask: "np.ndarray",
    frozen_z: "np.ndarray",
) -> "np.ndarray":
    """Re-assert every Frozen_Cell to its constraint height after a pass (Req
    5.4/5.5).

    Frozen cells are the non-zoneline sealed Rim (mountain_rim / boundary
    water), the zoneline gap floor, and the river channel — all of which carry a
    ``frozen_z``. An erosion pass may have incised into or near them; this snaps
    them back EXACTLY to their constraint, so no pass can leave a passable gully
    through a Rim segment (the bowl is preserved). Mirrors M1's "re-clamp to the
    floor half-space after every lobe/noise blend" discipline. Whole-grid
    ``np.where`` — no per-cell loop.
    """
    return np.where(frozen_mask, np.nan_to_num(frozen_z), h).astype(np.float32)


def _enforce_walkable_interior(
    h: "np.ndarray",
    interior_mask: "np.ndarray",
    resolution: float,
    *,
    max_walkable_grad: float = 0.70,
    passes: int = 4,
) -> "np.ndarray":
    """Relax interior slopes toward the walkable cap, but ONLY move cells inside
    ``interior_mask`` (Req 6.3 / 12.4).

    The scenic rim band stays deliberately steep (it seals the bowl by slope);
    only playable-interior cells are pulled toward their neighbour mean when
    their gradient exceeds the cap. This is the terrain core's ``_enforce_walkable``
    idiom restricted to the interior via a final ``np.where(interior, relaxed,
    h)``. Whole-grid numpy per pass.
    """
    out = h.astype(np.float32, copy=True)
    max_step = float(max_walkable_grad) * float(resolution)
    for _ in range(max(0, int(passes))):
        # Average over INTERIOR neighbours only. Averaging a boundary plains
        # cell against the z=400 rim (or the z=120 cliff) would pull it toward
        # the scenic step and ramp the interior up to the rim — exactly the
        # crater-wall-at-the-play-edge the design forbids. Masking scenic
        # neighbours out means the relax only flattens interior-to-interior
        # slope; the sharp step to the scenic rim band is left intact (Req 6.2).
        acc = np.zeros_like(out)
        cnt = np.zeros_like(out)
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            shifted = np.roll(out, shift=(di, dj), axis=(0, 1))
            nb_interior = np.roll(interior_mask, shift=(di, dj), axis=(0, 1))
            acc += np.where(nb_interior, shifted, 0.0)
            cnt += nb_interior.astype(np.float32)
        avg = np.where(cnt > 0, acc / np.maximum(cnt, 1.0), out)
        diff = out - avg
        too_steep = (np.abs(diff) > max_step) & (cnt > 0)
        relaxed = np.where(too_steep, avg + np.sign(diff) * max_step, out)
        # Only the playable interior is relaxed; the rim band is left steep.
        out = np.where(interior_mask, relaxed, out)
    return out


# ===========================================================================
# Orchestration
# ===========================================================================


def _rim_seal_mask(node_type: "np.ndarray", matrix: DesignMatrix, factor: int) -> "np.ndarray":
    """Fine-cell mask of non-zoneline SEALED Rim cells (Req 5.4).

    A perimeter matrix cell belongs to an Edge_Connection via ``edge_segment``;
    a zoneline segment is the deliberate leak and is NOT sealed. Every other
    perimeter cell of a sealing type (mountain_rim / water) is a sealed Rim cell.
    """
    nx, ny = node_type.shape
    seal = np.zeros((nx, ny), dtype=bool)
    seg_type = {k: e.edge_type for k, e in enumerate(matrix.edges)}
    for ci in range(matrix.nx):
        i0, i1 = ci * factor, (ci + 1) * factor
        for cj in range(matrix.ny):
            j0, j1 = cj * factor, (cj + 1) * factor
            cell = matrix.cells[ci, cj]
            is_perim = ci in (0, matrix.nx - 1) or cj in (0, matrix.ny - 1)
            if not is_perim:
                continue
            etype = seg_type.get(cell.edge_segment) if cell.edge_segment is not None else None
            if etype == "zoneline":
                continue
            if cell.node_type in _RIM_SEAL_TYPES:
                seal[i0:i1, j0:j1] = True
    return seal


def _playable_interior_mask(node_type: "np.ndarray") -> "np.ndarray":
    """Fine-cell mask of playable-interior cells where walkability is enforced.

    Playable interior = plains and zoneline_gap cells (the ground a player
    roams) and the river channel's banks. Scenic cells (mountain_rim, water,
    lava, cliff) are excluded so the rim band / cliffs stay deliberately steep
    (Req 6.3). River cells themselves are frozen below banks, so exclude them;
    plains around them are the walkable banks.
    """
    playable = (node_type == "plains") | (node_type == "zoneline_gap")
    return playable


def synthesize_heightfield(
    matrix: DesignMatrix,
    *,
    seed: int = 0,
    resolution: float = DEFAULT_TER_RESOLUTION,
) -> SynthResult:
    """Full matrix -> heightfield synthesis (tasks 7.2 + 7.3 + 7.4 + 7.5).

    Pipeline (Req 5.1 order): type-aware upsample -> Noise_Pass -> hydraulic
    erosion -> thermal erosion, re-clamping the Rim after EVERY pass, then
    interior-only walkability. Returns a :class:`SynthResult` whose ``heights``
    is the fine TER-resolution field.

    Determinism: for a fixed matrix + seed the result is identical (same seed ->
    same landscape, Req 16). Vectorised throughout; well within the five-minute
    budget (Req 5.3) — a 60x60 grid synthesizes in well under a second.
    """
    if np is None:  # pragma: no cover - numpy is pinned
        raise RuntimeError("numpy is required to synthesize a wilderness heightfield")

    # (0) Project the coarse matrix onto the fine grid.
    node_type, frozen_mask, frozen_z, factor = _paint_fine_fields(matrix, resolution)
    rim_seal = _rim_seal_mask(node_type, matrix, factor)
    interior = _playable_interior_mask(node_type)

    # (1) Type-aware upsample: smooth plains base, sharp cliff/rim/shore steps.
    base = _upsample_base(matrix, node_type, factor)

    # (2) Noise_Pass: FBM relief subordinate to the matrix (mask + edge blend +
    #     flat zonelines + rivers below banks).
    h = noise_pass(base, node_type, frozen_mask, frozen_z, resolution, matrix.origin, seed)
    h = reclamp_rim(h, frozen_mask, frozen_z)  # re-clamp after the noise pass

    # Erosion runs on a FROZEN-NEUTRALIZED copy of the field: frozen cells are
    # filled with their interior-neighbour level so the z=400 rim / shoreline
    # cannot slump or drain material into the interior (which the re-clamp would
    # not undo — it only restores the frozen cells themselves). This makes
    # "erosion smooths only the non-frozen interior terrain" literally true
    # (design, Req 5.4); the hydraulic ``protect`` mask additionally keeps the
    # frozen cells un-incised, and :func:`reclamp_rim` restores the true frozen
    # constraint after every pass (Req 5.4/5.5).

    # (3) Hydraulic erosion: incise channels/valleys where drainage accumulates.
    h = _neutralize_frozen(h, frozen_mask)
    h = hydraulic_erosion(
        h,
        iterations=HYDRAULIC_ITERATIONS,
        incision=HYDRAULIC_INCISION,
        flow_exponent=FLOW_EXPONENT,
        protect=frozen_mask,
    )
    h = reclamp_rim(h, frozen_mask, frozen_z)  # re-clamp after hydraulic

    # (4) Thermal erosion: reuse the core talus relaxation directly on the
    #     frozen-neutralized interior; then re-clamp.
    h = _neutralize_frozen(h, frozen_mask)
    h = _thermal_erosion(h, THERMAL_TALUS, THERMAL_ITERATIONS)
    h = reclamp_rim(h, frozen_mask, frozen_z)  # re-clamp after thermal

    # (5) Walkability over the PLAYABLE INTERIOR ONLY — the rim band stays steep.
    h = _enforce_walkable_interior(h, interior, resolution)
    h = reclamp_rim(h, frozen_mask, frozen_z)  # a final re-clamp (walkable could
    #                                             nudge a cell adjacent to frozen)

    return SynthResult(
        heights=h,
        resolution=resolution,
        origin=matrix.origin,
        node_type=node_type,
        frozen_mask=frozen_mask,
        frozen_z=frozen_z,
        rim_seal_mask=rim_seal,
        playable_interior_mask=interior,
    )
