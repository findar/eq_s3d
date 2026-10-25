"""
generators/builder.py
---------------------
Orchestrates the full generation pipeline:

    ZoneSpec  →  TER (geometry)  +  ZON (placement)  +  DDS (textures)
              →  .eqg archive  +  .glb preview

This is the single entry point the CLI and (later) the AI agent call.
"""

from __future__ import annotations

import zlib
from pathlib import Path
from typing import Optional, Tuple

from core.eqg import EqgZone
from core.zon import ZonFile, ZonLight, ZonRegion
from core.ter import TerFile
from .zone_spec import ZoneSpec
from .geometry import build_mesh
from .textures import generate_texture

# Region kind → ZON name prefix
_REGION_PREFIX = {
    "water": "AWT", "lava": "ALV", "pvp": "APK",
    "zoneline": "ATP", "ice": "ASL", "generic": "APV",
}

# Zone types that use the heightfield terrain backend. (The backend registry
# replaces this set in wave 3 task 12.2; the rename just moves the value here.)
_TERRAIN_THEMES = {"wilderness"}


def _stable_seed(*parts) -> int:
    """
    Deterministic 31-bit seed from arbitrary parts.

    Uses zlib.crc32 rather than the builtin hash(): hash() of strings is salted
    per-process (PYTHONHASHSEED), so it is NOT stable across runs. crc32 is, so
    the same inputs always yield the same seed — the guarantee the seed-pinning
    feature depends on.
    """
    s = "|".join(str(p) for p in parts)
    return zlib.crc32(s.encode("utf-8")) & 0x7FFFFFFF


class ZoneBuilder:
    """
    Build a complete zone from a ZoneSpec.

    Usage::

        result = ZoneBuilder(spec).build(output_dir="output")
        print(result.eqg_path, result.glb_path)
    """

    def __init__(self, spec: ZoneSpec):
        self.spec = spec

    def _base_seed(self, name: str) -> int:
        """
        The seed the geometry/texture backends derive from. Prefer the spec's
        recorded seed (so pinning a seed reproduces the exact zone); fall back
        to a stable hash of the name for hand-authored specs that carry none.
        """
        if self.spec.seed is not None:
            return self.spec.seed & 0x7FFFFFFF
        return _stable_seed(name)

    def build(self,
              output_dir: str | Path = "output",
              write_glb: bool = True,
              ter_version: int = 2) -> "BuildResult":
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        name = self.spec.name.lower()
        ter_filename = f"ter_{name}.ter"

        # 1. Geometry → TER (named ter_<zone> per RoF2 convention).
        #    Route to the heightfield terrain backend for wilderness zones, box
        #    backend otherwise.
        ter = self._build_geometry(name, ter_version)

        # 2. Placement → ZON. The terrain is registered as the ZON's first model
        #    (RoF2 convention: ZON model[0] == "TER_<zone>.TER").
        zon = self._build_zon(ter_filename)

        # 3. Assemble archive. Store the terrain under its ter_ filename.
        eqg = EqgZone(name)
        eqg.set_placement(zon)
        # Store TER with the correct ter_ filename
        eqg.add_model(ter_filename, ter.to_bytes())
        # Keep a handle so GLB export can use the geometry (pack=False avoids
        # writing a duplicate <zone>.ter — the model is already added above)
        eqg.set_terrain(ter, pack=False)

        # 4. Textures → DDS (procedural by default; AI provider if a key is set)
        for mat_name, mat_spec in self.spec.materials.items():
            dds = generate_texture(
                mat_spec.description,
                mat_spec.color,
                size=256,
                name=mat_name,
                seed=_stable_seed(self._base_seed(name), mat_name),
            )
            eqg.add_texture(mat_spec.texture, dds)

        # 5. Pack .eqg
        eqg_path = out_dir / f"{name}.eqg"
        eqg.write(eqg_path)

        # 5. GLB preview — pass per-material base colours so the preview shows
        #    the real palette rather than arbitrary hues.
        glb_path = None
        if write_glb:
            glb_path = out_dir / f"{name}.glb"
            mat_colors = self._material_color_map(ter)
            room_pacing = [
                {
                    "id": r.id,
                    "role": r.role,
                    "graph_depth": r.graph_depth,
                    "center": [r.center_x, r.center_y, r.floor_z],
                    # Content / semantic layer (advisory; may be empty).
                    "semantic_type": r.semantic_type,
                    "room_theme": r.room_theme,
                    "district": r.district,
                    "prop_hints": list(r.prop_hints),
                    "encounter_intent": r.encounter_intent,
                    "boss": r.boss,
                }
                for r in self.spec.rooms
            ]
            gates = [
                {
                    "id": g.id,
                    "tier": g.tier,
                    "lock": [g.lock_x, g.lock_y, g.lock_z],
                    "key": [g.key_x, g.key_y, g.key_z],
                    "key_room": g.key_room_id,
                }
                for g in self.spec.gates
            ]
            # Content / semantic layer (field names unchanged — Req 11.6).
            content_meta = {
                "dungeon_theme": self.spec.dungeon_theme,
                "dungeon_race": self.spec.dungeon_race,
                "elemental_tint": self.spec.elemental_tint,
            }
            result = eqg.write_glb(glb_path, material_colors=mat_colors,
                                   room_pacing=room_pacing, gates=gates,
                                   content=content_meta,
                                   zone_type=self.spec.zone_type)
            if result is None:
                glb_path = None  # trimesh not available

            # Top-down schematic map (SVG sidecar) for the UI "Map" view.
            from .mapview import render_map_svg
            map_path = out_dir / f"{name}.map.svg"
            map_path.write_text(render_map_svg(self.spec), encoding="utf-8")

        return BuildResult(
            spec=self.spec,
            eqg_path=eqg_path,
            glb_path=glb_path,
            vertex_count=len(ter.vertices),
            polygon_count=len(ter.polygons),
            material_count=len(ter.materials),
        )

    def _material_color_map(self, ter: TerFile) -> dict:
        """
        Map each TER material index → its spec base colour (r,g,b 0-255), so
        the GLB preview reflects the zone's intended palette. Matches by
        material name; the terrain backend uses a single 'ground' material, so
        fall back to the dominant floor colour.
        """
        colors: dict = {}
        for mat in ter.materials:
            spec_mat = self.spec.materials.get(mat.name)
            if spec_mat is not None:
                colors[mat.index] = spec_mat.color
            else:
                # Terrain single-material meshes: use floor/wall colour
                fallback = (self.spec.materials.get("wall")
                            or self.spec.materials.get("floor"))
                if fallback is not None:
                    colors[mat.index] = fallback.color
        return colors

    # ------------------------------------------------------------------
    # Geometry backend selection
    # ------------------------------------------------------------------

    def _build_geometry(self, name: str, ter_version: int) -> TerFile:
        """Route to the right geometry backend by zone type."""
        if self.spec.zone_type in _TERRAIN_THEMES:
            ter = self._build_terrain(name, ter_version)
            if ter is not None:
                return ter
        # Fall back to the box backend
        mesh = build_mesh(self.spec)
        return mesh.to_ter(name=f"ter_{name}", version=ter_version)

    def _build_terrain(self, name: str, ter_version: int):
        """Generate heightfield terrain spanning the zone's room-graph bounds."""
        from .field.terrain import TerrainSpec, build_terrain

        # Size the terrain to the room footprint plus a generous margin.
        if self.spec.rooms:
            xs = [r.center_x for r in self.spec.rooms]
            ys = [r.center_y for r in self.spec.rooms]
            margin = 600.0
            width = max(1200.0, (max(xs) - min(xs)) + 2 * margin)
            depth = max(1200.0, (max(ys) - min(ys)) + 2 * margin)
        else:
            width = depth = 2000.0

        spec = TerrainSpec(
            width=width,
            depth=depth,
            resolution=50.0,
            seed=self._base_seed(name),
            height_scale=360.0,
            noise_scale=max(500.0, min(width, depth) * 0.4),
            max_walkable_grad=0.85,
        )
        ter = build_terrain(spec, name=f"ter_{name}")
        if ter is not None:
            ter.version = ter_version
        return ter

    def _build_zon(self, ter_filename: str) -> ZonFile:
        zon = ZonFile()

        # The terrain mesh is the ZON's first model (RoF2 convention).
        # Stored uppercase to match how the client references it.
        zon.models.append(ter_filename.upper().replace(".TER", ".TER"))

        for light in self.spec.lights:
            zon.lights.append(ZonLight(
                name=light.id,
                x=light.x, y=light.y, z=light.z,
                r=light.r, g=light.g, b=light.b,
                radius=light.radius,
            ))

        for region in self.spec.regions:
            prefix = _REGION_PREFIX.get(region.kind, "APV")
            zon.regions.append(ZonRegion(
                name=f"{prefix}_{region.id}",
                center_x=region.center_x,
                center_y=region.center_y,
                center_z=region.center_z,
                extend_x=region.extent_x,
                extend_y=region.extent_y,
                extend_z=region.extent_z,
            ))

        return zon


class BuildResult:
    """Summary of a completed build."""

    def __init__(self, spec, eqg_path, glb_path,
                 vertex_count, polygon_count, material_count):
        self.spec = spec
        self.eqg_path = eqg_path
        self.glb_path = glb_path
        self.vertex_count = vertex_count
        self.polygon_count = polygon_count
        self.material_count = material_count

    def summary(self) -> str:
        lines = [
            f"Built zone: {self.spec.name}",
            f"  Rooms:     {len(self.spec.rooms)}",
            f"  Corridors: {len(self.spec.corridors)}",
            f"  Lights:    {len(self.spec.lights)}",
            f"  Regions:   {len(self.spec.regions)}",
            f"  Geometry:  {self.vertex_count} verts, {self.polygon_count} polys, {self.material_count} mats",
            f"  EQG:       {self.eqg_path}",
        ]
        if self.glb_path:
            lines.append(f"  GLB:       {self.glb_path}")
        return "\n".join(lines)
