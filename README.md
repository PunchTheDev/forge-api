# forge-api

REST backend for [Forge](https://github.com/PunchTheDev/forge) — the competitive parametric CAD benchmark on Gittensor subnet 74.

The API is the single source of truth for specs, submissions, leaderboard, and SOTA. The CLI, dashboard, and CI all read from it.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/specs` | List all problem specs |
| GET | `/specs/{id}` | Get spec by ID |
| POST | `/submissions` | Record a benchmark result |
| GET | `/submissions` | List submissions (filterable by spec, contributor) |
| GET | `/submissions/{id}` | Get submission by ID |
| GET | `/leaderboard` | Full leaderboard (all specs) |
| GET | `/leaderboard/{spec_id}` | Leaderboard for one spec |
| GET | `/sota` | Current SOTA for all specs |
| GET | `/sota/{spec_id}` | Current SOTA for one spec |

Interactive docs at `/docs` when running.

## Running locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Or with Docker:

```bash
docker compose up
```

## Seeding data

Copy specs from the forge repo and POST the initial SOTA:

```bash
SPECS_DIR=data/specs  # copy forge/specs/*.json here first
python3 scripts/seed.py /path/to/forge
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_PATH` | `data/forge.db` | SQLite database path |
| `SPECS_DIR` | `data/specs` | Directory of spec JSON files |

## Tests

```bash
python3 -m pytest tests/ -v
```

## License

MIT
