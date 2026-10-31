"""Compile and inspect a pinned bottle master. Local operations; zero providers."""
from __future__ import annotations

import io
import json
import math
import shutil
import zipfile
from pathlib import Path

import fitz
from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from apps.pipeline.services.design_spec import BACKEND, digest, resolve_assets, unresolved, validate_spec


def is_hybrid(task):
    return (getattr(task, "options", None) or {}).get("authoring_backend") == BACKEND


def compile_bundle(data, destination, *, expected_hash=None):
    """Write into a NEW staging directory. Caller publishes only after success."""
    from apps.ire.compose_hybrid_bottle import compose, svg
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.rasterize import pdf_to_png
    from apps.ire.pdf_raster import render_verified
    spec = validate_spec(data, expected_hash=expected_hash)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    doc, report = compose(spec)
    # SVG is realized before the PDF emitter expands vector AssetRefs in place.
    (destination / "artwork.svg").write_bytes(svg(doc, spec))
    (destination / "artwork-back.svg").write_bytes(svg(doc, spec, back=True))
    (destination / "design-spec.json").write_text(json.dumps(spec.model_dump(), indent=2, ensure_ascii=False) + "\n")
    usage = {}
    emit_pdf_ai(doc, str(destination / "artwork.pdf"), usage_out=usage)
    shutil.copyfile(destination / "artwork.pdf", destination / "artwork-pdf-compatible.ai")
    if usage["refused"]["roles"] or usage["refused"]["chunks"]:
        raise ValueError("Required type was not emitted; this revision cannot be published.")
    source = resolve_assets(spec)[0][spec.illustration.asset_id]
    with Image.open(source) as image:
        original_pixels = digest(image.convert("RGB").tobytes())
    with fitz.open(destination / "artwork.pdf") as pdf:
        if len(pdf) != 2:
            raise ValueError("Both front and back artwork pages are required.")
        page = pdf[0]
        images = page.get_images(full=True)
        preserved = False
        for row in images:
            with Image.open(io.BytesIO(pdf.extract_image(row[0])["image"])) as image:
                if digest(image.convert("RGB").tobytes()) == original_pixels:
                    preserved = True
        if not preserved:
            raise ValueError("The exported PDF did not preserve the original illustration pixels.")
        used_fonts = list({row for p in pdf for row in p.get_fonts()})
        for role in report["fonts"].values():
            matching = [row for row in used_fonts if row[3].endswith(role["postscript"])]
            if not matching or not all(pdf.extract_font(row[0])[3] for row in matching):
                raise ValueError("A required font is not embedded in the PDF.")
        pages, logical = [], True
        for page, surface in zip(pdf, (spec.surface, spec.back_surface)):
            actual_mm = [page.rect.width / mm, page.rect.height / mm]
            if max(abs(a - b) for a, b in zip(actual_mm, (surface.width_mm, surface.height_mm))) > 0.001:
                raise ValueError("The artwork page does not match the proposed surface dimensions.")
            # Inspect visible text's actual ink bounds, not only graph boxes.
            spans = [span for block in page.get_text("dict")["blocks"] if "lines" in block
                     for line in block["lines"] for span in line["spans"]]
            safe = fitz.Rect(surface.safe_mm * mm, surface.safe_mm * mm,
                             page.rect.width - surface.safe_mm * mm, page.rect.height - surface.safe_mm * mm)
            if not spans or any(not (safe + (-.01, -.01, .01, .01)).contains(fitz.Rect(span["bbox"])) for span in spans):
                raise ValueError("Visible type is missing or crosses the proposed safe margin.")
            logical &= all(("FEFF" + row["text"].encode("utf-16-be").hex()).upper().encode()
                           in page.read_contents().upper() for row in report["text_runs"] if row["surface_id"] == surface.surface_id)
            pages.append({"surface_id": surface.surface_id, "page_mm": actual_mm})
        report.update(page_mm=pages[0]["page_mm"], surfaces=pages, original_raster_pixels_preserved=True, image_objects=len(images),
                      embedded_fonts=[row[3] for row in used_fonts if row[2] == "TrueType"],
                      logical_text_in_pdf=logical)
        if not report["logical_text_in_pdf"]:
            raise ValueError("Logical copy is missing from the exported PDF.")
    report["surface_renders"] = [render_verified(str(destination / "artwork.pdf"), str(destination / name), 600, page=page)
                                 for page, name in enumerate(("artwork.png", "artwork-back.png"))]
    # Graph geometry + the exported surface give a deterministic 2D elevation.
    # The closure profile is an explicit drawing assumption, never a measurement.
    make_review_proof(spec, destination)
    if not pdf_to_png(str(destination / "comparison-at-100-percent.pdf"), str(destination / "comparison.png"), dpi=180):
        raise ValueError("The real-size comparison could not be rendered.")
    render_verified(str(destination / "comparison-at-100-percent.pdf"), str(destination / "front-back-elevations.png"), 180, page=1)
    for node, _ in doc.walk():
        if node.type == "image":
            node.src = "assets/solar-gesture.png"
    portable = doc.model_dump()
    (destination / "design-graph.json").write_text(json.dumps(portable, indent=2, ensure_ascii=False) + "\n")
    assets = destination / "assets"
    assets.mkdir()
    shutil.copyfile(source, assets / "solar-gesture.png")
    shutil.copyfile(resolve_assets(spec)[0]["bbrose-approved-logo"], assets / "bbrose-logo.svg")
    symbol = resolve_assets(spec)[0]["estimated-sign-source"]
    shutil.copyfile(symbol, assets / symbol.name)
    shutil.copyfile(symbol.parent / "OFL.txt", assets / "estimated-sign-OFL.txt")
    from apps.pipeline.services.design_spec import resolve_fonts
    for role, font in resolve_fonts(spec.type_tokens).items():
        path = Path(font["path"])
        shutil.copyfile(path, assets / path.name)
        licence = path.parent / "OFL.txt"
        if not licence.is_file():
            raise ValueError("A font licence is missing from the delivery bundle.")
        shutil.copyfile(licence, assets / f"{role}-OFL.txt")
    report.update(schema="hybrid_preflight/1.0", spec_hash=digest(spec.model_dump()), revision=spec.revision,
                  source_asset_sha256=next(a.sha256 for a in spec.assets if a.role == "illustration"),
                  software_preflight="passed", creative_acceptance="review_pending", fidelity_acceptance="unreviewed",
                  production_ready=False, unresolved=unresolved(spec), native_ai="not_built",
                  material_appearance="illustrative_2d", print_colour="RGB proof; no supplier ICC conversion",
                  finish_plates="none_requested", prototype_cap_height_mm=32.0,
                  prototype_height_convention=("108 mm overall, owner-provided" if spec.stock.height_datum == "overall"
                                               else "108 mm overall for comparison only; stock datum unresolved"),
                  pdf_artwork_layers=["ARTWORK"], svg_groups=["ARTWORK", "LIVE TYPE", "LOGO"],
                  proof_annotations="Safe inset and dimensions on the comparison sheet; no supplier cutline or bleed")
    (destination / "preflight.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    (destination / "READ-ME.txt").write_text(
        "Sun Repair / S-2422-type — proposed editable artwork\n\n"
        "Print comparison-at-100-percent.pdf at 100%, without Fit to page. Check its 50 mm bar.\n"
        "artwork.pdf and artwork-pdf-compatible.ai carry identical editable PDF content.\n"
        "The latter is NOT a native Illustrator file. SVG embeds live type, fonts, vector logo and original illustration.\n"
        "The front elevation is a deterministic cylindrical projection, with an assumed cap and shoulder. It is not 3D.\n"
        "The original concept is a direction reference; layout/material changes are deliberate and unapproved.\n"
        "No production release, creative pass or fidelity pass is claimed. Read preflight.json for unresolved items.\n")
    files = {path.name: digest(path.read_bytes()) for path in destination.iterdir() if path.is_file()}
    with zipfile.ZipFile(destination / "editable-master.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(destination.rglob("*")):
            if path.is_file() and path.name != "editable-master.zip":
                archive.write(path, path.relative_to(destination))
    files["editable-master.zip"] = digest((destination / "editable-master.zip").read_bytes())
    return {"backend": BACKEND, "design_spec": spec.model_dump(), "spec_hash": digest(spec.model_dump()),
            "preflight": report, "artifact_hashes": files, "creative_acceptance": "review_pending",
            "production_ready": False}


def make_review_proof(spec, destination):
    """A4 landscape, real mm. View uses one master via cylindrical arc projection."""
    destination = Path(destination)
    raw = destination / "review-base.pdf"
    canvas = Canvas(str(raw), pagesize=(297 * mm, 210 * mm))
    navy, grey = HexColor("#1D3444"), HexColor("#55646E")
    def text(x, y, words, size=9, color=navy):
        canvas.setFillColor(color)
        canvas.setFont("Helvetica", size)
        canvas.drawString(x * mm, (210 - y) * mm, words)
    canvas.setFillColor(HexColor("#F6F4EE")); canvas.rect(0, 0, 297 * mm, 210 * mm, fill=1, stroke=0)
    text(15, 17, "SUN REPAIR / THE AUTHORED MASTER", 19)
    text(15, 25, "Day 2  |  Concept reference beside the new export  |  Creative review pending", 9, grey)
    text(20, 38, "ORIGINAL CONCEPT", 9)
    text(104, 38, "NEW MASTER / PROPOSED BOTTLE", 9)
    text(208, 38, "FRONT / 1:1", 8)
    text(250, 38, "BACK / 1:1", 8)
    paths, _ = resolve_assets(spec)
    concept = paths["sun-repair-concept-147"]
    # Fixed, recorded visual bounds of the retained 1024×1536 concept.
    # Clip the picture for comparison only; original bytes remain immutable.
    x0, y0, x1, y1 = 317, 95, 696, 1470
    scale = 108 / (y1 - y0)
    px, py = 32.0, 46.0
    canvas.saveState()
    clip = canvas.beginPath(); clip.rect(px * mm, (210 - py - 108) * mm, (x1 - x0) * scale * mm, 108 * mm)
    canvas.clipPath(clip, stroke=0, fill=0)
    canvas.drawImage(str(concept), (px - x0 * scale) * mm, (210 - py - (1536 - y0) * scale) * mm,
                     1024 * scale * mm, 1536 * scale * mm)
    canvas.restoreState()
    bottle_x, top = 130.0, 46.0
    draw_bottle(canvas, spec, destination / "artwork.png", bottle_x, top)
    # Dimension lines describe the display convention, not a supplier certificate.
    canvas.setStrokeColor(grey); canvas.setLineWidth(0.35)
    canvas.line(170 * mm, (210 - top) * mm, 170 * mm, (210 - top - 108) * mm)
    for yy in (top, top + 108):
        canvas.line(168 * mm, (210 - yy) * mm, 172 * mm, (210 - yy) * mm)
    text(174, 99, "108 mm*", 8, grey)
    text(124, 162, "29 mm diameter (owner)", 8, grey)
    text(208, 117, "Two 32 x 60 mm proposed print arcs", 8, grey)
    text(208, 123, "Live type + approved vector logo", 8, grey)
    text(208, 129, "Original pixels; declared lower crop", 8, grey)
    text(208, 135, "No redraw or tracing", 8, grey)
    text(20, 162, "Layout / amber-glass reference only", 8, grey)
    text(15, 176, "*108 mm overall height is owner-provided; supplier verification is pending." if spec.stock.height_datum == "overall"
         else "*108 mm is used as overall height only to align this picture. Its actual datum is unresolved.", 9)
    text(15, 182, "Cap (32 mm), shoulder and print zone are design assumptions. New view is a 2D projection, not a stock drawing.", 9)
    text(15, 188, "The new composition changes the reference. Creative / fidelity review and supplier approval remain pending.", 9)
    canvas.setStrokeColor(navy); canvas.setLineWidth(0.7)
    canvas.line(15 * mm, 11 * mm, 65 * mm, 11 * mm)
    for xx in (15, 65): canvas.line(xx * mm, 9 * mm, xx * mm, 13 * mm)
    text(70, 201, "50 mm calibration bar  |  Print at 100%, no Fit to page. Screen size depends on zoom.", 8)
    canvas.showPage()
    canvas.setFillColor(HexColor("#F6F4EE")); canvas.rect(0, 0, 297 * mm, 210 * mm, fill=1, stroke=0)
    text(15, 17, "FRONT + BACK / SAME EXPORTED MASTER", 19)
    text(15, 25, "Proposed 2D cylindrical elevations  |  1:1 at 100% print scale", 9, grey)
    text(70, 38, "FRONT", 9); text(175, 38, "BACK", 9)
    draw_bottle(canvas, spec, destination / "artwork.png", 70, 46)
    draw_bottle(canvas, spec, destination / "artwork-back.png", 175, 46, back=True)
    text(15, 176, "Front and back are 180 degrees apart. The two 32 mm arcs leave clear side zones; no seam is assumed.", 9)
    text(15, 182, "108 mm overall height is owner-provided; stock geometry and print region remain unverified." if spec.stock.height_datum == "overall"
         else "108 mm overall is a comparison convention; actual height datum, stock geometry and print region are unresolved.", 9)
    text(15, 188, "Neither view is a physical print test or a photorealistic rendering. Creative and supplier approval remain pending.", 9)
    canvas.setStrokeColor(navy); canvas.line(15*mm, 11*mm, 65*mm, 11*mm)
    for xx in (15, 65): canvas.line(xx*mm, 9*mm, xx*mm, 13*mm)
    text(70, 201, "50 mm calibration bar  |  Print at 100%, no Fit to page.", 8)
    canvas.save()
    # Place actual exported artwork PDF, preserving live text and vectors.
    with fitz.open(raw) as proof, fitz.open(destination / "artwork.pdf") as artwork:
        for page_number, x in enumerate((208, 250)):
            rect = fitz.Rect(x * mm, 46 * mm, (x + spec.surface.width_mm) * mm, (46 + spec.surface.height_mm) * mm)
            proof[0].show_pdf_page(rect, artwork, page_number)
            inset = spec.surface.safe_mm * mm
            proof[0].draw_rect(fitz.Rect(rect.x0 + inset, rect.y0 + inset, rect.x1 - inset, rect.y1 - inset),
                              color=(.42, .60, .64), width=.3, dashes="[2 2] 0", overlay=True)
        proof.save(destination / "comparison-at-100-percent.pdf")
    raw.unlink()


def draw_bottle(canvas, spec, artwork_png, x, top, *, back=False):
    """Illustrative stock elevation. Only diameter/envelope are owner-provided.

    A 32 mm flat decoration is projected onto a 29 mm cylinder using sin(s/r).
    No beauty image is used to infer shape, copy, colours or artwork placement.
    """
    def rectangle(xx, yy, ww, hh, color, stroke=False):
        canvas.setFillColor(HexColor(color)); canvas.setStrokeColor(HexColor("#AAB8BF"))
        canvas.rect(xx * mm, (210 - yy - hh) * mm, ww * mm, hh * mm, fill=1, stroke=int(stroke))
    def gradient(xx, yy, ww, hh, colors, stops):
        canvas.saveState()
        path = canvas.beginPath(); path.rect(xx * mm, (210 - yy - hh) * mm, ww * mm, hh * mm)
        canvas.clipPath(path, stroke=0, fill=0)
        canvas.linearGradient(xx * mm, 0, (xx + ww) * mm, 0, [HexColor(c) for c in colors], stops)
        canvas.restoreState()
    geometry = spec.illustration_geometry
    cap, collar, shoulder = geometry.cap_height_mm, geometry.collar_height_mm, geometry.shoulder_height_mm
    body_top, base = top + cap, top + 108
    # One declared outline controls shoulder, cylindrical sides and rounded heel.
    canvas.saveState()
    path = canvas.beginPath()
    path.moveTo((x + 4) * mm, (210 - body_top) * mm)
    path.lineTo((x + 25) * mm, (210 - body_top) * mm)
    path.curveTo((x + 25) * mm, (210 - body_top - shoulder/2) * mm, (x + 29) * mm, (210 - body_top - shoulder/2) * mm, (x + 29) * mm, (210 - body_top - shoulder) * mm)
    path.lineTo((x + 29) * mm, (210 - base + 3) * mm)
    path.curveTo((x + 29) * mm, (210 - base + 1) * mm, (x + 28) * mm, (210 - base) * mm, (x + 26) * mm, (210 - base) * mm)
    path.lineTo((x + 3) * mm, (210 - base) * mm)
    path.curveTo((x + 1) * mm, (210 - base) * mm, x * mm, (210 - base + 1) * mm, x * mm, (210 - base + 3) * mm)
    path.lineTo(x * mm, (210 - body_top - shoulder) * mm)
    path.curveTo(x * mm, (210 - body_top - shoulder/2) * mm, (x + 4) * mm, (210 - body_top - shoulder/2) * mm, (x + 4) * mm, (210 - body_top) * mm)
    path.close()
    canvas.clipPath(path, stroke=0, fill=0)
    gradient(x, body_top, 29, 108-cap, ["#A9B8BD", "#F5F7F6", "#FFFFFF", "#DBE4E5", "#8C9DA3"], [0, .12, .48, .89, 1])
    rectangle(x + 2.0, top + 103.7, 25.0, 1.3, "#D2DFDF")
    rectangle(x + 1.3, top + cap + shoulder + 1, 0.55, 63, "#FFFFFF")
    canvas.restoreState()
    chrome = ["#293138", "#EDF1F2", "#FFFFFF", "#5E666B", "#151D21", "#E4E9EB", "#FFFFFF", "#8D979C"]
    stops = [0, .09, .24, .43, .54, .67, .86, 1]
    gradient(x + (29-geometry.cap_width_mm)/2, top, geometry.cap_width_mm, cap-collar, chrome, stops)
    gradient(x + (29-geometry.collar_width_mm)/2, top + cap-collar, geometry.collar_width_mm, collar, chrome, stops)
    canvas.setStrokeColor(HexColor("#6B747A")); canvas.setLineWidth(0.3)
    canvas.ellipse((x + 4) * mm, (210 - top - 1) * mm, (x + 25) * mm, (210 - top + .7) * mm, stroke=1, fill=0)
    for radius, color in ([] if back else [(1.7, "#DDE3E4"), (1.25, "#646D71"), (.75, "#202B31")]):
        canvas.setFillColor(HexColor(color)); canvas.circle((x + 14.5) * mm, (210 - top - 6) * mm, radius * mm, fill=1, stroke=0)
    # Narrow image strips implement the cylindrical UV mapping of the print master.
    width, height = spec.surface.width_mm, spec.surface.height_mm
    radius, middle, y = spec.stock.diameter_mm / 2, x + 14.5, top + geometry.decoration_top_mm
    strips = 200
    for i in range(strips):
        a, b = width * i / strips, width * (i + 1) / strips
        left = middle + radius * math.sin((a - width / 2) / radius)
        right = middle + radius * math.sin((b - width / 2) / radius)
        scale = (right - left) / (b - a)
        canvas.saveState()
        clip = canvas.beginPath(); clip.rect(left * mm, (210 - y - height) * mm, (right - left + .004) * mm, height * mm)
        canvas.clipPath(clip, stroke=0, fill=0)
        canvas.drawImage(str(artwork_png), (left - a * scale) * mm, (210 - y - height) * mm,
                         width * scale * mm, height * mm)
        canvas.restoreState()
