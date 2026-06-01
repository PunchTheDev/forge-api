"""Seed data/specs/ from a local forge repo checkout and POST the initial SOTA."""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

import httpx

API_BASE = os.environ.get("API_BASE", "http://localhost:8000")


def seed_specs(forge_path: Path) -> None:
    src = forge_path / "specs"
    dst = Path("data/specs")
    dst.mkdir(parents=True, exist_ok=True)
    for f in src.glob("*.json"):
        shutil.copy(f, dst / f.name)
        print(f"Copied spec: {f.name}")


def seed_sota(forge_path: Path) -> None:
    sota_path = forge_path / "sota" / "score.json"
    if not sota_path.exists():
        print("No sota/score.json found — skipping SOTA seed")
        return

    with open(sota_path) as fh:
        sota = json.load(fh)

    payload = {
        "spec_id": sota["spec_id"],
        "agent_path": sota["agent"],
        "contributor": sota["contributor"],
        "commit_hash": sota["commit"],
        "mass_grams": sota["score_grams"],
        "fea_stress_mpa": sota["fea_stress_mpa"],
        "fea_allowable_mpa": sota["fea_allowable_mpa"],
        "passed": True,
        "notes": sota.get("note"),
    }

    r = httpx.post(f"{API_BASE}/submissions", json=payload)
    r.raise_for_status()
    print(f"Seeded SOTA submission: {r.json()['id']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed forge-api from a forge repo")
    parser.add_argument("forge_path", help="Path to local forge repo")
    args = parser.parse_args()

    forge = Path(args.forge_path)
    if not forge.exists():
        print(f"forge path not found: {forge}", file=sys.stderr)
        sys.exit(1)

    seed_specs(forge)
    seed_sota(forge)
    print("Done.")


if __name__ == "__main__":
    main()
