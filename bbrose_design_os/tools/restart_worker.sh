#!/bin/zsh
# Restart the Celery worker on the repository's revision (the §BH55 standing practice: after every landing — the
# Complete Product preflight needs repo == worker revision). Refuses beside a gate or a pytest. Logs to logs/worker.log.
# Tracked here since the clean-up of 2026-10-04; before that it lived, untracked, at ~/bh70_work/restart_worker.sh.
set -u
cd "${0:A:h:h}" || exit 2
if ps -axo command | grep -qE "[M]acOS/Python -m pytest|[g]uarded_commit\.sh"; then echo "BUSY"; exit 3; fi
[[ -z "$(git status --porcelain)" ]] || { echo "DIRTY TREE — not restarting"; exit 4; }
master=$(ps -axo pid,ppid,command | awk '$2==1 && /celery -A config worker/ {print $1}' | head -1)
if [[ -n "$master" ]]; then
  kill -TERM $master
  for i in {1..60}; do ps -p $master > /dev/null || break; sleep 1; done
  ps -p $master > /dev/null && { echo "the old worker did not stop in 60 s"; exit 5; }
fi
# [his goal for the pitch, 2026-10-15, B (5)] the designer's eye looks at every drawing made here
export DESIGNERS_EYE=true
export FACE_ART=true
# Rescue limits: the shared journal reserves $25 per Shanghai calendar day and $250 total.
export MAX_COST_PER_TASK=25
export MAX_COST_PER_DAY=25
( nohup venv/bin/celery -A config worker -l info --concurrency=1 >> logs/worker.log 2>&1 & )
echo "worker started $(date -u +%Y-%m-%dT%H:%M:%SZ) at $(git rev-parse --short HEAD)" >> logs/worker_started.txt
sleep 8
venv/bin/python - <<'PY'
import os, sys
sys.path.insert(0, ".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django; django.setup()
from django.db import connection
with connection.cursor() as c:
    c.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
from apps.pipeline.services.revision import current_revision
from apps.pipeline.round_tasks import report_worker_revision
repo, worker = current_revision(), report_worker_revision.delay().get(timeout=30)
print("repo %s · worker %s · %s" % (repo, worker, "MATCH" if repo == worker else "MISMATCH"))
# the chain's own preflight (the owner's goal of 2026-10-29: the restart's check moved off the ARIA preflight)
from apps.pipeline.services.round_files_gate import chain_preflight
pf = chain_preflight()
print("chain_preflight:", pf["result"])
for name, row in pf["checks"].items():
    if not row["ok"]:
        print("  BLOCKED", name, row["detail"])
PY
