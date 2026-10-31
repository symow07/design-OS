# BBROSE Design OS

An AI-assisted packaging design pipeline for the BBROSE cosmetics brand. A human
guides an agent team from a text brief to print-ready packaging, approving the
work at gates along the way.

## Pipeline

Orchestrated by `ARIAAgent` (`apps/pipeline/agents/aria.py`):

```
Creative Director → Prompt Engineer → Image Producer → QA Reviewer
  → Gate 1   (human approves a design)
  → Dimension gate   (human confirms carton dimensions)
  → deterministic dieline generation (SVG + optional Illustrator .ai)
  → Gate 2   (human approves the dieline)
  → Completed   (download dieline + branded spec-sheet PDF)
```

The **dieline generator** (`apps/dielines/`) draws every carton's
die. Per its design contract, the AI only ever *estimates* scalar
dimensions; **all geometry is produced by deterministic Python**
(`apps/dielines/geometry/`), with a human confirming dimensions before geometry
runs.

- **Scenario A** — exact dimensions read straight from the `Product` record
  (`width_mm` / `depth_mm` / `height_mm`); no AI, no API key.
- **Scenario B** — Claude estimates dimensions from context; low-confidence
  fields are left blank for manual entry.

## Setup

Requires **Python 3.11** (the dieline code uses syntax that needs 3.10+) and
**PostgreSQL**.

```bash
cd bbrose_design_os
python3.11 -m venv venv
venv/bin/pip install -r requirements.txt

cp .env.example .env          # then fill in values (see below)
createdb bbrose_db            # or point DATABASE_URL at an existing DB

venv/bin/python manage.py migrate
venv/bin/python manage.py seed_bbrose          # brand + canonical color systems
venv/bin/python manage.py createsuperuser
```

`.env` keys: `SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, and (optional)
`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` for the AI stages. See `.env.example`
for the full list (storage backend, AI model overrides, Celery mode, demo
credentials).

## Run modes (Celery)

`CELERY_EAGER` (`.env`) selects how pipeline tasks execute — it defaults to
the value of `DEBUG` but is independent of it:

- `CELERY_EAGER=true` — **demo mode.** `.delay()` runs tasks synchronously
  in-process; no Redis or Celery worker needed. Eager task errors always
  propagate (`CELERY_TASK_EAGER_PROPAGATES=True`).
- `CELERY_EAGER=false` — **worker mode.** Tasks enqueue to Redis and require
  `celery -A config worker`. Task creation returns `503 "pipeline worker
  offline"` when no worker answers a ping, and the unauthenticated `/healthz`
  endpoint reports DB / Redis / worker status (`200` healthy, `503` not).

## Security notes

- **Rotate the old hardcoded demo admin password on every existing deployment
  NOW.** Earlier revisions of the demo scripts `demo_walkthrough.py` /
  `eyeliner_task.py` (removed in the clean-up of 2026-10-04; git history keeps
  them) shipped a hardcoded `admin` password in source. Run
  `manage.py rotate_demo_password` (prints a generated password, or pass
  `--password`) on each deployment.
- Media (generated designs, dielines, PDFs) is never served anonymously:
  `STORAGE_BACKEND=local` streams files through the login-protected
  `/files/<path>` route in both debug and production; `STORAGE_BACKEND=s3`
  uses a private bucket with signed URLs (1 h expiry).

## Run the clickable demo

The dieline gate works end-to-end **without any API key** via Scenario A:

```bash
venv/bin/python manage.py seed_dieline_demo    # product + a task parked at Gate 1
venv/bin/python manage.py runserver
```

Open <http://127.0.0.1:8000/>, log in, select the **[DEMO]** task, then:

1. **Gate 1** — pick one of the three designs.
2. **Confirm Dimensions** — pre-filled from the product (35 × 35 × 100 mm); adjust and **Generate Dieline**.
3. **Gate 2** — review the generated dieline SVG, then **Approve Final**.
4. **Completed** — download the dieline SVG and the spec-sheet PDF.

## Notes

- `.ai` (Illustrator) export is best-effort: it needs native `cairo` + `svglib`
  (`brew install cairo && pip install svglib cairosvg`). SVG is always produced.
- Media downloads require login and are served in both debug and production
  via `/files/<path>` (see Security notes).
- `dieline-generator/` is the original standalone source the `apps/dielines`
  app was merged from, kept for reference.
