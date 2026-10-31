// === INIT ===
document.addEventListener('DOMContentLoaded', () => {
  // arrow wrapper: the click event must never reach submitTask's
  // omission-approval parameter (B4b-2C §5 — approval is per-attempt)
  // [the owner's answer to the UI directions of 2026-09-25: a design's page carries no start form]
  document.getElementById('btn-submit')?.addEventListener(
    'click', () => { FORM_CONFIRMED = false; submitTask(); });   // [his goal of 2026-10-06, item 1] asked afresh each Start
  initTargetSelector();

  // §BH55 Phase 3: the home opens no one's design (it used to open the first design waiting on anyone); a design's
  // own address opens that design, and the browser's back and forward move between designs and the home
  if (window.OPEN_TASK_ID) {
    history.replaceState({taskId: String(OPEN_TASK_ID)}, '', location.pathname + location.search);
    loadTask(OPEN_TASK_ID, {push: false});
  }
  window.addEventListener('popstate', (e) => {
    const id = e.state && e.state.taskId;
    if (id) loadTask(id, {push: false});
    else showHome();
  });

  initLoadingClass();
  initConnectionToasts();
});

// [the checklist of 2026-09-26: the notification bell moved into the one shell's top bar — templates/base.html,
// static/js/shell.js — where every page carries it; its old header is gone with the old page]

// === LOADING CLASS ON BUTTON CLICK ===
function initLoadingClass() {
  document.addEventListener('click', e => {
    const btn = e.target.closest('.btn-approve, .btn-reject, #btn-submit, .btn-download');
    if (!btn || btn.disabled) return;
    btn.classList.add('loading');
    // Clear after 8s as a fallback; explicit unlocks happen when handlers settle
    setTimeout(() => btn.classList.remove('loading'), 8000);
  }, true);
}

// === CONNECTION / TOASTS ===
function initConnectionToasts() {
  window.addEventListener('online', () => showToast('Connection restored', 'info'));
  window.addEventListener('offline', () => showToast('Connection lost — the design goes on working', 'warning'));
}

function showToast(msg, type = 'info') {
  const stack = document.getElementById('toast-stack');
  if (!stack) return;
  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  t.textContent = msg;
  stack.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

// === DESIGN TARGET SELECTOR (B4a) ===
// Which target the shared pipeline builds. Default packaging → composer looks
// exactly as before; Product Container reveals its optional inputs.
// [his last goal before the pitch, 2026-10-16, Step 1 (5): "New design: nothing pre-selected"] none until he picks one
var SELECTED_TARGET = null;

// §BH70(1), item 15: the targets that start from the product's own shape, as the page lists them (`HINT_TARGETS`)
// [the owner's answer of 2026-09-27 to the §BH70 report's fourth question: "when a brief says "gloss" without saying
// which, ask me: wand vial or squeeze tube." The server asks before anything is created; his choice is kept here for
// the one submission it answers, rides the brief as its container hint, and is cleared when the design starts]
var GLOSS_CHOICE = '';
// [his goal of 2026-10-06, item 1: "the Container type I choose ALWAYS wins"] set when, asked because his brief's words
// name another form, he keeps the Container type he chose — for the one submission his answer belongs to
var FORM_CONFIRMED = false;

function askGlossContainer(data, onChoice) {
  const d = document.getElementById('gloss-dialog');
  if (!d || typeof d.showModal !== 'function') {
    sayInPage(data.words || data.question || 'Wand vial or squeeze tube?');
    return;
  }
  document.getElementById('gloss-title').textContent = data.question || '';
  document.getElementById('gloss-desc').textContent = data.words || '';
  const box = document.getElementById('gloss-choices');
  box.innerHTML = (data.choices || []).map(c =>
    `<button type="button" class="btn primary" data-gloss="${escapeHtml(c.key)}"${c.keeps ? ' data-keeps="1"' : ''}>${escapeHtml(c.label)}</button>`)
    .join('') + '<button type="button" class="btn" data-gloss="">Not now</button>';
  box.onclick = function (e) {
    const b = e.target.closest('button[data-gloss]');
    if (!b) return;
    d.close();
    if (b.dataset.gloss) onChoice(b.dataset.gloss, b.dataset.keeps === '1');
  };
  d.showModal();
}

function _takesProductHints(target) {
  const ph = document.getElementById('product-hints');
  return !!ph && (ph.dataset.targets || '').split(/\s+/).indexOf(target) !== -1;
}

function initTargetSelector() {
  const sel = document.getElementById('target-selector');
  if (!sel) return;
  sel.querySelectorAll('.target-chip:not([disabled])').forEach(chip => {
    chip.addEventListener('click', () => {
      // B4a: switching only changes which target-specific fields are shown.
      // Shared fields (project name, brief, product) are never touched, so
      // typed text survives a switch.
      sel.querySelectorAll('.target-chip').forEach(c => {
        c.classList.remove('active');
        c.setAttribute('aria-checked', 'false');
      });
      chip.classList.add('active');
      chip.setAttribute('aria-checked', 'true');
      SELECTED_TARGET = chip.dataset.target;
      const ci = document.getElementById('container-inputs');
      if (ci) ci.hidden = SELECTED_TARGET !== 'product_container';     // [2026-09-25: no inline style — CSP]
      // §BH70(1), item 15: the product hints, for every target the page names — Complete Product among them
      const ph = document.getElementById('product-hints');
      if (ph) ph.hidden = !_takesProductHints(SELECTED_TARGET);
      // B4b-2C §2: hiding the editor HOLDS the canonical inventory — the UI
      // module only needs to know which target is visible so the
      // held-reference notice can speak for the hidden files.
      if (window.DesignOSReferenceUI) {
        DesignOSReferenceUI.setTargetVisibility(
          SELECTED_TARGET === 'product_container');
      }
      const ta = document.getElementById('task-input');
      if (ta) ta.placeholder = SELECTED_TARGET === 'product_container'
        ? 'Describe the container design (e.g. rose-nectar lip gloss, warm rose, gold cap)…'
        : 'What should it look and feel like? Name the mood, the colours, the finish, anything it must say…';  // §BH55 Phase 3: it read "Give ARIA a task..."
      // Composite hint (C3): name the linked stages when a composite target is
      // selected, so Complete Product visibly reads as multi-stage.
      const hint = document.getElementById('composite-hint');
      if (hint) {
        const stages = COMPOSITE_STAGES[SELECTED_TARGET];
        // 2C-1 §2/§13: the workflow preview — human-gated, multi-stage,
        // honestly labelled (not production-ready).
        hint.innerHTML = stages
          ? `<span class="ch-tag">Made in stages — each one approved by you</span>
             <ol class="ch-steps">
               <li>Design the product container</li>
               <li>Approve the container (your gates)</li>
               <li>Design coordinated packaging</li>
               <li>Review the complete product set</li>
             </ol>` : '';
        hint.hidden = !stages;
      }
    });
  });
  // §BH55 Phase 3: the server chooses the target the page opens on — its default, or a finished design's own when a
  // start is filled in from one — and the page takes it as a click would, so that target's fields show
  const chosen = sel.querySelector('.target-chip.active:not([disabled])');
  if (chosen) chosen.click();
}

// === TASK SUBMISSION ===
// omissionApproved is set ONLY by the omission dialog's confirm action, and
// only for that single attempt (B4b-2C §5) — nothing stores the approval.
async function submitTask(omissionApproved) {
  omissionApproved = omissionApproved === true;
  // [Step 1 (5)] nothing is chosen for him: Start asks what is being designed, in words, and sends nothing
  if (!SELECTED_TARGET) {
    showToast('Choose what you are designing first — question 1.', 'info');
    const first = document.querySelector('#target-selector .target-chip:not([disabled])');
    if (first) first.focus();
    return;
  }
  const text = document.getElementById('task-input').value.trim();
  if (!text) return;   // brief is required
  const nameEl = document.getElementById('project-name');
  const projectName = nameEl ? nameEl.value.trim() : '';

  const productEl = document.getElementById('product-select');
  const productId = productEl ? productEl.value : null;
  // [his answers after 122 was redrawn, 2026-10-08, (1)] his optional SKU, sent with every kind of design
  const skuEl = document.getElementById('sku-input');
  const sku = skuEl ? skuEl.value.trim() : '';
  // Optional container archetype hint appended to the brief so it reaches the
  // concept prompt + profile inference without a new create-API field.
  let taskText = projectName ? `${projectName}\n\n${text}` : text;
  if (_takesProductHints(SELECTED_TARGET)) {
    // B4a: optional hints appended to the brief so they reach the concept
    // prompt and profile inference. HINTS ONLY - the authoritative profile is
    // confirmed later at the Confirm Profile gate.
    const hints = [];
    [['container-archetype', 'Container type'],
     ['container-category', 'Product category'],
     ['container-capacity', 'Capacity'],
     ['container-closure', 'Closure']].forEach(([id, label]) => {
      const v = ((document.getElementById(id) || {}).value || '').trim();
      if (v) hints.push(`${label}: ${v}`);
    });
    if (hints.length) taskText = `${taskText}\n\n[${hints.join('; ')}]`;
  }
  // [the owner's answer of 2026-09-27: a gloss named with no container asked him — his choice rides the brief]
  if (GLOSS_CHOICE) taskText = `${taskText}\n\n[Container type: ${GLOSS_CHOICE}]`;

  // §BH69(2): the inspiration pictures are read BEFORE the design starts — Start waits for a read still running
  const inspiration = window.DesignOSInspiration || null;
  const inside = window.DesignOSInside || null;          // [his final goal, B1] the inside references, read at once
  const sticker = window.DesignOSSticker || null;        // [his final goal, B3] the custom sticker's pictures
  if ((inspiration && inspiration.reading()) || (inside && inside.reading()) || (sticker && sticker.reading())) {
    showToast('A picture is still being read — Start once its words show.', 'info');
    return;
  }

  // [His goal after the pitch page, 2026-10-15, B (9)] the pitch run, asked by its one tick beside Start
  const pitchRun = !!(document.getElementById('autopilot-toggle') || {}).checked;

  document.getElementById('btn-submit').disabled = true;
  document.getElementById('btn-submit').textContent = 'Starting...';

  // B4b-2A-3: transport branches only by design target. Product Container is
  // ALWAYS multipart (zero staged files is a valid multipart request);
  // everything else stays JSON. References come solely from the canonical
  // inventory through the public handle — never from inputs, DOM or globals.
  const isContainer = SELECTED_TARGET === 'product_container';
  const refUI = isContainer ? window.DesignOSReferenceUI : null;
  const intake = {};
  ['dimensions', 'count', 'material', 'method', 'languages', 'copy'].forEach(key => {
    intake[key] = ((document.getElementById('intake-' + key) || {}).value || '');
  });
  let fetchOpts;
  if (isContainer) {
    if (!refUI) {
      // failing safely beats silently submitting a task the owner believes
      // carries references. The UI handle is the structured error surface;
      // when it is the thing that is missing, write to the rendered error
      // region directly — the in-page notice only if even that markup is absent.
      _referenceIntegrationError(
        'REFERENCE_UI_UNAVAILABLE',
        'The reference panel did not initialise — reload the page before ' +
        'starting a Product Container task. Nothing was sent.');
      document.getElementById('btn-submit').disabled = false;
      document.getElementById('btn-submit').textContent = 'Start the design';
      return;
    }
    refUI.clearErrors();
    const fd = new FormData();
    fd.append('task_text', taskText);
    fd.append('intake', JSON.stringify(intake));
    if (productId) fd.append('product_id', productId);
    if (sku) fd.append('sku', sku);
    if (ACTIVE_BRAND_ID) fd.append('brand_id', ACTIVE_BRAND_ID);
    fd.append('design_target', SELECTED_TARGET);
    if (FORM_CONFIRMED) fd.append('form_confirmed', 'true');
    if (pitchRun) fd.append('autopilot', 'true');
    try {
      refUI.appendToFormData(fd);
      if (inspiration) inspiration.appendToFormData(fd);                 // §BH69(2): read into words, never drawn from
      if (inside) inside.appendToFormData(fd);                           // [his final goal, B1] the inside's pictures
      if (sticker) sticker.appendToFormData(fd);                         // [his final goal, B3] the sticker's
    } catch (err) {
      // never surface exception text — a stable code and calm words (§14)
      refUI.showGeneralError(
        'REFERENCE_PAYLOAD_BUILD_FAILED',
        'Staged references could not be attached — nothing was sent. ' +
        'Your files are still staged.');
      document.getElementById('btn-submit').disabled = false;
      document.getElementById('btn-submit').textContent = 'Start the design';
      return;
    }
    refUI.setSubmitting(true);
    fetchOpts = {method: 'POST', headers: {'X-CSRFToken': getCsrf()}, body: fd};
  } else {
    // B4b-2C §4: a Packaging submission while Product Container references
    // are staged must be an informed decision, not a silent omission. The
    // dialog asks once, for THIS attempt only; any outcome other than the
    // explicit confirm dispatches nothing.
    const heldUI = window.DesignOSReferenceUI;
    const held = heldUI ? heldUI.count() : 0;
    if (held > 0 && !omissionApproved &&
        SELECTED_TARGET === 'packaging' && window.DesignOSOmissionDialog) {
      document.getElementById('btn-submit').disabled = false;
      document.getElementById('btn-submit').textContent = 'Start the design';
      DesignOSOmissionDialog.open({
        count: held,
        needsCorrection: document.querySelectorAll(
          '.ref-card.server-error').length > 0,
        opener: document.getElementById('btn-submit'),
        onCancel: function () { /* stay on Packaging, keep everything */ },
        onReturn: function () { heldUI.returnToProductContainer(); },
        onSubmit: function () { submitTask(true); },
      });
      return;
    }
    if ((inspiration && inspiration.count() > 0) || (inside && inside.count() > 0)
        || (sticker && sticker.count() > 0)) {
      // §BH69(2): a design with inspiration pictures carries them — any kind of design, read into words at Start
      const fd = new FormData();
      fd.append('task_text', taskText);
    fd.append('intake', JSON.stringify(intake));
      if (productId) fd.append('product_id', productId);
      if (sku) fd.append('sku', sku);
      if (ACTIVE_BRAND_ID) fd.append('brand_id', ACTIVE_BRAND_ID);
      fd.append('design_target', SELECTED_TARGET);
      if (FORM_CONFIRMED) fd.append('form_confirmed', 'true');
      if (pitchRun) fd.append('autopilot', 'true');
      if (inspiration) inspiration.appendToFormData(fd);
      if (inside) inside.appendToFormData(fd);
      if (sticker) sticker.appendToFormData(fd);
      fetchOpts = {method: 'POST', headers: {'X-CSRFToken': getCsrf()}, body: fd};
    } else {
      fetchOpts = {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCsrf()},
        body: JSON.stringify({
          task_text: taskText,
          intake,
          product_id: productId || undefined,
          sku: sku || undefined,
          brand_id: ACTIVE_BRAND_ID || undefined,
          design_target: SELECTED_TARGET,
          form_confirmed: FORM_CONFIRMED || undefined,
          autopilot: pitchRun || undefined,
        }),
      };
    }
  }

  try {
    const res = await fetch('/api/tasks/create/', fetchOpts);
    const data = await res.json();
    if (res.ok) {
      GLOSS_CHOICE = '';
      FORM_CONFIRMED = false;
      document.getElementById('task-input').value = '';
      if (inspiration) inspiration.clear();
      if (inside) inside.clear();
      if (sticker) sticker.clear();
      // success is the ONLY moment staged references are cleared. That
      // includes confirmed Packaging success after omission approval: the
      // owner explicitly finished a different task agreeing the held
      // Product Container references would not be used (B4b-2C §6).
      if (refUI) refUI.clearAfterSuccess();
      else if (omissionApproved && window.DesignOSReferenceUI) {
        DesignOSReferenceUI.clearAfterSuccess();
      }
      // [the owner's answer to the UI directions of 2026-09-25: a started design opens on its own page — the start
      // page holds no design. A page may define BBROSE_OPEN_DESIGN before this script loads to be told instead
      // (the browser tests' harness does, so its stand-in design is never opened)]
      (window.BBROSE_OPEN_DESIGN || (id => window.location.assign(designAddress(id))))(data.task_id);
    } else if (data && data.error === 'GLOSS_CONTAINER_QUESTION') {
      // nothing was created: he is asked which, and the design starts on his choice
      askGlossContainer(data, function (choice) { GLOSS_CHOICE = choice; submitTask(omissionApproved); });
    } else if (data && (data.error === 'CONTAINER_TYPE_QUESTION' || data.error === 'CONTAINER_TYPE_DIFFERS')) {
      // [his goal of 2026-10-06, item 1] nothing was created: his brief's words name two forms, or another form than the
      // Container type he chose — he answers, and his answer is his Container type (the list itself where it is shown)
      askGlossContainer(data, function (choice, keeps) {
        const field = document.getElementById('container-archetype');
        if (keeps) FORM_CONFIRMED = true;
        else if (field && _takesProductHints(SELECTED_TARGET)) field.value = choice;
        else GLOSS_CHOICE = choice;
        submitTask(omissionApproved);
      });
    } else if (isContainer && refUI &&
               data && data.error === 'REFERENCE_VALIDATION_FAILED') {
      // the server names each rejected file (category + request-local index);
      // the UI marks the matching STAGED cards — files remain in the browser
      refUI.showServerErrors(data.rejections || []);
    } else if (isContainer && refUI) {
      // any other refusal (4xx/5xx) on a container flow: a GENERAL error —
      // no individual staged file may be falsely marked invalid
      refUI.showGeneralError(
        'TASK_CREATE_FAILED',
        'The task could not be created (' +
        ((data && (data.words || data.error)) || 'unknown error') +
        '). Nothing was sent to production and your staged references ' +
        'are untouched.');
    } else {
      // §BH69(2): a refusal that carries its words says them (an inspiration picture the door refused)
      sayInPage(data.words || ('Error: ' + (data.error || 'Unknown error')));
    }
  } catch (err) {
    // network failure or malformed response: nothing was created server-side
    // that we can confirm — staged references are deliberately retained, and
    // no individual file is falsely marked invalid
    if (isContainer && refUI) {
      refUI.showGeneralError(
        'SUBMISSION_FAILED',
        'The request failed — nothing was confirmed. Your staged ' +
        'references are untouched.');
    } else {
      sayInPage('The request failed — nothing was confirmed.');
    }
  } finally {
    if (refUI) refUI.setSubmitting(false);
    document.getElementById('btn-submit').disabled = false;
    document.getElementById('btn-submit').textContent = 'Start the design';
  }
}

// === LOAD TASK ===
async function loadTask(taskId, opts) {
  // [the owner's answer to the UI directions of 2026-09-25: a design's page shows ONE design — its header, its concepts
  // and its library are that design's own — so opening another design from it (a Complete Product's other stage)
  // opens that design's own page, never its step under this one's header]
  if (window.OPEN_TASK_ID && String(taskId) !== String(window.OPEN_TASK_ID)) {
    window.location.assign(designAddress(taskId));
    return;
  }
  stopLiveUpdates();
  activeTaskId = taskId;
  lastLogId = 0;
  if (!opts || opts.push !== false) pushDesignAddress(taskId);     // §BH55 Phase 3: the design's own address

  const data = await fetchStatus(taskId);
  if (!data) return;
  // [his goal of 2026-10-06, item 2] the status the page opened on: a stage he opened finished moves on to the next stage
  // only when it finished while he watched
  if (window._openedFor !== String(taskId)) { window._openedFor = String(taskId); window._openedStatus = data.status; }

  renderTaskState(data);

  if (WORKING_STATUSES.includes(data.status)) {
    const rs = data.container_reconstruction_status;
    if (rs && rs.terminal) {
      // terminal snapshot: nothing to poll — but watched, as startIntervalPolling watches it. [Found by Day 10's full
      // suite, 2026-10-23] a container's approval read in the moment before its files (gate_2_approved, its drawing
      // done) returned here with nothing armed, and the page stayed on "Approved — preparing the files" until a reload
      startWatching(taskId, data);
      return;
    }
    startPolling(taskId, data);
  } else {
    startWatching(taskId, data);        // [his goal of 2026-10-06, item 2] a step of his: watched for what moves without him
  }
}

// === LIVE UPDATES (Milestone 13.2: SSE with polling fallback) ===
// Stall watchdog (hardening 2026-07-04): some proxies/CDNs buffer SSE without
// erroring, so onerror never fires and the UI silently freezes. The server
// emits a visible `ping` event ~15s; if NO event of any kind arrives for
// SSE_STALL_MS the client abandons the stream and falls back to polling.
var SSE_STALL_MS = 45000;
var pollTimer = null;
var _pollGeneration = 0;

function startPolling(taskId, initialData) {
  stopLiveUpdates();
  if (window.EventSource) {
    try {
      const es = new EventSource(`/api/tasks/${taskId}/events/`);
      window._taskES = es;
      let lastEventAt = Date.now();
      const alive = () => { lastEventAt = Date.now(); };
      const fallBack = () => {
        es.close();
        if (window._taskES === es) window._taskES = null;
        if (window._esWatchdog) { clearInterval(window._esWatchdog); window._esWatchdog = null; }
        startIntervalPolling(taskId);
      };
      const gen = _pollGeneration;
      const refresh = async () => {
        alive();
        if (activeTaskId != taskId) { stopLiveUpdates(); return; }
        const data = await fetchStatus(taskId);
        // §12: re-check after the await — a task switch mid-request must
        // not let the old task's snapshot paint the new task's board
        if (gen !== _pollGeneration || activeTaskId != taskId) return;
        if (data) renderTaskState(data);
      };
      es.addEventListener('status', refresh);
      es.addEventListener('log', refresh);
      es.addEventListener('ping', alive);
      // [his goal of 2026-10-06, item 2: "Today I had to refresh to see the trend pictures and thought it was still
      // working."] the settled snapshot is DRAWN: this read `refresh(); stopLiveUpdates();` — the stop moved the poll
      // generation while the refresh still waited on its fetch, so the screen the design had reached was thrown away and
      // the page stayed on the working feed until a reload. It is fetched after the stop now, drawn, and watched on.
      es.addEventListener('settled', async () => {
        stopLiveUpdates();
        const data = await fetchStatus(taskId);
        if (activeTaskId != taskId || !data) return;
        renderTaskState(data);
        if (WORKING_STATUSES.includes(data.status)) startPolling(taskId, data);
        else startWatching(taskId, data);
      });
      es.onerror = fallBack;
      window._esWatchdog = setInterval(() => {
        if (activeTaskId != taskId) { stopLiveUpdates(); return; }
        if (Date.now() - lastEventAt > SSE_STALL_MS) fallBack();
      }, 5000);
      return;
    } catch (e) { /* fall through to polling */ }
  }
  startIntervalPolling(taskId, initialData);
}

// Fallback polling (UI-2B-1 controller): settle-then-schedule — exactly one
// in-flight request, the next timer is armed only after the previous request
// finishes, terminal states stop the loop, and a generation token makes any
// late response from an earlier task/loop inert (§12: never rely on abort
// alone). Interval bounds and retry policy live HERE, nowhere else.
var POLL_FALLBACK_MS = 10000;
// the polling floor — kept when the page set one before this script loaded (a design's page opens its design as it
// loads, so a browser test that measures the loop at a short floor sets it first)
var POLL_MIN_MS = (typeof POLL_MIN_MS === 'number') ? POLL_MIN_MS : 2000;
var POLL_MAX_MS = 60000;
var STATUS_RETRY_LIMIT = 3;     // bounded automatic retry for refresh failures

function _clampPollMs(ms) {
  const n = parseInt(ms, 10);
  if (!n || isNaN(n)) return POLL_FALLBACK_MS;
  return Math.min(POLL_MAX_MS, Math.max(POLL_MIN_MS, n));
}

function _noteStatusRefresh(failed) {
  // §13: STATUS_REFRESH_FAILED is presentation-only — it never claims the
  // reconstruction itself failed, and it clears on the next good snapshot
  const note = document.getElementById('recon-refresh-note');
  if (!note) return;
  note.hidden = !failed;
  note.textContent = failed
    ? 'Reconstruction status could not be refreshed. The confirmed profile '
      + 'remains recorded. (STATUS_REFRESH_FAILED)'
    : '';
}

function startIntervalPolling(taskId, initialData) {
  const gen = ++_pollGeneration;
  let failures = 0;

  const schedule = (data) => {
    const rs = data && data.container_reconstruction_status;
    const ms = _clampPollMs(rs && rs.poll_after_ms);
    pollTimer = setTimeout(tick, ms);
  };

  const tick = async () => {
    if (gen !== _pollGeneration || activeTaskId != taskId) return;
    const data = await fetchStatus(taskId);
    // stale-response check AFTER the await: a response that raced a task
    // switch (or a newer loop) may not paint anything
    if (gen !== _pollGeneration || activeTaskId != taskId) return;
    if (!data) {
      failures += 1;
      _noteStatusRefresh(true);
      if (failures <= STATUS_RETRY_LIMIT) schedule(null);
      return;                     // bound reached: keep the note, stop quietly
    }
    failures = 0;
    _noteStatusRefresh(false);
    renderTaskState(data);
    const rs = data.container_reconstruction_status;
    if (!WORKING_STATUSES.includes(data.status) || (rs && rs.terminal)) {
      startWatching(taskId, data);  // [his goal of 2026-10-06, item 2] a step of his, watched for what moves without him
      return;                     // terminal — no further timer
    }
    schedule(data);
  };

  // §9: loadTask already performed the immediate refresh — the first tick
  // is scheduled from THAT snapshot's cadence, not the generic fallback
  schedule(initialData || null);
}

// [his goal of 2026-10-06, item 2: "When a step finishes in the background (trend pictures found, directions made, concept
// pictures drawn, a drawing done, the carton's pictures), the open design page switches to the next screen on its own,
// without me pressing refresh."] A design waiting at a step of his can still move without him — the trend window closes,
// a redraw finishes, a Complete Product's carton begins once its vial is approved, another tab or person acts — and the
// event stream is closed at a step of his. The page asks where the design stands (/where/, a few fields) every few
// seconds and redraws when the version of its screen moves; a Complete Product's stage that finished while he watched
// opens the next stage's page. His own ticks and notes do not move the version, so nothing he is typing is redrawn.
// The floor is kept when the page set one before this script loaded (the browser tests set a short one).
var WATCH_MS = (typeof WATCH_MS === 'number') ? WATCH_MS : 4000;
var watchTimer = null;

function startWatching(taskId, data) {
  if (watchTimer) { clearTimeout(watchTimer); watchTimer = null; }
  const gen = _pollGeneration;
  const seen = (data && data.watch && data.watch.version) || null;
  const tick = async () => {
    watchTimer = null;
    if (gen !== _pollGeneration || activeTaskId != taskId) return;
    let where = null;
    try {
      const res = await fetch(`/api/tasks/${taskId}/where/`, {cache: 'no-store'});
      where = res.ok ? await res.json() : null;
    } catch (e) { where = null; }
    if (gen !== _pollGeneration || activeTaskId != taskId) return;
    if (where && where.next_task_id && where.status === 'completed' && window._openedStatus !== 'completed'
        && window.OPEN_TASK_ID) {
      window.location.assign(designAddress(where.next_task_id));     // the next stage, which his approval began
      return;
    }
    if (where && seen !== null && where.version !== seen) { loadTask(taskId, {push: false}); return; }
    watchTimer = setTimeout(tick, WATCH_MS);
  };
  watchTimer = setTimeout(tick, WATCH_MS);
}

function stopLiveUpdates() {
  _pollGeneration += 1;           // §12: orphan any in-flight tick
  if (pollTimer) { clearTimeout(pollTimer); pollTimer = null; }
  if (watchTimer) { clearTimeout(watchTimer); watchTimer = null; }
  if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
  if (window._taskES) { try { window._taskES.close(); } catch (e) {} window._taskES = null; }
  if (window._esWatchdog) { clearInterval(window._esWatchdog); window._esWatchdog = null; }
}

// === FETCH STATUS ===
async function fetchStatus(taskId) {
  // Full history in one fetch (2026-07-04): superseded images from earlier
  // passes come along; the Gate 1 gallery filters to the current set and the
  // design-history panel shows everything.
  try {
    const res = await fetch(`/api/tasks/${taskId}/status/?include_superseded=1`);
    return res.ok ? await res.json() : null;
  } catch { return null; }
}

// Transient states where ARIA is actively working — keep polling, show feed.


// B4b-2B §14: structured fallback for the one failure the UI handle cannot
// present — its own absence. Uses the server-rendered error region when it
// exists; the in-page notice only as the last resort on a page without the section.
function _referenceIntegrationError(code, message) {
  const host = document.getElementById('ref-errors');
  const live = document.getElementById('ref-live');
  if (host) {
    const row = document.createElement('div');
    row.className = 'ref-error-row ref-error-general';
    row.setAttribute('role', 'alert');
    row.setAttribute('tabindex', '-1');
    row.textContent = message;
    host.textContent = '';
    host.appendChild(row);
    if (live) live.textContent = message;
    row.focus();
  } else {
    sayInPage(message);
  }
}
