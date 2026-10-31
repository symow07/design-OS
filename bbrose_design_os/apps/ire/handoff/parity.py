"""Real Illustrator visual-parity harness (Phase 2A-8-CORR-1 §3/§9).

Executes the VERIFICATION variant of the handoff script in real
Illustrator (font preflight aborts atomically before any document exists),
collects the exported PDF/PNG, measures the ACTUAL exported geometry with
PyMuPDF and compares it against the accepted task baseline. Verification is
never claimed from the serialized graph or object counts alone.
"""
from __future__ import annotations

import json
from pathlib import Path

#: §3 tolerances.
POSITION_TOL_MM = 1.0
POSITION_TOL_FRAC = 0.02
ROTATION_TOL_DEG = 0.5

HANDOFF_FONT_UNAVAILABLE = "HANDOFF_FONT_UNAVAILABLE"
HANDOFF_TEXT_GEOMETRY_MISMATCH = "HANDOFF_TEXT_GEOMETRY_MISMATCH"
HANDOFF_MOTIF_GEOMETRY_MISMATCH = "HANDOFF_MOTIF_GEOMETRY_MISMATCH"
HANDOFF_LOGO_GEOMETRY_MISMATCH = "HANDOFF_LOGO_GEOMETRY_MISMATCH"
HANDOFF_GRADIENT_PARITY_FAILED = "HANDOFF_GRADIENT_PARITY_FAILED"


def _tol(expected_mm: float) -> float:
    return max(POSITION_TOL_MM, abs(expected_mm) * POSITION_TOL_FRAC)


def run_parity(graph: dict, package_dir: str, baseline: dict) -> dict:
    """Execute verification jsx; measure the export; compare to baseline.

    ``baseline``: {"text_spans": {"BAKED": {"w_mm":…}, …},
                   "path_count": int, "raster_count": int}
    Returns the parity report (also written to parity_report.json).
    """
    from apps.ire.handoff.illustrator_exec import (
        illustrator_available,
        run_jsx,
    )
    from apps.ire.handoff.jsx_emitter import emit_design_handoff_jsx

    out = Path(package_dir)
    report: dict = {"schema_version": "illustrator_parity_report/1.0",
                    "differences": [], "codes": []}

    verification_jsx = out / "verification_handoff.jsx"
    verification_jsx.write_text(
        emit_design_handoff_jsx(graph, verification=True))

    if not illustrator_available():
        report["status"] = "ILLUSTRATOR_EXECUTION_VERIFICATION_REQUIRED"
        report["reason"] = "Illustrator unavailable (or blocked by a modal)"
        _write(out, report, None)
        return report

    summary = run_jsx(str(verification_jsx))
    _write(out, None, summary)
    if not summary.get("executed"):
        report["status"] = "ILLUSTRATOR_EXECUTION_VERIFICATION_REQUIRED"
        report["reason"] = summary.get("reason", "")
        _write(out, report, summary)
        return report
    if summary.get("status") == HANDOFF_FONT_UNAVAILABLE:
        # atomic abort: no document was created, nothing to measure
        report["status"] = HANDOFF_FONT_UNAVAILABLE
        report["missing_fonts"] = summary.get("missingFonts", [])
        report["codes"] = [HANDOFF_FONT_UNAVAILABLE]
        _write(out, report, summary)
        return report

    exported = out / "illustrator_exported_preview.pdf"
    if not exported.exists():
        report["status"] = "ILLUSTRATOR_EXECUTION_VERIFICATION_REQUIRED"
        report["reason"] = "export did not produce a PDF"
        _write(out, report, summary)
        return report

    measured = measure_exported_pdf(str(exported))
    report["measured"] = measured
    report["baseline"] = baseline

    for text, expected in (baseline.get("text_spans") or {}).items():
        actual = (measured.get("text_spans") or {}).get(text)
        if actual is None:
            report["codes"].append(HANDOFF_TEXT_GEOMETRY_MISMATCH)
            report["differences"].append(f"text {text!r} missing from the "
                                         "Illustrator export")
            continue
        for axis in ("w_mm", "h_mm"):
            if axis in expected and abs(actual[axis] - expected[axis]) > \
                    _tol(expected[axis]):
                report["codes"].append(HANDOFF_TEXT_GEOMETRY_MISMATCH)
                report["differences"].append(
                    f"text {text!r} {axis}: exported {actual[axis]:.1f} vs "
                    f"accepted {expected[axis]:.1f}")
    if baseline.get("raster_count") is not None and \
            measured.get("raster_count") != baseline["raster_count"]:
        report["codes"].append(HANDOFF_LOGO_GEOMETRY_MISMATCH)
        report["differences"].append(
            f"raster count {measured.get('raster_count')} vs "
            f"{baseline['raster_count']}")
    if baseline.get("gradient_expected") and not measured.get("has_shading"):
        report["codes"].append(HANDOFF_GRADIENT_PARITY_FAILED)
        report["differences"].append("no gradient shading in the export")

    report["codes"] = sorted(set(report["codes"]))
    report["status"] = "PARITY_OK" if not report["codes"] else \
        "PARITY_FAILED"
    _write(out, report, summary)
    return report


def measure_exported_pdf(pdf_path: str) -> dict:
    """Actual geometry of the Illustrator-exported PDF (PyMuPDF)."""
    import fitz

    K = 25.4 / 72.0
    with fitz.open(pdf_path) as pdf:
        page = pdf[0]
        spans: dict = {}
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span["text"].strip()
                    if not text:
                        continue
                    x0, y0, x1, y1 = span["bbox"]
                    spans[text] = {"w_mm": round((x1 - x0) * K, 2),
                                   "h_mm": round((y1 - y0) * K, 2),
                                   "x_mm": round(x0 * K, 2),
                                   "y_mm": round(y0 * K, 2),
                                   "font": span.get("font", "")}
        drawings = page.get_drawings()
        images = page.get_images(full=True)
        # gradients live as /ShadingType (axial/radial) or /PatternType 2
        # objects in the PDF's resources — the authoritative check
        has_shading = False
        for xref in range(1, pdf.xref_length()):
            source = pdf.xref_object(xref, compressed=True) or ""
            if "/ShadingType" in source or "/PatternType 2" in source:
                has_shading = True
                break
        return {"text_spans": spans,
                "path_count": len(drawings),
                "raster_count": len(images),
                "has_shading": bool(has_shading),
                "page_mm": [round(page.rect.width * K, 1),
                            round(page.rect.height * K, 1)]}


def _write(out: Path, parity: dict | None, execution: dict | None) -> None:
    if parity is not None:
        (out / "parity_report.json").write_text(
            json.dumps(parity, indent=1, ensure_ascii=True))
    if execution is not None:
        (out / "illustrator_execution_report.json").write_text(
            json.dumps(execution, indent=1, ensure_ascii=True))


__all__ = ["run_parity", "measure_exported_pdf", "HANDOFF_FONT_UNAVAILABLE"]
