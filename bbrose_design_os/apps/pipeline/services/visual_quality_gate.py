"""VQR-2A — fail-closed Product Container visual quality gate.

``product_container_visual_quality_gate/1.0`` is the ONE evaluator that
decides whether a technically completed reconstruction may be treated as
owner-review ready, Gate-2 ready or handoff ready. It exists because the
owner-rejected task 53 was structurally valid (real .ai, real vectors,
lifecycle COMPLETED) yet visually unusable — and every prior surface
classified it as shippable.

Fail-closed principle (§2 of the VQR-2A brief):

* every required axis is PASS / FAIL / UNMEASURED / NOT_APPLICABLE;
* PASS means MEASURED and satisfied — never inferred from object counts;
* UNMEASURED on a required axis is BLOCKING;
  [§BH71 (0a), the owner's goal of 2026-09-28: an UNMEASURED axis is an acceptance warning shown beside
  Approve, never a block — the overall reads UNMEASURED, never PASS, and a MEASURED FAIL still fails; an axis
  with no evaluation at all is a defect of this evaluator and still refuses]
* the overall gate passes only when every required axis is PASS (or
  legitimately NOT_APPLICABLE). Absence of evidence is never success.

The evaluator is pure: it reads persisted records and artifact bytes, writes
nothing, dispatches nothing, calls no provider. Reports carry no filesystem
paths, storage keys, artifact bytes or stack traces.

Measurement sources (2026-08-03):

* artifact_authority   — VQR-6 authority (reused, never re-derived);
* artboard_fitness     — /MediaBox parsed from the .ai bytes vs the
                         fixed-page catalog and the confirmed profile;
* front_artwork        — container_design_graph/1.1 placeholder signature;
* silhouette_fidelity  — product bounds are NOT yet persisted → UNMEASURED
                         until VQR-2B (graph key ``product_bounds`` honored
                         when a future generator records it);
* closure_fidelity     — assembly inventory NOT yet persisted → UNMEASURED
                         until VQR-1 (graph key ``closure_assembly`` honored);
* logo / typography / composition — only presence/count evidence exists
                         today → UNMEASURED until VQR-3 / VQR-4 record real
                         metrics (structured records honored when present).

No current reconstruction can pass this gate. That is the point: detection
first (VQR-2A), correction later (VQR-1, 2B, 3, 4, 5).
"""
from __future__ import annotations

import re

VQ_GATE_SCHEMA = "product_container_visual_quality_gate/1.0"

PASS = "PASS"
FAIL = "FAIL"
UNMEASURED = "UNMEASURED"
NOT_APPLICABLE = "NOT_APPLICABLE"

BLOCKED_VISUAL_QUALITY = "BLOCKED_VISUAL_QUALITY"
VISUAL_QUALITY_PASSED = "VISUAL_QUALITY_PASSED"
#: §BH71 (0a): nothing measured failed and some required axis is not measured — approvable, its unmeasured axes
#: warned beside Approve; never "passed"
VISUAL_QUALITY_NOT_FULLY_MEASURED = "VISUAL_QUALITY_NOT_FULLY_MEASURED"

# blocking finding codes
VQ_ARTIFACT_AUTHORITY_FAILED = "VQ_ARTIFACT_AUTHORITY_FAILED"
VQ_ARTBOARD_NOT_PRODUCT_DERIVED = "VQ_ARTBOARD_NOT_PRODUCT_DERIVED"
VQ_ARTBOARD_UNRELATED_TO_PRODUCT = "VQ_ARTBOARD_UNRELATED_TO_PRODUCT"
VQ_ARTBOARD_UNMEASURED = "VQ_ARTBOARD_UNMEASURED"
VQ_SILHOUETTE_DIVERGENT = "VQ_SILHOUETTE_DIVERGENT"
VQ_SILHOUETTE_COMPARISON_UNAVAILABLE = "VQ_SILHOUETTE_COMPARISON_UNAVAILABLE"
VQ_CLOSURE_FAMILY_MISMATCH = "VQ_CLOSURE_FAMILY_MISMATCH"
VQ_CLOSURE_STRUCTURE_UNMEASURED = "VQ_CLOSURE_STRUCTURE_UNMEASURED"
VQ_FRONT_ARTWORK_UNRESOLVED_PLACEHOLDER = \
    "VQ_FRONT_ARTWORK_UNRESOLVED_PLACEHOLDER"
VQ_FRONT_ARTWORK_UNMEASURED = "VQ_FRONT_ARTWORK_UNMEASURED"
VQ_LOGO_METRICS_UNMEASURED = "VQ_LOGO_METRICS_UNMEASURED"
VQ_LOGO_DEFECTIVE = "VQ_LOGO_DEFECTIVE"
VQ_TYPOGRAPHY_METRICS_UNMEASURED = "VQ_TYPOGRAPHY_METRICS_UNMEASURED"
VQ_TYPOGRAPHY_DEFECTIVE = "VQ_TYPOGRAPHY_DEFECTIVE"
VQ_COMPOSITION_COMPARISON_UNAVAILABLE = \
    "VQ_COMPOSITION_COMPARISON_UNAVAILABLE"
VQ_COMPOSITION_DEFECTIVE = "VQ_COMPOSITION_DEFECTIVE"

REQUIRED_AXES = (
    "artifact_authority", "artboard_fitness", "silhouette_fidelity",
    "closure_fidelity", "front_artwork_resolution", "logo_quality",
    "typography_quality", "composition_quality",
)

# ---------------------------------------------------------------------------
# §13 threshold policy: every numeric decision constant lives HERE, is
# versioned, appears in the report, and is calibrated from accepted fixtures
# or explicit design policy — never chosen to let rejected output pass.
MM_TO_PT = 72.0 / 25.4
THRESHOLDS = {
    "version": "vqr2a_thresholds/1.0",
    # fixed page standards a product reconstruction must never inherit
    "fixed_page_artboards_pt": {
        "A4": (595.276, 841.890),
        "LETTER": (612.0, 792.0),
        "A3": (841.890, 1190.551),
        "LEGAL": (612.0, 1008.0),
    },
    "artboard_match_tolerance_pt": 1.0,
    # a product-derived artboard stays within this factor of the confirmed
    # product extent (mm→pt); beyond it the canvas is unrelated presentation
    # space (design policy, calibrated against the VQ-1 M3 review artboards)
    "artboard_max_product_factor": 3.0,
    # silhouette aspect-ratio relative deviation ceiling (design policy;
    # enforcement requires VQR-2B measurements — declared here so 2B
    # calibrates against ONE versioned constant)
    "silhouette_max_aspect_deviation": 0.15,
    # closure families whose structural evidence must include these
    # components before the family can PASS (VQ-1 dropper assembly)
    "closure_required_components": {
        "dropper": ("collar", "bulb"),
        "pump": ("collar", "actuator"),
    },
    # NOT typography_min_text_pt. §W2 ruled the container_production_method
    # capability table the authority on minimum text size, per run and per
    # surface, so this gate no longer owns a flat number to compare against.
    # The 5.0 survives as container_text_floor.FALLBACK_FLOOR_PT, where the
    # record discloses it as a fallback. Keeping a second copy here would be
    # the conflation §W2(c) names: a constant that does not name its domain.
    # minimum rendered logo extent when VQR-3 records logo metrics
    "logo_min_extent_pt": 8.0,
}

# how far into the .ai the /MediaBox header scan reads (the box lives in the
# page dictionary near the head; cap keeps the evaluator cheap on any file)
_MEDIABOX_SCAN_BYTES = 2 * 1024 * 1024
_MEDIABOX_RE = re.compile(
    rb"/MediaBox\s*\[\s*([\d.+-]+)\s+([\d.+-]+)\s+([\d.+-]+)\s+([\d.+-]+)")

# owner-facing wording for unmeasured axes (§9)
#: [§BH71 (0a): it read "This required quality criterion was not measured. The result cannot advance."]
UNMEASURED_SENTENCE = ("This quality check was not measured; it is shown as a warning beside Approve and is "
                      "never marked passed.")


def _axis(state, *, code="", reason="", measured=None, missing_measurement=""):
    entry = {"state": state, "required": True, "code": code, "reason": reason,
             "measured": measured or {}}
    if missing_measurement:
        entry["missing_measurement"] = missing_measurement
    return entry


# ---------------------------------------------------------------------------
# §2 combiner — pure and unit-testable: the ONLY place overall is decided


def combine_axes(axes: dict) -> dict:
    """Fail-closed combination of required axes. PASS only when every
    required axis is PASS or legitimately NOT_APPLICABLE; FAIL on any
    required FAIL; UNMEASURED required axes are BLOCKING findings.

    [§BH71 (0a): an UNMEASURED required axis is an acceptance warning — the overall reads UNMEASURED, never PASS,
    and refuses nothing; a FAIL still fails; an axis with no evaluation is the evaluator's defect and refuses.]"""
    findings = []
    warnings = []
    overall = PASS
    unmeasured = False
    for name in REQUIRED_AXES:
        entry = axes.get(name)
        if entry is None or not isinstance(entry, dict) \
                or entry.get("state") not in (PASS, FAIL, UNMEASURED,
                                              NOT_APPLICABLE):
            entry = _axis(UNMEASURED,
                          code=f"VQ_{name.upper()}_MISSING",
                          reason="no axis evaluation exists")
            entry["defect"] = "NO_AXIS_EVALUATION"      # §BH71 (0a): a defect, not a measurement to waive
            axes[name] = entry
        state = entry["state"]
        if not entry.get("required", True):
            continue
        if state == FAIL:
            overall = FAIL
            findings.append({"code": entry.get("code") or
                             f"VQ_{name.upper()}_FAILED",
                             "axis": name,
                             "message": entry.get("reason") or
                             "measured and did not satisfy the criterion"})
        elif state == UNMEASURED and entry.get("defect"):
            overall = FAIL
            findings.append({"code": entry.get("code") or
                             f"VQ_{name.upper()}_UNMEASURED",
                             "axis": name,
                             "message": (entry.get("reason") or
                                         UNMEASURED_SENTENCE)})
        elif state == UNMEASURED:
            unmeasured = True
            warnings.append({"code": entry.get("code") or
                             f"VQ_{name.upper()}_UNMEASURED",
                             "axis": name,
                             "message": (entry.get("reason") or
                                         UNMEASURED_SENTENCE)})
    if overall == PASS and unmeasured:
        overall = UNMEASURED
    return {"overall": overall, "blocking_findings": findings,
            "acceptance_warnings": warnings}


# ---------------------------------------------------------------------------
# per-axis measurement


def _artifact_authority_axis(status, result):
    """Reuse the VQR-6 authority facts — never a second availability
    derivation. The caller hands in the already-built contracts."""
    retry = (status.get("retry") or {})
    technical = retry.get("recovery") == "TECHNICAL_INTERVENTION_REQUIRED"
    ai_ok = bool(result and result["artifacts"]["ai"]["available"])
    if status["lifecycle_state"] == "COMPLETED" and ai_ok and not technical:
        return _axis(PASS, measured={
            "lifecycle_state": status["lifecycle_state"],
            "ai_available": True,
            "technical_intervention_required": False})
    return _axis(FAIL, code=VQ_ARTIFACT_AUTHORITY_FAILED,
                 reason="the editable AI authority is not cleanly available",
                 measured={"lifecycle_state": status["lifecycle_state"],
                           "ai_available": ai_ok,
                           "technical_intervention_required": technical})


def _read_mediabox(output):
    """(width_pt, height_pt) from the .ai bytes, or None when unreadable.
    Storage errors are an UNMEASURED signal, never an exception."""
    try:
        with output.design_preview_ai.open("rb") as fh:
            head = fh.read(_MEDIABOX_SCAN_BYTES)
    except Exception:
        return None
    match = _MEDIABOX_RE.search(head)
    if not match:
        return None
    try:
        x0, y0, x1, y1 = (float(v) for v in match.groups())
    except ValueError:
        return None
    width, height = abs(x1 - x0), abs(y1 - y0)
    if width <= 0 or height <= 0:
        return None
    return (width, height)


def _artboard_axis(output, profile, graph=None):
    box = _read_mediabox(output)
    if box is None:
        return _axis(UNMEASURED, code=VQ_ARTBOARD_UNMEASURED,
                     reason="the output artboard could not be measured",
                     missing_measurement="artboard record (VQR-2B)")
    width, height = box
    tol = THRESHOLDS["artboard_match_tolerance_pt"]
    for name, (pw, ph) in THRESHOLDS["fixed_page_artboards_pt"].items():
        if (abs(width - pw) <= tol and abs(height - ph) <= tol) or \
                (abs(width - ph) <= tol and abs(height - pw) <= tol):
            return _axis(
                FAIL, code=VQ_ARTBOARD_NOT_PRODUCT_DERIVED,
                reason=f"the reconstruction uses a fixed {name} page "
                       "artboard instead of a product-derived canvas",
                measured={"artboard_pt": [round(width, 2), round(height, 2)],
                          "matched_page_standard": name})
    w_mm = (profile or {}).get("width_mm")
    h_mm = (profile or {}).get("height_mm")
    if not w_mm or not h_mm:
        return _axis(UNMEASURED, code=VQ_ARTBOARD_UNMEASURED,
                     reason="the confirmed profile carries no product "
                            "dimensions to relate the artboard to",
                     measured={"artboard_pt": [round(width, 2),
                                               round(height, 2)]})
    # [his answer of 2026-10-05, W5: "fix the artboard check so tubes pass; a check that refuses every tube is wrong"]
    # the artboard is related to the product as it is DRAWN — a tube flat, π/2 of its confirmed width — exactly as the
    # silhouette axis reads it below (his answer after test day finding 3, (4) "round"); the factor is unchanged. Read
    # against the round width, every tube's sheet measured 3.85 × it (2.45 × its drawn flat end) and was refused.
    from apps.pipeline.targets.container.silhouettes import drawn_width_mm
    w_mm = drawn_width_mm((profile or {}).get("archetype"), float(w_mm))
    factor = THRESHOLDS["artboard_max_product_factor"]
    # [his goal of 2026-10-10, item 2: "A palette design must include the whole palette: the lid AND the open tray"]
    # the open tray, drawn below the lid at the size it prints, is the product too and never presentation canvas: the
    # sheet's height it took (the drawing's own record) is allowed beside the lid's; the factor is unchanged
    tray_mm = [float(v) for v in [(graph or {}).get("open_tray_sheet_mm")] if v]
    max_w = float(w_mm) * MM_TO_PT * factor
    max_h = float(h_mm) * MM_TO_PT * factor + sum(tray_mm) * MM_TO_PT
    measured = {"artboard_pt": [round(width, 2), round(height, 2)],
                **({"open_tray_sheet_pt": round(tray_mm[0] * MM_TO_PT, 2)} if tray_mm else {}),
                "product_extent_pt": [round(float(w_mm) * MM_TO_PT, 2),
                                      round(float(h_mm) * MM_TO_PT, 2)],
                "max_product_factor": factor,
                # owner correction (2026-08-03): this axis certifies the
                # STRUCTURAL document artboard only — client-presentation
                # artboard fitness is a separate, unevaluated question
                "artboard_role": "STRUCTURAL_DOCUMENT_ARTBOARD",
                "client_presentation_fitness": "NOT_EVALUATED"}
    if width > max_w or height > max_h:
        return _axis(FAIL, code=VQ_ARTBOARD_UNRELATED_TO_PRODUCT,
                     reason="the artboard is unrelated presentation canvas — "
                            "far larger than the confirmed product extent",
                     measured=measured)
    return _axis(PASS, measured=measured)


def _silhouette_axis(graph, profile):
    """SELECTED-CONCEPT silhouette fidelity — UNMEASURED until VQR-2B
    performs concept-side + reconstruction-side comparison.

    VQR-1 owner correction: the product-bounds-vs-confirmed-profile check
    is STRUCTURAL conformance (does the emitted geometry honor the
    confirmed dimensions/M3 structure), NOT concept fidelity. A measured
    structural VIOLATION still fails this axis (a reconstruction that
    breaks its own confirmed dims can never advance), but structural
    conformance PASS is recorded separately as
    ``structural_silhouette_conformance`` and never claims concept
    fidelity — the axis stays UNMEASURED and blocking.
    """
    w_mm = (profile or {}).get("width_mm")
    h_mm = (profile or {}).get("height_mm")
    if w_mm:
        # [his answer after test day finding 3, 2026-09-30, (4) "round": a tube's confirmed width is its round
        # diameter, and it is drawn as wide as its flat end, π/2 of it] the outline is read against the width the form
        # is DRAWN at — 117's drawing failed here at 0.363 against its round 50 mm, and deviates 0.000 from its 78.5
        from apps.pipeline.targets.container.silhouettes import drawn_width_mm
        w_mm = drawn_width_mm((profile or {}).get("archetype"), float(w_mm))

    # R2b: when a reconstruction-vs-selected-concept silhouette comparison
    # IS persisted, this axis finally measures concept fidelity instead of
    # standing UNMEASURED by construction. The comparison is produced by
    # vqr2b_reconstruction_measurement and carries its own resolution
    # evidence; an under-resolved comparison is NOT a pass.
    comparison = (graph or {}).get("reconstruction_silhouette") or {}
    if comparison.get("schema") == "reconstruction_silhouette_measurement/1.0":
        measured = {
            "binding_statistic": comparison.get("binding_statistic"),
            "mean_abs_deviation": comparison.get("mean_abs_deviation"),
            "max_abs_deviation": comparison.get("max_abs_deviation"),
            "threshold": comparison.get("threshold"),
            "threshold_status": comparison.get("threshold_status"),
            "resolution": comparison.get("resolution"),
        }
        warning = (comparison.get("resolution") or {}).get(
            "quantisation_warning")
        if warning:
            measured["quantisation_warning"] = warning
            return _axis(
                UNMEASURED, code=VQ_SILHOUETTE_COMPARISON_UNAVAILABLE,
                reason="a comparison exists but the reconstruction raster "
                       "is quantisation-dominated, so the deviation is an "
                       "artefact of resolution rather than of the artwork",
                measured=measured,
                missing_measurement="a reconstruction raster with enough "
                                    "rows per profile sample")
        if comparison.get("within_threshold"):
            return _axis(PASS,
                         reason="reconstructed silhouette matches the "
                                "selected concept within the recorded "
                                "tolerance (mean absolute deviation over "
                                "the shared 64-sample profile)",
                         measured=measured)
        return _axis(FAIL, code=VQ_SILHOUETTE_DIVERGENT,
                     reason="reconstructed silhouette diverges from the "
                            "selected concept beyond the recorded "
                            "tolerance",
                     measured=measured)

    bounds = (graph or {}).get("product_bounds") or {}
    try:
        bw = float(bounds.get("width_pt", 0))
        bh = float(bounds.get("height_pt", 0))
    except (TypeError, ValueError):
        bw = bh = 0
    if bw > 0 and bh > 0 and w_mm and h_mm:
        expected = float(h_mm) / float(w_mm)
        actual = bh / bw
        deviation = abs(actual - expected) / expected
        measured = {"expected_aspect": round(expected, 3),
                    "reconstructed_aspect": round(actual, 3),
                    "relative_deviation": round(deviation, 3)}
        if deviation > THRESHOLDS["silhouette_max_aspect_deviation"]:
            measured["structural_silhouette_conformance"] = FAIL
            return _axis(FAIL, code=VQ_SILHOUETTE_DIVERGENT,
                         reason="the reconstructed product aspect ratio "
                                "diverges from the confirmed profile — a "
                                "structural conformance violation",
                         measured=measured)
        measured["structural_silhouette_conformance"] = PASS
        return _axis(
            UNMEASURED, code=VQ_SILHOUETTE_COMPARISON_UNAVAILABLE,
            reason="structural silhouette conformance PASSES (emitted "
                   "bounds honor the confirmed profile), but "
                   "selected-concept silhouette fidelity is NOT yet "
                   "measured — concept comparison arrives with VQR-2B",
            measured=measured,
            missing_measurement="selected-concept mask/contour "
                                "comparison (VQR-2B)")
    measured = {"structural_silhouette_conformance": UNMEASURED}
    if w_mm and h_mm:
        measured["expected_aspect"] = round(float(h_mm) / float(w_mm), 3)
    return _axis(
        UNMEASURED, code=VQ_SILHOUETTE_COMPARISON_UNAVAILABLE,
        reason="no reconstructed-silhouette measurement is persisted; a "
               "body rectangle or archetype string is not a measurement",
        measured=measured,
        missing_measurement="product bounds + contour comparison (VQR-2B)")


def _closure_axis(graph, profile):
    family = ((profile or {}).get("cap_style")
              or (profile or {}).get("cap_type") or "")
    assembly = (graph or {}).get("closure_assembly") or {}
    required = THRESHOLDS["closure_required_components"].get(family)
    if not family:
        return _axis(UNMEASURED, code=VQ_CLOSURE_STRUCTURE_UNMEASURED,
                     reason="the confirmed profile names no closure family",
                     missing_measurement="closure assembly evidence (VQR-1)")
    if not assembly:
        return _axis(
            UNMEASURED, code=VQ_CLOSURE_STRUCTURE_UNMEASURED,
            reason=f"the confirmed closure is '{family}' but no structural "
                   "assembly evidence is persisted; a generic cap block is "
                   "not a measurement",
            measured={"confirmed_family": family},
            missing_measurement="closure assembly inventory (VQR-1)")
    built = str(assembly.get("family") or "")
    components = {str(c).lower() for c in (assembly.get("components") or [])}
    measured = {"confirmed_family": family, "built_family": built,
                "components": sorted(components)}
    if built != family:
        built_label = built or "a generic block"
        return _axis(FAIL, code=VQ_CLOSURE_FAMILY_MISMATCH,
                     reason=f"the reconstruction built '{built_label}' where "
                            f"the confirmed profile requires '{family}'",
                     measured=measured)
    if required and not set(required).issubset(components):
        missing = sorted(set(required) - components)
        return _axis(FAIL, code=VQ_CLOSURE_FAMILY_MISMATCH,
                     reason=f"the '{family}' assembly lacks required "
                            f"structure: {', '.join(missing)}",
                     measured=measured)
    return _axis(PASS, measured=measured)


def _front_artwork_axis(graph):
    if not graph:
        return _axis(UNMEASURED, code=VQ_FRONT_ARTWORK_UNMEASURED,
                     reason="no design graph is persisted for this output",
                     missing_measurement="design graph (VQR-3)")
    motif_groups = graph.get("motif_groups")
    decorative = graph.get("decorative_raster_count")
    zones = graph.get("zones_consumed") or []
    if motif_groups is None or decorative is None:
        return _axis(UNMEASURED, code=VQ_FRONT_ARTWORK_UNMEASURED,
                     reason="the design graph does not record artwork "
                            "content facts",
                     missing_measurement="artwork content census (VQR-3)")
    measured = {"motif_group_count": len(motif_groups),
                "decorative_raster_count": int(decorative),
                "zones_consumed": list(zones)}
    if not motif_groups and not decorative:
        # [his answer of 2026-10-05, W6: "type-only is a real design style; refuse only real placeholder text"] a front
        # that prints its own words and nothing else is a resolved composition — type-only — unless those words are
        # placeholder text; a front with no type either is still a zone-only fill. A graph written before the census
        # counted the front's type carries no ``front_type`` and is read as before.
        front_type = graph.get("front_type")
        if isinstance(front_type, dict):
            measured["front_type"] = front_type
            placeholders = front_type["placeholder_runs"]
            if placeholders:
                return _axis(
                    FAIL, code=VQ_FRONT_ARTWORK_UNRESOLVED_PLACEHOLDER,
                    reason="the front prints placeholder text, never product copy: "
                           + ", ".join("%s %r" % (p["node_name"], p["text"]) for p in placeholders),
                    measured=measured)
            if front_type["runs"] or front_type["lettering"]:
                measured["front_style"] = "type-only"
                return _axis(PASS, measured=measured)
        return _axis(
            FAIL, code=VQ_FRONT_ARTWORK_UNRESOLVED_PLACEHOLDER,
            reason="the visible front artwork is a zone-only fill with no "
                   "resolved composition — a guide zone presented as final "
                   "artwork", measured=measured)
    return _axis(PASS, measured=measured)


def _logo_axis(spec, graph):
    metrics = spec.get("container_logo_metrics/1.0") or {}
    presence = {"logo_rasters":
                ((graph or {}).get("primitives") or {}).get("logo_rasters")}
    if not metrics:
        return _axis(
            UNMEASURED, code=VQ_LOGO_METRICS_UNMEASURED,
            reason="only logo presence is recorded; size, clipping, "
                   "distortion and contrast are not measured",
            measured=presence,
            missing_measurement="rendered logo metrics (VQR-3)")
    try:
        extent = float(metrics.get("rendered_extent_pt", 0))
        clipped = bool(metrics.get("clipped"))
        distorted = bool(metrics.get("materially_distorted"))
    except (TypeError, ValueError):
        return _axis(UNMEASURED, code=VQ_LOGO_METRICS_UNMEASURED,
                     reason="the recorded logo metrics are malformed",
                     missing_measurement="rendered logo metrics (VQR-3)")
    measured = {"rendered_extent_pt": extent, "clipped": clipped,
                "materially_distorted": distorted, **presence}
    if clipped or distorted or extent < THRESHOLDS["logo_min_extent_pt"]:
        return _axis(FAIL, code=VQ_LOGO_DEFECTIVE,
                     reason="the rendered logo is clipped, distorted or "
                            "below the minimum rendered size",
                     measured=measured)
    return _axis(PASS, measured=measured)


#: every field the typography verdict rests on. Three of them are defect
#: FLAGS, and an absent flag read with ``metrics.get(f)`` is False — the axis
#: asserting "not clipped, not overlapping" about things nobody measured.
#: Presence is checked before value. §BH50(f)(2): ``placeholder_text_present``
#: left this tuple in the commit that made placeholder copy its own blocker
#: (container_placeholder_copy/1.0, carried by readiness['content'] at
#: acceptance) — the same six pieces were counted here a second time.
_TYPOGRAPHY_FIELDS = ("min_text_pt", "clipped", "materially_overlapping",
                      "below_size_floor")

#: each defect flag and the finding it reports when it fires. The axis used to
#: recite all four defects in one sentence, which on a partial record asserted
#: about fields nobody had measured — the absent-flag defect made in prose
#: instead of in code. It became live rather than latent when §W5 made
#: ``placeholder_text_present`` measurable while ``materially_overlapping``
#: stayed absent: a placeholder finding would have announced an overlap too.
_TYPOGRAPHY_FLAG_FINDINGS = {
    "clipped": "type is clipped",
    "materially_overlapping": "type is set over type",
    # §W2 — the floor is per-run and comes from the print method recorded for
    # the run's surface, so the producer decides it and the gate reads the
    # verdict. A scalar min_text_pt compared against one flat number could
    # not: it failed a 2.0 pt bottom inkjet code that is standard practice.
    "below_size_floor": "type is below its print method's minimum size",
    # "placeholder_text_present" left at §BH50(f)(2): its own blocker now
}

_TYPOGRAPHY_FLAGS = tuple(_TYPOGRAPHY_FLAG_FINDINGS)


def _typography_axis(spec, graph):
    metrics = spec.get("container_typography_metrics/1.0") or {}
    runs = ((graph or {}).get("primitives") or {}).get("live_text")
    if not metrics:
        return _axis(
            UNMEASURED, code=VQ_TYPOGRAPHY_METRICS_UNMEASURED,
            reason="only the text-run count is recorded; scale, placement, "
                   "overlap and legibility are not measured — run count "
                   "alone can never pass",
            measured={"live_text_runs": runs},
            missing_measurement="typography metrics (VQR-4)")
    absent = [f for f in _TYPOGRAPHY_FIELDS if metrics.get(f) is None]
    measured = {f: metrics[f] for f in _TYPOGRAPHY_FIELDS if f not in absent}
    try:
        if "min_text_pt" in measured:
            measured["min_text_pt"] = float(measured["min_text_pt"])
    except (TypeError, ValueError):
        return _axis(UNMEASURED, code=VQ_TYPOGRAPHY_METRICS_UNMEASURED,
                     reason="the recorded typography metrics are malformed",
                     missing_measurement="typography metrics (VQR-4)")
    for flag in _TYPOGRAPHY_FLAGS:
        if flag in measured:
            measured[flag] = bool(measured[flag])
    measured["live_text_runs"] = runs
    for key in ("unmeasured", "unmeasured_reasons"):
        if key in metrics:
            measured[key] = metrics[key]
    findings = [text for flag, text in _TYPOGRAPHY_FLAG_FINDINGS.items()
                if measured.get(flag)]
    if findings:
        # a defect that WAS measured stays a finding even when the record is
        # incomplete: an unmeasured neighbour does not un-see it. Both states
        # block, but only FAIL tells the owner something was actually found.
        # The reason names the findings that fired rather than reciting all
        # four, so it cannot assert about a field nobody measured.
        return _axis(FAIL, code=VQ_TYPOGRAPHY_DEFECTIVE,
                     reason="; ".join(findings), measured=measured)
    if absent:
        return _axis(UNMEASURED, code=VQ_TYPOGRAPHY_METRICS_UNMEASURED,
                     reason="typography metrics are incomplete — "
                            + ", ".join(absent) + " not measured, so a record "
                            "showing no defect is not a container shown to "
                            "have none",
                     measured=measured,
                     missing_measurement="typography metrics (VQR-4)")
    return _axis(PASS, measured=measured)


#: every field the composition verdict rests on, and the finding each one
#: reports when it fires. ``front_hierarchy_nonempty`` is the typography
#: defect read the other way round: an absent flag is False under ``.get()``,
#: and False here means DEFECTIVE, so the axis announced "the front hierarchy
#: is empty" about a hierarchy nobody had looked at. Presence before value.
_COMPOSITION_COUNTS = {
    "elements_outside_artboard": "elements fall outside the artboard",
    # §W3(a) — the finding names what the rule actually catches. "required
    # elements overlap" described a rule nobody had written; type set over a
    # motif is not a defect and this axis must not be read as saying it is.
    "blocking_overlaps": "text is set over text",
}
_COMPOSITION_FIELDS = (*_COMPOSITION_COUNTS, "front_hierarchy_nonempty")


def _back_copy_has_no_surface(spec):
    """[His answer W10] the back panel's record says the brief's back copy had nowhere to print."""
    from apps.ire.back_panel import NO_SURFACE, SCHEMA
    record = spec.get(SCHEMA)
    return isinstance(record, dict) and NO_SURFACE in list(record.get("codes") or ())


def _composition_axis(spec):
    metrics = spec.get("container_composition_metrics/1.0") or {}
    containment = spec.get("container_zone_containment_report") or {}
    if not metrics:
        return _axis(
            UNMEASURED, code=VQ_COMPOSITION_COMPARISON_UNAVAILABLE,
            reason="element bounds, hierarchy and the selected-concept "
                   "composition comparison are not measured; zone "
                   "containment alone is insufficient",
            measured={"zone_containment": containment.get("contained")},
            missing_measurement="composition comparison (VQR-2B / VQR-3)")
    absent = [f for f in _COMPOSITION_FIELDS if metrics.get(f) is None]
    measured = {}
    try:
        for field in _COMPOSITION_COUNTS:
            if field not in absent:
                measured[field] = int(metrics[field])
    except (TypeError, ValueError):
        return _axis(UNMEASURED, code=VQ_COMPOSITION_COMPARISON_UNAVAILABLE,
                     reason="the recorded composition metrics are malformed",
                     missing_measurement="composition comparison (VQR-2B)")
    if "front_hierarchy_nonempty" not in absent:
        measured["front_hierarchy_nonempty"] = bool(
            metrics["front_hierarchy_nonempty"])
    measured["zone_containment"] = containment.get("contained")
    for key in ("unmeasured", "unmeasured_reasons"):
        if key in metrics:
            measured[key] = metrics[key]
    findings = [text for field, text in _COMPOSITION_COUNTS.items()
                if measured.get(field)]
    # [his answer of 2026-10-05, W10: "Never nowhere"] the brief's back copy with no surface to print on is a finding
    if _back_copy_has_no_surface(spec):
        findings.append("the brief's back copy has no surface to print on — no back print zone, no wrap label "
                        "reaching the back, no base label")
    if measured.get("front_hierarchy_nonempty") is False:
        findings.append("the front hierarchy is empty")
    if findings:
        # a defect that WAS measured stays a finding even when the record is
        # incomplete: an unmeasured neighbour does not un-see it. Both states
        # block, but only FAIL tells the owner something was actually found.
        # The reason names the findings that fired rather than reciting all
        # three, so it cannot assert about a field nobody measured.
        return _axis(FAIL, code=VQ_COMPOSITION_DEFECTIVE,
                     reason="; ".join(findings), measured=measured)
    if absent:
        return _axis(UNMEASURED, code=VQ_COMPOSITION_COMPARISON_UNAVAILABLE,
                     reason="composition metrics are incomplete — "
                            + ", ".join(absent) + " not measured, so a record "
                            "showing no defect is not a container shown to "
                            "have none",
                     measured=measured,
                     missing_measurement="composition comparison (VQR-2B)")
    return _axis(PASS, measured=measured)


# ---------------------------------------------------------------------------


def evaluate_container_visual_quality(task):
    """The gate report for ``task``, or None when a visual-quality
    evaluation is not meaningful:

    * wrong target / no confirmed reconstruction lifecycle (contract None);
    * lifecycle is not COMPLETED — a worker failure stays a worker failure
      and an inconsistent record stays technical intervention (§10/§11);
      incomplete reconstructions are never evaluated as visual results.

    Pure read: no writes, no dispatch, no provider.
    """
    from apps.pipeline.services.reconstruction_status import (
        build_container_reconstruction_result,
        build_container_reconstruction_status,
    )
    status = build_container_reconstruction_status(task)
    if status is None or status["lifecycle_state"] != "COMPLETED":
        return None
    result = build_container_reconstruction_result(task)
    output = task.current_output()
    spec = (output.spec_sheet or {}) if output else {}
    # prefer the 2.0 record where a target publishes one; the 1.1 and 1.0
    # keys remain the fallback for spec sheets emitted before the wiring
    graph = spec.get("container_design_graph/2.0") \
        or spec.get("container_design_graph/1.1") \
        or spec.get("container_design_graph/1.0") or {}
    profile = spec.get("container_profile") or {}
    confirmation = spec.get("container_confirmation") or {}
    resume = spec.get("container_resume") or {}

    axes = {
        "artifact_authority": _artifact_authority_axis(status, result),
        "artboard_fitness": _artboard_axis(output, profile, graph),
        "silhouette_fidelity": _silhouette_axis(graph, profile),
        "closure_fidelity": _closure_axis(graph, profile),
        "front_artwork_resolution": _front_artwork_axis(graph),
        "logo_quality": _logo_axis(spec, graph),
        "typography_quality": _typography_axis(spec, graph),
        "composition_quality": _composition_axis(spec),
    }
    combined = combine_axes(axes)
    # §BH71 (0a): approvable when nothing measured failed; "passed" only when every required axis passed
    passed = combined["overall"] != FAIL
    # VQR-1 owner correction (§1): structural conformance is reported as a
    # DISTINCT fact — it never stands in for selected-concept fidelity
    structural_conformance = (axes["silhouette_fidelity"]["measured"]
                              .get("structural_silhouette_conformance",
                                   UNMEASURED))
    return {
        "schema": VQ_GATE_SCHEMA,
        "structural_silhouette_conformance": structural_conformance,
        "selected_concept_silhouette_fidelity":
            axes["silhouette_fidelity"]["state"],
        "task_id": task.id,
        "design_target": task.design_target,
        "selected_concept_id": output.approved_image_id if output else None,
        "confirmed_profile_hash": confirmation.get("combined_hash"),
        "reconstruction_identity": resume.get("celery_task_id"),
        "evaluated_at": (task.updated_at.isoformat()
                         if task.updated_at else None),
        "thresholds_version": THRESHOLDS["version"],
        "overall": combined["overall"],
        "owner_review_ready": passed,
        "gate2_ready": passed,
        "handoff_ready": passed,
        "required_axes": axes,
        "blocking_findings": combined["blocking_findings"],
        "acceptance_warnings": combined["acceptance_warnings"],
        "status": (VISUAL_QUALITY_PASSED if combined["overall"] == PASS
                   else VISUAL_QUALITY_NOT_FULLY_MEASURED if passed
                   else BLOCKED_VISUAL_QUALITY),
    }
