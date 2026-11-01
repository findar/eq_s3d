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

UV_SCALE = 0.01   # one texture repeat per 100 u (unchanged)

SPECS = {
    "dungeon_flat": lambda: plan_to_spec(ZonePlan(name="wuv", zone_type="dungeon",
                                                  verticality="flat"), seed=7),
    "dungeon_elevated": lambda: plan_to_spec(ZonePlan(name="wuv", zone_type="dungeon",
                                                      verticality="dramatic"), seed=678358326),
    "dungeon_themed": lambda: plan_to_spec(make_plan("a gnoll temple dungeon with 8 rooms",
                                                     name="wuv"), seed=7),
    "city": lambda: plan_to_spec(ZonePlan(name="wuv", zone_type="city"), seed=7),
}


def _walls(ter):
    """Each wall triangle as (corner positions (3,3), corner uvs (3,2), its
    visible-side normal)."""
    out = []
    for p in ter.polygons:
        vs = [ter.vertices[i] for i in (p.v1, p.v2, p.v3)]
        n = np.array([vs[0].nx, vs[0].ny, vs[0].nz])
        if abs(n[2]) > 0.5:
            continue
        P = np.array([[v.x, v.y, v.z] for v in vs])
        UV = np.array([[v.u, v.v] for v in vs])
        out.append((P, UV, n))
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
    _, ter = built
    walls = _walls(ter)
    assert walls
    for P, UV, n in walls:
        area = np.linalg.norm(np.cross(P[1] - P[0], P[2] - P[0]))
        if area < 1e-6:
            continue
        up = np.array([0.0, 0.0, 1.0])
        right = np.cross(-n, up)
        right /= np.linalg.norm(right)
        gu, gv = _gradient(P, UV[:, 0]), _gradient(P, UV[:, 1])
        # v falls as z rises, u rises to the right, both at 100 u per repeat.
        assert gv @ up == pytest.approx(-UV_SCALE, abs=1e-6)
        assert gu @ right == pytest.approx(UV_SCALE, abs=1e-6)


def test_room_walls_face_into_their_room(built):
    spec, ter = built
    checked = 0
    for P, _, n in _walls(ter):
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
    _, ter = built
    for p in ter.polygons:
        for i in (p.v1, p.v2, p.v3):
            v = ter.vertices[i]
            if v.nz > 0.5:
                assert (v.u, v.v) == pytest.approx((v.x * UV_SCALE, -v.y * UV_SCALE), abs=1e-4)
            elif v.nz < -0.5:
                assert (v.u, v.v) == pytest.approx((v.x * UV_SCALE, v.y * UV_SCALE), abs=1e-4)
