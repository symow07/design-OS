"""gate1_reference_regeneration_prompts/1.0 contract (2A-6E-CORR-5 §4/§5)
and the job-scoped failure/recovery semantics (§6/§7).

The live regeneration failed because the legacy Prompt Engineer path capped
output at 3,000 tokens, truncated the JSON, had no repair, kept no raw
response, and its failure propagated to the parent task. These pin the
replacement contract end to end.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from apps.core.models import Brand
from apps.pipeline.models import (
    ApiCallRecord,
    ConceptInfluencePlan,
    ConceptReference,
    CreativeBrief,
    DesignTask,
    Gate1RegenerationJob,
    GeneratedImage,
)
from apps.pipeline.services.concept_references import (
    build_influence_plan,
    plan_hash,
)
from apps.pipeline.services.gate1_prompts import (
    GATE1_PROMPTS_SCHEMA,
    MAX_OUTPUT_TOKENS,
    build_regeneration_prompts,
    validate_regeneration_payload,
)
from apps.pipeline.services.gate1_regeneration import (
    GateRegenerationError,
    VARIATION_IDENTITIES,
    recover_task_to_gate1,
)

from .test_gate1_reference_regeneration import regen_payload

REF_IDS = [2, 7, 8, 10]
HASH = "a" * 64


def _response(payload):
    return json.dumps(payload) if isinstance(payload, dict) else str(payload)


def _call_model_from(responses):
    calls = []

    def call(system, message):
        calls.append(message)
        payload = responses[min(len(calls) - 1, len(responses) - 1)]
        return _response(payload), "test:model"
    return call, calls


class PayloadValidationTests(TestCase):
    def test_valid_three_prompt_payload_parses(self):
        payload = regen_payload(REF_IDS, HASH)
        assert validate_regeneration_payload(
            payload, VARIATION_IDENTITIES, REF_IDS, HASH) == []

    def test_empty_variations_fail_with_a_precise_code(self):
        payload = regen_payload(REF_IDS, HASH)
        payload["variations"] = []
        codes = validate_regeneration_payload(
            payload, VARIATION_IDENTITIES, REF_IDS, HASH)
        assert any("PROMPT_ENGINEER_EMPTY_RESPONSE" in c for c in codes)

    def test_prose_only_output_fails(self):
        codes = validate_regeneration_payload(
            "Here are three lovely design ideas...",
            VARIATION_IDENTITIES, REF_IDS, HASH)
        assert any("SCHEMA_MISMATCH" in c for c in codes)

    def test_wrong_variation_ids_fail(self):
        payload = regen_payload(REF_IDS, HASH)
        payload["variations"][2]["variation_id"] = "D_EXTRA"
        codes = validate_regeneration_payload(
            payload, VARIATION_IDENTITIES, REF_IDS, HASH)
        assert any("variation_ids must be exactly" in c for c in codes)

    def test_unechoed_bindings_fail(self):
        payload = regen_payload(REF_IDS, HASH)
        payload["approved_reference_ids"] = [1]
        payload["influence_plan_hash"] = "b" * 64
        codes = validate_regeneration_payload(
            payload, VARIATION_IDENTITIES, REF_IDS, HASH)
        assert any("approved_reference_ids" in c for c in codes)
        assert any("influence_plan_hash" in c for c in codes)

    def test_collapsed_signatures_fail_diversity(self):
        payload = regen_payload(REF_IDS, HASH, break_diversity=True)
        codes = validate_regeneration_payload(
            payload, VARIATION_IDENTITIES, REF_IDS, HASH)
        assert any("VARIATION_PROMPTS_NOT_DISTINCT" in c for c in codes)

    def test_output_token_budget_covers_rich_payloads(self):
        # the incident: max_tokens=3000 truncated the response mid-JSON
        assert MAX_OUTPUT_TOKENS >= 8000


class BuilderTests(TestCase):
    def _build(self, responses):
        call, calls = _call_model_from(responses)
        result = build_regeneration_prompts(
            direction={"name": "Editorial Soft Radiance",
                       "direction_id": "d1"},
            product_block="face powder carton",
            influence_plan={"schema_version": "material_influence_plan/1.0"},
            plan_hash=HASH, reference_ids=REF_IDS,
            variation_identities=VARIATION_IDENTITIES,
            richness_directives="RICHNESS", call_model=call)
        return result, calls

    def test_happy_path_returns_three_bound_prompts(self):
        result, calls = self._build([regen_payload(REF_IDS, HASH)])
        assert result.ok and result.attempts == 1
        assert [p["variation_id"] for p in result.prompts] == \
            VARIATION_IDENTITIES
        assert all(p["full_prompt"] for p in result.prompts)
        assert len(result.raw_responses) == 1
        # the message carries the influence plan and the echo bindings
        assert "material_influence_plan/1.0" in calls[0]
        assert str(sorted(REF_IDS)) in calls[0].replace(", ", ", ")

    def test_malformed_first_response_triggers_one_bounded_repair(self):
        truncated = '{"schema_version": "gate1_reference_regeneration_'
        result, calls = self._build([truncated,
                                     regen_payload(REF_IDS, HASH)])
        assert result.ok and result.attempts == 2
        assert len(calls) == 2
        # the repair message carries the exact error AND the raw response
        assert "PROMPT_ENGINEER_OUTPUT_PARSE_FAILURE" in calls[1]
        assert truncated in calls[1]
        assert result.raw_responses[0] == truncated

    def test_double_failure_preserves_everything_and_stops(self):
        result, calls = self._build(["prose one", "prose two"])
        assert not result.ok
        assert result.attempts == 2 and len(calls) == 2
        assert result.codes
        assert result.raw_responses == ("prose one", "prose two")

    def test_wrong_keys_payload_is_repaired(self):
        legacy_shape = {"prompts": [{"direction_name": "x",
                                     "full_prompt": "y"}]}
        result, calls = self._build([legacy_shape,
                                     regen_payload(REF_IDS, HASH)])
        assert result.ok and result.attempts == 2
        assert "schema_version must be" in calls[1] \
            or "SCHEMA_MISMATCH" in calls[1]


class RecoveryTests(TestCase):
    """§7: restoring a task wrongly failed by a job-scoped regeneration
    failure — verified against database invariants, zero provider calls."""

    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, True)
        self._override = override_settings(MEDIA_ROOT=self.media)
        self._override.enable()
        self.addCleanup(self._override.disable)
        self.user = User.objects.create_superuser("rc", "r@r.com", "pw")
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.task = DesignTask.objects.create(
            brand=self.brand, task_text="Baked Powder", status="failed",
            error_message="Prompt Engineer produced 0 variation prompts",
            created_by=self.user)
        self.brief = CreativeBrief.objects.create(
            task=self.task, directions=[], design_intent={},
            selected_direction_id="d1")
        self.images = [GeneratedImage.objects.create(
            task=self.task, direction_name="d", prompt_used=f"p{n}",
            variation_number=n,
            user_rejection_label="REJECTED_BY_USER — X") for n in (1, 2, 3)]
        rows = []
        for index in range(2):
            (Path(self.media) / f"rc{index}.png").write_bytes(b"\x89PNG")
            rows.append(ConceptReference.objects.create(
                task=self.task, source_type="HISTORICAL_DESIGN_REFERENCE",
                library_item_id=f"design_reference:rc{index}",
                title=f"rc{index}", image_root="media",
                image_path=f"rc{index}.png",
                permission_status=ConceptReference.PERMISSION_APPROVED,
                approved_by=self.user))
        self.rows = rows
        plan = build_influence_plan(self.task, rows)
        self.plan = ConceptInfluencePlan.objects.create(
            task=self.task, plan=plan, plan_hash=plan_hash(plan),
            created_by=self.user)
        self.job = Gate1RegenerationJob.objects.create(
            task=self.task, direction_id="d1", status="failed",
            approved_reference_ids=[r.pk for r in rows],
            influence_plan_hash=self.plan.plan_hash,
            variation_identities=list(VARIATION_IDENTITIES),
            error="Prompt Engineer produced 0 variation prompts",
            created_by=self.user)

    def test_recovery_restores_gate_state_without_any_provider_call(self):
        calls_before = ApiCallRecord.objects.count()
        result = recover_task_to_gate1(self.task, self.job, self.user)
        assert result["recovered"] is True
        self.task.refresh_from_db()
        assert self.task.status == "awaiting_gate_1"
        assert self.task.error_message == ""
        assert ApiCallRecord.objects.count() == calls_before
        # everything preserved: approvals, plan, historical images, job
        assert ConceptReference.objects.filter(
            task=self.task,
            permission_status="USER_APPROVED_FOR_CONCEPT_REFERENCE"
        ).count() == 2
        self.job.refresh_from_db()
        assert self.job.status == "failed"          # audit intact
        for image in self.images:
            image.refresh_from_db()
            assert image.user_rejection_label
        from apps.pipeline.models import AgentLog
        note = AgentLog.objects.filter(
            task=self.task, action__contains="Operational recovery").first()
        assert note and note.payload["job_id"] == self.job.pk
        assert note.payload["code"] == "GATE1_REGENERATION_FAILED"

    def test_recovery_refuses_when_images_were_generated(self):
        GeneratedImage.objects.create(
            task=self.task, direction_name="new", prompt_used="new",
            variation_number=1)
        with self.assertRaises(GateRegenerationError) as ctx:
            recover_task_to_gate1(self.task, self.job, self.user)
        assert ctx.exception.code == "RECOVERY_PRECONDITION_FAILED"

    def test_recovery_refuses_when_approvals_changed(self):
        self.rows[0].permission_status = \
            ConceptReference.PERMISSION_CANDIDATE
        self.rows[0].save()
        with self.assertRaises(GateRegenerationError):
            recover_task_to_gate1(self.task, self.job, self.user)


class StatusApiTests(TestCase):
    def test_status_api_exposes_the_latest_regeneration_job(self):
        user = User.objects.create_superuser("sa", "s@s.com", "pw")
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        task = DesignTask.objects.create(
            brand=brand, task_text="x", status="awaiting_gate_1",
            created_by=user)
        job = Gate1RegenerationJob.objects.create(
            task=task, direction_id="d1", status="failed",
            approved_reference_ids=[1, 2], influence_plan_hash="h" * 64,
            variation_identities=list(VARIATION_IDENTITIES),
            error="boom", created_by=user)
        self.client.force_login(user)
        body = self.client.get(f"/api/tasks/{task.pk}/status/").json()
        assert body["latest_regeneration_job"]["id"] == job.pk
        assert body["latest_regeneration_job"]["status"] == "failed"
        assert body["latest_regeneration_job"]["error"] == "boom"
