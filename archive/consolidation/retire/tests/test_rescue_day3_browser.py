"""Actual browser authoring and download; captures require verified startup."""
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import urlparse
from django.test import override_settings
from apps.pipeline.tests.browser_live_server import DrainedStaticLiveServerTestCase
from apps.pipeline.tests.test_browser_staged_reference_ui import RefUiHarness

@override_settings(BRAND_MARK_APPROVAL_LOOKUP=True)
class RescueDay3BrowserTests(RefUiHarness,DrainedStaticLiveServerTestCase):
    def test_twelve_bottle_page_and_checked_download(self):
        from apps.pipeline.models import DesignTask,ApiCallRecord
        ctx=self._context(viewport={'width':1440,'height':1050})
        ctx.route('**/*',lambda r:r.continue_() if urlparse(r.request.url).hostname in ('localhost','127.0.0.1') else r.abort())
        page=ctx.new_page();page.goto(self.live_server_url+'/dashboard/stand-master/legacy/')
        page.wait_for_function("document.querySelector('.hybrid-picture img').naturalWidth > 0")
        assert page.get_by_role('link',name='Download',exact=True).count()==1
        assert page.get_by_role('button',name='Approve',exact=True).count()==0
        page.get_by_role('button',name='Save a new geometry revision').click()
        page.wait_for_url('**/dashboard/stand-master/*/',timeout=30000)
        page.wait_for_function("document.querySelector('.hybrid-picture img').naturalWidth > 0")
        assert page.locator('.hybrid-picture img').evaluate('img=>img.naturalWidth')>2000
        assert page.locator('#id_height').input_value()=='420.0'
        with page.expect_download() as got:page.get_by_role('link',name='Download',exact=True).click()
        assert got.value.suggested_filename=='assembly-package.zip'
        assert page.get_by_text('Original briefs, retained unchanged',exact=True).count()==1
        assert page.get_by_role('link',name='Pinned serum proof').count()==1
        if os.environ.get('RESCUE_DAY3_PROOF_DIR'):
            root=Path(os.environ['RESCUE_DAY3_PROOF_DIR'])
            deployment=json.loads((root.parent/'rescue_runtime/day3-deployment.json').read_text())
            head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
            assert deployment['commit']==head and deployment['startup_verified'] is True
            page.screenshot(path=str(root/'stand-master-ui.png'),full_page=True)
        task=DesignTask.objects.get(options__authoring_backend='hybrid_assembly')
        assert task.options['current_revision']==1 and not ApiCallRecord.objects.exists()
        page.get_by_role('link',name='Serum master and fidelity correction').click()
        assert page.get_by_text('Designer review needed',exact=True).count()==1
        assert page.get_by_role('link',name='Display',exact=True).count()==1
