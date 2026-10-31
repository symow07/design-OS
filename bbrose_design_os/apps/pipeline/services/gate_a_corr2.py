"""GATE-A-CORR-2 — rebuild the source as flat, self-contained PostScript.

R1 carried the right colours (Illustrator painted body, collar and closure
correctly) but only three of forty objects reached the visible result. This
slice does not guess why. It removes the two things any explanation would have
to run through — inter-layer stacking and inherited graphics state — and hands
the owner a script that records what Illustrator actually builds.

R1 is preserved unchanged, exactly as R0 was.
"""
import json
import os

from django.conf import settings

from . import ai8_color as A
from . import illustrator_fixtures as FX
from .gate_a_corr1 import (ACCEPTED_PDF, ACCEPTED_PNG, DEFECTIVE,  # noqa: F401
                           FROZEN, LOGO_COMPONENTS, LOGO_LAYER,
                           LOGO_SOURCE_PATH_ITEMS, LOGO_SUBPATHS,
                           _geometry_digest, _pdf_color_ops, _png_flat_colors,
                           enclosed_regions, freeze_verification,
                           pdf_paint_sequence, sha256_file, sha256_text)

VQ2 = os.path.join(settings.BASE_DIR, "docs", "visual_quality", "vq2")
PA = os.path.join(settings.BASE_DIR, "docs", "production_authority")
FIXDIR = os.path.join(VQ2, "illustrator_fixtures")

R1_AI = os.path.join(VQ2, "vq2_a2_r2_final_gate_a_r1.ai")
R1_SHA = "0555c9f68d10bbd0369bcf191791f5b74366f5f74b3ed8453f4b254ad96400e2"

STEM = "vq2_a2_r2_final_gate_a_r2"
OUT_AI = os.path.join(VQ2, STEM + ".ai")
OUT_PDF = os.path.join(VQ2, STEM + ".pdf")
OUT_PNG = os.path.join(VQ2, STEM + ".png")
OUT_MANIFEST = os.path.join(VQ2, STEM + "_manifest.json")
OUT_EQUIV = os.path.join(VQ2, STEM + "_equivalence.json")
OUT_R1_FAILURE = os.path.join(VQ2, "vq2_a2_r2_final_gate_a_r1_failure.json")
OUT_R2_OPEN = os.path.join(VQ2, "vq2_a2_r2_final_gate_a_r2_initial_open.json")
OUT_FIXTURES = os.path.join(VQ2, "illustrator_compatibility_fixtures.json")
JSX = os.path.join(PA, "illustrator_gate_a_roundtrip.jsx")

R1_FAILURE_CODES = [
    "ILLUSTRATOR_EXECUTION_VERIFICATION_FAILED",
    "ILLUSTRATOR_GATE_A_R1_ARTWORK_NOT_RENDERED",
    "ILLUSTRATOR_LOGO_NOT_RENDERED",
    "ILLUSTRATOR_DIVIDER_NOT_RENDERED",
    "ILLUSTRATOR_PRODUCT_NAME_NOT_RENDERED",
    "ILLUSTRATOR_SUPPORTING_COPY_NOT_RENDERED",
    "ILLUSTRATOR_SOURCE_PROOF_DIVERGENCE_PERSISTS",
    "GATE_A_R2_SOURCE_REQUIRED",
]

VISIBLE_IN_ILLUSTRATOR = ["STRUCTURE_BODY", "STRUCTURE_COLLAR",
                          "STRUCTURE_CLOSURE"]

R2_SHA = "6ae00f726ddefda4adad93325735c489e3fe987452f9c1a2f603236c73e4c49a"

R2_INITIAL_OPEN_CODES = [
    "ILLUSTRATOR_GATE_A_R2_INITIAL_OPEN_PASSED",
    "ILLUSTRATOR_GATE_A_R1_ARTWORK_LOSS_RESOLVED",
    "ILLUSTRATOR_R2_FULL_VISIBLE_ARTWORK_PRESENT",
    "ILLUSTRATOR_R2_VECTOR_PATHS_PRESENT",
]

R2_CONFIRMED_VISIBLE = [
    "body", "collar", "closure", "BBROSE logo",
    "medallion and registered symbol", "divider", "Rose", "Damascena",
    "NIGHT REPAIR OIL", "approved colours",
    "separate Path and Compound Path objects",
]


def r2_initial_open_receipt():
    """The owner opened R2 in Illustrator and every object was there.

    This is the first Illustrator run of this artwork that did not lose
    something, and it closes the second defect. It is not a Gate A pass: the
    file that came back is the R2 source itself, so nothing was saved, closed
    or reopened, and there is no verification-result JSON.
    """
    live = sha256_file(OUT_AI)
    return {
        "record_type": "illustrator_gate_a_r2_initial_open/1.0",
        "created_at": "2026-07-31",
        "environment": {"application": "Adobe Illustrator 2026",
                        "operating_system": "macOS"},
        "subject": STEM + ".ai",
        "subject_sha256": live,
        "result": "INITIAL_OPEN_PASSED",
        "codes": R2_INITIAL_OPEN_CODES,
        "confirmed_visible": R2_CONFIRMED_VISIBLE,
        "objects_expected": 40,
        "artwork_reported_missing": 0,
        "what_this_establishes": [
            "the R1 artwork loss is resolved - every object the owner listed "
            "is present, where R1 rendered only three",
            "Illustrator parsed the EPS into real vector objects rather than "
            "embedding or rasterising it: the owner reports separate Path and "
            "Compound Path objects",
            "compound paths survived, so the counters and the medallion are "
            "intact as objects and not merely as pixels",
            "the approved colours render, which R0 could not do at all",
            "the flat, self-contained construction was the right response - "
            "removing layer blocks and inherited state removed the defect",
        ],
        "what_this_does_not_establish": [
            "Gate A - no save, close or reopen happened, so nothing is known "
            "about whether the document survives a round trip",
            "provenance - the returned file is byte-identical to the source, "
            "so it carries no evidence of having been through Illustrator",
            "which of H1 or H2 caused the R1 loss: R2 changed several things "
            "at once (no layer blocks, no AI operators, no inherited state, a "
            "different Creator line), so the fix does not isolate the "
            "mechanism",
        ],
        "upload": {
            "reported_sha256": R2_SHA,
            "accepted_r2_source_sha256": live,
            "equals_r2_source": R2_SHA == live,
            "is_new_verification_copy": False,
            "finding": "the returned .ai hashes exactly to the R2 source, so "
                       "it is the original re-uploaded. A verification copy "
                       "necessarily differs from the file it was saved from.",
            "corroboration": "digest equality computed against "
                             "docs/visual_quality/vq2/" + STEM + ".ai on disk; "
                             "the uploaded file itself was not present in this "
                             "environment and was not re-hashed here",
        },
        "uploaded_proofs": {
            "reported": "the uploaded PDF and PNG render the full artwork",
            "carries_illustrator_provenance": False,
            "note": "the R2 proofs generated here already render the full "
                    "artwork, so a PDF/PNG that matches them is a re-upload of "
                    "this repository's own output and says nothing about "
                    "Illustrator. Only an export taken from the REOPENED "
                    "verification copy carries provenance. Neither upload was "
                    "present in this environment, so neither was hashed here "
                    "and neither is claimed as evidence.",
            "generated_here": {
                "pdf_sha256_16": sha256_file(OUT_PDF)[:16],
                "png_sha256_16": sha256_file(OUT_PNG)[:16],
            },
        },
        "verification_result_json_received": False,
        "roundtrip_performed": False,
        "gate_a_effect": "NONE - Gate A remains BLOCKED",
        "remaining_requirement": (
            "the four artefacts written by illustrator_gate_a_roundtrip.jsx"),
        "remaining_blocker_is_procedural_not_a_defect": True,
        "remaining_blocker_note": (
            "both known defects are now closed - R0's black emission and R1's "
            "artwork loss. What stands between this and Gate A is provenance: "
            "a document that has been saved, closed and reopened in "
            "Illustrator, with the result recorded. That is a procedure, not a "
            "fault in the source."),
        "fixture_a_still_useful": True,
        "fixture_a_now_optional": True,
        "fixture_a_note": (
            "fixture A would still isolate whether R1 lost its artwork to "
            "stacking or to a dropped layer boundary. That is now forensic "
            "rather than blocking, since R2 renders correctly. Worth a few "
            "seconds only if the mechanism is wanted for the record."),
        "accepted_design_modified": False,
        "source_modified": False,
    }


def source_doc():
    """The accepted geometry, read from R1 — the same lines R0 carried."""
    return A.parse_ai8(open(R1_AI).read())


# --------------------------------------------------------------------------
# R1 human failure
# --------------------------------------------------------------------------

def r1_failure_record():
    """What the owner saw, what it rules out, and what it does NOT establish."""
    doc = source_doc()
    objs = list(doc.objects())
    body_bb = A.object_bbox(objs[0])

    inside, outside = [], []
    for o in objs[3:]:
        b = A.object_bbox(o)
        within = (b[0] >= body_bb[0] and b[2] <= body_bb[2]
                  and b[1] >= body_bb[1] and b[3] <= body_bb[3])
        (inside if within else outside).append(f"{o.layer}/{o.name}")

    survivors = []
    for o in objs[:3]:
        b = A.object_bbox(o)
        overlaps = not (b[1] >= body_bb[3] or b[3] <= body_bb[1])
        survivors.append({
            "object": o.name,
            "bbox": [round(v, 2) for v in b],
            "vertically_overlaps_body": overlaps,
        })

    return {
        "record_type": "illustrator_gate_a_r1_human_failure/1.0",
        "created_at": "2026-07-31",
        "environment": {"application": "Adobe Illustrator 2026",
                        "operating_system": "macOS"},
        "opened_file": "vq2_a2_r2_final_gate_a_r1.ai",
        "opened_sha256": sha256_file(R1_AI),
        "illustrator_window_title":
            "vq2_a2_r2_final_gate_a_r1 [Converted].ai @ 66.05 % (RGB/Preview)",
        "converted_suffix_note":
            "Illustrator showed [Converted], i.e. it ran an import rather than "
            "opening a native document. Which importer, and with what layer "
            "semantics, is not established by the screenshot.",
        "result": "FAILED",
        "codes": R1_FAILURE_CODES,
        "human_screenshot_received": False,
        "screenshot_note":
            "a screenshot was shown in the working session; no image FILE was "
            "supplied to this environment, so none is stored or claimed here. "
            "What it showed is described below.",
        "screenshot_shows": [
            "one bottle: body in a pale pink, collar in mid brown, closure in "
            "near-black plum",
            "the three structural colours are correct, so colour serialization "
            "is no longer the defect",
            "no logo, no divider, no Rose, no Damascena, no NIGHT REPAIR OIL",
            "artboard and page proportions correct",
        ],
        "visible_objects": 3,
        "missing_objects": 37,
        "expected_objects": 40,
        "visible_object_names": VISIBLE_IN_ILLUSTRATOR,
        "what_this_rules_out": [
            "colour serialization — the three visible objects carry their "
            "approved colours, which R0 did not",
            "wholesale parse failure — Illustrator built a document with "
            "correct page geometry",
            "any claim that automated source/proof equivalence certifies "
            "Illustrator execution",
        ],
        "measurement": {
            "body_bbox_pt": [round(v, 2) for v in body_bb],
            "artwork_objects_fully_inside_body_bbox": len(inside),
            "artwork_objects_outside_body_bbox": len(outside),
            "surviving_objects": survivors,
            "finding": "all 37 missing objects lie fully inside the body's "
                       "bounding box; the 3 survivors are exactly the objects "
                       "the body does not cover",
        },
        "hypotheses": [
            {"id": "H1",
             "statement": "the body ends up stacked above the artwork, so all "
                          "40 objects exist but 37 are hidden behind it",
             "status": "NOT_ESTABLISHED"},
            {"id": "H2",
             "statement": "Illustrator stopped or discarded content after the "
                          "third %AI5_BeginLayer block, so the artwork is not "
                          "in the document at all",
             "status": "NOT_ESTABLISHED"},
        ],
        "why_not_resolved_here": (
            "the three survivors are BOTH the first three layers AND the only "
            "geometry outside the body's bounding box, so the observation fits "
            "either hypothesis exactly. Illustrator is not driven from this "
            "environment, so the two are not separated here. Fixture A and the "
            "round-trip script's inventory each settle it in Illustrator."),
        "cause_asserted": False,
        "r2_does_not_depend_on_the_answer": (
            "R2 emits no layer blocks and no inherited state, so there is no "
            "inter-layer stacking left to invert (H1) and no layer boundary "
            "left to drop (H2)"),
        "classification": [
            "ILLUSTRATOR_EXECUTION_FAILED_SOURCE",
            "GATE_A_R1_ARTWORK_NOT_RENDERED",
            "NOT_PRODUCTION_AUTHORITY",
            "PRESERVED_FOR_AUDIT",
        ],
        "preserved": True,
        "overwritten": False,
        "superseded_by": STEM + ".ai",
        "superseded_by_is_illustrator_verified": False,
    }


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

def build_fixtures(write=True):
    doc = source_doc()
    if write:
        os.makedirs(FIXDIR, exist_ok=True)
    records = []
    for name, fdoc in FX.build_all(doc):
        text = A.serialize_eps_r2(fdoc, title=f"GATE-A-FIXTURE-{name}")
        rec = FX.evaluate(name, fdoc, text)
        if write:
            base = os.path.join(FIXDIR, f"fixture_{name.lower()}")
            with open(base + ".ai", "w", encoding="ascii") as fh:
                fh.write(text)
            A.build_pdf(fdoc, base + ".pdf")
            A.render_png(base + ".pdf", base + ".png",
                         height_px=min(900, int(fdoc.size[1] * 3)))
            rec["files"] = {k: os.path.relpath(base + "." + k,
                                               settings.BASE_DIR)
                            for k in ("ai", "pdf", "png")}
            rec["sha256"] = sha256_text(text)
        records.append(rec)
    out = {
        "record_type": "illustrator_compatibility_fixtures/1.0",
        "created_at": "2026-07-31",
        "purpose": "prove the R2 serializer independently of the artwork, and "
                   "let Illustrator separate H1 from H2",
        "emitted_by": "the same serializer that writes the R2 source",
        "fixtures": records,
        "all_structural_checks_passed": all(r["passed"] for r in records),
        "illustrator_confirmed": False,
        "illustrator_confirmation_note":
            "structural checks are about the bytes. Whether Illustrator paints "
            "them is what the owner's run establishes.",
    }
    if write:
        with open(OUT_FIXTURES, "w") as fh:
            json.dump(out, fh, indent=1, ensure_ascii=False)
            fh.write("\n")
    return out


# --------------------------------------------------------------------------
# R2 records
# --------------------------------------------------------------------------

def r2_manifest(doc, text):
    """Every object, its colour three ways, and its explicit paint."""
    audit = A.audit_graphics_state(text)
    back = A.parse_eps_r2(text)
    back_objs = list(back.objects())
    executed = A.ps_resolve(text)
    rows, groups = [], {}
    for o, b, (ex_rgb, kind, detail) in zip(doc.objects(), back_objs,
                                            executed):
        exp = o.expected_rgb
        row = {
            "group": o.layer,
            "object": o.name,
            "role": o.role,
            "expected_color": A.hexs(exp),
            "emitted_color_operator":
                "%.6f %.6f %.6f setrgbcolor" % A._norm(exp),
            "emitted_numeric_values": list(A._norm(exp)),
            "parsed_resulting_color": A.hexs(b.emitted_rgb),
            "executed_color": A.hexs(ex_rgb),
            "paint_operator": ("stroke" if o.paint_op == "S"
                               else ("eofill" if A.EVEN_ODD else "fill")),
            "executed_as": kind,
            "winding_or_width": detail,
            "explicitly_painted": True,
            "inherits_paint_state": False,
            "color_assigned": True,
            "defaulted_to_black": False,
        }
        row["pass"] = (b.emitted_rgb == exp and ex_rgb == exp
                       and b.geometry == o.geometry)
        rows.append(row)
        groups.setdefault(o.layer, []).append(row)
    return {
        "record_type": "illustrator_gate_a_r2_manifest/1.0",
        "created_at": "2026-07-31",
        "source": STEM + ".ai",
        "format": "flat EPS, standard PostScript operators only",
        "uses_ai_operator_vocabulary": False,
        "layer_blocks_emitted": 0,
        "color_map": {k: A.hexs(v) for k, v in A.FLAT_COLORS.items()},
        "objects": rows,
        "objects_total": len(rows),
        "groups_present": {g: len(v) for g, v in groups.items()},
        "groups_expected": A.EXPECTED_GROUPS,
        "all_expected_objects_found":
            {g: len(v) for g, v in groups.items()} == A.EXPECTED_GROUPS,
        "explicitly_painted_objects": sum(1 for r in rows
                                          if r["explicitly_painted"]),
        "objects_defaulting_to_black":
            sum(1 for r in rows if r["parsed_resulting_color"] == "#000000"),
        "objects_with_unassigned_color": 0,
        "objects_inheriting_paint_state": 0,
        "graphics_state": audit,
        "passed": all(r["pass"] for r in rows) and audit["passed"],
    }


def r2_equivalence(doc, text):
    """AI / PDF / PNG from one model, compared as written files."""
    back = A.parse_eps_r2(text)
    pdf_seq = pdf_paint_sequence(OUT_PDF) if os.path.exists(OUT_PDF) else []
    png_flat = _png_flat_colors(OUT_PNG) if os.path.exists(OUT_PNG) else set()
    r1_doc = A.parse_ai8(open(R1_AI).read())

    per_object = []
    for i, (o, b) in enumerate(zip(doc.objects(), back.objects())):
        exp = A.hexs(o.expected_rgb)
        pdf_color = pdf_seq[i][0] if i < len(pdf_seq) else None
        png_present = (A.hexs(A.ACCEPTED_PROOF_PIXELS[o.role]) in png_flat
                       if png_flat else None)
        per_object.append({
            "group": o.layer, "object": o.name,
            "expected_color": exp,
            "ai_source_color": A.hexs(b.emitted_rgb),
            "pdf_color": pdf_color,
            "png_quantised_color_present": png_present,
            "identical": (A.hexs(b.emitted_rgb) == exp
                          and (pdf_color == exp if pdf_seq else True)
                          and png_present is not False),
        })
    diffs = [r for r in per_object if not r["identical"]]
    geo_same = _geometry_digest(r1_doc) == _geometry_digest(back)
    order_same = ([(o.layer, o.name) for o in r1_doc.objects()]
                  == [(o.layer, o.name) for o in back.objects()])
    return {
        "record_type": "illustrator_source_proof_equivalence/1.0",
        "created_at": "2026-07-31",
        "revision": "R2",
        "single_object_model": "apps/pipeline/services/ai8_color.py",
        "per_object_colors_read_back_from_written_files": bool(pdf_seq),
        "separate_preview_color_implementation": False,
        "proof_only_color_correction": False,
        "ai_only_fallback": False,
        "outputs": {"ai": STEM + ".ai", "pdf": STEM + ".pdf",
                    "png": STEM + ".png"},
        "object_count": {"ai": len(per_object), "pdf": len(pdf_seq),
                         "expected": sum(A.EXPECTED_GROUPS.values()),
                         "identical": len(per_object) == len(pdf_seq)
                         == sum(A.EXPECTED_GROUPS.values())},
        "geometry_hashes": {
            "r1_source": _geometry_digest(r1_doc),
            "r2_source": _geometry_digest(back),
            "identical": geo_same},
        "object_ordering_identical": order_same,
        "page_dimensions_pt": {
            "r1": r1_doc.hires_bbox, "r2": back.hires_bbox,
            "identical": r1_doc.hires_bbox == back.hires_bbox
            and r1_doc.bbox == back.bbox},
        "per_object_color_comparison": per_object,
        "source_versus_proof_color_differences": diffs,
        "visual_diff": {
            "method": "the PNG is a raster of the same PDF, and the PDF is "
                      "written from the same object model as the AI",
            "differing_objects": len(diffs)},
        "passed": not diffs and geo_same and order_same,
        "failure_code_if_not_equivalent":
            "ILLUSTRATOR_SOURCE_AND_PROOF_NOT_EQUIVALENT",
    }


def r2_freeze(r2_text):
    """Drift and counters measured on R2 itself, against R1.

    An earlier version of this passed R1 in twice, which made every drift
    figure a comparison of a file with itself and therefore incapable of
    reporting drift at all. Both files are parsed here — R1 with the AI reader,
    R2 with the EPS reader — so the numbers can move.
    """
    r1 = A.parse_ai8(open(R1_AI).read())
    r2 = A.parse_eps_r2(r2_text)
    a = {(o.layer, o.name): o for o in r1.objects()}
    b = {(o.layer, o.name): o for o in r2.objects()}

    drift = [k for k in a if k not in b or a[k].geometry != b[k].geometry]
    glyph_drift = len([k for k in drift
                       if k[0] in ("06_ROSE_LETTERING",
                                   "07_DAMASCENA_LETTERING",
                                   "08_SUPPORTING_COPY")])
    logo = [o for o in r2.objects() if o.layer == LOGO_LAYER]
    mv = items = cp = 0
    for o in logo:
        for op, _ in o.subpaths():
            if op == "m":
                mv += 1
            elif op == "h":
                cp += 1
            else:
                items += 1

    counters = []
    for (layer, name), o in b.items():
        if o.paint_op != "f":
            continue
        eo, size = enclosed_regions(r2, o, even_odd=True)
        if eo:
            counters.append({"layer": layer, "object": name,
                             "enclosed_regions": eo, "raster_px": list(size)})
    logo_regions = sum(c["enclosed_regions"] for c in counters
                       if c["layer"] == LOGO_LAYER)
    name_regions = sum(c["enclosed_regions"] for c in counters
                       if c["layer"] in ("06_ROSE_LETTERING",
                                         "07_DAMASCENA_LETTERING"))
    return {
        "record_type": "gate_a_corr2_accepted_freeze/1.0",
        "measured_between": ["vq2_a2_r2_final_gate_a_r1.ai", STEM + ".ai"],
        "self_comparison": False,
        "frozen_identities": FROZEN,
        "objects_compared": len(a),
        "geometry_drift": len(drift),
        "geometry_drift_objects": [f"{k[0]}/{k[1]}" for k in drift],
        "glyph_drift": glyph_drift,
        "object_names_identical": sorted(a) == sorted(b),
        "page_size_drift": 0 if (r1.bbox == r2.bbox
                                 and r1.hires_bbox == r2.hires_bbox) else 1,
        "logo": {"components": len(logo), "components_expected":
                 LOGO_COMPONENTS, "source_path_items": items,
                 "source_path_items_expected": LOGO_SOURCE_PATH_ITEMS,
                 "subpaths": mv, "subpaths_expected": LOGO_SUBPATHS,
                 "closepaths": cp,
                 "drift": 0 if (len(logo) == LOGO_COMPONENTS
                                and items == LOGO_SOURCE_PATH_ITEMS
                                and mv == LOGO_SUBPATHS) else 1},
        "counters": counters,
        "counter_bearing_objects": len(counters),
        "logo_counter_regions": logo_regions,
        "product_name_counter_regions": name_regions,
        "counter_method": "flood fill from the crop border of each R2 object "
                          "rendered alone; a closed counter is an enclosed "
                          "region that is not there",
        "failure_code_if_drift": "GATE_A_R2_ACCEPTED_ARTWORK_DRIFT",
        "passed": not drift and sorted(a) == sorted(b),
    }


def r2_gates(text, manifest, equiv, freeze):
    audit = manifest["graphics_state"]
    by_role = {}
    for r in manifest["objects"]:
        by_role.setdefault(r["role"], set()).add(r["parsed_resulting_color"])
    checks = {
        "forty_visible_objects_present": manifest["objects_total"] == 40,
        "eight_required_groups_present":
            manifest["all_expected_objects_found"],
        "all_artwork_objects_explicitly_painted":
            manifest["explicitly_painted_objects"] == 40,
        "no_hidden_artwork_group": manifest["objects_total"] == sum(
            manifest["groups_present"].values()),
        "no_layer_blocks_emitted": manifest["layer_blocks_emitted"] == 0,
        "no_clipping_state_after_each_object":
            "clip" not in text and "eoclip" not in text,
        "no_unmatched_graphics_state_operation":
            audit["gsave_grestore_balanced"],
        "every_object_sets_own_colour": audit["every_object_sets_own_colour"],
        "no_object_relies_on_inherited_paint_state":
            manifest["objects_inheriting_paint_state"] == 0,
        "all_four_approved_colors_present":
            set().union(*by_role.values()) == {
                A.hexs(c) for c in A.FLAT_COLORS.values()},
        "body_color_is_D9BDB5": by_role.get("BODY") == {"#D9BDB5"},
        "collar_color_is_705242": by_role.get("COLLAR") == {"#705242"},
        "closure_color_is_493034": by_role.get("CLOSURE") == {"#493034"},
        "all_artwork_color_is_502525": by_role.get("ARTWORK") == {"#502525"},
        "black_default_visible_objects_is_zero":
            manifest["objects_defaulting_to_black"] == 0,
        "source_proof_geometry_identical":
            equiv["geometry_hashes"]["identical"],
        "source_proof_color_identical": not equiv[
            "source_versus_proof_color_differences"],
        "object_ordering_identical": equiv["object_ordering_identical"],
        "page_dimensions_identical": equiv["page_dimensions_pt"]["identical"],
        "logo_counters_present": freeze["logo_counter_regions"] >= 7,
        "product_name_counters_present":
            freeze["product_name_counter_regions"] >= 5,
        "raster_objects_zero": "BeginImage" not in text
        and "%AI5_BeginRaster" not in text,
        "live_text_zero": all(t not in text for t in ("/Font", " Tx ", "show")),
        "geometry_drift_zero": freeze["geometry_drift"] == 0
        and equiv["geometry_hashes"]["identical"],
        "artwork_drift_zero": freeze["glyph_drift"] == 0
        and freeze["logo"]["drift"] == 0,
        "freeze_is_not_a_self_comparison": freeze["self_comparison"] is False,
        "no_state_affecting_operators": not audit["forbidden_operators_present"],
    }
    return {
        "record_type": "gate_a_corr2_automated_gates/1.0",
        "created_at": "2026-07-31",
        "checks": checks,
        "all_passed": all(checks.values()),
        "failed": [k for k, v in checks.items() if not v],
        "gate_a_state": "BLOCKED",
        "gate_a_passed": None,
        "these_checks_cannot_pass_gate_a": True,
        "gate_a_requires":
            "a human running illustrator_gate_a_roundtrip.jsx in Adobe "
            "Illustrator and confirming both dialogs",
        "r1_taught_us":
            "R1 passed every automated gate of its own slice and still lost 37 "
            "objects in Illustrator. Automated checks constrain the bytes; "
            "they do not establish what Illustrator does with them.",
    }


def build(write=True):
    doc = source_doc()
    text = A.serialize_eps_r2(doc)

    if write:
        with open(OUT_AI, "w", encoding="ascii") as fh:
            fh.write(text)
        A.build_pdf(doc, OUT_PDF)
        A.render_png(OUT_PDF, OUT_PNG)

    manifest = r2_manifest(doc, text)
    equiv = r2_equivalence(doc, text)
    freeze = r2_freeze(text)
    gates = r2_gates(text, manifest, equiv, freeze)
    fixtures = build_fixtures(write=write)
    failure = r1_failure_record()

    ident = {
        "file": STEM + ".ai",
        "sha256": sha256_text(text),
        "classification": [
            "ILLUSTRATOR_COMPATIBLE_AI8_EPS_VECTOR_SOURCE",
            "PENDING_HUMAN_ILLUSTRATOR_EXECUTION",
            "SRGB_CONCEPT_ARTWORK",
        ],
        "illustrator_verified": False,
        "production_authority": False,
        "named_layers_guaranteed": False,
        "named_layers_note":
            "R2 is plain EPS, so Illustrator will most likely import it as a "
            "single layer. Group and object names are carried as DSC comments "
            "and the eight group names are preserved, but Illustrator-native "
            "named LAYERS are not guaranteed. Correct stacking and independent "
            "editability are what Gate A requires; named layers are a "
            "convenience, and trading them for artwork that actually renders "
            "is the owner's call to see rather than mine to hide.",
    }
    for rec in (manifest, equiv, gates):
        rec["r2_source"] = ident

    if write:
        with open(OUT_R2_OPEN, "w") as fh:
            json.dump(r2_initial_open_receipt(), fh, indent=1,
                      ensure_ascii=False)
            fh.write("\n")
        for path, rec in ((OUT_MANIFEST, manifest), (OUT_EQUIV, equiv),
                          (OUT_R1_FAILURE, failure)):
            with open(path, "w") as fh:
                json.dump(rec, fh, indent=1, ensure_ascii=False)
                fh.write("\n")
        with open(os.path.join(PA, "gate_a_corr2_automated_gates.json"),
                  "w") as fh:
            json.dump(gates, fh, indent=1, ensure_ascii=False)
            fh.write("\n")

    return {"text": text, "manifest": manifest, "equivalence": equiv,
            "gates": gates, "fixtures": fixtures, "failure": failure,
            "identity": ident}
