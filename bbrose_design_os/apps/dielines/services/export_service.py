"""Shared dieline export orchestration (Milestone 10.1, fixes audit H4).

Extracted from ``DielineAgent.generate()`` so the agent path and the HTTP API
path run the exact same pipeline:

    geometry engine → SVG (+validation) → CMYK production PDF (+prepress
    checks) → Illustrator .ai (production-PDF copy, SVG fallback) → spec JSON

Every exporter receives an ABSOLUTE output directory under
``MEDIA_ROOT/dielines/<job_id>/`` — there is no working-directory pinning
anywhere (the old ``_in_export_dir`` context manager changed the CWD
process-wide and raced under concurrent Celery workers). Because the files live under
MEDIA_ROOT they are durable and servable through the authenticated routes
(``/files/<path>`` and ``/api/dielines/jobs/<id>/files/<kind>``).

The DielineJob path fields store MEDIA_ROOT-relative paths
(``dielines/<job_id>/<file>``); legacy jobs generated before Phase 10 may
still carry ``exports/...`` paths, which the file route resolves against
``settings.DIELINE_EXPORT_DIR`` for backward compatibility.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings

from apps.dielines.exporters.counter_display_files import (
    carton_ai_from_pdf,
    carton_ai_from_svg,
    write_carton_cf2,
    write_carton_dxf,
    write_carton_pdf,
    write_carton_svg,
)
from apps.dielines.exporters.svg_validator import (
    validate_ai,
    validate_production_pdf,
    validate_svg,
)
from apps.dielines.geometry.engine import calculate_dieline

_PREVIEW_AI_WARNING = (
    ".ai file is preview-grade (rendered from RGB SVG, no "
    "CutContour/Crease spot plates) — use the production PDF "
    "for the factory"
)


class DielineExportError(ValueError):
    """Raised when a generated deliverable fails validation.

    Subclasses ValueError so pre-Phase-10 callers catching ValueError keep
    working. ``details`` carries the individual validator messages.
    """

    def __init__(self, message: str, details: list[str] | None = None):
        super().__init__(message)
        self.details = list(details or [])


def job_export_dir(job_id) -> Path:
    """Absolute directory that holds every deliverable for a job."""
    return Path(settings.MEDIA_ROOT) / "dielines" / str(job_id)


def media_relative_path(job_id, filename: str) -> str:
    """MEDIA_ROOT-relative path stored on DielineJob (servable via /files/)."""
    return f"dielines/{job_id}/{filename}"


def export_filenames(job_id) -> dict[str, str]:
    job_id = str(job_id)
    return {
        "svg": f"{job_id}.svg",
        "ai": f"{job_id}.ai",
        "pdf": f"{job_id}_production.pdf",
        "spec": f"{job_id}_spec.json",
        "dxf": f"{job_id}.dxf",
        "cf2": f"{job_id}.cf2",
    }


def generate_exports(job, params, log=None, artwork_tint=None, panel_info=None, map_front=None, inside=None,
                     orientation=None) -> dict:
    """Run geometry + all exporters + validators for confirmed dimensions.

    ``job`` is a DielineJob, ``params`` a validated DielineInputJSON. Updates
    the job row (input_json, validation_status, warnings, output paths) and
    returns a dict with the SVG string, absolute file paths, the geometry
    summary and accumulated warnings.

    ``artwork_tint`` (optional): the carton's ground — its map front's own ground when the concept's map draws
    the front (``apps/pipeline/agents/aria.py``). [The clean-up of 2026-10-04 (E2), approved by the owner: the
    ``artwork_path`` and ``motif_path`` of 2026-07-04/07 are removed — no caller had passed either since the owner's
    finding on design 119.]

    [The clean-up of 2026-10-04, its one engine per job: ``vector_art_style`` and ``concept_spec`` — the direction's
    style composer drawing the carton (DIP-2A-5-DIE-3) — are removed; no caller has passed them since the Illustrator
    package was built from the carton's own map front (E5b). The composer itself stays in apps/ire.]

    ``map_front`` (optional — his go of 2026-10-02, the map path for a carton): the carton's own concept picture's
    map, its shapes traced and its type given words; in components mode it draws the front panel as the picture draws
    it (``compose_components_graph``).

    Raises DielineExportError (a ValueError) when the SVG fails validation and
    GeometryError (also a ValueError) when the engine rejects the geometry, so
    existing callers that catch ValueError keep working.
    """
    log = log or (lambda msg, data=None, level="info": None)
    job_id = str(job.id)
    names = export_filenames(job_id)
    out_dir = job_export_dir(job_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_dir_s = str(out_dir)

    # [His correction of 2026-10-07 (transcribed at a6b2092): "Never widen the carton for text; the "widen" step is
    # removed."] the carton is drawn at the size confirmed, whatever its label needs — the label shrinks to fit or stops

    log("Dieline: running geometry engine")
    coords = calculate_dieline(params)
    # [His second goal of 2026-10-06, item 2: "A FAST FOLD CHECK INSIDE THE SYSTEM: pure geometry ... run on every
    # dieline before I see it ... A failure is fixed or shown to me, never hidden."] the die folded as drawn, before
    # anything is made from it; its record travels with the design, and a failure holds Gate 2 by name
    from apps.dielines.geometry import fold_check as _fold_check
    fold_check = _fold_check.check(coords)
    log("Dieline: the die folded and checked — %d checks, %s (%.1f ms)" % (
        len(fold_check["findings"]), "every one holds" if fold_check["passed"]
        else "%d do not: %s" % (len(fold_check["failed"]), "; ".join(x["id"] for x in fold_check["failed"])),
        fold_check["ms"]), data={"failed": fold_check["failed"]}, level="info" if fold_check["passed"] else "warning")

    # --- SVG (designer working file) + validation --------------------------
    svg_string = write_carton_svg(coords, job_id, output_dir=out_dir_s)
    svg_errors = validate_svg(svg_string, coords)
    if svg_errors:
        job.input_json = dict(params.model_dump(), **({"orientation": "flat"} if orientation == "flat" else {}))
        job.validation_status = "invalid"
        job.warnings = svg_errors
        job.save(update_fields=["input_json", "validation_status", "warnings"])
        log(f"Dieline: SVG validation failed — {svg_errors}", level="error")
        raise DielineExportError(
            f"SVG validation failed: {svg_errors}", details=svg_errors,
        )
    svg_path = os.path.join(out_dir_s, names["svg"])

    # --- CMYK production / prepress PDF -------------------------------------
    # Drawn directly from coords with reportlab (no SVG round-trip). This is
    # the real factory deliverable; a failure is a warning, not fatal.
    pdf_path = None
    pdf_warnings: list[str] = []
    try:
        pdf_path = write_carton_pdf(
            coords, job_id,
            product_name=params.metadata.product_name,
            product_type=params.metadata.product_type,
            bleed_mm=params.print_settings.bleed_mm,
            safe_margin_mm=params.print_settings.safe_margin_mm,
            glue_tab_mm=params.construction.glue_tab_mm,
            board_thickness_mm=params.construction.board_thickness_mm,
            output_dir=out_dir_s,
        )
        if not os.path.exists(pdf_path):
            pdf_path = None
        else:
            # Milestone 9.5 prepress sanity checks (spot plates, /All
            # registration, TrimBox/BleedBox). Failures are warnings the
            # user sees, not fatal.
            pdf_warnings = validate_production_pdf(pdf_path)
            if pdf_warnings:
                log(
                    f"Dieline: production PDF checks failed — {pdf_warnings}",
                    level="warning",
                )
    except Exception as exc:
        log(f"Dieline: production PDF export failed — {exc}", level="warning")
        pdf_path = None

    # --- the die shop's DXF and CF2 (the consolidation of 2026-10-29: the stand die's writer writes the carton's) ------
    dxf_path = cf2_path = None
    try:
        write_carton_dxf(coords, os.path.join(out_dir_s, names["dxf"]))
        write_carton_cf2(coords, os.path.join(out_dir_s, names["cf2"]))
        dxf_path, cf2_path = os.path.join(out_dir_s, names["dxf"]), os.path.join(out_dir_s, names["cf2"])
    except Exception as exc:
        log(f"Dieline: DXF/CF2 export failed — {exc}", level="warning")

    # --- Illustrator .ai deliverable (Milestone 9.5, audit H6) ---------------
    # Modern .ai is PDF-compatible, so the factory-grade .ai is the production
    # PDF itself. Only when the PDF is unavailable do we fall back to the
    # SVG-rendered RGB file, explicitly labeled preview-grade.
    ai_path = None
    ai_source = None
    if pdf_path:
        try:
            candidate = carton_ai_from_pdf(
                pdf_path, job_id, output_dir=out_dir_s,
            )
            if os.path.exists(candidate):
                ai_path = candidate
                ai_source = "production_pdf"
        except Exception as exc:
            log(f"Dieline: .ai from production PDF failed — {exc}", level="warning")
            ai_path = None
    if ai_path is None:
        try:
            candidate = carton_ai_from_svg(svg_string, job_id, output_dir=out_dir_s)
            if os.path.exists(candidate):
                ai_path = candidate
                ai_source = "svg_preview"
                log(
                    "Dieline: .ai exported from SVG — preview-grade "
                    "(RGB, no spot plates), not a factory deliverable",
                    level="warning",
                )
        except Exception as exc:
            log(f"Dieline: .ai export skipped — {exc}", level="warning")
            ai_path = None
    if ai_path and not validate_ai(
        ai_path, require_spot_colors=(ai_source == "production_pdf"),
    ):
        log(f"Dieline: .ai failed validation, discarded — {ai_path}", level="warning")
        ai_path = None
        ai_source = None

    # --- design-on-dieline deliverable (IRE, 2026-07-08) ----------------------
    # The editable .ai is now built from the Design Graph (apps.ire): the
    # components composition goes composer -> pdf_ai emitter, so the file is
    # native editable objects (paths, live text, vector barcode, editable
    # gradients), the house mark the only raster when it is drawn from its
    # picture. The user-facing preview is a PNG rasterized from that .ai (SVG
    # policy: no user-facing SVG). Best-effort throughout.
    design_preview_png = None
    design_preview_ai = None
    design_inside_png = None   # [his final goal, 2026-10-05, B1] the INSIDE artboard's picture
    label_offer_previews = []  # [his final goal, 2026-10-05, C5] a stopped label's offers, drawn
    native_ai = None           # [his final goal, 2026-10-05, C6] the native, layered .ai
    self_check = None          # [his final goal, 2026-10-05, C7] the drawing's own check
    drawing_views = None       # [his goal of 2026-10-13, (6)] each drawing's place, for his page
    inside_print = None
    front_type = None          # §BH55 Phase 2: the carton front's type, measured where it is composed
    back_copy = None           # [his review of 119, 2026-10-05, point 2] the back's copy, laid out where it is composed
    # [the owner's finding on design 119, 2026-10-03: "Every panel is vector, drawn from the concept's map"] every
    # carton is composed, as editable objects — one whose front is drawn from its concept's map, and one given no
    # picture, with none, on its own ground; it was composed only where a picture had been made to place on it
    try:
        _tint = artwork_tint or "#EFE9E4"
        ai_out = os.path.join(out_dir_s, f"{job_id}_design_preview.ai")
        # the Design Graph, emitted as an editable .ai [the clean-up of 2026-10-04 (E2), approved by the owner:
        # this service no longer makes the pixel-faithful .ai or cuts a motif into pieces — no caller had handed
        # it a picture since the owner's finding on design 119]
        # [the owner's second answer of 2026-09-25: the house mark through its one switch
        # (apps/ire/brand_mark.py) — `png` exactly as before, `master` when an approved one is on file]
        from apps.ire import brand_mark as _brand_mark
        _house = _brand_mark.house_mark()
        from apps.ire.compose import compose_components_graph
        from apps.ire.emitters.pdf_ai import emit_pdf_ai
        doc = compose_components_graph(
            coords, tint=_tint,
            logo_path=_house["png"],
            product_name=params.metadata.product_name or "",
            subtitle=params.metadata.product_type or "",
            panel_info=panel_info, map_front=map_front, inside=inside,
            safe_margin_mm=params.print_settings.safe_margin_mm,
            turn_faces=orientation == "flat",          # [his goal of 2026-10-13, (2)] a box lying flat
            **_brand_mark.master_kwargs(_house["master"]))
        from apps.ire.compose import BACK_COPY_KEY, FRONT_TYPE_KEY, INSIDE_KEY
        # [his goal of 2026-10-13, (1): "NO check ever stops a design"] a line whose words the owner did not supply is
        # left out of the drawing — never drawn (§AE2(c)) — and said beside Approve; the carton is drawn on without it
        from apps.ire.brand_string_runtime import leave_out_provisional
        _left_out = leave_out_provisional(doc)
        front_type = doc.metadata.get(FRONT_TYPE_KEY)
        from apps.ire import views_of as _views_of
        drawing_views = _views_of.views(doc)
        inside_print = doc.metadata.get(INSIDE_KEY)
        back_copy = doc.metadata.get(BACK_COPY_KEY)
        # [his final goal, 2026-10-05, C7: "THE SYSTEM CHECKS ITS OWN WORK ... Fix them itself, or show what and
        # where. Never hand me a defect silently."] the graph repaired before it is drawn, the drawn file read after
        from apps.ire import self_check as _self_check
        _regions, _folds, _axis = _self_check.carton_frame(coords)
        design_preview_ai, self_check = _self_check.run(doc, lambda d: emit_pdf_ai(d, ai_out), _regions, folds=_folds,
                                                        safe_mm=params.print_settings.safe_margin_mm, inside_axis=_axis)
        if _left_out:
            self_check = _self_check.record(self_check["fixed"], self_check["shown"] + [
                {"kind": "brand words", "fixed": False,
                 "what": "the %s line is left out — its words were not supplied by you, and the system never writes brand "
                         "copy; give them in the brief or the product's record, then ask for changes" % run["tier"]}
                for run in _left_out])
        log("Dieline: design .ai built from the Design Graph (editable objects)")
        log("Dieline: the drawing checked its own work — %d fixed, %d to look at"
            % (len(self_check["fixed"]), len(self_check["shown"])), data={"said": self_check["said"]})
        native_ai = _native(doc, os.path.join(out_dir_s, f"{job_id}_design_native.ai"), log,
                            drawing=design_preview_ai)
        # [his final goal, 2026-10-05, C5: "Only if it still doesn't fit, STOP and offer: a wider carton, the info
        # printed on the inside, or fewer languages."] a stopped label's offers, each composed and drawn whole — no
        # paid call — and kept only where its own drawing holds the label
        from apps.ire.compose import LABEL_DOES_NOT_FIT
        if back_copy and LABEL_DOES_NOT_FIT in (back_copy.get("codes") or []) and back_copy.get("offers"):
            def composed(coords_, info_):
                return compose_components_graph(
                    coords_, tint=_tint, logo_path=_house["png"], product_name=params.metadata.product_name or "",
                    subtitle=params.metadata.product_type or "", panel_info=info_, map_front=map_front,
                    inside=inside, safe_margin_mm=params.print_settings.safe_margin_mm,
                    turn_faces=orientation == "flat",
                    **_brand_mark.master_kwargs(_house["master"]))
            label_offer_previews = _offer_previews(back_copy["offers"], params, coords, panel_info or {}, composed,
                                                   out_dir_s, job_id, log)

        # On-screen preview: a PNG snapshot of the real .ai deliverable.
        if design_preview_ai:
            from apps.ire.rasterize import pdf_to_png
            png_out = os.path.join(out_dir_s, f"{job_id}_design_preview.png")
            if pdf_to_png(design_preview_ai, png_out):
                design_preview_png = png_out
            else:
                log("Dieline: preview PNG rasterization unavailable "
                    "(no sips/pdftoppm) — .ai still produced", level="warning")
            # [his final goal, 2026-10-05, B1: "Two artboards, OUTSIDE and INSIDE."] the inside's own picture
            if doc.inside is not None:
                import fitz
                inside_png = os.path.join(out_dir_s, f"{job_id}_design_inside.png")
                with fitz.open(design_preview_ai) as drawn:
                    drawn[1].get_pixmap(dpi=150).save(inside_png)
                design_inside_png = inside_png
        log("Dieline: design deliverable generated (.ai + PNG preview)")
    except Exception as exc:  # noqa: BLE001 — preview is best-effort
        log(f"Dieline: design deliverable failed — {exc}", level="warning")
        design_preview_png = design_preview_ai = design_inside_png = None
        # [His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (1): "the design continues and the problem is shown
        # beside Approve in plain words"] a design whose drawing could not be made is never handed on in silence — its
        # die and its files are there; the drawing's absence is said beside Approve, a fault of the system's, not a check
        from apps.ire import self_check as _self_check
        self_check = _self_check.record([], [{
            "kind": "the drawing", "fixed": False,
            "what": "the design could not be drawn on its die — a fault in the system itself (%s), not one of its "
                    "checks; the die and its files are made, the design .ai and its picture are not — ask for changes "
                    "to draw it again" % type(exc).__name__}])

    # Non-fatal warnings surfaced to the user: engine geometry notes
    # (dust-flap clamp, slit reduction, thickness compensation) plus any
    # prepress-check findings on the production PDF.
    geometry_notes = list((coords.derived or {}).get("notes") or [])
    all_warnings = geometry_notes + pdf_warnings
    if ai_source == "svg_preview":
        all_warnings.append(_PREVIEW_AI_WARNING)

    summary = {
        "flat_width_mm": coords.flat_width_mm,
        "flat_height_mm": coords.flat_height_mm,
        "panel_count": len(coords.panels),
    }

    # --- machine-readable spec sheet (served as kind="spec") -----------------
    spec_path = os.path.join(out_dir_s, names["spec"])
    spec_doc = {
        "job_id": job_id,
        "template": params.template,
        "unit": params.unit,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": params.model_dump(),
        "summary": summary,
        "warnings": all_warnings,
        "ai_source": ai_source,
        "files": {
            "svg": names["svg"],
            "ai": names["ai"] if ai_path else None,
            "pdf": names["pdf"] if pdf_path else None,
            "spec": names["spec"],
        },
    }
    try:
        with open(spec_path, "w", encoding="utf-8") as fh:
            json.dump(spec_doc, fh, indent=2)
    except OSError as exc:
        log(f"Dieline: spec sheet write failed — {exc}", level="warning")
        spec_path = None

    # --- persist job state ----------------------------------------------------
    job.input_json = dict(params.model_dump(), **({"orientation": "flat"} if orientation == "flat" else {}))
    # [his second goal of 2026-10-06, item 2] the job names the style it is drawn at — a design made before the house's
    # cartons were named the reverse tuck end, drawn again, says so on its own row too
    job.template_type = params.template
    job.validation_status = "valid"
    job.warnings = all_warnings
    job.svg_output_path = media_relative_path(job_id, names["svg"])
    job.ai_output_path = media_relative_path(job_id, names["ai"]) if ai_path else ""
    job.pdf_output_path = media_relative_path(job_id, names["pdf"]) if pdf_path else ""
    job.save(update_fields=[
        "input_json", "template_type", "validation_status", "warnings", "svg_output_path",
        "ai_output_path", "pdf_output_path",
    ])
    log(
        "Dieline: SVG + CMYK production PDF generated and validated"
        if pdf_path else "Dieline: SVG generated and validated"
    )

    return {
        "svg_string": svg_string,
        "svg_path": svg_path,
        "ai_path": ai_path,
        "ai_source": ai_source,
        "production_pdf_path": pdf_path,
        "dxf_path": dxf_path,
        "cf2_path": cf2_path,
        "spec_path": spec_path,
        "design_preview_png_path": design_preview_png,   # PNG snapshot or None
        "design_preview_ai_path": design_preview_ai,
        "front_type": front_type,                          # §BH55 Phase 2: Gate 2 reads it (§BH50(f)(3))
        "back_copy": back_copy,                            # [his review of 119, 2026-10-05, point 2]
        "fold_check": fold_check,                          # [his second goal of 2026-10-06, item 2]
        "inside_print": inside_print,                      # [his final goal, 2026-10-05, B1]
        "design_inside_png_path": design_inside_png,
        "label_offer_previews": label_offer_previews,
        "native_ai": native_ai,
        "self_check": self_check,
        "drawing_views": drawing_views,
        "export_dir": out_dir_s,
        "coords": coords,
        "warnings": list(job.warnings) if job.warnings else [],
        **summary,
    }


def _native(doc, path: str, log, drawing: str | None = None) -> dict:
    """[His final goal, 2026-10-05, C6: "EVERY ELEMENT IS ITS OWN PIECE. In the .ai, each part is a separate, named layer
    or group he can select, move or delete alone. Text stays editable where possible."] The design's native .ai, built
    in Illustrator where it is on this machine — else the record says why, and the PDF-compatible .ai is the file.
    [His bug on design 124, 2026-10-12 (OWNER_BLOCKER_CLEARANCE.md, transcribed at c32250d).] Checked against
    ``drawing`` (the design's own .ai) and not offered where it does not carry it whole."""
    from django.conf import settings

    from apps.ire.emitters import native_ai
    if not settings.NATIVE_AI_BUILD:
        # [his goal of 2026-10-12, (1)] the space it would be built in said all the same — RGB, or his printer's profile
        profile = native_ai.press_profile()
        return {"schema": native_ai.SCHEMA, "built": False,
                "reason": "the native .ai is not built on this run (NATIVE_AI_BUILD is off)",
                "space": "CMYK" if profile else "RGB", "profile": profile}
    try:
        record = native_ai.build(doc, path, drawing=drawing)
    except Exception as exc:  # noqa: BLE001 — the PDF-compatible .ai stands; the record says why, never silently
        record = {"schema": native_ai.SCHEMA, "built": False, "reason": "the native .ai failed: %s" % exc}
    log("Dieline: native .ai %s" % ("built in Illustrator" if record.get("built") else "not built — %s"
                                    % record.get("reason")), level="info" if record.get("built") else "warning")
    return record


def _offer_previews(offers, params, coords, panel_info, composed, out_dir_s, job_id, log) -> list:
    """[His final goal, 2026-10-05, C5.] Each offer of a stopped label — the wider carton, each set of fewer languages —
    composed and drawn as the design would be if he took it: its .ai, the outside's picture and (where it prints one) the
    inside's; an offer whose own drawing still cannot hold the label is dropped and said. [His second goal of 2026-10-06,
    item 1] the info printed inside is no longer offered."""
    import fitz

    from apps.ire.compose import BACK_COPY_KEY, LABEL_DOES_NOT_FIT
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    variants = []
    # [his correction of 2026-10-07] a wider carton is never offered for text
    for langs in offers.get("fewer_languages") or []:
        variants.append(("fewer_languages", {"languages": list(langs)}, coords, dict(panel_info, label_languages=langs)))
    out = []
    for key, what, coords_, info_ in variants:
        doc = composed(coords_, info_)
        if LABEL_DOES_NOT_FIT in ((doc.metadata.get(BACK_COPY_KEY) or {}).get("codes") or []):
            log(f"Dieline: the offer {key} {what} still cannot hold the label when drawn — not offered", level="warning")
            continue
        stem = "%s_offer_%s%s" % (job_id, key, "_" + "-".join(what["languages"]) if "languages" in what else "")
        ai = emit_pdf_ai(doc, os.path.join(out_dir_s, stem + ".ai"))
        row = dict(what, offer=key, ai=ai, said=(doc.metadata.get(BACK_COPY_KEY) or {}).get("said") or [])
        with fitz.open(ai) as drawn:
            row["png"] = os.path.join(out_dir_s, stem + ".png")
            drawn[0].get_pixmap(dpi=110).save(row["png"])
            if drawn.page_count > 1 and doc.inside is not None:
                row["png_inside"] = os.path.join(out_dir_s, stem + "_inside.png")
                drawn[1].get_pixmap(dpi=110).save(row["png_inside"])
        out.append(row)
    return out


def resolve_export_file(job, kind: str) -> Path | None:
    """Absolute, traversal-safe path for a job deliverable, or None.

    Resolves the stored MEDIA_ROOT-relative path (Phase 10 layout). Legacy
    pre-Phase-10 jobs stored ``exports/...`` (or ``/exports/...``) paths;
    those resolve against BASE_DIR but must land inside DIELINE_EXPORT_DIR.
    """
    if kind == "spec":
        stored = media_relative_path(job.pk, export_filenames(job.pk)["spec"])
    else:
        field = {
            "svg": "svg_output_path",
            "ai": "ai_output_path",
            "pdf": "pdf_output_path",
        }.get(kind)
        if field is None:
            return None
        stored = (getattr(job, field) or "").strip()
        if not stored:
            return None

    rel = stored.lstrip("/")
    candidates = [(Path(settings.MEDIA_ROOT), rel)]
    if rel.startswith("exports/"):
        # Legacy layout: relative to BASE_DIR, confined to DIELINE_EXPORT_DIR.
        candidates.append((Path(settings.DIELINE_EXPORT_DIR), rel[len("exports/"):]))
    for root, relpath in candidates:
        root = root.resolve()
        try:
            target = (root / relpath).resolve()
        except (OSError, ValueError):
            continue
        if target.is_relative_to(root) and target.is_file():
            return target
    return None
