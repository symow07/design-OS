/* The files page works in place (the owner, 2026-10-30): Accept, Accept all, Redraw and Make my files post without a
   reload, and only what changed is replaced, so the scroll, an open image and a note being typed all stay. While a job
   runs the page asks again. Without JavaScript the forms post normally and the page refreshes itself. */
(() => {
  const POLL_MS = 5000;
  let polling = null;

  const plain = node => {
    const copy = node.cloneNode(true);
    copy.querySelectorAll('[name=csrfmiddlewaretoken]').forEach(field => field.remove());
    return copy.outerHTML;
  };

  const swap = (from, to) => {
    if (!from || !to) return;
    if (plain(from) !== plain(to)) from.replaceWith(document.importNode(to, true));
  };

  const apply = html => {
    const fresh = new DOMParser().parseFromString(html, 'text/html');
    document.querySelectorAll('[data-live]').forEach(part => {
      swap(part, fresh.querySelector(`[data-live="${part.dataset.live}"]`));
    });
    fresh.querySelectorAll('[data-live]').forEach(part => {
      if (!document.querySelector(`[data-live="${part.dataset.live}"]`) && part.dataset.after) {
        document.querySelector(part.dataset.after)?.after(document.importNode(part, true));
      }
    });
    document.querySelectorAll('[data-face-card]').forEach(card => {
      const twin = fresh.querySelector(`[data-face-card="${card.dataset.faceCard}"]`);
      if (!twin) return;
      [...card.children].forEach((child, index) => swap(child, twin.children[index]));
    });
    poll(fresh.querySelector('[data-refreshing]') !== null);
  };

  const ask = () => fetch(location.href, {credentials: 'same-origin', headers: {Accept: 'text/html'}})
    .then(response => response.text()).then(apply).catch(() => poll(true));

  function poll(on) {
    clearTimeout(polling);
    polling = on ? setTimeout(ask, POLL_MS) : null;
  }

  document.addEventListener('submit', event => {
    const form = event.target;
    if (!form.closest('[data-in-place]') || form.dataset.posting) return;
    event.preventDefault();
    form.dataset.posting = 'yes';
    const button = form.querySelector('button[type=submit]');
    if (button) button.disabled = true;
    fetch(form.action, {method: 'POST', body: new FormData(form), credentials: 'same-origin'})
      .then(response => response.text())
      .then(apply)
      .catch(() => {
        // the post may not have arrived: the browser's own submit says so in the page
        delete form.dataset.posting;
        form.submit();
      });
  });

  poll(document.querySelector('[data-refreshing]') !== null);
})();
