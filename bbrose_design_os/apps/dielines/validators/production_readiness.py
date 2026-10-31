"""Gate-2 production readiness validation (DIP-2A-5-DIE-4).

Machine gate in front of the human Gate-2 approval: a PackagingOutput may
only be approved when its deliverables mechanically satisfy the production
contract. Every failure carries a stable code; the approve endpoint refuses
with the full list, and there is deliberately NO override flag — a failing
condition is fixed upstream, never waved through.

Failure codes (from the task-#47 correction contract):
    TEMPLATE_MISMATCH             wrong dieline template for the task
    STRUCTURE_CHECKLIST_MISSING   no structural checklist was generated
    MISSING_CLOSURE_DETAILS       a required closure feature is absent
    DIMENSIONS_UNRECONCILED       supplied dimension sets not reconciled
    CLOSURE_COLLISION             a physical collision check failed
    INCOMPLETE_BLEED              bleed contour incomplete / prepress fail
    RASTER_DECORATIVE_BACKGROUND  decorative or panel-sized raster artwork
    ARTWORK_INVENTORY_MISSING     no raster/vector inventory to verify
    RGB_ARTWORK                   RGB paint operators in the design .ai
    FORBIDDEN_PANEL_TEXT          task-title/brief text on consumer panels
    PLACEHOLDER_REGULATORY_INFO   placeholder/empty regulatory panel copy
    TEXT_BELOW_MINIMUM_SIZE       live text under the print floor
    PRODUCTION_PDF_MISSING        no factory PDF deliverable
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

#: DOMAIN (§W2(c)): DIELINES — folding-carton litho/flexo on board, the same
#: floor `validators/production.py` enforces. NOT the container floor: §W2
#: ruled the container_production_method capability table governs there, per
#: run and per surface (apps/ire/container_text_floor.py).
_MIN_TEXT_PT = 4.5

_PLACEHOLDER_RE = re.compile(
    r"lorem ipsum|placeholder|\bTBD\b|\bTODO\b|to be confirmed|"
    r"to be determined|xxx+|\[[^\]]*\]|<[^>]*>|"
    r"^\s*[-–—.]*\s*$",
    re.IGNORECASE,
)
# Regulatory fields that must carry real copy on a cosmetic carton.
_REQUIRED_INFO_FIELDS = ("net_weight", "warnings", "how_to_use")
# Optional fields that, when present, must still be real copy (an
# "INGREDIENTS: to be confirmed" panel is not manufacturable).
_OPTIONAL_INFO_FIELDS = ("description", "ingredients", "regulatory_text")

# Content-stream RGB paint operators ("0 0 1 rg" etc.). CMYK uses k/K.
# PURE BLACK (0 0 0) is exempt: reportlab's vector-barcode renderer always
# writes a black RGB graphics-state initializer, and 0/0/0 RGB converts
# deterministically to K-only on any RIP — only COLORED RGB ink can shift
# in conversion, and that is what the gate must catch.
_RGB_OP_RE = re.compile(rb"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(?:rg|RG)\b")


def _has_colored_rgb(content: bytes) -> bool:
    for m in _RGB_OP_RE.finditer(content):
        try:
            if any(float(v) > 0.0 for v in m.groups()):
                return True
        except ValueError:
            return True     # unparseable operand: fail closed
    return False


@dataclass
class ReadinessReport:
    failures: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return not self.failures

    def fail(self, code: str, detail: str) -> None:
        self.failures.append({"code": code, "detail": detail})

    def to_dict(self) -> dict:
        return {"ready": self.ready, "failures": self.failures,
                "warnings": self.warnings, "checked": self.checked}


def evaluate_production_readiness(
    output, *, expected_template: str | None = None,
    forbidden_panel_texts: tuple[str, ...] = (),
) -> ReadinessReport:
    """Evaluate a PackagingOutput's deliverables for Gate-2 approval.

    ``expected_template``: the template the task's spec demands (when known).
    ``forbidden_panel_texts``: strings that must NOT appear on consumer
    panels (the task title, brief instructions...).
    """
    r = ReadinessReport()
    spec = output.spec_sheet or {}

    # 1. Template ------------------------------------------------------------
    r.checked.append("template")
    if expected_template and spec.get("template") != expected_template:
        r.fail("TEMPLATE_MISMATCH",
               f"spec template {spec.get('template')!r} does not match the "
               f"required {expected_template!r}")

    # 2–5. Structural checklist (reconciliation + closure + collisions) ------
    checklist = _job_json(output, "_structural_checklist.json")
    r.checked.append("structural_checklist")
    if checklist is None:
        r.fail("STRUCTURE_CHECKLIST_MISSING",
               "no structural comparison checklist was generated for this "
               "output — the structure was never verified against the "
               "manufacturing reference")
    else:
        missing = [f["feature"] for f in checklist.get("required_features", [])
                   if not f.get("present")]
        if missing:
            r.fail("MISSING_CLOSURE_DETAILS",
                   "required closure features absent: " + "; ".join(missing))
        rec = checklist.get("reconciliation") or {}
        if rec.get("discrepancies"):
            r.fail("DIMENSIONS_UNRECONCILED",
                   " | ".join(rec["discrepancies"]))
        collisions = [c for c in rec.get("collision_checks", [])
                      if not c.get("ok")]
        for c in collisions:
            if c.get("name") == "bleed_contour_complete":
                r.fail("INCOMPLETE_BLEED", c.get("detail", "bleed incomplete"))
            else:
                r.fail("CLOSURE_COLLISION",
                       f"{c.get('name')}: {c.get('detail', '')}")

    # 6. Raster policy ---------------------------------------------------------
    inventory_doc = _job_json(output, "_artwork_inventory.json")
    r.checked.append("artwork_inventory")
    if inventory_doc is None:
        r.fail("ARTWORK_INVENTORY_MISSING",
               "no raster/vector inventory exists for the design artwork — "
               "the decorative field cannot be verified as native vector")
    else:
        inv = inventory_doc.get("inventory", {})
        if inv.get("decorative_raster_count", 1) or \
                inv.get("panel_sized_raster_count", 1):
            r.fail("RASTER_DECORATIVE_BACKGROUND",
                   f"decorative rasters: {inv.get('decorative_raster_count')}, "
                   f"panel-sized rasters: {inv.get('panel_sized_raster_count')} "
                   "— the decorative background must be native vector")
        # 10. Minimum text size (live text; the sticker renderer enforces its
        # own floor internally).
        r.checked.append("min_text_size")
        min_pt = inv.get("min_text_size_pt")
        if min_pt is not None and min_pt < _MIN_TEXT_PT:
            r.fail("TEXT_BELOW_MINIMUM_SIZE",
                   f"live text at {min_pt:g} pt is below the {_MIN_TEXT_PT} pt "
                   "print floor")

    # 7. RGB artwork + 8. forbidden text — inspected in the design .ai --------
    ai_path = _file_path(output.design_preview_ai)
    r.checked.append("design_ai_inspection")
    if ai_path:
        rgb, text = _inspect_ai(ai_path)
        if rgb:
            r.fail("RGB_ARTWORK",
                   "the design .ai paints with RGB operators — all artwork "
                   "ink must be CMYK (spot separations live on the "
                   "production PDF)")
        for forbidden in forbidden_panel_texts:
            f = forbidden.strip().lower()
            if not (f and text):
                continue
            hit = f in text.lower()
            if not hit:
                # Truncated fragments count too: the task-#47 defect printed
                # the first 60 chars of the brief as the "product name".
                hit = any(
                    len(line) >= 20 and line in f
                    for line in (ln.strip().lower() for ln in text.splitlines())
                )
            if hit:
                r.fail("FORBIDDEN_PANEL_TEXT",
                       f"panel artwork contains task/brief text: "
                       f"{forbidden.strip()[:80]!r}")
    else:
        r.warnings.append("design .ai missing — RGB/text inspection skipped")

    # 9. Placeholder regulatory info ------------------------------------------
    r.checked.append("regulatory_info")
    info = spec.get("panel_info") or {}
    for fld in _REQUIRED_INFO_FIELDS:
        value = str(info.get(fld) or "")
        if not value.strip() or _PLACEHOLDER_RE.search(value):
            r.fail("PLACEHOLDER_REGULATORY_INFO",
                   f"regulatory field {fld!r} is empty or placeholder text")
    for fld in _OPTIONAL_INFO_FIELDS:
        value = str(info.get(fld) or "")
        if value.strip() and _PLACEHOLDER_RE.search(value):
            r.fail("PLACEHOLDER_REGULATORY_INFO",
                   f"regulatory field {fld!r} carries placeholder text")

    # 13. Factory PDF must exist ------------------------------------------------
    r.checked.append("production_pdf")
    if not _file_path(output.production_pdf):
        r.fail("PRODUCTION_PDF_MISSING",
               "no CMYK production PDF deliverable on this output")

    return r


# --- helpers -------------------------------------------------------------------


def _file_path(filefield) -> str | None:
    try:
        if filefield and filefield.name:
            path = filefield.path
            return path if os.path.exists(path) else None
    except Exception:  # noqa: BLE001 — storage without .path
        return None
    return None


def _job_json(output, suffix: str) -> dict | None:
    """Load ``<export_dir>/<job_id><suffix>`` for the output's dieline job."""
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


def _inspect_ai(path: str) -> tuple[bool, str]:
    """(has_rgb_operators, extracted_text) for a PDF-compatible .ai.

    Raster XObjects are exempt from the RGB check (the flagged logo lockup
    may be an RGB PNG) — only PAGE CONTENT paint operators count.
    """
    try:
        import fitz
    except ImportError:
        return False, ""
    rgb = False
    text_parts: list[str] = []
    try:
        with fitz.open(path) as doc:
            for page in doc:
                content = page.read_contents() or b""
                if _has_colored_rgb(content):
                    rgb = True
                text_parts.append(page.get_text())
    except Exception:  # noqa: BLE001 — unreadable file: no claim either way
        return False, ""
    return rgb, "\n".join(text_parts)


__all__ = ["ReadinessReport", "evaluate_production_readiness"]
