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
| GET | `/sota/{spec_id}/eligibility` | Check if a score beats SOTA (marginal-gain rule) |
| POST | `/eval/preview` | Run a live sandboxed eval on submitted agent code |
| GET | `/rounds` | List all competition rounds |
| GET | `/rounds/active` | Active rounds only |
| GET | `/rounds/{id}` | Round details with full spec list |
| POST | `/admin/submissions/batch` | Batch-import submissions (admin only) |

Interactive docs at `/docs` when running.

### Marginal-gain rule

`GET /sota/{spec_id}/eligibility?score=<float>` returns whether the score beats current SOTA by the required margin:

| SOTA age | Required improvement |
|---|---|
| 0–7 days | 1.0% |
| 7–30 days | 0.5% |
| 30–90 days | 0.1% |
| 90+ days | any improvement |

### Live eval preview

`POST /eval/preview` accepts `{agent_code: str, spec_id: str}` and returns full eval results (pass/fail, score, FEA stress, displacement, elapsed). Requires the `forge-eval` Docker image on the host.

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
