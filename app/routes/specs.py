import json
import os
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app import specs as spec_store
from app.db import get_db
from app.models import Spec

router = APIRouter(prefix="/specs", tags=["specs"])

_TIERS = Literal["easy", "medium", "hard"]

_ROUNDS_DIR = os.environ.get("ROUNDS_DIR", "data/rounds")


def _active_round_ids() -> set[str]:
    """Return IDs of rounds with status='active'."""
    path = Path(_ROUNDS_DIR)
    if not path.exists():
        return set()
    active: set[str] = set()
    for f in sorted(path.glob("*.json")):
        try:
            with open(f) as fh:
                raw = json.load(fh)
            if raw.get("status") == "active":
                active.add(raw["id"])
        except Exception:
            pass
    return active


async def _claimed_spec_ids() -> set[str]:
    """Return spec IDs that have at least one passing submission (SOTA claimed)."""
    async with get_db() as db:
        async with db.execute(
            "SELECT DISTINCT spec_id FROM submissions WHERE passed = 1"
        ) as cur:
            rows = await cur.fetchall()
    return {row["spec_id"] for row in rows}


@router.get("", response_model=list[Spec])
async def list_specs(
    tier: _TIERS | None = Query(None, description="Filter by difficulty tier (easy/medium/hard)"),
    round_id: str | None = Query(None, description="Filter by round ID (e.g. round_001)"),
    material: str | None = Query(None, description="Filter by material (e.g. pla, petg, aluminum_6061, stainless_316)"),
    active: bool | None = Query(None, description="When true, return only specs in currently active rounds"),
    unclaimed: bool | None = Query(None, description="When true, return only specs with no passing submission (no SOTA set yet)"),
):
    specs = spec_store.load_all()
    # unclaimed=true implies active-round context: non-competition specs (e.g.
    # Thingiverse catalog entries) have no round and are never "claimable".
    if active or unclaimed:
        active_ids = _active_round_ids()
        specs = [s for s in specs if s.round_id in active_ids]
    if tier is not None:
        specs = [s for s in specs if s.tier == tier]
    if round_id is not None:
        specs = [s for s in specs if s.round_id == round_id]
    if material is not None:
        specs = [s for s in specs if s.material == material]
    if unclaimed is not None:
        claimed = await _claimed_spec_ids()
        if unclaimed:
            specs = [s for s in specs if s.id not in claimed]
        else:
            specs = [s for s in specs if s.id in claimed]
    return specs


@router.get("/{spec_id}", response_model=Spec)
async def get_spec(spec_id: str):
    spec = spec_store.load_one(spec_id)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Spec '{spec_id}' not found")
    return spec
