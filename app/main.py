"""Forge API — source of truth for specs, submissions, leaderboard, and SOTA."""

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
    version="0.15.5",
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
