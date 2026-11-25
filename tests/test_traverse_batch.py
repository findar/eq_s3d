"""
tests/test_traverse_batch.py
----------------------------
The gate's array helpers (test-speed task 6) against the scalar ones they
replaced in the hot loops. The batch forms must give the SAME floats, not near
ones: the seam limits are inclusive, and the contact point decides the heights
compared, so a 1-ulp change or a tie broken the other way can join two faces
the scalar test kept apart.

Triangles are drawn on a coarse lattice so vertices coincide, edges touch and
run parallel, and several edge pairs tie for nearest: the cases where a
reordering would show.
"""

import numpy as np

import analyzer.traverse as T

RNG_SEEDS = range(4)


def _tris(rng, n, lattice=4.0, spread=6):
    """``n`` triangles with lattice-point corners, heights 0..9 u."""
    xy = rng.integers(0, spread, size=(n, 3, 2)) * lattice
    xy = xy + rng.integers(0, 2, size=(n, 1, 2)) * rng.random((n, 1, 2)) * 0.5
    z = rng.integers(0, 4, size=(n, 3, 1)) * 3.0
    return np.concatenate([xy, z], axis=2).astype(np.float64)


def test_contact_batch_is_the_scalar_contact_bit_for_bit():
    for seed in RNG_SEEDS:
        rng = np.random.default_rng(seed)
        TI, TJ = _tris(rng, 600), _tris(rng, 600)
        dist, pt = T._tri_tri_xy_contact_batch(TI, TJ)
        for k in range(len(TI)):
            d, p = T._tri_tri_xy_contact(TI[k], TJ[k])
            assert dist[k] == d and tuple(pt[k]) == tuple(p), (seed, k)


def test_seam_joins_is_the_scalar_seam_test():
    agent = T.AgentModel()
    eps, step = agent.adjacency_eps, agent.max_step_up
    for seed in RNG_SEEDS:
        rng = np.random.default_rng(100 + seed)
        TI, TJ = _tris(rng, 600), _tris(rng, 600)
        got = T._seam_joins(TI, TJ, eps, step)
        for k in range(len(TI)):
            d, p = T._tri_tri_xy_contact(TI[k], TJ[k])
            want = (d <= eps + T.CONTACT_TOL and abs(T._plane_z_at(TI[k], p[0], p[1])
                                                     - T._plane_z_at(TJ[k], p[0], p[1]))
                    <= step + T.CONTACT_TOL)
            assert bool(got[k]) == want, (seed, k)


def test_grid_pairs_holds_every_overlapping_pair_once_in_order():
    rng = np.random.default_rng(7)
    lo = rng.random((300, 2)) * 200
    hi = lo + rng.random((300, 2)) * 30
    ci, cj = T._grid_pairs(lo, hi, 16.0)
    got = list(zip(ci.tolist(), cj.tolist()))
    assert got == sorted(set(got)) and all(i < j for i, j in got)
    over = {(i, j) for i in range(300) for j in range(i + 1, 300)
            if (lo[j] <= hi[i]).all() and (hi[j] >= lo[i]).all()}
    assert over <= set(got)


def test_tri_buckets_find_what_bary_z_finds():
    rng = np.random.default_rng(11)
    tris = _tris(rng, 400, lattice=8.0, spread=12)
    P = np.r_[rng.random((500, 2)) * 96, tris[:50, 0, :2], tris[50:100, :2, :2].mean(axis=1)]
    ins, z = T._bary_z(P, tris)
    grid = T._TriBuckets(tris)
    k, t, gins, gz = grid.pairs(P)
    assert {(a, b) for a, b in zip(k[gins].tolist(), t[gins].tolist())} == set(map(tuple, np.argwhere(ins).tolist()))
    assert (gz[gins] == z[k[gins], t[gins]]).all()
    for i in range(0, len(P), 7):
        hins, hz = grid.heights(float(P[i, 0]), float(P[i, 1]))
        assert hz[hins].tolist() == z[i][ins[i]].tolist()
