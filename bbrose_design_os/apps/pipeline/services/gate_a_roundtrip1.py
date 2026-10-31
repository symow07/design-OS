"""GATE A round trip 1 — artwork survived, the page did not.

The owner ran the script and a real Illustrator document came back: native
PDF-based .ai, Creator Adobe Illustrator 30.0, a hash that differs from the R2
source. Every object, colour and vector survived. What did not survive is the
page: Illustrator's generic EPS import brings the artwork in without the source
artboard, and the script saved whatever default it was handed.

Two separate things went wrong and they must not be merged:

  the ARTBOARD defect, in the script, which this slice fixes
  an ABORTED RUN, which overwrote the result JSON belonging to the run that
  produced the verification copy, leaving that copy with no provenance record

Everything here is measured from the returned file, not read from the report.
"""
import json
import os

from django.conf import settings

from .gate_a_corr2 import OUT_AI as R2_AI
from .gate_a_corr2 import STEM as R2_STEM
from .gate_a_corr2 import sha256_file

VQ2 = os.path.join(settings.BASE_DIR, "docs", "visual_quality", "vq2")
PA = os.path.join(settings.BASE_DIR, "docs", "production_authority")

DRIFT_STEM = "vq2_a2_r2_final_illustrator_verified_artboard_drift"
DRIFT_AI = os.path.join(VQ2, DRIFT_STEM + ".ai")
DRIFT_PDF = os.path.join(VQ2, DRIFT_STEM + ".pdf")
DRIFT_PNG = os.path.join(VQ2, DRIFT_STEM + ".png")
ABORTED_JSON = os.path.join(
    PA, "illustrator_execution_verification_result_aborted_run.json")
JSX = os.path.join(PA, "illustrator_gate_a_roundtrip.jsx")
OUT_RECORD = os.path.join(VQ2, "gate_a_roundtrip_1_artboard_drift.json")

DRIFT_SHA = \
    "547f55b8f6a71e9b85236d185b0fdc977497374ebf96fc50339388c8660967c0"

PAGE_W, PAGE_H = 207.1627, 493.2283
DRIFT_W, DRIFT_H = 763.654, 983.225

PASS_CODES = [
    "ILLUSTRATOR_R2_SAVE_COMPLETED",
    "ILLUSTRATOR_R2_FULL_ARTWORK_PRESERVED",
    "ILLUSTRATOR_R2_COLOURS_PRESERVED",
    "ILLUSTRATOR_R2_VECTOR_OBJECTS_PRESERVED",
]
FAIL_CODES = [
    "ILLUSTRATOR_GATE_A_PAGE_SIZE_DRIFT",
    "ILLUSTRATOR_GATE_A_ARTBOARD_NOT_PRESERVED",
    "ILLUSTRATOR_ROUNDTRIP_PARTIAL_PASS",
    "ILLUSTRATOR_EXECUTION_VERIFICATION_INCOMPLETE",
]

APPROVED = {"#D9BDB5", "#705242", "#493034", "#502525"}


def inspect_drift_copy():
    """Read the returned document itself: page, objects, colours, rasters."""
    import fitz
    d = fitz.open(DRIFT_AI)
    page = d[0]
    draw = page.get_drawings()
    fills, strokes, rect = {}, {}, None
    for it in draw:
        if it.get("fill") is not None:
            k = "#%02X%02X%02X" % tuple(round(v * 255) for v in it["fill"])
            fills[k] = fills.get(k, 0) + 1
        if it.get("color") is not None:
            k = "#%02X%02X%02X" % tuple(round(v * 255) for v in it["color"])
            strokes[k] = strokes.get(k, 0) + 1
        rect = it["rect"] if rect is None else rect | it["rect"]
    out = {
        "file": DRIFT_STEM + ".ai",
        "sha256": sha256_file(DRIFT_AI),
        "native_format": "PDF-based Illustrator document",
        "pages": len(d),
        "page_pt": [round(page.rect.width, 4), round(page.rect.height, 4)],
        "drawing_objects": len(draw),
        "filled_objects": sum(fills.values()),
        "stroked_objects": sum(strokes.values()),
        "fill_colours": fills,
        "stroke_colours": strokes,
        "raster_images": len(page.get_images()),
        "live_text_characters": len(page.get_text().strip()),
        "ink_bbox_pt": [round(v, 6) for v in
                        (rect.x0, rect.y0, rect.x1, rect.y1)] if rect else None,
        "ink_size_pt": [round(rect.width, 6), round(rect.height, 6)]
        if rect else None,
    }
    d.close()
    return out


def record(write=True):
    m = inspect_drift_copy()
    colours = set(m["fill_colours"]) | set(m["stroke_colours"])
    aborted = json.load(open(ABORTED_JSON)) if os.path.exists(ABORTED_JSON) \
        else None

    rec = {
        "record_type": "illustrator_gate_a_roundtrip_1/1.0",
        "created_at": "2026-07-31",
        "environment": {"application": "Adobe Illustrator 30.0 (Macintosh)",
                        "reported_version": "30.0.0",
                        "operating_system": "Macintosh OS 26.5.2/64"},
        "result": "ARTWORK_PASSED_ARTBOARD_FAILED",
        "pass_codes": PASS_CODES,
        "fail_codes": FAIL_CODES,

        "roundtrip_is_genuine": {
            "returned_sha256": m["sha256"],
            "matches_owner_report": m["sha256"] == DRIFT_SHA,
            "r2_source_sha256": sha256_file(R2_AI),
            "differs_from_r2_source": m["sha256"] != sha256_file(R2_AI),
            "is_native_illustrator_document": m["native_format"].startswith(
                "PDF-based"),
            "finding": "this is the first submission that is genuinely a "
                       "different file from the source, and it is a native "
                       "Illustrator document rather than our EPS. A save did "
                       "happen.",
        },

        "artwork_verified_here": {
            "measured_from": "the returned .ai itself, not the report",
            "drawing_objects": m["drawing_objects"],
            "expected_objects": 40,
            "object_count_preserved": m["drawing_objects"] == 40,
            "filled_objects": m["filled_objects"],
            "stroked_objects": m["stroked_objects"],
            "fill_colours": m["fill_colours"],
            "stroke_colours": m["stroke_colours"],
            "all_four_approved_colours_present": colours == APPROVED,
            "no_unapproved_colour": colours <= APPROVED,
            "raster_images": m["raster_images"],
            "live_text_characters": m["live_text_characters"],
            "passed": (m["drawing_objects"] == 40 and colours == APPROVED
                       and m["raster_images"] == 0
                       and m["live_text_characters"] == 0),
        },

        "artboard_failure": {
            "expected_page_pt": [PAGE_W, PAGE_H],
            "expected_page_mm": [73.08, 174.00],
            "actual_page_pt": m["page_pt"],
            "actual_page_mm": [269.40, 346.86],
            "page_size_drift": m["page_pt"] != [PAGE_W, PAGE_H],
            "ink_bbox_pt": m["ink_bbox_pt"],
            "ink_size_pt": m["ink_size_pt"],
            "artwork_translated": True,
            "artwork_rescaled": False,
            "rescale_evidence": "the ink height measures "
                                f"{m['ink_size_pt'][1]} pt against the "
                                "source's 423.989 pt - the same physical size. "
                                "The artwork moved; it did not grow.",
            "measurement_note": "ink width reads about 0.15 pt wider than the "
                                "source's analytically exact 138.9238 pt "
                                "because this reader bounds curves by their "
                                "control points. That is a measurement basis, "
                                "not a size change.",
        },

        "root_cause": {
            "statement": "the generic EPS import preserved the artwork but "
                         "brought no page with it, and the script saved the "
                         "default artboard it was handed",
            "is_an_automation_script_defect": True,
            "is_an_artwork_defect": False,
            "fix": "the script now restores the source page around the "
                   "imported artwork before Save As, and re-checks it after "
                   "reopen",
            "artwork_untouched_by_the_fix": True,
        },

        "second_finding_aborted_run": {
            "what_happened": "the result JSON on disk was written by a "
                             "DIFFERENT, aborted run: the file dialog was "
                             "given illustrator_gate_a_roundtrip.jsx instead "
                             "of the .ai, Illustrator could not open it, and "
                             "the script recorded FAIL with save, reopen and "
                             "both exports false",
            "recorded_result": (aborted or {}).get("human_result"),
            "recorded_save_completed": (aborted or {}).get("save_completed"),
            "recorded_notes": (aborted or {}).get("notes"),
            "consequence": "that FAIL record overwrote the result belonging to "
                           "the run that actually produced the verification "
                           "copy, so the returned .ai/.pdf/.png have no "
                           "script-written provenance to point at",
            "the_returned_files_are_still_genuine": True,
            "but_provenance_is_not_established_by_the_json": True,
            "preserved_as":
                "docs/production_authority/"
                "illustrator_execution_verification_result_aborted_run.json",
            "script_fixes": [
                "a selection that is not the expected .ai now STOPS the run "
                "instead of continuing into a failed open",
                "an existing result JSON is copied aside before a new one is "
                "written, so a later run can never destroy an earlier record",
            ],
        },

        "preserved_evidence": {
            "ai": DRIFT_STEM + ".ai",
            "pdf": DRIFT_STEM + ".pdf",
            "png": DRIFT_STEM + ".png",
            "sha256": m["sha256"],
            "classification": [
                "ILLUSTRATOR_ARTWORK_PASSED_ARTBOARD_FAILED",
                "PRESERVED_FOR_AUDIT",
                "NOT_PRODUCTION_AUTHORITY",
            ],
            "overwritten": False,
            "renamed_from": "vq2_a2_r2_final_illustrator_verified.ai",
            "rename_reason": "the canonical verified name is freed for the "
                             "corrected run; this file keeps the evidence",
        },

        "gate_a_effect": "NONE - Gate A remains BLOCKED",
        "accepted_artwork_modified": False,
        "r2_source_modified": False,
        "next_required": "run the corrected illustrator_gate_a_roundtrip.jsx "
                         "once more on " + R2_STEM + ".ai",
    }
    if write:
        with open(OUT_RECORD, "w") as fh:
            json.dump(rec, fh, indent=1, ensure_ascii=False)
            fh.write("\n")
    return rec


def final_gates():
    """The contract the next round trip is measured against (brief section 7).

    Declared now and evaluated when the artefacts arrive, so the bar cannot be
    lowered after seeing the result.
    """
    return {
        "record_type": "gate_a_roundtrip_final_gates/1.0",
        "created_at": "2026-07-31",
        "evaluated": False,
        "evaluated_when": "the corrected round trip returns its four artefacts",
        "requirements": {
            "verified_ai_differs_from_r2_source": None,
            "verified_ai_differs_from_artboard_drift_copy": None,
            "r2_source_unchanged": None,
            "page_width_pt_is_207_1627": None,
            "page_height_pt_is_493_2283": None,
            "no_geometry_drift": None,
            "no_colour_drift": None,
            "forty_vector_drawings_remain": None,
            "no_raster_images": None,
            "no_live_text": None,
            "logo_and_counters_preserved": None,
            "divider_width_preserved": None,
            "artwork_remains_visible": None,
            "source_pdf_and_png_correspond": None,
            "result_json_exists": None,
            "human_result_is_pass": None,
            "save_completed": None,
            "reopen_completed": None,
            "pdf_export_completed": None,
            "png_export_completed": None,
        },
        "known_hashes_that_must_not_recur": {
            "r2_source": sha256_file(R2_AI),
            "artboard_drift_copy": DRIFT_SHA,
        },
        "expected_page_pt": [PAGE_W, PAGE_H],
        "a_null_requirement_is_not_a_pass": True,
        "gate_a_state": "BLOCKED",
    }
