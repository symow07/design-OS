"""Safe semantic-document enrichment — DIP-1C-3A (schema 1.1).

What must hold: an unsafe optional title is OMITTED (not sanitized, not transmitted, not
fatal) so the item stays indexable; product-family and script-coverage metadata come only
from existing bounded machine observations and stay explicitly machine-derived; schema 1.0
stays frozen; and the recursive value boundary is untouched.

Nothing here contacts OpenAI.
"""
from __future__ import annotations

import pytest

from apps.accounts.models import DecisionEvent

from . import semantic_document as SD
from .dataset_identifiers import DIP0C2_ASSET_CANDIDATE_DATASET
from .models import (
    CorpusItem, FontFaceProfile, GovernanceDecisionProjection, HistoricalDesignProfile,
    HumanAssertionProjection, MachineClassification, OperationalPermissionProjection,
    SourceArtifact,
)
from .test_review_campaign import asset, brand

pytestmark = pytest.mark.django_db
_n = 0


def _artifact():
    global _n
    _n += 1
    return SourceArtifact.objects.create(
        source_identifier=f"enr-{_n}", source_location=f"logical:enr:{_n}",
        source_type=SourceArtifact.SourceType.FILE, sha256=f"{_n:064x}",
        parser_identifier="t", parser_version="1", source_schema_version="t/1.0")


def _historical(title, family=""):
    global _n
    _n += 1
    item = CorpusItem.objects.create(
        item_kind=CorpusItem.Kind.HISTORICAL_DESIGN,
        external_key=f"historical:enr:{_n}")
    HistoricalDesignProfile.objects.create(
        corpus_item=item, primary_source_artifact=_artifact(), display_title=title,
        page_artboard_count=1, extracted_design_unit_count=1,
        audit_status="MACHINE_AUDITED", product_family_machine_label=family)
    return item


def _font(family_name, coverage):
    global _n
    _n += 1
    item = CorpusItem.objects.create(
        item_kind=CorpusItem.Kind.FONT, external_key=f"font:enr:{_n}")
    FontFaceProfile.objects.create(
        corpus_item=item, primary_source_artifact=_artifact(), face_index=0,
        family_name=family_name, subfamily="Regular", postscript_name=family_name,
        weight=400, width="NORMAL", italic=False, variable_axes=[],
        script_coverage=coverage, suspected_system_copy=False,
        evidence_state="PRESENT_UNREVIEWED",
        technical_suitability_state="HEALTHY")
    return item


# === schema versioning ===========================================================
def test_schema_1_0_stays_frozen_and_1_1_is_active():
    assert SD.DOCUMENT_SCHEMA_V1_0 == "intelligence_semantic_document/1.0"
    assert SD.DOCUMENT_SCHEMA_V1_1 == "intelligence_semantic_document/1.1"
    assert SD.DOCUMENT_SCHEMA == SD.DOCUMENT_SCHEMA_V1_1
    # 1.0's field list is frozen exactly as it shipped
    assert SD.INCLUDED_FIELDS_V1_0 == (
        "external_key", "item_kind", "display_label", "dataset_identifier",
        "product_family_label", "style_labels", "font_metadata",
        "observed_fact_labels", "observed_fact_values",
        "machine_classification_labels", "human_assertion_labels",
        "readiness_state", "blocker_codes")
    assert {"machine_product_family_labels", "observed_script_coverage"} <= set(
        SD.INCLUDED_FIELDS)
    # 1.1 REMOVES 1.0's raw `product_family_label`: it was an unbounded passthrough of a
    # machine string and therefore an unvalidated leak vector, superseded by the bounded
    # machine-marked field. A schema version may remove a field; it may not redefine 1.0.
    assert "product_family_label" in SD.INCLUDED_FIELDS_V1_0
    assert "product_family_label" not in SD.INCLUDED_FIELDS


def test_a_1_1_document_hashes_differently_from_its_1_0_shape():
    item = brand().corpus_item
    document = SD.build_semantic_document(item)
    assert document["schema_version"] == SD.DOCUMENT_SCHEMA_V1_1
    legacy = {k: v for k, v in document.items()
              if k in set(SD.INCLUDED_FIELDS_V1_0) | {"schema_version"}}
    legacy["schema_version"] = SD.DOCUMENT_SCHEMA_V1_0
    assert SD.document_hash(document) != SD.document_hash(legacy)


def test_1_1_documents_are_deterministic():
    item = brand().corpus_item
    assert SD.build_semantic_document(item) == SD.build_semantic_document(item)


# === optional unsafe display label: omitted, not fatal, not sanitized ============
def test_unsafe_optional_title_is_omitted_and_the_item_stays_indexable():
    item = _historical("LG5505唇彩.ai", family="lip-colour")
    document, diagnostics = SD.build_semantic_document(item, with_diagnostics=True)
    # the item IS indexable ...
    assert document["external_key"] == item.external_key
    # ... the unsafe title is simply absent
    assert "display_label" not in document
    assert diagnostics == [{"field": "display_label",
                            "reason_code": SD.OPTIONAL_DISPLAY_LABEL_OMITTED_SOURCE_FILENAME}]
    # ... and its safe siblings survived
    assert document["machine_product_family_labels"] == ["LIP_COLOUR"]


def test_the_unsafe_value_never_appears_in_document_bytes_hash_or_text():
    item = _historical("LG5505唇彩.ai", family="lip-colour")
    document = SD.build_semantic_document(item)
    blob = repr(document) + SD.semantic_text(document)
    assert "LG5505唇彩.ai" not in blob
    assert ".ai" not in SD.semantic_text(document)
    SD._assert_within_boundary(document)


def test_an_unsafe_title_is_never_sanitized_into_a_title():
    """Stripping '.ai' and presenting the remainder as a reviewed title would manufacture
    metadata no human approved."""
    item = _historical("LG5505唇彩.ai", family="lip-colour")
    document = SD.build_semantic_document(item)
    assert document.get("display_label", "") == ""
    assert "LG5505唇彩" not in SD.semantic_text(document)   # not the stripped stem either
    # the stored value is preserved untouched
    assert HistoricalDesignProfile.objects.get(
        corpus_item=item).display_title == "LG5505唇彩.ai"


def test_safe_titles_are_still_carried():
    item = _historical("BL-2050 STAND")
    assert SD.build_semantic_document(item)["display_label"] == "BL-2050 STAND"


def test_all_six_representative_filename_titles_become_indexable():
    titles = ["LG5505唇彩.ai", "ZYG5528遮瑕膏.ai", "PM5520妆前乳.ai",
              "BL-2055 FB-2056.ai", "FL-2025.ai", "YB-1059(ES6009).END.ai"]
    for title in titles:
        item = _historical(title, family="lip-colour")
        document = SD.build_semantic_document(item)   # must not raise
        assert "display_label" not in document
        assert title not in SD.semantic_text(document)
        assert document["machine_product_family_labels"] == ["LIP_COLOUR"]


# === machine product family ======================================================
def test_product_family_comes_from_bounded_machine_observations_and_is_marked_machine():
    item = _historical("BL-2050 STAND", family="eye-colour")
    document = SD.build_semantic_document(item)
    assert document["machine_product_family_labels"] == ["EYE_COLOUR"]
    # the key itself declares the labels machine-derived, and human labels stay separate
    assert "machine" in "machine_product_family_labels"
    assert document["human_assertion_labels"] == []


def test_product_family_normalizes_through_an_explicit_vocabulary():
    assert SD.PRODUCT_FAMILY_VOCABULARY["lip-colour"] == "LIP_COLOUR"
    item = _historical("safe title", family="makeup-compact")
    assert SD.build_semantic_document(item)["machine_product_family_labels"] == [
        "MAKEUP_COMPACT"]


def test_unknown_family_becomes_other_and_empty_yields_nothing():
    assert SD.build_semantic_document(
        _historical("safe a", family="something-new"))[
        "machine_product_family_labels"] == [SD.PRODUCT_FAMILY_OTHER]
    assert SD.build_semantic_document(
        _historical("safe b", family=""))["machine_product_family_labels"] == []


def test_a_path_like_value_can_never_become_a_product_family():
    item = _historical("safe title", family="materials/DOWNLOADE 2026/x.ai")
    document = SD.build_semantic_document(item)
    assert document["machine_product_family_labels"] == []      # refused, not mapped
    assert "materials" not in SD.semantic_text(document)


def test_conflicting_machine_labels_stay_visible_as_a_conflict():
    item = _historical("safe title", family="lip-colour")
    from decimal import Decimal
    MachineClassification.objects.create(
        corpus_item=item, classification_type=SD.PRODUCT_FAMILY_CLASSIFICATION_TYPE,
        label="concealer", confidence=Decimal("0.6000"), classifier_identifier="t",
        classifier_version="1", classification_schema_version="t/1.0",
        source_artifact=_artifact(), classification_hash="d" * 64)
    labels = SD.build_semantic_document(item)["machine_product_family_labels"]
    # both survive, and the disagreement is explicit — never silently resolved
    assert "LIP_COLOUR" in labels and "CONCEALER" in labels
    assert SD.PRODUCT_FAMILY_CONFLICT in labels


# === font script coverage ========================================================
def test_script_coverage_is_carried_for_font_records():
    item = _font("almarai", {"latin": 159, "arabic": 104, "numerals": 10,
                             "arabic_presentation_a": 59})
    document = SD.build_semantic_document(item)
    assert document["observed_script_coverage"] == ["ARABIC", "LATIN"]


def test_numerals_is_excluded_as_a_non_script_character_class():
    item = _font("qurova demo", {"latin": 151, "numerals": 10})
    assert SD.build_semantic_document(item)["observed_script_coverage"] == ["LATIN"]
    assert "numerals" in SD.NON_SCRIPT_TOKENS


def test_script_coverage_uses_the_bounded_vocabulary_and_is_sorted():
    item = _font("mixed", {"cyrillic": 5, "latin": 100, "greek": 3, "wingdings": 2})
    coverage = SD.build_semantic_document(item)["observed_script_coverage"]
    assert coverage == sorted(coverage)
    assert set(coverage) <= set(SD.SCRIPT_VOCABULARY.values()) | {
        SD.SCRIPT_OTHER, SD.SCRIPT_UNKNOWN}
    assert SD.SCRIPT_OTHER in coverage        # wingdings is not a known script


def test_script_coverage_carries_no_raw_ranges_paths_or_filenames():
    item = _font("almarai", {"latin": 159, "arabic": 104})
    document = SD.build_semantic_document(item)
    text = SD.semantic_text(document)
    assert "U+" not in text and "materials" not in text and ".ttf" not in text
    SD._assert_within_boundary(document)


def test_a_non_font_item_has_no_script_coverage():
    assert SD.build_semantic_document(
        asset(DIP0C2_ASSET_CANDIDATE_DATASET).corpus_item)[
        "observed_script_coverage"] == []


# === boundary + read-only ========================================================
def test_the_assembled_1_1_document_is_validated_as_a_whole():
    for item in (_historical("LG5505唇彩.ai", family="lip-colour"),
                 _font("almarai", {"latin": 1, "arabic": 2}),
                 asset(DIP0C2_ASSET_CANDIDATE_DATASET).corpus_item,
                 brand().corpus_item):
        SD._assert_within_boundary(SD.build_semantic_document(item))


def test_enrichment_writes_nothing_and_creates_no_authority():
    before = (DecisionEvent.objects.count(), HumanAssertionProjection.objects.count(),
              GovernanceDecisionProjection.objects.count(),
              OperationalPermissionProjection.objects.count())
    SD.build_semantic_document(_historical("LG5505唇彩.ai", family="lip-colour"))
    SD.build_semantic_document(_font("almarai", {"latin": 1, "arabic": 2}))
    assert (DecisionEvent.objects.count(), HumanAssertionProjection.objects.count(),
            GovernanceDecisionProjection.objects.count(),
            OperationalPermissionProjection.objects.count()) == before
