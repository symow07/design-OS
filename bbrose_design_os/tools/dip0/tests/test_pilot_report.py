"""Slice 4 — pilot selection, report writing, reconciliation, end-to-end run."""
from __future__ import annotations

import json

from tools.dip0 import archives as A
from tools.dip0 import classify as CL
from tools.dip0 import config as C
from tools.dip0 import fonts as F
from tools.dip0 import integrity as I
from tools.dip0 import report as R
from tools.dip0.detect import detect
from tools.dip0.pilot import build_pilot, select_historical
from tools.dip0.walk import group_duplicates, walk_source


def _pipeline(tree):
    res = walk_source()
    for r in res.files:
        detect(r)
    arch = A.build_archive_report(res.files)
    fnt = F.build_font_report(res.files)
    CL.annotate(res.files)
    dupes = group_duplicates(res.files)
    for r in res.files:
        r["duplicate_group"] = dupes["index"].get(r["relative_path"])
    return res, arch, fnt, dupes


class TestPilot:
    def test_deterministic(self, tree):
        res, *_ = _pipeline(tree)
        a = build_pilot(res.files)
        b = build_pilot(res.files)
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)

    def test_paths_are_exact_and_exist(self, tree):
        res, *_ = _pipeline(tree)
        p = build_pilot(res.files)
        picks = [x["relative_path"] for x in p["historical_designs"]]
        picks += [x["relative_path"] for x in p["reusable_assets"]]
        picks += [x["relative_path"] for x in p["backgrounds"]]
        picks += [x["relative_path"] for x in p["fonts"]["download_folder_fonts"]]
        picks += [x["relative_path"] for x in p["brand_assets"]["bbrose_candidates"]]
        assert picks
        for rel in picks:
            assert rel.startswith("materials/")
            assert (C.REPO_ROOT / rel).exists()

    def test_poor_filename_hygiene_selected(self, tree):
        res, *_ = _pipeline(tree)
        h = select_historical(res.files)
        assert any("poor_filename_hygiene" in c["reasons"] for c in h)
        assert any(c["relative_path"].endswith("(2).ai") for c in h)

    def test_legacy_postscript_ai_selected(self, tree):
        res, *_ = _pipeline(tree)
        h = select_historical(res.files)
        assert any("legacy_postscript_ai" in c["reasons"] for c in h)

    def test_brand_and_third_party_both_present_and_separated(self, tree):
        res, *_ = _pipeline(tree)
        b = build_pilot(res.files)["brand_assets"]
        assert any("BBROSE" in e["relative_path"] for e in b["bbrose_candidates"])
        third = {e["relative_path"].split("/")[-1] for e in b["unconfirmed_third_party"]}
        assert third == {"ATC LOGO.ai", "JOJIA LOGO.ai"}
        assert all(e["ownership_status"] == "UNCONFIRMED_THIRD_PARTY"
                   for e in b["unconfirmed_third_party"])

    def test_fonts_pair_licensed_with_quarantined_for_contrast(self, tree):
        res, *_ = _pipeline(tree)
        f = build_pilot(res.files)["fonts"]
        assert f["download_folder_fonts"] and f["suspected_system_fonts"]
        # neither set is cleared
        for e in f["download_folder_fonts"] + f["suspected_system_fonts"]:
            assert e["license_status"] == "UNVERIFIED"

    def test_requirements_block_reports_truthfully(self, tree):
        res, *_ = _pipeline(tree)
        p = build_pilot(res.files)
        # the synthetic tree has no CJK/stand designs → must report False, not lie
        assert p["requirements_met"]["chinese_annotations"] is False
        assert p["all_requirements_met"] is False
        assert p["requirements_met"]["poor_filename_hygiene"] is True
        assert p["requirements_met"]["official_brand_candidate"] is True

    def test_mixed_raster_caveat_declared(self, tree):
        res, *_ = _pipeline(tree)
        p = build_pilot(res.files)
        assert any("SIZE PROXY" in c for c in p["caveats"])


class TestReports:
    def test_inventory_written_with_traceable_paths(self, tree):
        res, arch, fnt, dupes = _pipeline(tree)
        R.write_inventory(res.files)
        rows = [json.loads(line) for line in
                (C.OUT_INVENTORY / "inventory.jsonl").read_text().splitlines()]
        assert len(rows) == len(res.files)
        assert all(r["relative_path"].startswith("materials/") for r in rows)
        assert (C.OUT_INVENTORY / "inventory.csv").exists()

    def test_nothing_written_under_materials(self, tree):
        res, arch, fnt, dupes = _pipeline(tree)
        before = I.snapshot()
        pilot = build_pilot(res.files)
        recon = R.reconcile(res.files, res, dupes, arch, fnt, before,
                            I.compare(before, I.snapshot()),
                            I.verify_hashes(res.files, sample=None),
                            I.no_output_under_source())
        R.write_all(res.files, res, dupes, arch, fnt, pilot, recon,
                    {"matches": True, "differences": {}})
        after = I.compare(before, I.snapshot())
        assert after["unchanged"] is True
        assert not list(C.SOURCE_ROOT.rglob("inventory.jsonl"))

    def test_reconciliation_totals_add_up(self, tree):
        res, arch, fnt, dupes = _pipeline(tree)
        before = I.snapshot()
        recon = R.reconcile(res.files, res, dupes, arch, fnt, before,
                            I.compare(before, I.snapshot()),
                            I.verify_hashes(res.files, sample=5),
                            I.no_output_under_source())
        assert recon["indexed_files"] == len(res.files)
        assert sum(recon["counts_by_category"].values()) == len(res.files)
        assert sum(recon["counts_by_extension"].values()) == len(res.files)
        assert sum(recon["counts_by_parser_support"].values()) == len(res.files)
        assert recon["excluded_junk"] == 3

    def test_divergence_reported_not_hidden(self, tree):
        recon = {"indexed_files": 10, "duplicates": {"groups": 2}}
        d = R.compare_to_pre_audit(recon, {"indexed_files": 12,
                                           "duplicates.groups": 2})
        assert d["matches"] is False
        assert d["differences"]["indexed_files"]["actual"] == 10
        assert d["differences"]["indexed_files"]["delta"] == -2

    def test_summary_md_declares_taxonomy_additions(self, tree):
        res, arch, fnt, dupes = _pipeline(tree)
        before = I.snapshot()
        pilot = build_pilot(res.files)
        recon = R.reconcile(res.files, res, dupes, arch, fnt, before,
                            I.compare(before, I.snapshot()),
                            I.verify_hashes(res.files, sample=5),
                            I.no_output_under_source())
        md = R.write_summary_md(recon, pilot, arch, fnt, dupes,
                                {"matches": True, "differences": {}}).read_text()
        assert "ARCHIVE" in md and "LICENSE_EVIDENCE" in md
        assert "read-only" in md

    def test_duplicate_group_id_on_records(self, tree):
        res, *_ = _pipeline(tree)
        dup = [r for r in res.files if r.get("duplicate_group")]
        assert dup and all(r["duplicate_group"].startswith("dup-") for r in dup)


class TestRunnerSafety:
    def test_write_json_refuses_source_root(self, tree):
        import pytest
        with pytest.raises(RuntimeError):
            R._write_json(C.SOURCE_ROOT / "evil.json", {"x": 1})


class TestSerializationRobustness:
    """Regression: OS/2.achVendID came back as raw bytes for a malformed font in
    Fonts/3333, aborting the whole 7,586-file run at write time."""

    def test_safe_str_coerces_bytes_vendor_id(self):
        from tools.dip0.fonts import _safe_str
        assert _safe_str(b"Mj_\xae") == "Mj_\xae"
        assert _safe_str(b"ADBE\x00") == "ADBE"
        assert _safe_str(None) is None
        assert _safe_str("  ADBE ") == "ADBE"
        assert _safe_str(b"\x00\x00") is None

    def test_every_record_is_json_serialisable(self, tree):
        res, *_ = _pipeline(tree)
        from tools.dip0.pilot import build_pilot
        for r in res.files:
            json.dumps(r, ensure_ascii=False, default=R.json_default)
        json.dumps(build_pilot(res.files), default=R.json_default)

    def test_json_default_still_raises_on_unexpected_types(self):
        import pytest
        assert R.json_default(b"ab") == "ab"
        assert R.json_default({"b", "a"}) == ["a", "b"]
        with pytest.raises(TypeError):
            R.json_default(object())


class TestPilotSizing:
    """The real library has 9 CJK-named and 6 poor-hygiene designs; without a
    per-reason cap the pilot ballooned to 24 against a 10-15 requirement."""

    def test_per_reason_cap_bounds_the_pilot(self):
        from tools.dip0.pilot import PER_REASON_CAP, select_historical
        # 30 CJK-named historical designs must not produce a 30-file pilot
        recs = [{"relative_path": f"materials/historical AI production designs/唇彩{i}.ai",
                 "filename": f"唇彩{i}.ai", "extension": ".ai",
                 "size_bytes": 1_000_000 * (i + 1),
                 "category": {"value": "HISTORICAL_DESIGN"},
                 "signature_kind": {"value": "pdf"}} for i in range(30)]
        h = select_historical(recs, target=14)
        assert len(h) <= 14
        cjk = [c for c in h if "chinese_annotations" in c["reasons"]]
        assert 1 <= len(cjk) <= PER_REASON_CAP

    def test_trim_keeps_sole_exemplar_of_each_requirement(self, tree):
        res, *_ = _pipeline(tree)
        from tools.dip0.pilot import select_historical
        h = select_historical(res.files, target=2)   # brutal target
        reasons = {x for c in h for x in c["reasons"]}
        # the only postscript .ai and the only poor-name .ai must survive
        assert "legacy_postscript_ai" in reasons
        assert "poor_filename_hygiene" in reasons

    def test_exemplars_span_the_size_range(self):
        from tools.dip0.pilot import _spread
        pool = [{"size_bytes": s, "relative_path": f"p{s}"} for s in (5, 50, 500)]
        picked = _spread(pool, 2)
        assert [p["size_bytes"] for p in picked] == [5, 500]   # smallest + largest


class TestOutOfScopeReviewSheet:
    def test_sheet_lists_every_excluded_file_with_disposition(self, tree):
        res, *_ = _pipeline(tree)
        p = R.write_out_of_scope_review(res.files)
        import csv as _csv
        rows = list(_csv.DictReader(p.open(encoding="utf-8")))
        oos = [r for r in res.files if r["category"]["value"] == "OUT_OF_SCOPE"]
        assert len(rows) == len(oos) and rows
        assert set(rows[0]) == {"relative_path", "filename", "detected_type",
                                "size_bytes", "exclusion_rule", "evidence",
                                "confidence", "recommended_disposition",
                                "human_confirmed_disposition"}

    def test_human_field_is_never_machine_written(self, tree):
        res, *_ = _pipeline(tree)
        import csv as _csv
        rows = list(_csv.DictReader(
            R.write_out_of_scope_review(res.files).open(encoding="utf-8")))
        assert all(r["human_confirmed_disposition"] == "" for r in rows)

    def test_disposition_depends_on_confidence(self, tree):
        res, *_ = _pipeline(tree)
        import csv as _csv
        rows = {r["filename"]: r for r in _csv.DictReader(
            R.write_out_of_scope_review(res.files).open(encoding="utf-8"))}
        # .mp4 / .xlsx are format-driven (0.85) → permanent
        assert rows["Weixin Videos2025-11-03.mp4"]["recommended_disposition"] \
            == "exclude_permanently"
        # apparel mockup is rule-inferred (0.7) → wants a human
        assert rows["shirt.psd"]["recommended_disposition"] \
            == "human_confirm_exclusion"

    def test_excluded_files_are_never_touched(self, tree):
        before = I.snapshot()
        res, *_ = _pipeline(tree)
        R.write_out_of_scope_review(res.files)
        assert I.compare(before, I.snapshot())["unchanged"] is True


class TestMilestoneDocs:
    def test_only_summary_and_pilot_are_committed(self, tree):
        res, arch, fnt, dupes = _pipeline(tree)
        before = I.snapshot()
        pilot = build_pilot(res.files)
        recon = R.reconcile(res.files, res, dupes, arch, fnt, before,
                            I.compare(before, I.snapshot()),
                            I.verify_hashes(res.files, sample=5),
                            I.no_output_under_source())
        md = R.write_summary_md(recon, pilot, arch, fnt, dupes,
                                {"matches": True, "differences": {}})
        d = R.write_milestone_docs(recon, pilot, md)
        docs = C.REPO_ROOT / "docs" / "design_intelligence" / "dip0a"
        assert {p.name for p in docs.iterdir()} == {"summary.md",
                                                    "pilot_manifest.json"}
        assert "inventory.jsonl" not in {p.name for p in docs.iterdir()}
        assert str(docs) == d["docs_dir"]

    def test_summary_records_source_of_truth_and_the_zip_correction(self, tree):
        res, arch, fnt, dupes = _pipeline(tree)
        before = I.snapshot()
        pilot = build_pilot(res.files)
        recon = R.reconcile(res.files, res, dupes, arch, fnt, before,
                            I.compare(before, I.snapshot()),
                            I.verify_hashes(res.files, sample=5),
                            I.no_output_under_source())
        md = R.write_summary_md(recon, pilot, arch, fnt, dupes,
                                {"matches": True, "differences": {}}).read_text()
        assert "Source-of-truth counts" in md
        assert "double-counting" in md and "25.10.15.zip" in md
        assert "COLOR_PALETTE" in md and "SUPPORTING_METADATA" in md
