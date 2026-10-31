"""Slice 1 — recursive inventory: walk, exclusions, symlink safety, hashing.

Read-only. Never follows links out of the source root, never loops, never
opens an archive. Hashing is resumable via a (relpath, size, mtime_ns) cache.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from . import config as C

HASH_CHUNK = 1 << 20  # 1 MiB


@dataclass
class WalkResult:
    files: list[dict] = field(default_factory=list)
    junk: list[dict] = field(default_factory=list)          # excluded, still counted
    symlinks: list[dict] = field(default_factory=list)      # recorded, never followed
    skipped_dirs: list[str] = field(default_factory=list)
    excluded: list[dict] = field(default_factory=list)      # §BH30(h)(2): ruled exclusions, recorded not walked
    errors: list[str] = field(default_factory=list)
    dir_count: int = 0


def _stat_key(rel: str, st: os.stat_result) -> str:
    return f"{rel}|{st.st_size}|{st.st_mtime_ns}"


def sha256_file(path: str | Path, chunk: int = HASH_CHUNK) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


class HashCache:
    """Resumable hash cache keyed on (relpath, size, mtime_ns)."""

    def __init__(self, path: Path):
        self.path = path
        self._data: dict[str, str] = {}
        if path.exists():
            try:
                self._data = json.loads(path.read_text())
            except (ValueError, OSError):
                self._data = {}
        self.hits = 0
        self.misses = 0

    def get_or_compute(self, key: str, fullpath: str) -> str:
        if key in self._data:
            self.hits += 1
            return self._data[key]
        self.misses += 1
        digest = sha256_file(fullpath)
        self._data[key] = digest
        return digest

    def save(self) -> None:
        C.assert_output_safe(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data))


def walk_corpus(roots: Sequence[Path] | None = None, *,
                cache: HashCache | None = None,
                hash_files: bool = True) -> WalkResult:
    """Walk EVERY read-only corpus root and merge into one WalkResult.

    The §BH18(c) Option B seam. `walk_source` stays exactly what it was — a
    single-root walk — and this is the additive merge point above it, so
    `SOURCE_ROOT` keeps its meaning and no existing single-root caller changes
    behaviour.

    Records carry REPO_ROOT-relative `relative_path`, so rows from the two roots
    cannot collide and the row schema needs no change to express either.
    A missing root contributes nothing rather than raising: `os.walk` on a
    non-existent directory yields no entries, which is what makes the tmp-tree
    fixtures work unchanged.
    """
    roots = list(roots) if roots is not None else list(C.corpus_roots())
    merged = WalkResult()
    for r in roots:
        part = walk_source(r, cache=cache, hash_files=hash_files)
        merged.files.extend(part.files)
        merged.junk.extend(part.junk)
        merged.symlinks.extend(part.symlinks)
        merged.skipped_dirs.extend(part.skipped_dirs)
        merged.excluded.extend(part.excluded)
        merged.errors.extend(part.errors)
        merged.dir_count += part.dir_count
    return merged


def walk_source(root: Path | None = None, *, cache: HashCache | None = None,
                hash_files: bool = True) -> WalkResult:
    """Walk `root` (default: materials/) collecting one record per real file."""
    root = Path(root or C.SOURCE_ROOT)
    res = WalkResult()
    seen_dirs: set[tuple[int, int]] = set()   # (st_dev, st_ino) loop guard
    root_real = root.resolve()

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        # loop guard: a hardlinked/bind-mounted dir revisited
        try:
            dst = os.stat(dirpath)
            key = (dst.st_dev, dst.st_ino)
            if key in seen_dirs:
                res.errors.append(f"directory loop guard tripped: {dirpath}")
                dirnames[:] = []
                continue
            seen_dirs.add(key)
        except OSError as e:
            res.errors.append(f"stat dir {dirpath}: {e}")
            dirnames[:] = []
            continue
        res.dir_count += 1

        # prune skipped dirs, and never descend a symlinked dir
        pruned = []
        for d in list(dirnames):
            full = os.path.join(dirpath, d)
            if C.is_skipped_dir(d):
                res.skipped_dirs.append(C.relpath(full))
                pruned.append(d)
            elif C.is_excluded_path(C.relpath(full)):
                # §BH30(h)(2): a ruled exclusion — recorded, never descended
                res.excluded.append({"relative_path": C.relpath(full), "kind": "dir"})
                pruned.append(d)
            elif os.path.islink(full):
                res.symlinks.append(_symlink_record(full, root_real))
                pruned.append(d)
        dirnames[:] = [d for d in dirnames if d not in pruned]

        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = C.relpath(full)

            if os.path.islink(full):
                res.symlinks.append(_symlink_record(full, root_real))
                continue
            if C.is_excluded_path(rel):
                # §BH30(h)(2): a ruled exclusion naming a FILE (e.g. the alias) — recorded, not inventoried
                res.excluded.append({"relative_path": rel, "kind": "file"})
                continue
            if C.is_junk(fn):
                try:
                    size = os.lstat(full).st_size
                except OSError:
                    size = 0
                res.junk.append({"relative_path": rel, "filename": fn, "size_bytes": size})
                continue
            try:
                st = os.stat(full)
            except OSError as e:
                res.errors.append(f"stat {rel}: {e}")
                continue
            if not os.path.isfile(full):
                continue

            ext = os.path.splitext(fn)[1].lower()
            rec = {
                "relative_path": rel,
                "filename": fn,
                "extension": ext,
                "size_bytes": st.st_size,
                "mtime_iso": _iso(st.st_mtime),
                "mtime_ns": st.st_mtime_ns,
                "sha256": None,
                "parser_support": {"status": C.parser_support(ext), "parser": None},
                "warnings": [],
            }
            if hash_files:
                try:
                    k = _stat_key(rel, st)
                    rec["sha256"] = (cache.get_or_compute(k, full) if cache
                                     else sha256_file(full))
                except OSError as e:
                    rec["warnings"].append(f"hash_failed: {e}")
                    res.errors.append(f"hash {rel}: {e}")
            res.files.append(rec)

    res.files.sort(key=lambda r: r["relative_path"])
    return res


def _symlink_record(full: str, root_real: Path) -> dict:
    try:
        target = os.readlink(full)
    except OSError:
        target = "<unreadable>"
    resolved = Path(full).resolve()
    escapes = root_real not in resolved.parents and resolved != root_real
    return {
        "relative_path": C.relpath(full),
        "target": target,
        "resolved": str(resolved),
        "escapes_source_root": bool(escapes),
        "followed": False,
    }


def _iso(ts: float) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")


# --- duplicates -------------------------------------------------------------

def group_duplicates(files: list[dict]) -> dict:
    """Exact-content duplicate groups keyed by sha256.

    DETECTION ONLY — nothing is deleted, moved or replaced. The canonical
    candidate is the shortest path (shallowest, then lexicographic): a stable,
    explainable heuristic, not a decision.
    """
    by_hash: dict[str, list[dict]] = defaultdict(list)
    for r in files:
        if r.get("sha256") and r["size_bytes"] > 0:
            by_hash[r["sha256"]].append(r)

    groups = []
    for digest, recs in by_hash.items():
        if len(recs) < 2:
            continue
        members = sorted(r["relative_path"] for r in recs)
        canonical = min(members, key=lambda p: (p.count("/"), len(p), p))
        size = recs[0]["size_bytes"]
        branches = sorted({m.split("/")[1] for m in members if "/" in m})
        groups.append({
            "sha256": digest,
            "size_bytes": size,
            "copies": len(members),
            "canonical_candidate": canonical,
            "duplicate_members": [m for m in members if m != canonical],
            "redundant_bytes": size * (len(members) - 1),
            "cross_folder": len({os.path.dirname(m) for m in members}) > 1,
            "branches": branches,
            "cross_branch": len(branches) > 1,
            "confidence": 1.0,          # exact SHA-256 content match
            "basis": "sha256_exact",
        })
    groups.sort(key=lambda g: (-g["redundant_bytes"], g["canonical_candidate"]))

    index = {}
    for i, g in enumerate(groups):
        gid = f"dup-{i:04d}"
        g["group_id"] = gid
        for m in [g["canonical_candidate"], *g["duplicate_members"]]:
            index[m] = gid
    return {
        "groups": groups,
        "index": index,
        "group_count": len(groups),
        "redundant_copies": sum(g["copies"] - 1 for g in groups),
        "redundant_bytes": sum(g["redundant_bytes"] for g in groups),
    }
