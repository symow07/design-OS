"""ARIA Visual Inspector — VQ-1-RESET-1 Part A.

Judges rendered PIXELS, never metadata declarations. Two layers:

A. deterministic image analysis (``visual_extract`` + the metrics here);
B. multimodal visual judgment by a vision model that sees both the
   reference and the output.

The renderer never judges its own output: the inspector takes rendered
files as input, has no import of any fixture generator, and the vision
prompt is blind — it is never told what component the system believes it
drew (§7 forbids assuming PIPETTE_BULB).

Nothing here can emit AUTO_ACCEPTED. The best verdict is
PASSES_VISUAL_INSPECTION_PENDING_HUMAN_REVIEW.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

INSPECTION_SCHEMA = "visual_quality_inspection/1.0"
PLAN_SCHEMA = "visual_correction_plan/1.0"
SEMANTIC_SCHEMA = "component_semantic_classification/1.0"
LOOP_SCHEMA = "visual_correction_loop/1.0"

VISUALLY_REJECTED = "VISUALLY_REJECTED"
VISUALLY_WORSE = "VISUALLY_WORSE_THAN_PREVIOUS"
VISUALLY_IMPROVED_INSUFFICIENT = "VISUALLY_IMPROVED_BUT_INSUFFICIENT"
PASSES_PENDING_HUMAN = "PASSES_VISUAL_INSPECTION_PENDING_HUMAN_REVIEW"
VERDICTS = (VISUALLY_REJECTED, VISUALLY_WORSE,
            VISUALLY_IMPROVED_INSUFFICIENT, PASSES_PENDING_HUMAN)

#: §7 component semantics — never assume the serum implies a pipette bulb
COMPONENT_SEMANTICS = (
    "EXPOSED_RUBBER_PIPETTE_BULB",
    "BULB_WITH_INTEGRAL_FLARED_SKIRT",
    "DECORATIVE_OUTER_BULB_COVER",
    "COMPLETE_CLOSURE_OVERCAP",
    "OTHER_CLOSURE_FORM",
    "UNCERTAIN",
)
SEMANTIC_HUMAN_REQUIRED = "VQ_COMPONENT_SEMANTICS_HUMAN_CONFIRMATION_REQUIRED"
SEMANTIC_MIN_CONFIDENCE = 0.75

#: §21 blockers that must fail the fixture whenever they remain visible
VISUAL_BLOCKERS = (
    "VQ_BULB_SPEAR_OR_LEAF_SHAPE", "VQ_BULB_ARTIFICIAL_INSERTION_STEM",
    "VQ_COLLAR_RECTANGULAR_OPENING", "VQ_COLLAR_BOWED_BOX",
    "VQ_SHOULDER_POLYGONIZED", "VQ_BODY_ROUNDED_RECTANGLE_FALLBACK",
    "VQ_BASE_DETACHED", "VQ_COMPONENT_PROJECTION_MISMATCH",
    "VQ_CLOSURE_VISUALLY_TOP_HEAVY", "VQ_CONTOUR_DIVERGENCE_FROM_CONCEPT",
    "VQ_WORSE_THAN_PREVIOUS_BASELINE",
)

MAX_CORRECTION_PASSES = 3
MIN_CONTOUR_IMPROVEMENT = 0.02
VISION_OPERATION = "visual_inspection"
WEB_SEARCH_OPERATION = "web_geometry_search"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _sha(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


# --- layer A: deterministic --------------------------------------------------

def _resample(profile, n=200):
    vals = [v for v in profile if v is not None]
    if not vals:
        return [0.0] * n
    idx = [i for i, v in enumerate(profile) if v is not None]
    top, bot = idx[0], idx[-1]
    span = max(bot - top, 1)
    out = []
    for i in range(n):
        y = top + span * i / (n - 1)
        lo = int(y)
        hi = min(lo + 1, len(profile) - 1)
        a = profile[lo] if profile[lo] is not None else 0.0
        b = profile[hi] if profile[hi] is not None else a
        f = y - lo
        out.append(a * (1 - f) + b * f)
    scale = max(out) or 1.0
    return [v / scale for v in out]


def contour_metrics(ref_profile: list, out_profile: list,
                    n: int = 200) -> dict:
    """Scale- and height-normalized comparison of two half-width profiles.
    Both are normalized by their own maximum width, so this measures SHAPE,
    not size."""
    a, b = _resample(ref_profile, n), _resample(out_profile, n)
    diffs = [abs(x - y) for x, y in zip(a, b)]
    mean_d = sum(diffs) / len(diffs)
    max_d = max(diffs)
    # shape-context style: compare the normalized derivative sequences too
    da = [a[i + 1] - a[i] for i in range(len(a) - 1)]
    db = [b[i + 1] - b[i] for i in range(len(b) - 1)]
    grad_d = sum(abs(x - y) for x, y in zip(da, db)) / len(da)
    band = {}
    for name, lo, hi in (("upper_third", 0, n // 3),
                         ("middle_third", n // 3, 2 * n // 3),
                         ("lower_third", 2 * n // 3, n)):
        seg = diffs[lo:hi]
        band[name] = round(sum(seg) / max(len(seg), 1), 5)
    return {"normalized_contour_distance": round(mean_d, 5),
            "max_contour_distance": round(max_d, 5),
            "gradient_distance": round(grad_d, 5),
            "band_distance": band,
            "reference_profile_n": len(ref_profile),
            "output_profile_n": len(out_profile)}


def profile_shape_findings(profile: list, *, label: str) -> dict:
    """Structural reads taken from the pixels alone — deliberately
    component-agnostic so it cannot presuppose a bulb."""
    p = _resample(profile, 120)
    peak = p.index(max(p))
    n = len(p)
    # longest run of near-constant width (a cylinder), as a fraction
    run = best = 0
    for i in range(1, n):
        if abs(p[i] - p[i - 1]) < 0.012 and p[i] > 0.45:
            run += 1
            best = max(best, run)
        else:
            run = 0
    lower = p[int(n * 0.75):]
    flare = (max(lower) - min(lower)) if lower else 0.0
    straight_frac = best / n
    return {"label": label,
            "peak_at_fraction_from_top": round(peak / (n - 1), 4),
            "longest_constant_width_run": round(straight_frac, 4),
            "lower_flare": round(flare, 4),
            "top_closure_width": round(p[0], 4),
            "reads_as_cylinder_with_dome": straight_frac >= 0.20,
            "reads_as_teardrop": (0.30 <= peak / (n - 1) <= 0.75
                                  and straight_frac < 0.12)}


def parallelism_and_symmetry(prof: dict) -> dict:
    """Body-wall parallelism from the profile; symmetry only where both
    edges were actually measured (never claimed on an occluded side)."""
    hw = [v for v in prof.get("half_width", []) if v is not None]
    out = {"symmetry_measurable": "left" in prof and "right" in prof}
    if hw:
        lo, hi = int(len(hw) * 0.45), int(len(hw) * 0.9)
        band = hw[lo:hi] or hw
        mean = sum(band) / len(band)
        out["wall_band_mean_half_width"] = round(mean, 3)
        out["wall_band_max_deviation"] = round(
            max(abs(v - mean) for v in band), 3)
        out["walls_parallel_within_1pc"] = \
            max(abs(v - mean) for v in band) <= 0.01 * mean
    if out["symmetry_measurable"]:
        cx = prof["centerline_px"]
        devs = [abs((cx - lo) - (hi - cx))
                for lo, hi in zip(prof["left"], prof["right"])
                if lo is not None and hi is not None]
        out["mean_symmetry_error_px"] = round(
            sum(devs) / len(devs), 3) if devs else None
    else:
        out["symmetry_note"] = prof.get(
            "occlusion_note", "one edge not measurable in this image")
    return out


def curvature_continuity(profile: list, n: int = 120) -> dict:
    """Second differences of the normalized profile. A polygonized
    contour shows repeated near-zero curvature separated by spikes."""
    p = _resample(profile, n)
    d1 = [p[i + 1] - p[i] for i in range(len(p) - 1)]
    d2 = [abs(d1[i + 1] - d1[i]) for i in range(len(d1) - 1)]
    spikes = sum(1 for v in d2 if v > 0.02)
    flat = sum(1 for v in d2 if v < 1e-4)
    return {"mean_abs_second_difference": round(sum(d2) / len(d2), 6),
            "max_second_difference": round(max(d2), 6),
            "curvature_spikes": spikes,
            "flat_segments": flat,
            "polygonized": spikes >= 4 and flat >= n * 0.5}


def palette_distance(ref_path: str, out_path: str, bins: int = 6) -> dict:
    import numpy as np
    from PIL import Image

    def hist(p):
        a = np.asarray(Image.open(p).convert("RGB").resize((96, 96)))
        h, _ = np.histogramdd(a.reshape(-1, 3) / 256.0,
                              bins=(bins, bins, bins),
                              range=((0, 1), (0, 1), (0, 1)))
        h = h.ravel()
        return h / max(h.sum(), 1)
    a, b = hist(ref_path), hist(out_path)
    inter = float(sum(min(x, y) for x, y in zip(a, b)))
    return {"histogram_intersection": round(inter, 4),
            "palette_distance": round(1.0 - inter, 4)}


# --- layer B: multimodal -----------------------------------------------------

VISION_SYSTEM = """You are an independent visual inspector for packaging \
structure. You are shown a REFERENCE photograph of a real product and a \
GENERATED synthetic render. You did not create the render and you have no \
stake in it.

Describe what you actually see BEFORE judging. Never assume what a \
component is from the product category; name the shape you observe.

Reply with ONE JSON object only:
{
 "reference_description": "...",
 "output_description": "...",
 "top_component_observed_shape": "...",
 "component_semantics": {"classification": "<one of \
EXPOSED_RUBBER_PIPETTE_BULB|BULB_WITH_INTEGRAL_FLARED_SKIRT|\
DECORATIVE_OUTER_BULB_COVER|COMPLETE_CLOSURE_OVERCAP|OTHER_CLOSURE_FORM|\
UNCERTAIN>", "confidence": 0.0, "evidence": "..."},
 "same_component_type": true,
 "same_structural_family": true,
 "closure_proportions_physically_coherent": true,
 "output_appears_generic": false,
 "failing_component": "<BULB|COLLAR|NECK|SHOULDER|BODY|BASE|NONE>",
 "per_component_score": {"closure":0,"shoulder":0,"body":0,"silhouette":0},
 "reference_preservation_score": 0,
 "visual_findings": ["..."],
 "critical_blockers": ["..."],
 "confidence": 0.0
}
Scores are 0-10. Never output an acceptance verdict; the verdict is \
computed elsewhere."""


def run_vision_inspection(reference_path: str, output_path: str, *,
                          previous_path: str | None = None,
                          call_fn=None, model: str | None = None) -> dict:
    """One bounded multimodal call. ``call_fn`` is injectable so tests run
    deterministically without a provider."""
    from django.conf import settings

    from apps.pipeline.services.claude_service import (call_claude,
                                                       extract_json,
                                                       image_block_from_file)
    parts = [{"type": "text",
              "text": "IMAGE 1 = REFERENCE photograph of the real product."},
             image_block_from_file(reference_path),
             {"type": "text",
              "text": "IMAGE 2 = GENERATED synthetic structural render."},
             image_block_from_file(output_path)]
    if previous_path:
        parts += [{"type": "text",
                   "text": "IMAGE 3 = the PREVIOUS generated iteration, "
                           "already rejected by a human reviewer."},
                  image_block_from_file(previous_path)]
    parts.append({"type": "text",
                  "text": "Describe both images, then answer. JSON only."})
    fn = call_fn or call_claude
    resp = fn(VISION_SYSTEM, parts, max_tokens=1600,
              operation=VISION_OPERATION,
              model=model or (settings.QA_VISION_MODEL
                              or settings.CLAUDE_MODEL_FAST))
    data = resp if isinstance(resp, dict) else extract_json(resp)
    return data or {}


# --- §7 semantic gate ---------------------------------------------------------

def classify_component_semantics(profile_findings: dict,
                                 vision: dict | None) -> dict:
    """Combine the pixel read with the vision model's classification. A
    long constant-width run ending in a flare is not a teardrop whatever
    a model says, so the deterministic read can veto."""
    det = ("BULB_WITH_INTEGRAL_FLARED_SKIRT"
           if (profile_findings.get("reads_as_cylinder_with_dome")
               and profile_findings.get("lower_flare", 0) > 0.05)
           else "UNCERTAIN")
    v = (vision or {}).get("component_semantics") or {}
    vclass = v.get("classification", "UNCERTAIN")
    vconf = float(v.get("confidence") or 0.0)
    agree = vclass == det
    if det != "UNCERTAIN" and not agree and vclass in (
            "EXPOSED_RUBBER_PIPETTE_BULB",):
        # deterministic veto: the profile is not a bare tapering bulb
        resolved, conf = "UNCERTAIN", min(vconf, 0.5)
        note = ("deterministic profile shows a long constant-width run "
                "with a lower flare, which contradicts a bare tapering "
                "pipette bulb")
    elif agree:
        resolved, conf, note = det, min(0.95, (vconf + 0.8) / 2), \
            "deterministic profile and vision model agree"
    else:
        resolved, conf, note = vclass, vconf * 0.8, \
            "vision classification, deterministic read inconclusive"
    blocked = conf < SEMANTIC_MIN_CONFIDENCE or resolved == "UNCERTAIN"
    return {"schema_version": SEMANTIC_SCHEMA,
            "deterministic_classification": det,
            "vision_classification": vclass,
            "vision_confidence": round(vconf, 3),
            "resolved_classification": resolved,
            "confidence": round(conf, 3),
            "agreement": agree, "note": note,
            "evidence": v.get("evidence", ""),
            "profile_findings": profile_findings,
            "generation_blocked": blocked,
            "blocker": SEMANTIC_HUMAN_REQUIRED if blocked else None,
            "human_confirmed": False,
            "allowed_values": list(COMPONENT_SEMANTICS)}


# --- inspection --------------------------------------------------------------

def inspect(*, inspection_id: str, reference_paths: dict, output_path: str,
            output_id: str, reference_profile: list,
            output_profile_source: dict, previous: dict | None = None,
            vision: dict | None = None, extractor_validation: dict,
            component_identities: tuple = (),
            physical_packet: dict | None = None,
            previous_human_findings: tuple = ()) -> dict:
    """§6 — one structured, persistable inspection record."""
    out_prof = output_profile_source.get("half_width", [])
    metrics = contour_metrics(reference_profile, out_prof)
    shape = profile_shape_findings(out_prof, label=output_id)
    ref_shape = profile_shape_findings(reference_profile, label="reference")
    geom = parallelism_and_symmetry(output_profile_source)
    curve = curvature_continuity(out_prof)
    semantics = classify_component_semantics(ref_shape, vision)

    findings, blockers = [], []
    if shape["reads_as_teardrop"] and not ref_shape["reads_as_teardrop"]:
        findings.append("output top component reads as a teardrop/leaf "
                        "while the reference reads as a cylinder with a "
                        "rounded dome")
        blockers.append("VQ_BULB_SPEAR_OR_LEAF_SHAPE")
    if (shape["top_closure_width"] < 0.02
            and ref_shape["top_closure_width"] < 0.02
            and shape["lower_flare"] < 0.02 < ref_shape["lower_flare"]):
        findings.append("output lacks the reference's lower flare")
    if curve["polygonized"]:
        findings.append("output contour is polygonized")
        blockers.append("VQ_SHOULDER_POLYGONIZED")
    if metrics["normalized_contour_distance"] > 0.08:
        findings.append(
            f"normalized contour distance "
            f"{metrics['normalized_contour_distance']} exceeds 0.08")
        blockers.append("VQ_CONTOUR_DIVERGENCE_FROM_CONCEPT")
    for f in (vision or {}).get("critical_blockers", []) or []:
        if f not in blockers:
            blockers.append(f)
    vfind = list((vision or {}).get("visual_findings", []) or [])

    prev_d = (previous or {}).get(
        "deterministic", {}).get("normalized_contour_distance")
    delta = None
    regression = None
    if prev_d is not None:
        delta = round(prev_d - metrics["normalized_contour_distance"], 5)
        regression = ("IMPROVED" if delta > MIN_CONTOUR_IMPROVEMENT else
                      "WORSE" if delta < -1e-9 else "NO_MATERIAL_CHANGE")

    if regression == "WORSE":
        verdict = VISUALLY_WORSE
    elif blockers or semantics["generation_blocked"]:
        verdict = (VISUALLY_IMPROVED_INSUFFICIENT
                   if regression == "IMPROVED" else VISUALLY_REJECTED)
    else:
        verdict = PASSES_PENDING_HUMAN

    scores = (vision or {}).get("per_component_score", {}) or {}
    return {
        "schema_version": INSPECTION_SCHEMA,
        "inspection_id": inspection_id, "created_at": _now(),
        "reference_ids": {k: {"path": v, "sha256_16": _sha(v)}
                          for k, v in reference_paths.items()
                          if os.path.exists(v)},
        "output_id": output_id,
        "output": {"path": output_path,
                   "sha256_16": _sha(output_path)
                   if os.path.exists(output_path) else None},
        "component_identities": list(component_identities),
        "physical_packet_present": bool(physical_packet),
        "previous_human_findings": list(previous_human_findings),
        "extractor_validation": extractor_validation,
        "component_semantics": semantics,
        "deterministic": {**metrics, "output_shape": shape,
                          "reference_shape": ref_shape,
                          "geometry": geom, "curvature": curve},
        "multimodal": vision or {"unavailable": True},
        "per_component_score": {
            "closure": scores.get("closure"), "shoulder": scores.get(
                "shoulder"), "body": scores.get("body"),
            "silhouette": scores.get("silhouette")},
        "silhouette_score": scores.get("silhouette"),
        "closure_score": scores.get("closure"),
        "shoulder_score": scores.get("shoulder"),
        "body_score": scores.get("body"),
        "reference_preservation_score":
            (vision or {}).get("reference_preservation_score"),
        "visual_findings": findings + vfind,
        "critical_blockers": blockers,
        "improvement_against_previous": {
            "previous_output_id": (previous or {}).get("output_id"),
            "contour_distance_delta": delta, "direction": regression},
        "confidence": (vision or {}).get("confidence"),
        "recommended_correction_type": (
            "SEMANTIC_MODEL_REPLACEMENT" if semantics["generation_blocked"]
            else "CONTOUR_CORRECTION" if blockers else "NONE"),
        "verdict": verdict,
        "human_review_state": "NOT_REVIEWED",
        "note": "verdict is advisory; a human structural rejection always "
                "stands and no state here can auto-accept",
    }


# --- §8 correction planner ----------------------------------------------------

def build_correction_plan(inspection: dict, *, iteration: str,
                          prohibited: tuple = ()) -> dict:
    sem = inspection["component_semantics"]
    semantic_failure = sem["generation_blocked"] or not sem["agreement"]
    failed = ((inspection.get("multimodal") or {}).get("failing_component")
              or ("BULB" if "VQ_BULB_SPEAR_OR_LEAF_SHAPE"
                  in inspection["critical_blockers"] else "UNKNOWN"))
    if semantic_failure:
        cause = ("the component model itself is wrong: the visible "
                 "component was classified from an assumption rather "
                 "than from the reference")
        ctype, target = "SEMANTIC", "component model (replace, do not tune)"
        change = ("replace the component model after human semantic "
                  "confirmation; parameter tuning is prohibited")
    elif inspection["deterministic"]["curvature"]["polygonized"]:
        cause = "the contour is built from straight segments"
        ctype, target = "CONTOUR", "contour generator (segment -> curve)"
        change = "rebuild the contour with continuous curves"
    else:
        cause = ("the contour diverges from the reference beyond the "
                 "configured limit")
        ctype, target = "CONTOUR", "canonical half-profile parameters"
        change = "correct the half-profile against extracted landmarks"
    return {"schema_version": PLAN_SCHEMA, "iteration_identity": iteration,
            "inspection_id": inspection["inspection_id"],
            "failed_component": failed, "root_cause": cause,
            "problem_class": ctype, "target": target,
            "required_change": change,
            "prohibited_changes": list(prohibited) + [
                "tuning the frozen LEGACY_REJECTED_STRUCTURAL_GENERATOR "
                "formulas", "reusing the CORR-5 bulb model by default",
                "treating a semantic-model failure as a parameter tweak"],
            "expected_visual_improvement": (
                "the visible component matches the reference component "
                "type" if ctype == "SEMANTIC"
                else "normalized contour distance falls below 0.08"),
            "model_replacement_required": semantic_failure,
            "confidence": inspection.get("confidence"),
            "human_review_state": "NOT_REVIEWED"}


# --- §9 loop control ----------------------------------------------------------

def loop_should_stop(history: list) -> dict:
    """Bounded closed loop. Stops on regression, semantic uncertainty, a
    repeated blocker, or insufficient improvement — before the cap."""
    if not history:
        return {"stop": False, "reason": None, "passes_used": 0}
    last = history[-1]
    n = len(history)
    if n >= MAX_CORRECTION_PASSES:
        return {"stop": True, "reason": "MAX_CORRECTION_PASSES_REACHED",
                "passes_used": n}
    if last["verdict"] == VISUALLY_WORSE:
        return {"stop": True, "reason": "RESULT_BECAME_WORSE",
                "passes_used": n}
    if last["component_semantics"]["generation_blocked"]:
        return {"stop": True, "reason": "SEMANTIC_UNCERTAINTY_REMAINS",
                "passes_used": n}
    if n >= 2:
        a = set(history[-1]["critical_blockers"])
        b = set(history[-2]["critical_blockers"])
        if a and a & b:
            return {"stop": True, "reason": "SAME_BLOCKER_REPEATED_TWICE",
                    "passes_used": n, "repeated": sorted(a & b)}
        delta = history[-1]["improvement_against_previous"].get(
            "contour_distance_delta")
        if delta is not None and delta < MIN_CONTOUR_IMPROVEMENT:
            return {"stop": True,
                    "reason": "CONTOUR_IMPROVEMENT_BELOW_MINIMUM",
                    "passes_used": n}
    if last["verdict"] == PASSES_PENDING_HUMAN:
        return {"stop": True, "reason": "PENDING_HUMAN_REVIEW",
                "passes_used": n}
    return {"stop": False, "reason": None, "passes_used": n}


def persist(record: dict, out_dir: str, name: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name)
    with open(path, "w") as f:
        json.dump(record, f, indent=2)
    return path
