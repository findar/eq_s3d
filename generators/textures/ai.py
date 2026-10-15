"""
generators/textures/ai.py
--------------------------
Reference AI texture provider. Calls an image-generation API to synthesise a
tileable texture from the spec's description, anchored to EQ's muted palette,
then encodes it to DDS.

This is a REFERENCE implementation. It activates only when an API key is
present in the environment; otherwise `available()` returns False and the
factory falls back to the procedural provider. No key is required for the
project to run.

Supported (via env var):
  OPENAI_API_KEY     → OpenAI images (gpt-image-1)
  STABILITY_API_KEY  → Stability AI

The actual network call is intentionally thin and defensive: any failure
(missing lib, network error, bad response) returns None so the caller can fall
back to procedural rather than crashing a generation.
"""

from __future__ import annotations

import os
from typing import Optional

import numpy as np

from .base import TextureProvider, TextureSpec
from .dds import rgba_to_dds, make_tileable


class AIProvider(TextureProvider):
    name = "ai"

    def __init__(self):
        self.openai_key = os.environ.get("OPENAI_API_KEY")
        self.stability_key = os.environ.get("STABILITY_API_KEY")

    def available(self) -> bool:
        return bool(self.openai_key or self.stability_key)

    def generate(self, spec: TextureSpec) -> bytes:
        img = None
        if self.openai_key:
            img = self._try_openai(spec)
        if img is None and self.stability_key:
            img = self._try_stability(spec)

        if img is None:
            # Signal failure to the factory by raising; it will fall back.
            raise RuntimeError("AI texture generation failed; no image returned")

        if spec.tileable:
            img = make_tileable(img.astype(np.float32), blend=0.18)
        return rgba_to_dds(np.clip(img, 0, 255).astype(np.uint8))

    # ------------------------------------------------------------------
    # Prompt construction — anchor to EQ's muted fantasy-stone aesthetic
    # ------------------------------------------------------------------

    def _build_prompt(self, spec: TextureSpec) -> str:
        base = spec.description or f"{spec.kind} surface"
        return (
            f"seamless tileable {base}, "
            f"top-down flat texture, no lighting, no shadows, no perspective, "
            f"muted desaturated earth tones, matte, "
            f"late-1990s fantasy MMO game texture, low contrast, "
            f"consistent repeating pattern"
        )

    # ------------------------------------------------------------------
    # Providers — each returns an (H, W, 3) uint8 array or None on failure
    # ------------------------------------------------------------------

    def _try_openai(self, spec: TextureSpec) -> Optional[np.ndarray]:
        try:
            from openai import OpenAI
            import base64
            from io import BytesIO
            from PIL import Image

            client = OpenAI(api_key=self.openai_key)
            result = client.images.generate(
                model="gpt-image-1",
                prompt=self._build_prompt(spec),
                size="1024x1024",
                n=1,
            )
            b64 = result.data[0].b64_json
            raw = base64.b64decode(b64)
            img = Image.open(BytesIO(raw)).convert("RGB")
            img = img.resize((spec.size, spec.size), Image.LANCZOS)
            return np.asarray(img, dtype=np.uint8)
        except Exception as e:
            print(f"[textures.ai] OpenAI generation failed: {e}")
            return None

    def _try_stability(self, spec: TextureSpec) -> Optional[np.ndarray]:
        try:
            import requests
            from io import BytesIO
            from PIL import Image

            resp = requests.post(
                "https://api.stability.ai/v2beta/stable-image/generate/core",
                headers={
                    "Authorization": f"Bearer {self.stability_key}",
                    "Accept": "image/*",
                },
                files={"none": ""},
                data={
                    "prompt": self._build_prompt(spec),
                    "output_format": "png",
                    "aspect_ratio": "1:1",
                },
                timeout=60,
            )
            if resp.status_code != 200:
                print(f"[textures.ai] Stability error {resp.status_code}: {resp.text[:200]}")
                return None
            img = Image.open(BytesIO(resp.content)).convert("RGB")
            img = img.resize((spec.size, spec.size), Image.LANCZOS)
            return np.asarray(img, dtype=np.uint8)
        except Exception as e:
            print(f"[textures.ai] Stability generation failed: {e}")
            return None
