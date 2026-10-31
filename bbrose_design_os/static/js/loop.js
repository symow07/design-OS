// §BH54(b) (k) 4 — each piece's room, shown as he types. The room is MEASURED by the server (the back panel's own
// composer, in the task's back zone — or the zone typed in this form); this script only asks and shows the server's
// words. Over its room a piece is still saved: the line warns, the form never refuses. Without this script the page
// still works: the rooms it was served with stand, and the confirmation page measures again.
(function () {
  const form = document.querySelector('form.knobs[data-room-url]');
  if (!form) return;
  const watched = Array.from(form.querySelectorAll('textarea[data-piece], input[name^="back_"]'));
  let timer = null;
  let asked = 0;

  function show(rooms) {
    form.querySelectorAll('.room[data-piece]').forEach(line => {
      const piece = (rooms.pieces || {})[line.dataset.piece];
      if (!piece) return;
      line.textContent = piece.line;
      line.classList.toggle('over', !!piece.over && piece.state !== 'unwritten');
    });
    const total = document.getElementById('room-total');
    if (total) {
      total.textContent = rooms.total_line || '';
      total.classList.toggle('over', rooms.fits === false);
    }
  }

  async function ask() {
    const mine = ++asked;
    try {
      const res = await fetch(form.dataset.roomUrl, {method: 'POST', body: new FormData(form), credentials: 'same-origin',
                                                     headers: {'Accept': 'application/json'}});
      if (!res.ok || mine !== asked) return;       // a bad number is said by the render, not here; a stale answer is dropped
      show(await res.json());
    } catch (e) { /* the page still works without the live line */ }
  }

  watched.forEach(field => field.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(ask, 250); }));
})();
