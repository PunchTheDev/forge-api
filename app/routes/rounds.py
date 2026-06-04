"""Rounds endpoints — list competition rounds and their spec sets."""

import json
import os
from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import specs as spec_store
from app.db import get_db
from app.models import OverallBestEntry, OverallLeaderboardEntry, RoundLeaderboard

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


@router.get("/{round_id}/leaderboard", response_model=RoundLeaderboard)
async def get_round_leaderboard(round_id: str):
    """Per-round leaderboard: contributors ranked by breadth-normalized score within this round.

    round_score = mean(per_spec_rank_fraction) across all specs in the round.
    Unentered specs count as rank_fraction = 1.0 (baseline). Lower is better.

    A contributor who wins all specs in the round has a round_score approaching 1/(N+1)
    where N = total contributors in the round. A contributor who enters none scores 1.0.
    """
    path = Path(ROUNDS_DIR) / f"{round_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Round '{round_id}' not found")
    with open(path) as fh:
        round_data = Round.model_validate(json.load(fh))

    spec_ids = [s.id for s in round_data.specs]
    if not spec_ids:
        return RoundLeaderboard(round_id=round_id, total_specs=0, entries=[])

    # Load full spec metadata so we have direction per spec.
    all_specs = spec_store.load_all()
    spec_meta = {s.id: s for s in all_specs if s.id in set(spec_ids)}
    direction_by_spec = {sid: spec_meta[sid].scoring.direction for sid in spec_ids if sid in spec_meta}

    placeholders = ",".join("?" * len(spec_ids))
    query = f"""
        SELECT s.id as submission_id, s.spec_id, s.contributor,
               s.mass_grams, COALESCE(s.score, s.mass_grams) as score,
               COALESCE(s.score_metric, 'mass_grams') as score_metric,
               s.agent_path, s.commit_hash,
               s.submitted_at
        FROM submissions s
        WHERE s.spec_id IN ({placeholders}) AND s.passed = 1
    """
    async with get_db() as db:
        async with db.execute(query, spec_ids) as cur:
            all_rows = await cur.fetchall()

    # Best score per (spec, contributor)
    best_by: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in all_rows:
        spec_id = row["spec_id"]
        contributor = row["contributor"]
        score = row["score"]
        direction = direction_by_spec.get(spec_id, "minimize")
        existing = best_by[spec_id].get(contributor)
        if existing is None:
            best_by[spec_id][contributor] = dict(row)
        else:
            existing_score = existing["score"]
            is_better = (direction == "maximize" and score > existing_score) or \
                        (direction == "minimize" and score < existing_score)
            if is_better:
                best_by[spec_id][contributor] = dict(row)

    # Rank within each spec, compute normalized scores
    contrib_bests: dict[str, list[OverallBestEntry]] = defaultdict(list)
    for spec_id, contrib_map in best_by.items():
        direction = direction_by_spec.get(spec_id, "minimize")
        n_entered = len(contrib_map)
        ranked = sorted(
            contrib_map.values(),
            key=lambda r: r["score"],
            reverse=(direction == "maximize"),
        )
        for rank_idx, row in enumerate(ranked):
            rank = rank_idx + 1
            normalized = rank / (n_entered + 1)
            contrib_bests[row["contributor"]].append(
                OverallBestEntry(
                    spec_id=spec_id,
                    rank=rank,
                    mass_grams=row["mass_grams"],
                    score=row["score"],
                    score_metric=row["score_metric"],
                    normalized_score=normalized,
                    submission_id=row["submission_id"],
                    submitted_at=row["submitted_at"],
                    agent_path=row["agent_path"],
                    commit_hash=row["commit_hash"],
                )
            )

    total_specs = len(spec_ids)
    entries: list[OverallLeaderboardEntry] = []
    for contributor, bests in contrib_bests.items():
        specs_entered = len(bests)
        total_wins = sum(1 for b in bests if b.rank == 1)
        avg_rank = sum(b.rank for b in bests) / specs_entered
        entered_norm_sum = sum(b.normalized_score for b in bests)
        missing_specs = total_specs - specs_entered
        round_score = (entered_norm_sum + missing_specs * 1.0) / total_specs if total_specs else 1.0
        entries.append(
            OverallLeaderboardEntry(
                rank=0,
                contributor=contributor,
                specs_entered=specs_entered,
                total_wins=total_wins,
                avg_rank=round(avg_rank, 4),
                overall_score=round(round_score, 6),
                best=sorted(bests, key=lambda b: b.spec_id),
            )
        )

    entries.sort(key=lambda e: (e.overall_score, -e.specs_entered))
    for i, entry in enumerate(entries):
        entry.rank = i + 1

    return RoundLeaderboard(round_id=round_id, total_specs=total_specs, entries=entries)


@router.get("/{round_id}", response_model=Round)
async def get_round(round_id: str):
    path = Path(ROUNDS_DIR) / f"{round_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Round '{round_id}' not found")
    with open(path) as fh:
        return Round.model_validate(json.load(fh))
