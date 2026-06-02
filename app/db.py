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
    step_data   BLOB,
    score       REAL,
    score_metric TEXT,
    score_direction TEXT DEFAULT 'minimize'
)
"""

MIGRATE_ADD_STEP_DATA = """
ALTER TABLE submissions ADD COLUMN step_data BLOB
"""

MIGRATE_ADD_SOTA_ELIGIBLE = """
ALTER TABLE submissions ADD COLUMN sota_eligible INTEGER
"""

MIGRATE_ADD_SCORE = """
ALTER TABLE submissions ADD COLUMN score REAL
"""

MIGRATE_ADD_SCORE_METRIC = """
ALTER TABLE submissions ADD COLUMN score_metric TEXT
"""

MIGRATE_ADD_SCORE_DIRECTION = """
ALTER TABLE submissions ADD COLUMN score_direction TEXT DEFAULT 'minimize'
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_submissions_spec ON submissions(spec_id)",
    "CREATE INDEX IF NOT EXISTS idx_submissions_contributor ON submissions(contributor)",
    "CREATE INDEX IF NOT EXISTS idx_submissions_mass ON submissions(spec_id, mass_grams)",
    "CREATE INDEX IF NOT EXISTS idx_submissions_score ON submissions(spec_id, score)",
]


async def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_SUBMISSIONS)
        for idx in CREATE_INDEXES:
            await db.execute(idx)
        # Migrate existing DBs that predate various columns.
        async with db.execute("PRAGMA table_info(submissions)") as cur:
            cols = {row[1] async for row in cur}
        if "step_data" not in cols:
            await db.execute(MIGRATE_ADD_STEP_DATA)
        if "sota_eligible" not in cols:
            await db.execute(MIGRATE_ADD_SOTA_ELIGIBLE)
        if "score" not in cols:
            await db.execute(MIGRATE_ADD_SCORE)
        if "score_metric" not in cols:
            await db.execute(MIGRATE_ADD_SCORE_METRIC)
        if "score_direction" not in cols:
            await db.execute(MIGRATE_ADD_SCORE_DIRECTION)
        # Backfill score/score_metric/score_direction for rows created before multi-objective support.
        await db.execute(
            "UPDATE submissions SET score = mass_grams, score_metric = 'mass_grams' WHERE score IS NULL"
        )
        await db.execute(
            "UPDATE submissions SET score_direction = 'minimize' WHERE score_direction IS NULL"
        )

        # Data correction: thin-frame submission (7450daa) claimed 27g but fails
        # FEA at 60.3 MPa > 25.0 MPa allowable (1.2mm plate insufficient at bolt holes).
        # Mark as failed so the leaderboard reflects the real verified SOTA.
        await db.execute(
            "UPDATE submissions SET passed = 0, "
            "notes = 'Invalidated: 1.2mm plate fails FEA at bolt holes (60.3 MPa > 25 MPa)' "
            "WHERE commit_hash = '7450daa' AND passed = 1"
        )

        await db.commit()


@asynccontextmanager
async def get_db():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db
