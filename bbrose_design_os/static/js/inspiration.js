/* §BH69(2) — THE INSPIRATION BOX on New design (templates/dashboard/new.html), for every kind of design. Each picture
   dropped or chosen is read into words at once (POST /api/inspiration/read/), and what was taken shows under it —
   layout, colours, mood, finish, type style — with what was seen and never taken. Start sends the pictures with the
   design (poll.js asks this box through window.DesignOSInspiration); the design is planned from their words, and the
   picture itself is never drawn from. Its colours are said in words, never as codes. No inline script and no inline
   style. On a design's Adjust panel (templates/dashboard/_inspiration_add.html, data-task) the same box reads each
   picture against that design and keeps it there once read (POST /api/tasks/<id>/inspiration/) — nothing waits for a
   Start, and the Adjust form beside it, whose tries stay free, never carries a picture. */
(function () {
  'use strict';

  // [his final goal, 2026-10-05, B1] the same box twice on New design: the inspiration pictures, and beside them the
  // inside references — each read at once (an inside reference for its pattern and style), each sent with Start
  function mount(box, handle) {
  if (!box) { return; }
  var input = box.querySelector('.ref-input');
  var list = box.querySelector('.inspire-list');
  var zone = box.querySelector('.inspire-zone');
  var max = parseInt(box.getAttribute('data-max') || '6', 10);
  var kind = box.getAttribute('data-kind') || 'inspiration_picture';
  var task = box.getAttribute('data-task');         // a design's Adjust panel: each picture is kept with it once read
  var staged = [];                                  // {file, li, state: 'reading' | 'read' | 'refused'}

  function csrf() {
    var m = document.cookie.match(/(?:^|; )csrftoken=([^;]*)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) { e.className = cls; }
    if (text) { e.textContent = text; }
    return e;
  }

  function show(item, data) {
    var body = item.li.querySelector('.inspire-words');
    body.querySelector('.inspire-state').remove();
    var taken = data.taken || {};
    var rows = kind === 'inside_reference'
      ? [['Pattern', taken.pattern], ['Direction', taken.direction], ['Density', taken.density],
         ['Style', taken.style]]
      : kind === 'sticker_reference'
      ? [['Shape', taken.shape], ['Fill', taken.fill], ['Border', taken.border], ['Style', taken.style]]
      : [['Layout', taken.layout], ['Colours', taken.colour_words], ['Mood', taken.mood],
         ['Finish', taken.finish], ['Type', taken.type_style]];
    var dl = el('dl', 'inspire-read');
    rows.forEach(function (r) {
      if (!r[1]) { return; }
      dl.appendChild(el('dt', '', r[0]));
      dl.appendChild(el('dd', '', r[1]));
    });
    body.appendChild(dl);
    if (taken.take) { body.appendChild(el('p', 'inspire-take', 'What the design takes: ' + taken.take)); }
    if (data.seen_not_taken && data.seen_not_taken.length) {
      body.appendChild(el('p', 'inspire-seen', 'Seen, and never copied: ' + data.seen_not_taken.join(' · ')));
    }
    var cost = data.read_before ? 'Read before — nothing spent' : 'Read for $' + Number(data.cost_usd).toFixed(3);
    body.appendChild(el('p', 'small inspire-cost', task ? cost + ' · kept with this design' : cost));
    if (data.over_cap) { body.appendChild(el('p', 'inspire-state warn', data.over_cap)); }
    if (task) {                                     // kept: it stays with the design, so there is nothing to remove
      var gone = item.li.querySelector('.inspire-remove');
      if (gone) { gone.remove(); }
    }
    item.li.classList.remove('reading');
    item.li.classList.add('read');
  }

  function refuse(item, words) {
    var state = item.li.querySelector('.inspire-state');
    if (state) { state.textContent = words; state.classList.add('warn'); }
    item.li.classList.remove('reading');
    item.li.classList.add('refused');
  }

  function read(item) {
    var fd = new FormData();
    fd.append('picture', item.file, item.file.name);
    fd.append('kind', kind);
    fetch(task ? '/api/tasks/' + encodeURIComponent(task) + '/inspiration/' : '/api/inspiration/read/',
          {method: 'POST', credentials: 'same-origin', headers: {'X-CSRFToken': csrf(), 'Accept': 'application/json'},
           body: fd})
      .then(function (r) { return r.json().then(function (d) { return {ok: r.ok, d: d}; }); })
      .then(function (x) {
        if (x.ok) { item.state = 'read'; show(item, x.d); }
        else { item.state = 'refused'; refuse(item, (x.d && x.d.words) || 'The picture could not be read.'); }
      })
      .catch(function () {
        item.state = 'refused';
        refuse(item, 'The picture could not be read just now — remove it and add it again.');
      });
  }

  function remove(item) {
    staged = staged.filter(function (i) { return i !== item; });
    item.li.remove();
  }

  function add(files) {
    Array.prototype.forEach.call(files, function (file) {
      if (staged.filter(function (i) { return i.state !== 'refused'; }).length >= max) { return; }
      var li = el('li', task ? 'inspire-item reading' : 'inspire-item');
      var img = el('img', 'inspire-pic');
      img.alt = '';
      img.src = URL.createObjectURL(file);
      li.appendChild(img);
      var body = el('div', 'inspire-words');
      body.appendChild(el('b', 'inspire-name', file.name));
      body.appendChild(el('p', 'inspire-state', task ? 'Reading the picture…' : 'Added — read after Start'));
      li.appendChild(body);
      var btn = el('button', 'btn sm ghost inspire-remove', 'Remove');
      btn.type = 'button';
      li.appendChild(btn);
      list.appendChild(li);
      var item = {file: file, li: li, state: task ? 'reading' : 'staged'};
      btn.addEventListener('click', function () { remove(item); });
      staged.push(item);
      if (task) { read(item); }
    });
  }

  input.addEventListener('change', function () { add(input.files); input.value = ''; });
  if (zone) {
    zone.addEventListener('dragover', function (e) { e.preventDefault(); zone.classList.add('drag-active'); });
    zone.addEventListener('dragleave', function () { zone.classList.remove('drag-active'); });
    zone.addEventListener('drop', function (e) {
      e.preventDefault();
      zone.classList.remove('drag-active');
      if (e.dataTransfer && e.dataTransfer.files) { add(e.dataTransfer.files); }
    });
  }

  if (task) { return; }                             // a design's box keeps each picture itself; there is no Start to ask

  // what Start asks of this box (static/js/poll.js submitTask)
  window[handle] = {
    count: function () { return staged.filter(function (i) { return i.state !== 'refused'; }).length; },
    reading: function () { return staged.some(function (i) { return i.state === 'reading'; }); },
    appendToFormData: function (fd) {
      staged.forEach(function (i) { if (i.state !== 'refused') { fd.append(kind, i.file, i.file.name); } });
    },
    clear: function () { staged.forEach(function (i) { i.li.remove(); }); staged = []; },
  };
  }

  mount(document.getElementById('inspiration-box'), 'DesignOSInspiration');
  mount(document.getElementById('inside-box'), 'DesignOSInside');
  mount(document.getElementById('sticker-box'), 'DesignOSSticker');
  // [his last goal before the pitch, 2026-10-16, Step 1 (6)] a design's Adjust panel arrives after its page (adjust.js):
  // its box is mounted when it does
  window.DesignOSMountInspiration = function (box) { mount(box, 'DesignOSInspiration'); };
})();
