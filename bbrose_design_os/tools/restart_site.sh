#!/bin/zsh
# Restart the local site (Django runserver on 127.0.0.1:8000, no autoreload) on the working tree, logging to
# logs/site.log, and print what it answers. Refuses beside a gate or a pytest.
set -u
cd "${0:A:h:h}" || exit 2
if ps -axo command | grep -qE "[M]acOS/Python -m pytest|[g]uarded_commit\.sh"; then echo "BUSY"; exit 3; fi
[[ -z "$(git status --porcelain)" ]] || { echo "DIRTY TREE — not restarting"; exit 4; }
pid=$(lsof -nP -iTCP:8000 -sTCP:LISTEN -t 2>/dev/null | head -1)
if [[ -n "$pid" ]]; then
  kill -TERM $pid
  for i in {1..30}; do ps -p $pid > /dev/null || break; sleep 1; done
  ps -p $pid > /dev/null && { echo "the old site did not stop in 30 s"; exit 5; }
fi
# [his goal for the pitch, 2026-10-15, B (5)] the designer's eye looks at every drawing made here
export DESIGNERS_EYE=true
export FACE_ART=true
# Rescue limits: the shared journal reserves $25 per Shanghai calendar day and $250 total.
export MAX_COST_PER_TASK=25
export MAX_COST_PER_DAY=25
( nohup venv/bin/python manage.py runserver 127.0.0.1:8000 --noreload >> logs/site.log 2>&1 & )
for i in {1..30}; do curl -s -o /dev/null http://127.0.0.1:8000/ && break; sleep 1; done
echo "site started $(date -u +%Y-%m-%dT%H:%M:%SZ) at $(git rev-parse --short HEAD): $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/)"
