"""Grounding facts the export relies on (export spec task 2, Requirement 3.3).

``docs/RESEARCH.md`` "Step 17: takeover and doors" has the evidence; these tests pin the
install facts the code builds on, so a different install fails loudly instead of exporting
a zone that names a model the client can't draw. They read the install (``EQ_PATH``) and
never write to it; without an install they skip, as the survey tests do.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.pfs import PfsArchive
from core.zon import ZonFile
from generators.decor.stock import Importer, _Wld, eq_path_from_env

EQ = eq_path_from_env()
pytestmark = pytest.mark.skipif(EQ is None, reason="EQ_PATH is not set (no EQ install to read)")

#: The Door model a takeover's doors rows name (archive decision 8): the classic plain door,
#: imported from its s3d object archive and packed into our .eqg by the build (task 5).
DOOR_KEY = "BBDOOR1"
DOOR_ARCHIVE = "ecommons_obj.s3d"
DOOR_WLD = "ecommons_obj.wld"
DOOR_MESH_HASH = "b29f16cdfe7d32a6"


def _names(archive: str) -> set[str]:
    return {f.name.lower() for f in PfsArchive.from_file(EQ / archive).files}


def test_door_model_exists_where_the_decision_says():
    """BBDOOR1 is an actor in ecommons_obj.s3d, imports unchanged (hash), and is a
    12-triangle slab 1 x 10 x 10.05 units hinged at its origin."""
    files = {f.name.lower(): f.data for f in PfsArchive.from_file(EQ / DOOR_ARCHIVE).files}
    assert DOOR_KEY in _Wld(files[DOOR_WLD]).actors
    model = Importer(EQ).get(DOOR_KEY)          # refuses a mesh that no longer matches
    assert model.archive == DOOR_ARCHIVE
    assert model.mesh_hash == DOOR_MESH_HASH
    assert len(model.ter.polygons) == 12
    pts = np.array([(v.x, v.y, v.z) for v in model.ter.vertices])
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    np.testing.assert_allclose(hi - lo, [1.0, 10.0, 10.0], atol=0.1)
    # The hinge edge is at the origin: the slab runs from x -1..0, y -10..0, z 0..10.
    np.testing.assert_allclose(hi, [0.0, 0.0, 10.05], atol=0.1)
    assert len(model.textures) == 1


def test_no_door_model_is_global():
    """The client's always-loaded object archive holds only the PoK stone, and the global
    load list names no door archive, so a takeover must pack its own Door model."""
    wlds = [f.data for f in PfsArchive.from_file(EQ / "global_obj.s3d").files
            if f.name.lower().endswith(".wld")]
    assert [sorted(_Wld(d).actors) for d in wlds] == [["POKTELE500"]]
    load = (EQ / "Resources" / "GlobalLoad.txt").read_text(encoding="latin1").lower()
    assert "door" not in load


@pytest.mark.parametrize("short", ["arena", "clz"])
def test_eqg_with_loose_zon(short):
    """arena (also an s3d zone) and clz (the client's character select, EQG only, which the
    client's log shows loading) ship the same way: an .eqg holding the TER and no .zon, and
    a loose EQGZ <short>.zon whose model table names the TER and only files in that .eqg."""
    names = _names(f"{short}.eqg")
    assert not any(n.endswith(".zon") for n in names)
    zon = ZonFile.from_bytes((EQ / f"{short}.zon").read_bytes())
    assert zon.models[0].lower().startswith("ter_") and zon.models[0].lower() in names
    assert all(m.lower() in names for m in zon.models)
    if short == "arena":
        assert "arena.wld" in _names("arena.s3d")
