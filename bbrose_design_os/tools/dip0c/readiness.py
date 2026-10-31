"""Technical readiness — axis A ONLY (DIP-0C2b).

Scores what the ARTEFACT is. Nothing here reads or writes ownership, licensing,
reuse posture, retrieval or automatic-use eligibility, and no value in the
vocabulary refers to them (that is why `READY_AFTER_RIGHTS_REVIEW` was retired).

The verdict is **not** a blended score. Evidence is collected with an explicit
`blocking` flag, and the verdict falls out of a fixed precedence over the blocking
evidence — so the same artefact + the same config always yields the same verdict,
and every verdict can be traced to the evidence item that caused it.

Source-level and candidate-level assessments are BOTH produced and kept:
* **safety/tool blockers propagate** parent → candidate (corruption, unsafe SVG,
  EPS tool limitation) — a candidate cannot be cleaner than a file we cannot
  safely or fully read;
* **quality judgments propagate in neither direction** — a clean isolated sticker
  on a messy sheet keeps its own verdict, and a poor crop on a pristine sheet does
  not inherit the sheet's.
"""
from __future__ import annotations

from . import assetcandidate as AC
from . import config as C

PARSER = f"{C.TOOL_NAME}.readiness/{C.TOOL_VERSION}"

# thresholds (fingerprinted into every assessment so results reproduce)
THRESHOLDS = {
    "complexity_high_paths": 20_000,
    "complexity_medium_paths": 5_000,
    "raster_coverage_cleanup": 0.60,   # vector this raster-heavy needs cleanup
    "isolation_low": 0.05,             # candidate occupies <5% of the surface
    "min_effective_long_edge": C.RES_THRESHOLDS[C.RES_LOW_RES_REFERENCE],
}
CONFIG_FP = AC.config_fingerprint({"readiness": THRESHOLDS,
                                   "vocabulary": list(C.TECHNICAL_READINESS)})

# Blockers that legitimately propagate from the source file to every candidate.
PROPAGATING_BLOCKERS = (C.EV_CORRUPTION, C.EV_UNSAFE_SVG, C.EV_EPS_TOOL_LIMITATION)


def evidence(code: str, detail: str, *, tier: str = C.TIER_HEURISTIC,
             signal=None, blocking: bool = False) -> dict:
    if code not in C.READINESS_EVIDENCE_CODES:
        raise ValueError(f"unknown readiness evidence code: {code!r}")
    return {"code": code, "tier": tier, "detail": detail, "signal": signal,
            "blocking": blocking}


# --- precedence -------------------------------------------------------------
# First matching blocking code wins. Deterministic; no scoring soup.
_PRECEDENCE = (
    (C.EV_CORRUPTION, C.READY_REJECT_CANDIDATE),
    (C.EV_UNSAFE_SVG, C.READY_QUARANTINE),
    (C.EV_EPS_TOOL_LIMITATION, None),               # REQUIRES_TOOL / HEADER_ONLY_PARTIAL
    (C.EV_EMBEDDED_RASTER_DEPENDENCE, C.READY_NEEDS_VECTOR_RECONSTRUCTION),
    (C.EV_WATERMARK_SUSPICION, C.READY_REFERENCE_ONLY),
    (C.EV_RASTER_RESOLUTION, C.READY_REFERENCE_ONLY),
    (C.EV_COLLECTION_SHEET_AMBIGUITY, C.READY_NEEDS_CLEANUP),
    (C.EV_VECTOR_RASTER_BALANCE, C.READY_NEEDS_CLEANUP),
    (C.EV_UNSUPPORTED_FEATURES, C.READY_NEEDS_CLEANUP),
    (C.EV_PATH_CLEANLINESS, C.READY_NEEDS_CLEANUP),
)


def assess(evidence_items: list[dict], *, header_facts: bool = False) -> dict:
    """Axis-A verdict from evidence. Rights are never consulted."""
    blocking = {e["code"]: e for e in evidence_items if e["blocking"]}
    value = None
    cause = None
    for code, verdict in _PRECEDENCE:
        if code in blocking:
            cause = blocking[code]
            if code == C.EV_EPS_TOOL_LIMITATION:
                # header data present -> the audit is partial, not merely blocked
                value = (C.READY_HEADER_ONLY_PARTIAL if header_facts
                         else C.READY_REQUIRES_TOOL)
            else:
                value = verdict
            break

    if value is None:
        caveats = [e for e in evidence_items
                   if not e["blocking"] and e["code"] in (
                       C.EV_COMPLEXITY, C.EV_ISOLATION, C.EV_TRANSPARENT_BACKGROUND,
                       C.EV_EDITABLE_COLORS)
                   and e.get("signal") == "caveat"]
        value = (C.READY_TECHNICALLY_USABLE_WITH_CAVEATS if caveats
                 else C.READY_TECHNICALLY_READY)

    blocked_by_tool = C.EV_EPS_TOOL_LIMITATION in blocking
    return {
        "value": C.readiness_value(value),
        "confidence": _confidence(value, cause, evidence_items),
        "tier": (C.TIER_REQUIRES_TOOL if blocked_by_tool
                 else C.TIER_DIRECT if cause and cause["tier"] == C.TIER_DIRECT
                 else C.TIER_HEURISTIC),
        "caused_by": cause["code"] if cause else None,
        "evidence": evidence_items,
        "blocked_by_tool": blocked_by_tool,
        "config_fingerprint": CONFIG_FP,
        "parser": PARSER,
        # axis A says nothing about rights — stated, not implied
        "axis": "A_technical_only",
    }


def _confidence(value, cause, items) -> float:
    if value in (C.READY_REQUIRES_TOOL, C.READY_HEADER_ONLY_PARTIAL):
        return 0.0                       # we did not see the artefact
    if cause is None:
        return 0.6
    return 0.8 if cause["tier"] == C.TIER_DIRECT else 0.6


def merge_source_blockers(candidate_assessment: dict, source_assessment: dict,
                          candidate_evidence: list[dict]) -> dict:
    """Safety/tool blockers propagate parent -> candidate. Quality judgments do
    NOT propagate in either direction."""
    src_blockers = [e for e in source_assessment["evidence"]
                    if e["blocking"] and e["code"] in PROPAGATING_BLOCKERS]
    if not src_blockers:
        return candidate_assessment
    merged = list(candidate_evidence)
    for e in src_blockers:
        item = dict(e)
        item["detail"] = f"inherited from source file: {e['detail']}"
        merged.append(item)
    header_facts = any(e["code"] == C.EV_EPS_TOOL_LIMITATION
                       and e.get("signal") == "header_facts"
                       for e in src_blockers)
    return assess(merged, header_facts=header_facts)
