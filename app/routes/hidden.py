"""Admin endpoints for private held-out eval specs.

Hidden specs are stored in the DB (seeded from HIDDEN_SPECS_JSON env var) and
are never exposed via public routes. CI uses FORGE_ADMIN_KEY to fetch one
sample per round for post-merge consistency evaluation.
"""

from __future__ import annotations

import hmac
import json
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException

from app.db import get_db

router = APIRouter(prefix="/admin/hidden", tags=["admin"])


def _require_admin(authorization: str = Header(default="")) -> None:
    key = os.environ.get("FORGE_ADMIN_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="Admin key not configured on server.")
    token = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(token, key):
        raise HTTPException(status_code=403, detail="Invalid admin key.")


@router.get("/specs/{round_id}/sample")
async def sample_hidden_spec(round_id: str, authorization: str = Header(default="")) -> dict:
    """Return one random hidden spec for the given round. Requires admin key."""
    _require_admin(authorization)
    async with get_db() as db:
        async with db.execute(
            "SELECT spec_json FROM hidden_specs WHERE round_id = ? ORDER BY RANDOM() LIMIT 1",
            (round_id,),
        ) as cur:
            row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No hidden specs for round '{round_id}'.")
    return json.loads(row[0])


@router.post("/submissions", status_code=201)
async def record_hidden_submission(
    body: dict,
    authorization: str = Header(default=""),
) -> dict:
    """Record a hidden-spec eval result. Requires admin key."""
    _require_admin(authorization)
    required = {"spec_id", "agent_path", "contributor", "commit_hash", "passed"}
    missing = required - body.keys()
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing fields: {missing}")
    sub_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        await db.execute(
            """INSERT INTO hidden_submissions
               (id, spec_id, agent_path, contributor, commit_hash,
                score, metric, direction, passed, notes, submitted_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                sub_id,
                body["spec_id"],
                body["agent_path"],
                body["contributor"],
                body["commit_hash"],
                body.get("score"),
                body.get("metric"),
                body.get("direction", "minimize"),
                1 if body["passed"] else 0,
                body.get("notes", ""),
                now,
            ),
        )
        await db.commit()
    return {"id": sub_id, "recorded": True}


@router.get("/submissions/{contributor}")
async def contributor_hidden_history(
    contributor: str, authorization: str = Header(default="")
) -> list[dict]:
    """Return all hidden-spec submissions for a contributor. Requires admin key."""
    _require_admin(authorization)
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM hidden_submissions WHERE contributor = ? ORDER BY submitted_at DESC",
            (contributor,),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]
