"""
tests/conftest.py
-----------------
Shared pytest configuration for the Property_Suite and the rest of the tests.

Two responsibilities (M0 design, "tests/conftest.py"):

1. Hypothesis profiles. Registered at import time, before the Hypothesis
   plugin's ``pytest_configure`` applies ``--hypothesis-profile``, so that
   ``default`` is active for the Default_Run and ``thorough`` is available via
   ``--hypothesis-profile thorough``. ``default`` uses ``derandomize=True`` and
   ``database=None`` so two runs on the same commit evaluate the same examples
   with no replay of a saved failure.

2. Fixtures for the no-API / no-network properties (P16): ``no_api_keys`` and
   ``no_network``.
"""

from __future__ import annotations

import os
import socket

import pytest
from hypothesis import settings

# ---------------------------------------------------------------------------
# 1. Hypothesis profiles (registered at import, before profile selection)
# ---------------------------------------------------------------------------

settings.register_profile(
    "default",
    max_examples=100,
    derandomize=True,
    database=None,
    deadline=200,
)
settings.register_profile(
    "thorough",
    max_examples=500,
    derandomize=False,
    deadline=None,
)  # default DirectoryBasedExampleDatabase
settings.load_profile("default")


# ---------------------------------------------------------------------------
# 2. Fixtures
# ---------------------------------------------------------------------------

# API-key environment variables the no_api_keys fixture clears.
_API_ENV_VARS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "STABILITY_API_KEY",
    "EQ_S3D_PLANNER",
    "EQ_S3D_TEXTURE_PROVIDER",
)


@pytest.fixture
def no_api_keys(monkeypatch):
    """Guarantee the no-API default selection path.

    Deletes every API-key / provider-override environment variable and resets
    the forced planner and texture provider to ``None`` so auto-selection runs
    with no key present. Keys are read through ``core.env.env_value`` (``os``
    environment first, then ``.env``); this fixture also points
    ``core.env.DOTENV_PATH`` at a missing file so a developer's real ``.env``
    can never leak a key into a test asserting no-key behaviour.
    """
    import ai.planner
    import core.env
    import generators.textures.factory as texture_factory

    for name in _API_ENV_VARS:
        monkeypatch.delenv(name, raising=False)

    # Neutralise the project .env: point the reader at a path that does not
    # exist, so dotenv_values() returns an empty mapping.
    monkeypatch.setattr(core.env, "DOTENV_PATH", core.env.DOTENV_PATH.parent / ".env.nonexistent-for-tests")

    ai.planner.set_planner(None)
    texture_factory.set_provider(None)
    try:
        yield
    finally:
        # Restore auto-select so a forced value can't leak into other tests.
        ai.planner.set_planner(None)
        texture_factory.set_provider(None)


# Loopback host strings that always pass through the network guard.
_LOOPBACK_HOSTS = frozenset({"localhost", "::1", "ip6-localhost"})


def _host_of(address):
    """Extract the host component of a socket address, or None for AF_UNIX /
    unrecognised shapes (which are treated as loopback / pass-through)."""
    if isinstance(address, (str, bytes)):
        # AF_UNIX path — not a network target.
        return None
    if isinstance(address, (tuple, list)) and address:
        return address[0]
    return None


def _is_loopback(address) -> bool:
    """True if the address is loopback or a non-network (AF_UNIX) target.

    Loopback is 127.0.0.0/8, ``::1`` and the localhost host strings. On Windows
    ``socket.socketpair()`` connects over loopback, and the anyio portal
    TestClient starts creates one, so these must pass through (finding 4).
    """
    host = _host_of(address)
    if host is None:
        # AF_UNIX or an unrecognised shape — not a reachable network target.
        return True
    host = str(host)
    if host in _LOOPBACK_HOSTS:
        return True
    if host.startswith("127."):
        return True
    if host == "::1":
        return True
    # IPv4-mapped loopback, e.g. "::ffff:127.0.0.1".
    if host.lower().startswith("::ffff:127."):
        return True
    return False


@pytest.fixture
def no_network(monkeypatch):
    """Block every non-loopback network operation and record the attempt.

    Patches ``socket.socket.connect``, ``socket.socket.connect_ex``,
    ``socket.socket.bind`` and ``socket.getaddrinfo``. Loopback
    (127.0.0.0/8, ``::1``, ``localhost``) and AF_UNIX pass through to the real
    implementation; anything else is appended to the yielded ``attempts`` list
    and raises ``OSError``. ``bind`` records non-loopback binds the same way, so
    Req 8.3 / 8.4 can assert that no foreign listener opens. Tests assert
    ``attempts == []``.
    """
    attempts: list = []

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_bind = socket.socket.bind
    real_getaddrinfo = socket.getaddrinfo

    def guarded_connect(self, address, *args, **kwargs):
        if _is_loopback(address):
            return real_connect(self, address, *args, **kwargs)
        attempts.append(("connect", address))
        raise OSError("no_network: blocked connect to %r" % (address,))

    def guarded_connect_ex(self, address, *args, **kwargs):
        if _is_loopback(address):
            return real_connect_ex(self, address, *args, **kwargs)
        attempts.append(("connect_ex", address))
        raise OSError("no_network: blocked connect_ex to %r" % (address,))

    def guarded_bind(self, address, *args, **kwargs):
        if _is_loopback(address):
            return real_bind(self, address, *args, **kwargs)
        attempts.append(("bind", address))
        raise OSError("no_network: blocked bind to %r" % (address,))

    def guarded_getaddrinfo(host, *args, **kwargs):
        if host is None or _is_loopback((host, None)):
            return real_getaddrinfo(host, *args, **kwargs)
        attempts.append(("getaddrinfo", host))
        raise OSError("no_network: blocked getaddrinfo for %r" % (host,))

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket.socket, "bind", guarded_bind)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)

    yield attempts


# ---------------------------------------------------------------------------
# 3. Isolation from the developer's shell
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True, scope="session")
def _no_dev_wilderness_flag():
    """Run every test with the dev-only wilderness override OFF.

    ``EQ_S3D_DEV_WILDERNESS=1`` is set in the shell that runs the server, so it
    can leak into a suite run from that shell and flip "wilderness is disabled"
    assertions. Tests that want it on set it themselves (monkeypatch.setenv).
    Session-scoped so Hypothesis tests don't see a function-scoped fixture.
    """
    saved = os.environ.pop("EQ_S3D_DEV_WILDERNESS", None)
    yield
    if saved is not None:
        os.environ["EQ_S3D_DEV_WILDERNESS"] = saved
