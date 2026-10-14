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
        rz=90.0, scale=1.5,
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
        # Rotation converts to EQ heading units and back — allow small float error
        assert abs(zon2.objects[0].rz - 90.0) < 1.0

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
