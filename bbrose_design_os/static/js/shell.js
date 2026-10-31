/* THE SHELL (templates/base.html): the three pills open their short lists; "/" puts the cursor in the one search field;
   the counts refresh while the page stays open, so what is running, waiting and needing attention is always current
   (the owner's goal of 2026-09-25, (d)). No inline script anywhere: this file is the shell's only behaviour. */
(function () {
  'use strict';
  var pills = document.getElementById('shell-pills');
  if (!pills) { return; }

  function closeAll(except) {
    pills.querySelectorAll('.pill[aria-expanded="true"]').forEach(function (b) {
      if (b === except) { return; }
      b.setAttribute('aria-expanded', 'false');
      var d = document.getElementById(b.getAttribute('aria-controls'));
      if (d) { d.hidden = true; }
    });
  }

  pills.addEventListener('click', function (e) {
    var btn = e.target.closest('.pill');
    if (!btn) { return; }
    var open = btn.getAttribute('aria-expanded') === 'true';
    closeAll(btn);
    btn.setAttribute('aria-expanded', open ? 'false' : 'true');
    var drop = document.getElementById(btn.getAttribute('aria-controls'));
    if (drop) { drop.hidden = open; }
  });

  document.addEventListener('click', function (e) {
    if (!e.target.closest('#shell-pills')) { closeAll(null); }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { closeAll(null); return; }
    var t = e.target;
    var typing = t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable);
    if (e.key === '/' && !typing) {
      var f = document.getElementById('shell-find');
      if (f) { e.preventDefault(); f.focus(); f.select(); }
    }
  });

  // THE BELL (the old dashboard's, reached again): a notification opened is read — marked by this click, then the
  // design opens; "Mark all read" marks every one. Without a script the row still opens its design.
  function csrf() {
    var m = document.cookie.match(/(?:^|; )csrftoken=([^;]*)/);
    return m ? decodeURIComponent(m[1]) : '';
  }
  function markRead(body) {
    return fetch('/api/notifications/mark_read/', {
      method: 'POST', credentials: 'same-origin',
      headers: { 'X-CSRFToken': csrf(), 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify(body)
    });
  }
  function showUnread(n) {
    var el = pills.querySelector('[data-unread]');
    if (!el) { return; }
    el.textContent = String(n);
    el.closest('.pill').classList.toggle('zero', !n);
  }
  pills.addEventListener('click', function (e) {
    var row = e.target.closest('[data-note]');
    if (row && row.classList.contains('new')) {
      e.preventDefault();
      var go = function () { if (row.getAttribute('href') && row.getAttribute('href') !== '#') { location.href = row.href; } };
      markRead({ id: Number(row.getAttribute('data-note')) }).then(go, go);
      return;
    }
    var all = e.target.closest('[data-notes-read]');
    if (all) {
      markRead({}).then(function (r) {
        if (!r.ok) { return; }
        pills.querySelectorAll('.note-row.new').forEach(function (n) { n.classList.remove('new'); });
        pills.querySelectorAll('.note-row .new-tag').forEach(function (t) { t.remove(); });
        showUnread(0);
        all.remove();
      }, function () { /* the next page shows the count as it stands */ });
    }
  });

  // the counts, refreshed every 30 seconds while the page is in view — numbers only; a list changes on the next page
  function refresh() {
    if (document.hidden) { return; }
    fetch('/dashboard/pulse/', { credentials: 'same-origin', headers: { 'Accept': 'application/json' } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data || !data.counts) { return; }
        if (typeof data.unread === 'number') { showUnread(data.unread); }
        Object.keys(data.counts).forEach(function (key) {
          var n = pills.querySelector('[data-count="' + key + '"]');
          if (n) {
            n.textContent = String(data.counts[key]);
            n.closest('.pill').classList.toggle('zero', !data.counts[key]);
          }
        });
      })
      .catch(function () { /* the next refresh tries again; the page keeps the counts it has */ });
  }
  setInterval(refresh, 30000);

  // a brand switch (New design, the Library): choosing a brand switches to it — its button does the same without a script
  document.querySelectorAll('form.brand-switch select').forEach(function (s) {
    s.addEventListener('change', function () { s.form.submit(); });
  });
  document.addEventListener('visibilitychange', refresh);
})();
