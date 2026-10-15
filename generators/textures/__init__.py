"""
generators.textures — texture generation with pluggable providers.

Public API:
    get_provider()       → the best available TextureProvider
    generate_texture(...) → convenience wrapper (back-compat)
"""

from .base import TextureSpec, TextureProvider
from .factory import get_provider, generate_texture

__all__ = [
    "TextureSpec",
    "TextureProvider",
    "get_provider",
    "generate_texture",
]
