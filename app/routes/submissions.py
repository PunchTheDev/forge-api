import base64
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import Response

from app.db import get_db
from app.models import Submission, SubmissionCreate
from app.notify import send_sota_alert
from app.routes.leaderboard import invalidate_overall_cache
from app.scoring import sota_eligible as compute_sota_eligible

router = APIRouter(prefix="/submissions", tags=["submissions"])
admin_router = APIRouter(prefix="/admin/submissions", tags=["admin"])

MAX_EVALS_PER_DAY = int(os.environ.get("MAX_EVALS_PER_DAY", "20"))


@router.post("", response_model=Submission, status_code=201)
async def create_submission(body: SubmissionCreate):
    sub_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    today = now[:10]  # "YYYY-MM-DD"
    step_data = base64.b64decode(body.step_b64) if body.step_b64 else None

    # Compute SOTA eligibility before inserting so we can store it.
    score_for_eligibility = body.score if body.score is not None else body.mass_grams
    eligible, old_sota_score = await _compute_eligibility(body.spec_id, score_for_eligibility, body.score_direction)

    async with get_db() as db:
        async with db.execute(
            "SELECT COUNT(*) FROM submissions WHERE contributor = ? AND submitted_at >= ?",
            (body.contributor, today),
        ) as cur:
            row = await cur.fetchone()
        count = row[0]
        if count >= MAX_EVALS_PER_DAY:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {MAX_EVALS_PER_DAY} submissions per contributor per UTC day.",
            )
        score = body.score if body.score is not None else body.mass_grams
        await db.execute(
            """INSERT INTO submissions
               (id, spec_id, agent_path, contributor, commit_hash, mass_grams,
                fea_stress_mpa, fea_allowable_mpa, passed, pr_number, notes, submitted_at, step_data,
                sota_eligible, score, score_metric, score_direction)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                sub_id,
                body.spec_id,
                body.agent_path,
                body.contributor,
                body.commit_hash,
                body.mass_grams,
                body.fea_stress_mpa,
                body.fea_allowable_mpa,
                int(body.passed),
                body.pr_number,
                body.notes,
                now,
                step_data,
                int(eligible),
                score,
                body.score_metric,
                body.score_direction,
            ),
        )
        await db.commit()

    if body.passed:
        invalidate_overall_cache()

    if eligible and body.passed:
        await send_sota_alert(
            body.spec_id,
            body.score_metric or "mass_grams",
            body.score_direction or "minimize",
            score,
            old_sota_score,
            body.contributor,
        )

    return _build_submission(sub_id, now, body, step_data is not None, eligible, score)


@router.get("", response_model=list[Submission])
async def list_submissions(
    spec_id: str | None = Query(None),
    contributor: str | None = Query(None),
    commit_hash: str | None = Query(None),
    passed_only: bool = Query(True),
    limit: int = Query(50, le=500),
):
    conditions = []
    params: list = []

    if spec_id:
        conditions.append("spec_id = ?")
        params.append(spec_id)
    if contributor:
        conditions.append("contributor = ?")
        params.append(contributor)
    if commit_hash:
        conditions.append("commit_hash = ?")
        params.append(commit_hash)
    if passed_only:
        conditions.append("passed = 1")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    query = f"SELECT * FROM submissions {where} ORDER BY submitted_at DESC LIMIT ?"
    params.append(limit)

    async with get_db() as db:
        async with db.execute(query, params) as cur:
            rows = await cur.fetchall()

    return [_row_to_submission(r) for r in rows]


@router.get("/{submission_id}", response_model=Submission)
async def get_submission(submission_id: str):
    async with get_db() as db:
        async with db.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)) as cur:
            row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    return _row_to_submission(row)


@admin_router.post("/batch")
async def batch_create_submissions(
    body: list[SubmissionCreate],
    x_admin_token: str | None = Header(None),
):
    """Insert multiple submissions without rate limiting. Requires X-Admin-Token."""
    expected = os.environ.get("ADMIN_SECRET", "")
    if not expected or x_admin_token != expected:
        raise HTTPException(status_code=403, detail="Invalid or missing admin token")

    inserted = 0
    failed = 0
    errors: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()

    async with get_db() as db:
        for i, item in enumerate(body):
            sub_id = str(uuid.uuid4())
            step_data = base64.b64decode(item.step_b64) if item.step_b64 else None
            score = item.score if item.score is not None else item.mass_grams
            try:
                await db.execute(
                    """INSERT INTO submissions
                       (id, spec_id, agent_path, contributor, commit_hash, mass_grams,
                        fea_stress_mpa, fea_allowable_mpa, passed, pr_number, notes, submitted_at, step_data,
                        score, score_metric, score_direction)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        sub_id,
                        item.spec_id,
                        item.agent_path,
                        item.contributor,
                        item.commit_hash,
                        item.mass_grams,
                        item.fea_stress_mpa,
                        item.fea_allowable_mpa,
                        int(item.passed),
                        item.pr_number,
                        item.notes,
                        now,
                        step_data,
                        score,
                        item.score_metric,
                        item.score_direction,
                    ),
                )
                inserted += 1
            except Exception as exc:
                failed += 1
                errors.append({"index": i, "error": str(exc)})
        await db.commit()

    if inserted > 0:
        invalidate_overall_cache()

    return {"inserted": inserted, "failed": failed, "errors": errors}


@router.delete("/{submission_id}", status_code=204)
async def delete_submission(submission_id: str, x_admin_token: str | None = Header(None)):
    """Delete a submission by ID. Requires X-Admin-Token header matching ADMIN_SECRET env var."""
    expected = os.environ.get("ADMIN_SECRET", "")
    if not expected or x_admin_token != expected:
        raise HTTPException(status_code=403, detail="Invalid or missing admin token")
    async with get_db() as db:
        async with db.execute("SELECT id FROM submissions WHERE id = ?", (submission_id,)) as cur:
            row = await cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Submission not found")
        await db.execute("DELETE FROM submissions WHERE id = ?", (submission_id,))
        await db.commit()
    invalidate_overall_cache()


@router.get("/{submission_id}/step")
async def get_submission_step(submission_id: str):
    """Return the raw STEP file bytes for 3D viewing."""
    async with get_db() as db:
        async with db.execute(
            "SELECT step_data FROM submissions WHERE id = ?", (submission_id,)
        ) as cur:
            row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    if row["step_data"] is None:
        raise HTTPException(status_code=404, detail="No STEP file stored for this submission")
    return Response(
        content=bytes(row["step_data"]),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={submission_id}.step"},
    )


async def _compute_eligibility(spec_id: str, score: float, direction: str = "minimize") -> tuple[bool, float | None]:
    """Look up the current SOTA and determine if score is SOTA-eligible.

    Returns (eligible, current_sota_score). current_sota_score is None when no
    passing submission exists yet (first submission is always eligible).
    """
    query = """
        SELECT COALESCE(score, mass_grams) AS best_score, submitted_at
        FROM submissions
        WHERE spec_id = ? AND passed = 1
        ORDER BY
            CASE WHEN COALESCE(score_direction, 'minimize') = 'maximize'
                 THEN -COALESCE(score, mass_grams)
                 ELSE  COALESCE(score, mass_grams)
            END ASC
        LIMIT 1
    """
    async with get_db() as db:
        async with db.execute(query, (spec_id,)) as cur:
            row = await cur.fetchone()

    if row is None:
        return True, None  # No existing SOTA — always eligible.

    current_score = float(row["best_score"])
    sota_at = datetime.fromisoformat(row["submitted_at"]).replace(tzinfo=timezone.utc)
    age_days = (datetime.now(timezone.utc) - sota_at).total_seconds() / 86400
    eligible, _ = compute_sota_eligible(score, current_score, age_days, direction)
    return eligible, current_score


def _row_to_submission(row) -> Submission:
    raw_eligible = row["sota_eligible"]
    raw_score = row["score"]
    return Submission(
        id=uuid.UUID(row["id"]),
        spec_id=row["spec_id"],
        agent_path=row["agent_path"],
        contributor=row["contributor"],
        commit_hash=row["commit_hash"],
        mass_grams=row["mass_grams"],
        fea_stress_mpa=row["fea_stress_mpa"],
        fea_allowable_mpa=row["fea_allowable_mpa"],
        passed=bool(row["passed"]),
        pr_number=row["pr_number"],
        notes=row["notes"],
        submitted_at=datetime.fromisoformat(row["submitted_at"]),
        has_step=row["step_data"] is not None,
        sota_eligible=bool(raw_eligible) if raw_eligible is not None else None,
        score=raw_score if raw_score is not None else row["mass_grams"],
        score_metric=row["score_metric"] or "mass_grams",
        score_direction=row["score_direction"] or "minimize",
    )


def _build_submission(sub_id: str, now: str, body: SubmissionCreate, has_step: bool, eligible: bool, score: float) -> Submission:
    return Submission(
        id=uuid.UUID(sub_id),
        spec_id=body.spec_id,
        agent_path=body.agent_path,
        contributor=body.contributor,
        commit_hash=body.commit_hash,
        mass_grams=body.mass_grams,
        fea_stress_mpa=body.fea_stress_mpa,
        fea_allowable_mpa=body.fea_allowable_mpa,
        passed=body.passed,
        pr_number=body.pr_number,
        notes=body.notes,
        submitted_at=datetime.fromisoformat(now),
        has_step=has_step,
        sota_eligible=eligible,
        score=score,
        score_metric=body.score_metric,
        score_direction=body.score_direction,
    )
