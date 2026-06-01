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
    # Best submission per contributor: the row with minimum mass.
    # Subquery finds the min-mass submission ID per contributor so we can
    # return submission_id (for the STEP viewer) and has_step.
    query = """
        SELECT s.id as submission_id, s.contributor, s.agent_path,
               s.mass_grams, s.fea_stress_mpa, s.commit_hash,
               s.submitted_at, s.pr_number,
               (s.step_data IS NOT NULL) as has_step
        FROM submissions s
        INNER JOIN (
            SELECT contributor, MIN(mass_grams) as min_mass
            FROM submissions
            WHERE spec_id = ? AND passed = 1
            GROUP BY contributor
        ) best ON s.contributor = best.contributor
               AND s.mass_grams = best.min_mass
               AND s.spec_id = ?
               AND s.passed = 1
        ORDER BY s.mass_grams ASC
    """
    async with get_db() as db:
        async with db.execute(query, (spec_id, spec_id)) as cur:
            rows = await cur.fetchall()

    entries = [
        LeaderboardEntry(
            rank=i + 1,
            submission_id=r["submission_id"],
            contributor=r["contributor"],
            agent_path=r["agent_path"],
            mass_grams=r["mass_grams"],
            fea_stress_mpa=r["fea_stress_mpa"],
            commit_hash=r["commit_hash"],
            submitted_at=r["submitted_at"],
            pr_number=r["pr_number"],
            has_step=bool(r["has_step"]),
        )
        for i, r in enumerate(rows)
    ]
    return Leaderboard(spec_id=spec_id, entries=entries)
