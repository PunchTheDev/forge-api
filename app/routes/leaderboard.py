from collections import defaultdict

from fastapi import APIRouter, HTTPException

from app import specs as spec_store
from app.db import get_db
from app.models import (
    Leaderboard,
    LeaderboardEntry,
    OverallBestEntry,
    OverallLeaderboard,
    OverallLeaderboardEntry,
)
from app.routes.rounds import _load_rounds

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("/overall", response_model=OverallLeaderboard)
async def get_overall_leaderboard():
    """Cross-spec leaderboard: ranks contributors by mean rank position across entered specs.

    avg_rank = mean(per-spec rank) across all specs a contributor has entered (lower is better).
    A contributor with avg_rank 1.0 holds #1 on every spec they entered.
    Tiebreak: specs_entered DESC (more breadth wins ties).
    Only active-round specs contribute; legacy seed specs are excluded.
    normalized_score per entry is still returned for per-spec reference display.
    """
    # Only rank against active-round specs; legacy seed specs are excluded.
    active_rounds = [r for r in _load_rounds() if r.status == "active"]
    active_spec_ids = {s.id for r in active_rounds for s in r.specs}

    all_specs = spec_store.load_all()
    round_specs = [s for s in all_specs if s.id in active_spec_ids]
    total_specs = len(round_specs)
    baseline_by_spec = {s.id: s.scoring.baseline_score for s in round_specs}
    direction_by_spec = {s.id: s.scoring.direction for s in round_specs}

    # Per-spec best per contributor, direction-aware.
    per_spec_rows: dict[str, list] = {}
    async with get_db() as db:
        for spec in round_specs:
            direction = spec.scoring.direction
            if direction == "maximize":
                best_agg = "MAX(COALESCE(score, mass_grams))"
                order_clause = "COALESCE(s.score, s.mass_grams) DESC"
            else:
                best_agg = "MIN(COALESCE(score, mass_grams))"
                order_clause = "COALESCE(s.score, s.mass_grams) ASC"
            query = f"""
                SELECT s.id as submission_id, s.contributor,
                       s.mass_grams, COALESCE(s.score, s.mass_grams) as score,
                       COALESCE(s.score_metric, 'mass_grams') as score_metric,
                       s.submitted_at
                FROM submissions s
                INNER JOIN (
                    SELECT contributor, {best_agg} as best_score
                    FROM submissions
                    WHERE spec_id = ? AND passed = 1
                    GROUP BY contributor
                ) best ON s.contributor = best.contributor
                       AND COALESCE(s.score, s.mass_grams) = best.best_score
                       AND s.spec_id = ?
                       AND s.passed = 1
                ORDER BY {order_clause}
            """
            async with db.execute(query, (spec.id, spec.id)) as cur:
                per_spec_rows[spec.id] = await cur.fetchall()

    # Aggregate per contributor. Normalize so lower is always better across metrics.
    contrib_bests: dict[str, list[OverallBestEntry]] = defaultdict(list)
    for spec_id, rows in per_spec_rows.items():
        baseline = baseline_by_spec.get(spec_id, 1.0)
        direction = direction_by_spec.get(spec_id, "minimize")
        for rank_idx, row in enumerate(rows):
            score = row["score"]
            if direction == "maximize":
                normalized = (baseline / score) if score else 1.0
            else:
                normalized = (score / baseline) if baseline else 1.0
            contrib_bests[row["contributor"]].append(
                OverallBestEntry(
                    spec_id=spec_id,
                    rank=rank_idx + 1,
                    mass_grams=row["mass_grams"],
                    score=score,
                    score_metric=row["score_metric"],
                    normalized_score=normalized,
                    submission_id=row["submission_id"],
                    submitted_at=row["submitted_at"],
                )
            )

    if not contrib_bests:
        return OverallLeaderboard(total_specs=total_specs, entries=[])

    entries: list[OverallLeaderboardEntry] = []
    for contributor, bests in contrib_bests.items():
        specs_entered = len(bests)
        total_wins = sum(1 for b in bests if b.rank == 1)
        avg_rank = sum(b.rank for b in bests) / specs_entered
        entries.append(
            OverallLeaderboardEntry(
                rank=0,  # filled below after sort
                contributor=contributor,
                specs_entered=specs_entered,
                total_wins=total_wins,
                avg_rank=round(avg_rank, 4),
                best=sorted(bests, key=lambda b: b.spec_id),
            )
        )

    # Primary sort: avg_rank ASC (lower = better); tiebreak: specs_entered DESC (more breadth wins ties)
    entries.sort(key=lambda e: (e.avg_rank, -e.specs_entered))
    for i, entry in enumerate(entries):
        entry.rank = i + 1

    return OverallLeaderboard(total_specs=total_specs, entries=entries)


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
    # Load spec to determine score direction.
    spec = spec_store.load_one(spec_id)
    direction = spec.scoring.direction if spec else "minimize"
    metric = spec.scoring.metric if spec else "mass_grams"

    # For each contributor, find their best submission using the spec's scoring direction.
    # COALESCE(score, mass_grams) is the canonical score value for any metric.
    # For maximize metrics we want MAX; for minimize we want MIN.
    if direction == "maximize":
        best_agg = "MAX(COALESCE(score, mass_grams))"
        order_clause = "COALESCE(s.score, s.mass_grams) DESC"
    else:
        best_agg = "MIN(COALESCE(score, mass_grams))"
        order_clause = "COALESCE(s.score, s.mass_grams) ASC"

    query = f"""
        SELECT s.id as submission_id, s.contributor, s.agent_path,
               s.mass_grams, COALESCE(s.score, s.mass_grams) as score,
               COALESCE(s.score_metric, 'mass_grams') as score_metric,
               COALESCE(s.score_direction, 'minimize') as score_direction,
               s.fea_stress_mpa, s.commit_hash,
               s.submitted_at, s.pr_number,
               (s.step_data IS NOT NULL) as has_step
        FROM submissions s
        INNER JOIN (
            SELECT contributor, {best_agg} as best_score
            FROM submissions
            WHERE spec_id = ? AND passed = 1
            GROUP BY contributor
        ) best ON s.contributor = best.contributor
               AND COALESCE(s.score, s.mass_grams) = best.best_score
               AND s.spec_id = ?
               AND s.passed = 1
        ORDER BY {order_clause}
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
            score=r["score"],
            score_metric=r["score_metric"],
            score_direction=r["score_direction"],
            fea_stress_mpa=r["fea_stress_mpa"],
            commit_hash=r["commit_hash"],
            submitted_at=r["submitted_at"],
            pr_number=r["pr_number"],
            has_step=bool(r["has_step"]),
        )
        for i, r in enumerate(rows)
    ]
    return Leaderboard(spec_id=spec_id, entries=entries)
