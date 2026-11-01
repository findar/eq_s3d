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

import zlib
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Mapping, Optional, Tuple

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
    passed = res.passed
    if passed:
        # Trees (step 2, Req 6): the trunks must not cut anything off.
        cut = trees_block(spec, ter, vegetation_for(spec, ter).placement.instances, agent)
        if cut is not None:
            passed = False
            problems.append(f"tree trunks cut off {cut} from Spawn")
    room = RoomResult(room_id="bowl", role="bowl", reachable=passed,
                      floor_faces=res.playable_faces,
                      reached_faces=res.reachable_faces,
                      reason="; ".join(problems))
    return TraversalReport(
        zone_name=spec.name, agent=agent, total_rooms=1,
        reachable_rooms=1 if passed else 0, rooms=[room],
        total_faces=res.total_faces, standable_faces=res.standable_faces,
        reachable_faces=res.reachable_faces, seed_face=res.seed_face,
        notes=list(res.notes),
    )


# ---------------------------------------------------------------------------
# Trees (roadmap step 2, spec zone-generator-wilderness-trees)
# ---------------------------------------------------------------------------

#: The Density_Level when the spec doesn't name one (Req 3.1).
DEFAULT_TREES = "normal"
#: Half the player's width: trunks grow by this much for the walkability check.
PLAYER_HALF_WIDTH = 1.5
#: Raster step of the walkability check (world units).
TREE_CHECK_STEP = 2.0


def _salted_seed(*parts) -> int:
    """A 31-bit seed from ``parts`` (crc32, stable across processes). Trees
    salt their own streams so the terrain's never moves (design Decision 4)."""
    return zlib.crc32("|".join(str(p) for p in parts).encode("utf-8")) & 0x7FFFFFFF


@dataclass(frozen=True)
class Vegetation:
    """Everything the build adds for trees: the placement, one model per
    Species placed (by archive filename), their textures (by filename), the
    sidecar block and any warnings. Shared through the cache; don't mutate."""

    placement: object                  # generators.vegetation.placement.Placement
    models: Mapping[str, TerFile]
    textures: Mapping[str, bytes]
    model_index: Mapping[str, str]     # Species name -> model filename
    report: Mapping[str, object]
    warnings: Tuple[str, ...] = ()


class _TerRef:
    """Carries the TER into the cached function without making it part of the
    key (the heights fingerprint is the key; equal heights give equal trees)."""

    def __init__(self, ter: TerFile):
        self.ter = ter

    def __hash__(self) -> int:
        return 0

    def __eq__(self, other) -> bool:
        return isinstance(other, _TerRef)


def _ter_fingerprint(ter: TerFile) -> int:
    z = np.fromiter((v.z for v in ter.vertices), dtype=np.float64, count=len(ter.vertices))
    return zlib.crc32(z.tobytes())


def vegetation_for(spec: ZoneSpec, ter: TerFile) -> Vegetation:
    """The trees for a wilderness spec and its built TER. Pure; cached on the
    spec's landscape inputs, the Density_Level and the TER's heights, so the
    builder and the bowl gate share one result."""
    payload = spec.wilderness or {}
    edges = normalise_edges(payload.get("edges"))
    return _vegetation(int(spec.seed) & 0x7FFFFFFF,
                       tuple((s, edges[s]) for s in DEFAULT_SIDES),
                       payload.get("biome", DEFAULT_BIOME),
                       payload.get("trees", DEFAULT_TREES),
                       payload.get("trees_source", "default"),
                       (float(spec.safe_point[0]), float(spec.safe_point[1])),
                       _ter_fingerprint(ter), _TerRef(ter))


@lru_cache(maxsize=8)
def _vegetation(seed: int, edges: Tuple[Tuple[str, str], ...], biome: str, level: str,
                source: str, spawn_xy: Tuple[float, float], _fp: int,
                ter_ref: _TerRef) -> Vegetation:
    from generators.vegetation.kit import load_vegetation_kit
    from generators.vegetation.models import model_name, tree_model
    from generators.vegetation.placement import grove_ratio, place_trees
    from generators.vegetation.textures import (
        bark_texture, bark_texture_name, leaf_texture, leaf_texture_name)

    land = _landscape(seed, edges, biome)
    kit_id = load_biome_kit(biome).vegetation_kit
    kit = load_vegetation_kit(kit_id)
    warnings: List[str] = []
    if kit is None:
        warnings.append(f"vegetation_kit_missing:{kit_id}")
    placement = place_trees(land, ter_ref.ter, kit, level,
                            _salted_seed(seed, "vegetation", "placement"),
                            spawn_xy=spawn_xy)

    models: Dict[str, TerFile] = {}
    textures: Dict[str, bytes] = {}
    model_index: Dict[str, str] = {}
    for name in sorted({t.species for t in placement.instances}):
        sp = kit.species[name]
        fname = model_name(sp)
        model_index[name] = fname
        models[fname] = tree_model(sp, _salted_seed(seed, "vegetation", "model", name))
        tex_seed = _salted_seed(seed, "vegetation", "texture", name)
        textures[bark_texture_name(sp)] = bark_texture(sp, tex_seed)
        textures[leaf_texture_name(sp)] = leaf_texture(sp, tex_seed)

    n = len(placement.instances)
    report: Dict[str, object] = {
        "kit": kit_id, "level": level, "level_source": source,
        "counts": {k: placement.counts.get(k, 0) for k in sorted(placement.counts)},
        "total": n,
        "models": sorted(models),
        "grove_ratio": (round(grove_ratio(placement.instances, placement.eligible_area), 3)
                        if n >= 2 else None),
    }
    if placement.capped:
        report["capped"] = {"placed": n, "target": placement.target}
        warnings.append(f"vegetation_capped:{n}/{placement.target}")
    return Vegetation(placement=placement, models=models, textures=textures,
                      model_index=model_index, report=report, warnings=tuple(warnings))


def _reached_faces(spec: ZoneSpec, ter: TerFile, agent: AgentModel):
    """The walk surface and the faces reached from Spawn, flooded exactly as the
    bowl gate floods them (Invisible_Walls honoured)."""
    from analyzer.traverse import _nearest_standable_face, build_walk_surface
    from generators.wilderness.bowl import _flood_excluding, _invisible_wall_faces

    land = landscape_for(spec)
    surf = build_walk_surface(ter, agent)
    spawn = _spawn_world_point(land.synth, land.matrix, land.bowl.heights)
    seed = _nearest_standable_face(surf, np.asarray(spawn, dtype=np.float64),
                                   xy_radius=float(land.synth.resolution) * 8.0)
    if seed is None:
        return surf, set()
    return surf, _flood_excluding(surf, seed, _invisible_wall_faces(surf, land.bowl))


def trees_block(spec: ZoneSpec, ter: TerFile, trees, agent: Optional[AgentModel] = None,
                step: float = TREE_CHECK_STEP) -> Optional[str]:
    """Req 6.1: with every Trunk_Disc grown by the player's half-width removed,
    is every walkable point still connected to Spawn? Returns ``None`` when it
    is, else names a cut-off fine cell.

    The reached faces of the grid TER are rasterised at ``step``; pixels
    connected to Spawn WITHOUT trees must stay connected WITH them (outside the
    grown discs), so raster artefacts can't fail a zone.
    """
    from scipy.ndimage import label

    if not trees:
        return None
    agent = agent or AgentModel()
    land = landscape_for(spec)
    nx, ny = land.synth.heights.shape
    res = float(land.synth.resolution)
    ox, oy = land.synth.origin
    surf, reached = _reached_faces(spec, ter, agent)
    if not reached:
        return None
    on = np.zeros(len(surf.faces), dtype=bool)
    on[list(reached)] = True

    # Pixel centres over the vertex grid, mapped to their grid triangle (quad q
    # holds triangles 2q (a-b-c, fx >= fy) and 2q+1 (a-c-d), as built above).
    x0, y0 = ox + 0.5 * res, oy + 0.5 * res
    xs = x0 + step * (np.arange(int((nx - 1) * res / step)) + 0.5)
    ys = y0 + step * (np.arange(int((ny - 1) * res / step)) + 0.5)
    gx = (xs - x0) / res
    gy = (ys - y0) / res
    qi, fx = np.floor(gx).astype(int), gx - np.floor(gx)
    qj, fy = np.floor(gy).astype(int), gy - np.floor(gy)
    tri = 2 * (qi[:, None] * (ny - 1) + qj[None, :]) + (fx[:, None] < fy[None, :])
    walk = on[tri]

    covered = np.zeros_like(walk)
    for t in trees:
        r = t.radius + PLAYER_HALF_WIDTH
        i0 = max(int((t.x - r - x0) / step) - 1, 0)
        i1 = min(int((t.x + r - x0) / step) + 2, len(xs))
        j0 = max(int((t.y - r - y0) / step) - 1, 0)
        j1 = min(int((t.y + r - y0) / step) + 2, len(ys))
        if i0 >= i1 or j0 >= j1:
            continue
        dx = xs[i0:i1, None] - t.x
        dy = ys[None, j0:j1] - t.y
        covered[i0:i1, j0:j1] |= dx * dx + dy * dy <= r * r

    sx, sy = spec.safe_point[0], spec.safe_point[1]
    si = min(max(int((sx - x0) / step), 0), len(xs) - 1)
    sj = min(max(int((sy - y0) / step), 0), len(ys) - 1)

    def spawn_component(mask):
        labels, _ = label(mask)
        lab = labels[si, sj]
        if lab == 0:  # Spawn's own pixel isn't in the mask: use the nearest one
            ii, jj = np.nonzero(mask)
            if len(ii) == 0:
                return np.zeros_like(mask)
            k = int(np.argmin((ii - si) ** 2 + (jj - sj) ** 2))
            lab = labels[ii[k], jj[k]]
        return labels == lab

    before = spawn_component(walk)
    after = spawn_component(walk & ~covered)
    cut = before & ~covered & ~after
    if not cut.any():
        return None
    ci, cj = (int(v[0]) for v in np.nonzero(cut))
    return f"playable cell ({int((xs[ci] - ox) // res)},{int((ys[cj] - oy) // res)})"

