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
from typing import Dict, List, Optional

from .extractor import ZoneExtractor, ZoneMetrics

# ---------------------------------------------------------------------------
# Default reference zones per theme (shipped as suggestions)
# ---------------------------------------------------------------------------

REFERENCE_ZONES: Dict[str, List[str]] = {
    "dungeon": [
        "gukbottom", "guk", "solb", "sola", "velketor",
        "sseru", "chardokb", "kaesora", "unrest",
    ],
    "outdoor": [
        "qeytoqrg", "eastkarana", "northkarana", "southkarana",
        "nektulos", "lavastorm", "permafrost",
    ],
    "city": [
        "poknowledge", "qeynos2", "freeportw", "rivervale",
        "felwithea", "kelethin",
    ],
    "cave": [
        "dranikhollows", "veksar", "cabwest", "crystal",
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

    def _find_eqg(self, zone_name: str) -> Optional[Path]:
        """Locate a .eqg file for zone_name inside the EQ directory."""
        candidates = [
            self.eq_path / f"{zone_name}.eqg",
            self.eq_path / "resources" / f"{zone_name}.eqg",
        ]
        for c in candidates:
            if c.exists():
                return c
        # Walk one level deep
        for child in self.eq_path.iterdir():
            candidate = child / f"{zone_name}.eqg"
            if candidate.exists():
                return candidate
        return None

    def analyze_zone(self, zone_name: str) -> Optional[ZoneMetrics]:
        path = self._find_eqg(zone_name)
        if path is None:
            print(f"  [skip] {zone_name}.eqg not found in {self.eq_path}")
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

            "uv": {
                "scale": agg([m.uv_scale_mean for m in metrics_list]),
            },

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
    args = parser.parse_args()

    builder = StyleBuilder(eq_path=args.eq_path, output_dir=args.output)

    if args.all:
        for theme, zones in REFERENCE_ZONES.items():
            builder.build_theme(theme, zones)
    else:
        zones = args.zones or REFERENCE_ZONES[args.theme]
        builder.build_theme(args.theme, zones)
