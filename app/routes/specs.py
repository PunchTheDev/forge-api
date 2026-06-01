from fastapi import APIRouter, HTTPException

from app import specs as spec_store
from app.models import Spec

router = APIRouter(prefix="/specs", tags=["specs"])


@router.get("", response_model=list[Spec])
async def list_specs():
    return spec_store.load_all()


@router.get("/{spec_id}", response_model=Spec)
async def get_spec(spec_id: str):
    spec = spec_store.load_one(spec_id)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Spec '{spec_id}' not found")
    return spec
