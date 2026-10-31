"""Generalized production-readiness validation (Phase 2A-6, §11–12).

Generalizes the task-#47 validator into the standard Gate-2 gate, organized
by the four failure families the contract names. Every failure carries its
own structured code — nothing is flattened into a single generic
PRODUCTION_NOT_READY (that string is only the transport-level error the
endpoint returns alongside the itemized list).

There is NO override in this phase.

STRUCTURAL
    STRUCTURE_NOT_CONFIRMED · TEMPLATE_MISMATCH · PANEL_SEQUENCE_MISMATCH ·
    MISSING_CLOSURE_GEOMETRY · DIMENSIONS_UNRECONCILED · CLOSURE_COLLISION ·
    INVALID_SLIT_OR_NOTCH · INCOMPLETE_BLEED · CUT_FOLD_CONFLICT ·
    OPEN_OR_SELF_INTERSECTING_CONTOUR · STRUCTURE_CHECKLIST_MISSING
ARTWORK
    PANEL_SIZED_RASTER · PRINTABLE_CONCEPT_RENDER · RGB_PRODUCTION_ARTWORK ·
    FLATTENED_PANEL_GRAPHICS · INSUFFICIENT_EDITABLE_VECTOR_COVERAGE ·
    DUPLICATED_PANEL_TEXTURE · REFERENCE_ONLY_IMAGE_PRINTABLE ·
    ARTWORK_INVENTORY_MISSING
CONTENT
    (the per-field codes from services.print_data) · FORBIDDEN_PANEL_TEXT ·
    TEXT_BELOW_MINIMUM_SIZE
COLOR/OUTPUT
    INVALID_SPOT_DEFINITION · TECHNICAL_LAYER_PRINTABLE ·
    MISSING_OUTPUT_INTENT · INVALID_FONT_EMBEDDING · PRODUCTION_PDF_MISSING
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

from apps.dielines import registry

CATEGORY_STRUCTURAL = "structural"
CATEGORY_ARTWORK = "artwork"
CATEGORY_CONTENT = "content"
CATEGORY_OUTPUT = "color_output"

#: DOMAIN (§W2(c)): DIELINES — folding-carton litho/flexo on board, where 4.5
#: pt is the smallest live text a printed panel may carry. NOT the container
#: floor: §W2 ruled the container_production_method capability table governs
#: there, per run and per surface (apps/ire/container_text_floor.py), because
#: minimum legible size is a property of how type meets the substrate — you
#: cannot emboss at 5 pt and a 2.0 pt bottom inkjet code is standard practice.
_MIN_TEXT_PT = 4.5
#: A production panel must be genuinely reconstructed, not two shapes and a
#: raster: at least this many editable decorative objects.
_MIN_DECORATIVE_VECTOR = 12
#: Raster coverage over the printable panels, above which the artwork is
#: effectively a raster design regardless of object counts.
_MAX_RASTER_AREA_FRACTION = 0.02

_RGB_OP_RE = re.compile(rb"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(?:rg|RG)\b")
#: Technical linework that must live on non-printing layers.
_TECHNICAL_SPOTS = ("CutContour", "Crease")


@dataclass
class ProductionReport:
    failures: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked: list[str] = field(default_factory=list)
    editability: dict = field(default_factory=dict)
    #: ICC profile identity backing the output intent (§9).
    output_intent: dict = field(default_factory=dict)

    @property
    def ready(self) -> bool:
        return not self.failures

    def fail(self, category: str, code: str, detail: str, **extra) -> None:
        entry = {"category": category, "code": code, "detail": detail}
        entry.update(extra)
        self.failures.append(entry)

    def codes(self) -> set[str]:
        return {f["code"] for f in self.failures}

    def by_category(self) -> dict:
        out: dict[str, list] = {}
        for f in self.failures:
            out.setdefault(f["category"], []).append(f)
        return out

    def to_dict(self) -> dict:
        return {
            "ready": self.ready,
            "failures": self.failures,
            "failures_by_category": self.by_category(),
            "warnings": self.warnings,
            "checked": self.checked,
            "editability": self.editability,
            "output_intent": self.output_intent,
        }


def evaluate_production(
    output, *, expected_template: str | None = None,
    print_record=None, forbidden_panel_texts: tuple[str, ...] = (),
    require_structure_confirmation: bool = True,
) -> ProductionReport:
    """Full production-readiness evaluation for a PackagingOutput."""
    r = ProductionReport()
    spec = output.spec_sheet or {}

    _check_structural(r, output, spec, expected_template,
                      require_structure_confirmation)
    inventory = _check_artwork(r, output, spec)
    _check_content(r, output, spec, print_record, forbidden_panel_texts,
                   inventory)
    _check_color_output(r, output, spec)
    r.editability = _editability_report(inventory, output)
    return r


# --- structural ----------------------------------------------------------------


def _check_structural(r, output, spec, expected_template, require_confirmation):
    r.checked.append("template")
    job = getattr(output, "dieline_job", None)
    template = spec.get("template")

    if expected_template and template != expected_template:
        r.fail(CATEGORY_STRUCTURAL, "TEMPLATE_MISMATCH",
               f"spec template {template!r} does not match the required "
               f"{expected_template!r}")

    r.checked.append("structure_confirmation")
    record = dict(getattr(job, "structure_selection", None) or {}) if job else {}
    if require_confirmation:
        if not record:
            r.fail(CATEGORY_STRUCTURAL, "STRUCTURE_NOT_CONFIRMED",
                   "no structural selection is recorded for this output — the "
                   "die was never confirmed against a declared template")
        elif not record.get("confirmed_at"):
            r.fail(CATEGORY_STRUCTURAL, "STRUCTURE_NOT_CONFIRMED",
                   "the structure was never confirmed by a reviewer")
        else:
            expected_hash = registry.geometry_hash(
                record.get("template_id", ""),
                record.get("template_version", ""),
                record.get("parameters") or {})
            if expected_hash != record.get("geometry_hash"):
                r.fail(CATEGORY_STRUCTURAL, "STRUCTURE_NOT_CONFIRMED",
                       "the die changed after confirmation (geometry hash "
                       "mismatch) — re-confirm the structure")

    # The template VERSION must itself be production-eligible: a version
    # carrying a known manufacturing defect may be reproduced for history but
    # never newly shipped (Phase 2A-6-CORR-1).
    r.checked.append("template_version")
    version = (record.get("template_version")
               or spec.get("template_version") or None)
    if template:
        try:
            defn = registry.resolve(template, version)
        except (registry.UnknownTemplate, registry.TemplateVersionMismatch) as exc:
            defn = None
            r.fail(CATEGORY_STRUCTURAL, "TEMPLATE_MISMATCH", str(exc))
        # 2A-9E §6: a PHYSICAL_SAMPLE_VALIDATION_REQUIRED structure whose
        # EXACT geometry hash has a recorded FIT_PASS clears ONLY this
        # structural physical blocker (the other Gate-2 blockers — output
        # intent, font licence, content — still apply independently). Reuse
        # promotion_blockers so the match rule is identical everywhere.
        physical_cleared = False
        if (defn is not None
                and defn.ineligibility_code
                == registry.PHYSICAL_SAMPLE_VALIDATION_REQUIRED
                and job is not None):
            from apps.dielines.services.physical_validation import (
                promotion_blockers,
            )
            physical_cleared = not promotion_blockers(
                job, template_key=defn.key,
                geometry_hash=record.get("geometry_hash", ""))
        # §BH70(3) (§BH70 LIVE): "A physical sample is never required to finish a design (a colleague test-fits; that
        # is not the system's job)." A structure held ONLY by the sample condition is no longer refused here: its
        # untested geometry is a warning, and a FIT_PASS recorded for exactly this geometry is still read and said
        if (defn is not None and not defn.production_ready
                and defn.ineligibility_code == registry.PHYSICAL_SAMPLE_VALIDATION_REQUIRED):
            r.warnings.append(
                f"{registry.PHYSICAL_SAMPLE_VALIDATION_REQUIRED}: {defn.key} is {defn.structure_status} — "
                + ("a printed sample of exactly this geometry has recorded FIT_PASS" if physical_cleared
                   else registry.PHYSICAL_SAMPLE_INFORMATION))
        elif defn is not None and not defn.production_ready:
            # Return the template's OWN code: a superseded version and an
            # unmeasured provisional structure are different problems with
            # different remedies.
            code = defn.ineligibility_code or "NON_PRODUCTION_TEMPLATE_VERSION"
            if code == registry.MEASURED_REFERENCE_REQUIRED:
                detail = (
                    f"{defn.key} is {defn.structure_status} — its cut and fold "
                    "boundaries are correct but the closure mechanics are not "
                    "modelled from a measured production die: "
                    + "; ".join(defn.structural_limitations)
                )
            else:
                detail = (
                    f"{defn.key} carries a known manufacturing defect and is "
                    "kept only so historical jobs reproduce exactly"
                    + (f"; regenerate on version {defn.superseded_by}"
                       if defn.superseded_by else "")
                )
            r.fail(CATEGORY_STRUCTURAL, code, detail,
                   structure_status=defn.structure_status)

    # Declared panel sequence vs the sequence actually drawn.
    r.checked.append("panel_sequence")
    drawn = spec.get("panel_order") or []
    if template and drawn:
        try:
            declared = registry.resolve(template, version).panel_order()
        except (registry.UnknownTemplate, registry.TemplateVersionMismatch):
            declared = []
        if declared and list(drawn) != declared:
            r.fail(CATEGORY_STRUCTURAL, "PANEL_SEQUENCE_MISMATCH",
                   f"drawn panel sequence {list(drawn)} does not match the "
                   f"declared sequence {declared} for {template}")

    checklist = _job_json(output, "_structural_checklist.json")
    r.checked.append("structural_checklist")
    if checklist is None:
        r.fail(CATEGORY_STRUCTURAL, "STRUCTURE_CHECKLIST_MISSING",
               "no structural comparison checklist exists — the structure was "
               "never verified against its declared template")
        return

    missing = [f["feature"] for f in checklist.get("required_features", [])
               if not f.get("present")]
    if missing:
        r.fail(CATEGORY_STRUCTURAL, "MISSING_CLOSURE_GEOMETRY",
               "required closure features absent: " + "; ".join(missing))

    rec = checklist.get("reconciliation") or {}
    if rec.get("discrepancies"):
        r.fail(CATEGORY_STRUCTURAL, "DIMENSIONS_UNRECONCILED",
               " | ".join(rec["discrepancies"]))
    for c in rec.get("collision_checks", []):
        if c.get("ok"):
            continue
        name = c.get("name", "")
        if name == "bleed_contour_complete":
            code = "INCOMPLETE_BLEED"
        elif "slit" in name or "notch" in name:
            code = "INVALID_SLIT_OR_NOTCH"
        else:
            code = "CLOSURE_COLLISION"
        r.fail(CATEGORY_STRUCTURAL, code, f"{name}: {c.get('detail', '')}")

    geom = checklist.get("geometry_integrity") or {}
    if geom.get("self_intersecting") or geom.get("open_contour"):
        r.fail(CATEGORY_STRUCTURAL, "OPEN_OR_SELF_INTERSECTING_CONTOUR",
               "the cut contour is open or self-intersecting")
    if geom.get("cut_fold_conflict"):
        r.fail(CATEGORY_STRUCTURAL, "CUT_FOLD_CONFLICT",
               "a crease is drawn along a cut edge")


# --- artwork ---------------------------------------------------------------------


def _check_artwork(r, output, spec) -> dict:
    r.checked.append("artwork_inventory")
    doc = _job_json(output, "_artwork_inventory.json")
    if doc is None:
        r.fail(CATEGORY_ARTWORK, "ARTWORK_INVENTORY_MISSING",
               "no raster/vector inventory exists — the artwork cannot be "
               "verified as native vector")
        return {}
    inv = doc.get("inventory", {})

    if inv.get("panel_sized_raster_count", 1):
        r.fail(CATEGORY_ARTWORK, "PANEL_SIZED_RASTER",
               f"{inv['panel_sized_raster_count']} panel-sized raster(s) in "
               "the production artwork")
    for raster in inv.get("rasters", []):
        if raster.get("decorative"):
            r.fail(CATEGORY_ARTWORK, "PRINTABLE_CONCEPT_RENDER",
                   f"decorative raster {raster.get('name')!r} is printable — "
                   "the concept render is reference-only and must never print")
        if raster.get("reference_only"):
            r.fail(CATEGORY_ARTWORK, "REFERENCE_ONLY_IMAGE_PRINTABLE",
                   f"reference-only image {raster.get('name')!r} is on a "
                   "printing layer")

    frac = inv.get("raster_area_fraction")
    if frac is not None and frac > _MAX_RASTER_AREA_FRACTION:
        r.fail(CATEGORY_ARTWORK, "FLATTENED_PANEL_GRAPHICS",
               f"rasters cover {frac:.1%} of the panel area (limit "
               f"{_MAX_RASTER_AREA_FRACTION:.0%}) — the design is effectively "
               "flattened artwork")

    r.checked.append("editable_vector_coverage")
    deco = inv.get("decorative_vector_count")
    if deco is not None and deco < _MIN_DECORATIVE_VECTOR:
        r.fail(CATEGORY_ARTWORK, "INSUFFICIENT_EDITABLE_VECTOR_COVERAGE",
               f"only {deco} editable decorative objects (minimum "
               f"{_MIN_DECORATIVE_VECTOR}) — the artwork is not genuinely "
               "reconstructed")

    r.checked.append("panel_variation")
    dupes = inv.get("duplicate_panel_groups") or []
    if dupes:
        r.fail(CATEGORY_ARTWORK, "DUPLICATED_PANEL_TEXTURE",
               "identical artwork repeated across panels: " + ", ".join(dupes))
    return inv


# --- content -----------------------------------------------------------------------


def _check_content(r, output, spec, print_record, forbidden_texts, inventory):
    r.checked.append("printed_data")
    if print_record is not None:
        for failure in print_record.production_failures():
            r.fail(CATEGORY_CONTENT, failure["code"], failure["detail"],
                   field=failure.get("field"))
    else:
        # Legacy outputs carry raw panel_info; run the same contract over it.
        from apps.pipeline.services.print_data import build_print_record
        info = spec.get("panel_info") or {}
        # [his review of 127, 130, 131 and 132, 2026-10-15, C (7)] a piece the system wrote is never his copy: unverified
        from apps.pipeline.services.label_copy import PANEL_MADE_IN_KEY, PANEL_WRITTEN_KEY
        written = set(info.get(PANEL_WRITTEN_KEY) or ()) | ({"regulatory_text"} if info.get(PANEL_MADE_IN_KEY) else set())
        rec = build_print_record(info, verified_keys=[k for k in info.keys() if k not in written])
        for failure in rec.production_failures():
            r.fail(CATEGORY_CONTENT, failure["code"], failure["detail"],
                   field=failure.get("field"))

    r.checked.append("forbidden_copy")
    ai_path = _file_path(getattr(output, "design_preview_ai", None))
    if ai_path:
        rgb, text = _inspect_pdf(ai_path)
        if rgb:
            r.fail(CATEGORY_OUTPUT, "RGB_PRODUCTION_ARTWORK",
                   "the design .ai paints with colored RGB operators — all "
                   "production ink must be CMYK or a named spot")
        for forbidden in forbidden_texts:
            f = (forbidden or "").strip().lower()
            if not (f and text):
                continue
            lower = text.lower()
            hit = f in lower or any(
                len(line) >= 20 and line in f
                for line in (ln.strip().lower() for ln in text.splitlines()))
            if hit:
                r.fail(CATEGORY_CONTENT, "FORBIDDEN_PANEL_TEXT",
                       f"panel artwork contains internal task/brief text: "
                       f"{forbidden.strip()[:80]!r}")
                break
    else:
        r.warnings.append("design .ai missing — RGB/forbidden-text inspection "
                          "skipped")

    r.checked.append("min_text_size")
    min_pt = (inventory or {}).get("min_text_size_pt")
    if min_pt is not None and min_pt < _MIN_TEXT_PT:
        r.fail(CATEGORY_CONTENT, "TEXT_BELOW_MINIMUM_SIZE",
               f"live text at {min_pt:g} pt is below the {_MIN_TEXT_PT} pt "
               "print floor")


# --- color / output ------------------------------------------------------------------


def _check_color_output(r, output, spec):
    r.checked.append("production_pdf")
    pdf_path = _file_path(getattr(output, "production_pdf", None))
    if not pdf_path:
        r.fail(CATEGORY_OUTPUT, "PRODUCTION_PDF_MISSING",
               "no CMYK production PDF deliverable on this output")
        return

    r.checked.append("spot_separations")
    try:
        import fitz
    except ImportError:
        r.warnings.append("PyMuPDF unavailable — PDF colour/font checks skipped")
        return
    try:
        with fitz.open(pdf_path) as doc:
            fonts = [f for page in doc for f in page.get_fonts(full=True)]
            body = ""
            for xref in range(1, doc.xref_length()):
                try:
                    obj = doc.xref_object(xref, compressed=False)
                except Exception:  # noqa: BLE001 — skip an unreadable object
                    continue
                if obj:
                    body += obj
            has_output_intent = "/OutputIntent" in body
            spot_ok = all(spot in body for spot in _TECHNICAL_SPOTS)
    except Exception as exc:  # noqa: BLE001 — unreadable file: report, don't crash
        r.warnings.append(f"production PDF could not be inspected: {exc}")
        return

    if not spot_ok:
        r.fail(CATEGORY_OUTPUT, "INVALID_SPOT_DEFINITION",
               "the production PDF does not define the CutContour and Crease "
               "spot separations the die house needs")

    # The ICC profile's IDENTITY is part of the readiness record: a reviewer
    # must be able to see WHICH press condition the file claims.
    from apps.dielines.exporters.output_intent import (
        PREVIEW_ONLY_NO_OUTPUT_INTENT,
        describe_profile,
    )
    identity = describe_profile()
    r.output_intent = identity.to_dict()
    if not has_output_intent:
        r.fail(CATEGORY_OUTPUT, "MISSING_OUTPUT_INTENT",
               f"{PREVIEW_ONLY_NO_OUTPUT_INTENT}: the PDF carries no ICC "
               f"OutputIntent — {identity.detail}",
               icc_validation=identity.validation_result)
    elif not identity.valid:
        # An intent is present but the configured profile no longer validates
        # (swapped, truncated, or replaced with an RGB profile).
        r.fail(CATEGORY_OUTPUT, "INVALID_OUTPUT_INTENT_PROFILE",
               f"the configured ICC profile is not a valid CMYK output "
               f"profile — {identity.detail}",
               icc_validation=identity.validation_result)
    r.checked.append("font_embedding")
    unembedded = [f[3] for f in fonts if len(f) > 3 and f[3] and
                  not str(f[3]).startswith(("ABCDEE", "AAAAAA")) and
                  len(f) > 5 and f[5] in ("", "n/a")]
    if unembedded:
        r.fail(CATEGORY_OUTPUT, "INVALID_FONT_EMBEDDING",
               f"fonts are not embedded or outlined: {sorted(set(unembedded))}")


# --- editability report (§12) -----------------------------------------------------


def _editability_report(inventory: dict, output) -> dict:
    inv = inventory or {}
    counts = inv.get("node_counts", {})
    return {
        "artwork_mode": inv.get("artwork_mode", ""),
        "vector_object_count": inv.get("vector_object_count", 0),
        "raster_object_count": inv.get("raster_count", 0),
        "raster_area_mm2": inv.get("raster_area_mm2", 0.0),
        "raster_area_fraction": inv.get("raster_area_fraction", 0.0),
        "decorative_vector_coverage": inv.get("decorative_vector_count", 0),
        "live_text_count": inv.get("live_text_count", 0),
        "outlined_text_count": inv.get("outlined_text_count", 0),
        "clipping_masks": inv.get("clip_mask_count", 0),
        "gradients": inv.get("gradient_count", 0),
        "swatches": inv.get("swatches", {}),
        "spot_colors": list(_TECHNICAL_SPOTS),
        "technical_layers": ["DIELINE_CUT", "DIELINE_FOLD", "BLEED_GUIDE",
                             "SAFE_MARGIN", "DIMENSIONS", "TECHNICAL_NOTES"],
        "printing_layers": [g["name"] for g in inv.get("layer_groups", [])
                            if g.get("role") in ("background", "decoration",
                                                 "product", "typography",
                                                 "logo", "info", "effects")],
        "reference_only_layers": [r["name"] for r in inv.get("rasters", [])
                                  if r.get("reference_only")],
        "editable_elements": (inv.get("vector_object_count", 0)
                              + inv.get("live_text_count", 0)),
        "fixed_elements": (inv.get("raster_count", 0)
                           + inv.get("outlined_text_count", 0)),
        "sticker_bridges": counts.get("sticker_bridge", 0),
        "panel_roles": inv.get("panel_roles", []),
    }


# --- helpers -----------------------------------------------------------------------


def _file_path(filefield) -> str | None:
    try:
        if filefield and filefield.name:
            path = filefield.path
            return path if os.path.exists(path) else None
    except Exception:  # noqa: BLE001 — storage without .path
        return None
    return None


def _job_json(output, suffix: str) -> dict | None:
    job = getattr(output, "dieline_job", None)
    if job is None:
        return None
    from apps.dielines.services.export_service import job_export_dir
    path = os.path.join(str(job_export_dir(job.id)), f"{job.id}{suffix}")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _has_colored_rgb(content: bytes) -> bool:
    """Colored RGB paint operators. Pure black (0 0 0) is exempt: reportlab's
    vector-barcode renderer writes a black RGB state initializer, and 0/0/0
    converts deterministically to K-only on any RIP."""
    for m in _RGB_OP_RE.finditer(content):
        try:
            if any(float(v) > 0.0 for v in m.groups()):
                return True
        except ValueError:
            return True
    return False


def _inspect_pdf(path: str) -> tuple[bool, str]:
    try:
        import fitz
    except ImportError:
        return False, ""
    rgb, parts = False, []
    try:
        with fitz.open(path) as doc:
            for page in doc:
                if _has_colored_rgb(page.read_contents() or b""):
                    rgb = True
                parts.append(page.get_text())
    except Exception:  # noqa: BLE001
        return False, ""
    return rgb, "\n".join(parts)


__all__ = ["ProductionReport", "evaluate_production",
           "CATEGORY_STRUCTURAL", "CATEGORY_ARTWORK", "CATEGORY_CONTENT",
           "CATEGORY_OUTPUT"]
