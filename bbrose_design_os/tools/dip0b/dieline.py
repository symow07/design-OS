"""Likely-dieline detection and technical-line classification (DIP-0B3).

Nothing here is a dieline. Everything is a *candidate* awaiting human
confirmation, and every verdict records what supported it, what contradicted it,
and what evidence was missing.

Evidence weights follow the approved model. Highest-weight evidence is
topological — closed structural contours, shared panel edges, dashed fold
structures, glue-flap topology, repeated panel dimensions. Recurring
RGB-converted red/cyan, filename terms such as 刀线, nearby text-like geometry and
visual resemblance are **supporting only** and can never carry a verdict alone.

`/Separation /All` proves registration ink exists in the document. It never proves
that a particular thin stroke is a registration mark: that association is claimed
only when the content-stream walk provably aligns with the drawing list.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass

from tools.dip0.provenance import Inferred, human_block

from . import config as C

ALGORITHM_VERSION = "b3-0.2.0"
PARSER = f"{C.TOOL_NAME}.dieline/{ALGORITHM_VERSION}"

# Technical line classes. Nothing is forced into cut or fold.
LINE_CLASSES = (
    "CUT_LINE_CANDIDATE",
    "FOLD_LINE_CANDIDATE",
    "CREASE_LINE_CANDIDATE",
    "REGISTRATION_MARK_CANDIDATE",
    "CROP_MARK_CANDIDATE",
    "DIMENSION_MARK_CANDIDATE",
    "STRUCTURAL_UNRESOLVED",
)

# Three page-level outcomes. A binary verdict forces a confident answer where the
# evidence does not support one: HL5503 has 13 orthogonal panels and 77 /All
# painting operations, yet neither qualifies nor cleanly rejects. It is preserved
# as the calibration example for why a human-review band exists.
LIKELY_DIELINE = "LIKELY_DIELINE_STRUCTURE"
BORDERLINE = "BORDERLINE_REVIEW_REQUIRED"
REJECTED = "REJECTED_NO_DIELINE_EVIDENCE"
OUTCOMES = (LIKELY_DIELINE, BORDERLINE, REJECTED)

OFF_CANVAS_TECHNICAL = "OFF_CANVAS_TECHNICAL_CANDIDATE"

FILENAME_HINT = re.compile(r"刀线|dieline|die[-_ ]?line|展盒|吸塑", re.I)


@dataclass(frozen=True)
class DielineConfig:
    """Gate + human-review band. Never tuned around a single file."""

    min_contour_area_frac: float = 0.025   # outer contour vs design surface
    min_contour_orthogonal: float = 0.30
    min_panels: int = 3
    # Route B: overwhelming topology on a canvas where the carton is small.
    route_b_min_shared_edges: int = 5
    route_b_min_dashed: int = 5
    route_b_min_panels: int = 5
    # Human-review band, applied ONLY to pages that miss the gate but still show
    # meaningful structural evidence.
    borderline_min_score: float = 0.45
    borderline_max_score: float = 0.60
    # A page that clears the gate but carries several contradictions is not a
    # confident verdict either.
    borderline_min_contradictions: int = 2

    def fingerprint(self) -> str:
        blob = json.dumps(asdict(self), sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()[:16]


DEFAULT_DIELINE_CONFIG = DielineConfig()

# Backwards-compatible module constants (read by tests and reports).
MIN_CONTOUR_AREA_FRAC = DEFAULT_DIELINE_CONFIG.min_contour_area_frac
MIN_CONTOUR_ORTHO = DEFAULT_DIELINE_CONFIG.min_contour_orthogonal
MIN_PANELS = DEFAULT_DIELINE_CONFIG.min_panels

# Recorded in every run so B4 inherits the distinction rather than rediscovering it.
B4_HANDOFF_NOTES = {
    "structural_is_not_technical": (
        "A thin structural stroke is NOT technical ink. Keep two sets: (A) "
        "structural-geometry evidence — thin strokes, dashed strokes, panel "
        "contours, shared edges, folds, glue-flap topology; (B) technical-colour "
        "evidence — directly associated spot/registration inks, high-confidence "
        "technical-colour candidates, ambiguous RGB-to-spot matches. A stroke may "
        "belong to one set, both, or neither. Never exclude a colour from artwork "
        "intelligence merely because its path is thin."),
    "registration_black_ambiguity": (
        "Path-level spot association is UNAVAILABLE on this pilot, so an "
        "RGB-converted black path must never be mapped to /Separation /All as a "
        "fact. Allow multiple candidate explanations, record delta-E to every "
        "plausible spot/process black, mark ambiguity, cap confidence, and place "
        "unresolved cases in `unresolved_or_ambiguous`. Document-level /All "
        "presence must not automatically remove ordinary black artwork from the "
        "artwork palette."),
    "dimension_marks": (
        "no geometric dimension-mark candidates detected under the current rule"),
    "dimension_mark_spot_check_pages": [
        "ES3083吸塑 展盒刀线.ai", "FB-2060 白卡.ai", "HL5503高光液.ai",
        "YB-1025(LP5870)...ai",
    ],
    "dimension_mark_open_questions": [
        "are dimension annotations genuinely absent from these designs?",
        "are dimensions drawn as outlined glyphs rather than geometry?",
        "is the current detector too narrow?",
    ],
}


def _inf(value, source, evidence, confidence, tier=C.TIER_HEURISTIC) -> dict:
    d = Inferred(value=value, source=source, evidence=list(evidence),
                 confidence=round(max(0.0, min(1.0, confidence)), 3),
                 parser=PARSER).to_dict()
    d["tier"] = tier
    return d


# --------------------------------------------------------------------------
# line classification


def classify_lines(graph: dict, marks_by_path: dict[int, str],
                   has_dieline_region: bool, outer_path: int | None,
                   shared_paths: set[int]) -> dict:
    """Assign each structural path a technical class.

    Without panel-topology evidence nothing becomes a cut or a fold: a
    decorative border stays `STRUCTURAL_UNRESOLVED`.
    """
    counts = dict.fromkeys(LINE_CLASSES, 0)
    per_path: dict[int, str] = {}

    for p in graph["_paths"]:
        idx = p["path_index"]
        if idx in marks_by_path:
            cls = marks_by_path[idx]
        elif not has_dieline_region:
            # No panel topology on this page -> nothing is a cut or a fold.
            cls = "STRUCTURAL_UNRESOLVED"
        elif p["dashed"]:
            cls = "FOLD_LINE_CANDIDATE"
        elif outer_path is not None and idx == outer_path:
            cls = "CUT_LINE_CANDIDATE"
        elif idx in shared_paths:
            cls = "CREASE_LINE_CANDIDATE"
        else:
            cls = "STRUCTURAL_UNRESOLVED"
        per_path[idx] = cls
        counts[cls] += 1

    return {"counts": counts, "per_path": per_path,
            "note": ("classes are heuristic unless directly supported by PDF "
                     "operators or human review; decorative linework stays "
                     "STRUCTURAL_UNRESOLVED without panel topology")}


# --------------------------------------------------------------------------
# evidence model


def evaluate_dieline(graph: dict, surface: tuple, cs: dict, filename: str,
                     cfg: DielineConfig = DEFAULT_DIELINE_CONFIG) -> dict:
    """Weighted evidence and a three-way outcome for a page-level dieline."""
    surface_area = max((surface[2] - surface[0]) * (surface[3] - surface[1]), 1e-6)
    outer = graph.get("outer_contour")
    contour_frac = (outer["area_pt2"] / surface_area) if outer else 0.0

    positive: list[str] = []
    contradictory: list[str] = []
    missing: list[str] = []
    score = 0.0

    # --- highest-weight, topological ---------------------------------------
    if outer and contour_frac >= cfg.min_contour_area_frac:
        positive.append(f"closed structural contour covering {contour_frac:.1%} "
                        "of the design surface")
        score += 0.30
    elif outer:
        contradictory.append(f"largest closed contour covers only "
                             f"{contour_frac:.1%} of the surface")
    else:
        missing.append("no closed structural contour")

    if outer and outer["orthogonal_fraction"] >= cfg.min_contour_orthogonal:
        positive.append(f"contour is {outer['orthogonal_fraction']:.0%} "
                        "axis-aligned")
        score += 0.10
    elif outer:
        contradictory.append("contour is largely non-orthogonal")

    ortho_panels = graph.get("orthogonal_panel_count", 0)
    if ortho_panels >= cfg.min_panels:
        positive.append(f"{ortho_panels} substantially orthogonal closed panels "
                        f"(of {graph['panel_count']} closed structural paths)")
        score += 0.15
    else:
        missing.append(f"fewer than {cfg.min_panels} orthogonal closed panels "
                       f"({graph['panel_count']} closed paths, most non-orthogonal "
                       "— decorative closed shapes are not carton panels)")

    if graph["shared_edge_count"] > 0:
        positive.append(f"{graph['shared_edge_count']} shared panel edges")
        score += 0.20
    else:
        missing.append("no shared panel edges (panels do not meet)")

    if graph["dashed_segments"] > 0:
        positive.append(f"{graph['dashed_segments']} dashed segments "
                        "(fold/crease structure)")
        score += 0.15
    else:
        missing.append("no dashed fold/crease structure")

    if graph["glue_flap_candidates"]:
        positive.append(f"{len(graph['glue_flap_candidates'])} glue-flap-like "
                        "panels (single-edge attachment, angled side)")
        score += 0.10

    if graph.get("mirrored_panel_pairs"):
        positive.append(f"{graph['mirrored_panel_pairs']} mirrored panel pairs")
        score += 0.05

    # --- document-level registration ink (DIRECT fact, weak dieline signal) --
    if cs["registration_ink_used_on_page"]:
        positive.append(f"registration ink /Separation /All used by "
                        f"{cs['registration_painting_ops']} painting operations "
                        "(document-level, DIRECT)")
        score += 0.05
    else:
        missing.append("registration ink not used on this page")

    if cs["path_association"] != "DIRECT":
        missing.append("path-level /All association unavailable: "
                       + cs["alignment_reason"])

    # --- supporting only: can never carry a verdict -------------------------
    supporting: list[str] = []
    if FILENAME_HINT.search(filename):
        supporting.append(f"filename hint in {filename!r} (supporting only)")

    if graph["segments"] and graph["segments_axis_aligned_fraction"] < 0.1:
        contradictory.append("structural segments are almost entirely "
                             "non-orthogonal (ornamental linework)")

    if graph["panel_count"] == 0:
        contradictory.append("no closed structural geometry at all")

    # Gate: topology must carry it. Supporting evidence adds nothing to `score`
    # and can never qualify a region on its own.
    #
    # Route A - a large closed cut contour with orthogonal panels (ES3083).
    # Route B - overwhelming panel topology on a canvas so large that the carton
    #           is a small fraction of it (YB-1031: 36 shared edges, 80 dashed).
    route_a = bool(outer and contour_frac >= cfg.min_contour_area_frac
                   and ortho_panels >= cfg.min_panels)
    route_b = bool(graph["shared_edge_count"] >= cfg.route_b_min_shared_edges
                   and graph["dashed_segments"] >= cfg.route_b_min_dashed
                   and ortho_panels >= cfg.route_b_min_panels)
    qualifies = route_a or route_b
    route = "contour_and_panels" if route_a else ("panel_topology" if route_b
                                                  else None)

    # Meaningful structural evidence: the precondition for a human-review band.
    # A purely ornamental frame has none, and is rejected whatever its score.
    has_topology = bool(ortho_panels >= cfg.min_panels
                        or graph["shared_edge_count"] > 0
                        or graph["dashed_segments"] > 0)

    if qualifies and len(contradictory) >= cfg.borderline_min_contradictions:
        outcome = BORDERLINE          # cleared the gate, but evidence conflicts
    elif qualifies:
        outcome = LIKELY_DIELINE
    elif (has_topology
          and cfg.borderline_min_score <= score < cfg.borderline_max_score):
        outcome = BORDERLINE          # real evidence, insufficient to decide
    else:
        outcome = REJECTED
    return {
        "outcome": outcome,
        "qualifies": outcome == LIKELY_DIELINE,
        "qualifying_route": route,
        "score": round(score, 3),
        "confidence": round(min(1.0, score), 3),
        "has_meaningful_structural_evidence": has_topology,
        "config_fingerprint": cfg.fingerprint(),
        "config": asdict(cfg),
        "human_confirmed_outcome": None,
        "contour_area_fraction": round(contour_frac, 4),
        "positive_evidence": positive,
        "contradictory_evidence": contradictory,
        "missing_evidence": missing,
        "supporting_evidence_only": supporting,
        "outcome_policy": ("clearly above the gate -> LIKELY_DIELINE_STRUCTURE; "
                           "clearly below with no topology -> "
                           "REJECTED_NO_DIELINE_EVIDENCE; close to the gate or "
                           "conflicting evidence -> BORDERLINE_REVIEW_REQUIRED"),
    }


def build_dieline_candidate(graph: dict, surface: tuple, cs: dict,
                            filename: str, page: int,
                            cfg: DielineConfig = DEFAULT_DIELINE_CONFIG) -> dict:
    """Always returns a record. Every page keeps its raw score, all four evidence
    channels, its confidence, the configuration fingerprint, and a blank
    human-confirmed outcome — including rejections."""
    ev = evaluate_dieline(graph, surface, cs, filename, cfg)

    outer = graph.get("outer_contour")
    # The region is the largest connected STRUCTURAL COMPONENT. Anchoring it on
    # the largest closed polygon put ES3083's dieline box around its blank spec
    # table, because a real carton outline is never a single closed path.
    main = graph.get("main_structural_component")
    bbox = (main["bbox_pt"] if main
            else (outer["bbox_pt"] if outer else None))
    return {
        "outcome": ev["outcome"],
        "qualifies": ev["outcome"] == LIKELY_DIELINE,
        "region_id": f"{filename}-p{page}-dl00",
        "type": _inf(ev["outcome"], "page_structural_graph",
                     ev["positive_evidence"] or ev["missing_evidence"],
                     ev["score"]),
        "bbox_pt": bbox,
        "region_anchor": ("main_structural_component" if main
                          else "largest_closed_contour"),
        "structural_paths_in_region": (main["paths"] if main else None),
        "panel_count": graph["panel_count"],
        "shared_edge_count": graph["shared_edge_count"],
        "glue_flap_count": len(graph["glue_flap_candidates"]),
        "evidence": ev,
        "registration_ink_document_level": {
            "present": cs["registration_ink_used_on_page"],
            "painting_operations": cs["registration_painting_ops"],
            "tier": C.TIER_DIRECT,
        },
        "registration_path_association": {
            "status": cs["path_association"],
            "reason": cs["alignment_reason"],
            "tier": cs["tier_path_level"],
        },
        "human_confirmed": human_block(),
        "human_confirmed_outcome": None,      # only a person writes this
        "human_confirmed_is_dieline": None,
        "config_fingerprint": cfg.fingerprint(),
        "export_policy": ("analytical measurements only — no SVG, DXF or AI "
                          "export; historical paths are never imported into the "
                          "production dieline engine"),
    }
