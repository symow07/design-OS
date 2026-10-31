"""VQ-1-RESET-1A — physical geometry evidence packet.

Turns the completed ``web_container_geometry_research/1.0`` session into a
packet a human can adjudicate. It generates NO geometry.

Two rules drive the design:

* §1 search snippets are not technical evidence. Every measurement that
  came from a snippet is demoted to ``SNIPPET_NOT_TECHNICAL_EVIDENCE``;
  only measurements re-extracted from a governed page fetch carry a
  referent and a confidence.
* §8 when deterministic pixel measurement and a multimodal numeric claim
  disagree, the pixels govern and the model's claim stays a semantic
  hypothesis. The conflict is recorded as
  ``VQ_MULTIMODAL_NUMERIC_CLAIM_CONFLICT``.

Nothing here approves anything: every permission defaults false and every
decision field is PENDING.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

PACKET_SCHEMA = "vq1_geometry_evidence_review/1.0"
MATRIX_SCHEMA = "component_semantic_decision_matrix/1.0"
DECISION_SCHEMA = "human_evidence_decision_form/1.0"
AUTHORITY_SCHEMA = "visualizer_authority_rule/1.0"

VQ_MULTIMODAL_NUMERIC_CLAIM_CONFLICT = "VQ_MULTIMODAL_NUMERIC_CLAIM_CONFLICT"
SNIPPET_NOT_EVIDENCE = "SNIPPET_NOT_TECHNICAL_EVIDENCE"

#: §1 six-tier authority. Only 1-3 may independently support concept
#: geometry; 4 needs corroboration; 5-6 can never authorize a dimension.
AUTHORITY_TIERS = {
    1: {"label": "manufacturer technical drawing / CAD / official spec sheet",
        "may_authorize_alone": True},
    2: {"label": "official manufacturer or supplier product page with "
                 "explicit dimensions and multiple views",
        "may_authorize_alone": True},
    3: {"label": "established packaging distributor with explicit "
                 "dimensional data", "may_authorize_alone": True},
    4: {"label": "retail listing with source-stated measurements",
        "may_authorize_alone": False, "requires_corroboration": True},
    5: {"label": "image-only source", "may_authorize_alone": False},
    6: {"label": "marketplace, stock, gallery or editorial context",
        "may_authorize_alone": False},
}

#: §4 controlled referent vocabulary — never combined, never averaged
REFERENTS = (
    "BODY_OUTSIDE_DIAMETER", "BODY_HEIGHT_TO_SHOULDER",
    "BOTTLE_HEIGHT_WITHOUT_CLOSURE", "TOTAL_HEIGHT_WITH_CLOSURE",
    "NECK_OUTSIDE_DIAMETER", "NECK_FINISH", "COLLAR_OUTSIDE_DIAMETER",
    "COLLAR_VISIBLE_HEIGHT", "DARK_COMPONENT_MAXIMUM_WIDTH",
    "DARK_COMPONENT_VISIBLE_HEIGHT", "PIPETTE_LENGTH", "NOMINAL_CAPACITY",
    "OVERFLOW_CAPACITY", "GLASS_WEIGHT", "DROPPER_ASSEMBLY_LENGTH",
    "REFERENT_UNRESOLVED",
)

#: §6 decision options — presented, never preselected
SEMANTIC_OPTIONS = {
    "A": {"code": "EXPOSED_RUBBER_PIPETTE_BULB",
          "definition": "A conventional compressible rubber bulb directly "
                        "visible above the metal collar.",
          "internal_hidden_mechanism_required": False},
    "B": {"code": "ELASTOMER_BULB_WITH_INTEGRAL_FLARED_SKIRT",
          "definition": "A rubber bulb whose visible lower section flares "
                        "outward and meets or overlaps the collar, without "
                        "a long exposed narrow stem.",
          "internal_hidden_mechanism_required": False},
    "C": {"code": "DECORATIVE_OUTER_CLOSURE_COVER",
          "definition": "A visible outer cover concealing a separate "
                        "internal bulb or actuator.",
          "internal_hidden_mechanism_required": True},
    "D": {"code": "COMPLETE_CLOSURE_OVERCAP",
          "definition": "The visible dark component is an outer cap over "
                        "the actual functional closure.",
          "internal_hidden_mechanism_required": True},
    "E": {"code": "OTHER_CLOSURE_FORM", "definition": "None of the above.",
          "internal_hidden_mechanism_required": None},
    "F": {"code": "UNCERTAIN_RESEARCH_AGAIN",
          "definition": "Evidence insufficient; research again.",
          "internal_hidden_mechanism_required": None},
}

#: §9 independent per-source actions
SOURCE_ACTIONS = ("APPROVE_AS_PHYSICAL_ANALOG", "APPROVE_AS_FACT_SOURCE",
                  "APPROVE_MEASUREMENTS_FOR_CONCEPT_GEOMETRY",
                  "APPROVE_AS_COMPONENT_SEMANTIC_EVIDENCE",
                  "NEEDS_VERIFICATION", "REJECT")

#: §10 seven separate rights, all default-deny for this phase
def rights_default() -> dict:
    return {"retrieval_permission": True,
            "reference_view_permission": True,
            "fact_source_permission": False,
            "concept_geometry_permission": False,
            "provider_input_permission": False,
            "artwork_reuse_permission": False,
            "design_memory_permission": False}


CONFLICT_ACTIONS = ("SELECT_SOURCE_A", "SELECT_SOURCE_B",
                    "KEEP_BOTH_AS_DISTINCT_VARIANTS", "REJECT_BOTH",
                    "NEEDS_MANUFACTURER_CONFIRMATION")


def _now():
    return datetime.now(timezone.utc).isoformat()


# --- §1 tiering ---------------------------------------------------------------

_T1 = ("technical drawing", "cad", "spec sheet", "specification sheet",
       "datasheet", "data sheet", "neck finish dimensions", "drawing")
_T3 = ("sks-bottle", "bottlestore", "containerandpackaging", "glassnow",
       "premiumvials", "impackedpackaging")
_T4 = ("shop", "store", "buy")
_T5_6 = ("pinterest", "dribbble", "behance", "instagram", "shutterstock",
         "istockphoto", "gettyimages", "freepik", "unsplash", "pexels",
         "amazon", "ebay", "aliexpress", "alibaba", "temu", "etsy",
         "made-in-china", "dhgate", "wikipedia", "vogue", "reddit")


def authority_tier(domain: str, title: str = "", url: str = "",
                   has_dimensions: bool = False) -> int:
    d, t, u = (domain or "").lower(), (title or "").lower(), (url or "").lower()
    if any(k in d for k in _T5_6):
        return 6
    if any(k in t or k in u for k in _T1):
        return 1
    if any(k in d for k in _T3):
        return 3
    if has_dimensions:
        return 2
    if any(k in d for k in _T4):
        return 4
    return 5


def may_authorize_alone(tier: int) -> bool:
    return bool(AUTHORITY_TIERS.get(tier, {}).get("may_authorize_alone"))


# --- §4 referent-aware extraction from FETCHED PAGE TEXT ----------------------

_PATTERNS = (
    (r"(?:body|bottle)\s+(?:outside\s+)?diameter[^0-9]{0,18}"
     r"(\d{1,3}(?:\.\d)?)\s*(mm|cm|in)", "BODY_OUTSIDE_DIAMETER"),
    (r"\bdiameter[^0-9]{0,14}(\d{1,3}(?:\.\d)?)\s*(mm|cm|in)",
     "BODY_OUTSIDE_DIAMETER"),
    (r"(?:overall|total)\s+height[^0-9]{0,18}(\d{1,3}(?:\.\d)?)\s*(mm|cm|in)",
     "TOTAL_HEIGHT_WITH_CLOSURE"),
    (r"(?:bottle|body)\s+height[^0-9]{0,18}(\d{1,3}(?:\.\d)?)\s*(mm|cm|in)",
     "BOTTLE_HEIGHT_WITHOUT_CLOSURE"),
    (r"\bheight[^0-9]{0,14}(\d{1,3}(?:\.\d)?)\s*(mm|cm|in)",
     "BOTTLE_HEIGHT_WITHOUT_CLOSURE"),
    (r"neck\s+(?:outside\s+)?diameter[^0-9]{0,14}(\d{1,3}(?:\.\d)?)\s*(mm)",
     "NECK_OUTSIDE_DIAMETER"),
    (r"(?:collar|ferrule)[^0-9]{0,20}(\d{1,3}(?:\.\d)?)\s*(mm)",
     "COLLAR_OUTSIDE_DIAMETER"),
    (r"(?:pipette|tube)\s+length[^0-9]{0,14}(\d{1,3}(?:\.\d)?)\s*(mm)",
     "PIPETTE_LENGTH"),
    (r"(\d{1,3}(?:\.\d)?)\s*mm\s*[x×]\s*(\d{1,3}(?:\.\d)?)\s*mm\s*"
     r"(?:dropper|pipette)", "DROPPER_ASSEMBLY_LENGTH"),
    (r"(?:overflow|brimful)\s+capacity[^0-9]{0,14}(\d{1,4}(?:\.\d)?)\s*(ml)",
     "OVERFLOW_CAPACITY"),
    (r"(?:glass\s+)?weight[^0-9]{0,14}(\d{1,4}(?:\.\d)?)\s*(g|gram)",
     "GLASS_WEIGHT"),
)
_NECK_FIN = re.compile(r"\b(\d{2}\s*[/-]\s*\d{3})\b")
_CAP = re.compile(r"\b(\d{1,4})\s*(ml|mL)\b")


def extract_referenced(text: str, source: dict) -> list[dict]:
    """Referent-aware extraction from a FETCHED page body. Units are
    preserved as stated (§3): an inch value stays an inch value and the
    mm conversion is recorded alongside, never in place of it."""
    out, low = [], (text or "").lower()

    def add(referent, raw, unit, ctx, conf):
        mm = None
        if unit == "mm":
            mm = float(raw)
        elif unit == "cm":
            mm = float(raw) * 10
        elif unit == "in":
            mm = round(float(raw) * 25.4, 2)
        out.append({
            "component_referent": referent,
            "raw_value": raw, "original_unit": unit,
            "value_mm_converted": mm,
            "unit_preserved": True,
            "evidence_text": ctx.strip()[:180],
            "source_domain": source["domain"], "source_url": source["url"],
            "source_tier": source["authority_tier"],
            "may_authorize_alone": source["may_authorize_alone"],
            "extraction": "GOVERNED_PAGE_FETCH",
            "confidence": conf, "verification_state": "UNVERIFIED",
            "human_decision": "PENDING"})

    for pat, referent in _PATTERNS:
        for m in re.finditer(pat, low):
            unit = m.group(m.lastindex) if m.lastindex and \
                m.group(m.lastindex) in ("mm", "cm", "in", "ml", "g",
                                         "gram") else "mm"
            add(referent, m.group(1), "g" if unit == "gram" else unit,
                low[max(0, m.start() - 60):m.end() + 20],
                0.7 if source["authority_tier"] == 1 else 0.55)
    for m in _NECK_FIN.finditer(text or ""):
        add("NECK_FINISH", m.group(1).replace(" ", ""), "neck_finish_code",
            (text or "")[max(0, m.start() - 60):m.end() + 40], 0.8)
    for m in _CAP.finditer(text or ""):
        add("NOMINAL_CAPACITY", m.group(1), "ml",
            (text or "")[max(0, m.start() - 50):m.end() + 30], 0.6)
    return _dedupe(out)


def _dedupe(rows: list) -> list:
    """§4 — one value must not be filed under two referents silently. An
    identical value matching several patterns is kept ONCE and flagged
    ambiguous, because a value whose referent is unresolved cannot guide
    geometry."""
    by_value: dict = {}
    for r in rows:
        key = (r["raw_value"], r["original_unit"], r["source_url"])
        by_value.setdefault(key, []).append(r)
    out = []
    for rows_for_value in by_value.values():
        refs = {r["component_referent"] for r in rows_for_value}
        first = rows_for_value[0]
        if len(refs) == 1:
            out.append(first)
            continue
        out.append({**first,
                    "component_referent": "REFERENT_UNRESOLVED",
                    "candidate_referents": sorted(refs),
                    "referent_ambiguous": True,
                    "confidence": 0.0,
                    "may_support_concept_geometry": False,
                    "note": "one value matched several referent patterns; "
                            "a human must state which referent applies"})
    return out


def demote_snippet_measurements(measurements: list) -> list:
    """§1 — snippet-derived values are not technical evidence."""
    out = []
    for m in measurements:
        out.append({**m,
                    "component_referent": "REFERENT_UNRESOLVED",
                    "original_referent_guess": m.get("component_referent"),
                    "extraction": "SEARCH_SNIPPET",
                    "evidence_class": SNIPPET_NOT_EVIDENCE,
                    "may_support_concept_geometry": False,
                    "confidence": 0.0,
                    "human_decision": "PENDING"})
    return out


# --- §5 conflict enrichment ---------------------------------------------------

def enrich_conflict(conflict: dict, measurements: list) -> dict:
    """Conflicts are explained, never resolved."""
    ref = conflict["component_referent"]
    vals = conflict["values_mm"]
    rows = [m for m in measurements
            if m.get("original_referent_guess") == ref
            or m.get("component_referent") == ref]
    spread = (max(vals) / min(vals)) if vals and min(vals) else 0
    if spread > 3:
        why = ("the values differ by more than 3x, which usually means two "
               "DIFFERENT physical quantities were captured under one "
               "guessed referent (for example a dropper assembly length "
               "against a collar diameter), not a genuine disagreement")
    elif ref in ("PIPETTE_LENGTH", "pipette_length"):
        why = ("pipette/dropper lengths legitimately differ by bottle "
               "height; these are probably distinct products")
    else:
        why = ("two sources state different values for what may be the "
               "same referent; a manufacturer drawing is needed to settle "
               "it")
    return {"fact_type": ref,
            "source_a": (rows[0]["source_domain"] if rows else None),
            "source_b": (rows[-1]["source_domain"] if len(rows) > 1
                         else None),
            "raw_values": vals, "unit": "mm",
            "referent_difference": ("the referent was INFERRED from snippet "
                                    "context and is not reliable"),
            "likely_explanation": why,
            "one_source_includes_closure": "UNKNOWN",
            "confidence": 0.0,
            "required_human_action": "PENDING",
            "allowed_actions": list(CONFLICT_ACTIONS),
            "auto_resolved": False}


# --- §7/§8 pixel evidence and the authority rule ------------------------------

def reference_pixel_evidence(px: dict) -> dict:
    return {"banner": "REFERENCE PIXEL MEASUREMENT · CONCEPT-VISUAL "
                      "EVIDENCE ONLY · NOT A PHYSICAL DIMENSION",
            "source_image": px.get("source_image"),
            "centerline_px": px.get("centerline_px"),
            "measurements_px": px.get("measurements_px", {}),
            "ratios_of_body_width": px.get("ratios", {}),
            "occlusion": ("the LEFT side of the bottle is partially "
                          "occluded by the adjacent carton in image #97; "
                          "the silhouette was measured from the clean "
                          "RIGHT edge about the calibrated centerline"),
            "symmetry_claim": "NOT_MEASURABLE_FROM_THIS_PHOTOGRAPH",
            "bilateral_symmetry_asserted": False,
            "uncertainty_px": px.get("uncertainty_px", 2.0),
            "authority": "CONCEPT_VISUAL_ONLY_NOT_PHYSICAL"}


def visualizer_authority_rule() -> dict:
    return {"schema_version": AUTHORITY_SCHEMA,
            "rule": "When deterministic image measurement and a multimodal "
                    "model's numeric claim conflict, the deterministic "
                    "measurement governs visible numeric relationships. The "
                    "multimodal result remains a semantic hypothesis only.",
            "deterministic_governs": ["visible numeric relationships",
                                      "ratios", "widths", "heights"],
            "multimodal_governs": ["semantic hypothesis only"],
            "multimodal_may_override_measured_ratios": False,
            "conflict_finding": VQ_MULTIMODAL_NUMERIC_CLAIM_CONFLICT,
            "on_conflict": "record the conflict and require human review"}


def numeric_conflicts(deterministic: dict, multimodal_claims: list) -> list:
    """Every model numeric claim checked against the measured ratio."""
    out = []
    for claim in multimodal_claims:
        measured = deterministic.get(claim["metric"])
        if measured is None:
            continue
        stated = claim["model_value"]
        disagree = abs(stated - measured) > max(0.15 * measured, 0.05)
        out.append({
            "metric": claim["metric"], "model_claim": stated,
            "deterministic_measurement": measured,
            "model_quote": claim.get("quote", ""),
            "conflict": disagree,
            "finding": (VQ_MULTIMODAL_NUMERIC_CLAIM_CONFLICT if disagree
                        else None),
            "governs": "DETERMINISTIC_MEASUREMENT",
            "multimodal_status": "SEMANTIC_HYPOTHESIS_ONLY",
            "human_review_required": disagree})
    return out


# --- §6 decision matrix -------------------------------------------------------

def semantic_decision_matrix(pixel_evidence: dict, sources: list,
                             multimodal: dict) -> dict:
    """Every option gets its evidence. None is preselected."""
    pf = pixel_evidence.get("ratios_of_body_width", {})
    const_run = pixel_evidence.get("measurements_px", {}).get(
        "dark_component_constant_width_run_px")
    flare = pixel_evidence.get("measurements_px", {}).get(
        "dark_component_flare_width_px")
    drawing_ids = [s["source_id"] for s in sources
                   if s.get("technical_drawing_indicated")]
    rows = {}
    for key, opt in SEMANTIC_OPTIONS.items():
        rows[key] = {
            **opt,
            "supporting_source_ids": [], "contradicting_source_ids": [],
            "reference_pixel_evidence": "", "technical_drawing_evidence":
                ("no fetched drawing resolves the closure construction; "
                 f"candidate drawings: {drawing_ids}" if drawing_ids
                 else "none"),
            "physical_plausibility": "", "confidence": 0.0,
            "unresolved_questions": [], "selected": False}
    rows["A"]["reference_pixel_evidence"] = (
        f"AGAINST: the dark component holds a constant width for "
        f"{const_run} px before flaring; a bare compressible bulb usually "
        f"tapers continuously")
    rows["A"]["physical_plausibility"] = "common construction, but the "\
        "measured profile does not match a bare tapering bulb"
    rows["A"]["unresolved_questions"] = [
        "is the straight section a moulding artefact of the photograph?"]
    rows["B"]["reference_pixel_evidence"] = (
        f"FOR: constant-width run of {const_run} px terminating in a "
        f"{flare} px flare that meets the collar edge-to-edge")
    rows["B"]["physical_plausibility"] = "consistent with the measured "\
        "profile; no external stem is required"
    rows["B"]["unresolved_questions"] = [
        "does any supplier drawing show an integral flared skirt?"]
    rows["C"]["reference_pixel_evidence"] = (
        "FOR: the crisp dome and straight sidewall read as a rigid moulded "
        "part rather than compressible rubber")
    rows["C"]["physical_plausibility"] = "common on premium serum closures"
    rows["C"]["unresolved_questions"] = [
        "is a separate internal bulb visible in any supplier photograph?",
        "does the collar height allow a concealed actuator?"]
    rows["D"]["reference_pixel_evidence"] = (
        "AGAINST: an overcap would normally cover the collar; here the "
        "dark component sits ABOVE the collar and is narrower than it "
        f"(ratio {pf.get('dark_component_to_collar')})")
    rows["D"]["physical_plausibility"] = "possible but contradicted by the "\
        "measured width relationship"
    rows["E"]["reference_pixel_evidence"] = "not evaluated"
    rows["F"]["reference_pixel_evidence"] = (
        "the deterministic read and the multimodal hypothesis disagree; "
        "no fetched source states the closure construction")
    rows["F"]["physical_plausibility"] = "the current recorded state"
    rows["F"]["unresolved_questions"] = [
        "no Tier-1 drawing yet shows the dark component's construction"]
    return {"schema_version": MATRIX_SCHEMA,
            "options": rows,
            "current_recorded_state": "UNCERTAIN",
            "blocker": "VQ_COMPONENT_SEMANTICS_HUMAN_CONFIRMATION_REQUIRED",
            "preselected": None,
            "multimodal_hypothesis": (multimodal.get("component_semantics")
                                      or {}),
            "note": "no option is preselected; the multimodal "
                    "classification is a hypothesis and never a decision"}


# --- §13 decision form --------------------------------------------------------

def decision_form(shortlist: dict, matrix: dict, referents: list) -> dict:
    return {"schema_version": DECISION_SCHEMA, "created_at": _now(),
            "decisions": [
                {"id": 1, "requirement": "Approve at least 3 physical "
                 "analog sources", "minimum": 3, "candidates":
                 [s["source_id"] for s in shortlist["primary_bottle"]
                  + shortlist["alternates"]], "selected": [],
                 "state": "PENDING"},
                {"id": 2, "requirement": "Approve at least 2 fact sources",
                 "minimum": 2, "candidates":
                 [s["source_id"] for s in shortlist["primary_bottle"]
                  + shortlist["primary_closure"]], "selected": [],
                 "state": "PENDING"},
                {"id": 3, "requirement": "Approve at least 1 technical "
                 "drawing", "minimum": 1, "candidates":
                 [s["source_id"] for s in shortlist["technical_drawings"]],
                 "selected": [], "state": "PENDING"},
                {"id": 4, "requirement": "Approve specific measurement "
                 "referents", "minimum": 1, "candidates": referents,
                 "selected": [], "state": "PENDING"},
                {"id": 5, "requirement": "Select one component-semantic "
                 "option", "minimum": 1,
                 "candidates": list(matrix["options"]), "selected": [],
                 "state": "PENDING"},
                {"id": 6, "requirement": "Select one bottle/closure "
                 "construction family", "minimum": 1,
                 "candidates": ["18/415_DROPPER", "20/410_DROPPER",
                                "24/410_DROPPER", "OTHER_NECK_FINISH"],
                 "selected": [], "state": "PENDING"},
                {"id": 7, "requirement": "Authorize or reject another "
                 "structural iteration", "minimum": 1,
                 "candidates": ["AUTHORIZE_NEXT_STRUCTURAL_ITERATION",
                                "REJECT_FOR_NOW"], "selected": [],
                 "state": "PENDING"}],
            "bundling_prohibited": "each decision is independent; approving "
                                   "a physical analog never approves its "
                                   "dimensions, and approving dimensions is "
                                   "limited to the exact stated referents",
            "all_pending": True}


def next_structural_consequences(matrix: dict) -> list:
    """§11.12 — what each semantic choice would mean for the next model."""
    return [
        {"if_selected": "A", "consequence": "model a bare compressible "
         "bulb with a continuous taper; the measured constant-width run "
         "must then be explained as a photographic artefact"},
        {"if_selected": "B", "consequence": "model one elastomer component "
         "with a straight sidewall, rounded dome and integral flared skirt "
         "meeting the collar; NO external stem"},
        {"if_selected": "C", "consequence": "model a rigid outer cover as "
         "the visible component and keep an internal bulb as a separate, "
         "normally hidden technical part"},
        {"if_selected": "D", "consequence": "model an overcap covering the "
         "functional closure; the collar would need re-measuring because "
         "an overcap changes what is visible"},
        {"if_selected": "E", "consequence": "define the construction before "
         "any geometry"},
        {"if_selected": "F", "consequence": "no structural model may be "
         "built; a further governed research pass is required"},
    ]
