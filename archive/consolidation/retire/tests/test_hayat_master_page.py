"""The HAYAT page and the actual Day 14 file door, with private fixture bytes."""
import hashlib
import importlib.util
import json
from pathlib import Path

from PIL import Image
import pytest

from apps.pipeline.services import hayat_master_page as page
from apps.pipeline.services import master_tasks as mt


@pytest.fixture
def sources(tmp_path):
    master, pick = tmp_path / "master", tmp_path / "pick"
    (master / "panels").mkdir(parents=True)
    pick.mkdir()
    dimensions = {name: [20.45, 73.45] for name in page.PANELS}
    dimensions.update(body=[58.5, 42], cap=[58.5, 32], label=[16, 16],
                      back=[20.45, 74.35], top_end=[20, 20.45], bottom_end=[20, 20.45])
    (pick / "crop.json").write_text(json.dumps({"panels": {name: {"mm": mm} for name, mm in dimensions.items()}}))
    for name in page.PANELS:
        Image.new("RGB", (30, 30), "#ede9df").save(pick / f"{name}.png")
        Image.new("RGB", (60, 60), "#eeeade").save(master / "panels" / f"{name}-flat.png")
    for name in ("drawing.png", "carton-flat.png", "label-with-die.png"):
        Image.new("RGB", (50, 50), "white").save(master / name)
    for tint in ("", "tints/fig-milk", "tints/ember"):
        folder = master / tint
        folder.mkdir(parents=True, exist_ok=True)
        for name in page.SURFACES:
            # The door tests the pinned byte identity, not native Illustrator validity.
            (folder / name).write_bytes(b"%PDF-1.7\n% private AI test fixture " + tint.encode() + name.encode())
        Image.new("RGB", (120, 140), "white").save(folder / "leaflet-flat.png")
        Image.new("RGB", (120, 140), "white").save(folder / "leaflet-with-die.png")
        (folder / "leaflet-fit-report.json").write_text(json.dumps({"hidden_characters": 0, "floor_pt": 6,
                                                                  "printed_lines": [{"inside_safe": True}, {"inside_safe": True}]}))
        (folder / "leaflet-fold-check.json").write_text(json.dumps({"status": "PROVISIONAL", "fits_inside_carton": True}))
        (folder / "carton-fit-report.json").write_text(json.dumps({"hidden_characters": 0,
                                                                 "printed_lines": [{"inside_safe": True}]}))
    (master / "eye-r0.json").write_text(json.dumps({"verdict": "design finding listed", "findings": ["Fragments retained"]}))
    (master / "fidelity.json").write_text(json.dumps({"finding": "Below 300", "panels": {"body": {
        "de00_mean": .79, "de00_max": 11.8, "ssim": .99, "effective_ppi_at_trim": 122.7,
        "nominal_ppi_at_trim": 245.5, "ppi_300_met": False,
        "holds": {"de00_mean": True, "de00_max": False, "ssim": True}}}}))
    (master / "readings.json").write_text(json.dumps({"sketch": "Words divide a whole", "master": "Words divide a whole"}))
    (master / "carton-fit-report.json").write_text(json.dumps({"floor_pt": 5, "overset": [
        {"language": "en", "overflow_lines": ["Full warning line", "Full claim line"], "overflow_characters": 32},
        {"language": "es", "overflow_lines": ["Advertencia completa"], "overflow_characters": 20},
        {"language": "ar", "overflow_lines": ["النص الأول", "النص الثاني", "النص الثالث"], "overflow_characters": 35}],
        "full_text_native_retention_pending": False}))
    (master / "repair").mkdir()
    repairs = {}
    for name, share in (("side_left", .067976), ("side_right", .082624)):
        row = {"changed_share_of_panel": share,
               "formerly_protected_paint_pixels_changed_under_new_ruling": 3108,
               "meaning": "Existing paint restored from the original raw sheet under D-R1B-7."}
        for stage in ("before", "after", "mask"):
            row[stage] = f"repair/{name}-{stage}.png"
            Image.new("RGB", (60, 60), "white").save(master / row[stage])
        repairs[name] = row
    (master / "repair/repair.json").write_text(json.dumps({"panels": repairs}))
    cap = {"changed_share": .1486426624, "changed_pixels_2x": 26173,
           "protected_pink_pixels": 24569, "protected_pink_changed_pixels": 0,
           "trace_geometry_changed": False, "trace_sha256_before": "unchanged", "trace_sha256_after": "unchanged",
           "scope": "Construction ghosts and ground border only."}
    for key in ("before", "after", "mask", "proof", "vector_overlay_preview", "protected_pink_mask",
                "protected_pink_difference", "allowed_mask", "blend_alpha"):
        cap[key] = f"repair/cap-{key}.png"
        Image.new("RGB", (60, 40), "white").save(master / cap[key])
    (master / "repair/cap-cleanup.json").write_text(json.dumps(cap))
    return master, pick


@pytest.fixture
def publication(db, settings, sources, client, django_user_model):
    from apps.core.models import Brand
    settings.MEDIA_ROOT = str(sources[0].parent / "media")
    settings.HISTORY_TIER_RECORD = str(sources[0].parent / "no-tiers.jsonl")
    Brand.objects.create(name="BBROSE")
    user = django_user_model.objects.create_superuser(username="hayat-page", email="", password="private-test")
    client.force_login(user)
    result = page.publish(*sources)
    return {"result": result, "record": page.load(), "media": Path(settings.MEDIA_ROOT), "sources": sources}


def _body(response):
    return b"".join(response.streaming_content)


def test_nine_pairs_are_equal_physical_scale_without_approval(publication, client):
    response = client.get(page.PAGE_URL)
    assert response.status_code == 200
    html = response.content.decode()
    assert html.count('data-panel="') == 9
    for panel in publication["record"]["panels"]:
        style = f'width:{panel["width_mm"]}mm;height:{panel["height_mm"]}mm'
        assert html.count(style) >= 2
        assert panel["sketch_url"] in html and panel["master_url"] in html
    assert "Drawing, not a render" in html
    assert "design finding listed" in html and "Fragments retained" in html
    assert "Below 300" in html
    assert "1 of nine panels have unmet fidelity or resolution measurements" in html
    assert "122.70 PPI" in html and "de00_max, 300 PPI" in html
    assert "Flagged proposal" in html and "not applied" in html
    assert "Approve" not in html
    assert "Ẓilāl" not in html and "Golden Hour" not in html
    assert client.post(page.PAGE_URL).status_code == 405


def test_all_fifteen_ai_files_use_day14_database_pins(publication, client):
    record = publication["record"]
    assert len(record["downloads"]) == 15
    assert [len(tint["files"]) for tint in record["tints"]] == [5, 5, 5]
    manifest = json.loads((publication["sources"][0] / "page-manifest.json").read_text())
    for file in record["downloads"]:
        assert file["url"].startswith("/files/" + mt.MEDIA_FOLDER + "/" + page.SLUG + "/")
        response = client.get(file["url"])
        assert response.status_code == 200
        expected = manifest["files"][file["url"].removeprefix("/files/")]["sha256"]
        assert hashlib.sha256(_body(response)).hexdigest() == expected


def test_empty_fidelity_checks_cannot_be_presented_as_pass(publication):
    path = publication["sources"][0] / "fidelity.json"
    path.write_text(json.dumps({"panels": {"body": {"ppi_300_met": True, "holds": {}}}}))
    record = page.build_manifest(*publication["sources"])
    assert record["panels"][0]["fidelity"]["holds"] is False
    assert record["fidelity_failures"] == 1


def test_leaflets_have_explicit_no_sketch_counterparts_and_pinned_flats_and_checks(publication, client):
    html = client.get(page.PAGE_URL).content.decode()
    assert html.count('data-leaflet="') == 3
    assert html.count("no sketch — regulated copy") == 3
    assert "engine remains PROVISIONAL" in html
    assert "actual printed alif 2.42 mm against the 2.5 mm floor" in html
    assert "Carton copy does not fit" in html  # No blanket clearing merely because a leaflet exists.
    assert '<td>Rosewater</td><td>Leaflet</td><td>0</td><td>2</td><td>Yes</td>' in html
    assert len(publication["record"]["copy_fit"]) == 6
    for leaflet in publication["record"]["leaflets"]:
        for field in ("flat_url", "ai_url", "fold_url"):
            assert leaflet[field] in html
            assert client.get(leaflet[field]).status_code == 200
    reports = publication["record"]["reports"]
    assert len([row for row in reports if row["name"].endswith("leaflet-fit-report.json")]) == 3
    assert len([row for row in reports if row["name"].endswith("leaflet-fold-check.json")]) == 3


def test_leaflet_fit_failures_and_missing_measurements_are_never_shown_as_zero_or_safe(publication, client):
    path = publication["sources"][0] / "leaflet-fit-report.json"
    path.write_text(json.dumps({"hidden_characters": 3, "printed_lines": [{"inside_safe": False}]}))
    page.publish(*publication["sources"])
    html = client.get(page.PAGE_URL).content.decode()
    assert '<tr class="hayat-finding"><td>Rosewater</td><td>Leaflet</td><td>3</td><td>1</td><td>No</td>' in html
    path.write_text('{}')
    page.publish(*publication["sources"])
    html = client.get(page.PAGE_URL).content.decode()
    assert '<td>Rosewater</td><td>Leaflet</td><td>Not recorded</td><td>Not recorded</td><td>Not recorded</td>' in html


def test_overset_copy_warning_is_visible_with_per_language_counts(publication, client):
    html = client.get(page.PAGE_URL).content.decode()
    assert "Carton copy does not fit" in html
    assert "6 lines are overset at the 5 pt floor" in html
    assert "These lines do not appear on the printed flat" in html
    assert '<td>EN</td><td>2</td>' in html
    assert '<td>ES</td><td>1</td>' in html
    assert '<td>AR</td><td>3</td>' in html
    assert "Full warning line" in html and "النص الثالث" in html
    assert publication["record"]["overset_line_count"] == 6


def test_native_overset_shows_actual_hidden_characters_without_inventing_line_counts(publication, client):
    master = publication["sources"][0]
    (master / "carton-fit-report.json").write_text(json.dumps({"floor_pt": 5,
        "full_text_native_retention_pending": False, "overset": [
            {"language": "en", "overset": True, "full_characters": 100, "visible_characters": 25,
             "visible_lines": ["one", "two", "three", "four", "five"],
             "hidden_remainder": "Exact remaining warning and claim", "full_copy": "Complete native draft"}]}))
    page.publish(*publication["sources"])
    html = client.get(page.PAGE_URL).content.decode()
    assert "Carton copy does not fit" in html
    assert "75 characters are overset at the 5 pt floor" in html
    assert '<td>EN</td><td>—</td><td>75</td><td>5</td>' in html
    assert "Exact remaining warning and claim" in html
    assert "lines are overset" not in html


def test_missing_native_retention_proof_does_not_claim_full_wording_is_retained(publication, client):
    path = publication["sources"][0] / "carton-fit-report.json"
    report = json.loads(path.read_text())
    del report["full_text_native_retention_pending"]
    path.write_text(json.dumps(report))
    page.publish(*publication["sources"])
    html = client.get(page.PAGE_URL).content.decode()
    assert "retention in native area text is awaiting validation" in html
    assert "full wording is retained as live area text in the native file" not in html


def test_owner_directed_repair_is_disclosed_separately_and_all_proof_images_are_pinned(publication, client):
    html = client.get(page.PAGE_URL).content.decode()
    assert html.count('data-repair="') == 2
    assert "Owner-directed repair · D-R1B-7" in html
    assert "6.8% of panel pixels changed" in html and "8.26% of panel pixels changed" in html
    assert "3108 paint pixels protected by the earlier rule" in html
    assert "The original crops and 2× baseline plates remain unchanged" in html
    assert "fidelity measurements describe the pinned sketch’s exact 2× baseline" in html
    for panel in publication["record"]["panels"]:
        if "repair" not in panel:
            continue
        for key in ("before_url", "after_url", "mask_url"):
            url = panel["repair"][key]
            assert url in html and url.startswith("/files/")
            response = client.get(url)
            assert response.status_code == 200
            assert _body(response).startswith(mt.PNG_MAGIC)


def test_cap_cleanup_is_prominent_with_changed_share_and_all_pinned_evidence(publication, client):
    html = client.get(page.PAGE_URL).content.decode()
    assert html.count('data-cap-cleanup="true"') == 1
    assert "Owner-directed cap cleanup · D-R1B-8" in html
    assert "14.86% of pixels changed (26173 pixels)" in html
    assert "Protected pink: 24569 pixels, 0 changed" in html
    assert "The traced logotype is unchanged" in html
    cap = next(panel for panel in publication["record"]["panels"] if panel["name"] == "cap")["cap_cleanup"]
    assert len(cap["evidence"]) == 9
    for item in cap["evidence"]:
        assert item["url"] in html and item["url"].startswith("/files/")
        response = client.get(item["url"])
        assert response.status_code == 200
        assert _body(response).startswith(mt.PNG_MAGIC)
    report = next(row for row in publication["record"]["reports"] if row["name"] == "repair/cap-cleanup.json")
    assert client.get(report["url"]).status_code == 200


def test_authorized_cap_trace_patch_discloses_failed_global_overlay_and_fringe_changes(publication, client):
    master = publication["sources"][0]
    path = master / "repair/cap-cleanup.json"
    cap = json.loads(path.read_text())
    cap.update(trace_geometry_changed=True, trace_sha256_after="changed", changed_share=.1491708314,
               changed_pixels_2x=26266, protected_pink_changed_pixels=93, construction_fringe_pixels=99,
               protected_pink_changed_outside_explicit_construction_fringe=0,
               independent_strong_pink_changed_pixels=0,
               construction_fringe_mask="repair/cap-construction-fringe-mask.png")
    Image.new("RGB", (60, 40), "white").save(master / cap["construction_fringe_mask"])
    path.write_text(json.dumps(cap))
    patch = {"before_vector": "repair/cap-logotype-before.svg", "after_vector": "repair/cap-logotype-after.svg",
             "mask": "repair/cap-vector-patch-mask.png", "actual_saved_svg_iou_against_independent_original_sketch": .9833734843,
             "iou_0_95_met": True, "changed_share_of_word": .0024464683,
             "trace_to_sketch_max_mm": .1456540377, "sketch_to_trace_max_mm": .4641829877,
             "outside_authorized_notch_boxes_max_mm": .0464182988, "only_two_local_command_ranges_changed": True,
             "all_other_vector_text_byte_identical": True,
             "original_reference_contour_caveat": "The original reference retains the removed guide-induced notches."}
    for key in ("before_vector", "after_vector"):
        (master / patch[key]).write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>')
    Image.new("RGB", (60, 40), "white").save(master / patch["mask"])
    (master / "repair/cap-vector-patch.json").write_text(json.dumps(patch))
    page.publish(*publication["sources"])
    html = client.get(page.PAGE_URL).content.decode()
    assert "14.92% of pixels changed (26266 pixels)" in html
    assert "Protected pink: 24569 pixels, 93 changed" in html
    assert "explicit 99-pixel construction fringe; 0 changed outside it" in html
    assert "Independently selected strong pink: 0 changed pixels" in html
    assert "Only two command ranges changed; all other vector text is byte-identical" in html
    assert "Saved-SVG IoU 0.983373 meets the 0.95 threshold" in html
    assert "Unmet: global 0.3 mm overlay tolerance" in html
    assert "Sketch → trace 0.464183 mm; trace → sketch 0.145654 mm" in html
    assert "The traced logotype is unchanged" not in html
    assert "Trace preservation requires review" not in html
    record = next(panel for panel in page.load()["panels"] if panel["name"] == "cap")["cap_cleanup"]
    assert len(record["evidence"]) == 10
    assert len(record["trace_patch"]["evidence"]) == 3
    for item in record["evidence"] + record["trace_patch"]["evidence"]:
        assert item["url"] in html and client.get(item["url"]).status_code == 200


def eye_evidence(master):
    for round_no, verdict in ((0, "fail"), (1, "pass")):
        folder = master / "eye-inputs" / f"r{round_no}"
        folder.mkdir(parents=True)
        image = folder / "body.png"
        Image.new("RGB", (30, 30), "white" if round_no else "#eeddaa").save(image)
        (master / f"eye-r{round_no}.json").write_text(json.dumps({
            "payload": {"verdict": verdict, "findings": ["Retained raw finding"]},
            "images": [{"path": "comparison/body.png", "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                        "caption": "Exact archived body pair"}]}))
    assessment = {"first_eye_sha256": hashlib.sha256((master / "eye-r0.json").read_bytes()).hexdigest(),
                  "first_verdict_retained_verbatim": "fail", "authority": "Owner D-R1B-3 takes precedence.",
                  "findings": [{"panel": "cap", "action": "Retain both required elements.",
                                "finding": "Reviewer asked to remove mark and tint.", "reason": "The owner requires both."},
                               {"panel": "back", "action": "Restore Arabic batch label.", "finding": "Missing التشغيلة"}],
                  "repair_scope": ["Three cartons only: batch label and front rule."]}
    (master / "eye-assessment.json").write_text(json.dumps(assessment))


def test_eye_scope_assessment_is_prominent_both_raw_verdicts_and_sent_images_stay_pinned(publication, client):
    master = publication["sources"][0]
    eye_evidence(master)
    page.publish(*publication["sources"])
    html = client.get(page.PAGE_URL).content.decode()
    assert 'data-eye-assessment="true"' in html
    assert "First verdict retained: fail" in html
    assert "Retain both required elements" in html and "The owner requires both" in html
    assert "Restore Arabic batch label" in html and "Three cartons only" in html
    assert "eye-r0.json · fail" in html and "eye-r1.json · pass" in html
    record = page.load()
    assert client.get(record["eye_assessment"]["url"]).status_code == 200
    for number, eye in enumerate(record["eyes"]):
        assert len(eye["archived_inputs"]) == 1
        url = eye["archived_inputs"][0]["url"]
        assert f"eye-inputs/r{number}/body.png" in url
        response = client.get(url)
        assert response.status_code == 200
        assert _body(response) == (master / f"eye-inputs/r{number}/body.png").read_bytes()


def test_incomplete_null_payload_is_not_presented_as_a_final_verdict(publication, client):
    master = publication["sources"][0]
    eye_evidence(master)
    path = master / "eye-r1.json"
    record = json.loads(path.read_text())
    record.update(payload=None, status="incomplete", stop_reason="max_tokens", final_verdict_available=False,
                  partial_verdict_word="fail", partial_findings=[{"panel": "cap", "finding": "Cap tint overlaps painted dots."}],
                  prompt="Internal prompt must not replace the verdict")
    path.write_text(json.dumps(record))
    path = master / "eye-assessment.json"
    assessment = json.loads(path.read_text())
    assessment.update(open_at_close=["Partial second-look finding: cap tint overlap."],
                      second_look_disputed_finding={"claim": "Front separator absent.", "evidence": "Saved-file readback contains the rule."},
                      rule="No third look or further creative repair.")
    path.write_text(json.dumps(assessment))
    page.publish(*publication["sources"])
    html = client.get(page.PAGE_URL).content.decode()
    assert "Eye not cleared: first fail, second incomplete/token limit" in html
    assert "No valid final pass is recorded" in html
    assert "Partial findings only — not a completed final verdict" in html
    assert "Cap tint overlaps painted dots" in html
    assert "Saved-file readback contains the rule" in html
    assert "eye-r1.json · pass" not in html
    assert "Internal prompt must not replace the verdict" not in html
    assert page.load()["eyes"][-1]["incomplete"] is True


@pytest.mark.parametrize("verdict", ("pass", "fail"))
def test_completion_eye_is_final_while_failed_and_truncated_history_remain(publication, client, verdict):
    master = publication["sources"][0]
    eye_evidence(master)
    (master / "eye-r1.json").write_text(json.dumps({"payload": None, "status": "incomplete",
        "stop_reason": "max_tokens", "final_verdict_available": False,
        "partial_findings": [{"finding": "Historical partial finding"}]}))
    folder = master / "eye-inputs/r2"
    folder.mkdir()
    image = folder / "comparison.png"
    Image.new("RGB", (40, 80), "white").save(image)
    (master / "eye-r2.json").write_text(json.dumps({"status": "completed", "final_verdict_available": True,
        "payload": {"verdict": verdict, "findings": [{"finding": "Final completion finding"}]},
        "images": [{"path": "comparison.png", "sha256": hashlib.sha256(image.read_bytes()).hexdigest()}]}))
    page.publish(*publication["sources"])
    html = client.get(page.PAGE_URL).content.decode()
    assert f"Round 1C completion eye: {verdict}" in html
    assert "eye-r0.json · fail" in html
    assert "Historical partial finding" in html and "Partial findings only" in html
    assert "Final completion finding" in html
    assert ("No valid final pass is recorded" in html) == (verdict == "fail")
    assert "first fail, second incomplete/token limit" not in html
    record = page.load()
    assert len(record["eyes"]) == 3 and record["eye_completion"]["verdict"] == verdict
    assert client.get(record["eyes"][-1]["archived_inputs"][0]["url"]).status_code == 200


@pytest.mark.parametrize("corruption", ("archive", "assessment"))
def test_stale_eye_input_or_scope_assessment_cannot_be_published(sources, corruption):
    master, pick = sources
    eye_evidence(master)
    if corruption == "archive":
        (master / "eye-inputs/r0/body.png").write_bytes(b"changed after the eye")
    else:
        (master / "eye-r0.json").write_text(json.dumps({"payload": {"verdict": "changed"}}))
    with pytest.raises(ValueError, match="Archived eye input|Eye assessment"):
        page.build_manifest(master, pick)


def test_one_byte_mismatch_409_local_pin_cannot_authorize_then_restore(publication, client):
    file = publication["record"]["downloads"][0]
    relative = file["url"].removeprefix("/files/")
    target = publication["media"] / relative
    original = target.read_bytes()
    target.write_bytes(original + b"\nchanged")
    adjacent = publication["media"] / mt.MEDIA_FOLDER / page.SLUG / mt.RECORD_NAME
    local = json.loads(adjacent.read_text())
    local["files"][relative]["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    adjacent.write_text(json.dumps(local))
    response = client.get(file["url"])
    assert response.status_code == 409
    assert b"SHA256 mismatch" in response.content
    target.write_bytes(original)
    response = client.get(file["url"])
    assert response.status_code == 200
    assert _body(response) == original


def test_publication_has_no_workflow_approval_or_additional_ai(publication):
    from apps.pipeline.models import DesignTask, GeneratedImage
    task = DesignTask.objects.get(pk=publication["result"]["task_id"])
    assert task.status == "queued" and task.options["publication_only"]
    assert task.options["spend_held"]
    assert not GeneratedImage.objects.get(task=task).is_approved
    assert len(list(publication["media"].rglob("*.ai"))) == 15
    assert not list(publication["media"].rglob("*.pdf"))


def test_republish_updates_database_page_without_workflow_transition(publication):
    first = publication["result"]
    second = page.publish(*publication["sources"])
    assert first["task_id"] == second["task_id"]
    assert first["output_id"] == second["output_id"]


def test_master_requires_authenticated_page_and_file_requests(publication, client):
    client.logout()
    assert client.get(page.PAGE_URL).status_code == 302
    assert client.get(publication["record"]["downloads"][0]["url"]).status_code == 302


def test_missing_surface_and_source_escape_are_refused(sources):
    master, pick = sources
    body = master / "body-wrap.ai"
    body.unlink()
    with pytest.raises(ValueError, match="Missing master surface"):
        page.build_manifest(master, pick)
    external = master.parent / "outside.ai"
    external.write_bytes(b"%PDF-1.7\n")
    body.symlink_to(external)
    with pytest.raises(ValueError, match="outside the pick and master"):
        page.build_manifest(master, pick)


def test_close_suite_freezes_input_membership_and_detects_mutation_without_absorbing_outputs(tmp_path):
    runner = page.REPO / "docs/rounds/r1-balm/master/closeout/evidence/run_full_suite.py"
    spec = importlib.util.spec_from_file_location("hayat_close_runner", runner)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    master = tmp_path / "docs/rounds/r1-balm/master"
    master.mkdir(parents=True)
    artifact = master / "leaflet.ai"
    artifact.write_bytes(b"frozen design")
    baseline = master / "evidence/close/entry-engine-geometry.json"
    baseline.parent.mkdir(parents=True)
    baseline.write_text('{"safe_mm":[1.5,1.5,16.5,69.5]}')
    verification = baseline.parent / "final-verification.json"
    verification.write_text('{"holds":true}')
    for output in ("verification-independent/measurements.json", "closeout/evidence/result.json", "eye-r2.json",
                   "eye-inputs/r2/leaflet.png", "calls/eye-r2.response.json", "spend-close.json", "page-manifest.json"):
        path = master / output
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("authorized output")
    frozen = module.design_inputs(tmp_path)
    assert set(frozen) == {path.relative_to(tmp_path).as_posix() for path in (artifact, baseline, verification)}
    (master / "eye-r2.json").write_text("completed after source freeze")
    (master / "new-publication-output.json").write_text("new file is not retroactively a run input")
    assert module.changed_frozen_inputs(frozen, tmp_path) == []
    artifact.write_bytes(b"mutated design")
    assert module.changed_frozen_inputs(frozen, tmp_path) == [artifact.relative_to(tmp_path).as_posix()]
    artifact.unlink()
    assert module.changed_frozen_inputs(frozen, tmp_path) == [artifact.relative_to(tmp_path).as_posix()]
    baseline.write_text('{"safe_mm":[0,0,18,71]}')
    verification.write_text('{"holds":false}')
    assert set(module.changed_frozen_inputs(frozen, tmp_path)) == set(frozen)
