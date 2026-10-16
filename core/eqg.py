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
        self._pack_terrain: bool = True   # whether set_terrain is also packed
        self._placement: Optional[ZonFile] = None
        self._textures:  Dict[str, bytes]  = {}
        self._models:    Dict[str, bytes]  = {}   # name → raw TER/MOD bytes

    # ------------------------------------------------------------------
    # Setters
    # ------------------------------------------------------------------

    def set_terrain(self, ter: TerFile, pack: bool = True) -> "EqgZone":
        """
        Set the terrain mesh.

        If *pack* is True, the terrain is written to the archive as
        `<zone_name>.ter`. Set pack=False when the terrain has already been
        added via add_model() under a custom filename (e.g. ter_<zone>.ter)
        and you only want this handle for GLB export.
        """
        self._terrain = ter
        self._pack_terrain = pack
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

        if self._terrain is not None and self._pack_terrain:
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

    def write_glb(self, path: str | Path,
                  material_colors: Optional[Dict[int, tuple]] = None,
                  room_pacing: Optional[list] = None,
                  gates: Optional[list] = None,
                  theme: Optional[dict] = None) -> Optional[Path]:
        """
        Export the zone terrain as a GLB file for browser preview.

        *material_colors* optionally maps a material index → (r,g,b) 0-255 so
        the preview reflects the zone's real palette instead of arbitrary hues.
        The GLB does not carry the actual DDS textures (that would need UV
        unwrap + texture packing); per-material base colour is a faithful,
        lightweight stand-in that shows the intended look.

        Requires *trimesh*.  Returns None if trimesh is unavailable or there is
        no terrain data.
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

        # Colour each VERTEX by the base colour of the material its polygons
        # use. If material_colors isn't supplied, fall back to distinct hues so
        # materials are at least distinguishable. Per-vertex colours avoid
        # trimesh's face→vertex conversion (needs scipy).
        import colorsys
        n_mats = max(1, len(ter.materials))
        vertex_colors = np.full((len(verts), 4), 180, dtype=np.uint8)
        vertex_colors[:, 3] = 255
        for poly in ter.polygons:
            mat_idx = poly.material if poly.material >= 0 else 0
            if material_colors and mat_idx in material_colors:
                r, g, b = material_colors[mat_idx]
                rgba = [int(r), int(g), int(b), 255]
            else:
                hue = (mat_idx % n_mats) / n_mats
                r, g, b = colorsys.hsv_to_rgb(hue, 0.45, 0.75)
                rgba = [int(r * 255), int(g * 255), int(b * 255), 255]
            for vi in (poly.v1, poly.v2, poly.v3):
                if 0 <= vi < len(verts):
                    vertex_colors[vi] = rgba
        mesh.visual.vertex_colors = vertex_colors

        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        mesh.export(str(out_path))

        # Emit a companion .zone.json sidecar carrying lights, regions, and
        # metadata so the browser viewer can render overlays. Named
        # <zone>.zone.json next to the GLB.
        self._write_glb_sidecar(out_path, room_pacing, gates, theme)

        return out_path

    def _write_glb_sidecar(self, glb_path: Path, room_pacing: Optional[list] = None,
                           gates: Optional[list] = None,
                           theme: Optional[dict] = None) -> None:
        """Write a <name>.zone.json next to the GLB with lights/regions/metrics."""
        import json

        ter = self._terrain
        zs = [v.z for v in ter.vertices] if ter else [0]
        xs = [v.x for v in ter.vertices] if ter else [0]
        ys = [v.y for v in ter.vertices] if ter else [0]

        data = {
            "name": self.zone_name,
            "bounds": {
                "min": [min(xs), min(ys), min(zs)],
                "max": [max(xs), max(ys), max(zs)],
            },
            "metrics": {
                "vertices": len(ter.vertices) if ter else 0,
                "polygons": len(ter.polygons) if ter else 0,
                "materials": len(ter.materials) if ter else 0,
            },
            "lights": [],
            "regions": [],
            "rooms": room_pacing or [],
            "gates": gates or [],
            "theme": theme or {},
        }

        if self._placement is not None:
            for lt in self._placement.lights:
                data["lights"].append({
                    "name": lt.name,
                    "pos": [lt.x, lt.y, lt.z],
                    "color": [lt.r, lt.g, lt.b],
                    "radius": lt.radius,
                })
            for reg in self._placement.regions:
                # Classify by name prefix
                prefix = reg.name.split("_")[0].upper() if "_" in reg.name else ""
                kind = {
                    "AWT": "water", "ALV": "lava", "APK": "pvp",
                    "ATP": "zoneline", "ASL": "ice", "APV": "generic",
                }.get(prefix, "generic")
                data["regions"].append({
                    "name": reg.name,
                    "kind": kind,
                    "center": [reg.center_x, reg.center_y, reg.center_z],
                    "extent": [reg.extend_x, reg.extend_y, reg.extend_z],
                })

        sidecar = glb_path.with_suffix("")  # strip .glb
        sidecar = sidecar.with_suffix(".zone.json")
        sidecar.write_text(json.dumps(data, indent=2))

    def __repr__(self) -> str:
        return (
            f"EqgZone({self.zone_name!r}, "
            f"terrain={'yes' if self._terrain else 'no'}, "
            f"textures={len(self._textures)})"
        )
