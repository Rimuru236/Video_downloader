"""
Pytest configuration for the backend test suite (TEST-2).

Isolates every test in this suite against a fresh temp SQLite DB and a
fresh temp config.json — never the real project's streamvault.db or
config/config.json. This is a session-scoped setup done once, not per-test,
so individual tests must use unique IDs (uuid4 etc.) rather than relying on
a clean slate, and any test that mutates a *global* setting (api_key,
cors_origins, api_rate_limit_per_min, ...) must reset it in a `finally`
block so it doesn't leak into unrelated tests later in the same session.

This mirrors the pattern used by the ad-hoc scratch scripts written earlier
in this review (e2e_test.py, sec1_test.py, etc.) — formalized here as the
real, checked-in test suite instead of one-off scripts, per TEST-2.
"""
import asyncio
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# ── Isolated environment — must happen before any backend module is
# imported, since e.g. database/db_manager.py reads database_url at import
# time to construct the engine. conftest.py's module body runs during
# pytest's early plugin/conftest discovery, well before any test module
# (or `main`, or `database.db_manager`) gets imported, so this is the
# correct place for it.
_TMP_DIR = tempfile.mkdtemp(prefix="sv_pytest_")
os.environ["SV_DATABASE_URL"] = f"sqlite+aiosqlite:///{os.path.join(_TMP_DIR, 'test.db')}"
os.environ["SV_DOWNLOAD_FOLDER"] = os.path.join(_TMP_DIR, "downloads")
os.makedirs(os.environ["SV_DOWNLOAD_FOLDER"], exist_ok=True)

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
os.chdir(_PROJECT_ROOT)

import config.config_manager as _cfgmod  # noqa: E402
_cfgmod.CONFIG_PATH = Path(os.path.join(_TMP_DIR, "config.json"))


def pytest_sessionstart(session):
    from database.db_manager import init_db
    asyncio.run(init_db())


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TMP_DIR, ignore_errors=True)


@pytest.fixture(scope="session")
def tmp_dir():
    """The session's isolated scratch directory — for tests that need a
    real file on disk (e.g. FE-2's file-serving, REL-3's delete_files)."""
    return _TMP_DIR


@pytest.fixture(scope="session")
def app():
    import main as app_module
    return app_module.app


@pytest.fixture(scope="session")
def client(app):
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture
def cfg():
    from config.config_manager import ConfigManager
    return ConfigManager()


def run_async(coro):
    """Small helper so test functions can stay plain `def` (no
    pytest-asyncio dependency) while still calling async backend code."""
    return asyncio.run(coro)
