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


@pytest.fixture
def client(set_env):
    # Re-import app after env is set so db.py reads the patched DB_PATH
    import importlib
    import app.db
    import app.main
    importlib.reload(app.db)
    importlib.reload(app.main)
    from app.main import app
    with TestClient(app) as c:
        yield c
