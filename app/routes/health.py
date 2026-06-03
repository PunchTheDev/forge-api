"""Deep health check — verifies DB, rounds, specs, and storage are accessible."""

import asyncio

from fastapi import APIRouter

import app.storage as storage
from app.db import get_db
from app.routes.rounds import _load_rounds
from app.specs import load_all as load_all_specs

router = APIRouter(tags=["health"])


@router.get("/health/deep")
async def health_deep():
    checks: dict[str, object] = {}
    ok = True

    # DB check — simple row count
    try:
        async with get_db() as db:
            async with db.execute("SELECT COUNT(*) FROM submissions") as cur:
                row = await cur.fetchone()
        checks["db"] = {"status": "ok", "submission_count": row[0]}
    except Exception as exc:
        checks["db"] = {"status": "error", "detail": str(exc)}
        ok = False

    # Rounds check
    try:
        rounds = _load_rounds()
        active = [r.id for r in rounds if r.status == "active"]
        checks["rounds"] = {"status": "ok", "total": len(rounds), "active": active}
        if not rounds:
            checks["rounds"]["status"] = "warn"
            ok = False
    except Exception as exc:
        checks["rounds"] = {"status": "error", "detail": str(exc)}
        ok = False

    # Specs check
    try:
        all_specs = load_all_specs()
        checks["specs"] = {"status": "ok", "total": len(all_specs)}
        if not all_specs:
            checks["specs"]["status"] = "warn"
    except Exception as exc:
        checks["specs"] = {"status": "error", "detail": str(exc)}
        ok = False

    # Storage check
    if storage.is_configured():
        try:
            bucket = __import__("os").environ["S3_BUCKET"]

            def _head():
                storage._client().head_bucket(Bucket=bucket)

            await asyncio.to_thread(_head)
            checks["storage"] = {"status": "ok", "backend": "s3", "bucket": bucket}
        except Exception as exc:
            checks["storage"] = {"status": "error", "backend": "s3", "detail": str(exc)}
            ok = False
    else:
        checks["storage"] = {"status": "ok", "backend": "sqlite_blob"}

    return {"status": "ok" if ok else "degraded", "checks": checks}
