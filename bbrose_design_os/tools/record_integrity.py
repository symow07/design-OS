"""A373/3q — the DIGEST_BOUND tier for findings records.

Three tiers: HASHED (law, change moves protocol_identity), DIGEST_BOUND
(records, change permitted and always leaves a recorded diff), UNBOUND
(scratch and captures, change free). Findings records had no middle
tier, so the only visible options were hashing them (wrong — they
legitimately change) or leaving them (what we had).

APPEND_ONLY records are checked by PREFIX STABILITY, which is stronger
than a digest: it detects truncation, reordering, and edits to history
while permitting growth. REVISABLE records are checked by digest.

Usage: record_integrity.py --check | --regenerate
"""
import glob
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "docs/roadmap/palt_m6/record_digest_manifest.json")
#: A402/3s — extension-matching stands as the selection proxy, but the
#: complement is CLASSIFIED, not reported. Reporting 4044 rows to a
#: reader is not a control; it depends on someone noticing. A new kind
#: appearing without a stored disposition halts the selection.
RECORD_EXTENSIONS = (".json", ".jsonl")
PATTERNS = tuple(os.path.join(ROOT, "docs/roadmap/palt_m6/**/*" + e)
                 for e in RECORD_EXTENSIONS)
PATTERN = PATTERNS[0]

#: Every kind present in the tree carries a disposition. RECORD_KIND
#: must be inside the binding pattern. .jsonl would have raised here on
#: first appearance instead of hiding in a 4044-row complement.
EXTENSION_DISPOSITIONS = {
    ".json": ("RECORD_KIND", "the programme's record format"),
    ".jsonl": ("RECORD_KIND", "line-delimited records: firing traces, "
                              "control traces, per-seed event counts"),
    ".png": ("NOT_A_RECORD", "rendered raster output, not a finding"),
    ".exr": ("NOT_A_RECORD", "linear render buffers, not a finding"),
    ".md": ("NOT_A_RECORD", "owner launchers and prose notes"),
    ".py": ("NOT_A_RECORD", "source"),
    ".pyc": ("NOT_A_RECORD", "build artefact"),
    ".txt": ("NOT_A_RECORD", "captures and scratch text"),
    ".log": ("NOT_A_RECORD", "runtime logs, unbound by design"),
    ".ai": ("NOT_A_RECORD", "Illustrator output"),
    ".pdf": ("NOT_A_RECORD", "rendered document output"),
    ".svg": ("NOT_A_RECORD", "vector output"),
    ".jpg": ("NOT_A_RECORD", "raster reference imagery"),
    ".jpeg": ("NOT_A_RECORD", "raster reference imagery"),
    ".webp": ("NOT_A_RECORD", "raster reference imagery"),
    ".eps": ("NOT_A_RECORD", "vector output"),
    ".obj": ("NOT_A_RECORD", "geometry output"),
    ".html": ("NOT_A_RECORD", "templates"),
    ".js": ("NOT_A_RECORD", "source"), ".jsx": ("NOT_A_RECORD", "source"),
    ".sh": ("NOT_A_RECORD", "source"), ".ttf": ("NOT_A_RECORD", "font asset"),
    ".eml": ("NOT_A_RECORD", "stored correspondence"),
    ".TAG": ("NOT_A_RECORD", "vendor marker file"),
    ".gz": ("NOT_A_RECORD", "compressed captures — compression is a storage "
                            "decision, not a change of kind; classified "
                            "2026-08-20 at WI-3G/§AJ2 when the kind first "
                            "appeared, per A403"),
    "(none)": ("NOT_A_RECORD", "extensionless: dotfiles, LICENSE, markers"),
}

#: A403 — the traversal root is declared and complement-checked one
#: level up. "A directory nobody thought to walk" is the same defect
#: above extension. This terminates: the repository root has no
#: complement.
RECORD_ROOTS = ("docs/roadmap",)
DIRECTORY_DISPOSITIONS = {
    "docs": ("CONTAINS_RECORD_ROOT", "docs/roadmap is a declared root"),
    "apps": ("NOT_A_RECORD_ROOT", "source"),
    "config": ("NOT_A_RECORD_ROOT", "settings"),
    "tools": ("NOT_A_RECORD_ROOT", "instruments"),
    "scripts": ("NOT_A_RECORD_ROOT", "operational scripts"),
    "static": ("NOT_A_RECORD_ROOT", "frontend assets"),
    "templates": ("NOT_A_RECORD_ROOT", "django templates"),
    "vendor": ("NOT_A_RECORD_ROOT", "third-party"),
    "media": ("NOT_A_RECORD_ROOT", "uploaded and generated media"),
    "exports": ("NOT_A_RECORD_ROOT", "generated deliverables"),
    "logs": ("NOT_A_RECORD_ROOT", "runtime logs"),
    "var": ("NOT_A_RECORD_ROOT", "reproducible build intermediates "
            "(m6_products_build OBJ/cfg scratch) — regenerable from the "
            "build phase, never records; classified 2026-08-14 when the "
            "kind first appeared, per A403"),
    ".pytest_cache": ("NOT_A_RECORD_ROOT", "tool cache"),
    ".ruff_cache": ("NOT_A_RECORD_ROOT", "tool cache"),
    ".tier2_captures": ("NOT_A_RECORD_ROOT", "retained captures, unbound by design"),
    "(root)": ("NOT_A_RECORD_ROOT", "repository root files"),
}


#: §AJ3 — extensions that WRAP a kind rather than being one. A file is
#: classified by what it wraps, because `os.path.splitext` reduces
#: `findings.json.gz` to `.gz` and dispositioning `.gz` NOT_A_RECORD
#: would let a compressed findings record disappear into the complement.
#: That is the defect this module exists to close, arriving by suffix.
COMPRESSION_WRAPPERS = {".gz": "gzip"}


def classifying_extension(path):
    """The extension a file is classified BY, which is not always the
    extension it ends with.

    `x.log.gz` -> `.log` (a capture, unbound). `x.json.gz` -> `.json` (a
    record, and therefore outside the binding pattern and refused). A
    bare `x.gz` has nothing inside and falls back to the wrapper's own
    disposition. An unknown inner extension still raises upstream, so
    wrapping cannot launder a kind past A403.
    """
    stem, ext = os.path.splitext(path)
    if ext in COMPRESSION_WRAPPERS:
        inner = os.path.splitext(stem)[1]
        if inner:
            return inner
    return ext or "(none)"


class UnclassifiedKind(RuntimeError):
    """A402/A403 — a new kind halts the selection until it is classified."""


def classify_complement(root=None):
    """The complement is classified, not reported. Raises on a kind with
    no stored disposition; refuses on a RECORD_KIND sitting outside the
    binding pattern.

    ``root`` overrides the walked directory and the binding patterns
    together, so a test can build a whole tree and watch this refuse.
    §AA: a guard nobody has seen fire is not evidence of anything, and
    before WI-3G this one could only be fired by editing the real tree.
    """
    import glob as _g
    patterns = PATTERNS if root is None else tuple(
        os.path.join(root, "**/*" + e) for e in RECORD_EXTENSIONS)
    enumerated = set()
    for pat in patterns:
        enumerated |= set(_g.glob(pat, recursive=True))
    root = os.path.join(ROOT, "docs/roadmap/palt_m6") if root is None else root
    every = set()
    for d, _, fs in os.walk(root):
        every |= {os.path.join(d, f) for f in fs}
    complement = every - enumerated
    kinds = {}
    #: the classifying kind is not always the suffix, so a reader told
    #: "a .json is outside the pattern" could hunt the tree and find no
    #: .json at all. Every kind carries an example.
    samples = {}
    for f in complement:
        k = classifying_extension(f)
        kinds[k] = kinds.get(k, 0) + 1
        samples.setdefault(k, os.path.relpath(f, root))
    refusals = []
    for ext in sorted(kinds):
        d = EXTENSION_DISPOSITIONS.get(ext)
        if d is None:
            raise UnclassifiedKind(
                f"extension {ext!r} appeared in the complement with no "
                f"stored disposition ({kinds[ext]} files, e.g. "
                f"{samples[ext]}) — classify it RECORD_KIND or "
                "NOT_A_RECORD before the selection proceeds")
        if d[0] == "RECORD_KIND":
            refusals.append(
                f"RECORD_KIND_OUTSIDE_PATTERN: {ext} ({kinds[ext]} files, "
                f"e.g. {samples[ext]})")
    return kinds, refusals


def classify_roots():
    """A403 — one level up, and it terminates here."""
    tops = {p for p in os.listdir(ROOT)
            if os.path.isdir(os.path.join(ROOT, p))
            and p not in (".git", "venv", "node_modules", "materials",
                          "__pycache__")}
    for top in sorted(tops):
        if top not in DIRECTORY_DISPOSITIONS:
            raise UnclassifiedKind(
                f"directory {top!r} is outside the declared record roots "
                f"{RECORD_ROOTS} and carries no stored disposition — "
                "classify it before the selection proceeds")
    return sorted(tops)

#: Evidence-based classification (A376). APPEND_ONLY names records whose
#: entries are dated history: adding is legitimate, editing prior bytes
#: is not. Everything else is REVISABLE — including every measurement
#: swatch, because 23 of them were rewritten by the A293 revert cycle
#: and calling them history would make the manifest fail on facts that
#: already happened.
APPEND_ONLY_NAMES = ("record_gate_ledger.jsonl",
                     "flake_register.json", "suite_manifest_diffs.json",
                     "opt_out_log.json", "defect_classes.json",
                     "method_evidence_register.json")


def digest(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]


def classify(path):
    return ("APPEND_ONLY" if os.path.basename(path) in APPEND_ONLY_NAMES
            else "REVISABLE")


def survey():
    rows = {}
    paths = set()
    for pat in PATTERNS:
        paths |= set(glob.glob(pat, recursive=True))
    for p in sorted(paths):
        rel = os.path.relpath(p, ROOT)
        if rel.endswith("record_digest_manifest.json"):
            continue
        body = open(p, "rb").read()
        rows[rel] = {"classification": classify(p), "digest": digest(p),
                     "bytes": len(body),
                     "prefix": hashlib.sha256(body[:512]).hexdigest()[:16]}
    return rows


def check(now=None):
    m = json.load(open(MANIFEST))
    if now is None:
        now = survey()
    refusals = []
    for rel, rec in m["records"].items():
        if rel not in now:
            refusals.append(f"RECORD_MISSING: {rel}")
            continue
        cur = now[rel]
        if rec["classification"] == "APPEND_ONLY":
            # prefix stability + growth: truncation, reordering and edits
            # to history all fail; appending passes.
            if cur["prefix"] != rec["prefix"]:
                refusals.append(f"HISTORY_EDITED: {rel} first 512 bytes moved")
            if cur["bytes"] < rec["bytes"]:
                refusals.append(
                    f"APPEND_ONLY_SHRANK: {rel} {rec['bytes']} -> {cur['bytes']}")
        elif cur["digest"] != rec["digest"]:
            refusals.append(
                f"RECORD_DIGEST_MISMATCH: {rel} {rec['digest']} -> "
                f"{cur['digest']} — regenerate to record the diff")
    for rel in sorted(set(now) - set(m["records"])):
        refusals.append(f"RECORD_UNDECLARED: {rel}")
    return refusals


def regenerate():
    old = (json.load(open(MANIFEST))["records"]
           if os.path.exists(MANIFEST) else {})
    now = survey()
    added = sorted(set(now) - set(old))
    removed = sorted(set(old) - set(now))
    changed = sorted(r for r in set(old) & set(now)
                     if old[r]["digest"] != now[r]["digest"])
    print(f"RECORD MANIFEST DIFF: +{len(added)} -{len(removed)} "
          f"~{len(changed)}")
    for r in added[:10]:
        print(f"    + {r}")
    for r in removed:
        print(f"    - {r}")
    for r in changed[:20]:
        print(f"    ~ {r}")
    # A352 repair 5's rule, applied here: nothing is written until every
    # candidate carries a classification.
    import importlib.util
    _s = importlib.util.spec_from_file_location(
        "sweep_manifest", os.path.join(ROOT, "tools", "sweep_manifest.py"))
    SM = importlib.util.module_from_spec(_s)
    _s.loader.exec_module(SM)
    probe = os.path.join(ROOT, ".record_regen_candidates.json")
    SM.build_manifest(
        [{"path": r, "match": k} for k, rs in
         (("added", added), ("removed", removed), ("changed", changed))
         for r in rs],
        # The classifier must accept every RECORD_EXTENSION, not just
        # .json: it was hard-coded to .json and therefore refused the
        # three .jsonl candidates and ABORTED THE WRITE, while printing
        # a diff that read as applied. A gate that refuses correctly and
        # a gate that refuses on its own stale assumption look identical
        # from the diff line.
        lambda c: ("GENUINE" if c["path"].endswith(RECORD_EXTENSIONS)
                   else None), probe)
    SM.writable(probe)
    log = json.load(open(MANIFEST)) if os.path.exists(MANIFEST) else {
        "record_type": "record_digest_manifest/1.0", "diffs": []}
    log.setdefault("diffs", []).append(
        {"added": len(added), "removed": len(removed), "changed": len(changed),
         "changed_names": changed[:50]})
    log["records"] = now
    log["counts"] = {
        "total": len(now),
        "append_only": sum(1 for v in now.values()
                           if v["classification"] == "APPEND_ONLY"),
        "revisable": sum(1 for v in now.values()
                         if v["classification"] == "REVISABLE")}
    json.dump(log, open(MANIFEST, "w"), indent=1, sort_keys=True)
    print(f"manifest digest: {digest(MANIFEST)}")
    return added, removed, changed


#: A539/A554 — THE FREE HARVEST. The verdict and the failing set are
#: already computed on every run and were thrown away on the green
#: path: a pass printed three words and recorded neither its extent nor
#: the set it passed over. That is the shape 3m closed for TIER_2 at
#: the suite level and it survived here at the record level.
#:
#: APPENDED, never overwritten. A fixed path rewritten each run is
#: class twenty-two, CAPTURE_WITHOUT_RETENTION — the current
#: observation available and the history destroyed as it is made,
#: which is the defect .tier2_gate_output already exhibits. This
#: ledger is declared APPEND_ONLY above, so its own gate checks it by
#: prefix stability and permits only growth.
#: REDIRECTABLE, AND NEVER SILENTLY. ``ROOT`` is derived from ``__file__``
#: (line 21), not from the cwd, so a subprocess launched in a scratch
#: directory still appended HERE. That is how the suite came to be the
#: majority author of a file that reads as a record of commit attempts:
#: ``test_palette_statistics.GuardedCommitTests`` runs the real
#: ``guarded_commit.sh``, which reaches line 152 and appends, on every
#: TIER_1 and every TIER_2 run. Measured at the time of this change: of
#: the 295 committed lines, roughly two in three were the test suite.
#:
#: The override moves WHERE the line is written. It does not move what is
#: CHECKED — ``survey()``/``check()`` still read the real records under
#: ``ROOT``, so a redirected run is still a real verdict about the real
#: tree, and cannot be used to make a failing tree look clean. The write
#: announces itself (see ``emit_ledger``) so that a redirect can never be
#: invisible in the output ``guarded_commit.sh`` captures.
LEDGER_ENV = "RECORD_INTEGRITY_LEDGER"
LEDGER = (os.environ.get(LEDGER_ENV)
          or os.path.join(ROOT, "docs/roadmap/palt_m6/record_gate_ledger.jsonl"))


def emit_ledger(verdict, refusals, rows):
    """One line per run. Zero marginal cost: every value below was
    already computed to decide the verdict."""
    import datetime
    line = {
        "utc": datetime.datetime.now(
            datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "verdict": verdict,
        "records_checked": len(rows),
        "append_only": sum(1 for r in rows.values()
                           if r["classification"] == "APPEND_ONLY"),
        "revisable": sum(1 for r in rows.values()
                         if r["classification"] == "REVISABLE"),
        "refusal_count": len(refusals),
        # the FAILING SET itself, entire and untruncated — a count
        # without an enumeration is not a declaration (2p), and the
        # stderr path above truncates at 20
        "failing_set": refusals,
    }
    with open(LEDGER, "a") as fh:
        fh.write(json.dumps(line, sort_keys=True) + "\n")
    # A redirect that cannot be seen in the output is a redirect that will
    # be forgotten and then relied on. Say so, on the line that did it.
    if os.environ.get(LEDGER_ENV):
        print(f"RECORD_INTEGRITY_LEDGER_REDIRECTED={LEDGER} "
              f"(via {LEDGER_ENV}; the real ledger was NOT appended to)")
    return line


def main(argv):
    if "--regenerate" in argv:
        regenerate()
        return 0
    classify_roots()
    _kinds, comp_refusals = classify_complement()
    rows = survey()
    refusals = comp_refusals + check(rows)
    verdict = "REFUSED" if refusals else "OK"
    line = emit_ledger(verdict, refusals, rows)
    if refusals:
        print("RECORD_INTEGRITY_REFUSED (A373/3q)", file=sys.stderr)
        for r in refusals[:20]:
            print(f"  {r}", file=sys.stderr)
        if len(refusals) > 20:
            print(f"  ... and {len(refusals) - 20} more", file=sys.stderr)
        print(f"RECORD_INTEGRITY=REFUSED records={line['records_checked']} "
              f"failing={line['refusal_count']} ledger={LEDGER}")
        return 1
    # the pass now carries its EXTENT, not just its verdict
    print(f"RECORD_INTEGRITY=OK records={line['records_checked']} "
          f"(append_only={line['append_only']} "
          f"revisable={line['revisable']}) failing=0")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
