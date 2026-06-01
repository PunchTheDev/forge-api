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
    client.post("/submissions", json=GOOD_SUBMISSION)
    r = client.get("/sota/001_bracket")
    assert r.status_code == 200
    sota = r.json()
    assert sota["score_grams"] == 108.48
    assert sota["contributor"] == "TestMiner"


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
