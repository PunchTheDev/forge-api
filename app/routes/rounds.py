"""Rounds endpoints — list competition rounds and their spec sets."""

import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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


@router.get("/{round_id}", response_model=Round)
async def get_round(round_id: str):
    path = Path(ROUNDS_DIR) / f"{round_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Round '{round_id}' not found")
    with open(path) as fh:
        return Round.model_validate(json.load(fh))
