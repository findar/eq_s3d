"""
core/eqg.py
-----------
High-level orchestration: assemble a complete .eqg archive from a TerFile,
ZonFile, texture DDS bytes, and optional model files.

Also provides GLB export for the browser preview viewer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from .pfs import PfsArchive
from .ter import TerFile
from .zon import ZonFile


# ---------------------------------------------------------------------------
# EQG builder
# ---------------------------------------------------------------------------

class EqgZone:
    """
    Assembles and writes a complete EQG zone archive.

    Usage::

        zone = EqgZone("myzone")
        zone.set_terrain(ter_file)
        zone.set_placement(zon_file)
        zone.add_texture("stone_wall_01.dds", dds_bytes)
        zone.write("output/myzone.eqg")
    """

    def __init__(self, zone_name: str):
        self.zone_name = zone_name.lower()
        self._terrain:   Optional[TerFile] = None
        self._placement: Optional[ZonFile] = None
        self._textures:  Dict[str, bytes]  = {}
        self._models:    Dict[str, bytes]  = {}   # name → raw TER/MOD bytes

    # ------------------------------------------------------------------
    # Setters
    # ------------------------------------------------------------------

    def set_terrain(self, ter: TerFile) -> "EqgZone":
        self._terrain = ter
        return self

    def set_placement(self, zon: ZonFile) -> "EqgZone":
        self._placement = zon
        return self

    def add_texture(self, filename: str, dds_bytes: bytes) -> "EqgZone":
        self._textures[filename.lower()] = dds_bytes
        return self

    def add_model(self, filename: str, ter_bytes: bytes) -> "EqgZone":
        self._models[filename.lower()] = ter_bytes
        return self

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def build_archive(self) -> PfsArchive:
        """Pack everything into a PfsArchive (without writing to disk)."""
        arc = PfsArchive()

        if self._terrain is not None:
            arc.add(f"{self.zone_name}.ter", self._terrain.to_bytes())

        if self._placement is not None:
            arc.add(f"{self.zone_name}.zon", self._placement.to_bytes())

        for fname, data in self._textures.items():
            arc.add(fname, data)

        for fname, data in self._models.items():
            arc.add(fname, data)

        return arc

    def write(self, path: str | Path) -> Path:
        """Write the .eqg archive to *path*."""
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        self.build_archive().write_file(out_path)
        return out_path

    # ------------------------------------------------------------------
    # GLB export (for browser preview)
    # ------------------------------------------------------------------

    def write_glb(self, path: str | Path) -> Optional[Path]:
        """
        Export the zone terrain as a GLB file for browser preview.

        Requires *trimesh* (pip install trimesh).  Returns None if trimesh
        is not available or there is no terrain data.
        """
        if self._terrain is None:
            return None

        try:
            import numpy as np
            import trimesh
        except ImportError:
            return None

        ter = self._terrain
        if not ter.vertices or not ter.polygons:
            return None

        # Build vertex arrays
        verts = np.array(
            [[v.x, v.y, v.z] for v in ter.vertices], dtype=np.float32
        )
        faces = np.array(
            [[p.v1, p.v2, p.v3] for p in ter.polygons], dtype=np.int32
        )
        normals = np.array(
            [[v.nx, v.ny, v.nz] for v in ter.vertices], dtype=np.float32
        )

        mesh = trimesh.Trimesh(
            vertices=verts,
            faces=faces,
            vertex_normals=normals,
            process=False,
        )

        # Assign a simple material colour per material index for the preview
        # (full texture mapping requires UV unwrap, done separately)
        import colorsys
        n_mats = max(1, len(ter.materials))
        face_colors = np.zeros((len(faces), 4), dtype=np.uint8)
        for i, poly in enumerate(ter.polygons):
            hue = (poly.material % n_mats) / n_mats if poly.material >= 0 else 0
            r, g, b = colorsys.hsv_to_rgb(hue, 0.4, 0.7)
            face_colors[i] = [int(r * 255), int(g * 255), int(b * 255), 255]
        mesh.visual.face_colors = face_colors

        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        mesh.export(str(out_path))
        return out_path

    def __repr__(self) -> str:
        return (
            f"EqgZone({self.zone_name!r}, "
            f"terrain={'yes' if self._terrain else 'no'}, "
            f"textures={len(self._textures)})"
        )
