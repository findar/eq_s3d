r"""Stock drops between floors, and the links between a zone's built and cave parts
(district races step 31, task 1).

**Drops.** The zone's walked floor on step 6's layered 4 u raster
(``dungeon_topology_survey.Floor``'s rules: floor-wound standable faces, neighbours join
within ``max_step_up`` plus a 40 deg slope over the cell step), keeping every floor piece of
at least ``MIN_PIECE`` cells, not just the largest, so a floor reached only by falling is
there. A **drop** starts at a cell of the largest piece (the walked zone: a ledge you can
stand on) in a direction where it has no walk neighbour: the column one or two cells on
(``REACH``) holds no floor the walk could step to and does hold floor lower by more than
that step (the 3 u of ``AgentModel.max_step_up`` plus the slope allowance, the raster's
form of the gate's seam test), at most ``LOOK`` u down; the highest such floor is the
landing. It counts only if nothing solid lies between: a segment ``BODY`` u over the ledge
out to the landing's column, then straight down to just over the landing, crosses no solid
face (``wall_survey._arrays``: every face that isn't passable). Neighbouring drop cells are
one **site** (at least ``MIN_SITE`` cells); its height is the median of its cells'.

Per zone, then pooled per kind (``stock_room_shapes.KINDS``, built, cave and city,
``LEFT_OUT`` dropped): site heights p50/p90/max, and **passage ends**: the zone is split
into chambers and passage at its race's width (``stock_room_shapes``: the ``--halls``
split, run on every piece kept here); a site is a **drop end** when most of its ledge
cells are passage and it lies at the passage's tip (the passage's cells within ``REACH_END``
u of the site sit behind it: the drop's direction is within 45 deg of the way out from
them, and, where those cells run one way (``ELONGATED``), within 45 deg of that run, so a
drop off a tunnel's side is a ledge, not an end). The flush ends are the doorways (a connected run of passage cells touching one
chamber) of the passages that link two chambers and of the passages a drop ends (so a
dead-end nook off one chamber is no end). The share is drop ends over drop ends plus
flush ends.

**Layered links** (``--layered``): each chamber's finish (``room_scale_survey.measure_scales``,
the 0-10 estimate from its walls' grid share; under ``CAVE_BELOW`` reads as cave, the rest as
built), chambers with no finish left out; a chamber alone among the other class (a wing of
one) takes its neighbours' majority; then the chamber graph's same-class components are the
parts, and a zone mixes when it has a built and a cave part of at least ``MIN_PART``
chambers each, joined, and each class holds at least ``MIN_SHARE`` of the graded chambers. Per zone: the chamber-graph edges joining each such built part to each such
cave part it touches.

What the methods miss: drops into water read as drops (water regions are BSP data, not
read); a slope too steep to stand on reads as a drop if it falls more than the step
(you'd slide it: also one-way); placed objects (bridges, stairs, lifts) aren't in the zone
mesh, so a drop beside a placed stair counts; a lip or railing lower than ``BODY`` u doesn't
block; ledges on a floor piece other than the largest (kaesora's temple, a zone-in reached
by a drop) aren't looked at; drops off a ledge under a cell wide, or onto floor under ``MIN_PIECE`` cells, are
missed; the raster's cell height averages a cell's floor, so a drop of a few u reads within
about 2 u. Passage ends: passages under the chamber width are passage, and a passage room
under it too, so a drop out of a small room reads as a passage end; a side drop off a
walkway along the passage reads as an end only when it points out of the passage's tip.
Layered: the finish is a wall-squareness read, not material, and a small chamber's few walls
make it noisy; links through chambers with no finish are missed.

Usage::

    python scripts/stock_drops.py --eq-path F:\everquest_rof2 --cache %TEMP%\p9cache
    python scripts/stock_drops.py --eq-path F:\everquest_rof2 --zones kaesora --spot 3
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from analyzer.traverse import AgentModel  # noqa: E402
from dungeon_topology_survey import (CELL, LAYER_GAP, WIDTH, Floor, _samples,  # noqa: E402
                                     _sub_components, chamber_graph, split)
from generators.semantics import RACE_HEIGHT  # noqa: E402
from stock_room_shapes import KINDS, LEFT_OUT, _mesh, _race, floor_tris  # noqa: E402
from wall_survey import _arrays  # noqa: E402

MIN_PIECE = 25      # floor pieces under this many cells (400 u^2) are left out
REACH = 2           # a landing is one or two cells on from the ledge
LOOK = 500.0        # and at most this far down (u)
BODY = 2.5          # the clear-path test runs this far over the ledge (u)
LAND = 2.0          # and down to this far over the landing (u)
MIN_SITE = 2        # a site has at least this many ledge cells
REACH_END = 24.0    # a passage's cells this near a site say which way it runs (u)
END_ANGLE = 45.0    # a site within this of the way out of the passage is its end (deg)
ELONGATED = 2.0     # a passage's near cells this much longer than wide have a run direction
BUCKET = 16.0       # solid faces bucketed on this XY grid (u)
CAVE_BELOW = 4.5    # finish under this is cave (rough 0-3, hewn 4-6, built 7-10)
MIN_PART = 3        # a part has at least this many chambers
MIN_SHARE = 0.2     # and a mixed zone at least this share of its chambers in each class
DROP_KINDS = ("built", "cave", "city")
#: Zones the wall survey and the room-scale survey left out as mixed: where layered links are.
MIXED = ("chardok", "cazicthule", "hole", "mistmoore", "velketor", "unrest", "dulak")


# ---------------------------------------------------------------------------
# Floor: every piece
# ---------------------------------------------------------------------------

def all_floor(tris: np.ndarray, agent: AgentModel):
    """``Floor``'s layered raster keeping every piece of at least ``MIN_PIECE`` cells.

    Returns the Floor (its graph, xy, z, boundary and dist over the kept cells), each
    cell's piece label, the largest piece's label, and column -> cells."""
    pts = _samples(tris, CELL / 2)
    ij = np.floor(pts[:, :2] / CELL).astype(np.int64)
    order = np.lexsort((pts[:, 2], ij[:, 1], ij[:, 0]))
    ij, z = ij[order], pts[order, 2]
    new_col = np.ones(len(z), bool)
    new_col[1:] = (ij[1:] != ij[:-1]).any(1)
    new_node = new_col.copy()
    new_node[1:] |= (z[1:] - z[:-1]) > LAYER_GAP
    node = np.cumsum(new_node) - 1
    n = int(node[-1]) + 1
    nij = ij[new_node]
    nz = np.bincount(node, z, n) / np.bincount(node, None, n)
    cols: dict = defaultdict(list)
    for k, (ci, cj) in enumerate(nij):
        cols[(int(ci), int(cj))].append(k)
    tan = math.tan(math.radians(agent.walkable_slope_deg))
    rows, colz, wts = [], [], []
    for k, (ci, cj) in enumerate(nij):
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                if not (di or dj):
                    continue
                d = math.hypot(di, dj) * CELL
                lim = agent.max_step_up + d * tan
                best = None
                for m in cols.get((int(ci) + di, int(cj) + dj), ()):
                    dz = abs(nz[m] - nz[k])
                    if dz <= lim and (best is None or dz < best[1]):
                        best = (m, dz)
                if best is not None:
                    rows.append(k)
                    colz.append(best[0])
                    wts.append(d)
    g = coo_matrix((wts, (rows, colz)), shape=(n, n)).tocsr()
    g = g.maximum(g.T)
    _, lab = connected_components(g, directed=False)
    size = np.bincount(lab)
    idx = np.nonzero(size[lab] >= MIN_PIECE)[0]
    floor = Floor.__new__(Floor)
    floor.graph = g[idx][:, idx]
    floor.ij, floor.z = nij[idx], nz[idx]
    floor.xy = (floor.ij + 0.5) * CELL
    floor.n = len(idx)
    floor.boundary = np.diff(floor.graph.indptr) < 8
    dist = dijkstra(floor.graph, directed=False, indices=np.nonzero(floor.boundary)[0],
                    min_only=True)
    floor.dist = dist + CELL / 2
    piece = lab[idx]
    main = int(np.bincount(piece).argmax())
    kcols: dict = defaultdict(list)
    for k, (ci, cj) in enumerate(floor.ij):
        kcols[(int(ci), int(cj))].append(k)
    return floor, piece, main, kcols


# ---------------------------------------------------------------------------
# Clear path: segment against the solid faces
# ---------------------------------------------------------------------------

class Solids:
    """The zone's solid faces in XY buckets, for segment tests."""

    def __init__(self, tri: np.ndarray):
        self.tri = tri
        lo = np.floor(tri[:, :, :2].min(1) / BUCKET).astype(np.int64)
        hi = np.floor(tri[:, :, :2].max(1) / BUCKET).astype(np.int64)
        span = (hi - lo + 1).prod(1)
        keep = np.nonzero(span <= 4096)[0]     # a sky lid or a sea plane isn't between floors
        self.skipped = int(len(tri) - len(keep))
        keys, ids = [], []
        for t in keep:
            ii, jj = np.meshgrid(np.arange(lo[t, 0], hi[t, 0] + 1),
                                 np.arange(lo[t, 1], hi[t, 1] + 1), indexing="ij")
            keys.append(ii.ravel() * 1_000_003 + jj.ravel())
            ids.append(np.full(ii.size, t))
        keys = np.concatenate(keys) if keys else np.zeros(0, np.int64)
        ids = np.concatenate(ids) if ids else np.zeros(0, np.int64)
        o = np.argsort(keys, kind="stable")
        self.keys, self.ids = keys[o], ids[o]

    def _cands(self, bi, bj):
        k = bi * 1_000_003 + bj
        a = np.searchsorted(self.keys, k, "left")
        b = np.searchsorted(self.keys, k, "right")
        return a, b

    def blocked(self, p0: np.ndarray, p1: np.ndarray) -> np.ndarray:
        """Whether each segment p0[i] -> p1[i] crosses a solid face."""
        n = len(p0)
        out = np.zeros(n, bool)
        if not n:
            return out
        lo = np.floor(np.minimum(p0[:, :2], p1[:, :2]) / BUCKET).astype(np.int64)
        hi = np.floor(np.maximum(p0[:, :2], p1[:, :2]) / BUCKET).astype(np.int64)
        seg_ids, tri_ids = [], []
        for di in (0, 1):
            for dj in (0, 1):
                bi = np.minimum(lo[:, 0] + di, hi[:, 0])
                bj = np.minimum(lo[:, 1] + dj, hi[:, 1])
                if di and (hi[:, 0] == lo[:, 0]).all():
                    continue
                if dj and (hi[:, 1] == lo[:, 1]).all():
                    continue
                first = ((di == 0) | (hi[:, 0] > lo[:, 0])) & ((dj == 0) | (hi[:, 1] > lo[:, 1]))
                a, b = self._cands(bi, bj)
                cnt = np.where(first, b - a, 0)
                tot = int(cnt.sum())
                if not tot:
                    continue
                s = np.repeat(np.arange(n), cnt)
                start = np.repeat(a, cnt)
                off = np.arange(tot) - np.repeat(np.cumsum(cnt) - cnt, cnt)
                seg_ids.append(s)
                tri_ids.append(self.ids[start + off])
        if not seg_ids:
            return out
        s = np.concatenate(seg_ids)
        t = np.concatenate(tri_ids)
        pair = np.unique(s * (len(self.tri) + 1) + t)
        s, t = pair // (len(self.tri) + 1), pair % (len(self.tri) + 1)
        for c in range(0, len(s), 2_000_000):
            ss, tt = s[c:c + 2_000_000], t[c:c + 2_000_000]
            hit = _seg_tri(p0[ss], p1[ss], self.tri[tt])
            out[np.unique(ss[hit])] = True
        return out


def _seg_tri(p0, p1, tri, eps=1e-9):
    """Moller-Trumbore, segment form: does p0 -> p1 cross the triangle (inside its span)."""
    d = p1 - p0
    e1 = tri[:, 1] - tri[:, 0]
    e2 = tri[:, 2] - tri[:, 0]
    h = np.cross(d, e2)
    a = np.einsum("ij,ij->i", e1, h)
    ok = np.abs(a) > eps
    f = np.where(ok, 1.0 / np.where(ok, a, 1.0), 0.0)
    s = p0 - tri[:, 0]
    u = f * np.einsum("ij,ij->i", s, h)
    q = np.cross(s, e1)
    v = f * np.einsum("ij,ij->i", d, q)
    t = f * np.einsum("ij,ij->i", e2, q)
    return ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-6) & (t < 1 - 1e-6)


# ---------------------------------------------------------------------------
# Drops
# ---------------------------------------------------------------------------

def find_drops(floor: Floor, piece, main: int, kcols: dict, solids: Solids, agent: AgentModel):
    """Per ledge cell: (ledge cell, landing cell, height) of its lowest clear drop."""
    tan = math.tan(math.radians(agent.walkable_slope_deg))
    cand = []
    for k in np.nonzero(piece == main)[0]:
        ci, cj = (int(v) for v in floor.ij[k])
        zk = floor.z[k]
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                if not (di or dj):
                    continue
                for s in range(1, REACH + 1):
                    lim = agent.max_step_up + math.hypot(di, dj) * s * CELL * tan
                    col = kcols.get((ci + s * di, cj + s * dj), ())
                    if any(abs(floor.z[m] - zk) <= lim for m in col):
                        break                       # floor goes on here: no drop this way
                    below = [m for m in col if lim < zk - floor.z[m] <= LOOK]
                    if below:
                        cand.append((k, max(below, key=lambda m: floor.z[m])))
                        break
    if not cand:
        return []
    cand = np.array(cand)
    k, m = cand[:, 0], cand[:, 1]
    up = np.c_[floor.xy[k], floor.z[k] + BODY]
    over = np.c_[floor.xy[m], floor.z[k] + BODY]
    land = np.c_[floor.xy[m], floor.z[m] + LAND]
    clear = ~solids.blocked(up, over)
    clear[clear] = ~solids.blocked(over[clear], land[clear])
    best: dict = {}
    for kk, mm in zip(k[clear], m[clear]):
        h = float(floor.z[kk] - floor.z[mm])
        if kk not in best or h < best[kk][2]:
            best[int(kk)] = (int(kk), int(mm), h)
    return list(best.values())


def drop_sites(floor: Floor, drops: list) -> list:
    """Neighbouring ledge cells grouped: (ledge cells, landing cells, heights) per site."""
    if not drops:
        return []
    ks = np.array([d[0] for d in drops])
    mask = np.zeros(floor.n, bool)
    mask[ks] = True
    lab = _sub_components(floor.graph, mask)
    by = defaultdict(list)
    for d in drops:
        by[int(lab[d[0]])].append(d)
    return [v for v in by.values() if len(v) >= MIN_SITE]


def passage_ends(floor: Floor, chamber: np.ndarray, sites: list):
    """(doorways, drop ends, chamber-ledge sites) of one zone's split."""
    g = floor.graph.tocoo()
    a, b = chamber[g.row], chamber[g.col]
    plab = _sub_components(floor.graph, chamber < 0)
    touch = (a < 0) & (b >= 0)
    by_pc = defaultdict(set)
    for r, c in zip(g.row[touch], b[touch]):
        by_pc[(int(c), int(plab[r]))].add(int(r))
    n_ch = defaultdict(int)
    for (c, p) in by_pc:
        n_ch[p] += 1

    def doorways(keep_passages):
        out = 0
        for (c, p), rs in by_pc.items():
            if p not in keep_passages:
                continue
            mask = np.zeros(floor.n, bool)
            mask[list(rs)] = True
            lab = _sub_components(floor.graph, mask)
            out += len(np.unique(lab[list(rs)]))
        return out
    ends, ledge, end_p = [], 0, set()
    for site in sites:
        ks = np.array([d[0] for d in site])
        ms = np.array([d[1] for d in site])
        if (chamber[ks] < 0).mean() <= 0.5:
            ledge += 1
            continue
        p = np.bincount(plab[ks][plab[ks] >= 0]).argmax()
        centre = floor.xy[ks].mean(0)
        zc = floor.z[ks].mean()
        pn = np.nonzero(plab == p)[0]
        near = pn[(np.linalg.norm(floor.xy[pn] - centre, axis=1) <= REACH_END)
                  & (np.abs(floor.z[pn] - zc) <= 16.0)]
        out = centre - floor.xy[near].mean(0) if len(near) else np.zeros(2)
        go = (floor.xy[ms] - floor.xy[ks]).mean(0)
        nrm = np.linalg.norm(out) * np.linalg.norm(go)
        along = True
        if len(near) > 2:
            # The passage's run near the site (its cells' long axis): a drop off the side
            # of a tunnel runs across it, a drop at its tip along it.
            ev, vec = np.linalg.eigh(np.cov(floor.xy[near].T))
            if ev[1] > ELONGATED * max(ev[0], 1e-9):
                ax = vec[:, 1]
                along = abs(ax @ go) / max(np.linalg.norm(go), 1e-9) >= math.cos(math.radians(END_ANGLE))
        if along and nrm > 1e-9 and math.degrees(math.acos(np.clip(out @ go / nrm, -1, 1))) <= END_ANGLE:
            ends.append(site)
            end_p.add(int(p))
        else:
            ledge += 1
    # Flush ends: the doorways of the passages that link two chambers, and of those a drop ends.
    links = {p for p, k in n_ch.items() if k >= 2}
    return doorways(links | end_p), ends, ledge


def measure_drops(eq_path: Path, zone: str, agent: AgentModel, cache: Path = None) -> dict:
    t0 = time.time()
    race = _race(zone)
    h = RACE_HEIGHT.get(race, RACE_HEIGHT["default"])
    floor, piece, main, kcols = all_floor(floor_tris(eq_path, zone, agent, cache), agent)
    mesh, _eqg = _mesh(eq_path, zone)
    tri, _f, _n, _a = _arrays(mesh)
    solids = Solids(tri)
    drops = find_drops(floor, piece, main, kcols, solids, agent)
    sites = drop_sites(floor, drops)
    chamber, nch = split(floor, WIDTH * h / RACE_HEIGHT["default"])
    doors, ends, ledge = passage_ends(floor, chamber, sites)

    def site_row(site):
        hs = [d[2] for d in site]
        ks = np.array([d[0] for d in site])
        c = ks[np.argmin(np.linalg.norm(floor.xy[ks] - floor.xy[ks].mean(0), axis=1))]
        m = dict((d[0], d[1]) for d in site)[int(c)]
        return {"h": float(statistics.median(hs)), "cells": len(site),
                "x": float(floor.xy[c, 0]), "y": float(floor.xy[c, 1]), "z": float(floor.z[c]),
                "land_z": float(floor.z[m]), "lands_off_main": bool(piece[m] != main)}

    rows = [site_row(s) for s in sites]
    end_ids = {id(s) for s in ends}
    for r, s in zip(rows, sites):
        r["end"] = id(s) in end_ids
    return {"zone": zone, "race": race, "h_race": h, "cells": int(floor.n),
            "main_cells": int((piece == main).sum()), "pieces": int(len(np.unique(piece))),
            "drop_cells": [d[2] for d in drops], "sites": rows, "doors": doors,
            "ends": len(ends), "ledge": ledge, "nch": nch, "skipped_faces": solids.skipped,
            "secs": time.time() - t0}


def _q(v, qs=(50, 90)):
    return [float(np.percentile(v, q)) if len(v) else float("nan") for q in qs]


def drops_report(a, agent) -> list:
    print(f"{'zone':12s} {'kind':5s} {'cells':>6s} {'pcs':>3s} {'dcell':>5s} {'sites':>5s} "
          f"{'site h 50/90/max u':>18s} {'off':>3s} {'doors':>5s} {'ends':>4s} {'share':>5s} "
          f"{'secs':>5s}")
    rows = []
    for kind in a.kinds:
        for zone in KINDS[kind]:
            if a.zones and zone not in a.zones:
                continue
            try:
                r = measure_drops(a.eq_path, zone, agent, a.cache)
            except Exception as e:  # noqa: BLE001 - a zone this install lacks or can't read
                print(f"{zone:12s} {kind:5s} error: {type(e).__name__}: {e}")
                continue
            r["kind"] = kind
            rows.append(r)
            hs = [s["h"] for s in r["sites"]]
            p50, p90 = _q(hs)
            share = r["ends"] / (r["ends"] + r["doors"]) if r["ends"] + r["doors"] else float("nan")
            print(f"{zone:12s} {kind:5s} {r['cells']:6d} {r['pieces']:3d} {len(r['drop_cells']):5d} "
                  f"{len(hs):5d} {p50:6.0f}/{p90:5.0f}/{(max(hs) if hs else float('nan')):5.0f} "
                  f"{sum(s['lands_off_main'] for s in r['sites']):3d} {r['doors']:5d} {r['ends']:4d} "
                  f"{share:5.2f} {r['secs']:5.0f}" + ("  (left out)" if zone in LEFT_OUT else ""),
                  flush=True)
    print()
    print("pooled per kind (LEFT_OUT dropped): site heights (u), per-cell heights, passage ends")
    print(f"{'kind':6s} {'zones':>5s} {'sites':>5s} {'site h 50/90/max':>17s} {'cell h 50/90':>12s} "
          f"{'doors':>5s} {'ends':>4s} {'share':>5s} {'zone share 10/50/90':>20s}")
    pooled = [r for r in rows if r["zone"] not in LEFT_OUT]
    for kind in list(dict.fromkeys(r["kind"] for r in pooled)) + ["all"]:
        rs = [r for r in pooled if kind in ("all", r["kind"])]
        hs = [s["h"] for r in rs for s in r["sites"]]
        hc = [x for r in rs for x in r["drop_cells"]]
        doors = sum(r["doors"] for r in rs)
        ends = sum(r["ends"] for r in rs)
        zs = [r["ends"] / (r["ends"] + r["doors"]) for r in rs if r["ends"] + r["doors"]]
        z10, z50, z90 = _q(zs, (10, 50, 90))
        print(f"{kind:6s} {len(rs):5d} {len(hs):5d} {_q(hs)[0]:6.0f}/{_q(hs)[1]:4.0f}/"
              f"{(max(hs) if hs else float('nan')):5.0f} {_q(hc)[0]:5.0f}/{_q(hc)[1]:5.0f} "
              f"{doors:5d} {ends:4d} {ends / max(1, ends + doors):5.2f} "
              f"{z10:6.2f}/{z50:5.2f}/{z90:6.2f}")
    return rows


def spot_check(rows: list, n: int) -> None:
    """``n`` typical drop ends for a look in the client: one per kind in turn, height between
    the pooled p50 and p90, landing on the walked piece, a doorway-sized site (3-40 cells);
    the widest such per kind."""
    pool = [(r["kind"], r["zone"], s) for r in rows if r["zone"] not in LEFT_OUT for s in r["sites"]]
    lo, hi = _q([s["h"] for _, _, s in pool])
    pick = [p for p in pool if p[2]["end"] and not p[2]["lands_off_main"]
            and lo <= p[2]["h"] <= hi and 3 <= p[2]["cells"] <= 40]
    pick.sort(key=lambda p: -p[2]["cells"])
    out, seen = [], set()
    kinds = list(dict.fromkeys(p[0] for p in pick))
    while len(out) < n and any(p[1] not in seen for p in pick):
        for kind in kinds:
            for p in pick:
                if p[0] == kind and p[1] not in seen:
                    seen.add(p[1])
                    out.append(p[1:])
                    break
            if len(out) == n:
                break
    print()
    print("spot check (ledge cell nearest the site's middle; EQ's /loc prints y, x, z):")
    for zone, s in out:
        print(f"  {zone}: ledge x {s['x']:.0f} y {s['y']:.0f} z {s['z']:.0f} -> landing z "
              f"{s['land_z']:.0f} ({s['h']:.0f} u, {s['cells']} cells, "
              f"{'passage end' if s['end'] else 'ledge'}"
              f"{', lands off the walked piece' if s['lands_off_main'] else ''})")


# ---------------------------------------------------------------------------
# Layered links
# ---------------------------------------------------------------------------

def layered(eq_path: Path, zone: str, agent: AgentModel, cache: Path = None) -> dict:
    from room_scale_survey import measure_scales
    mesh, eqg = _mesh(eq_path, zone)
    m = measure_scales(mesh, agent, floors_up=eqg, faces=(floor_tris(eq_path, zone, agent, cache),))
    if not m.get("edges"):
        return {"zone": zone, "mixed": False, "built": 0, "cave": 0, "pairs": []}
    floor, chamber, values = m["_floor"], m["_chamber"], m["_values"]
    nch = int(chamber.max()) + 1
    cls = {c: ("cave" if v < CAVE_BELOW else "built") for c, v in values.items()}
    edges = [(u, v) for u, v in chamber_graph(floor, chamber, nch) if u in cls and v in cls]
    adj = defaultdict(set)
    for u, v in edges:
        adj[u].add(v)
        adj[v].add(u)
    # A chamber with no neighbour of its own class takes its neighbours' majority.
    for c in list(cls):
        nb = [cls[x] for x in adj[c]]
        if nb and cls[c] not in nb:
            cls[c] = max(set(nb), key=nb.count)
    parent = {c: c for c in cls}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for u, v in edges:
        if cls[u] == cls[v]:
            parent[find(u)] = find(v)
    size = defaultdict(int)
    for c in cls:
        size[find(c)] += 1
    big = {p for p, s in size.items() if s >= MIN_PART}
    links = defaultdict(int)
    for u, v in edges:
        pu, pv = find(u), find(v)
        if cls[u] != cls[v] and pu in big and pv in big:
            key = (pu, pv) if cls[u] == "built" else (pv, pu)
            links[key] += 1
    nb = sum(1 for p in big if cls[p] == "built")
    nc = sum(1 for p in big if cls[p] == "cave")
    share = min(sum(v == "built" for v in cls.values()), sum(v == "cave" for v in cls.values())) / len(cls)
    return {"zone": zone, "mixed": bool(nb and nc and links and share >= MIN_SHARE),
            "built": nb, "cave": nc, "share": share,
            "chambers": len(cls), "pairs": sorted(links.values(), reverse=True),
            "built_ch": sum(1 for c in cls if cls[c] == "built" and find(c) in big),
            "cave_ch": sum(1 for c in cls if cls[c] == "cave" and find(c) in big)}


def layered_report(a, agent) -> None:
    zones = list(dict.fromkeys(list(MIXED) + [z for k in ("built", "cave") for z in KINDS[k]]))
    if a.zones:
        zones = [z for z in zones if z in a.zones]
    print()
    print(f"layered links (finish < {CAVE_BELOW} cave, parts of >= {MIN_PART} chambers, "
          f"minority class >= {MIN_SHARE}); built/cave = parts (chambers in them):")
    print(f"{'zone':12s} {'ch':>3s} {'built':>9s} {'cave':>9s} {'minor':>5s} {'mixed':>5s}  "
          f"links per built-cave pair")
    per_zone = []
    for zone in zones:
        if not ((a.eq_path / f"{zone}.s3d").exists() or (a.eq_path / f"{zone}.eqg").exists()):
            print(f"{zone:12s} not in the install")
            continue
        try:
            r = layered(a.eq_path, zone, agent, a.cache)
        except Exception as e:  # noqa: BLE001
            print(f"{zone:12s} error: {type(e).__name__}: {e}")
            continue
        if not r.get("chambers"):
            print(f"{zone:12s} no graded chambers")
            continue
        print(f"{zone:12s} {r['chambers']:3d} {r['built']:3d} ({r['built_ch']:3d}) "
              f"{r['cave']:3d} ({r['cave_ch']:3d}) {r['share']:5.2f} "
              f"{'yes' if r['mixed'] else 'no':>5s}  "
              f"{r['pairs']}" + ("  (left out)" if zone in LEFT_OUT else ""), flush=True)
        if r["mixed"] and zone not in LEFT_OUT:
            per_zone.append((zone, r))
    if per_zone:
        tot = [sum(r["pairs"]) for _, r in per_zone]
        best = [r["pairs"][0] for _, r in per_zone]
        allp = [x for _, r in per_zone for x in r["pairs"]]
        print(f"mixed zones {len(per_zone)} ({', '.join(z for z, _ in per_zone)}): links per zone "
              f"median {statistics.median(tot):.1f} (min {min(tot)}, max {max(tot)}); the "
              f"best-linked pair per zone median {statistics.median(best):.1f}; per pair median "
              f"{statistics.median(allp):.1f} over {len(allp)} pairs")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--eq-path", required=True, type=Path)
    ap.add_argument("--kinds", nargs="+", default=list(DROP_KINDS))
    ap.add_argument("--zones", nargs="+", help="only these zones")
    ap.add_argument("--cache", type=Path, help="floor faces, as stock_room_shapes --cache")
    ap.add_argument("--spot", type=int, default=3, help="drop sites to print for a look")
    ap.add_argument("--no-layered", action="store_true", help="skip the layered links")
    a = ap.parse_args(argv)
    agent = AgentModel()
    rows = drops_report(a, agent)
    if rows and a.spot:
        spot_check(rows, a.spot)
    if not a.no_layered:
        layered_report(a, agent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
