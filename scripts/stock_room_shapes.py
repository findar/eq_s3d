r"""Stock room sizes, shapes and placement per kind of zone (step 27, task 9).

Rooms can't be read from the zone files (a WLD zone is one triangle soup), so a
room is a **chamber** of step 6's floor split (``dungeon_topology_survey``): the
zone's walked floor (floor-wound faces the traversal agent can stand on, slope
<= 40 deg, step <= 3 u) on a 4 u layered raster, the floor wider than ``WIDTH``
(40 u x H / 6, as ``race_size_survey`` scales it for big races) split at necks
(a watershed on the distance to the floor's edge: two wide basins stay apart
where the floor between them is under 3/4 of the narrower one's widest point)
and grown back out by half the width. Floor narrower than the width is passage.
Chambers touch, or one passage joins them: those are the edges.

Per chamber: area = its raster cells x 16 u^2; side = sqrt(area); aspect =
sqrt of the ratio of its floor's two principal variances (exactly long/short
for a rectangle; an L or a ring reads squarer than its bounding box); centre =
its floor's mean. Then ``grid_score.measure_shape`` (the same code that judges
our builds): axis share of the edge bearings (world axes, and at the rotation
catching most), nearest-neighbour spread, side/aspect/area spread.

**Entry angle**, per doorway (a connected run of passage cells touching a
chamber): the passage's direction is from the doorway's centre to the mean of
that passage's cells within ``REACH`` u of it (on the doorway's level); the
wall's outward normal is the mean, over the doorway's chamber-side cells, of
the vector from the nearest core cell (floor at least half the width from any
edge) to the cell, which is square to a straight wall. The angle between them
is 0 for a passage meeting its wall square. Chambers that touch directly (a
neck, no passage) have no entry angle; their share is printed as ``direct``.

What it can't see: rooms narrower than the width threshold (under about 7 H
across) are passage, so the smallest stock rooms are missing and the side
minimum reads high; a chamber's side includes its door stubs. Open land
(outdoor, open-air cities) has no necks to split at, so its chambers are
pieces of open ground cut where it narrows between hills or buildings, not
rooms; read those kinds as "open areas", not rooms.

``--halls`` (hall length step 30, task 1): **hall length door to door**, per
passage link between two chambers, the shortest walk through that passage's own
cells from one chamber's doorway cells to the other's, plus a cell (``hall_lengths``),
per zone and pooled per kind (p10/p50/p90, and the spread of the zone medians;
``grid_score.hall_table``). Direct contacts (chambers touching, no passage) have no
length, and passages no longer than ``SHORT_H`` (3 H, a corridor's width) are openings;
both are left out, as our throats are (``excl``). What the raster misses: the walk runs on
an 8-neighbour 4 u grid and cuts inside corners, so it reads a winding passage a
little short of its centreline and a straight diagonal up to ~8 % long; a passage
under a cell wide, or broken where the walk's step limit parts it, joins nothing; a
chamber's edge sits about a cell past its room's wall, so each hall reads a few u
short; a passage room under the width threshold is counted as hall, so a chain of
small rooms reads as one long hall. Outdoor kinds are open areas, not rooms.

``--halls --by-race`` (district races step 31, task 1): the same lengths grouped by the
zone's inhabiting race (``BY_RACE``, a hand table; each name is checked against the install
and the missing ones printed), each zone measured at that race's H (``RACE_HEIGHT``; races
it lacks, orc, undead, dwarf and dark elf, at the default 6 u) and with the chamber width
scaled to it. Per race group: pooled door-to-door p10/p50/p90 and the spread of the zone
medians, in u and in H. A race has a **signal** if the median of its zone medians lies
outside all-built's zone-median p10..p90 band (``KINDS["built"]`` less ``LEFT_OUT``), read
both in H and in u (a giant's hall is long in u and short in H). LDoN adventure zones
(``guk*``, ``ruj*``, ``mmc*``, ``mir*``) are instanced layouts of one theme each, so a
race of them weighs four zones of one designer's kit.

``--eqg A.eqg ...`` runs the same method on built zones: the calibration, since a
built room's true side, aspect and square doors are known from its spec.

``--plots DIR`` draws each zone's chambers and edges (``DIR/<zone>.png``).
``--cache DIR`` keeps each zone's floor faces. ``.eqg`` zones are read from
their ``.ter`` (floors are the side with the larger standable area).

Usage::

    python scripts/stock_room_shapes.py --eq-path F:\everquest_rof2 --cache %TEMP%\p9cache
    python scripts/stock_room_shapes.py --eq-path F:\everquest_rof2 --kinds cave --plots %TEMP%\p9
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from analyzer.traverse import AgentModel, build_walk_surface  # noqa: E402
from dungeon_topology_survey import (CELL, WIDTH, Floor, _sub_components,  # noqa: E402
                                     chamber_graph, plot, split)
from generators.semantics import RACE_HEIGHT  # noqa: E402
from grid_score import (angle_between, hall_summary, hall_table, measure_shape,  # noqa: E402
                        shape_table, summarise_shapes)
from race_size_survey import ZONE_RACE  # noqa: E402

#: Kind -> stock zones. Built = built and hewn dungeons (wall_survey's styles);
#: cave = rough-walled ones; city = city zones, enclosed and open; outdoor =
#: outdoor zones with walled-in ground (the outdoor dungeons' stock).
KINDS = {
    "built": ("befallen", "guktop", "gukbottom", "sebilis", "karnor", "chardok", "charasis",
              "kaesora", "najena", "qcat", "kurn", "codecay", "hohonora", "sleeper",
              "tacvi", "inktuta", "txevu"),
    "cave": ("blackburrow", "paw", "crystal", "runnyeye", "soldunga", "soldungb",
             "permafrost", "droga"),
    "city": ("neriaka", "neriakb", "neriakc", "kaladima", "kaladimb", "akanon", "paineel",
             "thurgadina", "shadowhaven", "felwithea", "erudnext", "cabwest", "oggok",
             "halas", "rivervale", "qeynos", "freporte"),
    "outdoor": ("crushbone", "beholder", "unrest", "mistmoore", "kithicor", "lavastorm"),
}
#: Zones measured but whose split doesn't give rooms (left out of the kind's row).
LEFT_OUT = {
    "hohonora": "a Plane of Power zone of open courts: 146 open areas up to 7x the median",
    "droga": "124 chambers (wall_survey leaves it out too); it would outweigh the other caves",
    # Open cities: the open ground is one area many times the median (max/median 11-26),
    # or the whole zone (qeynos). Their room-like areas are the enclosed cities'.
    "qeynos": "open city: the whole walked floor is one area",
    "freporte": "open city: one open area 26x the median",
    "erudnext": "open city: one open area 22x the median",
    "paineel": "open city: one open area 12x the median",
}
#: Races beyond race_size_survey's list.
EXTRA_RACE = {"karnor": "lizardman", "sebilis": "froglok", "charasis": "default",
              "kael": "giant", "thurgadina": "default"}

REACH = 24.0        # a passage's first leg: its cells this far from the doorway (u)
LEVEL = 16.0        # and within this of the doorway's floor height (u)
#: ``--halls``: a passage no longer than this many H (a stock corridor's width, the
#: 3 H ours are cut to) is an opening, not a hall: read as a throat (ours: a corridor
#: no longer than its width) and left out with the direct contacts.
SHORT_H = 3.0


#: Races replaced here: Nagafen's lair is one dragon cave in a kobold warren; at a
#: dragon's width (140 u) the whole of soldungb is one chamber.
OVERRIDE_RACE = {"soldungb": "kobold"}


#: ``--by-race``: race group -> stock zones it inhabits (or built them). Asked for but not
#: in the RoF2 install: nurga (goblins), grobb (trolls), chardokb (sarnaks), gukta (frogloks).
#: No troll dungeon is left, so trolls have no row. Iksar-built zones count as lizardman.
BY_RACE = {
    "giant": ("kael",),
    "dragon": ("sleeper", "veeshan", "skyshrine"),
    "froglok": ("guktop", "gukbottom", "sebilis", "guka", "gukb", "gukc", "gukd"),
    "sarnak": ("chardok",),
    "goblin": ("runnyeye", "droga"),
    "orc": ("crushbone", "ruja", "rujb", "rujc", "rujd"),
    "kobold": ("soldunga", "soldungb", "warrens"),
    "gnoll": ("blackburrow", "paw"),
    "ogre": ("oggok",),
    "lizardman": ("karnor", "kaesora", "charasis", "cazicthule"),
    "undead": ("befallen", "kurn", "codecay", "unrest", "mistmoore", "frozenshadow",
               "mmca", "mmcb", "mmcc", "mmcd", "mira", "mirb"),
    "dwarf": ("kaladima", "kaladimb", "thurgadina", "thurgadinb"),
    "dark elf": ("neriaka", "neriakb", "neriakc"),
}


def _race(zone: str) -> str:
    return OVERRIDE_RACE.get(zone) or ZONE_RACE.get(zone) or EXTRA_RACE.get(zone, "default")


def _mesh(eq_path: Path, zone: str):
    from outdoor_dungeon_survey import load_mesh
    if zone.endswith(".eqg"):           # a built zone (``--eqg``): its path
        path = Path(zone)
    elif (eq_path / f"{zone}.s3d").exists():
        return load_mesh(eq_path, zone), False
    else:
        path = eq_path / f"{zone}.eqg"
    from core.pfs import PfsArchive
    from core.ter import TerFile
    arc = PfsArchive.from_file(path)
    ter = [f.name for f in arc.files if f.name.endswith(".ter")]
    if not ter:
        raise FileNotFoundError(f"{zone}.eqg has no .ter")
    return TerFile.from_bytes(arc.get(ter[0])), True


def floor_tris(eq_path: Path, zone: str, agent: AgentModel, cache: Path = None) -> np.ndarray:
    cache = None if zone.endswith(".eqg") else cache
    if cache is not None and (cache / f"{zone}.npz").exists():
        return np.load(cache / f"{zone}.npz")["floor"]
    mesh, eqg = _mesh(eq_path, zone)
    surf = build_walk_surface(mesh, agent, floors_up=eqg)
    tri = surf.verts[surf.faces]
    nz = surf.normals[:, 2]
    if eqg:
        # Floors are the side with the larger standable area.
        area = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
        up = area[surf.standable & (nz > 0)].sum() >= area[surf.standable & (nz < 0)].sum()
        keep = surf.standable & ((nz > 0) if up else (nz < 0))
    else:
        keep = surf.standable & (nz < 0)    # WLD floors wind down
    floor = tri[np.nonzero(keep)[0]]
    if cache is not None:
        cache.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cache / f"{zone}.npz", floor=floor)
    return floor


def entry_angles(floor: Floor, chamber: np.ndarray, nch: int, width: float):
    """Entry angle (deg) per doorway, and the count of direct chamber-chamber contacts."""
    core = (floor.dist >= width / 2) & (chamber >= 0)
    trees = {}
    for c in range(nch):
        idx = np.nonzero(core & (chamber == c))[0]
        if len(idx):
            trees[c] = (cKDTree(floor.xy[idx]), idx)
    g = floor.graph.tocoo()
    a, b = chamber[g.row], chamber[g.col]
    direct = {(min(i, j), max(i, j)) for i, j in zip(a, b) if i >= 0 and j >= 0 and i != j}
    passage = chamber < 0
    plab = _sub_components(floor.graph, passage)
    # passage node -> chambers it touches; chamber-side contact cells per (passage node, chamber)
    touch = (a < 0) & (b >= 0)
    side: dict = {}
    for r, cn, c in zip(g.row[touch], g.col[touch], b[touch]):
        side.setdefault((int(c), int(r)), []).append(int(cn))
    by_pc: dict = {}
    for (c, r) in side:
        by_pc.setdefault((c, int(plab[r])), []).append(r)
    # Passage components touching one chamber only are alcoves, not links.
    links: dict = {}
    for (c, p) in by_pc:
        links.setdefault(p, set()).add(c)
    out = []
    for (c, p), rs in by_pc.items():
        if len(links[p]) < 2 or c not in trees:
            continue
        rs = np.array(sorted(set(rs)))
        mask = np.zeros(floor.n, bool)
        mask[rs] = True
        lab = _sub_components(floor.graph, mask)
        pnodes = np.nonzero(plab == p)[0]
        for d in np.unique(lab[rs]):
            door = rs[lab[rs] == d]
            m = floor.xy[door].mean(0)
            zm = floor.z[door].mean()
            near = pnodes[(np.linalg.norm(floor.xy[pnodes] - m, axis=1) <= REACH)
                          & (np.abs(floor.z[pnodes] - zm) <= LEVEL)]
            if len(near) < 2:
                continue
            go = floor.xy[near].mean(0) - m
            cells = sorted({cn for r in door for cn in side[(c, int(r))]})
            tree, idx = trees[c]
            _, k = tree.query(floor.xy[cells])
            nrm = (floor.xy[cells] - floor.xy[idx[k]]).mean(0)
            ang = angle_between(tuple(go), tuple(nrm))
            if ang == ang:
                out.append(ang)
    return out, len(direct)


def hall_lengths(floor: Floor, chamber: np.ndarray) -> list:
    """Door-to-door length (u) of each passage link between two chambers (``--halls``).

    Per passage component touching two or more chambers: its doorway cells per chamber
    (passage cells next to that chamber), the shortest walk through the passage's own
    cells from one chamber's doorway to the other's, plus one cell (half a cell each
    end, to the chamber's edge). A passage joining three or more chambers (a junction)
    gives the links of Prim's tree over those walks, as ``chamber_graph`` joins it.
    Chambers that touch directly (no passage) have no length and are left out."""
    from scipy.sparse.csgraph import dijkstra
    g = floor.graph.tocoo()
    a, b = chamber[g.row], chamber[g.col]
    plab = _sub_components(floor.graph, chamber < 0)
    touch = (a < 0) & (b >= 0)
    contacts: dict = {}
    for r, c in zip(g.row[touch], b[touch]):
        contacts.setdefault(int(plab[r]), {}).setdefault(int(c), set()).add(int(r))
    out = []
    for p, chs in contacts.items():
        if len(chs) < 2:
            continue                    # an alcove off one chamber
        nodes = np.nonzero(plab == p)[0]
        sub = floor.graph[nodes][:, nodes]
        ids = sorted(chs)
        door = {c: np.searchsorted(nodes, sorted(chs[c])) for c in ids}
        dist = {c: dijkstra(sub, directed=False, indices=door[c], min_only=True) for c in ids}
        d = {(u, v): float(dist[u][door[v]].min()) for u in ids for v in ids if u != v}
        inside, rest = {ids[0]}, set(ids[1:])
        while rest:
            best, u, v = min((d[(u, v)], u, v) for u in inside for v in rest)
            if np.isfinite(best):
                out.append(best + CELL)
            inside.add(v)
            rest.discard(v)
    return out


def measure_zone(eq_path: Path, zone: str, agent: AgentModel, cache: Path = None,
                 plots: Path = None, race: str = None) -> dict:
    t0 = time.time()
    race = race or _race(zone)
    h = RACE_HEIGHT.get(race, RACE_HEIGHT["default"])
    width = WIDTH * h / RACE_HEIGHT["default"]
    floor = Floor(floor_tris(eq_path, zone, agent, cache), agent)
    chamber, nch = split(floor, width)
    edges = chamber_graph(floor, chamber, nch)
    cen, sides, asp, areas = [], [], [], []
    for c in range(nch):
        xy = floor.xy[chamber == c]
        cen.append((*xy.mean(0), floor.z[chamber == c].mean()))
        areas.append(len(xy) * CELL * CELL)
        sides.append(math.sqrt(areas[-1]))
        ev = np.sort(np.linalg.eigvalsh(np.cov(xy.T))) if len(xy) > 2 else np.ones(2)
        asp.append(math.sqrt(ev[1] / max(ev[0], 1e-9)))
    m = measure_shape(cen, edges, sides, asp, areas, h)
    ent, direct = entry_angles(floor, chamber, nch, width)
    halls = hall_lengths(floor, chamber)
    short = sum(x <= SHORT_H * h for x in halls)
    m.update(zone=zone, race=race, nch=nch, entry=ent, direct=direct, short=short,
             excluded=direct + short, d2d=[x for x in halls if x > SHORT_H * h], h=h,
             med_side=float(np.median(sides)), secs=time.time() - t0)
    if plots is not None:
        plots.mkdir(parents=True, exist_ok=True)
        plot({"zone": Path(zone).stem, "floor": floor, "chamber": chamber, "nch": nch, "edges": edges,
              "centres": np.array(cen), "entry": 0, "map_lines": []},
             plots / f"{Path(zone).stem}.png")
    return m


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--eq-path", required=True, type=Path)
    ap.add_argument("--kinds", nargs="+", default=list(KINDS))
    ap.add_argument("--zones", nargs="+", help="only these zones (of the kinds)")
    ap.add_argument("--cache", type=Path)
    ap.add_argument("--plots", type=Path)
    ap.add_argument("--json", type=Path, help="write the per-zone rows here")
    ap.add_argument("--eqg", nargs="+", type=Path,
                    help="measure these built .eqg zones instead (the method's calibration: "
                         "our rooms' true sizes and square doors are known)")
    ap.add_argument("--halls", action="store_true",
                    help="print passage length door to door per zone and per kind instead")
    ap.add_argument("--by-race", action="store_true",
                    help="with --halls: group the lengths by the zone's race (BY_RACE)")
    a = ap.parse_args(argv)
    if a.halls and a.by_race:
        return _halls_by_race(a, AgentModel())
    agent = AgentModel()
    rows = []
    if a.eqg:
        for path in a.eqg:
            m = measure_zone(a.eq_path, str(path), agent, None, a.plots)
            m["kind"] = path.stem.rstrip("0123456789")    # p9cave2004 pools as p9cave
            rows.append(m)
        print(hall_table(hall_summary(rows)) if a.halls else shape_table(summarise_shapes(rows)))
        return 0
    if a.halls:
        return _halls(a, agent)
    print(f"{'zone':12s} {'kind':8s} {'race':9s} {'N':>3s} {'E':>3s} {'ax10':>5s} {'axbst':>5s} "
          f"{'nnCV':>5s} {'nnmin':>5s} {'ent50':>5s} {'>20':>4s} {'dir':>3s} "
          f"{'side u':>6s} {'mn/mx':>9s} {'asp50':>5s} {'arCV':>5s} {'secs':>5s}")
    for kind in a.kinds:
        for zone in KINDS[kind]:
            if a.zones and zone not in a.zones:
                continue
            try:
                m = measure_zone(a.eq_path, zone, agent, a.cache, a.plots)
            except Exception as e:  # noqa: BLE001 - a zone this install lacks or can't read
                print(f"{zone:12s} {kind:8s} error: {type(e).__name__}: {e}")
                continue
            m["kind"] = kind
            rows.append(m)
            ent = m["entry"]
            print(f"{zone:12s} {kind:8s} {m['race']:9s} {m['nch']:3d} {m['edges']:3d} "
                  f"{m['axis10']:5.2f} {m['axis10_best']:5.2f} {m['nn_cv']:5.2f} {m['nn_min']:5.2f} "
                  f"{(np.median(ent) if ent else float('nan')):5.0f} "
                  f"{(np.mean(np.array(ent) > 20) if ent else float('nan')):4.2f} {m['direct']:3d} "
                  f"{m['med_side']:6.0f} {m['side_min']:4.2f}/{m['side_max']:4.2f} "
                  f"{np.median(m['aspects']):5.2f} {m['area_cv']:5.2f} {m['secs']:5.0f}",
                  flush=True)
    kept = [r for r in rows if r["zone"] not in LEFT_OUT and r["nch"] >= 3]
    print()
    print("pooled per kind (zones with >= 3 chambers):")
    print(shape_table(summarise_shapes(kept)))
    if a.json:
        a.json.write_text(json.dumps([{k: v for k, v in r.items()} for r in rows], indent=1))
    return 0


def _halls(a, agent) -> int:
    """``--halls``: passage length door to door per zone, then per kind."""
    rows = []
    print(f"{'zone':12s} {'kind':8s} {'race':9s} {'N':>3s} {'halls':>5s} {'dir':>3s} {'shrt':>4s} "
          f"{'d2d 10/50/90 u':>16s} {'p50 H':>6s} {'secs':>5s}")
    for kind in a.kinds:
        for zone in KINDS[kind]:
            if a.zones and zone not in a.zones:
                continue
            try:
                m = measure_zone(a.eq_path, zone, agent, a.cache, a.plots)
            except Exception as e:  # noqa: BLE001 - a zone this install lacks or can't read
                print(f"{zone:12s} {kind:8s} error: {type(e).__name__}: {e}")
                continue
            m["kind"] = kind
            rows.append(m)
            d = sorted(m["d2d"])
            q = [float(np.percentile(d, k)) if d else float("nan") for k in (10, 50, 90)]
            print(f"{zone:12s} {kind:8s} {m['race']:9s} {m['nch']:3d} {len(d):5d} "
                  f"{m['direct']:3d} {m['short']:4d} {q[0]:5.0f}/{q[1]:4.0f}/{q[2]:5.0f} {q[1] / m['h']:6.1f} "
                  f"{m['secs']:5.0f}" + ("  (left out)" if zone in LEFT_OUT else ""), flush=True)
    kept = [r for r in rows if r["zone"] not in LEFT_OUT and r["nch"] >= 3]
    print()
    print("pooled per kind (zones with >= 3 chambers, LEFT_OUT dropped; outdoor = open areas):")
    print(hall_table(hall_summary(kept)))
    if a.json:
        a.json.write_text(json.dumps([{k: r[k] for k in ("zone", "kind", "race", "h", "nch",
                                                            "direct", "short", "d2d")} for r in rows],
                                     indent=1))
    return 0


def _halls_by_race(a, agent) -> int:
    """``--halls --by-race``: door-to-door length per race group, against all-built."""
    missing = [z for zs in BY_RACE.values() for z in zs
               if not ((a.eq_path / f"{z}.s3d").exists() or (a.eq_path / f"{z}.eqg").exists())]
    print("not in the install: " + (", ".join(missing) or "none")
          + " (asked for, not found: nurga, grobb, chardokb, gukta)")
    measured: dict = {}

    def run(zone, race):
        key = (zone, race)
        if key not in measured:
            h_race = race if race in RACE_HEIGHT else "default"
            try:
                measured[key] = measure_zone(a.eq_path, zone, agent, a.cache, None, race=h_race)
            except Exception as e:  # noqa: BLE001 - a zone this install lacks or can't read
                print(f"{zone:12s} error: {type(e).__name__}: {e}")
                measured[key] = None
        return measured[key]

    print(f"{'zone':12s} {'race':9s} {'H':>4s} {'N':>3s} {'halls':>5s} {'d2d 10/50/90 u':>16s} "
          f"{'p50 H':>6s} {'secs':>5s}")
    rows = []
    for group, zones in BY_RACE.items():
        for zone in zones:
            if zone in missing or (a.zones and zone not in a.zones):
                continue
            m = run(zone, group)
            if m is None:
                continue
            r = dict(m, kind=group)
            rows.append(r)
            d = sorted(r["d2d"])
            q = [float(np.percentile(d, k)) if d else float("nan") for k in (10, 50, 90)]
            print(f"{zone:12s} {group:9s} {r['h']:4.0f} {r['nch']:3d} {len(d):5d} "
                  f"{q[0]:5.0f}/{q[1]:4.0f}/{q[2]:5.0f} {q[1] / r['h']:6.1f} {r['secs']:5.0f}",
                  flush=True)
    base = []
    for zone in KINDS["built"]:
        if zone in LEFT_OUT or (a.zones and zone not in a.zones):
            continue
        m = run(zone, _race(zone))      # the kinds' own H, as ``--halls`` reads them
        if m is not None and m["nch"] >= 3:
            base.append(dict(m, kind="all-built"))
    kept = [r for r in rows if r["nch"] >= 3]
    s = hall_summary(base + kept)
    print()
    print("per race group (zones with >= 3 chambers), against all-built (KINDS built, "
          "LEFT_OUT dropped):")
    print(hall_table(s))
    b = s.get("all-built")
    if b:
        print()
        print("signal: the race's median zone median outside all-built's zone-median p10..p90 "
              f"(H {b['zmedh_p10']:.1f}..{b['zmedh_p90']:.1f}, u {b['zmed_p10']:.0f}.."
              f"{b['zmed_p90']:.0f}; all-built p50 {b['zmedh_p50']:.1f} H, {b['zmed_p50']:.0f} u)")
        print(f"{'race':9s} {'n':>2s} {'zmed50 H':>8s} {'x built':>7s} {'H sig':>5s} "
              f"{'zmed50 u':>8s} {'x built':>7s} {'u sig':>5s}")
        for group, r in s.items():
            if group == "all-built":
                continue
            sig_h = not b["zmedh_p10"] <= r["zmedh_p50"] <= b["zmedh_p90"]
            sig_u = not b["zmed_p10"] <= r["zmed_p50"] <= b["zmed_p90"]
            print(f"{group:9s} {r['n']:2d} {r['zmedh_p50']:8.1f} {r['zmedh_p50'] / b['zmedh_p50']:7.2f} "
                  f"{'yes' if sig_h else 'no':>5s} {r['zmed_p50']:8.0f} "
                  f"{r['zmed_p50'] / b['zmed_p50']:7.2f} {'yes' if sig_u else 'no':>5s}")
    if a.json:
        a.json.write_text(json.dumps([{k: r[k] for k in ("zone", "kind", "race", "h", "nch", "d2d")}
                                      for r in base + rows], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
