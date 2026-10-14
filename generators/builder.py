"""
generators/builder.py
---------------------
Orchestrates the full generation pipeline:

    ZoneSpec  →  TER (geometry)  +  ZON (placement)  +  DDS (textures)
              →  .eqg archive  +  .glb preview

This is the single entry point the CLI and (later) the AI agent call.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from core.eqg import EqgZone
from core.zon import ZonFile, ZonLight, ZonRegion
from .zone_spec import ZoneSpec
from .geometry import build_mesh
from .textures import generate_texture

# Region kind → ZON name prefix
_REGION_PREFIX = {
    "water": "AWT", "lava": "ALV", "pvp": "APK",
    "zoneline": "ATP", "ice": "ASL", "generic": "APV",
}


class ZoneBuilder:
    """
    Build a complete zone from a ZoneSpec.

    Usage::

        result = ZoneBuilder(spec).build(output_dir="output")
        print(result.eqg_path, result.glb_path)
    """

    def __init__(self, spec: ZoneSpec):
        self.spec = spec

    def build(self,
              output_dir: str | Path = "output",
              write_glb: bool = True,
              ter_version: int = 2) -> "BuildResult":
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        name = self.spec.name.lower()
        ter_filename = f"ter_{name}.ter"

        # 1. Geometry → TER (named ter_<zone> per RoF2 convention)
        mesh = build_mesh(self.spec)
        ter = mesh.to_ter(name=f"ter_{name}", version=ter_version)

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

        # 4. Textures → DDS
        for mat_name, mat_spec in self.spec.materials.items():
            dds = generate_texture(mat_spec.description, mat_spec.color)
            eqg.add_texture(mat_spec.texture, dds)

        # 5. Pack .eqg
        eqg_path = out_dir / f"{name}.eqg"
        eqg.write(eqg_path)

        # 5. GLB preview
        glb_path = None
        if write_glb:
            glb_path = out_dir / f"{name}.glb"
            result = eqg.write_glb(glb_path)
            if result is None:
                glb_path = None  # trimesh not available

        return BuildResult(
            spec=self.spec,
            eqg_path=eqg_path,
            glb_path=glb_path,
            vertex_count=len(ter.vertices),
            polygon_count=len(ter.polygons),
            material_count=len(ter.materials),
        )

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
