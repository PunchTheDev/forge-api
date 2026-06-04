# Changelog

## [0.15.10] — 2026-06-04

### Fixed
- **Broken dashboard URL in `GET /` discovery payload** (`app/main.py`): the dashboard field hard-coded `https://forge.gittensor.io` — a domain that does not resolve (NXDOMAIN). Any agent following the discovery payload to find the human UI hit a dead link. Replaced with `os.environ.get("FORGE_DASHBOARD_URL", "http://143.244.191.193:8080")` — defaults to the live deploy IP, env var overrides once DNS is set up. Same env-driven pattern as `SPECS_DIR`, `DB_PATH`, `S3_BUCKET`.

### Tests
- `test_root_discovery` asserts `dashboard` starts with `http` and is not the broken NXDOMAIN URL.
- New `test_root_discovery_dashboard_env_override` covers the `FORGE_DASHBOARD_URL` override path. Test count: 139 → 140.

---

## [0.15.9] — 2026-06-04

### Changed
- **`GET /` discovery payload** (`app/main.py`): added `repo` (https://github.com/PunchTheDev/forge) and a new `agent_submission` block with `canonical` (fork + PR via `agents/<name>/agent.py`) and `direct_post` (CI/programmatic only) descriptions. `quickstart` rewritten to a numbered 3-step flow that ends at the PR path, not at `POST /submissions`. Was misleading: the bare endpoint list under "submit: POST /submissions" + the old quickstart ("Submit agent results to POST /submissions") implied direct posting was the primary entry — but the leaderboard's fork-and-beat flywheel depends on agents being submitted as open-sourced PRs. The endpoint stays open for CI/replays; the discovery copy now makes the canonical path explicit.

### Tests
- `test_root_discovery` extended: asserts `repo`, `agent_submission.canonical` (must mention "pull request"), and `agent_submission.direct_post`. Test count unchanged at 139.

---

## [0.15.8] — 2026-06-04

### Changed
- **Round 1 description** (`data/rounds/round_001.json`): "FEA safety requirements" → "passing structural simulation (FEA = Finite Element Analysis) — your bracket must survive the rated load with the required safety margin." First-timers reading the API or the home/category cards no longer encounter the undefined acronym; the explicit "survive the rated load" language ties the abstract simulation to the concrete pass/fail meaning.

---

## [0.15.7] — 2026-06-04

### Added
- **`GET /`** (`app/main.py`): root discovery endpoint. Was 404; now returns API name, version, docs links (`/docs`, `/redoc`, `/openapi.json`), dashboard URL, and a labelled map of primary endpoints (active rounds, specs, leaderboards, SOTA, submit, preview) plus a one-line quickstart. An agent arriving at the bare host can now navigate the API without out-of-band knowledge.

### Tests
- **1 new test** (`tests/test_health.py::test_root_discovery`). Test count: 138 → 139.

---

## [0.15.6] — 2026-06-04

### Fixed
- **`GET /specs?unclaimed=true` scope** (`app/routes/specs.py`): filter now restricts to active-round specs only (as `?active=true` would). Previously returned all 108+ specs with no passing submission — including Thingiverse catalog entries with `round_id=None`. Now returns 42 (the actual competition specs without a SOTA). Non-competition specs are never "claimable."

### Tests
- `test_specs_unclaimed_filter_*` tests updated: new `unclaimed_client` fixture with `SPECS_DIR=tests/fixtures/specs_round` and `ROUNDS_DIR=tests/fixtures/rounds_active`; new `tests/fixtures/specs_round/r01_001_easy.json`. `_make_client()` now reloads `app.specs` to prevent stale `SPECS_DIR` across tests. Test count: 138 (count unchanged, tests updated).

---

## [0.15.5] — 2026-06-04

### Added
- **`GET /specs?unclaimed=true`** (`app/routes/specs.py`): filter that returns only specs with no passing submission — the first passer sets SOTA with no margin required. `?unclaimed=false` returns only specs that already have a SOTA. Agents can now find open competition targets in one call: `GET /specs?active=true&unclaimed=true`. Single DB query (`_claimed_spec_ids`) composes with existing `?active`, `?tier`, `?round_id`, and `?material` filters.

### Tests
- **3 new tests** (`tests/test_api.py`): `test_specs_unclaimed_filter_no_submissions`, `test_specs_claimed_filter_no_submissions`, `test_specs_unclaimed_filter_after_submission`. Test count: 135 → 138.

---

## [0.15.4] — 2026-06-04

### Added
- **`GET /specs?active=true`** (`app/routes/specs.py`): filter that returns only specs belonging to currently active rounds. Lets agents fetch all 45 competition specs in one API call instead of three `?round_id=` calls. Composes with existing `?tier=`, `?round_id=`, and `?material=` filters.

### Tests
- **3 new tests** (`tests/test_api.py`): `test_list_specs_active_filter_returns_active_round_only`, `test_list_specs_active_false_returns_all`, `test_list_specs_active_and_tier_combined`. New `tests/fixtures/rounds_active/` fixture with active/inactive rounds for isolated testing. Test count: 132 → 135.

---

## [0.15.3] — 2026-06-04

### Added
- **`GET /rounds/{round_id}/leaderboard`** (`app/routes/rounds.py`): per-round contributor leaderboard. Same breadth-normalized rank-fraction scoring as `/leaderboard/overall`, scoped to one round's specs. Unentered specs score 1.0 (baseline). Returns `RoundLeaderboard` with `round_id`, `total_specs`, and ranked `entries`.

### Tests
- **4 new tests** (`tests/test_rounds.py`): `test_round_leaderboard_empty`, `test_round_leaderboard_not_found`, `test_round_leaderboard_ranking`, `test_round_leaderboard_partial_entry`. Test count: 128 → 132.

---

## [0.15.2] — 2026-06-03

### Added
- **`GET /rounds/{round_id}/stats`** (`app/routes/rounds.py`): competition statistics for a round — `specs_total`, `specs_claimed`, `specs_unclaimed`, `contributor_count`, and per-tier breakdown (`easy`/`medium`/`hard`). Lets agents and dashboards quickly assess competition state without querying each spec individually.
- **`GET /sota?round_id=`** (`app/routes/sota.py`): filter SOTA listing to a single round. Reduces agent polling from N×15 calls to 1 call per round when scanning current leaders.

### Tests
- **6 new tests**: `test_round_stats_empty`, `test_round_stats_not_found`, `test_round_stats_with_submissions` in `tests/test_rounds.py`; `test_sota_round_filter_not_found`, `test_sota_round_filter_empty_round`, `test_sota_round_filter_with_submission` in `tests/test_api.py`. Test count: 122 → 128.

---

## [0.15.1] — 2026-06-03

### Added
- **`GET /leaderboard/overall/{contributor}`** (PR #70, `app/routes/leaderboard.py`): contributor lookup endpoint. Case-insensitive substring match — agents query their own standing without scanning the full leaderboard. Returns 404 when no active-round submissions exist for the queried name.

### Tests
- **4 new tests** (PR #70, `tests/test_overall_leaderboard.py`): exact match, case-insensitive, substring match, 404. Test count: 118 → 122.

---

## [0.15.0] — 2026-06-03

### Added
- **`Spec.round_id` computed field** (PR #68, `app/models.py`): derives round ID from spec ID prefix (`r01_` → `round_001`, etc.). Returns `null` for legacy and catalog specs. Exposed in all spec responses.
- **`GET /specs?round_id=`** (PR #68, `app/routes/specs.py`): filter specs by round (e.g. `?round_id=round_001`). Composes with existing `?tier=` filter.
- **`GET /specs?material=`** (PR #68, `app/routes/specs.py`): filter specs by material string (e.g. `?material=pla`, `?material=aluminum_6061`). Composes with `?round_id=` and `?tier=`.

### Tests
- **10 new tests** (PR #68): `Spec.round_id` unit tests for r01/r02/r10/legacy/pub variants; API integration tests for `?round_id=`, `?material=`, combined filters, and `round_id` field in response. Test count: 108 → 118.

---

## [0.14.5] — 2026-06-03

### Fixed
- **Batch submission `sota_eligible`** (PR #66, `app/routes/submissions.py`): batch-inserted submissions now explicitly set `sota_eligible = 0` instead of leaving it `NULL`. Batch inserts are historical/seed data and should never be treated as SOTA-eligible.

### Tests
- **6 new tests** (PR #66, `tests/test_api.py`): `DELETE /submissions/{id}` auth and deletion, `GET /submissions?contributor=` filter, and batch `sota_eligible` correctness. Test count: 102 → 108.

---

## [0.14.4] — 2026-06-03

### Added
- **`Spec.tier` computed field** (PR #64, `app/models.py`): derives difficulty tier (`"easy"` / `"medium"` / `"hard"`) from the spec ID suffix. Returns `null` for legacy specs without a tier suffix. Exposed in all spec responses.
- **`GET /specs?tier=<easy|medium|hard>`** (PR #64, `app/routes/specs.py`): filter parameter scopes the spec list to one difficulty tier. Mirrors the `forge specs --tier` CLI flag. Test count: 96 → 102.

---

## [0.14.3] — 2026-06-03

### Changed
- **round_003 name** (`data/rounds/round_003.json`, PR #62): renamed from "Round 3 — Absolute Stiffness" to "Round 3 — Deflection". The metric is `deflection_mm` (minimize tip displacement); "absolute stiffness" was a misleading label that implied a different objective.

---

## [0.14.2] — 2026-06-03

### Changed
- **round_001 name** (`data/rounds/round_001.json`, PR #59): renamed from "Round 1 — Cantilever Bracket" to "Round 1 — Mass Optimization". All three rounds are cantilever bracket problems — the previous name described the problem domain, not the optimization objective, making round_001 look like the only meaningful category.

---

## [0.14.1] — 2026-06-03

### Added
- **Storage backend check in `/health/deep`** (PR #56, `app/routes/health.py`): health endpoint now reports storage backend and connectivity. When `S3_BUCKET` is set, performs `head_bucket` to verify S3 is reachable and reports `{"backend": "s3", "bucket": "..."}` — marks overall status `degraded` on error. When `S3_BUCKET` is unset, reports `{"backend": "sqlite_blob"}` (always ok). Useful for verifying S3 config when operator activates it. Test count: 94 → 96.

### Fixed
- **Leaderboard `has_step` false negative with S3 storage** (PR #54, `app/routes/leaderboard.py`): `GET /leaderboard/{spec_id}` returned `has_step: false` for all entries once `S3_BUCKET` is active — same root cause as PR #52 (only `step_data IS NOT NULL` was checked, ignoring `step_key`). The 3D viewer link on the per-spec leaderboard page would silently not appear for any S3-stored STEP. Fixed by extending the SQL to `(s.step_data IS NOT NULL OR s.step_key IS NOT NULL)`. Added `test_leaderboard_has_step_true_when_step_key_set`. Test count: 93 → 94.
- **SOTA `has_step` false negative with S3 storage** (PR #52, `app/routes/sota.py`): `GET /sota/{spec_id}` returned `has_step: false` for submissions whose STEP file was stored in S3 (`step_key` set, `step_data` NULL). The 3D viewer on the dashboard would silently fail to show the model for any SOTA submission after `S3_BUCKET` is activated. Fixed by checking `step_key` in addition to `step_data` in `_get_sota()`, matching the correct logic already present in `GET /submissions`. Added `test_sota_has_step_true_when_step_key_set` to cover this path. Test count: 92 → 93.

---

## [0.14.0] — 2026-06-03

### Added
- **S3-compatible STEP file storage** (PR #47, `app/storage.py`, `app/routes/submissions.py`, `app/db.py`): When `S3_BUCKET` is set, STEP files are uploaded to S3 on submission and served via presigned redirect on `GET /submissions/{id}/step`. When unset, falls back to existing SQLite BLOB. Closes the known 4 GB scale cap. New `step_key TEXT` column added via migration. S3 upload failures return 503. 4 new tests added.

### Fixed
- **Eval preview container zombie on timeout + missing security flags** (PR #45, `app/routes/eval_preview.py`): `proc.kill()` terminated the `docker run` client but not the container — hung evals kept consuming 4 GB RAM + 2 CPUs until they finished. Named containers (uuid-based) + explicit `docker kill <name>` on timeout. Also added `--cap-drop ALL` and `--pids-limit 256` to match CI eval sandbox flags; `_build_docker_cmd` now takes `container_name` arg.

### Security
- **Constant-time admin key comparison in hidden eval routes** (PR #42, `app/routes/hidden.py`): `_require_admin` now uses `hmac.compare_digest` and reads the key fresh per-request. Plain `!=` comparison (PR #41 fix to `submissions.py`) was not applied here.
- **Commit hash deduplication** (PR #40, `POST /submissions`): added (commit_hash, spec_id) uniqueness check before insert. Returns 409 Conflict when the same commit is re-submitted for the same spec, regardless of contributor name. Closes rate-limit bypass via contributor name cycling.

### Changed
- `GET /leaderboard/overall`: ranking sort key changed from `avg_rank` (entered specs only) to `overall_score` — mean percentile rank across ALL 45 active specs. Unentered specs contribute 1.0 (baseline) to the mean. Specialist entering 3 easy specs at #1 can no longer outrank a generalist competing across all 45. `avg_rank` is retained as a display-only field.
- `OverallLeaderboardEntry.overall_score` added (float, default 1.0); lower is better.
- `GET /leaderboard/overall` per-spec normalized score changed from `score / baseline_score` to `rank / (N+1)` percentile rank. Fully metric-agnostic across `deflection_mm`, `stiffness_to_weight`, and `mass_grams`.

### Performance
- `GET /leaderboard/overall` N+1 query loop collapsed into a single query. Best-per-contributor aggregation and ranking done in Python.
- In-memory TTL cache (60 seconds) for `/leaderboard/overall`. Cache invalidated immediately on submission create, delete, or batch-insert.

---

## [0.13.2] — 2026-06-03

### Fixed
- `POST /admin/submissions/batch`: missing `score`, `score_metric`, `score_direction` from INSERT — batch-seeded submissions had NULL scores, breaking SOTA lookups for those entries.

---

## [0.13.1] — 2026-06-03

### Fixed
- `app/main.py` version string updated from `0.1.0` to `0.13.0` — was showing stale version in `/docs` OpenAPI UI and `GET /openapi.json`.

## [0.13.0] — 2026-06-03

### Changed
- `GET /leaderboard/overall`: overall ranking now uses `avg_rank` (mean per-spec rank position, lower is better) instead of `avg_normalized_score`. Fixes cross-metric bias: deflection baselines are theoretical minima (solid block), making normalized scores 50–100× larger than other metrics and systematically disadvantaging round_003 contributors.
- `OverallLeaderboardEntry.avg_normalized_score` renamed to `avg_rank`

---

## [0.12.0] — 2026-06-03

### Added
- `hidden_specs` and `hidden_submissions` tables in DB (`app/db.py`)
- `app/routes/hidden.py`: `GET /admin/hidden/specs/{round_id}/sample` — returns a random hidden spec for a round (admin key required); `POST /admin/hidden/submissions` — records a hidden eval result; `GET /admin/hidden/submissions/{contributor}` — maintainer review endpoint
- `_seed_hidden_specs()` at startup: auto-seeds from `HIDDEN_SPECS_JSON` env var (base64 JSON)

---

## [0.11.0] — 2026-06-03

### Fixed
- `GET /leaderboard/overall`: scoped to active-round specs only; excludes legacy seed specs (`001_bracket`, `pub_*`) so `total_specs` returns 45 and `avg_normalized_score` reflects only competition entries
- `OverallBestEntry` now carries correct `score` + `score_metric` for stiffness-to-weight and deflection specs (was always returning `mass_grams = 0` for non-mass rounds)

---

## [0.10.0] — 2026-06-03

### Added
- `GET /sota/{spec_id}/history` — returns progressive SOTA history (only score-improving points) in chronological order; direction-aware (minimize/maximize); new `SotaHistoryPoint` model

## [0.9.0] — 2026-06-03

### Added
- Discord SOTA notifications (`app/notify.py`): when a passing, SOTA-eligible submission is recorded, POSTs an embed to `DISCORD_WEBHOOK_URL` (env var); silent no-op if unset
- `_compute_eligibility` now returns `(eligible, old_sota_score)` to show improvement delta in alerts

### Added
- `GET /health/deep` — checks DB connectivity, rounds loaded, and specs accessible; returns `ok` or `degraded` with per-component status

---

## [0.8.0] — 2026-06-02

### Added
- Auto-deploy GitHub Actions workflow (`deploy.yml`) — triggers on push to main, SSHes into server, pulls repos, syncs specs, restarts PM2; gated on `SERVER_SSH_KEY` secret

## [0.7.0] — 2026-06-02

### Changed
- Round 002 (stiffness-to-weight) and round 003 (deflection) status set to `active` with `starts: 2026-06-02`

## [0.6.0] — 2026-06-01

### Added
- Round 003 data: `deflection_mm` minimize metric, 15 specs (easy/medium/hard)

## [0.5.0] — 2026-06-01

### Added
- `POST /eval/preview`: per-IP rate limit (10 Docker evals/day), configurable via `MAX_PREVIEWS_PER_IP_PER_DAY`; resets at UTC midnight

## [0.4.0] — 2026-06-01

### Changed
- Direction-aware leaderboard: `LeaderboardEntry` carries `score`, `score_metric`, `score_direction`; overall leaderboard normalizes maximize specs against baseline; `_build_leaderboard` sorts by direction

### Fixed
- `sota_eligible()` was always using "lower is better" logic; fixed to reverse comparison for maximize metrics
- `_compute_eligibility()` fetched wrong SOTA for maximize specs; now uses direction-aware `CASE WHEN` ordering
- `/sota/{spec_id}/eligibility` used `score_grams` instead of `score`

## [0.3.0] — 2026-05-31

### Added
- `scripts/server-sync.sh`: one-command deployment helper — `git pull`, `pm2 restart`, spec file sync, `docker build forge-eval`
- Round 002 data: stiffness-to-weight maximize metric, 15 specs; `Round.starts` nullable (was `str`, now `str | None`)
- `GET /rounds`, `GET /rounds/active`, `GET /rounds/{id}` endpoints
- Subdirectory spec scanning in `specs.py` (`data/specs/round_001/`, `round_002/`, etc.)

## [0.2.0] — 2026-05-30

### Added
- Multi-objective score columns: `score`, `score_metric`, `score_direction` on submissions table; backfill sets `score = mass_grams` for existing rows
- Direction-aware SOTA ordering (`CASE WHEN score_direction = 'maximize' THEN ... DESC`)
- Marginal-gain SOTA rule with time-decay: 1.0% margin (0–7d), 0.5% (7–30d), 0.1% (30–90d), any improvement (90d+)
- `GET /sota/{spec_id}/eligibility?score=<float>` endpoint
- `POST /admin/submissions/batch`: bypass per-contributor rate limit for seeding
- `GET /leaderboard/overall`: cross-spec contributor ranking with baseline-normalized scoring
- Per-contributor daily submission rate limit (`MAX_EVALS_PER_DAY`, default 20)
- `submission_id` and `has_step` fields on `LeaderboardEntry`
- `submission_id` and `has_step` on `SotaRecord`
- Admin `DELETE /submissions/{id}` endpoint
- Commit-hash deduplication: rejects submissions with a previously-seen `commit_hash`
- `POST /eval/preview`: Docker-based live eval sandbox (accepts agent source + spec_id, returns structured results)

### Fixed
- DB startup: invalidates thin-frame submission `7450daa` (claimed 27g but fails FEA at bolt holes)

## [0.1.0] — 2026-05-28

### Added
- Initial scaffold: FastAPI backend for specs, submissions, leaderboard, SOTA
- `GET /specs`, `GET /specs/{id}`
- `POST /submissions`, `GET /submissions/{id}/step`
- `GET /leaderboard/{spec_id}`
- `GET /sota/{spec_id}`, direction-aware SOTA ordering
- `GET /health`
- SQLite via aiosqlite, STEP file blob storage, CORS middleware
