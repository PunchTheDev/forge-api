"""Rounds endpoints — list competition rounds and their spec sets."""

import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import get_db

ROUNDS_DIR = os.environ.get("ROUNDS_DIR", "data/rounds")

router = APIRouter(prefix="/rounds", tags=["rounds"])


class RoundSpec(BaseModel):
    id: str
    tier: str
    file: str | None = None  # forge repo path; not required by API


class Round(BaseModel):
    id: str
    name: str
    description: str
    status: str
    starts: str | None = None
    ends: str | None = None
    scoring_metric: str
    scoring_direction: str
    specs: list[RoundSpec]
    notes: str | None = None


class TierStats(BaseModel):
    total: int
    claimed: int
    unclaimed: int


class RoundStats(BaseModel):
    round_id: str
    specs_total: int
    specs_claimed: int
    specs_unclaimed: int
    contributor_count: int
    tiers: dict[str, TierStats]


def _load_rounds() -> list[Round]:
    path = Path(ROUNDS_DIR)
    if not path.exists():
        return []
    rounds = []
    for f in sorted(path.glob("*.json")):
        try:
            with open(f) as fh:
                raw = json.load(fh)
            rounds.append(Round.model_validate(raw))
        except Exception:
            pass
    return rounds


@router.get("", response_model=list[Round])
async def list_rounds():
    return _load_rounds()


@router.get("/active", response_model=list[Round])
async def list_active_rounds():
    return [r for r in _load_rounds() if r.status == "active"]


@router.get("/{round_id}/stats", response_model=RoundStats)
async def get_round_stats(round_id: str):
    """Competition statistics for a round: claimed/unclaimed specs, contributor count, tier breakdown."""
    path = Path(ROUNDS_DIR) / f"{round_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Round '{round_id}' not found")
    with open(path) as fh:
        round_data = Round.model_validate(json.load(fh))

    spec_ids = [s.id for s in round_data.specs]
    if not spec_ids:
        return RoundStats(
            round_id=round_id,
            specs_total=0,
            specs_claimed=0,
            specs_unclaimed=0,
            contributor_count=0,
            tiers={},
        )

    placeholders = ",".join("?" * len(spec_ids))
    query = f"""
        SELECT spec_id, COUNT(DISTINCT contributor) as contributors
        FROM submissions
        WHERE spec_id IN ({placeholders}) AND passed = 1
        GROUP BY spec_id
    """
    contributor_query = f"""
        SELECT COUNT(DISTINCT contributor) as cnt
        FROM submissions
        WHERE spec_id IN ({placeholders}) AND passed = 1
    """
    async with get_db() as db:
        async with db.execute(query, spec_ids) as cur:
            rows = await cur.fetchall()
        async with db.execute(contributor_query, spec_ids) as cur:
            contrib_row = await cur.fetchone()

    claimed_spec_ids = {row["spec_id"] for row in rows}
    specs_claimed = len(claimed_spec_ids)
    contributor_count = int(contrib_row["cnt"]) if contrib_row else 0

    # Tier breakdown
    tier_map: dict[str, list[str]] = {}
    for s in round_data.specs:
        tier_map.setdefault(s.tier, []).append(s.id)

    tiers: dict[str, TierStats] = {}
    for tier, ids in tier_map.items():
        tier_claimed = len([sid for sid in ids if sid in claimed_spec_ids])
        tiers[tier] = TierStats(total=len(ids), claimed=tier_claimed, unclaimed=len(ids) - tier_claimed)

    return RoundStats(
        round_id=round_id,
        specs_total=len(spec_ids),
        specs_claimed=specs_claimed,
        specs_unclaimed=len(spec_ids) - specs_claimed,
        contributor_count=contributor_count,
        tiers=tiers,
    )


@router.get("/{round_id}", response_model=Round)
async def get_round(round_id: str):
    path = Path(ROUNDS_DIR) / f"{round_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Round '{round_id}' not found")
    with open(path) as fh:
        return Round.model_validate(json.load(fh))
