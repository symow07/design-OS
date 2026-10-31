"""Phase 2B-3V UI correction — combined profile + decoration-zone confirmation.

Task #51 reached awaiting_container_profile but the browser rendered the legacy
B4a screen (archetype cards + three sliders): depth, per-field authority, the
proposed decoration zones, the hashes and the refusal codes never reached the
human. These tests pin the correction:

  §2  product-record dims (incl. depth) seed the proposal AS RECORDED and
      survive an unchanged confirm (no silent source downgrade);
  §3  the tube proposal now carries an optional CAP_PRINT_ZONE;
  §4  depth is REQUIRED — a depth-less profile refuses before reconstruction,
      and zone confirmation cannot be bypassed;
  §5  a refusal preserves the persisted values;
  UI  the served frontend binds container_profile/1.0 + zones (not the legacy
      profile-only POST) and exposes the combined action.

No provider call anywhere.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase

from apps.core.models import Brand, Product
from apps.pipeline.models import DesignTask, GeneratedImage, PackagingOutput
from apps.pipeline.services import container_contract as cc
from apps.pipeline.targets.base import DesignTarget

ROLE_REVIEWER = "Reviewer"

_JS = (Path(__file__).resolve().parents[3] / "static" / "js"
       / "confirm_profile.js").read_text()


class FrontendBindingTests(TestCase):
    """The served confirm screen binds the 2B-1 contract, not the legacy form."""

    def test_frontend_renders_versioned_contract(self):
        assert "container_profile/1.0" in _JS
        assert "container_decoration_zones/1.0" in _JS

    def test_frontend_renders_depth(self):
        assert "depth_mm" in _JS and "body_depth_mm" in _JS

    def test_frontend_posts_zones_with_confirmation_state(self):
        assert "user_confirmation_state" in _JS
        assert "USER_CONFIRMED" in _JS
        assert "zones: zones" in _JS                 # zones ride the POST

    def test_frontend_combined_action_not_legacy_reconstruct(self):
        # the PAGE action keeps the combined 2B-3V label; since UI-2A the
        # "Confirm & Reconstruct" name exists ONLY as the reviewed dialog's
        # explicit dispatch action (§7), never as a page-level legacy button
        assert "Confirm the shape and print areas" in _JS  # [the owner's goal of 2026-09-25, (d): the same claim in plain words]
        assert 'id="cpd-confirm">Confirm and draw it' in _JS
        assert _JS.count("Confirm and draw it") == 1

    def test_frontend_shows_hashes_and_authority(self):
        assert "profile_hash" in _JS and "zone_hash" in _JS
        assert "zone_set_hash" in _JS
        assert "PRODUCT_RECORD · AS_RECORDED" in _JS

    def test_frontend_renders_refusal_detail_without_reset(self):
        assert "refusal-detail" in _JS
        # the refusal path re-renders zones but never rebuilds _profileState
        refusal = _JS.split("Refusal path", 1)[1]
        assert "_profileState = {" not in refusal


class SeededProposalTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="B", master_brief="x")
        self.product = Product.objects.create(
            brand=self.brand, product_id="CO-410", name="Rosé Nectar",
            category="CO", year=2026, product_type="lip gloss",
            width_mm=35, depth_mm=25, height_mm=95)

    def test_product_record_dims_seed_as_recorded(self):
        rec = cc.build_inferred_profile("tube", "slim",
                                        estimates={"body_width_mm": 35.0})
        rec = cc.merge_product_record_dims(rec, self.product)
        for name, want in (("body_width_mm", 35.0), ("body_depth_mm", 25.0),
                           ("body_height_mm", 95.0)):
            f = rec["fields"][name]
            assert f["value"] == want
            assert f["source"] == cc.SRC_PRODUCT_RECORD
            assert f["verification"] == cc.UNVERIFIED   # a record, not a spec
        assert cc.profile_is_confirmable(rec) == []      # dims sourced → ready

    def test_tube_cap_zone_only_proposed_when_cap_is_bounded(self):
        # correction item 1/4: no cap zone proposal on an UNBOUNDED cap
        rec = cc.build_inferred_profile("tube", "slim")
        types = [z["zone_type"] for z in cc.propose_zones(rec)]
        assert types == ["FRONT_PRINT_ZONE", "BACK_PRINT_ZONE",
                         "BOTTOM_CODE_ZONE"]
        # with recorded cap dims the optional bounded cap zone appears
        rec = cc.build_inferred_profile("tube", "slim", estimates={
            "cap_width_mm": 20.0, "cap_height_mm": 12.0})
        zones = cc.propose_zones(rec)
        types = [z["zone_type"] for z in zones]
        assert types == ["FRONT_PRINT_ZONE", "BACK_PRINT_ZONE",
                         "CAP_PRINT_ZONE", "BOTTOM_CODE_ZONE"]
        cap = zones[2]
        assert cap["parent_surface"] == "CAP_FRONT"
        assert cap["curvature_type"] == cc.CYLINDRICAL   # bounded → resolvable
        assert cap["max_artwork_coverage"] <= 0.3        # small mark only
        assert cap["user_confirmation_state"] == cc.ZONE_PROPOSED

    def test_depth_missing_blocks_confirmability(self):
        rec = cc.merge_user_profile(
            cc.build_inferred_profile("tube"),
            {"body_width_mm": 35.0, "body_height_mm": 95.0})   # no depth
        problems = cc.profile_is_confirmable(rec)
        assert any("body_depth_mm" in p for p in problems)


class CombinedConfirmEndpointTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="B", master_brief="x")
        self.product = Product.objects.create(
            brand=self.brand, product_id="CO-410", name="Rosé Nectar",
            category="CO", year=2026, product_type="lip gloss",
            width_mm=35, depth_mm=25, height_mm=95)
        group, _ = Group.objects.get_or_create(name=ROLE_REVIEWER)
        self.user = User.objects.create_user("r", "r@t.com", "pw")
        self.user.groups.add(group)
        self.client.force_login(self.user)
        self.task = DesignTask.objects.create(
            brand=self.brand, product=self.product, task_text="gloss",
            status="awaiting_container_profile",
            design_target=DesignTarget.PRODUCT_CONTAINER.value)
        img = GeneratedImage.objects.create(
            task=self.task, direction_name="D", prompt_used="p",
            variation_number=1)
        self.out = PackagingOutput.objects.create(
            task=self.task, approved_image=img,
            spec_sheet={"backend": "container",
                        "container_profile": {"archetype": "tube"}})

    def _post(self, profile=None, zones=None):
        body = {"profile": profile or {"archetype": "tube", "variant": "slim",
                                       "height_mm": 95, "width_mm": 35,
                                       "depth_mm": 25, "cap_style": "screw"}}
        if zones is not None:
            body["zones"] = zones
        return self.client.post(
            f"/api/tasks/{self.task.id}/confirm_container_profile/",
            body, content_type="application/json")

    def _confirmed_zones(self):
        rec = cc.merge_product_record_dims(
            cc.build_inferred_profile("tube", "slim"), self.product)
        zones = cc.propose_zones(rec)
        for z in zones:
            z["user_confirmation_state"] = cc.ZONE_USER_CONFIRMED
        return zones

    @patch("apps.pipeline.tasks.resume_aria_container_profile.delay")
    def test_zone_confirmation_cannot_be_bypassed(self, mock_delay):
        resp = self._post()                              # profile only
        assert resp.status_code == 409
        assert resp.json()["error"] == \
            "CONTAINER_DECORATION_ZONE_CONFIRMATION_REQUIRED"
        mock_delay.assert_not_called()
        self.task.refresh_from_db()
        assert self.task.status == "awaiting_container_profile"

    @patch("apps.pipeline.tasks.resume_aria_container_profile.delay")
    def test_refusal_preserves_persisted_values(self, mock_delay):
        self._post()                                     # 409, persists record
        self.out.refresh_from_db()
        rec = self.out.spec_sheet[cc.PROFILE_SCHEMA]
        f = rec["fields"]
        assert f["body_width_mm"]["value"] == 35.0
        assert f["body_depth_mm"]["value"] == 25.0
        assert f["body_height_mm"]["value"] == 95.0
        assert rec["confirmation_state"] == "UNCONFIRMED"
        zones = self.out.spec_sheet[cc.ZONES_SCHEMA]["zones"]
        assert zones and all(z["user_confirmation_state"] == "PROPOSED"
                             for z in zones)

    @patch("apps.pipeline.tasks.resume_aria_container_profile.delay")
    def test_unchanged_product_record_dims_keep_their_source(self, mock_delay):
        resp = self._post(zones=self._confirmed_zones())
        assert resp.status_code == 200, resp.json()
        self.out.refresh_from_db()
        rec = self.out.spec_sheet[cc.PROFILE_SCHEMA]
        for name in ("body_width_mm", "body_depth_mm", "body_height_mm"):
            assert rec["fields"][name]["source"] == cc.SRC_PRODUCT_RECORD, name
        assert rec["confirmation_state"] == "CONFIRMED"
        assert self.out.spec_sheet["container_confirmation"]["combined_hash"]
        mock_delay.assert_called_once()                 # reconstruction resumes

    @patch("apps.pipeline.tasks.resume_aria_container_profile.delay")
    def test_user_edited_dim_promotes_to_user_visual(self, mock_delay):
        zones = self._confirmed_zones()
        resp = self._post(profile={"archetype": "tube", "variant": "slim",
                                   "height_mm": 96, "width_mm": 35,
                                   "depth_mm": 25, "cap_style": "screw"},
                          zones=zones)
        assert resp.status_code == 200, resp.json()
        self.out.refresh_from_db()
        rec = self.out.spec_sheet[cc.PROFILE_SCHEMA]
        assert rec["fields"]["body_height_mm"]["source"] == cc.SRC_USER_VISUAL
        assert rec["fields"]["body_width_mm"]["source"] == cc.SRC_PRODUCT_RECORD

    @patch("apps.pipeline.tasks.resume_aria_container_profile.delay")
    def test_depth_missing_refuses_profile_confirmation(self, mock_delay):
        self.task.product = None
        self.task.save(update_fields=["product"])       # no record to seed
        resp = self._post(profile={"archetype": "tube", "height_mm": 95,
                                   "width_mm": 35},     # no depth anywhere
                          zones=self._confirmed_zones())
        assert resp.status_code == 409
        assert resp.json()["error"] == "CONTAINER_PROFILE_CONFIRMATION_REQUIRED"
        assert any("body_depth_mm" in d for d in resp.json()["detail"])
        mock_delay.assert_not_called()

    @patch("apps.pipeline.tasks.resume_aria_container_profile.delay")
    def test_no_provider_call_during_confirmation(self, mock_delay):
        with patch("apps.pipeline.services.claude_service.call_claude") as pe, \
                patch("apps.pipeline.agents.image_producer.openai.images.edit") as ie, \
                patch("apps.pipeline.agents.image_producer.openai.images.generate") as ig:
            self._post()                                 # refusal path
            self._post(zones=self._confirmed_zones())    # confirm path
        pe.assert_not_called()
        ie.assert_not_called()
        ig.assert_not_called()

    def test_legacy_container_task_stays_readable(self):
        # a pre-2B-1 output (no versioned keys) still serializes for the UI
        resp = self.client.get(f"/api/tasks/{self.task.id}/status/")
        assert resp.status_code == 200
        po = resp.json().get("packaging_output") or {}
        assert po.get("spec_sheet", {}).get("container_profile", {}) \
            .get("archetype") == "tube"
