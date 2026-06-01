"""Spec loading from local JSON files."""

import json
import os
from pathlib import Path

from app.models import Spec

SPECS_DIR = os.environ.get("SPECS_DIR", "data/specs")


def load_all() -> list[Spec]:
    path = Path(SPECS_DIR)
    if not path.exists():
        return []
    specs = []
    for f in sorted(path.glob("*.json")):
        with open(f) as fh:
            raw = json.load(fh)
        specs.append(Spec.model_validate(raw))
    return specs


def load_one(spec_id: str) -> Spec | None:
    path = Path(SPECS_DIR) / f"{spec_id}.json"
    if not path.exists():
        return None
    with open(path) as fh:
        return Spec.model_validate(json.load(fh))
