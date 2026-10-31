"""Batchable human-review manifest and queues (DIP-0C2d).

Three interpretation rules govern this module, and each is enforced by a test:

1. **A collection group is NOT a duplicate family.** A sheet may hold many
   independent assets that are reviewed together but are in no way substitutes for
   one another. Group types stay distinct (`COLLECTION_GROUP`, `VISUAL_FAMILY`,
   `SOURCE_PACKAGE_FAMILY`, `EXACT_DUPLICATE_GROUP`,
   `CROSS_FORMAT_SOURCE_FAMILY`) and are never all called "families".
2. **`UNKNOWN_RELATIONSHIP` is a review queue, not evidence.** It means a
   comparison was generated, the evidence was insufficient, and a human may
   clarify. It is grouped by *shared reason* so nobody inspects 49 unrelated edges
   one at a time.
3. **An EPS without a hash is UNAVAILABLE, not unrelated.** Absence of a hash is
   not evidence of visual difference.

Machine and human sections are separate blocks. **A human decision never
overwrites machine inference** — the machine block is immutable once written.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from . import config as C
from . import phash

PARSER = f"{C.TOOL_NAME}.review_c2d/{C.TOOL_VERSION}"


# --- why is this UNKNOWN edge unresolved? -----------------------------------
def unknown_reason(edge: dict, a: dict, b: dict) -> str:
    """One shared reason per edge, so the queue batches by cause, not by pair."""
    if edge.get("perceptual_comparison") == "UNAVAILABLE_REQUIRES_TOOL":
        return C.UR_EPS_VISUAL_CAPABILITY_UNAVAILABLE
    if edge.get("weak_visual_evidence"):
        return C.UR_LOW_INFORMATION_IMAGE
    dd, dp = edge.get("dhash_distance"), edge.get("phash_distance")
    if dd is None or dp is None:
        return C.UR_SOURCE_FAMILY_EVIDENCE_ONLY
    # one hash says "close", the other says "far" -> the evidence conflicts
    if (min(dd, dp) <= C.HAMMING_STRONG) and (max(dd, dp) > C.HAMMING_REVIEW):
        return C.UR_CONFLICTING_HASH_EVIDENCE
    # a whole-file candidate compared against a crop from a segmented sheet
    a_whole = not (a.get("collection") or {}).get("is_member")
    b_whole = not (b.get("collection") or {}).get("is_member")
    if a_whole != b_whole:
        return C.UR_CANDIDATE_VS_WHOLE_SHEET_MISMATCH
    if C.HAMMING_STRONG < max(dd, dp) <= C.HAMMING_REVIEW:
        return C.UR_THRESHOLD_REVIEW_BAND
    if a["source_path"] != b["source_path"] and (
            a["source_folder"] == b["source_folder"]):
        return C.UR_SOURCE_FAMILY_EVIDENCE_ONLY
    return C.UR_VISUAL_EVIDENCE_INSUFFICIENT


UNKNOWN_REASON_ACTION = {
    C.UR_EPS_VISUAL_CAPABILITY_UNAVAILABLE:
        "Do NOT read these as visually unrelated. Confirm the source/package "
        "relationship, and defer any visual judgement until Ghostscript lands.",
    C.UR_LOW_INFORMATION_IMAGE:
        "The image carries too little visual information for a hash to mean "
        "anything. Judge by eye or exclude.",
    C.UR_CONFLICTING_HASH_EVIDENCE:
        "dHash and pHash disagree. Look at the pair and decide.",
    C.UR_CANDIDATE_VS_WHOLE_SHEET_MISMATCH:
        "A whole-file candidate is being compared with a crop from a segmented "
        "sheet — the units are not comparable. Decide whether the SOURCES are "
        "related instead.",
    C.UR_THRESHOLD_REVIEW_BAND:
        "The hashes are close but not conclusive (7-12). Confirm or reject.",
    C.UR_SOURCE_FAMILY_EVIDENCE_ONLY:
        "Only source/package evidence exists — no visual equivalence was "
        "established. Confirm the SOURCE relationship only.",
    C.UR_VISUAL_EVIDENCE_INSUFFICIENT:
        "The comparison ran and produced no conclusion. Judge by eye.",
    C.UR_SEGMENTATION_GRANULARITY_MISMATCH:
        "The two sides were segmented at different granularities.",
}


# --- groups: five DISTINCT kinds, never all called 'families' ---------------
def build_groups(sources, cands, src_edges, cand_edges, components) -> list[dict]:
    by_id = {c["candidate_id"]: c for c in cands}
    groups: list[dict] = []

    def add(gtype, members, evidence, note, *, level):
        groups.append({"group_id": f"{gtype}:{len(groups):03d}",
                       "group_type": gtype, "level": level,
                       "members": sorted(members), "size": len(members),
                       "evidence": evidence, "note": note})

    # A — exact FILE duplicates (byte-identical). Never a visual claim.
    exact = defaultdict(set)
    for e in src_edges:
        if any(h["relationship"] == C.SRC_EXACT_FILE_DUPLICATE
               for h in e["hypotheses"]):
            exact[e.get("sha256") or e["a"]].update((e["a"], e["b"]))
    for sha, members in exact.items():
        add(C.GROUP_EXACT_DUPLICATE, members,
            [f"identical SHA-256 {str(sha)[:16]}…"],
            "byte-identical FILES. Originals are never deleted or consolidated; a "
            "human decides which copy is canonical.", level="source")

    # B — collection groups: candidates segmented from ONE surface.
    for comp in components:
        if len(comp) < 2:
            continue
        member_edges = [e for e in cand_edges
                        if e["a"] in comp and e["b"] in comp]
        rels = {h["relationship"] for e in member_edges for h in e["hypotheses"]}
        visual = rels & {C.CAND_EXACT_VISUAL_DUPLICATE, C.CAND_LIKELY_NEAR_DUPLICATE}
        if visual:
            add(C.GROUP_VISUAL_FAMILY, comp,
                [f"visual equivalence edges: {sorted(visual)}"],
                "candidates that are visually EQUIVALENT — potential substitutes.",
                level="candidate")
        else:
            parents = {by_id[m]["source_path"] for m in comp if m in by_id}
            add(C.GROUP_COLLECTION, comp,
                [f"segmented from {len(parents)} source surface(s): "
                 f"{sorted(Path(p).name for p in parents)}"],
                "A COLLECTION GROUP IS NOT A DUPLICATE FAMILY. These candidates "
                "come from one sheet and are reviewed together, but they are "
                "independent assets and are NOT substitutes for one another.",
                level="candidate")

    # C — cross-format source families
    xf = defaultdict(set)
    for e in src_edges:
        if any(h["relationship"] == C.SRC_ALTERNATE_FORMAT_SOURCE
               for h in e["hypotheses"]):
            key = _stem_key(e["a"])
            xf[key].update((e["a"], e["b"]))
    for key, members in xf.items():
        fmts = sorted({Path(m).suffix.lower() for m in members})
        add(C.GROUP_CROSS_FORMAT, members,
            [f"same artwork carried as {fmts}",
             "formats differ in editability; readiness is NOT shared"],
            "One artwork in several FORMATS. Each member keeps its own technical "
            "readiness, its own capabilities and its own rights.", level="source")

    # D — source/package families
    pkg = defaultdict(set)
    for e in src_edges:
        if any(h["relationship"] == C.SRC_SAME_DOWNLOAD_PACKAGE
               for h in e["hypotheses"]):
            pkg[str(Path(e["a"]).parent)].update((e["a"], e["b"]))
    for folder, members in pkg.items():
        add(C.GROUP_SOURCE_PACKAGE, members,
            [f"same download package: {folder}"],
            "Co-located files. Package membership is CONTEXT — it does not make "
            "the candidates inside equivalent.", level="source")

    return groups


def _stem_key(path: str) -> str:
    from .families import normalize_stem
    return normalize_stem(Path(path).name)


# --- manifest rows: machine block + BLANK human block -----------------------
def build_rows(cands, cand_edges, groups, noms, blocking) -> list[dict]:
    by_id = {c["candidate_id"]: c for c in cands}
    edges_by_cand = defaultdict(list)
    for e in cand_edges:
        edges_by_cand[e["a"]].append(e)
        edges_by_cand[e["b"]].append(e)
    nominated = {n["nominated_candidate_id"]: n for n in noms
                 if n.get("nominated_candidate_id")}
    groups_by_member = defaultdict(list)
    for g in groups:
        for m in g["members"]:
            groups_by_member[m].append(g)

    rows = []
    for c in cands:
        cid = c["candidate_id"]
        my_groups = (groups_by_member.get(cid, [])
                     + groups_by_member.get(c["source_path"], []))
        edges = edges_by_cand.get(cid, [])
        hashable = c.get("hash") is not None
        info = (c["hash"]["information"] if hashable else None)

        reasons, prio = _priority(c, edges, my_groups, nominated.get(cid),
                                  hashable, info, by_id)
        machine = {
            "source_file": c["source_path"],
            "candidate_id": cid,
            "candidate_type": c.get("asset_type", C.ASSET_TYPE_UNKNOWN),
            "technical_readiness": c["readiness"],
            "rights_status": c["rights"],
            "reuse_posture": C.POSTURE_PENDING,
            "retrieval_eligibility": c["retrieval"],
            "automatic_use_eligibility": c["automatic_use"],
            "exact_duplicate_group": _gid(my_groups, C.GROUP_EXACT_DUPLICATE),
            "collection_group": _gid(my_groups, C.GROUP_COLLECTION),
            "source_package_family": _gid(my_groups, C.GROUP_SOURCE_PACKAGE),
            "cross_format_source_family": _gid(my_groups, C.GROUP_CROSS_FORMAT),
            "visual_family": _gid(my_groups, C.GROUP_VISUAL_FAMILY),  # None if no
            "relationship_edges": [
                {"other": (e["b"] if e["a"] == cid else e["a"]),
                 "primary": e["primary"], "confidence": e["confidence"]}
                for e in edges],
            "relationship_hypotheses": sorted(
                {h["relationship"] for e in edges for h in e["hypotheses"]}),
            "dhash": (c["hash"]["dhash"] if hashable else None),
            "phash": (c["hash"]["phash"] if hashable else None),
            "hash_distances": [
                {"other": (e["b"] if e["a"] == cid else e["a"]),
                 "dhash_distance": e.get("dhash_distance"),
                 "phash_distance": e.get("phash_distance")}
                for e in edges],
            "transform_evidence": sorted(
                {e["best_transform"] for e in edges
                 if e.get("transform_only_match")}),
            "information_score": (
                {"grayscale_std": info["grayscale_std"],
                 "entropy_bits": info["entropy_bits"],
                 "alpha_coverage": info["alpha_coverage"],
                 "weak_evidence": info["weak_evidence"]} if info else None),
            "canonical_candidate_nomination": (
                nominated[cid]["nomination"] if cid in nominated else None),
            "confidence": (round(max((e["confidence"] for e in edges), default=0.0),
                                 3)),
            "review_priority": prio,
            "review_reasons": reasons,
            "capability_limitations": _limits(c, hashable, blocking),
            "provenance": {"parser": PARSER,
                           "hash_config_fingerprint": phash.CONFIG_FP,
                           "algorithm_version": phash.ALGORITHM_VERSION},
        }
        rows.append({"machine": machine, "human": C.human_review_block()})
    return rows


def _gid(groups, gtype):
    for g in groups:
        if g["group_type"] == gtype:
            return g["group_id"]
    return None


def _limits(c, hashable, blocking) -> list[str]:
    out = []
    if not hashable:
        out.append(f"{C.VISUAL_COMPARISON_UNAVAILABLE}: no perceptual hash could be "
                   "computed (EPS previews are not decodable). This is NOT evidence "
                   "of visual difference — the comparison could not be made.")
        out.append(f"{C.READY_REQUIRES_TOOL}: geometry/editability need Ghostscript")
    if blocking.get("skipped_bucket_count"):
        out.append(f"relationship search is not exhaustive: "
                   f"{blocking['skipped_bucket_count']} blocking bucket(s) exceeded "
                   f"{blocking['max_bucket_members']} members and were skipped")
    return out


# --- priority (every priority carries reasons) ------------------------------
def _priority(c, edges, groups, nomination, hashable, info, by_id):
    reasons = []
    high = medium = False

    if _gid(groups, C.GROUP_EXACT_DUPLICATE):
        high = True
        reasons.append("exact file duplicate — a canonical copy must be chosen")
    if nomination:
        high = True
        reasons.append("nominated CANONICAL_CANDIDATE — needs human selection")
    xf = _gid(groups, C.GROUP_CROSS_FORMAT)
    if xf:
        readiness = {by_id[m]["readiness"] for m in
                     _members(groups, C.GROUP_CROSS_FORMAT) if m in by_id}
        if len(readiness) > 1:
            high = True
            reasons.append("cross-format family whose members have DIFFERENT "
                           "technical readiness — no member may inherit another's")
    if any(e.get("weak_visual_evidence") is False
           and e.get("dhash_distance") is not None
           and e.get("phash_distance") is not None
           and min(e["dhash_distance"], e["phash_distance"]) <= C.HAMMING_STRONG
           and max(e["dhash_distance"], e["phash_distance"]) > C.HAMMING_REVIEW
           for e in edges):
        high = True
        reasons.append("conflicting hash evidence (dHash and pHash disagree)")
    if any(e.get("_unknown_reason") == C.UR_CANDIDATE_VS_WHOLE_SHEET_MISMATCH
           for e in edges):
        high = True
        reasons.append("candidate-vs-whole-sheet mismatch")
    if (c["readiness"] in (C.READY_TECHNICALLY_READY,
                           C.READY_TECHNICALLY_USABLE_WITH_CAVEATS)
            and c["rights"]["ownership"] == "unconfirmed"):
        high = True
        reasons.append("technically strong but ownership/licence unverified — "
                       "unusable until rights are confirmed")

    if not hashable:
        medium = True
        reasons.append(f"{C.VISUAL_COMPARISON_UNAVAILABLE} (EPS) — requires tool; "
                       "NOT to be read as visually unrelated")
    if info and info["weak_evidence"]:
        medium = True
        reasons.append("low-information image — hash distance is not trustworthy")
    if any(e["primary"] == C.CAND_UNKNOWN_RELATIONSHIP for e in edges):
        medium = True
        reasons.append("UNKNOWN_RELATIONSHIP edges await human clarification "
                       "(a review queue, not positive family evidence)")
    if any(e.get("transform_only_match") for e in edges):
        medium = True
        reasons.append("transform-only (mirrored/rotated) evidence")

    if _gid(groups, C.GROUP_COLLECTION):
        reasons.append("member of a COLLECTION_GROUP — reviewed together, but "
                       "these are independent assets, NOT substitutes")
    if _gid(groups, C.GROUP_SOURCE_PACKAGE):
        reasons.append("shares a download package (context only)")

    if high:
        return reasons, C.PRIORITY_HIGH
    if medium:
        return reasons, C.PRIORITY_MEDIUM
    if reasons:
        return reasons, C.PRIORITY_LOW
    return ["no relationship affects future reuse"], C.PRIORITY_OPTIONAL


def _members(groups, gtype):
    for g in groups:
        if g["group_type"] == gtype:
            return g["members"]
    return []
