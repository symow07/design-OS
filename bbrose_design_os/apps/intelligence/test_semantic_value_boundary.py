"""Semantic-document value boundary — DIP-1C-1-CORR-1.

The original boundary check inspected prohibited *field names* only, so a filesystem path
sitting inside an allowed field (`style_labels`, via
`DesignAssetProfile.collection_family_label`) passed validation — 34 of 176 documents would
have transmitted source paths to OpenAI. These tests pin both halves of the repair: the
contaminated field is gone, and every nested value is now inspected.

Nothing here contacts OpenAI.
"""
from __future__ import annotations

import pytest

from apps.accounts.models import DecisionEvent

from . import semantic_document as SD
from .dataset_identifiers import DIP0C2_ASSET_CANDIDATE_DATASET
from .models import (
    DesignAssetProfile, GovernanceDecisionProjection, HumanAssertionProjection,
    OperationalPermissionProjection,
)
from .test_review_campaign import asset, brand

pytestmark = pytest.mark.django_db

# the exact real value observed in the live corpus that the preview caught
REAL_LEAKED_VALUE = "materials/DOWNLOADE 2026/DOWNLOADS 12-2025/9993170.ai"


def _doc(**over):
    """A minimal schema-1.1 document."""
    base = {
        "schema_version": SD.DOCUMENT_SCHEMA,
        "external_key": "asset:x:1", "item_kind": "DESIGN_ASSET",
        "display_label": "abc123", "dataset_identifier": "d/1.0",
        "machine_product_family_labels": [], "style_labels": [], "font_metadata": {},
        "observed_script_coverage": [],
        "observed_fact_labels": [], "observed_fact_values": [],
        "machine_classification_labels": [], "human_assertion_labels": [],
        "readiness_state": "", "blocker_codes": [],
    }
    base.update(over)
    return base


# === the reported real defect ====================================================
def test_the_real_reported_path_is_rejected():
    with pytest.raises(SD.SemanticDocumentError) as exc:
        SD._assert_within_boundary(_doc(style_labels=["UNKNOWN", REAL_LEAKED_VALUE]))
    assert exc.value.code == SD.MATERIALS_PATH_VALUE
    # the location is identified ...
    assert "style_labels[1]" in str(exc.value)
    # ... but the prohibited value itself is never echoed
    assert REAL_LEAKED_VALUE not in str(exc.value)


def test_materials_path_with_source_extension_is_rejected():
    with pytest.raises(SD.SemanticDocumentError):
        SD._assert_within_boundary(_doc(style_labels=["materials/x/9993170.ai"]))


# === path shapes =================================================================
@pytest.mark.parametrize("value,code", [
    ("/Users/symow/secret.ai", SD.ABSOLUTE_PATH_VALUE),
    ("/home/someone/x.psd", SD.ABSOLUTE_PATH_VALUE),
    ("/private/tmp/a.png", SD.ABSOLUTE_PATH_VALUE),
    ("/tmp/scratch.eps", SD.ABSOLUTE_PATH_VALUE),
    ("C:\\Users\\me\\logo.ai", SD.ABSOLUTE_PATH_VALUE),
    ("D:/designs/pattern.psd", SD.ABSOLUTE_PATH_VALUE),
    ("../../etc/passwd", SD.RELATIVE_PATH_VALUE),
    ("..\\windows\\thing", SD.RELATIVE_PATH_VALUE),
    ("file:///Users/x/y.ai", SD.FILE_URI_VALUE),
    ("materials/Fonts/3333/consola.ttf", SD.MATERIALS_PATH_VALUE),
    ("materials\\Fonts\\x.otf", SD.MATERIALS_PATH_VALUE),
    ("9993170.ai", SD.SOURCE_FILENAME_VALUE),
    ("logo.psd", SD.SOURCE_FILENAME_VALUE),
    ("archive.zip", SD.SOURCE_FILENAME_VALUE),
    ("Pantone_3519C.ase", SD.SOURCE_FILENAME_VALUE),
    ("collection/sheet.svg", SD.RELATIVE_PATH_VALUE),
])
def test_path_like_values_are_rejected_with_a_reason_code(value, code):
    with pytest.raises(SD.SemanticDocumentError) as exc:
        SD._assert_within_boundary(_doc(style_labels=[value]))
    assert exc.value.code == code


# === recursion: nested structures are inspected ==================================
def test_nested_list_values_are_inspected():
    with pytest.raises(SD.SemanticDocumentError) as exc:
        SD._assert_within_boundary(
            _doc(observed_fact_values=["fine", "also fine", REAL_LEAKED_VALUE]))
    assert "observed_fact_values[2]" in str(exc.value)


def test_nested_dictionary_values_are_inspected():
    with pytest.raises(SD.SemanticDocumentError) as exc:
        SD._assert_within_boundary(
            _doc(font_metadata={"family_name": "ok",
                                "technical_suitability_state": "/Users/x/f.ttf"}))
    assert "font_metadata.technical_suitability_state" in str(exc.value)


def test_a_prohibited_value_cannot_ride_inside_an_allowed_field_name():
    """The whole defect in one assertion: the field name is allow-listed, the value is not."""
    doc = _doc(style_labels=[REAL_LEAKED_VALUE])
    assert "style_labels" in SD.INCLUDED_FIELDS      # the field IS allowed ...
    with pytest.raises(SD.SemanticDocumentError):    # ... the value still fails closed
        SD._assert_within_boundary(doc)


def test_field_name_check_still_fires():
    with pytest.raises(SD.SemanticDocumentError) as exc:
        SD._assert_within_boundary(_doc(source_location="anything"))
    assert exc.value.code == SD.PROHIBITED_FIELD_NAME


# === safe values must NOT be rejected ============================================
@pytest.mark.parametrize("value", [
    "floral motif", "luxury packaging", "pink and gold", "Arabic display font",
    "MOTIF", "BACKGROUND", "SURFACE_ARTWORK", "makeup-compact", "lip-colour",
    "janda apple cobbler solid", "gobold bold", "v1.0 release", "3.5 mm",
    "50/50 split", "ES3083吸塑 展盒刀线", "BL-2050 STAND",
])
def test_ordinary_descriptive_values_remain_accepted(value):
    SD._assert_within_boundary(_doc(style_labels=[value]))   # must not raise


def test_dataset_identifier_with_a_version_slash_is_accepted():
    # "dip0c2_asset_candidate_pilot/1.0" contains a slash but is not a path
    SD._assert_within_boundary(_doc(dataset_identifier="dip0c2_asset_candidate_pilot/1.0"))


# === the real affected shape (not only a synthetic validator test) ===============
def test_the_real_contaminated_profile_shape_no_longer_leaks():
    """Reproduces the live DesignAssetProfile shape that caused the defect: a
    collection_family_label holding a source path. The document must build cleanly and
    must not carry the path."""
    rc = asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    DesignAssetProfile.objects.filter(corpus_item=rc.corpus_item).update(
        collection_family_label=REAL_LEAKED_VALUE)
    document = SD.build_semantic_document(rc.corpus_item)   # would previously raise/leak
    blob = repr(document) + SD.semantic_text(document)
    assert "materials/" not in blob
    assert "9993170.ai" not in blob
    assert REAL_LEAKED_VALUE not in blob
    # the safe kind label is still present
    assert "MOTIF" in document["style_labels"]


def test_collection_family_label_is_not_transmitted_but_is_preserved_in_the_database():
    rc = asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    DesignAssetProfile.objects.filter(corpus_item=rc.corpus_item).update(
        collection_family_label=REAL_LEAKED_VALUE)
    SD.build_semantic_document(rc.corpus_item)
    # the stored provenance value is untouched — we do not mutate source records
    profile = DesignAssetProfile.objects.get(corpus_item=rc.corpus_item)
    assert profile.collection_family_label == REAL_LEAKED_VALUE


# === whole-corpus + read-only ====================================================
def test_document_generation_writes_nothing_and_creates_no_authority():
    before = (DecisionEvent.objects.count(), HumanAssertionProjection.objects.count(),
              GovernanceDecisionProjection.objects.count(),
              OperationalPermissionProjection.objects.count())
    for rc in (asset(DIP0C2_ASSET_CANDIDATE_DATASET), brand()):
        SD.build_semantic_document(rc.corpus_item)
    assert (DecisionEvent.objects.count(), HumanAssertionProjection.objects.count(),
            GovernanceDecisionProjection.objects.count(),
            OperationalPermissionProjection.objects.count()) == before


def test_every_built_document_passes_the_value_boundary():
    for rc in (asset(DIP0C2_ASSET_CANDIDATE_DATASET), brand()):
        document = SD.build_semantic_document(rc.corpus_item)
        SD._assert_within_boundary(document)      # no prohibited value anywhere


# === an unsafe REQUIRED field still excludes, with a reason, never crashing ======
def test_an_item_with_an_unsafe_required_field_is_excluded_not_fatal():
    """Optional-field omission (DIP-1C-3A) does not weaken the boundary: when a REQUIRED
    identity field carries a path, the document is refused and the item is excluded with a
    reason — never crashed over and never sanitized into passing."""
    from .models import CorpusItem
    from .semantic_index import build_semantic_documents
    good = asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    CorpusItem.objects.create(
        item_kind=CorpusItem.Kind.DESIGN_ASSET,
        external_key="asset:materials/DOWNLOADE 2026/9993170.ai")  # required field unsafe

    docs, manifest, exclusions = build_semantic_documents(with_exclusions=True)
    excluded = {e["external_key"]: e["reason_code"] for e in exclusions}
    assert "asset:materials/DOWNLOADE 2026/9993170.ai" in excluded
    assert excluded["asset:materials/DOWNLOADE 2026/9993170.ai"] == SD.MATERIALS_PATH_VALUE
    assert good.corpus_item.external_key in {i.external_key for i, _ in docs}


def test_excluded_items_do_not_affect_the_corpus_manifest_hash():
    """An item that is not indexed must not influence the index's identity."""
    from .models import CorpusItem
    from .semantic_index import corpus_manifest_hash
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    before = corpus_manifest_hash()
    CorpusItem.objects.create(
        item_kind=CorpusItem.Kind.DESIGN_ASSET,
        external_key="asset:materials/x/unsafe.ai")     # excluded at the boundary
    assert corpus_manifest_hash() == before             # excluded -> not hashed
