"""Curated starter-library candidates (DIP-0C4c).

**A shortlist for a human to look at. Not a library.**

The only machine posture is `CURATED_STARTER_CANDIDATE`. `APPROVED_FONT`,
`APPROVED_BRAND_FONT`, `ACTIVE_FONT`, `RETRIEVABLE_FONT` and `PRODUCTION_READY_FONT` are
unreachable from here — a guard raises on every one of them.

A candidate is nominated on **provenance and technical health**, never on taste. Rights
remain unresolved, every permission stays `false`, and the final selection is a human's.
Being on this list means only: *"if you are going to review anything first, review this."*
"""
from __future__ import annotations

from collections import defaultdict

from . import config as C
from . import font_packages as FP
from . import rights_model as RM

PARSER = f"{C.TOOL_NAME}.font_curated/{C.TOOL_VERSION}"
SCHEMA_VERSION = "font_curated/1.0"

CURATED_STARTER_CANDIDATE = "CURATED_STARTER_CANDIDATE"

# States that would mean the machine had decided something. It has not, and cannot.
FORBIDDEN = ("APPROVED_FONT", "APPROVED_BRAND_FONT", "ACTIVE_FONT",
             "RETRIEVABLE_FONT", "PRODUCTION_READY_FONT")

# The capability slots a starter library needs to cover.
CAPABILITIES = (
    "latin_display", "latin_body", "arabic_display", "arabic_body",
    "cjk_compatible", "modern_sans", "elegant_serif", "handwritten_display",
    "multilingual_utility",
)


def machine_curated_state(value: str | None) -> str | None:
    if value in FORBIDDEN:
        raise C.HumanOnlyStateViolation(
            f"{value!r} is a HUMAN decision. Machine code may nominate a "
            f"{CURATED_STARTER_CANDIDATE} for review; it may never approve, activate "
            "or make a font retrievable.")
    if value not in (None, CURATED_STARTER_CANDIDATE):
        raise ValueError(f"{value!r} is not a permitted curated state")
    return value


def _capabilities(group: dict, styles: set) -> list[str]:
    caps = []
    doms = set(group.get("dominant_scripts") or [])
    scripts = set(group.get("scripts") or [])
    display = "display" in styles
    body = "body candidate" in styles or group.get("face_count", 0) >= 3

    if "latin" in doms:
        caps.append("latin_display" if display else "latin_body")
    if doms & {"arabic", "arabic_presentation_b", "arabic_presentation_a"} \
            or scripts & {"arabic"}:
        caps.append("arabic_display" if display else "arabic_body")
    if doms & {"cjk", "cjk_ext_a", "cjk_ext_b", "kana", "hangul"}:
        caps.append("cjk_compatible")
    if "sans" in styles:
        caps.append("modern_sans")
    if "serif" in styles:
        caps.append("elegant_serif")
    if "handwritten" in styles:
        caps.append("handwritten_display")
    if len(scripts) >= 3 and body:
        caps.append("multilingual_utility")
    return sorted(set(caps))


def nominate(*, groups: list, faces: list, packages: list, evidence_by_path: dict,
             suspicions: dict, styles: dict, dedupe: dict) -> dict:
    """Nominate candidates. Nothing is approved, activated, or made retrievable."""
    by_face = {f["face_id"]: f for f in faces}

    candidates = []
    for g in groups:
        members = [by_face[fid] for fid in g["faces"] if fid in by_face]
        if not members:
            continue

        pkgs = {FP.package_of(m["source_path"]) for m in members}
        kinds = {FP.classify_package(p) for p in pkgs}
        # a candidate must come from a KNOWN package — never from the unverified dump
        if kinds != {FP.PKG_DOWNLOAD_PACKAGE}:
            continue

        ev_files = sorted({e["evidence_file"]
                           for m in members
                           for e in (evidence_by_path.get(m["source_path"]) or [])
                           if e.get("mentions_fonts")})
        if not ev_files:
            continue                                   # no font-relevant evidence

        suspected = any(suspicions.get(m["face_id"], {}).get("outcome")
                        == "SUSPECTED_SYSTEM_FONT_COPY" for m in members)
        if suspected:
            continue

        if g["state"] != "FAMILY_GROUPED":
            continue                                   # relationship is uncertain
        if not all(m.get("parse_status") == "PARSED" for m in members):
            continue

        st = {t for m in members
              for t in (styles.get(m["face_id"], {}).get("tag_names") or [])}
        restrictions = sorted({r
                               for m in members
                               for e in (evidence_by_path.get(m["source_path"]) or [])
                               for r in (e.get("restrictions_detected") or [])})

        candidates.append({
            "schema_version": SCHEMA_VERSION,
            "state": machine_curated_state(CURATED_STARTER_CANDIDATE),
            "group_id": g["group_id"],
            "family": g["family_key"],
            "display_names": g["display_names"],
            "source_packages": sorted(pkgs),
            "face_count": g["face_count"],
            "weight_classes": g["weight_classes"],
            "is_variable": g["is_variable"],
            "variable_axes": g["variable_axes"],
            "scripts": g["scripts"],
            "dominant_scripts": g["dominant_scripts"],
            "style_tags": sorted(st),
            "capabilities": _capabilities(g, st),
            "license_evidence_mentioning_fonts": ev_files,
            "restrictions_detected": restrictions,
            "duplicate_hashes": g["duplicate_hashes"],
            "selection_basis": [
                "known source package (not the unverified dump)",
                "font-relevant licence evidence is present (UNREVIEWED)",
                "no system-font suspicion",
                "family relationship is not in conflict",
                "every face parses cleanly",
            ],
            "rights_status": "LICENSE_UNVERIFIED — evidence exists but is UNREVIEWED",
            "permissions": {flag: False for flag in RM.PERMISSION_FLAGS},
            "human_confirmation": None,
            "note": "A CANDIDATE FOR REVIEW. Not approved, not active, not retrievable, "
                    "not production-ready. Being on this list means only: review this "
                    "one first.",
            "parser": PARSER,
        })

    candidates.sort(key=lambda c: (-c["face_count"], c["family"] or ""))

    covered = defaultdict(list)
    for c in candidates:
        for cap in c["capabilities"]:
            covered[cap].append(c["family"])

    gaps = [cap for cap in CAPABILITIES if not covered.get(cap)]
    return {
        "schema_version": SCHEMA_VERSION,
        "candidates": candidates,
        "candidate_count": len(candidates),
        "capability_coverage": {k: sorted(v) for k, v in sorted(covered.items())},
        "capability_gaps": gaps,
        "gap_note": (
            "these capabilities have NO candidate that meets the bar (known package + "
            "font-relevant evidence + healthy + unconflicted). The library cannot be "
            "built from what is here alone — fonts will have to be acquired with "
            "provenance." if gaps else "every capability has at least one candidate"),
        "all_permissions_false": True,
        "approved": False,
        "activated": False,
        "note": "A SHORTLIST FOR HUMAN REVIEW. Nothing here is approved or activated.",
        "parser": PARSER,
    }
