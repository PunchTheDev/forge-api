"""SQLite database setup and connection management."""

import os
from contextlib import asynccontextmanager

import aiosqlite

DB_PATH = os.environ.get("DB_PATH", "data/forge.db")

CREATE_SUBMISSIONS = """
CREATE TABLE IF NOT EXISTS submissions (
    id          TEXT PRIMARY KEY,
    spec_id     TEXT NOT NULL,
    agent_path  TEXT NOT NULL,
    contributor TEXT NOT NULL,
    commit_hash TEXT NOT NULL,
    mass_grams  REAL NOT NULL,
    fea_stress_mpa   REAL NOT NULL,
    fea_allowable_mpa REAL NOT NULL,
    passed      INTEGER NOT NULL,
    pr_number   INTEGER,
    notes       TEXT,
    submitted_at TEXT NOT NULL,
    step_data   BLOB
)
"""

MIGRATE_ADD_STEP_DATA = """
ALTER TABLE submissions ADD COLUMN step_data BLOB
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_submissions_spec ON submissions(spec_id)",
    "CREATE INDEX IF NOT EXISTS idx_submissions_contributor ON submissions(contributor)",
    "CREATE INDEX IF NOT EXISTS idx_submissions_mass ON submissions(spec_id, mass_grams)",
]


async def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_SUBMISSIONS)
        for idx in CREATE_INDEXES:
            await db.execute(idx)
        # Migrate existing DBs that predate the step_data column.
        async with db.execute("PRAGMA table_info(submissions)") as cur:
            cols = {row[1] async for row in cur}
        if "step_data" not in cols:
            await db.execute(MIGRATE_ADD_STEP_DATA)
        await db.commit()


@asynccontextmanager
async def get_db():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db
