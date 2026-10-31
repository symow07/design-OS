# BBROSE Design OS — Milestones v2: Production Hardening & Feature Build-Out
**Stack:** Python · Django 4.2 · PostgreSQL · Celery/Redis · Claude API · OpenAI API · HTML/CSS/JS
**Basis:** AUDIT_REPORT.md (2026-07-02). Every fix milestone cites the audit finding it resolves.
**Scope:** Take the working demo → the company's main production design tool.

---

## How to use this document

Each milestone is a self-contained Claude Code prompt.
Copy the prompt → paste into Claude Code → execute → verify → move to next.
Do NOT skip milestones inside a phase. Phases 8–9 are blockers; do them first.
Every prompt assumes your working directory is `bbrose_design_os/`.
Numbering continues from Milestones v1 (which ended at Phase 7).

---

## PHASE 8 — Critical Stability & Security Fixes
**Goal:** Nothing can strand, leak, or silently break. Fixes audit C1–C3, C6, C7, H1, H10.

---

### Milestone 8.1 — Authenticated Media Storage (fixes C1)

```
Media is only served when DEBUG=True (config/urls.py:15-16) and has no auth.
Fix both.

Tasks:
1. Add django-storages + boto3 to requirements.txt. In settings.py add a
   STORAGE_BACKEND env switch: "local" (default) or "s3". When "s3", configure
   S3 via env (AWS_STORAGE_BUCKET_NAME, region, private ACL, signed URLs with
   1h expiry).
2. For local mode, create an authenticated download view in apps/core/views.py:
   GET /files/<path> — requires login, resolves against MEDIA_ROOT with strict
   path-traversal protection (resolve + verify prefix), streams via FileResponse.
   Register in config/urls.py for BOTH debug and production. Remove the
   static() media mapping.
3. Update apps/pipeline/serializers.py and the dielines API so every returned
   asset URL goes through the auth route (local) or a signed URL (s3). Never
   return raw /media/ paths.
4. Tests: unauthenticated request → 302/403; traversal attempt (../) → 404;
   authenticated request streams the file.

Verify: run with DEBUG=False (and a dummy ALLOWED_HOSTS) — Gate 1 images and
Gate 2 dieline previews load; direct /media/ URL no longer works.
```

---

### Milestone 8.2 — Crash-Safe Gate State Machine (fixes C2)

```
ARIAAgent.run() marks tasks failed on error, but resume_after_gate_1,
resume_dieline_generation, and resume_after_gate_2 (apps/pipeline/agents/aria.py)
have no error wrapper. A crash strands the task in gate_1_approved /
generating_dieline / gate_2_approved forever, and TaskRetryView only accepts
status='failed' (views.py:241).

Tasks:
1. Extract the try/except → self._fail(...) wrapper from run() into a decorator
   or context manager; apply it to all three resume_* methods so any exception
   sets status='failed', logs to AgentLog with traceback, and records
   task.error_message.
2. In apps/pipeline/tasks.py, on final retry exhaustion call a fail-safe that
   marks the task failed (never re-raise into the void).
3. Extend TaskRetryView: allow retry from failed AND from any intermediate
   status (gate_1_approved, generating_dieline, gate_2_approved) — it should
   resume from the correct step for each status, not restart from scratch.
4. Add DesignTask.error_message (TextField, blank) + migration if not present.
5. Frontend (templates/dashboard/index.html): add render branches for
   gate_2_approved and rejected (currently blank panels, ~line 1200-1212);
   show error_message + Retry button on failed.
6. Tests: force an exception inside each resume_* (mock) → task ends 'failed';
   retry from each stuck status resumes the right step.

Verify: kill the Celery worker mid-resume, restart, hit Retry from the UI —
the task completes.
```

---

### Milestone 8.3 — Gate Concurrency & Ownership (fixes C3)

```
Gate views do read-check-write without locking (apps/pipeline/views.py:77-131),
and Gate2ApproveView never checks packaging_output_id belongs to task_id.

Tasks:
1. In every gate view (Gate1Approve/Reject, Gate2Approve/Reject, DimensionConfirm),
   replace get-then-save with an atomic conditional transition:
   updated = DesignTask.objects.filter(id=task_id, status='awaiting_gate_1')
             .update(status='gate_1_approved')
   if updated == 0 → 409 Conflict {"error": "Task is not awaiting this gate"}.
   Only enqueue the Celery resume when updated == 1.
2. Gate2ApproveView: get_object_or_404(PackagingOutput, id=..., task_id=task_id).
   Same pattern for any image_id / job_id passed to any view.
3. Add a DB CheckConstraint or model-level guard: at most one PackagingOutput
   per (task, is_final=True).
4. Tests: two concurrent approvals → exactly one 200 and one 409, exactly one
   Celery enqueue (mock); cross-task packaging_output_id → 404.

Verify: hammer Gate 1 approve with two parallel curl calls; confirm single
pipeline run in AgentLog.
```

---

### Milestone 8.4 — Secrets & Credentials Cleanup (fixes C6)

```
demo_walkthrough.py:45 and eyeliner_task.py:18 hardcode admin/bbrose2026.

Tasks:
1. Both scripts must read DEMO_ADMIN_USER / DEMO_ADMIN_PASSWORD from env
   (python-dotenv), erroring clearly if unset. Add the keys to .env.example
   with empty values.
2. Add a management command `rotate_demo_password` that resets the admin
   user's password to a supplied value (or prints a generated one).
3. Grep the whole repo for other literals (passwords, keys, tokens); report
   and remove any found.
4. Document in README: rotate the old bbrose2026 password on every existing
   deployment NOW.

Verify: grep -ri "bbrose2026" returns nothing.
```

---

### Milestone 8.5 — Configurable Models + Resilient AI Retries (fixes C7)

```
Model names are pinned in code (claude_service.py:18-19 opus/sonnet,
image_producer.py:26 dall-e-3) and pipeline_errors.py retries any Exception
twice with a fixed 5s sleep.

Tasks:
1. Move to settings (env-driven): CLAUDE_MODEL_HEAVY, CLAUDE_MODEL_FAST,
   IMAGE_MODEL, IMAGE_SIZE, IMAGE_QUALITY. Defaults = current values.
   All agents and services read from settings only.
2. Rewrite the retry decorator in apps/pipeline/services/pipeline_errors.py:
   - Retry ONLY transient errors: rate limits (429), overloaded (529),
     5xx, timeouts, connection errors — use anthropic/openai SDK exception
     classes, not bare Exception.
   - Exponential backoff with jitter, honor Retry-After when present,
     max 5 attempts, cap total wait (configurable).
   - Never retry 400/401/403/404 — fail fast with a clear AgentLog entry.
3. On startup (AppConfig.ready or a check), warn-log if an API key required
   by the configured backend is missing.
4. Tests: mock 429 with Retry-After → waits and succeeds; mock 401 → fails
   immediately, no retry; model names come from overridden settings.

Verify: pipeline runs with settings-only model config; no model string
literals remain in apps/ (grep).
```

---

### Milestone 8.6 — Durable Image Handling (fixes H1)

```
image_producer.py:46-51 silently skips failed downloads; serializers fall back
to DALL·E signed URLs that expire in ~1h; GeneratedImage.image_url is
URLField(max_length=500) and OpenAI URLs exceed it.

Tasks:
1. Migration: image_url → TextField (no length limit).
2. Download with retry (3 attempts, backoff) and a timeout; verify content-type
   and non-zero size; on final failure mark the GeneratedImage with
   download_failed=True and log — never leave a silent gap.
3. Serializer must NEVER return the remote signed URL: if local file missing
   and download_failed, return a placeholder flag the frontend renders as
   "image unavailable — retry" with a per-image redownload endpoint
   POST /api/images/<id>/redownload/.
4. QA Reviewer: if an image file is missing, skip vision for that image with
   an explicit AgentLog note (currently silently degrades to text-only).
5. Tests: failed download flow, redownload endpoint, long URL storage.

Verify: block network to oaidalleapiprodscus (mock), run a pass — UI shows
retryable placeholders, nothing 500s.
```

---

### Milestone 8.7 — Celery Decoupled From DEBUG (fixes H7)

```
settings.py:160 ties CELERY_TASK_ALWAYS_EAGER to DEBUG and EAGER_PROPAGATES
is False, masking dev failures.

Tasks:
1. New env var CELERY_EAGER (default: value of DEBUG for backwards compat,
   but independent). Set CELERY_TASK_EAGER_PROPAGATES=True always.
2. Add /healthz endpoint (apps/core): checks DB, Redis (when not eager), and
   returns worker heartbeat status via celery inspect ping with a short timeout.
   Unauthenticated, returns 200/503 JSON.
3. Task creation view: if not eager and no worker responds to ping, return
   503 "pipeline worker offline" instead of enqueueing into a black hole.
4. Document the two run modes in README.

Verify: stop Redis with CELERY_EAGER=false → task creation returns 503 and
/healthz shows red; eager mode still works for the demo.
```

---

## PHASE 9 — Geometry & Print Correctness
**Goal:** Every dieline that validates is physically foldable and print-shop ready. Fixes C4, C5, H5 (limits), H6, plus provisional constants + docs.

---

### Milestone 9.1 — Dust/Tuck Height Guard + Dimension Limits (fixes C4, part of H5)

```
engine.py:351: dust_h = D × 0.631, tuck zone = W × 1.227. When D > ~1.945·W the
dust flaps exceed the tuck flaps and the sheet top (verified: 12×40×60 →
geometry at y = −10.52). Nothing rejects it; all tests are square (W=D).

Tasks:
1. In apps/dielines/geometry/engine.py: clamp dust_h to
   min(D × 0.631, tuck_zone_height − 2.0mm safety margin). Log/annotate when
   clamped so the spec sheet notes "dust flap reduced".
2. In apps/dielines/validators/schema.py: add max dimensions (e.g. W,D ≤ 300,
   H ≤ 600 — confirm with print shop) and a hard reject when D > 2.5·W with a
   clear message (beyond clamp range = wrong style for this geometry).
3. Post-generation invariant check in the engine: cut-polygon bounding box
   must lie within [0, flat_width] × [0, flat_height] (small epsilon);
   raise GeometryError otherwise — garbage must never export.
4. Tests: add non-square products to the matrix — 12×40×60, 15×35×90,
   40×12×60, and a boundary case at the clamp threshold. Assert bounds
   invariant for ALL matrix entries.

Verify: pytest apps/dielines/tests — all pass including new non-square cases;
12×40×60 either clamps cleanly (bounds OK) or rejects with the style message.
```

---

### Milestone 9.2 — Board Thickness Allowances + DECISION-015 Lock Notches (fixes C5)

```
Locked DECISION-015 (shoulder lock cuts) is unimplemented, and
board_thickness_mm never affects panel layout (engine.py:199-204 raw sums;
thickness only feeds the spec table at 430-441).

Tasks:
1. Read dieline-generator/docs/geometry_decisions.md DECISION-015 first
   (moved into this repo by Milestone 9.4 — do 9.4 first if not done).
2. Implement shoulder lock cuts: board_thickness × 2 notches at each tuck-flap
   base per the decision spec, classified as CUT lines.
3. Add per-panel thickness allowances to fold positions: standard folding-
   carton practice — inside dimensions grow by t per wrap so the carton closes
   square (front panel W, back panel W + 2t, etc. — follow the decision doc /
   ECMA convention and document the chosen rule in the code header).
4. Update flat_width/flat_height math and the spec-sheet inner/outer table to
   stay consistent.
5. Tests: with t=0.45, fold positions shift by the documented allowances;
   notches present in the cut path; t=0 reproduces legacy geometry exactly
   (regression guard against the 28x28x120 coordinate dump).

Verify: 162+ tests pass; coordinate-dump regression matches at t=0.
```

---

### Milestone 9.3 — Re-Measure Provisional Constants (closes engine TODOs)

```
engine.py:149-158 flags two provisional constants: the stadium-slit width
factor and the shoulder tangent length (k=0.5523 quarter-arc approximation) —
never re-measured from the reference Illustrator file.

Tasks:
1. Use dieline-generator/docs/28x28x120_coordinate_dump.json (the measured
   reference) to derive both constants precisely; if the dump lacks the needed
   points, emit a MEASUREMENT_NEEDED.md listing exactly which coordinates to
   extract from the reference .ai and stop.
2. Replace the TODO constants, remove the "cannot claim Pacdora-grade" caveat
   only if measurements confirm, and add DECISION-017 documenting the values.
3. Guard fragile webs: when W ≤ 15, ensure ≥ 2 mm web remains beside the
   tuck-top slit (scale slit width down); test at W=12.
4. Regression tests against the coordinate dump.
```

---

### Milestone 9.4 — Migrate Design Docs, Delete Duplicates (repo hygiene)

```
The design contract lives ONLY in dieline-generator/docs/ (a stale duplicate
project), and engine.py:2 points maintainers at a file that doesn't exist in
the merged repo. Stale LOCKED decisions 011/014 contradict 016 (which the
code follows).

Tasks (repo root, not bbrose_design_os/):
1. Move dieline-generator/docs/geometry_decisions.md, ai_dieline_contract.md,
   and 28x28x120_coordinate_dump.json → bbrose_design_os/apps/dielines/docs/.
   Update the engine.py header path reference.
2. In geometry_decisions.md: mark DECISION-011 and DECISION-014 as SUPERSEDED
   by DECISION-016 with a one-line note each.
3. Delete dieline-generator/ entirely (audit confirmed the merged copy is
   strictly newer). Delete bbrose_design_os/venv_py39_backup/.
4. Add venv/, exports/, media/, *.pyc, .DS_Store to .gitignore if missing.
   Initialize git if the repo isn't version-controlled yet; commit.

Verify: pytest still passes; engine.py header points at an existing file.
```

---

### Milestone 9.5 — PDF/X-Ready Production PDF + Real .ai (fixes H6, M-print)

```
production_pdf.py: registration marks use process CMYK(1,1,1,1) — invisible on
the CutContour/Crease separation plates; fonts are non-embedded base-14; no
TrimBox/BleedBox. ai_exporter.py produces an RGB flattened PDF renamed .ai.

Tasks:
1. Registration marks: use the /All separation colorant (reportlab
   registration color) so they appear on every plate.
2. Embed a TTF (DejaVu Sans or brand font) for all spec-sheet text.
3. Set MediaBox/TrimBox/BleedBox correctly (trim = flat size, bleed = trim +
   bleed_mm) and add OutputIntent metadata targeting PDF/X-4 as far as
   reportlab allows; document any gaps.
4. .ai export: generate from the production PDF path (spot colors intact)
   instead of the RGB SVG; keep the SVG fallback but label its limitations in
   the code and API response ("preview-grade").
5. Validators: extend validate_ai/production checks — assert the spot color
   names CutContour and Crease exist in the PDF resources.
6. Tests for each: marks on plates (inspect PDF ops), embedded font present,
   boxes set, spot names found.

Verify: open the PDF in a preflight tool / Ghostscript separation dump —
CutContour, Crease, and registration all render on their plates.
```

---

## PHASE 10 — Dieline API Hardening
**Goal:** The API path is as correct and safe as the agent path. Fixes H4.

---

### Milestone 10.1 — API Parity, Defaults, Export Routes, IDOR (fixes H4)

```
apps/dielines/api/views.py problems: (a) omitting optional fields → 400
because None is passed into pydantic instead of defaults (lines 57-67);
(b) GenerateDielineView never produces the CMYK production PDF; (c) no CWD
pinning → exports land in the process CWD; (d) response advertises
/exports/{id}.svg which no route serves; (e) no object-level authorization;
(f) LoginRequiredMixin on APIView returns 302 not 401.

Tasks:
1. Defaults: use dims.get(key, DEFAULT) exactly like
   apps/pipeline/agents/dieline_agent.py:254-258; single shared constant
   module for the defaults (3.0 bleed / 4.0 safety / 10.0 glue — confirm).
2. Extract the export orchestration (SVG + .ai + production PDF + validation
   + _in_export_dir CWD pinning) from DielineAgent into a shared service
   apps/dielines/services/export_service.py; both the agent and the API view
   call it. Replace os.chdir with absolute output paths passed to exporters
   (thread-safe; delete _in_export_dir once nothing chdirs).
3. Serve exports: authenticated route GET /api/dielines/jobs/<id>/files/<kind>
   (kind = svg|ai|pdf|spec) using the Milestone 8.1 auth machinery; API
   responses return these URLs only.
4. AuthZ: add owner FK to DielineJob (migration); views enforce
   owner-or-role check (roles arrive in Phase 11 — for now owner or is_staff).
   Replace LoginRequiredMixin with DRF IsAuthenticated so unauthenticated
   calls get 401 JSON.
5. Fix InspirationView mislabeling body width/height as flat_width_mm/
   flat_height_mm (api/views.py:268-269).
6. Tests: omitted-fields request succeeds with defaults; generate → all 3
   files exist under the job's export dir regardless of process CWD; foreign
   user → 403/404; anonymous → 401; file route streams each kind.
```

---

## PHASE 11 — Multi-User, Roles & Workflow
**Goal:** A real team can use it daily with accountability. Fixes H2, H3, H9, H10.

---

### Milestone 11.1 — Users, Roles, Ownership, Audit Trail (fixes H2)

```
No task owner/assignee, no approver recorded on gates, LOGIN_URL is the admin
login so every designer needs is_staff.

Tasks:
1. apps/accounts: real login/logout pages (non-admin), LOGIN_URL=/accounts/login/.
   Groups as roles: Designer, Reviewer, Admin. Management command seed_roles.
2. DesignTask: created_by FK, assigned_to FK (nullable) + migration.
   Task creation sets created_by=request.user.
3. GateDecision model: task FK, gate (1|2|dimension), decision, notes,
   decided_by FK, decided_at. Every gate view writes one — this is the audit
   trail. Keep existing status fields for compatibility.
4. Permissions: Designers create/submit; only Reviewer/Admin approve gates
   (DRF permission classes). AgentLog gains an optional actor FK for
   human-triggered events (retry, reject).
5. Dashboard: show owner/assignee on task cards; "My tasks" filter; gate
   panels display who approved what and when.
6. Tests: designer cannot approve; reviewer can; GateDecision rows written
   with correct actor.
```

---

### Milestone 11.2 — Multi-Brand Support (fixes H3, H9)

```
views.py:20 and dashboard/views.py:18 use Brand.objects.first() —
nondeterministic with 2+ brands. Also dashboard/views.py:24 filters
ColorSystem status="active" but the model/seeds use "canonical" → empty
brand panel.

Tasks:
1. Task creation accepts brand_id (default: sole brand if exactly one exists,
   else required). Validate product/campaign belong to that brand.
2. Dashboard: brand switcher (dropdown) scoping the task list, stats, and
   brand panel; store selection per-user (profile or session).
3. Fix the ColorSystem status filter → 'canonical' (or make the constant
   shared so it can't drift again).
4. Tests: two brands seeded — creation with wrong product/brand pair → 400;
   palette panel non-empty for seeded data.
```

---

### Milestone 11.3 — Revision Workflow: Edit, Re-Run, Clean Notes (fixes H10 + UX gaps)

```
gate_1_notes are never cleared after approval (aria.py:64) so old rejection
feedback poisons every later re-run. Designers also can't edit prompts or
re-run a single stage.

Tasks:
1. Clear gate_1_notes (and gate_2_notes) on approval; store historical notes
   in GateDecision (11.1) instead.
2. Add "Edit & re-run" at Gate 1: reviewer can edit the image prompts
   (surface ImagePrompt records in the UI) and trigger a regenerate-images-only
   pass (skip Creative Director/Prompt Engineer), guarded by the existing
   revision cap.
3. Add per-stage re-run endpoints: rerun_creative, rerun_prompts, rerun_images
   — each resets only downstream artifacts, keeps history.
4. GeneratedImage housekeeping: mark superseded images (superseded=True)
   instead of accumulating unbounded; UI shows current set with a history
   toggle.
5. Tests: approve → notes cleared but preserved in GateDecision; image-only
   rerun does not call the Claude creative stage (mock assertion).
```

---

## PHASE 12 — New Features
**Goal:** The capabilities a main company design tool needs beyond fixing what exists.

---

### Milestone 12.1 — Additional Carton Styles (fixes H5)

```
Only straight_tuck_end_carton exists; schema forces H>W and H>D — compacts
and palettes are impossible.

Tasks:
1. Refactor geometry: StyleBase interface (panels(), flaps(), fold_lines(),
   invariants()) with StraightTuckEnd as the first implementation —
   zero behavior change, all existing tests pass.
2. Implement reverse_tuck_end_carton (mirror tuck orientation) — nearest
   neighbor, reuses most measured constants.
3. Implement tuck_top_auto_bottom (crash-lock bottom) for heavier products.
4. Relax schema per-style: each style declares its own dimension constraints
   (H>W only where the style requires it). Model + API accept structure_type;
   Scenario B (Claude estimation) may propose the style but a human confirms
   it at the dimension gate, per the AI contract.
5. Per-style test matrices incl. non-square cases and bounds invariants
   (Milestone 9.1 pattern).

Note: new styles need measured reference files like the 28x28x120 dump —
if none exist, geometry from ECMA standard formulas, flagged provisional.
```

---

### Milestone 12.2 — Cost Ledger & Budget Controls

```
No cost accounting exists; the only guard is revision caps (aria.py:10-12).

Tasks:
1. ApiCallRecord model: task FK, provider, model, operation, input/output
   tokens or image count, computed cost, created_at. Claude service and image
   producer write one per call (prices in settings, per model).
2. Budget guards in settings: MAX_COST_PER_TASK, MAX_COST_PER_DAY. Exceeding
   the task cap fails the task with a clear message; the daily cap blocks new
   task creation with a 429-style response.
3. Dashboard: cost per task on the card; brain-stats panel shows today/this
   month spend by provider.
4. Tests: budget breach paths; ledger rows per pipeline stage.
```

---

### Milestone 12.3 — Design Library & Search

```
Completed work is currently only reachable through the task list (capped at
50, no filters).

Tasks:
1. Library view: grid of all approved PackagingOutputs — thumbnail, product,
   brand, date, dimensions, approver. Filters: brand, product category, date
   range, status; text search over brief/product name (Postgres full-text).
2. Detail page: final design, dieline preview, all downloads (SVG/AI/PDF/
   spec sheet), gate history (GateDecision), cost (12.2), link to source task.
3. "Start from existing": new task pre-filled from a library item's brief +
   prompts as the starting point.
4. Paginate everything (DRF pagination + UI).
```

---

### Milestone 12.4 — Notifications

```
Designers currently discover state changes only by watching the dashboard.

Tasks:
1. In-app notification model + bell menu: task reached a gate you can approve,
   your task failed, your task completed.
2. Email (Django email backend, console backend in dev) on: awaiting_gate_1,
   awaiting_dimensions, awaiting_gate_2, failed, completed — sent to
   created_by/assigned_to and reviewers per role.
3. Per-user notification preferences (profile flags).
4. Tests: signal/state-transition → notification rows + outbound email.
```

---

### Milestone 12.5 — Batch & Campaign Runs

```
Tasks are created one at a time; campaigns need a size/variant run.

Tasks:
1. BatchRun model: campaign FK, list of products, shared brief overrides.
   Creating a batch fans out one DesignTask per product (Celery group),
   respecting the daily budget (12.2).
2. Batch view: progress per task, aggregate gate queue ("approve all Gate 1
   picks in one screen" — one selected image per task, single submit that
   applies Milestone 8.3 atomic transitions per task).
3. Batch export: zip of all final deliverables for the campaign.
4. Tests: fan-out count, budget-blocked fan-out, aggregate approve.
```

---

## PHASE 13 — Frontend Overhaul
**Goal:** From one 1,600-line template to a maintainable, live UI. Fixes H8, part of C2 UI.

---

### Milestone 13.1 — Split the Mega-Template

```
templates/dashboard/index.html is 1,600+ lines of HTML+CSS+JS.

Tasks:
1. Split into template partials: base.html, task_list.html, task_detail.html,
   gate1_gallery.html, dimension_form.html, gate2_review.html, completed.html,
   brand_panel.html. CSS → static/css/dashboard.css; JS → static/js/ modules
   (api.js, poll.js, gates.js, render.js).
2. Every task status maps to exactly one partial — including failed,
   rejected, gate_2_approved (blank today).
3. No behavior change; whitenoise serves the new static files.

Verify: full demo walkthrough (seed_dieline_demo) works identically.
```

---

### Milestone 13.2 — SSE Live Updates + Pagination (fixes H8)

```
2s per-task polling + 5s stats polling won't survive a team; TaskListView
truncates at 50 (views.py:255).

Tasks:
1. Server-Sent Events endpoint /api/tasks/<id>/events/ streaming status +
   new AgentLog entries (django-eventstream or a StreamingHttpResponse
   generator with a Postgres LISTEN/NOTIFY or lightweight Redis pubsub;
   choose the simplest that works with the current deploy).
2. Frontend swaps polling for EventSource with automatic fallback to 10s
   polling if SSE fails.
3. Paginate task list API (DRF PageNumberPagination, 25/page) + UI paging and
   status/brand/owner filters.
4. Brain-stats: recompute server-side max once per 15s (cache), not per
   request.

Verify: two browser tabs see a gate transition within 1s without any 2s
request storm in the network tab.
```

---

## PHASE 14 — Ops, Deployment & CI
**Goal:** Boring, observable, repeatable production. Fixes all MEDIUM ops findings.

---

### Milestone 14.1 — Logging, Monitoring, Security Headers

```
Tasks:
1. LOGGING config in settings.py: console JSON in prod, verbose in dev;
   loggers for apps.pipeline, apps.dielines, celery; request-id middleware.
2. Sentry SDK (env-gated DSN) for Django + Celery.
3. Production security settings, active when DEBUG=False:
   SECURE_SSL_REDIRECT, HSTS (with sane initial max-age), SESSION_COOKIE_SECURE,
   CSRF_COOKIE_SECURE, CSRF_TRUSTED_ORIGINS from env, X_FRAME_OPTIONS=DENY,
   SECURE_REFERRER_POLICY. Replace the fragile DEBUG env-coercion shim
   (settings.py:14-19) with env.bool.
4. `manage.py check --deploy` must come back clean.
```

---

### Milestone 14.2 — Pinned Dependencies & CI

```
Tasks:
1. Pin all requirements (pip-compile: requirements.in → requirements.txt);
   django==4.2.<latest>; psycopg[binary] instead of psycopg2-binary.
2. GitHub Actions (or equivalent) CI: ruff lint, full pytest with a Postgres
   service container, `manage.py makemigrations --check`, `check --deploy`.
3. Delete the Pacdora path (pacdora_agent.py, PACKAGING_BACKEND toggle,
   playwright dependency) after team confirmation — audit found it demo-grade
   with a test that mocks a call the agent never makes. If it must stay,
   quarantine behind the toggle and exclude from CI coverage requirements.
4. New tests required by CI to pass: DRF gate views (from 8.2/8.3), dielines
   API (10.1), permissions (11.1) — replace the one-line stubs in
   apps/core/tests.py, apps/dashboard, apps/accounts.
```

---

### Milestone 14.3 — Deployment & Backups

```
Tasks:
1. Dockerfile (python:3.11-slim, gunicorn) + docker-compose.prod.yml: web,
   worker, redis, postgres, with /healthz (8.7) wired as the healthcheck.
2. Entrypoint runs migrate + collectstatic; media volume or S3 per 8.1.
3. Nightly pg_dump backup job + media sync; documented restore procedure
   (test it once).
4. RUNBOOK.md: deploy, rollback, rotate keys, common failures (worker down,
   budget exceeded, stuck task recovery).
```

---

## Execution order & definition of done

| Priority | Phases | Gate to next |
|---|---|---|
| P0 — blockers | 8, 9 | Demo passes with DEBUG=False; all geometry tests (incl. non-square) green |
| P1 — safe team use | 10, 11 | Two-user concurrent walkthrough clean; audit trail populated |
| P2 — daily-driver features | 12, 13 | A real campaign run end-to-end by a designer, not a developer |
| P3 — production ops | 14 | CI green, deployed via Docker, restore drill done |

**Overall definition of done:** a designer with a Designer-role account creates a task, a reviewer approves both gates, and the print shop accepts the production PDF — with zero developer involvement and full audit/cost records.
