# BBROSE Design OS — Operations Runbook (Milestone 14.3)

All commands run from `bbrose_design_os/` unless noted. The production stack
is `docker-compose.prod.yml` (web + worker + redis + postgres).
**Note:** Docker was not available on the machine where these files were
authored — run `docker compose -f docker-compose.prod.yml build` once on the
deploy host and fix anything it surfaces before the first real deploy. The
backup/restore procedure *was* tested end-to-end (2026-07-03) against a live
Postgres in local mode, and `docker-entrypoint.sh` is executed (happy + DB-down
paths) by the test suite on every CI run.

---

## 1. Deploy

```sh
# One-time host setup
cp .env.example .env      # then fill in: SECRET_KEY (50+ random chars),
                          # POSTGRES_PASSWORD, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS,
                          # ANTHROPIC_API_KEY, OPENAI_API_KEY, SENTRY_DSN (optional)

# Deploy / upgrade (build, migrate, collectstatic all happen in the entrypoint)
git pull
docker compose -f docker-compose.prod.yml up -d --build

# Watch it come up
docker compose -f docker-compose.prod.yml ps          # healthchecks: web uses /healthz
docker compose -f docker-compose.prod.yml logs -f web worker
curl -fsS http://localhost:8000/healthz               # {"status": "ok", ...}
```

TLS terminates in front of `web` (nginx/traefik/cloud LB) —
`SECURE_PROXY_SSL_HEADER` is already configured; forward `X-Forwarded-Proto`.

## 2. Rollback

```sh
git log --oneline -5                  # find the last good commit
git checkout <good-sha>
docker compose -f docker-compose.prod.yml up -d --build
```

Migrations are additive so far; if a bad migration must be reversed:
`docker compose -f docker-compose.prod.yml exec web python manage.py migrate <app> <previous_migration>`
— check `showmigrations` first. If the DB is damaged, restore from backup (§4).

## 3. Rotate keys & credentials

| Credential | How |
|---|---|
| `SECRET_KEY` | New value in `.env` → `up -d` (invalidates all sessions — users just re-log-in) |
| AI keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) | Rotate at the provider → update `.env` → `up -d` |
| Demo admin password | `docker compose -f docker-compose.prod.yml exec web python manage.py rotate_demo_password` |
| `POSTGRES_PASSWORD` | `ALTER USER bbrose WITH PASSWORD '...'` in psql, update `.env`, `up -d` |
| A user's password | `manage.py changepassword <username>` (exec in web) |

## 4. Backups & restore

**Nightly backup** — host cron (dump + media tar, 14-day retention):

```cron
0 3 * * *  cd /path/to/bbrose_design_os && sh scripts/backup.sh >> backups/backup.log 2>&1
```

Ship `backups/` off the host (rsync/rclone to object storage) — a backup on
the same disk is not a backup.

**Restore** (tested 2026-07-03: db row counts + 394 media files verified):

```sh
docker compose -f docker-compose.prod.yml stop worker     # stop writers
sh scripts/restore.sh backups/db_<stamp>.dump backups/media_<stamp>.tar.gz
docker compose -f docker-compose.prod.yml exec web python manage.py check
docker compose -f docker-compose.prod.yml start worker
# verify: log into the dashboard, open a completed task, download a deliverable
```

## 5. Common failures

**Worker down / "pipeline worker offline" (503 on task creation)**
`docker compose -f docker-compose.prod.yml ps worker` → restart it:
`docker compose -f docker-compose.prod.yml restart worker`.
`/healthz` shows `celery: no workers responded` in this state.

**Daily budget exceeded (429 on task creation)**
Spend hit `MAX_COST_PER_DAY` (rolling 24h, see the dashboard AI-spend panel /
`ApiCallRecord` in admin). Wait, or raise it in `.env` and `up -d`.

**Task failed with "task budget exceeded"**
One task crossed `MAX_COST_PER_TASK`. Inspect its `ApiCallRecord` rows in
admin; raise the cap or fix the loop before retrying.

**Task fails with `null value in column ... violates not-null constraint` right after a code update**
The Celery worker is running stale code from before a model migration (the dev
server auto-reloads; the worker does NOT). Restart the worker —
`pkill -f "celery -A config worker"` then `sh scripts/run_dev.sh` (or restart
the compose `worker` service in prod) — and hit Retry on the failed task.

**Stuck task recovery**
Every pipeline stage is crash-safe (Milestone 8.2): a crashed run ends
`failed` with `error_message`, and Retry in the dashboard resumes from the
correct step — including from stranded intermediate states. If a task sits in
`running` with a dead worker: restart the worker, then hit Retry.

**Task fails with "OpenAI account billing limit reached"**
The PROVIDER account (platform.openai.com) hit its own spending cap or ran
out of credits — this is separate from the app's MAX_COST_PER_DAY ledger.
Add credits / raise the limit under platform.openai.com → Billing, then hit
Retry. (Anthropic equivalent: console.anthropic.com → Billing.)

**Missing API keys**
Tasks fail immediately with "Missing API key(s): ..." — set them in `.env`,
`up -d`, hit Retry. The web log also warns at startup.

**Static files 404 / unstyled pages**
The entrypoint runs `collectstatic` with `USE_MANIFEST_STATIC=true`; check the
web startup log for collectstatic errors. Dev never needs collectstatic.

**Postgres disk growth**
`AgentLog` and `ApiCallRecord` grow with usage. Prune old rows via admin or a
scheduled `delete()` if they exceed your retention needs (safe: they're audit
data, not pipeline state).

**Dashboard slow / requests queueing under load**
Each live SSE task stream holds one gunicorn gthread thread (≤ ~5 min).
Capacity = workers × threads (image default 2×8 = 16). Override the `web`
command in the compose file to scale (see the sizing comment there). Long AI
runs live on the Celery worker, not gunicorn — scale `--concurrency` there
separately.

**Live updates frozen behind a CDN/proxy**
Some proxies buffer SSE without erroring. The server sends a `ping` event
~15s and the client falls back to 10s polling after 45s of silence, so the UI
self-heals — but for real-time behavior, disable buffering for
`/api/tasks/*/events/` (nginx: honoured automatically via `X-Accel-Buffering:
no`; Cloudflare: bypass cache/buffering for that path).
