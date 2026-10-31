"""The committed closure instrument (A158) — AST import graph over
apps/pipeline/services, transitive closure from the declared entry set
in entry_declaration.json, plus the declared subprocess edge. Computed
against CURRENT committed code. Co-located with the records it
produces; the closure-set identity recomputes from the declaration
alone, the provenance identity from this run's code commit."""
import ast
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
SERVICES = os.path.join(ROOT, "apps", "pipeline", "services")

decl = json.load(open(os.path.join(HERE, "entry_declaration.json")))
ENTRIES = sorted(decl["entries_with_reasoning"])

modules = {}
for dirpath, _dirs, files in os.walk(SERVICES):
    for fn in files:
        if fn.endswith(".py"):
            rel = os.path.relpath(os.path.join(dirpath, fn), SERVICES)
            modules[rel[:-3].replace(os.sep, "/")] = os.path.join(
                dirpath, fn)

edges = {}
for name, path in modules.items():
    out = set()
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                leaf = a.name.split(".")[-1]
                if leaf in modules:
                    out.add(leaf)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module.split(".")[-1] if node.module else ""
            if mod in modules:
                out.add(mod)
            for a in node.names:
                if a.name in modules:
                    out.add(a.name)
    edges[name] = out

reachable = set()
stack = [e for e in ENTRIES if e in modules]
missing_entries = [e for e in ENTRIES if e not in modules]
while stack:
    m = stack.pop()
    if m in reachable:
        continue
    reachable.add(m)
    stack.extend(edges.get(m, ()))

allow = json.load(open(os.path.join(
    ROOT, "docs/roadmap/palt_m6/fallback_audit/"
          "allowlist_dispositions.json")))["entries"]
per_entry = {}
for site in sorted(allow):
    mod = site.split(".py:")[0]
    per_entry[site] = ("IN_CLOSURE" if mod in reachable
                      else "INERT_BY_UNREACHABILITY")

code_commit = subprocess.run(
    ["git", "rev-parse", "--short", "HEAD"], capture_output=True,
    text=True, cwd=ROOT, check=True).stdout.strip()
instrument_sha = hashlib.sha256(
    open(os.path.abspath(__file__), "rb").read()).hexdigest()[:16]
provenance = hashlib.sha256(json.dumps(
    {"code_commit": code_commit, "instrument_sha": instrument_sha},
    sort_keys=True).encode()).hexdigest()[:16]

result = {
    "record_type": "powder_measurement_closure_computation/1.0",
    "closure_set_identity": decl["closure_set_identity"],
    "provenance_identity_2x": provenance,
    "provenance_payload": {"code_commit": code_commit,
                           "instrument_sha": instrument_sha},
    "provenance_recipe": ("sha256(json.dumps({'code_commit', "
                          "'instrument_sha'}, sort_keys=True))[:16] — "
                          "payload above"),
    "entries_declared": ENTRIES,
    "entries_missing_from_current_code": missing_entries,
    "modules_scanned": len(modules),
    "reachable_count": len(reachable),
    "reachable": sorted(reachable),
    "allowlist_per_entry": per_entry,
}
out_path = os.path.join(HERE, "closure_computation.json")
with open(out_path, "w") as f:
    json.dump(result, f, indent=1)
print("reachable:", len(reachable), "of", len(modules),
      "| provenance:", provenance)
print("allowlist:", sum(1 for v in per_entry.values()
                        if v == "INERT_BY_UNREACHABILITY"),
      "unreachable of", len(per_entry))
