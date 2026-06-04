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


def test_health_deep_storage_sqlite(deep_client, monkeypatch):
    """Storage check reports sqlite_blob backend when S3_BUCKET is not set."""
    monkeypatch.delenv("S3_BUCKET", raising=False)

    import app.storage, app.routes.health
    importlib.reload(app.storage)
    importlib.reload(app.routes.health)

    r = deep_client.get("/health/deep")
    assert r.status_code == 200
    body = r.json()
    assert body["checks"]["storage"]["status"] == "ok"
    assert body["checks"]["storage"]["backend"] == "sqlite_blob"


def test_health_deep_storage_s3_error(deep_client, monkeypatch):
    """Storage check reports error when S3_BUCKET is set but bucket is unreachable."""
    monkeypatch.setenv("S3_BUCKET", "nonexistent-test-bucket")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")

    import app.storage, app.routes.health
    importlib.reload(app.storage)
    importlib.reload(app.routes.health)

    r = deep_client.get("/health/deep")
    assert r.status_code == 200
    body = r.json()
    assert body["checks"]["storage"]["status"] == "error"
    assert body["checks"]["storage"]["backend"] == "s3"
    assert body["status"] == "degraded"


def test_root_discovery(client):
    """Bare root returns a discovery payload, not 404, so agents can navigate."""
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Forge API"
    assert "version" in body
    assert body["docs"]["swagger"] == "/docs"
    assert body["docs"]["openapi"] == "/openapi.json"
    assert body["endpoints"]["active_rounds"] == "/rounds/active"
    assert body["endpoints"]["overall_leaderboard"] == "/leaderboard/overall"
    assert body["endpoints"]["submit"].startswith("POST")
    assert "quickstart" in body
    # Canonical submission path: PR-based, with direct POST clearly marked as secondary.
    assert body["repo"] == "https://github.com/PunchTheDev/forge"
    assert "canonical" in body["agent_submission"]
    assert "pull request" in body["agent_submission"]["canonical"].lower()
    assert "direct_post" in body["agent_submission"]
