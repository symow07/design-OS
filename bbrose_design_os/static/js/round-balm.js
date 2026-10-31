(function () {
  'use strict';
  function show(name) {
    ['selection', 'history', 'jury'].forEach(function (key) {
      var section = document.getElementById('round-' + key);
      if (section) section.hidden = key !== name;
    });
    document.querySelectorAll('[data-round-tab]').forEach(function (button) {
      var selected = button.dataset.roundTab === name;
      button.classList.toggle('primary', selected);
      button.setAttribute('aria-pressed', String(selected));
    });
  }
  document.addEventListener('click', function (event) {
    var tab = event.target.closest('[data-round-tab]');
    if (tab) { show(tab.dataset.roundTab); return; }
    var link = event.target.closest('[data-round-jump]');
    if (!link) return;
    var id = link.dataset.roundJump;
    var target = document.getElementById('selection-candidate-' + id) || document.getElementById('history-candidate-' + id);
    if (target) {
      event.preventDefault();
      show(target.closest('#round-history') ? 'history' : 'selection');
      target.scrollIntoView();
    }
  });
  document.querySelectorAll('[data-panel-width]').forEach(function (image) {
    var width = Number(image.dataset.panelWidth), height = Number(image.dataset.panelHeight);
    if (Number.isFinite(width) && width > 0 && Number.isFinite(height) && height > 0) {
      image.style.width = width + 'mm'; image.style.height = height + 'mm';
    }
  });
})();
