"""DIP-0A configuration: roots, exclusions, extension policy, taxonomy.

`materials/` is READ-ONLY source material. Nothing in this package may write,
rename, move or modify anything beneath SOURCE_ROOT — `assert_output_safe()`
enforces that outputs land outside it.

Since §BH18(c) the corpus is TWO roots, not one. `SOURCE_ROOT` keeps its
original meaning — the 28GB read-only library — and a second, additive root
reaches the container font faces. Both are read-only and both are refused by
`assert_output_safe()`. See `corpus_roots()`, and note in particular that it is
a function rather than a module-level tuple.
"""
from __future__ import annotations

import fnmatch
import os
from pathlib import Path

TOOL_NAME = "dip0"
TOOL_VERSION = "0.1.0"

REPO_ROOT = Path(__file__).resolve().parents[3]
APP_ROOT = Path(__file__).resolve().parents[2]  # bbrose_design_os/, where apps/ imports from  # the git root; dip0 sits in bbrose_design_os/tools/ since 2026-10-04
SOURCE_ROOT = REPO_ROOT / "materials"
OUTPUT_ROOT = REPO_ROOT / "var" / "design_intelligence" / "audits" / "dip0"

#: The additive second corpus root (§BH18(c), Option B). These are LIVE TRACKED
#: APPLICATION ASSETS, not read-only source material like SOURCE_ROOT — which is
#: precisely why they must be guarded rather than merely walked: nothing in this
#: package may write to them either.
CONTAINER_FONT_DIR = "bbrose_design_os/static/fonts"

OUT_INVENTORY = OUTPUT_ROOT / "inventory"
OUT_PREVIEWS = OUTPUT_ROOT / "previews"
OUT_REPORTS = OUTPUT_ROOT / "reports"
OUT_MANIFESTS = OUTPUT_ROOT / "manifests"
OUT_TEMP = OUTPUT_ROOT / "temporary"

# --- exclusions -------------------------------------------------------------
# OS / editor / recovery junk. Excluded from the inventory but COUNTED, so the
# reconciliation can prove nothing vanished silently.
JUNK_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini", "Icon\r"}
JUNK_GLOBS = (
    "~$*",           # Office lock files
    "~*.tmp",
    "*.tmp",
    "*.temp",
    "*.swp",
    "*.swo",
    "*.crdownload",
    "*.part",
    "AI Recovery*",  # Illustrator recovery
    "~AI*",
)
# Directories never descended into (recorded as skipped).
SKIP_DIR_NAMES = {"__MACOSX", ".git", ".svn", "node_modules", "__pycache__"}


def is_junk(name: str) -> bool:
    if name in JUNK_NAMES:
        return True
    return any(fnmatch.fnmatch(name, g) for g in JUNK_GLOBS)


def is_skipped_dir(name: str) -> bool:
    # hidden/cache directories are skipped wholesale
    return name in SKIP_DIR_NAMES or name.startswith(".")


#: §BH30(h)(2) — THE RULED EXCLUSION LIST. Entries the corpus walk skips,
#: each a repository-relative path exactly as typed on disk: no glob, no
#: inference, no prefix logic beyond "this path". A directory entry is not
#: descended into; a file entry is not inventoried. ADDITIVE to
#: SKIP_DIR_NAMES / is_junk. Reversible only by ruling: admitting an entry
#: into the governed corpus is ONE DELETED LINE here, under its own census
#: and admission ruling (§BH30(h): "each enters DIP-0A through its own
#: census and admission ruling"). The runner snapshot prints this set with
#: its on-disk byte sizes, so every regen states aloud what it does not
#: govern. Why these two (2026-09-05): the §BH27 library and its alias
#: are outside the governed corpus until ruled (§BH27/28). The three
#: folders dropped on 2026-09-03 (17-10-2024, ALL..MOCKUP, ADOBE STOCK)
#: sat here from §BH30(h) — the §BH30(e) regen had swept them in (+8,984
#: inventory rows against a declared +51) — until they entered through
#: their own census (§BH35) and admission rulings (§BH36/§BH37): three
#: deleted lines at §BH37(2), the 13 quarantined executables gone from
#: disk first (§BH36(d)), every admitted file tiered REFERENCE by machine.
EXCLUDED_PATHS = (
    "materials/Fonts/FONTS 2026",   # §BH27/28: the dropped library, outside until ruled
    "materials/FONTS 2026",         # the macOS alias file left by the drop; not material
)


def is_excluded_path(rel: str) -> bool:
    """True when the repository-relative path is EXACTLY one of EXCLUDED_PATHS
    (or lies beneath a directory entry). Compared as typed; no globbing."""
    rel = rel.replace(os.sep, "/").strip("/")
    for entry in EXCLUDED_PATHS:
        if rel == entry or rel.startswith(entry + "/"):
            return True
    return False


def excluded_entries_on_disk(repo_root=None) -> list:
    """For the runner's snapshot: each EXCLUDED_PATHS entry with its kind and
    on-disk byte size (files counted recursively for a directory), or
    'absent'. Read-only."""
    root = Path(repo_root) if repo_root else REPO_ROOT
    out = []
    for entry in EXCLUDED_PATHS:
        p = root / entry
        if p.is_dir():
            n = b = 0
            for dp, dn, fns in os.walk(p, followlinks=False):
                for fn in fns:
                    try:
                        b += (Path(dp) / fn).stat().st_size; n += 1
                    except OSError:
                        pass
            out.append({"entry": entry, "kind": "dir", "files": n, "bytes": b})
        elif p.is_file():
            out.append({"entry": entry, "kind": "file", "files": 1, "bytes": p.stat().st_size})
        else:
            out.append({"entry": entry, "kind": "absent", "files": 0, "bytes": 0})
    return out


# --- parser support policy --------------------------------------------------
# supported  : a deep parser exists (or will) for DIP-0B/0C
# partial    : inspectable to a limited degree
# archive    : inventoried + manifest only, never extracted in DIP-0A
# evidence   : license/readme material, attached to nearby assets
# unsupported: inventoried and reported, no parser
SUPPORTED_EXT = {
    ".ai", ".eps", ".pdf", ".svg",
    ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff",
    ".otf", ".ttf", ".woff", ".woff2",
}
PARTIAL_EXT = {".psd", ".ttc", ".avif", ".gif", ".ase"}
ARCHIVE_EXT = {".zip"}
EVIDENCE_EXT = {".txt", ".html", ".htm", ".url", ".md"}
UNSUPPORTED_EXT = {".fon", ".mp4", ".mov", ".xlsx", ".xls", ".xml", ".db"}

FONT_EXT = {".otf", ".ttf", ".ttc", ".woff", ".woff2", ".fon"}
VECTOR_EXT = {".ai", ".eps", ".svg", ".pdf"}
RASTER_EXT = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".avif", ".gif", ".psd"}
# Colour systems: Adobe Swatch Exchange + siblings. Parsed in DIP-0C at the
# earliest; a palette file is never auto-used before a human approves it.
PALETTE_EXT = {".ase", ".aco", ".acb", ".clr"}
# Management/provenance sidecars — inventoried and traceable, never assets.
METADATA_EXT = {".xml", ".plist"}


def parser_support(ext: str) -> str:
    if ext in ARCHIVE_EXT:
        return "archive"
    if ext in EVIDENCE_EXT:
        return "evidence"
    if ext in SUPPORTED_EXT:
        return "supported"
    if ext in PARTIAL_EXT:
        return "partial"
    if ext in UNSUPPORTED_EXT:
        return "unsupported"
    return "unsupported"


# --- taxonomy ---------------------------------------------------------------
# User-approved set (2026-07-10). OUT_OF_SCOPE = "we know what it is and
# deliberately exclude it". UNKNOWN = "the system cannot yet classify it" —
# kept strictly separate, and reserved for genuinely unidentified files.
CATEGORIES = (
    "HISTORICAL_DESIGN",
    "REUSABLE_VECTOR_ASSET",
    "RASTER_DESIGN_ASSET",
    "BACKGROUND",
    "PATTERN",
    "MOTIF",
    "ICON",
    "BRAND_MASTER",
    "LOGO",
    "FONT",
    "COLOR_PALETTE",
    "PHOTOGRAPHY_REFERENCE",
    "PRODUCT_REFERENCE",
    "DIELINE_REFERENCE",
    "ARCHIVE",              # transport/storage container, not a knowledge class
    "LICENSE_EVIDENCE",     # supporting evidence, not a knowledge class
    "SUPPORTING_METADATA",  # provenance/management sidecar, not a knowledge class
    "OUT_OF_SCOPE",
    "UNKNOWN",
)

# Categories that are inventoried and traceable but are NOT Design Intelligence
# knowledge classes: excluded from retrieval and generation by rule, permanently.
NON_KNOWLEDGE_CATEGORIES = frozenset({
    "ARCHIVE", "LICENSE_EVIDENCE", "SUPPORTING_METADATA", "OUT_OF_SCOPE",
    "UNKNOWN",
})

# Knowledge classes whose retrieval is gated on a later ingestion contract.
RETRIEVAL_GATED_CATEGORIES = frozenset({"COLOR_PALETTE", "FONT"})

_NON_KNOWLEDGE_REASON = {
    "ARCHIVE": ("transport/storage container; its existence proves nothing about "
                "the licence or approval of its contents; extraction deferred to "
                "a controlled milestone"),
    "LICENSE_EVIDENCE": ("supporting evidence linked to nearby assets; never a "
                         "reusable design asset and never auto-changes licence "
                         "status"),
    "SUPPORTING_METADATA": ("provenance / font-management evidence; never enters "
                            "design retrieval, never a reusable asset"),
    "OUT_OF_SCOPE": "understood and deliberately excluded from Design Intelligence",
    "UNKNOWN": "unidentified; cannot be trusted for retrieval",
}
_GATED_REASON = {
    "COLOR_PALETTE": ("retrieval blocked until DIP-0C/DIP-1 establishes the "
                      "palette ingestion contract; auto-use blocked until parsed "
                      "and human-approved"),
    "FONT": ("licence UNVERIFIED; no font is installed, embedded, redistributed "
             "or auto-used before human approval"),
}


def retrieval_posture(category: str) -> dict:
    """Whether a category may ever feed retrieval/generation, and why not yet.

    Nothing in DIP-0A is retrieval-enabled: the retrieval contract does not exist
    until DIP-1. This records WHY — by rule (permanent) or by gate (pending).
    """
    non_knowledge = category in NON_KNOWLEDGE_CATEGORIES
    if non_knowledge:
        reason = _NON_KNOWLEDGE_REASON[category]
    elif category in RETRIEVAL_GATED_CATEGORIES:
        reason = _GATED_REASON[category]
    else:
        reason = ("design knowledge class; retrieval contract not established "
                  "until DIP-1")
    return {
        "knowledge_class": not non_knowledge,
        "excluded_from_retrieval_by_rule": non_knowledge,
        "retrieval_allowed": False,
        "automatic_use_allowed": False,
        "reason": reason,
    }

# Branches with special standing.
HISTORICAL_DIR = "materials/historical AI production designs"
FONTS_DIR = "materials/Fonts"
FONT_QUARANTINE_DIR = "materials/Fonts/3333"


def corpus_roots() -> tuple[Path, ...]:
    """Every read-only corpus root, in walk order, resolved AT CALL TIME.

    A FUNCTION and not a module-level tuple, deliberately. `SOURCE_ROOT` and
    `REPO_ROOT` are monkeypatched by the test fixtures; a tuple frozen at import
    would keep pointing at the real 28GB library while every other root moved to
    the tmp tree, so the tests would silently walk the live corpus. The same
    hazard applies to any caller that rebinds a root at runtime.

    Order matters only for reporting; the walk merges the roots.
    """
    return (SOURCE_ROOT, REPO_ROOT / CONTAINER_FONT_DIR)


def assert_output_safe(path: Path) -> None:
    """Refuse to write anywhere under ANY read-only corpus root.

    Widened by §BH18(c)(2). Before that this refused only `SOURCE_ROOT`, so the
    container font faces — live tracked application assets — would have been
    walked by the audit while carrying no write protection at all. The guard is
    widened rather than duplicated: a second guard beside this one would leave
    32 existing call sites pointed at the narrower of the two.
    """
    p = Path(path).resolve()
    for root in corpus_roots():
        r = root.resolve()
        if p == r or r in p.parents:
            raise RuntimeError(
                f"refusing to write inside read-only corpus root {r}: {p}")


def ensure_output_dirs() -> None:
    for d in (OUT_INVENTORY, OUT_PREVIEWS, OUT_REPORTS, OUT_MANIFESTS, OUT_TEMP):
        assert_output_safe(d)
        d.mkdir(parents=True, exist_ok=True)


def physical_path(rel: str, root: Path | None = None) -> Path:
    """Where a recorded materials/ path's bytes live now.

    The recorded relative path stays the record's identity. Since the Day 6 library
    migration (manifest docs/audit/day-6/library/manifest-2026-10-19.jsonl) a file
    may sit at its new path; the application seam resolves it and refuses a digest
    that disagrees. Outside the manifest the literal path is returned unchanged."""
    base = Path(root or REPO_ROOT)
    literal = base / rel
    if literal.exists() or not str(rel).startswith("materials/"):
        return literal
    import sys
    if str(APP_ROOT) not in sys.path:
        sys.path.insert(0, str(APP_ROOT))
    from apps.ire.materials_paths import resolve_material_file
    return resolve_material_file(rel, repo_root=base)


def relpath(path: os.PathLike | str, root: Path | None = None) -> str:
    """Project-relative path, always `materials/...` with forward slashes."""
    root = root or REPO_ROOT
    return os.path.relpath(str(path), str(root)).replace(os.sep, "/")
