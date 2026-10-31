"""Customer-supplied dieline as the authoritative structure
(Task-50 correction §3/§5/§6/§7).

Task #50 shipped on a generic 90×25×92 STE die while the customer's real
reference (Pacdora, 90×32×92 inner, 0.5 mm board) says otherwise — a
supplied manufacturing dieline must never be replaced by a generic template
because its nominal dimensions look similar. This service makes the
customer file a first-class, highest-authority structural source:

    register_customer_dieline(job, path, user)   sha256 + provenance +
                                                 measured geometry record
    customer_dieline_record(job)                 the persisted record
    validate_reference_parity(record, coords)    §7 gate with stable codes

The record is provenance + measurement, never a reusable design asset; the
source file is read, hashed and measured — no unrelated permissions are
granted, and no artwork mapping proceeds until parity passes and a human
confirms the structure.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

CUSTOMER_DIELINE_SCHEMA = "customer_supplied_dieline/1.0"
SOURCE_CUSTOMER = "CUSTOMER_SUPPLIED_DIELINE"
#: Phase 2A-9 §9 — a die supplied by the manufacturer/carton supplier
#: carries the same highest structural authority as a customer file.
SOURCE_SUPPLIER = "CUSTOMER_OR_MANUFACTURER_SUPPLIED_DIELINE"
_ALLOWED_SOURCES = frozenset({SOURCE_CUSTOMER, SOURCE_SUPPLIER})

#: §7 stable codes.
CUT_MISMATCH = "CUSTOMER_DIELINE_CUT_MISMATCH"
CREASE_MISMATCH = "CUSTOMER_DIELINE_CREASE_MISMATCH"
FLAP_MISMATCH = "CUSTOMER_DIELINE_FLAP_MISMATCH"
PANEL_SEQUENCE_MISMATCH = "CUSTOMER_DIELINE_PANEL_SEQUENCE_MISMATCH"
DIMENSION_MISMATCH = "CUSTOMER_DIELINE_DIMENSION_MISMATCH"
BLEED_MISMATCH = "CUSTOMER_DIELINE_BLEED_MISMATCH"

COORDINATE_TOLERANCE_MM = 0.1

#: Pacdora legend stroke colors (their exports label the layers by color):
#: bleed = green, trim/cut = blue, crease = red. Tolerant RGB matching.
_COLOR_ROLES = (
    ("crease", (1.0, 0.0, 0.0), 0.35),
    ("cut", (0.0, 0.0, 1.0), 0.35),
    ("bleed", (0.0, 0.7, 0.2), 0.35),
)

_SUPPORTED = (".ai", ".pdf")


class CustomerDielineError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _classify_color(color) -> str:
    if color is None:
        return "cut"
    for role, (r, g, b), tolerance in _COLOR_ROLES:
        if (abs(color[0] - r) <= tolerance and abs(color[1] - g) <= tolerance
                and abs(color[2] - b) <= tolerance):
            return role
    return "cut"


def _paths_hash(paths: list) -> str:
    payload = json.dumps(
        [[[round(v, 2) for v in point] for point in path] for path in paths],
        separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def extract_reference_geometry(path: str) -> dict:
    """Cut/crease/bleed polylines + measurements from a vector dieline
    (PDF-compatible .ai or .pdf via PyMuPDF; DXF requires ezdxf — reported,
    not silently skipped). Units normalized to mm, origin at the geometry's
    top-left; geometry itself is never altered."""
    import fitz

    suffix = Path(path).suffix.lower()
    if suffix not in _SUPPORTED:
        raise CustomerDielineError(
            "CUSTOMER_DIELINE_FORMAT_UNSUPPORTED",
            f"{suffix} import needs a dedicated parser (DXF requires ezdxf; "
            "CDR requires a CorelDRAW converter — neither is installed); "
            "supply the .ai or .pdf export. This fails CLOSED — the file is "
            "never silently skipped")
    K = 25.4 / 72.0
    roles = {"cut": [], "crease": [], "bleed": []}
    with fitz.open(path) as doc:
        page = doc[0]
        for drawing in page.get_drawings():
            role = _classify_color(drawing.get("color"))
            for item in drawing["items"]:
                kind = item[0]
                if kind == "l":
                    p1, p2 = item[1], item[2]
                    roles[role].append([[p1.x * K, p1.y * K],
                                        [p2.x * K, p2.y * K]])
                elif kind == "c":
                    points = [item[i] for i in range(1, 5)]
                    roles[role].append([[p.x * K, p.y * K] for p in points])
                elif kind == "re":
                    rect = item[1]
                    roles[role].append([
                        [rect.x0 * K, rect.y0 * K], [rect.x1 * K, rect.y0 * K],
                        [rect.x1 * K, rect.y1 * K], [rect.x0 * K, rect.y1 * K],
                        [rect.x0 * K, rect.y0 * K]])
    all_points = [pt for paths in roles.values() for pa in paths for pt in pa]
    if not all_points:
        raise CustomerDielineError(
            "CUSTOMER_DIELINE_EMPTY",
            "no vector geometry found in the reference file")
    min_x = min(p[0] for p in all_points)
    min_y = min(p[1] for p in all_points)
    for paths in roles.values():
        for pa in paths:
            for p in pa:
                p[0] = round(p[0] - min_x, 3)
                p[1] = round(p[1] - min_y, 3)

    # panel widths: vertical creases bound interior panels; the glue flap
    # and the last side panel end at the CUT contour, so the cut extent
    # supplies the outer boundaries (real manufacturing dies work this way)
    verticals = sorted({round(pa[0][0], 1) for pa in roles["crease"]
                        if len(pa) == 2
                        and abs(pa[0][0] - pa[1][0]) < 0.2
                        and abs(pa[0][1] - pa[1][1]) > 10})
    cut_xs = [p[0] for pa in roles["cut"] for p in pa]
    boundaries = list(verticals)
    if cut_xs:
        left, right = round(min(cut_xs), 1), round(max(cut_xs), 1)
        if not boundaries or left < boundaries[0] - 0.2:
            boundaries = [left] + boundaries
        if not boundaries or right > boundaries[-1] + 0.2:
            boundaries = boundaries + [right]
    panel_widths = [round(b - a, 1)
                    for a, b in zip(boundaries, boundaries[1:])]
    horizontals = sorted({round(pa[0][1], 1) for pa in roles["crease"]
                          if len(pa) == 2
                          and abs(pa[0][1] - pa[1][1]) < 0.2
                          and abs(pa[0][0] - pa[1][0]) > 10})
    body_height = (round(max(horizontals) - min(horizontals), 1)
                   if len(horizontals) >= 2 else None)
    extent_w = round(max(p[0] for pa in roles["cut"] for p in pa), 1) \
        if roles["cut"] else None
    extent_h = round(max(p[1] for pa in roles["cut"] for p in pa), 1) \
        if roles["cut"] else None

    return {
        "cut_paths": roles["cut"], "crease_paths": roles["crease"],
        "bleed_paths": roles["bleed"],
        "cut_path_hash": _paths_hash(roles["cut"]),
        "crease_path_hash": _paths_hash(roles["crease"]),
        "bleed_path_hash": _paths_hash(roles["bleed"]),
        "panel_widths_mm": panel_widths,
        "body_height_mm": body_height,
        "flat_extent_mm": [extent_w, extent_h],
        "counts": {role: len(paths) for role, paths in roles.items()},
    }


def register_customer_dieline(job, path: str, user, *,
                              inner_mm: tuple | None = None,
                              board_thickness_mm: float | None = None,
                              provenance: str = "",
                              source_type: str = SOURCE_CUSTOMER) -> dict:
    """Persist the customer/manufacturer reference as the job's
    authoritative structural source (pending human confirmation at the
    structure gate). ``source_type`` is bounded: a customer file and a
    manufacturer/supplier file carry the same top authority."""
    if source_type not in _ALLOWED_SOURCES:
        raise CustomerDielineError(
            "CUSTOMER_DIELINE_SOURCE_UNKNOWN",
            f"source_type must be one of {sorted(_ALLOWED_SOURCES)}")
    source = Path(path)
    if not source.exists():
        raise CustomerDielineError("CUSTOMER_DIELINE_FILE_MISSING", path)
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    geometry = extract_reference_geometry(path)
    record = {
        "schema_version": CUSTOMER_DIELINE_SCHEMA,
        "source": source_type,
        "file_name": source.name,
        "sha256": sha,
        "format": source.suffix.lower(),
        "provenance": provenance[:500],
        "inner_mm": list(inner_mm) if inner_mm else None,
        "board_thickness_mm": board_thickness_mm,
        "panel_widths_mm": geometry["panel_widths_mm"],
        "body_height_mm": geometry["body_height_mm"],
        "flat_extent_mm": geometry["flat_extent_mm"],
        "cut_path_hash": geometry["cut_path_hash"],
        "crease_path_hash": geometry["crease_path_hash"],
        "bleed_path_hash": geometry["bleed_path_hash"],
        "counts": geometry["counts"],
        "registered_by": getattr(user, "username", str(user)),
        "confirmed": False,
    }
    payload = dict(job.extraction_result or {})
    payload["customer_dieline"] = record
    payload["customer_dieline_geometry"] = {
        key: geometry[key] for key in ("cut_paths", "crease_paths",
                                       "bleed_paths")}
    job.extraction_result = payload
    job.save(update_fields=["extraction_result"])
    return record


def customer_dieline_record(job) -> dict | None:
    return (job.extraction_result or {}).get("customer_dieline")


def validate_reference_parity(record: dict, *, panel_widths_mm: list,
                              body_height_mm: float,
                              cut_path_hash: str = "",
                              crease_path_hash: str = "",
                              bleed_present: bool = True) -> list[str]:
    """§7: proposed/imported structure vs the registered customer record."""
    failures: list[str] = []
    expected_widths = record.get("panel_widths_mm") or []
    if len(expected_widths) != len(panel_widths_mm):
        failures.append(
            PANEL_SEQUENCE_MISMATCH
            + f": {len(panel_widths_mm)} panels vs reference "
              f"{len(expected_widths)}")
    else:
        for index, (expected, actual) in enumerate(
                zip(expected_widths, panel_widths_mm)):
            if abs(expected - actual) > COORDINATE_TOLERANCE_MM:
                failures.append(
                    DIMENSION_MISMATCH
                    + f": panel {index} width {actual}mm vs reference "
                      f"{expected}mm")
    reference_height = record.get("body_height_mm")
    if reference_height is not None and \
            abs(reference_height - body_height_mm) > COORDINATE_TOLERANCE_MM:
        failures.append(DIMENSION_MISMATCH
                        + f": body height {body_height_mm}mm vs reference "
                          f"{reference_height}mm")
    if cut_path_hash and cut_path_hash != record.get("cut_path_hash"):
        failures.append(CUT_MISMATCH + ": cut topology differs from the "
                                       "registered reference")
    if crease_path_hash and crease_path_hash != \
            record.get("crease_path_hash"):
        failures.append(CREASE_MISMATCH + ": crease topology differs from "
                                          "the registered reference")
    if not bleed_present and record.get("counts", {}).get("bleed"):
        failures.append(BLEED_MISMATCH + ": the reference carries a bleed "
                                         "contour that is missing")
    return failures


def archetype_difference_report(record: dict, coords) -> dict:
    """Phase 2A-9 §9: when a supplied die arrives, compare it with the
    provisional archetype the task was previewed on and PRESERVE the
    differences — historical provisional outputs are never rewritten.

    ``record`` is the registered customer/manufacturer record;``coords`` the
    archetype's DielineCoordinates. The report is descriptive: the supplied
    die is the authority regardless of how small the differences are.
    """
    d = coords.derived or {}
    archetype_widths = [round(p.width, 2) for p in coords.panels]
    supplied_widths = [round(w, 2) for w in record.get("panel_widths_mm") or []]
    differences: list[str] = []
    if len(supplied_widths) != len(archetype_widths):
        differences.append(
            f"panel count: supplied {len(supplied_widths)} vs archetype "
            f"{len(archetype_widths)}")
    else:
        for index, (sup, arc) in enumerate(
                zip(supplied_widths, archetype_widths)):
            if abs(sup - arc) > COORDINATE_TOLERANCE_MM:
                differences.append(
                    f"panel {index} width: supplied {sup} mm vs archetype "
                    f"{arc} mm (delta {sup - arc:+.2f})")
    supplied_h = record.get("body_height_mm")
    archetype_h = round(coords.dimensions.inner[2], 2)
    if supplied_h is not None and \
            abs(supplied_h - archetype_h) > COORDINATE_TOLERANCE_MM:
        differences.append(
            f"body height: supplied {supplied_h} mm vs archetype inner "
            f"{archetype_h} mm")
    return {
        "supplied_source": record.get("source"),
        "supplied_sha256": record.get("sha256"),
        "archetype": f"{d.get('structure_type')}/{d.get('template_version')}",
        "supplied_panel_widths_mm": supplied_widths,
        "archetype_panel_widths_mm": archetype_widths,
        "supplied_body_height_mm": supplied_h,
        "archetype_body_height_mm": archetype_h,
        "differences": differences,
        "authority": "the supplied die outranks the archetype regardless of "
                     "difference size; artwork remaps only after the "
                     "supplied die is confirmed",
    }


__all__ = ["register_customer_dieline", "customer_dieline_record",
           "extract_reference_geometry", "validate_reference_parity",
           "archetype_difference_report",
           "CustomerDielineError", "SOURCE_CUSTOMER", "SOURCE_SUPPLIER",
           "CUSTOMER_DIELINE_SCHEMA", "COORDINATE_TOLERANCE_MM"]
