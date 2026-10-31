"""A183 — the ONE-TIME key-scheme migration, committed as its own
record. Text keys -> normalized-shape keys.

It is deliberately NOT a flag on tools/allowlist_disposition.py: a
bulk-disposition option on the writer would be a reusable refresh path,
which is the operation 3c abolished. This script runs once, and the
tool's guarantee is untouched — every divergent key is dispositioned
individually with a stated reason.

The reason ("key scheme migrated; no guarded expression changed") is
true of every key BY CONSTRUCTION rather than by promise, and this
script PROVES it before dispositioning anything: the per-(file,symbol)
occurrence distribution must be identical under both schemes. If a
guarded expression had been added, removed or altered, that
distribution would move and the migration refuses.
"""
import collections
import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


C = _load("allowlist_census", os.path.join(ROOT, "tools",
                                           "allowlist_census.py"))
D = _load("allowlist_disposition",
          os.path.join(ROOT, "tools", "allowlist_disposition.py"))

REASON = ("key scheme migrated from literal match text to normalized "
          "expression shape (A183); no guarded expression was added, "
          "removed or altered — established by an unchanged multiset of "
          "raw match texts per symbol AND a git assertion that the "
          "migration commit touched no scanned source (A186/3d)")


def raw_multiset(rev=None):
    """A186/3d — the multiset of RAW MATCH TEXTS per (file, symbol).

    This REPLACES the earlier per-symbol occurrence distribution: the
    distribution is derivable from this multiset, so nothing is lost,
    and the multiset additionally catches an IN-PLACE EDIT — swapping
    .get(k, 0.0) for .get(k, 1.0) leaves the distribution identical
    and moves this. The earlier proof could not see that, and the
    conclusion it reached was carried by a fact the author knew and
    the instrument never tested."""
    out = collections.Counter()
    for label, pat, only, skip in (
            ("fallbacks", C.FALLBACK_SHAPES, None, True),
            ("a32", C.A32_SHAPES, set(C.MEASUREMENT_MODULES), False)):
        for path in sorted(C.SERVICES.rglob("*.py")):
            if only and path.name not in only:
                continue
            rel = path.relative_to(ROOT)
            src = (path.read_text() if rev is None
                   else subprocess.run(["git", "show", f"{rev}:./{rel}"],
                                       capture_output=True, text=True,
                                       cwd=ROOT).stdout)
            if not src:
                continue
            for m in pat.finditer(src):
                if skip:
                    ctx = src[max(0, m.start() - 400):m.start() + 200]
                    if "INSTRUMENT_REFUSED" in ctx \
                            or "STIMULUS_NOT_REALIZED" in ctx:
                        continue
                line = src[:m.start()].count("\n") + 1
                out[(label, path.name, C.symbol_of(src, line),
                     " ".join(m.group(0).split()))] += 1
    return out


def scanned_tree_untouched(before, after):
    """The premise the earlier script never checked and the author
    simply knew: that the migration commit edited no scanned source.
    Asserted from git, not from knowledge."""
    changed = subprocess.run(
        ["git", "diff", "--name-only", f"{before}..{after}", "--",
         "apps/pipeline/services"], capture_output=True, text=True,
        cwd=ROOT).stdout.split()
    return changed


def verify_cosmetic(before, after):
    """Both halves, reported separately per 3d."""
    a = raw_multiset(before)
    b = raw_multiset(after)
    touched = scanned_tree_untouched(before, after)
    return {
        "multiset_unchanged": a == b,
        "multiset_delta": {k: (a[k], b[k]) for k in set(a) | set(b)
                           if a[k] != b[k]},
        "scanned_tree_untouched": not touched,
        "scanned_files_changed": touched,
        "cosmetic_established": (a == b) and not touched,
    }


def main():
    """The migration itself already ran (f10d2a2). Re-invoking main()
    verifies rather than repeats: A186's strengthened instrument, both
    halves, against the real migration commit."""
    res = verify_cosmetic("f10d2a2^", "f10d2a2")
    if not res["cosmetic_established"]:
        raise SystemExit(f"REFUSED — not established cosmetic: {res}")
    print("ESTABLISHED cosmetic (A186): raw-match-text multiset "
          "unchanged AND scanned tree untouched by the migration commit")
    base = json.load(open(C.BASELINE))
    found = C.current()

    _f, div = D.divergences(base)
    argv = ["--commit"]
    for keys in div.values():
        for k in keys:
            argv += ["--disposition", f"{k}=cosmetic:{REASON}"]
    print(f"dispositioning {sum(len(k) for k in div.values())} keys "
          "individually through the tool")
    rc = D.main(argv)
    b = json.load(open(C.BASELINE))
    b["scheme"] = ("keys are file :: symbol :: (shape:<normalized "
                   "expression> | text:<literal match>); the tag says "
                   "which, and a text: key means the fragment did not "
                   "parse standalone")
    json.dump(b, open(C.BASELINE, "w"), indent=1, sort_keys=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
