from apps.pipeline.tests.quality_fixtures import critique, reviewed
"""Phase 8 regression tests — gate concurrency, ownership, retry, redownload.

Covers audit findings C2 (stranded states / retry), C3 (gate races + Gate 2
ownership), and H1 (image redownload endpoint).
"""
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase

from apps.core.models import Brand
from apps.pipeline.models import DesignTask, GeneratedImage, PackagingOutput


class GateApiTestBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("t", "t@t.com", "pw")
        self.client.force_login(self.user)
        self.brand = Brand.objects.create(name="B", master_brief="x")

    def _task(self, status, **kw):
        return DesignTask.objects.create(
            brand=self.brand, task_text="t", status=status, **kw
        )

    def _image(self, task):
        return reviewed(GeneratedImage.objects.create(
            task=task, direction_name="d", prompt_used="p", image_url="u"
        ))


class GateConcurrencyTests(GateApiTestBase):
    """C3 — atomic transitions: second identical approval gets 409."""

    @patch("apps.pipeline.tasks.resume_aria_gate1.delay")
    def test_double_gate1_approve_second_gets_409(self, mock_delay):
        task = self._task("awaiting_gate_1")
        img = self._image(task)
        url = f"/api/tasks/{task.id}/gate1_approve/"
        first = self.client.post(url, {"image_id": img.id})
        second = self.client.post(url, {"image_id": img.id})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(mock_delay.call_count, 1)

    @patch("apps.pipeline.tasks.resume_aria_gate2.delay")
    def test_gate2_approve_rejects_foreign_output(self, mock_delay):
        task = self._task("awaiting_gate_2")
        other = self._task("awaiting_gate_2")
        foreign = PackagingOutput.objects.create(
            task=other, spec_sheet={}, approved_image=self._image(other)
        )
        res = self.client.post(
            f"/api/tasks/{task.id}/gate2_approve/",
            {"packaging_output_id": foreign.id},
        )
        self.assertIn(res.status_code, (404, 400, 409))
        mock_delay.assert_not_called()
        task.refresh_from_db()
        self.assertEqual(task.status, "awaiting_gate_2")


class TaskRetryTests(GateApiTestBase):
    """C2 — retry recovers stranded intermediate states, not just 'failed'."""

    def test_retry_rejected_for_active_status(self):
        task = self._task("awaiting_gate_1")
        res = self.client.post(f"/api/tasks/{task.id}/retry/")
        self.assertEqual(res.status_code, 409)

    @patch("apps.pipeline.tasks.run_aria_pipeline.delay")
    def test_retry_from_failed_requeues(self, mock_delay):
        task = self._task("failed", error_message="boom")
        res = self.client.post(f"/api/tasks/{task.id}/retry/")
        self.assertEqual(res.status_code, 200)
        mock_delay.assert_called_once()
        task.refresh_from_db()
        self.assertEqual(task.error_message, "")

    @patch("apps.pipeline.tasks.resume_aria_gate1.delay")
    def test_retry_from_stranded_gate_1_approved(self, mock_delay):
        task = self._task("gate_1_approved")
        img = self._image(task)
        img.is_approved = True
        img.save()
        res = self.client.post(f"/api/tasks/{task.id}/retry/")
        self.assertEqual(res.status_code, 200)
        mock_delay.assert_called_once()

    @patch("apps.pipeline.tasks.resume_aria_gate1.delay")
    def test_his_second_blocker_123_a_step_still_working_is_never_run_again_beside_itself(self, mock_delay):
        """[His second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010).]
        123's Garden Wrap, resumed 14 s into the step after its choice, read its map twice beside itself. A step whose
        log is still moving is refused in words — nothing dispatched, nothing moved — and the page is told so (no
        Resume offered); quiet past twice its measured time, it resumes."""
        from datetime import timedelta

        from django.utils import timezone

        from apps.pipeline.models import AgentLog
        from apps.pipeline.step_times import STALLED_TIMES, typical
        task = self._task("gate_1_approved")
        img = self._image(task)
        img.is_approved = True
        img.save()
        line = AgentLog.objects.create(task=task, agent_name="ARIA", action="ARIA: Gate 1 approved — image %d" % img.pk)
        res = self.client.post(f"/api/tasks/{task.id}/retry/")
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.json()["code"], "STILL_WORKING")
        self.assertIn("still working on this step", res.json()["error"])
        mock_delay.assert_not_called()
        self.assertIs(self.client.get(f"/api/tasks/{task.id}/status/").json()["stalled"], False)
        from apps.pipeline.step_times import STALLED_UNMEASURED_SECONDS
        quiet = STALLED_TIMES * max([v[0] for v in typical().values()] + [STALLED_UNMEASURED_SECONDS]) + 60.0
        AgentLog.objects.filter(pk=line.pk).update(timestamp=timezone.now() - timedelta(seconds=quiet))
        self.assertIs(self.client.get(f"/api/tasks/{task.id}/status/").json()["stalled"], True)
        res = self.client.post(f"/api/tasks/{task.id}/retry/")
        self.assertEqual(res.status_code, 200)
        mock_delay.assert_called_once()

    def test_retry_from_gate_1_approved_without_image_reopens_gate(self):
        task = self._task("gate_1_approved")
        res = self.client.post(f"/api/tasks/{task.id}/retry/")
        self.assertEqual(res.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status, "awaiting_gate_1")


class CrashSafeResumeTests(GateApiTestBase):
    """C2 — an exception inside a resume marks the task failed."""

    def test_resume_crash_marks_task_failed(self):
        from apps.pipeline.agents.aria import ARIAAgent

        task = self._task("gate_1_approved")
        agent = ARIAAgent(task.id)
        # A nonexistent image id makes the resume raise internally; the
        # crash_safe wrapper must convert that into status='failed' rather
        # than letting the exception strand the task.
        try:
            agent.resume_after_gate_1(999999)
        except Exception:
            self.fail("crash_safe wrapper did not swallow the exception")
        task.refresh_from_db()
        self.assertEqual(task.status, "failed")
        self.assertTrue(task.error_message)


class ImageRedownloadTests(GateApiTestBase):
    """H1 — per-image redownload endpoint."""

    @patch("apps.pipeline.services.round_calls.download_image_bytes")
    def test_redownload_recovers_failed_image(self, mock_dl):
        import tempfile

        from django.test import override_settings

        task = self._task("awaiting_gate_1")
        img = self._image(task)
        img.download_failed = True
        img.image_url = "https://example.com/x.png"
        img.save()
        mock_dl.return_value = b"png-bytes"
        with tempfile.TemporaryDirectory() as tmp, override_settings(MEDIA_ROOT=tmp):
            res = self.client.post(f"/api/images/{img.id}/redownload/")
        self.assertEqual(res.status_code, 200)
        img.refresh_from_db()
        self.assertFalse(img.download_failed)

    def test_redownload_requires_auth(self):
        task = self._task("awaiting_gate_1")
        img = self._image(task)
        self.client.logout()
        res = self.client.post(f"/api/images/{img.id}/redownload/")
        self.assertIn(res.status_code, (302, 401, 403))
