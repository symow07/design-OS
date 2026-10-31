# BBROSE Design OS — Complete Project Documentation
**Last updated:** 2026-07-03 · **Branch:** `v2-features-phase12-14` (13 commits ahead of `main`) · **State:** 363 tests passing, ruff clean, `check --deploy` clean

---

## 1. What this project is

BBROSE Design OS is an **AI-assisted packaging design pipeline** for the BBROSE cosmetics brand. A human guides a team of AI agents from a one-line text brief to **print-ready packaging deliverables** (dieline SVG, Illustrator `.ai`, CMYK production PDF, branded spec sheet), approving the work at human gates along the way.

**Stack:** Python 3.11 · Django 4.2 · PostgreSQL 16 · Celery + Redis · Claude API (text/vision agents) · OpenAI API (DALL-E 3 images) · DRF · vanilla-JS dashboard · Docker/gunicorn for production.

**Repo layout:**

```
bbrose-systemOS/                     ← repo root (git)
├── PROJECT_DOCUMENTATION.md         ← this file
├── README.md                        ← quick-start
├── RUNBOOK → bbrose_design_os/RUNBOOK.md (ops manual)
├── AUDIT_REPORT.md                  ← 2026-07-02 production-readiness audit
├── BBROSE_DesignOS_Milestones(1).md ← v1 build plan (phases 0–7)
├── BBROSE_DesignOS_Milestones_v2.md ← v2 hardening plan (phases 8–14)
├── EXECUTION_STATUS.md              ← per-phase status table
├── .github/workflows/ci.yml         ← CI (ruff + pytest vs Postgres 16)
└── bbrose_design_os/                ← the Django project
    ├── apps/core/        brand knowledge: Brand, ColorSystem, MaterialSystem,
    │                     AestheticLanguage, PackagingStructure, Product, Campaign;
    │                     /healthz; authenticated /files/ media route; request-id middleware
    ├── apps/pipeline/    the AI pipeline: agents, models, gates API, cost ledger,
    │                     notifications, design library, batch runs, SSE live updates
    ├── apps/dielines/    deterministic dieline generator: geometry engine, styles,
    │                     exporters (SVG/AI/PDF), validators, its own REST API + docs
    ├── apps/dashboard/   server-rendered dashboard + design-library pages
    ├── apps/accounts/    non-admin login/logout, seed_roles, rotate_demo_password
    ├── config/           settings, urls, celery, wsgi
    ├── templates/        dashboard shell + partials, library, login
    ├── static/           css/dashboard.css + js/{api,render,gates,poll}.js
    ├── scripts/          backup.sh / restore.sh
    ├── Dockerfile, docker-compose.prod.yml, docker-entrypoint.sh
    └── requirements.in / requirements.txt (pinned lock) / requirements-dev.txt
```

---

## 2. The pipeline (how a design gets made)

Orchestrated by `ARIAAgent` (`apps/pipeline/agents/aria.py`). Every stage is crash-safe: any exception marks the task `failed` with the error message, and Retry resumes from the correct step.

```
Brief (text) ──▶ Creative Director (Claude)      3–5 design directions
             ──▶ Prompt Engineer  (Claude)       structured image prompts
             ──▶ Image Producer   (DALL-E 3)     3 concept images (durable local copies)
             ──▶ QA Reviewer      (Claude vision) scores vs brand standards
             ──▶ auto-revision loop (capped)     regenerates if QA is weak
   GATE 1    ──▶ human approves one image  (or rejects with notes / edits prompts / reruns)
             ──▶ DielineAgent estimates dimensions
                   Scenario A: exact dims from the Product record (no AI)
                   Scenario B: Claude estimate; low-confidence fields left blank
   DIM GATE  ──▶ human confirms W×D×H + style (structure_type)
             ──▶ deterministic geometry engine → SVG + .ai + CMYK production PDF
                   (validated: bounds invariant, spot plates, prepress checks)
   GATE 2    ──▶ human approves the dieline
  COMPLETED  ──▶ downloads: dieline SVG, .ai, production PDF, spec-sheet PDF
```

**Design contract:** the AI only ever *estimates scalar dimensions*. **All geometry is deterministic Python** (`apps/dielines/geometry/`) — no generative geometry, ever. A human confirms dimensions before geometry runs.

**Carton styles** (Milestone 12.1): `straight_tuck_end_carton` (locked, measured reference), plus provisional `reverse_tuck_end_carton` and `tuck_top_auto_bottom_carton` (crash-lock base; permits H<W, so compacts/palettes work). Provisional styles are flagged on the spec sheet and must be human-confirmed at the dimension gate.

---

## 3. Complete build history

### v1 — Phases 0–7 (initial build, sessions through 2026-05)

| Phase | What was built |
|---|---|
| 0 | Django scaffold, Postgres, env config |
| 1 | Brand knowledge models (Brand, ColorSystem, MaterialSystem, AestheticLanguage, PackagingStructure, Product, Campaign) + `seed_bbrose` |
| 2 | Pipeline models (DesignTask, AgentLog, CreativeBrief, GeneratedImage, PackagingOutput) |
| 3 | Claude service layer, brand-context retriever, the five sub-agents (Creative Director, Prompt Engineer, Image Producer, QA Reviewer, ARIA lead) + legacy Pacdora agent |
| 4 | Task/gate JSON API + Celery background tasks |
| 5 | Single-page dashboard (queue, live feed, Gate 1 gallery, gates UI) |
| 6 | Product catalog import from Excel (incl. product images) |
| 7 | End-to-end pipeline test with mocked providers |

**2026-05-20 — Dieline generator merge.** The standalone `dieline-generator/` project (deterministic STE-carton geometry + exporters, built against a measured 28×28×120 reference from a professional Illustrator file) was merged in as `apps.dielines`, replacing Pacdora as the post-Gate-1 step (`PACKAGING_BACKEND` toggle). Python upgraded to 3.11. New dimension gate added between Gate 1 and Gate 2.

### 2026-07-02 — Production-readiness audit (`AUDIT_REPORT.md`)

~7,300 lines audited. Verdict: *works as a single-user demo, not safe as the company's main tool.* Findings: 7 CRITICAL (C1–C7), 11 HIGH (H1–H11), plus MEDIUM ops gaps. This audit drove the v2 plan; every v2 milestone cites the finding it fixes.

### v2 — Phases 8–14 (hardening + build-out, completed 2026-07-03)

#### PHASE 8 — Critical Stability & Security (fixes C1–C3, C6, C7, H1, H7)
- **8.1 Authenticated media** — DEBUG-only `/media/` removed; login-protected `/files/<path>` route (path-traversal safe) in all environments; `STORAGE_BACKEND=s3` option (private bucket, 1h signed URLs); serializers never return raw media paths or expiring provider URLs.
- **8.2 Crash-safe state machine** — `@crash_safe` on `run()` + all three `resume_*` entry points; `DesignTask.error_message`; Retry works from `failed` AND stranded intermediate states, resuming the right step; dashboard renders every status (failed/rejected/gate_2_approved were blank).
- **8.3 Gate concurrency** — all gate views use one atomic conditional `UPDATE ... WHERE status=<expected>`; the race loser gets 409 and never enqueues; Gate 2 validates the output belongs to the task; DB constraint: one final-approved output per task.
- **8.4 Credentials cleanup** — hardcoded `admin/bbrose2026` removed from demo scripts (env-driven now); `manage.py rotate_demo_password`; repo greps clean.
- **8.5 Configurable models + resilient retries** — `CLAUDE_MODEL_HEAVY/FAST`, `IMAGE_MODEL/SIZE/QUALITY` env-driven; retry decorator retries ONLY transient errors (429/529/5xx/timeouts) with exponential backoff + jitter + Retry-After, fails fast on 4xx; startup warning for missing keys.
- **8.6 Durable images** — `image_url` → TextField; download retry w/ backoff + content-type/size verification; `download_failed` flag → retryable UI placeholder + `POST /api/images/<id>/redownload/`; QA skips missing files with an explicit log note.
- **8.7 Celery decoupled from DEBUG** — `CELERY_EAGER` env var (demo mode = in-process, worker mode = Redis); eager errors always propagate; unauthenticated `/healthz` (DB + Redis + worker ping → 200/503); task creation returns 503 when no worker is alive.

#### PHASE 9 — Geometry & Print Correctness (fixes C4, C5, H6 + hygiene)
- **9.4 Docs migration** (done first) — design contract (`geometry_decisions.md`, `ai_dieline_contract.md`, coordinate dump) moved into `apps/dielines/docs/`; DECISIONs 011/014 marked SUPERSEDED by 016; stale `dieline-generator/` and `venv_py39_backup/` deleted.
- **9.1 Dust/tuck guard + limits** — dust flap clamps to `min(D×0.631, tuck_zone−2mm)` with a spec-sheet note; schema max W,D ≤ 300 / H ≤ 600 and hard reject D > 2.5·W; post-generation bounding-box invariant (`GeometryError` — garbage never exports); non-square test matrix.
- **9.2 Board thickness + DECISION-015** — opt-in `thickness_compensation` (ECMA rule: back +2t, sides +t, flat +4t) + shoulder lock notches (2t); **t=0 reproduces the golden engine snapshot byte-for-byte** (regression-guarded).
- **9.3 Provisional constants** — the old coordinate dump predates DECISION-016, so the slit-width factor and shoulder-k stay provisional; `MEASUREMENT_NEEDED.md` lists the exact points to measure from `SLIMMING_CREAM_R-108-A.ai`; DECISION-017 slit web guard (≥2mm web at W≤15) implemented + tested.
- **9.5 PDF/X-ready output** — registration marks on the `/All` separation (visible on every plate); embedded DejaVu TTF; MediaBox/TrimBox/BleedBox set; `.ai` is now a copy of the CMYK production PDF (spot colors intact; SVG fallback labeled preview-grade); validator asserts `CutContour`/`Crease` spot names exist. Gap: reportlab has no OutputIntent API → no formal PDF/X-4 conformance claim.

#### PHASE 10 — Dieline API Hardening (fixes H4)
- **10.1** — omitted optional fields fall back to shared defaults (`apps/dielines/constants.py`) instead of 400; export orchestration extracted to `services/export_service.py` (agent + API run the identical pipeline: geometry → SVG+validate → production PDF+prepress checks → .ai → spec JSON); all exporters take absolute paths (no `os.chdir` anywhere — thread-safe); authenticated `GET /api/dielines/jobs/<id>/files/<kind>` (svg|ai|pdf|spec); `DielineJob.owner` FK + owner-or-staff enforcement; DRF `IsAuthenticated` (401 JSON, not 302); InspirationView label fix; `test_api_phase10.py`.

#### PHASE 11 — Multi-User, Roles & Workflow (fixes H2, H3, H9, H10)
- **11.1 Users/roles/audit** — real non-admin login (`/accounts/login/`); Designer/Reviewer/Admin groups + `seed_roles`; `DesignTask.created_by/assigned_to`; **GateDecision** model = immutable audit trail of every human decision (who/what/when/notes); `AgentLog.actor` for human-triggered events; designers create, only Reviewer/Admin approve; dashboard shows owner + "My tasks" filter + gate history.
- **11.2 Multi-brand** — task creation takes `brand_id` (sole brand default); product/campaign validated against the brand; per-session brand switcher scoping the dashboard; `STATUS_CANONICAL` shared constant (fixes the empty palette panel).
- **11.3 Revision workflow** — gate notes cleared on approval (history preserved in GateDecision); reviewers can edit image prompts + trigger image-only reruns at Gate 1 (revision-capped); per-stage rerun endpoints (`rerun_creative/prompts/images`); superseded images kept behind a history toggle instead of accumulating.

#### PHASE 12 — New Features (built 2026-07-03)
- **12.1 Additional carton styles** — `_StyleConfig` registry + `calculate_dieline()` dispatch inside the engine (STE **byte-identical**, regression green); `reverse_tuck_end_carton` (mirrored tuck panels) and `tuck_top_auto_bottom_carton` (4-flap crash-lock base, ECMA approximation) — both flagged **provisional** (no measured reference file); per-style schema constraints (auto-bottom drops H>W/H>D → compacts/palettes possible); API accepts human-confirmed `structure_type`; `geometry/styles.py` public registry; +22 tests.
- **12.2 Cost ledger & budgets** — `ApiCallRecord` row per Claude/image call with computed USD cost (prices in settings); task attribution via a ContextVar bound in `crash_safe`; `MAX_COST_PER_TASK` breach fails the task with a clear message; `MAX_COST_PER_DAY` (rolling 24h) blocks new task creation with 429; per-task cost on the dashboard badge + today/month spend panel; admin-browsable ledger; +13 tests.
- **12.3 Design library & search** — `/api/library/` paginated (25/page) catalogue of final-approved outputs; filters: brand, category, date range; text search over brief + product name (Postgres full-text, `icontains` fallback for SQLite/CI); detail endpoint with downloads/gate history/brief/cost; **"start from existing"** seeds a new task from a library item; `/dashboard/library/` page; +7 tests.
- **12.4 Notifications** — `Notification` + `NotificationPreference` models; pre/post_save signal fires only on real transitions INTO `awaiting_gate_1/awaiting_dimensions/awaiting_gate_2/failed/completed`; gate events → owner+assignee+Reviewers/Admins, terminal events → owner+assignee; email via Django backend (console in dev); per-user channel prefs; dashboard bell with unread badge, list, mark-read; +6 tests.
- **12.5 Batch & campaign runs** — `BatchRun` fans out one task per product (budget + worker guards); aggregate detail view (per-task progress + Gate-1 queue with images); **single-submit aggregate Gate 1 approve** using the atomic 8.3 transition per task (per-task conflict results, no double-enqueue); zip export of all final deliverables; +10 tests.

#### PHASE 13 — Frontend Overhaul (built 2026-07-03)
- **13.1 Template split** — the 1,810-line `dashboard/index.html` became: a 39-line shell + 3 partials (`_task_list/_task_detail/_brand_panel`) + `static/css/dashboard.css` + 4 classic-script JS modules (`api.js` = shared `var` globals + helpers, `render.js`, `gates.js`, `poll.js`). Verified via: `node --check` per module, **function-set equality** (all 42 functions present, none dropped/duplicated), live-server 200s for page + all assets, and a **headless Chromium login+load with zero uncaught JS errors**. Manifest static storage made opt-in (`USE_MANIFEST_STATIC`) so dev/tests don't need collectstatic.
- **13.2 SSE + pagination** — `GET /api/tasks/<id>/events/` streams status changes + new AgentLog rows (StreamingHttpResponse generator; settles + closes at any gate/terminal state so workers aren't held); frontend uses EventSource with automatic 10s-polling fallback; task list API paginated (25/page) with status/brand/owner filters; brain-stats computed server-side and cached 15s (`/api/stats/`); +8 tests.

#### PHASE 14 — Ops, Deployment & CI (built 2026-07-03)
- **14.1 Logging/monitoring/security** — LOGGING config (verbose text dev / JSON prod) with request-ids on every record (`RequestIDMiddleware` + filter, `X-Request-ID` echoed); env-gated Sentry (Django+Celery, no DSN = never imported); production security active at DEBUG=False (SSL redirect, HSTS, secure cookies, proxy SSL header) + always-on nosniff/referrer-policy/X-Frame-Options DENY; fragile DEBUG shim → `env.bool`. **`manage.py check --deploy`: 0 issues.**
- **14.2 Pinned deps & CI** — `requirements.txt` = fully-pinned 68-package lock; `requirements.in` documents direct deps; `requirements-dev.txt` adds ruff/pip-tools; **Pacdora quarantined per team decision 2026-07-03** (kept behind `PACKAGING_BACKEND=dieline`, playwright removed from the lock, its test marked `@pytest.mark.pacdora`, excluded in CI, still passes when selected); GitHub Actions: ruff → migration-drift check → `check --deploy` → pytest vs a Postgres 16 service container; ruff config in `pyproject.toml`, all 20 findings fixed; pytest now also collects `tests.py` files (apps/core's 8 Phase-8 tests were silently uncollected before).
- **14.3 Deployment & backups** — `Dockerfile` (python:3.11-slim, gunicorn **gthread** so SSE streams don't starve the worker pool) + `docker-compose.prod.yml` (web/worker/redis/postgres, `/healthz` as the web healthcheck, worker pinged via celery inspect); entrypoint waits for the DB then runs migrate+collectstatic (web only); `scripts/backup.sh` (nightly `pg_dump -Fc` + media tar, 14-day retention) + `scripts/restore.sh`; `RUNBOOK.md` (deploy/rollback/rotate/restore/common failures). **Restore drill executed for real:** live dev DB dumped → restored into a scratch DB → row counts verified across 5 tables (all match) + 394-file media round-trip.

#### Post-build efficiency audit (2026-07-03)
Query-count probe against a seeded 60-task dataset found one N+1: `/api/library/` at **54 queries per 25-row page** (per-row approver lookup + cost aggregate). Fixed with `Subquery`/`Sum` annotations → **4 queries, 6.7ms**. All other hot endpoints: single-digit queries; `/api/stats/` cache confirmed (warm call = 1 session query only).

---

## 4. Verification status — what was proven vs. what wasn't

**Proven (run on this machine):**
- 363 tests passing (geometry regressions, gate races, permissions, budgets, notifications, batch, SSE, library, media auth, healthz…)
- STE geometry byte-identical to the golden 28×28×120 snapshot
- ruff clean · zero migration drift · `check --deploy` 0 issues
- Headless Chromium dashboard load: zero uncaught JS errors
- Backup → restore drill: DB row counts + media file counts verified
- Endpoint efficiency: measured query counts (see above)

**NOT verified here (do before relying on it):**
1. **Docker image build** — docker isn't installed on this machine. Run `docker compose -f docker-compose.prod.yml build` once on the deploy host (RUNBOOK notes this).
2. **Live AI pipeline walkthrough** — `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` are empty in `.env`. The dieline demo path works keyless (Scenario A), but the full brief→images→gates→deliverables run needs real keys.
3. Provisional geometry (9.3 constants, 12.1 new styles) awaits measured reference files.

---

## 5. How to run

### Dev / demo (no API keys needed for the dieline path)
```bash
cd bbrose_design_os
venv/bin/python manage.py migrate
venv/bin/python manage.py seed_bbrose && venv/bin/python manage.py seed_roles
venv/bin/python manage.py seed_dieline_demo     # task parked at Gate 1
venv/bin/python manage.py runserver
# open http://127.0.0.1:8000/ → login → walk Gate 1 → dimensions → Gate 2 → downloads
```
`CELERY_EAGER=true` (default in dev) runs pipeline tasks in-process — no Redis/worker needed.

### Full AI pipeline
Set in `.env`: `ANTHROPIC_API_KEY` (console.anthropic.com) and `OPENAI_API_KEY` (platform.openai.com). Budget caps default to $5/task, $100/day.

### Production
See `bbrose_design_os/RUNBOOK.md`. Summary: fill `.env` (SECRET_KEY 50+ chars, POSTGRES_PASSWORD, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, API keys) → `docker compose -f docker-compose.prod.yml up -d --build` → TLS terminates in front of :8000 → nightly `scripts/backup.sh` via cron.

---

## 6. Configuration reference (`.env`)

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` / `DEBUG` / `ALLOWED_HOSTS` / `DATABASE_URL` / `REDIS_URL` | — | Django basics |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | empty | AI stages (pipeline blocked without them) |
| `CLAUDE_MODEL_HEAVY` / `CLAUDE_MODEL_FAST` | opus-4-7 / sonnet-4-6 | vision QA / text agents |
| `IMAGE_MODEL` / `IMAGE_SIZE` / `IMAGE_QUALITY` | dall-e-3 / 1024x1792 / hd | image generation |
| `MAX_COST_PER_TASK` / `MAX_COST_PER_DAY` / `IMAGE_PRICE_PER_IMAGE` | 5.0 / 100.0 / 0.12 | budget guards (0 disables) |
| `CELERY_EAGER` | =DEBUG | demo (in-process) vs worker mode |
| `STORAGE_BACKEND` | local | `local` = auth `/files/` route; `s3` = private bucket + signed URLs |
| `PACKAGING_BACKEND` | dieline | `pacdora` re-enables the quarantined legacy path |
| `EMAIL_BACKEND` + `EMAIL_HOST_*` / `DEFAULT_FROM_EMAIL` / `NOTIFICATION_BASE_URL` | console | notification email |
| `SENTRY_DSN` / `SENTRY_ENVIRONMENT` / `SENTRY_TRACES_SAMPLE_RATE` | empty | error monitoring (off unless set) |
| `SECURE_SSL_REDIRECT` / `SECURE_HSTS_SECONDS` / `CSRF_TRUSTED_ORIGINS` | true / 3600 / [] | prod security (active at DEBUG=False) |
| `USE_MANIFEST_STATIC` | false | hashed/compressed static (prod, after collectstatic) |
| `DEMO_ADMIN_USER` / `DEMO_ADMIN_PASSWORD` | empty | demo scripts (never hardcoded) |

---

## 7. API surface (all session-authenticated unless noted)

**Pipeline** — `POST /api/tasks/create/` (Designer; 503 no worker, 429 over budget) · `GET /api/tasks/` (paginated, filters: status/brand/owner) · `GET /api/tasks/<id>/status/` · `GET /api/tasks/<id>/events/` (SSE) · `GET /api/stats/` (cached 15s) · gates: `gate1_approve|gate1_reject|confirm_dimensions|gate2_approve|gate2_reject` (Reviewer/Admin; atomic, 409 on race) · `retry` · `rerun_images|rerun_prompts|rerun_creative` · `images/<id>/redownload/` · `images/<id>/update_prompt/` · `tasks/<id>/download_spec/`

**Library** — `GET /api/library/` (paginated + filters + search) · `GET /api/library/<id>/` · `POST /api/library/<id>/reuse/`

**Notifications** — `GET /api/notifications/` · `POST /api/notifications/mark_read/` · `GET|PUT /api/notifications/preferences/`

**Batches** — `POST /api/batches/create/` · `GET /api/batches/<id>/` · `POST /api/batches/<id>/gate1_approve/` (aggregate) · `GET /api/batches/<id>/export/` (zip)

**Dielines** — `POST /api/dielines/generate/` (accepts `structure_type`) · `GET /api/dielines/jobs/<id>/files/<kind>` (svg|ai|pdf|spec; owner-or-staff) · inspiration/estimation endpoints

**Infra** — `GET /healthz` (unauthenticated 200/503) · `GET /files/<path>` (login-required media)

---

## 8. Key design decisions (and where they're recorded)

| Decision | Where |
|---|---|
| AI never generates geometry; deterministic engine + human dimension gate | `apps/dielines/docs/ai_dieline_contract.md` |
| All geometry constants measured or flagged provisional (DECISION-001…017) | `apps/dielines/docs/geometry_decisions.md` |
| STE reference locked to a golden snapshot; t=0 must be byte-identical | `apps/dielines/docs/28x28x120_engine_reference.json` + `test_reference_regression.py` |
| Gate transitions are single conditional UPDATEs (no locks, losers get 409) | `apps/pipeline/views.py::_transition` |
| Human gate decisions are immutable audit rows | `GateDecision` model |
| Every AI call is metered; budgets enforce at task + day level | `apps/pipeline/services/cost_ledger.py` |
| Pacdora legacy path quarantined, not deleted (team decision 2026-07-03) | `PACKAGING_BACKEND` toggle; playwright out of the lock; CI excludes `-m pacdora` |
| SSE over websockets/brokers — simplest that fits sync gunicorn + Postgres | `apps/pipeline/live_views.py` |
| Provisional carton styles must be human-confirmed before production | engine notes + spec sheet + dimension gate |

---

## 9. Next steps (in order)

1. Add `ANTHROPIC_API_KEY` + `OPENAI_API_KEY` to `.env` → run the full end-to-end walkthrough.
2. Validate the Docker build on the deploy host (`docker compose -f docker-compose.prod.yml build`).
3. Merge `v2-features-phase12-14` → `main`; push; confirm CI goes green on GitHub.
4. (Optional) Switch image generation to `gpt-image-1` — better text-on-packaging; small change in `image_producer.py` (base64 response, size/quality mapping), switchable via `IMAGE_MODEL`.
5. Measure `SLIMMING_CREAM_R-108-A.ai` per `MEASUREMENT_NEEDED.md` to definitively lock the provisional geometry constants; obtain reference files for the two new carton styles.
6. First real deploy per RUNBOOK; run the backup cron; do one restore drill on the host.
