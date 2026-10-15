"""
tests/test_textures.py
----------------------
Tests for the texture provider system (procedural default + AI fallback).
"""

import os
import numpy as np
import pytest

from generators.textures import generate_texture, get_provider, TextureSpec
from generators.textures.procedural import ProceduralProvider
from generators.textures.ai import AIProvider
from generators.textures import factory
from generators.textures.dds import make_tileable


def _decode_dds(dds: bytes, size: int) -> np.ndarray:
    """Decode an uncompressed A8R8G8B8 DDS back to RGB."""
    assert dds[:4] == b"DDS "
    px = np.frombuffer(dds[128:], dtype=np.uint8).reshape(size, size, 4)
    return px[..., [2, 1, 0]]  # BGR -> RGB


class TestProceduralProvider:
    def test_always_available(self):
        assert ProceduralProvider().available() is True

    def test_produces_valid_dds(self):
        prov = ProceduralProvider()
        spec = TextureSpec(name="floor", kind="stone", base_color=(110, 100, 92),
                           size=128, seed=1)
        dds = prov.generate(spec)
        assert dds[:4] == b"DDS "
        # 128-byte header + size*size*4 pixels
        assert len(dds) == 128 + 128 * 128 * 4

    def test_deterministic(self):
        prov = ProceduralProvider()
        spec = TextureSpec(name="floor", kind="stone", base_color=(110, 100, 92),
                           size=64, seed=7)
        assert prov.generate(spec) == prov.generate(spec)

    def test_different_kinds_differ(self):
        prov = ProceduralProvider()
        a = prov.generate(TextureSpec(name="a", kind="stone", base_color=(100, 100, 100), size=64, seed=1))
        b = prov.generate(TextureSpec(name="b", kind="grass", base_color=(100, 100, 100), size=64, seed=1))
        assert a != b

    def test_base_color_anchors_output(self):
        prov = ProceduralProvider()
        # A dark base should produce a darker mean than a light base
        dark = _decode_dds(prov.generate(TextureSpec(name="d", kind="stone", base_color=(40, 40, 40), size=64, seed=1)), 64)
        light = _decode_dds(prov.generate(TextureSpec(name="l", kind="stone", base_color=(200, 200, 200), size=64, seed=1)), 64)
        assert dark.mean() < light.mean()


class TestTileable:
    def test_edges_match_after_tiling(self):
        rng = np.random.default_rng(0)
        img = rng.random((64, 64, 3)).astype(np.float32) * 255
        tiled = make_tileable(img, blend=0.25)
        # Left edge should be close to right edge after blending
        left = tiled[:, 0, :]
        right = tiled[:, -1, :]
        # Not identical (blend is a fade) but much closer than the raw image
        raw_diff = np.abs(img[:, 0, :] - img[:, -1, :]).mean()
        tiled_diff = np.abs(left - right).mean()
        assert tiled_diff < raw_diff


class TestFactory:
    def teardown_method(self):
        factory.set_provider(None)  # restore auto-select

    def test_default_is_procedural_without_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("STABILITY_API_KEY", raising=False)
        monkeypatch.delenv("EQ_S3D_TEXTURE_PROVIDER", raising=False)
        factory.set_provider(None)
        assert get_provider().name == "procedural"

    def test_override_forces_procedural(self, monkeypatch):
        monkeypatch.setenv("EQ_S3D_TEXTURE_PROVIDER", "procedural")
        factory.set_provider(None)
        assert get_provider().name == "procedural"

    def test_generate_texture_backcompat(self):
        dds = generate_texture("dark cave rock", (90, 82, 76), size=64, name="wall")
        assert dds[:4] == b"DDS "

    def test_caching_returns_identical(self):
        a = generate_texture("stone floor", (110, 100, 92), size=64, name="floor", seed=3)
        b = generate_texture("stone floor", (110, 100, 92), size=64, name="floor", seed=3)
        assert a == b


class TestAIProvider:
    def test_unavailable_without_keys(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("STABILITY_API_KEY", raising=False)
        assert AIProvider().available() is False

    def test_available_with_key(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        assert AIProvider().available() is True

    def test_prompt_anchors_to_eq_aesthetic(self):
        prov = AIProvider()
        spec = TextureSpec(name="wall", description="wet cave rock", kind="rock")
        prompt = prov._build_prompt(spec)
        assert "seamless" in prompt
        assert "tileable" in prompt
        assert "wet cave rock" in prompt
