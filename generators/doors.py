"""
generators/doors.py
-------------------
The Door model a build with Gates packs (export spec task 5, Requirements 3.3, 5).

A Gate is a door at run time: an EQEmu ``doors`` row the SQL export writes (task 4), never
geometry or a ZON object (lessons-learned "Design calls"). The row names a model the client
must already hold for the zone, and no door model is global (archive decision 8), so a build
with Gates carries its own: ``BBDOOR1``, the classic plain door from ``ecommons_obj.s3d``,
imported from the install at build time through the decor importer
(:class:`generators.decor.stock.Importer`), exactly as a Prop's stock model is. It packs as
``obj_bbdoor1.mod`` (the stock ``OBJ_`` convention) plus its one texture, and is listed in the
ZON's model table with no object placed; the doors rows name it :data:`DOOR_MODEL`.

The model is a slab 1 x 10 x 10.05 units (x thick, y wide, z tall) hinged at its origin
(x -1..0, y -10..0). A doors row's ``size`` is 100 per unit of scale (decision 9), so the SQL
scales it to a corridor of width ``w`` with ``size = round(100 * w / DOOR_WIDTH)``.

**No install** (``EQ_PATH`` unset or missing): the build skips the Door model with the
warning :data:`NO_INSTALL`, as Decor does, and is otherwise the same build. Its bytes are
then those of the build before this task. Nothing from the install is ever committed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Optional

from core.ter import TerFile

#: The catalogue key of the Door model (archive decision 8).
DOOR_KEY = "BBDOOR1"
#: The packed file name, and the ZON model table entry.
DOOR_FILE = "obj_bbdoor1.mod"
#: The name a ``doors`` row writes: the ``.mod`` file name without ``.MOD``, upper-cased.
DOOR_MODEL = "OBJ_BBDOOR1"
#: The model's width in units (its y extent, hinge to latch) at ``size`` 100.
DOOR_WIDTH = 10.0
#: Its height in units (z extent) at ``size`` 100.
DOOR_HEIGHT = 10.05
#: Its thickness in units (x extent).
DOOR_THICKNESS = 1.0

#: The warning a build with Gates gives when it has no install to copy the Door model from.
NO_INSTALL = "doors_none:no_install (EQ_PATH unset or missing), built with no Door model"
#: The warning prefix when the install holds no importable Door model.
NOT_IMPORTABLE = "doors_none:not_importable"


@dataclass
class DoorModel:
    """The packed Door model: its ``.mod`` (named :data:`DOOR_FILE`) and its textures."""
    model: TerFile
    textures: Dict[str, bytes] = field(default_factory=dict)

    @property
    def model_file(self) -> str:
        return DOOR_FILE


def door_model(eq_path: Path | str, importer=None) -> DoorModel:
    """The Door model imported from the install at ``eq_path`` (``importer``: an existing
    :class:`~generators.decor.stock.Importer` to share its cache). Raises
    :class:`~generators.decor.stock.NotImportable` when the install can't give it."""
    from generators.decor.stock import Importer, _renamed

    stock = (importer or Importer(eq_path)).get(DOOR_KEY)
    return DoorModel(_renamed(stock.ter, DOOR_FILE), dict(stock.textures))


def doors_for(spec, warnings: list, eq_path=None,
              importer_for: Optional[Callable] = None) -> Optional[DoorModel]:
    """The Door model for a build, or ``None``: when the spec has no Gates (the build is
    unchanged), or with a warning when there is no install or it can't give the model.
    ``importer_for(eq_path)`` returns the importer to use (the builder's shared one)."""
    if not spec.gates:
        return None
    from generators.decor.stock import NotImportable, eq_path_from_env

    eq = eq_path if eq_path is not None else eq_path_from_env()
    if eq is None:
        warnings.append(NO_INSTALL)
        return None
    try:
        return door_model(eq, importer_for(eq) if importer_for else None)
    except NotImportable as e:
        warnings.append(f"{NOT_IMPORTABLE} ({e}), built with no Door model")
        return None
