/* START A NEW DESIGN (templates/dashboard/new.html): the rail on the left keeps what is answered — what is being
   designed, for which product, whether it is described — as the form changes. It reads the form; it sends nothing. */
(function () {
  'use strict';
  function rail(key, words, done) {
    var span = document.querySelector('[data-rail="' + key + '"]');
    if (span) { span.textContent = words; }
    var step = span && span.closest('.rstep');
    if (step) { step.classList.toggle('ok', !!done); }
  }
  function refresh() {
    var chip = document.querySelector('#target-selector .target-chip.active');
    rail('what', chip ? chip.querySelector('.chip-name').textContent.trim() : '—', !!chip);
    var sel = document.getElementById('product-select');
    var opt = sel && sel.options[sel.selectedIndex];
    rail('product', opt && sel.value ? opt.textContent.split('·')[0].split(' — ').slice(1).join(' — ').trim() || opt.textContent.trim()
                                     : 'None on record', true);
    var text = document.getElementById('task-input');
    var written = !!(text && text.value.trim());
    rail('describe', written ? 'Written' : 'In your own words', written);
    var start = document.getElementById('rail-start');
    if (start) { start.classList.toggle('later', !written); start.classList.toggle('now', written); }
  }
  document.addEventListener('DOMContentLoaded', function () {
    document.addEventListener('click', function (e) { if (e.target.closest('#target-selector')) { setTimeout(refresh, 0); } });
    var sel = document.getElementById('product-select');
    if (sel) { sel.addEventListener('change', refresh); }
    var text = document.getElementById('task-input');
    if (text) { text.addEventListener('input', refresh); }
    refresh();
  });
})();
