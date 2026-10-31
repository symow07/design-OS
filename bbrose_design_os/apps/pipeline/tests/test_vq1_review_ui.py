"""VQ-1-CORR-1 — visual-review UI + bounded artifact delivery."""
from __future__ import annotations

import json
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from apps.pipeline import vq_views

User = get_user_model()


class VQ1UITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("vqop", password="x")
        self.client = Client(HTTP_HOST="127.0.0.1")
        # NEVER touch the real human-review record — redirect state writes
        # to a temp file for the duration of the test
        import shutil
        import tempfile
        self._real = vq_views.REVIEW_STATE_FILE
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        self._tmp = os.path.join(folder, "review_state.json")
        vq_views.REVIEW_STATE_FILE = self._tmp

    def tearDown(self):
        vq_views.REVIEW_STATE_FILE = self._real
        if os.path.exists(self._tmp):
            os.remove(self._tmp)

    def test_artifacts_served_with_correct_types_and_content(self):
        self.client.force_login(self.user)
        png = self.client.get("/api/visual-quality/vq1/review-png/")
        assert png.status_code == 200
        assert png["Content-Type"] == "image/png"
        body = b"".join(png.streaming_content)
        assert body[:8] == b"\x89PNG\r\n\x1a\n" and len(body) > 50000
        pdf = self.client.get("/api/visual-quality/vq1/review-pdf/")
        assert pdf.status_code == 200
        assert pdf["Content-Type"] == "application/pdf"
        assert b"".join(pdf.streaming_content)[:5] == b"%PDF-"
        graph = self.client.get("/api/visual-quality/vq1/graph/")
        data = json.loads(b"".join(graph.streaming_content))
        assert data["backbone_hash"].startswith("19f9b98d0bc46a0d")

    def test_anonymous_refused_and_invalid_paths_404(self):
        r = self.client.get("/api/visual-quality/vq1/review-png/")
        assert r.status_code in (302, 403)          # login required
        self.client.force_login(self.user)
        assert self.client.get(
            "/api/visual-quality/vq1/passwd/").status_code == 404
        assert self.client.get(
            "/api/visual-quality/vq1/").status_code == 200

    def test_review_page_opens_without_task_selection(self):
        self.client.force_login(self.user)
        r = self.client.get("/dashboard/visual-quality/vq1/")
        assert r.status_code == 200
        body = r.content.decode()
        assert "VQ-1 — STRUCTURAL FORM REVIEW" in body
        assert "structure only" in body
        assert "ACCEPT VQ-1 STRUCTURAL BACKBONE" in body
        assert "REJECT / REVISION REQUIRED" in body
        assert "NOT_REVIEWED" in body               # nothing preselected

    def test_dashboard_shows_the_program_section(self):
        # §BH55 Phase 3 p3-rulings: the programme moved off the home to the Status page, read from its records — the
        # home's banner was a sentence fixed in the template ("VQ-1 / CORR-2..CORR-5 all REJECTED") they contradict
        self.client.force_login(self.user)
        body = self.client.get("/dashboard/status/").content.decode()
        # [§BH70(1), item 22 of the list the owner was sent: it read "The visual-quality programme", one bottle's
        # programme presented as the whole — it is headed as the bottle's, and says no other form has one yet]
        assert "The bottle's visual-quality programme" in body
        assert "no other form has one yet" in body
        assert "/api/visual-quality/vq1/corr5-p4-png/" in body
        assert "never imply a fix for it" in body
        assert "FINAL VISUAL QUALITY PROGRAM" not in self.client.get("/dashboard/").content.decode()

    def test_decision_records_state_without_touching_tasks(self):
        from apps.pipeline.models import ApiCallRecord, DesignTask
        calls0 = ApiCallRecord.objects.count()
        tasks0 = DesignTask.objects.count()
        self.client.force_login(self.user)
        r = self.client.post("/dashboard/visual-quality/vq1/decision/",
                             {"state": "ACCEPTED"})
        assert r.status_code == 200
        rec = json.loads(r.content)
        assert rec["state"] == "ACCEPTED"
        assert "never task-52 approval" in rec["scope"]
        # acceptance cannot approve task 52 or start VQ-2: nothing changed
        assert ApiCallRecord.objects.count() == calls0
        assert DesignTask.objects.count() == tasks0
        assert self.client.post(
            "/dashboard/visual-quality/vq1/decision/",
            {"state": "MAYBE"}).status_code == 400
