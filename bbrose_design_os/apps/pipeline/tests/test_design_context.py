"""Phase 2A-3 — read-only DIP context adapter.

The properties under test: read-only in every sense, authorization from the caller's
identity with fail-soft denial, deterministic bounded query planning, labelled
descriptive-only references, and the production-input boundary — no reference may become
an input to anything downstream.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounts import authz_policy as authz
from apps.accounts.models import (
    DecisionEvent, GRANT_TEST_FIXTURE, ReviewerProfile, ReviewerRoleAssignment,
)
from apps.intelligence.models import (
    CorpusItem, EvidenceReference, GovernanceDecisionProjection,
    HistoricalDesignProfile, HumanAssertionProjection, OperationalPermissionProjection,
    ReviewCandidate, SourceArtifact,
)
from apps.pipeline.design_context import (
    CHANNEL_LIMITS, CONTEXT_SCHEMA, QUERY_PLAN_VERSION, REFERENCE_FIELDS,
    build_design_context, build_query_plan, context_hash, production_input_references,
    to_generator_entries,
)

pytestmark = pytest.mark.django_db
User = get_user_model()


def _brief(**changes):
    brief = {
        "brand": "BBROSE", "product_name": "Dew Serum",
        "product_category": "serum carton", "design_target": "packaging",
        "preferred_styles": ["engraved serif typography"],
        "preferred_colors": ["soft pink"],
    }
    brief.update(changes)
    return brief


def _reviewer(*, role=authz.DESIGN_REVIEWER, enabled=True, active=True, name=None):
    name = name or f"ctx-{User.objects.count()}"
    granter = User.objects.create_user(username=f"{name}-granter")
    user = User.objects.create_user(username=name, is_active=active)
    ReviewerProfile.objects.create(user=user, reviewer_enabled=enabled)
    ReviewerRoleAssignment.objects.create(
        user=user, role=role, granted_by=granter, granted_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=1),
        grant_source=GRANT_TEST_FIXTURE, grant_reason="context test")
    return user


def _corpus_item(kind, external_key, *, title=""):
    item = CorpusItem.objects.create(item_kind=kind, external_key=external_key)
    source = SourceArtifact.objects.create(
        source_identifier=f"src-{external_key}", source_location=f"logical:{external_key}",
        source_type=SourceArtifact.SourceType.FILE, sha256="a" * 64,
        parser_identifier="test", parser_version="1", source_schema_version="1")
    EvidenceReference.objects.create(
        corpus_item=item, source_artifact=source, evidence_kind="SOURCE_FILE",
        locator={"path": f"bounded/{external_key}.ai"},
        locator_schema_version="source_file/1.0", evidence_hash="b" * 64)
    if kind == CorpusItem.Kind.HISTORICAL_DESIGN:
        HistoricalDesignProfile.objects.create(
            corpus_item=item, primary_source_artifact=source,
            display_title=title or external_key, audit_status="MACHINE_AUDITED")
    return item


@pytest.fixture
def small_corpus():
    return {
        "historical": _corpus_item(CorpusItem.Kind.HISTORICAL_DESIGN,
                                   "historical:ctx:serum carton stand",
                                   title="Serum Carton Stand"),
        "asset": _corpus_item(CorpusItem.Kind.DESIGN_ASSET,
                              "asset:ctx:engraved serum pattern"),
        "font": _corpus_item(CorpusItem.Kind.FONT, "font:ctx:engraved serif face"),
        "brand": _corpus_item(CorpusItem.Kind.BRAND_ASSET, "brand:ctx:soft pink palette"),
    }


def _authority():
    return (DecisionEvent.objects.count(), HumanAssertionProjection.objects.count(),
            GovernanceDecisionProjection.objects.count(),
            OperationalPermissionProjection.objects.count())


# === query planning ===============================================================

def test_query_plan_is_deterministic_bounded_and_brief_driven():
    plan = build_query_plan(_brief())
    assert plan == build_query_plan(_brief())
    channels = [entry["channel"] for entry in plan]
    assert channels == ["HISTORICAL_DESIGN", "DESIGN_ASSET_METADATA",
                        "FONT_TECHNICAL", "BRAND_OR_PALETTE_CANDIDATE"]
    for entry in plan:
        assert entry["limit"] == CHANNEL_LIMITS[entry["channel"]]
        assert len(entry["query"]) <= 200

    # channels irrelevant to the brief are omitted, not padded
    minimal = build_query_plan(_brief(preferred_styles=[], preferred_colors=[]))
    assert [entry["channel"] for entry in minimal] == [
        "HISTORICAL_DESIGN", "DESIGN_ASSET_METADATA"]


def test_plan_uses_lexical_reviewer_search_defaults_only(small_corpus):
    """Every executed query flows through build_search_query defaults: reviewer-candidate
    mode, lexical ranking. Semantic encoding must never be touched."""
    import apps.intelligence.semantic_query as semantic_query

    def _boom(*args, **kwargs):
        raise AssertionError("semantic path must never be called by the context adapter")

    original = semantic_query.encode_semantic_query
    semantic_query.encode_semantic_query = _boom
    try:
        context = build_design_context(_reviewer(), _brief())
    finally:
        semantic_query.encode_semantic_query = original
    assert context["metadata"]["authorization"] == "AUTHORIZED"


# === authorization =================================================================

def test_an_actorless_or_inactive_caller_gets_an_empty_context_and_generation_continues():
    """§BH58(d) NARROWED THIS from five refused actor states to two.

    It used to refuse a plain user, a DISABLED reviewer and an OBSERVER as well, because
    this read was checked against `VIEW_INTELLIGENCE_REVIEW_QUEUE` — the reviewer gate.
    The owner ruled that apart: "Reading the house library to inform a design is not
    reviewing evidence, and a background job is not a person." Those three are asserted
    as ALLOWED in the test below; these two still refuse, because identity was never the
    thing being removed.
    """
    from django.contrib.auth.models import AnonymousUser
    for actor, reason in ((AnonymousUser(), "DENIED:PIPELINE_NO_ACTOR"),
                          (_reviewer(active=False, name="inactive"),
                           "DENIED:PIPELINE_ACTOR_INACTIVE")):
        context = build_design_context(actor, _brief())
        assert context["references"] == []
        assert context["metadata"]["authorization"] == reason
        assert any(w.startswith("CONTEXT_UNAVAILABLE_UNAUTHORIZED")
                   for w in context["warnings"])
        # and the empty context still satisfies the schema + boundary
        assert context["schema_version"] == CONTEXT_SCHEMA
        assert production_input_references(context) == []
        assert to_generator_entries(context) == []


def test_review_authority_is_no_longer_required_to_read_the_house_library(small_corpus):
    """§BH58(d), the other half, and the one that measures what changed.

    Each of these three was refused before with DENIED:REVIEWER_DISABLED or
    DENIED:REVIEWER_PROFILE_MISSING or DENIED:ROLE_NOT_AUTHORIZED. The owner's own account
    is the middle case — authenticated, active, reviewer profile disabled, no roles — and
    it is why every run of his brief saw an empty context.

    Reviewing itself is untouched; `apps/accounts/test_authorization.py` asserts that all
    45 reviewer actions still require reviewer standing.
    """
    for actor in (User.objects.create_user(username="plain-user"),
                  _reviewer(enabled=False, name="disabled"),
                  _reviewer(role=authz.OBSERVER, name="observer")):
        context = build_design_context(actor, _brief())
        assert context["metadata"]["authorization"] == "AUTHORIZED"
        # the read stays a READ: the boundary the context contract owns does not move
        assert production_input_references(context) == []


def test_identity_comes_from_the_caller_never_from_the_brief(small_corpus):
    """A brief cannot smuggle an actor: unknown brief fields are refused before any
    query, so 'user_id'/'role' in brief data never reach authorization."""
    from apps.pipeline.design_intent import DesignIntentError
    with pytest.raises(DesignIntentError):
        build_design_context(_reviewer(), _brief(role="BRAND_ADMIN"))
    with pytest.raises(DesignIntentError):
        build_design_context(_reviewer(), _brief(user_id=1))


# === references ====================================================================

def test_authorized_reviewer_gets_bounded_labelled_descriptive_references(small_corpus):
    context = build_design_context(_reviewer(), _brief())
    assert context["schema_version"] == CONTEXT_SCHEMA
    assert context["query_plan_version"] == QUERY_PLAN_VERSION
    references = context["references"]
    assert references, "expected matches from the seeded corpus"
    ids = {reference["corpus_item_id"] for reference in references}
    assert str(small_corpus["historical"].pk) in ids
    for reference in references:
        assert set(reference) == set(REFERENCE_FIELDS)
        assert reference["reference_use"] == "DESCRIPTIVE_REFERENCE_ONLY"
        assert reference["provenance"] in ("MACHINE_DERIVED", "HUMAN_VERIFIED")
        # nothing human-verified exists in this corpus: no published projection
        assert reference["provenance"] == "MACHINE_DERIVED"
        assert reference["operational_permission_state"] == "ALL_DENIED"
        assert "/" not in reference["display_label"]
        assert reference["summary"]
    historical = next(r for r in references
                      if r["corpus_item_id"] == str(small_corpus["historical"].pk))
    assert "reference memory only" in historical["summary"]
    assert "layout may not be copied" in historical["summary"]


def test_limits_dedup_and_dataset_diversity_hold(small_corpus):
    for index in range(6):                       # exceed the historical channel limit
        _corpus_item(CorpusItem.Kind.HISTORICAL_DESIGN,
                     f"historical:ctx:serum carton extra {index}",
                     title=f"Serum Carton Extra {index}")
    context = build_design_context(_reviewer(), _brief())
    historical = [r for r in context["references"]
                  if r["item_kind"] == "HISTORICAL_DESIGN"]
    assert len(historical) <= CHANNEL_LIMITS["HISTORICAL_DESIGN"]
    all_ids = [r["corpus_item_id"] for r in context["references"]]
    assert len(all_ids) == len(set(all_ids)), "duplicate corpus items in context"
    per_dataset = {}
    for r in historical:
        per_dataset[r["dataset_lineage"]] = per_dataset.get(r["dataset_lineage"], 0) + 1
    assert all(count <= 2 for count in per_dataset.values())
    # every seeded historical item shares one dataset lineage, so the diversity cap (2)
    # binds before the channel limit (3) — the exclusions land under dataset_cap
    excluded = context["metadata"]["excluded"]
    assert excluded.get("dataset_cap", 0) + excluded.get("over_limit", 0) >= 1
    assert len(historical) == 2


def test_empty_corpus_is_a_valid_empty_context():
    context = build_design_context(_reviewer(), _brief())
    assert context["references"] == []
    assert "CONTEXT_EMPTY" in context["warnings"]
    assert context["metadata"]["included"] == 0
    assert context["metadata"]["context_hash"] == context_hash(context)


def test_context_hash_is_deterministic(small_corpus):
    user = _reviewer()
    first = build_design_context(user, _brief())
    second = build_design_context(user, _brief())
    assert first["metadata"]["context_hash"] == second["metadata"]["context_hash"]


# === the production-input boundary =================================================

def test_no_reference_carries_a_loadable_identity(small_corpus):
    context = build_design_context(_reviewer(), _brief())
    serialized = str(context)
    assert "source_hash_summary" not in serialized
    assert "detail_url" not in serialized
    assert "locator" not in serialized
    assert "/intelligence/" not in serialized      # no navigable handle
    assert "materials/" not in serialized
    assert production_input_references(context) == []


def test_blocked_references_stay_visibly_blocked_through_to_the_generator(small_corpus):
    from apps.intelligence.evidence_integrity import EvidenceIntegrityResolver

    class Blocking:
        blocks_evidence_dependent_claims = True
        status = "REVIEW_REQUIRED"

    original = EvidenceIntegrityResolver.evaluate
    # integrity signals surface in search rows via readiness; simulate a blocked row by
    # marking the reference flags directly through the adapter's own row mapping
    from apps.pipeline.design_context import _reference_from_row
    row = {
        "corpus_item_id": "x" * 8, "item_kind": "BRAND_ASSET",
        "display_label": "observed palette", "dataset_identifier": "dip0c3",
        "identity_state": "RESOLVED", "readiness_state": "REVIEW_REQUIRED",
        "evidence_integrity_state": "REVIEW_REQUIRED", "blocker_codes": ["INTEGRITY"],
        "governance_status": "NOT_BUILT", "human_assertion_status": "STALE",
        "retrieval": {"allowed": False}, "automatic_use": {"allowed": False},
    }
    reference = _reference_from_row(row, "BRAND_OR_PALETTE_CANDIDATE", "palette")
    assert reference["blocked"] is True
    assert "EVIDENCE_INTEGRITY_BLOCKED" in reference["flags"]
    assert reference["provenance"] == "MACHINE_DERIVED"
    entries = to_generator_entries({"references": [reference]})
    assert entries[0]["blocked"] is True
    assert "EVIDENCE_INTEGRITY_BLOCKED" in entries[0]["note"]
    assert original is EvidenceIntegrityResolver.evaluate


# === generator integration =========================================================

def test_generator_receives_context_in_one_call_and_rules_stay_enforced(small_corpus):
    import json as _json

    from apps.pipeline.design_direction_generator import generate_design_directions

    from .direction_fixtures import valid_document

    context = build_design_context(_reviewer(), _brief())
    entries = to_generator_entries(context)

    calls = []
    def fake(system, content):
        calls.append(content)
        return _json.dumps(valid_document()), "fake:model"

    result = generate_design_directions(
        brief=_brief(), dip_context=entries, call_model=fake)
    assert result.ok and len(calls) == 1
    text = calls[0] if isinstance(calls[0], str) else calls[0][-1]["text"]
    assert "QUOTED DESCRIPTIVE DATA" in text
    assert "<<references>>" in text and "<<end references>>" in text
    assert "never carry an exact source composition" in text
    # distinctness stays active with context present
    assert len(result.document["directions"]) == 3


def test_no_context_and_unavailable_context_both_generate_fine():
    import json as _json

    from apps.pipeline.design_direction_generator import generate_design_directions

    from .direction_fixtures import valid_document
    for entries in ([], to_generator_entries(
            build_design_context(User.objects.create_user(username="nobody"), _brief()))):
        result = generate_design_directions(
            brief=_brief(), dip_context=entries,
            call_model=lambda s, c: (_json.dumps(valid_document()), "fake:model"))
        assert result.ok


# === read-only =====================================================================

def test_the_adapter_writes_nothing(small_corpus):
    candidate_states = list(ReviewCandidate.objects.values_list("pk", "workflow_status"))
    before = _authority()
    build_design_context(_reviewer(name="readonly"), _brief())
    assert _authority() == before
    assert list(ReviewCandidate.objects.values_list(
        "pk", "workflow_status")) == candidate_states
