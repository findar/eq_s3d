"""
tests/test_env.py
-----------------
Unit tests for ``core.env.env_value`` (Req 10.2).

Pin the precedence contract: ``os.environ`` wins, then the project ``.env`` via
``dotenv_values`` (which does not mutate the process environment), then the
default. The critical no-leak invariant is that ``env_value`` NEVER mutates
``os.environ`` — reading a value from ``.env`` must not copy it into the process
environment, or the ``no_api_keys`` fixture (and the no-API-by-default
north-star) would break.
"""

from __future__ import annotations

import os

import core.env
from core.env import env_value


def _write_env(path, **pairs):
    path.write_text("\n".join(f"{k}={v}" for k, v in pairs.items()) + "\n")


def test_env_precedence_and_no_mutation(tmp_path, monkeypatch):
    """os.environ wins over .env; .env is the fallback; default is last; and
    os.environ is never mutated by env_value."""
    dotenv_file = tmp_path / ".env"
    _write_env(dotenv_file, EQ_S3D_TEST_KEY="from-dotenv")
    monkeypatch.setattr(core.env, "DOTENV_PATH", dotenv_file)

    # Make sure the key is absent from the real environment to start.
    monkeypatch.delenv("EQ_S3D_TEST_KEY", raising=False)
    before = dict(os.environ)

    # 1. os.environ wins over the .env value.
    monkeypatch.setenv("EQ_S3D_TEST_KEY", "from-environ")
    assert env_value("EQ_S3D_TEST_KEY") == "from-environ"

    # 2. With the env var absent, fall back to the .env value.
    monkeypatch.delenv("EQ_S3D_TEST_KEY", raising=False)
    assert env_value("EQ_S3D_TEST_KEY") == "from-dotenv"

    # 3. Default when neither source has the key.
    assert env_value("EQ_S3D_MISSING_KEY", "the-default") == "the-default"
    assert env_value("EQ_S3D_MISSING_KEY") is None

    # 4. Reading the .env value did NOT copy it into os.environ.
    assert "EQ_S3D_TEST_KEY" not in os.environ
    before.pop("EQ_S3D_TEST_KEY", None)
    assert dict(os.environ) == before


def test_env_value_returns_default_when_dotenv_missing(tmp_path, monkeypatch):
    """No-API-by-default: a missing .env and absent env var yields the default,
    so the rule planner / procedural textures run with zero keys."""
    monkeypatch.setattr(core.env, "DOTENV_PATH", tmp_path / ".env.does-not-exist")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert env_value("OPENAI_API_KEY") is None
    assert env_value("OPENAI_API_KEY", "fallback") == "fallback"
    assert "OPENAI_API_KEY" not in os.environ
