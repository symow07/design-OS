"""Committed startup is verified before optional proof capture; browser DB isolated."""
import json,os,subprocess
from pathlib import Path
from urllib.parse import urlparse
from django.test import override_settings
from apps.pipeline.tests.browser_live_server import DrainedStaticLiveServerTestCase
from apps.pipeline.tests.test_browser_staged_reference_ui import RefUiHarness

@override_settings(HYBRID_BOTTLE_ENABLED=True)
class RescueDay4BrowserTests(RefUiHarness,DrainedStaticLiveServerTestCase):
    def test_review_pages_exact_pins_zoom_download_and_no_approve(self):
        from apps.pipeline.models import DesignTask,ApiCallRecord
        ctx=self._context(viewport={'width':1440,'height':1050})
        ctx.route('**/*',lambda r:r.continue_() if urlparse(r.request.url).hostname in ('localhost','127.0.0.1') else r.abort())
        page=ctx.new_page();page.goto(self.live_server_url+'/dashboard/serum-master/day4/')
        page.wait_for_function("document.querySelectorAll('.pair img').length===2 && Array.from(document.querySelectorAll('.pair img')).every(i=>i.naturalWidth===1024)")
        assert page.get_by_role('button',name='Approve',exact=True).count()==0
        assert page.get_by_text('Designer review needed',exact=True).count()==1
        for name in ('Presentation','Artwork','Construction'):assert page.get_by_role('link',name=name,exact=True).count()==1
        with page.expect_download() as download:page.get_by_role('link',name='Download review package').click()
        assert download.value.suggested_filename=='day4-review-package.zip'
        capture=os.environ.get('RESCUE_DAY4_PROOF_DIR')
        if capture:
            root=Path(capture);record=json.loads((root.parent/'rescue_runtime/day4-deployment.json').read_text());head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
            assert record['commit']==head and record['startup_verified'] is True
            page.screenshot(path=str(root/'serum-master-ui.png'),full_page=True)
        page.goto(self.live_server_url+'/dashboard/stand-master/day4/')
        page.wait_for_function("document.querySelector('.stand-picture').naturalWidth>2000")
        assert page.get_by_text('322 mm',exact=False).count()>=1
        if capture:page.screenshot(path=str(Path(capture)/'stand-master-ui.png'),full_page=True)
        page.get_by_role('link',name='Construction',exact=True).click()
        assert page.get_by_role('link',name='Half-pitch stagger: width refusal, no silent repitch').count()==1
        assert not DesignTask.objects.exists() and not ApiCallRecord.objects.exists()
