import base64
import json

import pytest
from fastapi.testclient import TestClient


GOOD_SUBMISSION = {
    "spec_id": "001_bracket",
    "agent_path": "agents/slim-spine",
    "contributor": "TestMiner",
    "commit_hash": "abc1234",
    "mass_grams": 108.48,
    "fea_stress_mpa": 7.50,
    "fea_allowable_mpa": 25.0,
    "passed": True,
    "pr_number": 1,
    "notes": "Slim spine agent",
}


def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_list_specs(client: TestClient):
    r = client.get("/specs")
    assert r.status_code == 200
    specs = r.json()
    assert len(specs) == 1
    assert specs[0]["id"] == "001_bracket"


def test_get_spec(client: TestClient):
    r = client.get("/specs/001_bracket")
    assert r.status_code == 200
    assert r.json()["name"] == "Wall Mounting Bracket"


def test_get_spec_missing(client: TestClient):
    r = client.get("/specs/does_not_exist")
    assert r.status_code == 404


def test_create_submission(client: TestClient):
    r = client.post("/submissions", json=GOOD_SUBMISSION)
    assert r.status_code == 201
    body = r.json()
    assert body["mass_grams"] == 108.48
    assert "id" in body


def test_list_submissions_empty(client: TestClient):
    r = client.get("/submissions")
    assert r.status_code == 200
    assert r.json() == []


def test_list_submissions_after_insert(client: TestClient):
    client.post("/submissions", json=GOOD_SUBMISSION)
    r = client.get("/submissions?spec_id=001_bracket")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_leaderboard_empty(client: TestClient):
    r = client.get("/leaderboard/001_bracket")
    assert r.status_code == 200
    assert r.json()["entries"] == []


def test_leaderboard_with_submissions(client: TestClient):
    r1 = client.post("/submissions", json=GOOD_SUBMISSION)
    heavier = {**GOOD_SUBMISSION, "contributor": "Other", "mass_grams": 150.0, "commit_hash": "xyz"}
    client.post("/submissions", json=heavier)

    r = client.get("/leaderboard/001_bracket")
    assert r.status_code == 200
    entries = r.json()["entries"]
    assert len(entries) == 2
    assert entries[0]["rank"] == 1
    assert entries[0]["mass_grams"] == 108.48  # lightest first
    assert "submission_id" in entries[0]
    assert entries[0]["submission_id"] == r1.json()["id"]
    assert entries[0]["has_step"] is False


def test_sota_missing_spec(client: TestClient):
    r = client.get("/sota/does_not_exist")
    assert r.status_code == 404


def test_sota_no_submissions(client: TestClient):
    r = client.get("/sota/001_bracket")
    assert r.status_code == 404


def test_sota_with_submission(client: TestClient):
    sub = client.post("/submissions", json=GOOD_SUBMISSION)
    r = client.get("/sota/001_bracket")
    assert r.status_code == 200
    sota = r.json()
    assert sota["score_grams"] == 108.48
    assert sota["contributor"] == "TestMiner"
    assert "submission_id" in sota
    assert sota["submission_id"] == sub.json()["id"]
    assert "has_step" in sota


def test_sota_best_wins(client: TestClient):
    client.post("/submissions", json=GOOD_SUBMISSION)
    better = {**GOOD_SUBMISSION, "mass_grams": 95.0, "commit_hash": "better123"}
    client.post("/submissions", json=better)
    r = client.get("/sota/001_bracket")
    assert r.json()["score_grams"] == 95.0


def test_submission_has_step_false_without_data(client: TestClient):
    r = client.post("/submissions", json=GOOD_SUBMISSION)
    assert r.status_code == 201
    assert r.json()["has_step"] is False


def test_submission_has_step_true_with_data(client: TestClient):
    import base64
    step_bytes = b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n"
    sub = {**GOOD_SUBMISSION, "step_b64": base64.b64encode(step_bytes).decode()}
    r = client.post("/submissions", json=sub)
    assert r.status_code == 201
    body = r.json()
    assert body["has_step"] is True
    sub_id = body["id"]

    step_r = client.get(f"/submissions/{sub_id}/step")
    assert step_r.status_code == 200
    assert step_r.content == step_bytes


def test_submission_step_404_no_step(client: TestClient):
    r = client.post("/submissions", json=GOOD_SUBMISSION)
    sub_id = r.json()["id"]
    r2 = client.get(f"/submissions/{sub_id}/step")
    assert r2.status_code == 404


def test_submission_step_404_missing_id(client: TestClient):
    r = client.get("/submissions/00000000-0000-0000-0000-000000000000/step")
    assert r.status_code == 404


def test_list_submissions_filter_commit_hash(client: TestClient):
    client.post("/submissions", json=GOOD_SUBMISSION)
    other = {**GOOD_SUBMISSION, "commit_hash": "deadbeef", "contributor": "other"}
    client.post("/submissions", json=other)

    r = client.get("/submissions?commit_hash=abc1234&passed_only=false")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["commit_hash"] == "abc1234"

    r2 = client.get("/submissions?commit_hash=deadbeef&passed_only=false")
    assert r2.status_code == 200
    assert len(r2.json()) == 1
    assert r2.json()[0]["commit_hash"] == "deadbeef"

    r3 = client.get("/submissions?commit_hash=notexist&passed_only=false")
    assert r3.status_code == 200
    assert r3.json() == []


# --- Rate limiting ---

def test_rate_limit_allows_under_cap(client: TestClient, monkeypatch):
    monkeypatch.setenv("MAX_EVALS_PER_DAY", "3")
    import importlib
    import app.routes.submissions as sub_mod
    importlib.reload(sub_mod)
    for i in range(3):
        sub = {**GOOD_SUBMISSION, "commit_hash": f"hash{i}"}
        r = client.post("/submissions", json=sub)
        assert r.status_code == 201


def test_rate_limit_blocks_at_cap(client: TestClient, monkeypatch):
    monkeypatch.setenv("MAX_EVALS_PER_DAY", "2")
    import importlib
    import app.routes.submissions as sub_mod
    importlib.reload(sub_mod)
    for i in range(2):
        client.post("/submissions", json={**GOOD_SUBMISSION, "commit_hash": f"ok{i}"})
    r = client.post("/submissions", json={**GOOD_SUBMISSION, "commit_hash": "blocked"})
    assert r.status_code == 429
    assert "Rate limit exceeded" in r.json()["detail"]


def test_rate_limit_independent_per_contributor(client: TestClient, monkeypatch):
    monkeypatch.setenv("MAX_EVALS_PER_DAY", "1")
    import importlib
    import app.routes.submissions as sub_mod
    importlib.reload(sub_mod)
    r1 = client.post("/submissions", json={**GOOD_SUBMISSION, "contributor": "AliceBot", "commit_hash": "alice1"})
    assert r1.status_code == 201
    # Bob uses a different commit hash — same hash + spec would be rejected by dedup
    r2 = client.post("/submissions", json={**GOOD_SUBMISSION, "contributor": "BobBot", "commit_hash": "bob1"})
    assert r2.status_code == 201
    # Alice's second submission on a new commit is blocked by her 1/day cap
    r3 = client.post("/submissions", json={**GOOD_SUBMISSION, "contributor": "AliceBot", "commit_hash": "alice2"})
    assert r3.status_code == 429


def test_rate_limit_default_is_20(client: TestClient, monkeypatch):
    monkeypatch.delenv("MAX_EVALS_PER_DAY", raising=False)
    import importlib
    import app.routes.submissions as sub_mod
    importlib.reload(sub_mod)
    assert sub_mod.MAX_EVALS_PER_DAY == 20


# --- commit hash deduplication ---

def test_duplicate_commit_hash_rejected(client: TestClient):
    """Same (commit_hash, spec_id) pair is rejected with 409 regardless of contributor."""
    r1 = client.post("/submissions", json=GOOD_SUBMISSION)
    assert r1.status_code == 201
    # Same commit hash, same spec — different contributor → should still be rejected
    r2 = client.post("/submissions", json={**GOOD_SUBMISSION, "contributor": "Attacker"})
    assert r2.status_code == 409
    assert "already scored" in r2.json()["detail"]


def test_same_commit_different_specs_allowed(client: TestClient):
    """Same commit hash is allowed across different specs."""
    r1 = client.post("/submissions", json=GOOD_SUBMISSION)
    assert r1.status_code == 201
    # Same commit hash, different spec — should succeed
    r2 = client.post("/submissions", json={**GOOD_SUBMISSION, "spec_id": "002_bracket_hard"})
    assert r2.status_code == 201


# --- score_direction ---

def test_submission_default_direction_is_minimize(client: TestClient):
    r = client.post("/submissions", json=GOOD_SUBMISSION)
    assert r.status_code == 201
    assert r.json()["score_direction"] == "minimize"


def test_submission_maximize_direction_stored(client: TestClient):
    sub = {**GOOD_SUBMISSION, "score": 185.5, "score_metric": "stiffness_to_weight",
           "score_direction": "maximize", "commit_hash": "stiff1"}
    r = client.post("/submissions", json=sub)
    assert r.status_code == 201
    body = r.json()
    assert body["score_direction"] == "maximize"
    assert body["score_metric"] == "stiffness_to_weight"
    assert body["score"] == 185.5


def test_sota_direction_in_response(client: TestClient):
    client.post("/submissions", json=GOOD_SUBMISSION)
    r = client.get("/sota/001_bracket")
    assert r.status_code == 200
    assert "score_direction" in r.json()
    assert r.json()["score_direction"] == "minimize"


def test_sota_maximize_picks_highest(client: TestClient):
    """For maximize direction, the submission with the highest score should be SOTA."""
    low = {**GOOD_SUBMISSION, "score": 50.0, "score_metric": "stiffness_to_weight",
           "score_direction": "maximize", "commit_hash": "stiff_low"}
    high = {**GOOD_SUBMISSION, "score": 200.0, "score_metric": "stiffness_to_weight",
            "score_direction": "maximize", "commit_hash": "stiff_high", "contributor": "Other"}
    client.post("/submissions", json=low)
    client.post("/submissions", json=high)
    r = client.get("/sota/001_bracket")
    assert r.status_code == 200
    assert r.json()["score"] == 200.0


# --- direction-aware eligibility ---

def test_eligibility_minimize_no_sota(client: TestClient):
    r = client.get("/sota/001_bracket/eligibility?score=100.0")
    assert r.status_code == 200
    assert r.json()["eligible"] is True
    assert r.json()["reason"] == "No current SOTA — any passing submission is eligible"


def test_eligibility_minimize_beats_by_margin(client: TestClient):
    """Minimize: new score must be ≥1% lower than current SOTA (within first 7 days)."""
    client.post("/submissions", json=GOOD_SUBMISSION)  # SOTA = 108.48
    # 108.48 * 0.99 = 107.3952 — need to score ≤107.3952
    r = client.get("/sota/001_bracket/eligibility?score=107.0")
    assert r.status_code == 200
    assert r.json()["eligible"] is True


def test_eligibility_minimize_short_of_margin(client: TestClient):
    """Minimize: a score that beats SOTA but by less than 1% is ineligible."""
    client.post("/submissions", json=GOOD_SUBMISSION)  # SOTA = 108.48
    # 108.48 * 0.995 = 107.9376 — marginal improvement, less than 1%
    r = client.get("/sota/001_bracket/eligibility?score=108.0")
    assert r.status_code == 200
    assert r.json()["eligible"] is False


def test_eligibility_maximize_no_sota(client: TestClient):
    r = client.get("/sota/001_bracket/eligibility?score=300.0")
    assert r.status_code == 200
    assert r.json()["eligible"] is True


def test_eligibility_maximize_beats_by_margin(client: TestClient):
    """Maximize: new score must be ≥1% higher than current SOTA (within first 7 days)."""
    sub = {**GOOD_SUBMISSION, "score": 200.0, "score_metric": "stiffness_to_weight",
           "score_direction": "maximize", "commit_hash": "max1"}
    client.post("/submissions", json=sub)  # SOTA = 200.0
    # 200.0 * 1.01 = 202.0 — need to score ≥202.0
    r = client.get("/sota/001_bracket/eligibility?score=205.0")
    assert r.status_code == 200
    assert r.json()["eligible"] is True


def test_eligibility_maximize_short_of_margin(client: TestClient):
    """Maximize: a score that beats SOTA but by less than 1% is ineligible."""
    sub = {**GOOD_SUBMISSION, "score": 200.0, "score_metric": "stiffness_to_weight",
           "score_direction": "maximize", "commit_hash": "max2"}
    client.post("/submissions", json=sub)  # SOTA = 200.0
    # 201.0 beats but only by 0.5%, below the 1% threshold
    r = client.get("/sota/001_bracket/eligibility?score=201.0")
    assert r.status_code == 200
    assert r.json()["eligible"] is False


def test_eligibility_maximize_lower_than_sota_ineligible(client: TestClient):
    """Maximize: a score lower than SOTA is never eligible."""
    sub = {**GOOD_SUBMISSION, "score": 200.0, "score_metric": "stiffness_to_weight",
           "score_direction": "maximize", "commit_hash": "max3"}
    client.post("/submissions", json=sub)  # SOTA = 200.0
    r = client.get("/sota/001_bracket/eligibility?score=150.0")
    assert r.status_code == 200
    assert r.json()["eligible"] is False


def test_sota_history_empty(client: TestClient):
    r = client.get("/sota/001_bracket/history")
    assert r.status_code == 200
    assert r.json() == []


def test_sota_history_missing_spec(client: TestClient):
    r = client.get("/sota/does_not_exist/history")
    assert r.status_code == 404


def test_sota_history_records_improvements(client: TestClient):
    """History only records entries that improved the SOTA."""
    # First submission sets the record.
    client.post("/submissions", json={**GOOD_SUBMISSION, "mass_grams": 100.0, "commit_hash": "h1"})
    # Worse score — not a new SOTA.
    client.post("/submissions", json={**GOOD_SUBMISSION, "mass_grams": 120.0, "commit_hash": "h2"})
    # Better score — sets a new SOTA.
    client.post("/submissions", json={**GOOD_SUBMISSION, "mass_grams": 90.0, "commit_hash": "h3"})

    r = client.get("/sota/001_bracket/history")
    assert r.status_code == 200
    history = r.json()
    assert len(history) == 2
    assert history[0]["score"] == 100.0
    assert history[1]["score"] == 90.0


# --- admin batch ---

def test_batch_submissions_requires_auth(client: TestClient, monkeypatch):
    monkeypatch.setenv("ADMIN_SECRET", "secret123")
    r = client.post("/admin/submissions/batch", json=[GOOD_SUBMISSION])
    assert r.status_code == 403


def test_batch_submissions_stores_score_fields(client: TestClient, monkeypatch):
    """Batch insert must persist score, score_metric, score_direction."""
    monkeypatch.setenv("ADMIN_SECRET", "secret123")
    item = {**GOOD_SUBMISSION, "score": 3.75, "score_metric": "stiffness_to_weight",
            "score_direction": "maximize", "commit_hash": "batch1"}
    r = client.post("/admin/submissions/batch", json=[item],
                    headers={"X-Admin-Token": "secret123"})
    assert r.status_code == 200
    assert r.json()["inserted"] == 1

    subs = client.get("/submissions?passed_only=false").json()
    assert len(subs) == 1
    assert subs[0]["score"] == 3.75
    assert subs[0]["score_metric"] == "stiffness_to_weight"
    assert subs[0]["score_direction"] == "maximize"


def test_batch_submissions_sota_eligible_false(client: TestClient, monkeypatch):
    """Batch-inserted submissions are not SOTA-eligible (historical seed data)."""
    monkeypatch.setenv("ADMIN_SECRET", "secret123")
    item = {**GOOD_SUBMISSION, "commit_hash": "batch2"}
    r = client.post("/admin/submissions/batch", json=[item],
                    headers={"X-Admin-Token": "secret123"})
    assert r.status_code == 200
    subs = client.get("/submissions?passed_only=false").json()
    assert len(subs) == 1
    # Batch entries should never be SOTA-eligible — they are seed/historical data.
    assert subs[0]["sota_eligible"] is False


# --- DELETE /submissions/{id} ---

def test_delete_submission_requires_auth(client: TestClient, monkeypatch):
    """DELETE /submissions/{id} rejects requests without X-Admin-Token."""
    monkeypatch.setenv("ADMIN_SECRET", "secret123")
    r = client.post("/submissions", json=GOOD_SUBMISSION)
    sub_id = r.json()["id"]

    del_r = client.delete(f"/submissions/{sub_id}")
    assert del_r.status_code == 403


def test_delete_submission_removes_entry(client: TestClient, monkeypatch):
    """DELETE /submissions/{id} removes the entry from the DB."""
    monkeypatch.setenv("ADMIN_SECRET", "secret123")
    r = client.post("/submissions", json=GOOD_SUBMISSION)
    sub_id = r.json()["id"]

    del_r = client.delete(f"/submissions/{sub_id}", headers={"X-Admin-Token": "secret123"})
    assert del_r.status_code == 204

    get_r = client.get(f"/submissions/{sub_id}")
    assert get_r.status_code == 404


def test_delete_submission_404_not_found(client: TestClient, monkeypatch):
    """DELETE /submissions/{id} returns 404 for unknown IDs."""
    monkeypatch.setenv("ADMIN_SECRET", "secret123")
    del_r = client.delete(
        "/submissions/00000000-0000-0000-0000-000000000000",
        headers={"X-Admin-Token": "secret123"},
    )
    assert del_r.status_code == 404


# --- GET /submissions contributor filter ---

def test_list_submissions_filter_contributor(client: TestClient):
    """?contributor= returns only submissions from that contributor."""
    client.post("/submissions", json=GOOD_SUBMISSION)
    other = {**GOOD_SUBMISSION, "contributor": "OtherMiner", "commit_hash": "xyz9"}
    client.post("/submissions", json=other)

    r = client.get("/submissions?contributor=TestMiner&passed_only=false")
    assert r.status_code == 200
    subs = r.json()
    assert len(subs) == 1
    assert subs[0]["contributor"] == "TestMiner"


def test_list_submissions_contributor_no_match(client: TestClient):
    """?contributor= returns empty list when no submissions match."""
    client.post("/submissions", json=GOOD_SUBMISSION)
    r = client.get("/submissions?contributor=nobody&passed_only=false")
    assert r.status_code == 200
    assert r.json() == []


# --- hidden admin endpoint auth ---

def test_hidden_spec_returns_503_when_key_unset(client: TestClient, monkeypatch):
    """Returns 503 when FORGE_ADMIN_KEY is not set — not 200 or 403."""
    monkeypatch.delenv("FORGE_ADMIN_KEY", raising=False)
    r = client.get(
        "/admin/hidden/specs/round_001/sample",
        headers={"Authorization": "Bearer anything"},
    )
    assert r.status_code == 503


def test_hidden_spec_returns_403_on_wrong_key(client: TestClient, monkeypatch):
    """Returns 403 when FORGE_ADMIN_KEY is set but token is wrong."""
    monkeypatch.setenv("FORGE_ADMIN_KEY", "correct-key")
    r = client.get(
        "/admin/hidden/specs/round_001/sample",
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert r.status_code == 403


def test_hidden_spec_returns_403_on_missing_token(client: TestClient, monkeypatch):
    """Returns 403 when FORGE_ADMIN_KEY is set but no token is provided."""
    monkeypatch.setenv("FORGE_ADMIN_KEY", "correct-key")
    r = client.get("/admin/hidden/specs/round_001/sample")
    assert r.status_code == 403


def test_hidden_submission_requires_auth(client: TestClient, monkeypatch):
    """POST /admin/hidden/submissions returns 503 without key configured."""
    monkeypatch.delenv("FORGE_ADMIN_KEY", raising=False)
    r = client.post(
        "/admin/hidden/submissions",
        json={
            "spec_id": "hidden_001",
            "agent_path": "agents/test/agent.py",
            "contributor": "TestBot",
            "commit_hash": "abc",
            "passed": True,
        },
    )
    assert r.status_code == 503


# --- hidden spec happy paths ---

def _make_hidden_specs_env(specs: list) -> str:
    """Encode a list of spec dicts as the HIDDEN_SPECS_JSON env var value."""
    return base64.b64encode(json.dumps(specs).encode()).decode()


def test_hidden_spec_returns_spec_with_valid_key(tmp_path, monkeypatch):
    """GET /admin/hidden/specs/{round}/sample returns a spec when key and data are valid."""
    spec = {
        "id": "hidden_round_001_001_easy",
        "round_id": "round_001",
        "tier": "easy",
        "material": "pla",
        "constraints": {"load_newtons": 100.0},
        "scoring": {"metric": "mass_grams", "direction": "minimize"},
    }
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("SPECS_DIR", "tests/fixtures/specs")
    monkeypatch.setenv("FORGE_ADMIN_KEY", "secret")
    monkeypatch.setenv("HIDDEN_SPECS_JSON", _make_hidden_specs_env([spec]))

    import importlib
    import app.db
    import app.main
    importlib.reload(app.db)
    importlib.reload(app.main)
    from app.main import app
    from fastapi.testclient import TestClient as TC

    with TC(app) as c:
        r = c.get(
            "/admin/hidden/specs/round_001/sample",
            headers={"Authorization": "Bearer secret"},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == spec["id"]


def test_hidden_submission_records_with_valid_key(tmp_path, monkeypatch):
    """POST /admin/hidden/submissions returns 201 and stores the record."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("SPECS_DIR", "tests/fixtures/specs")
    monkeypatch.setenv("FORGE_ADMIN_KEY", "secret")

    import importlib
    import app.db
    import app.main
    importlib.reload(app.db)
    importlib.reload(app.main)
    from app.main import app
    from fastapi.testclient import TestClient as TC

    with TC(app) as c:
        r = c.post(
            "/admin/hidden/submissions",
            json={
                "spec_id": "hidden_round_001_001_easy",
                "agent_path": "agents/my-agent/agent.py",
                "contributor": "miner42",
                "commit_hash": "deadbeef",
                "passed": True,
                "score": 42.5,
                "metric": "mass_grams",
            },
            headers={"Authorization": "Bearer secret"},
        )
    assert r.status_code == 201
    data = r.json()
    assert data["recorded"] is True
    assert "id" in data


def test_list_specs_tier_filter_hard(tmp_path, monkeypatch):
    """GET /specs?tier=hard returns only specs whose id ends in _hard."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("SPECS_DIR", "tests/fixtures/specs_multi")

    import importlib
    import app.db
    import app.specs as app_specs
    import app.main
    importlib.reload(app.db)
    importlib.reload(app_specs)
    importlib.reload(app.main)
    from app.main import app
    from fastapi.testclient import TestClient as TC

    with TC(app) as c:
        r = c.get("/specs?tier=hard")
    assert r.status_code == 200
    specs = r.json()
    assert len(specs) >= 1
    assert all(s["tier"] == "hard" for s in specs)
    assert all(s["id"].endswith("_hard") for s in specs)


def test_spec_tier_field_in_response(client: TestClient):
    """Spec response includes computed tier field (None for legacy IDs)."""
    r = client.get("/specs/001_bracket")
    assert r.status_code == 200
    assert r.json()["tier"] is None


def _specs_multi_client(tmp_path, monkeypatch):
    """Return a TestClient backed by the specs_multi fixture directory."""
    import importlib
    import app.db
    import app.specs as app_specs
    import app.main

    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("SPECS_DIR", "tests/fixtures/specs_multi")
    importlib.reload(app.db)
    importlib.reload(app_specs)
    importlib.reload(app.main)
    from app.main import app
    from fastapi.testclient import TestClient as TC
    return TC(app)


def test_list_specs_round_id_filter(tmp_path, monkeypatch):
    """GET /specs?round_id=round_001 returns only r01_* specs."""
    with _specs_multi_client(tmp_path, monkeypatch) as c:
        r = c.get("/specs?round_id=round_001")
    assert r.status_code == 200
    specs = r.json()
    assert len(specs) >= 1
    assert all(s["round_id"] == "round_001" for s in specs)
    ids = [s["id"] for s in specs]
    assert all(i.startswith("r01_") for i in ids)


def test_list_specs_round_id_filter_round_002(tmp_path, monkeypatch):
    """GET /specs?round_id=round_002 returns only r02_* specs."""
    with _specs_multi_client(tmp_path, monkeypatch) as c:
        r = c.get("/specs?round_id=round_002")
    assert r.status_code == 200
    specs = r.json()
    assert len(specs) >= 1
    assert all(s["round_id"] == "round_002" for s in specs)


def test_list_specs_material_filter(tmp_path, monkeypatch):
    """GET /specs?material=aluminum_6061 returns only aluminum specs."""
    with _specs_multi_client(tmp_path, monkeypatch) as c:
        r = c.get("/specs?material=aluminum_6061")
    assert r.status_code == 200
    specs = r.json()
    assert len(specs) >= 1
    assert all(s["material"] == "aluminum_6061" for s in specs)


def test_list_specs_round_and_tier_combined(tmp_path, monkeypatch):
    """GET /specs?round_id=round_001&tier=easy returns intersection."""
    with _specs_multi_client(tmp_path, monkeypatch) as c:
        r = c.get("/specs?round_id=round_001&tier=easy")
    assert r.status_code == 200
    specs = r.json()
    assert len(specs) >= 1
    assert all(s["round_id"] == "round_001" for s in specs)
    assert all(s["tier"] == "easy" for s in specs)


def test_spec_round_id_field_in_response(client: TestClient):
    """Spec response includes computed round_id field (None for legacy IDs)."""
    r = client.get("/specs/001_bracket")
    assert r.status_code == 200
    assert r.json()["round_id"] is None


def test_sota_round_filter_not_found(client: TestClient):
    """GET /sota?round_id=nonexistent returns 404."""
    r = client.get("/sota?round_id=nonexistent_round")
    assert r.status_code == 404


def test_sota_round_filter_empty_round(tmp_path, monkeypatch):
    """GET /sota?round_id=round_x with no submissions returns []."""
    import importlib, json

    rounds_dir = tmp_path / "rounds"
    rounds_dir.mkdir()
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()

    spec_data = {
        "id": "rs_001_easy",
        "version": "1.0",
        "name": "Test spec",
        "description": "desc",
        "material": "pla",
        "constraints": {
            "load_newtons": 100.0, "load_point_mm": [50.0, 25.0, 25.0],
            "safety_factor": 1.5, "bolt_pattern_mm": [[0.0, 0.0], [50.0, 0.0]],
            "bolt_diameter_clearance_mm": 6.5, "mount_face_x_mm": 0.0,
            "build_volume_mm": [100.0, 80.0, 60.0],
            "max_overhang_deg": 50.0, "min_wall_thickness_mm": 1.0,
        },
        "scoring": {"metric": "mass_grams", "direction": "minimize"},
    }
    (specs_dir / "rs_001_easy.json").write_text(json.dumps(spec_data))

    round_data = {
        "id": "round_sota_test", "name": "SOTA filter test", "description": "d",
        "status": "active", "starts": "2026-01-01", "ends": None,
        "scoring_metric": "mass_grams", "scoring_direction": "minimize",
        "specs": [{"id": "rs_001_easy", "tier": "easy"}], "notes": None,
    }
    (rounds_dir / "round_sota_test.json").write_text(json.dumps(round_data))

    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("SPECS_DIR", str(specs_dir))
    monkeypatch.setenv("ROUNDS_DIR", str(rounds_dir))

    import app.db, app.main, app.routes.rounds, app.routes.sota, app.specs
    importlib.reload(app.db)
    importlib.reload(app.specs)
    importlib.reload(app.routes.rounds)
    importlib.reload(app.routes.sota)
    importlib.reload(app.main)
    from app.main import app

    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        r = c.get("/sota?round_id=round_sota_test")
        assert r.status_code == 200
        assert r.json() == []  # no submissions yet


def test_sota_round_filter_with_submission(tmp_path, monkeypatch):
    """GET /sota?round_id=round_x only returns SOTAs for specs in that round."""
    import importlib, json

    rounds_dir = tmp_path / "rounds"
    rounds_dir.mkdir()
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()

    # Two specs: one in our round, one legacy
    def _spec(spec_id):
        return {
            "id": spec_id, "version": "1.0", "name": f"Spec {spec_id}", "description": "d",
            "material": "pla",
            "constraints": {
                "load_newtons": 100.0, "load_point_mm": [50.0, 25.0, 25.0],
                "safety_factor": 1.5, "bolt_pattern_mm": [[0.0, 0.0], [50.0, 0.0]],
                "bolt_diameter_clearance_mm": 6.5, "mount_face_x_mm": 0.0,
                "build_volume_mm": [100.0, 80.0, 60.0],
                "max_overhang_deg": 50.0, "min_wall_thickness_mm": 1.0,
            },
            "scoring": {"metric": "mass_grams", "direction": "minimize"},
        }

    (specs_dir / "rf_001_easy.json").write_text(json.dumps(_spec("rf_001_easy")))
    (specs_dir / "legacy_spec.json").write_text(json.dumps(_spec("legacy_spec")))

    round_data = {
        "id": "round_filter", "name": "Filter round", "description": "d",
        "status": "active", "starts": "2026-01-01", "ends": None,
        "scoring_metric": "mass_grams", "scoring_direction": "minimize",
        "specs": [{"id": "rf_001_easy", "tier": "easy"}], "notes": None,
    }
    (rounds_dir / "round_filter.json").write_text(json.dumps(round_data))

    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("SPECS_DIR", str(specs_dir))
    monkeypatch.setenv("ROUNDS_DIR", str(rounds_dir))

    import app.db, app.main, app.routes.rounds, app.routes.sota, app.specs
    importlib.reload(app.db)
    importlib.reload(app.specs)
    importlib.reload(app.routes.rounds)
    importlib.reload(app.routes.sota)
    importlib.reload(app.main)
    from app.main import app

    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        base = {"agent_path": "a/b", "commit_hash": "abc", "mass_grams": 80.0,
                "fea_stress_mpa": 5.0, "fea_allowable_mpa": 25.0, "passed": True, "pr_number": 1, "contributor": "Alice"}
        c.post("/submissions", json={**base, "spec_id": "rf_001_easy"})
        c.post("/submissions", json={**base, "spec_id": "legacy_spec"})

        # Filter returns only the round spec
        r = c.get("/sota?round_id=round_filter")
        assert r.status_code == 200
        results = r.json()
        assert len(results) == 1
        assert results[0]["spec_id"] == "rf_001_easy"

        # No filter returns both
        r2 = c.get("/sota")
        assert r2.status_code == 200
        assert len(r2.json()) == 2
