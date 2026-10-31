// === DESIGN REVIEW BOARD (RB2) ===
// The UI renderer over the renderer-agnostic ReviewBoardData (RB1). Draws the
// consistent, target-independent informational sections — Project Header (§1),
// Specifications (§5), Approval status + history (§6), References "Reference
// Only" (§4) — as a shared frame above the state-specific interactive block
// (the concept gallery §2 / selected preview §3, which the existing show*
// functions still render, with their buttons/handlers unchanged).
//
// Defensive by contract: if review_board data is absent/malformed this no-ops
// and hides the frame, so the approval UI always degrades to the pre-RB2
// behavior rather than breaking. The interactive path never depends on this.

function renderReviewBoard(data) {
  const host = document.getElementById('review-board');
  if (!host) return;
  const rb = data && data.review_board;
  if (!rb || typeof rb !== 'object') {   // fallback: no board, no frame
    host.style.display = 'none';
    host.innerHTML = '';
    return;
  }
  try {
    // Decision-first: supporting sections are COMPACT (collapsed) by default
    // so the artwork/action stays dominant. Each is a <details> the reviewer
    // can expand; the summary carries the essentials so nothing is lost while
    // collapsed. The board renders BELOW the artwork (CSS order).
    host.innerHTML = _rbProject(rb.header)
      + _rbComparison(rb.comparison)
      + _rbSpecs(rb.specifications)
      + _rbApproval(rb.approval)
      + _rbReferences(rb.references, rb.references_expected);
    host.style.display = 'block';
  } catch (e) {                          // any render error → safe fallback
    console.error('review board render failed', e);
    host.style.display = 'none';
    host.innerHTML = '';
  }
}

function _rbField(label, value) {
  if (!value) return '';
  return `<div class="rb-field"><span class="rb-field-label">${escapeHtml(label)}</span>`
    + `<span class="rb-field-value">${escapeHtml(String(value))}</span></div>`;
}

// One collapsible section. `summaryExtra` is the compact context shown inline
// on the summary line so collapsing loses no essential information.
function _rbSection(cls, title, summaryExtra, body) {
  if (!body) return '';
  return `<details class="rb-section ${cls}">
      <summary class="rb-summary"><span class="rb-section-title">${escapeHtml(title)}</span>`
    + (summaryExtra ? `<span class="rb-summary-extra">${summaryExtra}</span>` : '')
    + `</summary><div class="rb-body">${body}</div></details>`;
}

function _rbProject(h) {
  h = h || {};
  const date = (h.updated_at || h.created_at || '').slice(0, 10);
  // Project metadata is SECONDARY — a quiet strip; essentials inline, rest on expand.
  const extra = [h.brand, h.product, h.target, h.version]
    .filter(Boolean).map(escapeHtml).join(' · ');
  const body = `<div class="rb-fields">
      ${_rbField('Brand', h.brand)}
      ${_rbField('Product', h.product)}
      ${_rbField('Designing', h.target)}
      ${_rbField('Version', h.version)}
      ${_rbField('Date', date)}
      ${_rbField('AI', h.ai_version)}
    </div>`;
  return _rbSection('rb-project', 'Project', extra, body);
}

// 2B-3V-CORR-3 §12: the selected concept and the current reconstruction side
// by side — the human judges fidelity visually, never from JSON alone. This
// section renders OPEN (not collapsed): it is decision-relevant at Gate 2.
function _rbComparison(c) {
  if (!c || !c.selected_concept_url || !c.reconstruction_url) return '';
  const body = `<div class="rb-compare-pair">
      <figure class="rb-compare-item">
        <img src="${c.selected_concept_url}" alt="the concept you chose" loading="lazy">
        <figcaption>${escapeHtml(c.selected_caption || 'The concept you chose')}</figcaption>
      </figure>
      <figure class="rb-compare-item">
        <img src="${c.reconstruction_url}" alt="what was made from it" loading="lazy">
        <figcaption>${escapeHtml(c.reconstruction_caption || 'What was made from it')}</figcaption>
      </figure>
    </div>`;
  // §BH55 Phase 3: it read "Selected concept vs reconstruction"
  return `<details class="rb-section rb-compare" open>
      <summary class="rb-summary"><span class="rb-section-title">The concept you chose, and what was made from it</span></summary>
      <div class="rb-body">${body}</div></details>`;
}

function _rbSpecs(rows) {
  if (!Array.isArray(rows) || !rows.length) return '';
  const items = rows.map(r =>
    `<div class="rb-field"><span class="rb-field-label">${escapeHtml(r.label || '')}</span>`
    + `<span class="rb-field-value">${escapeHtml(String(r.value || ''))}</span></div>`).join('');
  return _rbSection('rb-specs', 'Specifications', `${rows.length}`,
    `<div class="rb-fields">${items}</div>`);
}

// §BH55 Phase 3: each decision in words — they read the records' own codes ("gate_1 · approve")
var RB_GATE_WORDS = {gate_1: 'The concept', dimension: 'The size', container_profile: "The container's shape",
                     design_intent: 'The design intent', structure: "The carton's structure", gate_2: 'The design'};
var RB_DECISION_WORDS = {approve: 'approved', reject: 'changes asked for'};

function _rbApproval(a) {
  if (!a || typeof a !== 'object') return '';
  const status = statusWords(a.status || '');           // §BH55 Phase 3: it read the engine's state in capitals
  const hist = (Array.isArray(a.history) ? a.history : []).map(ev =>
    `<li><span class="rb-ev-gate">${escapeHtml(RB_GATE_WORDS[ev.gate] || codeWords(ev.gate))}</span> · `
    + `<span class="rb-ev-decision">${escapeHtml(RB_DECISION_WORDS[ev.decision] || codeWords(ev.decision))}</span>`
    + (ev.decided_by ? ` · ${escapeHtml(ev.decided_by)}` : '')
    + (ev.decided_at ? ` · ${escapeHtml(String(ev.decided_at).slice(0, 10))}` : '')
    + (ev.notes ? `<div class="rb-ev-notes">${escapeHtml(ev.notes)}</div>` : '')
    + `</li>`).join('');
  const body = `${_rbField('Reviewer', a.reviewer)}`
    + (hist ? `<ul class="rb-history">${hist}</ul>` : '')
    + (a.notes ? `<div class="rb-notes">${escapeHtml(a.notes)}</div>` : '');
  // Status stays visible on the summary line — it's decision-relevant.
  return _rbSection('rb-approval', 'Approval',
    `<span class="rb-status">${escapeHtml(status)}</span>`, body || '&nbsp;');
}

// B4b-3A: uploaded source material, grouped by category, presented from
// persisted metadata through the authorized endpoint only. Raster types get
// a real preview; PDF/AI/EPS get an honest neutral file card — never <img>.
// Everything user-controlled (filenames above all) goes through escapeHtml.
function _rbReferences(refs, expected) {
  refs = Array.isArray(refs) ? refs : [];
  if (!refs.length) {
    // §9: targets that accept uploads state the absence explicitly — no
    // empty headings, no placeholder cards. Other targets render nothing,
    // exactly as before this slice.
    if (!expected) return '';
    return _rbSection('rb-references', 'References', '0',
      `<p class="rb-ref-empty">No references were supplied for this task.</p>`);
  }

  // group by category, preserving the server's deterministic order
  const groups = [];
  const byKey = {};
  refs.forEach(r => {
    const key = r.category || 'other';
    if (!byKey[key]) {
      byKey[key] = {label: r.category_label || r.name || key,
                    note: r.category_note || '', items: []};
      groups.push(byKey[key]);
    }
    byKey[key].items.push(r);
  });

  const body = groups.map(g => `
    <section class="rb-ref-group">
      <h4 class="rb-ref-group-title">${escapeHtml(g.label)}</h4>
      ${g.note ? `<p class="rb-ref-group-note">${escapeHtml(g.note)}</p>` : ''}
      <ul class="rb-ref-list">
        ${g.items.map(_rbReferenceCard).join('')}
      </ul>
    </section>`).join('');

  return _rbSection('rb-references', 'References', `${refs.length}`, body);
}

function _rbReferenceCard(r) {
  const name = escapeHtml(r.filename || 'reference');
  const status = escapeHtml(String(r.status || '').replace(/_/g, ' '));
  const date = r.uploaded_at
    ? `<time datetime="${escapeHtml(r.uploaded_at)}">${escapeHtml(String(r.uploaded_at).slice(0, 10))}</time>`
    : '';
  const meta = [escapeHtml(r.media_type || ''),
                escapeHtml(r.file_size_display || ''),
                escapeHtml(r.source || '')]
    .filter(Boolean).join(' · ');
  // preview: raster through the authorized endpoint; documents get their
  // type stated textually — an honest card, no fake thumbnail
  const visual = (r.previewable && r.image_url)
    ? `<img class="rb-ref-thumb" src="${escapeHtml(r.image_url)}" alt="${name}" loading="lazy">`
    : `<span class="rb-ref-doc" aria-hidden="true">${escapeHtml(r.doc_type || 'FILE')}</span>`;
  const typeLine = (r.previewable && r.image_url) ? ''
    : `<span class="rb-ref-doc-note">${escapeHtml(r.doc_type || 'File')} document — no visual preview</span>`;
  const actions = r.open_url
    ? `<span class="rb-ref-actions">
         <a href="${escapeHtml(r.open_url)}" target="_blank" rel="noopener"
            aria-label="Open ${name}">Open</a>
         <a href="${escapeHtml(r.download_url || r.open_url)}"
            aria-label="Download ${name}">Download</a>
       </span>` : '';
  return `<li class="rb-ref-card">
      ${visual}
      <span class="rb-ref-meta">
        <span class="rb-ref-name" title="${name}">${name}</span>
        ${typeLine}
        <span class="rb-ref-detail">${meta}${date ? ' · ' : ''}${date}</span>
        <span class="rb-ref-badge">${status || 'REFERENCE ONLY'}</span>
      </span>
      ${actions}
    </li>`;
}
