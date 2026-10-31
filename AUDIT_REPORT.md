# BBROSE Design OS — Full Production-Readiness Audit
**Date:** 2026-07-02 · **Scope:** entire repo (`bbrose_design_os` + `dieline-generator`) · ~7,300 lines of Python audited; dieline test suite executed (162/162 passed, DB-less).

**Verdict:** Works well as a single-user demo. Not yet safe as the company's main design tool — there are showstoppers in media serving, the gate state machine, geometry edge cases, and multi-user security. All are fixable; a prioritized plan is at the end.

> **RE-MEASURED 2026-09-20 — §BH55 Phase 4, "the stale July audit".** Nothing above or below is rewritten: this
> document is the reading of 2026-07-02 and stays as it was written (CLAUDE.md, §AZ0(u) — annotate, never rewrite).
> What is added is a dated **STATUS** line under each CRITICAL finding, saying what that finding measures today and
> where. **None of the seven CRITICALs stands as written**: C1, C2, C3, C6 and C7 are closed outright, C4 is closed
> in the validator, and C5 is implemented but conditional on a flag whose three doors disagree on its default. The
> verdict sentence above is therefore stale in three of the four areas it names — media serving, the gate state
> machine and multi-user security — and partly stale in the fourth.
>
> **SCOPE OF THIS RE-MEASURE:** the CRITICAL section only. **HIGH and MEDIUM were NOT re-measured**, and two spot
> checks say they must not be read as cleared: H3's `Brand.objects.first()` occurs 20 times in `apps/`, and H11's
> `pacdora_agent.py` is still in the tree. An unannotated finding below means "not looked at in this pass", never
> "still true" and never "closed".
>
> **AND THIS IS NOT THE FRESH AUDIT.** The owner's §BH43 line parks that in his own words — "The long tail — the
> exempt surfaces, the Kufi and Sahel hunt, my purchase sitting, the dark accent and ink roles, CMYK print intent,
> and **a fresh audit to replace the stale July one** — waits for me to open it"
> (`OWNER_BLOCKER_CLEARANCE.md:20382-20385`). §BH55 Phase 4 names the same items and is him opening them, but what
> it opens for THIS one is the staleness: a reading of 2026-07-02 that still asserts, at the root of the
> repository, showstoppers that were closed months ago. That is corrected here, in place. A fresh audit — a new
> reading of the whole system, with its own verdict — is a different act, it is the one he named, and it is not
> taken here.

---

## CRITICAL — will break or is a security hole

### C1. Generated files 404 in production
`config/urls.py:15-16` serves `/media/` only when `DEBUG=True`. With `DEBUG=False`, every design image, dieline SVG, and PDF returned by the API is a dead link — Gate 1 gallery and Gate 2 viewer go blank. Media also has **zero authentication**: anyone with a URL sees all designs.
**Fix:** S3 (or nginx `X-Accel-Redirect`) with authenticated download views.

**STATUS 2026-09-20 — CLOSED.** `config/urls.py:34` routes `files/<path:path>` to `apps.core.views.serve_media`, an
authenticated download view; the comment at `:31-33` records that the `DEBUG`-only unauthenticated `/media/` route
"was removed (Milestone 8.1 / audit C1)". The dead-link half and the zero-authentication half are both answered.

### C2. Tasks can get stranded forever, with no recovery from the UI
`ARIAAgent.run()` catches errors and marks the task `failed` (`aria.py:45-117`), but the three `resume_*` methods (`aria.py:196, 266, 346`) have no such wrapper. If a resume raises, the task is stuck in `gate_1_approved` / `generating_dieline` / `gate_2_approved` — the frontend polls "working" forever (`templates/dashboard/index.html:1189`), and `TaskRetryView` only accepts `status='failed'` (`views.py:241`), so recovery requires the DB shell. `gate_2_approved` and `rejected` have no render branch at all (`index.html:1200-1212`).

**STATUS 2026-09-20 — CLOSED.** The resume methods carry the error wrapper the finding said they lacked:
`@crash_safe` on `resume_after_gate_1` (`aria.py:910`) and on the four resumes below it. `TaskRetryView`
(`views.py:1738`) now recovers "a failed OR stuck task", and its docstring names Milestone 8.2 and this defect —
"a crash mid-resume used to strand tasks in intermediate statuses with no recovery from the UI".

### C3. Gate race conditions + missing ownership check
Gate views do read-check-write without `select_for_update` (`views.py:77-91`): two users approving the same task both pass and enqueue duplicate pipeline runs → duplicate outputs, double AI spend. Worse, `Gate2ApproveView` (`views.py:119-131`) never checks that `packaging_output_id` belongs to `task_id` — any logged-in user can final-approve any other task's output, or pass a bogus ID and strand the task (→ C2).

**STATUS 2026-09-20 — CLOSED.** Both halves. The task is taken under a row lock — `views.py:440`,
`DesignTask.objects.select_for_update().get(id=task.id)` — and the output is resolved as
`get_object_or_404(PackagingOutput, id=packaging_output_id, task=task)` (`views.py:634`), so an output belonging to
another task cannot be approved through this door.

### C4. Non-foldable dieline geometry passes validation silently
`geometry/engine.py:351`: dust flap height = `D × 0.631`, tuck zone = `W × 1.227`. When depth > ~1.95 × width (deep narrow cartons), dust flaps become **taller than the tuck flaps** — violating locked DECISION-004 and extending outside the declared sheet (verified: 12×40×60 mm → geometry at y = −10.5 mm). Spec-sheet dimensions are wrong, the validator (`validators/schema.py:109-121`) doesn't check the W:D relation, and all test products are square so tests never catch it. **A print shop could receive a die that can't fold.**

**STATUS 2026-09-20 — CLOSED in the validator.** `apps/dielines/validators/schema.py:173-179`, commented "Milestone
9.1 (audit C4)", refuses a carton whose `depth_mm` exceeds `max_ratio × width_mm` — the W:D relation the finding said
nothing checked. (What the dieline path still owes is measured elsewhere and is not this finding: see entry 10 on
`bbrose_design_os/docs/roadmap/bh55/ACCEPTANCE_TIME_LIST.md`.)

### C5. Board-thickness allowances and shoulder lock cuts missing
Locked DECISION-015 (shoulder lock notches at the tuck bases — "without these the tuck tears the shoulder on first fold") is **not implemented** anywhere in `engine.py`. Fold positions are raw `G+W+D+W+D` sums (`engine.py:199-204`); `board_thickness_mm` only feeds the spec table (`engine.py:430-441`). On real 0.35+ mm stock the wrap won't close square.

**STATUS 2026-09-20 — IMPLEMENTED, CONDITIONAL.** Both are built. The DECISION-015 shoulder lock notches are cut at
each tuck base (`apps/dielines/geometry/engine.py:488-529`) and the ECMA per-panel allowances are applied — but only
when `thickness_compensation` is true: `engine.py:599` reads `t_comp = board_thickness if comp else 0.0`, and with
`comp` false the layout is the legacy raw `G+W+D+W+D` sum the finding describes, byte-identical to the reference
snapshot by design. **The doors disagree on the default**: `apps/pipeline/views.py:855` defaults it False,
`apps/pipeline/agents/aria.py:1076-1077` defaults it True, `apps/pipeline/agents/dieline_agent.py:349-350` defaults
it False. So whether a carton is drawn with its lock notches depends on which door the design came through — which
is not what the finding asked for, and is not a state this document could have described.

### C6. Hardcoded admin credentials in source
`demo_walkthrough.py:45` and `eyeliner_task.py:18`: `admin / bbrose2026`. Rotate and remove.

**STATUS 2026-09-20 — CLOSED.** `bbrose2026` occurs in no `.py` file in the tree.

### C7. Pinned AI model names + naive retry
`claude_service.py:18-19` pins `claude-opus-4-7`/`claude-sonnet-4-6`; `image_producer.py:26` pins `dall-e-3`. A model retirement bricks the pipeline with no settings override. Retry logic (`pipeline_errors.py:25-51`) is 2 fixed 5s attempts on bare `Exception` — retries non-retryable 401s, gives up on 429 bursts, no backoff.

**STATUS 2026-09-20 — CLOSED for the pinned names.** `apps/pipeline/services/claude_service.py:31-53` reads
`settings.CLAUDE_MODEL_HEAVY` and `settings.CLAUDE_MODEL_FAST`, with its own comment naming Milestone 8.5: "Model
names are settings-driven". A model retirement is now a settings change. The retry half of this finding
(`pipeline_errors.py`) was not re-measured in this pass.

---

## HIGH — breaks under real daily usage

- **H1. Expiring image URLs / silent download failures.** `image_producer.py:46-51` silently skips failed downloads; the serializer then falls back to the DALL·E signed URL (`serializers.py:15-19`), which expires in ~1 hour → broken Gate 1 images. Also `image_url` is `URLField(max_length=500)` (`pipeline/models.py:52`) — OpenAI URLs routinely exceed that → Postgres error kills the pass.
- **H2. No multi-user model.** No task owner/assignee, no approver recorded on gates, no roles, no audit trail (`pipeline/models.py:18-27`). `LOGIN_URL=/admin/login/` means every designer needs `is_staff` → full Django admin access.
- **H3. Single-brand hardcode.** `views.py:20`, `dashboard/views.py:18` use `Brand.objects.first()` — undefined ordering; a second brand makes task creation nondeterministic.
- **H4. Dieline API bugs.** `api/views.py:57-67`: omitting optional fields (bleed etc.) → 400 instead of documented defaults. The API path never generates the CMYK production PDF (only the agent path does), doesn't pin CWD (exports land wherever the process launched; `os.chdir` in `dieline_agent.py:76-86` is also process-wide → race under concurrent workers), and advertises `/exports/{id}.svg` which no URL route serves. No object-level auth (IDOR): any user can regenerate anyone's job.
- **H5. Only one carton style, no max dimensions.** Only `straight_tuck_end_carton` exists; schema forces H>W and H>D — compacts/palettes are impossible. No upper bound: a 5,000 mm carton validates.
- **H6. `.ai` export is an RGB PDF renamed.** `exporters/ai_exporter.py` produces a flattened generic PDF — Illustrator loses layers/spot colors. Only the production PDF has real `CutContour`/`Crease` spot separations (that part is done correctly).
- **H7. Celery-eager coupling.** `CELERY_TASK_ALWAYS_EAGER = DEBUG` (`settings.py:160`): in dev the multi-minute pipeline runs inside the HTTP request; in prod it silently requires Redis+worker with no health check. `EAGER_PROPAGATES=False` masks dev failures.
- **H8. Frontend won't scale.** One 1,600-line template, 2s polling per task + 5s stats polling, task list truncated at 50 with no pagination (`views.py:255`).
- **H9. Dashboard palette bug.** `dashboard/views.py:24` filters `ColorSystem status="active"` but seeds/pipeline use `'canonical'` (`core/models.py:21`) — brand panel renders empty.
- **H10. Stale rejection notes.** `gate_1_notes` never cleared after approval (`aria.py:64`) — old feedback re-applied on every retry.
- **H11. Pacdora legacy path is demo-grade.** Guessed CSS selectors, blind 4s waits (`pacdora_agent.py:137-221`); its test mocks a call the agent never makes (`test_full_pipeline.py:219-229`) — false confidence. Consider deleting the path entirely.

---

## MEDIUM — quality / ops

- No `LOGGING` config, no Sentry/APM, no health endpoints; failures live only in `AgentLog` rows.
- Unpinned requirements (`anthropic`, `openai`, `celery` floating); `django==4.2` misses 4.2.x security patches; `psycopg2-binary` discouraged in prod.
- No prod security headers (HSTS, `SECURE_SSL_REDIRECT`, secure cookies, `CSRF_TRUSTED_ORIGINS`).
- No cost controls beyond revision caps: no per-day budget or token ledger (HD DALL·E + Opus vision QA per image per pass).
- Test gaps: dieline unit tests are strong (162 pass), but zero tests for DRF gate views/races; `core`/`accounts`/`dashboard` tests are stubs; no non-square (W≠D) product in the geometry test matrix (which is why C4 was never caught).
- Production PDF polish: registration marks use process CMYK not the `/All` separation (invisible on die plates), fonts not embedded, no TrimBox/BleedBox — not PDF/X compliant.
- Two provisional geometry constants (slit-width factor, shoulder tangent k=0.5523) flagged in-code as never re-measured from the reference AI file (`engine.py:149-158`).
- Aspect-ratio QA hardcodes DALL·E portrait (`image_checks.py:30`); prompt engineer emits Midjourney `--ar` flags DALL·E ignores.
- Repo hygiene: `venv/` + `venv_py39_backup/` inside the tree (delete the backup); `dieline-generator/` duplicate is strictly older and can be deleted — **but first move `docs/geometry_decisions.md`, `docs/ai_dieline_contract.md`, and `28x28x120_coordinate_dump.json` into the main app** (the engine header references docs that don't exist in the merged repo). Reconcile stale LOCKED decisions 011/014 vs 016 while doing so.

---

## What's already good

Deterministic geometry engine with a written design contract; AI-never-touches-geometry contract honored; Scenario B handles malformed Claude output, missing keys, and low confidence gracefully; production PDF uses true spot-color separations; SECRET_KEY from env; `IsAuthenticated` enforced on the API; 162 passing geometry/exporter tests; sensible revision caps.

---

## Roadmap to "main company designer"

**Phase 1 — Stop-the-bleed (1–2 weeks)**
1. Real media storage (S3/nginx) + authenticated downloads (C1).
2. Crash-safe state machine: wrap `resume_*`, atomic `UPDATE…WHERE status=`, ownership check on Gate 2, retry from any stuck state (C2/C3).
3. Geometry guards: `dust_h < tuck_h` clamp, max dimensions, W≠D tests (C4). Rotate demo credentials (C6).
4. Model names/sizes to settings + backoff-aware retries (C7). Fix image download retry + `URLField` length (H1).

**Phase 2 — Multi-user & print fidelity (2–4 weeks)**
5. Owner/assignee/approver on tasks, roles, non-admin login, audit trail (H2). Fix brand hardcode (H3).
6. Implement DECISION-015 notches + board-thickness allowances (C5); re-measure the two provisional constants.
7. Fix dieline API (defaults, production PDF, export routes, IDOR) (H4). Generate `.ai` from the spot-color PDF (H6).

**Phase 3 — Scale & ops (ongoing)**
8. Additional carton styles (flat formats for compacts/palettes) (H5).
9. Replace polling with WebSockets/SSE; paginate; break up the mega-template (H8).
10. Ops baseline: pinned deps, LOGGING+Sentry, Redis/Celery health checks, security headers, CI with gate-view tests, cost ledger.
11. Delete `venv_py39_backup/`, Pacdora path, and `dieline-generator/` (after moving docs).
