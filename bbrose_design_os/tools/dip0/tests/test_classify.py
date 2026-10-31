"""Slice 3 — classification, licence evidence, ownership, quarantine, provenance."""
from __future__ import annotations

from tools.dip0 import config as C
from tools.dip0.classify import annotate, classify, is_license_evidence
from tools.dip0.detect import detect
from tools.dip0.fonts import build_font_report
from tools.dip0.walk import walk_source


def _annotated(tree):
    recs = [detect(r) for r in walk_source().files]
    build_font_report(recs)
    return {r["filename"]: r for r in annotate(recs)}


class TestCategories:
    def test_historical_ai_high_confidence(self, tree):
        r = _annotated(tree)["LP5526-E.ai"]
        assert r["category"]["value"] == "HISTORICAL_DESIGN"
        assert r["category"]["confidence"] >= 0.9

    def test_scattered_ai_never_becomes_historical(self, tree):
        # LOGO6.ai is an .ai OUTSIDE the historical branch → must not be merged in
        r = _annotated(tree)["LOGO6.ai"]
        assert r["category"]["value"] != "HISTORICAL_DESIGN"
        assert r["category"]["value"] == "LOGO"

    def test_archive_is_its_own_category_not_unknown(self, tree):
        r = _annotated(tree)["bundle.zip"]
        assert r["category"]["value"] == "ARCHIVE"

    def test_license_file_is_evidence_category(self, tree):
        r = _annotated(tree)["License premium.txt"]
        assert r["category"]["value"] == "LICENSE_EVIDENCE"

    def test_out_of_scope_vs_unknown_are_distinct(self, tree):
        a = _annotated(tree)
        assert a["Q Cargo China Receipt (1).xlsx"]["category"]["value"] == "OUT_OF_SCOPE"
        assert a["Weixin Videos2025-11-03.mp4"]["category"]["value"] == "OUT_OF_SCOPE"
        # .fon is understood-but-unparseable; it is NOT out of scope
        assert a["old.fon"]["category"]["value"] == "FONT"

    def test_folder_hints_are_capped_confidence(self, tree):
        r = _annotated(tree)["bg.jpg"]
        assert r["category"]["value"] == "BACKGROUND"
        assert r["category"]["confidence"] <= 0.6      # hint, never truth
        assert r["category"]["source"] == "folder_hint"

    def test_unrelated_mockup_excluded_but_packaging_mockup_kept(self, tree):
        assert classify({"relative_path": "materials/x/apparel-mockup/shirt.psd",
                         "filename": "shirt.psd", "extension": ".psd",
                         "warnings": []})["value"] == "OUT_OF_SCOPE"
        keep = classify({"relative_path": "materials/x/paper-bag-mockup/bag.psd",
                         "filename": "bag.psd", "extension": ".psd",
                         "warnings": []})
        assert keep["value"] != "OUT_OF_SCOPE"        # packaging-relevant


class TestOwnership:
    def test_folder_never_establishes_ownership(self, tree):
        a = _annotated(tree)
        # all four sit in the SAME office folder, yet get different verdicts
        assert a["BBROSE.pdf"]["ownership_status"]["value"] == "LIKELY_BBROSE_UNCONFIRMED"
        assert a["ATC LOGO.ai"]["ownership_status"]["value"] == "UNCONFIRMED_THIRD_PARTY"
        assert a["JOJIA LOGO.ai"]["ownership_status"]["value"] == "UNCONFIRMED_THIRD_PARTY"
        for r in a.values():
            assert r["ownership_status"]["source"] != "folder"

    def test_third_party_logos_excluded_from_brand_retrieval(self, tree):
        a = _annotated(tree)
        assert a["ATC LOGO.ai"]["excluded_from_brand_retrieval"] is True
        assert a["JOJIA LOGO.ai"]["excluded_from_brand_retrieval"] is True
        assert "excluded_from_brand_retrieval" not in a["BBROSE.pdf"]

    def test_brand_candidates_still_require_review(self, tree):
        r = _annotated(tree)["BBROSE.pdf"]
        assert r["review_required"] is True
        assert "ownership_unconfirmed" in r["review_reasons"]
        assert r["ownership_status"]["confidence"] < 1.0


class TestLicenceEvidence:
    def test_predicate(self):
        assert is_license_evidence("License premium.txt", ".txt")
        assert is_license_evidence("readme.html", ".html")
        assert is_license_evidence("LicenseInfo.url", ".url")
        assert not is_license_evidence("rose.eps", ".eps")

    def test_same_dir_association(self, tree):
        r = _annotated(tree)["rose.eps"]
        assert r["license_evidence"]
        assert r["license_evidence"][0]["scope"] == "same_dir"
        assert r["license_evidence"][0]["filename"] == "License premium.txt"

    def test_evidence_never_grants_rights(self, tree):
        r = _annotated(tree)["rose.eps"]
        assert r["license_status"]["value"] == "PENDING_HUMAN_CONFIRMATION"
        assert r["license_status"]["confidence"] == 0.0   # evidence ≠ proof

    def test_asset_without_licence_is_unverified(self, tree):
        r = _annotated(tree)["LP5526-E.ai"]
        assert r["license_evidence"] == []
        assert r["license_status"]["value"] == "UNVERIFIED"

    def test_nearest_ancestor_wins(self, tree):
        # font sits beside readme.html in sinkin-sans/
        r = _annotated(tree)["PilotTest-Regular.ttf"]
        assert any(e["filename"] == "readme.html" for e in r["license_evidence"])


class TestFontQuarantine:
    def test_3333_branch_quarantined_with_all_flags_false(self, tree):
        r = _annotated(tree)["Arial.ttf"]
        p = r["font_posture"]
        assert p["quarantined"] is True
        assert p["source_classification"] == "SUSPECTED_SYSTEM_FONT_DUMP"
        assert p["license_status"] == "UNVERIFIED"
        assert p["review_required"] is True
        assert p["automatic_use_allowed"] is False
        assert p["embedding_allowed"] is False
        assert p["redistribution_allowed"] is False

    def test_licensed_download_font_still_unverified(self, tree):
        # readme.html evidence must NOT promote the font to licensed
        r = _annotated(tree)["PilotTest-Regular.ttf"]
        assert r["font_posture"]["quarantined"] is False
        assert r["font_posture"]["license_status"] == "UNVERIFIED"
        assert r["font_posture"]["embedding_allowed"] is False
        assert r["license_status"]["value"] == "UNVERIFIED"
        assert r["review_required"] is True

    def test_every_font_requires_review(self, tree):
        a = _annotated(tree)
        for fn in ("Arial.ttf", "mingliub.ttc", "Brand.otf", "PilotTest-Regular.ttf"):
            assert "font_license_unverified" in a[fn]["review_reasons"]


class TestProvenanceAndHumanSeparation:
    def test_every_inferred_field_has_provenance(self, tree):
        r = _annotated(tree)["LP5526-E.ai"]
        for field in ("category", "ownership_status", "license_status",
                      "signature_kind", "mime_detected"):
            p = r[field]
            assert set(p) == {"value", "source", "evidence", "confidence",
                              "extracted_at", "parser"}
            assert p["source"] and p["extracted_at"]

    def test_human_block_present_and_untouched_by_machine(self, tree):
        r = _annotated(tree)["LP5526-E.ai"]
        h = r["human_confirmed"]
        assert h["category"] is None and h["license_status"] is None
        assert h["ownership_status"] is None and h["reviewed_by"] is None

    def test_machine_and_human_values_never_share_a_key(self, tree):
        r = _annotated(tree)["BBROSE.pdf"]
        assert r["category"]["value"] == "BRAND_MASTER"    # machine
        assert r["human_confirmed"]["category"] is None    # human, separate

    def test_unknown_records_zero_confidence(self, tree):
        c = classify({"relative_path": "materials/x/blob.qqq", "filename": "blob.qqq",
                      "extension": ".qqq", "warnings": []})
        assert c["value"] == "UNKNOWN" and c["confidence"] == 0.0


class TestRealLibraryRegressions:
    """Bugs found by running slice 5 against the real 7,586-file library."""

    def test_ofl_and_apache_and_eula_are_strong_licence_evidence(self):
        from tools.dip0.classify import license_evidence_strength as s
        for fn in ("OFL.txt", "Apache License.txt", "KGFonts-TOU.txt",
                   "1001fonts-drink-south-demo-version-eula.txt",
                   "Back to Black - Terms Of Use.URL", "License premium.txt",
                   "DEMO - PERSONAL USE ONLY.txt"):
            assert s(fn, ".txt" if fn.endswith(".txt") else ".url") == "strong", fn

    def test_readme_and_notes_are_weak_evidence_not_unknown(self):
        from tools.dip0.classify import license_evidence_strength as s
        for fn in ("readme.html", "Read Me.txt", "More Info.txt",
                   "Important note (DEMO FONT).txt", "Fonts.txt"):
            assert s(fn, ".txt" if fn.endswith(".txt") else ".html") == "weak", fn

    def test_non_evidence_extensions_never_match(self):
        from tools.dip0.classify import license_evidence_strength as s
        assert s("rose.eps", ".eps") is None
        assert s("license-plate.ai", ".ai") is None   # design asset, not evidence

    def test_ofl_attaches_to_the_font_beside_it(self, tree):
        (C.SOURCE_ROOT / "DOWNLOADE 2026" / "sinkin-sans" / "OFL.txt").write_text("ofl")
        a = _annotated(tree)
        f = a["PilotTest-Regular.ttf"]
        assert any(e["filename"] == "OFL.txt" for e in f["license_evidence"])
        assert f["license_evidence_strength"] == "strong"
        # …and STILL does not grant any right
        assert f["font_posture"]["embedding_allowed"] is False
        assert f["license_status"]["value"] == "UNVERIFIED"

    def test_brand_named_png_is_a_render_not_a_brand_master(self):
        r = classify({"relative_path": "materials/x/Radiant Beauty with BBROSE Gloss.png",
                      "filename": "Radiant Beauty with BBROSE Gloss.png",
                      "extension": ".png", "warnings": []})
        assert r["value"] == "PRODUCT_REFERENCE"
        assert any("not a vector master" in e for e in r["evidence"])

    def test_brand_vector_master_still_brand_master(self):
        assert classify({"relative_path": "materials/x/BBROSE.pdf",
                         "filename": "BBROSE.pdf", "extension": ".pdf",
                         "warnings": []})["value"] == "BRAND_MASTER"
        assert classify({"relative_path": "materials/x/LOGO6.ai",
                         "filename": "LOGO6.ai", "extension": ".ai",
                         "warnings": []})["value"] == "LOGO"

    def test_brand_named_render_keeps_unconfirmed_ownership(self, tree):
        from tools.dip0.classify import ownership
        o = ownership({"filename": "Radiant Beauty with BBROSE Gloss.png"})
        assert o["value"] == "LIKELY_BBROSE_UNCONFIRMED"


class TestApprovedTaxonomyAmendments:
    """User decisions, 2026-07-10: COLOR_PALETTE, SUPPORTING_METADATA, and the
    knowledge-class / retrieval posture for non-knowledge categories."""

    def _c(self, rel, fn, ext):
        return classify({"relative_path": rel, "filename": fn,
                         "extension": ext, "warnings": []})

    def test_ase_is_color_palette_not_unknown(self):
        c = self._c("materials/x/Pantone_3519C.ase", "Pantone_3519C.ase", ".ase")
        assert c["value"] == "COLOR_PALETTE"
        assert any("never confirms an official BBROSE palette" in e
                   for e in c["evidence"])

    def test_palette_extension_beats_folder_hint(self):
        # an .ase inside a "*-background" folder must not become BACKGROUND
        c = self._c("materials/x/glowing-particles-background/p.ase", "p.ase", ".ase")
        assert c["value"] == "COLOR_PALETTE"

    def test_palette_parser_partial_and_gated(self):
        assert C.parser_support(".ase") == "partial"
        p = C.retrieval_posture("COLOR_PALETTE")
        assert p["knowledge_class"] is True
        assert p["retrieval_allowed"] is False
        assert p["automatic_use_allowed"] is False
        assert "DIP-0C/DIP-1" in p["reason"]

    def test_palette_requires_review_and_no_auto_ownership(self):
        from tools.dip0.classify import needs_review, ownership
        rec = {"relative_path": "materials/x/Pantone_3519C.ase",
               "filename": "Pantone_3519C.ase", "extension": ".ase",
               "warnings": [], "parser_support": {"status": "partial"}}
        rec["category"] = classify(rec)
        req, reasons = needs_review(rec)
        assert req and "palette_unparsed_and_ownership_unconfirmed" in reasons
        assert ownership(rec)["value"] == "UNKNOWN"   # filename proves nothing

    def test_font_metadata_xml_is_supporting_metadata(self, tree):
        (C.SOURCE_ROOT / "Fonts" / "fms_metadata.xml").write_text("<x/>")
        a = _annotated(tree)
        r = a["fms_metadata.xml"]
        assert r["category"]["value"] == "SUPPORTING_METADATA"
        assert r["category_subtype"] == "FONT_METADATA"
        assert r["associated_branch"] == C.FONTS_DIR
        assert r["posture"]["knowledge_class"] is False
        assert r["posture"]["excluded_from_retrieval_by_rule"] is True

    def test_unknown_reserved_for_genuinely_unidentified(self):
        assert self._c("materials/x/blob.qqq", "blob.qqq", ".qqq")["value"] == "UNKNOWN"

    def test_archive_is_not_a_knowledge_class(self, tree):
        r = _annotated(tree)["bundle.zip"]
        p = r["posture"]
        assert p["knowledge_class"] is False
        assert p["excluded_from_retrieval_by_rule"] is True
        assert "proves nothing about the licence" in p["reason"]
        assert "archive_contents_unverified" in r["review_reasons"]

    def test_license_evidence_is_not_a_knowledge_class(self, tree):
        p = _annotated(tree)["License premium.txt"]["posture"]
        assert p["knowledge_class"] is False
        assert p["retrieval_allowed"] is False

    def test_out_of_scope_and_unknown_excluded_by_rule(self):
        for cat in ("OUT_OF_SCOPE", "UNKNOWN", "ARCHIVE", "LICENSE_EVIDENCE",
                    "SUPPORTING_METADATA"):
            p = C.retrieval_posture(cat)
            assert p["knowledge_class"] is False
            assert p["excluded_from_retrieval_by_rule"] is True

    def test_design_knowledge_classes_are_knowledge_but_not_yet_retrievable(self):
        for cat in ("HISTORICAL_DESIGN", "PATTERN", "BRAND_MASTER"):
            p = C.retrieval_posture(cat)
            assert p["knowledge_class"] is True
            assert p["retrieval_allowed"] is False   # no contract until DIP-1

    def test_every_record_carries_a_posture(self, tree):
        for r in _annotated(tree).values():
            assert set(r["posture"]) == {"knowledge_class",
                                         "excluded_from_retrieval_by_rule",
                                         "retrieval_allowed",
                                         "automatic_use_allowed", "reason"}
