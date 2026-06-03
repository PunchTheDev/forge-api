from fastapi import APIRouter, HTTPException, Query
from typing import Literal

from app import specs as spec_store
from app.models import Spec

router = APIRouter(prefix="/specs", tags=["specs"])

_TIERS = Literal["easy", "medium", "hard"]


@router.get("", response_model=list[Spec])
async def list_specs(
    tier: _TIERS | None = Query(None, description="Filter by difficulty tier (easy/medium/hard)"),
    round_id: str | None = Query(None, description="Filter by round ID (e.g. round_001)"),
    material: str | None = Query(None, description="Filter by material (e.g. pla, petg, aluminum_6061, stainless_316)"),
):
    specs = spec_store.load_all()
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
