"""Provisional-structure preview set (Phase 2A-9 §5).

Generates, for one DielineJob and the open-source-adapted STE archetype,
the full structural-review package — WITHOUT artwork and WITHOUT
confirming the structure:

    1. clean cut/crease/bleed preview (SVG + PNG)
    2. labelled panel map (JSON; panel names also on the SVG/PDF)
    3. dimension overlay (production-style dimensioned PDF, provisional id)
    4. closure and flap inventory (JSON)
    5. compensation report (JSON)
    6. collision report (JSON)
    7. provisional 3D folded mockup (PNG, structural faces)
    8. 100%-scale physical-test PDF
    9. parameter table with confidence and assumptions (JSON)

Every artifact carries the labels PROVISIONAL STRUCTURE / PHYSICAL SAMPLE
REQUIRED / NOT APPROVED FOR MASS PRODUCTION. The structure record is
persisted UNCONFIRMED — the task stays at structural review.
"""
from __future__ import annotations

import json
import os

from apps.dielines.analysis.reconciliation import reconcile_dimensions
from apps.dielines.exporters.physical_test_pdf import export_physical_test_pdf
from apps.dielines.exporters.structural_comparison import build_checklist
from apps.dielines.exporters.svg_exporter import export_svg
from apps.dielines.geometry import ecma_ste, opposed_tuck
from apps.dielines.geometry.engine import calculate_dieline
from apps.dielines.services.export_service import job_export_dir
from apps.dielines.validators.schema import DielineInputJSON

PROVISIONAL_LABELS = [
    "PROVISIONAL STRUCTURE",
    "PHYSICAL SAMPLE REQUIRED",
    "NOT APPROVED FOR MASS PRODUCTION",
]

#: archetype module per template (hashes, collision report, extras)
_MODULES = {
    ecma_ste.TEMPLATE_ID: ecma_ste,
    opposed_tuck.TEMPLATE_ID: opposed_tuck,
}


def build_provisional_params(*, inner_mm: tuple, board_thickness_mm: float,
                             glue_tab_mm: float = 12.0,
                             product_name: str = "",
                             product_type: str = "",
                             template: str = ecma_ste.TEMPLATE_ID,
                             template_version: str = "0.1"
                             ) -> DielineInputJSON:
    """Validated input for a provisional archetype (dimensions are INNER)."""
    width, depth, height = inner_mm
    return DielineInputJSON(
        template=template,
        template_version=template_version,
        unit="mm",
        dimensions={"width_mm": width, "depth_mm": depth,
                    "height_mm": height},
        print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
        construction={"glue_tab_mm": glue_tab_mm,
                      "board_thickness_mm": board_thickness_mm,
                      "thickness_compensation": True},
        metadata={"product_name": product_name or "PROVISIONAL STRUCTURE",
                  "product_type": product_type or "physical-test preview"},
    )


def generate_provisional_preview(job, params: DielineInputJSON) -> dict:
    """Build the §5 artifact set. Returns the manifest (also persisted on
    ``job.extraction_result['provisional_preview']``)."""
    from apps.dielines import registry

    coords = calculate_dieline(params)
    d = coords.derived
    template_key = f"{d['structure_type']}/{d['template_version']}"
    module = _MODULES[d["archetype"]]
    collision_report = module.collision_report
    geometry_content_hashes = module.geometry_content_hashes
    parameters = dict(d["parameters"])
    # Geometry identity hashes over the registry-declared INPUT parameters
    # (same identity the structure-confirmation gate uses); the frozen spec
    # constants (hook, chamfer, ...) are part of the template VERSION.
    input_parameters = {
        "width_mm": params.dimensions.width_mm,
        "depth_mm": params.dimensions.depth_mm,
        "height_mm": params.dimensions.height_mm,
        "bleed_mm": params.print_settings.bleed_mm,
        "safe_margin_mm": params.print_settings.safe_margin_mm,
        "glue_tab_mm": params.construction.glue_tab_mm,
        "board_thickness_mm": params.construction.board_thickness_mm,
    }
    geometry_hash = registry.geometry_hash(
        d["structure_type"], d["template_version"], input_parameters)
    content_hashes = geometry_content_hashes(coords)

    out_dir = (job_export_dir(str(job.id))
               / f"provisional_{d['structure_type']}_"
                 f"{d['template_version'].replace('.', '_')}")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_dir_s = str(out_dir)
    stem = f"{job.id}_PROVISIONAL"
    manifest: dict = {
        "labels": PROVISIONAL_LABELS,
        "template_key": template_key,
        "structure_status": d["structure_status"],
        "geometry_hash": geometry_hash,
        "content_hashes": content_hashes,
        "artifacts": {},
    }

    def _save_json(name: str, payload: dict) -> str:
        path = os.path.join(out_dir_s, f"{stem}_{name}.json")
        payload = {"labels": PROVISIONAL_LABELS, "template_key": template_key,
                   "geometry_hash": geometry_hash, **payload}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, default=str)
        return path

    # 1. cut/crease/bleed preview -----------------------------------------
    export_svg(coords, stem, output_dir=out_dir_s)
    svg_path = os.path.join(out_dir_s, f"{stem}.svg")
    manifest["artifacts"]["preview_svg"] = svg_path
    png_path = os.path.join(out_dir_s, f"{stem}.png")
    try:
        import fitz
        with fitz.open(svg_path) as doc:
            doc[0].get_pixmap(matrix=fitz.Matrix(4, 4)).save(png_path)
        manifest["artifacts"]["preview_png"] = png_path
    except Exception as exc:  # noqa: BLE001 — raster preview is best-effort
        manifest["artifacts"]["preview_png_error"] = str(exc)

    # 2. labelled panel map -------------------------------------------------
    manifest["artifacts"]["panel_map"] = _save_json("panel_map", {
        "panel_sequence": [p.name for p in coords.panels],
        "panels": [{"name": p.name, "x_mm": p.x, "y_mm": p.y,
                    "width_mm": p.width, "height_mm": p.height}
                   for p in coords.panels],
        "flat_mm": [coords.flat_width_mm, coords.flat_height_mm],
    })

    # 3. dimension overlay (production-style dimensioned drawing) -----------
    try:
        from apps.dielines.exporters.production_pdf import (
            export_production_pdf,
        )
        dim_pdf = export_production_pdf(
            coords, stem,
            product_name=params.metadata.product_name,
            product_type="PROVISIONAL — PHYSICAL SAMPLE REQUIRED",
            bleed_mm=params.print_settings.bleed_mm,
            safe_margin_mm=params.print_settings.safe_margin_mm,
            glue_tab_mm=params.construction.glue_tab_mm,
            board_thickness_mm=params.construction.board_thickness_mm,
            output_dir=out_dir_s,
        )
        manifest["artifacts"]["dimension_overlay_pdf"] = dim_pdf
    except Exception as exc:  # noqa: BLE001 — overlay is diagnostic
        manifest["artifacts"]["dimension_overlay_error"] = str(exc)

    # 4./5./6. inventories + compensation + collisions ----------------------
    reconciliation = reconcile_dimensions(
        coords,
        supplied_inner=coords.dimensions.inner,
        supplied_outer=coords.dimensions.outer,
    )
    checklist = build_checklist(coords, reconciliation)
    manifest["artifacts"]["structural_checklist"] = _save_json(
        "structural_checklist", checklist)
    manifest["artifacts"]["flap_inventory"] = _save_json("flap_inventory", {
        "closure": {
            "type": "straight tuck end — both tucks hinge from the back",
            "top_tuck": {"hook_mm": d["top_tuck_lip_mm"],
                         "lock_ear_mm": d["tuck_lock_ear_mm"],
                         "shoulders": "quadratic Bezier (emitted as exact "
                                      "cubics), control k "
                                      f"{parameters['shoulder_control_k']}"},
            "bottom_tuck": "mirror of the top tuck",
            "entry_slits_mm": [d["entry_slit_mm"], d["entry_slit_depth_mm"]],
            "dust_flaps": {"count": 4, "depth_mm": d["dust_flap_height_mm"],
                           "form": "chamfer + taper "
                                   f"({parameters['chamfer_mm']} / "
                                   f"{parameters['taper_mm']} mm)"},
            "glue_flap": {"width_mm": parameters["glue_tab_mm"],
                          "corner_chamfer_mm": parameters["chamfer_mm"]},
        },
        "flap_polygons": {"tuck": len(coords.tuck_flap_polygons),
                          "dust": len(coords.dust_flap_polygons)},
    })
    manifest["artifacts"]["compensation_report"] = _save_json(
        "compensation_report", {
            "dimension_model": {
                "inner_mm": list(coords.dimensions.inner),
                "manufacture_mm": list(coords.dimensions.manufacture),
                "outer_mm": list(coords.dimensions.outer),
                "convention": "external = inner + 2t (adapted source); "
                              "reconciliation inner = manufacture - 2t",
            },
            "compensations": d["compensation_report"],
            "assumptions": d["assumptions"],
        })
    manifest["artifacts"]["collision_report"] = _save_json(
        "collision_report", {
            "archetype_checks": collision_report(coords),
            "reconciliation_checks": [
                {"name": c.name, "ok": c.ok, "value_mm": c.value_mm,
                 "limit_mm": c.limit_mm, "detail": c.detail}
                for c in reconciliation.collision_checks],
        })

    # 7. provisional 3D folded mockup ---------------------------------------
    mock_path = os.path.join(out_dir_s, f"{stem}_3d_mockup.png")
    try:
        from apps.dielines.exporters.mockup_3d import export_folded_mockup
        source_png = manifest["artifacts"].get("preview_png")
        result = (export_folded_mockup(coords, source_png, mock_path)
                  if source_png else None)
        if result:
            manifest["artifacts"]["mockup_3d"] = result
        else:
            manifest["artifacts"]["mockup_3d_error"] = (
                "mockup renderer returned nothing (diagnostic only)")
    except Exception as exc:  # noqa: BLE001 — mockup is diagnostic
        manifest["artifacts"]["mockup_3d_error"] = str(exc)

    # 8. 100%-scale physical-test PDF ----------------------------------------
    manifest["artifacts"]["physical_test_pdf"] = export_physical_test_pdf(
        coords, str(job.id), template_key=template_key,
        geometry_hash=geometry_hash, output_dir=out_dir_s,
        notes="Only a recorded physical FIT_PASS can advance this template "
              "beyond 0.1.")

    # 2A-9-CORR-2 extras: attachment map, folded diagnostic, comparison
    if d["archetype"] == opposed_tuck.TEMPLATE_ID:
        manifest["artifacts"]["attachment_map"] = _save_json(
            "attachment_map", {"attachment_map": d["attachment_map"]})
        try:
            from apps.dielines.exporters.folded_diagnostic import (
                export_folded_diagnostic,
            )
            fold_png = os.path.join(out_dir_s,
                                    f"{stem}_folded_diagnostic.png")
            if export_folded_diagnostic(coords, fold_png,
                                        collision=collision_report(coords)):
                manifest["artifacts"]["folded_diagnostic"] = fold_png
        except Exception as exc:  # noqa: BLE001 — diagnostic best-effort
            manifest["artifacts"]["folded_diagnostic_error"] = str(exc)
        try:
            from apps.dielines.exporters.attachment_overlay import (
                export_attachment_overlay,
            )
            rejected = calculate_dieline(build_provisional_params(
                inner_mm=(params.dimensions.width_mm,
                          params.dimensions.depth_mm,
                          params.dimensions.height_mm),
                board_thickness_mm=params.construction.board_thickness_mm,
                glue_tab_mm=params.construction.glue_tab_mm,
                template=ecma_ste.TEMPLATE_ID))
            overlay_png = os.path.join(out_dir_s,
                                       f"{stem}_attachment_overlay.png")
            if export_attachment_overlay(rejected, coords,
                                         d["attachment_map"], overlay_png):
                manifest["artifacts"]["attachment_overlay"] = overlay_png
        except Exception as exc:  # noqa: BLE001 — overlay best-effort
            manifest["artifacts"]["attachment_overlay_error"] = str(exc)

    # 9. parameter table -------------------------------------------------------
    manifest["artifacts"]["parameter_table"] = _save_json("parameter_table", {
        "parameters": parameters,
        "confidence": {
            "inner_dimensions": "HIGH — user-verified reference facts "
                                "(90 x 32 x 92 inner, 0.5 mm board)",
            "panel_sequence": "HIGH — user-verified reference fact",
            "closure_orientation": ("HIGH — opposing attachment per the "
                                    "reference attachment map"
                                    if d["archetype"]
                                    == opposed_tuck.TEMPLATE_ID else
                                    "REJECTED — same-panel closure "
                                    "contradicts the reference"),
            "flap_shapes": "ESTIMATED — adapted formula defaults; exact "
                           "reference contours unverifiable without the "
                           "vector file",
            "allowance_convention": "ESTIMATED — external = inner + 2t; "
                                    "physical sample decides",
        },
        "assumptions": d["assumptions"],
        "formula_provenance": d["formula_provenance"],
    })

    payload = dict(job.extraction_result or {})
    payload["provisional_preview"] = manifest
    job.extraction_result = payload
    job.save(update_fields=["extraction_result"])
    return manifest


__all__ = ["generate_provisional_preview", "build_provisional_params",
           "PROVISIONAL_LABELS"]
