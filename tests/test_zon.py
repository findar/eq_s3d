"""
tests/test_zon.py
-----------------
Round-trip tests for ZON binary serialisation.
"""

import pytest
from core.zon import (
    ZonFile, ZonObject, ZonRegion, ZonLight,
    REGION_WATER, REGION_LAVA,
)


def _make_zon() -> ZonFile:
    zon = ZonFile()
    zon.models.append("rock01.mod")
    zon.models.append("torch01.mod")

    zon.objects.append(ZonObject(
        name="rock_a", model_id=0,
        x=100.0, y=200.0, z=0.0,
        yaw=1.5, scale=1.5,
    ))
    zon.objects.append(ZonObject(
        name="torch_entrance", model_id=1,
        x=10.0, y=10.0, z=30.0,
    ))

    zon.regions.append(ZonRegion(
        name="AWT_entrance_pool",
        center_x=50.0, center_y=50.0, center_z=2.0,
        extend_x=20.0, extend_y=20.0, extend_z=3.0,
    ))

    zon.lights.append(ZonLight(
        name="torch_01",
        x=10.0, y=10.0, z=30.0,
        r=1.0, g=0.6, b=0.2,
        radius=40.0,
    ))
    return zon


class TestZonRoundTrip:
    def test_roundtrip_counts(self):
        zon = _make_zon()
        zon2 = ZonFile.from_bytes(zon.to_bytes())
        assert len(zon2.models)  == 2
        assert len(zon2.objects) == 2
        assert len(zon2.regions) == 1
        assert len(zon2.lights)  == 1

    def test_roundtrip_model_names(self):
        zon = _make_zon()
        zon2 = ZonFile.from_bytes(zon.to_bytes())
        assert zon2.models[0] == "rock01.mod"
        assert zon2.models[1] == "torch01.mod"

    def test_roundtrip_object_position(self):
        zon = _make_zon()
        zon2 = ZonFile.from_bytes(zon.to_bytes())
        obj = zon2.objects[0]
        assert abs(obj.x - 100.0) < 0.01
        assert abs(obj.y - 200.0) < 0.01
        assert abs(obj.z -   0.0) < 0.01

    def test_roundtrip_object_rotation(self):
        zon = _make_zon()
        zon2 = ZonFile.from_bytes(zon.to_bytes())
        # Radians are stored as-is (float32), no unit conversion.
        assert zon2.objects[0].yaw == pytest.approx(1.5, abs=1e-6)

    def test_roundtrip_every_field_exactly(self):
        # Values exactly representable in float32, so the round trip is exact.
        zon = ZonFile()
        zon.models += ["ter_x.ter", "veg_a.mod"]
        zon.objects.append(ZonObject(name="veg_0001", model_id=1, x=-12.5, y=40.25,
                                     z=3.75, yaw=-2.5, pitch=0.125, roll=-0.0625,
                                     scale=1.25))
        zon.regions.append(ZonRegion(name="AWT_pool", center_x=1.5, center_y=-2.5,
                                     center_z=0.5, rotation=-1.5, extend_x=8.0,
                                     extend_y=4.0, extend_z=2.0))
        zon.lights.append(ZonLight(name="l1", x=1.0, y=2.0, z=3.0, r=0.5, g=0.25,
                                   b=0.75, radius=64.0))
        zon2 = ZonFile.from_bytes(zon.to_bytes())
        assert zon2 == zon

    def test_place_takes_yaw_in_radians(self):
        zon = ZonFile()
        obj = zon.place("veg_0001", "veg_a.mod", 1.0, 2.0, 3.0, yaw=-3.0, scale=0.5)
        back = ZonFile.from_bytes(zon.to_bytes()).objects[0]
        assert obj.yaw == -3.0 and back.yaw == pytest.approx(-3.0, abs=1e-6)
        assert back.pitch == 0.0 and back.roll == 0.0

    def test_roundtrip_region_name(self):
        zon = _make_zon()
        zon2 = ZonFile.from_bytes(zon.to_bytes())
        assert zon2.regions[0].name == "AWT_entrance_pool"

    def test_roundtrip_region_extents(self):
        zon = _make_zon()
        zon2 = ZonFile.from_bytes(zon.to_bytes())
        r = zon2.regions[0]
        assert abs(r.extend_x - 20.0) < 0.01
        assert abs(r.center_z -  2.0) < 0.01

    def test_roundtrip_light_color(self):
        zon = _make_zon()
        zon2 = ZonFile.from_bytes(zon.to_bytes())
        lt = zon2.lights[0]
        assert abs(lt.r - 1.0) < 0.001
        assert abs(lt.g - 0.6) < 0.001
        assert abs(lt.b - 0.2) < 0.001
        assert abs(lt.radius - 40.0) < 0.01

    def test_water_factory(self):
        r = ZonRegion.water("test_pool", center_x=0, center_y=0, center_z=0)
        assert r.name.startswith("AWT_")

    def test_lava_factory(self):
        r = ZonRegion.lava("lava_pit", center_x=0, center_y=0, center_z=0)
        assert r.name.startswith("ALV_")

    def test_add_model_dedup(self):
        zon = ZonFile()
        idx1 = zon.add_model("rock.mod")
        idx2 = zon.add_model("rock.mod")
        assert idx1 == idx2
        assert len(zon.models) == 1

    def test_invalid_magic(self):
        with pytest.raises(ValueError):
            ZonFile.from_bytes(b"BADM\x00" * 20)


def _stock_zon(name: str) -> ZonFile:
    from pathlib import Path
    from core.env import env_value
    from core.pfs import PfsArchive
    eq = env_value("EQ_PATH")
    if not eq or not (Path(eq) / f"{name}.eqg").exists():
        pytest.skip(f"needs EQ_PATH with {name}.eqg")
    arc = PfsArchive.from_file(Path(eq) / f"{name}.eqg")
    zon_name = next(f for f in arc.list_files() if f.lower().endswith(".zon"))
    return ZonFile.from_bytes(arc.get(zon_name))


class TestStockRotations:
    """Stock EQG zones store rotations in radians, yaw in the first field
    (trees-step design, research finding 5). A heading-unit or degree reading
    would put these far outside ±π."""

    def test_stock_tree_yaw_spans_a_full_turn(self):
        zon = _stock_zon("broodlands")
        trees = [o for o in zon.objects if "tree" in zon.models[o.model_id].lower()]
        assert len(trees) > 100
        yaws = [o.yaw for o in trees]
        assert min(yaws) < -3.0 and max(yaws) > 3.0
        assert all(abs(y) <= 3.1416 for y in yaws)
        # The other two fields are small tilts (≤ 0.46 rad on broodlands).
        assert all(abs(o.pitch) < 0.5 and abs(o.roll) < 0.5 for o in trees)

    def test_stock_region_rotation_is_radians(self):
        zon = _stock_zon("broodlands")
        assert zon.regions
        assert all(abs(r.rotation) <= 3.1416 for r in zon.regions)
