"""Real local browser: author, view, revise and download the serum master."""
import os
from pathlib import Path
from urllib.parse import urlparse

from django.test import override_settings
from apps.pipeline.tests.browser_live_server import DrainedStaticLiveServerTestCase
from apps.pipeline.tests.test_browser_staged_reference_ui import RefUiHarness


@override_settings(BRAND_MARK_APPROVAL_LOOKUP=True, HYBRID_BOTTLE_ENABLED=True)
class RescueDay2BrowserTests(RefUiHarness, DrainedStaticLiveServerTestCase):
    def test_authoring_page_preserves_copy_and_exposes_real_proof(self):
        from apps.pipeline.models import ApiCallRecord, DesignTask
        ctx = self._context(viewport={"width": 1440, "height": 1050})
        ctx.route("**/*", lambda r: r.continue_() if urlparse(r.request.url).hostname in ("localhost", "127.0.0.1") else r.abort())
        page = ctx.new_page()
        page.goto(self.live_server_url + "/dashboard/serum-master/legacy/")
        page.get_by_role("button", name="Create my editable master").click()
        page.wait_for_url("**/dashboard/serum-master/*/", timeout=30000)
        picture = page.locator(".hybrid-picture img")
        page.wait_for_function("document.querySelector('.hybrid-picture img').naturalWidth > 0")
        assert picture.evaluate("img=>img.naturalWidth") > 2000
        assert page.locator("#id_arabic").input_value() == "سيروم صن ريبير"
        assert page.get_by_role("button", name="Approve", exact=True).count() == 0
        with page.expect_download() as download:
            page.get_by_role("link", name="1:1 comparison PDF").click()
        assert download.value.suggested_filename == "comparison-at-100-percent.pdf"
        if os.environ.get("RESCUE_PROOF_DIR"):
            root = Path(os.environ["RESCUE_PROOF_DIR"]); root.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(root / "serum-master-ui.png"), full_page=True)
        task = DesignTask.objects.get(options__authoring_backend="hybrid_bottle")
        assert task.options["current_revision"] == 1
        assert ApiCallRecord.objects.count() == 0
