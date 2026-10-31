"""VQR-6 — single artifact and status authority (server).

The contradiction the owner rejected: a truthy FieldFile made the Gate-2
surface offer "Download Design .ai (editable)" while the reconstruction
status said the AI was unavailable and technical intervention was required.
These tests hold the fix: the result contract is the ONLY availability
authority for Product Container artifacts, Gate-2 readiness is one derived
decision, the serializer never emits a raw FileField URL for container
results, and the approve/handoff backends refuse GATE_2_NOT_READY states
without creating anything.
"""
import json
from unittest.mock import patch

from apps.pipeline.models import GateDecision
from apps.pipeline.serializers import PackagingOutputSerializer
from apps.pipeline.services.reconstruction_status import (
    build_container_gate2_readiness)

from .test_confirm_profile_ui2b1 import _DELAY, _StatusFixture


class ResultAuthorityTests(_StatusFixture):

    def _serialized(self, task):
        return PackagingOutputSerializer(task.packaging_outputs.first()).data

    def test_truthy_but_unavailable_ai_yields_no_action_url(self):
        # tampered record: FieldFile truthy, storage unresolvable
        task = self._task("completed")
        out = task.packaging_outputs.first()
        out.design_preview_ai.name = "../../.env"
        out.save(update_fields=["design_preview_ai"])
        data = self._serialized(task)
        assert data["design_preview_ai_url"] is None
        readiness = build_container_gate2_readiness(task)
        assert readiness["ready"] is False
        assert readiness["ai_authoritative"] is False
        assert readiness["technical_intervention_required"] is True

    def test_missing_and_deleted_ai_yield_no_action_url(self):
        missing = self._task("completed")
        missing.packaging_outputs.first().design_preview_ai.delete(save=True)
        assert self._serialized(missing)["design_preview_ai_url"] is None
        stored_gone = self._task("completed")
        out = stored_gone.packaging_outputs.first()
        out.design_preview_ai.storage.delete(out.design_preview_ai.name)
        assert self._serialized(stored_gone)["design_preview_ai_url"] is None

    def test_png_alone_never_makes_gate2_ready(self):
        task = self._task("completed")
        task.packaging_outputs.first().design_preview_ai.delete(save=True)
        readiness = build_container_gate2_readiness(task)
        assert readiness["png_preview_available"] is True
        assert readiness["ai_authoritative"] is False
        assert readiness["ready"] is False
        assert readiness["reason_code"] == \
            "RECONSTRUCTION_STATUS_INCONSISTENT"

    def test_missing_optional_png_with_valid_ai_keeps_ai_authority(self):
        # VQR-2A: PNG loss alone never blocks — the block, when present,
        # comes from the visual quality gate, never from the optional PNG
        task = self._task("completed")
        task.packaging_outputs.first().design_preview.delete(save=True)
        readiness = build_container_gate2_readiness(task)
        assert readiness["ai_authoritative"] is True
        assert readiness["png_preview_available"] is False
        # [§BH71 (0a), the owner's goal of 2026-09-28: this fixture measures nothing — it read
        # VISUAL_QUALITY_GATE_FAILED and inspection only; an unmeasured check is a warning beside Approve, so
        # neither the PNG nor the quality check blocks it]
        assert readiness["ready"] is True and readiness["reason_code"] is None
        assert readiness["inspection_only"] is False

    def test_non_completed_states_block_with_their_lifecycle(self):
        for state, reason in (("queued", "QUEUED"), ("running", "RUNNING"),
                              ("failed", "FAILED"),
                              ("dispatch_failed", "FAILED")):
            readiness = build_container_gate2_readiness(self._task(state))
            assert readiness["ready"] is False, state
            assert readiness["reason_code"] == reason, state

    def test_clean_completed_is_ready_with_authorized_urls_only(self):
        # VQR-2A: artifact authority alone no longer makes Gate 2 ready —
        # readiness additionally requires the visual quality gate to PASS.
        # A quality-passing evaluation restores full readiness; the fixture
        # itself (no measurable quality evidence) stays honestly blocked.
        task = self._task("completed")
        readiness = build_container_gate2_readiness(task)
        # [§BH71 (0a), the owner's goal of 2026-09-28: the fixture's quality evidence is unmeasured, never
        # failed — it read ready False, VISUAL_QUALITY_GATE_FAILED and inspection only; unmeasured is a warning
        # beside Approve, never a block, and the overall still never reads PASS]
        assert readiness["ready"] is True
        assert readiness["reason_code"] is None
        assert readiness["ai_authoritative"] is True
        assert readiness["png_preview_available"] is True
        assert readiness["inspection_only"] is False
        assert readiness["visual_quality"]["overall"] == "UNMEASURED"
        with patch("apps.pipeline.services.visual_quality_gate."
                   "evaluate_container_visual_quality",
                   return_value={"overall": "PASS",
                                 "status": "VISUAL_QUALITY_PASSED",
                                 "blocking_findings": []}):
            passing = build_container_gate2_readiness(task)
        assert passing["ready"] is True
        assert passing["reason_code"] is None
        assert passing["handoff_ready"] is True
        assert passing["owner_review_ready"] is True
        assert passing["inspection_only"] is False
        data = self._serialized(task)
        assert data["design_preview_ai_url"] == \
            f"/api/tasks/{task.id}/reconstruction-artifact/ai/?download=1"
        assert data["design_preview_url"] == \
            f"/api/tasks/{task.id}/reconstruction-artifact/png/"

    def test_no_raw_files_url_anywhere_in_the_container_payload(self):
        for state in ("completed", "queued", "failed"):
            task = self._task(state)
            r = self.client.get(f"/api/tasks/{task.id}/status/")
            dump = json.dumps(r.json())
            assert "/files/" not in dump, state
            assert "/media/" not in dump, state

    def test_review_board_comparison_uses_contract_urls_only(self):
        # the §12 comparison's reconstruction side is a result surface too:
        # authorized endpoint when the contract vouches, absent otherwise —
        # never the raw /files/ media URL of the stored PNG
        from django.core.files.base import ContentFile

        from apps.pipeline.review_board import build_review_board
        task = self._task("completed")
        out = task.packaging_outputs.first()
        out.approved_image.image_file.save(
            "concept.png", ContentFile(b"\x89PNG\r\n\x1a\nx"), save=True)
        comp = build_review_board(task).comparison
        assert comp is not None
        assert comp.reconstruction_url == \
            f"/api/tasks/{task.id}/reconstruction-artifact/png/"
        tampered = self._task("completed")
        t_out = tampered.packaging_outputs.first()
        t_out.approved_image.image_file.save(
            "concept.png", ContentFile(b"\x89PNG\r\n\x1a\nx"), save=True)
        t_out.design_preview_ai.name = "../../.env"
        t_out.save(update_fields=["design_preview_ai"])
        comp = build_review_board(tampered).comparison
        assert comp is None or comp.reconstruction_url is None

    def test_packaging_serializer_behavior_unchanged(self):
        task = self._task("queued", target="packaging")
        out = task.packaging_outputs.first()
        from django.core.files.base import ContentFile
        out.design_preview_ai.save("pkg.ai", ContentFile(b"%!PS x"),
                                   save=True)
        data = self._serialized(task)
        assert data["design_preview_ai_url"] == out.design_preview_ai.url
        assert build_container_gate2_readiness(task) is None


class Gate2EnforcementTests(_StatusFixture):

    def _approve(self, task):
        out = task.packaging_outputs.first()
        return self.client.post(
            f"/api/tasks/{task.id}/gate2_approve/",
            {"packaging_output_id": out.id}, content_type="application/json")

    def _handoff(self, task):
        return self.client.post(
            f"/api/tasks/{task.id}/generate_handoff/", {},
            content_type="application/json")

    @patch(_DELAY)
    def test_direct_approve_refused_when_not_ready(self, delay):
        for state in ("queued", "failed", "inconsistent_no_ai"):
            task = self._task(state)
            decisions = GateDecision.objects.count()
            r = self._approve(task)
            assert r.status_code == 409, state
            assert r.json()["error"] == "GATE_2_NOT_READY", state
            assert r.json()["reason_code"], state
            assert GateDecision.objects.count() == decisions, state
            before = task.status
            task.refresh_from_db()
            assert task.status == before, state
        delay.assert_not_called()

    def test_tampered_record_refuses_approve_and_handoff(self):
        task = self._task("completed")
        out = task.packaging_outputs.first()
        out.design_preview_ai.name = "../../.env"
        out.save(update_fields=["design_preview_ai"])
        spec_before = out.spec_sheet
        a = self._approve(task)
        assert a.status_code == 409
        assert a.json()["error"] == "GATE_2_NOT_READY"
        h = self._handoff(task)
        assert h.status_code == 409
        assert h.json()["error"] == "GATE_2_NOT_READY"
        out.refresh_from_db()
        assert out.spec_sheet == spec_before          # no handoff generated

    def test_handoff_refused_without_authoritative_ai(self):
        task = self._task("inconsistent_no_ai")
        r = self._handoff(task)
        assert r.status_code == 409
        assert r.json()["error"] == "GATE_2_NOT_READY"

    @patch("openai.images")
    @patch("apps.pipeline.services.claude_service.call_claude")
    def test_refusals_call_no_provider(self, claude, images):
        task = self._task("failed")
        assert self._approve(task).status_code == 409
        assert self._handoff(task).status_code == 409
        claude.assert_not_called()
        images.edit.assert_not_called()
        images.generate.assert_not_called()
