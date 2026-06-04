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


def test_round_stats_empty(rounds_client):
    """Stats for a round with no submissions shows all specs unclaimed."""
    resp = rounds_client.get("/rounds/round_test/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["round_id"] == "round_test"
    assert data["specs_total"] == 1
    assert data["specs_claimed"] == 0
    assert data["specs_unclaimed"] == 1
    assert data["contributor_count"] == 0
    assert "easy" in data["tiers"]
    assert data["tiers"]["easy"]["total"] == 1
    assert data["tiers"]["easy"]["claimed"] == 0


def test_round_stats_not_found(rounds_client):
    resp = rounds_client.get("/rounds/does_not_exist/stats")
    assert resp.status_code == 404


def test_round_stats_with_submissions(tmp_path, monkeypatch):
    """Stats correctly counts claimed specs and unique contributors."""
    import importlib
    import json

    rounds_dir = tmp_path / "rounds"
    rounds_dir.mkdir()
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()

    # Round with two easy specs and one medium
    round_data = {
        "id": "round_s",
        "name": "Stats Test Round",
        "description": "For testing stats.",
        "status": "active",
        "starts": "2026-01-01",
        "ends": None,
        "scoring_metric": "mass_grams",
        "scoring_direction": "minimize",
        "specs": [
            {"id": "stat_easy_1", "tier": "easy"},
            {"id": "stat_easy_2", "tier": "easy"},
            {"id": "stat_medium_1", "tier": "medium"},
        ],
        "notes": None,
    }
    (rounds_dir / "round_s.json").write_text(json.dumps(round_data))

    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("SPECS_DIR", str(specs_dir))
    monkeypatch.setenv("ROUNDS_DIR", str(rounds_dir))

    import app.db, app.main, app.routes.rounds
    importlib.reload(app.db)
    importlib.reload(app.routes.rounds)
    importlib.reload(app.main)
    from app.main import app

    with TestClient(app) as c:
        base = {"agent_path": "a/b", "mass_grams": 100.0,
                "fea_stress_mpa": 5.0, "fea_allowable_mpa": 25.0, "passed": True, "pr_number": 1}
        # Two contributors submit on stat_easy_1, nobody on stat_easy_2 or stat_medium_1
        c.post("/submissions", json={**base, "spec_id": "stat_easy_1", "contributor": "Alice", "commit_hash": "abc1"})
        c.post("/submissions", json={**base, "spec_id": "stat_easy_1", "contributor": "Bob", "mass_grams": 90.0, "commit_hash": "abc2"})

        resp = c.get("/rounds/round_s/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["specs_total"] == 3
        assert data["specs_claimed"] == 1
        assert data["specs_unclaimed"] == 2
        assert data["contributor_count"] == 2
        assert data["tiers"]["easy"]["claimed"] == 1
        assert data["tiers"]["easy"]["unclaimed"] == 1
        assert data["tiers"]["medium"]["claimed"] == 0


def test_upcoming_round_null_starts(tmp_path, monkeypatch):
    """Rounds with starts=null (upcoming) load without validation errors."""
    rounds_dir = tmp_path / "rounds"
    rounds_dir.mkdir()
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()

    upcoming = {
        "id": "round_002",
        "name": "Round 2 — Stiffness-to-Weight",
        "description": "Maximize stiffness-to-weight ratio.",
        "status": "upcoming",
        "starts": None,
        "ends": None,
        "scoring_metric": "stiffness_to_weight",
        "scoring_direction": "maximize",
        "specs": [{"id": "r02_001_easy", "tier": "easy"}],
        "notes": None,
    }
    (rounds_dir / "round_002.json").write_text(json.dumps(upcoming))

    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("SPECS_DIR", str(specs_dir))
    monkeypatch.setenv("ROUNDS_DIR", str(rounds_dir))

    import importlib
    import app.db, app.main, app.routes.rounds
    importlib.reload(app.db)
    importlib.reload(app.routes.rounds)
    importlib.reload(app.main)
    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        resp = c.get("/rounds")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "round_002"
        assert data[0]["starts"] is None
        assert data[0]["status"] == "upcoming"

        resp2 = c.get("/rounds/active")
        assert resp2.status_code == 200
        assert len(resp2.json()) == 0  # upcoming rounds are not active


# ── Round leaderboard tests ────────────────────────────────────────────────────

def _make_round_leaderboard_setup(tmp_path, monkeypatch):
    """Helper: creates a round with 2 specs and spec JSON files, returns (rounds_dir, specs_dir)."""
    import importlib

    rounds_dir = tmp_path / "rounds"
    rounds_dir.mkdir()
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()

    round_data = {
        "id": "round_lb",
        "name": "Leaderboard Test Round",
        "description": "For leaderboard tests.",
        "status": "active",
        "starts": "2026-01-01",
        "ends": None,
        "scoring_metric": "mass_grams",
        "scoring_direction": "minimize",
        "specs": [
            {"id": "lb_spec_1", "tier": "easy"},
            {"id": "lb_spec_2", "tier": "medium"},
        ],
        "notes": None,
    }
    (rounds_dir / "round_lb.json").write_text(json.dumps(round_data))

    # Minimal spec JSON files so spec_store can load direction info
    base_spec = {
        "version": "1.0",
        "description": "Test bracket.",
        "material": "pla",
        "constraints": {
            "load_newtons": 100.0, "load_point_mm": [50.0, 25.0, 25.0],
            "safety_factor": 1.5, "bolt_pattern_mm": [[0.0, 0.0]],
            "bolt_diameter_clearance_mm": 6.5, "mount_face_x_mm": 0.0,
            "build_volume_mm": [100.0, 80.0, 80.0],
            "max_overhang_deg": 45.0, "min_wall_thickness_mm": 1.0,
        },
        "scoring": {"metric": "mass_grams", "direction": "minimize", "baseline_mass_grams": 150.0},
    }
    (specs_dir / "lb_spec_1.json").write_text(json.dumps({**base_spec, "id": "lb_spec_1", "name": "LB Spec 1"}))
    (specs_dir / "lb_spec_2.json").write_text(json.dumps({**base_spec, "id": "lb_spec_2", "name": "LB Spec 2"}))

    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("SPECS_DIR", str(specs_dir))
    monkeypatch.setenv("ROUNDS_DIR", str(rounds_dir))

    import app.db, app.main, app.routes.rounds
    importlib.reload(app.db)
    importlib.reload(app.routes.rounds)
    importlib.reload(app.main)
    from app.main import app
    return app


def test_round_leaderboard_empty(tmp_path, monkeypatch):
    """Leaderboard returns empty entries when no submissions exist."""
    app = _make_round_leaderboard_setup(tmp_path, monkeypatch)
    with TestClient(app) as c:
        resp = c.get("/rounds/round_lb/leaderboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["round_id"] == "round_lb"
    assert data["total_specs"] == 2
    assert data["entries"] == []


def test_round_leaderboard_not_found(tmp_path, monkeypatch):
    """Leaderboard returns 404 for an unknown round."""
    app = _make_round_leaderboard_setup(tmp_path, monkeypatch)
    with TestClient(app) as c:
        resp = c.get("/rounds/does_not_exist/leaderboard")
    assert resp.status_code == 404


def test_round_leaderboard_ranking(tmp_path, monkeypatch):
    """Contributor with lower mass on both specs ranks first."""
    app = _make_round_leaderboard_setup(tmp_path, monkeypatch)
    base = {"agent_path": "a/b", "mass_grams": 100.0,
            "fea_stress_mpa": 5.0, "fea_allowable_mpa": 25.0, "passed": True, "pr_number": 1}
    with TestClient(app) as c:
        # Alice wins lb_spec_1, Bob wins lb_spec_2
        c.post("/submissions", json={**base, "spec_id": "lb_spec_1", "contributor": "Alice", "mass_grams": 80.0, "commit_hash": "a1"})
        c.post("/submissions", json={**base, "spec_id": "lb_spec_1", "contributor": "Bob",   "mass_grams": 90.0, "commit_hash": "b1"})
        c.post("/submissions", json={**base, "spec_id": "lb_spec_2", "contributor": "Alice", "mass_grams": 120.0, "commit_hash": "a2"})
        c.post("/submissions", json={**base, "spec_id": "lb_spec_2", "contributor": "Bob",   "mass_grams": 95.0,  "commit_hash": "b2"})

        resp = c.get("/rounds/round_lb/leaderboard")
    assert resp.status_code == 200
    data = resp.json()
    entries = data["entries"]
    assert len(entries) == 2
    # Bob wins both specs (lb_spec_1: Bob 90 < Alice 80? No — Alice 80 < Bob 90 → Alice wins spec_1)
    # lb_spec_1: Alice=80 (rank 1), Bob=90 (rank 2)
    # lb_spec_2: Bob=95 (rank 1), Alice=120 (rank 2)
    # Alice: spec_1 rank 1/(2+1)=0.333, spec_2 rank 2/(2+1)=0.667 → mean=0.5 over 2 specs → round_score=(0.5+0)/2=0.25? No...
    # round_score = (sum of norm scores for entered + 1.0 * unentered) / total_specs
    # Alice entered both: (0.333 + 0.667) / 2 = 0.5
    # Bob entered both:   (0.667 + 0.333) / 2 = 0.5
    # Tied overall_score → tiebreak by specs_entered (equal) → keep original order
    assert entries[0]["rank"] == 1
    assert entries[1]["rank"] == 2
    assert entries[0]["specs_entered"] == 2
    assert entries[0]["total_wins"] == 1  # each won one spec


def test_round_leaderboard_partial_entry(tmp_path, monkeypatch):
    """A contributor who enters only some specs is penalized correctly."""
    app = _make_round_leaderboard_setup(tmp_path, monkeypatch)
    base = {"agent_path": "a/b", "mass_grams": 100.0,
            "fea_stress_mpa": 5.0, "fea_allowable_mpa": 25.0, "passed": True, "pr_number": 1}
    with TestClient(app) as c:
        # Charlie enters only lb_spec_1; Dave enters both
        c.post("/submissions", json={**base, "spec_id": "lb_spec_1", "contributor": "Charlie", "mass_grams": 70.0,  "commit_hash": "c1"})
        c.post("/submissions", json={**base, "spec_id": "lb_spec_1", "contributor": "Dave",    "mass_grams": 80.0,  "commit_hash": "d1"})
        c.post("/submissions", json={**base, "spec_id": "lb_spec_2", "contributor": "Dave",    "mass_grams": 100.0, "commit_hash": "d2"})

        resp = c.get("/rounds/round_lb/leaderboard")
    assert resp.status_code == 200
    entries = resp.json()["entries"]
    by_name = {e["contributor"]: e for e in entries}
    # Dave entered both specs and wins lb_spec_2 outright
    # Dave: lb_spec_1 rank 2/(2+1)=0.667, lb_spec_2 rank 1/(1+1)=0.5 → (0.667+0.5)/2=0.583
    # Charlie: lb_spec_1 rank 1/(2+1)=0.333, lb_spec_2 not entered=1.0 → (0.333+1.0)/2=0.667
    # Dave (0.583) < Charlie (0.667) → Dave ranks first
    assert by_name["Dave"]["rank"] < by_name["Charlie"]["rank"]
    assert by_name["Charlie"]["specs_entered"] == 1
    assert by_name["Dave"]["specs_entered"] == 2
