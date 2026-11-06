r"""Measure what stands inside stock rooms (step 9, task 1).

Uses the zones and floor walk of ``wall_survey``. Per zone and per room:

- **Solids**: connected groups of wall faces standing at least ``INSET`` u inside the
  chamber's edge, at least ``MIN_TALL`` u tall. A group is **free-standing** when it's
  compact (its plan bounding box no more than ``MAX_ASPECT`` to 1, at most ``MAX_SIDE``
  across) and it faces every way, so it surrounds something (a pillar, a block). Anything
  else is a **partition** (an inner wall, a stair's side, a raised floor's edge).
- **Where** free-standing solids stand: distance from the room's middle over its half
  size: ``centre`` under 0.33, ``mid`` under 0.66, ``edge`` beyond.
- **Raised** floor: at least ``RISE`` u over the chamber's median, on at least ``MIN_SHARE``
  of it; its share of the room and median rise.
- **Sunk** floor the same way, below the median. Much of this is a stair or ramp that
  the chamber includes, so it's reported and not used as a bar.
- **Placed objects**: the instance fragments (0x15) of the zone's ``objects.wld``, and how
  many stand in a room. These are not in the zone's mesh: statues, furniture and some
  pillars. Everything else here is mesh-only, so it's a floor on what a room holds.

``measure_rooms`` takes any mesh, so built zones are judged by the same code (task 11).
``--plots DIR`` draws each zone's rooms, free-standing solids in red, partitions in grey.

Usage::

    python scripts/room_feature_survey.py --eq-path F:\everquest_rof2
    python scripts/room_feature_survey.py --eq-path F:\everquest_rof2 --zones befallen \
        --plots %TEMP%\rooms --cache %TEMP%\rooms\cache
"""

from __future__ import annotations

import argparse
import struct
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from analyzer.traverse import AgentModel, build_walk_surface  # noqa: E402
from core.pfs import PfsArchive  # noqa: E402
from core.wld import _decode_string_hash  # noqa: E402
from core.ter import FLAG_PASSABLE  # noqa: E402
from dungeon_topology_survey import CELL, Floor, split  # noqa: E402
from outdoor_dungeon_survey import load_mesh  # noqa: E402
from wall_survey import LEFT_OUT, STYLES, WIDTH, _arrays, stock_faces  # noqa: E402

INSET = 10.0        # a solid stands this far inside the room's edge (u)
MIN_TALL = 4.0      # at least this tall (u)
MIN_SIDE = 2.0      # at least this across (u)
MAX_SIDE = 40.0     # free-standing: at most this across (u)
MAX_ASPECT = 2.5    # and no longer than this to 1
MIN_FACING = 3      # and facing at least this many of the four quarters
MIN_ROOM = 50.0     # rooms under this side are left out (u)
RISE = 2.0          # raised or sunk floor is this far from the median (u)
MIN_SHARE = 0.08    # on at least this share of the room
ABOVE = 30.0        # a wall counts up to this far over the floor it stands on (u)


def _groups(tri, f, n, floor: Floor, chamber: np.ndarray):
    """Connected groups of wall faces inside rooms: [(face indices, room)]."""
    cols = {}
    for k, (i, j) in enumerate(floor.ij):
        cols.setdefault((int(i), int(j)), []).append(k)
    cen = tri.mean(1)
    picked, room_of = [], {}
    for w in np.nonzero(np.abs(n[:, 2]) < 0.7)[0]:
        ci, cj = np.floor(cen[w, :2] / CELL).astype(int)
        for k in cols.get((int(ci), int(cj)), ()):
            if (floor.z[k] - 1 <= cen[w, 2] <= floor.z[k] + ABOVE
                    and floor.dist[k] >= INSET and chamber[k] >= 0):
                picked.append(int(w))
                room_of[int(w)] = int(chamber[k])
                break
    parent = {w: w for w in picked}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    by_vert = {}
    for w in picked:
        for v in f[w]:
            by_vert.setdefault(int(v), []).append(w)
    for faces in by_vert.values():
        for other in faces[1:]:
            parent[find(faces[0])] = find(other)
    out = {}
    for w in picked:
        out.setdefault(find(w), []).append(w)
    return [(faces, room_of[faces[0]]) for faces in out.values()]


def _classify(faces, tri, n):
    """(kind, side, middle): kind is free, partition, or None when it's too small."""
    pts = tri[faces].reshape(-1, 3)
    low, high = pts[:, :2].min(0), pts[:, :2].max(0)
    size = high - low
    side = float(size.max())
    if side < MIN_SIDE or pts[:, 2].max() - pts[:, 2].min() < MIN_TALL:
        return None, side, (low + high) / 2
    facing = {int(a // 90) % 4 for a in np.degrees(np.arctan2(n[faces, 1], n[faces, 0])) % 360}
    aspect = side / max(float(size.min()), 1e-3)
    free = side <= MAX_SIDE and aspect <= MAX_ASPECT and len(facing) >= MIN_FACING
    return ("free" if free else "partition"), side, (low + high) / 2


def measure_rooms(mesh, agent: AgentModel, floors_up: bool = True, faces=None) -> dict:
    """Every measure of one mesh; see the module docstring."""
    if faces is None:
        surf = build_walk_surface(mesh, agent, floors_up=floors_up)
        all_tri = surf.verts[surf.faces]
        up = surf.normals[:, 2] > 0 if floors_up else surf.normals[:, 2] < 0
        floor_tris = all_tri[np.nonzero(surf.standable & up)[0]]
    else:
        floor_tris = faces
    floor = Floor(floor_tris, agent)
    chamber, nch = split(floor, WIDTH)
    tri, f, n, _a = _arrays(mesh)
    rooms = [c for c in range(nch) if (chamber == c).sum() * CELL * CELL >= MIN_ROOM * MIN_ROOM]
    free = {c: [] for c in rooms}
    partitions = {c: 0 for c in rooms}
    sides, where = [], {"centre": 0, "mid": 0, "edge": 0}
    drawn = []
    for faces_, c in _groups(tri, f, n, floor, chamber):
        kind, side, mid = _classify(faces_, tri, n)
        drawn.append((kind, faces_))
        if kind is None or c not in free:
            continue
        if kind == "partition":
            partitions[c] += 1
            continue
        free[c].append(mid)
        sides.append(side)
        xy = floor.xy[chamber == c]
        lo, hi = xy.min(0), xy.max(0)
        r = float(np.max(np.abs(mid - (lo + hi) / 2) / np.maximum((hi - lo) / 2, 1e-3)))
        where["centre" if r < 0.33 else "mid" if r < 0.66 else "edge"] += 1
    raised, shares, rises, sunk = 0, [], [], 0
    for c in rooms:
        z = floor.z[chamber == c]
        delta = z - np.median(z)
        up_, down = delta > RISE, delta < -RISE
        if up_.mean() >= MIN_SHARE:
            raised += 1
            shares.append(float(up_.mean()))
            rises.append(float(np.median(delta[up_])))
        if down.mean() >= MIN_SHARE:
            sunk += 1
    counts = [len(v) for v in free.values() if v]
    total = sum(where.values()) or 1
    return {
        "rooms": len(rooms),
        "with_free": len(counts) / max(len(rooms), 1),
        "free_p50": float(np.median(counts)) if counts else 0.0,
        "free_p90": float(np.percentile(counts, 90)) if counts else 0.0,
        "free_per_room": sum(counts) / max(len(rooms), 1),
        "side_p50": float(np.median(sides)) if sides else 0.0,
        "with_partition": sum(1 for v in partitions.values() if v) / max(len(rooms), 1),
        "where": {k: v / total for k, v in where.items()},
        "raised": raised / max(len(rooms), 1),
        "raised_share": float(np.median(shares)) if shares else 0.0,
        "rise": float(np.median(rises)) if rises else 0.0,
        "sunk": sunk / max(len(rooms), 1),
        "_floor": floor, "_chamber": chamber, "_tri": tri, "_drawn": drawn,
    }


def placed_objects(eq_path: Path, zone: str) -> list:
    """Each instance in the zone's objects.wld as (x, y, z, name): the instance fragment
    (0x15) holds name, object name, flags and a null reference, then x, y, z. The object
    name is a negative offset into the file's XOR-coded string table."""
    data = PfsArchive.from_file(eq_path / f"{zone}.s3d").get("objects.wld")
    if data is None:
        return []
    _magic, _version, count, _bsp, _u1, hash_size, _u2 = struct.unpack_from("<7I", data, 0)
    strings = _decode_string_hash(data[28:28 + hash_size])
    pos = 28 + hash_size
    out = []
    for _ in range(count):
        size, frag = struct.unpack_from("<II", data, pos)
        if frag == 0x15:
            _name, obj, _flags, _ref = struct.unpack_from("<iiIi", data, pos + 8)
            x, y, z = struct.unpack_from("<3f", data, pos + 8 + 16)
            name = ""
            if obj < 0:
                name = strings[-obj:strings.find(b"\0", -obj)].decode("latin1").replace("_ACTORDEF", "")
            out.append((x, y, z, name))
        pos += 8 + size
    return out


def objects_in_rooms(objs, floor: Floor, chamber: np.ndarray) -> float:
    """The share of placed objects standing within a raster cell of a walked room's floor."""
    if not objs:
        return 0.0
    cols = {}
    for k, (i, j) in enumerate(floor.ij):
        cols.setdefault((int(i), int(j)), []).append(k)
    hit = 0
    for x, y, z, _name in objs:
        for k in cols.get((int(x // CELL), int(y // CELL)), ()):
            if chamber[k] >= 0 and abs(floor.z[k] - z) <= 20:
                hit += 1
                break
    return hit / len(objs)


def plot(zone: str, r: dict, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    f = r["_floor"]
    fig, ax = plt.subplots(figsize=(14, 14), dpi=70)
    ax.scatter(f.xy[:, 0], f.xy[:, 1], s=2, marker="s", c="#e4e4e4", linewidths=0)
    for kind, colour, lw in (("partition", "#888888", 0.6), ("free", "tab:red", 1.2)):
        segs = [t[:, :2] for k, faces in r["_drawn"] if k == kind for t in r["_tri"][faces]]
        ax.add_collection(LineCollection(segs, colors=colour, linewidths=lw))
    ax.set_aspect("equal")
    ax.autoscale()
    ax.set_title(f"{zone}: free-standing solids (red), partitions (grey)")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)


def _band(vals) -> str:
    return f"{min(vals):.2f}-{max(vals):.2f}" if vals else "-"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--eq-path", required=True, type=Path)
    ap.add_argument("--zones", default=",".join(STYLES))
    ap.add_argument("--plots", type=Path)
    ap.add_argument("--cache", type=Path)
    args = ap.parse_args(argv)
    agent = AgentModel()
    print(f"{'zone':12} {'style':6} rooms | free: rooms  p50/p90 side | centre/mid/edge | partitions | "
          "raised share rise | sunk | objects in-room")
    rows = {}
    for zone in args.zones.split(","):
        mesh = load_mesh(args.eq_path, zone)
        floor_tris, _ceil = stock_faces(args.eq_path, zone, mesh, agent, args.cache)
        r = measure_rooms(mesh, agent, floors_up=False, faces=floor_tris)
        objs = placed_objects(args.eq_path, zone)
        r["objects"] = len(objs)
        r["in_room"] = objects_in_rooms(objs, r["_floor"], r["_chamber"])
        r["top"] = Counter(o[3] for o in objs).most_common(5)
        rows[zone] = r
        w = r["where"]
        print(f"{zone:12} {STYLES.get(zone, '-'):6} {r['rooms']:5} | {r['with_free']:.2f} "
              f"{r['free_p50']:3.0f}/{r['free_p90']:3.0f} {r['side_p50']:5.1f} | "
              f"{w['centre']:.2f}/{w['mid']:.2f}/{w['edge']:.2f} | {r['with_partition']:.2f} | "
              f"{r['raised']:.2f} {r['raised_share']:.2f} {r['rise']:4.1f} | {r['sunk']:.2f} | "
              f"{r['objects']:5} {r['in_room']:.2f}"
              + (f"  LEFT OUT: {LEFT_OUT[zone]}" if zone in LEFT_OUT else ""), flush=True)
        print("      commonest objects: " + ", ".join(f"{n} {c}" for n, c in r["top"]), flush=True)
        if args.plots:
            plot(zone, r, args.plots / f"{zone}.png")
    print("\nBands (kept zones):")
    for style in ("rough", "hewn", "built"):
        kept = [r for z, r in rows.items() if STYLES.get(z) == style]
        if kept:
            print(f"  {style:6} rooms with free {_band([r['with_free'] for r in kept])}, per room "
                  f"{_band([r['free_per_room'] for r in kept])}, side {_band([r['side_p50'] for r in kept])}, "
                  f"raised {_band([r['raised'] for r in kept])}, raised share "
                  f"{_band([r['raised_share'] for r in kept if r['raised']])}, rise "
                  f"{_band([r['rise'] for r in kept if r['raised']])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
