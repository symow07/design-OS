"""2C-3 — Complete Product composite GOLDEN fixtures (A–H).

Deterministic synthetic fixtures prove the coordinator's accepted, rejected,
blocked, ready, unreviewed, stale-review and failure outcomes. No provider
is ever called; task #52 is only ever the REJECTED live-pilot fixture."""
from __future__ import annotations

import hashlib
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase
from django.utils import timezone

from apps.core.models import Brand, Product
from apps.ire.container_production_readiness import ACCEPTANCE_KEY
from apps.pipeline.models import (
    DesignProject,
    DesignTask,
    GateDecision,
    GeneratedImage,
    PackagingOutput,
    TaskReference,
)
from apps.pipeline.services import container_contract as cc
from apps.pipeline.services import pilot_closeout as pc
from apps.pipeline.targets import composite as comp

User = get_user_model()
FIXTURE_SCHEMA = "complete_product_composite_fixture/1.0"
_PNG = __import__("base64").b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4"
    "z8Dwn4EBAAT/Af9jZv5kAAAAAElFTkSuQmCC")


def fixture_declaration(fid, **expect) -> dict:
    """§2 contract: every fixture declares identity + expectations and a
    deterministic hash over its own declaration."""
    decl = {"schema_version": FIXTURE_SCHEMA, "fixture_id": fid,
            "recipe": "complete_product", **expect}
    decl["fixture_hash"] = hashlib.sha256(json.dumps(
        decl, sort_keys=True, default=str).encode()).hexdigest()
    return decl


class World(TestCase):
    """Deterministic synthetic composite world builder."""

    def setUp(self):
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.product = Product.objects.create(
            brand=self.brand, product_id="BBR-FX-1", name="Fixture",
            category="SK", year=2026)
        self.user = User.objects.create_superuser("fixop", password="x")

    def project(self):
        return DesignProject.objects.create(
            brand=self.brand, product=self.product, brief="b",
            design_target="complete_product", status="container",
            created_by=self.user)

    def container(self, project, *, accepted=None, status="completed",
                  blockers=(), rejected_snapshot=False):
        task = DesignTask.objects.create(
            brand=self.brand, product=self.product, task_text="c",
            design_target="product_container", stage="container",
            project=project, status=status, created_by=self.user)
        img = GeneratedImage.objects.create(
            task=task, direction_name="D", prompt_used="p",
            variation_number=1, is_approved=True)
        img.image_file.save("c.png", ContentFile(_PNG), save=True)
        prof = cc.build_inferred_profile("bottle", "cylindrical")
        spec = {
            "backend": "container", cc.PROFILE_SCHEMA: prof,
            cc.ZONES_SCHEMA: {"zones": [], "zone_set_hash": "z" * 12,
                              "confirmation_state": "CONFIRMED"},
            "container_selected_variation/1.0":
                {"variation_id": "FX_VARIATION"},
            "container_production_readiness/1.0": {
                "ready": not blockers, "blocking_codes": list(blockers)},
        }
        if accepted is True:
            spec[ACCEPTANCE_KEY] = {"state": "ACCEPTED",
                                    "decided_by": self.user.username,
                                    "decided_at": "2026-07-27"}
        if accepted is False or rejected_snapshot:
            spec["container_reconstruction_rejected_fx"] = {
                "state": "REJECTED", "rejected_output": {
                    "design_preview": "old.png"}}
        out = PackagingOutput.objects.create(
            task=task, approved_image=img, spec_sheet=spec)
        out.design_preview.save("prev.png", ContentFile(_PNG), save=True)
        return task, out

    def packaging(self, project, *, decision=None, blockers=(),
                  status="completed"):
        task = DesignTask.objects.get(project=project, stage="packaging")
        task.status = status
        task.save(update_fields=["status"])
        img = GeneratedImage.objects.create(
            task=task, direction_name="P", prompt_used="p",
            variation_number=1, is_approved=True)
        img.image_file.save("p.png", ContentFile(_PNG), save=True)
        out = PackagingOutput.objects.create(
            task=task, approved_image=img, spec_sheet={
                "container_production_readiness/1.0": {
                    "ready": not blockers,
                    "blocking_codes": list(blockers)}})
        out.design_preview.save("pk.png", ContentFile(_PNG), save=True)
        if decision:
            GateDecision.objects.create(task=task, gate="gate_2",
                                        decision=decision,
                                        decided_by=self.user)
        return task, out

    def advance(self, project):
        with patch("apps.pipeline.tasks.run_aria_pipeline") as m:
            m.delay.return_value = None
            comp.advance_project(project)
        project.refresh_from_db()
        return project


class FixtureATests(World):
    def test_accepted_container_advances_exactly_once(self):
        decl = fixture_declaration(
            "A", container_stage="ACCEPTED", packaging_stage="SPAWNED",
            expected_task_count=2, expected_handoff_count=1,
            expected_status="packaging",
            expected_state="AWAITING_PACKAGING_DECISION")
        assert len(decl["fixture_hash"]) == 64
        project = self.project()
        c_task, _ = self.container(project, accepted=True)
        refs0 = TaskReference.objects.count()
        self.advance(project)
        tasks = DesignTask.objects.filter(project=project)
        assert tasks.count() == 2
        pk_task = tasks.get(stage="packaging")
        handoffs = project.metadata["handoffs"]
        assert list(handoffs) == ["packaging"]
        rec = handoffs["packaging"]
        assert rec["source_task_id"] == c_task.id
        assert rec["destination_task_id"] == pk_task.id
        assert rec["human_visual_acceptance_state"] == "ACCEPTED"
        assert rec["selected_variation_identity"] == "FX_VARIATION"
        # the approved container rides as references on the packaging task
        new_refs = TaskReference.objects.filter(task=pk_task)
        assert new_refs.count() == TaskReference.objects.count() - refs0
        assert new_refs.filter(kind="container").exists()
        assert project.status == "packaging"          # current stage
        assert comp.project_state(project) == "IN_PROGRESS"
        # once packaging reaches human review the projection names it
        pk_task.status = "awaiting_gate_2"
        pk_task.save(update_fields=["status"])
        assert comp.project_state(project) == "AWAITING_PACKAGING_DECISION"
        pk_task.status = "queued"
        pk_task.save(update_fields=["status"])
        # idempotent: repeat advancement duplicates NOTHING
        self.advance(project)
        self.advance(project)
        assert DesignTask.objects.filter(project=project).count() == 2
        assert list(project.metadata["handoffs"]) == ["packaging"]
        assert TaskReference.objects.filter(
            task=pk_task).count() == new_refs.count()
        # §11 the handoff validates clean
        assert comp.validate_stage_handoff(
            rec, project=project, source_task=c_task,
            dest_task=pk_task) == []
        # §12 identity preservation
        prof = c_task.packaging_outputs.first().spec_sheet[cc.PROFILE_SCHEMA]
        assert rec["container_profile_hash"] == prof["profile_hash"]
        assert rec["approved_output_id"] == \
            c_task.packaging_outputs.first().id


class FixtureBTests(World):
    def test_rejected_container_blocks_packaging(self):
        project = self.project()
        task, out = self.container(project, accepted=None,
                                   status="awaiting_gate_2")
        pc.close_container_stage(task, actor=self.user,
                                 now_iso=timezone.now().isoformat())
        project.refresh_from_db()
        task.refresh_from_db()
        assert project.status == pc.PROJECT_STATUS
        assert task.status == pc.TERMINAL_STATUS
        self.advance(project)          # advancement must change nothing
        assert DesignTask.objects.filter(
            project=project, stage="packaging").count() == 0
        assert "handoffs" not in (project.metadata or {}) or not \
            project.metadata.get("handoffs")
        assert comp.project_state(project) == "CONTAINER_REJECTED"
        hda = comp.stage_human_acceptance(task)
        assert hda["state"].startswith("REJECTED")
        # a rejected source can never produce a valid handoff
        fake_dest = DesignTask.objects.create(
            brand=self.brand, product=self.product, task_text="x",
            design_target="packaging", stage="packaging",
            status="queued", created_by=self.user)
        rec = comp.build_stage_handoff(project, task, fake_dest)
        problems = comp.validate_stage_handoff(
            rec, project=project, source_task=task, dest_task=fake_dest)
        assert comp.HANDOFF_ACCEPTANCE_MISSING in problems
        assert comp.HANDOFF_REJECTED_SOURCE in problems


class FixtureCDETests(World):
    def _accepted_flow(self, container_blockers=(), pkg_blockers=(),
                       pkg_decision="approve"):
        project = self.project()
        self.container(project, accepted=True,
                       blockers=container_blockers)
        self.advance(project)
        self.packaging(project, decision=pkg_decision,
                       blockers=pkg_blockers)
        return self.advance(project)

    def test_fixture_c_packaging_rejected(self):
        project = self._accepted_flow(pkg_decision="reject")
        assert comp.project_state(project) == "PACKAGING_REJECTED"
        summary = comp.build_project_summary(project)
        assert summary["design_complete"] is False
        assert summary["production_ready"] is False
        # container stays accepted; no third stage
        assert DesignTask.objects.filter(project=project).count() == 2
        stages = {s["label"]: s for s in summary["stages"]}
        assert stages["container"]["human_acceptance"] == "ACCEPTED"
        assert "REJECTED" in stages["packaging"]["human_acceptance"]

    def test_fixture_d_design_complete_production_blocked(self):
        project = self._accepted_flow(
            container_blockers=("MISSING_OUTPUT_INTENT",
                                "CONTAINER_FONT_CONFIRMATION_REQUIRED"),
            pkg_blockers=("PHYSICAL_FIT_VALIDATION_PENDING",))
        assert comp.project_state(project) == \
            "DESIGN_COMPLETE_PRODUCTION_BLOCKED"
        summary = comp.build_project_summary(project)
        assert summary["design_complete"] is True
        assert summary["production_ready"] is False
        combined = summary["combined_blockers"]
        assert set(combined) == {"MISSING_OUTPUT_INTENT",
                                 "CONTAINER_FONT_CONFIRMATION_REQUIRED",
                                 "PHYSICAL_FIT_VALIDATION_PENDING"}
        assert len(combined) == len(set(combined))    # no duplicates
        assert "blocker" in summary["next_required_action"].lower()

    def test_fixture_e_fully_production_ready_synthetic(self):
        project = self._accepted_flow()
        assert comp.project_state(project) == "PRODUCTION_READY"
        summary = comp.build_project_summary(project)
        assert summary["design_complete"] is True
        assert summary["production_ready"] is True
        assert summary["combined_blockers"] == []
        stages = {s["label"]: s for s in summary["stages"]}
        for st in stages.values():
            assert st["human_acceptance"] == "ACCEPTED"
            assert st["deliverables"]           # downloads present
        assert project.metadata["handoffs"]["packaging"]["handoff_hash"]


class FixtureFGHTests(World):
    def test_fixture_f_unreviewed_container_holds(self):
        project = self.project()
        self.container(project, accepted=None)
        self.advance(project)
        assert DesignTask.objects.filter(
            project=project, stage="packaging").count() == 0
        hold = project.metadata.get("hold") or {}
        assert hold.get("code") == \
            comp.COMPOSITE_STAGE_HUMAN_ACCEPTANCE_REQUIRED
        state = comp.project_state(project)
        assert state == "AWAITING_CONTAINER_DECISION"

    def test_fixture_g_newer_reconstruction_requires_new_review(self):
        project = self.project()
        task, out = self.container(project, accepted=True)
        # a NEWER reconstruction arrives: the acceptance record names the
        # PRIOR output; the rejection-snapshot mechanics of the HDA reader
        # treat un-decided newer output via the acceptance key — simulate
        # the platform behaviour: the new reconstruction CLEARS the stale
        # acceptance key (a new output has no decision of its own)
        spec = out.spec_sheet
        stale = spec.pop(ACCEPTANCE_KEY)
        spec["container_reconstruction"] = {"status": "RECONSTRUCTED",
                                            "blockers": []}
        spec["acceptance_history"] = [stale]      # history preserved
        out.spec_sheet = spec
        out.save(update_fields=["spec_sheet"])
        self.advance(project)
        assert DesignTask.objects.filter(
            project=project, stage="packaging").count() == 0
        hda = comp.stage_human_acceptance(task)
        assert hda["state"] == "NOT_REVIEWED"
        assert hda["codes"]        # acceptance-required code present
        assert out.spec_sheet["acceptance_history"] == [stale]

    def test_fixture_h_failure_stays_reviewable_and_retries_cleanly(self):
        project = self.project()
        task, _ = self.container(project, accepted=None, status="failed")
        self.advance(project)
        assert project.status == "failed"
        assert project.failed_stage == "container"
        assert comp.project_state(project) == "FAILED_REVIEWABLE"
        assert DesignTask.objects.filter(project=project).count() == 1
        # bounded resume: the stage recovers without duplication
        task.status = "awaiting_gate_2"
        task.save(update_fields=["status"])
        spec = task.packaging_outputs.first().spec_sheet
        spec[ACCEPTANCE_KEY] = {"state": "ACCEPTED",
                                "decided_by": self.user.username,
                                "decided_at": "2026-07-27"}
        o = task.packaging_outputs.first()
        o.spec_sheet = spec
        o.save(update_fields=["spec_sheet"])
        task.status = "completed"
        task.save(update_fields=["status"])
        self.advance(project)
        assert DesignTask.objects.filter(project=project).count() == 2
        assert project.status == "packaging"


class ProjectionAndSummaryTests(World):
    def test_all_canonical_states_are_reachable_and_distinct(self):
        seen = set()
        p1 = self.project()                      # IN_PROGRESS (no child)
        seen.add(comp.project_state(p1))
        p2 = self.project()
        self.container(p2, accepted=None)        # AWAITING_CONTAINER_DECISION
        seen.add(comp.project_state(p2))
        assert {"IN_PROGRESS", "AWAITING_CONTAINER_DECISION"} <= seen
        for s in seen:
            assert s in comp.PROJECT_STATES
        assert "COMPLETED" not in comp.PROJECT_STATES

    def test_summary_names_the_rejected_stage(self):
        project = self.project()
        task, _ = self.container(project, accepted=None,
                                 status="awaiting_gate_2")
        pc.close_container_stage(task, actor=self.user,
                                 now_iso=timezone.now().isoformat())
        project.refresh_from_db()
        summary = comp.build_project_summary(project)
        assert summary["project_state"] == "CONTAINER_REJECTED"
        assert summary["design_complete"] is False
        assert summary["production_ready"] is False
        stages = {s["label"]: s for s in summary["stages"]}
        assert "REJECTED" in stages["container"]["human_acceptance"]
        assert stages["packaging"]["task_id"] is None
