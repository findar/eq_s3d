r"""Measure race body heights and stock room sizes (step 7, task 16).

Two halves, both printed:

**Races.** Each dungeon race's body height H. Two sources from the client:

- ``racedata.txt`` (the install root): one row per race id; the last two
  fields are the race's default height for male and female, in world units
  (human 6, ogre 9, giant 21, ...). That is the size an NPC of the race has
  when it is spawned at size 0, i.e. at the race's default, and an NPC's
  ``size`` field is in the same units. **H is this default height.**
- The race's character model in a ``*_chr.s3d`` archive (``RACE_MODELS``:
  model code, race id, archive), posed and measured as a check. A model is a
  WLD skeleton (0x10) whose skinned meshes (0x36, in the skeleton's
  attached-mesh block or hung on its bones through 0x2D) keep their vertices
  in bone space: the mesh's vertex pieces (count, bone) bind runs of vertices
  to bones. The rest pose is each bone's own track (0x13 -> 0x12, frame 0):
  a quaternion (x, y, z over w), a shift and a scale, both stored over 256
  (the shift's denominator field is the bone's scale x 256, as LanternExtractor
  reads it; reading it as the shift's divisor breaks the Luclin human, whose
  bones carry scales of 6/256 .. 350/256, into a 14 u by 18 u tangle). The
  bone transforms (T R S) compose down the bone tree and every vertex moves by
  its bone's. The measured mesh is the body and head 0 (``<CODE>`` and
  ``<CODE>HE00``; other heads and armour pieces left out); "native" is its
  posed Z extent, plus the X and Y extents.

  Every humanoid model comes out 6-7 u tall natively whatever its race
  (gnome 6.8, ogre 6.5, frost giant 6.8), so the meshes are authored at one
  scale and the client sizes each race on top. The model can't give H by
  itself; it gives the body's proportions (a dragon's length over its
  height, which the footprint needs). How exactly the client scales a model
  to its race's height isn't in the client files: ``drawn`` assumes the
  native mesh is shown at H (scale = H / native height).

**Rooms.** Stock zones' chambers against the race that lives there
(``ZONE_RACE``). The floor is step 6's walk (``dungeon_topology_survey``:
floor-wound faces on the 4 u layered raster, the largest walked piece),
split into chambers the same way (watershed at necks), with the width
threshold scaled to the race: floor wider than 40 u x H / 6 (step 6 set 40 u
on zones of 6 u races; a giant's or a dragon's passage is wider, and at 40 u
Veeshan's Peak's tunnels read as chambers). A chamber's side is the square root of its floor area. Its height is
the p50, over its floor nodes, of the headroom up to the first ceiling-wound
face above the node (step 7's ``dungeon_vertical_survey`` ceiling columns);
its vault is the p90. Nodes with no ceiling over them (open sky, or the
flat lid outdoor zones put at their top) are left out;
a chamber with under ``MIN_COVER`` of its nodes covered is open and has no
height. Per zone: p10/p50/p90 over the covered chambers, in u and over the
resident race's H. ``EXCLUDED`` names the zones whose chambers don't
separate cleanly (read off ``--plots``); they are printed but left out of
the bands.

``--plots DIR`` draws each model's pose (front and side) to
``DIR/model_<code>.png`` and each zone's chambers (plan coloured by chamber
height over H; side view of floor and ceiling) to ``DIR/<zone>.png``.
``--cache DIR`` keeps each zone's faces (as ``dungeon_vertical_survey``).

Usage::

    python scripts/race_size_survey.py --eq-path F:\everquest_rof2
    python scripts/race_size_survey.py --eq-path F:\everquest_rof2 \
        --plots %TEMP%\race --cache %TEMP%\vert\cache
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from analyzer.traverse import AgentModel  # noqa: E402
from core.pfs import PfsArchive  # noqa: E402
from core.wld import WLD_MAGIC, VERSION_OLD, _decode_string_hash  # noqa: E402
from dungeon_topology_survey import CELL, WIDTH, Floor, split  # noqa: E402
from dungeon_vertical_survey import _column_heights, load_faces  # noqa: E402

# ---------------------------------------------------------------------------
# Races: (model code, EQ race id, archive). The first entry is the race's;
# the others are printed beside it. Race ids are EQ's (racedata.txt's first
# field); the code <-> id pairs are EQ's race list, not read from a file.
# ---------------------------------------------------------------------------

RACE_MODELS = {
    "default":   [("HUM", 1, "globalhum_chr"), ("HUF", 1, "globalhuf_chr")],
    "goblin":    [("GOB", 40, "runnyeye_chr")],
    "froglok":   [("FRG", 26, "gukbottom_chr"), ("FRO", 330, "globalfroglok_chr")],
    "kobold":    [("KOB", 48, "kob_chr")],
    "lizardman": [("LIZ", 51, "liz_chr")],
    "gnoll":     [("GNN", 39, "blackburrow_chr")],
    "sarnak":    [("SRW", 131, "chardok_chr")],
    "troll":     [("TRM", 9, "globaltrm_chr"), ("TRF", 9, "globaltrf_chr")],
    "ogre":      [("OGM", 10, "globalogm_chr"), ("OGF", 10, "globalogf_chr")],
    "giant":     [("FSG", 188, "kael_chr"), ("STG", 189, "kael_chr"),
                  ("GIA", 18, "permafrost_chr")],
    "dragon":    [("DRA", 49, "dra_chr"), ("DR2", 184, "dr2_chr")],
    # Not a dungeon race here: Crushbone's builders, a reference.
    "orc":       [("ORC", 54, "crushbone_chr")],
}

# Zone -> resident race (the builders, where the zone has one).
ZONE_RACE = {
    "befallen": "default",     # a human-built crypt, undead residents
    "crushbone": "orc",        # reference: orcs aren't a dungeon race here
    "blackburrow": "gnoll",
    "runnyeye": "goblin",
    "droga": "goblin",
    "soldunga": "kobold",
    "guktop": "froglok",
    "gukbottom": "froglok",
    "cazicthule": "lizardman",
    "chardok": "sarnak",
    "oggok": "ogre",
    "kael": "giant",
    "soldungb": "dragon",      # Nagafen's lair
    "veeshan": "dragon",       # Veeshan's Peak
    "sleeper": "dragon",
    "skyshrine": "dragon",
}

# Zones whose chambers don't separate cleanly on the plots (finding 8).
EXCLUDED = {
    "crushbone": "outdoor: its sky lid (620 u) sits under a higher face, so the lid "
                 "test misses it and the open valley reads as 100 H rooms",
}

HUMAN_H = 6.0        # the width threshold (40 u) was set on 6 u races' zones
MIN_COVER = 0.5      # a chamber with a ceiling over at least this share of it
LID_TOL = 1.0        # a ceiling this close to the zone's top is its sky lid (u)
MIN_HEAD = 2.0       # a ceiling at least this far over the floor node (u)

FRAG_SKELETON = 0x10
FRAG_TRACKDEF = 0x12
FRAG_TRACK = 0x13
FRAG_MESHREF = 0x2D
FRAG_MESH = 0x36


# ---------------------------------------------------------------------------
# racedata.txt
# ---------------------------------------------------------------------------

def race_heights(eq_path: Path) -> dict:
    """Race id -> (male, female) default height from the client's racedata."""
    out = {}
    f = eq_path / "racedata.txt"
    for line in f.read_text(errors="replace").splitlines():
        parts = [p for p in line.strip().split("^")]
        if parts and parts[-1] == "":
            parts = parts[:-1]
        if len(parts) < 3 or not parts[0].isdigit():
            continue
        try:
            out[int(parts[0])] = (float(parts[-2]), float(parts[-1]))
        except ValueError:
            continue
    return out


# ---------------------------------------------------------------------------
# WLD character models
# ---------------------------------------------------------------------------

class _Wld:
    """Fragment table of a WLD: (id, body start, body end, name), 1-based like
    WLD fragment references."""

    def __init__(self, data: bytes):
        magic, version, count, _b, _u, hsize, _u2 = struct.unpack_from("<7I", data, 0)
        if magic != WLD_MAGIC:
            raise ValueError("not a WLD")
        self.data = data
        self.old = version == VERSION_OLD
        self.hash = _decode_string_hash(data[28:28 + hsize])
        self.frags = [None]
        self.by_name = {}
        pos = 28 + hsize
        for _ in range(count):
            size, fid = struct.unpack_from("<II", data, pos)
            body = pos + 8
            name = self.string(struct.unpack_from("<i", data, body)[0])
            self.frags.append((fid, body, body + size, name))
            if name:
                self.by_name[name] = len(self.frags) - 1
            pos = body + size

    def string(self, ref: int) -> str:
        if ref >= 0 or -ref >= len(self.hash):
            return ""
        end = self.hash.index(b"\0", -ref)
        return self.hash[-ref:end].decode("ascii", "replace")

    def ref(self, r: int):
        """A fragment reference: positive = 1-based index, negative = name."""
        if r > 0:
            return r if r < len(self.frags) else None
        if r < 0:
            return self.by_name.get(self.string(r))
        return None

    def skeleton(self, idx: int):
        """0x10: bones (name, track ref, mesh ref, children) and attached meshes."""
        d = self.data
        pos = self.frags[idx][1] + 4
        flags, nbones, _poly = struct.unpack_from("<iii", d, pos)
        pos += 12
        if flags & 1:
            pos += 12
        if flags & 2:
            pos += 4
        bones = []
        for _ in range(nbones):
            bname, _bflags, track, mesh, nch = struct.unpack_from("<iiiii", d, pos)
            pos += 20
            kids = list(struct.unpack_from(f"<{nch}i", d, pos))
            pos += 4 * nch
            bones.append({"name": self.string(bname), "track": track,
                          "mesh": mesh, "children": kids})
        meshes = []
        if flags & 0x200:
            (n2,) = struct.unpack_from("<i", d, pos)
            pos += 4
            meshes = list(struct.unpack_from(f"<{n2}i", d, pos))
        return bones, meshes

    def bone_rest(self, track_ref: int):
        """0x13 -> 0x12 frame 0 as a 4x4 (T R S), or None."""
        t = self.ref(track_ref)
        if t is None or self.frags[t][0] != FRAG_TRACK:
            return None
        (def_ref,) = struct.unpack_from("<i", self.data, self.frags[t][1] + 4)
        td = self.ref(def_ref)
        if td is None or self.frags[td][0] != FRAG_TRACKDEF:
            return None
        pos = self.frags[td][1] + 4
        _flags, nframes = struct.unpack_from("<ii", self.data, pos)
        if nframes < 1:
            return None
        rd, rx, ry, rz, sx, sy, sz, sd = struct.unpack_from("<8h", self.data, pos + 8)
        q = np.array([rx, ry, rz, rd], float)
        n = np.linalg.norm(q)
        q = q / n if n > 0 else np.array([0.0, 0.0, 0.0, 1.0])
        m = np.eye(4)
        m[:3, :3] = _quat_mat(q) * (sd / 256.0 if sd else 1.0)
        m[:3, 3] = np.array([sx, sy, sz], float) / 256.0
        return m

    def mesh(self, idx: int):
        """0x36 (directly or through a 0x2D): name, vertices, vertex pieces."""
        if idx is None:
            return None
        fid, pos, _end, name = self.frags[idx]
        if fid == FRAG_MESHREF:
            (r,) = struct.unpack_from("<i", self.data, pos + 4)
            return self.mesh(self.ref(r))
        if fid != FRAG_MESH:
            return None
        d = self.data
        p = pos + 4 + 4 + 16
        centre = np.array(struct.unpack_from("<fff", d, p))
        p += 12 + 12 + 4 + 24
        (vc, tc, nc, cc, pc, vpc, _ptc, _vtc, _s9, scale) = struct.unpack_from("<10H", d, p)
        p += 20
        v = np.frombuffer(d, "<i2", vc * 3, p).reshape(-1, 3).astype(float) / (1 << scale)
        p += vc * 6
        p += tc * (4 if self.old else 8) + nc * 3 + cc * 4 + pc * 8
        pieces = (np.frombuffer(d, "<u2", vpc * 2, p).reshape(-1, 2)
                  if vpc else np.zeros((0, 2), int))
        return name, v + centre, pieces


def _quat_mat(q) -> np.ndarray:
    x, y, z, w = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def posed_model(eq_path: Path, code: str, archive: str):
    """The model's rest-pose body vertices (N x 3) and a note on what was
    used. Raises KeyError if the archive has no such model."""
    arc = PfsArchive.from_file(eq_path / f"{archive}.s3d")
    for f in arc.files:
        if not f.name.lower().endswith(".wld"):
            continue
        wld = _Wld(f.data)
        sk = wld.by_name.get(f"{code}_HS_DEF")
        if sk is None:
            continue
        bones, attached = wld.skeleton(sk)
        world = [None] * len(bones)
        missing = 0

        def visit(i, parent):
            nonlocal missing
            m = wld.bone_rest(bones[i]["track"])
            if m is None:
                missing += 1
                m = np.eye(4)
            world[i] = parent @ m
            for c in bones[i]["children"]:
                visit(c, world[i])

        visit(0, np.eye(4))
        refs = list(attached) + [b["mesh"] for b in bones if b["mesh"]]
        meshes = [m for m in (wld.mesh(wld.ref(r)) for r in refs) if m is not None]
        body = {f"{code}_DMSPRITEDEF", f"{code}HE00_DMSPRITEDEF"}
        chosen = [m for m in meshes if m[0] in body] or meshes
        pts = []
        for _name, v, pieces in chosen:
            out, k = v.copy(), 0
            for cnt, bone in pieces:
                if bone < len(world):
                    w = world[bone]
                    out[k:k + cnt] = v[k:k + cnt] @ w[:3, :3].T + w[:3, 3]
                k += cnt
            pts.append(out)
        if not pts:
            raise KeyError(f"{code}: skeleton without meshes in {archive}")
        return np.concatenate(pts), {"meshes": [m[0] for m in chosen],
                                     "bones": len(bones), "no_track": missing}
    raise KeyError(f"{code}_HS_DEF not in {archive}.s3d")


def measure_races(eq_path: Path, plots: Path = None) -> dict:
    """race -> {"H": default height, "rows": per model}."""
    heights = race_heights(eq_path)
    out = {}
    for race, models in RACE_MODELS.items():
        rows = []
        for code, rid, archive in models:
            row = {"code": code, "id": rid, "archive": archive,
                   "racedata": heights.get(rid)}
            try:
                v, note = posed_model(eq_path, code, archive)
            except (KeyError, FileNotFoundError, ValueError, struct.error) as e:
                row["error"] = str(e)
                rows.append(row)
                continue
            ext = v.max(0) - v.min(0)
            row.update(native=float(ext[2]), length=float(max(ext[0], ext[1])),
                       width=float(min(ext[0], ext[1])), note=note)
            if row["racedata"]:
                s = row["racedata"][0] / row["native"]
                row.update(drawn_len=row["length"] * s, drawn_wid=row["width"] * s)
            rows.append(row)
            if plots is not None:
                _plot_model(v, code, plots / f"model_{code}.png")
        first = rows[0]
        H = first["racedata"][0] if first["racedata"] else first.get("native")
        out[race] = {"H": H, "rows": rows}
    return out


def _plot_model(v: np.ndarray, code: str, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out.parent.mkdir(parents=True, exist_ok=True)
    fig, (a, b) = plt.subplots(1, 2, figsize=(9, 5), dpi=70)
    a.scatter(v[:, 0], v[:, 2], s=1)
    a.set_title(f"{code}: X-Z (native u)")
    a.set_aspect("equal")
    b.scatter(v[:, 1], v[:, 2], s=1)
    b.set_title("Y-Z")
    b.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Rooms
# ---------------------------------------------------------------------------

def chamber_heights(floor: Floor, chamber: np.ndarray, nch: int, ceil_cols: dict):
    """Per chamber: side (u), covered share, headroom p50 and p90 (nan if open).

    Outdoor zones close their sky with a flat lid at the top of the zone
    (Crushbone at 620 u, Oggok at 600, Cazic-Thule's yards at 170): a ceiling
    within ``LID_TOL`` of the zone's highest ceiling counts as open sky."""
    tops = [c.max() for c in ceil_cols.values() if len(c)]
    lid = max(tops) - LID_TOL if tops else np.inf
    head = np.full(floor.n, np.nan)
    for k, ((i, j), z) in enumerate(zip(floor.ij, floor.z)):
        cz = ceil_cols.get((int(i), int(j)))
        if cz is None:
            continue
        c = cz[cz > z + MIN_HEAD]
        if len(c) and c[0] < lid:
            head[k] = c[0] - z
    rows = []
    for c in range(nch):
        m = chamber == c
        h = head[m]
        cover = float(np.isfinite(h).mean())
        hh = h[np.isfinite(h)]
        ok = cover >= MIN_COVER and len(hh)
        rows.append({"side": float(np.sqrt(m.sum()) * CELL), "cover": cover,
                     "h50": float(np.median(hh)) if ok else np.nan,
                     "h90": float(np.percentile(hh, 90)) if ok else np.nan})
    return rows, head


def survey_zone(eq_path: Path, zone: str, H: float, agent: AgentModel,
                cache: Path = None, width: float = WIDTH) -> dict:
    floor_tris, ceil_tris, _wet = load_faces(eq_path, zone, agent, cache)
    floor = Floor(floor_tris, agent)
    chamber, nch = split(floor, width)
    rows, head = chamber_heights(floor, chamber, nch, _column_heights(ceil_tris))
    covered = [r for r in rows if np.isfinite(r["h50"])]
    return {"zone": zone, "H": H, "floor": floor, "chamber": chamber, "nch": nch,
            "rows": rows, "covered": covered, "head": head,
            "side": np.array([r["side"] for r in covered]),
            "height": np.array([r["h50"] for r in covered]),
            "vault": np.array([r["h90"] for r in covered]),
            "open": nch - len(covered)}


def plot_zone(r: dict, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    f, ch, H = r["floor"], r["chamber"], r["H"]
    ext = f.xy.max(0) - f.xy.min(0)
    ax_i = int(np.argmax(ext))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(22, 10), dpi=70,
                                 gridspec_kw={"width_ratios": [1, 1.4]})
    hc = np.array([row["h50"] for row in r["rows"]] + [np.nan])
    val = hc[np.where(ch >= 0, ch, len(hc) - 1)] / H
    grey = ~np.isfinite(val)
    a1.scatter(f.xy[grey, 0], f.xy[grey, 1], s=4, marker="s", c="#cccccc", linewidths=0)
    sc = a1.scatter(f.xy[~grey, 0], f.xy[~grey, 1], s=4, marker="s", c=val[~grey],
                    cmap="viridis", linewidths=0)
    fig.colorbar(sc, ax=a1, label="chamber height / H")
    for c in range(r["nch"]):
        m = ch == c
        x, y = f.xy[m].mean(0)
        a1.text(x, y, str(c), fontsize=7, color="red")
    a1.set_aspect("equal")
    a1.set_title(f"{r['zone']}: chambers (grey = passage or open), H = {H:g} u")
    a2.scatter(f.xy[:, ax_i], f.z, s=1, c="#888888", linewidths=0)
    top = np.isfinite(r["head"]) & (ch >= 0)
    a2.scatter(f.xy[top, ax_i], f.z[top] + r["head"][top], s=1, c="tab:red", linewidths=0)
    a2.set_aspect("equal")
    a2.set_xlabel("world " + "XY"[ax_i])
    a2.set_ylabel("height (u)")
    a2.set_title("side view: floor (grey), first ceiling over chamber floor (red); 1:1")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _p(v, qs=(10, 50, 90), fmt="{:.0f}") -> str:
    v = np.asarray(v)
    if v.size == 0:
        return "-"
    return "/".join(fmt.format(np.percentile(v, q)) for q in qs)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--eq-path", required=True, type=Path)
    ap.add_argument("--zones", default=",".join(ZONE_RACE))
    ap.add_argument("--exclude", default=",".join(EXCLUDED),
                    help="zones measured but left out of the bands")
    ap.add_argument("--width", type=float, default=WIDTH,
                    help="chamber width threshold for a 6 u race (u); scaled by H / 6")
    ap.add_argument("--plots", type=Path, help="write model and zone PNGs here")
    ap.add_argument("--cache", type=Path, help="keep each zone's faces here")
    ap.add_argument("--races-only", action="store_true")
    args = ap.parse_args(argv)
    agent = AgentModel()

    races = measure_races(args.eq_path, args.plots)
    print("races: H = racedata.txt default height (male); native = the posed model's "
          "Z extent; drawn length/width = the model's plan extents at H")
    print(f"{'race':10s} {'H':>5s} {'code':4s} {'id':>4s} {'archive':18s} {'racedata m/f':>12s} "
          f"{'native':>6s} {'len':>6s} {'wid':>6s} {'drawn len/wid':>13s}  meshes")
    for race, info in races.items():
        for k, r in enumerate(info["rows"]):
            hcol = f"{info['H']:5.1f}" if k == 0 and info["H"] else "     "
            rd = "%g/%g" % r["racedata"] if r["racedata"] else "-"
            if "error" in r:
                print(f"{race:10s} {hcol} {r['code']:4s} {r['id']:4d} {r['archive']:18s} "
                      f"{rd:>12s}  model NOT FOUND ({r['error']})")
                continue
            dl = (f"{r['drawn_len']:.1f}/{r['drawn_wid']:.1f}" if "drawn_len" in r else "-")
            print(f"{race:10s} {hcol} {r['code']:4s} {r['id']:4d} {r['archive']:18s} {rd:>12s} "
                  f"{r['native']:6.2f} {r['length']:6.2f} {r['width']:6.2f} {dl:>13s}  "
                  f"{', '.join(r['note']['meshes'])}"
                  + (f" ({r['note']['no_track']} bones without a track)"
                     if r["note"]["no_track"] else ""))
    print(f"walk agent player height: {agent.player_height:g} u")
    if args.races_only:
        return 0

    excluded = {z for z in args.exclude.split(",") if z}
    print()
    print(f"rooms: chambers wider than {args.width / HUMAN_H:.2f} H on the walked floor "
          f"({args.width:.0f} u for a 6 u race); height = p50 "
          f"headroom to the first ceiling over the chamber (vault = p90); a chamber with "
          f"< {MIN_COVER:.0%} of it under a ceiling is open; p10/50/90 over the covered chambers")
    print(f"{'zone':12s} {'race':10s} {'H':>5s} {'wid':>4s} {'N':>3s} {'open':>4s} {'height u':>11s} "
          f"{'vault u':>11s} {'side u':>11s} {'height/H':>14s} {'vault/H':>14s} {'side/H':>14s}")
    kept = []
    for zone in [z for z in args.zones.split(",") if z]:
        race = ZONE_RACE.get(zone, "default")
        H = races[race]["H"]
        try:
            r = survey_zone(args.eq_path, zone, H, agent, args.cache,
                            args.width * H / HUMAN_H)
        except Exception as e:  # a zone missing from this install
            print(f"{zone:12s} error: {type(e).__name__}: {e}")
            continue
        if args.plots:
            plot_zone(r, args.plots / f"{zone}.png")
        tag = " (excluded)" if zone in excluded else ""
        print(f"{zone:12s} {race:10s} {H:5.1f} {args.width * H / HUMAN_H:4.0f} {r['nch']:3d} {r['open']:4d} "
              f"{_p(r['height']):>11s} {_p(r['vault']):>11s} {_p(r['side']):>11s} "
              f"{_p(r['height'] / H, fmt='{:.1f}'):>14s} {_p(r['vault'] / H, fmt='{:.1f}'):>14s} "
              f"{_p(r['side'] / H, fmt='{:.1f}'):>14s}{tag}")
        if zone not in excluded and len(r["height"]):
            kept.append(r)
    print()
    for zone in sorted(excluded):
        print(f"excluded {zone}: {EXCLUDED.get(zone, 'by --exclude')}")
    if kept:
        def band(key, q):
            return np.percentile([np.percentile(r[key] / r["H"], q) for r in kept], [10, 90])
        print(f"bands over {len(kept)} zones ({', '.join(r['zone'] for r in kept)}): "
              "the p10-p90 across zones of each zone's percentile, as multiples of H")
        for key in ("height", "vault", "side"):
            lo, mid, hi = band(key, 10), band(key, 50), band(key, 90)
            med = [np.median([np.percentile(r[key] / r["H"], q) for r in kept])
                   for q in (10, 50, 90)]
            print(f"  {key:6s}  zone p10: {lo[0]:5.1f}-{lo[1]:5.1f}   zone p50: {mid[0]:5.1f}-"
                  f"{mid[1]:5.1f}   zone p90: {hi[0]:5.1f}-{hi[1]:5.1f}   "
                  f"(medians {med[0]:.1f} / {med[1]:.1f} / {med[2]:.1f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
