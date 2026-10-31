"""Confirm Profile UI-2B-2A — result contract and authorized artifact access.

The result contract exists ONLY for a clean completion (the status snapshot
already demands the recorded .ai); roles are explicit (.AI source of truth,
PNG preview only); artifact access goes through one role-addressed endpoint
with task scoping, root bounding and fixed media types — never a raw path,
storage key or MEDIA_URL. Everything is read-only.
"""
import json
from unittest.mock import patch

from django.test import Client

from apps.pipeline.models import GateDecision
from apps.pipeline.services.reconstruction_status import (
    build_container_reconstruction_result)

from .test_confirm_profile_ui2b1 import _DELAY, _StatusFixture


class ResultContractTests(_StatusFixture):

    def _result(self, task):
        r = self.client.get(f"/api/tasks/{task.id}/status/")
        assert r.status_code == 200
        return r.json()["container_reconstruction_result"]

    def test_result_only_for_clean_completion(self):
        for state in ("queued", "running", "failed", "dispatch_failed",
                      "inconsistent_no_ai", "inconsistent_no_resume",
                      "unconfirmed"):
            task = self._task(state, confirmed=(state != "unconfirmed"))
            assert self._result(task) is None, state
        for target in ("packaging", "complete_product"):
            assert self._result(self._task("queued", target=target)) is None

    def test_completed_contract_shape_and_roles(self):
        task = self._task("completed")
        result = self._result(task)
        assert result["schema"] == "container_reconstruction_result/1.0"
        assert result["lifecycle_state"] == "COMPLETED"
        assert result["profile_authority"] == "HUMAN_CONFIRMED_CONCEPT_ONLY"
        assert result["gate_decision_id"]
        ai, png = result["artifacts"]["ai"], result["artifacts"]["png"]
        assert ai["role"] == "AI_SOURCE_OF_TRUTH"
        assert png["role"] == "PNG_PREVIEW_ONLY"
        assert ai["available"] is True and ai["downloadable"] is True
        assert ai["openable"] is False and ai["previewable"] is False
        assert png["previewable"] is True
        assert ai["media_type"] == "application/illustrator"
        assert png["media_type"] == "image/png"
        assert ai["file_size"] > 0 and png["file_size"] > 0
        assert ai["filename"].endswith(".ai")
        assert ai["created_at"]
        assert ai["sha256"] is None          # not persisted → never invented
        assert ai["validation_state"] in ("RECORDED", "NOT_RECORDED")
        assert ai["download_url"].startswith(
            f"/api/tasks/{task.id}/reconstruction-artifact/ai/")
        assert png["preview_url"] == \
            f"/api/tasks/{task.id}/reconstruction-artifact/png/"

    def test_missing_png_keeps_a_clean_ai_result(self):
        task = self._task("completed")
        out = task.packaging_outputs.first()
        out.design_preview.delete(save=True)
        result = self._result(task)
        assert result is not None            # PNG export failure is permitted
        assert result["artifacts"]["ai"]["available"] is True
        png = result["artifacts"]["png"]
        assert png["available"] is False
        assert png["preview_url"] is None and png["download_url"] is None

    def test_missing_ai_prevents_any_result(self):
        task = self._task("completed")
        out = task.packaging_outputs.first()
        out.design_preview_ai.delete(save=True)
        assert self._result(task) is None
        # and the status snapshot says INCONSISTENT, not success
        r = self.client.get(f"/api/tasks/{task.id}/status/")
        assert r.json()["container_reconstruction_status"][
            "lifecycle_state"] == "RECONSTRUCTION_STATUS_INCONSISTENT"

    def test_contract_carries_no_paths_urls_or_bytes(self):
        task = self._task("completed")
        dump = json.dumps(self._result(task))
        for banned in ("/media/", "/files/", "MEDIA_URL", "/Users/", "/var/",
                       "dielines/", "base64", "Traceback"):
            assert banned not in dump, banned

    @patch(_DELAY)
    def test_result_is_deterministic_and_read_only(self, delay):
        task = self._task("completed")
        decisions = GateDecision.objects.count()
        first = build_container_reconstruction_result(task)
        second = build_container_reconstruction_result(task)
        assert first == second
        task.refresh_from_db()
        assert task.status == "awaiting_gate_2"
        assert GateDecision.objects.count() == decisions
        delay.assert_not_called()


class ArtifactAccessTests(_StatusFixture):

    def _url(self, task, role, download=False):
        return (f"/api/tasks/{task.id}/reconstruction-artifact/{role}/"
                + ("?download=1" if download else ""))

    def test_owner_gets_ai_as_attachment_with_safe_filename(self):
        task = self._task("completed")
        r = self.client.get(self._url(task, "ai"))
        assert r.status_code == 200
        disposition = r["Content-Disposition"]
        assert "attachment" in disposition
        assert ".ai" in disposition
        assert "/" not in disposition.split("filename=")[-1].strip('"')
        assert r["Content-Type"].startswith("application/illustrator")

    def test_png_serves_inline_and_download_switches_disposition(self):
        task = self._task("completed")
        inline = self.client.get(self._url(task, "png"))
        assert inline.status_code == 200
        assert "attachment" not in inline.get("Content-Disposition", "")
        assert inline["Content-Type"].startswith("image/png")
        att = self.client.get(self._url(task, "png", download=True))
        assert "attachment" in att["Content-Disposition"]

    def test_unauthenticated_and_unauthorized_are_non_leaking(self):
        task = self._task("completed")
        r = Client().get(self._url(task, "ai"))
        assert r.status_code in (401, 403)
        from django.contrib.auth.models import User
        outsider = User.objects.create_user("nobody2b2a", password="pw")
        c = Client()
        c.force_login(outsider)
        r2 = c.get(self._url(task, "ai"))
        assert r2.status_code in (403, 404)
        assert "gloss" not in r2.content.decode(errors="ignore")

    def test_wrong_role_target_state_and_missing_are_404(self):
        completed = self._task("completed")
        assert self.client.get(
            self._url(completed, "spec")).status_code == 404   # unknown role
        for state in ("queued", "unconfirmed"):
            t = self._task(state, confirmed=(state != "unconfirmed"))
            # queued has no artifacts; unconfirmed has no applicability
            assert self.client.get(self._url(t, "ai")).status_code == 404
        pkg = self._task("queued", target="packaging")
        assert self.client.get(self._url(pkg, "ai")).status_code == 404
        missing = self._task("completed")
        missing.packaging_outputs.first().design_preview_ai.delete(save=True)
        assert self.client.get(self._url(missing, "ai")).status_code == 404
        assert self.client.get(
            "/api/tasks/999999/reconstruction-artifact/ai/"
        ).status_code == 404

    def test_tampered_storage_name_cannot_escape_the_root(self):
        task = self._task("completed")
        out = task.packaging_outputs.first()
        out.design_preview_ai.name = "../../.env"
        out.save(update_fields=["design_preview_ai"])
        assert self.client.get(self._url(task, "ai")).status_code == 404

    @patch("openai.images")
    @patch("apps.pipeline.services.claude_service.call_claude")
    @patch(_DELAY)
    def test_artifact_access_mutates_and_calls_nothing(self, delay, claude,
                                                       images):
        task = self._task("completed")
        decisions = GateDecision.objects.count()
        spec_before = task.packaging_outputs.first().spec_sheet
        for role in ("ai", "png"):
            assert self.client.get(self._url(task, role)).status_code == 200
        task.refresh_from_db()
        assert task.status == "awaiting_gate_2"
        assert GateDecision.objects.count() == decisions
        assert task.packaging_outputs.first().spec_sheet == spec_before
        delay.assert_not_called()
        claude.assert_not_called()
        images.edit.assert_not_called()
        images.generate.assert_not_called()
