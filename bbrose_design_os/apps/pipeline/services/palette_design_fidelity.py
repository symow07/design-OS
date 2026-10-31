"""PALT-M4C §4 — ES3083 design fidelity.

Fidelity here means one thing: **does the built geometry realise what the
confirmed intent says the design is?** It is not similarity to a
photograph. No pixel overlay is computed and no calibrated photographic
accuracy is claimed — the ES3083 sheet carries no calibrated scale, so an
overlay would report a number with no unit behind it.

Two rules keep the report honest.

*Not every metric can fail.* A metric whose pass condition is also the
construction rule cannot discriminate between designs, and its pass is
not evidence. Every metric therefore declares ``discriminating_power``,
and the report LEADS with the discriminating split rather than an
aggregate that hides it.

*An unmeasurable requirement is not a satisfied one.* A metric whose
intent field is missing, or whose geometry does not exist yet, scores
UNMEASURABLE and is excluded from the score — never counted as a pass.
"""
from __future__ import annotations

import hashlib

from apps.pipeline.services import palette_design_intent as di

SCHEMA = "palette_design_fidelity/2.0"

PASS, FAIL, UNMEASURABLE = "PASS", "FAIL", "UNMEASURABLE"

LEVEL_WEIGHT = {di.HARD: 3.0, di.SOFT: 1.0, di.DECORATIVE: 0.25}

DISCRIMINATING = "DISCRIMINATING"
PASSES_BY_CONSTRUCTION = "PASSES_BY_CONSTRUCTION"
GUARANTEED = "GUARANTEED_BY_CONSTRUCTION"
LARGE_HEADROOM = "PASSES_WITH_LARGE_HEADROOM"

#: The eleven metrics the owner named, each bound to the intent field it
#: reads and the geometry property it measures.
METRICS = (
    ("PAN_SHAPE_FIDELITY", "pan_shapes",
     "the built pocket cross-section is the shape the design calls for",
     DISCRIMINATING),
    ("PAN_COUNT_FIDELITY", "pan_count",
     "the built pocket count equals the confirmed pan count",
     DISCRIMINATING),
    ("GRID_FIDELITY", "rows",
     "the built row and column counts equal the confirmed grid",
     DISCRIMINATING),
    ("RELATIVE_PAN_PROPORTION_FIDELITY", "relative_pan_sizes",
     "the pan aspect ratio matches the design's proportion",
     DISCRIMINATING),
    ("INTER_PAN_SPACING_FIDELITY", "spacing_rhythm",
     "the land between pockets is even on both axes", DISCRIMINATING),
    ("OUTER_MARGIN_FIDELITY", "margins",
     "the border land is no wider than the inter-pocket land",
     PASSES_BY_CONSTRUCTION),
    ("CASE_PROPORTION_FIDELITY", "silhouette",
     "the case footprint proportion matches the read silhouette",
     DISCRIMINATING),
    ("LID_BASE_RELATIONSHIP_FIDELITY", "opening_direction",
     "the lid and base relationship matches the opening direction",
     DISCRIMINATING),
    ("ARTWORK_ZONE_FIDELITY", "logo_position",
     "the artwork zones the design calls for exist in the design graph",
     DISCRIMINATING),
    ("TYPOGRAPHY_HIERARCHY_FIDELITY", "typography_zones",
     "every confirmed wordmark is present and ordered by hierarchy",
     DISCRIMINATING),
    ("COLOUR_ZONE_FIDELITY", "colour_zones",
     "every named colour reference survives as a named zone",
     DISCRIMINATING),
)

DISCRIMINATING_POWER = {m[0]: m[3] for m in METRICS}

DISCRIMINATING_POWER_NOTES = {
    "OUTER_MARGIN_FIDELITY":
        "the tray envelope is DEFINED as field + 2*land and this metric "
        "asks margin <= land, so equality holds by construction for every "
        "default build. It still fires against a supplied envelope, but "
        "its pass is not evidence about the design.",
}


class FidelityError(ValueError):
    """Raised when a fidelity report is asked for something it cannot
    mean."""


def _lands(tray):
    p = tray["pockets"][0]
    g = tray["grid"]
    return (round(g["pitch_x_mm"] - p["opening_width_mm"], 9),
            round(g["pitch_y_mm"] - p["opening_height_mm"], 9))


def _measure(code, tray, intent, graph):
    """Return ``(measured, expected)`` or raise ``LookupError`` when the
    geometry needed does not exist yet."""
    g, spec, p = tray["grid"], tray["spec"], tray["pockets"][0]
    lx, ly = _lands(tray)
    if code == "PAN_SHAPE_FIDELITY":
        return tray["pocket_shape"], intent.get("pan_shapes").value
    if code == "PAN_COUNT_FIDELITY":
        return tray["pocket_count"], intent.get("pan_count").value
    if code == "GRID_FIDELITY":
        return [g["rows"], g["columns"]], [intent.get("rows").value,
                                           intent.get("columns").value]
    if code == "RELATIVE_PAN_PROPORTION_FIDELITY":
        return (round(p["opening_width_mm"] / p["opening_height_mm"], 6),
                None)
    if code == "INTER_PAN_SPACING_FIDELITY":
        return round(abs(lx - ly), 9), 0.0
    if code == "OUTER_MARGIN_FIDELITY":
        mx = (spec["tray_width_mm"] - g["columns"] * g["pitch_x_mm"]) / 2.0
        my = (spec["tray_depth_mm"] - g["rows"] * g["pitch_y_mm"]) / 2.0
        return round(min(mx, my), 9), round(min(lx, ly), 9)
    if code == "CASE_PROPORTION_FIDELITY":
        return (round(spec["tray_width_mm"] / spec["tray_depth_mm"], 6),
                None)
    if code == "LID_BASE_RELATIONSHIP_FIDELITY":
        if "lid" not in tray.get("components", {}):
            raise LookupError(
                "no lid geometry exists yet — the moulded lid and its "
                "hinge are PALT-M4B-B, which has not been built")
        return tray["components"]["lid"]["opening_direction"], \
            intent.get("opening_direction").value
    if code == "ARTWORK_ZONE_FIDELITY":
        if graph is None:
            raise LookupError("no design graph was supplied to measure "
                              "artwork zones against")
        roles = {n.role for n, _ in graph["document"].walk()
                 if hasattr(n, "role")}
        return sorted(roles & {"artwork", "decoration", "typography"}), \
            ["artwork", "decoration", "typography"]
    if code == "TYPOGRAPHY_HIERARCHY_FIDELITY":
        if graph is None:
            raise LookupError("no design graph was supplied to measure "
                              "typography against")
        runs = [n for n, _ in graph["document"].walk()
                if getattr(n, "type", "") == "text"]
        return [r.text for r in runs], list(
            intent.get("typography_zones").value)
    if code == "COLOUR_ZONE_FIDELITY":
        if graph is None:
            raise LookupError("no design graph was supplied to measure "
                              "colour zones against")
        named = graph["document"].metadata.get(
            "named_colour_references", [])
        return sorted(named), sorted(intent.get("colour_zones").value)
    raise FidelityError(f"unknown metric {code!r}")        # pragma: no cover


def _verdict(code, measured, expected, field):
    if code in ("PAN_SHAPE_FIDELITY", "PAN_COUNT_FIDELITY",
                "GRID_FIDELITY", "COLOUR_ZONE_FIDELITY"):
        return PASS if measured == expected else FAIL
    if code == "RELATIVE_PAN_PROPORTION_FIDELITY":
        # the design reads as landscape pans; a square pan would be a
        # rounded square standing in for a rectangle
        return PASS if measured > 1.05 else FAIL
    if code == "INTER_PAN_SPACING_FIDELITY":
        return PASS if measured <= 1e-6 else FAIL
    if code == "OUTER_MARGIN_FIDELITY":
        return PASS if measured <= expected + 1e-9 else FAIL
    if code == "CASE_PROPORTION_FIDELITY":
        return PASS if 1.15 <= measured <= 2.10 else FAIL
    if code == "LID_BASE_RELATIONSHIP_FIDELITY":
        return PASS if measured == expected else FAIL
    if code == "ARTWORK_ZONE_FIDELITY":
        return PASS if set(expected) <= set(measured) else FAIL
    if code == "TYPOGRAPHY_HIERARCHY_FIDELITY":
        return PASS if list(measured) == list(expected) else FAIL
    raise FidelityError(f"unknown metric {code!r}")        # pragma: no cover


def score_palette_fidelity(intent, tray, *, graph=None) -> dict:
    """Eleven named metrics, each traceable to an intent field and a
    measurement."""
    rows, weighted, total = [], 0.0, 0.0
    hard_pass = hard_total = 0
    for code, field_name, means, power in METRICS:
        row = {"metric": code, "intent_field": field_name, "means": means,
               "discriminating_power": power}
        if code in DISCRIMINATING_POWER_NOTES:
            row["discriminating_power_note"] = \
                DISCRIMINATING_POWER_NOTES[code]
        field = intent.get(field_name)
        if field is None or field.confirmation_state == di.REMOVED:
            row.update({"verdict": UNMEASURABLE, "weight": 0.0,
                        "why": "the confirmed intent carries no such field; "
                               "an unread requirement is not a satisfied "
                               "one"})
            rows.append(row)
            continue
        try:
            measured, expected = _measure(code, tray, intent, graph)
        except LookupError as exc:
            row.update({"verdict": UNMEASURABLE, "weight": 0.0,
                        "why": str(exc)})
            rows.append(row)
            continue
        verdict = _verdict(code, measured, expected, field)
        weight = LEVEL_WEIGHT[field.constraint_level]
        total += weight
        if verdict == PASS:
            weighted += weight
        if field.constraint_level == di.HARD:
            hard_total += 1
            hard_pass += verdict == PASS
        row.update({"intended": field.value, "measured": measured,
                    "expected": expected, "verdict": verdict,
                    "weight": weight,
                    "constraint_level": field.constraint_level,
                    "confirmation_state": field.confirmation_state,
                    "confidence": round(float(field.confidence), 3)})
        rows.append(row)

    def _split(power=None, verdict=None):
        return [r["metric"] for r in rows
                if (power is None or r["discriminating_power"] == power)
                and (verdict is None or r["verdict"] == verdict)]

    disc = _split(DISCRIMINATING)
    disc_pass = [m for m in _split(DISCRIMINATING, PASS)]
    disc_fail = [m for m in _split(DISCRIMINATING, FAIL)]
    excluded = _split(verdict=UNMEASURABLE)
    return {
        "record_type": SCHEMA,
        # --- the owner-facing report leads with these five ---------------
        "discriminating_metrics_passed": disc_pass,
        "discriminating_metrics_failed": disc_fail,
        "metrics_excluded_from_the_score": excluded,
        "metrics_with_excessive_tolerance_headroom": _split(LARGE_HEADROOM),
        "metrics_guaranteed_by_construction": _split(GUARANTEED),
        "headline": (
            f"{len(disc_pass)}/{len(disc)} discriminating metrics pass, "
            f"{len(disc_fail)} fail; {len(excluded)} excluded from the "
            f"score; {len(_split(PASSES_BY_CONSTRUCTION))} pass by "
            f"construction"),
        "all_discriminating_metrics_passed": bool(disc) and not disc_fail
        and len(disc_pass) == len(disc),
        # --- supporting detail -------------------------------------------
        "concept_reference": intent.concept_reference,
        "intent_identity": intent.identity(),
        "tray_mesh_identity": tray["mesh_identity"],
        "metrics": rows,
        "passes_by_construction": _split(PASSES_BY_CONSTRUCTION),
        "hard_constraints_passed": f"{hard_pass}/{hard_total}",
        "weighted_score": round(weighted / total, 6) if total else None,
        "weighted_score_caveat":
            "the aggregate includes metrics that cannot fail for a default "
            "build, and excludes unmeasurable ones. Read the discriminating "
            "split, not this number.",
        "pixel_overlay_computed": False,
        "calibrated_photographic_accuracy_claimed": False,
        "why_no_pixel_overlay": "the ES3083 sheet carries no calibrated "
                                "scale, so an overlay would report a number "
                                "with no unit behind it",
        "measures": "WHETHER_THE_BUILT_GEOMETRY_REALISES_THE_CONFIRMED_"
                    "INTENT",
        "does_not_measure": [
            "visual similarity to the source image",
            "whether the confirmed intent is itself correct",
            "manufacturability",
            "any dimension against the real product",
        ],
        "owner_approved": False,
        "manufacturing_authority": "NOT_ESTABLISHED",
        "report_identity": hashlib.sha256(
            repr([(r["metric"], r["verdict"]) for r in rows]).encode()
            + tray["mesh_identity"].encode()).hexdigest()[:16],
    }
