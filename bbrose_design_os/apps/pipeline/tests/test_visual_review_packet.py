"""web_reference_visual_review_packet/1.0 — §14 contract tests.

Section integrity, provenance, honest unavailability, styling
classification, permission invariance, governed single-image acquisition.
"""
from __future__ import annotations

import io
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.pipeline.models import (DesignProject, DesignTask, WebAccessRecord,
                                  WebResearchSession)
from apps.pipeline.services import visual_review as vr

User = get_user_model()


def _png_bytes(seed=0):
    """A photo-like image (noise) so it clears the tracking-pixel size
    filter, as any real product photograph would."""
    import random

    from PIL import Image
    rnd = random.Random(seed)
    img = Image.new("RGB", (320, 240))
    img.putdata([(rnd.randrange(256), rnd.randrange(256),
                  rnd.randrange(256)) for _ in range(320 * 240)])
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


class _FakeResponse:
    def __init__(self, status=200, headers=None, body=b""):
        self.status_code = status
        self.headers = headers or {}
        self._body = body

    def iter_content(self, chunk_size=65536):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    def close(self):
        pass


class VisualReviewTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="vrp_")
        self.session = WebResearchSession.objects.create(
            product_identity="x", modes=[], status="AWAITING_HUMAN_REVIEW")
        img = Path(self.tmp) / "a.png"
        img.write_bytes(_png_bytes())
        self.analog = self.session.sources.create(
            original_url="https://sup.example/a", classification="analog",
            title="supplier bottle", source_tier=6,
            reference_view_permission=True)
        self.analog.extraction_warnings.append(
            {"kind": "representative_visual", "image_url":
             "https://sup.example/img.png",
             "declared_by_page": "https://sup.example/a",
             "quarantine_path": str(img), "content_sha256": "x",
             "provenance": "og image"})
        self.analog.save()
        self.insp = self.session.sources.create(
            original_url="https://gal.example/b",
            classification="inspiration", title="gallery", source_tier=6,
            reference_view_permission=True)
        self.weapon = self.session.sources.create(
            original_url="https://guns.example/r", classification="image",
            title="rifle", source_tier=6, human_review_state="REJECTED")
        self.brand = self.session.sources.create(
            original_url="https://mkt.example/44", classification="image",
            title="third-party brand", source_tier=6, mime_type="image/png",
            quarantine_path=str(img),
            human_review_state="NEEDS_VERIFICATION")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _entries(self):
        style = ("Styling analysis",
                 f"reflections and shadows = {vr.STYLING_LABEL}")
        return [
            {"source_id": self.analog.id, "domain": "sup.example",
             "section": "A",
             "quarantine_path": self.analog.extraction_warnings[-1][
                 "quarantine_path"],
             "banners": [(vr.NOT_EXACT_LABEL, (26, 82, 118))],
             "fields": [("Archetype", "dropper"), style],
             "footnotes": [], "decision_options": ["APPROVE AS PHYSICAL "
                                                   "ANALOG", "REJECT"]},
            {"source_id": self.insp.id, "domain": "gal.example",
             "section": "C", "quarantine_path": None,
             "banners": [(vr.REFERENCE_ONLY_LABEL, (120, 66, 18))],
             "fields": [("Influence", "palette"), style],
             "footnotes": [], "decision_options": ["APPROVE AS VISUAL "
                                                   "INSPIRATION", "REJECT"]},
            {"source_id": self.brand.id, "domain": "mkt.example",
             "section": "E", "quarantine_path": self.brand.quarantine_path,
             "banners": [("BRAND IDENTITY VERIFICATION REQUIRED",
                          (140, 20, 20))],
             "fields": [("Why unverified", "unknown relationship")],
             "footnotes": [], "decision_options": ["NEEDS_VERIFICATION "
                                                   "(keep)", "REJECT"]},
        ]

    def test_packet_sections_provenance_and_honest_unavailability(self):
        before = vr.permission_snapshot(self.session)
        p_before = (DesignProject.objects.count(), DesignTask.objects.count())
        with patch("apps.pipeline.agents.image_producer.openai") as prov:
            manifest = vr.build_visual_review_packet(
                self.session, self._entries(), ["archetype line"],
                ["decision line"], Path(self.tmp) / "out")
        assert not prov.mock_calls
        assert manifest["sections"]["A"] == [self.analog.id]
        assert manifest["sections"]["C"] == [self.insp.id]
        assert manifest["sections"]["E"] == [self.brand.id]
        assert self.weapon.id not in sum(manifest["sections"].values(), [])
        # unavailable visual is honest — no substitute image
        assert self.insp.id in manifest["missing_visual_source_ids"]
        assert self.analog.id in manifest["represented_source_ids"]
        assert Path(manifest["pdf"]).is_file()
        assert Path(manifest["png"]).is_file()
        template = json.loads(Path(manifest["json"]).read_text())
        assert all(v["decision"] is None
                   for v in template["decisions"].values())
        assert template["archetype_choice"]["decision"] is None
        # §11 permission invariance + nothing created
        assert vr.permission_snapshot(self.session) == before
        assert (DesignProject.objects.count(),
                DesignTask.objects.count()) == p_before
        self.analog.refresh_from_db()
        assert self.analog.provider_input_permission is False
        assert self.analog.artwork_reuse_permission is False
        assert self.analog.design_memory_permission is False

    def test_rejected_source_refused_as_candidate(self):
        entries = self._entries()
        entries[0]["source_id"] = self.weapon.id
        entries[0]["quarantine_path"] = None
        with pytest.raises(vr.VisualReviewError) as exc:
            vr.validate_entries(self.session, entries)
        assert exc.value.code == vr.VISUAL_REVIEW_SOURCE_IMAGE_MISMATCH

    def test_wrong_image_provenance_refused(self):
        stray = Path(self.tmp) / "stray.png"
        stray.write_bytes(_png_bytes(3))
        entries = self._entries()
        entries[0]["quarantine_path"] = str(stray)   # not recorded provenance
        with pytest.raises(vr.VisualReviewError) as exc:
            vr.validate_entries(self.session, entries)
        assert exc.value.code == vr.VISUAL_REVIEW_PROVENANCE_MISSING

    def test_classification_mixing_refused(self):
        entries = self._entries()
        entries[1]["section"] = "A"                  # inspiration into analogs
        with pytest.raises(vr.VisualReviewError) as exc:
            vr.validate_entries(self.session, entries)
        assert exc.value.code == vr.VISUAL_REVIEW_CLASSIFICATION_MIXED

    def test_missing_styling_classification_refused(self):
        entries = self._entries()
        entries[0]["fields"] = [("Archetype", "dropper")]
        with pytest.raises(vr.VisualReviewError) as exc:
            vr.validate_entries(self.session, entries)
        assert exc.value.code == vr.PHOTOGRAPHIC_STYLING_MISCLASSIFIED

    def test_acquisition_is_single_image_and_governed(self):
        page = ('<html><head><meta property="og:image" '
                'content="https://sup2.example/hero.png"/></head>'
                '<img src="https://sup2.example/other.png"></html>')
        responses = {
            "https://sup2.example/p": _FakeResponse(
                headers={"content-type": "text/html"},
                body=page.encode()),
            "https://sup2.example/hero.png": _FakeResponse(
                headers={"content-type": "image/png"},
                body=_png_bytes(1)),
        }

        def http_get(url, *, headers, timeout):
            resp = responses.get(url)
            if resp is None:
                raise AssertionError(f"unexpected fetch {url}")
            return resp

        src = self.session.sources.create(
            original_url="https://sup2.example/p", classification="analog",
            title="s2", source_tier=6)
        with override_settings(WEB_QUARANTINE_ROOT=self.tmp), \
                patch("apps.pipeline.services.web_research.check_url_policy"):
            rec = vr.acquire_representative_visual(
                self.session, src, http_get=http_get,
                robots=lambda url, ua: "allowed")
            # idempotent — no second fetch
            rec2 = vr.acquire_representative_visual(
                self.session, src, http_get=http_get,
                robots=lambda url, ua: "allowed")
        assert rec is not None and rec2 == rec
        assert rec["image_url"] == "https://sup2.example/hero.png"
        assert Path(rec["quarantine_path"]).is_file()
        assert WebAccessRecord.objects.filter(
            session=self.session, kind="image_fetch",
            url="https://sup2.example/hero.png").count() == 1

    def test_an_images_own_host_refusing_is_obeyed(self):
        """§BH71 PART 2: the image's own url is asked of its host's robots.txt — it was fetched unasked."""
        page = ('<html><head><meta property="og:image" '
                'content="https://cdn.refusing.example/hero.png"/></head></html>')

        def http_get(url, *, headers, timeout):
            if url == "https://sup3.example/p":
                return _FakeResponse(headers={"content-type": "text/html"}, body=page.encode())
            raise AssertionError(f"must not fetch {url}")

        def robots(url, ua):
            if "refusing" in url:
                return "disallowed"
            return "allowed"
        src = self.session.sources.create(
            original_url="https://sup3.example/p", classification="analog", title="s3", source_tier=6)
        with override_settings(WEB_QUARANTINE_ROOT=self.tmp), \
                patch("apps.pipeline.services.web_research.check_url_policy"):
            rec = vr.acquire_representative_visual(self.session, src, http_get=http_get, robots=robots)
        assert rec is None
        assert WebAccessRecord.objects.filter(
            session=self.session, kind="policy_block", url="https://cdn.refusing.example/hero.png",
            outcome="WEB_ROBOTS_DISALLOWED").exists()

    def test_acquisition_respects_robots(self):
        src = self.session.sources.create(
            original_url="https://denied.example/p",
            classification="analog", title="d", source_tier=6)
        with patch("apps.pipeline.services.web_research.check_url_policy"):
            rec = vr.acquire_representative_visual(
                self.session, src,
                http_get=lambda url, *, headers, timeout: (_ for _ in ()
                                                           ).throw(
                    AssertionError("must not fetch")),
                robots=lambda url, ua: "disallowed")
        assert rec is None
        assert WebAccessRecord.objects.filter(
            session=self.session, kind="policy_block",
            url="https://denied.example/p").exists()

    def _v11_entries(self, *, usable_insp=False):
        style = ("Styling analysis",
                 f"reflections and shadows = {vr.STYLING_LABEL}")
        insp_path = None
        if usable_insp:
            img = Path(self.tmp) / "insp.png"
            img.write_bytes(_png_bytes(7))
            self.insp.extraction_warnings.append(
                {"kind": "representative_visual",
                 "image_url": "https://gal.example/i.png",
                 "declared_by_page": "https://gal.example/b",
                 "quarantine_path": str(img), "content_sha256": "y",
                 "provenance": "og image"})
            self.insp.save()
            insp_path = str(img)
        return [
            {"source_id": self.analog.id, "domain": "sup.example",
             "section": "A",
             "quarantine_path": self.analog.extraction_warnings[0][
                 "quarantine_path"],
             "banners": [(vr.NOT_EXACT_LABEL, (26, 82, 118))],
             "fields": [("Archetype", "dropper"), style], "footnotes": [],
             "decision_options": ["APPROVE AS PHYSICAL ANALOG", "REJECT"]},
            {"source_id": self.insp.id, "domain": "gal.example",
             "section": "B", "quarantine_path": insp_path,
             "banners": [(vr.REFERENCE_ONLY_LABEL, (120, 66, 18))],
             "fields": [("Influence", "palette"), style], "footnotes": [],
             "decision_options": ["APPROVE AS VISUAL INSPIRATION",
                                  "REJECT"]},
            {"source_id": self.brand.id, "domain": "mkt.example",
             "section": "C", "quarantine_path": self.brand.quarantine_path,
             "banners": [("BRAND IDENTITY VERIFICATION REQUIRED",
                          (140, 20, 20))],
             "fields": [("Why unverified", "unknown")], "footnotes": [],
             "decision_options": ["NEEDS_VERIFICATION (keep)", "REJECT"]},
            {"source_id": self.textonly.id, "domain": "old.example",
             "section": "D", "quarantine_path": None,
             "banners": [("TEXT-ONLY — NOT A VISUAL CANDIDATE",
                          (105, 105, 105))],
             "fields": [("Why no visual", "logo only")], "footnotes": [],
             "decision_options": []},
        ]

    def _make_textonly(self):
        self.textonly = self.session.sources.create(
            original_url="https://old.example/t", classification="analog",
            title="text-only historical", source_tier=6,
            reference_view_permission=True)

    def test_v11_counts_exclude_empty_cards_and_warning(self):
        self._make_textonly()
        entries = self._v11_entries(usable_insp=False)
        manifest = vr.build_visual_review_packet(
            self.session, entries, ["a"], ["d"], Path(self.tmp) / "v11",
            section_config=vr.SECTIONS_V11, appendix=("D",),
            schema_version=vr.PACKET_SCHEMA_V11, file_prefix="corr_test")
        c = manifest["counts"]
        # the empty inspiration card is NOT counted as reviewable; the
        # warning source is NOT a pilot candidate; text-only is separate
        assert c["usable_pilot_candidate_visuals"] == 1
        assert c["visually_reviewable_analogs"] == 1
        assert c["visually_reviewable_inspirations"] == 0
        assert c["missing_visual_evidence"] == 1
        assert c["excluded_warning_visuals"] == 1
        assert c["text_only_sources"] == 1
        assert manifest["status"] == vr.PARTIALLY_COMPLETE
        template = json.loads(Path(manifest["json"]).read_text())
        assert str(self.brand.id) not in template["decisions"]
        assert str(self.textonly.id) not in template["decisions"]
        assert manifest["text_only_source_ids"] == [self.textonly.id]

    def test_v11_complete_when_all_candidates_have_visuals(self):
        self._make_textonly()
        entries = self._v11_entries(usable_insp=True)
        manifest = vr.build_visual_review_packet(
            self.session, entries, ["a"], ["d"], Path(self.tmp) / "v11c",
            section_config=vr.SECTIONS_V11, appendix=("D",),
            schema_version=vr.PACKET_SCHEMA_V11, file_prefix="corr_test2")
        assert manifest["status"] == "VISUAL_REVIEW_PACKET_COMPLETE"
        assert manifest["counts"]["missing_visual_evidence"] == 0

    def test_v11_appendix_must_stay_text_only(self):
        self._make_textonly()
        entries = self._v11_entries()
        # attaching ANY image to the historical text-only source is refused
        entries[3]["quarantine_path"] = self.analog.extraction_warnings[0][
            "quarantine_path"]
        with pytest.raises(vr.VisualReviewError) as exc:
            vr.validate_entries(self.session, entries,
                                section_config=vr.SECTIONS_V11,
                                appendix=("D",))
        assert exc.value.code == vr.VISUAL_REVIEW_SOURCE_IMAGE_MISMATCH

    def test_v11_sections_stay_separate_and_permissions_invariant(self):
        self._make_textonly()
        before = vr.permission_snapshot(self.session)
        entries = self._v11_entries()
        entries[0]["section"] = "B"          # analog into inspirations
        with pytest.raises(vr.VisualReviewError) as exc:
            vr.validate_entries(self.session, entries,
                                section_config=vr.SECTIONS_V11,
                                appendix=("D",))
        assert exc.value.code == vr.VISUAL_REVIEW_CLASSIFICATION_MIXED
        entries[0]["section"] = "A"
        with patch("apps.pipeline.agents.image_producer.openai") as prov:
            vr.build_visual_review_packet(
                self.session, entries, ["a"], ["d"], Path(self.tmp) / "v11p",
                section_config=vr.SECTIONS_V11, appendix=("D",),
                schema_version=vr.PACKET_SCHEMA_V11, file_prefix="corr_p")
        assert not prov.mock_calls
        assert vr.permission_snapshot(self.session) == before
        for s in self.session.sources.all():
            assert s.provider_input_permission is False
            assert s.artwork_reuse_permission is False
            assert s.design_memory_permission is False
        assert (DesignProject.objects.count(),
                DesignTask.objects.count()) == (0, 0)

    def test_download_endpoints_and_session_intact(self):
        from django.contrib.auth.models import Group
        manifest = vr.build_visual_review_packet(
            self.session, self._entries(), ["a"], ["d"],
            Path(self.tmp) / "out")
        self.session.summary["visual_review"] = manifest
        self.session.save(update_fields=["summary"])
        group, _ = Group.objects.get_or_create(name="Reviewer")
        user = User.objects.create_user("vrp", "v@t.com", "pw")
        user.groups.add(group)
        self.client.force_login(user)
        base = f"/api/web-research/sessions/{self.session.id}/visual-review"
        for kind in ("pdf", "png", "json"):
            assert self.client.get(f"{base}/{kind}/").status_code == 200
        assert self.client.get(f"{base}/exe/").status_code == 404
        self.session.refresh_from_db()
        assert self.session.status == "AWAITING_HUMAN_REVIEW"
