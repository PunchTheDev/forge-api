from fastapi import APIRouter, HTTPException

from app import specs as spec_store
from app.db import get_db
from app.models import Leaderboard, LeaderboardEntry

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("", response_model=list[Leaderboard])
async def list_leaderboards():
    specs = spec_store.load_all()
    return [await _build_leaderboard(s.id) for s in specs]


@router.get("/{spec_id}", response_model=Leaderboard)
async def get_leaderboard(spec_id: str):
    if spec_store.load_one(spec_id) is None:
        raise HTTPException(status_code=404, detail=f"Spec '{spec_id}' not found")
    return await _build_leaderboard(spec_id)


async def _build_leaderboard(spec_id: str) -> Leaderboard:
    # Best score per contributor (lowest mass among passed submissions)
    query = """
        SELECT contributor, agent_path, MIN(mass_grams) as mass_grams,
               fea_stress_mpa, commit_hash, submitted_at, pr_number
        FROM submissions
        WHERE spec_id = ? AND passed = 1
        GROUP BY contributor
        ORDER BY mass_grams ASC
    """
    async with get_db() as db:
        async with db.execute(query, (spec_id,)) as cur:
            rows = await cur.fetchall()

    entries = [
        LeaderboardEntry(
            rank=i + 1,
            contributor=r["contributor"],
            agent_path=r["agent_path"],
            mass_grams=r["mass_grams"],
            fea_stress_mpa=r["fea_stress_mpa"],
            commit_hash=r["commit_hash"],
            submitted_at=r["submitted_at"],
            pr_number=r["pr_number"],
        )
        for i, r in enumerate(rows)
    ]
    return Leaderboard(spec_id=spec_id, entries=entries)
