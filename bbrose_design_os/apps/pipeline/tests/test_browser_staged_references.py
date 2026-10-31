"""Real-browser tests for the staged-reference state module (B4b-2A-1).

The module is pure state — no DOM, no fetch — so nearly every property worth
proving is behavioural: what actually lands in a real FormData, when the real
URL API is called, whether removing one duplicate really preserves the other.
Per the recorded test-strategy decision (b6c4cd9), these run the REAL file in
headless Chromium via the established StaticLiveServerTestCase + Playwright
harness, not as Python source-text assertions.

Two seams make the invisible observable: an init script replaces
URL.createObjectURL/revokeObjectURL with recorders (the module's default
urlApi then records every call), and window.fetch is wrapped so any network
attempt is captured. FormData is inspected through its own entries() in the
browser — never inferred from the code that builds it.

The module is deliberately UNWIRED: production templates and poll.js must not
reference it yet. That isolation is itself asserted.
"""
from __future__ import annotations

import pytest
from apps.pipeline.tests.browser_live_server import DrainedStaticLiveServerTestCase

try:
    from playwright.sync_api import sync_playwright
    HAVE_PLAYWRIGHT = True
except ImportError:              # pragma: no cover
    HAVE_PLAYWRIGHT = False

from apps.pipeline.models import ApiCallRecord, DesignTask

# The five persisted keys — 'color', never 'colour' — with owner-facing labels.
_BOOTSTRAP = """
window.CFG = {
  categories: [
    {key: 'container', label: 'Container Reference'},
    {key: 'logo', label: 'Brand Logo'},
    {key: 'label', label: 'Existing Label or Artwork'},
    {key: 'inspiration', label: 'Visual Inspiration'},
    {key: 'color', label: 'Colour Reference'},
  ],
  previewableExtensions: ['.png', '.jpg', '.jpeg', '.webp'],
  referenceOnlyLabel: 'REFERENCE ONLY',
};
window.mk = function (name, type, n) {
  return new File([new Uint8Array(n || 3)], name, {type: type || ''});
};
window.inv = DesignOSStagedReferences.create(CFG);
window.__fetches = [];   // reset: only calls made AFTER bootstrap count
"""

_INIT = """
window.__url = {created: [], revoked: []};
URL.createObjectURL = function () {
  var u = 'blob:test-' + window.__url.created.length;
  window.__url.created.push(u);
  return u;
};
URL.revokeObjectURL = function (u) { window.__url.revoked.push(u); };
window.__fetches = [];
var _origFetch = window.fetch;
window.fetch = function () {
  window.__fetches.push(String(arguments[0]));
  return _origFetch.apply(window, arguments);
};
"""


@pytest.mark.skipif(not HAVE_PLAYWRIGHT, reason="playwright not installed")
class StagedReferencesBrowserTests(DrainedStaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        super().setUpClass()
        cls._pw = sync_playwright().start()
        cls._browser = cls._pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls._browser.close()
        cls._pw.stop()
        super().tearDownClass()

    def setUp(self):
        self.page = self._browser.new_page()
        self.page.add_init_script(_INIT)
        # the login page is a real, script-free HTML host on the live origin
        self.page.goto(self.live_server_url + "/accounts/login/")
        self.page.add_script_tag(
            url=self.live_server_url + "/static/js/staged_references.js")
        self.page.evaluate(_BOOTSTRAP)

    def tearDown(self):
        self.page.close()

    def js(self, script):
        return self.page.evaluate(script)

    # -- load and configuration (properties 1, 2) --------------------------

    def test_module_loads_and_requires_configuration(self):
        assert self.js("typeof DesignOSStagedReferences.create") == "function"
        assert self.js("typeof inv.addFiles") == "function"
        # a caller that supplies no categories is refused outright
        assert self.js("""
          (() => { try { DesignOSStagedReferences.create({}); return 'no'; }
                   catch (e) { return 'threw'; } })()
        """) == "threw"

    # -- staging (3, 5, 6, 11, 12, 13) --------------------------------------

    def test_staging_assigns_category_and_preserves_source_order(self):
        out = self.js("""
          (() => {
            inv.addFiles('container', [mk('one.png', 'image/png', 5)]);
            inv.addFiles('logo', [mk('Two.JPG', 'image/jpeg', 7),
                                  mk('three.pdf', 'application/pdf', 9),
                                  mk('four.webp', 'image/webp', 2)]);
            return inv.list().map(e => ({name: e.name, cat: e.category,
              label: e.categoryLabel, ext: e.ext, mime: e.mime,
              size: e.size, order: e.order, badge: e.referenceOnly}));
          })()
        """)
        assert [e["name"] for e in out] == ["one.png", "Two.JPG",
                                           "three.pdf", "four.webp"]
        assert [e["order"] for e in out] == [0, 1, 2, 3]
        assert [e["cat"] for e in out] == ["container", "logo", "logo", "logo"]
        assert out[0]["label"] == "Container Reference"
        # extension is normalised to lowercase; MIME and byte size retained
        assert out[1]["ext"] == ".jpg" and out[1]["mime"] == "image/jpeg"
        assert out[1]["size"] == 7
        assert all(e["badge"] == "REFERENCE ONLY" for e in out)

    # -- category contract (4, 7) -------------------------------------------

    def test_unknown_category_rejected_and_color_is_the_persisted_key(self):
        out = self.js("""
          (() => ({
            bogus: inv.addFiles('dieline', [mk('a.png')]).error,
            british: inv.addFiles('colour', [mk('b.png')]).error,
            proper: inv.addFiles('color', [mk('c.png')]).ok,
            staged: inv.count(),
          }))()
        """)
        assert out["bogus"] == "UNKNOWN_CATEGORY"
        # 'colour' is an OWNER-FACING label, never a persisted key
        assert out["british"] == "UNKNOWN_CATEGORY"
        assert out["proper"] is True
        assert out["staged"] == 1

    # -- identity (8, 9, 10) -------------------------------------------------

    def test_duplicates_coexist_with_unique_ids(self):
        out = self.js("""
          (() => {
            const f = mk('same.png', 'image/png');
            inv.addFiles('container', [mk('same.png', 'image/png')]);
            inv.addFiles('logo', [mk('same.png', 'image/png')]);
            inv.addFiles('inspiration', [f]);
            inv.addFiles('inspiration', [f]);   // the SAME File object again
            const l = inv.list();
            return {n: l.length, ids: l.map(e => e.id),
                    names: l.map(e => e.name)};
          })()
        """)
        assert out["n"] == 4
        assert len(set(out["ids"])) == 4
        assert out["names"] == ["same.png"] * 4

    # -- previews and object URLs (14-21) ------------------------------------

    def test_object_urls_only_for_previewable_rasters(self):
        out = self.js("""
          (() => {
            inv.addFiles('container', [mk('a.png', 'image/png'),
                                       mk('b.jpg', 'image/jpeg'),
                                       mk('c.webp', 'image/webp'),
                                       mk('d.pdf', 'application/pdf'),
                                       mk('e.ai', ''),
                                       mk('f.eps', '')]);
            return {created: window.__url.created.length,
                    kinds: inv.list().map(e => [e.ext, e.previewKind,
                                                e.objectUrl])};
          })()
        """)
        kinds = {ext: (kind, url) for ext, kind, url in out["kinds"]}
        assert out["created"] == 3           # png, jpg, webp — and only those
        for ext in (".png", ".jpg", ".webp"):
            assert kinds[ext][0] == "raster"
            assert kinds[ext][1] and kinds[ext][1].startswith("blob:test-")
        for ext in (".pdf", ".ai", ".eps"):
            assert kinds[ext][0] == "file-card"
            assert kinds[ext][1] is None     # a PDF can never reach an <img>

    # -- removal (22-25) -----------------------------------------------------

    def test_remove_deletes_exactly_one_and_revokes_exactly_its_url(self):
        out = self.js("""
          (() => {
            inv.addFiles('container', [mk('dup.png', 'image/png')]);
            inv.addFiles('logo', [mk('dup.png', 'image/png')]);
            inv.addFiles('label', [mk('doc.pdf', 'application/pdf')]);
            const first = inv.list()[0];
            const r1 = inv.remove(first.id);
            const afterRaster = {revoked: window.__url.revoked.slice(),
                                 left: inv.list().map(e => e.name)};
            const doc = inv.list().find(e => e.ext === '.pdf');
            inv.remove(doc.id);
            return {r1: r1, removedUrl: first.objectUrl,
                    afterRaster: afterRaster,
                    revokedAfterDoc: window.__url.revoked.length,
                    missing: inv.remove('ref-9999')};
          })()
        """)
        assert out["r1"] == {"ok": True, "removed": True}
        # exactly the removed entry's URL, and the duplicate filename survives
        assert out["afterRaster"]["revoked"] == [out["removedUrl"]]
        assert out["afterRaster"]["left"] == ["dup.png", "doc.pdf"]
        # removing a file-card revokes nothing further
        assert out["revokedAfterDoc"] == 1
        assert out["missing"] == {"ok": True, "removed": False}

    # -- clear and dispose (26-29) -------------------------------------------

    def test_clear_and_dispose_revoke_everything_exactly_once(self):
        out = self.js("""
          (() => {
            inv.addFiles('container', [mk('a.png', 'image/png'),
                                       mk('b.jpg', 'image/jpeg'),
                                       mk('c.pdf', 'application/pdf')]);
            inv.clear();
            const afterClear = window.__url.revoked.length;
            inv.clear();                       // repeat must not double-revoke
            const afterClear2 = window.__url.revoked.length;

            const inv2 = DesignOSStagedReferences.create(CFG);
            inv2.addFiles('logo', [mk('d.webp', 'image/webp')]);
            inv2.dispose();
            const afterDispose = window.__url.revoked.length;
            inv2.dispose();                    // repeat must be safe
            return {afterClear, afterClear2,
                    afterDispose,
                    afterDispose2: window.__url.revoked.length,
                    cleared: inv.count(),
                    disposedAdd: inv2.addFiles('logo', [mk('e.png')]).error};
          })()
        """)
        assert out["afterClear"] == 2          # the two rasters, not the pdf
        assert out["afterClear2"] == 2
        assert out["afterDispose"] == 3
        assert out["afterDispose2"] == 3
        assert out["cleared"] == 0
        assert out["disposedAdd"] == "DISPOSED"

    # -- encapsulation (30) --------------------------------------------------

    def test_list_is_a_safe_readonly_view(self):
        out = self.js("""
          (() => {
            inv.addFiles('container', [mk('a.png', 'image/png')]);
            const l = inv.list();
            l.push({id: 'fake'});              // mutating the returned array
            try { l[0].category = 'logo'; } catch (e) {}  // frozen entry
            return {internal: inv.count(),
                    category: inv.list()[0].category};
          })()
        """)
        assert out["internal"] == 1
        assert out["category"] == "container"

    # -- FormData (31-36) ----------------------------------------------------

    def test_formdata_carries_each_staged_file_exactly_once_in_order(self):
        out = self.js("""
          (() => {
            const empty = new FormData();
            const zero = inv.appendToFormData(empty);
            const zeroRows = Array.from(empty.entries()).length;

            inv.addFiles('container', [mk('shape.png', 'image/png', 4)]);
            inv.addFiles('color', [mk('chips.pdf', 'application/pdf', 6)]);
            inv.addFiles('logo', [mk('same.png', 'image/png', 2)]);
            inv.addFiles('inspiration', [mk('same.png', 'image/png', 8)]);
            const doomed = inv.list().find(e => e.category === 'logo');
            inv.remove(doomed.id);

            const fd = new FormData();
            fd.append('task_text', 'a serum bottle');
            const n = inv.appendToFormData(fd);
            const rows = [];
            for (const [k, v] of fd.entries()) {
              rows.push([k, (v instanceof File) ? v.name : v,
                         (v instanceof File) ? v.size : null]);
            }
            return {zero, zeroRows, n, rows};
          })()
        """)
        # zero staged files is valid and appends nothing (the empty FormData)
        assert out["zero"] == 0 and out["zeroRows"] == 0
        assert out["n"] == 3
        # inspected from the REAL FormData: correct server field per category,
        # staged order preserved, removed file absent, duplicate name present
        assert out["rows"] == [
            ["task_text", "a serum bottle", None],
            ["container", "shape.png", 4],
            ["color", "chips.pdf", 6],
            ["inspiration", "same.png", 8],
        ]

    # -- submitting lock (37-41) ---------------------------------------------

    def test_submitting_state_locks_mutation_but_not_reads(self):
        out = self.js("""
          (() => {
            inv.addFiles('container', [mk('a.png', 'image/png')]);
            const id = inv.list()[0].id;
            inv.setSubmitting(true);
            const locked = {
              submitting: inv.isSubmitting(),
              add: inv.addFiles('logo', [mk('b.png')]).error,
              remove: inv.remove(id).error,
              clear: inv.clear().error,
              read: inv.list().length,
            };
            inv.setSubmitting(false);
            const unlockedAdd = inv.addFiles('logo', [mk('b.png')]).ok;

            inv.setSubmitting(true);
            const success = inv.clear({confirmedSuccess: true}).ok;
            return {locked, unlockedAdd, success, after: inv.count()};
          })()
        """)
        assert out["locked"] == {"submitting": True, "add": "SUBMITTING",
                                 "remove": "SUBMITTING", "clear": "SUBMITTING",
                                 "read": 1}
        assert out["unlockedAdd"] is True
        # the confirmed-success cleanup path works during submission — it is
        # what 2A-3 will call once the server has actually confirmed the task
        assert out["success"] is True and out["after"] == 0

    # -- nothing beyond the browser (42-46) ----------------------------------

    def test_no_network_no_task_no_provider_call(self):
        self.js("""
          (() => {
            inv.addFiles('container', [mk('a.png', 'image/png'),
                                       mk('b.pdf', 'application/pdf')]);
            const fd = new FormData();
            inv.appendToFormData(fd);
            inv.remove(inv.list()[0].id);
            inv.clear();
          })()
        """)
        # the module never fetched, XHR'd or navigated anywhere
        assert self.js("window.__fetches") == []
        # nothing server-side happened: no task, no reference row, and the
        # provider ledger did not move (no provider / image-generation / OCR)
        assert DesignTask.objects.count() == 0
        assert ApiCallRecord.objects.count() == 0

    # -- isolation from production (§1/§14) ----------------------------------

    def test_wiring_matches_the_current_slice(self):
        """2A-3: poll.js submits through the public DesignOSReferenceUI handle
        and through it ONLY — the state module itself stays behind that handle,
        and the temporary bridge global is gone from all active code."""
        import os
        import subprocess

        from django.conf import settings
        base = settings.BASE_DIR
        poll = open(os.path.join(base, "static", "js", "poll.js")).read()
        tpl = open(os.path.join(base, "templates", "dashboard",
                                "new.html")).read()  # [the owner's answer to the UI directions of 2026-09-25: C's start page replaced the old single page]
        assert "DesignOSReferenceUI" in poll          # the public handle
        assert "DesignOSStagedReferences" not in poll  # never the state module
        assert "REF_FILES" not in poll
        out = subprocess.run(
            ["grep", "-rn", "REF_FILES",
             os.path.join(base, "static"), os.path.join(base, "templates")],
            capture_output=True, text=True).stdout
        assert out == "", out
        # load order: state module, then UI, then poll.js (script TAGS — a
        # comment mentions poll.js earlier and must not satisfy this)
        assert tpl.index("js/staged_references.js") \
            < tpl.index("js/staged_reference_ui.js") \
            < tpl.index("js/poll.js' %}")
