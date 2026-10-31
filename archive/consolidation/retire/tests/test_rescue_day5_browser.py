"""Day5 review, with screenshots only after verified committed startup."""
import json,os,subprocess
from pathlib import Path
from urllib.parse import urlparse
from django.test import override_settings
from apps.pipeline.tests.browser_live_server import DrainedStaticLiveServerTestCase
from apps.pipeline.tests.test_browser_staged_reference_ui import RefUiHarness

@override_settings(HYBRID_BOTTLE_ENABLED=True)
class RescueDay5BrowserTests(RefUiHarness,DrainedStaticLiveServerTestCase):
    def test_review_pages_pins_history_zoom_download_and_no_approval(self):
        from apps.pipeline.models import DesignTask,ApiCallRecord
        ctx=self._context(viewport={'width':1440,'height':1050})
        ctx.route('**/*',lambda r:r.continue_() if urlparse(r.request.url).hostname in ('localhost','127.0.0.1') else r.abort())
        page=ctx.new_page();page.goto(self.live_server_url+'/dashboard/serum-master/')
        page.wait_for_function("document.querySelectorAll('.pair img').length===2 && Array.from(document.querySelectorAll('.pair img')).every(i=>i.naturalWidth===1024)")
        page.evaluate("async () => { await Promise.all(Array.from(document.querySelectorAll('.pair img'), i => i.decode())); }")
        assert page.get_by_text('Designer review needed',exact=True).count()==1
        assert page.get_by_role('button',name='Approve',exact=True).count()==0
        for name in ('Presentation','Artwork','Construction'):assert page.get_by_role('link',name=name,exact=True).count()==1
        with page.expect_download() as download:page.get_by_role('link',name='Download review package').click()
        assert download.value.suggested_filename=='day5-review-package.zip'
        capture=os.environ.get('RESCUE_DAY5_PROOF_DIR')
        if capture:
            root=Path(capture);record=json.loads((root.parent/'rescue_runtime/day5-deployment.json').read_text())
            assert record['commit']==subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip() and record['startup_verified']
            page.screenshot(path=str(root/'serum-master-ui.png'),full_page=True)
        page.goto(self.live_server_url+'/dashboard/stand-master/day5/')   # Day 6 owns stand-master/; Day 5 is history
        page.wait_for_function("document.querySelector('.stand-picture').naturalWidth===2126")
        page.evaluate("async () => { await document.querySelector('.stand-picture').decode(); }")
        assert page.get_by_text('No candidate meets the release bar yet.',exact=False).count()==1
        assert page.locator('section[aria-label="Eligible choices"] img').count()==0
        assert page.locator('main.fidelity details').get_attribute('open') is None
        if capture:page.screenshot(path=str(Path(capture)/'stand-master-ui.png'),full_page=True)
        page.get_by_text('Rejected and pending concepts · review history, not choices',exact=True).click()
        page.wait_for_function("Array.from(document.querySelectorAll('details img')).every(i=>i.naturalWidth===1024)")
        assert page.locator('details img').count()==3
        page.get_by_role('link',name='Construction',exact=True).click()
        assert page.get_by_role('link',name='True 1:1 construction drawings').count()==1
        assert not DesignTask.objects.exists() and not ApiCallRecord.objects.exists()
