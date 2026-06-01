from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app import specs as spec_store
from app.db import get_db
from app.models import SotaRecord

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


@router.get("/{spec_id}", response_model=SotaRecord)
async def get_sota(spec_id: str):
    if spec_store.load_one(spec_id) is None:
        raise HTTPException(status_code=404, detail=f"Spec '{spec_id}' not found")
    record = await _get_sota(spec_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No passing submissions for spec '{spec_id}'")
    return record


async def _get_sota(spec_id: str) -> SotaRecord | None:
    query = """
        SELECT * FROM submissions
        WHERE spec_id = ? AND passed = 1
        ORDER BY mass_grams ASC
        LIMIT 1
    """
    async with get_db() as db:
        async with db.execute(query, (spec_id,)) as cur:
            row = await cur.fetchone()

    if row is None:
        return None

    return SotaRecord(
        spec_id=row["spec_id"],
        score_grams=row["mass_grams"],
        agent=row["agent_path"],
        contributor=row["contributor"],
        fea_stress_mpa=row["fea_stress_mpa"],
        fea_allowable_mpa=row["fea_allowable_mpa"],
        commit_hash=row["commit_hash"],
        submitted_at=datetime.fromisoformat(row["submitted_at"]),
        note=row["notes"],
    )
