"""
tests/test_door_models.py
-------------------------
Door models in builds with Gates (export spec task 5; Requirements 3.3, 5).

- A build with Gates packs the Door model (``obj_bbdoor1.mod`` and its texture), lists it
  in the ZON's models and places no object of it; the TER is the build's own either way.
- A build with no Gates gets no Door model (its bytes are the goldens' in
  ``tests/test_layout_engine.py``).
- With no install a build with Gates skips the Door model with a warning, and its bytes are
  those of the build before task 5.

Builds that hold the client's art live in ``tmp_path`` only.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pytest

from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from analyzer.rof2check import check_eqg
from analyzer.traverse import validate
from core.pfs import PfsArchive
from core.ter import TerFile
from core.zon import ZonFile
from generators import doors
from generators.builder import ZoneBuilder
from generators.decor.stock import eq_path_from_env
from generators.zone_spec import GateSpec, ZoneSpec

EQ = eq_path_from_env()
needs_install = pytest.mark.skipif(EQ is None, reason="EQ_PATH is not set (no EQ install to read)")

#: A build with Locks 2, and its bytes with no Door model (``temple_locks`` before task 5).
GATED = (dict(zone_type="dungeon", room_count=9, locks=2, dungeon_theme="temple",
              dungeon_race="troll", verticality="dramatic", layout="classic"), 11,
         "c5e9125f3a11aa7c040ded8d3010496a90550090f0f7e876b9b82fcb6243388c")


def _gated_spec(name="door"):
    fields, seed, _golden = GATED
    return plan_to_spec(ZonePlan(name=name, **fields).validate(), seed=seed)


def _hash(path) -> str:
    return hashlib.sha256(path.read_bytes()[:-4]).hexdigest()


def _zon(arc: PfsArchive) -> ZonFile:
    name = next(f for f in arc.list_files() if f.lower().endswith(".zon"))
    return ZonFile.from_bytes(arc.get(name))


def test_the_names_the_sql_writes():
    """The doors rows name the packed file without ``.mod``, upper-cased (archive
    decision 8), and the width the SQL scales by is the model's."""
    assert doors.DOOR_MODEL == "OBJ_BBDOOR1"
    assert doors.DOOR_FILE.upper() == doors.DOOR_MODEL + ".MOD"
    assert doors.DOOR_WIDTH == 10.0


def test_no_gates_no_door_and_no_warning():
    warnings: list = []
    assert doors.doors_for(ZoneSpec(name="x"), warnings, eq_path="unused") is None
    assert warnings == []


def test_gates_without_an_install_warn(tmp_path, monkeypatch):
    monkeypatch.setenv("EQ_PATH", str(tmp_path / "no_install_here"))
    spec = ZoneSpec(name="x", gates=[GateSpec(id="g0", corridor_id="c0", lock_x=0.0,
                                                  lock_y=0.0, lock_z=0.0, key_room_id="r0",
                                                  key_x=0.0, key_y=0.0, key_z=0.0)])
    warnings: list = []
    assert doors.doors_for(spec, warnings) is None
    assert warnings == [doors.NO_INSTALL]


@pytest.mark.slow
def test_no_install_build_is_the_build_before(tmp_path, monkeypatch):
    """No install: the build with Gates is the one before task 5, with the warning."""
    monkeypatch.setenv("EQ_PATH", str(tmp_path / "no_install_here"))
    result = ZoneBuilder(_gated_spec("g_temple_locks")).build(output_dir=tmp_path / "out",
                                                              write_glb=False)
    assert _hash(result.eqg_path) == GATED[2]
    assert doors.NO_INSTALL in result.warnings


@needs_install
def test_the_door_model_imports_as_the_decision_says():
    """``obj_bbdoor1.mod``: 12 triangles, DOOR_WIDTH wide, hinged at its origin, one
    texture, and it round-trips."""
    door = doors.door_model(EQ)
    assert door.model_file == doors.DOOR_FILE == door.model.name
    assert len(door.model.polygons) == 12 and len(door.textures) == 1
    pts = np.array([(v.x, v.y, v.z) for v in door.model.vertices])
    size = pts.max(axis=0) - pts.min(axis=0)
    np.testing.assert_allclose(size, [doors.DOOR_THICKNESS, doors.DOOR_WIDTH,
                                      doors.DOOR_HEIGHT], atol=0.1)
    raw = door.model.to_bytes()
    assert TerFile.from_bytes(raw, name=doors.DOOR_FILE).to_bytes() == raw


@pytest.mark.slow
@needs_install
def test_a_build_with_gates_packs_the_door_unplaced(tmp_path, monkeypatch):
    """Locks 2: the Door model and its texture are packed, listed last in the ZON's models
    and placed by no object; the TER is the no-install build's; the build passes the
    format check and the gate."""
    spec = _gated_spec()
    assert len(spec.gates) == 2
    result = ZoneBuilder(spec).build(output_dir=tmp_path / "with", write_glb=False)
    assert not any(w.startswith("doors_none") for w in result.warnings)
    arc = PfsArchive.from_file(result.eqg_path)
    names = {n.lower() for n in arc.list_files()}
    door = doors.door_model(EQ)
    assert doors.DOOR_FILE in names
    assert set(door.textures) <= names
    zon = _zon(arc)
    assert zon.models[-1] == doors.DOOR_FILE
    door_id = len(zon.models) - 1
    assert all(o.model_id != door_id for o in zon.objects)

    assert check_eqg(result.eqg_path, spec, sidecar_path=result.sidecar_path).passed
    rep = validate(result.eqg_path, spec=spec, check_corridors=True)
    assert rep.passed and rep.corridors_passed

    monkeypatch.setenv("EQ_PATH", str(tmp_path / "no_install_here"))
    plain = ZoneBuilder(_gated_spec()).build(output_dir=tmp_path / "without", write_glb=False)
    plain_arc = PfsArchive.from_file(plain.eqg_path)
    ter = "ter_door.ter"
    assert arc.get(ter) == plain_arc.get(ter)
    plain_zon = _zon(plain_arc)
    assert zon.models[:-1] == plain_zon.models
    assert zon.objects == plain_zon.objects
