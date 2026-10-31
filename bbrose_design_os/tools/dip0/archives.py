"""Slice 2 — ZIP inventory: manifest only, never extraction.

Reads the central directory (cheap even for the 3.5 GB archives), records the
internal manifest, estimates expanded size, and flags encrypted / corrupt /
nested / traversal / bomb-suspicious archives. Contents are NOT recursed into;
extraction is deferred to a separate reviewed milestone.
"""
from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from . import config as C

NESTED_EXT = (".zip", ".rar", ".7z", ".tar", ".gz", ".tgz")
BOMB_RATIO = 100.0
BOMB_MIN_EXPANDED = 1 << 30    # 1 GiB


def _is_traversal(name: str) -> bool:
    if name.startswith("/") or (len(name) > 1 and name[1] == ":"):
        return True
    return any(part == ".." for part in name.replace("\\", "/").split("/"))


def manifest_digest(entries: list[dict]) -> str:
    """Content-manifest fingerprint: identifies archives with identical payload
    listings even when the container bytes differ (recompression, timestamps)."""
    blob = "\n".join(f"{e['name']}|{e['uncompressed_size']}"
                     for e in sorted(entries, key=lambda e: e["name"]))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def inspect_zip(path: Path) -> dict:
    """Manifest-level inspection. Never extracts, never decompresses payloads."""
    info: dict = {
        "readable": False, "encrypted": False, "corrupt": False, "empty": False,
        "entry_count": 0, "expanded_bytes": 0, "compressed_bytes": 0,
        "expansion_ratio": 0.0, "nested_archives": [], "traversal_entries": [],
        "suspicious": [], "entries": [], "manifest_sha256": None,
        "comment": "", "error": None,
    }
    try:
        if path.stat().st_size == 0:
            # A 0-byte .zip is a failed/aborted download, not a malformed archive.
            info["empty"] = True
            info["error"] = "empty file (0 bytes) — probable failed download"
            return info
    except OSError as e:
        info["error"] = f"{type(e).__name__}: {e}"
        return info
    try:
        with zipfile.ZipFile(path) as z:          # central directory only
            info["readable"] = True
            info["comment"] = (z.comment or b"").decode("utf-8", "replace")[:200]
            for zi in z.infolist():
                if zi.is_dir():
                    continue
                enc = bool(zi.flag_bits & 0x1)
                if enc:
                    info["encrypted"] = True
                e = {
                    "name": zi.filename,
                    "uncompressed_size": zi.file_size,
                    "compressed_size": zi.compress_size,
                    "encrypted": enc,
                }
                info["entries"].append(e)
                info["expanded_bytes"] += zi.file_size
                info["compressed_bytes"] += zi.compress_size
                if zi.filename.lower().endswith(NESTED_EXT):
                    info["nested_archives"].append(zi.filename)
                if _is_traversal(zi.filename):
                    info["traversal_entries"].append(zi.filename)
    except zipfile.BadZipFile as e:
        info["corrupt"] = True
        info["error"] = f"BadZipFile: {e}"
        return info
    except (OSError, zipfile.LargeZipFile, RuntimeError) as e:
        info["error"] = f"{type(e).__name__}: {e}"
        return info

    info["entry_count"] = len(info["entries"])
    if info["compressed_bytes"] > 0:
        info["expansion_ratio"] = round(
            info["expanded_bytes"] / info["compressed_bytes"], 2)
    info["manifest_sha256"] = manifest_digest(info["entries"])

    if info["encrypted"]:
        info["suspicious"].append("encrypted_entries")
    if info["traversal_entries"]:
        info["suspicious"].append("path_traversal_entries")
    if info["nested_archives"]:
        info["suspicious"].append("nested_archives")
    if (info["expansion_ratio"] >= BOMB_RATIO
            and info["expanded_bytes"] >= BOMB_MIN_EXPANDED):
        info["suspicious"].append("high_expansion_ratio")
    return info


def build_archive_report(records: list[dict], root: Path | None = None) -> dict:
    """Inspect every archive record; group likely-duplicate archives by BOTH
    container hash and content-manifest fingerprint."""
    root = Path(root or C.REPO_ROOT)
    archives = [r for r in records
                if r["parser_support"]["status"] == "archive"]

    by_manifest: dict[str, list[str]] = {}
    by_content_hash: dict[str, list[str]] = {}
    out = []
    for r in archives:
        z = inspect_zip(root / r["relative_path"])
        entry = {
            "relative_path": r["relative_path"],
            "size_bytes": r["size_bytes"],
            "sha256": r["sha256"],
            "mtime_iso": r["mtime_iso"],
            **{k: v for k, v in z.items() if k != "entries"},
            "entry_sample": [e["name"] for e in z["entries"][:20]],
        }
        out.append(entry)
        if z["manifest_sha256"]:
            by_manifest.setdefault(z["manifest_sha256"], []).append(r["relative_path"])
        # Empty files all share the SHA-256 of nothing; grouping them as "exact
        # duplicates" would be technically true and practically meaningless.
        if r["sha256"] and r["size_bytes"] > 0:
            by_content_hash.setdefault(r["sha256"], []).append(r["relative_path"])

        r["archive"] = {k: entry[k] for k in
                        ("readable", "encrypted", "corrupt", "empty",
                         "entry_count", "expanded_bytes", "expansion_ratio",
                         "suspicious", "manifest_sha256")}
        for s in z["suspicious"]:
            r["warnings"].append(f"archive_{s}")
        if z["corrupt"]:
            r["warnings"].append("archive_corrupt")
        if z["empty"]:
            r["warnings"].append("archive_empty_failed_download")

    # identical bytes → certain duplicate; identical manifest only → probable
    exact = {h: ps for h, ps in by_content_hash.items() if len(ps) > 1}
    probable = {m: ps for m, ps in by_manifest.items()
                if len(ps) > 1 and not any(set(ps) <= set(e) for e in exact.values())}

    out.sort(key=lambda e: -e["size_bytes"])
    return {
        "archive_count": len(out),
        "total_archive_bytes": sum(e["size_bytes"] for e in out),
        "total_expanded_bytes": sum(e["expanded_bytes"] for e in out),
        "encrypted": [e["relative_path"] for e in out if e["encrypted"]],
        "corrupt": [e["relative_path"] for e in out if e["corrupt"]],
        "empty_failed_downloads": [e["relative_path"] for e in out if e["empty"]],
        "with_nested_archives": [e["relative_path"] for e in out
                                 if e["nested_archives"]],
        "suspicious": [{"relative_path": e["relative_path"],
                        "reasons": e["suspicious"]} for e in out if e["suspicious"]],
        "exact_duplicate_archives": exact,
        "probable_duplicate_archives_by_manifest": probable,
        "archives": out,
        "extraction_policy": "DIP-0A inventories manifests only; no archive was "
                             "opened for extraction or recursed into.",
    }
