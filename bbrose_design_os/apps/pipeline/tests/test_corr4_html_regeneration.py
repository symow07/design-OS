"""Browser-independent Gate-1 regeneration (2A-6E-CORR-4 §3–§6, §10–§11).

The essential regeneration workflow is server-rendered HTML: GET renders a
confirmation page (no job, no provider), POST re-validates against CURRENT
database state behind a signed expiring token, dry-run mode renders
DRY_RUN_ACCEPTED creating nothing, live mode creates exactly one idempotent
job with POST/Redirect/GET. Every refusal renders a visible page with a
stable code.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

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


class HtmlRegenerationTestCase(TestCase):
    def setUp(self):
        # Exercise retained legacy internals only; Day1 tests verify real admission is closed.
        hold = patch('apps.pipeline.services.gate1_regeneration.ensure_reference_refresh_enabled')
        hold.start()
        self.addCleanup(hold.stop)
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, True)
        self._media_override = override_settings(MEDIA_ROOT=self.media)
        self._media_override.enable()
        self.addCleanup(self._media_override.disable)
        self.user = User.objects.create_superuser("hr", "h@h.com", "pw")
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.task = DesignTask.objects.create(
            brand=self.brand, task_text="Baked Powder carton",
            status="awaiting_gate_1", created_by=self.user)
        from apps.pipeline.design_intent import (
            build_design_brief, build_design_intent)
        from .direction_fixtures import valid_document
        raw = valid_document()
        document = build_design_intent(
            brief=build_design_brief({
                "brand": "BBROSE", "product_name": "Baked Powder",
                "product_category": "face powder",
                "design_target": "packaging"}),
            intent=raw["design_intent"], directions=raw["directions"])
        self.brief = CreativeBrief.objects.create(
            task=self.task,
            design_intent={k: v for k, v in document.items()
                           if k != "directions"},
            directions=document["directions"],
            selected_direction_id=document["directions"][0]["direction_id"])
        self.images = [GeneratedImage.objects.create(
            task=self.task, direction_name="d", prompt_used=f"p{n}",
            variation_number=n,
            user_rejection_label="REJECTED_BY_USER — X") for n in (1, 2, 3)]
        self.rows = []
        for index in range(2):
            (Path(self.media) / f"h{index}.png").write_bytes(b"\x89PNG")
            self.rows.append(ConceptReference.objects.create(
                task=self.task, source_type="HISTORICAL_DESIGN_REFERENCE",
                library_item_id=f"design_reference:h{index}",
                title=f"h{index}", image_root="media",
                image_path=f"h{index}.png",
                permission_status=ConceptReference.PERMISSION_APPROVED,
                approved_by=self.user))
        plan = build_influence_plan(self.task, self.rows)
        self.plan = ConceptInfluencePlan.objects.create(
            task=self.task, plan=plan, plan_hash=plan_hash(plan),
            created_by=self.user)
        self.url = f"/dashboard/tasks/{self.task.pk}/gate1-regeneration/confirm/"
        self.client.force_login(self.user)

    def _token(self):
        response = self.client.get(self.url)
        assert response.status_code == 200
        content = response.content.decode()
        import re
        match = re.search(r'name="confirmation_token" value="([^"]+)"',
                          content)
        assert match, "confirmation token missing from the page"
        return match.group(1), content


@override_settings(GATE1_REGENERATION_MODE="dry_run")
class ConfirmationPageTests(HtmlRegenerationTestCase):
    def test_get_renders_the_full_contract_and_creates_nothing(self):
        calls = ApiCallRecord.objects.count()
        token, content = self._token()
        for expected in (f"#{self.rows[0].pk} h0", f"#{self.rows[1].pk} h1",
                         self.plan.plan_hash[:16],
                         "Editorial Panel", "Layered Type Field",
                         "Powder Constellation", "DRY RUN",
                         "concept reference", "Confirm regeneration",
                         "Cancel"):
            assert expected in content, expected
        assert Gate1RegenerationJob.objects.count() == 0
        assert ApiCallRecord.objects.count() == calls

    def test_wrong_state_renders_a_visible_stable_code(self):
        self.task.status = "completed"
        self.task.save()
        response = self.client.get(self.url)
        assert response.status_code == 409
        assert "TASK_STATE_REJECTED" in response.content.decode()

    def test_the_pages_are_in_the_one_shell_and_say_themselves_in_words(self):
        # [the owner's answer to the UI directions of 2026-09-25: "One clean visual system", "Plain words everywhere.
        # No engine codes on screen." — each code keeps its page, folded under "What the record says"]
        _token, content = self._token()
        assert 'class="bar"' in content and "Draw the concepts again" in content
        assert ' style="' not in content and "<style" not in content
        self.task.status = "completed"
        self.task.save()
        refused = self.client.get(self.url).content.decode()
        assert "This design is not at choosing its concept" in refused
        shown, _, folded = refused.partition('<details class="tech">')
        assert "TASK_STATE_REJECTED" not in shown and "TASK_STATE_REJECTED" in folded
        assert f'href="/dashboard/designs/{self.task.pk}/"' in refused              # back to the design itself

    def test_missing_reference_file_is_a_visible_error(self):
        (Path(self.media) / "h0.png").unlink()
        response = self.client.get(self.url)
        assert "REFERENCE_FILE_MISSING" in response.content.decode()

    def test_non_reviewer_is_visibly_rejected(self):
        outsider = User.objects.create_user("nobody", password="x")
        self.client.force_login(outsider)
        response = self.client.get(self.url)
        assert response.status_code == 403
        assert "AUTHORIZATION_REJECTED" in response.content.decode()

    def test_csrf_is_enforced_on_the_post(self):
        token, _ = self._token()
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        response = strict.post(self.url, {"confirmation_token": token})
        assert response.status_code == 403


@override_settings(GATE1_REGENERATION_MODE="dry_run")
class DryRunPostTests(HtmlRegenerationTestCase):
    def test_confirmed_dry_run_renders_accepted_and_creates_nothing(self):
        calls = ApiCallRecord.objects.count()
        images = set(GeneratedImage.objects.values_list("pk", flat=True))
        token, _ = self._token()
        with patch("apps.pipeline.tasks.regenerate_gate1_references.delay") \
                as mock_delay, \
                patch("apps.pipeline.agents.creative_director.call_claude") \
                as mock_cd:
            response = self.client.post(
                self.url, {"confirmation_token": token})
        content = response.content.decode()
        assert response.status_code == 200
        assert "DRY_RUN_ACCEPTED" in content
        assert "Diagnostic request ID" in content
        assert str(self.rows[0].pk) in content
        assert self.plan.plan_hash[:16] in content
        mock_delay.assert_not_called()
        mock_cd.assert_not_called()
        assert Gate1RegenerationJob.objects.count() == 0
        assert ApiCallRecord.objects.count() == calls
        assert set(GeneratedImage.objects.values_list("pk", flat=True)) == \
            images
        self.task.refresh_from_db()
        assert self.task.status == "awaiting_gate_1"
        for image in self.images:
            image.refresh_from_db()
            assert image.user_rejection_label.startswith("REJECTED_BY_USER")

    def test_stale_reference_set_is_rejected(self):
        token, _ = self._token()
        (Path(self.media) / "h2.png").write_bytes(b"\x89PNG")
        ConceptReference.objects.create(
            task=self.task, source_type="HISTORICAL_DESIGN_REFERENCE",
            library_item_id="design_reference:h2", title="h2",
            image_root="media", image_path="h2.png",
            permission_status=ConceptReference.PERMISSION_APPROVED,
            approved_by=self.user)
        response = self.client.post(self.url, {"confirmation_token": token})
        assert "REFERENCE_APPROVAL_CHANGED" in response.content.decode()
        assert Gate1RegenerationJob.objects.count() == 0

    def test_changed_plan_hash_is_rejected(self):
        token, _ = self._token()
        self.plan.plan_hash = "f" * 64
        self.plan.save()
        response = self.client.post(self.url, {"confirmation_token": token})
        assert "INFLUENCE_PLAN_HASH_MISMATCH" in response.content.decode()

    def test_garbage_token_is_a_visible_error(self):
        response = self.client.post(self.url,
                                    {"confirmation_token": "not-a-token"})
        assert response.status_code == 400
        assert "DRY_RUN_VALIDATION_FAILED" in response.content.decode()

    def test_repeated_dry_run_post_is_idempotent(self):
        token, _ = self._token()
        first = self.client.post(self.url, {"confirmation_token": token})
        second = self.client.post(self.url, {"confirmation_token": token})
        assert first.status_code == second.status_code == 200
        assert "DRY_RUN_ACCEPTED" in second.content.decode()
        assert Gate1RegenerationJob.objects.count() == 0


@override_settings(GATE1_REGENERATION_MODE="live")
class LiveModePostTests(HtmlRegenerationTestCase):
    def _confirm(self):
        token, _ = self._token()
        with patch("apps.pipeline.tasks.regenerate_gate1_references.delay") \
                as mock_delay, \
                patch("apps.pipeline.agents.creative_director.call_claude") \
                as mock_cd:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    self.url, {"confirmation_token": token})
        return response, mock_delay, mock_cd

    def test_live_post_creates_one_job_and_redirects(self):
        response, mock_delay, mock_cd = self._confirm()
        assert response.status_code == 302           # POST/Redirect/GET
        job = Gate1RegenerationJob.objects.get()
        assert f"/gate1-regeneration/jobs/{job.pk}/" in response.url
        assert mock_delay.call_count == 1
        mock_cd.assert_not_called()                  # never the CD
        assert sorted(job.approved_reference_ids) == \
            sorted(r.pk for r in self.rows)
        assert job.influence_plan_hash == self.plan.plan_hash
        status_page = self.client.get(response.url)
        content = status_page.content.decode()
        assert "QUEUED" in content
        assert "Refresh status" in content

    def test_repeated_live_post_reuses_the_active_job(self):
        self._confirm()
        # a reloaded confirmation page redirects straight to the status page
        get_again = self.client.get(self.url)
        assert get_again.status_code == 302
        job = Gate1RegenerationJob.objects.get()
        # and a resubmitted POST also reuses the job — never a duplicate
        with patch("apps.pipeline.tasks.regenerate_gate1_references.delay") \
                as mock_delay:
            resubmit = self.client.post(self.url,
                                        {"confirmation_token": "irrelevant"})
        assert resubmit.status_code == 302
        assert f"/gate1-regeneration/jobs/{job.pk}/" in resubmit.url
        mock_delay.assert_not_called()
        assert Gate1RegenerationJob.objects.count() == 1
