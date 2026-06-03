# forge-api

REST backend for [Forge](https://github.com/PunchTheDev/forge) — the competitive parametric CAD benchmark on Gittensor subnet 74.

The API is the single source of truth for specs, submissions, leaderboard, and SOTA. The CLI, dashboard, and CI all read from it.

## Endpoints

Interactive docs at `/docs` when running. Key routes:

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness check |
| GET | `/health/deep` | Deep check: DB, active rounds, spec count |

### Specs & rounds

| Method | Path | Description |
|--------|------|-------------|
| GET | `/specs` | List all problem specs |
| GET | `/specs/{id}` | Get spec by ID |
| GET | `/rounds` | List all rounds |
| GET | `/rounds/active` | Active rounds only |
| GET | `/rounds/{id}` | Round details with full spec list |

### Submissions

| Method | Path | Description |
|--------|------|-------------|
| POST | `/submissions` | Record a benchmark result |
| GET | `/submissions` | List submissions (filterable by spec, contributor) |
| GET | `/submissions/{id}` | Get submission by ID |
| GET | `/submissions/{id}/step` | Download the submitted STEP file |

### Leaderboard

| Method | Path | Description |
|--------|------|-------------|
| GET | `/leaderboard/overall` | Cross-spec overall ranking (active rounds only) |
| GET | `/leaderboard` | Per-spec leaderboard entries |
| GET | `/leaderboard/{spec_id}` | Leaderboard for one spec |

### SOTA

| Method | Path | Description |
|--------|------|-------------|
| GET | `/sota` | Current SOTA for all specs |
| GET | `/sota/{spec_id}` | Current SOTA for one spec |
| GET | `/sota/{spec_id}/history` | Progressive SOTA history (score improvements over time) |
| GET | `/sota/{spec_id}/eligibility` | Check if a score beats SOTA (marginal-gain rule) |

### Eval preview

| Method | Path | Description |
|--------|------|-------------|
| POST | `/eval/preview` | Run a live sandboxed eval on submitted agent code (10/IP/day) |

### Admin

| Method | Path | Description |
|--------|------|-------------|
| POST | `/admin/submissions/batch` | Batch-import submissions |
| GET | `/admin/hidden/specs/{round_id}/sample` | Sample a random hidden eval spec (auth required) |
| POST | `/admin/hidden/submissions` | Record a hidden eval result (auth required) |
| GET | `/admin/hidden/submissions/{contributor}` | Review hidden eval history for a contributor |

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

Copy specs from the forge repo and seed the database:

```bash
python3 scripts/seed.py /path/to/forge
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_PATH` | `data/forge.db` | SQLite database path |
| `SPECS_DIR` | `data/specs` | Directory of spec JSON files |
| `MAX_EVALS_PER_DAY` | `20` | Per-contributor daily submission rate limit |
| `DISCORD_WEBHOOK_URL` | — | Post SOTA notifications to Discord when set |
| `FORGE_LLM_KEY` | — | OpenRouter key for live eval preview |
| `FORGE_MODEL` | — | Model override for eval preview |
| `FORGE_ADMIN_KEY` | — | Secret for admin and hidden eval endpoints |
| `HIDDEN_SPECS_JSON` | — | Base64-encoded hidden spec set (from `scripts/generate_hidden_specs.py` in forge) |

## Tests

```bash
python3 -m pytest tests/ -v
```

## License

MIT
