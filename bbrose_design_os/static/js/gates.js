// === GATE 1 GALLERY ===
function showGallery(images, taskId, data) {
  document.getElementById('gallery-state').style.display = 'block';
  const gallery = document.getElementById('image-gallery');
  gallery.innerHTML = '';

  renderMaterialReferencePanel(taskId);

  if (!images.length) {
    // §BH55 Phase 3: it said "No images generated yet. Check logs for errors." — a designer has no logs to check
    gallery.innerHTML = '<p class="empty-note">No concepts have been drawn yet.</p>';
    return;
  }

  // §BH55 Phase 3: the stage in a designer's words
  gallery.innerHTML = '<div class="concept-note">These are concepts: the mood and the direction. The logo, the '
    + 'exact type and the brand\'s colours are set later, when the design is laid out. Choose the '
    + '<em>direction</em> you want — this is not the print file.</div>';
  // [his test blocker on design 123, 2026-10-09, (2)] three shown though a check still found them too alike — said
  // beside them, in words, and he chooses
  ((data && data.gate_1_alike_words) || []).forEach(note => {
    gallery.innerHTML += `<div class="concept-note alike-note">${escapeHtml(note)}</div>`;
  });

  // 2A-6E-CORR-5 §8: CURRENT ACTIVE CONCEPTS vs HISTORICAL/REJECTED are
  // separated, and a failed regeneration attempt is stated explicitly so
  // historical images are never presented as its output.
  const regenJob = data && data.latest_regeneration_job;
  if (regenJob && regenJob.status === 'failed') {
    // §BH55 Phase 3: the same statement in words — it read "Regeneration failed before image generation … (job #N …)"
    gallery.innerHTML += `<div class="concept-note" style="border:1px solid #7a2c2c;">
      <strong>Drawing the concepts again with references stopped before any was drawn.</strong>
      No new concept was made (${escapeHtml(regenJob.error || 'its reason is in History')}).
      The concepts below are the earlier ones.</div>`;
  }
  // [the owner's finding on design 119, 2026-10-03: "NO SILENT FALLBACK ... STOP and tell me why, with options"] the
  // concept he chose could not be drawn from its map: said here, with each part, and what he can do
  const mapStop = data && data.gate_1_map_stop;
  if (mapStop) {
    const parts = (mapStop.parts || []).map(p => `<li>${escapeHtml(p.name)} — ${escapeHtml(p.why)}</li>`).join('');
    gallery.innerHTML += `<div class="concept-note" style="border:1px solid #7a2c2c;">
      <strong>"${escapeHtml(mapStop.direction_name)}" was not drawn: ${escapeHtml(mapStop.why)}.</strong>
      ${parts ? `<ul>${parts}</ul>` : ''}
      Nothing was drawn in its place. You can ${escapeHtml((mapStop.options || []).join(', or '))}.</div>`;
  }
  const activeImages = images.filter(i => i.selectable === true && !i.superseded);
  const diagnostic = document.createElement('details');
  diagnostic.className = 'concept-diagnostics';
  diagnostic.innerHTML = '<summary>Review history — unavailable for approval</summary>';
  const quality = data && data.concept_quality;
  if (quality) { gallery.innerHTML += `<p class="concept-note">${escapeHtml(quality.message)}</p>`; }
  const historicalImages = images.filter(i => i.selectable !== true || i.superseded);
  if (!activeImages.length && historicalImages.length) {
    gallery.innerHTML += '<h3 style="margin:12px 0 4px;">Earlier concepts'
      + ' <span class="concept-tag">for reference — not new</span></h3>';
  } else if (activeImages.length && historicalImages.length) {
    gallery.innerHTML += '<h3 style="margin:12px 0 4px;">The concepts to choose from</h3>';
  }

  images.forEach(img => {
    const qaData = img.qa_notes_parsed || {};
    // §BH55 Phase 3: a check that never ran is "not checked" — it read "QA ?/10 ✗ Failed"
    const checked = qaData.score !== undefined && qaData.score !== null && qaData.score !== '';
    const score = checked ? qaData.score : null;
    const scoreClass = !checked ? 'score-none' : score >= 7 ? 'score-good' : score >= 5 ? 'score-ok' : 'score-bad';
    const issues = (qaData.issues || []).join(', ') || 'None';
    const obs = qaData.observations ? `<p>${escapeHtml(qaData.observations)}</p>` : '';
    const palette = qaData.deterministic && qaData.deterministic.palette;
    const paletteLine = (palette && palette.coverage != null)
      ? `<p>Palette check: ${Math.round(palette.coverage * 100)}% on-brand`
        + ` (mean ΔE ${palette.mean_delta_e != null ? palette.mean_delta_e : '—'})</p>`
      : '';

    // No local copy (download failed / expired source) → retryable placeholder
    // instead of a broken remote URL (Milestone 8.6).
    const visual = img.image_url_display
      ? `<img src="${img.image_url_display}" alt="${escapeHtml(img.direction_name)}" loading="lazy">`
      : `<div class="img-unavailable" style="display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;min-height:220px;background:rgba(255,255,255,0.04);border:1px dashed var(--cream-dim,#888);">
           <p style="margin:0;opacity:.7;">image unavailable</p>
           <button class="btn-download" onclick="redownloadImage(${taskId}, ${img.id})">Retry download</button>
         </div>`;

    const card = document.createElement('div');
    card.className = 'image-card';
    card.innerHTML = `
      ${visual}
      <div class="card-info">
        <span class="concept-tag">concept</span>
        ${img.user_rejection_label ? `<span class="concept-tag" style="background:#7a2c2c;color:#fff;">${escapeHtml(img.user_rejection_label)}</span>` : ''}
        <h4>${escapeHtml(img.direction_name)}</h4>
        ${img.direction_sentence ? `<p class="concept-sentence">${escapeHtml(img.direction_sentence)}</p>` : ''}
        ${nearCopyHtml(img)}
        <details class="concept-details"><summary>Details</summary>
        <div class="qa-row">
          ${checked
            ? `<span class="qa-score ${scoreClass}">Quality ${score}/10</span>
               <span class="qa-passed">${img.selectable ? '✓ meets the quality bar' : 'Review required'}</span>`
            : '<span class="qa-score score-none">Quality not checked</span>'}
        </div>
        ${materialReferencesUsedHtml(img)}
        ${checked ? `<details><summary>What the check saw</summary>${obs}${paletteLine}<p>Issues: ${escapeHtml(issues)}</p></details>` : ''}
        <details class="prompt-edit"><summary>Prompt (edit it, then draw again)</summary>
          <textarea id="prompt-edit-${img.id}" rows="4">${escapeHtml(img.prompt_used || '')}</textarea>
          <button class="btn-download" onclick="savePrompt(${taskId}, ${img.id})">Save the prompt</button>
        </details>
        </details>
        ${redrawnNoteHtml(img)}
        ${img.selectable !== true || img.superseded
          ? '<p class="concept-note">' + escapeHtml((img.quality_review || {}).review_status === 'rejected' ? 'Designer review needed' : 'Review pending') + ' — approval unavailable.</p>'
          : cannotDraw(img)
          ? cannotDrawHtml(taskId, img)
          : `<button class="btn-approve" onclick="approveGate1(${taskId}, ${img.id})">Use this concept</button>`}
      </div>
    `;
    (activeImages.includes(img) ? gallery : diagnostic).appendChild(card);
  });
  if (historicalImages.length) { gallery.appendChild(diagnostic); }

  // Earlier passes (superseded by reruns/revisions) — reviewable, not selectable.
  const superseded = ((data && data.images) || []).filter(i => i.superseded);
  // §BH55 Phase 3: counted from the server's own limit (MAX_REVISION_PASSES) — the page counted two; the server
  // allows one, and refused the second click
  const rerunCap = (data && data.image_rerun_cap !== undefined && data.image_rerun_cap !== null) ? data.image_rerun_cap : null;
  const allowance = data.repair_allowance || {};
  const rerunsLeft = allowance.remaining ?? ((rerunCap !== null) ? Math.max(0, rerunCap - (data.image_rerun_count || 0)) : null);
  const canResume = allowance.can_resume === true;
  const canRevise = allowance.can_revise ?? (rerunsLeft !== 0);
  document.getElementById('gate1-actions').innerHTML = `
    <p class="spend-note">${conceptCostWords(data)}${cartonMapWords(data)}</p>
    <div class="reject-section">
      <button class="btn-download" onclick="rerunImages(${taskId})"
        ${!canResume && !canRevise ? 'disabled title="Designer review needed"' : ''}>
        ${canResume ? 'Resume saved repair' : 'Draw these concepts again'}${!canResume && rerunsLeft != null ? ` (${rerunsLeft} left)` : ''}
      </button>
      ${spendNoteHtml(data, 'rerun')}
      <textarea id="reject-notes" placeholder="What should change? Say it in your own words…" rows="3"></textarea>
      <button class="btn-reject" onclick="rejectGate1(${taskId})" ${!canRevise ? 'disabled' : ''}>Ask for changes</button>
      ${allowance.reason ? `<p class="spend-note">${escapeHtml(allowance.reason)}</p>` : ''}
      ${askForChangesNote(data)}
    </div>
    ${designHistoryHtml(superseded, {label: `Earlier sets — ${superseded.length} replaced`})}
  `;
}

// [the owner's finding on design 119, 2026-10-03] a concept whose own picture its map cannot draw: choosing it again
// would stop again, so its card says so in place of the button (a stop for a missing key or a spending cap does not)
function cannotDraw(img) {
  const prov = img.reference_provenance || {};
  const stop = prov['design_map_stop/1.0'];
  const check = prov['concept_readable/1.0'];
  return !!((stop && stop.concept) || (check && check.state === 'NOT_DRAWABLE'));
}

// [His test blocker on design 122, 2026-10-07, items 4 and 6: "never a dead end: offer me in words what I can do (redraw
// for $X, draw this concept from the template, or pick another), each with a button"; "The refusal label 'ITS MAP CANNOT
// DRAW IT' is shouting engine words; say it plainly."] why, in plain words, and his three offers, each its own button
function cannotDrawHtml(taskId, img) {
  const prov = img.reference_provenance || {};
  const check = prov['concept_readable/1.0'] || {};
  const stop = prov['design_map_stop/1.0'] || {};
  const why = check.why || stop.why || 'its picture could not be read';
  const offers = check.offers || [
    {key: 'redraw', words: 'Redraw it on a plain contrasting backdrop', cost_usd: null},
    {key: 'template', words: "Draw it from its form's standard layout, with your brief's words — not this picture's design"},
    {key: 'another', words: 'Choose another concept'}];
  const button = (o) => {
    const cost = o.key === 'redraw' && o.cost_usd ? ` — about $${escapeHtml(o.cost_usd)}` : '';
    const act = o.key === 'redraw' ? `redrawConcept(${taskId}, ${img.id})`
      : o.key === 'template' ? `approveFromTemplate(${taskId}, ${img.id})`
      : `chooseAnotherConcept(${img.id})`;
    return `<button class="btn-download cannot-draw-offer" style="border-radius:14px;" data-offer="${escapeHtml(o.key)}" onclick="${act}">${escapeHtml(o.words)}${cost}</button>`;
  };
  return `<div class="cannot-draw"><p class="cannot-draw-why">We can't draw this concept yet: ${escapeHtml(why)}.</p>
      <div class="cannot-draw-offers">${offers.map(button).join('')}</div></div>`;
}

function redrawnNoteHtml(img) {
  const check = (img.reference_provenance || {})['concept_readable/1.0'] || {};
  if (!check.redrawn || !check.redraw) return '';
  const without = (check.redraw.left_out || []).length ? ` without ${escapeHtml(check.redraw.left_out.join(', '))},` : '';
  return `<p class="concept-redrawn">Redrawn${without} on a plain ${escapeHtml(check.redraw.backdrop.words)} backdrop so it can be drawn — $${escapeHtml(check.redraw.cost_usd)}.</p>`;
}

async function redrawConcept(taskId, imageId) {
  const res = await postAction(`/api/tasks/${taskId}/concept_redraw/`, {image_id: imageId});
  if (res) loadTask(taskId);
}

async function approveFromTemplate(taskId, imageId) {
  const res = await postAction(`/api/tasks/${taskId}/gate1_approve/`, {image_id: imageId, from_template: true});
  if (res) loadTask(taskId);
}

function chooseAnotherConcept(imageId) {
  const other = Array.from(document.querySelectorAll('#image-gallery .btn-approve'))[0];
  if (other) { other.scrollIntoView({behavior: 'smooth', block: 'center'}); other.focus(); }
  else showToast('No other concept can be drawn yet — redraw one, or draw it from the standard layout.', 'info');
}

async function savePrompt(taskId, imageId) {
  const prompt = document.getElementById(`prompt-edit-${imageId}`).value.trim();
  if (!prompt) { sayInPage('Write a prompt first.'); return; }
  const res = await postAction(`/api/images/${imageId}/update_prompt/`, {prompt});
  if (res) showToast('Prompt saved — use "Draw these concepts again" to see it drawn.', 'info');
  else sayInPage('The prompt was not saved — saving one needs a reviewer\'s role.');
}

// §BH55 Phase 3: what using a concept spends — nothing where the product's record carries its size, a measured
// estimate where it does not (dieline_agent reads all three or asks the model for them)
function conceptCostWords(data) {
  // [his go of 2026-10-02: the map path runs on its own for every new design] a container design reads its chosen
  // concept's design map once — said before the click, measured on the ledger
  if (data.design_target === 'product_container' || data.design_target === 'complete_product') {
    // [his test blocker on design 122, 2026-10-07, item 2] each concept was read when it was checked, before it was shown:
    // using one reads nothing again
    const checked = (data.images || []).some(i => ((i.reference_provenance || {})['concept_readable/1.0'] || {}).state === 'DRAWABLE');
    if (checked) return 'Using a concept spends nothing more — each one was read when it was checked, before you saw it.';
    const map = ((data.spend_estimates || {}).steps || {}).design_map_read || {};
    return map.rows
      ? `Using a concept reads its design map once — about $${Number(map.usd).toFixed(2)}, measured — so the drawing is made from the picture.`
      : 'Using a concept reads its design map once — a paid step this system has not measured yet — so the drawing is made from the picture.';
  }
  const step = ((data.spend_estimates || {}).steps || {}).size_estimate || {};
  if (data.size_from_record) return "Using a concept spends nothing — the carton is sized from the product's record.";
  if (!step.rows) return 'Using a concept: the product has no size on record, so the carton\'s size is estimated from '
    + 'the concept for you to confirm — a paid step this system has not measured yet.';
  return `Using a concept spends about $${Number(step.usd).toFixed(2)} — the product has no size on record, so the `
    + 'carton\'s size is estimated from the concept for you to confirm, measured.';
}

// [his go of 2026-10-02: the map path for a carton] a carton design reads its chosen concept's design map once too —
// said before the click, measured on the ledger (the read is the container's own operation)
function cartonMapWords(data) {
  if (data.design_target !== 'packaging' && data.design_target !== 'gift_set') return '';
  const map = ((data.spend_estimates || {}).steps || {}).design_map_read || {};
  return map.rows
    ? ` It also reads the concept's design map once — about $${Number(map.usd).toFixed(2)}, measured — so the front is drawn from the picture.`
    : " It also reads the concept's design map once — a paid step this system has not measured yet — so the front is drawn from the picture.";
}

// Requested changes revise the current concepts within the same shared allowance.
function askForChangesNote(data) {
  return '<span class="spend-note">Asking for changes applies your notes to the current concepts, then reviews the new images. Paid calls reserve budget first; all revisions share a two-round allowance.</span>';
}

// §BH54(k) 1: what a click costs, said before the click — measured on the ledger, never a quote.
function spendNoteHtml(data, kind) {
  const est = (data && data.spend_estimates) || null;
  if (!est) return '';
  if (kind === 'rerun' && est.rerun_images) {
    return `<span class="spend-note">spends ≈ $${Number(est.rerun_images.usd).toFixed(2)} — `
      + `${est.rerun_images.images} images at $${Number(est.image_usd).toFixed(2)} + a quality check each, measured</span>`;
  }
  // §BH55 Phase 3: this design's own kind, in words — it read "re-queues the paid pipeline — measured a task:" and each
  // kind by its key ("product_container"); the other kinds are said only when this one has spent nothing yet
  const own = (est.start_design || []).filter(s => s.target === window._lastDesignTarget);
  const rows = (own.length ? own : (est.start_design || [])).map(s =>
    `${targetWords(s.target)} $${Number(s.min_usd).toFixed(2)}–$${Number(s.max_usd).toFixed(2)}`);
  return rows.length ? `<span class="spend-note">starts its paid steps again — past designs spent ${rows.join(' · ')}, measured</span>` : '';
}
window._lastSpendEstimates = null;
window._lastDesignTarget = null;

function targetWords(key) {
  const words = String(key || 'other').replace(/_/g, ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

async function rerunImages(taskId) {
  const est = window._lastSpendEstimates && window._lastSpendEstimates.rerun_images;
  const cost = est ? ` This spends about $${Number(est.usd).toFixed(2)} (measured).` : '';
  if (!(await askInPage('Draw these concepts again from their prompts? The direction you chose is kept.' + cost,
                        {yes: 'Draw them again'}))) return;
  const res = await postAction(`/api/tasks/${taskId}/rerun_images/`, {});
  if (res === null) { sayInPage('Drawing again was refused — no draws are left, or your account may not do this.'); return; }
  loadTask(taskId);
}

async function redownloadImage(taskId, imageId) {
  const res = await postAction(`/api/images/${imageId}/redownload/`, {});
  if (!res) {
    sayInPage('The picture could not be fetched again — its link may have expired. Ask for changes to have the concepts drawn again.');
  }
  loadTask(taskId);
}

async function approveGate1(taskId, imageId) {
  if (!(await askInPage('Use this concept? The design is made from it next.', {yes: 'Use this concept'}))) return;      // §BH55 Phase 3: it said "packaging" for every kind
  await postAction(`/api/tasks/${taskId}/gate1_approve/`, {image_id: imageId});
  loadTask(taskId);
}

async function rejectGate1(taskId) {
  const notes = document.getElementById('reject-notes').value.trim();
  if (!notes) { sayInPage('Say what should change first.'); return; }
  await postAction(`/api/tasks/${taskId}/gate1_reject/`, {notes});
  loadTask(taskId);
}

// === DIMENSION GATE (dieline backend) ===
// [his second goal of 2026-10-06, item 2] a carton's sizes are its inside — what the product needs; each crease adds
// the board's thickness (apps/dielines/docs/TRADE_RULES.md §2)
const DIM_FIELDS = [
  ['width_mm', 'Width inside (mm)'], ['depth_mm', 'Depth inside (mm)'], ['height_mm', 'Height inside (mm)'],
  ['bleed_mm', 'Bleed (mm)'], ['safe_margin_mm', 'Safe margin (mm)'], ['glue_tab_mm', 'Glue tab (mm)'],
  ['board_thickness_mm', 'Board thickness (mm)'],
];
// [His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (2): "A palette or compact lies flat: its box's front is the
// lid's face (landscape)."] a box lying flat names its sides as it is seen — its front's width (the die's height), its
// front's height (the die's width), its depth — in that order, so "192 × 122 × 14" reads as he means it
const DIM_FIELDS_FLAT = [
  ['height_mm', 'Front width inside (mm) — the lid\'s long side'], ['width_mm', 'Front height inside (mm)'],
  ['depth_mm', 'Depth inside (mm) — its thickness'],
  ['bleed_mm', 'Bleed (mm)'], ['safe_margin_mm', 'Safe margin (mm)'], ['glue_tab_mm', 'Glue tab (mm)'],
  ['board_thickness_mm', 'Board thickness (mm)'],
];

// Info-panel fields (2026-07-06): printed on the carton's back face.
// Prefilled from the Product/Brand records; editable per task right here.
const INFO_FIELDS = [
  ['product_name', 'Product name (panel title)', 'input'],
  ['description', 'Description', 'textarea'],
  ['ingredients', 'Ingredients (INCI)', 'textarea'],
  ['how_to_use', 'How to use', 'textarea'],
  ['warnings', 'Warnings', 'textarea'],
  ['net_weight', 'Net weight (e.g. 30 ml e 1 fl. oz.)', 'input'],
  ['item_no', 'Item no', 'input'],
  ['barcode_ean', 'Barcode EAN (12-13 digits)', 'input'],
  ['qr_url', 'QR link', 'input'],
  ['regulatory_text', 'Supplier / importer block', 'textarea'],
];

function infoPanelFormHtml(panelInfo) {
  const info = panelInfo || {};
  const rows = INFO_FIELDS.map(([key, label, kind]) => {
    const val = escapeHtml(info[key] || '');
    const field = kind === 'textarea'
      ? `<textarea id="info-${key}" rows="2">${val}</textarea>`
      : `<input type="text" id="info-${key}" value="${val}">`;
    return `<label class="dim-row info-row"><span class="dim-label">${label}</span>${field}</label>`;
  }).join('');
  const filled = INFO_FIELDS.filter(([k]) => (info[k] || '').trim()).length;
  return `<details class="info-panel-form" ${filled ? 'open' : ''}>
    <summary>Printed information — back panel (descriptions, barcode, QR) · ${filled}/${INFO_FIELDS.length} filled</summary>
    <p class="dim-sub">Filled in from the product's record; changes apply to this design's files.</p>
    <div class="dim-form info-form">${rows}</div>
  </details>`;
}

function collectInfoPanel() {
  const out = {};
  for (const [key] of INFO_FIELDS) {
    const el = document.getElementById('info-' + key);
    if (el) out[key] = el.value;
  }
  return out;
}

// §BH55 Phase 3: what making the design spends — [E3, the clean-up of 2026-10-04] the label copy's translation, where
// it is switched on, and nothing else: no picture is made or edited for a carton (it said "one or two edits")
function makeTheDesignCostWords() {
  const step = ((window._lastSpendEstimates || {}).steps || {}).make_the_design;
  if (!step) return '';
  if (!step.translated) {
    return '<p class="spend-note">Making the design spends nothing — no picture is made or edited for it.</p>';
  }
  if (!step.usd) return '';
  return `<p class="spend-note">Making the design spends about $${Number(step.usd).toFixed(2)} — the label copy `
    + 'is translated, measured; no picture is made or edited for it.</p>';
}

// [His test blocker on design 122 at reconstruction, 2026-10-08, item 3: "The stop reason must be shown in plain words on
// the page, never only codes in a fold."] each reason a drawing stopped, in words and in view (the server's
// drawing_stop_reasons) — the record's own text stays in its fold beside
function stopReasonsHtml(reasons) {
  const list = (reasons || []).filter(Boolean);
  if (!list.length) return '';
  const said = r => r.charAt(0).toUpperCase() + r.slice(1) + (/[.!?]$/.test(r) ? '' : '.');
  return `<p class="stop-reasons-head">It stopped because:</p>
    <ul class="stop-reasons">${list.map(r => `<li>${escapeHtml(said(r))}</li>`).join('')}</ul>`;
}

function showDimensionGate(packagingOutput, taskId, images, panelInfo, stopWords) {
  _sizeTaskId = taskId;     // [his test findings on design 123, (6)] the sizes typed here are flagged for this design
  document.getElementById('dimensions-state').style.display = 'block';
  const view = document.getElementById('dimensions-view');

  if (!packagingOutput) {
    view.innerHTML = '<p class="loading-note">Working out the carton\'s size…</p>';
    startPolling(taskId);
    return;
  }

  const spec = packagingOutput.spec_sheet || {};
  const est = spec.estimated_dimensions || {};
  const scenario = spec.scenario || est.scenario || '?';
  // 2A-6E-CORR-6 §4: values the user already typed survive a structural
  // refusal — they take precedence over the (often empty) estimates.
  // [his test findings on design 123, 2026-10-09, (7)] his confirmed size shown again where the step reopens on it
  const entered = spec.entered_dimensions || (spec.size_confirmed || {}).dims || {};
  // §BH55 Phase 3: where the sizes came from, in words — the page said "Scenario A — read from product record"
  // whatever the source, a gift set's fit and a project's own bottle included
  // §BH70(1), item 20: the product designed for it — any product, not "the bottle" — and said when it stands on its edge
  const SOURCE_WORDS = {db: "the product's record", container: 'the product designed for it in this project',
                        'container on its edge': 'the product designed for it in this project, standing on its edge',
                        'container lying flat': 'the product designed for it in this project, the box lying flat, its '
                          + 'front the lid\'s face',
                        'gift set': "the set's own fit, the pieces on their insert", image: 'an estimate from the concept',
                        text: 'the brief', pdf: 'the PDF supplied', manual: 'what was entered'};
  const SOURCE_HINTS = {db: 'from the record', container: 'from the product', 'container on its edge': 'from the product, on its edge',
                        'container lying flat': 'from the product, lying flat',
                        'gift set': 'from the set',
                        image: 'estimated from the concept', text: 'from the brief', pdf: 'from the PDF', manual: 'entered'};
  const sources = [...new Set(['width_mm', 'depth_mm', 'height_mm'].map(k => (est[k] || {}).source).filter(Boolean))];
  const fromWords = sources.map(s => SOURCE_WORDS[s] || s).join(' and ');

  const REQUIRED_DIMS = ['width_mm', 'depth_mm', 'height_mm'];
  const rows = (est.orientation === 'flat' ? DIM_FIELDS_FLAT : DIM_FIELDS).map(([key, label]) => {
    const f = est[key] || {};
    const estVal = (f.value !== null && f.value !== undefined) ? f.value : '';
    const val = (entered[key] !== null && entered[key] !== undefined) ? entered[key] : estVal;
    const conf = f.confidence != null ? Math.round(f.confidence * 100) : null;
    const required = REQUIRED_DIMS.includes(key);
    const hint = (entered[key] !== undefined)
      ? '<span class="dim-hint">your entered value (retained)</span>'
      : (f.blocked
        ? '<span class="dim-hint dim-blocked">needs manual entry</span>'
        : (conf != null ? `<span class="dim-hint">${escapeHtml(SOURCE_HINTS[f.source] || ('from ' + (f.source || '')))}${conf < 95 ? ` · ${conf}% sure` : ''}</span>` : ''));
    return `<label class="dim-row">
      <span class="dim-label">${label} ${hint}</span>
      <input type="number" step="0.1" id="dim-${key}" value="${val}"
        ${required ? 'data-required="1"' : ''} ${f.blocked ? 'data-blocked="1"' : ''}
        ${f.blocked ? 'placeholder="enter value"' : ''} oninput="validateDims();scheduleQualifyDims()">
    </label>`;
  }).join('');
  const compChecked = (entered.thickness_compensation !== undefined)
    ? entered.thickness_compensation : true;

  // [the owner's goal of 2026-09-25, (d): what happened and what to do, in words; the record's own text folded]
  const err = spec.generation_error ? `<p class="dim-error">⚠ The last try at drawing it did not finish. Check the
      sizes below and try again.</p>
    ${stopReasonsHtml(stopWords)}
    <details class="tech"><summary>What the record says</summary><p><code>${escapeHtml(spec.generation_error)}</code></p></details>` : '';
  const rev = spec.gate_2_revision_note
    ? `<p class="dim-revision">↩ Changes asked for at the design's review: ${escapeHtml(spec.gate_2_revision_note)}</p>`
    : '';
  const structureSection = cartonStructureHtml(spec);
  const panelInfoShown = (spec.entered_panel_info
    && Object.keys(spec.entered_panel_info).length)
    ? spec.entered_panel_info : panelInfo;

  view.innerHTML = `
    <h3>Confirm the carton's size</h3>
    <p class="dim-sub">${fromWords ? `These sizes come from ${escapeHtml(fromWords)}. ` : ''}Check them, change any that
      are wrong${structureSection.hasSelector ? ", choose the carton's structure, then show it" : ', then make the design'}.</p>
    ${rev}
    <div class="dim-form">${rows}</div>
    <label class="dim-row" style="display:flex;align-items:center;gap:8px;margin-top:6px;font-size:12px;">
      <input type="checkbox" id="dim-thickness_compensation" ${compChecked ? 'checked' : ''}>
      Board-thickness compensation (recommended for real stock — panels grow so the carton closes square)
    </label>
    <div id="dim-size-flags"></div>
    ${structureSection.html}
    <div id="dim-qualification"></div>
    ${err}
    ${infoPanelFormHtml(panelInfoShown)}
    ${insideChoiceHtml(spec.confirmed_dimensions)}
    ${backInfoChoiceHtml(spec.confirmed_dimensions)}
    <div id="dim-msg" class="dim-msg"></div>
    ${makeTheDesignCostWords()}
    <div class="gate2-actions">
      <button id="dim-generate-btn" class="btn-approve" onclick="submitDimensions(${taskId})">
        ${structureSection.hasSelector ? "Show the carton's structure" : 'Make the design at this size'}</button>
      <button class="btn-reject" onclick="loadTask(${taskId})">Cancel</button>
    </div>
    ${designHistoryHtml(images)}
  `;

  // Gate the Generate button until every required + low-confidence (blocked)
  // field has a value, so we never submit a dieline that the backend will
  // reject for an out-of-range / missing dimension.
  document.querySelectorAll('input[name="struct-template"]').forEach(
    r => r.addEventListener('change', scheduleQualifyDims));
  validateDims();
  scheduleQualifyDims();
}

// 2A-9E §1/§3: the CARTON STRUCTURE selector. Candidates come from the
// server's new-selection chooser: the corrected 1.2 is RECOMMENDED, the
// legacy 1.1 is an advanced-only option with its known W-derived closure
// limitation spelled out, and neither is auto-selected. Customer-specific
// presets (Skynte) are shown only when the product matches.
// [the owner's goal of 2026-09-25, (d) and (c): the chooser says each version in words, in the one look — it was
// drawn with the old dark page's inline borders and greens; every input, name and handler is as it was]
function structCodeWords(text) {
  return String(text == null ? '' : text)
    .replace(/\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b/g, m => m.toLowerCase().replace(/_/g, ' '))
    .replace(/\b[a-z]+(?:_[a-z0-9]+)+\b/g, m => m.replace(/_/g, ' '));
}

function structCard(c, recommended) {
  const phys = c.physical_validation_required
    ? ' · <strong>a printed sample must still be tested</strong>' : '';
  return `
    <label class="struct-choice${recommended ? ' recommended' : ''}">
      <input type="radio" name="struct-template" value="${escapeHtml(c.key)}"
             data-template-id="${escapeHtml(c.template_id)}" data-version="${escapeHtml(c.version)}"
             onchange="validateDims();scheduleQualifyDims()">
      <span>
        <strong>${escapeHtml(c.label || c.template_label || structCodeWords(c.template_id))} — version ${escapeHtml(c.version)}</strong>
        ${recommended ? '<span class="tag done">Recommended — corrected</span>'
                      : '<span class="tag line">An earlier version — not for new work</span>'}<br>
        Closure: ${escapeHtml(structCodeWords(c.closure_type) || '—')} ·
        Panels: ${escapeHtml(structCodeWords(c.panel_sequence_label || (c.panel_order || []).join(' | ')))}<br>
        ${recommended
          ? "Its closure follows the carton's depth, with a 16 mm lip — it fits a wider range of sizes, and is technically qualified"
          : "Its tuck follows the carton's width — it fits a narrow range of sizes, kept for the designs made with it"}${phys}
      </span>
    </label>`;
}

function cartonStructureHtml(spec) {
  const selection = spec.structural_selection || {};
  const productText = String(spec.product_name || '').toLowerCase();
  const matchPreset = c => {
    if (!c.preset) return true;
    const marker = String(c.template_id).split('_')[0];
    return productText.includes(marker) || productText.includes('foundation');
  };
  const all = (selection.candidates || []).filter(matchPreset);
  const recommended = all.filter(c =>
    c.new_selection_class === 'RECOMMENDED_CORRECTED_VERSION'
    || c.new_selection_class === 'PRODUCTION_CURRENT'
    || (!c.new_selection_class && c.production_ready && !c.ineligibility_code));
  const legacy = all.filter(c =>
    c.new_selection_class === 'LEGACY_REPRODUCTION_ONLY');
  if (!recommended.length && !legacy.length) return {html: '', hasSelector: false};

  const legacyBlock = legacy.length ? `
    <details class="tech struct-legacy">
      <summary>Earlier versions — kept for the designs made with them</summary>
      <p class="small">They remake earlier designs and carry a known limit: their tuck grew with the carton's width,
        so they fit only a narrow range of sizes. Choose one only to remake an earlier design — never for new work.</p>
      ${legacy.map(c => structCard(c, false)).join('')}
    </details>` : '';

  return {hasSelector: true, html: `
    <div class="struct-chooser">
      <h4>The carton's structure — choose a version</h4>
      <p class="small">Choose the structure and its version yourself — neither is chosen for you. The corrected
        version is recommended: it is technically qualified, but a printed sample must still be tested before
        production, and its review waits until one fits. You will see its panels, its flaps and how it folds, and
        confirm it, before any artwork is drawn.</p>
      ${recommended.map(c => structCard(c,
          c.new_selection_class === 'RECOMMENDED_CORRECTED_VERSION')).join('')}
      ${legacyBlock}
    </div>`};
}

function selectedStructureTemplate() {
  const radio = document.querySelector('input[name="struct-template"]:checked');
  if (!radio) return null;
  return {template: radio.dataset.templateId, version: radio.dataset.version};
}

function validateDims() {
  const btn = document.getElementById('dim-generate-btn');
  if (!btn) return;
  const inputs = document.querySelectorAll(
    '#dimensions-view input[data-required], #dimensions-view input[data-blocked]'
  );
  let ok = true;
  inputs.forEach(i => {
    if (i.value === '' || isNaN(parseFloat(i.value)) || parseFloat(i.value) <= 0) ok = false;
  });
  const selectorPresent = !!document.querySelector('input[name="struct-template"]');
  if (selectorPresent && !selectedStructureTemplate()) ok = false;
  // 2A-9B §8: a parametrically qualified archetype blocks the preview on an
  // unsupported dimension combination — with the exact reason shown; the
  // user's values are never clamped or altered.
  let reason = 'Enter all required dimensions and select a carton structure to continue';
  // [his test findings on design 123, 2026-10-09, (6): "Flag impossible sizes at the size step"] a size the carton
  // cannot be made at for its product is never drawn
  if (ok && _lastSizeFlags.some(f => f.level === 'impossible')) {
    ok = false;
    reason = 'A size here cannot be made for this product — see why above the structure';
  }
  const chosen = selectedStructureTemplate && selectedStructureTemplate();
  if (ok && chosen && _lastQualification
      && _lastQualification.qualification_available
      && _lastQualification.supported === false) {
    ok = false;
    reason = 'These measures are outside what this structure supports — see why below';
  }
  btn.disabled = !ok;
  btn.title = ok ? '' : reason;
}

// [his final goal, 2026-10-05, B1: "At the size step he chooses per design: as referenced (default), solid colour, or
// plain."] the carton's inside, chosen here; what it follows said in words on the design's page
function insideChoiceHtml(entered) {
  const chosen = (entered && entered.inside_print) || 'referenced';
  const opt = (value, words) => `<label class="choice-row"><input type="radio" name="inside-print" value="${value}"
      ${chosen === value ? 'checked' : ''}> ${words}</label>`;
  return `<fieldset class="print-choices">
      <legend>The inside of the carton</legend>
      ${opt('referenced', 'As referenced — your inside pictures and your brief\'s "Inside:" words; with neither, the concept\'s own motif, in its own colours')}
      ${opt('solid', "One solid colour — the design's deep tone")}
      ${opt('plain', 'Plain — nothing printed inside')}
    </fieldset>`;
}

// [his final goal, 2026-10-05, B3: "THE BACK INFO IS A STICKER, his choice at the size step."]
function backInfoChoiceHtml(entered) {
  const chosen = (entered && entered.back_info) || 'sticker';
  const opt = (value, words) => `<label class="choice-row"><input type="radio" name="back-info" value="${value}"
      ${chosen === value ? 'checked' : ''}> ${words}</label>`;
  return `<fieldset class="print-choices">
      <legend>The back's information</legend>
      ${opt('sticker', 'A sticker — a white rounded label on the ground of the carton, with a margin round it')}
      ${opt('printed', 'Printed directly on the panel')}
      ${opt('custom', 'A custom sticker — as your sticker picture or the "Sticker:" words in your brief show it; with neither, the sticker above')}
    </fieldset>`;
}

function insideWords(inside) {
  if (!inside) return '';
  if (inside.mode === 'solid') return "One solid colour, the design's deep tone — as you chose.";
  if (inside.mode === 'plain') return 'Plain, as you chose.';
  const kind = {stripes: 'stripes', dots: 'dots', waves: 'waves', checks: 'checks', chevrons: 'chevrons',
                motif: 'the motif repeated', grid: 'a grid', solid: 'one colour'}[inside.pattern] || inside.pattern;
  return `${kind[0].toUpperCase()}${kind.slice(1)}, drawn in vector in the design's own colours, following ${inside.source || 'the concept'}.`;
}

async function submitDimensions(taskId) {
  const dims = {};
  for (const [key] of DIM_FIELDS) {
    const v = document.getElementById('dim-' + key).value;
    if (v !== '') dims[key] = parseFloat(v);
  }
  const comp = document.getElementById('dim-thickness_compensation');
  if (comp) dims.thickness_compensation = comp.checked;
  const msg = document.getElementById('dim-msg');
  if (dims.width_mm == null || dims.depth_mm == null || dims.height_mm == null) {
    msg.textContent = 'Width, depth and height are required.';
    return;
  }
  // 2A-6E-CORR-6 §3: the chosen structural template rides with the
  // dimensions; without one the server refuses with
  // STRUCTURAL_TEMPLATE_CONFIRMATION_REQUIRED and retains the values.
  const chosen = selectedStructureTemplate();
  if (chosen) {
    dims.template = chosen.template;
    dims.template_version = chosen.version;
  } else if (document.querySelector('input[name="struct-template"]')) {
    msg.textContent = 'Select a carton structure template first.';
    return;
  }
  msg.textContent = 'Making the design…';
  const res = await fetch(`/api/tasks/${taskId}/confirm_dimensions/`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCsrf()},
    body: JSON.stringify({dimensions: dims, panel_info: collectInfoPanel(),
                          inside_print: (document.querySelector('input[name="inside-print"]:checked') || {}).value
                                        || 'referenced',
                          back_info: (document.querySelector('input[name="back-info"]:checked') || {}).value
                                     || 'sticker'}),
  });
  if (res.ok) {
    loadTask(taskId);
  } else {
    const data = await res.json().catch(() => ({}));
    let detail = data.error || 'The design was not made';
    if (Array.isArray(data.details)) detail += ': ' + data.details.map(d => d.msg || '').join('; ');
    // [his test findings on design 123, (6)] a refusal said in words where the record gives them — never its code
    if (data.words) detail = data.words.charAt(0).toUpperCase() + data.words.slice(1) + '.';
    msg.textContent = detail;
  }
}

// === GATE 2 ===
function showGate2(packagingOutput, taskId, gateDecisions, images, targetLabel, taskData) {
  // VQR-6: for Product Container the ONE readiness authority decides which
  // result actions may exist. The serializer already withholds artifact
  // URLs the result contract does not vouch for; this gates the approval
  // and handoff surfaces the same way. Packaging (readiness null) is
  // untouched.
  const g2r = taskData && taskData.container_gate2_readiness;
  document.getElementById('gate2-state').style.display = 'block';
  const view = document.getElementById('mockup-view');

  if (!packagingOutput) {
    view.innerHTML = '<p class="loading-note">The design is being made…</p>';
    startPolling(taskId);
    return;
  }

  const svgUrl = packagingOutput.dieline_svg_url;
  const aiUrl = packagingOutput.dieline_ai_url;
  const pdfUrl = packagingOutput.production_pdf_url;
  const designUrl = packagingOutput.design_preview_url;
  const designAiUrl = packagingOutput.design_preview_ai_url;
  const renderUrl = packagingOutput.pacdora_render_url;
  // Target-agnostic heading: packaging keeps "Design on Dieline"; other
  // targets (Product Container, …) show a neutral "Design Preview".
  const isPackaging = !targetLabel || targetLabel === 'Packaging';
  // [D-D11-9, the review of Day 11] a published master (a palette, a lipstick's wrap) is no carton on its dieline: its
  // hero takes the neutral heading whatever its target
  const onDieline = isPackaging && !isMasterPublication(packagingOutput);
  const heroTitle = onDieline ? 'The design, on its dieline' : 'The design';        // §BH55 Phase 3
  // §BH55 Phase 2: an artwork design's files are a presentation .ai and a print PDF (a page per piece)
  const isArtwork = ((packagingOutput.spec_sheet || {}).backend === 'artwork');

  let preview;
  if (designUrl || svgUrl) {
    // The design preview is the hero — a PNG snapshot of the editable .ai
    // (no user-facing SVG). For packaging the bare technical dieline stays
    // one toggle away; other targets have no dieline layer.
    // [his final goal, 2026-10-05, B1: "Two artboards, OUTSIDE and INSIDE."] the inside beside the outside, with what
    // it follows in words
    const inside = (packagingOutput.spec_sheet || {})['inside_print/1.0'] || null;
    const insideHtml = packagingOutput.design_inside_url
      ? `<h3>The inside</h3>
         <p class="small">${escapeHtml(insideWords(inside))}</p>
         <img src="${packagingOutput.design_inside_url}" alt="The inside of the carton" class="dieline-img">`
      : (inside && inside.mode === 'plain' ? '<p class="small">The inside is plain, as you chose.</p>' : '');
    const hero = designUrl
      ? `<div class="drawing-hero"><h3>${onDieline ? 'The outside, on its dieline' : heroTitle}</h3>
         <img src="${designUrl}" alt="${heroTitle}" class="dieline-img">
         ${insideHtml}</div>
         ${svgUrl ? `<details class="dieline-toggle"><summary>Show the dieline alone (cuts and folds)</summary>
           <object data="${svgUrl}" type="image/svg+xml" class="dieline-img"></object></details>` : ''}`
      : `<div class="drawing-hero"><h3>The design</h3>
         <object data="${svgUrl}" type="image/svg+xml" class="dieline-img"></object></div>`;
    preview = `${hero}
      ${(g2r && g2r.inspection_only)
        ? `<p class="inspection-only-banner" role="note">It has not passed its quality check — what it did not
             pass is said beside Approve</p>
           <p class="contract-warn">This is the drawing's editable file. It has not passed its quality check;
             approving it keeps what it did not pass with your approval.</p>` : ''}
      ${downloadHtml([
        packagingOutput.native_ai_url && {url: packagingOutput.native_ai_url,
          words: slotWords(packagingOutput, 'native_ai', 'The .ai — Illustrator, layered, every piece its own')},
        designAiUrl && {url: designAiUrl,
          words: slotWords(packagingOutput, 'design_preview_ai', isArtwork ? 'The presentation .ai' : 'The design .ai, one layer')},
        pdfUrl && {url: pdfUrl, words: isArtwork ? 'The print PDF, a page per piece' : 'The production PDF (CMYK)'},
        aiUrl && {url: aiUrl, words: 'The dieline .ai — cuts and folds only'},
        ...otherFiles(packagingOutput),
      ], isArtwork ? artworkPieceLinks(packagingOutput.spec_sheet) : '')}`;
  } else if (g2r && designAiUrl) {
    // VQR-6: the PNG preview is optional — its absence must not hide the
    // authoritative editable .ai action or claim the output is unavailable.
    preview = `<h3>${heroTitle}</h3>
      <p class="spec-note">No picture was saved for this drawing. The editable .ai below is the design
        itself.</p>
      ${downloadHtml([{url: designAiUrl, words: 'The design .ai, one layer'}])}`;
  } else if (renderUrl) {
    preview = `<h3>3D mock-up</h3><img src="${renderUrl}" alt="3D mock-up" class="mockup-img">`;
  } else {
    preview = `<p class="spec-note">The design's files are not ready yet. Its specification is saved.</p>`;
  }

  const labelStop = labelStopHtml(packagingOutput, taskId);   // [his final goal, C5] a stopped label's offers
  // [his goal of 2026-10-13, (1)] Approve stands unless his own acceptance or the drawing itself is missing: a check
  // the drawing has not passed — the visual-quality check's among them — is said beside it, never a reason it is hidden
  const approvable = !g2r || g2r.ready || g2r.reason_code === 'VISUAL_QUALITY_GATE_FAILED';
  view.innerHTML = `
    <div id="drawings" class="drawings" aria-label="The design's drawings"></div>
    ${preview}
    ${designDecisionHtml(taskData && taskData.design_acceptance)}
    ${/* [his last goal before the pitch, 2026-10-16, Step 1 (8): "Remove the leftover "Illustrator package"
         box/button; Download is the one way to get files."] no package box, no button: the Download above is the one
         way */ ''}
    <details class="spec-sheet">
      <summary>The design's technical record</summary>
      <pre>${JSON.stringify(packagingOutput.spec_sheet, null, 2)}</pre>
    </details>
    ${labelStop}
    ${labelWidenedHtml(packagingOutput)}
    ${foldCheckHtml(packagingOutput)}
    ${designersEyeHtml(packagingOutput.designers_eye, taskData && taskData.acceptance_warnings)}
    ${selfCheckHtml(packagingOutput.self_check, packagingOutput.designers_eye)}
    ${(approvable && g2r && g2r.reason_code === 'VISUAL_QUALITY_GATE_FAILED' && taskData
       && taskData.container_visual_quality_gate) ? vqGatePanelHtml(taskData.container_visual_quality_gate) : ''}
    ${approvable ? gate2ProblemsHtml(taskData) : ''}
    ${approvable ? acceptanceWarningsHtml(taskData && taskData.acceptance_warnings, taskId) : ''}
    ${skuFieldHtml(taskData, taskId)}
    ${approvable
      ? `<div class="gate2-actions">
      ${labelStop ? '' : `<button class="btn primary lg" onclick="approveGate2(${taskId}, ${packagingOutput.id}, ${approveCounts(taskData)}, ${keptCount(taskData)})">Approve</button>`}
      <button class="btn quiet" onclick="toggleGate2Reject()">Ask for changes</button>
      ${canDecideDesign(taskData && taskData.design_acceptance) ? `<p class="gate2-records small">Approving records your
        account, the time and the drawing's own fingerprint, checked every time it is read.</p>` : ''}
    </div>
    <div id="gate2-reject-box" class="reject-section" style="display:none; margin-top:14px;">
      <textarea id="gate2-reject-notes" rows="3"
        placeholder="${isArtwork ? 'What needs to change? — this goes back to the concepts.' : 'What needs to change? (e.g. the carton too tall, the glue tab too wide) — this goes back to the size.'}"></textarea>
      <button class="btn-reject" onclick="rejectGate2(${taskId})">${isArtwork ? 'Send it back to the concepts' : 'Change the size'}</button>
    </div>`
      : `<div class="gate2-blocked" role="alert">
      <h4>This design cannot be approved yet</h4>
      <p>The shape you confirmed is recorded, but the drawing is
        ${g2r.technical_intervention_required
          ? 'in records that disagree — someone who knows the code must look'
          : 'not a clean, finished drawing'}. Its editable file is
        ${g2r.ai_authoritative ? 'there' : 'not there'}, and approving it cannot go ahead.
        ${g2r.png_preview_available ? 'Its picture is for looking only — never what is approved.' : ''}</p>
      <details class="tech"><summary>What the record says</summary><p><code>GATE_2_NOT_READY</code>
        <code>${escapeHtml(g2r.reason_code || '')}</code></p></details>
    </div>`}
    ${designHistoryHtml(images)}
  `;
  showDrawings(document.getElementById('drawings'), taskId);    // [his goal of 2026-10-13, (6)]
}

// [his second goal of 2026-10-06, item 2: "A FAST FOLD CHECK ... run on every dieline before I see it ... A failure is
// fixed or shown to me, never hidden."] The die folded and checked: its count beside Approve, each failure in words
function foldCheckHtml(packagingOutput) {
  const fold = (packagingOutput.spec_sheet || {})['fold_check/1.0'];
  if (!fold) return '';
  const n = (fold.findings || []).length;
  if (fold.passed) {
    return `<p class="fold-check ok" role="note">The die folds as the trade draws it: ${n} checks hold — every flap
      meets the edge it closes onto, the tube closes square, the tucks reach their slots.</p>`;
  }
  return `<div class="gate2-blocked fold-check" role="alert">
      <h4>The die does not fold as the trade draws it — ${(fold.failed || []).length} of ${n} checks fail</h4>
      <ul>${(fold.failed || []).map(x => `<li>${escapeHtml(x.words)}</li>`).join('')}</ul>
    </div>`;
}

// [his second goal of 2026-10-06, item 1: "only then widen the carton to the smallest width that fits (say so)"] A
// carton drawn wider than he confirmed so its label stands on the back's sticker: said beside Approve, in his sizes
function labelWidenedHtml(packagingOutput) {
  const widened = ((packagingOutput.spec_sheet || {})['back_copy/1.0'] || {}).widened;
  if (!widened || !widened.to_mm) return '';
  return `<div class="gate2-warnings label-widened" role="note">
      <h4>The carton is ${escapeHtml(String(widened.to_mm))} mm wide, not ${escapeHtml(String(widened.from_mm))} mm</h4>
      <p>${escapeHtml(widened.said)}</p>
    </div>`;
}

// [his final goal, 2026-10-05, C7: "THE SYSTEM CHECKS ITS OWN WORK ... Fix them itself, or show what and where. Never
// hand me a defect silently."] Beside Approve: what the drawing's own check fixed, and what it shows him, each with its
// panel and millimetres
// [his goal for the pitch, 2026-10-15, B (5): "DESIGNER'S EYE ... PASS means matches the concept ... Tell me the cost
// per design."] the drawing looked at beside its concept: its verdict, its fixes, what it still sees, what it cost
// [his last goal before the pitch, 2026-10-16, Step 1 (2): "One verdict: the designer's eye result replaces "Not measured
// yet" when it has run; never both, never contradicting."] the checks with no measurement it stands for, folded under it
function designersEyeHtml(eye, warnings) {
  if (!eye) return '';
  const stands = (warnings || []).filter(r => r.kind === 'eye');
  const cost = `$${Number(eye.cost_usd || 0).toFixed(2)}`;
  const looks = `${eye.looks} look${eye.looks === 1 ? '' : 's'}`;
  const head = eye.state === 'PASS'
    ? `<p><b>Matches its concept.</b> ${escapeHtml(eye.summary)}</p>`
    : eye.state === 'NOT_LOOKED'
      ? '<p><b>The designer\'s eye could not look this time</b> — compare the drawing with its concept before approving.</p>'
      : `<p><b>Differs from its concept in ${eye.left.length} place${eye.left.length === 1 ? '' : 's'}:</b> ${escapeHtml(eye.summary)}</p>
         <ul>${eye.left.map(d => `<li>${escapeHtml(d.part)} — the concept shows ${escapeHtml(d.concept)}; the drawing shows ${escapeHtml(d.drawing)}</li>`).join('')}</ul>`;
  const fixed = (eye.fixed || []).length
    ? `<details><summary>Applied changes (${eye.fixed.length})</summary><ul>${eye.fixed.map(f => `<li>${escapeHtml(f)}</li>`).join('')}</ul></details>` : '';
  const standsFor = stands.length
    ? `<details class="tech"><summary>The checks it answers for (${stands.length})</summary><ul>${stands.map(r =>
        `<li>${escapeHtml(r.words || '')}</li>`).join('')}</ul></details>` : '';
  return `<div class="gate2-warnings self-check designers-eye" role="note">
      <h4>The designer's eye — the drawing beside its concept</h4>
      ${head}${fixed}${standsFor}
      <p class="quiet">${looks}, ${cost}</p>
    </div>`;
}

function selfCheckHtml(check, eye) {
  if (!check) return '';
  // [Step 1 (2)] what the designer's eye said is said once, in its own box — never again here
  const eyes = ((eye && eye.left) || []).map(d => `${d.part} (`);
  const fixed = check.said.filter(s => s.startsWith('Fixed: '));
  const shown = check.said.filter(s => !s.startsWith('Fixed: ')
    && !eyes.some(p => s.replace(/^Look at: /, '').startsWith(p)));
  if (!shown.length && !fixed.length && check.said.length) return '';
  const list = (some) => `<ul>${some.map(s => `<li>${escapeHtml(s.replace(/^(Fixed|Look at): /, ''))}</li>`).join('')}</ul>`;
  return `<div class="gate2-warnings self-check" role="note">
      <h4>The drawing checked its own work</h4>
      ${shown.length ? `<p><b>Look at (${shown.length}):</b></p>${list(shown)}` : '<p>Nothing to look at: no defect found.</p>'}
      ${fixed.length ? `<details><summary>Fixed by itself (${fixed.length})</summary>${list(fixed)}</details>` : ''}
    </div>`;
}

// [his final goal, 2026-10-05, C5: "Only if it still doesn't fit, STOP and offer: a wider carton, the info printed on
// the inside, or fewer languages."] A stopped label: why, and each offer drawn as the design would be — his to take,
// none taken for him; Approve waits until he chooses
function labelStopHtml(packagingOutput, taskId) {
  const spec = packagingOutput.spec_sheet || {};
  const back = spec['back_copy/1.0'] || {};
  // [his final goal, C5c] a container's back that cannot stand in its languages offers fewer, as a carton's does
  const container = (spec['container_label_offers/1.0'] || []).length > 0;
  if (!container && !(back.codes || []).includes('CARTON_LABEL_DOES_NOT_FIT')) return '';
  const offers = packagingOutput.label_offers || [];
  const LANG = {en: 'English', es: 'Spanish', ar: 'Arabic'};
  // [his second goal of 2026-10-06, item 1; his correction of 2026-10-07] neither the info printed inside nor a wider
  // carton is an offer: fewer languages, by his choice, is the one
  const words = o => `Fewer languages — ${(o.languages || []).map(l => LANG[l] || l).join(' and ')}, on this ${container ? 'container' : 'carton'}`;
  const card = o => `<figure class="offer-card">
      <img src="${o.png_url}" alt="${escapeHtml(words(o))}" class="offer-img">
      ${o.png_inside_url ? `<img src="${o.png_inside_url}" alt="Its inside" class="offer-img">` : ''}
      <figcaption>${escapeHtml(words(o))}</figcaption>
      <button class="btn-approve" data-offer="${escapeHtml(o.offer)}"
        data-languages="${escapeHtml((o.languages || []).join(','))}"
        onclick="chooseLabelOffer(${taskId}, this.dataset.offer, this.dataset.languages)">Take this</button>
    </figure>`;
  return `<div class="gate2-blocked label-stop" role="alert">
      <h4>The label does not fit on this ${container ? "container's back" : 'carton'}</h4>
      <p>${container ? "Its back's label does not fit even shrunk evenly to its floor (3 pt); nothing was moved or dropped."
                     : escapeHtml((back.said || []).join(' ')) + '.'} Choose one — each is drawn below as the design
        would be, and taking it costs nothing.</p>
      <div class="offer-grid">${offers.map(card).join('')}</div>
      ${offers.length ? '' : '<p>No offer holds the label on this carton — ask for changes to its size or its copy.</p>'}
    </div>`;
}

async function chooseLabelOffer(taskId, offer, languages) {
  if (!(await askInPage('Make the design again with this choice? Nothing is spent.', {yes: 'Make it again'}))) return;
  const body = {offer};
  if (languages) body.languages = languages.split(',');
  await postAction(`/api/tasks/${taskId}/label_offer/`, body);
  loadTask(taskId);
}

// VQR-2A §9: ONE coherent Visual Quality Gate panel. Every required axis is
// shown with its state — UNMEASURED axes are never hidden, and there is no
// approval language anywhere on the same screen when the gate fails.
var VQ_AXIS_LABELS = {
  artifact_authority: 'The editable file is there and whole',
  artboard_fitness: 'The artboard fits the product',
  silhouette_fidelity: 'The outline matches the concept',
  closure_fidelity: 'The closure matches the concept',
  front_artwork_resolution: 'The front artwork is drawn, not a stand-in',
  logo_quality: 'The mark is not cut off, stretched or too small',
  typography_quality: 'No text is cut off, overlapping or too small',
  composition_quality: 'Everything is on the artboard, with no text over text',
};
//: a check's state, in words
var VQ_STATE_WORDS = {PASS: 'passes', FAIL: 'fails', UNMEASURED: 'not measured yet'};

function vqGatePanelHtml(q) {
  const measured = m => Object.entries(m || {})
    .map(([k, v]) => `${escapeHtml(k)}: ${escapeHtml(
        Array.isArray(v) ? v.join(' × ') : String(v))}`)
    .join(' · ');
  const axisRows = Object.entries(q.required_axes || {}).map(([name, a]) => {
    const cls = a.state === 'PASS' ? 'vq-pass'
      : a.state === 'FAIL' ? 'vq-fail' : 'vq-unmeasured';
    const vals = measured(a.measured);
    return `<li class="vq-axis ${cls}">
      <span class="vq-axis-name">${escapeHtml(VQ_AXIS_LABELS[name] || name)}</span>
      <span class="vq-axis-state">${escapeHtml(VQ_STATE_WORDS[a.state] || a.state)}</span>
      <span class="vq-axis-reason">${a.state === 'UNMEASURED'
        ? 'Not measured yet — a warning beside Approve.'
        // [his goal of 2026-10-13, (1): "NO check ever stops a design"] a failing check said, never a stop
        : a.state === 'FAIL' ? 'This check fails — it is said beside Approve, and approving keeps it with your approval.'
        : ''}</span>
      ${(a.code || a.reason || vals) ? `<details class="tech"><summary>What the record says</summary>
        ${a.code ? `<code class="vq-axis-code">${escapeHtml(a.code)}</code>` : ''}
        ${a.reason ? `<span class="vq-axis-why">${escapeHtml(a.reason)}</span>` : ''}
        ${vals ? `<span class="vq-axis-measured">${vals}</span>` : ''}</details>` : ''}
    </li>`;
  }).join('');
  const axes = Object.values(q.required_axes || {});
  const passing = axes.filter(a => a.state === 'PASS').length;
  return `<div class="gate2-blocked vq-gate-panel" role="alert">
      <h4>Its quality check: ${passing} of ${axes.length} pass</h4>
      <p>The drawing finished. Each check that fails is said beside Approve, and approving keeps it with your
        approval. A check not measured yet is a warning.</p>
      <details class="vq-axes"><summary>Each check (${axes.length})</summary>
        <ul class="vq-axis-list">${axisRows}</ul></details>
      <details class="tech"><summary>What the record says</summary><p><code>${escapeHtml(q.overall)}</code>
        <code>${escapeHtml(q.status || '')}</code></p></details>
    </div>`;
}

function toggleGate2Reject() {
  const box = document.getElementById('gate2-reject-box');
  if (box) box.style.display = box.style.display === 'none' ? 'flex' : 'none';
}

// §BH55 Phase 1: HIS DECISION ON THE DESIGN — the exact preview's sha256 (computed by the server from its bytes), his
// account and the time of his click recorded. [His goal of 2026-10-13, (5): "Merge "Accept this design" and "Approve"
// into one "Approve" … never two buttons that mean the same thing."] It is made by Approve (ACCEPTED) and by Ask for
// changes (REJECTED) — no button of its own; what it records is said in one quiet line beside them, its acts folded.
function canDecideDesign(da) {
  return !!(da && da.viewer_is_owner && da.at_its_gate && da.preview_sha256);
}

function designDecisionHtml(da) {
  if (!da) return '';
  // [the owner's goal of 2026-09-25, (d): each act in words — when, what, who, and whether the picture is still the
  // one decided on; the picture's sha256 and the check's own sentence kept, folded]
  const DECIDED = {ACCEPTED: 'Approved', REJECTED: 'Changes asked for'};
  const acts = (da.acts || []).map(a => `<li>${escapeHtml(whenWords(a.when))} — <b>${escapeHtml(DECIDED[a.decision] || a.decision)}</b>
    by ${escapeHtml(a.who)} · ${a.void ? 'the picture is no longer the one decided on, so this act counts for nothing'
      : 'the picture is still exactly the one decided on'}
    <details class="tech"><summary>What the record says</summary><p>sha256 <code>${escapeHtml(a.preview_sha256 || '')}</code>
      · ${escapeHtml(a.verification)}</p></details></li>`).join('');
  return acts ? `<details class="design-acts"><summary>Your decisions on this design (${(da.acts || []).length})</summary>
      <ul>${acts}</ul></details>` : '';
}

// the decision recorded on exactly the picture shown — true when kept; its refusal said in the page
async function recordDesignDecision(taskId, da, decision, note) {
  const body = new URLSearchParams({output_id: da.output_id, preview_sha256: da.preview_sha256, decision: decision,
                                    note: note || ''});
  const res = await fetch(`/dashboard/history/tasks/${taskId}/accept-design/`,
                          {method: 'POST', headers: {'X-CSRFToken': getCsrf()}, body: body});
  const text = await res.text();
  if (!res.ok) { await sayInPage(text); return false; }
  try { const d = JSON.parse(text); if (d.next) showToast(d.next, 'info'); } catch (e) { /* the task reload shows the act */ }
  return true;
}

// §BH71 (0a), the owner's goal of 2026-09-28: "Unmeasured checks (fidelity to the concept, copy fit) show as a
// warning beside Approve, never a block." Each in words; the record's codes folded under "What the record says".
// [his answer of 2026-09-29 to the §BH71 report, (4)] words the executor wrote that nobody has confirmed are said
// apart, "Not confirmed yet" — beside Approve the same way, never a block.
// [his review of 119, 2026-10-05, point 6: "show it as 'Not confirmed yet' beside Approve until I confirm it"] the
// translations' row shows their words and a button that confirms them
function acceptanceWarningsHtml(rows, taskId) {
  if (!Array.isArray(rows) || !rows.length) return '';
  const unconfirmed = rows.filter(r => r.kind === 'unconfirmed');
  // [Step 1 (2)] a check the designer's eye answers for ("eye") is said under its verdict, never here as well
  const unmeasured = rows.filter(r => r.kind === 'unmeasured');
  if (!unconfirmed.length && !unmeasured.length) return '';
  const confirmBox = (r) => r.confirm !== 'translations' ? '' : `
      <details class="translations"><summary>The words</summary><ul>${(r.detail || []).map(d =>
        `<li><b>${escapeHtml(d.language)}, ${escapeHtml(d.field)}:</b> ${escapeHtml(d.words)}</li>`).join('')}</ul></details>
      <button class="btn-confirm" onclick="confirmTranslations(${taskId})">Confirm the translations</button>`;
  const list = (some) => `<ul>${some.map(r => `<li>${escapeHtml(r.words || '')}${confirmBox(r)}</li>`).join('')}</ul>`;
  return `<div class="gate2-warnings" role="note">
      ${unmeasured.length ? `<h4>Not measured yet (${unmeasured.length})</h4>
      <p>These checks have no measurement yet. You can approve with them open; each is kept with your approval.</p>
      ${list(unmeasured)}` : ''}
      ${unconfirmed.length ? `<h4>Not confirmed yet (${unconfirmed.length})</h4>
      <p>Words the executor wrote that you have not confirmed. You can approve with them open; each is kept with
      your approval.</p>
      ${list(unconfirmed)}` : ''}
      <details class="tech"><summary>What the record says</summary><p>${unmeasured.concat(unconfirmed).map(r =>
        `<code>${escapeHtml(r.code || '')}</code>`).join(' ')}</p></details>
    </div>`;
}

// Approve's own counts: the checks not measured yet, and — written only when there is some — the words not confirmed
// yet, so a design with none asks exactly as it always did
function approveCounts(taskData) {
  // [his goal of 2026-10-13, (1)] every count in its own place — the checks not measured, the copy not confirmed — so
  // the checks it has not passed, after them, are never read as copy not confirmed
  const rows = (taskData && taskData.acceptance_warnings) || [];
  const unconfirmed = rows.filter(r => r.kind === 'unconfirmed').length;
  // [Step 1 (2)] the checks the designer's eye answers for are not "not measured yet"
  return `${rows.filter(r => r.kind === 'unmeasured').length}, ${unconfirmed}`;
}

async function confirmTranslations(taskId) {
  if (!(await askInPage('Confirm the label\'s Spanish and Arabic as they stand? If they change, they will ask again.',
                        {yes: 'Confirm them'}))) return;
  await postAction(`/api/tasks/${taskId}/confirm_translations/`, {});
  loadTask(taskId);
}

// [His answers after 122 was redrawn, 2026-10-08, (1): "Add an optional SKU field on New design and at Gate 2 so I can
// fill it in any time."] the design's SKU beside Approve: its product record's, said; else his to type, at any time
var _skuSaid = '';

function skuFieldHtml(taskData, taskId) {
  if (!taskData) return '';
  if (taskData.sku_from_product) {
    return `<p class="sku-line">SKU <strong>${escapeHtml(taskData.sku)}</strong> — from the product record</p>`;
  }
  return `<div class="sku-field">
      <label for="design-sku">SKU <span>optional</span></label>
      <input id="design-sku" class="field" maxlength="64" autocomplete="off" value="${escapeHtml(taskData.sku || '')}"
             placeholder="None yet — add it any time">
      <button class="btn" type="button" id="save-sku" onclick="saveSku(${taskId})">Save the SKU</button>
      <p id="sku-msg" class="small" role="status">${escapeHtml(_skuSaid)}</p>
    </div>`;
}

async function saveSku(taskId) {
  const msg = document.getElementById('sku-msg');
  const sku = document.getElementById('design-sku').value.trim();
  let res, body = {};
  try {
    res = await fetch(`/api/tasks/${taskId}/sku/`, {
      method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCsrf()},
      body: JSON.stringify({sku: sku})});
    body = await res.json().catch(() => ({}));
  } catch (err) {
    msg.textContent = 'The SKU was not saved — the site did not answer. Try again.';
    return;
  }
  if (!res.ok) {
    msg.textContent = body.words || 'The SKU was not saved.';
    return;
  }
  _skuSaid = body.words || 'Saved.';
  loadTask(taskId);
}

async function approveGate2(taskId, outputId, open, unconfirmed, kept) {  // open: checks not measured; unconfirmed: words
  const said = [];
  // [his goal of 2026-10-13, (1)] the checks it has not passed, said and kept with his approval
  if (kept) said.push(`${kept} check${kept === 1 ? ' it has' : 's it has'} not passed ${kept === 1 ? 'is' : 'are'} beside it`);
  if (open) said.push(`${open} check${open === 1 ? ' is' : 's are'} not measured yet`);
  if (unconfirmed) said.push(`${unconfirmed} piece${unconfirmed === 1 ? ' of copy is' : 's of copy are'} not confirmed yet`);
  if (!(await askInPage(said.length ? `Approve this design? ${said.join(' and ')}; `
      + 'they are kept with your approval. Its files are then final.'
      : 'Approve this design? Its files are then final.', {yes: 'Approve'}))) return;   // §BH55 Phase 3: one word for every kind
  // [his goal of 2026-10-13, (5)] one Approve: the design accepted on exactly this drawing first, then its gate
  const da = (window._lastTaskData || {}).design_acceptance;
  if (canDecideDesign(da) && !(await recordDesignDecision(taskId, da, 'ACCEPTED', ''))) return;
  await postAction(`/api/tasks/${taskId}/gate2_approve/`, {packaging_output_id: outputId});
  loadTask(taskId);
}

async function rejectGate2(taskId) {
  const notes = document.getElementById('gate2-reject-notes').value.trim();
  if (!notes) { sayInPage('Say what should change first.'); return; }
  // [his goal of 2026-10-13, (5)] one Ask for changes: the design turned down on exactly this drawing, with his words
  const da = (window._lastTaskData || {}).design_acceptance;
  if (canDecideDesign(da) && !(await recordDesignDecision(taskId, da, 'REJECTED', notes))) return;
  const res = await postAction(`/api/tasks/${taskId}/gate2_reject/`, {notes});
  if (res === null) { sayInPage('The request for changes was not sent — try again.'); return; }
  loadTask(taskId);
}

// [His goal of 2026-10-13, (5): "one "Download" (the layered .ai, with other formats in a small menu); never two buttons
// that mean the same thing."] ONE Download: the first file there is (the layered .ai where it was built), every other
// format in a small menu under it — the same for every kind of design. ONE primary a step: at its gate Approve is the
// step's, the Download beside it quiet; once finished, Download is the step's (``primary``)
function downloadHtml(files, extra, primary) {
  const there = (files || []).filter(Boolean);
  if (!there.length) return extra || '';
  const [first, ...rest] = there;
  const link = (f, cls) => `<a href="${escapeHtml(f.url)}"${f.plain ? '' : ' download'} class="${cls}">${escapeHtml(f.words)}</a>`;
  const more = rest.map(f => `<li>${link(f, 'download-more-link')}</li>`).join('') + (extra ? `<li>${extra}</li>` : '');
  return `<div class="download-one">
      <a href="${escapeHtml(first.url)}"${first.plain ? '' : ' download'} class="btn ${primary ? 'primary' : 'quiet'} download-main">Download</a>
      <span class="download-what">${escapeHtml(first.words)}</span>
      ${more ? `<details class="download-more"><summary>Other formats</summary><ul>${more}</ul></details>` : ''}
    </div>`;
}

// [D-D11-9: "its page shows every surface ... and the downloads (13 Oct B5–B6)"] a published master's other files —
// each piece's own .ai or PDF, its 1 : 1 sheets, the day's records — placed after the fixed formats, so the layered .ai
// stays the one Download and these sit under Other formats (PackagingOutputSerializer.other_files; [] for any other)
function otherFiles(po) {
  return ((po || {}).other_files || []).filter(f => f && f.url).map(f => ({url: f.url, words: f.words}));
}

// [D-D11-9, the review of Day 11] a published master (services/master_tasks.py): its one Download is the primary
// surface's own layered .ai and its drawing every surface, a page each — never a carton's "every piece its own" or
// "one layer". Its two fixed files are said in the words its publication stored for them (slot_words/1.0); a master
// published before it stored any is said neutrally; every other design keeps its ``fixed`` words
function isMasterPublication(po) {
  return ((po || {}).spec_sheet || {}).backend === 'master_publication';
}

function slotWords(po, slot, fixed) {
  if (!isMasterPublication(po)) return fixed;
  const said = (po.spec_sheet['slot_words/1.0'] || {})[slot];
  if (typeof said === 'string' && said) return said;
  return {native_ai: 'The layered .ai', design_preview_ai: 'Every surface, a page each'}[slot] || fixed;
}

// [His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (1): "NO check ever stops a design ... the problem is shown beside
// Approve in plain words."] every check the design stands at its gate without passing, in words (the server's
// gate2_problems), each kept with his approval — never a code, never a reason Approve is hidden
// [his last goal before the pitch, 2026-10-16, Step 1 (1): "Never show raw engine lines on a design page ... Group
// internal faults into ONE plain sentence, folded; show only what a designer needs to judge, in words."] the checks a
// designer judges, each in words, what the record names it by folded under it; the system's own notes ONE sentence,
// folded (gate2_problems.INTERNAL_WORDS)
function gate2ProblemsHtml(taskData) {
  const all = ((taskData && taskData.gate2_problems) || {}).kept || [];
  if (!all.length) return '';
  const kept = all.filter(k => !k.internal);
  const internal = all.filter(k => k.internal);
  const said = w => w.charAt(0).toUpperCase() + w.slice(1) + (/[.!?]$/.test(w) ? '' : '.');
  const where = k => (k.details || []).length
    ? `<details class="tech"><summary>Where</summary><p>${k.details.map(d => escapeHtml(d)).join(' · ')}</p></details>` : '';
  return `<div class="gate2-problems" role="note">
      ${kept.length ? `<h4>Checks it has not passed (${kept.length})</h4>
      <p>The design went on past each; approving keeps them with your approval.</p>
      <ul>${kept.map(k => `<li>${escapeHtml(said(k.words || ''))}${where(k)}</li>`).join('')}</ul>
      <details class="tech"><summary>What the record says</summary><p>${kept.map(k =>
        `<code>${escapeHtml(k.code || '')}</code>`).join(' ')}</p></details>` : ''}
      ${internal.map(k => `<details class="tech system-notes"><summary>${escapeHtml(said(k.words || ''))}</summary>
        <p>${(k.details || []).map(d => `<code>${escapeHtml(d)}</code>`).join(' ')}</p></details>`).join('')}
    </div>`;
}

function keptCount(taskData) {
  // [Step 1 (1)] the checks a designer judges — the system's own notes are no check of the design
  return (((taskData && taskData.gate2_problems) || {}).kept || []).filter(k => !k.internal).length;
}

// === COMPLETED ===
function showCompleted(data) {
  document.getElementById('complete-state').style.display = 'block';
  const po = data.packaging_output || {};
  // [his goal of 2026-10-13, (5)] one Download — the layered .ai where it was built — the other formats in its menu
  const files = [
    po.native_ai_url && {url: po.native_ai_url,
      words: slotWords(po, 'native_ai', 'The .ai — Illustrator, layered, every piece its own')},
    po.design_preview_ai_url && {url: po.design_preview_ai_url,
      words: slotWords(po, 'design_preview_ai', 'The design .ai, one layer')},
    po.production_pdf_url && {url: po.production_pdf_url, words: 'The production PDF (CMYK)'},
    po.spec_sheet && {url: `/api/tasks/${data.id}/download_spec/`, words: 'The specification (PDF)', plain: true},
    po.dieline_ai_url && {url: po.dieline_ai_url, words: 'The dieline .ai — cuts and folds only'},
    ...otherFiles(po),
  ];
  const heroPreview = po.design_preview_url
    ? `<img src="${po.design_preview_url}" alt="${isMasterPublication(po) ? 'The design' : 'Design on dieline'}" class="dieline-img">`
    : '';
  document.getElementById('complete-state').innerHTML = `
    <h3>✓ Finished</h3>
    <p>The design is approved and its files are ready.</p>
    <div id="drawings-done" class="drawings" aria-label="The design's drawings"></div>
    <div class="drawing-hero">${heroPreview}</div>
    ${downloadHtml(files, '', true)}
    ${designHistoryHtml(data.images)}
  `;
  showDrawings(document.getElementById('drawings-done'), data.id);   // [his goal of 2026-10-13, (6)]
}

// === FAILED ===
function showFailed(taskId, logs, stopWords, images) {
  const feed = document.getElementById('activity-feed');
  // Terminal state: clear first so repeated loads/polls don't stack notices,
  // then re-render the activity history for context.
  feed.innerHTML = '';
  lastLogId = 0;
  showFeed(logs || []);

  // [His test findings on design 121, 2026-10-07, item 3: "Errors are shown to me in words, never engine codes."] why it
  // stopped, in words, as the status it came with says it (apps/dashboard/words.stop_words) — or as the page was told
  // when it opened; never the record's own text, which a design that stopped while its page was open showed in codes
  let reason = (stopWords || window.DESIGN_REASON || '').trim();

  const notice = document.createElement('div');
  notice.className = 'failed-notice';
  const p = document.createElement('p');
  p.textContent = reason || 'The design stopped.';   // textContent → no XSS from logs (§BH55 Phase 3: it said "Pipeline failed.")
  const btn = document.createElement('button');
  btn.textContent = 'Try again';
  btn.onclick = () => retryTask(taskId);
  p.append(document.createTextNode(' '), btn);
  // §BH54(k) 1: a retry re-queues the paid pipeline; the measured cost stands beside the button
  const spend = document.createElement('span');
  spend.innerHTML = spendNoteHtml({spend_estimates: window._lastSpendEstimates}, 'retry');
  p.append(document.createTextNode(' '), spend);
  notice.appendChild(p);
  // [the owner's walk: a stopped design showed its log before its reason — the reason and "Try again" come first,
  // and what it did, step by step, is folded beneath them]
  feed.insertBefore(notice, feed.firstChild);
  const steps = Array.from(feed.children).filter(el => el !== notice);
  if (steps.length) {
    const fold = document.createElement('details');
    fold.className = 'tech feed-steps';
    fold.innerHTML = '<summary>What it did, step by step</summary>';
    steps.forEach(el => fold.appendChild(el));
    feed.appendChild(fold);
  }

  // Design history survives failure too — whatever was generated before the
  // crash stays reviewable (2026-07-04).
  const state = document.getElementById('feed-state');
  const old = state.querySelector('.design-history');
  if (old) old.remove();
  if (images && images.length) {
    state.insertAdjacentHTML('beforeend', designHistoryHtml(images));
  }
}

async function retryTask(taskId) {
  await postAction(`/api/tasks/${taskId}/retry/`, {});
  loadTask(taskId);
}

// === REJECTED ===
function showRejected(logs) {
  const feed = document.getElementById('activity-feed');
  feed.innerHTML = '';
  lastLogId = 0;
  showFeed(logs || []);

  const notice = document.createElement('div');
  notice.className = 'failed-notice';
  const p = document.createElement('p');
  p.textContent = 'This design was turned down and closed. Start a new design to go on.';
  notice.appendChild(p);
  feed.appendChild(notice);
  feed.scrollTop = feed.scrollHeight;
}


// === NATIVE ILLUSTRATOR HANDOFF (Phase 2A-8) ===
// §BH55 Phase 2: an artwork design's channel pieces — each a PNG at its exact pixel size, the file a channel takes
function artworkPieceLinks(spec) {
  const rec = (spec || {})['artwork_record/1.0'] || {};
  return (rec.formats || []).filter(f => f.png && f.png.url).map(f =>
    `<a href="${escapeHtml(f.png.url)}" download class="btn-download">${escapeHtml(f.label)} · ${f.png.px[0]} × ${f.png.px[1]} px</a>`
  ).join('');
}

// [his last goal before the pitch, 2026-10-16, Step 1 (8)] the Illustrator package's box and its button are gone:
// Download is the one way to get a design's files (downloadHtml)

// === MATERIAL REFERENCES (2A-6E, rebuilt 2A-6E-CORR-3) ===
// §2 build markers: which gates.js the browser ACTUALLY loaded. The page
// stamps window.__BBROSE_FRONTEND_BUILD__ from the served process revision;
// this file stamps its own feature marker. Both render inside the panel —
// if the visible build line is missing or old, the asset is stale.
// §BH55 Phase 3: both are on the panel now as its data-build attribute, not a line a designer reads ("Frontend build:
// page … · gates …"); the marker names this file's words
window.__BBROSE_GATES_BUILD__ = 'gates/bh55-p3-words-1';

// §BH55 Phase 3: a reference's codes in a designer's words — the panel printed them as stored
// ("HOUSE_PRODUCTION_LINEAGE_UNCONFIRMED", "USER_APPROVED_FOR_CONCEPT_REFERENCE"); a code not listed reads as words
var REF_SOURCE_WORDS = {HISTORICAL_DESIGN_REFERENCE: 'a past BBROSE design',
                        AI_DESIGN_LIBRARY: "one of the house's Illustrator files",
                        MATERIAL_LIBRARY: 'from the materials library', WEB_REFERENCE: 'found on the web'};
var REF_OWNERSHIP_WORDS = {HOUSE_PRODUCTION_LINEAGE_UNCONFIRMED: "the house's own work — not yet confirmed",
                           LIKELY_BBROSE_UNCONFIRMED: "probably BBROSE's own — not confirmed",
                           UNCONFIRMED_THIRD_PARTY: "probably someone else's — not confirmed",
                           OWNERSHIP_UNCONFIRMED: 'whose it is: not confirmed', UNKNOWN: 'whose it is: unknown'};
var REF_RIGHTS_WORDS = {RIGHTS_UNREVIEWED: 'its rights not reviewed', UNVERIFIED: 'its rights not verified',
                        PENDING_HUMAN_CONFIRMATION: 'its rights waiting for a person to confirm'};
var REF_PERMISSION_WORDS = {CANDIDATE: 'offered — not approved', DECLINED: 'declined',
                            USER_APPROVED_FOR_CONCEPT_REFERENCE: "approved — a reference for this design's concepts only"};
function codeWords(code) { return String(code || '').replace(/_/g, ' ').toLowerCase(); }
function referenceTitle(title) { return String(title || '').replace(/_+/g, ' ').trim(); }

// §BH71 PART 2 "never near-copied": a concept close to a trend picture its directions used is said beside it —
// look before you choose it; nothing is removed
function nearCopyHtml(img) {
  const near = (img.reference_provenance || {}).trend_near_copy;
  if (!near || !near.close_to || !near.close_to.length) return '';
  const which = near.close_to.map(c => `trend picture ${c.number} (found on ${escapeHtml(c.platform)}, `
    + `${c.bits_apart} of 64 apart)`).join(', ');
  return `<p class="near-copy"><strong>Close to ${which}</strong> — look before you choose it.</p>`;
}

// Per-render provenance: what ACTUALLY reached the image provider. A render
// must never claim library influence this section cannot evidence.
// §BH55 Phase 3: in words — it read "Approved concept-reference IDs", "Visual files passed to the provider" and the
// influence plan's hash (the plan and its hash are on the regeneration's own page)
function materialReferencesUsedHtml(img) {
  const prov = img.reference_provenance || {};
  const ids = prov.concept_reference_ids || [];
  const files = prov.visual_files_passed || [];
  if (!ids.length && !files.length) {
    return '<details><summary>References it was drawn with</summary>' +
      '<p>No reference from the library was shown to the drawing for this concept.</p></details>';
  }
  const fileList = files.map(f => `<li>${escapeHtml(f)}</li>`).join('');
  return `<details><summary>References it was drawn with (${ids.length} approved)</summary>
    <p>The pictures shown to the drawing:</p><ul>${fileList}</ul>
    <p><strong>References for this design's concepts only — none may be placed in a design.</strong></p>
  </details>`;
}

var _matRefPanel = {taskFor: null, seq: 0, busy: false, approvedIds: [],
                    pollSeq: 0};

// §3: every state change is written visibly. No silent path.
function _matRefStatus(text) {
  const status = document.getElementById('mat-ref-status');
  if (status) status.textContent = text;
  else console.warn('mat-ref-status element missing:', text);
}

// §4: ONE delegated listener on document — dashboard re-renders can replace
// the buttons freely; the handler never detaches, never duplicates.
(function initMaterialReferenceActions() {
  if (window.__BBROSE_GATES_INITIALIZED__) return;
  window.__BBROSE_GATES_INITIALIZED__ = true;
  document.addEventListener('click', function (event) {
    const el = event.target.closest('[data-action]');
    if (!el) return;
    const action = el.dataset.action;
    const taskId = parseInt(el.dataset.task || '', 10);
    // 2A-6E-CORR-4: regeneration is a plain server-rendered link now —
    // JavaScript handles only the non-essential enhancements here.
    const handlers = {
      'approve-concept-references': approveConceptReferences,
      'refresh-candidates': (id) => renderMaterialReferencePanel(id, true),
    };
    if (!handlers[action]) return;
    event.preventDefault();
    if (!taskId) {
      _matRefStatus('This control has lost its design — reload the page.');    // §BH55 Phase 3: it read EARLY_RETURN
      return;
    }
    handlers[action](taskId, el);
  });
})();

// The material-reference selection screen (§4): bounded candidates, explicit
// user approval of 2–4, nothing pre-selected, nothing sent before approval.
// Renders once per task (poll ticks never wipe selections); every fetch
// carries a sequence token so a stale response can never overwrite state.
async function renderMaterialReferencePanel(taskId, force) {
  const gallery = document.getElementById('image-gallery');
  let panel = document.getElementById('material-reference-panel');
  if (panel && _matRefPanel.taskFor === taskId && !force) {
    return;   // poll tick — never wipe the user's in-progress selection
  }
  if (!panel) {
    panel = document.createElement('div');
    panel.id = 'material-reference-panel';
    panel.className = 'concept-note';
    // [the owner's walk, finding 5: the concepts sat 3,735 px down, under this panel — they come first now]
    gallery.parentNode.insertBefore(panel, gallery.nextSibling);
  }
  const seq = ++_matRefPanel.seq;
  panel.innerHTML = '<p>Finding references in the library…</p>';
  let data;
  try {
    const res = await fetch(`/api/tasks/${taskId}/concept_references/`, {credentials: 'same-origin'});
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch (e) {
    if (seq === _matRefPanel.seq) {
      panel.innerHTML = `<p>The references could not be loaded (${escapeHtml(String(e))}).</p>`;
    }
    return;
  }
  if (seq !== _matRefPanel.seq) return;   // superseded by a newer render
  _matRefPanel.taskFor = taskId;
  const approved = data.approved_ids || [];
  _matRefPanel.approvedIds = approved;
  // §BH55 Phase 3: each card in words — it read "#12 <file_name> · MATERIAL_LIBRARY · raster · score 3.0 · ownership:
  // … · rights: … · permission: …"; the order (best match first) still says what the score said
  const cards = (data.candidates || []).map(c => `
    <label class="image-card" style="display:flex;gap:10px;align-items:flex-start;padding:8px;">
      <input type="checkbox" class="mat-ref-check" value="${c.id}" ${approved.includes(c.id) ? 'checked' : ''}>
      <img src="${c.thumbnail_url}" alt="${escapeHtml(referenceTitle(c.title))}" loading="lazy"
           style="width:90px;height:90px;object-fit:cover;flex:none;">
      <span style="font-size:12px;">
        <strong>${escapeHtml(referenceTitle(c.title))}</strong><br>
        ${escapeHtml(REF_SOURCE_WORDS[c.source_type] || codeWords(c.source_type))} · ${c.is_vector ? 'vector' : 'raster'}<br>
        ${c.relevance_reason ? `Offered for: ${escapeHtml(c.relevance_reason)}<br>` : ''}
        ${escapeHtml(REF_OWNERSHIP_WORDS[c.ownership_status] || codeWords(c.ownership_status))} ·
        ${escapeHtml(REF_RIGHTS_WORDS[c.rights_status] || codeWords(c.rights_status))}<br>
        ${(c.record && c.record.words) ? `<em>${escapeHtml(c.record.words)}</em><br>` : ''}
        ${(c.record && c.record.shows) ? `It shows: ${escapeHtml(c.record.shows)}<br>` : ''}
        <strong>${escapeHtml(REF_PERMISSION_WORDS[c.permission_status] || codeWords(c.permission_status))}</strong>
      </span>
    </label>`).join('');
  // §8: compact, always-visible action block at the top of the Gate-1
  // review area. The control is a NORMAL ANCHOR to the server-rendered
  // confirmation page — no fetch, no JSON, no globals, no dialogs: even if
  // every script handler fails, anchor navigation is plain browser behavior.
  const confirmUrl = `/dashboard/tasks/${taskId}/gate1-regeneration/confirm/`;
  const approvedWords = `${approved.length} ${approved.length === 1 ? 'reference' : 'references'} approved`;
  const actionBlock = approved.length ? `
    <div class="reject-section" style="border:1px solid #4e7a4e;padding:10px 14px;margin-bottom:10px;">
      <strong>${approvedWords} — the concepts can be drawn again with them</strong><br>
      <a class="btn-approve" style="display:inline-block;margin-top:8px;text-decoration:none;"
         href="${confirmUrl}">Review, then draw again</a>
    </div>` : '';
  panel.dataset.build = `page ${window.__BBROSE_FRONTEND_BUILD__ || 'unknown'} · gates ${window.__BBROSE_GATES_BUILD__}`;
  // [his goal of 2026-10-06, item 13: "the "draw again with references" grid is folded by default and shows only
  // references that match the brief, not unrelated stock"] folded, its count on the fold; open once he has opened it or
  // approved references from it — his picks shown where he made them
  const wasOpen = !!(panel.querySelector('details.mat-ref-fold[open]')) || approved.length > 0;
  const offered = (data.candidates || []).length;
  panel.innerHTML = `
    ${actionBlock}
    <details class="mat-ref-fold"${wasOpen ? ' open' : ''}>
    <summary><h4 style="display:inline">Draw the concepts again, with references</h4>
      <span class="quiet"> — ${offered ? `${offered} in the library match${offered === 1 ? 'es' : ''} this brief` : 'nothing in the library matches this brief'}</span></summary>
    <p>Choose <strong>two to four</strong> pictures from the library for the next concepts
       to draw on. Approving them makes them references for <strong>this design's concepts
       only</strong> — never placed in a design, and never used for another unless it chooses them too.
       Under each one, what the materials record says of it: a file the record has never judged says so.</p>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:8px;">${cards ||
      '<p class="empty-note">Nothing in the library matches this design.</p>'}</div>
    <p style="margin-top:10px;">
      <button id="mat-ref-approve-btn" class="btn-approve"
              data-action="approve-concept-references" data-task="${taskId}">Approve selected references</button>
      ${approved.length
        ? `<a id="mat-ref-regen-link" class="btn-download" style="text-decoration:none;"
             href="${confirmUrl}">Draw the concepts again with these references</a>`
        : `<span class="btn-download" style="opacity:.5;">Draw the concepts again with references (approve some first)</span>`}
      <button class="btn-download" data-action="refresh-candidates" data-task="${taskId}">Find other references</button>
    </p>
    <p id="mat-ref-status" style="font-size:12px;">${approved.length
      ? `${approvedWords} — you can draw the concepts again with them.`
      : 'Nothing approved yet — approve two to four to draw the concepts again with them.'}</p>
    </details>`;
}

async function approveConceptReferences(taskId) {
  // §BH55 Phase 3: every state is still written visibly (2A-6E-CORR-3 §3), in words — they read CLICK_RECEIVED,
  // EARLY_RETURN and REQUEST_SENDING
  _matRefStatus('Received — approving…');
  if (_matRefPanel.busy) {
    _matRefStatus('Still approving your last choice — wait for it to finish.');
    return;
  }
  const button = document.getElementById('mat-ref-approve-btn');
  const ids = Array.from(document.querySelectorAll('.mat-ref-check:checked'))
    .map(el => parseInt(el.value, 10));
  _matRefPanel.busy = true;
  if (button) { button.disabled = true; button.textContent = 'Approving…'; }
  _matRefStatus('Approving…');
  try {
    const res = await postAction(`/api/tasks/${taskId}/concept_references/approve/`, {ids});
    if (res && Array.isArray(res.approved_ids)) {
      const n = res.approved_ids.length;
      await renderMaterialReferencePanel(taskId, true);
      _matRefStatus(`✓ ${n} ${n === 1 ? 'reference' : 'references'} approved — for this design's concepts only, `
        + `never placed in a design. You can draw the concepts again with them.`);
    } else if (res && res.error) {
      _matRefStatus(`Not approved: ${res.error}`);
    } else if (res !== null) {
      _matRefStatus('The approval was not confirmed — reload the page to see whether it was kept.');
      sayInPage('The approval was not confirmed — reload the page to see whether it was kept.');
    } else {
      _matRefStatus('Not approved — see the message.');
    }
  } catch (e) {
    _matRefStatus(`Not approved: ${e}`);
    sayInPage(`Not approved: ${e}`);
  } finally {
    _matRefPanel.busy = false;
    const btn = document.getElementById('mat-ref-approve-btn');
    if (btn) { btn.disabled = false; btn.textContent = 'Approve selected references'; }
  }
}

// 2A-6E-CORR-4: the JS regeneration flow (arm/confirm panels, job polling)
// was removed — the essential action is the server-rendered confirmation
// page linked above, which works with JavaScript disabled. The job status
// page is server-rendered too, with a plain refresh link.


// === 2A-9B §8 — live parametric dimension qualification =====================
let _qualifyTimer = null;
let _lastQualification = null;
// [his test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (6): "Flag
// impossible sizes at the size step (I typed 1123 mm for a 120 mm product; it accepted it)."] the sizes as he types,
// flagged by the design's own product (POST size_flags): impossible in red, the button held; far larger said, never held
let _sizeTaskId = null;
let _sizeTimer = null;
let _lastSizeFlags = [];

function scheduleQualifyDims() {
  clearTimeout(_qualifyTimer);
  _qualifyTimer = setTimeout(qualifyDims, 350);
  clearTimeout(_sizeTimer);
  _sizeTimer = setTimeout(flagSizes, 300);
}

async function flagSizes() {
  const box = document.getElementById('dim-size-flags');
  if (!box || _sizeTaskId === null) return;
  const dims = {};
  for (const key of ['width_mm', 'depth_mm', 'height_mm']) {
    const el = document.getElementById('dim-' + key);
    if (el && el.value !== '' && !isNaN(parseFloat(el.value))) dims[key] = parseFloat(el.value);
  }
  try {
    const res = await fetch(`/api/tasks/${_sizeTaskId}/size_flags/`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCsrf()},
      body: JSON.stringify({dimensions: dims}),
    });
    _lastSizeFlags = (await res.json()).flags || [];
  } catch (err) {
    _lastSizeFlags = [];
  }
  box.innerHTML = _lastSizeFlags.length ? `<ul class="dim-size-flags">${_lastSizeFlags.map(f =>
    `<li class="${f.level === 'impossible' ? 'dim-error' : 'dim-hint'}">${escapeHtml(f.words.charAt(0).toUpperCase()
      + f.words.slice(1))}.</li>`).join('')}</ul>` : '';
  validateDims();
}

async function qualifyDims() {
  const box = document.getElementById('dim-qualification');
  if (!box) return;
  const chosen = selectedStructureTemplate && selectedStructureTemplate();
  if (!chosen) {
    box.innerHTML = '';
    _lastQualification = null;
    validateDims();
    return;
  }
  const val = key => {
    const el = document.getElementById('dim-' + key);
    return el && el.value !== '' ? parseFloat(el.value) : null;
  };
  const body = {
    template: chosen.template,
    width_mm: val('width_mm'), depth_mm: val('depth_mm'),
    height_mm: val('height_mm'),
    board_thickness_mm: val('board_thickness_mm') ?? 0.5,
    glue_tab_mm: val('glue_tab_mm') ?? 12.0,
    bleed_mm: val('bleed_mm') ?? 3.0,
    safe_margin_mm: val('safe_margin_mm') ?? 4.0,
  };
  if (body.width_mm == null || body.depth_mm == null || body.height_mm == null) {
    box.innerHTML = '';
    _lastQualification = null;
    validateDims();
    return;
  }
  try {
    const res = await fetch('/api/dielines/qualify_dimensions/', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCsrf()},
      body: JSON.stringify(body),
    });
    const q = await res.json();
    _lastQualification = q;
    box.innerHTML = renderQualification(q);
  } catch (err) {
    _lastQualification = null;
    box.innerHTML = '';
  }
  validateDims();
}

function renderQualification(q) {
  if (!q || !q.qualification_available) return '';
  const esc = escapeHtml;
  if (!q.supported) {
    const rows = (q.violations || []).map(v => `<li>${esc(v)}</li>`).join('');
    return `<div class="dim-qualify dim-qualify-bad">
      <strong>DIMENSION_COMBINATION_UNSUPPORTED</strong> — ${esc(q.template_key)}
      cannot generate this combination; the preview is disabled. Your values
      were NOT altered.
      <ul>${rows}</ul>
      <span class="dim-hint">envelope at this board/glue:
        W ≥ D + t + 20 · D ≥ ${esc(String(q.envelope ? q.envelope.depth_mm_min : ''))} mm ·
        H &gt; W and H &gt; D</span>
    </div>`;
  }
  const d = q.derived || {};
  const dims = q.dimensions || {};
  const collision = q.collision || {};
  return `<div class="dim-qualify dim-qualify-ok">
    <strong>SUPPORTED</strong> — ${esc(q.template_key)}
    · geometry hash <code>${esc(q.geometry_hash)}</code><br>
    inner ${esc(String((dims.inner_mm || []).join(' × ')))} →
    mfg ${esc(String((dims.manufacture_mm || []).join(' × ')))} →
    outer ${esc(String((dims.outer_mm || []).join(' × ')))} mm ·
    closure face ${esc(String(d.closure_face_mm))} mm ·
    tuck reach ${esc(String(d.major_tuck_reach_mm))} mm ·
    dust ${esc(String(d.dust_flap_depth_mm))} mm ·
    ears ${esc(String(d.locking_ear_mm))} mm ·
    folded checks ${collision.all_ok ? 'ALL PASS' : 'FAILED'}<br>
    <span class="dim-hint">${(q.assumptions || []).map(esc).join(' · ')}</span>
  </div>`;
}
