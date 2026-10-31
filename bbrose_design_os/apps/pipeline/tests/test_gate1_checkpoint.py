"""container_gate1_prompt_plan/1.0 — checkpointed image-production retry
(2C-2C-CORR-1). No provider is ever called in these tests."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.core.models import Brand, Product
from apps.pipeline.models import (ApiCallRecord, ConceptInfluencePlan,
                                  ConceptReference, CreativeBrief,
                                  DesignProject, DesignTask, GeneratedImage)
from apps.pipeline.services import container_gate1 as cg1
from apps.pipeline.services import gate1_checkpoint as ckpt

User = get_user_model()
IDS = ["A_AMBER_NOCTURNE", "B_ROSE_SMOKE", "C_NOCTURNE_APOTHECARY"]


def _valid_payload(ref_ids, plan_hash):
    """A payload that genuinely passes the container Gate-1 validator."""
    prompt = ("A premium thirty millilitre frosted glass dropper bottle "
              "with a flat shoulder and refined metallic collar stands on "
              "a seamless studio surface, rendered as a photoreal product "
              "concept with clearly readable BBROSE identity and product "
              "name typography on the front face of the bottle and a "
              "coordinated secondary carton behind it, ")
    variations = []
    for n, vid in enumerate(IDS):
        variations.append({
            "variation_id": vid, "title": f"T{n} {vid}",
            "prompt": prompt + f"variation {vid} treatment number {n}.",
            "typography_signature": f"typography-{n}-{vid}",
            "composition_signature": f"composition-{n}-{vid}",
            "motif_signature": f"motif-{n}-{vid}",
            "cap_body_signature": f"cap-{n}-{vid}",
            "decoration_zone_signature": f"zones-{n}-{vid}",
            "color_field_signature": f"colour-{n}-{vid}",
            "finish_signature": f"finish-{n}-{vid}",
            "native_reconstruction_plan": f"plan-{n}-{vid}",
            "reference_ids": list(ref_ids),
        })
    return {"schema_version": cg1.CONTAINER_GATE1_SCHEMA,
            "approved_reference_ids": sorted(ref_ids),
            "influence_plan_hash": plan_hash,
            "variations": variations}


class _StubAria:
    def __init__(self, task):
        self.task = task
        self.logged = []

    def log(self, msg, **kw):
        self.logged.append(msg)

    def _log_for(self, agent):
        return lambda *a, **k: None

    def _product_profile(self):
        return {}

    def _target(self):
        from apps.pipeline.targets import get_target
        return get_target(self.task.design_target)


class CheckpointTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ckpt_")
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        product = Product.objects.create(
            brand=brand, product_id="BBR-T-1", name="T", category="SK",
            year=2026, product_type="serum")
        self.user = User.objects.create_superuser("ckptop", password="x")
        self.project = DesignProject.objects.create(
            brand=brand, product=product, brief="b",
            design_target="complete_product", status="container",
            metadata={
                "gate1_variation_spec": {
                    "schema_version": "container_gate1_variation_spec/1.0",
                    "direction_id": "d1",
                    "variation_identities": IDS,
                    "richness_directives": "briefs", "max_prompt_attempts": 1},
                "web_grounded_pilot": {
                    "budget": {"pilot_ceiling_calls": 32},
                    "provider_context_contract": {
                        "raw_image_inputs": {"source_ids": [53, 54]}}},
            })
        self.task = DesignTask.objects.create(
            brand=brand, product=product, task_text="b",
            design_target="product_container", stage="container",
            project=self.project, status="failed", created_by=self.user)
        from apps.pipeline.design_intent import build_design_intent
        from apps.pipeline.tests.direction_fixtures import valid_document
        fx = valid_document()
        document = build_design_intent(
            brief={"brand": "BBROSE", "product_name": "T",
                   "product_category": "SK",
                   "design_target": "product_container"},
            intent=fx["design_intent"], directions=fx["directions"])
        self.brief = CreativeBrief.objects.create(
            task=self.task, directions=document["directions"],
            design_intent={k: v for k, v in document.items()
                           if k != "directions"},
            selected_direction_id="d1")
        # §BH55 Phase 4 ("the media stubs"): this wrote its stub into the REAL media tree — Path("media") resolved
        # from the working directory, not from MEDIA_ROOT — and left `media/test_ckpt_tmp/` behind after every run.
        # Its own media root now, for the run's length, so the suite leaves no mark on the repository.
        self._media = tempfile.TemporaryDirectory()
        self._media_override = override_settings(MEDIA_ROOT=self._media.name)
        self._media_override.enable()
        self.media_rel = f"test_ckpt_tmp/{Path(self.tmp).name}"
        media_dir = Path(self._media.name) / self.media_rel
        media_dir.mkdir(parents=True, exist_ok=True)
        (media_dir / "r.png").write_bytes(b"\x89PNG fakebytes")
        self.refs = []
        for n in (1, 2):
            self.refs.append(ConceptReference.objects.create(
                task=self.task, source_type="WEB_REFERENCE",
                library_item_id=f"web_source:{52 + n}",
                title=f"ref{n}", description="PHYSICAL_GEOMETRY only",
                relevance_reason="t", retrieval_score=1.0,
                image_root="media", image_path=f"{self.media_rel}/r.png",
                permission_status="USER_APPROVED_FOR_CONCEPT_REFERENCE",
                approved_by=self.user))
        self.plan = ConceptInfluencePlan.objects.create(
            task=self.task, plan={"p": 1}, plan_hash="ph" * 32)
        self.payload = _valid_payload([r.pk for r in self.refs],
                                      self.plan.plan_hash)
        self.prompts = [{"direction_name": "N",
                         "full_prompt": v["prompt"], "variation_id":
                         v["variation_id"], "notes": v["title"],
                         "assigned_reference_ids": v["reference_ids"]}
                        for v in self.payload["variations"]]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        self._media_override.disable()
        self._media.cleanup()

    def _checkpoint(self):
        return ckpt.create_checkpoint(
            self.task, payload=self.payload, prompts=self.prompts,
            pe_call_id=219, provider_model="anthropic:test")

    def test_passed_plan_becomes_active_checkpoint_and_reuses(self):
        cp = self._checkpoint()
        assert cp["schema_version"] == ckpt.CHECKPOINT_SCHEMA
        assert cp["state"] == ckpt.STATE_VALIDATED
        assert cp["prompt_engineer_call_id"] == 219
        assert list(cp["variations"]) == IDS
        ok, codes = ckpt.verify_checkpoint(self.task)
        assert ok and not codes
        calls_before = ApiCallRecord.objects.count()
        aria = _StubAria(self.task)
        with patch("apps.pipeline.services.gate1_prompts."
                   "build_regeneration_prompts") as builder:
            result = aria._target().gate1_variation_plan(
                aria, {"direction_id": "d1", "name": "N"})
        builder.assert_not_called()               # PE skipped entirely
        assert result.ok is True
        assert result.attempts == 0
        assert [p["variation_id"] for p in result.prompts] == IDS
        assert ApiCallRecord.objects.count() == calls_before  # no PE record
        assert "no provider call" in result.raw_responses[0]

    def test_bh67c4_a_slot_named_plan_checkpoints_and_reuses_under_the_slot_rule(self):
        """§BH67(c)4: with no person's identities for the project the variations name themselves. The checkpoint keys
        its variations by the plan's OWN ids, revalidates by the slot rule the plan was made under, and hands the
        budget guard those ids — a default-contract checkpoint stored no identities, and could not revalidate."""
        meta = dict(self.project.metadata)
        meta["gate1_variation_spec"] = {k: v for k, v in meta["gate1_variation_spec"].items()
                                        if k != "variation_identities"}
        self.project.metadata = meta
        self.project.save(update_fields=["metadata"])
        named = ["A_ORCHARD_HOUR", "B_SILK_TIDE", "C_LANTERN_ROW"]
        for v, p, vid in zip(self.payload["variations"], self.prompts, named):
            v["variation_id"] = p["variation_id"] = vid
        cp = self._checkpoint()
        assert cp["variation_identities"] == [] and list(cp["variations"]) == named
        assert ckpt.plan_variation_ids(cp) == named
        result = ckpt.checkpoint_plan_result(self.task)
        assert result.ok and [p["variation_id"] for p in result.prompts] == named
        # a plan whose ids break their slots is refused on revalidation, by the slot
        cp["prompt_plan"]["payload"]["variations"][0]["variation_id"] = "variation_1"
        meta = dict(self.project.metadata)
        meta[ckpt.CHECKPOINT_KEY] = cp
        self.project.metadata = meta
        self.project.save(update_fields=["metadata"])
        refused = ckpt.checkpoint_plan_result(self.task)
        assert not refused.ok and any(cg1.CONTAINER_VARIATION_IDENTITY_MISSING in c for c in refused.codes)

    def test_a_plan_made_without_references_revalidates_under_the_field_set_it_was_made_under(self):
        """A plan generated with no approved references carries no reference_ids (CORR-2 §7,
        CONTAINER_REQUIRED_FIELDS_NO_REFS). The checkpoint's revalidation demanded them of every plan, so every such
        checkpoint was refused on reuse — tasks 84, 88, 89 and 91 each hold one (measured read-only). It revalidates
        under the field set the plan was made under; a plan that WAS made with references still must carry them."""
        for r in self.refs:
            r.delete()
        self.plan.delete()
        self.task.refresh_from_db()
        for v, p in zip(self.payload["variations"], self.prompts):
            v.pop("reference_ids")
            p["assigned_reference_ids"] = None
        self.payload["approved_reference_ids"] = []
        self.payload["influence_plan_hash"] = ""
        cp = self._checkpoint()
        assert cp["reference_ids"] == [] and cp["influence_plan_hash"] == ""
        result = ckpt.checkpoint_plan_result(self.task)
        assert result.ok, result.codes

    @pytest.mark.filterwarnings("ignore")
    def test_context_drift_invalidates_without_rebuild(self):
        self._checkpoint()
        drifts = [
            lambda: self.project.metadata["gate1_variation_spec"].update(
                {"richness_directives": "CHANGED"}),
            lambda: setattr(self.refs[0], "description", "CHANGED scope"),
            lambda: setattr(self.plan, "plan_hash", "zz" * 32),
        ]
        for mutate in drifts:
            with self.subTest(mutate=mutate):
                mutate()
                self.project.save(update_fields=["metadata"])
                self.refs[0].save()
                self.plan.save()
                self.task.refresh_from_db()
                ok, codes = ckpt.verify_checkpoint(self.task)
                assert ok is False
                assert codes[0] == \
                    ckpt.GATE1_PROMPT_PLAN_CHECKPOINT_INVALIDATED
                aria = _StubAria(self.task)
                with patch("apps.pipeline.services.gate1_prompts."
                           "build_regeneration_prompts") as builder:
                    result = aria._target().gate1_variation_plan(
                        aria, {"direction_id": "d1", "name": "N"})
                builder.assert_not_called()       # never silently rebuilt
                assert result.ok is False
                assert ckpt.GATE1_PROMPT_PLAN_CHECKPOINT_INVALIDATED in \
                    result.codes

    def test_reference_file_drift_invalidates(self):
        self._checkpoint()
        (Path(self._media.name) / self.media_rel / "r.png").write_bytes(
            b"\x89PNG DIFFERENT")
        ok, codes = ckpt.verify_checkpoint(self.task)
        assert ok is False
        assert "reference file hashes changed" in " ".join(codes)

    def test_billing_block_preserves_plan_and_requires_ack(self):
        self._checkpoint()
        rerun_count_before = self.task.image_rerun_count
        ckpt.mark_billing_blocked(self.task, "A_AMBER_NOCTURNE")
        cp = ckpt.load_checkpoint(self.task)
        assert cp["state"] == ckpt.STATE_BILLING_BLOCKED
        assert cp["variations"]["A_AMBER_NOCTURNE"]["state"] == \
            ckpt.V_BILLING_BLOCKED
        # B and C untouched; the plan itself untouched; the regeneration
        # allowance untouched
        assert cp["variations"]["B_ROSE_SMOKE"]["state"] == ckpt.V_PENDING
        assert cp["variations"]["C_NOCTURNE_APOTHECARY"]["state"] == \
            ckpt.V_PENDING
        assert cp["prompt_plan"]["prompts"] == self.prompts
        self.task.refresh_from_db()
        assert self.task.image_rerun_count == rerun_count_before
        # retry without the owner acknowledgement is HELD (zero calls)
        aria = _StubAria(self.task)
        with patch("apps.pipeline.services.gate1_prompts."
                   "build_regeneration_prompts") as builder:
            result = aria._target().gate1_variation_plan(
                aria, {"direction_id": "d1", "name": "N"})
        builder.assert_not_called()
        assert result.ok is False
        assert ckpt.BILLING_ACK_REQUIRED in result.codes
        # acknowledgement releases the hold
        ckpt.acknowledge_billing(self.task, actor=self.user)
        cp = ckpt.load_checkpoint(self.task)
        assert cp["state"] == ckpt.STATE_VALIDATED
        assert cp["billing_acknowledgement"]["statement"] == ckpt.BILLING_ACK
        aria = _StubAria(self.task)
        with patch("apps.pipeline.services.gate1_prompts."
                   "build_regeneration_prompts") as builder:
            result = aria._target().gate1_variation_plan(
                aria, {"direction_id": "d1", "name": "N"})
        builder.assert_not_called()
        assert result.ok is True

    def test_resume_never_duplicates_generated_variation(self):
        self._checkpoint()
        img = GeneratedImage.objects.create(
            task=self.task, direction_name="N", prompt_used="p",
            variation_number=1,
            reference_provenance={"variation_identity": "A_AMBER_NOCTURNE"})
        found = ckpt.existing_variation_image(self.task, "A_AMBER_NOCTURNE")
        assert found == img
        assert ckpt.existing_variation_image(self.task,
                                             "B_ROSE_SMOKE") is None
        img.superseded = True
        img.save()
        assert ckpt.existing_variation_image(self.task,
                                             "A_AMBER_NOCTURNE") is None

    def test_budget_guard_stops_before_spend(self):
        cp = self._checkpoint()
        cp["slice_budget"] = {"ledger_at_slice_start":
                              ApiCallRecord.objects.count() - 2,
                              "slice_cap": 8}
        self.project.refresh_from_db()
        meta = dict(self.project.metadata)
        meta[ckpt.CHECKPOINT_KEY] = cp
        self.project.metadata = meta
        self.project.save(update_fields=["metadata"])
        assert ckpt.budget_guard(self.task, planned_calls=6) == []
        codes = ckpt.budget_guard(self.task, planned_calls=7)
        assert codes and codes[0] == ckpt.PROVIDER_CALL_BUDGET_EXCEEDED

    def test_prerequisites_gate_and_legacy_freedom(self):
        ready, missing = ckpt.generation_prerequisites(self.task)
        assert ready and not missing
        # composite task missing its spec HOLDS
        meta = dict(self.project.metadata)
        del meta["gate1_variation_spec"]
        self.project.metadata = meta
        self.project.save(update_fields=["metadata"])
        self.task.refresh_from_db()
        ready, missing = ckpt.generation_prerequisites(self.task)
        assert not ready and "active variation spec" in missing
        # non-composite (legacy / task #51 shape) is ALWAYS ready
        legacy = DesignTask.objects.create(
            brand=self.task.brand, product=self.task.product,
            task_text="legacy", design_target="product_container",
            status="queued", created_by=self.user)
        assert ckpt.generation_prerequisites(legacy) == (True, [])

    def test_selection_holds_until_configured_then_releases(self):
        from apps.pipeline.views import select_design_direction
        meta = dict(self.project.metadata)
        spec = meta.pop("gate1_variation_spec")
        self.project.metadata = meta
        self.project.save(update_fields=["metadata"])
        self.brief.selected_direction_id = ""
        self.brief.save(update_fields=["selected_direction_id"])
        self.task.status = "awaiting_direction_selection"
        self.task.save(update_fields=["status"])
        with patch("apps.pipeline.tasks.run_aria_pipeline") as rap:
            payload, http = select_design_direction(self.task, self.user,
                                                    "d1")
            assert http == 200
            assert payload["status"] == ckpt.HOLD_STATUS
            assert "active variation spec" in payload[
                "missing_prerequisites"]
        rap.delay.assert_not_called()             # the race is closed
        self.task.refresh_from_db()
        assert self.task.status == ckpt.HOLD_STATUS
        prereq = self.project.metadata if False else \
            DesignProject.objects.get(id=self.project.id).metadata
        assert prereq[ckpt.PREREQ_KEY]["state"] == \
            "AWAITING_GATE1_GENERATION_CONFIGURATION"
        # configuration completes → retry releases exactly once
        meta = dict(DesignProject.objects.get(id=self.project.id).metadata)
        meta["gate1_variation_spec"] = spec
        self.project.metadata = meta
        self.project.save(update_fields=["metadata"])
        from django.test import Client
        client = Client(HTTP_HOST="testserver")
        client.force_login(self.user)
        with patch("apps.pipeline.tasks.run_aria_pipeline") as rap:
            r = client.post(f"/api/tasks/{self.task.id}/retry/", {},
                            content_type="application/json")
            assert r.status_code == 200
            rap.delay.assert_called_once_with(self.task.id)
        self.task.refresh_from_db()
        assert self.task.status == "queued"

    def test_an_ordinary_complete_product_project_generates_without_the_pilots_governance(self):
        """§BH55 Phase 1 — measured on a no-spend dry run: a NEW Complete Product project carries none of the 2C
        pilot's prerequisites, and every one stopped right after its direction was chosen, in a status the
        dashboard cannot render. Only a project that declares the pilot is held by them now."""
        from apps.pipeline.views import select_design_direction
        self.project.metadata = {}                       # an ordinary project: no pilot, no mandated spec
        self.project.save(update_fields=["metadata"])
        self.task.refresh_from_db()
        assert ckpt.generation_prerequisites(self.task) == (True, [])
        self.brief.selected_direction_id = ""
        self.brief.save(update_fields=["selected_direction_id"])
        self.task.status = "awaiting_direction_selection"
        self.task.save(update_fields=["status"])
        with patch("apps.pipeline.tasks.run_aria_pipeline") as rap, \
                self.captureOnCommitCallbacks(execute=True):
            payload, http = select_design_direction(self.task, self.user, "d1")
            assert http == 200 and payload["status"] == "queued", payload
        rap.delay.assert_called_once_with(self.task.id)          # generation is enqueued, not held
        self.task.refresh_from_db()
        assert self.task.status != ckpt.HOLD_STATUS
        # a project that declares the pilot is still held by its own prerequisites
        self.project.metadata = {"web_grounded_pilot": {}}
        self.project.save(update_fields=["metadata"])
        self.task.refresh_from_db()
        ready, missing = ckpt.generation_prerequisites(self.task)
        assert not ready and {"active variation spec", "provider budget", "prohibited-use contract"} <= set(missing)

    def test_selection_enqueues_directly_when_ready(self):
        from apps.pipeline.views import select_design_direction
        self.brief.selected_direction_id = ""
        self.brief.save(update_fields=["selected_direction_id"])
        self.task.status = "awaiting_direction_selection"
        self.task.save(update_fields=["status"])
        with patch("apps.pipeline.tasks.run_aria_pipeline") as rap, \
                self.captureOnCommitCallbacks(execute=True):
            payload, http = select_design_direction(self.task, self.user,
                                                    "d1")
            assert http == 200 and payload["status"] == "queued"
        rap.delay.assert_called_once_with(self.task.id)
        meta = DesignProject.objects.get(id=self.project.id).metadata
        assert meta[ckpt.PREREQ_KEY]["state"] == \
            "GATE1_GENERATION_PREREQUISITES_READY"
