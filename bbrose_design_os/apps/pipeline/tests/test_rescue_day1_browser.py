"""Actual local UI checks; screenshot output is opt-in and contains test fixtures only."""
import os
from pathlib import Path
from urllib.parse import urlparse
from apps.pipeline.tests.browser_live_server import DrainedStaticLiveServerTestCase
from apps.pipeline.tests.test_browser_staged_reference_ui import RefUiHarness
from apps.pipeline.tests.quality_fixtures import reviewed
from apps.core.models import Brand
from apps.pipeline.models import DesignTask, GeneratedImage
from apps.pipeline.services.concept_quality import summary

class RescueDay1BrowserTests(RefUiHarness, DrainedStaticLiveServerTestCase):
    def _save(self, page, name):
        if os.environ.get('RESCUE_PROOF_DIR'):
            dest = Path(os.environ['RESCUE_PROOF_DIR']); dest.mkdir(parents=True, exist_ok=True)
            page.evaluate('window.scrollTo(0,0)')
            page.screenshot(path=str(dest/name), full_page=True)

    def test_product_first_intake_and_free_staging(self):
        ctx = self._context(viewport={'width':1440,'height':1100})
        ctx.route('**/*', lambda r: r.continue_() if urlparse(r.request.url).hostname in ('localhost','127.0.0.1') else r.abort())
        page = ctx.new_page(); calls=[]
        page.on('request',lambda req: calls.append(req.url) if '/api/inspiration/read/' in req.url else None)
        page.goto(self.live_server_url+'/dashboard/new/classic/')
        page.wait_for_selector('.target-chip')
        assert page.locator('.target-chip').evaluate_all('els=>els.slice(0,3).map(e=>e.dataset.target)') == ['product_container','display_stand','packaging']
        assert page.locator('.target-chip[aria-checked="true"]').count() == 0
        page.locator('#inspiration-box .ref-input').set_input_files({'name':'reference.png','mimeType':'image/png','buffer':b'test fixture'})
        page.wait_for_selector('#inspiration-box .inspire-item')
        assert 'read after Start' in page.locator('#inspiration-box').inner_text()
        assert not calls
        self._save(page,'intake-ui.png')

    def test_only_accepted_concept_has_approval_button(self):
        task=DesignTask.objects.create(brand=Brand.objects.first(),created_by=self.user,task_text='Test serum',status='awaiting_gate_1')
        for name,score in [('Accepted fixture',9),('Rejected fixture',4)]:
            reviewed(GeneratedImage.objects.create(task=task,direction_name=name,prompt_used='test'),score)
        GeneratedImage.objects.create(task=task,direction_name='Pending fixture',prompt_used='test')
        task.options={'concept_quality':summary(task.images.all())};task.save()
        page=self._design_page(task,viewport={'width':1440,'height':1000})
        page.wait_for_selector('#image-gallery .btn-approve')
        assert page.locator('#image-gallery .btn-approve').count()==1
        assert page.locator('#image-gallery .concept-diagnostics').count()==1
        assert not page.locator('#image-gallery .concept-diagnostics').evaluate('el=>el.open')
        self._save(page,'quality-gate-ui.png')
