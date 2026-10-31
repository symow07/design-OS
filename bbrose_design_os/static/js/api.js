// === SHARED STATE (globals, visible across all dashboard modules) ===
// Promoted from module-local let/const so the poll/render/gates modules share
// them (top-level let/const are script-scoped and would not cross <script>s).
var activeTaskId = null;
var pollInterval = null;
var lastLogId = 0;
// Transient states where ARIA is actively working — keep polling, show feed. [His goal of 2026-10-06, item 2] the
// server's own list (apps/pipeline/live_views.py WORKING_STATUSES) is held equal to this one by a test.
var WORKING_STATUSES = ['running', 'queued', 'awaiting_trend_review', 'gate_1_approved', 'generating_dieline',
                        'gate_2_approved'];      // [§BH71 PART 2: the window closes by itself, so the page keeps asking]

// === HELPERS ===
// §BH55 Phase 3: A DESIGN HAS ITS OWN ADDRESS. Opening one moves the browser's address to it; the back and
// forward buttons move between designs and back to the home, which opens no one's design.
function designAddress(taskId) {
  return '/dashboard/designs/' + taskId + '/';
}

function pushDesignAddress(taskId) {
  const url = designAddress(taskId);
  if (location.pathname !== url) history.pushState({taskId: String(taskId)}, '', url);
}

function showHome() {
  stopLiveUpdates();
  activeTaskId = null;
  hideAllStates();
  if (typeof renderStageBreadcrumb === 'function') renderStageBreadcrumb(null);
  renderStepLine({status: 'home'});                               // §BH55 Phase 3: the home draws no step line
  document.querySelectorAll('.task-item').forEach(el => el.classList.remove('active'));
  document.getElementById('task-title').textContent = 'Start a design';
  const badge = document.getElementById('task-status-badge');
  badge.textContent = '';
  badge.className = '';
}

// §BH55 Phase 3: the words a designer reads for a design's state — the server's one map (apps/dashboard/words.py)
function statusWords(status) {
  if (!window._statusWords) {
    const el = document.getElementById('status-words');
    try { window._statusWords = el ? JSON.parse(el.textContent) : {}; } catch (e) { window._statusWords = {}; }
  }
  return window._statusWords[status] || String(status || '').replace(/_/g, ' ');
}

// §BH55 Phase 3: WHERE THE DESIGN STANDS AMONG ITS STEPS, in a designer's words — a line above every design: the
// steps done, the one waiting on them ("your turn") or being worked on, and the ones still ahead. A carton has a size
// step, a bottle a shape step, a printed or on-screen piece neither. A stopped or rejected design draws no line; its
// own panel says what happened.
var STEP_FAMILIES = {
  artwork: ['Brief', 'Direction', 'Concept', 'Design', 'Approved'],
  container: ['Brief', 'Direction', 'Concept', 'Shape', 'Design', 'Approved'],
  carton: ['Brief', 'Direction', 'Concept', 'Size', 'Design', 'Approved'],
};
var ARTWORK_TARGETS = ['marketing_material', 'social_media', 'exhibition_booth', 'display_stand'];

function stepFamily(data) {
  const t = data.design_target || '';
  if (ARTWORK_TARGETS.includes(t)) return 'artwork';
  if (t === 'product_container') return 'container';
  return 'carton';
}

function currentStep(data, steps) {
  const s = data.status;
  const at = (name, extra) => Object.assign({i: steps.indexOf(name)}, extra || {});
  const some = (x) => Array.isArray(x) && x.length > 0;
  if (s === 'completed') return at('Approved', {done: true});
  if (s === 'gate_2_approved') return at('Approved', {working: true});
  if (s === 'awaiting_gate_2') return at('Design');
  if (s === 'generating_dieline') return at('Design', {working: true});
  if (s === 'awaiting_dimensions') return at('Size');
  if (s === 'awaiting_container_profile') return at('Shape');
  if (s === 'gate_1_approved') return at(steps.includes('Size') ? 'Size' : steps.includes('Shape') ? 'Shape' : 'Design',
                                         {working: true});
  if (s === 'awaiting_gate_1' || s === 'awaiting_gate1_generation_configuration') return at('Concept');
  if (s === 'awaiting_direction_selection') return at('Direction');
  if (s === 'awaiting_trend_review') return at('Direction', {working: true});      // §BH71 PART 2: the trends first
  if (s === 'queued' || s === 'running') {
    if (some(data.images) || (data.brief && some(data.brief.directions))) return at('Concept', {working: true});
    return at('Brief', {working: true});
  }
  return null;
}

function renderStepLine(data) {
  const el = document.getElementById('step-line');
  if (!el) return;
  const steps = STEP_FAMILIES[stepFamily(data)];
  const now = currentStep(data, steps);
  if (!now || now.i < 0) { el.innerHTML = ''; el.style.display = 'none'; return; }
  // [His goal after the pitch page, 2026-10-15, B (11)] a step the pitch run is taking is worked on, never "your turn"
  if (data.autopilot && data.autopilot.taking) now.working = true;
  el.style.display = '';
  el.innerHTML = '<ol class="steps" aria-label="Where this design stands">' + steps.map((name, i) => {
    const state = (i < now.i || (i === now.i && now.done)) ? 'done'
      : i === now.i ? (now.working ? 'working' : 'now') : 'next';
    const label = state === 'now' ? `${name} — your turn` : state === 'working' ? `${name} — working on it` : name;
    const current = (state === 'now' || state === 'working') ? ' aria-current="step"' : '';
    return `<li class="step step-${state}"${current}>${escapeHtml(label)}</li>`;
  }).join('') + '</ol>';
}

// §BH55 Phase 3: a refusal is DRAWN where the person is looking — it was thrown as a browser alert, which says
// nothing about where it came from and cannot be read again once it is dismissed (survey rows 4.13, 6.14)
function drawRefusal(words, what) {
  const note = document.getElementById('refusal-note');
  if (!note) { sayInPage(words); return; }                   // another page, with no place to draw it — said in the page
  note.innerHTML = `<strong>${escapeHtml(what || 'It was refused.')}</strong> ${escapeHtml(words)}`;
  note.hidden = false;
  note.scrollIntoView({block: 'nearest'});
}

function clearRefusal() {
  const note = document.getElementById('refusal-note');
  if (note) { note.hidden = true; note.innerHTML = ''; }
}

function hideAllStates() {
  clearRefusal();
  ['review-board', 'feed-state', 'trend-state', 'direction-state', 'gallery-state', 'dimensions-state', 'profile-state', 'gate2-state', 'complete-state', 'state-note'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
  });
}

function updateTaskDotInList(taskId, status) {
  const item = document.querySelector(`.task-item[data-task-id="${taskId}"]`);
  if (item) {
    item.dataset.status = status;
    const dot = item.querySelector('.task-status-dot');
    if (dot) dot.className = `task-status-dot status-${status}`;
    const words = item.querySelector('.task-state');       // §BH55 Phase 3: the row's words follow the design
    if (words) words.textContent = statusWords(status);
  }
}

async function postAction(url, body) {
  // Never fail silently (P3 fix 2026-07-04): a 403 (missing Reviewer role) or
  // 409 (gate already actioned elsewhere) used to return null and re-render
  // the same panel — "nothing happens". Surface the server's error text.
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCsrf()},
      body: JSON.stringify(body)
    });
    if (res.ok) return await res.json();
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      detail = data.error || data.detail || detail;
    } catch (e) { /* non-JSON body */ }
    drawRefusal(detail, 'It was refused.');
    return null;
  } catch (e) {
    drawRefusal('The server did not answer — it may be stopped. Nothing was changed.', 'It did not reach the server.');
    return null;
  }
}

function getCsrf() {
  return document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='))?.split('=')[1] || '';
}

function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => (
    {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]
  ));
}
