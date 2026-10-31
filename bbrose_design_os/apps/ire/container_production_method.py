"""Container production-method contract + validation (Phase 2B-3B, §1-§5/§9/§10).

Production methods are DERIVED from the confirmed decoration zones'
``permitted_techniques`` (the only source that exists — there is no method
picker). The load-bearing invariant: a technique that was a ``propose_zones``
machine default, confirmed only as part of zone geometry, is NEVER manufacturer
authority. So:

* authority defaults to ``USER_REQUESTED_UNVERIFIED`` /
  ``INFERRED_NONAUTHORITATIVE``;
* only ``VERIFIED_MANUFACTURER_CAPABILITY`` (from verified manufacturer/supplier
  evidence, which this phase has no channel to obtain) clears a readiness
  blocker — so a container's production-method authority stays UNVERIFIED by
  construction, and that is the intended, honest state;
* manufacturer capability is never inferred from a photo, a concept render, a
  historical design, or "what similar containers usually use".

[The owner's answer of 2026-09-27 to the §BH70 report's first question: "The maker's printing specification is
shown as a production note, never a blocker." Every code below that the maker's verified capability alone would
clear, or that compares the design with the inferred table, is read at the review as a production note
(``container_production_readiness.MAKER_SPECIFICATION_NOTES``) — what this module writes is unchanged, and the
text floor (§W2, §Y1) still refuses.]

Constraint checks (color count / line weight / text size) measure the EMITTED
geometry against INFERRED type-default limits. A PASS never clears the gate
(only verified authority does); a FAIL is a real advisory signal. All codes are
PRODUCTION-READINESS codes → they never enter the reconstruction ``blockers``.
"""
from __future__ import annotations

import hashlib
import json

from apps.pipeline.services.container_contract import zone_surface

# --- authority states (§2) ---------------------------------------------------
VERIFIED_MANUFACTURER_CAPABILITY = "VERIFIED_MANUFACTURER_CAPABILITY"
USER_REQUESTED_UNVERIFIED = "USER_REQUESTED_UNVERIFIED"
INFERRED_NONAUTHORITATIVE = "INFERRED_NONAUTHORITATIVE"
UNSUPPORTED = "UNSUPPORTED"
UNKNOWN = "UNKNOWN"

# --- verification sources (§3) -----------------------------------------------
SRC_MANUFACTURER_SPEC = "VERIFIED_MANUFACTURER_SPEC"
SRC_SUPPLIER_CONFIRMATION = "VERIFIED_SUPPLIER_CONFIRMATION"
SRC_PRODUCT_RECORD = "VERIFIED_PRODUCT_RECORD"
SRC_USER_REQUEST = "EXPLICIT_USER_REQUEST"
SRC_REFERENCE_OBSERVATION = "REFERENCE_DESIGN_OBSERVATION"
SRC_INFERRED = "INFERRED_NONAUTHORITATIVE"
SRC_UNKNOWN = "UNKNOWN"
#: only these clear VERIFIED_MANUFACTURER_CAPABILITY
_AUTHORITATIVE_SOURCES = frozenset({SRC_MANUFACTURER_SPEC,
                                    SRC_SUPPLIER_CONFIRMATION})

# --- §5 validation codes -----------------------------------------------------
TECHNIQUE_UNVERIFIED = "CONTAINER_TECHNIQUE_UNVERIFIED"
TECHNIQUE_UNSUPPORTED = "CONTAINER_TECHNIQUE_UNSUPPORTED"
METHOD_ZONE_MISMATCH = "CONTAINER_METHOD_ZONE_MISMATCH"
METHOD_SURFACE_MISMATCH = "CONTAINER_METHOD_SURFACE_MISMATCH"
MATERIAL_TECHNIQUE_MISMATCH = "CONTAINER_MATERIAL_TECHNIQUE_MISMATCH"
COLOR_COUNT_EXCEEDED = "CONTAINER_COLOR_COUNT_EXCEEDED"
MINIMUM_LINE_WEIGHT_FAILED = "CONTAINER_MINIMUM_LINE_WEIGHT_FAILED"
MINIMUM_TEXT_SIZE_FAILED = "CONTAINER_MINIMUM_TEXT_SIZE_FAILED"
#: §BH50(f)(1)/(5): a method's surface whose product copy is drawn only as a
#: depiction on this document — no printed run to measure against the
#: method's floor. An unmeasured surface is never read as passed; it blocks
#: acceptance through the production_method readiness section.
MINIMUM_TEXT_SIZE_UNMEASURED = "CONTAINER_MINIMUM_TEXT_SIZE_UNMEASURED"
REGISTRATION_TOLERANCE_FAILED = "CONTAINER_REGISTRATION_TOLERANCE_FAILED"
MAXIMUM_COVERAGE_EXCEEDED = "CONTAINER_MAXIMUM_COVERAGE_EXCEEDED"
WHITE_UNDERBASE_REQUIRED = "CONTAINER_WHITE_UNDERBASE_REQUIRED"
TRAPPING_REVIEW_REQUIRED = "CONTAINER_TRAPPING_REVIEW_REQUIRED"
OVERPRINT_REVIEW_REQUIRED = "CONTAINER_OVERPRINT_REVIEW_REQUIRED"

SCHEMA = "container_production_method/1.0"

_CAP_SURFACES = ("CAP_FRONT", "CAP_BACK", "CAP_TOP", "CAP_WRAP")

#: technique (2B-1 vocabulary) + surface/zone → production method_type (§4).
_TECHNIQUE_METHOD = {
    "screen_printing": ("CAP_PRINT", "SCREEN_PRINT"),
    "pad_printing": ("CAP_PRINT", "PAD_PRINT"),
    "hot_stamping": ("CAP_HOT_STAMP", "HOT_STAMP"),
    "adhesive_label": ("ADHESIVE_LABEL", "ADHESIVE_LABEL"),
    "wrap_label": ("WRAP_LABEL", "WRAP_LABEL"),
    "shrink_sleeve": ("SHRINK_SLEEVE", "SHRINK_SLEEVE"),
    "emboss": ("EMBOSS", "EMBOSS"),
    "deboss": ("DEBOSS", "DEBOSS"),
}

#: INFERRED_NONAUTHORITATIVE type defaults — typical values, NEVER manufacturer
#: authority. A PASS against these does not clear the gate.
_METHOD_DEFAULTS = {
    "SCREEN_PRINT": {"max_colors": 4, "min_line_mm": 0.20, "min_text_pt": 5.0,
                     "max_coverage": 0.90, "registration_mm": 0.30,
                     "white_underbase": "conditional"},
    "PAD_PRINT": {"max_colors": 2, "min_line_mm": 0.25, "min_text_pt": 5.0,
                  "max_coverage": 0.70, "registration_mm": 0.35,
                  "white_underbase": "conditional"},
    "HOT_STAMP": {"max_colors": 1, "min_line_mm": 0.30, "min_text_pt": 6.0,
                  "max_coverage": 0.50, "registration_mm": 0.40,
                  "white_underbase": "no"},
    "CAP_PRINT": {"max_colors": 2, "min_line_mm": 0.25, "min_text_pt": 5.0,
                  "max_coverage": 0.70, "registration_mm": 0.35,
                  "white_underbase": "conditional"},
    "CAP_HOT_STAMP": {"max_colors": 1, "min_line_mm": 0.30, "min_text_pt": 6.0,
                      "max_coverage": 0.50, "registration_mm": 0.40,
                      "white_underbase": "no"},
    "ADHESIVE_LABEL": {"max_colors": None, "min_line_mm": 0.15,
                       "min_text_pt": 4.0, "max_coverage": 1.0,
                       "registration_mm": 0.20, "white_underbase": "no"},
    "WRAP_LABEL": {"max_colors": None, "min_line_mm": 0.15, "min_text_pt": 4.0,
                   "max_coverage": 1.0, "registration_mm": 0.20,
                   "white_underbase": "no"},
    "SHRINK_SLEEVE": {"max_colors": None, "min_line_mm": 0.20,
                      "min_text_pt": 5.0, "max_coverage": 1.0,
                      "registration_mm": 0.50, "white_underbase": "conditional"},
    "EMBOSS": {"max_colors": 0, "min_line_mm": 0.50, "min_text_pt": 8.0,
               "max_coverage": 0.40, "registration_mm": 0.40,
               "white_underbase": "no"},
    "DEBOSS": {"max_colors": 0, "min_line_mm": 0.50, "min_text_pt": 8.0,
               "max_coverage": 0.40, "registration_mm": 0.40,
               "white_underbase": "no"},
    "BOTTOM_INKJET_CODE": {"max_colors": 1, "min_line_mm": 0.10,
                           "min_text_pt": 2.0, "max_coverage": 0.20,
                           "registration_mm": 0.50, "white_underbase": "no"},
}


# --- §Y1: who may move a floor -----------------------------------------------
#: Provenance values for a single constraint field on a built method record.
#: §Y1(d): a provenance field that is a constant is not provenance.
ORIGIN_TYPE_DEFAULT = "INFERRED_NONAUTHORITATIVE_TYPE_DEFAULT"
ORIGIN_ZONE_TIGHTENED = "ZONE_TIGHTENED"
ORIGIN_ZONE_NO_TABLE = "ZONE_PINNED_NO_TABLE_VALUE"
ORIGIN_ZONE_REFUSED = "TYPE_DEFAULT_ZONE_OVERRIDE_REFUSED"
ORIGIN_ZONE_UNADJUDICATED = "ZONE_PINNED_NOT_ADJUDICATED"
ORIGIN_ABSENT = "ABSENT"

REFUSED_ZONE_TEXT_FLOOR = "CONTAINER_ZONE_TEXT_FLOOR_BELOW_METHOD_CAPABILITY"

_REFUSAL_REASON = (
    "OWNER_BLOCKER_CLEARANCE.md §Y1(a) — a zone may TIGHTEN a text floor and "
    "may not LOOSEN one. The capability table describes what the PRESS can "
    "hold; a zone is a region of a design. This method's authority_state is "
    "INFERRED_NONAUTHORITATIVE or USER_REQUESTED_UNVERIFIED, and neither has "
    "standing to claim the press holds finer type than the method allows. The "
    "table value stands as the effective floor and the zone value is recorded "
    "here rather than discarded (§Y1(b))."
)


def _resolve_min_text_size(zone_pt, table_pt):
    """§Y1(a) — the effective text floor is the LARGER of zone and table.

    Returns ``(effective, origin, refusal|None)``.

    **Larger wins because for a text-size FLOOR larger means stricter.** That
    relation is NOT shared by the other two numeric constraints on this record
    and this rule must not be generalised to them:

    * ``minimum_line_weight_mm`` is also a floor, so larger is also stricter —
      but §Y1(e) scopes this ruling to the text floor and binds line weight as
      to the ``is not None`` defect ONLY. Adjudicating it is a separate ruling.
    * ``registration_tolerance_mm`` is a TOLERANCE, so **larger is LOOSER.**
      Applying "larger wins" there would permit exactly the loosening §Y1
      exists to forbid.

    The three fields do not share a direction, which is why the ruling is
    statistic-scoped. A future session that "completes" this by extending the
    max() to all three would silently loosen registration on every record.
    """
    if zone_pt is None and table_pt is None:
        return None, ORIGIN_ABSENT, None
    if zone_pt is None:
        return table_pt, ORIGIN_TYPE_DEFAULT, None
    if table_pt is None:
        # No table value exists for this method type, so there is no press
        # capability the zone could be contradicting. Honoured, and labelled
        # so it is not mistaken for a table-governed floor.
        return zone_pt, ORIGIN_ZONE_NO_TABLE, None
    zone_f, table_f = float(zone_pt), float(table_pt)
    if zone_f > table_f:
        return zone_pt, ORIGIN_ZONE_TIGHTENED, None
    if zone_f == table_f:
        return table_pt, ORIGIN_TYPE_DEFAULT, None
    # zone < table — REFUSED. §Y1(a) the table stands; §Y1(b) it is recorded
    # with both numbers and the reason, never discarded silently. A 0.0 zone
    # floor lands here too: it is below any table value, so it is refused
    # rather than silently clearing every run (§Y1(c)).
    return table_pt, ORIGIN_ZONE_REFUSED, {
        "code": REFUSED_ZONE_TEXT_FLOOR,
        "field": "minimum_text_size_pt",
        "zone_value_pt": zone_f,
        "table_value_pt": table_f,
        "effective_value_pt": table_f,
        "outcome": "REFUSED — zone value is below the method capability",
        "reason": _REFUSAL_REASON,
    }


def _zone_origin(zone_value) -> str:
    """Provenance for the constraint fields §Y1(e) does NOT adjudicate.

    A zone value is taken as supplied and labelled ``ZONE_PINNED_NOT_
    ADJUDICATED`` — honest about where the number came from, and explicit that
    no zone-vs-table comparison was performed on it. §Y1(e) binds only the
    text floor; extending the comparison here would be inventing a ruling.
    """
    return ORIGIN_ZONE_UNADJUDICATED if zone_value is not None \
        else ORIGIN_TYPE_DEFAULT


def _canonical(payload) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      default=str)


def _hash(payload) -> str:
    return hashlib.sha256(_canonical(payload).encode()).hexdigest()[:32]


def method_type_for(zone: dict) -> str | None:
    """(technique, surface, zone_type) → production method_type (§4)."""
    if zone.get("zone_type") == "BOTTOM_CODE_ZONE":
        return "BOTTOM_INKJET_CODE"
    techs = zone.get("permitted_techniques") or []
    if not techs:
        return None
    technique = techs[0]
    mapping = _TECHNIQUE_METHOD.get(technique)
    if mapping is None:
        return None
    cap_variant, body_variant = mapping
    is_cap = zone_surface(zone) in _CAP_SURFACES
    return cap_variant if is_cap else body_variant


def build_production_methods(zones: list[dict], profile_record: dict) -> dict:
    """container_production_method/1.0 — one record per confirmed zone's
    technique, authority UNVERIFIED by construction (§2)."""
    methods = []
    for z in zones or []:
        mtype = method_type_for(z)
        if mtype is None:
            methods.append({
                "method_id": f"m_{z.get('zone_id')}",
                "method_type": None, "target_zone_ids": [z.get("zone_id")],
                "target_surfaces": [zone_surface(z)],
                "authority_state": UNSUPPORTED,
                "verification_source": SRC_UNKNOWN,
                "unsupported_reason": "no supported technique on the zone"})
            continue
        defaults = _METHOD_DEFAULTS.get(mtype, {})
        # §Y1 — the zone may TIGHTEN the text floor and may not LOOSEN it. Every
        # other constraint takes the zone value as supplied (§Y1(e) scopes the
        # adjudication to the text floor) but now RECORDS that it did.
        text_pt, text_origin, text_refusal = _resolve_min_text_size(
            z.get("min_text_size_pt"), defaults.get("min_text_pt"))
        # §Y1(c) — `is not None`, not `or`, on all three numeric floors. With
        # `or`, a zone value of 0.0 is falsy and falls through to the type
        # default with nothing recording that it did: the record would then
        # claim a floor the zone did not ask for. The two sibling fields below
        # already did this correctly, so the file disagreed with itself exactly
        # on the fields where 0.0 is both meaningful and dangerous.
        line_mm = (z.get("min_line_weight_mm")
                   if z.get("min_line_weight_mm") is not None
                   else defaults.get("min_line_mm"))
        registration_mm = (z.get("registration_tolerance_mm")
                           if z.get("registration_tolerance_mm") is not None
                           else defaults.get("registration_mm"))
        constraints_by_field = {
            "permitted_color_count": _zone_origin(z.get("permitted_color_count")),
            "minimum_line_weight_mm": _zone_origin(z.get("min_line_weight_mm")),
            "minimum_text_size_pt": text_origin,
            "maximum_coverage": _zone_origin(z.get("max_artwork_coverage")),
            "registration_tolerance_mm": _zone_origin(
                z.get("registration_tolerance_mm")),
        }
        # §Y1(d) — constraints_source stops being a constant. Where every value
        # came from the type default it still reads exactly as before, so the
        # honest case is unchanged; where one did not, the field names which.
        _non_default = sorted(
            f for f, o in constraints_by_field.items()
            if o not in (ORIGIN_TYPE_DEFAULT, ORIGIN_ABSENT))
        constraints_source = ORIGIN_TYPE_DEFAULT if not _non_default else (
            "MIXED_ZONE_AND_TYPE_DEFAULT: " + ", ".join(
                f"{f}={constraints_by_field[f]}" for f in _non_default))
        rec = {
            "method_id": f"m_{z.get('zone_id')}",
            "method_type": mtype,
            "target_surfaces": [zone_surface(z)],
            "target_zone_ids": [z.get("zone_id")],
            # §0 (2B-3C) authority-source semantics: a technique a human
            # explicitly chose/confirmed for the design (zone source
            # EXPLICIT_USER_FACT) is EXPLICIT_USER_REQUEST / USER_REQUESTED_
            # UNVERIFIED (design intent, no manufacturer authority); a merely
            # machine-proposed technique is INFERRED_NONAUTHORITATIVE. Neither
            # clears the gate — only VERIFIED_MANUFACTURER_CAPABILITY does.
            "verification_source": (SRC_USER_REQUEST
                                    if z.get("source") == "EXPLICIT_USER_FACT"
                                    else SRC_INFERRED),
            "authority_state": (USER_REQUESTED_UNVERIFIED
                                if z.get("source") == "EXPLICIT_USER_FACT"
                                else INFERRED_NONAUTHORITATIVE),
            "manufacturer_identity": "",
            "compatible_container_materials": "UNKNOWN",
            "permitted_color_count": z.get("permitted_color_count")
            if z.get("permitted_color_count") is not None else defaults.get("max_colors"),
            "minimum_line_weight_mm": line_mm,
            "minimum_text_size_pt": text_pt,
            "maximum_coverage": z.get("max_artwork_coverage")
            if z.get("max_artwork_coverage") is not None else defaults.get("max_coverage"),
            "registration_tolerance_mm": registration_mm,
            "trapping_allowance": "REVIEW_REQUIRED",
            "overprint_requirement": "REVIEW_REQUIRED",
            "white_underbase_requirement": defaults.get("white_underbase", "no"),
            "opacity_requirement": "REVIEW_REQUIRED",
            "required_separation_layers": [],
            "required_technical_notes": [],
            "confirmed_by": "",
            "confirmed_at": "",
            "constraints_source": constraints_source,
            # §Y1(d) — per-field provenance. The string above is for a reader;
            # this is for a consumer that must not parse prose.
            "constraints_by_field": constraints_by_field,
            "minimum_text_size_source": text_origin,
            # §Y1(b) — a refused zone override is RECORDED with both numbers
            # and the reason. Empty on every honest record.
            "refused_zone_constraints": [text_refusal] if text_refusal else [],
        }
        rec["method_hash"] = _method_hash(rec)
        methods.append(rec)
    # §Y1(b) — roll the refusals up so a consumer does not have to walk every
    # method to discover that one of them had an override rejected.
    refused = [r for m in methods for r in m.get("refused_zone_constraints") or []]
    record = {"schema_version": SCHEMA, "methods": methods,
              "all_manufacturer_verified": bool(methods) and all(
                  m.get("authority_state") == VERIFIED_MANUFACTURER_CAPABILITY
                  for m in methods),
              "refused_zone_constraints": refused,
              "any_zone_override_refused": bool(refused)}
    record["method_set_hash"] = _hash(sorted(m.get("method_hash", "")
                                             for m in methods))
    return record


def _decoration_geometry(doc) -> dict:
    """Measure the EMITTED printed artwork (Decoration / motif / Surface
    groups) — never declared values: min stroke weight, min text size PER
    SURFACE, distinct printed colours. Technical/structural nodes (silhouette,
    swatches, reference) are excluded.

    §W2(a) changed two things here. The text minimum was read off
    ``product-name*`` runs alone and is now read off ALL artwork runs; and it
    was ONE global minimum checked against EVERY method's limit, which is what
    made a 2.0 pt bottom inkjet code fail the embossed panel's 8.0 pt limit —
    the false FAIL §W2 was written to stop. Each surface now carries its own
    minimum, and ``validate_production_methods`` compares a method only
    against the surfaces it actually prints.

    ``min_text_size_pt`` is kept as the global minimum because it is a
    published measurement other readers already use, but nothing adjudicates
    against it any more.

    THE SURFACE STRIP IS NOT MEASURED FOR TEXT SIZE, and this is not an
    exemption invented to reach a PASS — the artefact was run first and it
    said so. Extending the scan from ``product-name*`` to all runs pulled in
    ``Surface-BODY_BACK/BACK_DIRECT_PRINT/back-section-0-copy`` at 1.16 pt and
    condemned a correct container against ADHESIVE_LABEL's 4.0 pt floor. That
    run is the SCHEMATIC of the back panel drawn at diagram scale, not the
    printed panel; ``_surface_panels`` wraps every non-hero surface. §W1(c):
    the strip is a map, do not measure it harder, and
    ``text_runs_excluded_as_schematic`` counts what was skipped so the limit
    stays visible.

    §W1(a)'s full-scale panel is the surface itself, drawn at its confirmed
    zone dimensions in a ``TrueScaleSurface-*`` group, and it IS measured —
    against its own surface, not the hero's. Attributing it to the hero would
    hold regulatory copy to the front's print method, which is a different
    physical process on a different face of the same bottle.

    Line weight and colour keep their existing whole-artwork scope. §W2 ruled
    about text size; widening those here would be a change no owner asked for.
    """
    min_line = None
    min_text = None
    text_by_surface: dict[str, float] = {}
    # [his correction of 2026-10-07: "Shrink the whole label evenly ... Floor: 3 pt."] the back label's runs (by the
    # names its own record gives them) and every other run, each surface's minimum apart: a method's minimum holds the
    # other runs; the label's its floor (``back_panel.label_floor_pt``). ``min_text_size_pt_by_surface`` stays the
    # minimum over all of them, as published
    from apps.ire import back_panel as _bp
    label_names = {"back-panel-%s-%s-%s" % (e["section"], e["role"], e["order"])
                   for e in ((getattr(doc, "metadata", None) or {}).get(_bp.SCHEMA) or {}).get("lines") or []}
    label_by_surface: dict[str, float] = {}
    other_by_surface: dict[str, float] = {}
    schematic_text = 0
    depicted_surfaces: set[str] = set()
    colors: set[str] = set()

    def _in_artwork(name_chain: tuple[str, ...]) -> bool:
        """Is this node inside printed artwork, as opposed to sheet furniture?

        §BD(c) — OWNER-RULED: *"the deny-list discipline governs every
        instrument that measures text on the emitted document, named or not."*
        ``FRONT_DIRECT_PRINT_GROUP`` is the fourth entry for that reason.

        IT WAS ADDED BECAUSE THIS INSTRUMENT WENT DARK, NOT BECAUSE IT WAS
        NEVER LIT. Before §BB7(c) the direct-print front did not exist in
        production and the front name was emitted inside a group named
        ``Decoration``, which the first entry matched: the front WAS measured,
        at 8.0 pt. Wiring the two call sites renamed its parent and this
        function began returning False for every run on the front — the
        product name and the ruled descriptor both. Measured on the emitted
        document at both call sites, before and after, rather than reasoned
        about: the loss is real and it is this arc's own.

        AND IT IS INERT WITHOUT THE WIRING, which is why it rides with the
        wiring rather than in a tranche of its own. Walking the same composed
        document under the three-prefix list and under this four-prefix one:
        unwired, both see **6** runs — the identical set. Wired, the old list
        sees **4** and this one sees **7**. A commit landing this edit ahead of
        the wiring would provably alter no measurement, and a wiring commit
        landing without it is red at
        ``test_a_text_size_failure_is_readiness_and_not_a_blocker``. There is
        no third position for it.

        WHY THE NAME AND NOT THE ROLE, since the group carries
        ``role="decoration"`` and testing that would have matched without any
        edit here. Because it would ALSO have matched several groups this has
        always excluded, silently widening a §W2-ruled scope in a commit about
        something else. Matching one named group is the change that restores
        exactly what the wiring took away and nothing besides — and the name
        is imported from the emitter rather than spelled here, so the two
        cannot drift apart, which is the defect class §BB7 exists about.
        """
        from apps.ire.compose_container import (FRONT_DIRECT_PRINT_GROUP,
                                                TRUE_SCALE_SURFACE_PREFIX)
        return any(n.startswith(("Decoration", "motif-", "Surface-",
                                 FRONT_DIRECT_PRINT_GROUP,
                                 TRUE_SCALE_SURFACE_PREFIX))
                   for n in name_chain)

    def _surface_group(name_chain: tuple[str, ...]) -> tuple[str | None, bool]:
        """``(surface, true_scale)``, the same pair and the same §W1 reason as
        ``container_composition_metrics._emitted_surface`` — read off the name
        chain this walk already carries rather than from a parent map."""
        from apps.ire.compose_container import (SURFACE_GROUP_PREFIX,
                                                TRUE_SCALE_SURFACE_PREFIX)
        for n in name_chain:
            if n.startswith(TRUE_SCALE_SURFACE_PREFIX):
                return n[len(TRUE_SCALE_SURFACE_PREFIX):], True
            if n.startswith(SURFACE_GROUP_PREFIX):
                return n[len(SURFACE_GROUP_PREFIX):], False
        return None, False

    def _walk(node, chain):
        from apps.ire.compose_container import HERO_SURFACE
        nonlocal min_text, schematic_text, min_line
        name = str(getattr(node, "name", ""))
        chain2 = chain + (name,)
        artwork = _in_artwork(chain2)
        scope = (getattr(node, "print_scope", None)
                 if node.type == "text" else None)
        if scope is not None:
            # §BH50(f)(1) — the composer's declaration decides, and it is the
            # same declaration the §W2 size-floor record reads (§BD(c): one
            # rule, one scope). A printed run is artwork on its declared
            # surface whatever group it sits in; a depiction is schematic; an
            # annotation is not artwork. An undeclared run keeps the
            # allow-list and group logic below.
            sz = float(getattr(node, "size_pt", 0) or 0)
            if scope.kind == "DEPICTION_OF_PRODUCT_COPY":
                schematic_text += 1
                depicted_surfaces.add(str(scope.surface))
            elif scope.kind == "PRINTED_ON_PRODUCT" and sz:
                surface = str(scope.surface)
                if min_text is None or sz < min_text:
                    min_text = sz
                if sz < text_by_surface.get(surface, float("inf")):
                    text_by_surface[surface] = sz
                apart = label_by_surface if name in label_names else other_by_surface
                if sz < apart.get(surface, float("inf")):
                    apart[surface] = sz
        elif node.type == "text" and artwork:
            sz = float(getattr(node, "size_pt", 0) or 0)
            group_surface, true_scale = _surface_group(chain2)
            if group_surface is not None and not true_scale:
                schematic_text += 1
            elif sz:
                # §W1(b): the full-scale panel is attributed to ITS OWN
                # surface. Everything the emitter left outside a surface group
                # is on the hero — the emitter's own statement, not a guess.
                surface = HERO_SURFACE if group_surface is None \
                    else group_surface
                if min_text is None or sz < min_text:
                    min_text = sz
                if sz < text_by_surface.get(surface, float("inf")):
                    text_by_surface[surface] = sz
                apart = label_by_surface if name in label_names else other_by_surface
                if sz < apart.get(surface, float("inf")):
                    apart[surface] = sz
        if node.type in ("path", "rect") and artwork:
            stroke = getattr(node, "stroke", None)
            if stroke is not None and getattr(stroke, "width_mm", None):
                w = float(stroke.width_mm)
                if min_line is None or w < min_line:
                    min_line = w
                if getattr(stroke, "color", None) is not None:
                    colors.add(stroke.color.to_hex())
            fill = getattr(node, "fill", None)
            col = getattr(fill, "color", None)
            if col is not None:
                colors.add(col.to_hex())
        for child in getattr(node, "children", []) or []:
            _walk(child, chain2)
    _walk(doc.root, ())
    return {"min_line_weight_mm": min_line, "min_text_size_pt": min_text,
            "min_text_size_pt_by_surface": dict(sorted(text_by_surface.items())),
            # [his correction of 2026-10-07] the same minimum, the back label's runs apart from every other run
            "min_label_text_size_pt_by_surface": dict(sorted(label_by_surface.items())),
            "min_other_text_size_pt_by_surface": dict(sorted(other_by_surface.items())),
            "text_runs_excluded_as_schematic": schematic_text,
            # §BH50(f)(1): every surface on which this document draws product
            # copy as a DEPICTION — declared by the composer, never inferred.
            # A surface listed here that also prints (BODY_BACK: the strip
            # depicts it, the true-scale panel prints it) is measured by its
            # printed runs; one with no printed run (BOTTOM: its code is drawn
            # only in the bottom diagram) has nothing to hold against the floor
            # and is the surface `validate_production_methods` names unmeasured
            "depicted_text_surfaces": sorted(depicted_surfaces),
            "printed_colors": sorted(colors),
            "printed_color_count": len(colors)}


def validate_production_methods(methods_record: dict, zones: list[dict],
                                profile_record: dict, doc) -> dict:
    """§4/§5/§9/§10 validation against the EMITTED geometry + INFERRED
    type-default limits. Returns production-readiness codes (never
    reconstruction blockers). A constraint PASS does NOT clear the gate — only
    VERIFIED_MANUFACTURER_CAPABILITY authority does — so an unverified method
    always contributes CONTAINER_TECHNIQUE_UNVERIFIED."""
    geom = _decoration_geometry(doc)
    from apps.pipeline.services.container_contract import surfaces_for
    surfaces = set(surfaces_for(profile_record.get("archetype", ""),
                                profile_record.get("variant", "")))
    body_material = ((profile_record.get("fields") or {})
                     .get("body_material") or {}).get("value")

    per_method = []
    all_codes: list[str] = []
    for m in methods_record.get("methods") or []:
        codes: list[str] = []
        mtype = m.get("method_type")
        if mtype is None or m.get("authority_state") == UNSUPPORTED:
            codes.append(TECHNIQUE_UNSUPPORTED)
            per_method.append({"method_id": m.get("method_id"), "codes": codes})
            all_codes.extend(codes)
            continue
        # authority: only verified manufacturer capability clears the gate
        if m.get("authority_state") != VERIFIED_MANUFACTURER_CAPABILITY:
            codes.append(TECHNIQUE_UNVERIFIED)
        # surface sanity (derived from confirmed zones, but guard anyway)
        if any(s not in surfaces for s in m.get("target_surfaces") or []):
            codes.append(METHOD_SURFACE_MISMATCH)
        # material compatibility — UNKNOWN material never fails (honest)
        if body_material and mtype in ("HOT_STAMP", "CAP_HOT_STAMP") \
                and str(body_material).lower() in ("pe", "pp", "polyolefin"):
            codes.append(MATERIAL_TECHNIQUE_MISMATCH)
        # color count (§9) — measured printed colours vs the permitted limit
        cap = m.get("permitted_color_count")
        if cap is not None and geom["printed_color_count"] > cap:
            codes.append(COLOR_COUNT_EXCEEDED)
        # min line weight (§10) — measured emitted stroke
        mlw = m.get("minimum_line_weight_mm")
        if mlw and geom["min_line_weight_mm"] is not None \
                and geom["min_line_weight_mm"] < mlw - 1e-9:
            codes.append(MINIMUM_LINE_WEIGHT_FAILED)
        # min text size (§10, ruled by §W2(a)) — a method is compared only
        # against type on the surfaces IT prints. The global minimum was the
        # conflation: it let the smallest run anywhere on the container
        # condemn every other method's panel.
        mts = m.get("minimum_text_size_pt")
        unmeasured_surfaces: list[str] = []
        if mts:
            # [his correction of 2026-10-07: "when the label doesn't fit, the text gets SMALLER ... Floor: 3 pt."] the
            # back label's runs are held to its floor — his 3 pt, unless THIS method was confirmed and records more
            # (``back_panel.label_floor_pt``, the one answer the panel shrinks to and the axis measures against); every
            # other run on the method's surfaces to the method's minimum, as before
            from apps.ire.back_panel import label_floor_pt
            from apps.ire.container_method_provenance import is_confirmed, method_stage
            targets = m.get("target_surfaces") or []
            others = [geom["min_other_text_size_pt_by_surface"][s] for s in targets
                      if s in geom["min_other_text_size_pt_by_surface"]]
            labels = [geom["min_label_text_size_pt_by_surface"][s] for s in targets
                      if s in geom["min_label_text_size_pt_by_surface"]]
            if (others and min(others) < mts - 1e-9) or (
                    labels and min(labels) < label_floor_pt(mts, is_confirmed(method_stage(m))) - 1e-9):
                codes.append(MINIMUM_TEXT_SIZE_FAILED)
            # §BH50(f)(1)/(5): a surface this method prints whose product copy
            # the document draws only as a depiction has no printed run to
            # hold against the floor — unmeasured, and never read as passed
            unmeasured_surfaces = [
                s for s in m.get("target_surfaces") or []
                if s not in geom["min_text_size_pt_by_surface"]
                and s in geom.get("depicted_text_surfaces", [])]
            if unmeasured_surfaces:
                codes.append(MINIMUM_TEXT_SIZE_UNMEASURED)
        # trapping / overprint always need review at this authority level
        codes.append(TRAPPING_REVIEW_REQUIRED)
        codes.append(OVERPRINT_REVIEW_REQUIRED)
        per_method.append({"method_id": m.get("method_id"),
                           "method_type": mtype, "codes": codes,
                           "text_size_unmeasured_surfaces": unmeasured_surfaces})
        all_codes.extend(codes)

    # stable de-dup preserving order
    seen, ordered = set(), []
    for c in all_codes:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    return {"measurements": geom, "per_method": per_method,
            "codes": ordered,
            "manufacturer_verified": methods_record.get(
                "all_manufacturer_verified", False)}


def _method_hash(rec: dict) -> str:
    core = {k: rec.get(k) for k in (
        "method_type", "target_surfaces", "target_zone_ids",
        "authority_state", "verification_source", "permitted_color_count",
        "minimum_line_weight_mm", "minimum_text_size_pt", "maximum_coverage",
        "registration_tolerance_mm", "white_underbase_requirement")}
    return _hash(core)


__all__ = [
    "SCHEMA", "build_production_methods", "validate_production_methods",
    "method_type_for",
    "VERIFIED_MANUFACTURER_CAPABILITY", "USER_REQUESTED_UNVERIFIED",
    "INFERRED_NONAUTHORITATIVE", "UNSUPPORTED", "UNKNOWN",
    "SRC_MANUFACTURER_SPEC", "SRC_SUPPLIER_CONFIRMATION", "SRC_USER_REQUEST",
    "SRC_INFERRED", "SRC_UNKNOWN", "TECHNIQUE_UNVERIFIED",
    "TECHNIQUE_UNSUPPORTED", "METHOD_ZONE_MISMATCH", "METHOD_SURFACE_MISMATCH",
    "MATERIAL_TECHNIQUE_MISMATCH", "COLOR_COUNT_EXCEEDED",
    "MINIMUM_LINE_WEIGHT_FAILED", "MINIMUM_TEXT_SIZE_FAILED",
    "MINIMUM_TEXT_SIZE_UNMEASURED",
    "REGISTRATION_TOLERANCE_FAILED", "MAXIMUM_COVERAGE_EXCEEDED",
    "WHITE_UNDERBASE_REQUIRED", "TRAPPING_REVIEW_REQUIRED",
    "OVERPRINT_REVIEW_REQUIRED",
]
