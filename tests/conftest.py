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

3. ``shared_results``: results the gate sweeps share across xdist workers
   (world-sockets task 13), on disk under the session's temp root.
"""

from __future__ import annotations

import hashlib
import os
import pickle
import socket
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Hashable, List, Sequence

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

@pytest.fixture(autouse=True)
def _restore_tempdir():
    """`main.main(["generate", ...])` points the process-wide
    `tempfile.tempdir` at its output's `.tmp`, which a test's `tmp_path`
    deletes later; every later test on that worker then fails in scipy's temp
    files with FileNotFoundError. Put it back after each test."""
    import tempfile
    saved = tempfile.tempdir
    yield
    tempfile.tempdir = saved


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
# 3. Results shared across xdist workers (world-sockets task 13)
# ---------------------------------------------------------------------------

class SharedResults:
    """A memo every worker of one pytest session shares, ON DISK.

    xdist workers are separate processes, so a session fixture's memory is per
    worker: two sweep tests needing the same build on two workers would each
    make it. Here a result lives in a pickle under the session's temp root
    (``pytest-N/shared-results``, new each session, so a code change between
    runs can never be read back stale).

    ``get_many(keys, compute)`` claims each key it can (an ``O_EXCL`` lock file)
    and computes it, skips a key another worker is computing, then waits for
    those. A sweep split into many small tests is so made by every worker that
    picks one up, and the test that compares the sweep's rates reads what they
    made (and makes what nobody has started). A claimant always computes before
    it waits, so two workers never wait on each other. A claimant that fails
    drops its lock and re-raises; a waiter then claims the key and computes it
    (its own failure shows in its own test).

    Readers can't change a shared result: every read unpickles a fresh copy, and
    the claimant hands its caller an unpickled copy too.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _paths(self, key: Hashable):
        h = hashlib.sha1(repr(key).encode("utf-8")).hexdigest()[:24]
        return self.root / f"{h}.pkl", self.root / f"{h}.lock"

    @staticmethod
    def _load(path: Path):
        return pickle.loads(path.read_bytes())

    def _claim(self, lock: Path) -> bool:
        try:
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return True
        except FileExistsError:
            return False

    def _compute(self, key, compute, res: Path, lock: Path):
        try:
            data = pickle.dumps(compute(key))
        except BaseException:
            lock.unlink(missing_ok=True)
            raise
        tmp = res.with_name(f"{res.name}.{os.getpid()}.tmp")
        tmp.write_bytes(data)
        os.replace(tmp, res)
        return pickle.loads(data)

    def get_many(self, keys: Sequence[Hashable], compute: Callable, *,
                 timeout_s: float = 3600.0) -> List:
        out, waiting = {}, []
        for key in dict.fromkeys(keys):
            res, lock = self._paths(key)
            if res.exists():
                out[key] = self._load(res)
            elif self._claim(lock):
                out[key] = self._compute(key, compute, res, lock)
            else:
                waiting.append(key)
        for key in waiting:
            res, lock = self._paths(key)
            start = time.monotonic()
            while not res.exists():
                if not lock.exists() or time.monotonic() - start > timeout_s:
                    # The claimant failed (or hung): make it here.
                    if not lock.exists() and not self._claim(lock):
                        continue
                    out[key] = self._compute(key, compute, res, lock)
                    break
                time.sleep(0.25)
            else:
                out[key] = self._load(res)
        return [out[k] for k in keys]

    def get(self, key: Hashable, compute: Callable):
        return self.get_many([key], compute)[0]


@pytest.fixture(scope="session")
def shared_results(tmp_path_factory) -> SharedResults:
    """The session's :class:`SharedResults`. Under xdist each worker's basetemp
    is ``pytest-N/popen-gwK``; their parent is the one session root they share."""
    base = tmp_path_factory.getbasetemp()
    root = base.parent if os.environ.get("PYTEST_XDIST_WORKER") else base
    return SharedResults(root / "shared-results")


def gated_key(fields: dict, seed: int, max_attempts: int, timeout_s: float) -> tuple:
    """The :func:`gated_attempts` key for a plan of ``fields`` (``ZonePlan``
    keywords, no name) on sweep seed ``seed``. The plan is every field of the
    validated ``ZonePlan`` but its name, so two sweeps asking for one zone in
    different words (the vertical sweep's ``moderate``, the graph sweep's
    default) meet on one key, so one build."""
    from ai.schema import ZonePlan
    d = asdict(ZonePlan(name="sweep", **fields).validate())
    d.pop("name")
    plan = tuple(sorted((k, tuple(v) if isinstance(v, list) else v) for k, v in d.items()))
    return ("gated", plan, seed, max_attempts, timeout_s)


def gated_attempts(key: tuple) -> object:
    """``("gated", plan fields, seed, max_attempts, timeout_s)`` -> the pipeline's
    build -> gate -> retry loop on ``random.Random(seed)``: the attempts it took,
    or None when the budget ran out. Every sweep builds through this, so a zone
    two sweeps share is built once. The build goes in a temporary folder."""
    import random

    from ai.expand import plan_to_spec
    from ai.schema import ZonePlan
    from generators.pipeline import GenerationFailed, generate_validated

    _tag, fields, seed, max_attempts, timeout_s = key
    plan = ZonePlan(name="sweep", **{k: list(v) if isinstance(v, tuple) else v
                                     for k, v in fields}).validate()
    with tempfile.TemporaryDirectory(prefix="sweep", ignore_cleanup_errors=True) as tmp:
        try:
            vb = generate_validated(lambda s: plan_to_spec(plan, seed=s),
                                    zone_type=plan.zone_type, zone_id=plan.name,
                                    output_dir=Path(tmp), write_glb=False,
                                    rng=random.Random(seed), failure_log=None,
                                    max_attempts=max_attempts, timeout_s=timeout_s)
        except GenerationFailed:
            return None
    assert vb.validated
    return vb.attempts
