"""DIP-1C-5B — signed human semantic metadata workflow.

The load-bearing test here is the service→projection round-trip: `build_projection` fails
closed for the WHOLE chain, so any payload the service can emit but the projector refuses is
a latent outage across every projection domain, not a local metadata bug.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.utils import timezone
import pytest

from apps.accounts import authz_policy as authz
from apps.accounts.models import (
    DecisionEvent, GRANT_TEST_FIXTURE, ReviewerProfile, ReviewerRoleAssignment,
)
from apps.accounts.security import signing

from . import semantic_metadata_scope as scope
from .human_semantic_metadata import (
    FORBIDDEN_BRAND_CLAIMS, METADATA_ASSERTION_DOMAIN, METADATA_SCHEMA,
    MetadataBundleError, build_metadata_bundle, bundle_embedding_terms,
)
from .models import (
    CorpusItem, DesignAssetProfile, EvidenceReference, HumanAssertionProjection,
    ReviewCandidate, SourceArtifact,
)
from .projection import build_projection
from .review_services import AssertionValidationError, ReviewAuthorizationDenied
from .semantic_metadata_service import (
    REVIEW_SCOPE_ID, correct_human_semantic_metadata, record_human_semantic_metadata,
)

pytestmark = pytest.mark.django_db
User = get_user_model()
KEY = "2" * 32


@pytest.fixture(autouse=True)
def _signing(settings):
    settings.DECISION_EVENT_HMAC_KEYS = {"metadata-test": KEY}
    settings.DECISION_EVENT_ACTIVE_KEY_ID = "metadata-test"
    signing.reset_registry()
    yield
    signing.reset_registry()


def _reviewer(role=authz.DESIGN_REVIEWER, username=None):
    username = username or f"reviewer-{role}-{User.objects.count()}"
    granter = User.objects.create_user(username=f"grant-{username}")
    user = User.objects.create_user(username=username)
    ReviewerProfile.objects.create(user=user, reviewer_enabled=True)
    ReviewerRoleAssignment.objects.create(
        user=user, role=role, granted_by=granter, granted_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=30),
        grant_source=GRANT_TEST_FIXTURE, grant_reason="DIP-1C-5B test")
    return user


def _scoped_item(external_key="asset:metadata-0001", *, test_only=False):
    """A DESIGN_ASSET in the C2 dataset — deterministic scope segment `c2_assets`."""
    item = CorpusItem.objects.create(
        item_kind=CorpusItem.Kind.DESIGN_ASSET, external_key=external_key)
    source = SourceArtifact.objects.create(
        source_identifier=f"source-{external_key}", source_location=f"logical:{external_key}",
        source_type=SourceArtifact.SourceType.FILE, sha256="a" * 64,
        parser_identifier="test", parser_version="1", source_schema_version="1")
    evidence = EvidenceReference.objects.create(
        corpus_item=item, source_artifact=source, evidence_kind="SOURCE_FILE",
        locator={"path": f"bounded/{external_key}.ai"},
        locator_schema_version="source_file/1.0", evidence_hash="b" * 64,
        is_test_only=False)
    DesignAssetProfile.objects.create(
        corpus_item=item, primary_source_artifact=source,
        candidate_source_key=item.pk.hex[:16],
        source_manifest_entry_key=f"test:{item.pk}",
        dataset_identifier=scope.DIP0C2_ASSET_CANDIDATE_DATASET,
        candidate_asset_kind=DesignAssetProfile.CandidateKind.UNKNOWN,
        representation_state=DesignAssetProfile.Representation.UNKNOWN,
        technical_readiness=DesignAssetProfile.Readiness.REVIEW_REQUIRED,
        extraction_state="TEST_FIXTURE", dimensions_media={}, is_test_only=test_only)
    return item, evidence


def _bundle(**changes):
    bundle = {
        "design_styles": ["MINIMAL", "LUXURY"],
        "motifs": ["FLORAL"],
        "layout_or_format_types": ["PRODUCT_PACKAGING"],
        "search_synonyms": ["rose gold carton"],
        "reviewer_notes": "Soft floral packaging observed on the carton face.",
    }
    bundle.update(changes)
    return bundle


def _payload(item, evidence, **changes):
    payload = {
        "corpus_item_uuid": str(item.pk),
        "bundle": _bundle(),
        "evidence_reference_ids": [str(evidence.pk)],
        "review_scope_id": REVIEW_SCOPE_ID,
    }
    payload.update(changes)
    return payload


# --- contract ---------------------------------------------------------------------

def test_bundle_is_idempotent_so_the_projector_can_re_validate_its_own_payload():
    once = build_metadata_bundle(_bundle())
    assert build_metadata_bundle(once) == once
    assert once["schema_version"] == METADATA_SCHEMA


def test_bundle_refuses_unknown_fields_unknown_terms_and_authority_claims():
    with pytest.raises(MetadataBundleError) as unknown_field:
        build_metadata_bundle({"design_styles": ["MINIMAL"], "ownership": "BBROSE"})
    assert unknown_field.value.code == "UNSUPPORTED_FIELD"
    with pytest.raises(MetadataBundleError) as unknown_term:
        build_metadata_bundle({"design_styles": ["SPARKLY"]})
    assert unknown_term.value.code == "UNSUPPORTED_VOCABULARY"
    for claim in sorted(FORBIDDEN_BRAND_CLAIMS):
        with pytest.raises(MetadataBundleError) as forbidden:
            build_metadata_bundle({"brand_observations": [claim]})
        assert forbidden.value.code == "FORBIDDEN_AUTHORITY_CLAIM"
    with pytest.raises(MetadataBundleError) as empty:
        build_metadata_bundle({"reviewer_notes": "nothing descriptive here"})
    assert empty.value.code == "EMPTY_BUNDLE"


def test_bundle_refuses_paths_and_keeps_reviewer_notes_out_of_embedding_terms():
    with pytest.raises(MetadataBundleError) as path:
        build_metadata_bundle({"search_synonyms": ["/Users/x/materials/rose.ai"]})
    assert path.value.code == "PROHIBITED_VALUE"
    bundle = build_metadata_bundle(_bundle())
    terms = bundle_embedding_terms(bundle)
    assert "MINIMAL" in terms and "rose gold carton" in terms
    assert not any("carton face" in term for term in terms)


# --- scope ------------------------------------------------------------------------

def test_scope_is_deterministic_creates_nothing_and_excludes_test_only_items():
    _scoped_item("asset:metadata-0001")
    _scoped_item("asset:metadata-0002", test_only=True)
    before = (CorpusItem.objects.count(), ReviewCandidate.objects.count())
    first, second = scope.build_scope_document(), scope.build_scope_document()
    assert first == second and scope.scope_hash(first) == scope.scope_hash(second)
    keys = {entry["external_key"] for entry in first["entries"]}
    assert "asset:metadata-0001" in keys and "asset:metadata-0002" not in keys
    assert (CorpusItem.objects.count(), ReviewCandidate.objects.count()) == before


# --- signed events ----------------------------------------------------------------

def test_recording_requires_authorization_scope_membership_and_evidence():
    item, evidence = _scoped_item()
    reviewer = _reviewer()
    unprivileged = User.objects.create_user(username="nobody")
    with pytest.raises(ReviewAuthorizationDenied):
        record_human_semantic_metadata(
            user=unprivileged, payload=_payload(item, evidence))
    with pytest.raises(AssertionValidationError):
        record_human_semantic_metadata(
            user=reviewer, payload=_payload(item, evidence, evidence_reference_ids=[]))
    with pytest.raises(AssertionValidationError):
        record_human_semantic_metadata(
            user=reviewer, payload=_payload(item, evidence, review_scope_id="other/1.0"))
    other_item, _ = _scoped_item("asset:metadata-0009")
    with pytest.raises(AssertionValidationError):
        # evidence belonging to a different corpus item is refused
        record_human_semantic_metadata(
            user=reviewer, payload=_payload(other_item, evidence))
    assert DecisionEvent.objects.count() == 0


def test_system_admin_may_not_record_human_semantic_metadata():
    item, evidence = _scoped_item()
    admin = _reviewer(role=authz.SYSTEM_ADMIN, username="sysadmin")
    with pytest.raises(ReviewAuthorizationDenied):
        record_human_semantic_metadata(user=admin, payload=_payload(item, evidence))
    assert DecisionEvent.objects.count() == 0


def test_request_may_not_supply_server_derived_fields():
    item, evidence = _scoped_item()
    reviewer = _reviewer()
    with pytest.raises(AssertionValidationError):
        record_human_semantic_metadata(
            user=reviewer, payload=_payload(item, evidence, role_used=authz.BRAND_ADMIN))
    with pytest.raises(AssertionValidationError):
        record_human_semantic_metadata(
            user=reviewer, payload=_payload(item, evidence, hmac_signature="x"))
    assert DecisionEvent.objects.count() == 0


def test_recording_signs_an_event_grants_nothing_and_touches_no_review_candidate():
    item, evidence = _scoped_item()
    reviewer = _reviewer()
    event = record_human_semantic_metadata(user=reviewer, payload=_payload(item, evidence))
    assert event.action == authz.RECORD_HUMAN_SEMANTIC_METADATA
    assert event.payload["assertion_schema"] == METADATA_SCHEMA
    assert event.payload["assertion_domain"] == METADATA_ASSERTION_DOMAIN
    assert event.payload["review_scope_id"] == REVIEW_SCOPE_ID
    assert event.role_used == authz.DESIGN_REVIEWER
    assert event.payload["metadata_bundle"]["design_styles"] == ["LUXURY", "MINIMAL"]
    assert ReviewCandidate.objects.count() == 0
    # no permission or authority is expressible in the payload
    assert not ({"authority_effect", "permission", "grants", "retrieval"}
                & set(event.payload))


# --- projection round trip --------------------------------------------------------

def test_service_output_projects_and_correction_supersedes_it():
    item, evidence = _scoped_item()
    reviewer = _reviewer()
    first = record_human_semantic_metadata(user=reviewer, payload=_payload(item, evidence))

    build = build_projection()
    rows = [row for row in build.rows
            if row.assertion_domain == METADATA_ASSERTION_DOMAIN]
    assert len(rows) == 1
    row = rows[0]
    assert row.corpus_item_id == str(item.pk)
    assert row.effective_state == HumanAssertionProjection.EffectiveState.ASSERTED
    assert row.normalized_value["motifs"] == ["FLORAL"]
    assert row.projection_metadata["history_event_ids"] == [first.event_id]

    second = correct_human_semantic_metadata(user=reviewer, payload=_payload(
        item, evidence, bundle=_bundle(motifs=["LINE_ART"]),
        supersedes_event_id=first.event_id))
    build = build_projection()
    rows = [r for r in build.rows if r.assertion_domain == METADATA_ASSERTION_DOMAIN]
    assert len(rows) == 1
    assert rows[0].normalized_value["motifs"] == ["LINE_ART"]
    assert rows[0].source_event_id == second.event_id
    # immutable history: the prior event is preserved, not deleted
    assert rows[0].projection_metadata["superseded_event_ids"] == [first.event_id]
    assert DecisionEvent.objects.filter(event_id=first.event_id).exists()


def test_correction_may_not_cross_items_or_domains():
    item, evidence = _scoped_item()
    other_item, other_evidence = _scoped_item("asset:metadata-0003")
    reviewer = _reviewer()
    first = record_human_semantic_metadata(user=reviewer, payload=_payload(item, evidence))
    with pytest.raises(AssertionValidationError):
        correct_human_semantic_metadata(user=reviewer, payload=_payload(
            other_item, other_evidence, supersedes_event_id=first.event_id))
    with pytest.raises(AssertionValidationError):
        correct_human_semantic_metadata(user=reviewer, payload=_payload(
            item, evidence, supersedes_event_id=str(item.pk)))


def test_metadata_projection_does_not_disturb_other_domains():
    item, evidence = _scoped_item()
    reviewer = _reviewer()
    baseline = build_projection()
    record_human_semantic_metadata(user=reviewer, payload=_payload(item, evidence))
    after = build_projection()
    def non_metadata(build):
        return [row.logical_document() for row in build.rows
                if row.assertion_domain != METADATA_ASSERTION_DOMAIN]
    assert non_metadata(after) == non_metadata(baseline)


# --- schema 1.3 (defined, previewable, NOT built) ---------------------------------

def test_schema_1_3_is_defined_but_is_not_a_build_target():
    from .semantic_builders import (
        DEFINED_NOT_BUILDABLE_SCHEMAS, SUPPORTED_BUILD_SCHEMAS, SemanticBuilderError,
        build_semantic_corpus,
    )
    from .semantic_document_v13 import DOCUMENT_SCHEMA_V1_3
    assert DOCUMENT_SCHEMA_V1_3 in DEFINED_NOT_BUILDABLE_SCHEMAS
    assert DOCUMENT_SCHEMA_V1_3 not in SUPPORTED_BUILD_SCHEMAS
    with pytest.raises(SemanticBuilderError):
        build_semantic_corpus(document_schema_version=DOCUMENT_SCHEMA_V1_3)


def test_schema_1_3_with_no_human_metadata_is_identical_to_schema_1_2():
    from .semantic_document_v12 import build_semantic_document_v12
    from .semantic_document_v13 import build_semantic_document_v13
    item, _ = _scoped_item()
    v12 = build_semantic_document_v12(item)
    v13 = build_semantic_document_v13(item)
    assert v13["embedding_text"] == v12["embedding_text"]
    assert v13["embedding_text_hash"] == v12["embedding_text_hash"]
    assert v13["channels"]["human_semantic_metadata_terms"] == []


def test_schema_1_3_renders_human_terms_marked_verified_and_drops_unknown_and_notes():
    from .semantic_document_v13 import (
        HUMAN_METADATA_CHANNEL, build_semantic_document_v13,
    )
    item, _ = _scoped_item()
    bundle = build_metadata_bundle(_bundle(
        color_characteristics=["SOFT_PINK", "UNKNOWN"]))
    document = build_semantic_document_v13(
        item, metadata_by_item={str(item.pk): bundle})
    terms = [entry["term"] for entry
             in document["channels"][HUMAN_METADATA_CHANNEL]]
    assert "soft pink" in terms and "minimal" in terms
    assert "unknown" not in terms                     # an explicit non-answer is not evidence
    assert not any("carton face" in term for term in terms)   # notes never embedded
    assert all(entry["provenance"] == "VERIFIED_HUMAN_ASSERTION"
               for entry in document["channels"][HUMAN_METADATA_CHANNEL])
    assert "soft pink" in document["embedding_text"]


def test_local_preview_is_offline_and_state_a_matches_schema_1_2():
    from .semantic_metadata_preview import build_preview
    item, _ = _scoped_item()
    fixture = {str(item.pk): build_metadata_bundle(_bundle())}
    preview = build_preview(fixture_bundles=fixture)
    assert preview["embeddings_computed"] == 0
    assert preview["external_transfer"] == "NONE"
    assert preview["state_a_matches_schema_1_2"] is True
    assert preview["state_a"]["human_metadata_terms"] == 0
    assert preview["state_b"]["items_with_human_metadata"] == 1
    # fixtures stay in memory: no event, no projection row is created by previewing
    assert DecisionEvent.objects.count() == 0
    assert HumanAssertionProjection.objects.count() == 0


# --- browser surface ---------------------------------------------------------------

def _candidate_for(item):
    from .review_manifest import MANIFEST_ID
    return ReviewCandidate.objects.create(
        corpus_item=item, review_type=ReviewCandidate.ReviewType.DESIGN_ASSET,
        priority=50, review_manifest_id=MANIFEST_ID, machine_confidence_summary={})


def _form(evidence, **changes):
    data = {
        "review_scope_id": REVIEW_SCOPE_ID,
        "metadata_design_styles": ["MINIMAL"],
        "metadata_motifs": ["FLORAL"],
        "metadata_search_synonyms": "rose gold carton\n",
        "metadata_reviewer_notes": "Observed on the carton face.",
        "evidence_reference_ids": [str(evidence.pk)],
    }
    data.update(changes)
    return data


def test_review_detail_offers_metadata_only_in_scope_and_states_it_grants_nothing(client):
    from django.urls import reverse
    item, _ = _scoped_item()
    candidate = _candidate_for(item)
    client.force_login(_reviewer())
    body = client.get(
        reverse("intelligence:review-detail", args=[candidate.pk])).content.decode()
    assert "HUMAN SEARCH METADATA" in body
    assert "IT DOES NOT AUTHORIZE USE" in body
    assert "SOFT_PINK" in body and "BBROSE_LABEL_OBSERVED_UNCONFIRMED" in body
    assert "OFFICIAL_LOGO" not in body and "OWNED_BY_BBROSE" not in body
    assert DecisionEvent.objects.count() == 0        # GET writes nothing


def test_metadata_post_records_a_signed_event_and_rejects_bad_input(client):
    from django.urls import reverse
    item, evidence = _scoped_item()
    other_item, other_evidence = _scoped_item("asset:metadata-0004")
    candidate = _candidate_for(item)
    url = reverse("intelligence:review-record-semantic-metadata", args=[candidate.pk])
    client.force_login(_reviewer())

    assert client.post(url, _form(
        evidence, metadata_design_styles=["SPARKLY"])).status_code == 400
    assert client.post(url, _form(
        evidence, evidence_reference_ids=[str(other_evidence.pk)])).status_code == 400
    assert client.post(url, _form(
        evidence, review_scope_id="other/1.0")).status_code == 400
    assert DecisionEvent.objects.count() == 0

    assert client.post(url, _form(evidence)).status_code == 302
    event = DecisionEvent.objects.get()
    assert event.action == authz.RECORD_HUMAN_SEMANTIC_METADATA
    assert event.payload["corpus_item_id"] == str(item.pk)
    assert event.payload["metadata_bundle"]["motifs"] == ["FLORAL"]
    assert str(other_item.pk) not in str(event.payload)


def test_metadata_post_requires_authorization_and_is_post_only(client):
    from django.urls import reverse
    item, evidence = _scoped_item()
    candidate = _candidate_for(item)
    url = reverse("intelligence:review-record-semantic-metadata", args=[candidate.pk])
    assert client.post(url, _form(evidence)).status_code == 403
    client.force_login(_reviewer(role=authz.OBSERVER, username="observer"))
    assert client.post(url, _form(evidence)).status_code == 403
    client.logout()
    client.force_login(_reviewer(role=authz.SYSTEM_ADMIN, username="admin"))
    assert client.post(url, _form(evidence)).status_code == 403
    client.logout()
    client.force_login(_reviewer(username="ok"))
    assert client.get(url).status_code == 405
    assert DecisionEvent.objects.count() == 0


# --- published reader path (what the reviewer surface actually reads) --------------

def test_published_reader_surfaces_the_bundle_and_its_metadata_history(client):
    from django.urls import reverse
    from .projection import rebuild_assertion_projections
    from .projection_reader import read_published_assertions
    item, evidence = _scoped_item()
    candidate = _candidate_for(item)
    reviewer = _reviewer()
    first = record_human_semantic_metadata(user=reviewer, payload=_payload(item, evidence))
    second = correct_human_semantic_metadata(user=reviewer, payload=_payload(
        item, evidence, bundle=_bundle(motifs=["LINE_ART"]),
        supersedes_event_id=first.event_id))
    rebuild_assertion_projections(apply=True)

    result = read_published_assertions(item)
    assert result.state == "CURRENT"
    current = result.current_by_domain[METADATA_ASSERTION_DOMAIN]
    assert current["normalized_value"]["motifs"] == ["LINE_ART"]
    assert current["event_id"] == second.event_id
    assert current["label"] == ""          # a bundle has no single label

    history = {entry["event_id"]: entry for entry in result.history}
    assert history[first.event_id]["domain"] == METADATA_ASSERTION_DOMAIN
    assert history[first.event_id]["superseded"] is True
    assert history[second.event_id]["effective"] is True

    # and the reviewer surface renders it
    client.force_login(reviewer)
    body = client.get(
        reverse("intelligence:review-detail", args=[candidate.pk])).content.decode()
    assert "CURRENT DESCRIPTIVE METADATA" in body
    assert second.event_id in body and first.event_id in body
    assert "LINE_ART" in body


def test_no_service_can_emit_an_unprojectable_intelligence_action():
    """The projector fails closed on any intelligence action it cannot project, so every
    such action must have a projector branch. Guards against re-adding a dangling action."""
    from .projection import INTELLIGENCE_ACTIONS, SUPPORTED_ACTIONS
    workflow_only = {authz.VIEW_INTELLIGENCE_REVIEW_QUEUE,
                     authz.CLAIM_INTELLIGENCE_REVIEW}
    assert INTELLIGENCE_ACTIONS - SUPPORTED_ACTIONS == workflow_only
    assert not hasattr(authz, "REQUEST_SEMANTIC_METADATA_CLARIFICATION")


# --- BUSINESS_OWNER: descriptive capability only (DIP-1C-5C Part I) ----------------

def test_business_owner_may_describe_but_gains_no_authority_from_authz_1_3():
    """`authz/1.3` gave BUSINESS_OWNER a DESCRIPTIVE action. It must not have widened that
    role's authority surface, and the vocabulary must make an authority claim unsayable
    regardless of who is speaking."""
    from .models import GovernanceDecisionProjection, OperationalPermissionProjection
    item, evidence = _scoped_item()
    owner = _reviewer(role=authz.BUSINESS_OWNER, username="owner")

    event = record_human_semantic_metadata(user=owner, payload=_payload(item, evidence))
    assert event.role_used == authz.BUSINESS_OWNER
    assert event.payload["assertion_domain"] == METADATA_ASSERTION_DOMAIN

    # the seniority of the role does not unlock a prohibited claim
    for claim in sorted(FORBIDDEN_BRAND_CLAIMS):
        with pytest.raises(AssertionValidationError):
            record_human_semantic_metadata(user=owner, payload=_payload(
                item, evidence, bundle=_bundle(brand_observations=[claim])))

    # authority actions are unchanged from authz/1.2 for this role
    for action in (authz.FINALIZE_CANONICAL_BRAND_ASSET,
                   authz.FINALIZE_PRIMARY_BRAND_PALETTE):
        assert authz.BUSINESS_OWNER not in authz.POLICY[action]
    for action, roles in authz.POLICY_V1_2.items():
        assert authz.POLICY[action] == roles      # 1.2 mapping frozen, not re-opened

    # and describing created no governance or permission state
    assert GovernanceDecisionProjection.objects.count() == 0
    assert OperationalPermissionProjection.objects.count() == 0
