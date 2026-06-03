"""Forge API — source of truth for specs, submissions, leaderboard, and SOTA."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    version="0.13.2",
    lifespan=lifespan,
)

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
