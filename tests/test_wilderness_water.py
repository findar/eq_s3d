"""Visual water plane (wilderness spec task 6).

A build with water cells gets a flat, NON-collidable surface at the water
level with its own material and an AWT region; the walk surface ignores it, so
the bowl gate (Property 15) still means something at river edges.
"""

from __future__ import annotations

import numpy as np
import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from analyzer.rof2check import _check_collision_policy
from analyzer.traverse import AgentModel, build_walk_surface
from core.ter import FLAG_PASSABLE
from generators.builder import _REGION_PREFIX, ZoneBuilder
from generators.wilderness.build import bowl_report, build_wilderness_ter, wilderness_spec
from generators.wilderness.water import WATER_SURFACE_MATERIAL
from generators.zone_spec import ZoneSpec

RIVER = {"N": "zoneline", "E": "river"}


@pytest.fixture(scope="module")
def river_build():
    spec = wilderness_spec("k", 2024, RIVER)
    return spec, build_wilderness_ter(spec, "ter_k", 2)


def _water_polys(ter):
    idx = next(m.index for m in ter.materials if m.name == WATER_SURFACE_MATERIAL)
    return [p for p in ter.polygons if p.material == idx]


def test_water_cells_get_a_flat_surface_material_and_awt_region(river_build):
    spec, ter = river_build
    assert spec.water_level is not None
    polys = _water_polys(ter)
    assert polys
    zs = {ter.vertices[v].z for p in polys for v in (p.v1, p.v2, p.v3)}
    assert zs == {spec.water_level}
    assert WATER_SURFACE_MATERIAL in spec.materials
    water = [r for r in spec.regions if r.kind == "water"]
    assert water and _REGION_PREFIX[water[0].kind] == "AWT"


def test_water_polygons_are_not_collidable_and_not_standable(river_build):
    spec, ter = river_build
    polys = _water_polys(ter)
    assert all(p.flags & FLAG_PASSABLE for p in polys)
    water_mat = polys[0].material
    assert all(p.flags == 0 for p in ter.polygons if p.material != water_mat)
    assert _check_collision_policy(ter).passed
    water_faces = [i for i, p in enumerate(ter.polygons) if p.flags & FLAG_PASSABLE]
    agent = AgentModel()
    assert not build_walk_surface(ter, agent).standable[water_faces].any()
    # The default is what hides them: honoring no flags, the flat plane stands.
    assert build_walk_surface(ter, agent, skip_passable=False).standable[water_faces].all()


def test_bowl_still_holds_with_water(river_build):
    spec, ter = river_build
    assert bowl_report(spec, ter).passed


def test_dry_build_has_no_water_plane():
    spec = wilderness_spec("k", 2024)
    ter = build_wilderness_ter(spec, "ter_k", 2)
    assert WATER_SURFACE_MATERIAL not in spec.materials
    assert not any(r.kind == "water" for r in spec.regions)
    assert all(p.flags == 0 for p in ter.polygons)


def test_water_level_serializes_only_when_set(river_build):
    spec, _ = river_build
    assert ZoneSpec.from_dict(spec.to_dict()).water_level == spec.water_level
    dungeon = plan_to_spec(ZonePlan(name="d", zone_type="dungeon"), seed=1)
    assert dungeon.water_level is None
    assert "water_level" not in dungeon.to_dict()


def test_water_shows_in_the_glb_preview(tmp_path):
    trimesh = pytest.importorskip("trimesh")
    spec = wilderness_spec("karana_w", 2024, RIVER)
    result = ZoneBuilder(spec).build(output_dir=tmp_path)
    assert result.glb_path is not None and result.glb_path.exists()
    scene = trimesh.load(result.glb_path, force="scene")
    colors = np.concatenate([g.visual.vertex_colors[:, :3]
                             for g in scene.geometry.values()])
    water = spec.materials[WATER_SURFACE_MATERIAL].color
    assert (colors == np.array(water)).all(axis=1).any()
