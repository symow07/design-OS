"""Family grouping and duplicate relationships (DIP-0C4a).

**The family name is a grouping HYPOTHESIS, not identity proof.** Two faces that both
say "Regular" are not related; two files both called `Sans` prove nothing. So a group
is never formed on a matching name alone — it is formed on a name *plus* corroborating
evidence, and it records what agrees and what does not.

Where the evidence **conflicts** — the same family name under materially different
vendors, packages, or incompatible glyph coverage — the group is flagged
`FAMILY_RELATIONSHIP_REVIEW_REQUIRED` and split by vendor, rather than quietly merged.
Merging two unrelated foundries' "Script" into one reviewable family would hand a human
a decision built on a coincidence.

**Grouping key** (the business's D2): typographic family (**name ID 16**) when present,
else legacy family (**name ID 1**). ID 16 is designed to hold weights, widths and
optical sizes inside one family; ID 1 fragments them. Real example from the corpus:
`SinkinSans-400Regular.otf` has ID 16 = `Sinkin Sans` but ID 1 = `Sinkin Sans 400
Regular` — under ID 1 every weight becomes its own "family", and an 18-file package
explodes into 18 batches of one.

**Dedup runs BEFORE parsing.** ~941 SHA-256 groups cover 1,883 of the 4,883 files
(`materials/Fonts` is 92% byte-identical to `materials/Fonts/3333`). Parse the unique
set once; attach the result to every member. It is both the speed lever and the thing
that makes the duplicated dump collapse.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import defaultdict

from . import config as C

PARSER = f"{C.TOOL_NAME}.fontfamily/{C.TOOL_VERSION}"
SCHEMA_VERSION = "fontfamily/1.0"

# --- group states --------------------------------------------------------------
FAMILY_GROUPED = "FAMILY_GROUPED"
FAMILY_RELATIONSHIP_REVIEW_REQUIRED = "FAMILY_RELATIONSHIP_REVIEW_REQUIRED"
FAMILY_NAME_TOO_GENERIC = "FAMILY_NAME_TOO_GENERIC"
FAMILY_UNNAMED = "FAMILY_UNNAMED"
GROUP_STATES = (FAMILY_GROUPED, FAMILY_RELATIONSHIP_REVIEW_REQUIRED,
                FAMILY_NAME_TOO_GENERIC, FAMILY_UNNAMED)

# Names that describe a STYLE, not a family. They must never merge unrelated fonts.
GENERIC_NAMES = {
    "regular", "roman", "normal", "book", "plain", "medium",
    "sans", "serif", "sans serif", "sansserif", "script", "display",
    "italic", "oblique", "bold", "light", "thin", "black", "heavy",
    "condensed", "expanded", "text", "font", "untitled", "new",
}

# Evidence codes — what agrees, and what does not.
EV_SAME_ID16 = "SAME_TYPOGRAPHIC_FAMILY_ID16"
EV_SAME_ID1 = "SAME_LEGACY_FAMILY_ID1"
EV_SAME_VENDOR = "SAME_VENDOR"
EV_SAME_PACKAGE = "SAME_SOURCE_PACKAGE"
EV_SAME_PS_PREFIX = "SAME_POSTSCRIPT_PREFIX"
EV_COMPATIBLE_COVERAGE = "COMPATIBLE_GLYPH_COVERAGE"
EV_EXACT_DUPLICATE = "EXACT_DUPLICATE_MEMBERS"
EV_WEIGHT_LADDER = "COHERENT_WEIGHT_LADDER"
EV_VARIABLE_AXES = "SHARED_VARIABLE_AXES"

CONFLICT_VENDOR = "CONFLICTING_VENDORS"
CONFLICT_PACKAGE = "MULTIPLE_SOURCE_PACKAGES"
CONFLICT_COVERAGE = "INCOMPATIBLE_GLYPH_COVERAGE"
CONFLICT_PS_PREFIX = "CONFLICTING_POSTSCRIPT_PREFIXES"
CONFLICT_VERSION = "DIVERGENT_VERSIONS"
CONFLICT_GENERIC = "GENERIC_FAMILY_NAME"


def normalize(name: str | None) -> str | None:
    """Fold case, width and punctuation — but never fold two different names into one."""
    if not name:
        return None
    s = unicodedata.normalize("NFKC", str(name)).strip().lower()
    s = re.sub(r"[\s_\-\.]+", " ", s)
    s = re.sub(r"[^\w ]+", "", s)
    return re.sub(r"\s+", " ", s).strip() or None


def is_generic(normalized: str | None) -> bool:
    return bool(normalized) and normalized in GENERIC_NAMES


def family_key(face: dict) -> tuple[str | None, str]:
    """(normalized key, which name ID it came from). ID 16 preferred, else ID 1."""
    n = face["names"]
    id16 = normalize(n.get("family_typographic"))
    if id16:
        return id16, "name_id_16"
    id1 = normalize(n.get("family_legacy"))
    if id1:
        return id1, "name_id_1"
    return None, "none"


def ps_prefix(face: dict) -> str | None:
    ps = face["names"].get("postscript_name")
    if not ps:
        return None
    return normalize(ps.split("-")[0])


def package_of(path: str) -> str:
    """The source package — the directory a file came in. Meaningful for the
    `DOWNLOADE 2026/*` download packages; nearly meaningless for the two big dumps,
    which is a finding, not a bug."""
    # Day 6 migration: a font now lives under materials/fonts/<family>/, but the package it CAME IN is its
    # original folder, which the migration manifest keeps as the file's identity (D-D6-4: rights provenance).
    from tools.dip0.config import APP_ROOT
    import sys
    if str(APP_ROOT) not in sys.path:
        sys.path.insert(0, str(APP_ROOT))
    from apps.ire.materials_paths import migration_row
    row = migration_row(path)
    origin = row["old_path"] if row else path
    return str(C.Path(origin).parent)


def _coverage_compatible(a: dict, b: dict) -> bool:
    """Do two faces plausibly serve the same family? A CJK Ext-B face and a
    Latin-only face do not, whatever their name tables say."""
    da, db = a.get("dominant_script"), b.get("dominant_script")
    if da and db and da != db:
        # latin/numerals overlap is normal; a genuinely different script is not
        if {da, db} - {"latin", "numerals"}:
            return False
    ba = set(a.get("unicode_blocks") or [])
    bb = set(b.get("unicode_blocks") or [])
    if not ba or not bb:
        return True
    overlap = len(ba & bb) / max(1, min(len(ba), len(bb)))
    return overlap >= 0.30


def dedupe(files: list[dict]) -> dict:
    """Group files by SHA-256 BEFORE anything is parsed."""
    by_hash: dict[str, list[dict]] = defaultdict(list)
    for f in files:
        by_hash[f["sha256"]].append(f)
    groups = {h: sorted(v, key=lambda r: r["relative_path"])
              for h, v in by_hash.items()}
    dup_groups = {h: v for h, v in groups.items() if len(v) > 1}
    return {
        "unique_hashes": sorted(groups),
        "by_hash": groups,
        "duplicate_groups": dup_groups,
        "files_total": len(files),
        "files_unique": len(groups),
        "files_in_duplicate_groups": sum(len(v) for v in dup_groups.values()),
        "duplicate_group_count": len(dup_groups),
    }


def build_groups(faces: list[dict], *, by_hash: dict) -> list[dict]:
    """Group faces into review families. Evidence in, conflicts recorded, never merged
    on a name alone."""
    buckets: dict[str, list[dict]] = defaultdict(list)
    unnamed: list[dict] = []

    for f in faces:
        key, source = family_key(f)
        f["_family_key"] = key
        f["_family_key_source"] = source
        if not key:
            unnamed.append(f)
        else:
            buckets[key].append(f)

    groups: list[dict] = []
    for key in sorted(buckets):
        members = buckets[key]
        generic = is_generic(key)

        # A generic name is NOT a family. Split it by vendor + package so nothing
        # unrelated is merged, and say why.
        if generic:
            sub: dict[tuple, list[dict]] = defaultdict(list)
            for m in members:
                sub[(m.get("vendor_id") or "?",
                     package_of(m["source_path"]))].append(m)
            for (vendor, pkg), ms in sorted(sub.items()):
                groups.append(_group(key, ms, by_hash=by_hash,
                                     state=FAMILY_NAME_TOO_GENERIC,
                                     extra_conflicts=[CONFLICT_GENERIC],
                                     split_by=f"vendor={vendor} package={pkg}"))
            continue

        vendors = {m.get("vendor_id") or "?" for m in members}
        if len(vendors) > 1:
            # the same family name under different vendors: SPLIT, do not merge
            sub = defaultdict(list)
            for m in members:
                sub[m.get("vendor_id") or "?"].append(m)
            for vendor, ms in sorted(sub.items()):
                groups.append(_group(
                    key, ms, by_hash=by_hash,
                    state=FAMILY_RELATIONSHIP_REVIEW_REQUIRED,
                    extra_conflicts=[CONFLICT_VENDOR],
                    split_by=f"vendor={vendor}",
                    note=f"family {key!r} appears under {sorted(vendors)} — the same "
                         "name under different vendors is a coincidence until a human "
                         "says otherwise"))
            continue

        groups.append(_group(key, members, by_hash=by_hash))

    for f in unnamed:
        groups.append(_group(None, [f], by_hash=by_hash, state=FAMILY_UNNAMED))

    return sorted(groups, key=lambda g: (g["family_key"] or "~", g["group_id"]))


def _group(key, members, *, by_hash: dict, state: str = FAMILY_GROUPED,
           extra_conflicts=(), split_by: str | None = None,
           note: str | None = None) -> dict:
    vendors = sorted({m.get("vendor_id") or "?" for m in members})
    packages = sorted({package_of(m["source_path"]) for m in members})
    prefixes = sorted({p for p in (ps_prefix(m) for m in members) if p})
    versions = sorted({m.get("version") for m in members if m.get("version")})
    weights = sorted({m["weight_class"] for m in members if m.get("weight_class")})
    widths = sorted({m["width_class"] for m in members if m.get("width_class")})
    axes = sorted({a["tag"] for m in members for a in m.get("variable_axes") or []})
    scripts = sorted({s for m in members for s in m.get("scripts") or []})
    dominants = sorted({m.get("dominant_script") for m in members
                        if m.get("dominant_script")})

    evidence, conflicts = [], list(extra_conflicts)
    if any(m["_family_key_source"] == "name_id_16" for m in members):
        evidence.append(EV_SAME_ID16)
    if any(m["_family_key_source"] == "name_id_1" for m in members):
        evidence.append(EV_SAME_ID1)
    if len(vendors) == 1 and vendors[0] != "?":
        evidence.append(EV_SAME_VENDOR)
    elif len(vendors) > 1:
        conflicts.append(CONFLICT_VENDOR)
    if len(packages) == 1:
        evidence.append(EV_SAME_PACKAGE)
    elif len(packages) > 1:
        conflicts.append(CONFLICT_PACKAGE)
    if len(prefixes) == 1:
        evidence.append(EV_SAME_PS_PREFIX)
    elif len(prefixes) > 1:
        conflicts.append(CONFLICT_PS_PREFIX)
    if len(versions) > 1:
        conflicts.append(CONFLICT_VERSION)
    if len(weights) > 1:
        evidence.append(EV_WEIGHT_LADDER)
    if axes:
        evidence.append(EV_VARIABLE_AXES)

    # glyph compatibility, pairwise against the first member
    incompatible = [m for m in members[1:]
                    if not _coverage_compatible(members[0], m)]
    if incompatible:
        conflicts.append(CONFLICT_COVERAGE)
    elif len(members) > 1:
        evidence.append(EV_COMPATIBLE_COVERAGE)

    dupes = sorted({m["source_sha256"] for m in members
                    if len(by_hash.get(m["source_sha256"], [])) > 1})
    if dupes:
        evidence.append(EV_EXACT_DUPLICATE)

    if state == FAMILY_GROUPED and conflicts:
        state = FAMILY_RELATIONSHIP_REVIEW_REQUIRED

    gid = "fam-" + hashlib.sha256(
        (f"{key}|{split_by}|" + "|".join(sorted(m["face_id"] for m in members))
         ).encode()).hexdigest()[:16]

    return {
        "schema_version": SCHEMA_VERSION,
        "group_id": gid,
        "family_key": key,
        "key_source": (members[0]["_family_key_source"] if members else "none"),
        "state": state,
        "split_by": split_by,
        "face_count": len(members),
        "file_count": len({m["source_path"] for m in members}),
        "faces": sorted(m["face_id"] for m in members),
        "display_names": sorted({m["names"].get("family_typographic")
                                 or m["names"].get("family_legacy") or "?"
                                 for m in members}),
        "vendors": vendors,
        "source_packages": packages,
        "postscript_prefixes": prefixes,
        "versions": versions,
        "weight_classes": weights,
        "width_classes": widths,
        "variable_axes": axes,
        "is_variable": bool(axes),
        "scripts": scripts,
        "dominant_scripts": dominants,
        "duplicate_hashes": dupes,
        "supporting_evidence": sorted(set(evidence)),
        "conflicting_evidence": sorted(set(conflicts)),
        "incompatible_faces": sorted(m["face_id"] for m in incompatible),
        "note": note or ("a family name is a grouping HYPOTHESIS, not identity proof. "
                         "This group is a proposal for human review."),
        "human_confirmed_family": None,       # human only
        "parser": PARSER,
    }
