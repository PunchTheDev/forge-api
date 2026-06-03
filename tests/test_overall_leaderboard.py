"""Tests for GET /leaderboard/overall — cross-spec contributor ranking."""
import importlib

import pytest
from fastapi.testclient import TestClient


SPEC1_SUB = {
    "spec_id": "001_bracket",
    "agent_path": "agents/slim-spine",
    "contributor": "TestMiner",
    "commit_hash": "abc1234",
    "mass_grams": 108.48,
    "fea_stress_mpa": 7.50,
    "fea_allowable_mpa": 25.0,
    "passed": True,
}

SPEC2_SUB = {
    "spec_id": "002_bracket_hard",
    "agent_path": "agents/slim-spine",
    "contributor": "TestMiner",
    "commit_hash": "abc5678",
    "mass_grams": 160.0,
    "fea_stress_mpa": 8.0,
    "fea_allowable_mpa": 25.0,
    "passed": True,
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Override env vars; reload affected modules so module-level constants pick up changes.
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("SPECS_DIR", "tests/fixtures/specs_multi")
    monkeypatch.setenv("ROUNDS_DIR", "tests/fixtures/rounds_multi")
    import app.db
    import app.specs
    import app.routes.rounds
    import app.routes.leaderboard
    import app.main
    importlib.reload(app.db)
    importlib.reload(app.specs)
    importlib.reload(app.routes.rounds)
    importlib.reload(app.routes.leaderboard)
    importlib.reload(app.main)
    from app.main import app
    with TestClient(app) as c:
        yield c


# ── tests ──────────────────────────────────────────────────────────────────

def test_overall_empty(client: TestClient):
    r = client.get("/leaderboard/overall")
    assert r.status_code == 200
    body = r.json()
    assert body["total_specs"] == 3
    assert body["entries"] == []


def test_overall_single_contributor_one_spec(client: TestClient):
    client.post("/submissions", json=SPEC1_SUB)
    r = client.get("/leaderboard/overall")
    body = r.json()
    assert len(body["entries"]) == 1
    e = body["entries"][0]
    assert e["rank"] == 1
    assert e["contributor"] == "TestMiner"
    assert e["specs_entered"] == 1
    assert e["total_wins"] == 1
    # Only contributor on this spec → rank #1 → avg_rank = 1.0
    assert e["avg_rank"] == 1.0


def test_overall_single_contributor_two_specs(client: TestClient):
    client.post("/submissions", json=SPEC1_SUB)
    client.post("/submissions", json=SPEC2_SUB)
    r = client.get("/leaderboard/overall")
    body = r.json()
    e = body["entries"][0]
    assert e["specs_entered"] == 2
    assert e["total_wins"] == 2
    # Only contributor on both specs → rank #1 on each → avg_rank = 1.0
    assert e["avg_rank"] == 1.0
    assert len(e["best"]) == 2
    # best list is sorted by spec_id
    assert e["best"][0]["spec_id"] == "001_bracket"
    assert e["best"][1]["spec_id"] == "002_bracket_hard"


def test_overall_two_contributors_ranked_correctly(client: TestClient):
    # Both enter spec1: Alice lighter → rank 1, Bob heavier → rank 2.
    # With N=2: Alice norm = 1/(2+1) = 0.333, Bob norm = 2/(2+1) = 0.667.
    # overall_score (3 active specs): Alice = (0.333+1.0+1.0)/3 = 0.778, Bob = (0.667+1.0+1.0)/3 = 0.889.
    # Alice < Bob → Alice #1.
    alice = {**SPEC1_SUB, "contributor": "Alice", "mass_grams": 90.0, "commit_hash": "a1"}
    bob = {**SPEC1_SUB, "contributor": "Bob", "mass_grams": 180.0, "commit_hash": "b1"}
    client.post("/submissions", json=alice)
    client.post("/submissions", json=bob)

    r = client.get("/leaderboard/overall")
    body = r.json()
    assert len(body["entries"]) == 2
    assert body["entries"][0]["contributor"] == "Alice"
    assert body["entries"][1]["contributor"] == "Bob"
    assert body["entries"][0]["rank"] == 1
    assert body["entries"][1]["rank"] == 2


def test_overall_failed_submissions_excluded(client: TestClient):
    failed = {**SPEC1_SUB, "passed": False, "commit_hash": "fail1"}
    client.post("/submissions", json=failed)
    r = client.get("/leaderboard/overall")
    assert r.json()["entries"] == []


def test_overall_uses_best_per_spec(client: TestClient):
    # Two submissions from same contributor; only best (lighter) counts
    worse = {**SPEC1_SUB, "mass_grams": 150.0, "commit_hash": "w1"}
    better = {**SPEC1_SUB, "mass_grams": 100.0, "commit_hash": "b1"}
    client.post("/submissions", json=worse)
    client.post("/submissions", json=better)

    r = client.get("/leaderboard/overall")
    e = r.json()["entries"][0]
    # Only contributor → rank #1 on spec1 → avg_rank = 1.0 (score used is best: 100g)
    assert e["avg_rank"] == 1.0
    assert e["best"][0]["score"] == 100.0


def test_overall_total_wins_counts_correctly(client: TestClient):
    # Alice wins spec1; Bob wins spec2; Alice enters spec2 but doesn't win
    alice_s1 = {**SPEC1_SUB, "contributor": "Alice", "mass_grams": 90.0, "commit_hash": "as1"}
    alice_s2 = {**SPEC2_SUB, "contributor": "Alice", "mass_grams": 195.0, "commit_hash": "as2"}
    bob_s2 = {**SPEC2_SUB, "contributor": "Bob", "mass_grams": 140.0, "commit_hash": "bs2"}
    client.post("/submissions", json=alice_s1)
    client.post("/submissions", json=alice_s2)
    client.post("/submissions", json=bob_s2)

    r = client.get("/leaderboard/overall")
    entries = {e["contributor"]: e for e in r.json()["entries"]}

    assert entries["Alice"]["total_wins"] == 1  # only spec1
    assert entries["Bob"]["total_wins"] == 1    # only spec2
    assert entries["Alice"]["specs_entered"] == 2
    assert entries["Bob"]["specs_entered"] == 1


# ── GET /leaderboard/overall/{contributor} ─────────────────────────────────

def test_contributor_standing_found(client: TestClient):
    """GET /leaderboard/overall/{name} returns that contributor's entry."""
    client.post("/submissions", json=SPEC1_SUB)
    r = client.get("/leaderboard/overall/TestMiner")
    assert r.status_code == 200
    body = r.json()
    assert body["contributor"] == "TestMiner"
    assert body["rank"] == 1
    assert body["specs_entered"] == 1


def test_contributor_standing_case_insensitive(client: TestClient):
    """Contributor lookup is case-insensitive substring match."""
    client.post("/submissions", json=SPEC1_SUB)
    r = client.get("/leaderboard/overall/testminer")
    assert r.status_code == 200
    assert r.json()["contributor"] == "TestMiner"


def test_contributor_standing_substring_match(client: TestClient):
    """Partial name match works: 'Miner' matches 'TestMiner'."""
    client.post("/submissions", json=SPEC1_SUB)
    r = client.get("/leaderboard/overall/Miner")
    assert r.status_code == 200
    assert r.json()["contributor"] == "TestMiner"


def test_contributor_standing_not_found(client: TestClient):
    """Returns 404 when no submissions match the contributor query."""
    r = client.get("/leaderboard/overall/nobody")
    assert r.status_code == 404
