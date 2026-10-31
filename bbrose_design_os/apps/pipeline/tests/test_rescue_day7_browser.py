"""Day 7 §5: the Library page in a real browser — kinds with counts, previews that load, the excluded fonts heading, a detail
view with rights and "used in" — with screenshots only after verified committed startup (RESCUE_DAY7_PROOF_DIR)."""
import json, os, subprocess
from pathlib import Path
from urllib.parse import urlparse
from apps.pipeline.tests.browser_live_server import DrainedStaticLiveServerTestCase
from apps.pipeline.tests.test_browser_staged_reference_ui import RefUiHarness


class RescueDay7BrowserTests(RefUiHarness, DrainedStaticLiveServerTestCase):
    def test_library_page_kinds_previews_filters_excluded_fonts_and_detail(self):
        from apps.dashboard import materials_library as ml
        ctx = self._context(viewport={'width': 1440, 'height': 1050})
        ctx.route('**/*', lambda r: r.continue_() if urlparse(r.request.url).hostname in ('localhost', '127.0.0.1') else r.abort())
        page = ctx.new_page(); page.goto(self.live_server_url + '/dashboard/materials/?kind=pattern&q=gold')
        page.wait_for_function("document.querySelectorAll('img.material-picture').length>0 && Array.from(document.querySelectorAll('img.material-picture')).slice(0,8).every(i=>i.complete)")
        loaded = page.evaluate("Array.from(document.querySelectorAll('img.material-picture')).slice(0,8).filter(i=>i.naturalWidth>0).length")
        assert loaded >= 1, loaded
        counts = ml.index_counts()
        kinds = page.locator('nav[aria-label="Kinds"]')
        assert kinds.get_by_role('link', name='pattern (%d)' % dict(counts['kinds'])['pattern'], exact=True).count() == 1
        assert page.get_by_role('heading', name=ml.EXCLUDED_HEADING, exact=True).count() == 1
        assert page.get_by_role('button', name='Approve', exact=True).count() == 0
        capture = os.environ.get('RESCUE_DAY7_PROOF_DIR')
        if capture:
            root = Path(capture); record = json.loads((root.parent / 'rescue_runtime/day7-deployment.json').read_text())
            assert record['commit'] == subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() and record['startup_verified']
            page.screenshot(path=str(root / 'library-ui.png'), full_page=False)
        page.locator('article.material strong a').first.click()
        page.wait_for_selector('h2:has-text("Used in")')
        assert page.get_by_role('heading', name='Rights', exact=True).count() == 1
        assert page.get_by_text('D-D7-1', exact=False).count() >= 1
        if capture:
            page.screenshot(path=str(Path(capture) / 'library-detail-ui.png'), full_page=False)
        page.goto(self.live_server_url + '/dashboard/materials/?tier=excluded')
        assert page.get_by_role('heading', name=ml.EXCLUDED_HEADING, exact=True).count() == 1
        assert page.locator('article.material.excluded').count() >= 1
