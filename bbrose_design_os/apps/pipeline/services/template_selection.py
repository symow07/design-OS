"""Deterministic structural-template selection (Phase 2A-6, section 3).

The task-#47 failure in one sentence: the pipeline chose a structure by
defaulting, not by evidence. This module makes the choice an ordered,
auditable search over EVIDENCE, and makes "no evidence" a stop rather than a
guess.

Priority (first hit wins, highest authority first):

  1. EXPLICIT_USER_CONFIRMATION   the user confirmed a template for this task
  2. PRODUCT_TEMPLATE_ASSOCIATION an approved product/carton association
  3. SUPPLIED_STRUCTURAL_PROFILE  a verified supplied die/structural profile
  4. TARGET_STRATEGY_RECOMMENDATION  high-confidence strategy recommendation
  5. HUMAN_CONFIRMATION_REQUIRED  → STRUCTURAL_TEMPLATE_CONFIRMATION_REQUIRED
  6. GENERIC_FALLBACK_ACCEPTED    generic, and ONLY with explicit acceptance

Hard rules encoded here:

  * A generic template is never returned unless the caller passes
    ``generic_accepted=True``, which the API only sets from an explicit user
    action. Defaulting is impossible by construction.
  * Any structural evidence at all (association, supplied profile) blocks a
    silent generic: if the evidence names an unregistered or unbuildable
    template the result is confirmation-required, never a substitute.
  * Dimensions never select. They are checked against the chosen template's
    permitted ranges afterwards, and a range violation downgrades the result
    to confirmation-required.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from apps.dielines import registry

# Selection sources, most authoritative first.
SOURCE_USER = "EXPLICIT_USER_CONFIRMATION"
SOURCE_PRODUCT = "PRODUCT_TEMPLATE_ASSOCIATION"
SOURCE_PROFILE = "SUPPLIED_STRUCTURAL_PROFILE"
SOURCE_STRATEGY = "TARGET_STRATEGY_RECOMMENDATION"
SOURCE_GENERIC = "GENERIC_FALLBACK_ACCEPTED"

#: The single code every caller checks. Never a template substitution.
CONFIRMATION_REQUIRED = "STRUCTURAL_TEMPLATE_CONFIRMATION_REQUIRED"

_CONFIDENCE = {
    SOURCE_USER: 1.0,
    SOURCE_PRODUCT: 0.9,
    SOURCE_PROFILE: 0.85,
    SOURCE_STRATEGY: 0.7,
    SOURCE_GENERIC: 0.4,
}
#: A strategy recommendation below this is not authority — ask the human.
STRATEGY_CONFIDENCE_FLOOR = 0.7


@dataclass
class TemplateSelection:
    """The outcome of a selection attempt.

    ``resolved`` False means: do not generate geometry. Present
    ``candidates`` at the structure-confirmation gate and let a human decide.
    """
    resolved: bool
    template_id: str = ""
    version: str = ""
    source: str = ""
    confidence: float = 0.0
    code: str = ""
    #: Structural classification of the template that was examined.
    structure_status: str = ""
    reasons: list[str] = field(default_factory=list)
    candidates: list[dict] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def select_template(
    task, *, dimensions: dict | None = None, generic_accepted: bool = False,
    user_template: str | None = None, user_version: str | None = None,
    strategy_recommendation: tuple | None = None,
) -> TemplateSelection:
    """Choose the structural template for ``task``, or require confirmation.

    ``user_template``: an id the user explicitly confirmed for THIS task.
    ``user_version``: the version the user explicitly confirmed (2A-9E). A
    template with a declared recommended-corrected-version (STE/RTE) must
    NOT silently resolve to its legacy default — the reviewer confirms the
    version, and neither 1.1 nor 1.2 is auto-selected.
    ``strategy_recommendation``: optional ``(template_id, confidence)`` from
    the TargetStrategy — advisory only, and only honored at or above
    ``STRATEGY_CONFIDENCE_FLOOR``.
    ``generic_accepted``: the user explicitly accepted a generic structure.
    """
    dimensions = dimensions or {}
    reasons: list[str] = []
    evidence = _gather_evidence(task)

    # ---- 0. customer-supplied dieline (task-50 correction §3) -------------
    # A registered customer manufacturing die outranks EVERYTHING — generic
    # or user-picked templates must never replace supplied geometry merely
    # because nominal dimensions look similar. Selection stops here with the
    # customer source named; geometry comes from the imported vectors, and
    # confirmation still belongs to a human at the structure gate.
    customer = evidence.get("customer_dieline")
    if customer:
        return TemplateSelection(
            resolved=False,
            # 2A-9 §9: the record names its own source — a manufacturer/
            # supplier die carries the same top authority as a customer file.
            source=customer.get("source") or "CUSTOMER_SUPPLIED_DIELINE",
            reasons=reasons + [
                "a customer/manufacturer-supplied manufacturing dieline is "
                f"registered ({customer.get('file_name')}, sha256 "
                f"{str(customer.get('sha256'))[:12]}…) — parametric "
                "template selection is disabled; the imported vector "
                "geometry is the structure and requires human confirmation"],
            evidence=evidence,
            code="CUSTOMER_DIELINE_IMPORT_REQUIRED")

    # ---- 1. explicit user confirmation ------------------------------------
    if user_template:
        rec_ver = registry.recommended_corrected_version(user_template)
        if rec_ver and not user_version:
            # 2A-9E: a template with a corrected version must not silently
            # resolve to its legacy default. Recommend the corrected version,
            # require an explicit version confirmation, auto-select neither.
            reasons.append(
                f"{user_template} has a corrected version {rec_ver} "
                "(RECOMMENDED_CORRECTED_VERSION); its legacy version carries "
                "a known W-derived closure limitation and is offered only as "
                "an advanced legacy option. Confirm the version explicitly — "
                "neither is auto-selected.")
            return TemplateSelection(
                resolved=False, code=CONFIRMATION_REQUIRED, reasons=reasons,
                candidates=registry.new_selection_templates(),
                evidence=evidence)
        return _finalize(user_template, SOURCE_USER, dimensions, reasons,
                         evidence, "user explicitly confirmed this template",
                         user_version=user_version)

    # ---- 2. approved product/template association --------------------------
    assoc = evidence.get("product_association")
    if assoc:
        return _finalize(assoc["template_id"], SOURCE_PRODUCT, dimensions,
                         reasons, evidence,
                         f"product association: {assoc['origin']}")

    # ---- 3. verified supplied structural profile ---------------------------
    profile = evidence.get("supplied_profile")
    if profile:
        return _finalize(profile["template_id"], SOURCE_PROFILE, dimensions,
                         reasons, evidence,
                         f"supplied structural profile: {profile['origin']}")

    # ---- 4. target-strategy recommendation ---------------------------------
    if strategy_recommendation:
        rec_id, rec_conf = strategy_recommendation
        if rec_conf is not None and rec_conf >= STRATEGY_CONFIDENCE_FLOOR:
            return _finalize(rec_id, SOURCE_STRATEGY, dimensions, reasons,
                             evidence,
                             f"target strategy recommendation "
                             f"(confidence {rec_conf:.2f})",
                             confidence=float(rec_conf))
        reasons.append(
            f"target strategy recommended {rec_id!r} at confidence "
            f"{rec_conf} — below the {STRATEGY_CONFIDENCE_FLOOR} floor"
        )

    # ---- 6. generic fallback, only when explicitly accepted ----------------
    # (5 is the fall-through below: human confirmation.)
    if generic_accepted:
        if evidence.get("has_structural_reference"):
            reasons.append(
                "a structural reference exists for this task — a generic "
                "template cannot be accepted over customer structural evidence"
            )
        else:
            return _finalize("straight_tuck_end_carton", SOURCE_GENERIC,
                             dimensions, reasons, evidence,
                             "user explicitly accepted a generic structure")

    # ---- 5. human confirmation required ------------------------------------
    reasons.append(
        "no confirmed template, product association or verified structural "
        "profile — the panel sequence and closure geometry are unknown"
    )
    return TemplateSelection(
        resolved=False, code=CONFIRMATION_REQUIRED, reasons=reasons,
        candidates=registry.new_selection_templates(),
        evidence=evidence,
    )


def _finalize(template_id, source, dimensions, reasons, evidence, why,
              confidence=None, user_version=None) -> TemplateSelection:
    """Validate the chosen id against the registry + supplied dimensions.

    ``user_version`` (2A-9E): when the user explicitly confirmed a version,
    resolve THAT pinned version — the selection persists it, so a reviewer
    who picks 1.2 lands a 1.2 record, not a resolve()-default 1.1."""
    reasons = list(reasons) + [why]
    try:
        defn = registry.resolve(template_id, user_version)
    except registry.TemplateVersionMismatch as exc:
        reasons.append(f"{exc}")
        return TemplateSelection(
            resolved=False, code=CONFIRMATION_REQUIRED, reasons=reasons,
            candidates=registry.new_selection_templates(), evidence=evidence)
    except registry.UnknownTemplate as exc:
        reasons.append(f"{exc}")
        reasons.append(
            "structural evidence names an unregistered template — refusing "
            "to substitute a different structure"
        )
        return TemplateSelection(
            resolved=False, code=CONFIRMATION_REQUIRED, reasons=reasons,
            candidates=[d.to_dict() for d in registry.production_templates()],
            evidence=evidence,
        )

    # 2A-9E: a technically-qualified RECOMMENDED_CORRECTED_VERSION (STE/RTE
    # 1.2) that the reviewer explicitly confirmed by version MAY resolve —
    # it proceeds through structural preview, confirmation, artwork mapping
    # and editable preview. Gate 2 stays blocked by
    # PHYSICAL_SAMPLE_VALIDATION_REQUIRED until an exact-hash FIT_PASS. This
    # does NOT relax superseded/provisional/auto-bottom versions.
    _is_confirmed_correction = (
        user_version is not None
        and defn.version == registry.recommended_corrected_version(
            defn.template_id)
        and defn.ineligibility_code
        == registry.PHYSICAL_SAMPLE_VALIDATION_REQUIRED)
    if not defn.production_ready and not _is_confirmed_correction:
        # A provisional or superseded version may be inspected, never
        # produced. Return ITS code so the reason is unambiguous.
        reasons.append(
            f"{defn.key} is not production-eligible: {defn.ineligibility_code}"
        )
        reasons.extend(defn.structural_limitations)
        return TemplateSelection(
            resolved=False, code=defn.ineligibility_code, reasons=reasons,
            candidates=[d.to_dict() for d in registry.production_templates()],
            evidence=evidence,
            structure_status=defn.structure_status,
            template_id=defn.template_id, version=defn.version,
        )

    problems = defn.fits_dimensions(dimensions) if dimensions else []
    if problems:
        reasons.extend(problems)
        reasons.append(
            f"{defn.key} cannot be built at the supplied dimensions — a human "
            "must reconcile the structure and the numbers"
        )
        return TemplateSelection(
            resolved=False, code=CONFIRMATION_REQUIRED, reasons=reasons,
            candidates=[defn.to_dict()], evidence=evidence,
        )

    return TemplateSelection(
        resolved=True, template_id=defn.template_id, version=defn.version,
        source=source,
        confidence=confidence if confidence is not None else _CONFIDENCE[source],
        reasons=reasons, evidence=evidence,
    )


def _gather_evidence(task) -> dict:
    """Read-only structural evidence for this task. No inference, no search.

    Recognized today:
      * ``Product.packaging_structure.dieline_template_id`` — an approved
        association recorded on the brand's packaging-structure record.
      * ``PackagingStructure.surface_zones['dieline_template']`` — the same
        association expressed in the existing JSON payload (no migration
        needed for brands that already record it there).
    A future verified-die importer registers its result the same way.
    """
    evidence: dict = {"product_association": None, "supplied_profile": None,
                      "has_structural_reference": False,
                      "customer_dieline": None}
    # a registered customer-supplied dieline on the task's dieline job is
    # the highest structural authority (task-50 correction §3)
    try:
        output = task.packaging_outputs.filter(
            dieline_job__isnull=False).first()
        if output and output.dieline_job:
            from apps.dielines.services.customer_dieline import (
                customer_dieline_record)
            record = customer_dieline_record(output.dieline_job)
            if record:
                evidence["customer_dieline"] = {
                    key: record.get(key) for key in
                    ("source", "file_name", "sha256", "panel_widths_mm",
                     "body_height_mm", "confirmed")}
                evidence["has_structural_reference"] = True
    except Exception:  # noqa: BLE001 — evidence gathering never raises
        pass
    product = getattr(task, "product", None)
    structure = getattr(product, "packaging_structure", None) if product else None
    if structure is None:
        return evidence

    zones = getattr(structure, "surface_zones", None)
    template_id = ""
    origin = ""
    if isinstance(zones, dict):
        candidate = zones.get("dieline_template") or zones.get("dieline_template_id")
        if isinstance(candidate, str) and candidate.strip():
            template_id = candidate.strip()
            origin = (f"PackagingStructure {getattr(structure, 'structure_id', '')} "
                      f"surface_zones.dieline_template")
    if template_id:
        evidence["product_association"] = {
            "template_id": template_id, "origin": origin,
        }
        evidence["has_structural_reference"] = True
    return evidence


__all__ = [
    "TemplateSelection",
    "select_template",
    "CONFIRMATION_REQUIRED",
    "SOURCE_USER",
    "SOURCE_PRODUCT",
    "SOURCE_PROFILE",
    "SOURCE_STRATEGY",
    "SOURCE_GENERIC",
    "STRATEGY_CONFIDENCE_FLOOR",
]
