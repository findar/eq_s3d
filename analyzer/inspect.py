"""
analyzer/inspect.py
-------------------
Rich terminal inspector for EQG zone files.

Prints a detailed breakdown of a zone's metrics alongside its style profile,
so you can validate whether measurements match what you'd expect from
knowing the zone.

Usage::

    python -m analyzer.inspect F:/everquest_rof2/bertoxtemple.eqg
    python -m analyzer.inspect F:/everquest_rof2/bertoxtemple.eqg --theme dungeon
    python -m analyzer.inspect F:/everquest_rof2/broodlands.eqg --compare dreadspire.eqg
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Optional

from .extractor import ZoneExtractor, ZoneMetrics

# ---------------------------------------------------------------------------
# Rich import (fallback to plain text if not installed)
# ---------------------------------------------------------------------------
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.columns import Columns
    from rich import box
    _HAS_RICH = True
except ImportError:
    _HAS_RICH = False


# ---------------------------------------------------------------------------
# Inspector
# ---------------------------------------------------------------------------

class ZoneInspector:
    def __init__(self, eq_path: Optional[str] = None):
        self.eq_path = Path(eq_path) if eq_path else None
        self.console = Console() if _HAS_RICH else None

    def inspect(self, eqg_path: str | Path, theme: Optional[str] = None) -> ZoneMetrics:
        path = Path(eqg_path)
        if not path.exists():
            # Try relative to eq_path
            if self.eq_path:
                path = self.eq_path / eqg_path
        if not path.exists():
            raise FileNotFoundError(f"Cannot find: {eqg_path}")

        metrics = ZoneExtractor(path).extract()
        profile = self._load_profile(theme) if theme else self._guess_profile(metrics)

        if _HAS_RICH:
            self._render_rich(metrics, profile, theme)
        else:
            self._render_plain(metrics, profile)

        return metrics

    def compare(self, path_a: str | Path, path_b: str | Path) -> None:
        """Side-by-side metric comparison of two zones."""
        m_a = ZoneExtractor(Path(path_a)).extract()
        m_b = ZoneExtractor(Path(path_b)).extract()

        if _HAS_RICH:
            self._render_comparison(m_a, m_b)
        else:
            print(m_a.summary())
            print()
            print(m_b.summary())

    # ------------------------------------------------------------------
    # Rich rendering
    # ------------------------------------------------------------------

    def _render_rich(self, m: ZoneMetrics, profile: Optional[dict], theme: Optional[str]) -> None:
        c = self.console

        c.print()
        c.print(f"[bold cyan]⚔  Zone Inspector: [yellow]{m.zone_name}[/yellow][/bold cyan]")
        c.print()

        # --- Geometry table ---
        geo = Table(title="Geometry", box=box.SIMPLE_HEAVY, show_header=True)
        geo.add_column("Metric", style="cyan", width=20)
        geo.add_column("Value", style="white", width=16)
        geo.add_column("Profile range", style="dim", width=22)

        pg = profile.get("geometry", {}) if profile else {}
        geo.add_row("Vertices",     f"{m.vertex_count:,}",     "")
        geo.add_row("Polygons",     f"{m.polygon_count:,}",    "")
        geo.add_row("Width X",      f"{m.width_x:,.0f} u",     _range_str(pg.get("width_x")))
        geo.add_row("Width Y",      f"{m.width_y:,.0f} u",     _range_str(pg.get("width_y")))
        geo.add_row("Ceiling Z",    _flag(m.ceiling_height, pg.get("ceiling_height"), "{:.0f} u"),
                                                                _range_str(pg.get("ceiling_height")))
        geo.add_row("Floor area",   f"{m.floor_area:,.0f} u²", _range_str(pg.get("floor_area")))
        geo.add_row("Poly density", f"{m.poly_density:.5f}/u²", _range_str(pg.get("poly_density")))
        geo.add_row("UV scale med", f"{m.uv_scale_mean:.2f}",  _range_str((profile or {}).get("uv", {}).get("scale")))
        c.print(geo)

        # --- Materials table ---
        mat = Table(title="Materials", box=box.SIMPLE_HEAVY)
        mat.add_column("Metric",  style="cyan",  width=20)
        mat.add_column("Value",   style="white", width=16)
        mat.add_column("Profile", style="dim",   width=22)
        pm = profile.get("materials", {}) if profile else {}
        mat.add_row("Count",   _flag(m.material_count, pm.get("count"), "{:d}"),
                               _range_str(pm.get("count")))
        mat.add_row("Textures", f"{len(m.texture_filenames)}", "")
        for i, sh in enumerate(m.shader_names[:5]):
            mat.add_row(f"Shader {i+1}", _shader_short(sh), "")
        c.print(mat)

        # --- Lights & Regions ---
        lr = Table(title="Lights & Regions", box=box.SIMPLE_HEAVY)
        lr.add_column("Metric",  style="cyan",  width=20)
        lr.add_column("Value",   style="white", width=16)
        lr.add_column("Profile", style="dim",   width=22)
        pl = profile.get("lighting", {}) if profile else {}
        lr.add_row("Has ZON",       "✓" if m.has_zon else "✗ (embedded)", "")
        lr.add_row("Light count",   _flag(m.lights.count, pl.get("count"), "{:d}"),
                                    _range_str(pl.get("count")))
        lr.add_row("Light density", f"{m.lights.density_per_sq_unit:.2e}/u²",
                                    _range_str(pl.get("density")))
        if m.lights.colors:
            r,g,b = [sum(c[i] for c in m.lights.colors)/len(m.lights.colors) for i in range(3)]
            lr.add_row("Mean light RGB", f"({r:.2f},{g:.2f},{b:.2f})", "")
        lr.add_row("Region count",  f"{m.regions.total}", "")
        for rtype, cnt in sorted(m.regions.counts.items()):
            label = _region_label(rtype)
            lr.add_row(f"  {label}", f"{cnt}", "")
        c.print(lr)

        # --- Texture list ---
        if m.texture_filenames:
            tex = Table(title=f"Textures ({len(m.texture_filenames)})", box=box.SIMPLE_HEAVY)
            tex.add_column("#",    style="dim",   width=4)
            tex.add_column("File", style="white", width=45)
            for i, fname in enumerate(m.texture_filenames[:30]):
                tex.add_row(str(i+1), fname)
            if len(m.texture_filenames) > 30:
                tex.add_row("...", f"(+{len(m.texture_filenames)-30} more)")
            c.print(tex)

        # --- Bounding box diagram ---
        c.print(self._bbox_diagram(m))

        # --- Profile info ---
        if profile:
            src = theme or "auto-detected"
            c.print(f"[dim]Style profile: [italic]{src}[/italic] "
                    f"({profile.get('zone_count','?')} reference zones)[/dim]")
        else:
            c.print("[dim]No style profile loaded (run analyzer.style_builder first)[/dim]")
        c.print()

    def _render_comparison(self, a: ZoneMetrics, b: ZoneMetrics) -> None:
        c = self.console
        c.print()
        c.print(f"[bold cyan]Zone Comparison: [yellow]{a.zone_name}[/yellow] vs [yellow]{b.zone_name}[/yellow][/bold cyan]")
        c.print()

        t = Table(box=box.SIMPLE_HEAVY, show_header=True)
        t.add_column("Metric",        style="cyan",   width=20)
        t.add_column(a.zone_name,     style="white",  width=20)
        t.add_column(b.zone_name,     style="green",  width=20)
        t.add_column("Δ",             style="yellow", width=14)

        rows = [
            ("Vertices",    f"{a.vertex_count:,}",          f"{b.vertex_count:,}",
             _delta(a.vertex_count, b.vertex_count)),
            ("Polygons",    f"{a.polygon_count:,}",         f"{b.polygon_count:,}",
             _delta(a.polygon_count, b.polygon_count)),
            ("Width X",     f"{a.width_x:.0f} u",           f"{b.width_x:.0f} u",
             _delta(a.width_x, b.width_x, suffix="u")),
            ("Width Y",     f"{a.width_y:.0f} u",           f"{b.width_y:.0f} u",
             _delta(a.width_y, b.width_y, suffix="u")),
            ("Ceiling Z",   f"{a.ceiling_height:.0f} u",    f"{b.ceiling_height:.0f} u",
             _delta(a.ceiling_height, b.ceiling_height, suffix="u")),
            ("Poly density",f"{a.poly_density:.5f}",        f"{b.poly_density:.5f}",
             _delta(a.poly_density, b.poly_density, pct=True)),
            ("Materials",   f"{a.material_count}",          f"{b.material_count}",
             _delta(a.material_count, b.material_count)),
            ("Lights",      f"{a.lights.count}",            f"{b.lights.count}",
             _delta(a.lights.count, b.lights.count)),
            ("UV scale med",f"{a.uv_scale_mean:.2f}",       f"{b.uv_scale_mean:.2f}",
             _delta(a.uv_scale_mean, b.uv_scale_mean, pct=True)),
        ]
        for row in rows:
            t.add_row(*row)
        c.print(t)
        c.print()

    def _render_plain(self, m: ZoneMetrics, profile: Optional[dict]) -> None:
        print(m.summary())
        if profile:
            print(f"\nStyle profile: {profile.get('theme', '?')} "
                  f"({profile.get('zone_count','?')} reference zones)")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_profile(self, theme: str) -> Optional[dict]:
        candidates = [
            Path(f"styles/{theme}.json"),
            Path(__file__).parent.parent / "styles" / f"{theme}.json",
        ]
        for p in candidates:
            if p.exists():
                return json.loads(p.read_text())
        return None

    def _guess_profile(self, m: ZoneMetrics) -> Optional[dict]:
        """Try to auto-detect theme from shader names."""
        shaders = " ".join(m.shader_names).lower()
        if "terrain" in shaders or "maxterrain" in shaders:
            return self._load_profile("outdoor")
        if m.ceiling_height < 500 and m.material_count < 100:
            return self._load_profile("dungeon")
        if m.ceiling_height > 400:
            return self._load_profile("outdoor")
        return self._load_profile("dungeon")

    def _bbox_diagram(self, m: ZoneMetrics) -> str:
        """Simple ASCII bounding box diagram."""
        w = min(40, max(10, int(m.width_x / 200)))
        h = min(12, max(4,  int(m.width_y / 200)))
        cx = w // 2; cy = h // 2
        lines = []
        for row in range(h):
            line = []
            for col in range(w + 2):
                if row == 0 or row == h - 1:
                    line.append("─" if 0 < col < w + 1 else ("┌" if col == 0 else "┐") if row == 0 else ("└" if col == 0 else "┘"))
                elif col == 0 or col == w + 1:
                    line.append("│")
                elif row == cy and col == cx:
                    line.append("✦")
                else:
                    line.append(" ")
            lines.append("".join(line))
        scale = f"  {m.width_x:.0f}u × {m.width_y:.0f}u × {m.ceiling_height:.0f}u (XYZ)"
        return "\n".join(lines) + "\n" + scale


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _range_str(stat: Optional[dict]) -> str:
    if not stat:
        return ""
    return f"{stat['min']:.1f} – {stat['max']:.1f}  (μ={stat['mean']:.1f})"


def _flag(value: float, stat: Optional[dict], fmt: str = "{:.1f}") -> str:
    """Format value with ✓/⚠ indicator vs. profile range."""
    formatted = fmt.format(value)
    if not stat or not _HAS_RICH:
        return formatted
    lo = stat["min"] * 0.5
    hi = stat["max"] * 1.5
    if lo <= value <= hi:
        return f"[green]{formatted}[/green] ✓"
    return f"[yellow]{formatted}[/yellow] ⚠"


def _shader_short(shader: str) -> str:
    return shader.replace(".fx", "").replace("Opaque_", "").replace("Alpha_", "α/")


def _region_label(prefix: str) -> str:
    labels = {"AWT": "Water", "ALV": "Lava", "APK": "PvP",
              "ATP": "Zoneline", "ASL": "Ice", "APV": "Generic"}
    return labels.get(prefix, prefix)


def _delta(a: float, b: float, suffix: str = "", pct: bool = False) -> str:
    diff = b - a
    if pct and a != 0:
        pct_val = (diff / abs(a)) * 100
        sign = "+" if diff > 0 else ""
        return f"{sign}{pct_val:.1f}%"
    sign = "+" if diff > 0 else ""
    if suffix:
        return f"{sign}{diff:.0f}{suffix}"
    return f"{sign}{diff:.1f}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Inspect an EQG zone file")
    parser.add_argument("eqg",            help="Path to .eqg file")
    parser.add_argument("--eq-path",      help="EQ install directory (for shorthand zone names)")
    parser.add_argument("--theme",        help="Style profile theme to compare against (dungeon/outdoor/city/cave)")
    parser.add_argument("--compare",      help="Second .eqg to compare against")
    args = parser.parse_args()

    inspector = ZoneInspector(eq_path=args.eq_path)

    if args.compare:
        inspector.compare(args.eqg, args.compare)
    else:
        inspector.inspect(args.eqg, theme=args.theme)
