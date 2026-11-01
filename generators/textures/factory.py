"""
generators/textures/factory.py
-------------------------------
Provider selection, caching, and the back-compatible generate_texture().

Texture_Mode (placeholder textures spec Req 4): a zone surface material (one
with a ``surface_class``) is drawn as a labelled Placeholder by default.
``EQ_S3D_TEXTURE_PROVIDER`` = ``placeholder`` | ``procedural`` | ``ai`` overrides
that. Anything without a surface class (tree bark and leaf) keeps the old
order: AI if a key is present and it succeeds, else procedural. The procedural
provider always works (no network), so generation never fails for lack of a
key.

Caching: identical TextureSpecs produce identical DDS, so results are memoised
in-process to avoid repeat work (and repeat API cost for the AI provider).
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from core.env import env_value
from .base import TextureProvider, TextureSpec
from .procedural import ProceduralProvider
from .placeholder import PlaceholderProvider
from .ai import AIProvider

TEXTURE_MODES = ("placeholder", "procedural", "ai")

_cache: Dict[Tuple, bytes] = {}
_forced: Optional[TextureProvider] = None


def get_provider(prefer_ai: bool = True, surface_class: str = "") -> TextureProvider:
    """
    Return the provider for a request. A request with a *surface_class* gets
    the Placeholder unless ``EQ_S3D_TEXTURE_PROVIDER`` says ``procedural`` or
    ``ai``. Otherwise: AI if a key is present and prefer_ai is set, else
    procedural. A provider forced with ``set_provider`` wins over both.
    """
    if _forced is not None:
        return _forced

    override = (env_value("EQ_S3D_TEXTURE_PROVIDER") or "").lower()
    if override == "procedural":
        return ProceduralProvider()
    if override == "ai":
        return AIProvider()
    if surface_class:
        return PlaceholderProvider()

    if prefer_ai:
        ai = AIProvider()
        if ai.available():
            return ai
    return ProceduralProvider()


def set_provider(provider: Optional[TextureProvider]) -> None:
    """Force a specific provider (mainly for tests). None restores auto-select."""
    global _forced
    _forced = provider


def _cache_key(spec: TextureSpec, provider_name: str) -> Tuple:
    return (provider_name, spec.name, spec.description, spec.base_color,
            spec.kind, spec.size, spec.seed, spec.tileable, spec.surface_class)


def generate(spec: TextureSpec) -> bytes:
    """Generate DDS for a spec, with caching and automatic fallback."""
    return generate_with_mode(spec)[0]


def generate_with_mode(spec: TextureSpec) -> Tuple[bytes, str]:
    """``(DDS bytes, Texture_Mode that drew them)``: the provider's name, or
    ``procedural`` when a failing provider fell back."""
    provider = get_provider(surface_class=spec.surface_class)
    key = _cache_key(spec, provider.name)
    if key in _cache:
        return _cache[key], provider.name

    try:
        data = provider.generate(spec)
    except Exception as e:
        # AI (or any) provider failed → fall back to procedural
        if provider.name != "procedural":
            print(f"[textures] {provider.name} failed ({e}); falling back to procedural")
            fallback = ProceduralProvider()
            data = fallback.generate(spec)
            key = _cache_key(spec, fallback.name)
            provider = fallback
        else:
            raise

    _cache[key] = data
    return data, provider.name


# ---------------------------------------------------------------------------
# Back-compatible convenience wrapper (used by the existing builder)
# ---------------------------------------------------------------------------

# Map a material's logical name to a texture "kind" for better procedural output.
def _infer_kind(name: str, description: str) -> str:
    text = f"{name} {description}".lower()
    if any(w in text for w in ("grass", "meadow", "turf")):
        return "grass"
    if any(w in text for w in ("dirt", "earth", "mud", "sand", "ground")):
        return "dirt"
    if any(w in text for w in ("cave", "rock", "boulder", "cliff")):
        return "rock"
    if any(w in text for w in ("floor", "wall", "ceiling", "stone", "flagstone")):
        return "stone"
    return "stone"


def generate_texture(description: str,
                     color: Tuple[int, int, int],
                     size: int = 256,
                     name: str = "material",
                     seed: int = 0,
                     surface_class: str = "") -> bytes:
    """
    Back-compatible entry point. Builds a TextureSpec from a description +
    base colour and runs it through the active provider.
    """
    return texture_with_mode(description, color, size, name, seed, surface_class)[0]


def texture_with_mode(description: str,
                      color: Tuple[int, int, int],
                      size: int = 256,
                      name: str = "material",
                      seed: int = 0,
                      surface_class: str = "") -> Tuple[bytes, str]:
    """``generate_texture`` plus the Texture_Mode that drew it (for the
    sidecar's Texture_Manifest)."""
    spec = TextureSpec(
        name=name,
        description=description,
        base_color=color,
        kind=_infer_kind(name, description),
        size=size,
        seed=seed,
        surface_class=surface_class,
    )
    return generate_with_mode(spec)
