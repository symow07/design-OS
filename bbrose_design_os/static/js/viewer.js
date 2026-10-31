/* [His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (6): "SEE THE DESIGN ON THE PAGE: show each drawing (outside,
   inside, lid, tray, back label, plates) large, with click-to-enlarge, zoom and pan, so I never need to open the file to
   see it."] The design's drawings, from the server's own list (/api/tasks/<id>/drawing/): one shown large, the others
   beside it as small views; a click on the large one opens it over the page — the wheel or the buttons zoom, a drag
   pans, a double click fits it again, Escape closes. Never a new tab, never the file. */
(function () {
  'use strict';

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) { n.className = cls; }
    if (text) { n.textContent = text; }
    return n;
  }

  // ---- the enlarged view: zoom and pan over the page ----
  var box = null, img = null, state = {scale: 1, x: 0, y: 0, dragging: false, sx: 0, sy: 0};

  function apply() {
    img.style.transform = 'translate(' + state.x + 'px,' + state.y + 'px) scale(' + state.scale + ')';
  }
  function fit() { state.scale = 1; state.x = 0; state.y = 0; apply(); }
  function zoom(by, cx, cy) {
    var old = state.scale;
    state.scale = Math.min(12, Math.max(1, state.scale * by));
    if (cx !== undefined) {           // zoom about the pointer: the point under it stays under it
      var r = img.parentNode.getBoundingClientRect();
      var px = cx - r.left - r.width / 2 - state.x, py = cy - r.top - r.height / 2 - state.y;
      state.x -= px * (state.scale / old - 1);
      state.y -= py * (state.scale / old - 1);
    }
    if (state.scale === 1) { state.x = 0; state.y = 0; }
    apply();
  }

  function build() {
    if (box) { return box; }
    box = el('dialog', 'viewer-dialog');
    box.id = 'viewer-dialog';
    var bar = el('div', 'viewer-bar');
    var title = el('span', 'viewer-title');
    var out = el('button', 'btn sm quiet', '−'); out.type = 'button'; out.setAttribute('aria-label', 'Zoom out');
    var into = el('button', 'btn sm quiet', '+'); into.type = 'button'; into.setAttribute('aria-label', 'Zoom in');
    var whole = el('button', 'btn sm quiet', 'Fit'); whole.type = 'button';
    var close = el('button', 'btn sm', 'Close'); close.type = 'button';
    bar.appendChild(title); bar.appendChild(out); bar.appendChild(into); bar.appendChild(whole); bar.appendChild(close);
    var stage = el('div', 'viewer-stage');
    img = el('img', 'viewer-img');
    img.alt = '';
    img.draggable = false;
    stage.appendChild(img);
    box.appendChild(bar);
    box.appendChild(stage);
    out.addEventListener('click', function () { zoom(1 / 1.5); });
    into.addEventListener('click', function () { zoom(1.5); });
    whole.addEventListener('click', fit);
    close.addEventListener('click', function () { box.close(); });
    stage.addEventListener('wheel', function (e) { e.preventDefault(); zoom(e.deltaY < 0 ? 1.2 : 1 / 1.2, e.clientX, e.clientY); },
                           {passive: false});
    stage.addEventListener('dblclick', function (e) { if (state.scale > 1) { fit(); } else { zoom(3, e.clientX, e.clientY); } });
    stage.addEventListener('pointerdown', function (e) {
      if (state.scale === 1) { return; }
      state.dragging = true; state.sx = e.clientX - state.x; state.sy = e.clientY - state.y;
      stage.setPointerCapture(e.pointerId); stage.classList.add('dragging');
    });
    stage.addEventListener('pointermove', function (e) {
      if (!state.dragging) { return; }
      state.x = e.clientX - state.sx; state.y = e.clientY - state.sy; apply();
    });
    stage.addEventListener('pointerup', function () { state.dragging = false; stage.classList.remove('dragging'); });
    box.addEventListener('keydown', function (e) {
      if (e.key === '+' || e.key === '=') { zoom(1.5); } else if (e.key === '-') { zoom(1 / 1.5); }
      else if (e.key === '0') { fit(); }
    });
    document.body.appendChild(box);
    return box;
  }

  function enlarge(view) {
    var d = build();
    d.querySelector('.viewer-title').textContent = view.words;
    img.src = view.large;
    img.alt = view.words;
    fit();
    if (typeof d.showModal === 'function') { d.showModal(); } else { d.setAttribute('open', ''); }
  }

  // ---- the drawings on the page: one large, the rest as views beside it ----
  function render(host, views) {
    host.textContent = '';
    if (!views.length) { return; }
    var main = el('figure', 'drawing-main');
    var big = el('img', 'drawing-big');
    var caption = el('figcaption', 'drawing-caption');
    main.appendChild(big);
    main.appendChild(caption);
    var strip = el('div', 'drawing-strip');
    var current = views[0];
    function show(view) {
      current = view;
      big.src = view.url;
      big.alt = view.words;
      caption.textContent = view.words + ' — click to enlarge, then zoom and move around it';
      strip.querySelectorAll('button').forEach(function (b) { b.setAttribute('aria-pressed', String(b._view === view)); });
    }
    views.forEach(function (view) {
      var b = el('button', 'drawing-thumb');
      b.type = 'button';
      b._view = view;
      var t = el('img');
      t.loading = 'lazy';                 // the small views drawn as they come into sight, after the large one
      t.src = view.thumb;
      t.alt = '';
      b.appendChild(t);
      b.appendChild(el('span', '', view.words));
      b.addEventListener('click', function () { show(view); });
      strip.appendChild(b);
    });
    big.addEventListener('click', function () { enlarge(current); });
    host.appendChild(main);
    if (views.length > 1) { host.appendChild(strip); }
    show(views[0]);
  }

  /** host: an element; taskId: the design. Fills the host with the design's drawings, large, from the server. */
  window.showDrawings = async function (host, taskId) {
    if (!host) { return; }
    try {
      var res = await fetch('/api/tasks/' + taskId + '/drawing/', {credentials: 'same-origin'});
      if (!res.ok) { return; }
      var data = await res.json();
      render(host, data.views || []);
      // [his goal of 2026-10-13, (5) and (6)] the drawing shown once: the page's own picture of it gives way to the
      // views, and stays where there are none
      if ((data.views || []).length && host.parentNode) { host.parentNode.classList.add('has-drawings'); }
    } catch (e) { /* the page keeps its own picture */ }
  };
})();
