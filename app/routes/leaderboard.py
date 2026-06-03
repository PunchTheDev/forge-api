import time
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

# Simple in-memory TTL cache for the overall leaderboard — avoids 45 DB
# queries on every dashboard poll (30s interval).
_overall_cache: tuple[float, OverallLeaderboard] | None = None
_OVERALL_TTL = 60.0  # seconds


def invalidate_overall_cache() -> None:
    """Drop the in-memory overall leaderboard cache.

    Call this after any submission is accepted so the next request
    recomputes rankings instead of serving a stale result.
    """
    global _overall_cache
    _overall_cache = None


@router.get("/overall", response_model=OverallLeaderboard)
async def get_overall_leaderboard():
    """Cross-spec leaderboard: ranks contributors by breadth-normalized percentile rank.

    overall_score = mean(per_spec_rank_fraction) across ALL 45 active-round specs.

    Per-spec rank fraction = rank / (N + 1) where N = number of contributors entered.
    Not entering a spec counts as rank N+1, yielding exactly 1.0 (worst possible).
    Best contributor on a spec gets 1/(N+1); worst gets N/(N+1).

    This is fully metric-agnostic — deflection_mm, stiffness_to_weight, and mass_grams
    are treated identically regardless of how hard their baselines are to achieve.

    Lower overall_score = better. A perfect generalist sweeping all 45 specs → 1/(N+1).
    A mass-only specialist entering 15 specs: (15 * 1/(N+1) + 30 * 1.0) / 45.

    Only active-round specs contribute; legacy seed specs are excluded.
    avg_rank is also included over entered specs only for display purposes.
    """
    global _overall_cache
    now = time.monotonic()
    if _overall_cache is not None and now - _overall_cache[0] < _OVERALL_TTL:
        return _overall_cache[1]

    result = await _compute_overall_leaderboard()
    _overall_cache = (now, result)
    return result


async def _compute_overall_leaderboard() -> OverallLeaderboard:
    # Only rank against active-round specs; legacy seed specs are excluded.
    active_rounds = [r for r in _load_rounds() if r.status == "active"]
    active_spec_ids = {s.id for r in active_rounds for s in r.specs}

    all_specs = spec_store.load_all()
    round_specs = [s for s in all_specs if s.id in active_spec_ids]
    total_specs = len(round_specs)
    direction_by_spec = {s.id: s.scoring.direction for s in round_specs}

    if not round_specs:
        return OverallLeaderboard(total_specs=0, entries=[])

    # Single query: fetch every contributor's best row per spec in one pass.
    # We pull all passed submissions for active specs and aggregate in Python —
    # cheaper than 45 sequential queries at the cost of a slightly larger result set.
    spec_id_placeholders = ",".join("?" * len(round_specs))
    query = f"""
        SELECT s.id as submission_id, s.spec_id, s.contributor,
               s.mass_grams, COALESCE(s.score, s.mass_grams) as score,
               COALESCE(s.score_metric, 'mass_grams') as score_metric,
               s.submitted_at
        FROM submissions s
        WHERE s.spec_id IN ({spec_id_placeholders}) AND s.passed = 1
    """
    spec_ids = [s.id for s in round_specs]
    async with get_db() as db:
        async with db.execute(query, spec_ids) as cur:
            all_rows = await cur.fetchall()

    # Find each contributor's best score per spec (direction-aware).
    # best_by[spec_id][contributor] = best row seen so far
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
            if direction == "maximize" and score > existing_score:
                best_by[spec_id][contributor] = dict(row)
            elif direction == "minimize" and score < existing_score:
                best_by[spec_id][contributor] = dict(row)

    # Rank contributors within each spec, then build per-contributor best lists.
    # normalized_score = rank / (N + 1), where N = entries for that spec.
    # Not entering gives rank N+1 → normalized = 1.0 (worst possible, used below).
    contrib_bests: dict[str, list[OverallBestEntry]] = defaultdict(list)
    for spec_id, contrib_map in best_by.items():
        direction = direction_by_spec.get(spec_id, "minimize")
        n_entered = len(contrib_map)
        # Sort by score to determine ranks (1 = best)
        ranked = sorted(
            contrib_map.values(),
            key=lambda r: r["score"],
            reverse=(direction == "maximize"),
        )
        for rank_idx, row in enumerate(ranked):
            rank = rank_idx + 1
            # Percentile rank: 1/(N+1) = best, N/(N+1) = worst, 1.0 = not entered.
            normalized = rank / (n_entered + 1)
            score = row["score"]
            contrib_bests[row["contributor"]].append(
                OverallBestEntry(
                    spec_id=spec_id,
                    rank=rank,
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

        # avg_rank over entered specs only (for display)
        avg_rank = sum(b.rank for b in bests) / specs_entered

        # overall_score = mean normalized over ALL active specs.
        # Unentered specs count as 1.0 (baseline). Better-than-baseline = < 1.0.
        entered_norm_sum = sum(b.normalized_score for b in bests)
        missing_specs = total_specs - specs_entered
        overall_score = (entered_norm_sum + missing_specs * 1.0) / total_specs if total_specs else 1.0

        entries.append(
            OverallLeaderboardEntry(
                rank=0,  # filled below after sort
                contributor=contributor,
                specs_entered=specs_entered,
                total_wins=total_wins,
                avg_rank=round(avg_rank, 4),
                overall_score=round(overall_score, 6),
                best=sorted(bests, key=lambda b: b.spec_id),
            )
        )

    # Primary sort: overall_score ASC (lower = better — more specs beaten, by more margin)
    # Tiebreak: specs_entered DESC (more breadth wins ties at equal overall_score)
    entries.sort(key=lambda e: (e.overall_score, -e.specs_entered))
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
