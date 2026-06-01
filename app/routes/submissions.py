import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.db import get_db
from app.models import Submission, SubmissionCreate

router = APIRouter(prefix="/submissions", tags=["submissions"])


@router.post("", response_model=Submission, status_code=201)
async def create_submission(body: SubmissionCreate):
    sub_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    async with get_db() as db:
        await db.execute(
            """INSERT INTO submissions
               (id, spec_id, agent_path, contributor, commit_hash, mass_grams,
                fea_stress_mpa, fea_allowable_mpa, passed, pr_number, notes, submitted_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
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
            ),
        )
        await db.commit()

    return Submission(id=uuid.UUID(sub_id), submitted_at=datetime.fromisoformat(now), **body.model_dump())


@router.get("", response_model=list[Submission])
async def list_submissions(
    spec_id: str | None = Query(None),
    contributor: str | None = Query(None),
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
    )
