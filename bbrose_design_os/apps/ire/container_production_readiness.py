"""Container production readiness + Gate-2 enforcement (Phase 2B-3D).

Aggregates every persisted 2B-3A..2B-3C readiness section, the print-data
facts, the output intent (ICC) and — decisively — HUMAN DESIGN ACCEPTANCE into
one ``container_production_readiness/1.0`` verdict that Gate-2 approval
enforces with no override flag.

The human category is the authority: an automated MEASURED_PASS can never
override a recorded human visual rejection (task #51's frozen state), and a
reconstruction nobody has reviewed cannot be approved either.
"""
from __future__ import annotations

SCHEMA = "container_production_readiness/1.0"

# Human Design Acceptance states (2B-3D mandate).
HDA_NOT_REVIEWED = "NOT_REVIEWED"
HDA_ACCEPTED = "ACCEPTED"
HDA_REJECTED = "REJECTED"
HDA_REVISION_REQUIRED = "REVISION_REQUIRED"
#: [§BH71, after (0a): an acceptance whose bytes are not the picture read now counts for nothing — the state the
#: project stage already gives it (targets/composite.py)]
HDA_VOID = "VOID"

# Stable blocking codes.
HUMAN_VISUAL_ACCEPTANCE_REQUIRED = "HUMAN_VISUAL_ACCEPTANCE_REQUIRED"
MISSING_OUTPUT_INTENT = "MISSING_OUTPUT_INTENT"              # a production note since 2026-09-27 — see below
CONTAINER_PRINT_DATA_INCOMPLETE = "CONTAINER_PRINT_DATA_INCOMPLETE"
CONTAINER_RECONSTRUCTION_ABSENT = "CONTAINER_RECONSTRUCTION_ABSENT"

# --- THE OWNER'S ANSWER OF 2026-09-27 TO THE §BH70 REPORT'S FIRST QUESTION (transcribed unnumbered): "Yes. A
# --- design is finished when I approve it. The maker's printing specification is shown as a production note,
# --- never a blocker (same as the physical sample)."
#: A PRODUCTION NOTE: every code that compares the design with the method table the system infers in the maker's
#: place (``container_production_method._METHOD_DEFAULTS``, "typical values, NEVER manufacturer authority"), or that
#: exists only because the maker's capability is unverified. The verdict, and each section that has any, carry it
#: under ``production_notes`` — shown on the design's review and kept with its approval, for the printer — and it never
#: enters ``blocking_codes`` or ``ready``. The text floor is the one exception in that table (his §W2 and §Y1 own it)
#: and is not here; nothing else is here either — a copy overrun, an unmeasured check, placeholder copy, an unread
#: colour, a stale record and his own acceptance refuse as before, each under his own rule. Read at the review from
#: the saved records, never by rewriting one, and no check date is added: nothing newly blocks, so no saved design
#: turns stale for it. The production-authority gates (§BH46) are not these and are untouched.
#: [§BH71 (0a): an unmeasured check is an acceptance warning since — below — and still never a note]
MAKER_SPECIFICATION_NOTES = frozenset({
    "CONTAINER_TECHNIQUE_UNVERIFIED", "CONTAINER_TRAPPING_REVIEW_REQUIRED", "CONTAINER_OVERPRINT_REVIEW_REQUIRED",
    "CONTAINER_REGISTRATION_REVIEW_REQUIRED", "CONTAINER_COLOR_COUNT_EXCEEDED", "CONTAINER_MINIMUM_LINE_WEIGHT_FAILED",
    "CONTAINER_MAXIMUM_COVERAGE_EXCEEDED", "CONTAINER_REGISTRATION_TOLERANCE_FAILED",
    "CONTAINER_WHITE_UNDERBASE_REQUIRED", MISSING_OUTPUT_INTENT})
#: §BH71 (0b), THE OWNER'S GOAL OF 2026-09-28: "Propose a batch-code place for every form that lacks one, shown as a
#: production note, not a blocker." A design whose confirmed zones carry no code place reads this note, naming the
#: place its form's proposal offers (container_contract.code_zone_for) — where it read
#: CONTAINER_PRINT_DATA_INCOMPLETE: code_zone_confirmed, blocking. The product's name and SKU still refuse. [Annotation,
#: 2026-10-08: that the name and SKU refuse was the executor's own line beside (0b), never his words; since his answers
#: after 122 was redrawn the SKU is a note too — SKU_NOT_GIVEN.]
BATCH_CODE_PLACE_NOT_CONFIRMED = "CONTAINER_BATCH_CODE_PLACE_NOT_CONFIRMED"
#: [his answer on the print area's safe margin, 2026-10-01 (OWNER_BLOCKER_CLEARANCE.md, transcribed at f23b9e8): "The
#: picture (Recommended)"] a part a front drawn from its concept's measured layout places where the picture prints it,
#: inside its zone but within the zone's safe margin (``container_projection.validate_zone_containment``) — measured and
#: said beside Approve, as the code place is, never a block; the margin itself is not moved
ZONE_SAFE_MARGIN_AS_PICTURED = "CONTAINER_ZONE_SAFE_MARGIN_AS_PICTURED"
#: every head the verdict carries as a production note: the maker's specification (exact, as ruled) and the code place
#: [his answer on the safe margin: and a part inside the margin where the concept picture prints it]
#: [His answers after 122 was redrawn, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 0b0c7e7), (1): "a design
#: started from a brief may be approved without an SKU. "SKU missing" shows as a production note, never a block."] a design
#: with no SKU yet — he may add it at any time, on its Gate 2
SKU_NOT_GIVEN = "CONTAINER_SKU_NOT_GIVEN"
PRODUCTION_NOTES = MAKER_SPECIFICATION_NOTES | {BATCH_CODE_PLACE_NOT_CONFIRMED, ZONE_SAFE_MARGIN_AS_PICTURED,
                                                SKU_NOT_GIVEN}


def is_production_note(code) -> bool:
    """A code of the maker's printing specification, read by its head — the detail a code carries after its colon is
    kept as the record wrote it."""
    return str(code).split(":", 1)[0].strip() in PRODUCTION_NOTES        # [§BH71 (0b): and the code place]


def _split_notes(codes) -> tuple[list, list]:
    """(what refuses, the production notes), each in its saved order."""
    codes = list(codes or [])
    return [c for c in codes if not is_production_note(c)], [c for c in codes if is_production_note(c)]


# --- §BH71 (0a), THE OWNER'S GOAL OF 2026-09-28: "My approval overrides §BH50(f)(5). Unmeasured checks (fidelity to the
# --- concept, copy fit) show as a warning beside Approve, never a block."
#: AN ACCEPTANCE WARNING: a code that refuses only because a check is UNMEASURED — the fidelity reports' unmeasured
#: axes and the reports that are absent, the copy fit where it is unmeasured, and the text floor's unmeasured case (a
#: surface whose copy is only depicted). The verdict, and each section that has any, carry it under
#: ``acceptance_warnings``: shown beside Approve and kept with his approval, it never enters ``blocking_codes`` or
#: ``ready`` — and it is never marked passed, because §BH50(f)'s (5) keeps its second half. A MEASURED failure still
#: refuses, and so do placeholder copy, a stale record and his own acceptance; so does a run the emitter did not draw
#: at all ("(NOT_DRAWN)": the copy is missing, not unmeasured). The colour and font read-backs that cannot read
#: (COLOUR_USAGE_UNRECONCILED, CONTAINER_COLOUR_SOURCES_UNREAD, FONT_USAGE_UNRECONCILED) are not here either: they are
#: the instruments of §BH67's hard stops — a colour nothing specified, a face outside the granted set — and a hard
#: stop is not a check his (0a) names. Read at the review from the saved records, never by rewriting one; no check
#: date is added.
ACCEPTANCE_WARNINGS = frozenset({
    "CONTAINER_FIDELITY_UNMEASURED", "CONTAINER_QUANT_FIDELITY_UNMEASURED", "CONTAINER_MOTIF_FIDELITY_UNMEASURED",
    "CONTAINER_TYPOGRAPHY_FIDELITY_UNMEASURED", "CONTAINER_CONCEPT_FIDELITY_UNMEASURED", "CONTAINER_FIDELITY_REPORT_ABSENT",
    "CONTAINER_FRONT_COPY_FIT_UNMEASURED", "CONTAINER_BACK_COPY_FIT_UNMEASURED", "CONTAINER_MINIMUM_TEXT_SIZE_UNMEASURED",
    "CONTAINER_SHADE_ARABIC_UNCONFIRMED"})
#: [his answer of 2026-09-29 to the §BH71 report, (4): "the lid drawing draws the shade name my brief asks for"] the
#: warnings that are words nobody has confirmed rather than checks with no measurement — the record's shade drawn with
#: an Arabic the executor wrote (§BH55(a): "marked rather than assumed"). Beside Approve like the rest, never a block,
#: and said "not confirmed yet", apart from what is "not measured yet".
UNCONFIRMED_WARNINGS = frozenset({"CONTAINER_SHADE_ARABIC_UNCONFIRMED",
                                  # [his review of 119, 2026-10-05, point 6] a label's translations nobody has confirmed
                                  "CARTON_TRANSLATION_UNCONFIRMED"})


def is_acceptance_warning(code) -> bool:
    """A code that refuses only because a check is unmeasured, read by its head — the detail kept as recorded — except
    a run the emitter did not draw at all, which is missing copy and still refuses."""
    code = str(code)
    return code.split(":", 1)[0].strip() in ACCEPTANCE_WARNINGS and "(NOT_DRAWN)" not in code

#: The DECLARED readiness categories, aggregated from 2B-3A..2B-3C and 2C-2E.
#:
#: This tuple is NOT a filter over the persisted codes. It is the complete
#: statement of which categories this repository knows how to interpret, and
#: ``build_readiness`` refuses any category it does not name.
#:
#: §AV1 — it WAS a filter until 2026-08-21, and for 25 days it silently dropped
#: ``content``: the ``CONTENT_VERIFICATION_REQUIRED`` markers that
#: ``targets/container/__init__.py:810`` says "surface in the readiness report
#: and block production authority". Measured, they did neither. The writer
#: (2a92be8, 2026-07-27) added the category three days after the reader
#: (de27a61, 2026-07-24) froze this list, and nothing connected the two — the
#: test fixture re-typed the same eight names, so the test data embodied the
#: omission too.
#:
#: Adding ``"content"`` alone would have repaired that instance and left the
#: mechanism that produced it intact, ready for the next writer. So the
#: mechanism is what changed: an undeclared category now HALTS the report
#: instead of vanishing from it — the way a seventh spelling of "text" halts
#: ``tools/reserved_copy.py``'s scan rather than passing through it unseen.
#: §AV3 adds ``brand_strings`` — the RUNTIME half of the §AE2(c) remedy, and
#: the first category to arrive through the mechanism §AV1 installed rather
#: than around it. That sequence was ruled in advance and is worth recording,
#: because it is the whole argument for why AV1 came first: writing
#: ``readiness["brand_strings"]`` BEFORE declaring it here produces
#: ``UNDECLARED_READINESS_SECTION: brand_strings``, with the brand-string code
#: preserved under ``codes_not_interpreted``. Measured, not assumed. Against
#: the pre-§AV1 eight-name FILTER the same write produced nothing at all —
#: the runtime guard would have reported green while blocking exactly zero,
#: which is the §AA failure this tranche exists to stop manufacturing.
#: §BH50(f)(7): ``colour_usage`` — the colour counter reconciled against every
#: place the artefact applies colour; its disagreement and unread codes join
#: Gate-2 acceptance here, beside the font counter's, and never the
#: reconstruction. The unread code is spelled here as well as in
#: ``colour_roles`` (a test holds the two spellings equal).
#: §BH67 HARD STOP, OWNER RULED 2026-09-24: "a finish or colour applied that nothing specified". ``colour_sources`` —
#: every colour a printed element of the product carries, audited against the records that name them
#: (``colour_sources.printed_colour_audit``); a colour no record names is its code, at acceptance, never the
#: reconstruction. 2645345 WROTE the section and did not declare it here, so every run it reached read
#: UNDECLARED_READINESS_SECTION: colour_sources — exactly the shape §AV1 built this halt to catch, caught by the
#: executor reading a run's refusal after the gate, not by a test. Declared now, with a test that every section a real
#: reconstruction writes is one this module declares.
_SECTIONS = ("back_copy", "brand_strings", "colour_sources", "colour_usage", "content", "font", "front_copy",
             "material", "material_attribution", "production_method", "production_metrics",
             "quantitative_fidelity", "separations", "wrap_alignment")
COLOUR_USAGE_UNRECONCILED_CODE = "COLOUR_USAGE_UNRECONCILED"
#: §BH67: a reconstruction persisted before the audit carries no colour_sources section — its printed colours were
#: never read against a record, which is unmeasured, never clean (the colour_usage precedent below)
COLOUR_SOURCES_UNREAD_CODE = "CONTAINER_COLOUR_SOURCES_UNREAD"
#: §BH50(f)(3): ``front_copy`` — the front's small copy measured against the confirmed zone at the size
#: it is set; an overrun, an unmeasurable run and the unmeasured vertical axis are codes here, at
#: acceptance, and never in the reconstruction blockers. Declared in the same commit as its writer, the
#: §AV1 mechanism. A reconstructed spec that carries no front_copy channel reads UNMEASURED, never clean.
FRONT_COPY_FIT_UNMEASURED = "CONTAINER_FRONT_COPY_FIT_UNMEASURED"

#: §BH54(b), the second block, (q), OWNER RULED 2026-09-19: "THE BACK COPY DOES NOT FIT THIS BODY — a named blocker, not
#: a silence … nothing regulatory is dropped and nothing shrinks below its floor. Record it with its own code … I rule
#: it when I have read that. Everything else proceeds meanwhile; this blocks acceptance of the back, nothing else."
#: ``back_copy`` — declared in the same commit as its writer, the §AV1 mechanism. WHAT STOOD: the back panel names its
#: own overrun, CONTAINER_BACK_PANEL_COPY_EXCEEDS_PANEL — "which blocks", in its module's words — on a fit record that
#: lived in document metadata nothing on the governed path read (the target's own comment, §BH50(b): "a name nothing
#: reads says nothing"). The six unwritten-copy codes blocked the back regardless; his copy channel (8b3f17c) is what
#: removes them, and real words four times the panel's room would then have been drawn as a PREFIX with no blocker on
#: the record — his hard stop, "a regulatory section dropped or shrunk to fit", waiting silently. The record is
#: persisted now and its overflow is this section's code. THERE IS ONE ACCEPTANCE PER OUTPUT: the code sits in its own
#: section so every reader sees WHICH part blocks; it never enters the reconstruction's blockers, never stops a render,
#: an exploration or the loop, and the panel still shrinks nothing and drops nothing to fit.
BACK_COPY_DOES_NOT_FIT = "CONTAINER_BACK_COPY_DOES_NOT_FIT_THIS_BODY"
BACK_COPY_FIT_UNMEASURED = "CONTAINER_BACK_COPY_FIT_UNMEASURED"
#: the STANDING blocker: a record on the spec, written as his ruling awaits, read here at read time — so the blocker
#: holds while the placeholders of the day happen to fit, until he rules one of the ways out
BACK_COPY_BLOCKER_KEY = "container_back_copy_blocker/1.0"
BACK_COPY_AWAITING_RULING = "AWAITING_OWNER_RULING"


def back_copy_codes(fit: dict | None) -> list[str]:
    """The ``back_copy`` readiness codes of ONE run, from the back panel's own fit record (``container_back_panel/1.0``).
    No record, no confirmed zone, or a fit nobody could measure is UNMEASURED — never clean. Copy the panel's edge
    excludes is the named code, with the measurement and the sections by name. Pure."""
    if not fit:
        return [f"{BACK_COPY_FIT_UNMEASURED}: no fit record on this run"]
    if fit.get("fits") is None or not fit.get("fit_measured", True) or fit.get("emitted") is False and fit.get("fits") is not False:
        why = ", ".join(str(c) for c in fit.get("codes") or []) or "the fit was not measured"
        return [f"{BACK_COPY_FIT_UNMEASURED}: {why}"]
    if fit.get("fits") is False:
        out = [s.get("heading") for s in fit.get("sections") or []
               if s.get("lines_emitted", 0) < s.get("lines_required", 0)]
        # [his correction of 2026-10-07: "Only if it still doesn't fit at 3 pt, stop and tell me; don't widen or move
        # anything on your own."] the panel stops only at its floor (``back_panel.label_floor_of``): said so
        return [f"{BACK_COPY_DOES_NOT_FIT}: the back copy needs {fit.get('height_required_mm'):g} mm of the "
                f"{fit.get('height_available_mm'):g} mm its zone gives at {fit.get('size_pt'):g} pt — as small as its "
                f"floor lets the whole label shrink — in a {fit.get('column_mm'):g} mm column — over by "
                f"{fit.get('overflow_mm'):g} mm; outside the panel's edge, whole or in part: "
                f"{', '.join(str(h) for h in out)}. nothing is dropped or moved to fit: what the edge excludes is not "
                "drawn, and this blocks acceptance of the back"]
    return []

#: §AV1: emitted for a persisted category absent from ``_SECTIONS``. Blocking,
#: never advisory — an unrecognised category is a thing whose meaning nobody
#: here can vouch for, and production authority is not granted over it.
UNDECLARED_READINESS_SECTION = "UNDECLARED_READINESS_SECTION"

#: an explicit human acceptance record a future review flow may write; its
#: absence NEVER implies acceptance.
ACCEPTANCE_KEY = "container_human_visual_acceptance"


def human_design_acceptance(spec: dict, preview_sha256=...) -> dict:
    """The HUMAN visual authority for this output — derived only from
    explicit persisted human decisions, never from automated reports.

    * an explicit acceptance record → ACCEPTED
      [§BH71, after (0a), which makes his acceptance what stands between an unmeasured design and approval:
      ``preview_sha256`` is the preview's sha256 as it is NOW (None when it has none), passed where the picture
      is at hand. An acceptance that names other bytes → VOID, and his acceptance is required again; one written
      before any bytes were named, or read where the picture is not at hand, keeps its meaning.]
    * a frozen final-status / rejection snapshot → REJECTED (REVISION_REQUIRED)
      — these codes are never cleared automatically
    * a reconstruction with no human decision on record → NOT_REVIEWED
    """
    acceptance = spec.get(ACCEPTANCE_KEY) or {}
    if acceptance.get("state") == HDA_ACCEPTED and acceptance.get("decided_by"):
        named = acceptance.get("preview_sha256")
        if named and preview_sha256 is not ... and preview_sha256 != named:
            return {"state": HDA_VOID,
                    "decided_by": acceptance.get("decided_by"),
                    "decided_at": acceptance.get("decided_at", ""),
                    "detail": "the picture is no longer the bytes his acceptance names",
                    "codes": [HUMAN_VISUAL_ACCEPTANCE_REQUIRED]}
        return {"state": HDA_ACCEPTED,
                "decided_by": acceptance.get("decided_by"),
                "decided_at": acceptance.get("decided_at", ""),
                "codes": []}
    # §BH55 Phase 1: his door writes REJECTED too, and his last word stands — until 2026-09-19 nothing wrote this
    # record at all, and a REJECTED here would have read as NOT_REVIEWED
    if acceptance.get("state") == HDA_REJECTED and acceptance.get("decided_by"):
        return {"state": f"{HDA_REJECTED} / {HDA_REVISION_REQUIRED}",
                "decided_by": acceptance.get("decided_by"),
                "decided_at": acceptance.get("decided_at", ""),
                "codes": [HUMAN_VISUAL_ACCEPTANCE_REQUIRED]}
    final = spec.get("container_2b3v_final_status/1.0") or {}
    rejections = [k for k in spec
                  if k.startswith("container_reconstruction_rejected")]
    if final.get("gate2_human_acceptance") == "REJECTED" or rejections:
        return {"state": f"{HDA_REJECTED} / {HDA_REVISION_REQUIRED}",
                "rejections_on_record": sorted(rejections),
                "blocking_codes_preserved": list(
                    final.get("blocking_codes") or []),
                "codes": [HUMAN_VISUAL_ACCEPTANCE_REQUIRED]}
    if spec.get("container_reconstruction"):
        return {"state": HDA_NOT_REVIEWED,
                "detail": "a native reconstruction exists but no human visual "
                          "decision is on record",
                "codes": [HUMAN_VISUAL_ACCEPTANCE_REQUIRED]}
    return {"state": HDA_NOT_REVIEWED,
            "codes": [CONTAINER_RECONSTRUCTION_ABSENT]}


def _print_data(spec: dict) -> dict:
    """Container print-data facts: the coding zone, live product name and SKU
    the printed container cannot ship without."""
    zones = (spec.get("container_decoration_zones/1.0") or {}).get("zones") or []
    has_code_zone = any(z.get("zone_type") == "BOTTOM_CODE_ZONE" for z in zones)
    facts = {
        "product_name_present": bool(spec.get("product_name")),
        "sku_present": bool(spec.get("sku")),
        "code_zone_confirmed": has_code_zone,
    }
    # [§BH71 (0b): a missing code place is a production note naming the place its form offers, never a refusal;
    # the product's name still refuses — and, his answers after 122 was redrawn (1), a missing SKU is a note]
    codes = [f"{CONTAINER_PRINT_DATA_INCOMPLETE}: {name}"
             for name, ok in facts.items() if not ok and name not in ("code_zone_confirmed", "sku_present")]
    if not facts["sku_present"]:
        codes.append(f"{SKU_NOT_GIVEN}: none given yet — it may be added at any time")
    if not has_code_zone:
        from apps.pipeline.services import container_contract as cc
        record = spec.get(cc.PROFILE_SCHEMA) or {}
        place = cc.code_zone_for(record, zones) if record else None
        codes.append(f"{BATCH_CODE_PLACE_NOT_CONFIRMED}: proposed — {cc.code_place_words(place)}" if place else
                     f"{BATCH_CODE_PLACE_NOT_CONFIRMED}: none proposed — the record names no form to propose one on")
    return {"facts": facts, "codes": codes}


def _output_intent() -> dict:
    from apps.dielines.exporters.output_intent import describe_profile
    identity = describe_profile()
    d = identity.to_dict() if hasattr(identity, "to_dict") else dict(identity)
    codes = [] if d.get("valid") else [
        f"{MISSING_OUTPUT_INTENT}: {d.get('validation_result', '')}"]
    return {"identity": d, "codes": codes}


# --- §BH50(f)(5): UNMEASURED BLOCKS — WITH ONE SCOPE ------------------------
#: An unmeasured fidelity axis blocks ACCEPTANCE of production artwork —
#: Gate-2 approval, which reads this verdict — and is never marked passed. It
#: does NOT block exploration: nothing here is a reconstruction blocker, and
#: the reconstruction reaches RECONSTRUCTED exactly as before. The section is
#: DERIVED AT READ TIME from the persisted fidelity reports, like
#: ``print_data`` and ``output_intent``, and deliberately NOT declared in
#: ``_SECTIONS``: a key the target persisted would be absent from every spec
#: persisted before it (task 52's included), and a declared absent key reads
#: [] silently in the loop below — §AV1's failure with a declaration on top.
#: Rule 4's label UNMEASURED_BLOCKING (container_fidelity.py) is enforced
#: here and nowhere else, which is what makes it true (§BH50(f)(4)).
FIDELITY_UNMEASURED = "CONTAINER_FIDELITY_UNMEASURED"
QUANT_FIDELITY_UNMEASURED = "CONTAINER_QUANT_FIDELITY_UNMEASURED"
MOTIF_FIDELITY_UNMEASURED = "CONTAINER_MOTIF_FIDELITY_UNMEASURED"
TYPOGRAPHY_FIDELITY_UNMEASURED = "CONTAINER_TYPOGRAPHY_FIDELITY_UNMEASURED"
CONCEPT_FIDELITY_UNMEASURED = "CONTAINER_CONCEPT_FIDELITY_UNMEASURED"
FIDELITY_REPORT_ABSENT = "CONTAINER_FIDELITY_REPORT_ABSENT"
#: every persisted fidelity report that carries axes, with the code prefix its
#: unmeasured axes take. A report ABSENT from a reconstructed spec is every
#: axis unmeasured, and says so — silence is the §AV1 shape.
FIDELITY_REPORTS = (
    ("container_fidelity_report", FIDELITY_UNMEASURED),
    ("container_quantitative_fidelity/1.0", QUANT_FIDELITY_UNMEASURED),
    ("container_motif_fidelity_report", MOTIF_FIDELITY_UNMEASURED),
    ("container_typography_fidelity_report", TYPOGRAPHY_FIDELITY_UNMEASURED),
    ("container_concept_fidelity/1.0", CONCEPT_FIDELITY_UNMEASURED),
)
_MEASURED_STATES = ("MEASURED_PASS", "MEASURED_FAIL")
_NOT_APPLICABLE = "NOT_APPLICABLE"
FIDELITY_UNMEASURED_SCOPE = (
    "ACCEPTANCE — derived at read time from the persisted fidelity reports; "
    "never persisted, never a reconstruction blocker (§BH50(f)(5))")


def _seam_check(spec: dict) -> dict:
    """The seam check's applicability for this spec: the persisted record's
    own when the reconstruction wrote one (§BH50(f)(6)), else derived from the
    zone record by the same predicate — so a spec persisted before the state
    existed reads exactly as one written after it. A zone spelling problem is
    a finding here and never a raise: this is a read-only verdict a board
    prints, and a board must not fail because a stored zone is misspelled."""
    rec = (spec.get("container_wrap_alignment") or {}).get("seam_check")
    if rec and rec.get("state"):
        return {"state": rec["state"], "reason": rec.get("reason") or ""}
    from apps.ire import container_wrap_geometry as cwg
    from apps.pipeline.services import container_contract as cc
    zones = (spec.get(cc.ZONES_SCHEMA) or {}).get("zones") or []
    try:
        app = cwg.seam_applicability(zones)
    except cc.ZoneSurfaceSpellingError as exc:
        return {"state": cwg.UNMEASURED,
                "reason": f"{cc.ZONE_SURFACE_KEY_UNRECOGNISED}: {exc}"}
    return {"state": app["state"], "reason": app["reason"]}


def fidelity_unmeasured(spec: dict) -> dict:
    """§BH50(f)(5): one code per fidelity axis that is neither MEASURED_PASS
    nor MEASURED_FAIL, over every persisted report, for a spec that carries a
    reconstruction. Applicability is derived from the product's own facts at
    read time: the base report's ``wrap_alignment`` axis is NOT_APPLICABLE,
    with its reason, on a product with no wrapped surface (§BH50(f)(6)) — the
    one derivation the seam check itself uses, so the two records agree. No
    axis is deferred to a sibling record: a sibling that measures a different
    quantity does not discharge it."""
    if not spec.get("container_reconstruction"):
        return {"codes": [], "axes": {}, "not_applicable": {},
                "reports_absent": [], "scope": FIDELITY_UNMEASURED_SCOPE}
    codes: list[str] = []
    axes: dict[str, str] = {}
    not_applicable: dict[str, str] = {}
    absent: list[str] = []
    seam = None
    for key, prefix in FIDELITY_REPORTS:
        rep = spec.get(key)
        if not rep:
            absent.append(key)
            codes.append(f"{FIDELITY_REPORT_ABSENT}: {key}")
            continue
        raw = rep.get("axes")
        items = (list(raw.items()) if isinstance(raw, dict)
                 else [(a.get("axis"), a) for a in (raw or [])
                       if isinstance(a, dict)])
        for name, axis in items:
            state = str((axis or {}).get("state") or "")
            axes[f"{key}:{name}"] = state
            if state in _MEASURED_STATES:
                continue
            if key == "container_fidelity_report" and name == "wrap_alignment":
                seam = seam if seam is not None else _seam_check(spec)
                if seam["state"] == _NOT_APPLICABLE:
                    not_applicable[f"{key}:{name}"] = seam["reason"]
                    continue
            codes.append(f"{prefix}: {name}")
    return {"codes": codes, "axes": axes, "not_applicable": not_applicable,
            "reports_absent": absent, "scope": FIDELITY_UNMEASURED_SCOPE}


def build_readiness(spec: dict, preview_sha256=...) -> dict:
    """container_production_readiness/1.0 — the aggregated Gate-2 verdict.

    ``ready`` is True only when EVERY section is clean AND a human has
    explicitly accepted the design. There is no override flag.

    [The owner's answer of 2026-09-27: clean of what refuses. A code of the maker's printing specification
    (``MAKER_SPECIFICATION_NOTES``) is a production note — the verdict, and each section that has any, carry it
    under ``production_notes`` — and it never enters ``blocking_codes`` or ``ready``.]"""
    sections: dict = {}
    aggregated: list[str] = []
    production_notes: list[str] = []
    persisted = spec.get("container_production_readiness_codes") or {}
    for name in _SECTIONS:
        entry = persisted.get(name)
        codes = (entry if isinstance(entry, list)
                 else (entry or {}).get("codes", []) if isinstance(entry, dict)
                 else [])
        blocking_here, notes_here = _split_notes(codes)
        sections[name] = {"codes": blocking_here, **({"production_notes": notes_here} if notes_here else {})}
        aggregated.extend(str(c) for c in blocking_here)
        production_notes.extend(str(c) for c in notes_here)

    # §BH50(f)(3): a reconstructed spec persisted before the front_copy
    # channel existed carries no fit — UNMEASURED at read time, never clean.
    if spec.get("container_reconstruction") and "front_copy" not in persisted:
        code = f"{FRONT_COPY_FIT_UNMEASURED}: no front copy fit on record"
        sections["front_copy"]["codes"].append(code)
        aggregated.append(code)

    # §BH54(b) (q): a reconstructed spec persisted before the back_copy section existed carries no back-copy fit —
    # UNMEASURED at read time, never clean; and the STANDING blocker, his ruling awaited, is read here whatever the
    # panel of the day holds
    if spec.get("container_reconstruction") and "back_copy" not in persisted:
        code = f"{BACK_COPY_FIT_UNMEASURED}: no back copy fit on record"
        sections["back_copy"]["codes"].append(code)
        aggregated.append(code)
    standing = spec.get(BACK_COPY_BLOCKER_KEY) or {}
    if standing.get("status") == BACK_COPY_AWAITING_RULING and not any(
            str(c).startswith(BACK_COPY_DOES_NOT_FIT) for c in sections["back_copy"]["codes"]):
        code = f"{BACK_COPY_DOES_NOT_FIT}: {standing.get('summary') or 'his ruling is awaited'}"
        sections["back_copy"]["codes"].append(code)
        aggregated.append(code)

    # §BH50(f)(2): a reconstructed spec with no placeholder-copy record is not
    # "all copy supplied" — silence is the §AV1 shape. Derived at read time,
    # so a spec persisted before the record existed says so too.
    if spec.get("container_reconstruction") and not spec.get(
            "container_placeholder_copy/1.0"):
        code = ("CONTENT_VERIFICATION_REQUIRED: no placeholder-copy record on "
                "this reconstruction")
        sections["content"]["codes"].append(code)
        aggregated.append(code)

    # §BH50(f)(7): a reconstructed spec persisted before the colour_usage
    # section existed carries no colour reconciliation this module can read;
    # that is unmeasured, never "no defect". Derived at read time, like the
    # placeholder code above.
    if spec.get("container_reconstruction") and "colour_usage" not in persisted:
        code = (f"{COLOUR_USAGE_UNRECONCILED_CODE}: no colour_usage readiness "
                "section on this reconstruction (persisted before §BH50(f)(7))")
        sections["colour_usage"]["codes"].append(code)
        aggregated.append(code)

    # §BH67 HARD STOP: the same, for the printed-colour audit — a reconstruction persisted before it printed colours
    # nobody read against a record (task 91's lid printed the dropper's #5A2C3A); unread, never clean
    if spec.get("container_reconstruction") and "colour_sources" not in persisted:
        code = (f"{COLOUR_SOURCES_UNREAD_CODE}: no colour_sources readiness section on this "
                "reconstruction (persisted before §BH67's hard stop) — its printed colours were never read "
                "against a record")
        sections["colour_sources"]["codes"].append(code)
        aggregated.append(code)

    # §BH50(f)(6): the seam check's applicability travels beside its codes, so
    # a product with no wrapped surface reads NOT_APPLICABLE with its reason
    # HERE, where Gate 2 and the board look — never PASS and never silence.
    # Additive: the codes list stays the blocking input, and aggregation and
    # `ready` are unchanged.
    seam = (spec.get("container_wrap_alignment") or {}).get("seam_check")
    if seam and "wrap_alignment" in sections:
        sections["wrap_alignment"]["seam_check"] = {
            "state": seam.get("state"), "reason": seam.get("reason")}

    # §AV1: a persisted category this module does not declare is NOT dropped.
    # The codes under it are surfaced uninterpreted, for diagnosis, but they are
    # not what blocks — the undeclared category itself is. Interpreting codes
    # from a category nobody declared would be guessing at their meaning, which
    # is the failure one level down from the one this repairs.
    for name in sorted(set(persisted) - set(_SECTIONS)):
        entry = persisted.get(name)
        found = (entry if isinstance(entry, list)
                 else (entry or {}).get("codes", []) if isinstance(entry, dict)
                 else [])
        code = f"{UNDECLARED_READINESS_SECTION}: {name}"
        sections[name] = {"codes": [code], "undeclared": True,
                          "codes_not_interpreted": [str(c) for c in found]}
        aggregated.append(code)

    print_data = _print_data(spec)
    print_data["codes"], data_notes = _split_notes(print_data["codes"])  # §BH71 (0b): the code place is a note
    if data_notes:
        print_data["production_notes"] = data_notes
    sections["print_data"] = print_data
    aggregated.extend(print_data["codes"])
    production_notes.extend(data_notes)

    intent = _output_intent()
    intent["codes"], intent_notes = _split_notes(intent["codes"])       # the print shop's profile is a note
    if intent_notes:
        intent["production_notes"] = intent_notes
    sections["output_intent"] = intent
    aggregated.extend(intent["codes"])
    production_notes.extend(intent_notes)

    # §BH50(f)(5): the unmeasured fidelity axes, derived at read time and
    # absent from _SECTIONS by design (see fidelity_unmeasured). They block
    # acceptance here; the reconstruction never sees them.
    # [§BH71 (0a): his approval overrides this — they are acceptance warnings, split out below]
    unmeasured = fidelity_unmeasured(spec)
    sections["fidelity_unmeasured"] = unmeasured
    aggregated.extend(unmeasured["codes"])

    # §BH71 (0a): every code that refuses only because a check is unmeasured is an acceptance warning, wherever it
    # was read — shown beside Approve, never in blocking_codes or ready, and never marked passed
    acceptance_warnings = [c for c in aggregated if is_acceptance_warning(c)]
    aggregated = [c for c in aggregated if not is_acceptance_warning(c)]
    for section in sections.values():
        here = section.get("codes") if isinstance(section, dict) else None
        if isinstance(here, list) and any(is_acceptance_warning(c) for c in here):
            section["acceptance_warnings"] = [c for c in here if is_acceptance_warning(c)]
            section["codes"] = [c for c in here if not is_acceptance_warning(c)]

    # the human category is evaluated LAST but ranked FIRST: it can never be
    # outvoted by the automated sections above.
    human = human_design_acceptance(spec, preview_sha256)      # §BH71: the picture, where it is at hand
    sections["human_design_acceptance"] = human
    blocking = list(human["codes"]) + aggregated

    return {
        "schema_version": SCHEMA,
        "sections": sections,
        "human_design_acceptance_state": human["state"],
        "blocking_codes": blocking,
        "production_notes": production_notes,
        "acceptance_warnings": acceptance_warnings,
        "ready": not blocking,
    }


#: §BH50(g)(4), OWNER RULED — typed 2026-09-17, re-typed in OWNER RULING §BH53(a) (OWNER_BLOCKER_CLEARANCE.md
#: :21615-21617): "A STALE SPEC NEVER SHOWS AS CURRENT. The review board re-derives codes at readiness-read, or
#: marks the spec stale with the date its checks predate." Both halves: the board and the history print the reader's
#: own verdict, derived at readiness-read (``build_readiness``), and every reconstructed spec whose saved sections or
#: reports fall short of what HEAD's checks write is marked STALE with the date each check it predates was introduced
#: — its ruling and its commit beside the date. Nothing is rewritten ("historical persisted reports are audit evidence
#: and are never rewritten", container_fidelity.py) and nothing newly blocks: the persisted codes keep their role; the
#: mark informs. The declaration carries its date at the one place §AV1 forces a section to be declared: a name in
#: _SECTIONS with no date here is a census failure (test_2b3d_readiness pins it). Dates are the commits' own
#: (git log -S over this module), never typed from memory.
SECTION_SINCE = {
    "font": ("2026-07-24", "2B-3D", "de27a61"),
    "material": ("2026-07-24", "2B-3D", "de27a61"),
    "material_attribution": ("2026-07-24", "2B-3D", "de27a61"),
    "production_method": ("2026-07-24", "2B-3D", "de27a61"),
    "production_metrics": ("2026-07-24", "2B-3D", "de27a61"),
    "quantitative_fidelity": ("2026-07-24", "2B-3D", "de27a61"),
    "separations": ("2026-07-24", "2B-3D", "de27a61"),
    "wrap_alignment": ("2026-07-24", "2B-3D", "de27a61"),
    "content": ("2026-08-21", "§AV1", "77c144f"),
    "brand_strings": ("2026-08-21", "§AV3", "0027f41"),
    "front_copy": ("2026-09-17", "§BH50(f)(3)", "518dae2"),
    "colour_usage": ("2026-09-17", "§BH50(f)(7)", "ce19952"),
    "back_copy": ("2026-09-19", "§BH54(b) (q)", "q-back-copy"),      # the commit's own subject tag: a commit cannot cite its hash
    "colour_sources": ("2026-09-24", "§BH67 HARD STOP", "2645345"),   # the writer's commit; declared one commit later
}
#: check changes a spec can predate WITHOUT a missing key — read from the saved report's own content, never by
#: re-running a check on the drawing (that would compose, and a read writes nothing)
CHECK_EPOCHS = {
    "rule4_fail_closed": {"since": "2026-08-03", "ruling": "VQR-2A §6", "commit": "5512cdc",
                          "what": "container_fidelity_report: MEASURED_PASS requires every required axis MEASURED_PASS; "
                                  "an unmeasured required axis reads UNMEASURED_BLOCKING"},
    "pass_never_outvotes": {"since": "2026-09-17", "ruling": "§BH50(f)(5)", "commit": "27942c3",
                            "what": "the motif and quantitative reports: a measured pass beside an unmeasured axis reads "
                                    "UNMEASURED_BLOCKING"},
    "seam_on_wrapped_surfaces": {"since": "2026-09-17", "ruling": "§BH50(f)(6)", "commit": "39959b1",
                                 "what": "the seam check is placed on wrapped surfaces; a projected face reads NOT_APPLICABLE "
                                         "and carries no seam code"},
    "front_copy_safe_area": {"since": "2026-09-18", "ruling": "§BH50(g)(1), re-typed §BH53(a)",
                             "commit": "container_front_copy_fit/1.1",
                             "what": "the front-copy verdict is against the zone's safe area; a /1.0 record's verdict was "
                                     "against the zone"},
    # §BH70(1), item 5 of the list the owner was sent: the generic path's front copy is measured across, where its
    # only code had been that the path had no fit instrument — a spec saved with that code predates the reading
    "front_copy_generic_path": {"since": "2026-09-27", "ruling": "§BH70(1), item 5 of the list the owner was sent",
                                "commit": "container_front_copy_fit/1.1 on the generic path",
                                "what": "the front copy of a product the generic composer draws is measured across "
                                        "against the confirmed zone's safe area; before, its only code said nothing "
                                        "could measure it"},
}
#: the words of the one code the generic path wrote before §BH70(1) item 5 measured its front copy
GENERIC_NO_FIT_INSTRUMENT = "no fit instrument on this path"
_SEAM_CODES = ("CONTAINER_WRAP_SEAM_CONFLICT", "CONTAINER_TEXT_CROSSES_SEAM")


def spec_staleness(spec: dict) -> dict:
    """§BH50(g)(4): what HEAD's checks write that this reconstructed spec lacks, each with the date it predates —
    read from the saved records alone, never by composing and never by rewriting a saved report. A spec with no
    reconstruction has no checks to be stale. Additive: ``build_readiness`` and ``gate2_refusal`` never read this.
    [§BH54(d), 2026-09-18: ``gate2_refusal`` reads it since — at ACCEPTANCE alone; ``build_readiness`` still never does,
    so the mark stays information on every board and page.]"""
    if not spec.get("container_reconstruction"):
        return {"stale": False, "checks_predate": [], "latest_since": None, "reason": "no reconstruction on this spec"}
    items = []
    persisted = spec.get("container_production_readiness_codes") or {}
    for name in _SECTIONS:
        if name not in persisted:
            since, ruling, commit = SECTION_SINCE[name]
            items.append({"kind": "MISSING_SECTION", "since": since, "ruling": ruling, "commit": commit,
                          "what": f"readiness section {name!r}"})

    def states(report):
        axes = (report or {}).get("axes") or {}
        if not isinstance(axes, dict):
            return []
        return [((a or {}).get("state"), (a or {}).get("required", True)) for a in axes.values()]

    base = spec.get("container_fidelity_report") or {}
    if base.get("overall") == "MEASURED_PASS" and any(s == "UNMEASURED" and req for s, req in states(base)):
        items.append({"kind": "REPORT_OVERALL", **CHECK_EPOCHS["rule4_fail_closed"],
                      "what": "container_fidelity_report reads MEASURED_PASS over an unmeasured required axis"})
    for key in ("container_motif_fidelity_report", "container_quantitative_fidelity/1.0"):
        rep = spec.get(key) or {}
        if rep.get("overall") == "MEASURED_PASS" and any(s == "UNMEASURED" for s, _ in states(rep)):
            items.append({"kind": "REPORT_OVERALL", **CHECK_EPOCHS["pass_never_outvotes"],
                          "what": f"{key} reads MEASURED_PASS beside an unmeasured axis"})
    wrap = persisted.get("wrap_alignment")
    wrap_codes = (wrap if isinstance(wrap, list) else (wrap or {}).get("codes", []) if isinstance(wrap, dict) else [])
    if any(str(c).startswith(_SEAM_CODES) for c in wrap_codes) and _seam_check(spec).get("state") == "NOT_APPLICABLE":
        items.append({"kind": "SEAM_CODES", **CHECK_EPOCHS["seam_on_wrapped_surfaces"],
                      "what": "seam codes saved on a surface the seam check does not apply to"})
    if "container_front_copy_fit/1.0" in spec and "container_front_copy_fit/1.1" not in spec:
        items.append({"kind": "RECORD_VERSION", **CHECK_EPOCHS["front_copy_safe_area"],
                      "what": "container_front_copy_fit/1.0 — a verdict against the zone"})
    front = persisted.get("front_copy")
    front_codes = (front if isinstance(front, list) else (front or {}).get("codes", []) if isinstance(front, dict)
                   else [])
    if any(GENERIC_NO_FIT_INSTRUMENT in str(c) for c in front_codes):
        items.append({"kind": "SECTION_VERDICT", **CHECK_EPOCHS["front_copy_generic_path"],
                      "what": "its saved front-copy verdict says nothing could measure it; today each line's width "
                              "is measured against the confirmed zone"})
    latest = max((i["since"] for i in items), default=None)
    return {"stale": bool(items), "checks_predate": items, "latest_since": latest,
            "reason": (f"the saved checks predate {len(items)} change(s) to what HEAD writes, the latest {latest}"
                       if items else "every declared section and report this module reads is HEAD's")}


#: §BH54(d), OWNER RULED 2026-09-18: "A STALE MARK DOES NOT BLOCK. It says a verdict predates today's checks —
#: information, not refusal. What blocks is acceptance: a STALE spec is re-derived before it can be accepted and the
#: re-derivation decides." The code acceptance answers with; nothing else reads the mark as a refusal.
SPEC_STALE_REDERIVE_REQUIRED = "SPEC_STALE_REDERIVE_REQUIRED"


def gate2_refusal(spec: dict, preview_sha256=...) -> dict | None:
    """The Gate-2 enforcement verdict: a refusal payload, or None when
    approval may proceed. Refuses when the latest human decision is REJECTED,
    when no human has reviewed the reconstruction, or when any automated
    readiness section still carries codes.

    §BH54(d): a STALE spec is refused first and by name, whatever its saved codes say — the saved verdict is the
    thing that predates today's checks, so it decides nothing at acceptance; the re-derivation (a reconstruction of
    the same confirmed profile) writes the codes that do. What today's reader finds in the saved record follows the
    stale line in `failures`, as information about that record — never as the verdict.

    [§BH71: ``preview_sha256`` — the picture as it is now; Gate 2 passes it, so an acceptance of other bytes
    approves nothing.]"""
    report = build_readiness(spec, preview_sha256)
    stale = spec_staleness(spec)
    if stale["stale"]:
        return {
            "error": SPEC_STALE_REDERIVE_REQUIRED,
            "human_design_acceptance": report["human_design_acceptance_state"],
            "failures": [f"{SPEC_STALE_REDERIVE_REQUIRED}: the saved verdict predates {len(stale['checks_predate'])} "
                         f"of today's checks (latest {stale['latest_since']}) — re-derive; the re-derivation decides",
                         *report["blocking_codes"]],
            "staleness": stale,
            "production_notes": report["production_notes"],
            "acceptance_warnings": report["acceptance_warnings"],
            "readiness": report,
        }
    if report["ready"]:
        return None
    return {
        "error": "PRODUCTION_NOT_READY",
        "human_design_acceptance": report["human_design_acceptance_state"],
        "failures": report["blocking_codes"],
        "production_notes": report["production_notes"],
        "acceptance_warnings": report["acceptance_warnings"],
        "readiness": report,
    }


__all__ = [
    "SCHEMA", "build_readiness", "gate2_refusal", "human_design_acceptance",
    "HDA_NOT_REVIEWED", "HDA_ACCEPTED", "HDA_REJECTED",
    "HDA_REVISION_REQUIRED", "HUMAN_VISUAL_ACCEPTANCE_REQUIRED", "HDA_VOID",
    "MISSING_OUTPUT_INTENT", "UNDECLARED_READINESS_SECTION", "COLOUR_SOURCES_UNREAD_CODE",
    # the owner's answer of 2026-09-27
    "MAKER_SPECIFICATION_NOTES", "is_production_note",
    # §BH71 (0b)
    "BATCH_CODE_PLACE_NOT_CONFIRMED", "PRODUCTION_NOTES",
    # §BH71 (0a)
    "ACCEPTANCE_WARNINGS", "is_acceptance_warning", "UNCONFIRMED_WARNINGS",
    "CONTAINER_PRINT_DATA_INCOMPLETE",
    "CONTAINER_RECONSTRUCTION_ABSENT", "ACCEPTANCE_KEY",
    "FRONT_COPY_FIT_UNMEASURED",
    # §BH50(g)(4)
    "SECTION_SINCE", "CHECK_EPOCHS", "spec_staleness", "SPEC_STALE_REDERIVE_REQUIRED",
    # §BH50(f)(7)
    "COLOUR_USAGE_UNRECONCILED_CODE",
    # §BH50(f)(5)
    "fidelity_unmeasured", "FIDELITY_REPORTS", "FIDELITY_UNMEASURED",
    "QUANT_FIDELITY_UNMEASURED", "MOTIF_FIDELITY_UNMEASURED",
    "TYPOGRAPHY_FIDELITY_UNMEASURED", "CONCEPT_FIDELITY_UNMEASURED",
    "FIDELITY_REPORT_ABSENT", "FIDELITY_UNMEASURED_SCOPE",
]
