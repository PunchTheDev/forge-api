from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app import specs as spec_store
from app.db import get_db
from app.models import SotaEligibility, SotaHistoryPoint, SotaRecord
from app.scoring import sota_eligible, sota_margin_threshold

router = APIRouter(prefix="/sota", tags=["sota"])


@router.get("", response_model=list[SotaRecord])
async def list_sota():
    specs = spec_store.load_all()
    results = []
    for spec in specs:
        record = await _get_sota(spec.id)
        if record is not None:
            results.append(record)
    return results


@router.get("/{spec_id}/eligibility", response_model=SotaEligibility)
async def get_sota_eligibility(spec_id: str, score: float = Query(...)):
    if spec_store.load_one(spec_id) is None:
        raise HTTPException(status_code=404, detail=f"Spec '{spec_id}' not found")

    record = await _get_sota(spec_id)
    if record is None:
        return SotaEligibility(
            eligible=True,
            required_improvement_pct=0.0,
            current_score=0.0,
            margin_grams=0.0,
            reason="No current SOTA — any passing submission is eligible",
        )

    age_days = (datetime.now(timezone.utc) - record.submitted_at.replace(tzinfo=timezone.utc)).total_seconds() / 86400
    threshold_pct = sota_margin_threshold(age_days)
    required_improvement = abs(record.score) * threshold_pct
    eligible, reason = sota_eligible(score, record.score, age_days, record.score_direction)

    return SotaEligibility(
        eligible=eligible,
        required_improvement_pct=threshold_pct * 100,
        current_score=record.score,
        margin_grams=required_improvement,
        reason=reason,
    )


@router.get("/{spec_id}/history", response_model=list[SotaHistoryPoint])
async def get_sota_history(spec_id: str):
    """Progressive SOTA history — each entry is a moment the record improved."""
    if spec_store.load_one(spec_id) is None:
        raise HTTPException(status_code=404, detail=f"Spec '{spec_id}' not found")

    query = """
        SELECT COALESCE(score, mass_grams) AS s, contributor, agent_path, submitted_at,
               COALESCE(score_direction, 'minimize') AS direction
        FROM submissions
        WHERE spec_id = ? AND passed = 1
        ORDER BY submitted_at ASC
    """
    async with get_db() as db:
        async with db.execute(query, (spec_id,)) as cur:
            rows = await cur.fetchall()

    if not rows:
        return []

    direction = rows[0]["direction"]
    history: list[SotaHistoryPoint] = []
    running_best: float | None = None

    for row in rows:
        score = float(row["s"])
        if running_best is None:
            is_new_best = True
        elif direction == "maximize":
            is_new_best = score > running_best
        else:
            is_new_best = score < running_best

        if is_new_best:
            running_best = score
            history.append(
                SotaHistoryPoint(
                    score=score,
                    contributor=row["contributor"],
                    agent_path=row["agent_path"],
                    submitted_at=datetime.fromisoformat(row["submitted_at"]),
                )
            )

    return history


@router.get("/{spec_id}", response_model=SotaRecord)
async def get_sota(spec_id: str):
    if spec_store.load_one(spec_id) is None:
        raise HTTPException(status_code=404, detail=f"Spec '{spec_id}' not found")
    record = await _get_sota(spec_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No passing submissions for spec '{spec_id}'")
    return record


async def _get_sota(spec_id: str) -> SotaRecord | None:
    # Direction-aware SOTA: negate score for "maximize" metrics so ASC always picks best.
    # score_direction defaults to 'minimize' for pre-migration rows.
    query = """
        SELECT * FROM submissions
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
        return None

    raw_score = row["score"]
    score = raw_score if raw_score is not None else row["mass_grams"]
    score_metric = row["score_metric"] or "mass_grams"
    score_direction = row["score_direction"] or "minimize"
    return SotaRecord(
        spec_id=row["spec_id"],
        submission_id=str(row["id"]),
        has_step=(
            (bool(row["step_data"]) if "step_data" in row.keys() else False)
            or (bool(row["step_key"]) if "step_key" in row.keys() else False)
        ),
        score_grams=row["mass_grams"],
        score=score,
        score_metric=score_metric,
        score_direction=score_direction,
        agent=row["agent_path"],
        contributor=row["contributor"],
        fea_stress_mpa=row["fea_stress_mpa"],
        fea_allowable_mpa=row["fea_allowable_mpa"],
        commit_hash=row["commit_hash"],
        submitted_at=datetime.fromisoformat(row["submitted_at"]),
        note=row["notes"],
    )
