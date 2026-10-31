"""Gate-2 strict production-readiness enforcement (DIP-2A-5-DIE-4).

Endpoint contract: an output whose spec_sheet declares
``production_validation: "strict"`` cannot be Gate-2 approved while any
production failure stands — the endpoint answers 409 PRODUCTION_NOT_READY
with the failure list, records no GateDecision and enqueues nothing.
Non-strict (legacy) outputs keep the existing behavior unchanged.
[§BH55 Phase 2, 2026-09-19: except that a carton whose front copy overruns its panel is held, whatever its
validation — §BH50(f)(3), LIVE: "a copy overrun BLOCKS Gate 2".]
"""
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase

from apps.pipeline.models import DesignTask, GateDecision, GeneratedImage, PackagingOutput
from apps.pipeline.permissions import ROLE_REVIEWER

from apps.core.models import Brand


def _reviewer():
    user = User.objects.create_user("rev2", "r@t.com", "pw")
    group, _ = Group.objects.get_or_create(name=ROLE_REVIEWER)
    user.groups.add(group)
    return user


class Gate2StrictReadinessTests(TestCase):
    def setUp(self):
        self.reviewer = _reviewer()
        self.brand = Brand.objects.create(name="B", master_brief="x")
        self.task = DesignTask.objects.create(
            task_text="Design a luxury foundation carton for Skynte",
            status="awaiting_gate_2", brand=self.brand,
        )
        self.image = GeneratedImage.objects.create(
            task=self.task, direction_name="d", prompt_used="p", image_url="u",
        )
        self.client.force_login(self.reviewer)

    def _output(self, spec):
        return PackagingOutput.objects.create(
            task=self.task, spec_sheet=spec, approved_image=self.image,
        )

    @patch("apps.pipeline.tasks.resume_aria_gate2.delay")
    def test_strict_output_with_missing_artifacts_is_approved_with_each_failure_kept_in_words(self, mock_delay):
        # [his goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (1): "NO check ever stops a design"] the strict
        # validation's failures no longer refuse Gate 2: each kept with the approval, in the validator's own words
        output = self._output({
            "production_validation": "strict",
            "required_template": "skynte_foundation_tuck_carton",
            "template": "straight_tuck_end_carton",
            "panel_info": {},
        })
        res = self.client.post(
            f"/api/tasks/{self.task.id}/gate2_approve/",
            {"packaging_output_id": output.id},
        )
        self.assertEqual(res.status_code, 200, res.content)
        output.refresh_from_db()
        kept = output.spec_sheet["kept_with_approval"]
        codes = {k["code"] for k in kept}
        for code in ("TEMPLATE_MISMATCH", "STRUCTURE_CHECKLIST_MISSING", "ARTWORK_INVENTORY_MISSING",
                     "PLACEHOLDER_REGULATORY_INFO", "PRODUCTION_PDF_MISSING"):
            self.assertIn(code, codes)
        self.assertTrue(all(k["words"] and k["code"] not in k["words"] for k in kept), kept)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "gate_2_approved")
        mock_delay.assert_called_once()

    @patch("apps.pipeline.tasks.resume_aria_gate2.delay")
    def test_a_carton_whose_front_copy_overruns_its_panel_is_approved_with_it_kept(self, mock_delay):
        # §BH55 Phase 2 — §BH50(f)(3): "FRONT COPY: the 5.0 pt floor governs and a copy overrun BLOCKS Gate 2"; [his goal
        # of 2026-10-13, (1): "NO check ever stops a design"] the overrun is kept with the approval in words since
        from apps.ire.compose import FRONT_COPY_EXCEEDS_PANEL, FRONT_TYPE_KEY
        code = f"{FRONT_COPY_EXCEEDS_PANEL}:front:name"
        held = self._output({"template": "straight_tuck_end_carton", FRONT_TYPE_KEY: {"codes": [code]}})
        res = self.client.post(f"/api/tasks/{self.task.id}/gate2_approve/", {"packaging_output_id": held.id})
        self.assertEqual(res.status_code, 200, res.content)
        held.refresh_from_db()
        self.assertEqual(held.spec_sheet["kept_with_approval"], [
            {"code": "CARTON_FRONT_COPY_EXCEEDS_PANEL", "words": "the front's copy runs past its panel — front, name"}])
        DesignTask.objects.filter(pk=self.task.pk).update(status="awaiting_gate_2")
        PackagingOutput.objects.filter(task_id=self.task.pk).update(is_final_approved=False)
        clean = self._output({"template": "straight_tuck_end_carton", FRONT_TYPE_KEY: {"codes": []}})
        res = self.client.post(f"/api/tasks/{self.task.id}/gate2_approve/", {"packaging_output_id": clean.id})
        self.assertEqual(res.status_code, 200)

    @patch("apps.pipeline.tasks.resume_aria_gate2.delay")
    def test_a_carton_whose_front_copy_could_not_be_measured_is_not_held(self, mock_delay):
        # §BH71 (0a), the owner's goal of 2026-09-28: "Unmeasured checks … show as a warning beside Approve, never a
        # block." A run the instrument could not measure no longer holds the carton; a measured overrun still does
        from apps.ire.compose import FRONT_COPY_EXCEEDS_PANEL, FRONT_COPY_UNMEASURED, FRONT_TYPE_KEY
        unmeasured = f"{FRONT_COPY_UNMEASURED}:front:line"
        over = f"{FRONT_COPY_EXCEEDS_PANEL}:front:name"
        both = self._output({"template": "straight_tuck_end_carton", FRONT_TYPE_KEY: {"codes": [over, unmeasured]}})
        res = self.client.post(f"/api/tasks/{self.task.id}/gate2_approve/", {"packaging_output_id": both.id})
        # [his goal of 2026-10-13, (1)] approved; the measured overrun kept with it, never the unmeasured run
        self.assertEqual(res.status_code, 200, res.content)
        both.refresh_from_db()
        self.assertEqual([k["code"] for k in both.spec_sheet["kept_with_approval"]], ["CARTON_FRONT_COPY_EXCEEDS_PANEL"])
        DesignTask.objects.filter(pk=self.task.pk).update(status="awaiting_gate_2")
        PackagingOutput.objects.filter(task_id=self.task.pk).update(is_final_approved=False)
        only = self._output({"template": "straight_tuck_end_carton", FRONT_TYPE_KEY: {"codes": [unmeasured]}})
        res = self.client.post(f"/api/tasks/{self.task.id}/gate2_approve/", {"packaging_output_id": only.id})
        self.assertEqual(res.status_code, 200)

    @patch("apps.pipeline.tasks.resume_aria_gate2.delay")
    def test_non_strict_output_keeps_legacy_behavior(self, mock_delay):
        output = self._output({"template": "straight_tuck_end_carton"})
        res = self.client.post(
            f"/api/tasks/{self.task.id}/gate2_approve/",
            {"packaging_output_id": output.id},
        )
        self.assertEqual(res.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "gate_2_approved")
        mock_delay.assert_called_once()


class HisReviewPointSixTranslationsTests(TestCase):
    """[His review of 119, 2026-10-05, point 6: "The rest is translation: show it as 'Not confirmed yet' beside Approve
    until I confirm it."] A carton's translations stand "Not confirmed yet" beside Approve, with their words and a way
    to confirm them; once he confirms exactly those words the warning closes, and it opens again if they change. What
    stood beside Approve is kept with the approval."""

    def setUp(self):
        self.reviewer = _reviewer()
        self.task = DesignTask.objects.create(task_text="Rose Glaze Lip Gloss", status="awaiting_gate_2",
                                              brand=Brand.objects.create(name="B", master_brief="x"))
        image = GeneratedImage.objects.create(task=self.task, direction_name="d", prompt_used="p", image_url="u")
        self.output = PackagingOutput.objects.create(task=self.task, approved_image=image, spec_sheet={
            "panel_info": {"warnings": "For external use only.",
                           "translations": {"es": {"warnings": "Solo para uso externo."},
                                            "ar": {"warnings": "للاستخدام الخارجي فقط."}}}})
        self.client.force_login(self.reviewer)

    def _rows(self):
        from apps.pipeline.views import _acceptance_warnings
        return [r for r in _acceptance_warnings(self.task, None) if r["code"] == "CARTON_TRANSLATION_UNCONFIRMED"]

    def test_the_translations_stand_not_confirmed_until_he_confirms_them(self):
        rows = self._rows()
        assert len(rows) == 1 and rows[0]["kind"] == "unconfirmed" and rows[0]["confirm"] == "translations", rows
        assert "not confirmed yet" in rows[0]["words"]
        assert {d["language"] for d in rows[0]["detail"]} == {"Spanish", "Arabic"}
        res = self.client.post(f"/api/tasks/{self.task.id}/confirm_translations/", {})
        assert res.status_code == 200, res.content
        self.output.refresh_from_db()
        record = self.output.spec_sheet["translations_confirmed/1.0"]
        assert record["by"] == "rev2" and record["languages"] == ["ar", "es"]
        assert self._rows() == []                                               # confirmed: the warning closes
        spec = self.output.spec_sheet
        spec["panel_info"]["translations"]["es"]["warnings"] = "Solo uso externo."
        self.output.spec_sheet = spec
        self.output.save()
        assert len(self._rows()) == 1                                           # the words changed: it opens again

    @patch("apps.pipeline.tasks.resume_aria_gate2.delay")
    def test_what_stood_beside_approve_is_kept_with_the_approval(self, _delay):
        res = self.client.post(f"/api/tasks/{self.task.id}/gate2_approve/", {"packaging_output_id": self.output.id})
        assert res.status_code == 200, res.content
        self.output.refresh_from_db()
        kept = self.output.spec_sheet["acceptance_warnings_at_approval"]
        assert [k["code"] for k in kept] == ["CARTON_TRANSLATION_UNCONFIRMED"] and kept[0]["kind"] == "unconfirmed"

