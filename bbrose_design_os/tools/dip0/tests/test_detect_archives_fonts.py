"""Slice 2 — signature/MIME detection, ZIP manifests, font inspection."""
from __future__ import annotations

from tools.dip0 import config as C
from tools.dip0.archives import _is_traversal, build_archive_report, inspect_zip
from tools.dip0.detect import detect, sniff
from tools.dip0.fonts import build_font_report, inspect_font
from tools.dip0.walk import walk_source


def _by_name(records):
    return {r["filename"]: r for r in records}


def _detected(tree):
    recs = walk_source().files
    return [detect(r) for r in recs]


class TestSniff:
    def test_magic_bytes_table(self):
        assert sniff(b"%PDF-1.5") == "pdf"
        assert sniff(b"%!PS-Adobe-3.0") == "postscript"
        assert sniff(b"\xc5\xd0\xd3\xc6xx") == "eps_binary"
        assert sniff(b"8BPS\x00\x01") == "psd"
        assert sniff(bytes.fromhex("89504e470d0a1a0a")) == "png"
        assert sniff(b"\xff\xd8\xff\xe0") == "jpeg"
        assert sniff(b"OTTO....") == "sfnt_otf"
        assert sniff(b"\x00\x01\x00\x00") == "sfnt_ttf"
        assert sniff(b"ttcf....") == "ttc"
        assert sniff(b"PK\x03\x04") == "zip"
        assert sniff(b"MZ\x90\x00") == "mz_exe"
        assert sniff(b"  <svg xmlns=") == "svg_xml"
        assert sniff(b"\x00" * 8) == "unknown"

    def test_avif_vs_mp4_share_ftyp(self):
        assert sniff(b"\x00\x00\x00\x20ftypavif") == "avif"
        assert sniff(b"\x00\x00\x00\x20ftypmp42") == "mp4"


class TestAiRouting:
    def test_pdf_backed_ai_is_supported_via_pymupdf(self, tree):
        r = _by_name(_detected(tree))["LP5526-E.ai"]
        assert r["signature_kind"]["value"] == "pdf"
        assert r["parser_support"] == {"status": "supported", "parser": "pymupdf"}

    def test_legacy_postscript_ai_is_partial_and_warned(self, tree):
        r = _by_name(_detected(tree))["ES3089.ai"]
        assert r["signature_kind"]["value"] == "postscript"
        assert r["parser_support"]["status"] == "partial"
        assert any("legacy_postscript_ai" in w for w in r["warnings"])

    def test_extension_alone_never_decides(self, tree):
        recs = _by_name(_detected(tree))
        # same .ai extension, different parser routing — decided by signature
        assert (recs["LP5526-E.ai"]["parser_support"]["parser"]
                != recs["ES3089.ai"]["parser_support"]["parser"])


class TestMismatch:
    def test_jpeg_bytes_in_png_extension_warns(self, tree):
        r = _by_name(_detected(tree))["mislabelled.png"]
        assert any("signature_ext_mismatch" in w for w in r["warnings"])

    def test_xlsx_zip_container_is_not_a_mismatch(self, tree):
        r = _by_name(_detected(tree))["Q Cargo China Receipt (1).xlsx"]
        assert r["signature_kind"]["value"] == "zip"
        assert not any("signature_ext_mismatch" in w for w in r["warnings"])


class TestProvenanceOnDetection:
    def test_inferred_fields_carry_full_provenance(self, tree):
        r = _by_name(_detected(tree))["LP5526-E.ai"]
        for field in ("signature_kind", "mime_detected"):
            p = r[field]
            assert set(p) == {"value", "source", "evidence", "confidence",
                              "extracted_at", "parser"}
            assert p["evidence"] and 0.0 <= p["confidence"] <= 1.0
            assert p["extracted_at"].endswith("+00:00")


class TestZipManifest:
    def test_traversal_predicate(self):
        assert _is_traversal("../escape.txt")
        assert _is_traversal("/abs/path")
        assert not _is_traversal("inner/art.eps")

    def test_manifest_only_no_extraction(self, tree):
        z = inspect_zip(C.SOURCE_ROOT / "DOWNLOADE 2026" / "bundle.zip")
        assert z["readable"] and z["entry_count"] == 3
        assert z["expanded_bytes"] > 0 and z["manifest_sha256"]
        assert z["nested_archives"] == ["inner/nested.zip"]
        assert z["traversal_entries"] == ["../escape.txt"]
        assert set(z["suspicious"]) >= {"nested_archives", "path_traversal_entries"}
        # nothing was written next to the archive
        assert not (C.SOURCE_ROOT / "DOWNLOADE 2026" / "inner").exists()

    def test_corrupt_archive_flagged_not_fatal(self, tree):
        z = inspect_zip(C.SOURCE_ROOT / "DOWNLOADE 2026" / "broken.zip")
        assert z["corrupt"] is True and z["readable"] is False
        assert "BadZipFile" in z["error"]

    def test_report_separates_exact_and_probable_duplicates(self, tree):
        recs = _detected(tree)
        rep = build_archive_report(recs)
        exact = {p for ps in rep["exact_duplicate_archives"].values() for p in ps}
        probable = {p for ps in
                    rep["probable_duplicate_archives_by_manifest"].values() for p in ps}
        assert any("dupA.zip" in p for p in exact)
        assert any("dupB.zip" in p for p in exact)
        # identical manifest, different bytes → probable, not exact
        assert any("manifestA.zip" in p for p in probable)
        assert not any("manifestA.zip" in p for p in exact)

    def test_archive_records_annotated_and_never_recursed(self, tree):
        recs = _detected(tree)
        build_archive_report(recs)
        bundle = _by_name(recs)["bundle.zip"]
        assert bundle["archive"]["entry_count"] == 3
        assert any(w.startswith("archive_") for w in bundle["warnings"])
        # no inventory record was created for an entry *inside* an archive
        assert not any("nested.zip" in r["relative_path"] for r in recs)


class TestFontInspection:
    def test_real_font_metadata_extracted(self, tree):
        p = C.SOURCE_ROOT / "DOWNLOADE 2026" / "sinkin-sans" / "PilotTest-Regular.ttf"
        info = inspect_font(p, ".ttf")
        assert info["parsed"] is True
        face = info["faces"][0]
        assert face["family"] == "PilotTest"
        assert face["postscript_name"] == "PilotTest-Regular"
        assert face["weight_class"] == 400
        assert face["variable"] is False
        assert "latin" in face["scripts"]

    def test_fstype_recorded_as_evidence_not_permission(self, tree):
        p = C.SOURCE_ROOT / "DOWNLOADE 2026" / "sinkin-sans" / "PilotTest-Regular.ttf"
        face = inspect_font(p, ".ttf")["faces"][0]
        assert face["fs_type_raw"] == 8
        assert face["fs_type_meaning"] == "editable_embedding"
        # the report never converts fsType into an allow flag
        rep = build_font_report(walk_source().files)
        assert "never grant embedding" in rep["policy"]

    def test_license_description_captured_as_evidence(self, tree):
        p = C.SOURCE_ROOT / "DOWNLOADE 2026" / "sinkin-sans" / "PilotTest-Regular.ttf"
        face = inspect_font(p, ".ttf")["faces"][0]
        assert face["license_description"] == "Test licence evidence"

    def test_fon_unsupported_without_crashing(self, tree):
        info = inspect_font(C.SOURCE_ROOT / "DOWNLOADE 2026" / "legacy" / "old.fon", ".fon")
        assert info["parsed"] is False
        assert any("font_unsupported_format" in w for w in info["warnings"])

    def test_corrupt_font_records_warning_not_exception(self, tree):
        info = inspect_font(C.SOURCE_ROOT / "Fonts" / "Brand.otf", ".otf")
        assert info["parsed"] is False
        assert any("font_parse_failed" in w for w in info["warnings"])

    def test_quarantine_branch_counted(self, tree):
        rep = build_font_report(walk_source().files)
        assert rep["quarantine_branch"] == C.FONT_QUARANTINE_DIR
        assert rep["quarantined_count"] == 2   # Arial.ttf + mingliub.ttc
        assert rep["font_file_count"] >= 5

    def test_font_records_never_install_or_expose(self, tree):
        recs = walk_source().files
        build_font_report(recs)
        f = _by_name(recs)["PilotTest-Regular.ttf"]
        assert "font" in f and "installed" not in f


class TestEmptyArchiveRegression:
    """Two 0-byte .zip failed downloads were being reported as 'exact duplicate
    archives' of one another — true of the empty hash, useless to a reviewer."""

    def test_zero_byte_zip_is_empty_not_corrupt(self, tree):
        p = C.SOURCE_ROOT / "DOWNLOADE 2026" / "empty1.zip"
        p.write_bytes(b"")
        z = inspect_zip(p)
        assert z["empty"] is True and z["corrupt"] is False
        assert "failed download" in z["error"]

    def test_empty_archives_excluded_from_exact_duplicate_groups(self, tree):
        for n in ("empty1.zip", "empty2.zip"):
            (C.SOURCE_ROOT / "DOWNLOADE 2026" / n).write_bytes(b"")
        recs = _detected(tree)
        rep = build_archive_report(recs)
        dup_paths = {p for ps in rep["exact_duplicate_archives"].values() for p in ps}
        assert not any("empty" in p for p in dup_paths)
        assert len(rep["empty_failed_downloads"]) == 2
        r = _by_name(recs)["empty1.zip"]
        assert any("archive_empty_failed_download" in w for w in r["warnings"])

    def test_real_duplicate_archives_still_detected(self, tree):
        rep = build_archive_report(_detected(tree))
        assert any(len(ps) == 2 for ps in rep["exact_duplicate_archives"].values())
