"""
generators/textures/factory.py
-------------------------------
Provider selection, caching, and the back-compatible generate_texture().

Selection order: AI provider if a key is present and it succeeds, else the
procedural provider. The procedural provider always works (no network), so
generation never fails for lack of a key.

Caching: identical TextureSpecs produce identical DDS, so results are memoised
in-process to avoid repeat work (and repeat API cost for the AI provider).
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from core.env import env_value
from .base import TextureProvider, TextureSpec
from .procedural import ProceduralProvider
from .ai import AIProvider

_cache: Dict[Tuple, bytes] = {}
_forced: Optional[TextureProvider] = None


def get_provider(prefer_ai: bool = True) -> TextureProvider:
    """
    Return the best available provider. AI if a key is present and prefer_ai is
    set; otherwise procedural. Honour an EQ_S3D_TEXTURE_PROVIDER override
    ("procedural" | "ai") for testing/forcing.
    """
    if _forced is not None:
        return _forced

    override = (env_value("EQ_S3D_TEXTURE_PROVIDER") or "").lower()
    if override == "procedural":
        return ProceduralProvider()
    if override == "ai":
        return AIProvider()

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
            spec.kind, spec.size, spec.seed, spec.tileable)


def generate(spec: TextureSpec) -> bytes:
    """Generate DDS for a spec, with caching and automatic fallback."""
    provider = get_provider()
    key = _cache_key(spec, provider.name)
    if key in _cache:
        return _cache[key]

    try:
        data = provider.generate(spec)
    except Exception as e:
        # AI (or any) provider failed → fall back to procedural
        if provider.name != "procedural":
            print(f"[textures] {provider.name} failed ({e}); falling back to procedural")
            fallback = ProceduralProvider()
            data = fallback.generate(spec)
            key = _cache_key(spec, fallback.name)
        else:
            raise

    _cache[key] = data
    return data


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
                     seed: int = 0) -> bytes:
    """
    Back-compatible entry point used by the builder. Builds a TextureSpec from
    a description + base colour and runs it through the active provider.
    """
    spec = TextureSpec(
        name=name,
        description=description,
        base_color=color,
        kind=_infer_kind(name, description),
        size=size,
        seed=seed,
    )
    return generate(spec)
