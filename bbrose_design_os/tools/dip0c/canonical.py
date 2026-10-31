"""Canonical-candidate nomination (DIP-0C2c).

Machine code may **nominate** `CANONICAL_CANDIDATE`. It may **never select** a
final canonical asset — that is a human field, left blank.

Rights/licence evidence is shown as **context only** and contributes **nothing** to
the score. The axes stay separate: a technically strong but rights-unverified asset
can be the technical canonical candidate while remaining entirely unusable, and a
licensed asset with poor geometry does not become canonical because of its licence.
"""
from __future__ import annotations

from . import config as C

PARSER = f"{C.TOOL_NAME}.canonical/{C.TOOL_VERSION}"

# Technical merit only. Higher is a better technical representative of a family.
READINESS_RANK = {
    C.READY_TECHNICALLY_READY: 6,
    C.READY_TECHNICALLY_USABLE_WITH_CAVEATS: 5,
    C.READY_NEEDS_CLEANUP: 4,
    C.READY_HEADER_ONLY_PARTIAL: 3,
    C.READY_REQUIRES_TOOL: 2,
    C.READY_NEEDS_VECTOR_RECONSTRUCTION: 2,
    C.READY_REFERENCE_ONLY: 1,
    C.READY_QUARANTINE: 0,
    C.READY_REJECT_CANDIDATE: 0,
}


def nominate(component: list[str], candidates_by_id: dict) -> dict:
    """Nominate the strongest TECHNICAL representative of a family component."""
    scored = []
    for cid in component:
        c = candidates_by_id.get(cid)
        if not c:
            continue
        scored.append((_score(c), cid, c))
    if not scored:
        return {}
    scored.sort(key=lambda t: (-t[0]["total"], t[1]))
    best_score, best_id, best = scored[0]

    return {
        "component_size": len(component),
        "members": list(component),
        "nomination": C.POSTURE_CANONICAL_CANDIDATE,   # NOMINATED, not selected
        "nominated_candidate_id": best_id,
        "score_breakdown": best_score,
        "evidence": _evidence(best, best_score),
        "rights_context": _rights_context(best),
        "runners_up": [{"candidate_id": cid, "total": s["total"]}
                       for s, cid, _ in scored[1:4]],
        # the ONLY field that can make something canonical — machine leaves it blank
        "human_selected_canonical": None,
        "note": "a nomination is not a selection; no asset is activated, and "
                "rights evidence is context only and did not affect the score",
        "parser": PARSER,
    }


def _score(c: dict) -> dict:
    """Technical merit ONLY. Rights are deliberately absent from this function."""
    readiness = c.get("readiness", C.READY_REFERENCE_ONLY)
    ready = READINESS_RANK.get(readiness, 0)
    editable = 3 if c.get("source_format") in (".ai", ".pdf", ".svg") else 0
    raster_dep = -2 if c.get("jpeg_shell") else 0
    isolation = round(2 * float(c.get("isolation") or 0.0), 2)
    h = c.get("hash") or {}
    long_edge = max(h.get("source_dimensions", {}).get("w", 0),
                    h.get("source_dimensions", {}).get("h", 0))
    resolution = 2 if long_edge >= 2000 else 1 if long_edge >= 1000 else 0
    provenance = 1 if c.get("source_sha256") else 0
    total = ready + editable + raster_dep + isolation + resolution + provenance
    return {"readiness_rank": ready, "editable_geometry": editable,
            "raster_dependence_penalty": raster_dep, "isolation": isolation,
            "usable_resolution": resolution, "provenance": provenance,
            "total": round(total, 2),
            "rights_contribution": 0}       # explicitly zero, by design


def _evidence(c: dict, s: dict) -> list[str]:
    return [
        f"technical readiness {c.get('readiness')} (rank {s['readiness_rank']})",
        f"editable geometry: {c.get('source_format')} "
        f"(+{s['editable_geometry']})",
        f"raster dependence penalty {s['raster_dependence_penalty']}",
        f"isolation {c.get('isolation')}, usable resolution rank "
        f"{s['usable_resolution']}",
        "rights/licence evidence contributed 0 to this score by design",
    ]


def _rights_context(c: dict) -> dict:
    """Shown to the reviewer, contributes nothing to the score."""
    return {
        "ownership": "unconfirmed",
        "license": "unverified",
        "retrieval": False,
        "automatic_use": False,
        "note": "context only; a technically strong candidate may still be "
                "entirely unusable until a human confirms rights",
    }
