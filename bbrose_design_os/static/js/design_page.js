/* A DESIGN's page (templates/dashboard/design.html): the values the design's scripts read — which design, whose account,
   which brand, which build — handed over as data (the page carries no inline script), and the library panel: its tabs,
   and whether it stays open, remembered in this browser only. Loaded before every other script of the page. */
(function () {
  'use strict';
  var data = {};
  try { data = JSON.parse(document.getElementById('design-page').textContent); } catch (e) { data = {}; }
  window.CURRENT_USER = data.current_user || '';
  window.ACTIVE_BRAND_ID = (data.brand_id === undefined) ? null : data.brand_id;
  window.OPEN_TASK_ID = data.task_id || null;
  window.__BBROSE_FRONTEND_BUILD__ = data.build || '';
  window.DESIGN_REASON = data.reason || '';              // why it stopped, in words (apps/dashboard/words.py)
  window.DESIGN_LOOK_AGAIN = !!data.look_again;          // drawn again since it was turned down at review
  window.DESIGN_LOOK_AGAIN_PICTURE = data.look_again_picture || '';

  document.addEventListener('DOMContentLoaded', function () {
    var panel = document.getElementById('library-panel');
    var main = document.getElementById('design-main');
    if (!panel || !main) { return; }
    var KEY = 'bbrose.library.open';
    function setOpen(open) {
      main.classList.toggle('lib-closed', !open);
      document.querySelectorAll('.lib-toggle').forEach(function (b) { b.setAttribute('aria-expanded', open ? 'true' : 'false'); });
      try { localStorage.setItem(KEY, open ? '1' : '0'); } catch (e) { /* a private window keeps it for this page */ }
    }
    var stored = null;
    try { stored = localStorage.getItem(KEY); } catch (e) { stored = null; }
    setOpen(stored !== '0');
    document.querySelectorAll('.lib-toggle').forEach(function (b) {
      b.addEventListener('click', function () { setOpen(main.classList.contains('lib-closed')); });
    });
    var tabs = panel.querySelectorAll('[role="tab"]');
    function show(tab) {
      tabs.forEach(function (t) {
        var on = t === tab;
        t.setAttribute('aria-selected', on ? 'true' : 'false');
        var pane = document.getElementById(t.getAttribute('aria-controls'));
        if (pane) { pane.hidden = !on; }
      });
    }
    tabs.forEach(function (t) { t.addEventListener('click', function () { show(t); }); });
    if (tabs.length) { show(tabs[0]); }
  });
})();
