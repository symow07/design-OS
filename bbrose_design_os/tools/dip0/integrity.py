"""Original-file integrity verification (requirement 7).

Snapshot the source tree before and after the audit and prove nothing was
modified, nothing appeared, nothing vanished, and no generated output landed
under `materials/`. Hash stability is verified on a random sample (a full
re-hash is available behind `sample=None`).
"""
from __future__ import annotations

import os
import random
from collections.abc import Sequence
from pathlib import Path

from . import config as C
from .walk import sha256_file


def snapshot(root: Path | None = None) -> dict:
    """(relpath -> size|mtime_ns|inode) for every real file, junk included.

    Junk is included deliberately: an audit that deleted a Thumbs.db would
    still be a mutation of the source tree.

    WITH NO ARGUMENT THIS NOW COVERS EVERY CORPUS ROOT, not just `materials/`
    (§BH18(c)(1)). Widening the walk without widening this is the specific
    defect the ruling names: the reconciliation would go on reporting
    `unchanged: true` about `materials/` alone while saying nothing whatsoever
    about the new root — a silent false assurance produced by the very machinery
    that exists to prevent one. Passing an explicit `root` is unchanged and
    still snapshots exactly that one tree.
    """
    roots = [Path(root)] if root is not None else list(C.corpus_roots())
    out: dict[str, str] = {}
    for r in roots:
        for dirpath, dirnames, filenames in os.walk(r, followlinks=False):
            dirnames[:] = [d for d in dirnames
                           if not os.path.islink(os.path.join(dirpath, d))]
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                try:
                    st = os.lstat(full)
                except OSError:
                    continue
                out[C.relpath(full)] = f"{st.st_size}|{st.st_mtime_ns}|{st.st_ino}"
    return out


def compare(before: dict, after: dict, *,
            roots: Sequence[Path] | None = None) -> dict:
    """Diff two snapshots, and ALWAYS declare the scope the verdict covers.

    `roots_covered` exists so that `unchanged` can never be read without its
    extent (§BH18(c)(1), §AY0(d)). A verdict of "nothing changed" is only worth
    what the scope behind it is worth, and before this the scope was implicit
    and wrong the moment the corpus grew.
    """
    roots = list(roots) if roots is not None else list(C.corpus_roots())
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    modified = sorted(p for p in (set(before) & set(after)) if before[p] != after[p])
    return {
        "unchanged": not (added or removed or modified),
        "roots_covered": [C.relpath(r) for r in roots],
        "added": added,
        "removed": removed,
        "modified": modified,
        "file_count_before": len(before),
        "file_count_after": len(after),
    }


def verify_hashes(records: list[dict], sample: int | None = 50,
                  seed: int = 0) -> dict:
    """Re-hash `sample` inventory records (or all when sample is None)."""
    hashed = [r for r in records if r.get("sha256")]
    if sample is not None and len(hashed) > sample:
        rnd = random.Random(seed)
        hashed = rnd.sample(hashed, sample)
    mismatches = []
    checked = 0
    for r in hashed:
        full = C.REPO_ROOT / r["relative_path"]
        try:
            if sha256_file(full) != r["sha256"]:
                mismatches.append(r["relative_path"])
        except OSError as e:
            mismatches.append(f"{r['relative_path']}: {e}")
        checked += 1
    return {"checked": checked, "mismatches": mismatches,
            "stable": not mismatches,
            "mode": "full" if sample is None else f"sample:{sample}"}


def no_output_under_source() -> dict:
    """Prove the generated-output root is not inside ANY read-only corpus root.

    Widened with the corpus (§BH18(c)). `source_root` is kept in the payload
    under its original name and meaning for existing readers; `corpus_roots` and
    `output_inside_root` are additive, so a check that passed for `materials/`
    alone can no longer pass while blind to the second root.
    """
    out = C.OUTPUT_ROOT.resolve()
    roots = [r.resolve() for r in C.corpus_roots()]
    inside_of = [str(r) for r in roots if out == r or r in out.parents]
    inside = bool(inside_of)
    stray = []
    if C.OUTPUT_ROOT.exists() and inside:
        stray = [str(C.OUTPUT_ROOT)]
    return {"output_root": str(out),
            "source_root": str(C.SOURCE_ROOT.resolve()),
            "corpus_roots": [str(r) for r in roots],
            "output_inside_root": inside_of,
            "output_inside_source": inside, "stray": stray, "ok": not inside}
