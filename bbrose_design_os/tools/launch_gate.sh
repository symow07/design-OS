#!/bin/zsh
# launch_gate.sh <msgfile> <logfile> — runs the guarded gate from the app folder (the inner root), always.
# Pass ABSOLUTE paths: the script changes directory before it reads them. It refuses to start beside a running gate
# or test run (one gate at a time). Tracked here since the clean-up of 2026-10-04; before that it lived, untracked,
# at ~/bh33_work/launch_gate.sh (its history copy: docs/design_intelligence/sittings/bh33/launch_gate.sh).
MSG=$1; LOG=$2
cd "${0:A:h:h}" || { echo "cannot cd to the inner root" >> "$LOG"; exit 2; }
test -f tools/guarded_commit.sh || { echo "launcher missing at $(pwd)/tools/guarded_commit.sh" >> "$LOG"; exit 2; }
: > "$LOG"
if ps -axo command | grep -qE "[M]acOS/Python -m pytest|[g]uarded_commit\.sh"; then
  echo "BUSY — a gate or a test run is already running; not launched" >> "$LOG"; exit 3
fi
{ echo "launched $(date -u +%Y-%m-%dT%H:%M:%SZ) HEAD=$(git rev-parse --short HEAD) cwd=$(pwd)"; zsh tools/guarded_commit.sh -F "$MSG"; echo "GEXIT=$?"; echo "finished $(date -u +%Y-%m-%dT%H:%M:%SZ) HEAD=$(git rev-parse --short HEAD)"; } >> "$LOG" 2>&1
tail -3 "$LOG"
