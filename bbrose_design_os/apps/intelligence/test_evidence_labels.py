"""DIP-1C-5C-CORR-1 — evidence labels must distinguish what they label.

The defect these guard against was presentation-only and therefore easy to miss: every
reference's hash and locator was distinct, but the form rendered the shared
`SourceArtifact.sha256`, so 11 page units of one Illustrator file produced 11 identical
checkboxes. A reviewer cannot honestly cite evidence they cannot tell apart.
"""
from __future__ import annotations

import re

from django.contrib.auth import get_user_model
from django.utils import timezone
import pytest

from apps.accounts import authz_policy as authz
from apps.accounts.models import (
    DecisionEvent, GRANT_TEST_FIXTURE, ReviewerProfile, ReviewerRoleAssignment,
)

from .evidence_labels import evidence_label, labelled_evidence
from .models import (
    CorpusItem, EvidenceReference, GovernanceDecisionProjection,
    HistoricalDesignProfile, HumanAssertionProjection, OperationalPermissionProjection,
    ReviewCandidate, SourceArtifact,
)
from .review_manifest import MANIFEST_ID

pytestmark = pytest.mark.django_db
User = get_user_model()


def _reviewer():
    granter = User.objects.create_user(username="label-granter")
    user = User.objects.create_user(username="label-reviewer")
    ReviewerProfile.objects.create(user=user, reviewer_enabled=True)
    ReviewerRoleAssignment.objects.create(
        user=user, role=authz.DESIGN_REVIEWER, granted_by=granter,
        granted_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=1),
        grant_source=GRANT_TEST_FIXTURE, grant_reason="label test")
    return user


def _historical_item(*, units=11):
    """A historical design with one SOURCE_FILE and `units` FILE_PAGE_UNIT references —
    the exact shape that collided: one source artifact, many units."""
    item = CorpusItem.objects.create(
        item_kind=CorpusItem.Kind.HISTORICAL_DESIGN, external_key="historical:labels:00")
    source = SourceArtifact.objects.create(
        source_identifier="source-labels", source_location="repository:materials/x.ai",
        source_type=SourceArtifact.SourceType.FILE, sha256="e5" * 32,
        parser_identifier="test", parser_version="1", source_schema_version="1")
    HistoricalDesignProfile.objects.create(
        corpus_item=item, primary_source_artifact=source,
        display_title="BL-2050 STAND", audit_status="MACHINE_AUDITED")
    EvidenceReference.objects.create(
        corpus_item=item, source_artifact=source, evidence_kind="SOURCE_FILE",
        locator={"path": "materials/historical AI production designs/BL-2050 STAND.ai"},
        locator_schema_version="source_file/1.0", evidence_hash="aa" * 32)
    for index in range(units):
        EvidenceReference.objects.create(
            corpus_item=item, source_artifact=source, evidence_kind="FILE_PAGE_UNIT",
            locator={"page": 0, "unit_key": f"BL-2050 STAND-p0-u{index:02d}"},
            locator_schema_version="file_page/1.0",
            evidence_hash=f"{index:02d}" + "b" * 62)
    candidate = ReviewCandidate.objects.create(
        corpus_item=item, review_type=ReviewCandidate.ReviewType.HISTORICAL_MEMORY,
        priority=50, review_manifest_id=MANIFEST_ID, machine_confidence_summary={})
    return item, candidate


def _rendered_labels(body):
    return re.findall(
        r'name="evidence_reference_ids" value="([^"]+)">([^<]+)</label>', body)


# --- the helper -------------------------------------------------------------------

def test_page_units_of_one_source_file_are_distinguishable():
    item, _ = _historical_item(units=11)
    units = EvidenceReference.objects.filter(
        corpus_item=item, evidence_kind="FILE_PAGE_UNIT").order_by("pk")
    labels = [evidence_label(reference) for reference in units]
    assert len(labels) == 11
    assert len(set(labels)) == 11, "page-unit labels collide"
    # the shared source hash must not be what distinguishes (or fails to) them
    assert not any("e5e5e5" in label for label in labels)


def test_unit_key_and_page_are_displayed_when_safely_available():
    item, _ = _historical_item(units=3)
    reference = EvidenceReference.objects.get(
        corpus_item=item, locator__unit_key="BL-2050 STAND-p0-u01")
    label = evidence_label(reference)
    assert label == "FILE_PAGE_UNIT · page 0 · BL-2050 STAND-p0-u01"


def test_source_file_is_clearly_distinct_from_page_units():
    item, _ = _historical_item(units=3)
    source_label = evidence_label(EvidenceReference.objects.get(
        corpus_item=item, evidence_kind="SOURCE_FILE"))
    assert source_label.startswith("SOURCE_FILE · complete source · SHA-256 ")
    unit_labels = {evidence_label(r) for r in EvidenceReference.objects.filter(
        corpus_item=item, evidence_kind="FILE_PAGE_UNIT")}
    assert source_label not in unit_labels


def test_no_label_ever_renders_a_path():
    """`source_file`, `json_path`, `jsonl_record` and `archive_member` locators all carry
    real repository or materials paths. None may reach a label."""
    item, _ = _historical_item(units=1)
    source = SourceArtifact.objects.get()
    unsafe = [
        ("json_path/1.0", {"path": "var/design_intelligence/audits/x.json",
                           "segments": ["candidates", 3]}),
        ("jsonl_record/1.0", {"path": "materials/index.jsonl", "line": 12}),
        ("archive_member/1.0", {"archive_path": "materials/pack.zip",
                                "member_path": "inner/art.eps"}),
        ("source_file/1.0", {"path": "materials/secret/place.ai"}),
    ]
    for index, (schema, locator) in enumerate(unsafe):
        reference = EvidenceReference.objects.create(
            corpus_item=item, source_artifact=source, evidence_kind="RECORD",
            locator=locator, locator_schema_version=schema,
            evidence_hash=f"{index:02d}" + "f" * 62)
        label = evidence_label(reference)
        assert "materials/" not in label and "var/" not in label
        assert "/" not in label.replace(" · ", "")
        assert "{" not in label and '"' not in label      # no raw locator JSON


def test_a_locator_with_no_safe_value_fails_closed_to_reference_identity():
    item, _ = _historical_item(units=1)
    source = SourceArtifact.objects.get()
    reference = EvidenceReference.objects.create(
        corpus_item=item, source_artifact=source, evidence_kind="RECORD",
        locator={"archive_path": "a.zip", "member_path": "b.eps"},
        locator_schema_version="archive_member/1.0", evidence_hash="cc" * 32)
    label = evidence_label(reference)
    assert label.startswith("RECORD · evidence reference ")
    assert str(reference.pk)[:8] in label
    assert "cccccccccccc" in label                 # its OWN hash, not the source's
    assert source.sha256[:12] not in label
    # nothing invented
    assert "page" not in label and ".ai" not in label and ".zip" not in label


def test_a_path_like_unit_key_is_refused_rather_than_displayed():
    item, _ = _historical_item(units=1)
    source = SourceArtifact.objects.get()
    reference = EvidenceReference.objects.create(
        corpus_item=item, source_artifact=source, evidence_kind="FILE_PAGE_UNIT",
        locator={"page": 2, "unit_key": "materials/leaked/path.ai"},
        locator_schema_version="file_page/1.0", evidence_hash="dd" * 32)
    label = evidence_label(reference)
    assert label == "FILE_PAGE_UNIT · page 2"
    assert "materials" not in label


def test_font_face_and_artboard_locators_have_stable_labels():
    item, _ = _historical_item(units=1)
    source = SourceArtifact.objects.get()
    face = EvidenceReference.objects.create(
        corpus_item=item, source_artifact=source, evidence_kind="FONT_FACE",
        locator={"face_index": 0, "face_id": "face-8a5344c75ef2c5c86457"},
        locator_schema_version="font_face/1.0", evidence_hash="11" * 32)
    artboard = EvidenceReference.objects.create(
        corpus_item=item, source_artifact=source, evidence_kind="ARTBOARD",
        locator={"artboard": 3, "unit_key": "cover"},
        locator_schema_version="illustrator_artboard/1.0", evidence_hash="22" * 32)
    assert evidence_label(face) == "FONT_FACE · face 0 · face-8a5344c75ef2c5c86457"
    assert evidence_label(artboard) == "ARTBOARD · artboard 3 · cover"
    assert evidence_label(face) == evidence_label(face)          # deterministic


def test_labelled_evidence_preserves_order_and_pairs_each_reference():
    item, _ = _historical_item(units=4)
    references = list(EvidenceReference.objects.filter(
        corpus_item=item).order_by("pk"))
    pairs = labelled_evidence(references)
    assert [reference for reference, _ in pairs] == references
    assert all(label == evidence_label(reference) for reference, label in pairs)


# --- the rendered forms -----------------------------------------------------------

def test_every_review_form_renders_distinguishable_labels_and_reference_ids(client):
    from django.urls import reverse
    item, candidate = _historical_item(units=11)
    reviewer = _reviewer()
    client.force_login(reviewer)
    before = (DecisionEvent.objects.count(), HumanAssertionProjection.objects.count(),
              GovernanceDecisionProjection.objects.count(),
              OperationalPermissionProjection.objects.count())

    body = client.get(
        reverse("intelligence:review-detail", args=[candidate.pk])).content.decode()
    rendered = _rendered_labels(body)
    assert rendered, "no evidence checkboxes rendered"

    # every checkbox VALUE is still a canonical EvidenceReference id
    valid_ids = {str(pk) for pk in EvidenceReference.objects.filter(
        corpus_item=item).values_list("pk", flat=True)}
    assert {value for value, _ in rendered} <= valid_ids

    # labels distinguish: 12 references -> 12 distinct labels, on every form
    labels = {label.strip() for _, label in rendered}
    assert len(labels) == 12, f"labels collide: {sorted(labels)}"
    assert not any(len(set(label)) < 3 for label in labels)

    # the old collision must not be reachable anywhere on the page
    source_hash = SourceArtifact.objects.get().sha256
    assert f"FILE_PAGE_UNIT · {source_hash}" not in body
    for _, label in rendered:
        assert source_hash not in label or label.startswith("SOURCE_FILE")

    # no path and no raw locator JSON inside any LABEL. (The DIP-1B-5B review packet
    # separately renders a root-relative `repository:materials/…` location by design, so
    # this assertion is scoped to labels rather than the whole page.)
    for _, label in rendered:
        assert "materials/" not in label and "/Users/" not in label
        assert "{" not in label and '"' not in label

    # GET is inert
    assert (DecisionEvent.objects.count(), HumanAssertionProjection.objects.count(),
            GovernanceDecisionProjection.objects.count(),
            OperationalPermissionProjection.objects.count()) == before


def test_rendering_is_deterministic_across_requests(client):
    from django.urls import reverse
    _, candidate = _historical_item(units=6)
    client.force_login(_reviewer())
    url = reverse("intelligence:review-detail", args=[candidate.pk])
    first = _rendered_labels(client.get(url).content.decode())
    second = _rendered_labels(client.get(url).content.decode())
    assert first == second


def test_evidence_records_are_untouched_by_labelling(client):
    from django.urls import reverse
    item, candidate = _historical_item(units=5)
    before = {
        str(r.pk): (r.evidence_hash, r.source_artifact.sha256, r.locator,
                    r.locator_schema_version, r.evidence_kind)
        for r in EvidenceReference.objects.filter(corpus_item=item)}
    client.force_login(_reviewer())
    client.get(reverse("intelligence:review-detail", args=[candidate.pk]))
    after = {
        str(r.pk): (r.evidence_hash, r.source_artifact.sha256, r.locator,
                    r.locator_schema_version, r.evidence_kind)
        for r in EvidenceReference.objects.filter(corpus_item=item)}
    assert before == after


# === DIP-1C-5C-CORR-2: evidence options must be individually selectable ============

def _item_one_shape():
    """The real item-1 shape: one SOURCE_FILE plus eleven FILE_PAGE_UNIT references of the
    same source, in the pk order the form renders — the shape in which SOURCE_FILE and u06
    landed adjacent."""
    item, candidate = _historical_item(units=11)
    return item, candidate


def test_every_evidence_option_is_its_own_separated_block(client):
    """The defect: `</label><label>` with inline labels and no separator rendered twelve
    options as one continuous wrapping block, so adjacent options shared an ambiguous click
    target and SOURCE_FILE sat immediately beside a page unit."""
    from django.urls import reverse
    item, candidate = _item_one_shape()
    client.force_login(_reviewer())
    body = client.get(
        reverse("intelligence:review-detail", args=[candidate.pk])).content.decode()

    options = re.findall(
        r'<label class="evidence-option"><input type="checkbox" '
        r'name="evidence_reference_ids" value="([^"]+)"> ([^<]+)</label>', body)
    assert options, "evidence options are not rendered as separated blocks"
    # every evidence checkbox carries the class — none left in the old inline form
    assert body.count('name="evidence_reference_ids"') == body.count(
        'class="evidence-option"')
    # and no two EVIDENCE options are emitted without a separator between them.
    # (Vocabulary <select> labels are direct children of the `.filters` grid and are
    # therefore already block-level grid items; the defect was specific to checkboxes
    # nested inside a fieldset, which is itself a single grid item.)
    assert '</label><label class="evidence-option"' not in body
    for value, _ in options:
        assert f'</label><label class="evidence-option"><input type="checkbox" ' \
               f'name="evidence_reference_ids" value="{value}"' not in body


def test_labels_and_values_pair_correctly_in_the_real_item_shape(client):
    from django.urls import reverse
    item, candidate = _item_one_shape()
    client.force_login(_reviewer())
    body = client.get(
        reverse("intelligence:review-detail", args=[candidate.pk])).content.decode()
    rendered = dict(re.findall(
        r'name="evidence_reference_ids" value="([^"]+)"> ([^<]+)</label>', body))
    truth = {str(r.pk): evidence_label(r)
             for r in EvidenceReference.objects.filter(corpus_item=item)}
    for value, label in rendered.items():
        assert label.strip() == truth[value], f"label/value mismatch for {value}"
    assert len(rendered) == len(truth) == 12
    assert len(set(rendered)) == 12, "duplicate checkbox values"


@pytest.mark.parametrize("pick", ["SOURCE_FILE", "u06"])
def test_the_posted_reference_is_exactly_what_is_signed(client, settings, pick):
    """The decisive check: POST one id through the real view and form field, and confirm
    the signed payload contains that id and no neighbour."""
    from django.urls import reverse
    from apps.accounts.security import signing
    from .semantic_metadata_scope import scope_item_ids
    settings.DECISION_EVENT_HMAC_KEYS = {"corr2": "5" * 32}
    settings.DECISION_EVENT_ACTIVE_KEY_ID = "corr2"
    signing.reset_registry()
    item, candidate = _item_one_shape()
    references = {evidence_label(r): r for r in
                  EvidenceReference.objects.filter(corpus_item=item)}
    source_file = next(r for label, r in references.items()
                       if label.startswith("SOURCE_FILE"))
    unit_06 = next(r for label, r in references.items() if "u06" in label)
    chosen = source_file if pick == "SOURCE_FILE" else unit_06
    other = unit_06 if pick == "SOURCE_FILE" else source_file

    # the scope is computed from the corpus, so make this fixture item genuinely in scope
    if str(item.pk) not in scope_item_ids():
        pytest.skip("fixture item is not inside the live review scope")

    client.force_login(_reviewer())
    response = client.post(
        reverse("intelligence:review-record-semantic-metadata", args=[candidate.pk]),
        {"review_scope_id": "dip1c_semantic_metadata_review_scope/1.0",
         "metadata_design_styles": ["MINIMAL"],
         "evidence_reference_ids": [str(chosen.pk)]})
    assert response.status_code == 302, response.content[:200]
    event = DecisionEvent.objects.order_by("sequence_number").last()
    assert event.payload["evidence_reference_ids"] == [str(chosen.pk)]
    assert str(other.pk) not in str(event.payload)
    signing.reset_registry()


def test_multi_value_parsing_keeps_every_selected_reference(client):
    """`getlist` semantics: two boxes ticked must yield two ids, not the last one."""
    from django.test import RequestFactory
    from .views import _semantic_metadata_payload
    item, candidate = _item_one_shape()
    references = list(EvidenceReference.objects.filter(corpus_item=item).order_by("pk"))[:3]
    request = RequestFactory().post("/", {
        "review_scope_id": "x",
        "evidence_reference_ids": [str(r.pk) for r in references],
        "metadata_design_styles": ["MINIMAL", "LUXURY"]})
    payload = _semantic_metadata_payload(request, candidate)
    assert payload["evidence_reference_ids"] == [str(r.pk) for r in references]
    assert payload["bundle"]["design_styles"] == ["MINIMAL", "LUXURY"]


def test_render_order_cannot_substitute_one_reference_for_another(client):
    """Values are canonical ids, never positional indexes — so display order is irrelevant
    to what gets signed."""
    from django.urls import reverse
    item, candidate = _item_one_shape()
    client.force_login(_reviewer())
    body = client.get(
        reverse("intelligence:review-detail", args=[candidate.pk])).content.decode()
    values = re.findall(r'name="evidence_reference_ids" value="([^"]+)"', body)
    ids = {str(r.pk) for r in EvidenceReference.objects.filter(corpus_item=item)}
    assert set(values) <= ids
    assert not any(value.isdigit() for value in values), "a positional index was rendered"
