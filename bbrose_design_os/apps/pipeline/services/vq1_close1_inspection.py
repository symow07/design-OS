"""VQ-1-MASTER-CLOSE-1 §8/§10/§11/§12/§14 — evidence-assisted structural
inspection of the frozen M3 candidate.

The two inspectors are independent: separate identities, separate system
prompts, separate calls, and B never receives A's response. Neither may
judge colour, finish, gloss, shading or material realism (§9C — deferred to
VQ-3), and neither may lower a STRUCTURAL score because a reference-faithful
feature reads faintly under neutral fills (§8).

The inspectors are given the measured deviations rather than being told what
to conclude about them. Nothing here can emit HUMAN_ACCEPTED, MANUFACTURABLE
or PRODUCTION_READY.
"""
from __future__ import annotations

import hashlib
import json

INSPECTION_SCHEMA = "vq1_evidence_assisted_structural_inspection/1.0"
CONSISTENCY_SCHEMA = "vq1_final_structural_scorecard_consistency/1.0"

PASSES_PENDING_HUMAN = "PASSES_STRUCTURAL_INSPECTION_PENDING_HUMAN_REVIEW"
STRUCTURAL_DEFECT = "STRUCTURAL_DEFECT_PRESENT"
INSPECTION_NOT_PERFORMED = "INSPECTION_NOT_PERFORMED_INPUT_QUALITY_FAILED"

TRUE_DEFECT = "TRUE_STRUCTURAL_DEFECT"
LOW_SALIENCE = "LOW_SALIENCE_UNDER_NEUTRAL_PRESENTATION"

CATEGORIES = ("rounded_dome", "dark_shaft", "lower_flare", "flare_symmetry",
              "collar_sleeve", "collar_closure_junction", "neck_transition",
              "shoulder_transition", "complete_closure_coherence", "overall")

REQUIRED_FIELDS = ("structural_score", "structural_finding",
                   "critical_structural_blocker", "confidence",
                   "low_salience_observation", "material_observation_excluded",
                   "deterministic_evidence_consulted")

#: §14 rejection codes
C_SCORE_BELOW_10 = "VQ1_PASS_VERDICT_CONTAINS_SCORE_BELOW_10"
C_OVERALL_INCONSISTENT = "VQ1_OVERALL_10_WITH_CATEGORY_BELOW_10"
C_TEN_WITH_DEFECT = "VQ1_SCORE_10_CONTAINS_GENUINE_CONTOUR_CRITICISM"
C_MATERIAL_LEAK = "VQ1_MATERIAL_OBSERVATION_AFFECTED_STRUCTURAL_SCORE"
C_SALIENCE_PENALTY = "VQ1_LOW_SALIENCE_ALONE_REDUCED_STRUCTURAL_SCORE"
C_INPUT_FAILED = "VQ1_INPUT_QUALITY_FAILED"
C_EVIDENCE_IDENTITY = "VQ1_EVIDENCE_IDENTITY_INCORRECT"
C_CONTRADICTS_DETERMINISTIC = "VQ1_VISUAL_FINDING_CONTRADICTS_DETERMINISTIC"
C_MISSING_FIELD = "VQ1_SCORECARD_FIELD_MISSING"
C_MISSING_CATEGORY = "VQ1_SCORECARD_CATEGORY_MISSING"

#: words that mark a MATERIAL observation, which may never move a structural
#: score (§9C). Kept separate from geometry vocabulary on purpose.
MATERIAL_WORDS = ("rose-gold", "rose gold", "metallic", "gloss", "glossy",
                  "specular", "reflection", "reflective", "sheen", "finish",
                  "colour", "color", "shading", "shaded", "texture",
                  "photoreal", "photorealistic", "lighting", "highlight",
                  "matte", "frosted appearance", "material realism")

#: words that mark a genuine GEOMETRY criticism, which invalidates a 10
GEOMETRY_DEFECT_WORDS = ("missing", "absent", "omitted", "not reproduced",
                         "does not reproduce", "step", "stepped", "ledge",
                         "discontinuity", "discontinuous", "polygonal",
                         "faceted", "kinked", "asymmetric", "asymmetry",
                         "detached", "disconnected", "ring", "adapter",
                         "misaligned", "wrong proportion", "incorrect radius")

#: §8 — the rule handed to both inspectors, verbatim in each system prompt
SALIENCE_RULE = (
    "A reference-faithful feature may receive 10/10 when its contour matches "
    "the validated reference, its proportions match, its continuity matches, "
    "no structural defect exists, and its low visual salience results only "
    "from the removal of photographic shading. Low visual salience under "
    "neutral flat fill is NOT automatically a structural defect. You must "
    "still report any genuine contour mismatch that is visible in the "
    "analytical evidence, and a genuine contour mismatch DOES invalidate a "
    "score of 10."
)

SCOPE_RULE = (
    "You are judging STRUCTURAL GEOMETRY ONLY: silhouette, widths, "
    "proportions, curvature, continuity, symmetry and component "
    "relationships. You must NOT judge colour, finish, gloss, reflection, "
    "metallic appearance, texture, material realism, lighting or "
    "photographic realism. Those are deferred to a separate workstream and "
    "must never move a structural score. The candidate is a deliberately "
    "neutral flat-fill structural fixture; it is not attempting to look like "
    "a photograph."
)

_OUTPUT_CONTRACT = (
    "Return JSON only, with this exact shape:\n"
    '{"scores": {"<category>": {"structural_score": <int 1-10>, '
    '"structural_finding": "<one paragraph>", '
    '"critical_structural_blocker": <bool>, "confidence": <0-1>, '
    '"low_salience_observation": <bool>, '
    '"material_observation_excluded": <bool>, '
    '"deterministic_evidence_consulted": ["<evidence name>", ...]}}, '
    '"verdict": "PASSES_STRUCTURAL_INSPECTION_PENDING_HUMAN_REVIEW" or '
    '"STRUCTURAL_DEFECT_PRESENT", '
    '"defect_classifications": [{"observation": "...", '
    '"classification": "TRUE_STRUCTURAL_DEFECT" or '
    '"LOW_SALIENCE_UNDER_NEUTRAL_PRESENTATION", "evidence": "..."}]}\n'
    "Categories, all required: " + ", ".join(CATEGORIES) + ".\n"
    "Never output HUMAN_ACCEPTED, MANUFACTURABLE or PRODUCTION_READY."
)

INSPECTOR_A_ID = "STRUCTURAL_REFERENCE_FIDELITY_CRITIC"
INSPECTOR_A_SYSTEM = (
    "You are " + INSPECTOR_A_ID + ", inspecting a synthetic structural "
    "fixture against a reference photograph of a real product.\n\n"
    "Your single question for every component is: does the GEOMETRY of the "
    "fixture match the geometry of the reference?\n\n"
    + SCOPE_RULE + "\n\n" + SALIENCE_RULE + "\n\n"
    "You are given analytical evidence — normalized silhouettes, contour "
    "overlays, component masks, enlarged region overlays, and width and "
    "curvature diagrams carrying measured numbers. When a flat silhouette "
    "looks subtle, consult the overlays and the width/curvature evidence "
    "before scoring; they are the higher authority on contour position. "
    "Do not infer geometry from the photograph's shading.\n\n"
    "You have no knowledge of any previous inspection, score or verdict, and "
    "none exists for you to defer to. Judge only what this evidence shows.\n\n"
    + _OUTPUT_CONTRACT
)

INSPECTOR_B_ID = "STRUCTURAL_ADVERSARIAL_EVIDENCE_AUDITOR"
INSPECTOR_B_SYSTEM = (
    "You are " + INSPECTOR_B_ID + ". Your job is to ATTACK the evidence "
    "package you are shown and find what it might be concealing.\n\n"
    "Challenge specifically: the validity of the contour extraction; the "
    "validity of the neck inset measurement; the validity of the shoulder "
    "curvature measurement; hidden geometry deviations; asymmetry; false "
    "rings; adapters; a stepped collar; disconnected components; contour "
    "discontinuities; incorrect reference scaling; annotations positioned so "
    "as to conceal a mismatch; and any unsupported claim of exactness.\n\n"
    "Treat every number printed on a diagram as a claim to be checked "
    "against the curves drawn beside it, not as a fact.\n\n"
    + SCOPE_RULE + "\n\n" + SALIENCE_RULE + "\n\n"
    "For every criticism you raise you must classify it as either "
    "TRUE_STRUCTURAL_DEFECT (a real geometry mismatch you can point to in "
    "the evidence) or LOW_SALIENCE_UNDER_NEUTRAL_PRESENTATION (correct "
    "geometry that merely reads faintly without shading). Do not inflate a "
    "presentation complaint into a geometry defect, and do not excuse a real "
    "geometry defect as a presentation artifact.\n\n"
    "You have not been shown, and will not be shown, any other inspector's "
    "findings, scores or verdict.\n\n"
    + _OUTPUT_CONTRACT
)


def sha16(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:16]


def delivered_size(size, cap: int = 1568):
    w, h = size
    long_edge = max(w, h)
    if long_edge <= cap:
        return [w, h]
    k = cap / long_edge
    return [round(w * k), round(h * k)]


def check_floors(evidence: dict, floors: dict, mapping: dict) -> dict:
    """§10 — floors are checked against the DELIVERED bytes, never the native
    file, so an enlarged or downscaled crop can never pose as legible."""
    results, failures = {}, []
    for slot, ev_key in mapping.items():
        ev = evidence.get(ev_key)
        if ev is None:
            failures.append({"slot": slot, "code": "VQ1_REQUIRED_EVIDENCE_MISSING"})
            continue
        dw, dh = delivered_size(ev["size"])
        need = floors[slot]
        ok = True
        if "min_h" in need and dh < need["min_h"]:
            ok = False
        if "min_w" in need and dw < need["min_w"]:
            ok = False
        results[slot] = {"evidence": ev_key, "native_size": ev["size"],
                         "delivered_size": [dw, dh], "requirement": need,
                         "passes": ok, "sha256": ev.get("sha256"),
                         "is_native_resolution":
                             ev.get("is_native_resolution", True),
                         "enlargement_factor": ev.get("enlargement_factor")}
        if not ok:
            failures.append({"slot": slot,
                             "code": "VQ1_INPUT_RESOLUTION_INSUFFICIENT",
                             "delivered_size": [dw, dh],
                             "requirement": need})
    return {"record_type": "vq1_close1_input_quality/1.0",
            "floors": floors, "slots": results,
            "failures": failures, "passes": not failures}


def build_parts(images: list) -> list:
    """One labelled image block per evidence item, in a fixed order."""
    from apps.pipeline.services.claude_service import image_block_from_file
    parts = []
    for i, (label, path, note) in enumerate(images, start=1):
        parts.append({"type": "text",
                      "text": f"IMAGE {i} = {label}. {note}"})
        parts.append(image_block_from_file(path))
    return parts


def run_inspector(system_prompt: str, images: list, measurements: dict, *,
                  call_fn=None, model=None) -> dict:
    from django.conf import settings

    from apps.pipeline.services.claude_service import call_claude, extract_json
    parts = build_parts(images)
    parts.append({"type": "text", "text":
                  "MEASURED DETERMINISTIC EVIDENCE (source-pixel space, "
                  "normalized by body width 343 px). These are measurements, "
                  "not conclusions — judge whether they describe a "
                  "structural defect:\n"
                  + json.dumps(measurements, indent=1)
                  + "\n\nNow produce your scorecard. JSON only."})
    fn = call_fn or call_claude
    resp = fn(system_prompt, parts, max_tokens=4000,
              operation="vq1_close1_structural_inspection",
              model=model or (getattr(settings, "QA_VISION_MODEL", None)
                              or settings.CLAUDE_MODEL_FAST))
    data = resp if isinstance(resp, dict) else extract_json(resp)
    return data or {}


# --- §14 scorecard consistency -------------------------------------------------

def _mentions(text: str, words) -> list:
    low = (text or "").lower()
    return [w for w in words if w in low]


def check_scorecard(name: str, result: dict, input_quality: dict,
                    deterministic: dict) -> dict:
    """Reject a result whose own content contradicts its verdict."""
    codes, detail = [], []
    scores = (result or {}).get("scores") or {}

    if not input_quality.get("passes"):
        codes.append(C_INPUT_FAILED)

    for cat in CATEGORIES:
        if cat not in scores:
            codes.append(C_MISSING_CATEGORY)
            detail.append({"category": cat, "code": C_MISSING_CATEGORY})
            continue
        row = scores[cat]
        for f in REQUIRED_FIELDS:
            if f not in row:
                codes.append(C_MISSING_FIELD)
                detail.append({"category": cat, "field": f,
                               "code": C_MISSING_FIELD})

    verdict = (result or {}).get("verdict")
    numeric = {c: scores[c].get("structural_score")
               for c in CATEGORIES if c in scores}
    below = {c: v for c, v in numeric.items()
             if isinstance(v, int) and v < 10}

    if verdict == PASSES_PENDING_HUMAN and below:
        codes.append(C_SCORE_BELOW_10)
        detail.append({"code": C_SCORE_BELOW_10, "categories": below})

    if numeric.get("overall") == 10 and below:
        codes.append(C_OVERALL_INCONSISTENT)
        detail.append({"code": C_OVERALL_INCONSISTENT, "categories": below})

    for cat, row in scores.items():
        finding = row.get("structural_finding", "")
        score = row.get("structural_score")
        geo = _mentions(finding, GEOMETRY_DEFECT_WORDS)
        mat = _mentions(finding, MATERIAL_WORDS)
        if score == 10 and geo and not row.get("low_salience_observation"):
            codes.append(C_TEN_WITH_DEFECT)
            detail.append({"category": cat, "code": C_TEN_WITH_DEFECT,
                           "geometry_terms": geo})
        if mat and isinstance(score, int) and score < 10 \
                and not row.get("material_observation_excluded"):
            codes.append(C_MATERIAL_LEAK)
            detail.append({"category": cat, "code": C_MATERIAL_LEAK,
                           "material_terms": mat})
        if (isinstance(score, int) and score < 10
                and row.get("low_salience_observation") and not geo):
            codes.append(C_SALIENCE_PENALTY)
            detail.append({"category": cat, "code": C_SALIENCE_PENALTY})

    # a visual claim that the deterministic evidence refutes
    for cat, row in scores.items():
        f = (row.get("structural_finding") or "").lower()
        if cat == "neck_transition" and ("step" in f or "ledge" in f) \
                and deterministic.get("neck_is_smooth_waist"):
            codes.append(C_CONTRADICTS_DETERMINISTIC)
            detail.append({"category": cat,
                           "code": C_CONTRADICTS_DETERMINISTIC,
                           "note": "claims a stepped ledge; the dense "
                                   "reference is a smooth monotonic waist"})

    return {"record_type": CONSISTENCY_SCHEMA, "inspector": name,
            "codes": sorted(set(codes)), "detail": detail,
            "scores": numeric, "verdict": verdict,
            "consistent": not codes,
            "all_categories_10": bool(numeric)
            and all(v == 10 for v in numeric.values())
            and len(numeric) == len(CATEGORIES)}


def substantive_disagreement(a_res: dict, b_res: dict) -> dict:
    """§16 — "inspectors disagree on geometry correctness".

    Matching verdict STRINGS are not agreement. Two inspectors can both say
    PASSES while one calls a deviation a true structural defect and the other
    calls the same deviation a presentation artifact. That is a disagreement
    about geometry and it must block release.
    """
    def true_defects(res):
        return [c for c in (res or {}).get("defect_classifications", []) or []
                if c.get("classification") == TRUE_DEFECT]

    a_true, b_true = true_defects(a_res), true_defects(b_res)
    a_scores = {k: v.get("structural_score")
                for k, v in ((a_res or {}).get("scores") or {}).items()}
    b_scores = {k: v.get("structural_score")
                for k, v in ((b_res or {}).get("scores") or {}).items()}
    diverging = {k: [a_scores.get(k), b_scores.get(k)]
                 for k in set(a_scores) | set(b_scores)
                 if isinstance(a_scores.get(k), int)
                 and isinstance(b_scores.get(k), int)
                 and abs(a_scores[k] - b_scores[k]) >= 2}
    disagree = bool(len(a_true) != len(b_true) or diverging)
    return {"inspector_a_true_defects": len(a_true),
            "inspector_b_true_defects": len(b_true),
            "a_true_defect_observations": [c.get("observation")
                                           for c in a_true],
            "b_true_defect_observations": [c.get("observation")
                                           for c in b_true],
            "categories_diverging_by_2_or_more": diverging,
            "disagree_on_geometry_correctness": disagree}


def release_decision(a_chk: dict, b_chk: dict, dense: dict,
                     raster_ok: bool, disagreement: dict | None = None) -> dict:
    """§15/§16 — the release state, or the honest hard stop."""
    reasons = []
    if (disagreement or {}).get("disagree_on_geometry_correctness"):
        reasons.append("INSPECTORS_DISAGREE_ON_GEOMETRY_CORRECTNESS")
    if not dense.get("all_gates_pass"):
        reasons.append("DENSE_GEOMETRY_CONFIRMATION_FAILED")
    if not raster_ok:
        reasons.append("CERTIFIED_RASTER_STABILITY_NOT_PASSED")
    for nm, chk in (("A", a_chk), ("B", b_chk)):
        if not chk.get("consistent"):
            reasons.append(f"INSPECTOR_{nm}_SCORECARD_INCONSISTENT")
        if chk.get("verdict") != PASSES_PENDING_HUMAN:
            reasons.append(f"INSPECTOR_{nm}_DID_NOT_PASS")
        if not chk.get("all_categories_10"):
            reasons.append(f"INSPECTOR_{nm}_CATEGORY_BELOW_10")
    if a_chk.get("verdict") != b_chk.get("verdict"):
        reasons.append("INSPECTORS_DISAGREE")
    reasons = sorted(set(reasons))
    return {"state": ("VQ1_MASTER_STRUCTURAL_CANDIDATE_PENDING_HUMAN_REVIEW"
                      if not reasons
                      else "VQ1_MASTER_HARD_STOP_REVIEW_REQUIRED"),
            "blocking_reasons": reasons,
            "human_accepted": False, "manufacturable": False,
            "production_ready": False}
