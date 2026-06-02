import base64
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.db import get_db
from app.models import Submission, SubmissionCreate

router = APIRouter(prefix="/submissions", tags=["submissions"])


@router.post("", response_model=Submission, status_code=201)
async def create_submission(body: SubmissionCreate):
    sub_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    step_data = base64.b64decode(body.step_b64) if body.step_b64 else None

    async with get_db() as db:
        await db.execute(
            """INSERT INTO submissions
               (id, spec_id, agent_path, contributor, commit_hash, mass_grams,
                fea_stress_mpa, fea_allowable_mpa, passed, pr_number, notes, submitted_at, step_data)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
            ),
        )
        await db.commit()

    return _build_submission(sub_id, now, body, step_data is not None)


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


def _row_to_submission(row) -> Submission:
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
    )


def _build_submission(sub_id: str, now: str, body: SubmissionCreate, has_step: bool) -> Submission:
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
    )
