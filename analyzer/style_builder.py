"""
analyzer/style_builder.py
-------------------------
Build style profile JSON files by analyzing a corpus of existing EQ zones.

Run this once against your EQ install to populate the styles/ directory.
Those profiles are then used by the AI generator to keep output in-bounds.

Usage (CLI)::

    python -m analyzer.style_builder --eq-path "C:/EverQuest" --theme dungeon \
        --zones gukbottom solb velketor

This writes styles/dungeon.json (or merges into it if it exists).
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
import io
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from .extractor import ZoneExtractor, ZoneMetrics

# ---------------------------------------------------------------------------
# Default reference zones per theme (shipped as suggestions)
# ---------------------------------------------------------------------------

REFERENCE_ZONES: Dict[str, List[str]] = {
    "dungeon": [
        # Classic–PoP dungeons (the iconic EQ look), read via the WLD reader
        "befallen", "soldunga", "soldungb", "najena", "sebilis",
        "chardok", "velketor", "paw", "guktop", "gukbottom",
    ],
    "outdoor": [
        # Classic–PoP outdoor zones
        "gfaydark", "eastkarana", "northkarana", "oasis", "feerrott",
        "nektulos", "fieldofbone", "burningwood", "eastwastes",
    ],
    "city": [
        # Classic–PoP cities / social hubs
        "qeynos2", "freportw", "felwithea", "rivervale", "cabwest",
        "neriaka",
    ],
    "cave": [
        # Classic–PoP natural caves / organic underground
        "crushbone", "blackburrow", "runnyeye", "cazicthule", "kedge",
        "guktop", "gukbottom", "warrens",
    ],
}


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

class StyleBuilder:
    """
    Analyze a set of zone .eqg files and produce a style profile JSON.

    Usage::

        builder = StyleBuilder(eq_path="C:/EverQuest", output_dir="styles")
        builder.build_theme("dungeon", REFERENCE_ZONES["dungeon"])
    """

    def __init__(self, eq_path: str | Path, output_dir: str | Path = "styles"):
        self.eq_path    = Path(eq_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _find_zone(self, zone_name: str) -> Optional[Path]:
        """
        Locate a zone archive for zone_name. Prefers .eqg (modern), falls back
        to .s3d (Classic–PoP, read via the WLD reader).
        """
        for ext in (".eqg", ".s3d"):
            c = self.eq_path / f"{zone_name}{ext}"
            if c.exists():
                return c
        return None

    def analyze_zone(self, zone_name: str) -> Optional[ZoneMetrics]:
        path = self._find_zone(zone_name)
        if path is None:
            print(f"  [skip] {zone_name} (.eqg/.s3d) not found in {self.eq_path}")
            return None
        print(f"  [analyze] {path.name}")
        try:
            return ZoneExtractor(path).extract()
        except Exception as e:
            print(f"  [error] {zone_name}: {e}")
            return None

    def build_theme(self, theme: str, zone_names: List[str]) -> Dict:
        """
        Analyze all zones, aggregate statistics, write styles/<theme>.json.
        Returns the profile dict.
        """
        print(f"\nBuilding style profile: '{theme}'")
        print(f"Zones: {zone_names}\n")

        metrics_list: List[ZoneMetrics] = []
        for name in zone_names:
            m = self.analyze_zone(name)
            if m is not None and m.vertex_count > 0:
                metrics_list.append(m)

        if not metrics_list:
            print(f"[warning] No valid zones found for theme '{theme}'")
            return {}

        def agg(values: List[float]) -> Dict:
            if not values:
                return {"min": 0, "max": 0, "mean": 0, "std": 0}
            return {
                "min":  round(min(values),    2),
                "max":  round(max(values),    2),
                "mean": round(statistics.mean(values), 2),
                "std":  round(statistics.stdev(values) if len(values) > 1 else 0, 2),
            }

        profile = {
            "theme": theme,
            "zone_count": len(metrics_list),
            "analyzed_zones": [m.zone_name for m in metrics_list],

            "geometry": {
                "width_x":        agg([m.width_x        for m in metrics_list]),
                "width_y":        agg([m.width_y        for m in metrics_list]),
                "ceiling_height": agg([m.ceiling_height for m in metrics_list]),
                "poly_density":   agg([m.poly_density   for m in metrics_list]),
                "floor_area":     agg([m.floor_area     for m in metrics_list]),
            },

            "materials": {
                "count":   agg([m.material_count for m in metrics_list]),
                "shaders": _most_common([s for m in metrics_list for s in m.shader_names]),
            },

            "fidelity": {
                # Median triangle edge length (world units) — the resolution
                # target the generator should match for this theme's era.
                "edge_median": agg([m.edge_median for m in metrics_list if m.edge_median > 0]),
                "edge_mean":   agg([m.edge_mean for m in metrics_list if m.edge_mean > 0]),
            },

            "source_formats": _most_common([m.source_format for m in metrics_list]),

            # Measured texel density and Look_Stats (interesting textures
            # spec Req 2); replaces the old always-1.0 "uv" placeholder.
            "textures": texture_profile(self.eq_path, zone_names) or {},

            "lighting": {
                "count":       agg([m.lights.count            for m in metrics_list]),
                "mean_radius": agg([m.lights.mean_radius       for m in metrics_list if m.lights.count > 0]),
                "density":     agg([m.lights.density_per_sq_unit for m in metrics_list]),
                # Aggregate mean light color
                "mean_color": _mean_light_color(
                    [c for m in metrics_list for c in m.lights.colors]
                ),
            },

            "regions": {
                "type_counts": _aggregate_region_counts(metrics_list),
            },
        }

        out_path = self.output_dir / f"{theme}.json"
        out_path.write_text(json.dumps(profile, indent=2))
        print(f"\nProfile written to {out_path}")
        return profile

    def update_textures(self, theme: str, zone_names: List[str]) -> Dict:
        """Measure only the Texture_Profile and merge it into the existing
        ``styles/<theme>.json`` (dropping the old ``uv`` placeholder), leaving
        every other measured value as it is."""
        out_path = self.output_dir / f"{theme}.json"
        profile = json.loads(out_path.read_text()) if out_path.exists() else {"theme": theme}
        profile.pop("uv", None)
        profile["textures"] = texture_profile(self.eq_path, zone_names) or {}
        out_path.write_bytes((json.dumps(profile, indent=2) + "\n").encode("utf-8"))
        print(f"Texture profile written to {out_path}")
        return profile


# ---------------------------------------------------------------------------
# Texture_Profile (interesting textures spec Requirement 2)
# ---------------------------------------------------------------------------
#
# Texel density per surface: world units per texture repeat along the edges
# of wall (|nz| < 0.3), floor (nz > 0.7) and ceiling (nz < -0.7) triangles,
# pooled over the theme's zones (p25/p50/p75). Look_Stats over every 256x256
# texture in those zones (palette.bmp and other sizes skipped): luminance
# mean and spread, mean saturation and edge energy (mean absolute luminance
# step between neighbouring pixels), each p10/p50/p90. Classic .s3d zones
# are read through the WLD reader (UVs); .eqg zones through the TER reader.
# Values are rounded so a re-run gives the same bytes.

SURFACES = ("wall", "floor", "ceiling")
LOOK_KEYS = ("lum_mean", "lum_std", "saturation", "edge_energy")


def look_stats(rgb: np.ndarray) -> Dict[str, float]:
    """Look_Stats of an (H, W, 3) uint8 image."""
    f = rgb.astype(np.float64) / 255.0
    lum = 0.2126 * f[..., 0] + 0.7152 * f[..., 1] + 0.0722 * f[..., 2]
    mx, mn = f.max(-1), f.min(-1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    edge = (np.abs(np.diff(lum, axis=1)).mean() + np.abs(np.diff(lum, axis=0)).mean()) / 2
    return {"lum_mean": float(lum.mean()), "lum_std": float(lum.std()),
            "saturation": float(sat.mean()), "edge_energy": float(edge)}


def _surface_ratios(P: np.ndarray, T: np.ndarray, tris: np.ndarray) -> Dict[str, np.ndarray]:
    """World units per UV unit along each edge, grouped by the triangle's
    surface. ``P`` (V, 3) positions, ``T`` (V, 2) UVs, ``tris`` (F, 3)."""
    a, b, c = P[tris[:, 0]], P[tris[:, 1]], P[tris[:, 2]]
    n = np.cross(b - a, c - a)
    length = np.linalg.norm(n, axis=1)
    ok = length > 0
    nz = np.zeros(len(tris))
    nz[ok] = n[ok, 2] / length[ok]
    kinds = {"wall": ok & (np.abs(nz) < 0.3), "floor": ok & (nz > 0.7),
             "ceiling": ok & (nz < -0.7)}
    out = {}
    for kind, mask in kinds.items():
        t = tris[mask]
        vals = []
        for i, j in ((0, 1), (1, 2), (2, 0)):
            dw = np.linalg.norm(P[t[:, i]] - P[t[:, j]], axis=1)
            du = np.linalg.norm(T[t[:, i]] - T[t[:, j]], axis=1)
            keep = (du > 1e-4) & (dw > 0.5)
            vals.append(dw[keep] / du[keep])
        out[kind] = np.concatenate(vals) if vals else np.zeros(0)
    return out


def _zone_meshes(archive, zone: str, path: Path) -> Iterable[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """(positions, uvs, triangles) per mesh of a zone, UV-less meshes skipped."""
    if path.suffix.lower() == ".s3d":
        from core.wld import load_wld
        data = archive.get(f"{zone}.wld")
        if data is None:
            return
        for m in load_wld(data).meshes:
            if m.uvs and m.polygons:
                yield (np.asarray(m.vertices, dtype=np.float64),
                       np.asarray(m.uvs, dtype=np.float64),
                       np.asarray([p[:3] for p in m.polygons], dtype=np.int64))
    else:
        from core.ter import TerFile
        for name in archive.list_files():
            if name.lower().endswith(".ter"):
                ter = TerFile.from_bytes(archive.get(name))
                yield (np.array([[v.x, v.y, v.z] for v in ter.vertices]),
                       np.array([[v.u, v.v] for v in ter.vertices]),
                       np.array([[p.v1, p.v2, p.v3] for p in ter.polygons], dtype=np.int64))


def _zone_images(archive) -> Iterable[np.ndarray]:
    from PIL import Image
    for name in sorted(archive.list_files()):
        low = name.lower()
        if not low.endswith((".bmp", ".dds")) or low == "palette.bmp":
            continue
        try:
            img = Image.open(io.BytesIO(archive.get(name))).convert("RGB")
        except Exception:  # noqa: BLE001 — an unreadable image is skipped
            continue
        if img.size == (256, 256):
            yield np.asarray(img)


def _pcts(values: np.ndarray, qs: Tuple[int, ...], names: Tuple[str, ...], nd: int) -> Dict[str, float]:
    p = np.percentile(values, qs)
    return {k: round(float(v), nd) for k, v in zip(names, p)}


def texture_profile(eq_path: str | Path, zones: List[str]) -> Optional[Dict]:
    """The Texture_Profile for *zones* under *eq_path* (``None`` if none of
    them could be read)."""
    from core.pfs import PfsArchive

    eq_path = Path(eq_path)
    ratios: Dict[str, List[np.ndarray]] = {s: [] for s in SURFACES}
    looks: List[Dict[str, float]] = []
    measured: List[str] = []
    for zone in zones:
        path = next((eq_path / f"{zone}{ext}" for ext in (".s3d", ".eqg")
                     if (eq_path / f"{zone}{ext}").exists()), None)
        if path is None:
            continue
        archive = PfsArchive.from_file(path)
        for P, T, tris in _zone_meshes(archive, zone, path):
            for kind, vals in _surface_ratios(P, T, tris).items():
                ratios[kind].append(vals)
        looks.extend(look_stats(img) for img in _zone_images(archive))
        measured.append(zone)
    if not measured or not looks:
        return None

    density = {}
    for kind in SURFACES:
        vals = np.concatenate(ratios[kind]) if ratios[kind] else np.zeros(0)
        if len(vals):
            density[kind] = _pcts(vals, (25, 50, 75), ("p25", "p50", "p75"), 1)
    look = {key: _pcts(np.array([l[key] for l in looks]), (10, 50, 90),
                       ("p10", "p50", "p90"), 3)
            for key in LOOK_KEYS}
    return {"texel_density": density, "look": look,
            "zones": measured, "textures_measured": len(looks)}


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def _most_common(items: List[str], top_n: int = 5) -> List[str]:
    from collections import Counter
    return [item for item, _ in Counter(items).most_common(top_n)]


def _mean_light_color(colors: List[tuple]) -> List[float]:
    if not colors:
        return [1.0, 0.8, 0.5]
    r = statistics.mean(c[0] for c in colors)
    g = statistics.mean(c[1] for c in colors)
    b = statistics.mean(c[2] for c in colors)
    return [round(r, 3), round(g, 3), round(b, 3)]


def _aggregate_region_counts(metrics_list: List[ZoneMetrics]) -> Dict[str, float]:
    from collections import defaultdict
    totals: Dict[str, int] = defaultdict(int)
    for m in metrics_list:
        for prefix, count in m.regions.counts.items():
            totals[prefix] += count
    n = len(metrics_list)
    return {k: round(v / n, 2) for k, v in sorted(totals.items())}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build EQ zone style profiles")
    parser.add_argument("--eq-path",  required=True, help="Path to EQ install directory")
    parser.add_argument("--theme",    default="dungeon", choices=list(REFERENCE_ZONES.keys()))
    parser.add_argument("--zones",    nargs="*", help="Override zone list")
    parser.add_argument("--all",      action="store_true", help="Build all themes")
    parser.add_argument("--output",   default="styles", help="Output directory")
    parser.add_argument("--textures-only", action="store_true",
                        help="Only (re)measure the textures block and merge it in")
    args = parser.parse_args()

    builder = StyleBuilder(eq_path=args.eq_path, output_dir=args.output)
    run = builder.update_textures if args.textures_only else builder.build_theme

    if args.all:
        for theme, zones in REFERENCE_ZONES.items():
            run(theme, zones)
    else:
        zones = args.zones or REFERENCE_ZONES[args.theme]
        run(args.theme, zones)
