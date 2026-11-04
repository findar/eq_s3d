"""Wall UVs follow EQ's convention (placeholder textures spec task 11).

Stock walls run ``v`` down the wall and our placeholder labels need ``u`` to
run left-to-right as seen by a player, so on every box wall triangle: ``v``
falls as ``z`` rises, and ``u`` rises to the right of a viewer facing the
wall's visible side. The visible side is checked against the room footprints:
a room wall's normal points into its room.
"""

import numpy as np
import pytest

from ai.expand import plan_to_spec
from ai.planner import make_plan
from ai.schema import ZonePlan
from core.pfs import PfsArchive
from core.ter import TerFile
from generators.builder import ZoneBuilder

DEFAULT_UV_SCALE = 0.01   # 100 u per repeat, for a material with no texel_density


def uv_scale(spec, ter, material_index):
    """UV units per world unit for a TER material: 1 / its texel_density
    (interesting textures task 7), else the default."""
    density = spec.materials[ter.materials[material_index].name].texel_density
    return 1.0 / density if density else DEFAULT_UV_SCALE

def _classic(plan):
    """The plan on the classic engine: these cases were recorded on it, and
    graph is the default since graph-layout task 21."""
    plan.layout = "classic"
    return plan


SPECS = {
    "dungeon_flat": lambda: plan_to_spec(ZonePlan(name="wuv", zone_type="dungeon",
                                                  verticality="flat", layout="classic"),
                                         seed=7),
    "dungeon_elevated": lambda: plan_to_spec(ZonePlan(name="wuv", zone_type="dungeon",
                                                      verticality="dramatic",
                                                      layout="classic"), seed=678358326),
    "dungeon_themed": lambda: plan_to_spec(_classic(make_plan(
        "a gnoll temple dungeon with 8 rooms", name="wuv")), seed=7),
    "city": lambda: plan_to_spec(ZonePlan(name="wuv", zone_type="city"), seed=7),
}


def _walls(ter, spec=None):
    """Each wall triangle as (corner positions (3,3), corner uvs (3,2), its
    visible-side normal, its UV scale)."""
    out = []
    for p in ter.polygons:
        vs = [ter.vertices[i] for i in (p.v1, p.v2, p.v3)]
        n = np.array([vs[0].nx, vs[0].ny, vs[0].nz])
        if abs(n[2]) > 0.5:
            continue
        P = np.array([[v.x, v.y, v.z] for v in vs])
        UV = np.array([[v.u, v.v] for v in vs])
        out.append((P, UV, n, uv_scale(spec, ter, p.material) if spec else None))
    return out


def _gradient(P, values):
    """The world-space gradient of a value linear over triangle P."""
    e1, e2 = P[1] - P[0], P[2] - P[0]
    G = np.array([[e1 @ e1, e1 @ e2], [e1 @ e2, e2 @ e2]])
    k = np.linalg.solve(G, [values[1] - values[0], values[2] - values[0]])
    return k[0] * e1 + k[1] * e2


@pytest.fixture(scope="module", params=sorted(SPECS))
def built(request, tmp_path_factory):
    spec = SPECS[request.param]()
    result = ZoneBuilder(spec).build(output_dir=tmp_path_factory.mktemp(request.param),
                                     write_glb=False)
    ter = TerFile.from_bytes(PfsArchive.from_file(result.eqg_path).get("ter_wuv.ter"))
    return spec, ter


def test_wall_v_runs_down_and_u_runs_right(built):
    spec, ter = built
    walls = _walls(ter, spec)
    assert walls
    for P, UV, n, scale in walls:
        area = np.linalg.norm(np.cross(P[1] - P[0], P[2] - P[0]))
        if area < 1e-6:
            continue
        up = np.array([0.0, 0.0, 1.0])
        right = np.cross(-n, up)
        right /= np.linalg.norm(right)
        gu, gv = _gradient(P, UV[:, 0]), _gradient(P, UV[:, 1])
        # v falls as z rises, u rises to the right, both at the material's scale.
        assert gv @ up == pytest.approx(-scale, abs=1e-6)
        assert gu @ right == pytest.approx(scale, abs=1e-6)


def test_room_walls_face_into_their_room(built):
    spec, ter = built
    checked = 0
    for P, _, n, _ in _walls(ter):
        c = P.mean(axis=0)
        for room in spec.rooms:
            (x0, y0, _), (x1, y1, _) = room.bounds
            on_x = abs(c[0] - x0) < 0.01 or abs(c[0] - x1) < 0.01
            on_y = abs(c[1] - y0) < 0.01 or abs(c[1] - y1) < 0.01
            within = x0 - 0.01 <= c[0] <= x1 + 0.01 and y0 - 0.01 <= c[1] <= y1 + 0.01
            if within and (on_x or on_y):
                q = c + 2.0 * n
                assert x0 < q[0] < x1 and y0 < q[1] < y1
                checked += 1
                break
    assert checked > 0


def test_floor_and_ceiling_uvs_read_unmirrored(built):
    """Floors (seen from above) map v to -Y and ceilings (seen from below) to
    +Y, so a label reads unmirrored on both (task 6's finding, fixed in 7)."""
    spec, ter = built
    for p in ter.polygons:
        scale = uv_scale(spec, ter, p.material)
        for i in (p.v1, p.v2, p.v3):
            v = ter.vertices[i]
            if v.nz > 0.5:
                assert (v.u, v.v) == pytest.approx((v.x * scale, -v.y * scale), abs=1e-4)
            elif v.nz < -0.5:
                assert (v.u, v.v) == pytest.approx((v.x * scale, v.y * scale), abs=1e-4)
