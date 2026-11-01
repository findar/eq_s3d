"""
generators/vegetation
---------------------
Wilderness trees (roadmap step 2, spec ``zone-generator-wilderness-trees``).

Trees are a layer on top of the finished wilderness: the vegetation kit
(``kit``, data in ``styles/vegetation.json``), procedural tree models
(``models``) and their placement (``placement``). The TER is never touched.
"""

from __future__ import annotations

from generators.vegetation.kit import (
    DENSITY_LEVELS,
    FORMS,
    Groves,
    Species,
    VegetationKit,
    load_vegetation_kit,
)

__all__ = [
    "DENSITY_LEVELS",
    "FORMS",
    "Groves",
    "Species",
    "VegetationKit",
    "load_vegetation_kit",
]
