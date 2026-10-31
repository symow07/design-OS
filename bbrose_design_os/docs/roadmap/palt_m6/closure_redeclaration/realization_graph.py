"""The committed realization-closure instrument (A160) — AST
import-direction graph rooted at the declared realization roots plus
the declared subprocess edges, against CURRENT committed code, with
the declared dynamic-import stop condition. Run in a commit AFTER the
declaration's commit, never the same one."""
import ast
import hashlib
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
SERVICES = os.path.join(ROOT, "apps", "pipeline", "services")

decl = json.load(open(os.path.join(
    HERE, "realization_entry_declaration.json")))
ROOTS = decl["root_modules_for_traversal"]

modules = {}
for dirpath, _dirs, files in os.walk(SERVICES):
    for fn in files:
        if fn.endswith(".py"):
            rel = os.path.relpath(os.path.join(dirpath, fn), SERVICES)
            modules[rel[:-3].replace(os.sep, "/")] = os.path.join(
                dirpath, fn)

edges = {}
dynamic_hits = []
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
        elif isinstance(node, ast.Call):
            f = node.func
            called = getattr(f, "id", None) or getattr(f, "attr", None)
            if called in ("__import__", "import_module"):
                arg_const = (node.args and isinstance(node.args[0],
                                                     ast.Constant))
                dynamic_hits.append(
                    {"module": name, "line": node.lineno,
                     "constant_literal": bool(arg_const),
                     "target": (node.args[0].value if arg_const
                                else "NON_CONSTANT")})
    edges[name] = out

reach = set()
stack = [r for r in ROOTS if r in modules]
missing = [r for r in ROOTS if r not in modules]
while stack:
    m = stack.pop()
    if m in reach:
        continue
    reach.add(m)
    stack.extend(edges.get(m, ()))

# declared stop condition: any NON-constant dynamic import inside the
# realization closure stops the computation
in_closure_dynamic = [h for h in dynamic_hits if h["module"] in reach]
non_constant = [h for h in in_closure_dynamic
                if not h["constant_literal"]]
if non_constant:
    raise SystemExit(f"STOP: non-constant dynamic import in the "
                     f"realization closure: {non_constant}")

allow = json.load(open(os.path.join(
    ROOT, "docs/roadmap/palt_m6/fallback_audit/"
          "allowlist_dispositions.json")))["entries"]
CID = decl["closure_set_identity"]
per_entry = {}
for site in sorted(allow):
    mod = site.split(".py:")[0]
    per_entry[site] = (
        f"REACHED_IN_REALIZATION_CLOSURE[closure={CID}]"
        if mod in reach else
        f"INERT_IN_REALIZATION_CLOSURE[closure={CID}]")

code_commit = subprocess.run(
    ["git", "rev-parse", "--short", "HEAD"], capture_output=True,
    text=True, cwd=ROOT, check=True).stdout.strip()
instrument_sha = hashlib.sha256(
    open(os.path.abspath(__file__), "rb").read()).hexdigest()[:16]
provenance = hashlib.sha256(json.dumps(
    {"code_commit": code_commit, "instrument_sha": instrument_sha},
    sort_keys=True).encode()).hexdigest()[:16]

result = {
    "record_type": "palette_product_realization_closure_computation/1.0",
    "closure_set_identity": CID,
    "provenance_identity_2x": provenance,
    "provenance_payload": {"code_commit": code_commit,
                           "instrument_sha": instrument_sha},
    "provenance_recipe": ("sha256(json.dumps({'code_commit', "
                          "'instrument_sha'}, sort_keys=True))[:16]"),
    "roots_declared": ROOTS,
    "roots_missing_from_current_code": missing,
    "modules_scanned": len(modules),
    "reachable_count": len(reach),
    "reachable": sorted(reach),
    "dynamic_imports_in_closure_all_constant": in_closure_dynamic,
    "allowlist_per_entry": per_entry,
}
with open(os.path.join(HERE, "realization_computation.json"), "w") as f:
    json.dump(result, f, indent=1)
print("reachable:", len(reach), "of", len(modules),
      "| dynamic-in-closure:", len(in_closure_dynamic),
      "all constant" if not non_constant else "STOP")
print("allowlist reached:",
      sum(1 for v in per_entry.values() if v.startswith("REACHED")),
      "inert:", sum(1 for v in per_entry.values() if v.startswith("INERT")))
