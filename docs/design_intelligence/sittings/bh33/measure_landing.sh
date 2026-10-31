#!/bin/zsh
# Post-landing measurement: measure_landing.sh <base_commit> <gate_log>. Read-only.
BASE=$1; LOG=$2
cd /Users/symow/Desktop/bbrose-systemOS || exit 1
echo "=== gate log ===" && cut -c1-200 "$LOG"
H=$(git rev-parse --short HEAD) && echo "HEAD $H (base $BASE)"
echo "=== numstat $BASE..HEAD ===" && git diff --numstat $BASE $H && git diff --shortstat $BASE $H
echo "=== outside apps+register+ledger ===" && (git diff --name-only $BASE $H | grep -vE '^bbrose_design_os/apps/|record_gate_ledger|^OWNER_BLOCKER_CLEARANCE.md$' || echo NONE)
echo "=== manifest/records/identity in commit ===" && (git diff --name-only $BASE $H | grep -E 'suite_file_manifest|/records/|protocol_identity' || echo NONE)
echo "=== L6 ===" && head -1 bbrose_design_os/.tier2_gate_output
echo "=== L7 ledger HEAD $(git show HEAD:./bbrose_design_os/docs/roadmap/palt_m6/record_gate_ledger.jsonl | wc -l | tr -d ' ') HEAD~1 $(git show HEAD~1:./bbrose_design_os/docs/roadmap/palt_m6/record_gate_ledger.jsonl | wc -l | tr -d ' ') worktree $(wc -l < bbrose_design_os/docs/roadmap/palt_m6/record_gate_ledger.jsonl | tr -d ' ') ==="
bbrose_design_os/venv/bin/python - <<'EOF'
import hashlib, subprocess, os
a=subprocess.run(['git','show','HEAD~1:./bbrose_design_os/docs/roadmap/palt_m6/record_gate_ledger.jsonl'],capture_output=True).stdout
b=subprocess.run(['git','show','HEAD:./bbrose_design_os/docs/roadmap/palt_m6/record_gate_ledger.jsonl'],capture_output=True).stdout
print("ledger append-only (HEAD~1 byte-prefix of HEAD):", b.startswith(a), "| new line:", b[len(a):][:200].decode())
def seal(lines,x,y): return hashlib.sha256(b'\n'.join(lines[x:y]).rstrip(b'\n')).hexdigest()[:16]
g=open('bbrose_design_os/apps/ire/container_font_authority.py','rb').read().split(b'\n'); print("GATE [514:541]", seal(g,514,541), "(7fbeb8f1fe10b0fb) lines", len(g))
t=subprocess.run(['git','show','a76242c^:bbrose_design_os/apps/pipeline/tests/test_container_font_authority.py'],capture_output=True).stdout.split(b'\n'); print("TEST", seal(t,82,98), "(b32030dc827263e4)")
for tree,exp in (('docs/design_intelligence/dip0c','5ae44035bd03bae1'),('docs/design_intelligence/dip0a','4fe747b806ed71bd')):
    s=subprocess.run(f"find {tree} -type f | LC_ALL=C sort | xargs shasum -a 256 | shasum -a 256 | cut -c1-16",shell=True,capture_output=True,text=True).stdout.strip(); print("seal", tree, s, f"({exp})")
ok=True
for l in open(os.path.expanduser('~/bh32_work/m7_baseline.txt')):
    if l.startswith('#'): continue
    sha,size,path=l.split(None,2); ok &= hashlib.sha256(open(path.strip(),'rb').read()).hexdigest()==sha
print("M7 artefacts == baseline:", ok)
EOF
echo "=== porcelain ===" && (git status --porcelain || true) && echo "(end)"
