"""Tests for S3-backed STEP file storage.

The public submission flow stores STEP bytes in S3 when S3_BUCKET is set,
falling back to SQLite BLOB otherwise. These tests verify:
  - Blob fallback path: step_data stored in DB, GET /step returns bytes
  - S3 path: upload called, step_key stored, GET /step redirects to presigned URL
  - has_step flag set correctly in both cases
"""
import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

BASE_SUB = {
    "spec_id": "r01_001_easy",
    "agent_path": "agents/alice/agent.py",
    "contributor": "alice",
    "commit_hash": "abc123",
    "mass_grams": 50.0,
    "fea_stress_mpa": 20.0,
    "fea_allowable_mpa": 25.0,
    "passed": True,
    "score": 50.0,
    "score_metric": "mass_grams",
    "score_direction": "minimize",
}
STEP_BYTES = b"ISO-10303-21;\n; fake STEP content;\nEND-ISO-10303-21;"


def _payload(with_step: bool = True) -> dict:
    p = dict(BASE_SUB)
    if with_step:
        p["step_b64"] = base64.b64encode(STEP_BYTES).decode()
    return p


# ---------------------------------------------------------------------------
# Blob fallback (no S3_BUCKET set)
# ---------------------------------------------------------------------------


def test_step_stored_as_blob_when_s3_not_configured(client):
    resp = client.post("/submissions", json=_payload())
    assert resp.status_code == 201
    sub = resp.json()
    assert sub["has_step"] is True
    sub_id = sub["id"]

    step_resp = client.get(f"/submissions/{sub_id}/step")
    assert step_resp.status_code == 200
    assert step_resp.content == STEP_BYTES


def test_has_step_false_when_no_step_provided(client):
    resp = client.post("/submissions", json=_payload(with_step=False))
    assert resp.status_code == 201
    assert resp.json()["has_step"] is False


# ---------------------------------------------------------------------------
# S3 path
# ---------------------------------------------------------------------------


def test_step_uploaded_to_s3_when_configured(client, monkeypatch):
    """When S3_BUCKET is set, upload() is called and step_key is stored."""
    monkeypatch.setenv("S3_BUCKET", "test-bucket")

    mock_upload = AsyncMock(return_value="steps/some-uuid.step")
    mock_presign = AsyncMock(return_value="https://s3.example.com/steps/some-uuid.step?sig=x")

    with patch("app.storage.upload", mock_upload), patch("app.storage.presign", mock_presign):
        resp = client.post("/submissions", json=_payload())
        assert resp.status_code == 201
        sub = resp.json()
        assert sub["has_step"] is True
        sub_id = sub["id"]

        mock_upload.assert_awaited_once()
        upload_args = mock_upload.await_args
        assert upload_args[0][0] == sub_id  # first arg is submission_id
        assert upload_args[0][1] == STEP_BYTES

        step_resp = client.get(f"/submissions/{sub_id}/step", follow_redirects=False)
        assert step_resp.status_code == 302
        assert "s3.example.com" in step_resp.headers["location"]

        mock_presign.assert_awaited_once_with("steps/some-uuid.step")


def test_s3_upload_failure_returns_503(client, monkeypatch):
    """If S3 upload raises, the API returns 503 with a descriptive error."""
    monkeypatch.setenv("S3_BUCKET", "test-bucket")

    mock_upload = AsyncMock(side_effect=Exception("S3 unavailable"))
    with patch("app.storage.upload", mock_upload):
        resp = client.post("/submissions", json=_payload())
        assert resp.status_code == 503
        assert "S3 unavailable" in resp.json()["detail"]
