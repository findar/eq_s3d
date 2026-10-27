"""
core/env.py
-----------
Read configuration values from the process environment, with a non-mutating
fall back to the project ``.env`` file.

``python-dotenv`` is pinned but was historically unused (design finding 7). We
deliberately do NOT call ``load_dotenv()`` — that would copy ``.env`` entries
into ``os.environ`` and defeat the ``no_api_keys`` test fixture. Instead
``env_value`` reads ``os.environ`` first and, only if a key is absent there,
consults ``dotenv_values(DOTENV_PATH)``, which parses the file WITHOUT touching
the process environment.

``DOTENV_PATH`` is a module-level attribute on purpose so tests can monkeypatch
it to a missing file and prove that a developer's real ``.env`` can never leak a
key into a test asserting no-key behaviour, and so the no-API-by-default
north-star holds when neither source has the key.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from dotenv import dotenv_values

# Project .env lives at the repo root (one level above core/).
DOTENV_PATH: Path = Path(__file__).resolve().parent.parent / ".env"


def env_value(name: str, default: Optional[str] = None) -> Optional[str]:
    """Return a configuration value: ``os.environ`` first, then ``.env``.

    Reads ``os.environ`` first so an explicitly set environment variable always
    wins. Only if the key is absent there does it fall back to
    ``dotenv_values(DOTENV_PATH)`` (which parses the file and never mutates the
    process environment). Returns ``default`` when neither source has the key.

    This function NEVER mutates ``os.environ`` — no ``load_dotenv()`` is called.
    """
    import os

    if name in os.environ:
        return os.environ[name]

    try:
        values = dotenv_values(DOTENV_PATH)
    except Exception:
        values = {}
    value = values.get(name)
    if value is not None:
        return value
    return default
