# Changelog

## [Unreleased]

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
