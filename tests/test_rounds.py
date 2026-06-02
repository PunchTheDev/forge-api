"""Tests for GET /rounds, /rounds/active, /rounds/{id}."""

import json
import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def rounds_client(tmp_path, monkeypatch):
    """Client with a temp rounds dir containing one active round."""
    rounds_dir = tmp_path / "rounds"
    rounds_dir.mkdir()
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()

    round_data = {
        "id": "round_test",
        "name": "Test Round",
        "description": "A round for testing.",
        "status": "active",
        "starts": "2026-01-01",
        "ends": None,
        "scoring_metric": "mass_grams",
        "scoring_direction": "minimize",
        "specs": [
            {"id": "r_001_easy", "tier": "easy", "file": "specs/round_001/r_001_easy.json"},
        ],
        "notes": None,
    }
    (rounds_dir / "round_test.json").write_text(json.dumps(round_data))

    archived = dict(round_data, id="round_old", status="archived")
    (rounds_dir / "round_old.json").write_text(json.dumps(archived))

    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("SPECS_DIR", str(specs_dir))
    monkeypatch.setenv("ROUNDS_DIR", str(rounds_dir))

    import app.db
    import app.main
    import app.routes.rounds
    importlib.reload(app.db)
    importlib.reload(app.routes.rounds)
    importlib.reload(app.main)
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_list_rounds(rounds_client):
    resp = rounds_client.get("/rounds")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    ids = {r["id"] for r in data}
    assert "round_test" in ids
    assert "round_old" in ids


def test_list_active_rounds(rounds_client):
    resp = rounds_client.get("/rounds/active")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "round_test"
    assert data[0]["status"] == "active"


def test_get_round(rounds_client):
    resp = rounds_client.get("/rounds/round_test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "round_test"
    assert data["scoring_metric"] == "mass_grams"
    assert len(data["specs"]) == 1
    assert data["specs"][0]["tier"] == "easy"


def test_get_round_not_found(rounds_client):
    resp = rounds_client.get("/rounds/does_not_exist")
    assert resp.status_code == 404


def test_round_specs_structure(rounds_client):
    resp = rounds_client.get("/rounds/round_test")
    specs = resp.json()["specs"]
    assert specs[0]["id"] == "r_001_easy"
    assert specs[0]["tier"] == "easy"
    assert "file" in specs[0]
