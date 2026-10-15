"""
analyzer/extractor.py
---------------------
Extract measurable style metrics from an existing .eqg zone archive.

These metrics are used to build style profiles that constrain the AI generator,
ensuring generated zones stay within the aesthetic bounds of real EQ zones.

Metrics extracted per zone:
  - Bounding box and total floor area
  - Vertex count, polygon count, polygon density
  - Ceiling height (max Z - floor Z)
  - Material count, shader usage
  - Texture filenames and their implied color palettes
  - Light count, light color distribution, light density
  - Region types and counts (water, lava, etc.)
  - UV scale distribution (texture repeat frequency)
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.pfs import PfsArchive
from core.ter import TerFile, MAGIC_TERRAIN, MAGIC_MODEL
from core.zon import ZonFile, ZonLight, ZonRegion
from core.wld import load_wld, WldZone


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class LightStats:
    count: int = 0
    mean_radius: float = 0.0
    colors: List[Tuple[float, float, float]] = field(default_factory=list)
    density_per_sq_unit: float = 0.0   # lights / floor_area


@dataclass
class RegionStats:
    counts: Dict[str, int] = field(default_factory=dict)   # prefix → count
    total: int = 0


@dataclass
class ZoneMetrics:
    """All extracted metrics for a single zone."""
    zone_name: str

    # Geometry
    vertex_count: int = 0
    polygon_count: int = 0
    floor_area: float = 0.0       # XY bounding area in EQ units²
    poly_density: float = 0.0     # polygons per unit²
    bbox_min: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    bbox_max: Tuple[float, float, float] = (0.0, 0.0, 0.0)

    # Dimensions
    width_x: float = 0.0
    width_y: float = 0.0
    ceiling_height: float = 0.0   # max Z extent

    # Materials
    material_count: int = 0
    shader_names: List[str] = field(default_factory=list)
    texture_filenames: List[str] = field(default_factory=list)

    # UV  (median of per-vertex UV magnitude, 99th-pct clipped)
    uv_scale_mean: float = 1.0
    uv_scale_std: float = 0.0

    # Geometric fidelity — median triangle edge length (world units).
    # The key metric for matching an era's resolution.
    edge_median: float = 0.0
    edge_mean: float = 0.0

    # Container format: "eqg" (TER) or "s3d" (WLD)
    source_format: str = "eqg"

    # Lights  (from ZON file — 0 if zone has no ZON)
    lights: LightStats = field(default_factory=LightStats)

    # Regions  (from ZON file — empty if zone has no ZON)
    regions: RegionStats = field(default_factory=RegionStats)

    # Whether a ZON placement file was found
    has_zon: bool = False

    def summary(self) -> str:
        lines = [
            f"Zone: {self.zone_name}",
            f"  Geometry : {self.vertex_count:,} verts, {self.polygon_count:,} polys",
            f"  Bounds   : {self.width_x:.0f} × {self.width_y:.0f} × {self.ceiling_height:.0f} EQ units",
            f"  Area     : {self.floor_area:,.0f} u²  |  density: {self.poly_density:.5f} polys/u²",
            f"  Materials: {self.material_count}  |  textures: {len(self.texture_filenames)}",
            f"  Fidelity : edge median={self.edge_median:.1f}u  mean={self.edge_mean:.1f}u  [{self.source_format}]",
            f"  UV scale : median={self.uv_scale_mean:.2f}  std={self.uv_scale_std:.2f}",
            f"  ZON      : {'yes' if self.has_zon else 'no (embedded placement)'}",
            f"  Lights   : {self.lights.count}  (density: {self.lights.density_per_sq_unit:.2e}/u²)",
            f"  Regions  : {self.regions.counts}",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------

class ZoneExtractor:
    """
    Extract metrics from a .eqg archive.

    Usage::

        metrics = ZoneExtractor("gukbottom.eqg").extract()
        print(metrics.summary())
    """

    def __init__(self, zone_path: str | Path):
        self.path = Path(zone_path)
        self.zone_name = self.path.stem.lower()

    def extract(self) -> ZoneMetrics:
        """Route by container format: .eqg → TER, .s3d → WLD."""
        metrics = ZoneMetrics(zone_name=self.zone_name)
        if self.path.suffix.lower() == ".s3d":
            metrics.source_format = "s3d"
            return self._extract_s3d(metrics)
        metrics.source_format = "eqg"
        return self._extract_eqg(metrics)

    # ------------------------------------------------------------------
    # EQG (.ter / .zon) path
    # ------------------------------------------------------------------

    def _extract_eqg(self, metrics: ZoneMetrics) -> ZoneMetrics:
        arc = PfsArchive.from_file(self.path)

        ter_data = arc.get(f"{self.zone_name}.ter")
        if ter_data is None:
            ter_files = arc.get_by_extension("ter")
            if ter_files:
                ter_data = ter_files[0].data
            else:
                return metrics

        try:
            ter = TerFile.from_bytes(ter_data, name=self.zone_name)
        except Exception as e:
            print(f"[extractor] Could not parse TER for {self.zone_name}: {e}")
            return metrics

        self._extract_geometry(ter, metrics)
        self._extract_materials(ter, metrics)
        self._extract_fidelity_ter(ter, metrics)

        zon_data = arc.get(f"{self.zone_name}.zon")
        if zon_data is None:
            zon_files = arc.get_by_extension("zon")
            if zon_files:
                zon_data = zon_files[0].data

        if zon_data is not None:
            metrics.has_zon = True
            try:
                zon = ZonFile.from_bytes(zon_data)
                self._extract_lights(zon, metrics)
                self._extract_regions(zon, metrics)
            except Exception as e:
                print(f"[extractor] Could not parse ZON for {self.zone_name}: {e}")

        return metrics

    # ------------------------------------------------------------------
    # S3D (.wld) path — Classic–PoP zones
    # ------------------------------------------------------------------

    def _extract_s3d(self, metrics: ZoneMetrics) -> ZoneMetrics:
        arc = PfsArchive.from_file(self.path)

        wld_data = arc.get(f"{self.zone_name}.wld")
        if wld_data is None:
            # Pick the main zone WLD (not lights/objects)
            wlds = [f for f in arc.list_files()
                    if f.lower().endswith(".wld")
                    and f.lower() not in ("lights.wld", "objects.wld")]
            if not wlds:
                return metrics
            wld_data = arc.get(wlds[0])

        try:
            wld = load_wld(wld_data)
        except Exception as e:
            print(f"[extractor] Could not parse WLD for {self.zone_name}: {e}")
            return metrics

        self._extract_geometry_wld(wld, metrics)
        self._extract_materials_wld(wld, metrics)
        self._extract_fidelity_wld(wld, metrics)
        # Classic zones embed lighting/placement in WLD fragments we don't parse;
        # leave lights/regions empty (has_zon stays False), which is accurate.
        return metrics

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_geometry(self, ter: TerFile, metrics: ZoneMetrics) -> None:
        if not ter.vertices:
            return

        xs = [v.x for v in ter.vertices]
        ys = [v.y for v in ter.vertices]
        zs = [v.z for v in ter.vertices]

        bmin = (min(xs), min(ys), min(zs))
        bmax = (max(xs), max(ys), max(zs))

        metrics.bbox_min = bmin
        metrics.bbox_max = bmax
        metrics.width_x = bmax[0] - bmin[0]
        metrics.width_y = bmax[1] - bmin[1]
        metrics.ceiling_height = bmax[2] - bmin[2]
        metrics.floor_area = metrics.width_x * metrics.width_y

        metrics.vertex_count  = len(ter.vertices)
        metrics.polygon_count = len(ter.polygons)
        if metrics.floor_area > 0:
            metrics.poly_density = metrics.polygon_count / metrics.floor_area

        # UV scale: use per-vertex UV magnitude, clipped at 99th percentile to
        # avoid skew from large terrain tiling values (outdoor zones legitimately
        # use U/V values of 50–200+ for texture repetition across large meshes).
        import math
        uv_scales = []
        for v in ter.vertices:
            scale = max(abs(v.u), abs(v.v))
            if scale > 0 and not math.isnan(scale) and not math.isinf(scale):
                uv_scales.append(scale)
        if uv_scales:
            uv_scales.sort()
            # Clip at 99th percentile before computing stats
            p99_idx = int(len(uv_scales) * 0.99)
            clipped = uv_scales[:p99_idx] if p99_idx > 0 else uv_scales
            metrics.uv_scale_mean = statistics.median(clipped)   # median is more robust
            metrics.uv_scale_std  = statistics.stdev(clipped) if len(clipped) > 1 else 0.0

    def _extract_materials(self, ter: TerFile, metrics: ZoneMetrics) -> None:
        metrics.material_count  = len(ter.materials)
        metrics.shader_names    = list({m.shader for m in ter.materials})
        texture_files: List[str] = []
        for mat in ter.materials:
            for prop in mat.properties:
                if prop.type == 2 and prop.value_s.lower().endswith((".dds", ".bmp", ".png")):
                    texture_files.append(prop.value_s)
        metrics.texture_filenames = list(dict.fromkeys(texture_files))  # deduplicate

    def _extract_lights(self, zon: ZonFile, metrics: ZoneMetrics) -> None:
        ls = LightStats()
        ls.count = len(zon.lights)
        if zon.lights:
            ls.colors = [(lt.r, lt.g, lt.b) for lt in zon.lights]
            ls.mean_radius = statistics.mean(lt.radius for lt in zon.lights)
        if metrics.floor_area > 0:
            ls.density_per_sq_unit = ls.count / metrics.floor_area
        metrics.lights = ls

    def _extract_regions(self, zon: ZonFile, metrics: ZoneMetrics) -> None:
        rs = RegionStats()
        for reg in zon.regions:
            # Prefix is the first 3 characters before '_'
            prefix = reg.name.split("_")[0].upper() if "_" in reg.name else reg.name[:3].upper()
            rs.counts[prefix] = rs.counts.get(prefix, 0) + 1
        rs.total = len(zon.regions)
        metrics.regions = rs

    # ------------------------------------------------------------------
    # WLD-specific extraction (Classic–PoP)
    # ------------------------------------------------------------------

    def _extract_geometry_wld(self, wld: WldZone, metrics: ZoneMetrics) -> None:
        if wld.total_vertices == 0:
            return
        all_v = [v for m in wld.meshes for v in m.vertices]
        xs = [v[0] for v in all_v]
        ys = [v[1] for v in all_v]
        zs = [v[2] for v in all_v]
        bmin = (min(xs), min(ys), min(zs))
        bmax = (max(xs), max(ys), max(zs))
        metrics.bbox_min = bmin
        metrics.bbox_max = bmax
        metrics.width_x = bmax[0] - bmin[0]
        metrics.width_y = bmax[1] - bmin[1]
        metrics.ceiling_height = bmax[2] - bmin[2]
        metrics.floor_area = metrics.width_x * metrics.width_y
        metrics.vertex_count = wld.total_vertices
        metrics.polygon_count = wld.total_polygons
        if metrics.floor_area > 0:
            metrics.poly_density = metrics.polygon_count / metrics.floor_area

    def _extract_materials_wld(self, wld: WldZone, metrics: ZoneMetrics) -> None:
        metrics.material_count = len(wld.texture_names)
        metrics.texture_filenames = list(dict.fromkeys(wld.texture_names))
        # Classic WLD has no shader strings (fixed-function pipeline)
        metrics.shader_names = ["<fixed-function>"] if wld.texture_names else []

    # ------------------------------------------------------------------
    # Geometric fidelity (median triangle edge length)
    # ------------------------------------------------------------------

    def _extract_fidelity_ter(self, ter: TerFile, metrics: ZoneMetrics) -> None:
        verts = ter.vertices
        tris = [(verts[p.v1], verts[p.v2], verts[p.v3])
                for p in ter.polygons
                if p.v1 < len(verts) and p.v2 < len(verts) and p.v3 < len(verts)]
        self._edge_stats(
            [((a.x, a.y, a.z), (b.x, b.y, b.z), (c.x, c.y, c.z)) for a, b, c in tris],
            metrics,
        )

    def _extract_fidelity_wld(self, wld: WldZone, metrics: ZoneMetrics) -> None:
        self._edge_stats(wld.all_triangles(), metrics)

    def _edge_stats(self, triangles, metrics: ZoneMetrics) -> None:
        if not triangles:
            return
        # Sample large meshes for speed
        step = max(1, len(triangles) // 15000)
        edges: List[float] = []
        for a, b, c in triangles[::step]:
            edges.append(_dist(a, b))
            edges.append(_dist(b, c))
            edges.append(_dist(c, a))
        if edges:
            metrics.edge_median = statistics.median(edges)
            metrics.edge_mean = statistics.mean(edges)


def _dist(a, b) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)
