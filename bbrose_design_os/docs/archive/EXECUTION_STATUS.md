# Milestones v2 — Execution Status
**Updated:** 2026-07-03 (evening) · Test state: **362 passed + 1 skipped + 1 deselected (pacdora)** · ruff clean · `check --deploy` clean · branch `v2-features-phase12-14`

## ✅ PHASE 8 — Critical Stability & Security — COMPLETE
Auth media (`/files/`), crash-safe state machine + retry-from-stranded, atomic gate transitions (409 on race), credentials cleanup, settings-driven models + transient-only retries, durable image handling + redownload, `CELERY_EAGER` + `/healthz`.

## ✅ PHASE 9 — Geometry & Print Correctness — COMPLETE
Docs migrated to `apps/dielines/docs/` (dieline-generator/ + venv_py39_backup/ now deleted), dust clamp + bounds invariant + non-square matrix, thickness compensation + DECISION-015 notches (t=0 byte-identical to the golden snapshot), DECISION-017 slit web guard (9.3 constants remain provisional by design — see MEASUREMENT_NEEDED.md), `/All` registration marks + embedded TTF + Trim/BleedBox + spot-name validation, `.ai` = CMYK production PDF copy.

## ✅ PHASE 10 — Dieline API Hardening — COMPLETE
Shared defaults (`constants.py`) + `export_service.py` (no os.chdir anywhere), authenticated `jobs/<id>/files/<kind>` route, `DielineJob.owner` + owner-or-staff, DRF `IsAuthenticated` (401 JSON), InspirationView label fix, `test_api_phase10.py`.

## ✅ PHASE 11 — Multi-User, Roles & Workflow — COMPLETE
Non-admin login + Designer/Reviewer/Admin groups + `seed_roles`, `created_by`/`assigned_to`, `GateDecision` audit trail + `AgentLog.actor`, role-gated gates, brand switcher + brand-scoped creation + `STATUS_CANONICAL` fix, notes cleared on approval (history in GateDecision), prompt edit + image-only rerun + per-stage reruns + superseded housekeeping. `test_phase11.py`.

## ✅ PHASE 12 — New Features — COMPLETE (2026-07-03)
| Milestone | Delivered |
|---|---|
| 12.1 Carton styles | `_StyleConfig` dispatch + `calculate_dieline()`; STE byte-identical (regression green); provisional `reverse_tuck_end` + `tuck_top_auto_bottom` (crash-lock, relaxed H constraints → compacts/palettes); per-style schema rules; API accepts `structure_type`; `styles.py` registry |
| 12.2 Cost ledger | `ApiCallRecord` per Claude/image call (prices in settings); task bound via ContextVar in `crash_safe`; per-task cap fails the task, 24h cap → 429 on creation; spend on task badge + dashboard panel |
| 12.3 Library | `/api/library/` paginated + brand/category/date filters + text search (PG full-text, icontains fallback); detail w/ downloads + gate history + cost; "start from existing"; `/dashboard/library/` page |
| 12.4 Notifications | `Notification` + `NotificationPreference`; pre/post_save signal on status transitions; gate events → owner+reviewers, failed/completed → owner; console email in dev; bell menu + unread badge + mark-read + prefs API |
| 12.5 Batch runs | `BatchRun` fan-out (budget + worker guards), aggregate detail + Gate-1 queue, single-submit aggregate approve (atomic per task), zip export of final deliverables |

## ✅ PHASE 13 — Frontend Overhaul — COMPLETE (2026-07-03)
| Milestone | Delivered |
|---|---|
| 13.1 Template split | 1,810-line template → 39-line shell + 3 partials + `static/css/dashboard.css` + `static/js/{api,render,gates,poll}.js`. Verified: node --check, function-set equality (42 fns), live-server 200s, headless Chromium load with zero JS errors. Manifest static storage now opt-in (`USE_MANIFEST_STATIC`) |
| 13.2 SSE + pagination | `/api/tasks/<id>/events/` SSE stream (settles + closes at gates); EventSource with 10s-polling fallback; task list paginated (25/page) + status/brand/owner filters; brain-stats server-side + 15s cache (`/api/stats/`) |

## ✅ PHASE 14 — Ops, Deployment & CI — COMPLETE (2026-07-03)
| Milestone | Delivered |
|---|---|
| 14.1 Logging/security | JSON logs in prod + request-id middleware/filter; env-gated Sentry (Django+Celery); DEBUG=False security block (SSL/HSTS/secure cookies/proxy header) + always-on nosniff/DENY; env.bool DEBUG (shim removed); `check --deploy` clean |
| 14.2 Deps & CI | Pinned lock (68 pkgs) + `requirements.in` + `requirements-dev.txt`; **Pacdora quarantined** (user decision 2026-07-03: keep behind `PACKAGING_BACKEND`, playwright out of the lock, test marked `pacdora` + excluded in CI); GitHub Actions (ruff, migration drift, deploy check, pytest vs Postgres 16); ruff clean; pytest now collects `tests.py` (core suites were silently uncollected) |
| 14.3 Deploy & backups | Dockerfile (gthread for SSE) + compose (web/worker/redis/postgres, `/healthz` healthcheck); entrypoint migrate+collectstatic; backup/restore scripts + RUNBOOK.md. **Restore drill executed**: row counts verified across 5 tables + 394-file media round-trip |

## Known gaps / next actions
- **Docker build not validated** — docker unavailable on the dev machine; run `docker compose -f docker-compose.prod.yml build` on the deploy host (noted in RUNBOOK).
- **Full pipeline browser walkthrough not run** — needs `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`; only structural + headless-load verification was possible for Phase 13.
- **9.3 constants provisional** — blocked on measuring SLIMMING_CREAM_R-108-A.ai (MEASUREMENT_NEEDED.md).
- New carton styles (12.1) are flagged provisional until a measured reference file exists.
- Branch `v2-features-phase12-14` (12 commits ahead of `main`) — merge when the walkthrough passes.
