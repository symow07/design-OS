"""Phase 13 tests — frontend split (Milestone 13.1).

These are STRUCTURAL checks: the dashboard renders, the externalised static
assets are served, and each task-status partial's anchor element is present.
They do NOT execute the JS or run the pipeline (no API keys here) — the full
demo walkthrough must be verified manually in a browser.
"""
from django.contrib.auth.models import User
from django.test import TestCase

from apps.core.models import Brand


class DashboardRenderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("u", "u@t.com", "pw")
        Brand.objects.create(name="B", master_brief="x")
        self.client.force_login(self.user)

    JS_MODULES = ("api", "render", "gates", "poll")

    def _design(self):
        # [the owner's answer to the UI directions of 2026-09-25: the steps' scripts load on the design's own page]
        from apps.pipeline.models import DesignTask
        return DesignTask.objects.create(brand=Brand.objects.first(), task_text="a carton", status="awaiting_gate_1")

    def test_dashboard_renders_and_references_external_assets(self):
        resp = self.client.get(f"/dashboard/designs/{self._design().pk}/")
        assert resp.status_code == 200
        html = resp.content.decode()
        # CSS + JS are external, not inline.
        assert "css/bbrose.css" in html
        assert "<style>" not in html
        for mod in self.JS_MODULES:
            assert f"js/{mod}.js" in html
        # the values the modules read are handed over as data — the page carries no inline script
        assert 'id="design-page"' in html and '"current_user"' in html and '"brand_id"' in html
        assert "var CURRENT_USER" not in html

    def test_static_assets_are_discoverable(self):
        # What matters for serving is that the staticfiles finders locate the
        # files under STATICFILES_DIRS (whitenoise/runserver serve what finders
        # find). A live-server curl is done separately in the 13.1 verify step.
        from django.contrib.staticfiles import finders
        assert finders.find("css/bbrose.css") is not None  # [the owner's answer to the UI directions of 2026-09-25: C's start page replaced the old single page]
        for mod in self.JS_MODULES:
            assert finders.find(f"js/{mod}.js") is not None

    def test_status_anchor_elements_present(self):
        html = self.client.get(f"/dashboard/designs/{self._design().pk}/").content.decode()  # [the owner's answer to the UI directions of 2026-09-25: C's start page replaced the old single page]
        for anchor in ("empty-state", "feed-state", "gallery-state",
                       "dimensions-state", "gate2-state", "complete-state"):
            assert f'id="{anchor}"' in html


class LiveUpdatesTests(TestCase):
    """Milestone 13.2 — SSE stream and the paginated/filtered list (the cached stats left with the old dashboard's
    brain panel in the clean-up of 2026-10-04)."""

    def setUp(self):
        from django.contrib.auth.models import Group
        from apps.pipeline.models import DesignTask
        from apps.pipeline.permissions import ROLE_DESIGNER
        self.user = User.objects.create_user("u", "u@t.com", "pw")
        # Read endpoints require a team role (hardening 2026-07-04).
        group, _ = Group.objects.get_or_create(name=ROLE_DESIGNER)
        self.user.groups.add(group)
        self.brand = Brand.objects.create(name="B", master_brief="x")
        self.other = Brand.objects.create(name="B2", master_brief="y")
        self.client.force_login(self.user)
        self.DesignTask = DesignTask

    def test_sse_stream_settles_on_gate_status(self):
        from apps.pipeline.live_views import _event_stream
        from apps.pipeline.models import AgentLog
        task = self.DesignTask.objects.create(
            task_text="t", status="awaiting_gate_1", brand=self.brand)
        AgentLog.objects.create(task=task, agent_name="ARIA", action="started")
        # awaiting_gate_1 is not a working status → stream yields status + the
        # new log + settled, then returns (no blocking sleep).
        frames = list(_event_stream(task.id, last_log_id=0, max_seconds=5))
        joined = "".join(frames)
        assert "event: status" in joined
        assert "event: log" in joined
        assert "event: settled" in joined

    def test_sse_stream_missing_task(self):
        from apps.pipeline.live_views import _event_stream
        frames = list(_event_stream(999999, last_log_id=0, max_seconds=5))
        assert any("event: error" in f for f in frames)

    def test_sse_endpoint_content_type(self):
        task = self.DesignTask.objects.create(
            task_text="t", status="completed", brand=self.brand)
        resp = self.client.get(f"/api/tasks/{task.id}/events/")
        assert resp.status_code == 200
        assert resp["Content-Type"].startswith("text/event-stream")
        # Consume the streaming content so the generator closes cleanly.
        b"".join(resp.streaming_content)

    def test_task_list_paginated_and_filtered(self):
        for i in range(30):
            self.DesignTask.objects.create(
                task_text=f"t{i}", status="queued", brand=self.brand,
                created_by=self.user)
        self.DesignTask.objects.create(
            task_text="other", status="completed", brand=self.other,
            created_by=self.user)

        body = self.client.get("/api/tasks/").json()
        assert body["count"] == 31          # DRF pagination envelope
        assert len(body["results"]) == 25   # page size
        assert body["next"] is not None

        # Filters
        assert self.client.get("/api/tasks/?status=completed").json()["count"] == 1
        assert self.client.get(f"/api/tasks/?brand={self.other.id}").json()["count"] == 1
        assert self.client.get("/api/tasks/?owner=u").json()["count"] == 31
