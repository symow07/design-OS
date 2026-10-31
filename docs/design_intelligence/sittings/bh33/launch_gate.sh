#!/bin/zsh
# launch_gate.sh <msgfile> <logfile> — runs the guarded gate from the INNER root, always.
MSG=$1; LOG=$2
cd /Users/symow/Desktop/bbrose-systemOS/bbrose_design_os || { echo "cannot cd to the inner root" >> "$LOG"; exit 2; }
test -f tools/guarded_commit.sh || { echo "launcher missing at $(pwd)/tools/guarded_commit.sh" >> "$LOG"; exit 2; }
: > "$LOG"
{ echo "launched $(date -u +%Y-%m-%dT%H:%M:%SZ) HEAD=$(git rev-parse --short HEAD) cwd=$(pwd)"; zsh tools/guarded_commit.sh -F "$MSG"; echo "GEXIT=$?"; echo "finished $(date -u +%Y-%m-%dT%H:%M:%SZ) HEAD=$(git rev-parse --short HEAD)"; } >> "$LOG" 2>&1
tail -3 "$LOG"
