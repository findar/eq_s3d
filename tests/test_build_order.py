"""
tests/test_build_order.py
-------------------------
Same seed, same build (races-followups task 2, Req 3): a zone builds the same bytes whether it
is the first build in its process or comes after others.

The leak was ``generators.decor.stock.Importer._models``, the process-wide model cache behind
``builder._importer``: it was keyed by (mesh hash, archive), and the mesh hash leaves out a
mesh's material list, so catalogue entries sharing a mesh under other textures (CRATEH's
apples, CRATEI's beans) took the textures of whichever was imported first in the process.

- ``Importer.get`` gives each entry its own textures, in either order.
- Zone B built after zone A in this process equals B built alone in a fresh one: the ``.eqg``
  without its time footer (lessons-learned "Two `.eqg` writes are never byte-identical") and
  the ``.zone.json``.

Needs the install (``EQ_PATH``); skips without it. Builds live in ``tmp_path`` only.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from generators.decor.stock import Importer, eq_path_from_env

EQ = eq_path_from_env()
needs_install = pytest.mark.skipif(EQ is None, reason="EQ_PATH is not set (no EQ install to read)")
ROOT = Path(__file__).resolve().parent.parent

#: Two halas crates on one mesh, each with its own produce texture.
CRATES = {"CRATEH": "apples", "CRATEI": "beans"}

#: (ZonePlan fields, seed). Built after A, B's decor took CRATEH's apples for CRATEI's beans.
ZONE_A = (dict(zone_type="dungeon", room_count=12, dungeon_theme="fortress", layout="classic"), 5)
ZONE_B = (dict(zone_type="dungeon", room_count=12, dungeon_theme="fortress", layout="graph"), 5)

#: B built alone: run in a fresh interpreter, so nothing earlier is left in its process.
_ALONE = """
import sys
from ai.expand import plan_to_spec
from ai.schema import ZonePlan
from generators.builder import ZoneBuilder
from generators.pipeline import _with_decor
fields, seed, out = eval(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
spec = _with_decor(plan_to_spec(ZonePlan(name="order_b", **fields).validate(), seed=seed))
ZoneBuilder(spec).build(output_dir=out, write_glb=False)
"""


def _build(fields, seed, name, out):
    from ai.expand import plan_to_spec
    from ai.schema import ZonePlan
    from generators.builder import ZoneBuilder
    from generators.pipeline import _with_decor

    spec = _with_decor(plan_to_spec(ZonePlan(name=name, **fields).validate(), seed=seed))
    return ZoneBuilder(spec).build(output_dir=out, write_glb=False)


@needs_install
@pytest.mark.parametrize("order", [("CRATEH", "CRATEI"), ("CRATEI", "CRATEH")])
def test_entries_sharing_a_mesh_keep_their_own_textures(order):
    imp = Importer(EQ)
    for key in order:
        names = " ".join(imp.get(key).textures)
        assert CRATES[key] in names, f"{key} imported with {names}"
        other = next(v for k, v in CRATES.items() if k != key)
        assert other not in names, f"{key} imported with {names}"


@needs_install
@pytest.mark.slow
def test_zone_after_another_builds_as_alone(tmp_path):
    _build(*ZONE_A, "order_a", tmp_path / "a")
    after = _build(*ZONE_B, "order_b", tmp_path / "b_after")

    alone_dir = tmp_path / "b_alone"
    subprocess.run([sys.executable, "-c", _ALONE, repr(ZONE_B[0]), str(ZONE_B[1]), str(alone_dir)],
                   cwd=ROOT, check=True, capture_output=True, text=True)

    alone_eqg = (alone_dir / after.eqg_path.name).read_bytes()
    assert after.eqg_path.read_bytes()[:-4] == alone_eqg[:-4], ".eqg differs after another build"
    alone_side = (alone_dir / after.sidecar_path.name).read_text(encoding="utf-8")
    assert after.sidecar_path.read_text(encoding="utf-8") == alone_side, \
        ".zone.json differs after another build"
