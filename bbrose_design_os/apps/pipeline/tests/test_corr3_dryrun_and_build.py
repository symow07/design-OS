"""Frontend build markers (2A-6E-CORR-3 §2).

The regeneration-click incident chain ended at a browser running a stale
asset with no way to see it. These pin the backend half: the dashboard
carries the served revision and cache-busted asset URLs.

[§7's dry-run tests pinned the old POST /api/tasks/<id>/regenerate_with_references/
door, which the clean-up of 2026-10-04 (E7) removed with the old Gate-1
regeneration API; the regeneration page that replaced it keeps its dry-run and
live modes, held by test_corr4_html_regeneration.py.]
"""
from __future__ import annotations

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from apps.core.models import Brand


class BuildMarkerTests(TestCase):
    def test_dashboard_carries_build_and_cache_busted_assets(self):
        from apps.pipeline.services.revision import current_revision
        import json
        import re

        from apps.pipeline.models import DesignTask
        user = User.objects.create_superuser("b", "b@b.com", "pw")
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        task = DesignTask.objects.create(brand=brand, task_text="a carton", status="awaiting_gate_1")
        self.client.force_login(user)
        response = self.client.get(f"/dashboard/designs/{task.pk}/")  # [the owner's answer to the UI directions of 2026-09-25: C's start page replaced the old single page]
        html = response.content.decode()
        revision = current_revision()
        data = json.loads(re.search(r'<script id="design-page" type="application/json">(.*?)</script>', html, re.S).group(1))
        assert data["build"] == revision                       # handed to the scripts as data, never an inline script
        assert f"js/gates.js?v={revision}" in html
        assert f"js/api.js?v={revision}" in html

    def test_a_new_build_changes_the_asset_url(self):
        """The cache-buster is the served revision: a different revision is
        a different URL, so a stale asset cannot survive a new build."""
        from apps.pipeline.services.revision import current_revision
        from apps.pipeline.models import DesignTask
        user = User.objects.create_superuser("b2", "b2@b.com", "pw")
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        task = DesignTask.objects.create(brand=brand, task_text="a carton", status="awaiting_gate_1")
        self.client.force_login(user)
        current_revision.cache_clear()
        with override_settings(CODE_REVISION="build-one"):
            first = self.client.get(f"/dashboard/designs/{task.pk}/").content.decode()  # [the owner's answer to the UI directions of 2026-09-25: C's start page replaced the old single page]
        current_revision.cache_clear()
        with override_settings(CODE_REVISION="build-two"):
            second = self.client.get(f"/dashboard/designs/{task.pk}/").content.decode()
        current_revision.cache_clear()
        assert "js/gates.js?v=build-one" in first
        assert "js/gates.js?v=build-two" in second
