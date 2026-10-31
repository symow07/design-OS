"""Read-only HAYAT master page, using Day 14's database-pinned file door.

Publication copies existing artifacts. It creates no drawing, print file,
approval, gate transition, provider call, or notification.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.db import transaction

from . import master_tasks as mt

REPO = Path(settings.BASE_DIR).parent
MASTER = REPO / "docs/rounds/r1-balm/master"
PICK = REPO / "docs/rounds/r1-balm/developments/D1/A"
SLUG = "round-1-balm-hayat"
SCHEMA = "hayat_master_page/1"
PAGE_KEY = "hayat_master_page/1.0"
PAGE_URL = "/dashboard/round-1-balm/master/"
PANELS = ("body", "cap", "label", "front", "back", "side_left", "side_right", "top_end", "bottom_end")
SURFACES = ("body-wrap.ai", "cap-wrap.ai", "label.ai", "carton-artwork.ai", "leaflet.ai")
REPORTS = (
    ("fidelity.json", "Fidelity and effective PPI"),
    ("trace.json", "Cap logotype silhouette and removed 1"),
    ("cleaning.json", "Cleaning and preserved fragments"),
    ("repair/repair.json", "Owner-directed side repairs · D-R1B-7"),
    ("repair/cap-cleanup.json", "Owner-directed cap cleanup · D-R1B-8"),
    ("repair/cap-vector-patch.json", "Two local cap trace bridges · measured deviation"),
    ("repair/trace-before-cap-cleanup.json", "Trace measurements before the cap cleanup"),
    ("repair/eye1/type-repair.json", "Single eye repair · Arabic batch label and front rule"),
    ("type.json", "Live type and licensed faces"),
    ("type-cleaning.json", "Small-copy cleaning"),
    ("type-checks.json", "Type sizes, cap heights and overflow"),
    ("contrast.json", "Contrast against the plate"),
    ("net-checks.json", "Figures and ℮"),
    ("wraps.json", "Wrap bleed and seams"),
    ("wrap-ai-check.json", "Wrap AI read-back"),
    ("label-checks.json", "Label die and live tint"),
    ("carton-fold-check.json", "Carton fold check"),
    ("carton-fit-report.json", "Carton fit and copy overflow"),
    ("leaflet-fit-report.json", "Leaflet copy fit · regulated drafts"),
    ("leaflet-fold-check.json", "Provisional folded leaflet · fit inside the carton"),
    ("carton.json", "Carton geometry and panel placement"),
    ("ai-check.json", "Layered AI read-back"),
    ("native-ai-check.json", "Native Illustrator check"),
    ("derivatives.json", "Derivative differences"),
    ("allowed-differences.json", "Allowed differences"),
    ("readings.json", "Blind readings · for the record"),
    ("spend.json", "Spend"),
    ("spend-close.json", "Round 1C completion eye · separate spend audit"),
    ("audit.json", "Call audit"),
    ("checks/logotype.json", "Cap logotype silhouette and removed 1"),
    ("checks/font-activation.json", "Exact licensed fonts activated for Illustrator"),
    ("checks/dimensions.json", "Source and engine panel dimensions"),
    ("proposals/cap-emboss-proof.json", "Flagged emboss proposal · feature measurements"),
)


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _pretty(value):
    return json.dumps(value, ensure_ascii=False, indent=2)


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _exceptions(value, trail=()):
    """Surface the report's own failures; do not turn them into a second gate."""
    found = []
    if isinstance(value, list):
        for number, row in enumerate(value):
            found.extend(_exceptions(row, trail + (str(number + 1),)))
    elif isinstance(value, dict):
        name = value.get("name", " / ".join(trail))
        checks = {"at_least_5pt": "below 5 pt", "ratio_4_5_report_only": "contrast below 4.5 : 1",
                  "native_illustrator_validated": "native Illustrator validation not passed"}
        if any(part in {"body", "cap"} for part in trail):
            checks["cap_floor_2_5mm"] = "cap height below 2.5 mm"
        for key, words in checks.items():
            if value.get(key) is False:
                found.append(f"{name}: {words}")
        if value.get("overflow") is True:
            found.append(f"{name}: overflow recorded")
        if value.get("missing_glyphs"):
            found.append(f"{name}: missing glyphs recorded")
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                found.extend(_exceptions(child, trail + (key,)))
    return found


def build_manifest(master=MASTER, pick=PICK):
    """Pin only this picked sketch and its masters; the report is reviewable before publication."""
    master, pick = Path(master).resolve(), Path(pick).resolve()
    crop = _read(pick / "crop.json")
    files = {}

    def add(source, destination):
        source = Path(source).resolve()
        if not any(source.is_relative_to(root) for root in (master, pick)):
            raise ValueError("HAYAT publication source is outside the pick and master")
        if source.suffix.lower() not in {".png", ".ai", ".json", ".svg"}:
            raise ValueError("Unsupported master artifact")
        data = source.read_bytes()
        if source.suffix == ".png" and not data.startswith(mt.PNG_MAGIC):
            raise ValueError(f"Invalid PNG: {source.name}")
        if source.suffix == ".ai" and not data.startswith(b"%PDF-"):
            raise ValueError(f"AI is not PDF-compatible: {source.name}")
        relative = f"{mt.MEDIA_FOLDER}/{SLUG}/{destination}"
        files[relative] = {"source": str(source), "sha256": _digest(data), "bytes": len(data)}
        return "/files/" + relative

    fidelity_path = master / "fidelity.json"
    fidelity = _read(fidelity_path).get("panels", {}) if fidelity_path.exists() else {}
    cleaning_path = master / "cleaning.json"
    cleaning = _read(cleaning_path).get("panels", {}) if cleaning_path.exists() else {}
    repair_path = master / "repair/repair.json"
    repairs = _read(repair_path).get("panels", {}) if repair_path.exists() else {}
    cap_path = master / "repair/cap-cleanup.json"
    cap_cleanup = _read(cap_path) if cap_path.exists() else {}
    patch_path = master / "repair/cap-vector-patch.json"
    cap_patch = _read(patch_path) if patch_path.exists() else {}
    panels = []
    for name in PANELS:
        width, height = crop["panels"][name]["mm"]
        panel = {
            "name": name, "title": name.replace("_", " ").title(),
            "width_mm": round(width, 5), "height_mm": round(height, 5),
            "sketch_url": add(pick / f"{name}.png", f"sketch/{name}.png"),
            "master_url": add(master / "panels" / f"{name}-flat.png", f"panels/{name}-flat.png"),
        }
        measurement = fidelity.get(name)
        if measurement:
            fidelity_checks = measurement.get("holds")
            panel["fidelity"] = {
                "mean": measurement.get("de00_mean"), "max": measurement.get("de00_max"),
                "ssim": measurement.get("ssim"), "ppi": measurement.get("effective_ppi_at_trim"),
                "nominal_ppi": measurement.get("nominal_ppi_at_trim"),
                "holds": (isinstance(fidelity_checks, dict) and bool(fidelity_checks)
                          and all(fidelity_checks.values()) and measurement.get("ppi_300_met") is True),
                "failed": [key for key, value in measurement.get("holds", {}).items() if value is False]
                          + (["300 PPI"] if measurement.get("ppi_300_met") is False else []),
            }
        clean = cleaning.get(name)
        if clean and clean.get("before") and clean.get("after"):
            panel["cleaning"] = {
                "share_percent": round(clean["cleaned_area_share"] * 100, 2),
                "before_url": add(master / clean["before"], clean["before"]),
                "after_url": add(master / clean["after"], clean["after"]),
            }
        repair = repairs.get(name)
        if repair:
            panel["repair"] = {
                "share_percent": round(repair["changed_share_of_panel"] * 100, 2),
                "before_url": add(master / repair["before"], repair["before"]),
                "after_url": add(master / repair["after"], repair["after"]),
                "mask_url": add(master / repair["mask"], repair["mask"]),
                "meaning": repair["meaning"],
                "formerly_protected_pixels": repair["formerly_protected_paint_pixels_changed_under_new_ruling"],
            }
        if name == "cap" and cap_cleanup:
            evidence = []
            urls = {}
            for key, title in (("before", "Before cleanup"), ("after", "After cleanup"),
                               ("mask", "Local cleanup mask"), ("proof", "Cleanup proof"),
                               ("vector_overlay_preview", "Preserved vector over the cleaned ground"),
                               ("protected_pink_mask", "Protected pink mask"),
                               ("protected_pink_difference", "Protected pink difference"),
                               ("allowed_mask", "Allowed local support"), ("blend_alpha", "Blend support"),
                               ("construction_fringe_mask", "Explicit construction fringe")):
                if key not in cap_cleanup:
                    continue
                relative = cap_cleanup[key]
                urls[key + "_url"] = add(master / relative, relative)
                evidence.append({"title": title, "url": urls[key + "_url"]})
            panel["cap_cleanup"] = dict(
                urls, evidence=evidence, share_percent=round(cap_cleanup["changed_share"] * 100, 2),
                changed_pixels=cap_cleanup["changed_pixels_2x"],
                protected_pixels=cap_cleanup["protected_pink_pixels"],
                protected_changed_pixels=cap_cleanup["protected_pink_changed_pixels"],
                construction_fringe_pixels=cap_cleanup.get("construction_fringe_pixels"),
                protected_changed_outside_fringe=cap_cleanup.get("protected_pink_changed_outside_explicit_construction_fringe"),
                strong_pink_changed=cap_cleanup.get("independent_strong_pink_changed_pixels"),
                trace_unchanged=(not cap_cleanup["trace_geometry_changed"]
                                 and cap_cleanup["trace_sha256_before"] == cap_cleanup["trace_sha256_after"]),
                scope=cap_cleanup["scope"])
            if cap_patch:
                patch_evidence = []
                for key, title in (("before_vector", "Trace before the local bridges"),
                                   ("after_vector", "Final traced logotype"), ("mask", "Trace patch mask")):
                    relative = cap_patch[key]
                    patch_evidence.append({"title": title, "url": add(master / relative, relative)})
                panel["cap_cleanup"]["trace_patch"] = {
                    "iou": cap_patch["actual_saved_svg_iou_against_independent_original_sketch"],
                    "iou_holds": cap_patch["iou_0_95_met"],
                    "changed_share_percent": cap_patch["changed_share_of_word"] * 100,
                    "trace_to_sketch_mm": cap_patch["trace_to_sketch_max_mm"],
                    "sketch_to_trace_mm": cap_patch["sketch_to_trace_max_mm"],
                    "outside_notches_mm": cap_patch["outside_authorized_notch_boxes_max_mm"],
                    "overlay_holds": max(cap_patch["trace_to_sketch_max_mm"], cap_patch["sketch_to_trace_max_mm"]) <= .3,
                    "only_two_ranges": cap_patch["only_two_local_command_ranges_changed"],
                    "other_vector_bytes_unchanged": cap_patch["all_other_vector_text_byte_identical"],
                    "caveat": cap_patch["original_reference_contour_caveat"], "evidence": patch_evidence}
        panels.append(panel)
    downloads = []
    leaflets = []
    copy_fit = []
    for prefix, tint in (("", "Rosewater"), ("tints/fig-milk/", "Fig Milk"), ("tints/ember/", "Ember")):
        for name in SURFACES:
            if not (master / (prefix + name)).is_file():
                raise ValueError(f"Missing master surface: {prefix + name}")
        leaflet = {"tint": tint, "flat_url": add(master / (prefix + "leaflet-flat.png"), prefix + "leaflet-flat.png"),
                   "ai_url": add(master / (prefix + "leaflet.ai"), prefix + "leaflet.ai")}
        fold_proof = master / (prefix + "leaflet-with-die.png")
        if fold_proof.is_file():
            leaflet["fold_url"] = add(fold_proof, prefix + "leaflet-with-die.png")
        leaflets.append(leaflet)
        for surface in ("carton", "leaflet"):
            fit_file = master / (prefix + surface + "-fit-report.json")
            if fit_file.exists():
                measurement = _read(fit_file)
                lines = measurement.get("printed_lines")
                copy_fit.append({"tint": tint, "surface": surface,
                                 "hidden_characters": measurement.get("hidden_characters"),
                                 "printed_line_count": len(lines) if isinstance(lines, list) else None,
                                 "all_printed_lines_safe": (all(row["inside_safe"] is True for row in lines)
                                                            if isinstance(lines, list) and lines else None)})
    for path in sorted(master.rglob("*.ai")):
        relative = path.relative_to(master).as_posix()
        downloads.append({"name": relative, "url": add(path, relative),
                          "tint": "Fig Milk" if relative.startswith("tints/fig-milk/") else
                                  "Ember" if relative.startswith("tints/ember/") else "Rosewater"})
    reports = []
    report_sources = list(REPORTS)
    for slug, tint in (("fig-milk", "Fig Milk"), ("ember", "Ember")):
        for name in ("carton-fit-report.json", "carton-fold-check.json", "leaflet-fit-report.json", "leaflet-fold-check.json"):
            report_sources.append((f"tints/{slug}/{name}", f"{tint} · {name}"))
    for path in sorted(master.glob("**/native-checks/*.json")):
        relative = path.relative_to(master).as_posix()
        tint = "Fig Milk" if relative.startswith("tints/fig-milk/") else "Ember" if relative.startswith("tints/ember/") else "Rosewater"
        report_sources.append((relative, f"Native Illustrator · {tint} · {path.stem}"))
    for name, title in report_sources:
        path = master / name
        if not path.exists() and "/" not in name:
            path = master / "checks" / name
        if path.exists():
            data = _read(path)
            reports.append({"name": name, "title": title, "url": add(path, "reports/" + name),
                            "text": _pretty(data), "exceptions": _exceptions(data)})
    eyes = []
    for name in ("eye-r0.json", "eye-r1.json", "eye-r2.json"):
        path = master / name
        if path.exists():
            data = _read(path)
            payload = data.get("payload") if "payload" in data else data
            incomplete = (not isinstance(payload, dict) or data.get("status") == "incomplete"
                          or data.get("stop_reason") == "max_tokens" or data.get("final_verdict_available") is False)
            if incomplete:
                displayed = {key: data[key] for key in ("status", "stop_reason", "review_state", "final_verdict_available",
                             "partial_verdict_word", "partial_idea_survives", "partial_extraction", "partial_findings", "final_action")
                             if key in data}
                verdict = "incomplete — token limit; no final verdict" if data.get("stop_reason") == "max_tokens" else "incomplete — no final verdict"
            else:
                displayed, verdict = payload, payload.get("verdict", "Recorded")
            archived_inputs = []
            archive = master / "eye-inputs" / path.stem.removeprefix("eye-")
            for item in data.get("images", []):
                retained = archive / Path(item["path"]).name
                if _digest(retained.read_bytes()) != item["sha256"]:
                    raise ValueError("Archived eye input differs from the bytes sent")
                relative = retained.relative_to(master).as_posix()
                archived_inputs.append({"caption": item.get("caption", retained.name), "url": add(retained, relative)})
            eyes.append({"name": name, "url": add(path, "reports/" + name),
                         "text": _pretty(displayed), "verdict": verdict, "incomplete": incomplete,
                         "token_limit": data.get("stop_reason") == "max_tokens",
                         "archived_inputs": archived_inputs})
    eye_warning = None
    if eyes and eyes[-1]["incomplete"]:
        eye_warning = ("Eye not cleared: first " + str(eyes[0]["verdict"]) + ", second incomplete/token limit."
                       if len(eyes) == 2 and eyes[-1]["token_limit"] else "Eye not cleared: latest response is incomplete.")
    elif eyes and str(eyes[-1]["verdict"]).lower() != "pass":
        eye_warning = "Eye not cleared: latest recorded verdict is " + str(eyes[-1]["verdict"]) + "."
    assessment_path = master / "eye-assessment.json"
    assessment = None
    if assessment_path.exists():
        data = _read(assessment_path)
        if data.get("first_eye_sha256") and _digest((master / "eye-r0.json").read_bytes()) != data["first_eye_sha256"]:
            raise ValueError("Eye assessment does not bind the retained first verdict")
        assessment = {"url": add(assessment_path, "reports/eye-assessment.json"), "text": _pretty(data),
                      "authority": data.get("authority"), "first_verdict": data.get("first_verdict_retained_verbatim"),
                      "findings": data.get("findings", []), "repair_scope": data.get("repair_scope", []),
                      "open_at_close": data.get("open_at_close", []), "disputed": data.get("second_look_disputed_finding"),
                      "closing_rule": data.get("rule")}
    proposal = master / "proposals/cap-emboss-proof.png"
    fit_path = master / "carton-fit-report.json"
    fit = _read(fit_path) if fit_path.exists() else {}
    overset = []
    for row in fit.get("overset", []):
        if not (row.get("overflow_lines") or row.get("overset")):
            continue
        legacy_lines = row.get("overflow_lines")
        characters = row.get("overflow_characters")
        if characters is None and "full_characters" in row and "visible_characters" in row:
            characters = row["full_characters"] - row["visible_characters"]
        overset.append({"language": row["language"].upper(), "size_pt": row.get("size_pt", fit.get("floor_pt", 5)),
                        "lines": legacy_lines, "count": len(legacy_lines) if legacy_lines else None,
                        "characters": characters, "visible_count": len(row["visible_lines"]) if "visible_lines" in row else None,
                        "remainder": row.get("hidden_remainder"), "full_copy": row.get("full_copy")})
    record = {
        "schema": SCHEMA, "slug": SLUG, "page_url": PAGE_URL,
        "panels": panels, "downloads": downloads, "reports": reports, "eyes": eyes, "eye_assessment": assessment,
        "leaflets": leaflets,
        "copy_fit": copy_fit,
        "eye_warning": eye_warning,
        "eye_second_incomplete": len(eyes) == 2 and eyes[-1]["incomplete"],
        "eye_completion": eyes[-1] if eyes and eyes[-1]["name"] == "eye-r2.json" else None,
        "fidelity_failures": sum(1 for panel in panels if panel.get("fidelity", {}).get("holds") is False),
        "overset": overset, "overset_line_count": sum(row["count"] or 0 for row in overset),
        "overset_character_count": sum(row["characters"] or 0 for row in overset),
        "overset_retention_pending": fit.get("full_text_native_retention_pending", True),
        "drawing_url": add(master / "drawing.png", "drawing.png"),
        "carton_url": add(master / "carton-flat.png", "carton-flat.png"),
        "label_url": add(master / "label-with-die.png", "label-with-die.png"),
        "proposal_url": add(proposal, "proposals/cap-emboss-proof.png") if proposal.exists() else None,
        "tints": [{"name": name, "files": [row for row in downloads if row["tint"] == name]}
                  for name in ("Rosewater", "Fig Milk", "Ember")],
        "files": files,
    }
    (master / "page-manifest.json").write_text(_pretty(record) + "\n", encoding="utf-8")
    return record


def publish(master=MASTER, pick=PICK):
    """Publish existing bytes and database pins without entering an approval workflow."""
    from apps.core.models import Brand
    from apps.pipeline.models import DesignTask, GeneratedImage, PackagingOutput

    record = build_manifest(master, pick)
    brand = Brand.objects.filter(name__iexact="BBROSE").first()
    if brand is None:
        raise ValueError("BBROSE brand record is missing")
    pins = {}
    for relative, row in record["files"].items():
        data = Path(row["source"]).read_bytes()
        if _digest(data) != row["sha256"]:
            raise ValueError("Source changed during HAYAT publication")
        mt._write(Path(settings.MEDIA_ROOT) / relative, data, row["sha256"])
        pins[relative] = {"sha256": row["sha256"], "bytes": row["bytes"]}
    # Paths on the page are /files URLs. Its displayed reports and evidence are
    # pinned in the same current database output as the downloadable bytes.
    page = {key: value for key, value in record.items() if key != "files"}
    publication = {"schema": mt.RECORD_SCHEMA, "slug": SLUG, "files": pins}
    with transaction.atomic():
        task = DesignTask.objects.filter(**{f"options__{mt.KEY_OPTION}": SLUG}).order_by("pk").first()
        if task is None:
            task = DesignTask.objects.create(
                brand=brand, task_text="HAYAT — read-only master publication", design_target="packaging",
                status="queued", options={mt.KEY_OPTION: SLUG, "spend_held": True, "publication_only": True})
        else:
            task = DesignTask.objects.select_for_update().get(pk=task.pk)
            if not task.options.get("publication_only"):
                raise ValueError("HAYAT key belongs to a workflow task")
        output = task.current_output()
        if output is None:
            image = GeneratedImage.objects.create(
                task=task, direction_name="HAYAT — owner pick D1/A", prompt_used="Existing owner pick; no image call",
                image_file=page["drawing_url"].removeprefix("/files/"), is_approved=False)
            output = PackagingOutput(task=task, approved_image=image)
        output.spec_sheet = {"backend": "hayat_master_read_only", mt.SPEC_KEY: publication, PAGE_KEY: page}
        output.save()
    local = Path(settings.MEDIA_ROOT) / mt.MEDIA_FOLDER / SLUG / mt.RECORD_NAME
    local.write_text(_pretty(publication) + "\n", encoding="utf-8")
    result = {"schema": SCHEMA, "task_id": task.pk, "output_id": output.pk,
              "url": PAGE_URL, "files": len(pins), "ai_files": len(page["downloads"])}
    (Path(master) / "page-publication.json").write_text(_pretty(result) + "\n", encoding="utf-8")
    return result


def load():
    from apps.pipeline.models import DesignTask
    task = DesignTask.objects.filter(**{f"options__{mt.KEY_OPTION}": SLUG}).order_by("pk").first()
    output = task.current_output() if task else None
    record = output.spec_sheet.get(PAGE_KEY) if output and isinstance(output.spec_sheet, dict) else None
    if not isinstance(record, dict) or record.get("schema") != SCHEMA:
        raise ValueError("HAYAT master has not been published")
    return record
