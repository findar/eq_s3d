"""
generators/textures/base.py
----------------------------
Texture provider interface and the request spec.

A TextureProvider turns a TextureSpec (a description + palette + hints) into
DDS bytes. Concrete providers:
  - ProceduralProvider — layered noise, no network, deterministic, always works
  - AIProvider         — image-model API (optional, needs a key)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple


@dataclass
class TextureSpec:
    """A request for a single texture."""
    name: str                              # logical material name
    description: str = ""                  # prompt hint, e.g. "wet cave rock, mossy"
    base_color: Tuple[int, int, int] = (120, 112, 104)
    kind: str = "stone"                    # stone | dirt | rock | grass | organic | flat
    size: int = 256
    seed: int = 0
    tileable: bool = True


class TextureProvider:
    """Base class. Subclasses implement `generate`."""

    name: str = "base"

    def available(self) -> bool:
        """Whether this provider can run (e.g. has an API key)."""
        return True

    def generate(self, spec: TextureSpec) -> bytes:
        """Return DDS bytes for the given spec."""
        raise NotImplementedError
