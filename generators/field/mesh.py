"""
generators/field/mesh.py
------------------------
Extract a triangle mesh from a density FieldGrid via marching cubes, and
emit it as a TerFile ready for packaging.

Uses scikit-image's marching_cubes (robust, returns verts + faces + normals).
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np

from core.ter import TerFile, Material, Vertex, Polygon, MAGIC_TERRAIN
from .sdf import FieldGrid


def field_to_ter(grid: FieldGrid,
                 name: str,
                 material_name: str = "cave_rock",
                 texture: str = "cave_rock.dds",
                 shader: str = "Opaque_MaxCB1.fx",
                 uv_scale: float = 0.02,
                 version: int = 2) -> Optional[TerFile]:
    """
    Run marching cubes on the density field and build a TerFile.

    The surface is extracted at density level 0 (rock/air boundary).
    Returns None if the field has no surface (all solid or all air).
    """
    from skimage import measure

    density = grid.density

    # marching_cubes needs the level to be within the data range
    dmin, dmax = float(density.min()), float(density.max())
    if not (dmin < 0.0 < dmax):
        # No surface crossing zero → nothing to extract
        return None

    verts, faces, normals, _ = measure.marching_cubes(
        density, level=0.0, spacing=(grid.voxel, grid.voxel, grid.voxel)
    )

    # marching_cubes returns verts in grid space scaled by spacing; shift to world
    ox, oy, oz = grid.origin
    verts = verts + np.array([ox, oy, oz], dtype=np.float32)

    ter = TerFile(name=name, magic=MAGIC_TERRAIN, version=version)

    mat = Material(index=0, name=material_name, shader=shader)
    mat.add_diffuse(texture)
    ter.materials.append(mat)

    # Planar-ish UVs from world XY (good enough for cave rock; textures tile)
    ter.vertices = [
        Vertex(
            x=float(v[0]), y=float(v[1]), z=float(v[2]),
            nx=float(n[0]), ny=float(n[1]), nz=float(n[2]),
            u=float(v[0]) * uv_scale, v=float(v[1]) * uv_scale,
        )
        for v, n in zip(verts, normals)
    ]

    # marching_cubes winding: faces index into verts. The client wants CCW
    # from the visible side; skimage normals point toward decreasing density
    # (into the air), which is the visible side, so keep the order.
    ter.polygons = [
        Polygon(int(f[0]), int(f[1]), int(f[2]), material=0, flags=0)
        for f in faces
    ]

    return ter


def decimate_ter(ter: TerFile, target_ratio: float = 0.5) -> TerFile:
    """
    Reduce triangle count via trimesh quadric decimation. Marching cubes
    produces dense meshes; decimation keeps the silhouette while cutting polys.

    Returns a new TerFile. If trimesh/decimation is unavailable, returns the
    input unchanged.
    """
    try:
        import trimesh
    except ImportError:
        return ter

    if not ter.vertices or not ter.polygons:
        return ter

    verts = np.array([[v.x, v.y, v.z] for v in ter.vertices], dtype=np.float64)
    faces = np.array([[p.v1, p.v2, p.v3] for p in ter.polygons], dtype=np.int64)
    mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)

    target_faces = max(100, int(len(faces) * target_ratio))
    try:
        # trimesh 5.x uses face_count= and requires fast_simplification.
        reduced = mesh.simplify_quadric_decimation(face_count=target_faces)
    except TypeError:
        # Older trimesh positional API
        try:
            reduced = mesh.simplify_quadric_decimation(target_faces)
        except Exception:
            return ter
    except Exception:
        return ter

    reduced.fix_normals()
    out = TerFile(name=ter.name, magic=ter.magic, version=ter.version)
    out.materials = list(ter.materials)

    vn = reduced.vertex_normals
    uv_scale = 0.02
    out.vertices = [
        Vertex(
            x=float(p[0]), y=float(p[1]), z=float(p[2]),
            nx=float(n[0]), ny=float(n[1]), nz=float(n[2]),
            u=float(p[0]) * uv_scale, v=float(p[1]) * uv_scale,
        )
        for p, n in zip(reduced.vertices, vn)
    ]
    out.polygons = [
        Polygon(int(f[0]), int(f[1]), int(f[2]), material=0, flags=0)
        for f in reduced.faces
    ]
    return out
