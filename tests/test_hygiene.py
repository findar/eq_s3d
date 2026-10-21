"""
tests/test_hygiene.py
---------------------
M0 hygiene guards (see `.kiro/specs/zone-generator-m0-hygiene/`).

This module currently holds the outdoor-TER fork-point baseline (task 4.1). The
cave/viewer residue guards (task 14.1) are appended here later.

Fork-point baseline — why it exists
====================================
The M0 milestone deletes the cave pipeline and the legacy viewer. Those deletions
touch shared modules (`generators/builder.py`, `generators/layout.py`,
`generators/field/noise.py`, ...) that the *outdoor* (heightfield) backend also
depends on. This test pins the exact bytes the outdoor TER builder produces on the
UNCHANGED fork-point geometry, so any accidental behavioural change from a deletion
shows up as a hard failure instead of slipping through.

Fork-point commit: 99d346a7ba65ce22c2559f43a2703ccb8ac0a313
  ("Add zone-generator umbrella spec and M0 milestone spec")

Capture procedure (one-off, NOT committed — run on the fork-point code, before any
task-5 deletion, in the pinned `-Venv` worktree):

    import hashlib, tempfile
    from generators.layout import LayoutGenerator
    from tests.pbt_helpers import build_raw
    for s in OUTDOOR_BASELINE_SEEDS:
        spec = LayoutGenerator("outdoor", seed=s).generate(f"ob{s}", room_count=6)
        with tempfile.TemporaryDirectory() as d:
            _, ter_bytes, _ = build_raw(spec, d)
        print(s, hashlib.sha256(ter_bytes).hexdigest())

A later MISMATCH is a bug in the deletion that changed outdoor geometry — it is
NEVER a reason to recapture these literals. Fix the deletion instead.

Caveat (design risk): these hashes were captured in the pinned `-Venv` on this
machine. The byte-exact TER output can move across numpy versions (float ordering
/ libm differences), so a mismatch after a numpy bump is a known, separate cause —
investigate the environment before suspecting the deletion in that case.
"""

from __future__ import annotations

import hashlib
import tempfile

import pytest

from generators.layout import LayoutGenerator
from tests.pbt_helpers import build_raw


OUTDOOR_BASELINE_SEEDS = (7, 1955208177, 2147483647)

# seed -> sha256(ter_bytes).hexdigest() captured on fork-point 99d346a7
OUTDOOR_BASELINE = {
    7: "b3a852e7aa944bb982cfb7c7811b227c55a65305559ee1c16c393e9295b2e80d",
    1955208177: "638272f9fc80a96d2e0ec6622c4bfd509e4c55d71c0c7736dfb8957fd05b5da1",
    2147483647: "e51045058d3b5b3141947588004eb45bd185edab28a7dec1b718ccde7786a1e7",
}


@pytest.mark.parametrize("seed", OUTDOOR_BASELINE_SEEDS)
def test_outdoor_ter_matches_fork_point(seed):
    """The outdoor TER builder reproduces its fork-point bytes exactly.

    A failure means an M0 deletion changed outdoor geometry — fix the deletion,
    do not recapture the literal (see module docstring).
    """
    spec = LayoutGenerator("outdoor", seed=seed).generate(f"ob{seed}", room_count=6)
    with tempfile.TemporaryDirectory() as d:
        _, ter_bytes, _ = build_raw(spec, d)
    got = hashlib.sha256(ter_bytes).hexdigest()
    assert got == OUTDOOR_BASELINE[seed], (
        f"outdoor TER for seed {seed} drifted from the fork-point baseline; "
        f"an M0 deletion likely changed outdoor geometry"
    )
