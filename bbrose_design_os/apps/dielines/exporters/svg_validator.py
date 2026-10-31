from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET

from apps.dielines.geometry.coordinates import DielineCoordinates

_REQUIRED_GROUP_IDS = ("cut-lines", "fold-lines", "bleed", "safe-area")
_SVG_NS = "http://www.w3.org/2000/svg"
_TOLERANCE = 0.5  # mm


def validate_svg(svg_string: str, expected_coords: DielineCoordinates) -> list[str]:
    """Validate an SVG string against the expected DielineCoordinates.

    Returns a list of error strings; empty means valid. All checks run —
    errors accumulate rather than short-circuit.
    """
    errors: list[str] = []

    clean = re.sub(r"<![^>]*>", "", svg_string)
    try:
        root = ET.fromstring(clean)
    except ET.ParseError as exc:
        return [f"SVG is not valid XML: {exc}"]

    def tag(local: str) -> str:
        return f"{{{_SVG_NS}}}{local}"

    groups: dict[str, ET.Element] = {}
    for elem in root.iter(tag("g")):
        gid = elem.get("id")
        if gid:
            groups[gid] = elem

    # 1. Required layers
    for required_id in _REQUIRED_GROUP_IDS:
        if required_id not in groups:
            errors.append(f"Missing SVG group: {required_id}")

    # 2. viewBox must contain the full bleed outline. The cut-line coordinate
    # contract remains absolute, but the page is larger than the flat cut size.
    viewbox_raw = root.get("viewBox", "")
    vb_parts = viewbox_raw.split()
    if len(vb_parts) != 4:
        errors.append(f"SVG viewBox is missing or malformed: '{viewbox_raw}'")
    else:
        try:
            vb_x, vb_y, vb_w, vb_h = (float(p) for p in vb_parts)
            bleed_min_x, bleed_min_y, bleed_max_x, bleed_max_y = (
                expected_coords.bleed_polygon.bounds
            )
            vb_max_x = vb_x + vb_w
            vb_max_y = vb_y + vb_h
            if vb_x > bleed_min_x + _TOLERANCE:
                errors.append(
                    f"viewBox min x {vb_x} does not contain bleed min x {bleed_min_x}"
                )
            if vb_y > bleed_min_y + _TOLERANCE:
                errors.append(
                    f"viewBox min y {vb_y} does not contain bleed min y {bleed_min_y}"
                )
            if vb_max_x < bleed_max_x - _TOLERANCE:
                errors.append(
                    f"viewBox max x {vb_max_x} does not contain bleed max x {bleed_max_x}"
                )
            if vb_max_y < bleed_max_y - _TOLERANCE:
                errors.append(
                    f"viewBox max y {vb_max_y} does not contain bleed max y {bleed_max_y}"
                )
        except ValueError:
            errors.append(f"SVG viewBox contains non-numeric values: '{viewbox_raw}'")

    # 3. Fold lines must match the engine's crease list exactly. The legacy
    # STE layout emits 6 full-span creases; the side-seam archetype
    # (DECISION-020) emits per-panel segments — the source of truth is
    # ``expected_coords.fold_lines``, not a fixed count.
    if "fold-lines" in groups:
        fold_group = groups["fold-lines"]
        line_count = sum(1 for _ in fold_group.iter(tag("line")))
        expected_folds = len(expected_coords.fold_lines)
        if line_count != expected_folds:
            errors.append(
                f"Expected {expected_folds} fold lines, found {line_count}"
            )

    # 4. SVG must contain no text elements (print-output policy)
    text_count = sum(1 for _ in root.iter(tag("text")))
    if text_count > 0:
        errors.append(f"SVG must contain no <text> elements, found {text_count}")

    # 5. cut-lines layer must contain at least one path (the cut polygon)
    if "cut-lines" in groups:
        cut_group = groups["cut-lines"]
        path_count = sum(1 for _ in cut_group.iter(tag("path")))
        if path_count < 1:
            errors.append("cut-lines layer has no <path>")

    # 6. bleed layer must contain a path
    if "bleed" in groups:
        bleed_group = groups["bleed"]
        path_count = sum(1 for _ in bleed_group.iter(tag("path")))
        if path_count < 1:
            errors.append("bleed layer has no <path>")

    return errors


def validate_ai(ai_path: str, require_spot_colors: bool = False) -> bool:
    """Basic .ai sanity check (modern .ai files are PDF-compatible).

    With ``require_spot_colors=True`` (Milestone 9.5: use for .ai files copied
    from the production PDF) the file must also declare the CutContour and
    Crease Separation colorants — preview-grade SVG-rendered .ai files fail
    this stricter check by design.
    """
    try:
        if os.path.getsize(ai_path) <= 0:
            return False
        with open(ai_path, "rb") as fh:
            data = fh.read()
    except OSError:
        return False
    if data[:4] != b"%PDF":
        return False
    if require_spot_colors:
        return _has_spot_separations(data)
    return True


def _has_spot_separations(pdf_bytes: bytes) -> bool:
    """True if the PDF declares both die-plate Separation colorants.

    reportlab writes colorspace objects (``[/Separation /CutContour
    /DeviceCMYK …]``) uncompressed even with page compression on, so a byte
    scan is reliable for our own output.
    """
    return (
        b"/Separation" in pdf_bytes
        and b"/CutContour" in pdf_bytes
        and b"/Crease" in pdf_bytes
    )


def validate_production_pdf(pdf_path: str) -> list[str]:
    """Prepress checks for the CMYK production PDF (Milestone 9.5).

    Returns a list of error strings; empty means valid. Checks:
    - file exists, non-empty, %PDF header
    - CutContour and Crease Separation colorants present (die plates)
    - /All registration separation present (marks print on every plate)
    - TrimBox and BleedBox page boxes present
    """
    errors: list[str] = []
    try:
        if os.path.getsize(pdf_path) <= 0:
            return [f"production PDF is empty: {pdf_path}"]
        with open(pdf_path, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        return [f"production PDF unreadable: {exc}"]

    if data[:4] != b"%PDF":
        errors.append("production PDF has no %PDF header")
    if b"/Separation" not in data:
        errors.append("production PDF has no Separation colorants")
    if b"/CutContour" not in data:
        errors.append("production PDF is missing the CutContour spot plate")
    if b"/Crease" not in data:
        errors.append("production PDF is missing the Crease spot plate")
    if b"/All" not in data:
        errors.append(
            "production PDF is missing the /All registration separation"
        )
    if b"/TrimBox" not in data:
        errors.append("production PDF has no TrimBox")
    if b"/BleedBox" not in data:
        errors.append("production PDF has no BleedBox")
    # a TrueType font reference without its embedded font program is a
    # guaranteed print-shop rejection; the explicit Helvetica standard-14
    # fallback (no /TrueType at all) is unaffected
    if b"/TrueType" in data and b"/FontFile2" not in data:
        errors.append(
            "production PDF references TrueType fonts without an embedded "
            "font program (/FontFile2)"
        )
    return errors
