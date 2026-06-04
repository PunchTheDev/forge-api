import json
import os
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app import specs as spec_store
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


@router.get("", response_model=list[Spec])
async def list_specs(
    tier: _TIERS | None = Query(None, description="Filter by difficulty tier (easy/medium/hard)"),
    round_id: str | None = Query(None, description="Filter by round ID (e.g. round_001)"),
    material: str | None = Query(None, description="Filter by material (e.g. pla, petg, aluminum_6061, stainless_316)"),
    active: bool | None = Query(None, description="When true, return only specs in currently active rounds"),
):
    specs = spec_store.load_all()
    if active:
        active_ids = _active_round_ids()
        specs = [s for s in specs if s.round_id in active_ids]
    if tier is not None:
        specs = [s for s in specs if s.tier == tier]
    if round_id is not None:
        specs = [s for s in specs if s.round_id == round_id]
    if material is not None:
        specs = [s for s in specs if s.material == material]
    return specs


@router.get("/{spec_id}", response_model=Spec)
async def get_spec(spec_id: str):
    spec = spec_store.load_one(spec_id)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Spec '{spec_id}' not found")
    return spec
