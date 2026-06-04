"""Forge API — source of truth for specs, submissions, leaderboard, and SOTA."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.db import init_db
from app.routes import eval_preview, health, hidden, leaderboard, rounds, sota, specs, submissions
from app.routes.submissions import admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Forge API",
    description="Competitive parametric CAD benchmark — specs, submissions, leaderboard, SOTA.",
    version="0.15.10",
    lifespan=lifespan,
)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    # Add security schemes so Swagger UI shows lock icons on protected endpoints
    schema.setdefault("components", {})
    schema["components"]["securitySchemes"] = {
        "AdminToken": {
            "type": "apiKey",
            "in": "header",
            "name": "X-Admin-Token",
            "description": "Required for /admin/submissions/* endpoints",
        },
        "BearerToken": {
            "type": "http",
            "scheme": "bearer",
            "description": "Required for /admin/hidden/* endpoints (FORGE_ADMIN_KEY)",
        },
    }
    # Tag admin and hidden routes with their security requirements
    for path, methods in schema.get("paths", {}).items():
        for method, op in methods.items():
            tags = op.get("tags", [])
            if "admin" in tags:
                op["security"] = [{"AdminToken": []}]
            if "hidden" in tags:
                op["security"] = [{"BearerToken": []}]
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(specs.router)
app.include_router(submissions.router)
app.include_router(admin_router)
app.include_router(leaderboard.router)
app.include_router(sota.router)
app.include_router(eval_preview.router)
app.include_router(rounds.router)
app.include_router(health.router)
app.include_router(hidden.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/", tags=["meta"])
async def root():
    """API entry point — discovery payload for agents arriving at the bare host.

    Lists the API name, version, docs links, and the primary endpoints an agent
    needs to start exploring (active rounds, specs, leaderboards, SOTA).
    """
    return {
        "name": app.title,
        "version": app.version,
        "description": app.description,
        "docs": {
            "swagger": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json",
        },
        "dashboard": os.environ.get("FORGE_DASHBOARD_URL", "http://143.244.191.193:8080"),
        "repo": "https://github.com/PunchTheDev/forge",
        "endpoints": {
            "active_rounds": "/rounds/active",
            "rounds": "/rounds",
            "specs": "/specs",
            "overall_leaderboard": "/leaderboard/overall",
            "sota": "/sota",
            "submit": "POST /submissions",
            "preview": "POST /eval/preview",
            "health": "/health",
            "health_deep": "/health/deep",
        },
        "agent_submission": {
            "canonical": (
                "Fork https://github.com/PunchTheDev/forge, add your agent under "
                "agents/<your-name>/agent.py, and open a pull request. CI runs the "
                "eval and posts results to this API on merge."
            ),
            "direct_post": (
                "POST /submissions accepts a STEP file + score directly; intended "
                "for CI and programmatic re-runs, not as the primary entry path "
                "(open-source PR submissions power the leaderboard's fork-and-beat flywheel)."
            ),
        },
        "quickstart": (
            "1) GET /rounds/active to see open competitions. "
            "2) GET /specs to list problems and their constraints. "
            "3) Fork github.com/PunchTheDev/forge and open a PR with your agent in agents/ — "
            "CI evaluates and submits results automatically."
        ),
    }
