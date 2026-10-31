"""DIP-1C-6A — safe in-browser artwork previews.

The security tests carry most of the weight. A preview endpoint is a file-serving surface
bolted onto a review page, and the failure modes are the classic ones: traversal, symlink
escape, serving the original bytes, and a caller-supplied path. Each has a test that would
fail loudly if the boundary were removed.
"""
from __future__ import annotations

import hashlib
import os

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
import pytest

from apps.accounts import authz_policy as authz
from apps.accounts.models import (
    DecisionEvent, GRANT_TEST_FIXTURE, ReviewerProfile, ReviewerRoleAssignment,
)

from . import artwork_preview as preview
from .artwork_preview import (
    AVAILABLE, NOT_RENDERABLE, SOURCE_UNAVAILABLE, UNSUPPORTED_FORMAT, PreviewError,
    build_identity, preview_status, render_preview, resolve_source_path,
)
from .models import (
    CorpusItem, EvidenceReference, GovernanceDecisionProjection, HistoricalDesignProfile,
    HumanAssertionProjection, OperationalPermissionProjection, ReviewCandidate,
    SourceArtifact,
)
from .review_manifest import MANIFEST_ID

pytestmark = pytest.mark.django_db
User = get_user_model()
PNG_MAGIC = b"\x89PNG"

# A one-page PDF is the smallest honest stand-in for a PDF-backed .ai: same renderer path,
# no binary fixture committed to the repository.
MINIMAL_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 100]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n"
)


@pytest.fixture
def sandbox(tmp_path, settings):
    """A configured source root that is NOT the real repository, so nothing here can touch
    `materials/`."""
    root = tmp_path / "root"
    (root / "materials").mkdir(parents=True)
    settings.INTELLIGENCE_SOURCE_ROOTS = {"repository": root}
    settings.INTELLIGENCE_ALLOWED_SOURCE_PREFIXES = {"repository": ("materials",)}
    settings.INTELLIGENCE_PREVIEW_ROOT = tmp_path / "previews"
    return root


def _reviewer(*, role=authz.DESIGN_REVIEWER, enabled=True, active=True, name=None):
    name = name or f"prev-{User.objects.count()}"
    granter = User.objects.create_user(username=f"{name}-granter")
    user = User.objects.create_user(username=name, is_active=active)
    ReviewerProfile.objects.create(user=user, reviewer_enabled=enabled)
    ReviewerRoleAssignment.objects.create(
        user=user, role=role, granted_by=granter, granted_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=1),
        grant_source=GRANT_TEST_FIXTURE, grant_reason="preview test")
    return user


def _item(sandbox, *, filename="design.ai", payload=MINIMAL_PDF, relative=None,
          declared_hash=None, is_test_only=False):
    path = sandbox / "materials" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    item = CorpusItem.objects.create(
        item_kind=CorpusItem.Kind.HISTORICAL_DESIGN,
        external_key=f"historical:preview:{filename}")
    source = SourceArtifact.objects.create(
        source_identifier=f"src-{filename}",
        source_location=f"repository:{relative or f'materials/{filename}'}",
        source_type=SourceArtifact.SourceType.FILE,
        sha256=declared_hash or hashlib.sha256(payload).hexdigest(),
        parser_identifier="test", parser_version="1", source_schema_version="1")
    HistoricalDesignProfile.objects.create(
        corpus_item=item, primary_source_artifact=source,
        display_title="Preview fixture", audit_status="MACHINE_AUDITED")
    reference = EvidenceReference.objects.create(
        corpus_item=item, source_artifact=source, evidence_kind="SOURCE_FILE",
        locator={"path": relative or f"materials/{filename}"},
        locator_schema_version="source_file/1.0", evidence_hash="ab" * 32,
        is_test_only=is_test_only)
    candidate = ReviewCandidate.objects.create(
        corpus_item=item, review_type=ReviewCandidate.ReviewType.HISTORICAL_MEMORY,
        priority=50, review_manifest_id=MANIFEST_ID, machine_confidence_summary={})
    return item, source, reference, candidate


def _authority():
    return (DecisionEvent.objects.count(), HumanAssertionProjection.objects.count(),
            GovernanceDecisionProjection.objects.count(),
            OperationalPermissionProjection.objects.count())


# === source boundary =============================================================

def test_traversal_absolute_and_unconfigured_roots_are_refused(sandbox):
    _, source, _, _ = _item(sandbox)
    for location, expected in [
        ("repository:../outside.ai", SOURCE_UNAVAILABLE),
        ("repository:/etc/passwd", SOURCE_UNAVAILABLE),
        ("repository:materials/../../escape.ai", SOURCE_UNAVAILABLE),
        ("elsewhere:materials/design.ai", SOURCE_UNAVAILABLE),
        ("materials/design.ai", SOURCE_UNAVAILABLE),          # no root name at all
        ("repository:var/design_intelligence/secret.ai", SOURCE_UNAVAILABLE),
    ]:
        source.source_location = location
        with pytest.raises(PreviewError) as exc:
            resolve_source_path(source)
        assert exc.value.status == expected, location


def test_a_symlink_escaping_the_root_is_refused(sandbox, tmp_path):
    secret = tmp_path / "outside-the-root.ai"
    secret.write_bytes(MINIMAL_PDF)
    link = sandbox / "materials" / "link.ai"
    os.symlink(secret, link)
    _, source, _, _ = _item(sandbox, filename="other.ai")
    source.source_location = "repository:materials/link.ai"
    with pytest.raises(PreviewError) as exc:
        resolve_source_path(source)
    # resolve() follows the link, so the containment check sees the real location
    assert exc.value.status == SOURCE_UNAVAILABLE


def test_changed_source_bytes_are_refused_rather_than_attributed(sandbox):
    _, source, reference, _ = _item(sandbox, declared_hash="00" * 32)
    with pytest.raises(PreviewError) as exc:
        render_preview(reference, use_cache=False)
    assert exc.value.status == "HASH_MISMATCH"


def test_unsupported_and_test_only_sources_are_refused(sandbox):
    _, _, reference, _ = _item(sandbox, filename="notes.txt", payload=b"plain text")
    with pytest.raises(PreviewError) as exc:
        render_preview(reference, use_cache=False)
    assert exc.value.status == UNSUPPORTED_FORMAT

    _, _, test_only, _ = _item(sandbox, filename="fixture.ai", is_test_only=True)
    with pytest.raises(PreviewError) as exc:
        render_preview(test_only, use_cache=False)
    assert exc.value.status == "REVIEW_REQUIRED"


# === identity and cache ==========================================================

def test_preview_identity_binds_the_source_hash(sandbox):
    _, source, reference, _ = _item(sandbox)
    first = build_identity(reference)
    assert first.source_sha256 == source.sha256
    source.sha256 = "cd" * 32
    source.save()
    reference.refresh_from_db()
    second = build_identity(
        EvidenceReference.objects.select_related("source_artifact").get(pk=reference.pk))
    assert second.cache_key() != first.cache_key(), "cache identity ignored the source hash"


def test_render_caches_atomically_and_reuses_the_cache(sandbox):
    _, _, reference, _ = _item(sandbox)
    payload, identity = render_preview(reference)
    assert payload[:4] == PNG_MAGIC
    cached = identity.cache_path()
    assert cached.is_file() and cached.read_bytes() == payload
    assert preview.preview_root() in cached.parents
    # a second call reuses the file rather than re-rendering
    marker = b"\x89PNG" + b"CACHED-MARKER" + payload[17:]
    cached.write_bytes(marker)
    again, _ = render_preview(reference)
    assert again == marker
    assert not list(cached.parent.glob("*.part")), "a temporary file was left behind"


def test_a_failed_render_never_replaces_a_valid_cached_preview(sandbox):
    _, source, reference, _ = _item(sandbox)
    payload, identity = render_preview(reference)
    cached = identity.cache_path()
    assert cached.is_file()

    # corrupt the source so rendering fails, and ask for a fresh render
    path = sandbox / "materials" / "design.ai"
    path.write_bytes(b"not a pdf at all")
    with pytest.raises(PreviewError):
        render_preview(reference, use_cache=False)
    assert cached.read_bytes() == payload, "a failed render overwrote a valid preview"


def test_previews_are_written_only_under_the_configured_preview_root(sandbox, settings):
    _, _, reference, _ = _item(sandbox)
    _, identity = render_preview(reference)
    assert str(identity.cache_path()).startswith(str(settings.INTELLIGENCE_PREVIEW_ROOT))
    # nothing was written beside the source
    assert sorted(p.name for p in (sandbox / "materials").iterdir()) == ["design.ai"]


def test_source_bytes_are_never_modified(sandbox):
    _, source, reference, _ = _item(sandbox)
    path = sandbox / "materials" / "design.ai"
    before = (path.read_bytes(), path.stat().st_mtime_ns)
    render_preview(reference)
    render_preview(reference, use_cache=False)
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


# === status cards ================================================================

def test_status_reports_honestly_without_rendering(sandbox):
    _, _, ok_reference, _ = _item(sandbox)
    card = preview_status(ok_reference)
    assert card["status"] == AVAILABLE
    assert card["source_sha256_prefix"] == ok_reference.source_artifact.sha256[:12]
    assert len(card["source_sha256_prefix"]) == 12
    assert card["cached"] is False                # status must not render

    _, source, missing, _ = _item(sandbox, filename="gone.ai")
    (sandbox / "materials" / "gone.ai").unlink()
    assert preview_status(missing)["status"] == SOURCE_UNAVAILABLE

    _, _, unsupported, _ = _item(sandbox, filename="thing.txt", payload=b"x")
    assert preview_status(unsupported)["status"] == UNSUPPORTED_FORMAT


def test_a_page_unit_is_marked_as_a_view_not_a_separate_artwork(sandbox):
    _, source, _, _ = _item(sandbox, filename="multi.ai")
    unit = EvidenceReference.objects.create(
        corpus_item=CorpusItem.objects.get(external_key="historical:preview:multi.ai"),
        source_artifact=source, evidence_kind="FILE_PAGE_UNIT",
        locator={"page": 0, "unit_key": "multi-p0-u01"},
        locator_schema_version="file_page/1.0", evidence_hash="ee" * 32)
    card = preview_status(unit)
    assert card["is_page_view"] is True
    assert card["unit_identity"] == "page:0"
    source_card = preview_status(EvidenceReference.objects.get(
        source_artifact=source, evidence_kind="SOURCE_FILE"))
    assert source_card["is_page_view"] is False
    assert source_card["unit_identity"] == "source"


# === endpoint ====================================================================

def test_preview_endpoint_requires_an_authorized_active_enabled_reviewer(sandbox, client):
    _, _, reference, candidate = _item(sandbox)
    url = reverse("intelligence:review-evidence-preview", args=[candidate.pk, reference.pk])
    assert client.get(url).status_code == 403               # unauthenticated
    for user in (_reviewer(active=False, name="inactive"),
                 _reviewer(enabled=False, name="disabled"),
                 _reviewer(role=authz.OBSERVER, name="observer")):
        client.force_login(user)
        assert client.get(url).status_code == 403
        client.logout()


def test_preview_endpoint_serves_png_only_and_never_the_original_bytes(sandbox, client):
    _, _, reference, candidate = _item(sandbox)
    client.force_login(_reviewer(name="ok"))
    response = client.get(reverse(
        "intelligence:review-evidence-preview", args=[candidate.pk, reference.pk]))
    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Content-Disposition"] == "inline"
    assert response.content[:4] == PNG_MAGIC
    assert MINIMAL_PDF not in response.content
    assert b"%PDF" not in response.content[:64]


def test_an_evidence_reference_from_another_item_is_not_reachable(sandbox, client):
    _, _, _, candidate = _item(sandbox)
    _, _, other_reference, _ = _item(sandbox, filename="elsewhere.ai")
    client.force_login(_reviewer(name="cross"))
    response = client.get(reverse(
        "intelligence:review-evidence-preview",
        args=[candidate.pk, other_reference.pk]))
    assert response.status_code == 404


def test_a_failed_preview_returns_a_status_not_a_broken_image_or_a_path(sandbox, client):
    _, _, reference, candidate = _item(sandbox, filename="broken.ai", payload=b"garbage")
    client.force_login(_reviewer(name="broken"))
    response = client.get(reverse(
        "intelligence:review-evidence-preview", args=[candidate.pk, reference.pk]))
    assert response.status_code == 422
    body = response.content.decode()
    assert body == NOT_RENDERABLE
    assert "/" not in body and "materials" not in body


def test_the_review_page_shows_visual_evidence_and_stays_read_only(sandbox, client):
    _, _, reference, candidate = _item(sandbox)
    client.force_login(_reviewer(name="page"))
    before = _authority()
    body = client.get(reverse(
        "intelligence:review-detail", args=[candidate.pk])).content.decode()
    assert "VISUAL EVIDENCE" in body
    assert "VISUAL PREVIEW IS FOR DESCRIPTIVE REVIEW ONLY. IT DOES NOT AUTHORIZE USE." in body
    assert str(reference.pk) in body
    # the bound applies to the VISUAL EVIDENCE cards. The pre-existing
    # EVIDENCE-INTEGRITY section separately renders full dataset hashes, which is
    # existing technical-evidence display and out of scope here.
    section = body.split("VISUAL EVIDENCE", 1)[1].split("</section>", 1)[0]
    assert reference.source_artifact.sha256[:12] in section
    assert reference.source_artifact.sha256 not in section     # bounded prefix only
    assert str(sandbox) not in body                            # no absolute path anywhere
    assert _authority() == before
    assert ReviewCandidate.objects.get(pk=candidate.pk).workflow_status == (
        candidate.workflow_status)


def test_an_unavailable_preview_is_stated_rather_than_shown_as_an_image(sandbox, client):
    _, _, reference, candidate = _item(sandbox, filename="missing.ai")
    (sandbox / "materials" / "missing.ai").unlink()
    client.force_login(_reviewer(name="unavailable"))
    body = client.get(reverse(
        "intelligence:review-detail", args=[candidate.pk])).content.decode()
    assert SOURCE_UNAVAILABLE in body
    assert "Visual review cannot be completed in the browser" in body
    # and no <img> was emitted for it
    assert f"preview/{reference.pk}/" not in body
