"""Tests for GET /health and GET /health/deep."""

import json
import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def deep_client(tmp_path, monkeypatch):
    rounds_dir = tmp_path / "rounds"
    rounds_dir.mkdir()
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()

    round_data = {
        "id": "round_001",
        "name": "Round 001",
        "description": "Minimize mass.",
        "status": "active",
        "starts": "2026-01-01",
        "ends": None,
        "scoring_metric": "mass_grams",
        "scoring_direction": "minimize",
        "specs": [{"id": "spec_001", "tier": "easy"}],
        "notes": None,
    }
    (rounds_dir / "round_001.json").write_text(json.dumps(round_data))

    spec_data = {
        "id": "spec_001",
        "version": "1.0",
        "name": "Test Bracket",
        "description": "Test spec.",
        "material": "aluminum",
        "constraints": {
            "load_newtons": 500.0,
            "load_point_mm": [60.0, 40.0, 60.0],
            "safety_factor": 2.0,
            "bolt_pattern_mm": [[0.0, 0.0], [60.0, 0.0]],
            "bolt_diameter_clearance_mm": 6.5,
            "mount_face_x_mm": 0.0,
            "build_volume_mm": [120.0, 80.0, 60.0],
            "max_overhang_deg": 45.0,
            "min_wall_thickness_mm": 1.2,
        },
        "scoring": {"metric": "mass_grams", "direction": "minimize", "baseline_mass_grams": 100.0},
    }
    (specs_dir / "spec_001.json").write_text(json.dumps(spec_data))

    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("SPECS_DIR", str(specs_dir))
    monkeypatch.setenv("ROUNDS_DIR", str(rounds_dir))

    import app.db, app.main, app.routes.health, app.routes.rounds, app.specs
    importlib.reload(app.db)
    importlib.reload(app.specs)
    importlib.reload(app.routes.rounds)
    importlib.reload(app.routes.health)
    importlib.reload(app.main)
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_health_shallow(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_health_deep_ok(deep_client):
    r = deep_client.get("/health/deep")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["checks"]["db"]["status"] == "ok"
    assert body["checks"]["rounds"]["status"] == "ok"
    assert body["checks"]["rounds"]["total"] == 1
    assert "round_001" in body["checks"]["rounds"]["active"]
    assert body["checks"]["specs"]["status"] == "ok"
    assert body["checks"]["specs"]["total"] == 1


def test_health_deep_empty_rounds(tmp_path, monkeypatch):
    """Degraded when no rounds are loaded."""
    rounds_dir = tmp_path / "rounds"
    rounds_dir.mkdir()
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()

    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("SPECS_DIR", str(specs_dir))
    monkeypatch.setenv("ROUNDS_DIR", str(rounds_dir))

    import app.db, app.main, app.routes.health, app.routes.rounds, app.specs
    importlib.reload(app.db)
    importlib.reload(app.specs)
    importlib.reload(app.routes.rounds)
    importlib.reload(app.routes.health)
    importlib.reload(app.main)
    from app.main import app
    with TestClient(app) as c:
        r = c.get("/health/deep")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "degraded"
    assert body["checks"]["rounds"]["status"] == "warn"
