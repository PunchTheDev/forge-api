"""Tests for POST /eval/preview endpoint."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


AGENT_CODE = "def generate(spec):\n    return b'STEP_BYTES'\n"


@pytest.fixture
def client(set_env):
    import importlib
    import app.db
    import app.main
    importlib.reload(app.db)
    importlib.reload(app.main)
    from app.main import app
    with TestClient(app) as c:
        yield c


def _mock_proc(stdout_json: dict, returncode: int = 0):
    """Build a mock asyncio subprocess that returns given JSON as stdout."""
    payload = json.dumps(stdout_json, separators=(",", ":")).encode()
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(payload, b""))
    proc.kill = MagicMock()
    return proc


def test_preview_unknown_spec(client):
    resp = client.post("/eval/preview", json={"agent_code": AGENT_CODE, "spec_id": "no_such_spec"})
    assert resp.status_code == 404


def test_preview_agent_too_large(client):
    resp = client.post(
        "/eval/preview",
        json={"agent_code": "x" * (64 * 1024 + 1), "spec_id": "001_bracket"},
    )
    assert resp.status_code == 413


def test_preview_docker_not_available(client):
    with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
        resp = client.post(
            "/eval/preview",
            json={"agent_code": AGENT_CODE, "spec_id": "001_bracket"},
        )
    assert resp.status_code == 503


def test_preview_passed(client):
    result = {
        "passed": True,
        "score": 24.5,
        "score_metric": "mass_grams",
        "score_direction": "minimize",
        "stage": "ok",
        "reason": "passed",
        "fea_stress_mpa": 120.0,
        "fea_allowable_mpa": 150.0,
        "fea_element_count": 5000,
        "fea_load_node_count": 3,
        "fea_convergence_deviation": 0.01,
        "fea_displacement_mm": 0.05,
        "similarity": 0.3,
        "elapsed_seconds": 42.1,
    }
    with patch("asyncio.create_subprocess_exec", return_value=_mock_proc(result)):
        resp = client.post(
            "/eval/preview",
            json={"agent_code": AGENT_CODE, "spec_id": "001_bracket"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["passed"] is True
    assert body["score"] == pytest.approx(24.5)
    assert body["score_metric"] == "mass_grams"


def test_preview_failed(client):
    result = {
        "passed": False,
        "score": None,
        "score_metric": "mass_grams",
        "score_direction": "minimize",
        "stage": "fea",
        "reason": "stress too high",
        "elapsed_seconds": 18.0,
    }
    with patch("asyncio.create_subprocess_exec", return_value=_mock_proc(result, returncode=1)):
        resp = client.post(
            "/eval/preview",
            json={"agent_code": AGENT_CODE, "spec_id": "001_bracket"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["passed"] is False
    assert body["stage"] == "fea"


def test_preview_empty_output(client):
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(b"", b"some error"))
    proc.kill = MagicMock()
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        resp = client.post(
            "/eval/preview",
            json={"agent_code": AGENT_CODE, "spec_id": "001_bracket"},
        )
    assert resp.status_code == 500


def test_preview_bad_json_output(client):
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(b"not json\n", b""))
    proc.kill = MagicMock()
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        resp = client.post(
            "/eval/preview",
            json={"agent_code": AGENT_CODE, "spec_id": "001_bracket"},
        )
    assert resp.status_code == 500


def test_preview_rate_limit(client):
    """After exhausting the per-IP daily limit, requests return 429."""
    from datetime import datetime, timezone
    import app.routes.eval_preview as ep

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Simulate the test client IP already at the daily cap.
    ep._preview_counts["testclient"] = (today, ep.MAX_PREVIEWS_PER_IP_PER_DAY)

    resp = client.post("/eval/preview", json={"agent_code": AGENT_CODE, "spec_id": "001_bracket"})
    assert resp.status_code == 429

    # Clean up so other tests are not affected.
    del ep._preview_counts["testclient"]


def test_preview_docker_cmd_no_duplicate_entrypoint():
    """Ensure the docker cmd doesn't duplicate the Dockerfile ENTRYPOINT."""
    from app.routes.eval_preview import _build_docker_cmd

    cmd = _build_docker_cmd("/tmp/fake")
    # The ENTRYPOINT in the forge-eval image is `python3 -m benchmark.evaluate`.
    # It must appear exactly once — as the args following the image name.
    image_idx = cmd.index("forge-eval")
    post_image = cmd[image_idx + 1:]
    assert post_image == ["--agent", "/preview/agent.py", "--spec", "/preview/spec.json", "--json-compact"]
