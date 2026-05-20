from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path


def _svg_metadata_keyword(svg_string: str) -> str:
    encoded = base64.b64encode(svg_string.encode("utf-8")).decode("ascii")
    return f"svg_source_base64:{encoded}"


def _export_with_reportlab(svg_string: str, output_path: str, job_id: str) -> None:
    from reportlab.graphics import renderPDF
    from reportlab.pdfgen import canvas
    from svglib.svglib import svg2rlg

    output_dir = os.path.dirname(output_path) or "."
    with tempfile.NamedTemporaryFile(
        "w", suffix=".svg", encoding="utf-8", dir=output_dir, delete=False,
    ) as tmp:
        tmp.write(svg_string)
        tmp_path = tmp.name

    try:
        drawing = svg2rlg(tmp_path)
        if drawing is None:
            raise ValueError("could not parse SVG for AI export")

        pdf = canvas.Canvas(output_path, pagesize=(drawing.width, drawing.height))
        pdf.setTitle(f"{job_id}.ai")
        pdf.setSubject("Illustrator-compatible PDF generated from SVG")
        pdf.setCreator("dieline-generator")
        pdf.setKeywords(_svg_metadata_keyword(svg_string))
        renderPDF.draw(drawing, pdf, 0, 0)
        pdf.save()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def export_ai(svg_string: str, job_id: str) -> str:
    """
    Convert SVG to an Illustrator-compatible .ai file.

    Modern Illustrator .ai files are PDF-compatible internally. CairoSVG is
    used when native Cairo is available; ReportLab/Svglib is the local fallback
    for environments where the Python package is installed but libcairo is not.
    Returns the saved .ai path.
    """
    output_path = f"exports/{job_id}.ai"
    os.makedirs("exports", exist_ok=True)

    try:
        import cairosvg

        cairosvg.svg2pdf(
            bytestring=svg_string.encode("utf-8"),
            write_to=output_path,
            output_width=None,
            output_height=None,
        )
    except (ImportError, OSError):
        _export_with_reportlab(svg_string, output_path, job_id)

    return output_path
