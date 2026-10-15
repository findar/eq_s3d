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
from core.ter import TerFile
from .zone_spec import ZoneSpec
from .geometry import build_mesh
from .textures import generate_texture

# Region kind → ZON name prefix
_REGION_PREFIX = {
    "water": "AWT", "lava": "ALV", "pvp": "APK",
    "zoneline": "ATP", "ice": "ASL", "generic": "APV",
}

# Themes that use the organic (SDF + marching cubes) geometry backend.
# Others use the box/architectural backend.
_ORGANIC_THEMES = {"cave"}


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

        # 1. Geometry → TER (named ter_<zone> per RoF2 convention).
        #    Route to the organic backend for cave-like themes, box backend otherwise.
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

    # ------------------------------------------------------------------
    # Geometry backend selection
    # ------------------------------------------------------------------

    def _build_geometry(self, name: str, ter_version: int) -> TerFile:
        """Route to the organic (SDF) backend for caves, box backend otherwise."""
        if self.spec.theme in _ORGANIC_THEMES:
            ter = self._build_organic(name, ter_version)
            if ter is not None:
                return ter
            # Fall back to box backend if organic produced nothing
        mesh = build_mesh(self.spec)
        return mesh.to_ter(name=f"ter_{name}", version=ter_version)

    def _build_organic(self, name: str, ter_version: int):
        """
        Convert the ZoneSpec's rooms/corridors into an organic cave:
        rooms → chambers (spheres), corridors → tunnels (capsules).
        """
        from .field.cave import CaveSpec, Chamber, Tunnel, build_cave

        chambers = []
        for room in self.spec.rooms:
            # Chamber radius from the room footprint; centre at mid-height
            radius = 0.5 * min(room.width, room.depth)
            cz = room.floor_z + room.height * 0.5
            chambers.append(Chamber(
                center=(room.center_x, room.center_y, cz),
                radius=max(40.0, radius),
            ))

        tunnels = []
        for cor in self.spec.corridors:
            za = cor.from_z + 0.5 * cor.height
            zb = cor.to_z + 0.5 * cor.height
            tunnels.append(Tunnel(
                a=(cor.from_x, cor.from_y, za),
                b=(cor.to_x, cor.to_y, zb),
                radius=max(20.0, cor.width * 0.5),
            ))

        # Seed the cave noise from the zone name for determinism within a build
        cave = CaveSpec(
            chambers=chambers,
            tunnels=tunnels,
            noise_seed=abs(hash(name)) % (2 ** 31),
            voxel=12.0,
            noise_amplitude=26.0,
            noise_scale=130.0,
        )
        ter = build_cave(cave, name=f"ter_{name}", decimate=0.5)
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
