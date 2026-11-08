"""
generators/builder.py
---------------------
Orchestrates the full generation pipeline:

    ZoneSpec  →  TER (geometry)  +  ZON (placement)  +  DDS (textures)
              →  .eqg archive  +  .glb preview

This is the single entry point the CLI and (later) the AI agent call.
"""

from __future__ import annotations

import re
import zlib
from pathlib import Path
from collections import Counter
from typing import Dict, List, Optional, Tuple

from core.eqg import EqgZone
from core.paths import OutputRoot
from core.zon import ZonFile, ZonLight, ZonObject, ZonRegion
from core.ter import TerFile
from .zone_spec import ZoneSpec
from .textures.factory import texture_with_mode
from .backends import backend_for, BoxBackend

# Region kind → ZON name prefix
_REGION_PREFIX = {
    "water": "AWT", "lava": "ALV", "pvp": "APK",
    "zoneline": "ATP", "ice": "ASL", "generic": "APV",
}

# The Build_Name alphabet (umbrella glossary; design "Build_Name artifact
# naming", Req 8.1/8.2). Every artifact a build writes — the ``.eqg`` archive,
# its ``ter_<name>.ter`` / ``<name>.zon`` entries, the ZON model reference, the
# ``.glb``, the ``.zone.json`` Sidecar and the ``.map.svg`` — is named by this
# ONE stem, so a bad name can never reach a file (``ZoneBuilder.build`` checks
# it with ``fullmatch`` and raises ``ValueError`` *before* any write).
BUILD_NAME_RE = re.compile(r"[a-z0-9_]+")


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


_ROOM_SURFACES = ("floor", "wall", "ceiling")


def surface_of(material: str) -> Tuple[str, str, Optional[str]]:
    """``(Texture_Set, Surface, Surface_Class)`` of a material name
    (placeholder textures spec glossary). Room-graph names end in a room
    surface; ``wild_*`` is wilderness ground and ``liquid_*`` a liquid surface;
    anything else (tree bark and leaf) has no Surface_Class."""
    head, _, tail = material.rpartition("_")
    if material in _ROOM_SURFACES:
        return "", material, material
    if tail in _ROOM_SURFACES and head:
        return head, tail, tail
    if head == "wild":
        return head, tail, "ground"
    if head == "liquid":
        return head, tail, "liquid"
    return head, tail, None


def texel_density(theme: str, surface: str) -> float:
    """The theme profile's median world units per texture repeat on a
    surface (interesting textures spec Req 6)."""
    import json
    path = Path(__file__).resolve().parent.parent / "styles" / f"{theme}.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    return float(doc["textures"]["texel_density"][surface]["p50"])


def assign_texel_densities(spec: ZoneSpec) -> None:
    """Set ``texel_density`` on each room-graph surface material that a
    recipe (or the AI provider) will draw: the theme profile's median for its
    surface. Placeholder-mode materials keep 100 u so their labels stay
    readable; wilderness materials and any density already set are left as
    they are (interesting textures spec Req 6)."""
    from .textures.conformance import theme_for
    from .textures.factory import get_provider

    for name, mat in spec.materials.items():
        tex_set, surface, surface_class = surface_of(name)
        if mat.texel_density is not None or surface_class not in _ROOM_SURFACES:
            continue
        provider = get_provider(surface_class=surface_class, name=name)
        if provider.name == "placeholder":
            continue
        mat.texel_density = texel_density(theme_for(tex_set), surface)


def shape_measures(spec: ZoneSpec) -> dict:
    """The built room graph's shape measures (graph-layout Req 7.5; the
    survey's, from ``generators.topology.graph.TopologyGraph``): rooms are
    the spec's rooms, edges its corridors' ``from_room``-``to_room`` pairs,
    the entrance the room whose pacing role is ``entrance`` (else the first).
    Classic and grown builds are measured the same way, so the two compare."""
    from .topology.graph import Node, TopologyGraph

    ids = [r.id for r in spec.rooms]
    entrance = next((r.id for r in spec.rooms if r.role == "entrance"), ids[0])
    graph = TopologyGraph(Node(i, "entrance" if i == entrance else "chamber", "medium")
                          for i in ids)
    for c in spec.corridors:
        a, b = c.from_room, c.to_room
        if a in graph and b in graph and a != b and not graph.has_edge(a, b):
            graph.add_edge(a, b)
    return {
        "dead_end_share": round(graph.dead_end_share(), 4),
        "cycle_rank": graph.cycle_rank(),
        "deep_end": round(graph.deep_end_distance(), 4),
    }


def room_levels(spec: ZoneSpec) -> Dict[str, int]:
    """Each room's Level (room id -> Level): the layout record's ``levels``
    on a stacked graph build, else every room on Level 0."""
    levels = (spec.layout or {}).get("levels") or {}
    return {r.id: int(levels.get(r.id, 0)) for r in spec.rooms}


def connector_record(spec: ZoneSpec) -> Dict[str, dict]:
    """Each corridor as a connector (corridor id -> record): ``kind`` is
    ``bridge`` (``CorridorSpec.bridge`` set; the record's ``over`` names the
    lower room it crosses), ``stair`` (``steps`` != 0 with a rise), ``ramp``
    (a rise, ``steps`` 0) or ``flat``; ``rise`` the floor-height difference
    |to_z - from_z|;
    ``risers`` the stair's risers (a planned stair's from
    ``geometry.stair_layout``, the builder's own plan; a hand-picked count
    as given; 0 for a ramp or flat corridor); ``switchback`` whether the
    stair folds into a Switchback (a cramped planned stair is built
    straight, so it is not one)."""
    from .geometry import stair_layout

    rooms = {r.id: r for r in spec.rooms}
    out: Dict[str, dict] = {}
    for c in spec.corridors:
        rise = abs(c.to_z - c.from_z)
        risers, switchback = 0, False
        if c.bridge:
            kind = "bridge"
        elif rise <= 0.01:
            kind = "flat"
        elif c.steps == 0:
            kind = "ramp"
        else:
            kind = "stair"
            lay = stair_layout(c, rooms) if c.steps < 0 else None
            if lay is not None:
                risers = lay.plan.risers
                switchback = lay.plan.switchback and not lay.cramped
            else:
                risers = max(c.steps, 0)
        out[c.id] = {"kind": kind, "rise": round(rise, 2), "risers": risers,
                     "switchback": switchback}
        if c.bridge:
            out[c.id]["over"] = c.bridge
    return out


def _union_area(rects: List[Tuple[float, float, float, float]]) -> float:
    """Area of the union of axis-aligned rectangles (x0, y0, x1, y1), by
    coordinate compression (exact; the room counts here are small)."""
    rects = [r for r in rects if r[2] > r[0] and r[3] > r[1]]
    if not rects:
        return 0.0
    xs = sorted({v for r in rects for v in (r[0], r[2])})
    area = 0.0
    for xa, xb in zip(xs, xs[1:]):
        spans = sorted((r[1], r[3]) for r in rects if r[0] <= xa and r[2] >= xb)
        cover, top = 0.0, None
        for y0, y1 in spans:
            if top is None or y0 > top:
                cover += y1 - y0
                top = y1
            elif y1 > top:
                cover += y1 - top
                top = y1
        area += cover * (xb - xa)
    return area


def stacked_share(spec: ZoneSpec, levels: Optional[Dict[str, int]] = None) -> float:
    """The Stacked_Share of the spec's rooms: the room floor area that has
    another room's floor above it in plan, over the total room floor area.

    Method: each room's floor is its footprint rectangle; the part of it
    covered by the union of the footprints of rooms on a HIGHER Level is
    stacked (rooms on one Level never overlap in plan, and a room on a
    higher Level stands at least the Slab over it, so Level order is height
    order). Corridors and stairs are left out: they are thin and the share
    is about rooms over rooms. 0.0 with one Level."""
    levels = room_levels(spec) if levels is None else levels
    total = covered = 0.0
    for r in spec.rooms:
        (x0, y0, _), (x1, y1, _) = r.bounds
        total += (x1 - x0) * (y1 - y0)
        above = []
        for o in spec.rooms:
            if levels[o.id] <= levels[r.id]:
                continue
            (a0, b0, _), (a1, b1, _) = o.bounds
            above.append((max(x0, a0), max(y0, b0), min(x1, a1), min(y1, b1)))
        covered += _union_area(above)
    return round(covered / total, 4) if total > 0 else 0.0


def layout_sidecar(spec: ZoneSpec) -> Optional[dict]:
    """The sidecar's ``layout`` block: the engine's record from
    ``spec.layout`` (``{"engine": "classic"}`` for a classic layout) plus
    the built graph's ``shape``. A graph build (``spec.layout`` set) also
    gets ``levels`` (room id -> Level, all 0 when unstacked), ``connectors``
    (``connector_record``) and ``stacked_share``; a classic build leaves
    them out (one Level, no stairs: its block is step 6's). ``None`` for a
    zone with no rooms (wilderness)."""
    if not spec.rooms:
        return None
    block = dict(spec.layout) if spec.layout is not None else {"engine": "classic"}
    block["shape"] = shape_measures(spec)
    if spec.layout is not None:
        levels = room_levels(spec)
        block["levels"] = levels
        block["connectors"] = connector_record(spec)
        block["stacked_share"] = stacked_share(spec, levels)
    return block


def _diffuse_of(mat) -> Optional[str]:
    from core.ter import PROP_DIFFUSE
    return next((p.value_s for p in mat.properties if p.name == PROP_DIFFUSE), None)


def texture_manifest(ter: TerFile, modes: Dict[str, str], veg=None,
                     dds_by_name: Optional[Dict[str, bytes]] = None,
                     sites=None) -> List[dict]:
    """The sidecar's Texture_Manifest (Req 5): one entry per material of the
    TER and of every packed tree and Structure model, sorted by name, with its
    polygon count and the Texture_Mode that drew its texture (``vegetation``
    for the trees' own bark/leaf generator, ``sites`` for the Structures'
    materials). A texture drawn from a recipe also
    records its ``texture_family`` and ``look_stats`` (interesting textures
    spec Req 5.2)."""
    entries: Dict[str, dict] = {}

    def add(mesh: TerFile, mode_for) -> None:
        counts = Counter(p.material for p in mesh.polygons)
        for mat in mesh.materials:
            tex_set, surface, surface_class = surface_of(mat.name)
            e = entries.setdefault(mat.name, {
                "material": mat.name, "texture": _diffuse_of(mat),
                "texture_set": tex_set, "surface": surface,
                "surface_class": surface_class, "polygons": 0,
                "texture_mode": mode_for(mat.name),
            })
            e["polygons"] += counts.get(mat.index, 0)

    add(ter, lambda n: modes.get(n, "procedural"))
    if veg is not None:
        for fname in sorted(veg.models):
            add(veg.models[fname], lambda n: "vegetation")
    if sites is not None:
        for fname in sorted(sites.models):
            add(sites.models[fname], lambda n: "sites")

    if dds_by_name:
        from core.eqg import dds_to_rgb
        from .textures.conformance import look_stats
        from .textures.recipes import resolve
        for name, e in entries.items():
            recipe = resolve(name)
            if e["texture_mode"] == "procedural" and recipe and name in dds_by_name:
                e["texture_family"] = recipe.family
                stats = look_stats(dds_to_rgb(dds_by_name[name]))
                e["look_stats"] = {k: round(v, 4) for k, v in stats.items()}
    return [entries[k] for k in sorted(entries)]


def _vegetation_meshes(veg) -> Optional[list]:
    """The GLB ``vegetation`` mesh (Req 9.1): every tree's model, scaled,
    turned by its yaw and moved to its spot, merged into one mesh coloured by
    its Species' bark (trunk) and leaf (canopy) base colours. ``None`` when
    there are no trees, so the GLB stays the single terrain mesh."""
    if veg is None or not veg.placement.instances:
        return None
    import numpy as np
    from generators.vegetation.kit import load_vegetation_kit

    kit = load_vegetation_kit(veg.report["kit"])
    parts = {}
    for species, fname in veg.model_index.items():
        model = veg.models[fname]
        v = np.array([[p.x, p.y, p.z] for p in model.vertices], dtype=np.float64)
        n = np.array([[p.nx, p.ny, p.nz] for p in model.vertices], dtype=np.float64)
        f = np.array([[q.v1, q.v2, q.v3] for q in model.polygons], dtype=np.int64)
        sp = kit.species[species]
        rgba = {0: (*sp.bark, 255), 1: (*sp.leaf, 255)}
        col = np.full((len(v), 4), 255, dtype=np.uint8)
        for q in model.polygons:
            col[[q.v1, q.v2, q.v3]] = rgba.get(q.material, rgba[0])
        parts[species] = (v, n, f, col)

    verts, norms, faces, cols = [], [], [], []
    base = 0
    for tree in veg.placement.instances:
        v, n, f, col = parts[tree.species]
        c, s = np.cos(tree.yaw), np.sin(tree.yaw)
        rot = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
        verts.append(v @ rot.T * tree.scale + (tree.x, tree.y, tree.z))
        norms.append(n @ rot.T)
        faces.append(f + base)
        cols.append(col)
        base += len(v)
    return [("vegetation", np.vstack(verts), np.vstack(faces), np.vstack(cols),
             np.vstack(norms))]


def _sites_mesh(sites) -> Optional[tuple]:
    """The GLB ``sites`` mesh: every Structure's model turned by its yaw and
    moved to its spot, merged, coloured by its materials' base colours.
    ``None`` when there are no Structures."""
    if sites is None or not sites.structures:
        return None
    import numpy as np
    from generators.textures.sites import BASE_COLOR

    parts = {}
    for fname, model in sites.models.items():
        v = np.array([[p.x, p.y, p.z] for p in model.vertices], dtype=np.float64)
        n = np.array([[p.nx, p.ny, p.nz] for p in model.vertices], dtype=np.float64)
        f = np.array([[q.v1, q.v2, q.v3] for q in model.polygons], dtype=np.int64)
        rgba = {m.index: (*BASE_COLOR.get(m.name[len("site_"):], (128, 128, 128)), 255)
                for m in model.materials}
        col = np.full((len(v), 4), 255, dtype=np.uint8)
        for q in model.polygons:
            col[[q.v1, q.v2, q.v3]] = rgba[q.material]
        parts[fname] = (v, n, f, col)
    verts, norms, faces, cols = [], [], [], []
    base = 0
    for fname, st in sites.structures:
        v, n, f, col = parts[fname]
        c, s = np.cos(st.yaw), np.sin(st.yaw)
        rot = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
        verts.append(v @ rot.T + (st.x, st.y, st.z))
        norms.append(n @ rot.T)
        faces.append(f + base)
        cols.append(col)
        base += len(v)
    return ("sites", np.vstack(verts), np.vstack(faces), np.vstack(cols), np.vstack(norms))


def _extra_meshes(veg, sites) -> Optional[list]:
    """The GLB's meshes beyond the terrain: trees, then Structures."""
    meshes = list(_vegetation_meshes(veg) or [])
    site_mesh = _sites_mesh(sites)
    if site_mesh is not None:
        meshes.append(site_mesh)
    return meshes or None


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
        # Build_Name gate (Req 8.2): validate BEFORE any mkdir / write, so an
        # invalid name produces no partial output. The Build_Name is the one
        # stem every artifact is named by.
        name = self.spec.name.lower()
        if not BUILD_NAME_RE.fullmatch(name):
            raise ValueError(
                f"invalid Build_Name {self.spec.name!r}: must match "
                f"{BUILD_NAME_RE.pattern} (lower-case a-z, 0-9, underscore)"
            )

        # Every write this build performs is routed through an ``OutputRoot``
        # (Req 10.1): a path that resolves outside ``output_dir`` raises
        # ``OutsideOutputError`` and nothing is written. ``out_dir`` is the
        # resolved root; the artifact paths below are built from it so they are
        # inside by construction, but ``EqgZone``/the sidecar/map writers are
        # handed the ``OutputRoot`` so the check is enforced at the write.
        root = OutputRoot(output_dir)
        out_dir = root.mkdir()

        ter_filename = f"ter_{name}.ter"

        # 1. Geometry → TER (named ter_<zone> per RoF2 convention).
        #    Route through the backend registry by zone type. First record
        #    each surface material's texel density in the spec (it decides
        #    the UVs), from the texture mode that will draw it.
        assign_texel_densities(self.spec)
        ter, backend_name, warnings = self._build_geometry(name, ter_version)

        # An outdoor dungeon's layout warnings (rooms_reduced) ride with the
        # build's warnings.
        if self.spec.wilderness is not None and "dungeon" in self.spec.wilderness:
            warnings.extend(self.spec.wilderness["dungeon"]["warnings"])

        # Sites, then trees (wilderness only, steps 10 and 2): layers on top of
        # the built TER, which they never change; trees keep off Site ground.
        # Room-graph zones get neither (Req 10).
        veg = sites = None
        if self.spec.wilderness is not None:
            from generators.wilderness.build import sites_for, vegetation_for
            sites = sites_for(self.spec, ter)
            veg = vegetation_for(self.spec, ter)
            warnings.extend(veg.warnings)

        # 2. Placement → ZON. The terrain is registered as the ZON's first model
        #    (RoF2 convention: ZON model[0] == "TER_<zone>.TER").
        zon = self._build_zon(ter_filename, veg, sites)

        # 3. Assemble archive. Store the terrain under its ter_ filename.
        eqg = EqgZone(name)
        eqg.set_placement(zon)
        # Store TER with the correct ter_ filename
        eqg.add_model(ter_filename, ter.to_bytes())
        # Keep a handle so GLB export can use the geometry (pack=False avoids
        # writing a duplicate <zone>.ter — the model is already added above)
        eqg.set_terrain(ter, pack=False)

        # 4. Textures → DDS. Surfaces are labelled Placeholders by default
        #    (Texture_Mode, placeholder textures spec Req 4); the mode that
        #    drew each one goes in the Texture_Manifest.
        modes: Dict[str, str] = {}
        dds_by_name: Dict[str, bytes] = {}
        for mat_name, mat_spec in self.spec.materials.items():
            dds, modes[mat_name] = texture_with_mode(
                mat_spec.description,
                mat_spec.color,
                size=256,
                name=mat_name,
                seed=_stable_seed(self._base_seed(name), mat_name),
                surface_class=surface_of(mat_name)[2] or "",
            )
            eqg.add_texture(mat_spec.texture, dds)
            dds_by_name[mat_name] = dds

        # Tree models and their bark/leaf textures (Req 8.1).
        if veg is not None:
            for fname, model in veg.models.items():
                eqg.add_model(fname, model.to_bytes())
            for fname, dds in veg.textures.items():
                eqg.add_texture(fname, dds)
        # Structure models and their textures (POIs spec Req 8.4).
        if sites is not None:
            for fname, model in sites.models.items():
                eqg.add_model(fname, model.to_bytes())
            for fname, dds in sites.textures.items():
                eqg.add_texture(fname, dds)

        # 5. Pack .eqg (confinement-checked through the OutputRoot).
        eqg_path = out_dir / f"{name}.eqg"
        eqg.write(eqg_path, root=root)

        # Advisory pacing/gating + content layer for the sidecar. These ride
        # in the .zone.json sidecar (and the GLB sidecar), never in the binary.
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

        # Wilderness advisory data (biome, edges, barriers, region intent, POI
        # anchors). Empty for room-graph zones, so their sidecars gain no keys.
        wild_meta = self._wilderness_sidecar()
        if veg is not None:
            wild_meta["vegetation"] = dict(veg.report)
        if sites is not None:
            wild_meta["sites"] = dict(sites.report)
        # The Texture_Manifest rides with every build (Req 5).
        side_meta = {**wild_meta,
                     "textures": texture_manifest(ter, modes, veg, dds_by_name, sites)}
        # The layout block (graph-layout Req 7.5): engine, rule set, rooms'
        # kinds and sizes, and the built graph's shape, classic or grown.
        layout_meta = layout_sidecar(self.spec)
        if layout_meta is not None:
            side_meta["layout"] = layout_meta

        # 6. GLB preview — pass per-material base colours so the preview shows
        #    the real palette rather than arbitrary hues. The GLB path also
        #    writes its own <name>.zone.json next to the .glb.
        glb_path = None
        if write_glb:
            glb_path = out_dir / f"{name}.glb"
            mat_colors = self._material_color_map(ter)
            result = eqg.write_glb(glb_path, material_colors=mat_colors,
                                   room_pacing=room_pacing, gates=gates,
                                   content=content_meta,
                                   zone_type=self.spec.zone_type,
                                   extra=side_meta,
                                   root=root,
                                   extra_meshes=_extra_meshes(veg, sites),
                                   textures={m.index: dds_by_name[m.name]
                                             for m in ter.materials
                                             if m.name in dds_by_name})
            if result is None:
                glb_path = None  # trimesh not available
            warnings.extend(eqg.glb_warnings)

        # 7. Sidecar on EVERY build (not only when a GLB is written). When the
        #    GLB path ran it already wrote an identical <name>.zone.json; this
        #    rewrites the same content, and covers the write_glb=False case
        #    (e.g. the Pipeline's scratch attempts, which merge gate results in
        #    via `extra`). Content shape is shared with the GLB sidecar.
        sidecar_path = out_dir / f"{name}.zone.json"
        eqg.write_sidecar(
            sidecar_path,
            rooms=room_pacing,
            gates=gates,
            content=content_meta,
            extra={"zone_type": self.spec.zone_type, **side_meta},
            root=root,
        )

        # The map SVG and EQ map files are NOT written here: the Pipeline
        # post-pass writes them for the accepted build only (M2 Decision 8).

        return BuildResult(
            spec=self.spec,
            eqg_path=eqg_path,
            glb_path=glb_path,
            sidecar_path=sidecar_path,
            vertex_count=len(ter.vertices),
            polygon_count=len(ter.polygons),
            material_count=len(ter.materials),
            backend=backend_name,
            warnings=warnings,
        )

    def _wilderness_sidecar(self) -> dict:
        """The wilderness advisory keys for the ``.zone.json`` sidecar
        (Req 1.4, 3.7, 10.2, 14.4), or ``{}`` for a room-graph zone.

        Re-derived from the spec's cached landscape (the same one the mesh was
        built from), so it always describes the shipped terrain. Advisory only:
        none of it reaches the ``.eqg``.
        """
        payload = self.spec.wilderness
        if payload is None:
            return {}
        from generators.wilderness.biome_resolve import (
            BiomeSubstitution, WildernessIntent)
        from generators.wilderness.build import DEFAULT_BIOME, landscape_for
        from generators.wilderness.matrix import POIAnchor

        land = landscape_for(self.spec)
        biome = payload.get("biome", DEFAULT_BIOME)
        sub = payload.get("biome_substitution")
        intent = WildernessIntent(
            biome=biome, requested_biome=(sub or {}).get("requested", biome),
            substitution=BiomeSubstitution(**sub) if sub else None)
        rec = intent.sidecar_record()
        out: dict = {"biome": rec["biome"]}
        if "substitution" in rec:
            out["biome_substitution"] = rec["substitution"]

        # The regions the build actually ships: the bowl's plus any the spec
        # adds on top (e.g. the task-6 water-plane AWT regions).
        regions = {r.id: r for r in self.spec.regions}

        def box(rid: str) -> dict:
            r = regions[rid]
            return {"min_xy": [r.center_x - r.extent_x, r.center_y - r.extent_y],
                    "max_xy": [r.center_x + r.extent_x, r.center_y + r.extent_y]}

        out["edge_connections"] = {e.side: e.edge_type for e in land.bowl.edges}
        out["invisible_walls"] = [
            {"region_id": b.region_id, "side": b.side, **box(b.region_id),
             "kind": "invisible_wall"}
            for b in land.bowl.barriers if b.kind == "invisible_wall"
        ]
        out["lava"] = [
            {"region_id": b.region_id, **box(b.region_id), "damaging": True}
            for b in land.bowl.barriers if b.kind == "lava"
        ]
        out["region_intent"] = [
            {"region_id": r.id, "kind": r.kind, **box(r.id),
             "intent": self._region_intent(land, r)}
            for r in self.spec.regions
        ]
        sx, sy, sz = self.spec.safe_point
        spawn = POIAnchor(name="Spawn", x=sx, y=sy, is_spawn=True,
                          intent=land.matrix.cell(*land.matrix.spawn).intent)
        out["poi_anchors"] = [{**spawn.to_dict(), "z": sz}]
        if "dungeon" in payload:
            from generators.outdoor_dungeon import sidecar_block
            out["outdoor_dungeon"] = sidecar_block(self.spec)
        return out

    @staticmethod
    def _region_intent(land, region) -> str:
        """A region's Intent_Tag: the majority tag of the matrix cells under
        the fine cells its XY box covers. Read through the fine grid (the frame
        the mesh and regions are built in, ``factor`` fine cells per matrix
        cell), not the matrix's own world coordinates."""
        matrix, synth = land.matrix, land.synth
        factor = max(1, int(round(matrix.cell_size / synth.resolution)))
        ox, oy = synth.origin
        res = float(synth.resolution)
        nx, ny = synth.node_type.shape

        def span(c, e, o, n):
            lo = int((c - e - o) // res)
            hi = int((c + e - o) // res) - 1
            return range(max(lo, 0), min(max(hi, lo), n - 1) + 1)

        tags = [
            matrix.cell(min(fi // factor, matrix.nx - 1),
                        min(fj // factor, matrix.ny - 1)).intent
            for fi in span(region.center_x, region.extent_x, ox, nx)
            for fj in span(region.center_y, region.extent_y, oy, ny)
        ]
        return max(sorted(set(tags)), key=tags.count) if tags else "playable"

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

    def _build_geometry(self, name: str,
                        ter_version: int) -> Tuple[TerFile, str, list]:
        """Route through the backend registry by zone type.

        Returns ``(ter, backend_name, warnings)``. The chosen backend is
        ``backend_for(spec.zone_type)``; when its build returns ``None`` (e.g.
        terrain with numpy unavailable) we fall back to the box backend and
        record a ``backend_fallback`` warning, so a degraded machine still
        produces a zone instead of crashing.
        """
        ter_name = f"ter_{name}"
        warnings: list = []

        backend = backend_for(self.spec.zone_type)
        ter = backend.build(self.spec, ter_name, ter_version)
        if ter is not None:
            return ter, backend.name, warnings

        # Chosen backend couldn't run — fall back to the box backend.
        warnings.append(
            f"backend_fallback: {backend.name} unavailable, built with box"
        )
        box = BoxBackend()
        ter = box.build(self.spec, ter_name, ter_version)
        return ter, box.name, warnings

    def _build_zon(self, ter_filename: str, veg=None, sites=None) -> ZonFile:
        zon = ZonFile()

        # The terrain mesh is the ZON's first model (RoF2 convention):
        # ``TER_<NAME>.TER`` — the Build_Name upper-cased, the ONLY uppercase
        # form of the stem (design "Build_Name artifact naming", Req 8.2). The
        # ``ter_filename`` is already ``ter_<name>.ter`` so upper-casing it
        # yields exactly ``TER_<NAME>.TER``.
        zon.models.append(ter_filename.upper())

        # Trees (Req 8.2): each packed model once after the TER, one object per
        # tree, yaw in radians.
        if veg is not None:
            model_id = {}
            for fname in sorted(veg.models):
                model_id[fname] = len(zon.models)
                zon.models.append(fname)
            for i, tree in enumerate(veg.placement.instances):
                zon.objects.append(ZonObject(
                    name=f"veg_{i:04d}",
                    model_id=model_id[veg.model_index[tree.species]],
                    x=tree.x, y=tree.y, z=tree.z,
                    yaw=tree.yaw, scale=tree.scale,
                ))

        # Structures (POIs spec Req 8.4): each packed model once after the
        # trees', one object per Structure; yaw is the way its front faces
        # (archive decision 10), Z the surface under its centre.
        if sites is not None and sites.structures:
            site_id = {}
            for fname in sorted(sites.models):
                site_id[fname] = len(zon.models)
                zon.models.append(fname)
            for i, (fname, st) in enumerate(sites.structures):
                zon.objects.append(ZonObject(
                    name=f"site_{i:04d}", model_id=site_id[fname],
                    x=st.x, y=st.y, z=st.z, yaw=st.yaw, scale=1.0,
                ))

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
                 vertex_count, polygon_count, material_count,
                 backend="box", warnings=None,
                 sidecar_path=None, map_path=None):
        self.spec = spec
        self.eqg_path = eqg_path
        self.glb_path = glb_path
        # The .zone.json sidecar is written on every build (not only when a
        # GLB is exported). ``map_path`` is set by the Pipeline post-pass,
        # which writes the .map.svg for accepted builds only.
        self.sidecar_path = sidecar_path
        self.map_path = map_path
        self.vertex_count = vertex_count
        self.polygon_count = polygon_count
        self.material_count = material_count
        # Name of the geometry backend actually used ("box" | "terrain").
        self.backend = backend
        # Advisory warnings raised during the build (e.g. a backend fallback).
        self.warnings = list(warnings) if warnings else []

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
