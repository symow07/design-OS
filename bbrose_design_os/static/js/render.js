// === RENDER BASED ON STATUS ===
function renderTaskState(data) {
  window._lastSpendEstimates = data.spend_estimates || null;       // §BH54(k) 1: read by the controls that spend
  window._lastLogsTotal = data.logs_total || 0;                    // …and by the feed, in every state that shows it
  window._lastDesignTarget = data.design_target || null;           // §BH55 Phase 3: …and the retry's cost, this kind's own
  window._lastTaskData = data;                                     // [his goal of 2026-10-13, (5)] one Approve reads it
  document.getElementById('task-title').textContent = data.task_text.substring(0, 50);
  // Milestone 12.2 — surface accumulated AI spend for this task on the badge.
  const costSuffix = (data.cost_usd && data.cost_usd > 0) ? `  ·  $${data.cost_usd.toFixed(2)}` : '';
  // §BH55 Phase 3: the badge says where the design stands in a designer's words (it read the engine's state)
  document.getElementById('task-status-badge').textContent = statusWords(data.status) + costSuffix;
  document.getElementById('task-status-badge').className = `status-badge status-${data.status}`;
  // [his test day finding 1, 2026-09-29: the header's "spent" was written once, when the page opened, and the badge on
  // every refresh — design 116's header said "$0.01 spent" while its badge said "$0.64". One number, the true one: the
  // header is written here with the badge, from the same ledger sum (cost_usd)]
  const spent = document.getElementById('task-spent');
  if (spent && typeof data.cost_usd === 'number') spent.textContent = `$${data.cost_usd.toFixed(2)} spent`;

  updateTaskDotInList(data.id, data.status);
  hideAllStates();
  // [his test findings on design 121, 2026-10-07, item 2: "The status must always match the real state."] the working box
  // and its clock belong to a working design only — design 121 stopped while its page was open, and the box stayed,
  // "Working on it … Running for 3 min", its clock ticking under the stop
  if (!WORKING_STATUSES.includes(data.status) || data.status === 'awaiting_trend_review') showWorkingStep(null);

  // Composite coordinator (C3): stage breadcrumb above every child view.
  // No-ops when data.project is null (single-target parity).
  renderStageBreadcrumb(data.project);
  renderStepLine(data);                                          // §BH55 Phase 3: where the design stands
  // [his goal of 2026-10-13, (3)] "Not moving?" never outlives the stop it was offered for: gone with every new state
  // that is not a stop — the states that offer it draw it again below
  const staleResume = document.getElementById('resume-note');
  if (staleResume && data.stalled !== true) staleResume.remove();
  // [His goal after the pitch page, 2026-10-15, B (11): "Every page must be calm during the run: no stops, no pop-ups,
  // the page moving on by itself, one clear button per step."] a pitch-run design at a step the system is taking by
  // itself shows one line in place of the step's form, its feed beneath — the page watches it move on as it watches
  // every step; a step it stopped at shows its form and its one button again
  const pilotLine = document.getElementById('pilot-step');
  if (pilotLine) pilotLine.remove();
  if (data.autopilot && data.autopilot.taking) {
    showFeed(data.logs, data.logs_total);
    const feed = document.getElementById('feed-state');
    const line = document.createElement('div');
    line.id = 'pilot-step';
    line.className = 'working-step';
    line.setAttribute('role', 'status');
    line.innerHTML = `<span class="ws-dot" aria-hidden="true"></span><div><b class="ws-now">${escapeHtml(data.autopilot.taking_words)}</b></div>`;
    feed.insertBefore(line, feed.firstChild);
    return;
  }

  if (data.status === 'awaiting_trend_review') {
    // §BH71 PART 2: the trend pictures, ticked, before the directions — the window closes by itself
    showTrendBoard(data);
  } else if (WORKING_STATUSES.includes(data.status)) {
    showResume(data);                                              // §BH55 Phase 3: a design that has stopped moving
    // UI-2A §15/§18: a container task reconstructing after its profile
    // confirmation shows the CONFIRMED persisted profile ("Reconstruction
    // queued / running…"), never a mutable editor and not a bare feed.
    // Packaging's generating_dieline (no container_confirmation) is
    // untouched. UI-2B owns the richer lifecycle view.
    const _spec = ((data.packaging_output || {}).spec_sheet) || {};
    if (data.status === 'generating_dieline' && _spec.container_confirmation) {
      renderReviewBoard(data);
      showConfirmProfile(data);          // state-dispatched: frozen summary
      return;
    }
    showFeed(data.logs, data.logs_total);
    showWorkingStep(data.working_step);                           // [his goal of 2026-10-06, item 2]
    // Working panel is shared with the failed view — drop stale history.
    const staleHist = document.querySelector('#feed-state .design-history');
    if (staleHist) staleHist.remove();
  } else if (data.status === 'awaiting_direction_selection') {
    // Phase 2A-4: pre-render planning choice — no renders exist, so no Review
    // Board frame and no gallery; just the intent and the three cards.
    showTrendBoard(data, true);                  // §BH71 PART 2: the trends these directions were made with, read only
    showDirectionSelection(data);
  } else if (data.status === 'awaiting_gate_1') {
    // Selectable cards = current set only; earlier passes go to history.
    const current = (data.images || []).filter(i => !i.superseded);
    renderReviewBoard(data);        // RB2: shared frame above the concepts
    showGallery(current, data.id, data);
  } else if (data.status === 'awaiting_dimensions') {
    renderReviewBoard(data);
    showDimensionGate(data.packaging_output, data.id, data.images, data.panel_info, data.drawing_stop_words);
  } else if (data.status === 'awaiting_container_profile') {
    renderReviewBoard(data);
    showConfirmProfile(data);
  } else if (data.status === 'awaiting_gate_2') {
    renderReviewBoard(data);
    const targetLabel = data.review_board && data.review_board.header
      && data.review_board.header.target;
    showGate2(data.packaging_output, data.id, data.gate_decisions, data.images, targetLabel, data);
    // UI-2B-2A: a completed container reconstruction ALSO shows its frozen
    // confirmed profile + Reconstruction Result beside the approval UI —
    // and an INCONSISTENT completion shows the safe status panel instead of
    // silently pretending nothing is wrong
    const rsG2 = data.container_reconstruction_status;
    if (data.container_reconstruction_result
        || (rsG2 && rsG2.lifecycle_state
            === 'RECONSTRUCTION_STATUS_INCONSISTENT')) {
      showConfirmProfile(data);
    }
  } else if (data.status === 'completed') {
    renderReviewBoard(data);
    // Composite (C3): on the final stage of a finished project, show the
    // aggregated project summary (both deliverables); otherwise the untouched
    // single-task completed view.
    if (data.project && data.project.status === 'completed') {
      showProjectCompleted(data);
    } else {
      showCompleted(data);
    }
  } else if (data.status === 'failed') {
    showFailed(data.id, data.logs, data.stop_words, data.images);   // [item 3] why it stopped, in words
  } else if (data.status === 'rejected') {
    showRejected(data.logs);
  } else {
    // §BH55 Phase 3: a state with no panel of its own drew NOTHING — the pane was blank and the design looked lost
    // (survey rows 1.18, 6.24, 4.21). It says where the design stands, what it waits for, and where that is done.
    renderReviewBoard(data);
    showStateNote(data);
  }
}

//: what a state with no panel of its own waits for, and where it is done
const STATE_NOTES = {
  design_intent_confirmed: ["Its design intent is confirmed.",
                            "The next step for a palette is its own confirmation page."],
  awaiting_design_intent_confirmation: ["It waits for its design intent to be confirmed.",
                                        "That is done on its confirmation page."],
  container_stage_visually_rejected: ["It was rejected at its review, so it goes no further as it is.",
                                      "Its history holds what was said each time."],
  awaiting_gate1_generation_configuration: ["Its concepts are held before any drawing.",
                                            "They are released when everything they need exists — resume it below."],
  // [the clean-up of 2026-10-04, his Q1 "remove the dormant packaging flow"] the structure step is gone; a design
  // that paused at it (task 50) stays on record and readable, with nothing to do here
  awaiting_structure_confirmation: ["It paused at a structure check this site no longer runs.",
                                    "Nothing waits on it — its history holds every record and file."],
};

// a record's time in a reader's words ("25 Sep, 15:47"); the record's own stamp stays in the <time> element
function whenWords(iso) {
  const d = new Date(iso);
  return isNaN(d) ? String(iso || '').slice(0, 19)
    : d.toLocaleString('en-GB', {day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'});
}

function showStateNote(data) {
  const note = document.getElementById('state-note');
  if (!note) return;
  const words = STATE_NOTES[data.status] || [`It stands at “${statusWords(data.status)}”.`,
                                             'This step has no page of its own yet — its history holds every record.'];
  // [the owner's answer to the UI directions of 2026-09-25: a design turned down and drawn again since shows that
  // drawing here — the board sends him to "look again"]
  const po = data.packaging_output || {};
  const picture = window.DESIGN_LOOK_AGAIN_PICTURE || po.design_preview_url;
  const again = data.status === 'container_stage_visually_rejected' && window.DESIGN_LOOK_AGAIN && picture
    ? `<p>It was drawn again after that — here is the drawing now, to look at.</p>
       <img src="${escapeHtml(picture)}" alt="The drawing made again" class="dieline-img">` : '';
  note.innerHTML = `<h3>${escapeHtml(statusWords(data.status))}</h3><p>${escapeHtml(words[0])} ${escapeHtml(words[1])}</p>${again}
    <p><a href="/dashboard/history/tasks/${data.id}/">Open its history</a>${data.status === 'design_intent_confirmed'
      || data.status === 'awaiting_design_intent_confirmation'
      ? ` · <a href="/dashboard/palette/intent-confirmation/${data.id}/">Its design intent</a>` : ''}</p>
    ${designHistoryHtml(data.images)}`;
  note.hidden = false;
  note.style.display = 'block';          // hideAllStates hides it by display, as it does every other panel
  showResume(data);
}

//: the states a design can stop in with work half done — each resumes from its own step (TaskRetryView.RETRYABLE)
const RESUMABLE = {
  gate_1_approved: ["Its concept was chosen and the step after it has not finished.",
                    "Resuming runs that step again — a paid step."],
  generating_dieline: ["Its design is being laid out and has not finished.",
                       "Resuming takes it back to the size step to confirm again — it spends nothing."],
  gate_2_approved: ["It is approved and its files are being prepared.",
                    "Resuming prepares them again — it spends nothing."],
  awaiting_gate1_generation_configuration: ["Its concepts are held before any drawing.",
                                            "Resuming releases them when everything they need exists — a paid step."],
};

// §BH55 Phase 3 (survey row 6.22): a design stuck in a working state had no way on from its own page — only History's
// own retry, and only for a container. The control says what resuming does and whether it spends, before the click.
function showResume(data) {
  const words = RESUMABLE[data.status];
  // [his second test blocker on design 123, 2026-10-09] offered only once the design has stopped moving — 14 s into its
  // step, Garden Wrap was offered it, and the resume ran the step again beside the one still working. [His goal of
  // 2026-10-13, (3)] ONLY when the server says it has truly stopped: a payload that does not say (the live feed's, a
  // held design's) offers nothing — it showed whenever it was not told "false"
  const old = document.getElementById('resume-note');
  if (data.stalled !== true) { if (old) old.remove(); return; }
  const host = document.getElementById(WORKING_STATUSES.includes(data.status) ? 'feed-state' : 'state-note');
  if (!words || !host) return;
  if (old) old.remove();
  const note = document.createElement('div');
  note.id = 'resume-note';
  note.className = 'concept-note';
  note.innerHTML = `<p><strong>Not moving?</strong> ${escapeHtml(words[0])} ${escapeHtml(words[1])}</p>
    <button class="btn-download" onclick="resumeTask(${data.id})">Resume this design</button>
    ${(data.status === 'gate_1_approved' || data.status === 'awaiting_gate1_generation_configuration')
      ? spendNoteHtml(data, 'retry') : ''}`;
  host.appendChild(note);
}

async function resumeTask(taskId) {
  if (!(await askInPage('Resume this design from where it stopped?', {yes: 'Resume it'}))) return;
  const res = await postAction(`/api/tasks/${taskId}/retry/`, {});
  if (res) showToast('Resumed — it goes on from where it stopped.', 'info');
  loadTask(taskId);
}

// === ACTIVITY FEED ===
function showFeed(logs, total) {
  document.getElementById('feed-state').style.display = 'block';
  const feed = document.getElementById('activity-feed');
  // §BH54(k) 1: the payload carries the newest twenty rows; say so when more exist, and where they all are
  total = total || window._lastLogsTotal || 0;                     // the failed and rejected states pass no total
  let more = document.getElementById('feed-more');
  if (total && total > logs.length) {
    if (!more) {
      more = document.createElement('div');
      more.id = 'feed-more';
      more.className = 'spend-note';
      feed.parentNode.insertBefore(more, feed);
    }
    more.textContent = `Showing the newest ${logs.length} of ${total} steps — every one is in History, on this design's page there.`;
  } else if (more) { more.remove(); }

  // [the owner's answer to the UI directions of 2026-09-25: one visual system — each worker's colour is a class in the
  // brand's own palette (static/css/bbrose.css .log-entry.by-*); it was an inline style naming colours C's look never
  // defined, so none showed]
  const agentClass = {'ARIA': 'by-aria', 'CreativeDirector': 'by-director', 'PromptEngineer': 'by-prompts',
                      'ImageProducer': 'by-images', 'QAReviewer': 'by-review'};

  // §BH54(k) 1: the payload arrives NEWEST first; appended in that order, the first row set `lastLogId` and every
  // older row of the same refresh was dropped — a run that logged twice in a second showed once. Oldest first.
  logs.slice().sort((a, b) => a.id - b.id).forEach(log => {
    if (log.id <= lastLogId) return;
    lastLogId = log.id;
    const el = document.createElement('div');
    el.className = 'log-entry ' + (agentClass[log.agent_name] || 'by-other');
    // §BH55 Phase 3: who is working and what is being done, in words (apps/pipeline/feed_words.py) — it showed the
    // agent's name and its log line as written, unescaped, and under them the record's keys ("plan_hash: …"); the row as
    // written and what its record holds are the row's hover text now, and History keeps every row as it was written
    el.innerHTML = `<span class="log-agent">${escapeHtml(log.who || log.agent_name)}</span>
      <span class="log-action">${escapeHtml(log.said || log.action)}</span>
      <span class="log-time">${new Date(log.timestamp).toLocaleTimeString()}</span>`;
    el.title = [`${log.agent_name}: ${log.action}`, log.detail || ''].filter(Boolean).join(' — ');
    feed.appendChild(el);
    feed.scrollTop = feed.scrollHeight;
  });
}

// === DESIGN HISTORY (2026-07-04) ===
// Every generated design stays visible for the task's whole life — after
// Gate 1 approval the concepts used to vanish from the UI entirely, and the
// superseded-images history (Milestone 11.3) had no surface at all.
function designHistoryHtml(images, opts) {
  images = images || [];
  if (!images.length) return '';
  const o = opts || {};
  const cards = images.map(img => {
    const qa = (img.qa_notes_parsed || {}).score;
    // §BH55 Phase 3: in words — the badges read APPROVED, SUPERSEDED and "QA n/10"
    const badges = [
      img.is_approved ? '<span class="hist-badge hist-approved">chosen</span>' : '',
      img.superseded ? '<span class="hist-badge hist-superseded">replaced</span>' : '',
      qa != null ? `<span class="hist-badge">quality ${qa}/10</span>` : '',
    ].join('');
    const visual = img.image_url_display
      ? `<img src="${img.image_url_display}" alt="${escapeHtml(img.direction_name)}" loading="lazy"
             onclick="window.open('${img.image_url_display}', '_blank')" title="Open full size">`
      : '<div class="hist-missing">image unavailable</div>';
    return `<div class="history-card${img.superseded ? ' is-superseded' : ''}">
      ${visual}
      <p class="hist-name">${escapeHtml(img.direction_name)}</p>
      <div class="hist-badges">${badges}</div>
    </div>`;
  }).join('');
  const label = o.label || `Every concept drawn — ${images.length}`;
  return `<details class="design-history"${o.open ? ' open' : ''}>
    <summary>${escapeHtml(label)}</summary>
    <div class="history-grid">${cards}</div>
  </details>`;
}

// Gate History (Milestone 11.1) is now owned by the Review Board's Approval
// section (RB2) — the single source of approval history. The legacy inline
// renderer was removed to avoid duplicate information.


// [His goal of 2026-10-06, item 2: "While it works, it shows clearly what step it's on and roughly how long."] Above the
// working feed: the step, in words, its rough time as this site measured it (apps/pipeline/step_times.py — the median of
// that step's latest runs here, or "not measured yet"), and how long it has run; a step running well past its time says
// so. The clock ticks between refreshes without a request.
function _stepClock(seconds) {
  const s = Math.max(0, Math.round(seconds));
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, '0')} s`;
}

function _stepRough(seconds) {
  if (seconds < 50) return 'under a minute';
  const m = Math.round(seconds / 60);
  return m <= 1 ? 'about a minute' : `about ${m} minutes`;
}

function showWorkingStep(step) {
  const feed = document.getElementById('feed-state');
  if (!feed) return;
  let box = document.getElementById('working-step');
  if (!step) {
    if (box) box.remove();
    if (window._stepClockTimer) { clearInterval(window._stepClockTimer); window._stepClockTimer = null; }
    return;
  }
  if (!box) {
    box = document.createElement('div');
    box.id = 'working-step';
    box.className = 'working-step';
    box.setAttribute('role', 'status');
    feed.insertBefore(box, feed.firstChild);
  }
  const usual = step.typical_seconds != null
    ? `Usually ${_stepRough(step.typical_seconds)} — measured on this site's last ${step.measured_on} design${step.measured_on === 1 ? '' : 's'}.`
    : 'Its time is not measured yet on this site.';
  box.innerHTML = `<span class="ws-dot" aria-hidden="true"></span><div><b class="ws-now">Working on it: ${escapeHtml(step.words)}</b>
      <span class="ws-time">${escapeHtml(usual)} <span id="ws-elapsed"></span></span></div>`;
  const started = step.started_at ? Date.parse(step.started_at) : null;
  const tick = () => {
    const el = document.getElementById('ws-elapsed');
    if (!el || !started) return;
    const ran = (Date.now() - started) / 1000;
    const late = step.typical_seconds != null && ran > step.typical_seconds * 1.5 + 30;
    el.textContent = `Running for ${_stepClock(ran)}${late ? ' — longer than usual' : ''}.`;
  };
  if (window._stepClockTimer) clearInterval(window._stepClockTimer);
  tick();
  if (started) window._stepClockTimer = setInterval(tick, 1000);
}
