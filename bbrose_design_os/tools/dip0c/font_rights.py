"""Font rights, quarantine recommendations, and batch leverage (DIP-0C4b).

Every permission is `false` and stays `false`. Nothing here approves, installs,
recommends operationally, or makes anything retrievable. A machine may raise a
**quarantine candidate**; it may never reject, delete, or clear a font.

**Possession is not permission.** An OFL sitting beside a font is evidence that a
document exists — not that BBROSE may use the font commercially, embed it, or ship it.
`fsType` is embedding metadata. A vendor URL is a hyperlink. None of them is a licence
decision, and none of them will ever set one from here.

**Three independent review units** (the business's §5), because they answer different
questions and one does not settle another:

* **family** — is this typographically one thing? (technical)
* **source package** — what were we given, and with what paperwork? (rights)
* **family × package** — the same family from two packages may carry *different rights*.

A licence approval never propagates across packages because two family names match.
"""
from __future__ import annotations

from collections import defaultdict

from . import config as C
from . import font_packages as FP
from . import font_provenance as FPV
from . import rights_model as RM

PARSER = f"{C.TOOL_NAME}.font_rights/{C.TOOL_VERSION}"
SCHEMA_VERSION = "font_rights/1.0"

# --- machine-allowed postures ---------------------------------------------------
QUARANTINE_CANDIDATE = "QUARANTINE_CANDIDATE"
RIGHTS_UNRESOLVED = "RIGHTS_UNRESOLVED"
RIGHTS_REVIEW_REQUIRED = "RIGHTS_REVIEW_REQUIRED"
PROVENANCE_MISSING = "PROVENANCE_MISSING"
EVIDENCE_PRESENT_UNREVIEWED = "EVIDENCE_PRESENT_UNREVIEWED"
REFERENCE_ONLY = "REFERENCE_ONLY"
REQUIRES_HUMAN = "REQUIRES_HUMAN"
MACHINE_ALLOWED = (QUARANTINE_CANDIDATE, RIGHTS_UNRESOLVED, RIGHTS_REVIEW_REQUIRED,
                   PROVENANCE_MISSING, EVIDENCE_PRESENT_UNREVIEWED, REFERENCE_ONLY,
                   REQUIRES_HUMAN)

# --- the fail-closed operational policy -----------------------------------------
# A font without REVIEWED AND ACCEPTED rights evidence is disabled on every axis. This
# is the standing state of 4,786 of 4,883 fonts, and it is not a punishment — it is the
# only honest default when the paperwork does not exist.
FAIL_CLOSED_POLICY = {
    "license_status": "LICENSE_UNVERIFIED",
    "retrieval_allowed": False,
    "automatic_use_allowed": False,
    "production_use_allowed": False,
    "embedding_allowed": False,
    "redistribution_allowed": False,
}
NO_SUSPICION_IS_NOT_SAFETY = (
    "The absence of a system-font suspicion is NOT a finding of safety and NOT a "
    "licence. The foundry list is hand-written; a font from an unlisted foundry is "
    "simply never asked about. 'Not suspected' means 'not examined', never 'cleared'.")

# --- states no machine may ever produce -----------------------------------------
LICENSE_APPROVED = "LICENSE_APPROVED"
COMMERCIAL_USE_APPROVED = "COMMERCIAL_USE_APPROVED"
APPROVED_BRAND_FONT = "APPROVED_BRAND_FONT"
BBROSE_OWNED_CONFIRMED = "BBROSE_OWNED_CONFIRMED"
PERMANENTLY_REJECTED = "PERMANENTLY_REJECTED"
HUMAN_ONLY = (LICENSE_APPROVED, COMMERCIAL_USE_APPROVED, APPROVED_BRAND_FONT,
              BBROSE_OWNED_CONFIRMED, PERMANENTLY_REJECTED)

# What a human may later decide about a quarantine candidate. Recorded, never taken.
PERMITTED_HUMAN_OUTCOMES = (
    "PROPERLY_LICENSED",
    "INTERNAL_SYSTEM_DEPENDENCY",
    "THIRD_PARTY_RESTRICTED",
    "REMOVE_FROM_FUTURE_REVIEW",
    "QUARANTINE_PERMANENTLY",
)


def machine_font_state(value: str | None) -> str | None:
    """Guard. A machine may raise a question about a font; it may never answer one."""
    if value is None:
        return None
    if value in HUMAN_ONLY:
        raise C.HumanOnlyStateViolation(
            f"{value!r} is a HUMAN decision about a font. Machine code may recommend "
            f"quarantine and record evidence; it may never approve, clear, or "
            f"permanently reject. Allowed: {list(MACHINE_ALLOWED)}")
    if value not in MACHINE_ALLOWED:
        raise ValueError(f"{value!r} is not a known font rights state")
    return value


def permissions() -> dict:
    """Every operational permission, derived from the canonical PermissionSet — and
    every one of them false. No count is hardcoded anywhere."""
    return {flag: False for flag in RM.PERMISSION_FLAGS}


def assess_batch(*, batch_id: str, kind: str, faces: list[dict],
                 files: list[dict], package: dict | None,
                 suspicions: dict) -> dict:
    """A rights recommendation for ONE review batch. Recommends; never decides."""
    sus = [suspicions[f["face_id"]] for f in faces if f["face_id"] in suspicions]
    suspected = [s for s in sus
                 if s["outcome"] == FPV.SUSPECTED_SYSTEM_FONT_COPY]
    evidence_present = [s for s in sus
                        if s["outcome"] == FPV.SYSTEM_FONT_EVIDENCE_PRESENT]

    ev = (package or {}).get("license_evidence") or []
    usable_ev = [e for e in ev if e["mentions_fonts"]]
    restrictions = sorted({r for e in ev for r in e["restrictions_detected"]})
    warnings = sorted({w for e in ev for w in e["warnings"]})

    reasons: list[str] = []
    posture = RIGHTS_UNRESOLVED

    if suspected:
        posture = QUARANTINE_CANDIDATE
        foundries = sorted({f for s in suspected for f in s["foundries"]})
        reasons.append(
            f"{len(suspected)} face(s) carry name-table evidence of an OS/major "
            f"foundry ({', '.join(foundries)}). This is a SUSPICION, not a finding of "
            "wrongdoing: the font may be licensed, or an internal system dependency.")
    if not ev:
        reasons.append("no licence evidence of any kind is associated with this batch")
    elif not usable_ev:
        posture = QUARANTINE_CANDIDATE if suspected else RIGHTS_UNRESOLVED
        reasons.append(
            "licence evidence exists but NONE of it mentions fonts — it may govern "
            "something else entirely that happened to ship in the same folder")
    else:
        posture = EVIDENCE_PRESENT_UNREVIEWED
        reasons.append(
            f"{len(usable_ev)} licence document(s) mentioning fonts are associated — "
            "UNREVIEWED. Evidence is not approval.")
    if restrictions:
        reasons.append(f"restrictive terms detected: {restrictions}")

    unparseable = [f for f in files if f.get("parse_status") in
                   ("UNSUPPORTED_FORMAT", "PARSE_FAILED")]
    if unparseable and not faces:
        posture = REFERENCE_ONLY
        reasons.append(f"{len(unparseable)} file(s) cannot be parsed at all")

    return {
        "schema_version": SCHEMA_VERSION,
        "batch_id": batch_id,
        "batch_kind": kind,
        "file_count": len(files),
        "face_count": len(faces),
        "reuse_posture": machine_font_state(posture),
        "ownership_status": "OWNERSHIP_UNCONFIRMED",
        "license_status": "LICENSE_UNVERIFIED",
        "suspected_system_faces": len(suspected),
        "system_evidence_faces": len(evidence_present),
        "suspected_foundries": sorted({f for s in suspected for f in s["foundries"]}),
        "license_evidence_files": [e["evidence_file"] for e in ev],
        "license_evidence_mentioning_fonts": [e["evidence_file"] for e in usable_ev],
        "restrictions_detected": restrictions,
        "evidence_warnings": warnings,
        "reasons": reasons,
        "permissions": permissions(),
        "permitted_human_outcomes": list(PERMITTED_HUMAN_OUTCOMES),
        "machine_may_delete_or_reject": False,
        "source_files_moved_or_deleted": 0,
        "human_confirmation": None,          # human only
        "note": "A RECOMMENDATION. Every permission is false. No machine may approve, "
                "clear, delete or permanently reject a font.",
        "parser": PARSER,
    }


def system_font_batch_proposal(*, files: list, faces: list, suspicions: dict,
                               overlap: dict, unparseable: list) -> dict:
    """What a reviewer must SEE before accepting (or refusing) the dump quarantine.

    This is a PROPOSAL, not a disposition. Nothing is quarantined by inference, and the
    single biggest batch in the milestone is also the riskiest — so it is presented with
    its false-positive risk in plain sight rather than buried.
    """
    suspected = {fid for fid, s in suspicions.items()
                 if s["outcome"] == FPV.SUSPECTED_SYSTEM_FONT_COPY}
    sus_faces = [f for f in faces if f["face_id"] in suspected]
    vendors = defaultdict(int)
    foundries = defaultdict(int)
    for fid in suspected:
        s = suspicions[fid]
        if s["vendor_id"]:
            vendors[s["vendor_id"]] += 1
        for fo in s["foundries"]:
            foundries[fo] += 1

    # a face whose vendor names one foundry and whose copyright names another
    contradictory = []
    for fid in sorted(suspected):
        s = suspicions[fid]
        if len(s["foundries"]) > 1:
            contradictory.append({"face_id": fid, "foundries": s["foundries"],
                                  "vendor_id": s["vendor_id"]})

    return {
        "proposal": "QUARANTINE_CANDIDATE — the suspected duplicated dump",
        "is_applied": False,
        "applied_by_machine": False,
        "total_files": len(files),
        "total_faces": len(faces),
        "suspected_faces": len(sus_faces),
        "duplicate_overlap": overlap,
        "vendor_evidence": dict(sorted(vendors.items(), key=lambda kv: -kv[1])),
        "copyright_evidence": dict(sorted(foundries.items(), key=lambda kv: -kv[1])),
        "unsupported_fon_files": len(unparseable),
        "contradictory_evidence": contradictory[:20],
        "contradictory_count": len(contradictory),
        "known_exceptions": [
            "a Microsoft/Adobe/Monotype font may be perfectly LICENSED to BBROSE",
            "a font may be an internal system dependency BBROSE genuinely needs",
            f"{len(files) - len(sus_faces)} files in the dump carry NO system-font "
            "evidence at all — quarantining the folder quarantines them too",
            "the foundry list is hand-written: unlisted foundries are never suspected",
        ],
        "false_positive_risk": (
            "MATERIAL. This batch is defined by FOLDER, but suspicion is defined by "
            "NAME TABLE — and most files in the folder carry no suspicion. Accepting "
            "the batch quarantines fonts that were never individually implicated. That "
            "may still be the right call for an unverified dump; it is a judgement, and "
            "it is not the machine's."),
        "recommended_action": (
            "keep the dump operationally DISABLED (it already is, and always was) and "
            "rebuild the active library from verified sources — rather than attempting "
            "to clear 3,780 files of unknown provenance"),
        "permissions": permissions(),
        "human_confirmation": None,
        "parser": PARSER,
    }


def curated_library_recommendation(*, packages: list, evidence_fonts: int,
                                   faces: list) -> dict:
    """The business recommendation: curate forward, do not try to clear the dump."""
    dl = [p for p in packages if p["package_kind"] == FP.PKG_DOWNLOAD_PACKAGE]
    with_ev = [p for p in dl if p["has_license_evidence"]]
    scripts = defaultdict(int)
    for f in faces:
        if f.get("dominant_script"):
            scripts[f["dominant_script"]] += 1

    return {
        "strategy": "CURATED STARTER LIBRARY — rebuild from verified sources",
        "rationale": (
            "98% of the corpus has no licence evidence. Clearing 4,786 fonts of unknown "
            "provenance is not a review task, it is an archaeology project — and it "
            "would produce a library nobody can defend. Curating forward from the 46 "
            "organised packages is tractable, defensible, and produces a library that "
            "is smaller and entirely known."),
        "steps": [
            "1. keep the unverified dump operationally DISABLED (already true)",
            f"2. prioritise the {len(dl)} organised download packages",
            f"3. review the {evidence_fonts} fonts whose evidence actually mentions "
            "fonts, first",
            "4. select a small starter collection covering Latin, Arabic, CJK, display, "
            "body, and luxury/editorial",
            "5. require known provenance and explicit human approval before activation",
            "6. rebuild the operational library gradually from verified sources",
        ],
        "packages_with_font_evidence": len(with_ev),
        "script_coverage_available": dict(sorted(scripts.items(),
                                                 key=lambda kv: -kv[1])[:8]),
        "archive_note": (
            "the historical dump may remain ARCHIVED for investigation. It must not "
            "become the active BBROSE font library by default."),
        "activation_requires": "explicit human approval — not implemented, not in C4c",
        "parser": PARSER,
    }


# --- EXACT BYTES DO NOT PROVE IDENTICAL RIGHTS ----------------------------------
# The correction that matters most in C4b, and the one I got wrong first time.
#
# A SHA-256 match proves the FILES are the same. It says nothing about where each copy
# came from, what was signed to obtain it, or what that licence permits. Rights attach
# to PROVENANCE and ACQUISITION, not to content. The same TTF downloaded from a foundry
# under a paid licence and scraped from a warez site is byte-identical and legally
# nothing alike — and one package's OFL must never clear an identical file that arrived
# from an unverified source.
#
# So a duplicate group splits into TWO different kinds of grouping:
#   A. ONE technical identity group   — the bytes, safely shared
#   B. N provenance-rights subgroups  — the paperwork, never shared across sources
PROV_KNOWN_PACKAGE = "KNOWN_PACKAGE_WITH_EVIDENCE"
PROV_KNOWN_NO_EVIDENCE = "KNOWN_PACKAGE_NO_EVIDENCE"
PROV_UNVERIFIED_DUMP = "UNVERIFIED_DUMP"
PROV_UNKNOWN = "UNKNOWN_ORIGIN"


def _provenance_key(path: str, evidence: list) -> tuple[str, str]:
    """What do we actually know about where THIS copy came from?"""
    pkg = FP.package_of(path)
    kind = FP.classify_package(pkg)
    usable = [e for e in (evidence or []) if e.get("mentions_fonts")]
    if kind == FP.PKG_SUSPECTED_DUMP:
        return pkg, PROV_UNVERIFIED_DUMP
    if kind == FP.PKG_DOWNLOAD_PACKAGE:
        return pkg, (PROV_KNOWN_PACKAGE if usable else PROV_KNOWN_NO_EVIDENCE)
    return pkg, PROV_UNKNOWN


def duplicate_review_model(dedupe: dict, evidence_by_path: dict,
                           faces_by_hash: dict = None) -> list[dict]:
    """Split every exact-duplicate group into ONE technical identity group and N
    provenance-rights subgroups.

    A rights decision may be batched across duplicate members **only** when they share
    the same credible provenance *and* the same evidence. Otherwise the bytes are one
    thing and the rights are several.
    """
    out = []
    for sha, members in sorted(dedupe["duplicate_groups"].items()):
        paths = sorted(m["relative_path"] for m in members)

        subgroups: dict[tuple, list[str]] = defaultdict(list)
        for p in paths:
            subgroups[_provenance_key(p, evidence_by_path.get(p))].append(p)

        subs = []
        for (pkg, kind), ps in sorted(subgroups.items()):
            ev = sorted({e["evidence_file"]
                         for p in ps
                         for e in (evidence_by_path.get(p) or [])
                         if e.get("mentions_fonts")})
            subs.append({
                "provenance_kind": kind,
                "source_package": pkg,
                "paths": sorted(ps),
                "file_count": len(ps),
                "license_evidence_mentioning_fonts": ev,
                "rights_posture": machine_font_state(
                    EVIDENCE_PRESENT_UNREVIEWED if ev
                    else PROVENANCE_MISSING if kind in (PROV_UNVERIFIED_DUMP,
                                                        PROV_UNKNOWN)
                    else RIGHTS_REVIEW_REQUIRED),
                "permissions": permissions(),          # every one false
                "human_confirmation": None,
            })

        # A rights batch is permissible ONLY if every copy shares one credible
        # provenance AND one evidence set.
        one_provenance = len(subs) == 1
        credible = one_provenance and subs[0]["provenance_kind"] == PROV_KNOWN_PACKAGE
        faces = (faces_by_hash or {}).get(sha, [])

        out.append({
            "schema_version": "duplicate_review/1.0",
            "sha256": sha,
            "file_count": len(paths),
            "paths": paths,
            # --- A. the technical identity group: bytes, safely shared -----------
            "technical_identity_group": {
                "sha256": sha,
                "shared_safely": [
                    "identical bytes", "identical parsed metadata",
                    "identical glyph structure", "identical technical health",
                    "identical script coverage", "identical fsType data",
                    "identical family/face identity"],
                "face_ids": sorted({f["face_id"] for f in faces}),
                "face_count": len({f["face_id"] for f in faces}),
                "safe_as_one_decision": True,
                "scope": "TECHNICAL IDENTITY ONLY — not rights",
            },
            # --- B. the provenance-rights subgroups: never shared across sources --
            "provenance_rights_subgroups": subs,
            "rights_subgroup_count": len(subs),
            "rights_batchable": credible,
            "rights_batch_reason": (
                "every copy came from ONE credible package with font-relevant licence "
                "evidence — a single rights review may cover them"
                if credible else
                "the copies arrive from different or unverified sources. Identical "
                "bytes are NOT identical rights: one package's licence never clears "
                "an identical file that came from somewhere else."),
            "note": "EXACT BYTES DO NOT PROVE IDENTICAL RIGHTS. Rights attach to "
                    "PROVENANCE and ACQUISITION, not to content.",
            "parser": PARSER,
        })
    return out


def batch_leverage(*, files: list, faces: list, groups: list, packages: list,
                   suspicions: dict, dedupe: dict,
                   duplicate_model: list = None) -> dict:
    """How much review work can honestly be removed — and what stops each batch.

    **Reducing workload is not evidence that a batch decision is safe.** Every batch
    below carries its shared evidence AND its exceptions, and a batch with exceptions
    is not one decision.
    """
    suspected_faces = [fid for fid, s in suspicions.items()
                       if s["outcome"] == FPV.SUSPECTED_SYSTEM_FONT_COPY]
    dm = duplicate_model or []
    rights_batchable = sum(1 for d in dm if d["rights_batchable"])
    rights_subgroups = sum(d["rights_subgroup_count"] for d in dm)
    dl_pkgs = [p for p in packages
               if p["package_kind"] == FP.PKG_DOWNLOAD_PACKAGE]
    ev_pkgs = [p for p in dl_pkgs if p["has_license_evidence"]]

    # family x package — the same family from two packages is TWO rights units
    fxp = defaultdict(set)
    for f in faces:
        key = f.get("_family_key")
        if key:
            fxp[key].add(FP.package_of(f["source_path"]))
    split_families = {k: sorted(v) for k, v in fxp.items() if len(v) > 1}

    return {
        "raw_files": len(files),
        "faces": len(faces),
        "unique_files_by_hash": dedupe["files_unique"],
        "family_groups": len(groups),
        "source_packages": len(packages),
        "download_packages": len(dl_pkgs),
        "packages_with_license_evidence": len(ev_pkgs),
        "suspected_system_faces": len(suspected_faces),
        "levers": [
            {"lever": "exact duplicate groups — TECHNICAL identity",
             "removes_files": dedupe["files_in_duplicate_groups"]
                              - dedupe["duplicate_group_count"],
             "shared_evidence": "byte-identical SHA-256",
             "scope": "TECHNICAL IDENTITY ONLY",
             "exceptions": "none for the TECHNICAL audit — the bytes are the bytes",
             "safe_as_one_decision": True},
            {"lever": "exact duplicate groups — RIGHTS",
             "rights_batchable_groups": rights_batchable,
             "rights_subgroups_required": rights_subgroups,
             "shared_evidence": "NONE by default — rights attach to PROVENANCE, "
                                "not to content",
             "scope": "RIGHTS",
             "exceptions": "EXACT BYTES DO NOT PROVE IDENTICAL RIGHTS. The same TTF "
                           "bought under licence and scraped from elsewhere is "
                           "byte-identical and legally nothing alike. A rights batch "
                           "is permissible ONLY where every copy shares one credible "
                           "package AND one evidence set.",
             "safe_as_one_decision": False},
            {"lever": "suspected system-font batch",
             "removes_faces": len(suspected_faces),
             "shared_evidence": "name-table vendor/copyright naming an OS foundry",
             "exceptions": "a licensed Microsoft font is legal; each foundry may need "
                           "its own decision",
             "safe_as_one_decision": False},
            {"lever": "download packages with licence evidence",
             "batches": len(ev_pkgs),
             "shared_evidence": "one licence document per package",
             "exceptions": "evidence that does not mention fonts governs nothing",
             "safe_as_one_decision": False},
            {"lever": "family groups",
             "batches": len(groups),
             "shared_evidence": "name ID 16 + corroborating metadata",
             "exceptions": "190 groups have conflicting evidence",
             "safe_as_one_decision": False},
            {"lever": "family x source package",
             "families_split_across_packages": len(split_families),
             "shared_evidence": "none — this SPLITS work, it does not save it",
             "exceptions": "the same family from two packages may carry different "
                           "rights, and one package's licence never clears another",
             "safe_as_one_decision": False},
        ],
        "families_split_across_packages": dict(sorted(split_families.items())[:20]),
        "duplicate_rights_model": {
            "duplicate_groups": len(dm),
            "rights_batchable_groups": rights_batchable,
            "groups_needing_separate_rights_review": len(dm) - rights_batchable,
            "total_rights_subgroups": rights_subgroups,
            "rule": "exact duplicates are safe as ONE TECHNICAL IDENTITY decision, "
                    "but rights remain PROVENANCE-AWARE",
        },
        "note": "Workload reduction is NOT evidence that a batch decision is safe. "
                "Every lever above records what it shares and what it does not. "
                "EXACT BYTES DO NOT PROVE IDENTICAL RIGHTS.",
        "parser": PARSER,
    }
