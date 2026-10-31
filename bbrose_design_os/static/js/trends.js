// === THE TREND BOARD (§BH71 PART 2) ===
// The owner's goal of 2026-09-28: "Show the found pictures on the design page before directions. They are used by
// default; I can untick any I dislike in one click. They feed the directions in words, like my uploaded pictures. The
// pictures themselves are never placed, and never near-copied. Tell me the cost per design."
// The board is drawn from the design's live record (data.trend_board): each picture numbered, where it was found and a
// link to its page, ticked; one click posts the untick at once. The directions are made with the ticked pictures'
// words when he presses on — or when the review window closes, the clock shown here. Thumbnails come from our own
// origin; a picture's own page opens in a new tab. Nothing here places a picture anywhere.

function _trendEsc(text) {
  const div = document.createElement('div');
  div.textContent = String(text == null ? '' : text);
  return div.innerHTML;
}

function _trendClock(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');
}

function _trendCost(cost) {
  if (!cost) return '';
  const parts = [];
  if (cost.searches) parts.push(`${cost.searches} search${cost.searches === 1 ? '' : 'es'} ($${Number(cost.search_usd).toFixed(3)})`);
  if (cost.reads) parts.push(`${cost.reads} picture${cost.reads === 1 ? '' : 's'} read into words ($${Number(cost.read_usd).toFixed(3)})`);
  if (!parts.length) return 'Nothing spent on trends yet.';
  return `These trends cost $${Number(cost.total_usd).toFixed(3)}: ${parts.join(', ')}.`;
}

function _trendSignature(board) {
  return JSON.stringify([board.status, board.pictures.map(p => [p.id, p.used, p.feeds]), board.links.length,
                         board.brief ? board.brief.written_at : '']);
}

// [his goal for the pitch, 2026-10-15, A (1): "Write a short TREND BRIEF (what's new: colours, type, materials,
// illustration styles, layouts) and show it on the design page."] the brief first, its sources linked under it
const _TREND_BRIEF_SECTIONS = [['colours', 'Colours'], ['type', 'Type'], ['materials', 'Materials'],
                               ['illustration', 'Illustration styles'], ['layouts', 'Layouts']];

function _trendBrief(brief) {
  if (!brief) return '';
  const cite = text => _trendEsc(text).replace(/\[(\d+(?:,\s*\d+)*)\]$/, '<span class="trend-cite">[$1]</span>');
  const sections = _TREND_BRIEF_SECTIONS.filter(([key]) => (brief[key] || []).length).map(([key, label]) =>
    `<div class="trend-brief-part"><h4>${label}</h4><ul>${brief[key].map(p => `<li>${cite(p)}</li>`).join('')}</ul></div>`).join('');
  const sources = (brief.sources || []).length ? `<details class="trend-brief-sources"><summary>${brief.sources.length} source${brief.sources.length === 1 ? '' : 's'}</summary>
      <ol>${brief.sources.map(s => `<li value="${s.n}">${_trendEsc(s.platform)} · <a href="${_trendEsc(s.url)}" target="_blank" rel="noopener noreferrer">${_trendEsc(s.title || s.url)}</a></li>`).join('')}</ol></details>` : '';
  return `<section class="trend-brief" aria-labelledby="trend-brief-h">
      <h3 id="trend-brief-h">Trend brief</h3>
      ${brief.headline ? `<p class="trend-brief-headline">${_trendEsc(brief.headline)}</p>` : ''}
      ${brief.whats_new ? `<p>${_trendEsc(brief.whats_new)}</p>` : ''}
      <div class="trend-brief-grid">${sections}</div>
      ${sources}
    </section>`;
}

// the clock ticks between polls without redrawing the pictures
function _trendTick() {
  const el = document.getElementById('trend-clock');
  if (!el || !window._trendDeadline) return;
  const left = (window._trendDeadline - Date.now()) / 1000;
  el.textContent = left > 0 ? _trendClock(left) : 'now';
}

function showTrendBoard(data, readOnly) {
  const board = data.trend_board;
  const state = document.getElementById('trend-state');
  const view = document.getElementById('trend-view');
  if (!state || !view) return;
  if (!board || (!board.pictures.length && !board.links.length && board.status !== 'FAILED')) {
    state.style.display = 'none';
    return;
  }
  state.style.display = '';
  const open = !readOnly && board.status === 'READY' && data.status === 'awaiting_trend_review';
  window._trendDeadline = board.deadline ? Date.parse(board.deadline) : null;
  const signature = _trendSignature(board) + (open ? ':open' : ':closed');
  if (view.dataset.signature === signature) { _trendTick(); return; }
  view.dataset.signature = signature;

  const heading = open
    ? `Current trends for this ${_trendEsc(board.subject.replace(/^cosmetic /, ''))} — found on the web and read into words`
    : `The trends these directions were made with — ${board.used_at_confirm.length} of ${board.feeding} picture${board.feeding === 1 ? '' : 's'} used`;
  const lede = open
    ? 'Every picture is used by default. Untick any you dislike — one click each. The directions are made with the words '
      + 'of the ticked pictures; the pictures themselves are never drawn from and never copied.'
    : (board.confirmed_how ? `Confirmed: ${_trendEsc(board.confirmed_how)}.` : '');
  // [his goal of 2026-10-06, item 3] never a blank tile: a picture that feeds nothing and has no picture is a link (the
  // server sends it as one; one that comes so anyway joins the links here); one that feeds the directions keeps its tile
  // and its tick, its words in place of the picture it has none of
  const shown = board.pictures.filter(p => p.thumb_url || p.feeds);
  const asLinks = board.links.concat(board.pictures.filter(p => !(p.thumb_url || p.feeds)).map(p =>
    ({number: p.number, platform: p.platform, page_url: p.page_url, title: p.title, why: p.why_not})))
    .sort((a, b) => a.number - b.number);
  const cards = shown.map(p => {
    const thumb = p.thumb_url
      ? `<img src="${_trendEsc(p.thumb_url)}" alt="Trend picture ${p.number}, found on ${_trendEsc(p.platform)}" loading="lazy">`
      : '';
    const tick = p.feeds
      ? `<label class="trend-tick"><input type="checkbox" data-pick="${p.id}" ${p.used ? 'checked' : ''} ${open ? '' : 'disabled'}>
           <span>${open ? (p.used ? 'Used' : 'Not used') : (board.used_at_confirm.includes(p.id) ? 'Used' : 'Not used')}</span></label>`
      : `<p class="trend-why">${_trendEsc(p.why_not)}</p>`;
    return `<figure class="trend-card${p.feeds && !p.used ? ' off' : ''}" data-number="${p.number}">
        <span class="trend-no">${p.number}</span>${thumb}
        <figcaption>
          <span class="trend-from">Found on ${_trendEsc(p.platform)} · <a href="${_trendEsc(p.page_url)}" target="_blank" rel="noopener noreferrer">open the page</a></span>
          ${p.words ? `<span class="trend-words">${_trendEsc(p.words)}</span>` : ''}
          ${tick}
        </figcaption>
      </figure>`;
  }).join('');
  const links = asLinks.length ? `<div class="trend-links"><b>Found as links</b> — their pictures are not fetched:
      <ul>${asLinks.map(l => `<li>${l.number}. ${_trendEsc(l.platform)} · <a href="${_trendEsc(l.page_url)}" target="_blank" rel="noopener noreferrer">${_trendEsc(l.title || 'open the page')}</a>${l.why ? ` <span class="trend-why-link">(${_trendEsc(l.why)})</span>` : ''}</li>`).join('')}</ul></div>` : '';
  // [his test findings on design 121, 2026-10-07, item 5] the pictures left out — never shown — counted, with why
  const leftOut = (board.left_out || []).length ? `<p class="trend-left-out">Left out, not shown: ${board.left_out.map(l =>
      `${l.count} — ${_trendEsc(l.words)}`).join('; ')}.</p>` : '';
  const refusals = board.refusals.length ? `<ul class="trend-refusals">${board.refusals.map(r =>
      `<li><b>${_trendEsc(r.platform)}</b> — ${_trendEsc(r.words)}</li>`).join('')}</ul>` : '';
  const searched = board.searches.length ? `<details class="trend-searched"><summary>How this was searched (${board.searches.length} searches)</summary>
      <ul>${board.searches.map(s => `<li>${_trendEsc(s.platform)}: “${_trendEsc(s.query)}”</li>`).join('')}</ul></details>` : '';
  const failed = board.status === 'FAILED'
    ? `<p class="trend-why">The trend search stopped (${_trendEsc(board.failure)}) — the directions are made without trends.</p>` : '';
  const act = open ? `<div class="trend-act">
      <button type="button" class="btn primary" id="trend-continue">Make the directions now with ${board.ticked} picture${board.ticked === 1 ? '' : 's'}</button>
      <span class="quiet">or they are made with the ticked ones in <b id="trend-clock">${_trendClock(board.seconds_left || 0)}</b></span>
    </div>` : '';
  view.innerHTML = `<section class="trend-board" aria-labelledby="trend-h">
      <h2 id="trend-h">${heading}</h2>
      ${lede ? `<p class="trend-lede">${lede}</p>` : ''}
      ${_trendBrief(board.brief)}
      ${failed}
      <div class="trend-grid">${cards}</div>
      ${links}${leftOut}${refusals}
      <p class="trend-cost">${_trendEsc(_trendCost(board.cost))}</p>
      ${searched}${act}
    </section>`;

  view.querySelectorAll('input[data-pick]').forEach(box => {
    box.addEventListener('change', async () => {
      const used = box.checked;
      box.disabled = true;
      const res = await fetch(`/api/tasks/${data.id}/trends/${box.dataset.pick}/`, {
        method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCsrf()},
        body: JSON.stringify({used}),
      });
      box.disabled = false;
      if (!res.ok) {
        box.checked = !used;
        const body = await res.json().catch(() => ({}));
        drawRefusal(body.words || 'The tick could not be changed.', 'The tick was not changed.');
        return;
      }
      const card = box.closest('.trend-card');
      if (card) card.classList.toggle('off', !used);
      const label = box.parentElement.querySelector('span');
      if (label) label.textContent = used ? 'Used' : 'Not used';
      const ticked = view.querySelectorAll('input[data-pick]:checked').length;
      const go = document.getElementById('trend-continue');
      if (go) go.textContent = `Make the directions now with ${ticked} picture${ticked === 1 ? '' : 's'}`;
      view.dataset.signature = '';                 // the next poll redraws from the record
    });
  });
  const go = document.getElementById('trend-continue');
  if (go) {
    go.addEventListener('click', async () => {
      go.disabled = true;
      const res = await fetch(`/api/tasks/${data.id}/trends/continue/`, {
        method: 'POST', credentials: 'same-origin', headers: {'X-CSRFToken': getCsrf()},
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        drawRefusal(body.words || 'The directions could not be started.', 'Nothing was started.');
        go.disabled = false;
        return;
      }
      loadTask(data.id);
    });
  }
  if (window._trendClockTimer) clearInterval(window._trendClockTimer);
  if (open) window._trendClockTimer = setInterval(_trendTick, 1000);
}
