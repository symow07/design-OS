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

    # 3. Fold lines = 6 vertical/horizontal creases (slits live in cut-lines)
    if "fold-lines" in groups:
        fold_group = groups["fold-lines"]
        line_count = sum(1 for _ in fold_group.iter(tag("line")))
        if line_count != 6:
            errors.append(f"Expected 6 fold lines, found {line_count}")

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


def validate_ai(ai_path: str) -> bool:
    try:
        if os.path.getsize(ai_path) <= 0:
            return False
        with open(ai_path, "rb") as fh:
            header = fh.read(4)
    except OSError:
        return False
    return header == b"%PDF"
