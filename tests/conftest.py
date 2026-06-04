import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Use a temp file per test so each test gets a fresh DB
# (in-memory SQLite doesn't share state across aiosqlite connections)


@pytest.fixture(autouse=True)
def set_env(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("SPECS_DIR", "tests/fixtures/specs")


def _make_client():
    import importlib
    import app.db
    import app.specs
    import app.routes.specs
    import app.main
    importlib.reload(app.db)
    importlib.reload(app.specs)
    importlib.reload(app.routes.specs)
    importlib.reload(app.main)
    from app.main import app
    return TestClient(app)


@pytest.fixture
def client(set_env):
    # Re-import app after env is set so db.py reads the patched DB_PATH
    with _make_client() as c:
        yield c


@pytest.fixture
def unclaimed_client(tmp_path, monkeypatch):
    """Client with an active round configured (needed for ?unclaimed= filter tests).

    Uses specs_round/ fixtures (r01_001_easy has round_id=round_001 via ID prefix)
    and rounds_active/ so the round is active. The ?unclaimed filter restricts to
    active-round specs only.
    """
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("SPECS_DIR", "tests/fixtures/specs_round")
    monkeypatch.setenv("ROUNDS_DIR", "tests/fixtures/rounds_active")
    with _make_client() as c:
        yield c
