"""Day 6 review pages in a real browser, with screenshots only after verified committed startup."""
import json, os, subprocess
from pathlib import Path
from urllib.parse import urlparse
from django.test import override_settings
from apps.pipeline.tests.browser_live_server import DrainedStaticLiveServerTestCase
from apps.pipeline.tests.test_browser_staged_reference_ui import RefUiHarness


@override_settings(HYBRID_BOTTLE_ENABLED=True)
class RescueDay6BrowserTests(RefUiHarness, DrainedStaticLiveServerTestCase):
    def test_stand_and_serum_pages_pins_history_zoom_download_and_no_approval(self):
        from apps.pipeline.models import DesignTask, ApiCallRecord
        ctx = self._context(viewport={'width': 1440, 'height': 1050})
        ctx.route('**/*', lambda r: r.continue_() if urlparse(r.request.url).hostname in ('localhost', '127.0.0.1') else r.abort())
        page = ctx.new_page(); page.goto(self.live_server_url + '/dashboard/serum-master/')
        page.wait_for_function("document.querySelectorAll('.pair img').length===2 && Array.from(document.querySelectorAll('.pair img')).every(i=>i.naturalWidth===1024)")
        page.evaluate("async () => { await Promise.all(Array.from(document.querySelectorAll('.pair img'), i => i.decode())); }")
        assert page.get_by_text('Designer review needed', exact=True).count() == 1
        assert page.get_by_role('button', name='Approve', exact=True).count() == 0
        assert page.get_by_text('Bottle revision 4 sheet', exact=False).count() >= 1
        capture = os.environ.get('RESCUE_DAY6_PROOF_DIR')
        if capture:
            root = Path(capture); record = json.loads((root.parent / 'rescue_runtime/day6-deployment.json').read_text())   # docs/audit/rescue_runtime, as Day 5
            assert record['commit'] == subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() and record['startup_verified']
            page.screenshot(path=str(root / 'serum-master-ui.png'), full_page=True)
        page.goto(self.live_server_url + '/dashboard/stand-master/')
        page.wait_for_function("Array.from(document.querySelectorAll('.pair img')).length===2 && Array.from(document.querySelectorAll('.pair img')).every(i=>i.naturalWidth>0)")
        page.evaluate("async () => { await Promise.all(Array.from(document.querySelectorAll('.pair img'), i => i.decode())); }")
        assert page.get_by_text('Designer review needed', exact=True).count() == 1
        assert page.get_by_role('button', name='Approve', exact=True).count() == 0
        proof = page.locator('nav[aria-label="Proof views"]')      # the site header has its own Library link
        for name in ('Presentation', 'Surfaces', 'Render', 'Cut', 'Device', 'Library', 'History'):
            assert proof.get_by_role('link', name=name, exact=True).count() == 1
        with page.expect_download() as download: page.get_by_role('link', name='Download review package').click()
        assert download.value.suggested_filename == 'day6-review-package.zip'
        if capture: page.screenshot(path=str(Path(capture) / 'stand-master-ui.png'), full_page=True)
        page.get_by_role('link', name='Surfaces', exact=True).click()
        assert page.locator('table tbody tr').count() == 7
        page.goto(self.live_server_url + '/dashboard/stand-master/day5/')
        assert page.get_by_text('No candidate meets the release bar yet.', exact=False).count() == 1
        assert not DesignTask.objects.exists() and not ApiCallRecord.objects.exists()
