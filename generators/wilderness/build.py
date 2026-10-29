"""
generators/wilderness/build.py
------------------------------
The one seam between the wilderness generator and the rest of the build
(wilderness spec task 2).

Everything here is a pure function of ``(seed, edges, biome)``:

    build_matrix -> rewrite_matrix -> synthesize_heightfield -> assemble_bowl

``plan_to_spec`` calls :func:`wilderness_spec` to describe the zone (regions,
materials, Spawn as the safe point); ``TerrainBackend.build`` calls
:func:`build_wilderness_ter` to make the mesh; the pipeline calls
:func:`bowl_report` to gate the built mesh. All three re-derive the same
landscape from the spec's ``wilderness`` payload + seed, so the spec JSON stays
small and the three can never disagree. A small cache makes the repeat calls
free (a full landscape is ~50 ms anyway).

Later tasks extend THIS module, not ``backends.py``. Materials come from the
biome kit (``biome.py`` over ``styles/biomes.json``, task 7).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Mapping, Optional, Tuple

import numpy as np

from analyzer.traverse import AgentModel, RoomResult, TraversalReport
from core.ter import MAGIC_TERRAIN, SHADER_ALPHA, Material, Polygon, TerFile, Vertex
from generators.wilderness.biome import BiomeKit, ground_materials, load_biome_kit
from generators.wilderness.bowl import (
    BowlResult,
    _spawn_world_point,
    assemble_bowl,
    check_bowl,
)
from generators.wilderness.matrix import (
    DEFAULT_SIDES,
    EDGE_TYPES,
    DesignMatrix,
    EdgeConnection,
    build_matrix,
)
from generators.wilderness.rewrite import rewrite_matrix
from generators.wilderness.synth import SynthResult, synthesize_heightfield
from generators.wilderness.water import (
    WATER_SURFACE_MATERIAL,
    add_water_surface,
    sink_water_bed,
    water_quad_mask,
    water_regions,
)
from generators.zone_spec import MaterialSpec, ZoneSpec

DEFAULT_BIOME = "plains"

# ---------------------------------------------------------------------------
# Edge declarations
# ---------------------------------------------------------------------------

def normalise_edges(edges: Optional[Mapping[str, str]]) -> Dict[str, str]:
    """Validate a ``{side: edge_type}`` declaration and fill the four sides.

    Sides are N/E/S/W (case-insensitive); types are mountain/river/zoneline.
    An undeclared side is ``mountain`` (Req 3.3). Raises ``ValueError`` naming
    the bad side or type.
    """
    out = {side: "mountain" for side in DEFAULT_SIDES}
    for side, etype in (edges or {}).items():
        s = str(side).strip().upper()
        t = str(etype).strip().lower()
        if s not in out:
            raise ValueError(f"unknown edge side {side!r}; expected one of N, E, S, W")
        if t not in EDGE_TYPES:
            raise ValueError(
                f"unknown edge type {etype!r} for side {s}; "
                f"expected one of {', '.join(sorted(EDGE_TYPES))}"
            )
        out[s] = t
    return out


def parse_edges(text: str) -> Dict[str, str]:
    """``"N=zoneline,E=river"`` -> normalised four-side declaration."""
    pairs: Dict[str, str] = {}
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        side, sep, etype = part.partition("=")
        if not sep:
            raise ValueError(f"bad edge {part!r}; expected SIDE=TYPE, e.g. N=zoneline")
        pairs[side] = etype
    return normalise_edges(pairs)


# ---------------------------------------------------------------------------
# The landscape
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Landscape:
    """One synthesized wilderness: the rewritten matrix, the heightfield and
    the assembled bowl. Shared between callers via the cache — don't mutate."""

    matrix: DesignMatrix
    synth: SynthResult
    bowl: BowlResult


@lru_cache(maxsize=8)
def _landscape(seed: int, edges: Tuple[Tuple[str, str], ...], biome: str) -> Landscape:
    ecs = [EdgeConnection(side=s, edge_type=t) for s, t in edges]
    matrix = rewrite_matrix(build_matrix(biome, ecs, seed)).matrix
    synth = synthesize_heightfield(matrix, seed=seed)
    return Landscape(matrix=matrix, synth=synth, bowl=assemble_bowl(synth, matrix))


def synthesize_landscape(seed: int, edges: Optional[Mapping[str, str]] = None,
                         biome: str = DEFAULT_BIOME) -> Landscape:
    """Deterministic landscape for ``(seed, edges, biome)``."""
    norm = normalise_edges(edges)
    return _landscape(int(seed) & 0x7FFFFFFF,
                      tuple((s, norm[s]) for s in DEFAULT_SIDES), biome)


def landscape_for(spec: ZoneSpec) -> Landscape:
    """The landscape a wilderness spec describes."""
    if spec.wilderness is None:
        raise ValueError(f"spec {spec.name!r} carries no wilderness payload")
    if spec.seed is None:
        raise ValueError(f"wilderness spec {spec.name!r} has no seed")
    return synthesize_landscape(spec.seed, spec.wilderness.get("edges"),
                                spec.wilderness.get("biome", DEFAULT_BIOME))


def _quad_materials(land: Landscape, kit: BiomeKit) -> np.ndarray:
    """Per fine quad, the TER material name its two triangles use (task 7:
    from the biome kit, by region kind, slope, height and moisture)."""
    return ground_materials(kit, land.synth.node_type, land.bowl.heights,
                            land.synth.resolution)


def _wet_quads(land: Landscape, kit: BiomeKit) -> np.ndarray:
    """Quads that get the visual water plane: none if the kit has no water."""
    wet = water_quad_mask(land.synth.node_type)
    return wet if kit.water else np.zeros_like(wet)


# ---------------------------------------------------------------------------
# Spec, mesh and gate
# ---------------------------------------------------------------------------

def wilderness_spec(name: str, seed: int, edges: Optional[Mapping[str, str]] = None,
                    biome: str = DEFAULT_BIOME) -> ZoneSpec:
    """A ``ZoneSpec`` for an open wilderness: no rooms, the bowl's regions,
    one material per region kind present, Spawn as the safe point."""
    norm = normalise_edges(edges)
    land = synthesize_landscape(seed, norm, biome)
    kit = load_biome_kit(biome)
    spec = ZoneSpec(name=name, zone_type="wilderness", style_profile="outdoor",
                    seed=seed, wilderness={"biome": biome, "edges": norm})
    spec.ambient_light = kit.ambient_light
    kit_mats = kit.materials()
    for mat_name in sorted(set(_quad_materials(land, kit).ravel())):
        m = kit_mats[mat_name]
        spec.materials[mat_name] = MaterialSpec(
            name=mat_name, texture=f"{mat_name}.dds", color=m.color,
            description=m.description)
    spec.regions = list(land.bowl.regions)
    spec.water_level = float(land.matrix.water_level)
    if _wet_quads(land, kit).any():
        # Task 6: the visual water plane gets its own (alpha) material and an
        # AWT region per water body — only where the kit declares water (11.4).
        m = kit_mats[WATER_SURFACE_MATERIAL]
        spec.materials[WATER_SURFACE_MATERIAL] = MaterialSpec(
            name=WATER_SURFACE_MATERIAL, texture=f"{WATER_SURFACE_MATERIAL}.dds",
            shader=SHADER_ALPHA, color=m.color, description=m.description)
        spec.regions += water_regions(land.synth.node_type, land.synth.origin,
                                      land.synth.resolution, spec.water_level)
    spec.safe_point = _spawn_world_point(land.synth, land.matrix, land.bowl.heights)
    return spec


def build_wilderness_ter(spec: ZoneSpec, ter_name: str, ter_version: int) -> TerFile:
    """Triangulate the spec's bowl heightfield into a TER, materials from the
    biome kit. Same vertex frame and triangulation as ``build_bowl_ter`` (so
    the bowl gate's bands and Spawn line up), vectorised. Water quads also get
    a flat, passable surface at the water level (task 6, see ``water.py``)."""
    land = landscape_for(spec)
    kit = load_biome_kit(spec.wilderness.get("biome", DEFAULT_BIOME))
    res = float(land.synth.resolution)
    ox, oy = land.synth.origin
    water_level = float(land.matrix.water_level)
    wet = _wet_quads(land, kit)
    h = sink_water_bed(np.asarray(land.bowl.heights, dtype=np.float64), wet, water_level)
    nx, ny = h.shape

    ter = TerFile(name=ter_name, magic=MAGIC_TERRAIN, version=ter_version)
    quad_mat = _quad_materials(land, kit)
    names = sorted(set(quad_mat.ravel()) | ({WATER_SURFACE_MATERIAL} if wet.any() else set()))
    index = {n: i for i, n in enumerate(names)}
    for n in names:
        shader = spec.materials[n].shader if n in spec.materials else "Opaque_MaxCB1.fx"
        mat = Material(index=index[n], name=n, shader=shader)
        tex = spec.materials[n].texture if n in spec.materials else f"{n}.dds"
        mat.add_diffuse(tex)
        ter.materials.append(mat)

    # Vertices: cell-centre XY (the bowl's frame), gradient normals.
    gx, gy = np.gradient(h, res)
    nlen = np.sqrt(gx ** 2 + gy ** 2 + 1.0)
    ii, jj = np.meshgrid(np.arange(nx), np.arange(ny), indexing="ij")
    xs = (ox + (ii + 0.5) * res).ravel().tolist()
    ys = (oy + (jj + 0.5) * res).ravel().tolist()
    zs = h.ravel().tolist()
    nxs = (-gx / nlen).ravel().tolist()
    nys = (-gy / nlen).ravel().tolist()
    nzs = (1.0 / nlen).ravel().tolist()
    # Planar UVs, one texture repeat per 128 u.
    us = [x / 128.0 for x in xs]
    vs = [y / 128.0 for y in ys]
    ter.vertices = [Vertex(x=x, y=y, z=z, nx=a, ny=b, nz=c, u=u, v=v)
                    for x, y, z, a, b, c, u, v
                    in zip(xs, ys, zs, nxs, nys, nzs, us, vs)]

    # Two CCW (from +Z) triangles per quad, material from the biome kit.
    qi, qj = np.meshgrid(np.arange(nx - 1), np.arange(ny - 1), indexing="ij")
    a = (qi * ny + qj).ravel()
    b = ((qi + 1) * ny + qj).ravel()
    c = ((qi + 1) * ny + qj + 1).ravel()
    d = (qi * ny + qj + 1).ravel()
    mats = [index[m] for m in quad_mat.ravel()]
    polys = []
    for va, vb, vc, vd, m in zip(a.tolist(), b.tolist(), c.tolist(), d.tolist(), mats):
        polys.append(Polygon(va, vb, vc, material=m, flags=0))
        polys.append(Polygon(va, vc, vd, material=m, flags=0))
    ter.polygons = polys
    if wet.any():
        add_water_surface(ter, wet, (ox, oy), res, water_level,
                          material=index[WATER_SURFACE_MATERIAL])
    return ter


def bowl_report(spec: ZoneSpec, ter: TerFile,
                agent: Optional[AgentModel] = None) -> TraversalReport:
    """Run the bowl gate on a built wilderness TER, phrased as a
    ``TraversalReport`` so the pipeline's retry, logging and CLI output work
    unchanged: the whole bowl is one "room" that passes or fails."""
    agent = agent or AgentModel()
    land = landscape_for(spec)
    res = check_bowl(land.bowl, land.synth, land.matrix, agent=agent, ter=ter)
    problems = [str(x) for x in (*res.leaks, *res.zoneline_failures)]
    if res.unreachable:
        problems.append(f"{len(res.unreachable)} playable cell(s) unreachable "
                        f"from Spawn, e.g. {res.unreachable[0].region}")
    problems.extend(res.notes if not res.passed else [])
    room = RoomResult(room_id="bowl", role="bowl", reachable=res.passed,
                      floor_faces=res.playable_faces,
                      reached_faces=res.reachable_faces,
                      reason="; ".join(problems))
    return TraversalReport(
        zone_name=spec.name, agent=agent, total_rooms=1,
        reachable_rooms=1 if res.passed else 0, rooms=[room],
        total_faces=res.total_faces, standable_faces=res.standable_faces,
        reachable_faces=res.reachable_faces, seed_face=res.seed_face,
        notes=list(res.notes),
    )
