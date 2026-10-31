/* ADJUST, IN PLACE (templates/dashboard/_adjust.html) — his pick of 2026-09-25: "pick an element and try colours and faces
   from a library that stays open". A try is posted to the design loop asking for JSON (apps/dashboard/loop_views.py) and
   its picture is shown here, beside the design; a refusal is said in its own words, its code kept under the record. The
   element picked in Adjust is the one the library's colours are tried on; a face in the library is tried on the name.
   Without this script the form posts as it always did and the loop page answers. Nothing here is recorded as a choice. */
(function () {
  'use strict';
  function csrf() {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : '';
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c];
    });
  }
  // [his last goal before the pitch, 2026-10-16, Step 1 (6): "The design page loads with the drawing visible fast (no
  // blank seconds ...)"] the Adjust panel's controls are worked out after the page shows — a lid's took seconds to
  // compose (its knobs redraw the face) and held the whole page blank; they arrive here, with the library's tries
  document.addEventListener('DOMContentLoaded', function () {
    var pending = document.querySelector('#adjust[data-src]');
    if (!pending || !window.fetch) { bind(); return; }
    fetch(pending.dataset.src, {credentials: 'same-origin', headers: {'Accept': 'application/json'}})
      .then(function (res) { if (!res.ok) { throw new Error(String(res.status)); } return res.json(); })
      .then(function (data) {
        var holder = document.createElement('div');
        holder.innerHTML = data.adjust || '';
        var fresh = holder.querySelector('#adjust');
        if (fresh) { pending.replaceWith(fresh); } else { pending.remove(); }
        var lib = new DOMParser().parseFromString(data.library || '', 'text/html');
        ['lib-colours', 'lib-faces'].forEach(function (id) {
          var now = document.getElementById(id), got = lib.getElementById(id);
          if (now && got) { now.innerHTML = got.innerHTML; }
        });
        var box = document.getElementById('inspiration-box');
        if (box && window.DesignOSMountInspiration) { window.DesignOSMountInspiration(box); }
        bind();
      })
      .catch(function () {
        var why = pending.querySelector('.why');
        if (why) { why.textContent = 'The controls did not arrive — open the page again to try the design.'; }
      });
  });

  function bind() {
    var form = document.getElementById('adjust-form');
    if (!form || !form.dataset.inPlace || !window.fetch) { return; }
    var result = document.getElementById('adjust-result');
    var colours = Array.prototype.slice.call(form.querySelectorAll('select[data-kind="colour"]'));
    var face = form.querySelector('select[name="face_name"]');
    var picked = colours[0] || null;                   // the element the library's colours go to: the first, until picked

    function sayPicked() {
      document.querySelectorAll('[data-picked]').forEach(function (el) {
        el.textContent = picked ? picked.dataset.label.toLowerCase() : '';
      });
      colours.forEach(function (s) { s.closest('label').classList.toggle('picked', s === picked); });
    }
    colours.forEach(function (s) {
      s.addEventListener('focus', function () { picked = s; sayPicked(); });
      s.addEventListener('change', function () { picked = s; sayPicked(); });
    });
    sayPicked();

    function show(html, refused) {
      result.hidden = false;
      result.classList.toggle('refused', !!refused);
      result.innerHTML = html;
    }
    function tried(data) {
      var lines = (data.what_changed || []).map(function (l) { return '<li>' + esc(l) + '</li>'; }).join('');
      show('<figure><img src="' + esc(data.url) + '" alt="The design, tried"><figcaption>' +
           (lines ? '<ul>' + lines + '</ul>' : '<p>Drawn as it stands.</p>') +
           '<a href="' + esc(form.dataset.loop || '') + '#side-by-side">See every try side by side ›</a></figcaption></figure>');
      var tries = document.getElementById('adjust-tries');
      if (tries) {
        var n = tries.querySelector('[data-tries]');
        n.textContent = String((parseInt(n.textContent, 10) || 0) + 1);
        tries.hidden = false;
        var none = document.getElementById('adjust-no-tries');
        if (none) { none.remove(); }
      }
    }
    function refusedWords(data) {
      // a loop refusal reads "CODE: REFUSED — sentence": the sentence is said, the code kept under the record
      var why = String(data.why || '');
      var cut = why.indexOf(' — ');
      var words = cut >= 0 ? why.slice(cut + 3) : why;
      show('<p><b>It was not drawn.</b> ' + esc(words) + '</p><details class="tech"><summary>What the record says' +
           '</summary><p><code>' + esc(data.refused || '') + '</code></p></details>', true);
    }
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var go = form.querySelector('button[type="submit"]');
      go.disabled = true;
      show('<p>Drawing it…</p>');
      fetch(form.action, {method: 'POST', body: new FormData(form), credentials: 'same-origin',
                          headers: {'Accept': 'application/json', 'X-CSRFToken': csrf()}})
        .then(function (res) { return res.json().then(function (data) { return {ok: res.ok, data: data}; }); })
        .then(function (r) { if (r.ok) { tried(r.data); } else { refusedWords(r.data); } })
        .catch(function () { show('<p><b>It was not drawn.</b> The answer did not arrive — nothing was kept.</p>', true); })
        .then(function () { go.disabled = false; });
    });

    // the library beside the design: a colour is tried on the element picked in Adjust, a face on the name
    document.querySelectorAll('#library-panel [data-colour]').forEach(function (b) {
      b.addEventListener('click', function () {
        if (!picked) { return; }
        picked.value = b.dataset.colour;
        form.requestSubmit ? form.requestSubmit() : form.submit();
      });
    });
    document.querySelectorAll('#library-panel [data-face]').forEach(function (b) {
      b.addEventListener('click', function () {
        if (!face) { return; }
        face.value = b.dataset.face;
        form.requestSubmit ? form.requestSubmit() : form.submit();
      });
    });
  }
})();
