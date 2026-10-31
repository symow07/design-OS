// === CONFIRM CONTAINER PROFILE + DECORATION ZONES (2B-1 contract UI) ===
// Renders the COMBINED container_profile/1.0 + container_decoration_zones/1.0
// confirmation (2B-3V UI correction). The old B4a screen showed only archetype
// cards + three sliders and posted a profile alone — the live contract (depth,
// per-field authority, zones, hashes, refusal codes) never reached the human.
// The primary action confirms profile AND zones together; the backend refuses
// with ordered codes when either is incomplete. Refusals NEVER reset the form.
//
// Confirm Profile UI-1 (2026-08-01): the editor is now driven by the
// server-rendered container_profile_editor_config/1.0 (choices, ranges,
// defaults, creation hints) — the browser carries no catalog of its own.
// It adds semantic archetype radios (incl. the honest non-confirmable
// "Other"), variant/closure invalidation that clears visibly instead of
// substituting, slider+number proportion controls, a deterministic local
// silhouette preview (canvas — no network, no provider), dirty tracking and
// Reset to Suggested Profile. Confirmation itself is unchanged 2B-3V.

var _editorConfig = null;      // container_profile_editor_config/1.0
var _editorInitial = null;     // snapshot for dirty/reset
var _editorNotices = {variant: '', cap: ''};

// §BH64(c)/§BH61(a): NOTHING FALLS BACK TO BOTTLE, IN THE BROWSER TOO. This
// opened as a cylindrical bottle with a screw cap before any task was loaded —
// the same defect the server config had, in the half the owner actually looks
// at. Nothing is chosen until something chooses it. [§BH70(1): and no size is
// either. The three NUMBERS that stood here were a bottle's — 110 x 40 x 40
// and a 0.42 neck — "so a palette opens as 40 wide and 110 tall". A form now
// opens at its OWN starting size, `nominal` in the one declaration, read by
// `_openingSizes` below.]
var _profileState = {archetype: null, variant: null, cap_style: null,
                     height_mm: null, width_mm: null, depth_mm: null, neck_ratio: null,
                     cap_width_mm: null, cap_depth_mm: null, cap_height_mm: null};
var _contractState = {record: null, zones: [], confirmed: {}, included: {}};

// Optional zones may be skipped instead of confirmed (correction item 6);
// the front/back print zones are the required decoration contract.
var _OPTIONAL_ZONE_TYPES = ['CAP_PRINT_ZONE', 'CAP_TOP_PRINT_ZONE',
                            'BOTTOM_CODE_ZONE'];
function _zoneIsOptional(z) {
  return _OPTIONAL_ZONE_TYPES.indexOf(z.zone_type) !== -1;
}

var _EDITOR_KEYS = ['archetype', 'variant', 'cap_style', 'height_mm',
                    'width_mm', 'depth_mm', 'neck_ratio'];

function _archetypeCfg(key) {
  const cfgs = (_editorConfig && _editorConfig.archetypes) || [];
  return cfgs.find(a => a.key === (key || _profileState.archetype)) || null;
}

// §BH70(1): THE SIZE KEYS A FORM IS MEASURED BY, and where it may go. The
// shared rows stop at 20 mm wide, so a 7 mm pencil could not be entered; a
// form's own `ranges` (served from the one declaration through `form_ranges`,
// which the server validates by too) widen them for that form only.
var _SIZE_KEYS = ['height_mm', 'width_mm', 'depth_mm'];

function _rangeFor(cfg, key) {
  const row = ((_editorConfig && _editorConfig.proportions) || []).find(p => p.key === key) || {};
  const own = (cfg && cfg.ranges && cfg.ranges[key]) || {};
  return {min: own.min !== undefined ? own.min : row.min, max: own.max !== undefined ? own.max : row.max};
}

// §BH70(1): the sizes a form OPENS at — each size the record gave, else the
// form's own starting size (`nominal`); a neck only where the form has one. A
// form with no drawing ("Other") keeps what it was given.
function _openingSizes(cfg, given) {
  const out = {};
  const nominal = (cfg && cfg.nominal) || {};
  // [his test day finding 2, 2026-09-29: a size the brief states in words ("50 mm across", "180 mm tall") opens the
  // step where the record gives none — the brief's hint, inside this form's own limits, confirmed only when he does]
  const brief = (_editorConfig && _editorConfig.brief_sizes) || {};
  _SIZE_KEYS.forEach(k => {
    const r = _rangeFor(cfg, k);
    const fromBrief = (typeof brief[k] === 'number' && brief[k] >= r.min && brief[k] <= r.max) ? brief[k] : null;
    out[k] = given[k] !== null && given[k] !== undefined ? given[k]
      : (fromBrief !== null ? fromBrief : (nominal[k] !== undefined ? nominal[k] : null));
  });
  const hasNeck = !!(cfg && Array.isArray(cfg.proportions) && cfg.proportions.indexOf('neck_ratio') !== -1);
  out.neck_ratio = hasNeck
    ? (given.neck_ratio !== null && given.neck_ratio !== undefined ? given.neck_ratio
       : (nominal.neck_ratio !== undefined ? nominal.neck_ratio : null))
    : null;
  return out;
}

function showConfirmProfile(data) {
  document.getElementById('profile-state').style.display = 'block';
  const po = data.packaging_output || {};
  const spec = po.spec_sheet || {};
  // Already confirmed (2B-3V resume-correction §5): the persisted combined
  // confirmation is authoritative — render its state, never an active
  // confirmation form. A failed reconstruction shows its code + a resume
  // action that re-POSTs idempotently (no re-merge, no new decision).
  if (spec.container_confirmation) {
    _renderConfirmedState(data, spec);
    return;
  }
  _editorConfig = data.container_profile_editor || null;
  const legacy = spec.container_profile || {};
  const record = spec['container_profile/1.0'] || null;
  const zoneSet = spec['container_decoration_zones/1.0'] || {};
  const fields = (record && record.fields) || {};
  const fv = (name, fallback) => {
    const f = fields[name];
    return (f && f.value !== null && f.value !== undefined) ? f.value : fallback;
  };

  _zoneProposalKey = null;           // his test day finding 2: a page opened afresh asks for its own areas
  _contractState = {taskId: data.id, record: record, zones: (zoneSet.zones || []).map(z => ({...z})),
                    zoneSetHash: zoneSet.zone_set_hash || '',
                    confirmed: {}, included: {}};
  _contractState.zones.forEach(z => {
    _contractState.confirmed[z.zone_id] =
      z.user_confirmation_state === 'USER_CONFIRMED';
    _contractState.included[z.zone_id] = true;      // opt out explicitly
  });

  // §BH64(c): THE `|| 'bottle'` IS GONE. With no stored record this line
  // handed the owner a bottle for whatever he was designing, which is exactly
  // what §BH61(a) removed from the server and did not remove from the page.
  // `_editorConfig.proposed` is NOT consulted here and that is deliberate:
  // `_proposed_profile()` reads the same `container_profile/1.0` record this
  // line already reads, so it can never supply an archetype when `record`
  // cannot. What the page was missing is the SENTENCE for the empty case,
  // `no_proposal_reason`, which is now shown where the form is blocked.
  const loadedArch = (record && record.archetype) || legacy.archetype || null;
  const archCfg = _archetypeCfg(loadedArch);
  _profileState = {
    archetype: loadedArch,
    // §BH71 PART 3: a lid the proposal says no variant draws is never given the form's first variant here either
    variant: fv('variant', legacy.variant) ||
      ((_editorConfig && _editorConfig.unknown_shape) ? null
        : (archCfg && archCfg.variants.length ? archCfg.variants[0].key : null)),
    cap_style: fv('cap_type', legacy.cap_style) ||
      (archCfg && archCfg.caps.length ? archCfg.caps[0].key : null),
    // §BH70(1): a size the record does not give is the loaded FORM's own
    // starting size — it was a bottle's `|| 110`, `|| 40` and `|| 0.42` for
    // every form — and a neck is loaded only for a form that has one.
    ..._openingSizes(archCfg, {
      height_mm: Number(fv('body_height_mm', legacy.height_mm)) || null,
      width_mm: Number(fv('body_width_mm', legacy.width_mm)) || null,
      depth_mm: Number(fv('body_depth_mm', legacy.depth_mm)) || null,
      neck_ratio: Number(fv('neck_ratio', legacy.neck_ratio)) || null}),
    cap_width_mm: fv('cap_width_mm', null),
    cap_depth_mm: fv('cap_depth_mm', null),
    cap_height_mm: fv('cap_height_mm', null),
  };
  // the values loaded when the editor opened — reset restores exactly these
  _editorInitial = {..._profileState};
  _editorNotices = {variant: '', cap: '', size: ''};
  // [his test blocker on design 122 at the shape step] what he set before the page was loaded again, kept, said so
  const kept = _keptEdits(data.id);
  if (kept && kept.profile.archetype === _profileState.archetype) {
    _profileState = {..._profileState, ...kept.profile};
    if (Array.isArray(kept.zones) && kept.zones.length) _contractState.zones = kept.zones.map(z => ({...z}));
    Object.assign(_contractState.confirmed, kept.confirmed || {});
    Object.assign(_contractState.included, kept.included || {});
    _editorNotices.size = 'Your sizes and ticks from before the page was loaded again are kept — not confirmed yet.';
  }
  // §BH71 PART 3: the sentence for a lid no variant draws, where the variant is chosen
  if (_editorConfig && _editorConfig.unknown_shape && !_profileState.variant) {
    _editorNotices.variant = _editorConfig.unknown_shape.sentence;
  }

  const view = document.getElementById('profile-view');
  view.innerHTML = `
    <h3 class="profile-title">Confirm its shape, sizes and print areas</h3>
    <p class="profile-sub">Check the form, the sizes and where the print goes. Nothing is
      drawn until you confirm the shape and every print area.</p>
    ${_hintsPanel()}
    <div class="profile-editor-grid">
      <div class="profile-controls">
        <div id="archetype-cards" class="archetype-cards" role="radiogroup"
             aria-label="Its form"></div>
        <div class="profile-choices">
          <div class="choice-group" role="group" aria-labelledby="variant-label">
            <span class="choice-label" id="variant-label">Variant</span>
            <div id="variant-chips" class="chip-row"></div>
            <p id="variant-note" class="choice-note" role="status"></p>
          </div>
          <div class="choice-group" role="group" aria-labelledby="cap-label">
            <span class="choice-label" id="cap-label">Cap or closure</span>
            <div id="cap-chips" class="chip-row"></div>
            <p id="cap-note" class="choice-note" role="status"></p>
          </div>
        </div>
        <div class="profile-sliders">
          <p class="proportion-note">${(_editorConfig && _editorConfig.proportion_note) ||
            'These controls define relative silhouette proportions, not manufacturing dimensions.'}</p>
          <div id="proportion-rows"></div>
        </div>
        <div class="editor-status">
          <p id="profile-dirty" class="profile-dirty" role="status"></p>
          <p id="profile-incomplete" class="profile-incomplete"></p>
          <button type="button" class="profile-reset" id="profile-reset"
                  aria-label="Back to the suggested shape" disabled
                  onclick="resetProfileEditor()">Back to the suggested shape</button>
        </div>
      </div>
      <div class="profile-preview-panel">
        <span class="preview-disclaimer">${(_editorConfig &&
          _editorConfig.preview_disclaimer) ||
          'A preview of the shape — not a production drawing'}</span>
        <canvas id="profile-preview-canvas" width="220" height="300"
                aria-hidden="true"></canvas>
        <p id="profile-preview-summary" class="preview-summary"></p>
      </div>
    </div>
    <div class="contract-block" id="cap-dims-block">
      <h4>The cap's sizes — only to print on the cap</h4>
      <p class="contract-meta">The cap has no size until these are given, and a print area on it cannot be
        confirmed without one. Leave them blank, and skip the cap's print area, if nothing is printed there.</p>
      <div class="cap-dim-row">
        ${_capInput('cap_width_mm', 'Cap width')}
        ${_capInput('cap_depth_mm', 'Cap depth')}
        ${_capInput('cap_height_mm', 'Cap height')}
      </div>
    </div>
    <div id="profile-authority" class="contract-block"></div>
    <div id="zone-proposals" class="contract-block"></div>
    <div id="confirm-blocked-note" class="contract-warn" hidden></div>
    <button class="btn-approve profile-confirm" id="confirm-profile-zones"
            onclick="openConfirmProfileDialog(${data.id})">
      Confirm the shape and print areas
    </button>
    <div id="profile-msg" class="profile-msg" tabindex="-1"></div>
    <dialog id="confirm-profile-dialog" class="confirm-profile-dialog"
            aria-modal="true" aria-labelledby="cpd-title"
            aria-describedby="cpd-authority">
      <h3 id="cpd-title">Confirm this shape?</h3>
      <dl id="cpd-summary" class="cpd-summary"></dl>
      <p id="cpd-authority" class="contract-meta">These sizes set the shape the design is drawn on. They are
        your confirmation of the concept's shape — not a supplier's manufacturing dimensions, which come
        separately. The preview is a picture of the shape, not a manufacturing drawing.</p>
      <p class="contract-meta">Confirming records your decision and starts drawing the design. It does not
        set manufacturing dimensions.</p>
      <div class="cpd-actions">
        <button type="button" id="cpd-cancel" autofocus>Cancel</button>
        <button type="button" id="cpd-review">Look again</button>
        <button type="button" id="cpd-confirm">Confirm and draw it</button>
      </div>
      <p id="cpd-busy" class="contract-meta" role="status" hidden>
        Confirming — recording your decision and starting the drawing…</p>
    </dialog>`;
  _renderArchetypeCards();
  _renderContextChips();
  _renderProportions();
  _renderAuthorityTable();
  _renderZoneProposals();
  _editorRefresh();
  _showLearnOffer();                  // §BH71 PART 3: under the sentence, once the editor is drawn
}

// --- initial hints (B4a creation form — INITIAL_HINTS_ONLY, §8) --------------

function _hintsPanel() {
  const hints = (_editorConfig && _editorConfig.initial_hints) || {};
  const labels = {container_type: 'Container type',
                  product_category: 'Product category',
                  capacity: 'Capacity', closure: 'Closure'};
  const parts = Object.keys(labels)
    .filter(k => hints[k])
    .map(k => `<span class="hint-chip">${labels[k]}:
        ${escapeHtml(hints[k])}</span>`);
  // his test day finding 2: the size the brief states in words, as its own hint
  const said = _editorConfig && _editorConfig.brief_sizes && _editorConfig.brief_sizes.said;
  if (said) parts.push(`<span class="hint-chip">Size, from your brief: ${escapeHtml(said)}</span>`);
  if (!parts.length) return '';
  return `<div class="contract-block profile-hints">
      <h4>Said when the design was started</h4>
      <p class="contract-meta">Hints only — they are not confirmed, and nothing below is confirmed until you
        check it.</p>
      <div class="hint-chip-row">${parts.join('')}</div>
    </div>`;
}

// --- confirmed / resume states (unchanged 2B-3V) ------------------------------

// UI-2B-2A: the completed reconstruction result — AI source-of-truth card
// + PNG preview-only card, rendered from the persisted result contract.
// Read-only: links go to the authorized artifact endpoint, nothing else.
function _reconResultHtml(result, g2r) {
  const ai = result.artifacts.ai;
  const png = result.artifacts.png;
  // VQR-2A §8: artifacts of a quality-failed reconstruction stay accessible
  // for audit, but are labeled inspection-only — never owner-approved
  // artwork, never "successful design".
  const inspectionOnly = !!(g2r && g2r.inspection_only);
  // [the owner's goal of 2026-09-25, (d): the file's size and when it was saved, in words; its media type and its
  // validation state kept for readers of code, folded]
  const meta = a => (a.file_size === null || a.file_size === undefined) ? ''
    : escapeHtml(a.file_size >= 1024 * 1024 ? `${(a.file_size / 1048576).toFixed(1)} MB`
      : `${(a.file_size / 1024).toFixed(1)} KB`);
  const record = a => [a.media_type, a.validation_state ? `validation ${a.validation_state}` : '']
    .filter(Boolean).map(escapeHtml).join(' · ');
  const when = result.artifacts.ai.created_at
    ? `saved <time datetime="${escapeHtml(ai.created_at)}">${escapeHtml(whenWords(ai.created_at))}</time>`
    : '';
  const pngBody = png.available
    ? `<img class="recon-preview-img" src="${escapeHtml(png.preview_url)}"
          alt="The drawn design, as a picture"
          onerror="this.closest('.recon-artifact-card').querySelector('.recon-preview-fallback').hidden = false; this.hidden = true;">
       <p class="recon-preview-fallback contract-warn" role="status" hidden>
         The picture could not be loaded — the editable file above is still good.</p>
       <span class="recon-artifact-actions">
         <a href="${escapeHtml(png.preview_url)}" target="_blank" rel="noopener"
            aria-label="Open PNG preview ${escapeHtml(png.filename || '')}">Open PNG</a>
         <a href="${escapeHtml(png.download_url)}"
            aria-label="Download PNG preview ${escapeHtml(png.filename || '')}">Download PNG</a>
       </span>`
    : `<p class="contract-warn" role="status">No picture was saved for this drawing — the editable file above
         is still good.</p>`;
  return `<section class="recon-result" aria-labelledby="recon-result-title">
      <h4 id="recon-result-title">The drawing's files</h4>
      ${inspectionOnly
        ? `<p class="inspection-only-banner" role="note">It has not passed its quality check — what it did not
             pass is said beside Approve</p>` : ''}
      <div class="recon-artifact-card recon-ai-card">
        <span class="artifact-role-badge">${inspectionOnly
          ? 'Not passed its quality check' : 'The editable file'}</span>
        <span class="recon-artifact-name">${escapeHtml(ai.filename || 'container.ai')}</span>
        <span class="recon-artifact-meta">.AI · ${meta(ai)}${when ? ' · ' : ''}${when}</span>
        ${record(ai) ? `<details class="tech"><summary>What the record says</summary><p>${record(ai)}</p></details>` : ''}
        <span class="recon-artifact-actions">
          <a href="${escapeHtml(ai.download_url)}"
             aria-label="Download AI source ${escapeHtml(ai.filename || '')}">Download .AI</a>
        </span>
        ${inspectionOnly
          ? `<p class="contract-warn">This is the drawing's editable file. It has not passed its quality
              check; approving it keeps what it did not pass with your approval.</p>`
          : `<p class="contract-meta">The .ai file is the design itself — drawn on the shape you confirmed,
          not a supplier's manufacturing drawing.</p>`}
      </div>
      <div class="recon-artifact-card recon-png-card">
        <span class="artifact-role-badge preview-badge">A picture of it</span>
        ${pngBody}
      </div>
    </section>`;
}

// UI-2B-1: owner-facing lifecycle labels for the coarse states the
// backend actually persists. No fabricated phases, no fake percentages.
var _LIFECYCLE_LABELS = {
  QUEUED: 'Waiting to be drawn',
  RUNNING: 'Being drawn',
  COMPLETED: 'Drawn',
  FAILED: 'The drawing did not finish',
  RECONSTRUCTION_STATUS_INCONSISTENT:
    'Its records disagree about where the drawing stands',
};

function _reconStatusHtml(rs, taskId, hasResult) {
  const label = _LIFECYCLE_LABELS[rs.lifecycle_state] || rs.lifecycle_state;
  const active = rs.lifecycle_state === 'QUEUED'
    || rs.lifecycle_state === 'RUNNING';
  const art = rs.artifacts || {ai: {}, png: {}};
  const artLine =
    `The editable file: ${art.ai.available ? 'ready' : 'not ready yet'} · ` +
    `its picture: ${art.png.available ? 'ready' : 'not ready yet'}`;
  const times = [
    rs.queued_at ? `queued <time datetime="${escapeHtml(rs.queued_at)}">${escapeHtml(whenWords(rs.queued_at))}</time>` : '',
    rs.started_at ? `started <time datetime="${escapeHtml(rs.started_at)}">${escapeHtml(whenWords(rs.started_at))}</time>` : '',
    rs.finished_at ? `finished <time datetime="${escapeHtml(rs.finished_at)}">${escapeHtml(whenWords(rs.finished_at))}</time>` : '',
  ].filter(Boolean).join(' · ');
  let body = '';
  if (rs.lifecycle_state === 'QUEUED') {
    body = `<p class="contract-meta">Your confirmation is recorded and the drawing is queued. It has not
      finished yet.</p>
      <details class="tech"><summary>What the record says</summary><p>dispatched
        (${escapeHtml(rs.dispatch_status || '')})</p></details>`;
  } else if (rs.lifecycle_state === 'RUNNING') {
    body = rs.phase
      ? `<details class="tech"><summary>What the record says</summary><p>phase
           <code>${escapeHtml(String(rs.phase))}</code></p></details>`
      : '';
  } else if (rs.lifecycle_state === 'COMPLETED') {
    body = hasResult
      ? `<p class="contract-meta">Its files are below.</p>`
      : `<p class="contract-meta">Its files are not shown here yet.</p>`;
  } else if (rs.lifecycle_state === 'FAILED' && rs.error) {
    body = `<div class="recon-error" role="alert">
        ${stopReasonsHtml(rs.error.reasons)}
        <p class="contract-warn">The shape you confirmed and your decision are kept.</p>
        <details class="tech"><summary>What the record says</summary>
          <p class="contract-meta recon-error-msg"><code>${escapeHtml(rs.error.code)}</code>
            ${escapeHtml(rs.error.message || '')}</p></details>
      </div>
      ${_retryControlHtml(rs, taskId)}`;
  } else if (rs.lifecycle_state === 'RECONSTRUCTION_STATUS_INCONSISTENT') {
    body = `<p class="contract-warn">Its records disagree about where the drawing stands. The shape you
      confirmed and your decision are intact.</p>
      <details class="tech"><summary>What the record says</summary><p><code>RECONSTRUCTION_STATUS_INCONSISTENT</code>
      — the saved records do not describe one clean state.</p></details>
      ${_retryControlHtml(rs, taskId)}`;
  }
  return `<div class="recon-status-panel">
      <p id="recon-status" class="recon-status-label" role="status">
        ${escapeHtml(label)}</p>
      ${active ? `<progress class="recon-progress"
          aria-label="The drawing, in progress"></progress>`
        : ''}
      ${body}
      <p class="contract-meta recon-artifacts">${artLine}</p>
      ${times ? `<p class="contract-meta recon-times">${times}</p>` : ''}
      <p id="recon-refresh-note" class="contract-warn" role="status"
         hidden></p>
    </div>`;
}

function _renderConfirmedState(data, spec) {
  const conf = spec.container_confirmation || {};
  // [B1, the clean-up of 2026-10-04] who confirmed it, as the record says it, in the server's words
  // (container_confirmation_provenance) — it read "Confirmed by a person" whoever did; every name escaped
  const prov = data.container_confirmation_provenance || {};
  const rec = spec['container_profile/1.0'] || {};
  const zs = spec['container_decoration_zones/1.0'] || {};
  const err = spec.generation_error || '';
  const running = data.status === 'generating_dieline';
  const rs = data.container_reconstruction_status || null;
  const result = data.container_reconstruction_result || null;
  _lastReconStatus = rs;
  // §17: an identical snapshot must not rebuild the DOM (no repeated
  // announcements, no focus churn). The signature includes the task id so
  // a task switch always repaints.
  const view = document.getElementById('profile-view');
  const sig = 'confirmed|' + data.id + '|' + (result ? 'result|' +
      result.artifacts.png.available : 'noresult') + '|' + (rs
    ? [rs.lifecycle_state, rs.phase, rs.attempt,
       (rs.error || {}).code || '', rs.updated_at,
       (rs.artifacts || {ai: {}}).ai.available,
       (rs.artifacts || {png: {}}).png.available].join('|')
    : ['legacy', data.status, err].join('|'));
  if (view.dataset.confirmedSig === sig
      && document.getElementById('recon-status')) {
    return;
  }
  view.dataset.confirmedSig = sig;
  let stateHtml;
  if (rs) {
    stateHtml = _reconStatusHtml(rs, data.id, !!result);
  } else if (running) {
    stateHtml = `<p class="contract-meta">Being drawn…</p>
      <details class="tech"><summary>What the record says</summary><p>job
        <code>${escapeHtml(((spec.container_resume || {}).celery_task_id || '').slice(0, 12))}</code></p></details>`;
  } else if (err) {
    stateHtml = `<p class="contract-warn">The drawing did not finish.</p>
      ${stopReasonsHtml(data.drawing_stop_words)}
      <details class="tech"><summary>What the record says</summary><p><code>${escapeHtml(err)}</code></p></details>
      <button class="btn-approve profile-confirm" id="resume-reconstruction"
              onclick="submitContainerResume(${data.id})">
        Draw it again
      </button>`;
  } else {
    stateHtml = `<p class="contract-meta">Drawn — waiting for your review.</p>`;
  }
  // UI-2A §18: the PERSISTED confirmed values, never the mutable editor —
  // a refresh lands here again because the render is state-dispatched.
  const fields = rec.fields || {};
  const fv = name => {
    const f = fields[name] || {};
    return (f.value === null || f.value === undefined || f.value === '')
      ? '—' : f.value;
  };
  // [the owner's goal of 2026-09-25, (d): the confirmed form, variant and closure by the names the editor gave them
  // (container_profile_editor), never the record's keys ("rounded_rect"); and only the proportions its form has —
  // §BH61(b), "no neck proportion on a hinged case"]
  const forms = ((data.container_profile_editor || {}).archetypes) || [];
  const form = rec.archetype || fv('archetype');
  const fcfg = forms.find(a => a.key === form) || {};
  const named = (list, key) => ((list || []).find(x => x.key === key) || {}).label || key;
  const has = key => !Array.isArray(fcfg.proportions) || fcfg.proportions.includes(key);
  const confirmedRows = [
    ['Form', fcfg.label || form],
    ['Variant', named(fcfg.variants, rec.variant || fv('variant'))],
    ['Closure', named(fcfg.caps, fv('cap_type'))],
    ['Overall Height', `${fv('body_height_mm')} mm`],
    // [his answer after test day finding 3, (4) round: a tube's width is its round diameter — named as its form names it]
    [(fcfg.labels && fcfg.labels.width_mm) || 'Body Width', `${fv('body_width_mm')} mm`],
    ['Body Depth', `${fv('body_depth_mm')} mm`],
    has('neck_ratio') ? ['Neck Proportion', fv('neck_ratio')] : null,
  ].filter(Boolean).map(([k, v]) => `<div class="cpd-row"><dt>${escapeHtml(k)}</dt>` +
                    `<dd>${escapeHtml(String(v))}</dd></div>`).join('');
  document.getElementById('profile-view').innerHTML = `
    <h3 class="profile-title">Its shape, sizes and print areas — confirmed</h3>
    <p class="confirmed-authority-badge">${escapeHtml(prov.words || 'Not confirmed by a person')} — for the design, not for manufacture</p>
    <dl class="cpd-summary confirmed-profile-summary">${confirmedRows}</dl>
    <p class="contract-meta">These sizes set the shape the design is drawn on. They are not a supplier's
      manufacturing dimensions.</p>
    <details class="tech"><summary>The technical record</summary>
    <p class="contract-meta">schema ${rec.schema_version || 'container_profile/1.0'}
      · authority ${escapeHtml(conf.authority || 'HUMAN_CONFIRMED_CONCEPT_ONLY')}</p>
    <p class="contract-meta">confirmed by <strong>${escapeHtml(conf.confirmed_by || '—')}</strong>
      at ${escapeHtml(conf.confirmed_at || '—')}${conf.on_word_of
        ? `, on the word of ${escapeHtml(conf.on_word_of)}` : ''}<br>
      profile hash <code>${(rec.profile_hash || '').slice(0, 16)}</code>
      · zone set <code>${(zs.zone_set_hash || '').slice(0, 16)}</code>
      · combined <code>${(conf.combined_hash || '').slice(0, 16)}</code></p>
    <p class="contract-meta">zones: ${(zs.zones || []).map(z =>
        `${z.zone_id} (${z.user_confirmation_state})`).join(' · ') || '—'}</p>
    </details>
    ${stateHtml}
    ${result ? _reconResultHtml(result, data.container_gate2_readiness) : ''}
    ${rs ? _retryDialogHtml(rs, data.id) : ''}
    <div id="profile-msg" class="profile-msg" tabindex="-1"></div>`;
}

// --- owner-controlled retry (UI-2B-2B §9-§12) --------------------------------
// The control renders ONLY from server eligibility; the dialog is the one
// door to the resume POST, and every outcome is single-shot.

var _lastReconStatus = null;
var _retryDialogSettled = false;
var _retryInFlight = false;

function _retryControlHtml(rs, taskId) {
  const retry = rs.retry || {};
  if (retry.eligible) {
    return `<button class="btn-approve profile-confirm" id="open-retry-dialog"
        onclick="openRetryDialog(${taskId})">
        Draw it again…
      </button>`;
  }
  if (retry.recovery === 'TECHNICAL_INTERVENTION_REQUIRED') {
    return `<p class="contract-warn">It cannot be drawn again from here: someone who knows the code must
      look first. The shape you confirmed and your decision are intact.</p>
      <details class="tech"><summary>What the record says</summary><p><code>TECHNICAL_INTERVENTION_REQUIRED</code>
      (${escapeHtml(retry.reason_code || '')})</p></details>`;
  }
  return '';
}

function _retryDialogHtml(rs, taskId) {
  const retry = rs.retry || {};
  if (!retry.eligible) return '';
  const art = rs.artifacts || {ai: {}, png: {}};
  return `<dialog id="retry-dialog" class="confirm-profile-dialog"
      aria-modal="true" aria-labelledby="rtd-title"
      aria-describedby="rtd-consequence">
    <h3 id="rtd-title">Draw it again?</h3>
    <p id="rtd-consequence" class="contract-meta">The shape you confirmed will not change, and no new decision
      is recorded — your confirmation (decision #${escapeHtml(String(retry.existing_gate_decision_id || ''))})
      is used as it stands. What the failed attempt left stays in its history. The design is drawn again from
      the same shape. This does not create any manufacturing authority.</p>
    <details class="tech"><summary>What the record says</summary>
      <p class="contract-meta"><code>${escapeHtml((rs.error || {}).code || retry.reason_code || '')}</code>
      ${escapeHtml((rs.error || {}).message || '')}</p></details>
    <p class="contract-meta">The editable file:
      ${art.ai.available ? 'ready' : 'not ready'} · its picture:
      ${art.png.available ? 'ready' : 'not ready'}</p>
    <div class="cpd-actions">
      <button type="button" id="rtd-cancel" autofocus>Cancel</button>
      <button type="button" id="rtd-review">Look at the confirmed shape</button>
      <button type="button" id="rtd-retry">Draw it again</button>
    </div>
    <p id="rtd-busy" class="contract-meta" role="status" hidden>
      Drawing it again…</p>
  </dialog>`;
}

function openRetryDialog(taskId) {
  const dlg = document.getElementById('retry-dialog');
  const rs = _lastReconStatus;
  // §11: eligibility from the LATEST snapshot, never a stale button
  if (!dlg || dlg.open || _retryInFlight
      || !(rs && rs.retry && rs.retry.eligible)) return;
  _retryDialogSettled = false;
  document.getElementById('rtd-busy').hidden = true;
  ['rtd-cancel', 'rtd-review', 'rtd-retry'].forEach(id => {
    document.getElementById(id).disabled = false;
  });
  if (!dlg.dataset.bound) {
    dlg.dataset.bound = '1';
    document.getElementById('rtd-cancel').addEventListener('click',
      () => _settleRetryDialog('cancel', taskId));
    document.getElementById('rtd-review').addEventListener('click',
      () => _settleRetryDialog('review', taskId));
    document.getElementById('rtd-retry').addEventListener('click',
      () => _settleRetryDialog('retry', taskId));
    dlg.addEventListener('cancel', ev => {
      ev.preventDefault();
      if (!_retryInFlight) _settleRetryDialog('cancel', taskId);
    });
    dlg.addEventListener('keydown', ev => {
      if (ev.key !== 'Tab') return;
      const first = document.getElementById('rtd-cancel');
      const last = document.getElementById('rtd-retry');
      if (ev.shiftKey && document.activeElement === first) {
        ev.preventDefault(); last.focus();
      } else if (!ev.shiftKey && document.activeElement === last) {
        ev.preventDefault(); first.focus();
      }
    });
  }
  dlg.showModal();
  document.getElementById('rtd-cancel').focus();
}

function _settleRetryDialog(action, taskId) {
  if (_retryDialogSettled || _retryInFlight) return;
  const dlg = document.getElementById('retry-dialog');
  if (action === 'cancel') {
    _retryDialogSettled = true;
    dlg.close();
    const btn = document.getElementById('open-retry-dialog');
    if (btn) btn.focus();
    return;
  }
  if (action === 'review') {
    _retryDialogSettled = true;
    dlg.close();
    const summary = document.querySelector('.confirmed-profile-summary');
    if (summary) {
      summary.setAttribute('tabindex', '-1');
      summary.focus();
    }
    return;
  }
  _retryDialogSettled = true;
  _retryInFlight = true;
  ['rtd-cancel', 'rtd-review', 'rtd-retry'].forEach(id => {
    document.getElementById(id).disabled = true;
  });
  document.getElementById('rtd-busy').hidden = false;
  submitContainerResume(taskId);
}

function _closeRetryDialog() {
  const dlg = document.getElementById('retry-dialog');
  if (dlg && dlg.open) dlg.close();
  _retryInFlight = false;
}

async function submitContainerResume(taskId) {
  const msg = document.getElementById('profile-msg');
  msg.textContent = 'Drawing it again…';
  let res;
  try {
    res = await fetch(`/api/tasks/${taskId}/confirm_container_profile/`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCsrf()},
      body: JSON.stringify({profile: {}}),
    });
  } catch (err) {
    // §12: the POST may or may not have landed — reconcile through the
    // authoritative status before permitting anything else; never re-POST
    // blindly
    _closeRetryDialog();
    try {
      const check = await fetch(`/api/tasks/${taskId}/status/`);
      const state = await check.json();
      const rs = state.container_reconstruction_status || {};
      if (rs.lifecycle_state === 'QUEUED'
          || rs.lifecycle_state === 'RUNNING') {
        loadTask(taskId);              // the retry WAS accepted
        return;
      }
      if (rs.retry && rs.retry.eligible) {
        msg.textContent = 'The retry request failed before an answer '
          + 'arrived and no new attempt is running — you can retry again.';
      } else {
        msg.textContent = 'RETRY_STATE_UNRESOLVED — the retry outcome '
          + 'could not be determined. Reload the task before trying again.';
      }
    } catch (err2) {
      msg.textContent = 'RETRY_STATE_UNRESOLVED — the connection failed '
        + 'and the current state could not be read. Reload the task.';
    }
    msg.focus();
    return;
  }
  _closeRetryDialog();
  const data = await res.json().catch(() => ({}));
  if (res.ok) { loadTask(taskId); return; }
  msg.textContent = data.error || 'Resume refused.';
  msg.focus();
}

// --- the shape step in words (the owner's goal of 2026-09-25, (d)): what the screen says for each code the
// record holds; a code with no words here is shown as the record writes it, lower-cased and spaced — never hidden
var ZONE_WORDS = {
  FRONT_PRINT_ZONE: 'Front print area', BACK_PRINT_ZONE: 'Back print area',
  LEFT_SIDE_PRINT_ZONE: 'Left side print area', RIGHT_SIDE_PRINT_ZONE: 'Right side print area',
  WRAP_LABEL_ZONE: 'Wrap-around label', SCREEN_PRINT_ZONE: 'Screen-printed area', PAD_PRINT_ZONE: 'Pad-printed area',
  HOT_STAMP_ZONE: 'Foil-stamped area', CAP_PRINT_ZONE: 'Cap print area', CAP_TOP_PRINT_ZONE: 'Cap top print area',
  // [§BH71 (0b): it read 'Code on the bottom' — a compact's is on its base's underside and a pencil's on its barrel]
  NECK_BAND_ZONE: 'Neck band', SHRINK_SLEEVE_ZONE: 'Shrink sleeve', BOTTOM_CODE_ZONE: 'Batch code',
};
var SURFACE_WORDS = {
  BODY_FRONT: "the body's front", BODY_BACK: "the body's back", BODY_LEFT: "the body's left side",
  BODY_RIGHT: "the body's right side", BODY_WRAP: 'around the body', SHOULDER: 'the shoulder', NECK: 'the neck',
  CAP_FRONT: "the cap's front", CAP_TOP: "the cap's top", CAP_WRAP: 'around the cap', BOTTOM: 'the bottom',
  CRIMP_ZONE: 'the crimped end', LID_TOP: "the lid's top", LID_EDGE: "the lid's edge", BASE_BOTTOM: "the base's underside",
  BASE_EDGE: "the base's edge",
};
var CURVE_WORDS = {
  FLAT: 'flat', CYLINDRICAL: 'curved all round', TAPERED_CYLINDRICAL: 'curved and tapering', OVAL: 'oval',
  RECTANGULAR_WITH_ROUNDED_CORNERS: 'rounded rectangle', CUSTOM_PROFILE: 'its own profile', UNKNOWN: 'not known yet',
};
var METHOD_WORDS = {
  screen_printing: 'screen printing', pad_printing: 'pad printing', hot_stamping: 'foil stamping',
  adhesive_label: 'a stuck-on label', wrap_label: 'a wrap label', shrink_sleeve: 'a shrink sleeve', emboss: 'embossing',
  deboss: 'debossing', BOTTOM_INKJET_CODE: 'an inkjet batch code',            // [§BH71 (0b): '… on the bottom']
};
function codeWords(map, code) {
  return map[code] || String(code || '').toLowerCase().replace(/_/g, ' ');
}

// --- profile authority table (container_profile/1.0) ------------------------

var _FIELD_ORDER = [
  'archetype', 'variant', 'body_width_mm', 'body_depth_mm', 'body_height_mm',
  'neck_ratio', 'cap_type', 'cap_width_mm', 'cap_depth_mm', 'cap_height_mm',
  'body_material', 'cap_material', 'body_transparency', 'body_opacity',
  'body_base_color', 'cap_color', 'front_orientation', 'back_orientation',
  'manufacturer_constraints',
];

function _badge(text, cls) {
  return `<span class="authority-badge ${cls || ''}">${text}</span>`;
}

function _sourceBadge(f) {
  const src = (f && f.source) || 'UNKNOWN';
  const ver = (f && f.verification) || 'MISSING';
  const srcLabel = src === 'VERIFIED_PRODUCT_RECORD'
    ? 'PRODUCT_RECORD · AS_RECORDED' : src;
  const cls = src === 'VERIFIED_PRODUCT_RECORD' ? 'src-record'
    : (src === 'UNKNOWN' ? 'src-unknown' : 'src-inferred');
  return _badge(srcLabel, cls) + ' ' + _badge(ver, 'ver-' + ver.toLowerCase());
}

function _renderAuthorityTable() {
  const host = document.getElementById('profile-authority');
  const rec = _contractState.record;
  if (!rec) {
    host.innerHTML = `<p class="contract-warn">This design has no recorded shape yet, so where its values came
      from cannot be shown.</p>
      <details class="tech"><summary>What the record says</summary><p>No <code>container_profile/1.0</code> record
      is saved for this design.</p></details>`;
    return;
  }
  const fields = rec.fields || {};
  const rows = _FIELD_ORDER.map(name => {
    const f = fields[name] || {};
    let v = f.value;
    if (v === null || v === undefined || v === '') v = '—';
    if (typeof v === 'object') v = JSON.stringify(v);
    return `<tr><td class="fname">${name}</td>
      <td class="fval">${String(v).slice(0, 90)}</td>
      <td>${_sourceBadge(f)}</td></tr>`;
  }).join('');
  host.innerHTML = `
    <details class="tech"><summary>Where each value came from — the record</summary>
      <h4>Container profile — container_profile/1.0</h4>
      <p class="contract-meta">profile hash <code>${(rec.profile_hash || '').slice(0, 16)}</code>
        · state <strong>${rec.confirmation_state || 'UNCONFIRMED'}</strong></p>
      <table class="authority-table"><tbody>${rows}</tbody></table>
    </details>`;
}

// --- decoration-zone proposals (container_decoration_zones/1.0) --------------

function _renderZoneProposals() {
  const host = document.getElementById('zone-proposals');
  const zones = _contractState.zones;
  if (!zones.length) {
    host.innerHTML = `<p class="contract-warn">No print areas are proposed for this shape, so it cannot be
      confirmed yet.</p>
      <details class="tech"><summary>What the record says</summary><p>No <code>container_decoration_zones/1.0</code>
      zones are saved for this design.</p></details>`;
    return;
  }
  host.innerHTML = `
    <h4>Where the print goes</h4>
    <p class="contract-meta">Confirm each print area that is needed; an optional one may be skipped.</p>
    <details class="tech"><summary>What the record says</summary><p><code>container_decoration_zones/1.0</code>
      · zone set hash <code>${escapeHtml((_contractState.zoneSetHash || '').slice(0, 16))}</code></p></details>
    <div class="zone-cards">` + zones.map(z => {
    const optional = _zoneIsOptional(z);
    const included = _contractState.included[z.zone_id] !== false;
    const unknownCurve = z.curvature_type === 'UNKNOWN';
    return `
      <div class="zone-card ${_contractState.confirmed[z.zone_id] && included ? 'zone-confirmed' : ''} ${included ? '' : 'zone-skipped'}">
        <div class="zone-head">
          <strong>${escapeHtml(codeWords(ZONE_WORDS, z.zone_type))}</strong>
          <span class="zone-need">${optional ? 'Optional' : 'Needed'}</span>
        </div>
        <div class="zone-grid">
          <span>on <strong>${escapeHtml(codeWords(SURFACE_WORDS, z.parent_surface))}</strong>, ${escapeHtml(codeWords(CURVE_WORDS, z.curvature_type))}</span>
          <span>${z.width} × ${z.height} ${escapeHtml(z.units || 'mm')}, placed at ${z.x}, ${z.y} ${escapeHtml(z.units || 'mm')} on it</span>
          <span>artwork kept ${z.safe_margin_mm} mm inside its edge, covering up to ${(z.max_artwork_coverage * 100).toFixed(0)}% of it</span>
          <span>printed by ${escapeHtml((z.permitted_techniques || []).map(t => codeWords(METHOD_WORDS, t)).join(' or ') || '—')}</span>
        </div>
        <details class="tech"><summary>What the record says</summary><p><code>${escapeHtml(z.zone_type)}</code>
          <code>${escapeHtml(z.zone_id)}</code> · ${optional ? 'OPTIONAL' : 'REQUIRED'}
          · ${escapeHtml(z.verification || 'INFERRED_NONAUTHORITATIVE')} · surface ${escapeHtml(z.parent_surface)}
          · curvature ${escapeHtml(z.curvature_type)} · ${escapeHtml((z.permitted_techniques || []).join(', '))}
          · zone hash <code>${escapeHtml((z.zone_hash || '').slice(0, 12))}</code></p></details>
        ${unknownCurve ? `<p class="contract-warn">Its surface has no size yet — give the cap's sizes above, or skip
          this print area.</p>` : ''}
        ${optional ? `<label class="zone-confirm-row">
          <input type="checkbox" data-zone="${z.zone_id}"
                 ${included ? 'checked' : ''} onchange="toggleZoneInclude(this)">
          Include this optional print area
        </label>` : ''}
        <label class="zone-confirm-row" ${included ? '' : 'style="opacity:.4"'}>
          <input type="checkbox" data-zone="${z.zone_id}"
                 ${_contractState.confirmed[z.zone_id] ? 'checked' : ''}
                 ${included ? '' : 'disabled'}
                 onchange="toggleZoneConfirm(this)">
          I confirm this print area
        </label>
      </div>`;
  }).join('') + `</div>`;
}

function toggleZoneConfirm(box) {
  _contractState.confirmed[box.dataset.zone] = box.checked;
  _renderZoneProposals();
  _keepEdits();
}

function toggleZoneInclude(box) {
  _contractState.included[box.dataset.zone] = box.checked;
  _renderZoneProposals();
  _keepEdits();
}

// [his test blocker on design 122 at the shape step, 2026-10-08: "a confirm either moves on, or stays with my values"]
// what he set at the shape step — its sizes, its areas and his ticks — kept in this tab until it is confirmed, so a
// page loaded again before then opens with them, said so; never the record's, which only a confirm writes
function _keptKey(taskId) { return 'bbrose.shape.' + taskId; }

function _keepEdits() {
  if (!_contractState.taskId || !_profileState) return;
  // nothing set yet — the record's own values, nothing ticked — is nothing to keep
  const ticked = Object.keys(_contractState.confirmed).some(k => _contractState.confirmed[k]);
  if (!ticked && JSON.stringify(_profileState) === JSON.stringify(_editorInitial)) {
    _forgetEdits(_contractState.taskId);
    return;
  }
  try {
    sessionStorage.setItem(_keptKey(_contractState.taskId), JSON.stringify({
      profile: _profileState, zones: _contractState.zones, confirmed: _contractState.confirmed,
      included: _contractState.included}));
  } catch (e) { /* storage refused: the page still works, a reload opens on the record */ }
}

function _keptEdits(taskId) {
  try {
    const kept = JSON.parse(sessionStorage.getItem(_keptKey(taskId)) || 'null');
    return (kept && kept.profile && typeof kept.profile === 'object') ? kept : null;
  } catch (e) { return null; }
}

function _forgetEdits(taskId) {
  try { sessionStorage.removeItem(_keptKey(taskId)); } catch (e) { /* nothing kept */ }
}

// --- shared visual controls ---------------------------------------------------

function _capInput(key, label) {
  const v = _profileState[key];
  return `<label class="cap-dim-input">${label}
      <input type="number" min="1" max="120" step="0.5" data-cap-key="${key}"
             value="${v === null || v === undefined ? '' : v}"
             placeholder="— mm" onchange="setCapDim(this)"> mm
    </label>`;
}

function setCapDim(input) {
  const v = parseFloat(input.value);
  _profileState[input.dataset.capKey] = isNaN(v) ? null : v;
  _scheduleZoneProposal();                // his test day finding 2: a cap's size bounds the cap's print area
}

function _proportionRow(p) {
  const v = _profileState[p.key];
  return `<div class="slider-row">
      <label for="sl-${p.key}">${p.label}
        <span id="sl-val-${p.key}">${v}${p.unit}</span></label>
      <div class="slider-pair">
        <input type="range" id="sl-${p.key}" min="${p.min}" max="${p.max}"
               step="${p.step}" value="${v}" data-key="${p.key}"
               data-unit="${p.unit}" aria-label="${p.label}"
               aria-valuetext="${v}${p.unit ? ' ' + p.unit : ''}">
        <input type="number" id="num-${p.key}" min="${p.min}" max="${p.max}"
               step="${p.step}" value="${v}" data-key="${p.key}"
               data-unit="${p.unit}" aria-label="${p.label} value">
      </div>
    </div>`;
}

function _renderArchetypeCards() {
  const host = document.getElementById('archetype-cards');
  const cfgs = (_editorConfig && _editorConfig.archetypes) || [];
  if (!cfgs.length) {
    host.innerHTML = `<p class="contract-warn">Profile editor configuration
      is unavailable — reload the task.</p>`;
    return;
  }
  host.innerHTML = cfgs.map(a => {
    const checked = a.key === _profileState.archetype;
    // §BH64(d)3: THE ICON IS DRAWN FROM THE FORM'S OWN SILHOUETTE. There were
    // three PNGs under `static/img/containers/` — bottle, jar, tube — so the
    // compact's `<img>` was a 404 and its card was blank. An icon is now this
    // form's silhouette drawn at its declared `nominal` proportions, which is
    // the owner's "so the next archetype gets one by construction": a form
    // that exists has an icon, and no file can be missing. "Other" keeps the
    // honest `?` it has always had, because it has no silhouette to draw.
    const icon = a.confirmable
      ? `<canvas class="archetype-icon" width="150" height="200"
                 aria-hidden="true" data-icon="${a.key}"></canvas>`
      : `<span class="archetype-icon-other" aria-hidden="true">?</span>`;
    return `
    <button type="button" role="radio" aria-checked="${checked}"
            tabindex="${checked ? 0 : -1}"
            class="archetype-card ${checked ? 'active' : ''}"
            data-archetype="${a.key}">
      ${icon}
      <span class="archetype-name">${escapeHtml(a.label)}
        <span class="card-check" aria-hidden="true">${checked ? '✓ selected' : ''}</span></span>
      <span class="archetype-desc">${escapeHtml(a.description || '')}</span>
    </button>`;
  }).join('');
  host.querySelectorAll('canvas.archetype-icon').forEach(c => {
    const a = cfgs.find(x => x.key === c.dataset.icon);
    if (!a) return;
    _drawSilhouette(c.getContext('2d'), Object.assign(
      {archetype: a.key,
       variant: (a.variants && a.variants[0]) ? a.variants[0].key : null,
       cap_style: (a.caps && a.caps[0]) ? a.caps[0].key : null},
      a.nominal || {}), c.width, c.height);
  });
  const cards = Array.from(host.querySelectorAll('.archetype-card'));
  if (!cards.some(c => c.getAttribute('aria-checked') === 'true') && cards[0]) {
    cards[0].tabIndex = 0;
  }
  cards.forEach((card, idx) => {
    card.addEventListener('click', () => _selectArchetype(card.dataset.archetype));
    card.addEventListener('keydown', ev => {
      let next = null;
      if (ev.key === 'ArrowRight' || ev.key === 'ArrowDown') {
        next = cards[(idx + 1) % cards.length];
      } else if (ev.key === 'ArrowLeft' || ev.key === 'ArrowUp') {
        next = cards[(idx - 1 + cards.length) % cards.length];
      } else if (ev.key === ' ' || ev.key === 'Enter') {
        ev.preventDefault();
        _selectArchetype(card.dataset.archetype);
        return;
      }
      if (next) {
        ev.preventDefault();
        _selectArchetype(next.dataset.archetype, true);
      }
    });
  });
}

function _selectArchetype(key, focusCard) {
  if (key === _profileState.archetype) {
    if (focusCard) _focusArchetype(key);
    return;
  }
  const left = _archetypeCfg(_profileState.archetype);
  _profileState.archetype = key;
  const cfg = _archetypeCfg(key) || {variants: [], caps: [], label: key};
  const validVariants = cfg.variants.map(v => v.key);
  const validCaps = cfg.caps.map(c => c.key);
  _editorNotices = {variant: '', cap: ''};
  // §6/§7: a still-valid selection is preserved; an invalid one is CLEARED
  // visibly — never silently replaced with something the owner did not pick
  if (_profileState.variant && !validVariants.includes(_profileState.variant)) {
    _editorNotices.variant = validVariants.length
      ? `Variant "${_profileState.variant}" does not apply to ${cfg.label} — choose a variant.`
      : 'No predefined variant applies to a custom form.';
    _profileState.variant = null;
  } else if (!validVariants.length) {
    _editorNotices.variant = 'No predefined variant applies to a custom form.';
    _profileState.variant = null;
  }
  if (_profileState.cap_style && !validCaps.includes(_profileState.cap_style)) {
    _editorNotices.cap = validCaps.length
      ? `Closure "${_profileState.cap_style}" does not apply to ${cfg.label} — choose a closure.`
      : 'No predefined closure applies to a custom form.';
    _profileState.cap_style = null;
  } else if (!validCaps.length) {
    _editorNotices.cap = 'No predefined closure applies to a custom form.';
    _profileState.cap_style = null;
  }
  // §BH70(1): THE SIZES FOLLOW THE FORM. They stayed a bottle's 110 x 40 when a
  // palette or a pencil was chosen. A size is kept only when it was given for
  // THIS product — by its record, its product row or a person — and fits the
  // new form; the form being left's own starting size carries nothing about the
  // product, and a size outside the new form's limits cannot be entered for it.
  // Either way the new form's starting size is used, and the page says so.
  _editorNotices.size = '';
  if (cfg.nominal) {
    const leftNominal = (left && left.nominal) || {};
    const moved = [];
    _SIZE_KEYS.forEach(k => {
      const v = _profileState[k];
      const r = _rangeFor(cfg, k);
      const fits = v !== null && v !== undefined && v >= r.min && v <= r.max;
      if (!fits || v === leftNominal[k]) {
        if (_profileState[k] !== cfg.nominal[k]) moved.push(k);
        _profileState[k] = cfg.nominal[k];
      }
    });
    const hasNeck = cfg.proportions.indexOf('neck_ratio') !== -1;
    if (!hasNeck) _profileState.neck_ratio = null;
    else if (_profileState.neck_ratio === null || _profileState.neck_ratio === undefined) {
      _profileState.neck_ratio = cfg.nominal.neck_ratio;
    }
    if (moved.length) {
      _editorNotices.size = `Sizes set to a ${cfg.label.toLowerCase()}'s starting size — change them to your product's.`;
    }
  }
  _renderArchetypeCards();
  _renderContextChips();
  _renderProportions();
  _editorRefresh();
  if (focusCard) _focusArchetype(key);
}

function _focusArchetype(key) {
  const card = document.querySelector(
    `.archetype-card[data-archetype="${key}"]`);
  if (card) card.focus();
}

function _renderContextChips() {
  const cfg = _archetypeCfg() || {variants: [], caps: []};
  _chips('variant-chips', cfg.variants, 'variant', 'variant-note',
         _editorNotices.variant);
  _chips('cap-chips', cfg.caps, 'cap_style', 'cap-note', _editorNotices.cap);
}

function _chips(hostId, options, key, noteId, notice) {
  const host = document.getElementById(hostId);
  host.innerHTML = options.map(o =>
    `<button type="button" class="chip ${o.key === _profileState[key] ? 'active' : ''}"
             aria-pressed="${o.key === _profileState[key]}"
             data-val="${o.key}">${escapeHtml(o.label)}${o.key === _profileState[key]
               ? '<span class="chip-check" aria-hidden="true"> ✓</span>' : ''}</button>`
  ).join('');
  const note = document.getElementById(noteId);
  if (note) {
    note.textContent = notice ||
      (!options.length ? 'No predefined options apply.' : '');
  }
  host.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      _profileState[key] = chip.dataset.val;
      if (key === 'variant') _editorNotices.variant = '';
      if (key === 'cap_style') _editorNotices.cap = '';
      _chips(hostId, options, key, noteId, '');
      _editorRefresh();
    });
  });
}

// §BH64(d)1: ONLY THE PROPORTIONS THIS FORM HAS. `CONTAINER_EDITOR_ARCHETYPES`
// has carried a per-archetype `proportions` list since §BH61(c), and
// `container_profile_editor_config()` copied six keys out of each entry and
// dropped that one — so this page received the global list and drew a Neck
// Proportion slider for a hinged case. `proportions_for()` was written in the
// same arc and called by nothing. The owner: "no field shown that does not
// apply."
function _proportionsForArchetype() {
  const all = (_editorConfig && _editorConfig.proportions) || [];
  const cfg = _archetypeCfg();
  if (!cfg || !Array.isArray(cfg.proportions)) return [];
  // §BH70(1): at THIS form's limits — a pencil's width row reaches its 7 mm
  // [his answer after test day finding 3, (4) round: a form's own words for a row — a tube's width is its diameter]
  return all.filter(p => cfg.proportions.indexOf(p.key) !== -1)
    .map(p => Object.assign({}, p, _rangeFor(cfg, p.key),
                            (cfg.labels && cfg.labels[p.key]) ? {label: cfg.labels[p.key]} : {}));
}

function _renderProportions() {
  const host = document.getElementById('proportion-rows');
  if (!host) return;
  const rows = _proportionsForArchetype();
  host.innerHTML = (rows.length
    ? rows.map(p => _proportionRow(p)).join('')
    : '<p class="choice-note">No proportion applies until a form is chosen.</p>')
    + (_editorNotices.size
      ? `<p class="choice-note" id="size-note" role="status">${escapeHtml(_editorNotices.size)}</p>` : '');
  _bindSliders(host);
}

function _bindSliders(root) {
  const scope = root || document.getElementById('profile-view');
  if (!scope) return;
  scope.querySelectorAll('input[type="range"]').forEach(sl => {
    sl.addEventListener('input', () => {
      const key = sl.dataset.key;
      const val = key === 'neck_ratio' ? parseFloat(sl.value) : parseInt(sl.value, 10);
      _profileState[key] = val;
      _syncProportion(key, val, sl.dataset.unit, 'range');
      _editorRefresh();
    });
  });
  scope.querySelectorAll('.slider-pair input[type="number"]')
    .forEach(num => {
      num.addEventListener('change', () => {
        const key = num.dataset.key;
        let val = parseFloat(num.value);
        const min = parseFloat(num.min), max = parseFloat(num.max);
        if (isNaN(val)) val = _profileState[key];
        val = Math.min(max, Math.max(min, val));
        if (key !== 'neck_ratio') val = Math.round(val);
        _profileState[key] = val;
        _syncProportion(key, val, num.dataset.unit, 'number');
        _editorRefresh();
      });
    });
}

function _syncProportion(key, val, unit, origin) {
  const label = document.getElementById(`sl-val-${key}`);
  if (label) label.textContent = `${val}${unit}`;
  const sl = document.getElementById(`sl-${key}`);
  const num = document.getElementById(`num-${key}`);
  if (sl && origin !== 'range') sl.value = val;
  if (sl) sl.setAttribute('aria-valuetext', `${val}${unit ? ' ' + unit : ''}`);
  if (num && origin !== 'number') num.value = val;
}

// --- editor state: dirty / incomplete / reset (UI-1 §10/§11/§15) -------------

function _editorDirty() {
  if (!_editorInitial) return false;
  return _EDITOR_KEYS.some(k => _profileState[k] !== _editorInitial[k]);
}

function _editorIncomplete() {
  const cfg = _archetypeCfg();
  if (!cfg || !cfg.confirmable) return [];        // handled as custom form
  const missing = [];
  if (!_profileState.variant && cfg.variants.length) missing.push('variant');
  if (!_profileState.cap_style && cfg.caps.length) missing.push('closure');
  return missing;
}

function _editorRefresh() {
  _keepEdits();
  // §BH61(b), his words: "no cap dimensions where there is no cap" — the cap's sizes are asked of a form with a cap only
  const capBlock = document.getElementById('cap-dims-block');
  const form = _archetypeCfg();
  if (capBlock) capBlock.hidden = !(form && form.has_cap_dimensions);
  const dirtyEl = document.getElementById('profile-dirty');
  const incompleteEl = document.getElementById('profile-incomplete');
  const resetBtn = document.getElementById('profile-reset');
  const confirmBtn = document.getElementById('confirm-profile-zones');
  const blockedNote = document.getElementById('confirm-blocked-note');
  const dirty = _editorDirty();
  if (dirtyEl) {
    dirtyEl.textContent = dirty
      ? 'Changed from the suggested shape — nothing is confirmed yet.' : '';
  }
  if (resetBtn) resetBtn.disabled = !dirty;
  const missing = _editorIncomplete();
  const cfg = _archetypeCfg();
  const custom = cfg && !cfg.confirmable;
  if (incompleteEl) {
    incompleteEl.textContent = missing.length
      ? `Not finished yet — choose a ${missing.join(' and a ')}.`
      : '';
  }
  if (confirmBtn && blockedNote) {
    if (!_profileState.archetype) {
      // §BH64(c): with no form chosen the door is SHUT and the server's own
      // sentence says why — `no_proposal_reason` has been in the config since
      // §BH61(a) and nothing on this page had ever read it.
      confirmBtn.disabled = true;
      blockedNote.hidden = false;
      // the server's sentence in words, its code kept, folded beneath it
      blockedNote.innerHTML = `${escapeHtml((_editorConfig && _editorConfig.no_proposal_reason)
        || 'No form is chosen for this design, and none is assumed. Choose one above.')}
        ${(_editorConfig && _editorConfig.no_proposal_code) ? `<details class="tech"><summary>What the record says</summary>
          <p><code>${escapeHtml(_editorConfig.no_proposal_code)}</code></p></details>` : ''}`;
    } else if (custom) {
      confirmBtn.disabled = true;
      blockedNote.hidden = false;
      blockedNote.innerHTML = `A form of its own cannot be confirmed here yet — drawing one needs its own step,
        which is not built.
        <details class="tech"><summary>What the record says</summary>
          <p><code>OTHER_CUSTOM_PROFILE_RECONSTRUCTION_PENDING</code></p></details>`;
    } else if (missing.length) {
      confirmBtn.disabled = true;
      blockedNote.hidden = false;
      blockedNote.textContent = 'Not finished yet — make the choices above before confirming.';
    } else {
      confirmBtn.disabled = false;
      blockedNote.hidden = true;
      blockedNote.textContent = '';
    }
  }
  _drawProfilePreview();
  _scheduleZoneProposal();
}

// [his test day finding 2, 2026-09-29, design 117: he set his tube to 180 x 50 mm and the print areas beside it
// stayed those proposed for other sizes. The areas shown are now proposed by the server for the sizes shown — on
// opening and as a size changes — through the confirm door's own record (propose_container_zones, which writes
// nothing). A tick is cleared only where an area's numbers changed, so a size that moves no area keeps it.]
var _zoneProposalTimer = null;
var _zoneProposalKey = null;

function _zoneNumbers(z) {
  return z ? [z.parent_surface, z.x, z.y, z.width, z.height].join('|') : '';
}

function _scheduleZoneProposal() {
  const cfg = _archetypeCfg();
  if (!_contractState.taskId || !_profileState || !_profileState.archetype || !cfg || !cfg.confirmable) return;
  const key = JSON.stringify(_profileState);
  if (key === _zoneProposalKey) return;
  clearTimeout(_zoneProposalTimer);
  _zoneProposalTimer = setTimeout(() => _proposeZones(key), 250);
}

async function _proposeZones(key) {
  const taskId = _contractState.taskId;
  let res;
  try {
    res = await fetch(`/api/tasks/${taskId}/propose_container_zones/`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCsrf()},
      body: JSON.stringify({profile: JSON.parse(key)}),
    });
  } catch (err) {
    return;                       // no answer: the areas shown stay, and the confirm door checks them
  }
  if (!res.ok) return;            // a size out of its range while typing: the areas follow once it is valid
  const data = await res.json().catch(() => null);
  if (!data || !Array.isArray(data.zones)) return;
  if (_contractState.taskId !== taskId || JSON.stringify(_profileState) !== key) return;   // superseded
  _zoneProposalKey = key;
  const held = {};
  _contractState.zones.forEach(z => { held[z.zone_id] = _zoneNumbers(z); });
  _contractState.zones = data.zones.map(z => ({...z}));
  data.zones.forEach(z => {
    if (held[z.zone_id] !== _zoneNumbers(z)) _contractState.confirmed[z.zone_id] = false;
    if (!(z.zone_id in _contractState.included)) _contractState.included[z.zone_id] = true;
  });
  _renderZoneProposals();
}

function resetProfileEditor() {
  if (!_editorInitial) return;
  _profileState = {..._editorInitial};
  _editorNotices = {variant: '', cap: '', size: ''};
  _renderArchetypeCards();
  _renderContextChips();
  _renderProportions();          // re-rendering the rows IS the reset
  _editorRefresh();
}

// --- deterministic silhouette preview (UI-1 §12/§13) --------------------------
// Pure function of the editor state: canvas 2D, coarse archetype geometry,
// no network, no provider, no persisted output. It communicates archetype,
// body proportions, neck proportion and closure family — nothing more.

var _CAP_PREVIEW = {                    // (width×bodyW, height×bodyH)
  screw: [0.34, 0.12], pump: [0.26, 0.20], flip: [0.40, 0.09],
  lid: [1.02, 0.22], crimp: [0.60, 0.05], dropper: [0.30, 0.26],
  // §BH71 PART 3: the catalogue's closures, as silhouettes._cap_factors draws them
  brush_cap: [0.46, 0.42], crimp_spray: [0.72, 0.26], airless_pump: [0.98, 0.24], mist: [0.80, 0.22],
  roller_ball: [0.55, 0.30], nozzle: [0.30, 0.16],
};

function _drawProfilePreview() {
  const canvas = document.getElementById('profile-preview-canvas');
  if (canvas) {
    _drawSilhouette(canvas.getContext('2d'), _profileState,
                    canvas.width, canvas.height);
  }
  _updatePreviewSummary();
}

// §BH64(d): ONE DRAWER, and the card icons run it too — that is what makes an
// icon impossible to be missing. It takes a state and a box and draws; it
// reads no DOM and writes no summary, so the same function serves a 220x300
// preview and a 150x200 card.
function _drawSilhouette(ctx, s, cw, ch) {
  ctx.clearRect(0, 0, cw, ch);
  const stroke = '#b98a5e', fill = 'rgba(185, 138, 94, 0.14)';
  ctx.lineWidth = 2;
  ctx.strokeStyle = stroke;
  ctx.fillStyle = fill;

  // §BH70(1): a size the state does not give is the FORM's own starting size
  // (it was a bottle's 110 x 40 for every form); only a form with no drawing
  // at all falls to a plain frame's proportion.
  const nominal = ((_archetypeCfg(s.archetype) || {}).nominal) || {};
  const H = Number(s.height_mm) || nominal.height_mm || 100;
  const W = Number(s.width_mm) || nominal.width_mm || 50;
  // §BH64(d)2: NO SCREW CAP FOR A CLOSURE THIS TABLE DOES NOT KNOW. A clasp is
  // not in `_CAP_PREVIEW`, so `|| _CAP_PREVIEW.screw` gave the owner's hinged
  // case a screw cap — a fallback to a bottle's part, in the browser, where no
  // source guard could see it. An unknown closure is now drawn AS unknown.
  const capKnown = Object.prototype.hasOwnProperty.call(
    _CAP_PREVIEW, String(s.cap_style));
  const cap = capKnown ? _CAP_PREVIEW[s.cap_style] : [0.34, 0.10];
  const capH = (s.archetype === 'jar' ? _CAP_PREVIEW.lid[1] : cap[1]) * H;
  const scale = Math.min((cw - 70) / Math.max(W * 1.1, 30),
                         (ch - 46) / (H + capH));
  const bw = W * scale, bh = H * scale;
  const cx = cw / 2;
  const baseY = ch - 24;

  if (!s.archetype) {
    // §BH64(c): NO FORM CHOSEN. The chain below ends in an `else` that is a
    // BOTTLE, so an unset archetype was drawn as one — the picture asserting
    // a form nobody picked. It now draws an empty frame and says so.
    ctx.setLineDash([5, 5]);
    ctx.strokeRect(22, 22, cw - 44, ch - 44);
    ctx.setLineDash([]);
    ctx.font = '13px system-ui, -apple-system, sans-serif';
    ctx.fillStyle = stroke;
    ctx.textAlign = 'center';
    ctx.fillText('No container form chosen', cw / 2, ch / 2);
    return;
  }
  if (s.archetype === 'other') {
    // honest neutral custom silhouette — never a fabricated bottle
    ctx.setLineDash([6, 5]);
    _previewRoundRect(ctx, cx - bw / 2, baseY - bh, bw, bh, 14);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.font = '28px serif';
    ctx.fillStyle = stroke;
    ctx.textAlign = 'center';
    ctx.fillText('?', cx, baseY - bh / 2 + 10);
  } else if (s.archetype === 'jar') {
    const jw = Math.max(bw, bh * 0.62);
    _previewRoundRect(ctx, cx - jw / 2, baseY - bh * 0.78, jw, bh * 0.78, 8);
    ctx.fill(); ctx.stroke();
    const lw = jw * 1.04, lh = Math.max(10, bh * (s.variant === 'sifter' ? 0.34 : 0.2));
    _previewRoundRect(ctx, cx - lw / 2, baseY - bh * 0.78 - lh, lw, lh, 4);
    ctx.fill(); ctx.stroke();
    if (s.variant === 'airless') {                   // §BH71 PART 3: its pump button, on its lid
      const kw = jw * 0.32, kh = Math.max(5, bh * 0.08);
      _previewRoundRect(ctx, cx - kw / 2, baseY - bh * 0.78 - lh - kh, kw, kh, 3);
      ctx.fill(); ctx.stroke();
    }
  } else if (s.archetype === 'tube' && _serverOutline(s)) {
    // [his test blocker on design 122 at the shape step, 2026-10-08: "the shape preview shows a bottle, not a tube"] a
    // tube drawn from its own outline — the drawing's — at the sizes set: its crimped end flat, its shoulder to its cap
    _drawServerShape(ctx, _serverOutline(s), cx, cw, ch, W, H);
  } else if (s.archetype === 'tube') {
    const tw = bw * (s.variant === 'slim' ? 0.5 : 0.62);
    _previewRoundRect(ctx, cx - tw / 2, baseY - bh * 0.86, tw, bh * 0.86,
                      tw / 3);
    ctx.fill(); ctx.stroke();
    if (s.cap_style === 'crimp') {
      ctx.beginPath();                        // crimp seal band at the base
      ctx.moveTo(cx - tw / 2 - 4, baseY);
      ctx.lineTo(cx + tw / 2 + 4, baseY);
      ctx.stroke();
    } else {
      const cw2 = tw * (cap[0] + 0.25), ch2 = Math.max(8, bh * cap[1] * 0.9);
      if (!capKnown) ctx.setLineDash([3, 3]);
      _previewRoundRect(ctx, cx - cw2 / 2, baseY - bh * 0.86 - ch2, cw2, ch2, 3);
      ctx.fill(); ctx.stroke();
      ctx.setLineDash([]);
    }
  } else if (String(s.variant || '').indexOf('learned_') === 0 && _serverOutline(s)) {
    // §BH71 PART 3: a learned lid is drawn from the server's own drawing of it, as a form with no hand-drawn picture
    const shape = _serverOutline(s);
    const sc = Math.min((cw - 56) / Math.max(W, 1), (ch - 74) / Math.max(H, 1));
    const ow = W * sc, oh = H * sc;
    const x0 = cx - ow / 2, y0 = (ch - oh) / 2 - 6;
    [shape.outline, shape.closure].forEach(function (poly) {
      if (!poly || !poly.length) return;
      ctx.beginPath();
      ctx.moveTo(x0 + poly[0][0] * ow, y0 + poly[0][1] * oh);
      for (let i = 1; i < poly.length; i++) ctx.lineTo(x0 + poly[i][0] * ow, y0 + poly[i][1] * oh);
      ctx.closePath();
      ctx.fill(); ctx.stroke();
    });
  } else if (s.archetype === 'compact') {
    // §BH64(d)2 and §BH55(a): A COMPACT IS DRAWN IN PLAN — "the lid from above,
    // its closed thickness the depth". There was NO compact branch at all, so a
    // compact fell through to the `else` below, which is a bottle: "I judge by
    // the picture, and the picture is lying." The form's own description has
    // said "Drawn in PLAN" since §BH61(c); `drawn_as` is that sentence in a
    // form this function can read.
    const D = Number(s.depth_mm) || 0;
    const sc = Math.min((cw - 56) / Math.max(W, 1), (ch - 74) / Math.max(H, 1));
    const lw = W * sc, lh = H * sc;
    const off = Math.max(4, Math.min(16, D * sc));   // the closed thickness, as a step
    const x0 = cx - lw / 2, y0 = (ch - lh - off) / 2 - 6;
    const r = s.variant === 'square' ? 4 : (s.variant === 'paperboard' ? 2
      : ((s.variant === 'round' || s.variant === 'cushion') ? Math.min(lw, lh) / 2 : 14));
    ctx.save();                                      // the BASE, under the lid
    ctx.globalAlpha = 0.5;
    _previewRoundRect(ctx, x0 + off, y0 + off, lw, lh, r);
    ctx.fill(); ctx.stroke();
    ctx.restore();
    _previewRoundRect(ctx, x0, y0, lw, lh, r);       // the LID, seen from above
    ctx.fill(); ctx.stroke();
    ctx.beginPath();                                 // the hinge, on the back edge
    ctx.moveTo(x0 + lw * 0.30, y0);
    ctx.lineTo(x0 + lw * 0.70, y0);
    ctx.stroke();
    const fy = y0 + lh, fx = x0 + lw / 2;            // the closure, by its own name
    if (s.cap_style === 'magnet') {
      ctx.beginPath();
      ctx.arc(fx, fy, Math.max(3, lw * 0.05), 0, Math.PI * 2);
      ctx.fill(); ctx.stroke();
    } else if (s.cap_style === 'friction') {
      ctx.beginPath();
      ctx.moveTo(fx - lw * 0.12, fy);
      ctx.lineTo(fx + lw * 0.12, fy);
      ctx.stroke();
    } else if (s.cap_style === 'clasp') {
      const kw = Math.max(8, lw * 0.16), kh = Math.max(5, lh * 0.09);
      _previewRoundRect(ctx, fx - kw / 2, fy - kh / 2, kw, kh, 2);
      ctx.fill(); ctx.stroke();
    }
    ctx.save();                                      // and the depth, named where it shows
    ctx.font = '10px system-ui, -apple-system, sans-serif';
    ctx.fillStyle = stroke;
    ctx.textAlign = 'center';
    ctx.fillText('closed ' + (D || '?') + 'mm', cx, y0 + lh + off + 15);
    ctx.restore();
  } else if (s.archetype === 'lipstick' || s.archetype === 'mascara'
             || s.archetype === 'pencil') {
    // §BH70(1): THE THREE SLIM FORMS, each CLOSED and standing — its cap over
    // its body, the way silhouettes._capped_body draws them. A lipstick and a
    // mascara fell to the `else` below and were drawn as bottles; a pencil had
    // no card at all. Each draws its own parts: a lipstick's cap over its case
    // and the seam between, a mascara's long wand cap over its vial with the
    // wand inside, a pencil's cap over its long barrel and the butt end.
    let shares = {lipstick: [0.52, 1.0], mascara: [0.56, 0.9], pencil: [0.26, 1.0]}[s.archetype];
    // §BH71 PART 3: a liner pen's cap a third of it; a click pen's button, no cap
    if (s.archetype === 'pencil' && s.cap_style === 'click') shares = [0.06, 0.55];
    else if (s.archetype === 'pencil' && s.variant === 'pen') shares = [0.32, 1.0];
    const slim = s.variant === 'slim' ? 0.82 : 1;
    const bodyW = Math.max(6, bw * slim);
    const square = s.variant === 'square';
    const capH = bh * shares[0], capW = bodyW * shares[1];
    const top = baseY - bh;
    const rTop = square ? 2 : (s.archetype === 'pencil' ? capW / 2 : capW * 0.3);
    const rBase = square ? 2 : bodyW * 0.12;
    _previewRoundRect(ctx, cx - bodyW / 2, top + capH, bodyW, bh - capH, rBase);   // the body
    ctx.fill(); ctx.stroke();
    _previewRoundRect(ctx, cx - capW / 2, top, capW, capH, rTop);                  // its cap
    ctx.fill(); ctx.stroke();
    if (s.archetype === 'mascara') {
      ctx.setLineDash([3, 3]);                                  // the wand, inside
      ctx.beginPath();
      ctx.moveTo(cx, top + capH * 0.2);
      ctx.lineTo(cx, baseY - (bh - capH) * 0.18);
      ctx.stroke();
      ctx.setLineDash([]);
    } else if (s.archetype === 'lipstick') {
      ctx.beginPath();                                          // the seam, and a magnet at it
      ctx.moveTo(cx - bodyW / 2, top + capH);
      ctx.lineTo(cx + bodyW / 2, top + capH);
      ctx.stroke();
      if (s.cap_style === 'magnet') {
        ctx.beginPath();
        ctx.arc(cx, top + capH, Math.max(2, bodyW * 0.08), 0, Math.PI * 2);
        ctx.fill(); ctx.stroke();
      }
    } else {
      ctx.beginPath();                                          // the butt end, or the twist
      const endH = Math.max(3, bh * (s.variant === 'twist' ? 0.06 : 0.02));
      ctx.moveTo(cx - bodyW / 2, baseY - endH);
      ctx.lineTo(cx + bodyW / 2, baseY - endH);
      ctx.stroke();
    }
  } else if (s.archetype === 'bottle') {
    const bodyW = bw * (s.variant === 'slim' ? 0.72 : (s.variant === 'roller' ? 0.6 : 1));
    // §BH71 PART 3: an airless bottle has no neck — its overcap sits on its straight body
    const neckW = s.variant === 'airless' ? bodyW * 0.98 : Math.max(0.2, Math.min(0.7, Number(s.neck_ratio) || 0.42))
      * bodyW;
    const neckH = Math.max(8, bh * 0.09);
    const shoulderH = Math.max(6, bh * 0.07);
    const bodyH = bh - neckH - shoulderH;
    const r = (s.variant === 'square' || s.variant === 'flacon') ? 3 : 10;
    if (s.variant === 'tapered') {
      ctx.beginPath();                        // trapezoid body, narrower top
      ctx.moveTo(cx - bodyW / 2, baseY);
      ctx.lineTo(cx - bodyW * 0.42, baseY - bodyH);
      ctx.lineTo(cx + bodyW * 0.42, baseY - bodyH);
      ctx.lineTo(cx + bodyW / 2, baseY);
      ctx.closePath();
      ctx.fill(); ctx.stroke();
    } else {
      _previewRoundRect(ctx, cx - bodyW / 2, baseY - bodyH, bodyW, bodyH, r);
      ctx.fill(); ctx.stroke();
    }
    ctx.beginPath();                          // shoulder: body top → neck base
    ctx.moveTo(cx - bodyW * 0.42, baseY - bodyH);
    ctx.lineTo(cx - neckW / 2, baseY - bodyH - shoulderH);
    ctx.lineTo(cx + neckW / 2, baseY - bodyH - shoulderH);
    ctx.lineTo(cx + bodyW * 0.42, baseY - bodyH);
    ctx.closePath();
    ctx.fill(); ctx.stroke();
    const neckTop = baseY - bodyH - shoulderH - neckH;
    _previewRoundRect(ctx, cx - neckW / 2, neckTop, neckW, neckH, 1);
    ctx.fill(); ctx.stroke();
    if (s.cap_style === 'dropper') {
      const collarH = Math.max(8, bh * 0.07);
      _previewRoundRect(ctx, cx - neckW * 0.62, neckTop - collarH,
                        neckW * 1.24, collarH, 2);
      ctx.fill(); ctx.stroke();
      const bulbH = Math.max(12, bh * 0.16);
      ctx.beginPath();                        // rounded rubber bulb
      ctx.ellipse(cx, neckTop - collarH - bulbH / 2, neckW * 0.45,
                  bulbH / 2, 0, 0, Math.PI * 2);
      ctx.fill(); ctx.stroke();
    } else {
      const cw2 = bodyW * cap[0], ch2 = Math.max(8, bh * cap[1]);
      if (!capKnown) ctx.setLineDash([3, 3]);
      _previewRoundRect(ctx, cx - cw2 / 2, neckTop - ch2, cw2, ch2, 2);
      ctx.fill(); ctx.stroke();
      ctx.setLineDash([]);
    }
  } else if (_serverOutline(s)) {
    // §BH71 PART 3: a form this drawer has no hand-drawn picture of is drawn from the server's own drawing of it
    // (targets/ui.py _form_outlines: silhouettes.build_backbone at the form's starting size), scaled to the size
    // set here — its outline, then its closure over it. Never a bottle's.
    const shape = _serverOutline(s);
    const plan = ((_archetypeCfg(s.archetype) || {}).drawn_as === 'PLAN');
    const sc = plan ? Math.min((cw - 56) / Math.max(W, 1), (ch - 74) / Math.max(H, 1))
      : Math.min((cw - 70) / Math.max(W * 1.1, 30), (ch - 46) / Math.max(H, 1));
    const ow = W * sc, oh = H * sc;
    const x0 = cx - ow / 2, y0 = plan ? (ch - oh) / 2 - 6 : baseY - oh;
    [shape.outline, shape.closure].forEach(function (poly) {
      if (!poly || !poly.length) return;
      ctx.beginPath();
      ctx.moveTo(x0 + poly[0][0] * ow, y0 + poly[0][1] * oh);
      for (let i = 1; i < poly.length; i++) ctx.lineTo(x0 + poly[i][0] * ow, y0 + poly[i][1] * oh);
      ctx.closePath();
      ctx.fill(); ctx.stroke();
    });
  } else {
    // §BH70(1), item 9: A FORM THIS DRAWER DOES NOT KNOW IS NOT A BOTTLE. The
    // chain ended in an `else` that WAS the bottle, so the next form declared
    // on the server would have reached the owner drawn as one — the palette's
    // defect waiting for its next form. It draws an empty frame and says so.
    ctx.setLineDash([5, 5]);
    ctx.strokeRect(22, 22, cw - 44, ch - 44);
    ctx.setLineDash([]);
    ctx.font = '13px system-ui, -apple-system, sans-serif';
    ctx.fillStyle = stroke;
    ctx.textAlign = 'center';
    ctx.fillText('No drawing for this form yet', cw / 2, ch / 2);
  }
}

// §BH71 PART 3: "... and offers to learn it." Under the sentence, one button when the approved concept's own trace
// shows the lid and the system draws its kind; else the sentence why it cannot. The click learns it for every
// design and re-proposes this one with it; the page is drawn again from the server.
function _showLearnOffer() {
  const shape = _editorConfig && _editorConfig.unknown_shape;
  const note = document.getElementById('variant-note');
  if (!shape || !note || _profileState.variant || document.getElementById('learn-shape')) return;
  const box = document.createElement('div');
  box.id = 'learn-shape';
  box.className = 'learn-offer';
  if (shape.learnable) {
    box.innerHTML = `<button type="button" class="btn btn-secondary" id="learn-shape-btn">Learn this shape from
      the concept</button> <span class="muted" id="learn-shape-msg">It becomes a shape every design can use.</span>`;
  } else {
    box.innerHTML = `<span class="muted" id="learn-shape-msg">${escapeHtml(shape.not_learnable || '')}</span>`;
  }
  note.insertAdjacentElement('afterend', box);
  const btn = document.getElementById('learn-shape-btn');
  if (btn) btn.addEventListener('click', _learnShape);
}

async function _learnShape() {
  const shape = _editorConfig && _editorConfig.unknown_shape;
  const btn = document.getElementById('learn-shape-btn');
  const msg = document.getElementById('learn-shape-msg');
  if (!shape || !btn) return;
  btn.disabled = true;
  msg.textContent = 'Learning it…';
  let res, body = {};
  try {
    res = await fetch(shape.learn_url, {method: 'POST', headers: {'Content-Type': 'application/json',
                                                                  'X-CSRFToken': getCsrf()}, body: '{}'});
    body = await res.json();
  } catch (err) {
    btn.disabled = false;
    msg.textContent = 'It could not be reached — nothing was learned. Try again.';
    return;
  }
  if (!res.ok) {
    btn.disabled = false;
    msg.textContent = (body.detail && body.detail[0]) || 'It could not be learned.';
    return;
  }
  msg.textContent = `Learned: ${body.learned.label}. The shape is proposed with it.`;
  if (typeof loadTask === 'function' && window.OPEN_TASK_ID) loadTask(window.OPEN_TASK_ID);
}

// §BH71 PART 3: the server's own drawing of this form and variant — its outline and closure in shares of its box —
// or null when the server sends none (a form the declaration does not know).
function _drawServerShape(ctx, shape, cx, cw, ch, W, H) {
  const sc = Math.min((cw - 56) / Math.max(W, 1), (ch - 74) / Math.max(H, 1));
  const ow = W * sc, oh = H * sc;
  const x0 = cx - ow / 2, y0 = (ch - oh) / 2 - 6;
  [shape.outline, shape.closure].forEach(function (poly) {
    if (!poly || !poly.length) return;
    ctx.beginPath();
    ctx.moveTo(x0 + poly[0][0] * ow, y0 + poly[0][1] * oh);
    for (let i = 1; i < poly.length; i++) ctx.lineTo(x0 + poly[i][0] * ow, y0 + poly[i][1] * oh);
    ctx.closePath();
    ctx.fill(); ctx.stroke();
  });
}

function _serverOutline(s) {
  const outlines = (_archetypeCfg(s.archetype) || {}).outlines;
  if (!outlines) return null;
  return outlines[s.variant] || outlines[Object.keys(outlines)[0]] || null;
}

function _previewRoundRect(ctx, x, y, w, h, r) {
  r = Math.max(0, Math.min(r, w / 2, h / 2));
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function _updatePreviewSummary() {
  const el = document.getElementById('profile-preview-summary');
  if (!el) return;
  const s = _profileState;
  const cfg = _archetypeCfg() || {label: s.archetype, variants: [], caps: []};
  const variantLabel = (cfg.variants.find(v => v.key === s.variant) || {})
    .label || (s.variant ? s.variant : 'no variant chosen');
  const capLabel = (cfg.caps.find(c => c.key === s.cap_style) || {})
    .label || (s.cap_style ? s.cap_style : 'no closure chosen');
  if (!s.archetype) {
    // §BH64(c): the sentence matches the picture. Without this the summary
    // read "null, no variant chosen, no closure chosen — ... neck 42% ...".
    el.textContent = (_editorConfig && _editorConfig.no_proposal_reason)
      || 'No container form chosen. Nothing is assumed; choose a form above.';
    return;
  }
  // §BH64(d)1: THE SENTENCE SAYS ONLY WHAT THIS FORM HAS. It read
  // "Compact / Palette, Rounded Rectangle, Clasp — overall height 80, body
  // width 80, neck 42% of body width" — the neck clause was appended for every
  // form but "Other", unconditionally. "The control may be gone; the sentence
  // is not." It is now composed from the form's OWN proportion list and the
  // editor's own labels, so a form that declares no neck cannot be described
  // as having one, and a new form is described by construction.
  const measures = _proportionsForArchetype().map(p => (
    p.key === 'neck_ratio'
      ? `neck ${Math.round((Number(s.neck_ratio) || 0) * 100)}% of body width`
      : `${p.label.toLowerCase()} ${s[p.key]}${p.unit}`)).join(', ');
  el.textContent = s.archetype === 'other'
    ? `Custom container form — ${measures}. No standard silhouette applies. `
      + 'A preview only — not a production drawing.'
    : `${cfg.label}, ${variantLabel}, ${capLabel} — ${measures}. `
      + 'A preview only — not a production drawing.';
}

// --- reviewed confirmation dialog (UI-2A §7/§8) -------------------------------
// One reviewed door to the POST: the page button only OPENS this dialog, the
// dialog's explicit Confirm & Reconstruct is the single dispatch path, and a
// settled/in-flight guard makes double interaction send exactly one request.

var _confirmDialogSettled = false;
var _confirmInFlight = false;

function _cpdRow(label, value) {
  return `<div class="cpd-row"><dt>${escapeHtml(label)}</dt>` +
         `<dd>${escapeHtml(String(value))}</dd></div>`;
}

function openConfirmProfileDialog(taskId) {
  const dlg = document.getElementById('confirm-profile-dialog');
  if (!dlg || dlg.open || _confirmInFlight) return;
  // §6: readiness is re-checked at the door — an incomplete or
  // non-confirmable editor never opens the dialog
  const cfg = _archetypeCfg();
  if (!cfg || !cfg.confirmable || _editorIncomplete().length) return;
  const s = _profileState;
  const variantLabel = (cfg.variants.find(v => v.key === s.variant) || {})
    .label || s.variant;
  const capLabel = (cfg.caps.find(c => c.key === s.cap_style) || {})
    .label || s.cap_style;
  // §BH70(1), item 21 of the list the owner was sent: only the proportions its form has — a hinged case, a lipstick or
  // a pencil has no neck, and the dialog listed "Neck Proportion: null" for it
  const hasNeck = Array.isArray(cfg.proportions) && cfg.proportions.indexOf('neck_ratio') !== -1;
  document.getElementById('cpd-summary').innerHTML =
    _cpdRow('Form', cfg.label) +
    _cpdRow('Variant', variantLabel) +
    _cpdRow('Closure', capLabel) +
    _cpdRow('Overall Height', `${s.height_mm} mm`) +
    _cpdRow((cfg.labels && cfg.labels.width_mm) || 'Body Width', `${s.width_mm} mm`) +   // [his round: a tube's diameter]
    _cpdRow('Body Depth', `${s.depth_mm} mm`) +
    (hasNeck ? _cpdRow('Neck Proportion', s.neck_ratio) : '');
  _confirmDialogSettled = false;
  document.getElementById('cpd-busy').hidden = true;
  ['cpd-cancel', 'cpd-review', 'cpd-confirm'].forEach(id => {
    document.getElementById(id).disabled = false;
  });
  if (!dlg.dataset.bound) {
    dlg.dataset.bound = '1';
    document.getElementById('cpd-cancel').addEventListener('click',
      () => _settleConfirmDialog('cancel', taskId));
    document.getElementById('cpd-review').addEventListener('click',
      () => _settleConfirmDialog('review', taskId));
    document.getElementById('cpd-confirm').addEventListener('click',
      () => _settleConfirmDialog('confirm', taskId));
    dlg.addEventListener('cancel', ev => {
      ev.preventDefault();               // Escape = Cancel before dispatch;
      if (!_confirmInFlight) _settleConfirmDialog('cancel', taskId);
    });                                  // in flight: no ambiguous close
    dlg.addEventListener('keydown', ev => {
      if (ev.key !== 'Tab') return;      // explicit wrap — focus never rests
      const first = document.getElementById('cpd-cancel');
      const last = document.getElementById('cpd-confirm');
      if (ev.shiftKey && document.activeElement === first) {
        ev.preventDefault(); last.focus();
      } else if (!ev.shiftKey && document.activeElement === last) {
        ev.preventDefault(); first.focus();
      }
    });
  }
  dlg.showModal();
  document.getElementById('cpd-cancel').focus();
}

function _settleConfirmDialog(action, taskId) {
  if (_confirmDialogSettled || _confirmInFlight) return;
  const dlg = document.getElementById('confirm-profile-dialog');
  if (action === 'cancel') {
    _confirmDialogSettled = true;
    dlg.close();
    const btn = document.getElementById('confirm-profile-zones');
    if (btn) btn.focus();
    return;
  }
  if (action === 'review') {
    _confirmDialogSettled = true;
    dlg.close();
    const first = document.querySelector('.archetype-card[aria-checked="true"]')
      || document.querySelector('.archetype-card');
    if (first) first.focus();
    return;
  }
  // confirm: one request, dialog visibly locked until the response arrives
  _confirmDialogSettled = true;
  _confirmInFlight = true;
  ['cpd-cancel', 'cpd-review', 'cpd-confirm'].forEach(id => {
    document.getElementById(id).disabled = true;
  });
  document.getElementById('cpd-busy').hidden = false;
  submitContainerProfile(taskId);
}

function _closeConfirmDialog() {
  const dlg = document.getElementById('confirm-profile-dialog');
  if (dlg && dlg.open) dlg.close();
  _confirmInFlight = false;
}

// --- combined confirmation ------------------------------------------------------

async function submitContainerProfile(taskId) {
  const msg = document.getElementById('profile-msg');
  // Skipped optional zones are excluded from the confirmed contract (item 6);
  // included zones carry the user's per-zone confirmation state.
  const zones = _contractState.zones
    .filter(z => _contractState.included[z.zone_id] !== false)
    .map(z => ({
      ...z,
      user_confirmation_state:
        _contractState.confirmed[z.zone_id] ? 'USER_CONFIRMED' : 'PROPOSED',
    }));
  msg.textContent = 'Confirming the shape and print areas…';
  let res;
  try {
    res = await fetch(`/api/tasks/${taskId}/confirm_container_profile/`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCsrf()},
      body: JSON.stringify({profile: _profileState, zones: zones}),
    });
  } catch (err) {
    // UI-2A §17: the POST may or may not have reached the server. Never
    // blindly re-POST — inspect the persisted task/gate state first; only
    // when no accepted decision exists is another attempt allowed.
    _closeConfirmDialog();
    try {
      const check = await fetch(`/api/tasks/${taskId}/status/`);
      const state = await check.json();
      const spec = ((state.packaging_output || {}).spec_sheet) || {};
      if (spec.container_confirmation) {
        loadTask(taskId);            // it WAS accepted — render confirmed
        return;
      }
      msg.textContent = 'The request failed before an answer arrived and no '
        + 'confirmed shape exists yet — your choices are unchanged. '
        + 'You can confirm again.';
    } catch (err2) {
      msg.textContent = 'The connection failed and the current task state '
        + 'could not be read. Reload the task before confirming again — '
        + 'your selections are unchanged.';
    }
    msg.focus();
    return;
  }
  if (res.ok) {
    _closeConfirmDialog();
    _forgetEdits(taskId);           // confirmed: what he set is the record's now
    loadTask(taskId);
    return;
  }
  // Refusal path (§5): render the ordered code + per-zone detail WITHOUT
  // resetting any selection — the state objects are untouched.
  _closeConfirmDialog();
  const data = await res.json().catch(() => ({}));
  const detail = Array.isArray(data.detail) ? data.detail : [];
  // §BH70(1): a refusal that carries its reason in words shows it — the name that would be cut off says so
  msg.innerHTML = `<strong>The shape could not be confirmed.</strong> Nothing was changed — your choices are as
    you left them.${data.reason ? ` <span class="refusal-reason">${escapeHtml(String(data.reason))}</span>` : ''}
    <details class="tech"><summary>What the record says</summary>
      <p><code>${escapeHtml(data.error || 'CONFIRMATION_REFUSED')}</code></p>` +
    (detail.length
      ? `<ul class="refusal-detail">${detail.map(d => `<li>${escapeHtml(String(d))}</li>`).join('')}</ul>`
      : '') + `</details>`;
  if (Array.isArray(data.zones) && data.zones.length) {
    // §BH64(b) ON THE SCREEN. A zone whose GEOMETRY changed is a different
    // zone, and the tick beside it was a confirmation of numbers that are
    // gone. Keyed only on `zone_id`, the old tick survived a substitution and
    // the user could confirm a shape nobody had shown them — which defeats
    // CONTAINER_ZONE_PROFILE_DIVERGED with one more click. `zone_hash` is
    // what changes when the numbers change, so it is what decides.
    // [his test blocker on design 122 at the shape step, 2026-10-08: "every tick cleared"] an area is the one he ticked
    // while its numbers are the same — compared by its numbers, as the live proposal compares them, never only by a hash
    // a refusal may not carry
    const held = {};
    _contractState.zones.forEach(z => { held[z.zone_id] = _zoneNumbers(z); });
    _contractState.zones = data.zones.map(z => ({...z}));
    data.zones.forEach(z => {
      if (!(z.zone_id in _contractState.confirmed)
          || held[z.zone_id] !== _zoneNumbers(z)) {
        _contractState.confirmed[z.zone_id] =
          z.user_confirmation_state === 'USER_CONFIRMED';
      }
    });
    _renderZoneProposals();
  }
  _keepEdits();
  // [his test blocker on design 122 at the shape step: "no message saying why"] the reason in words, beside the button
  // he pressed, brought into view
  msg.classList.add('profile-msg-refused');
  msg.setAttribute('role', 'alert');
  try { msg.scrollIntoView({block: 'center'}); } catch (e) { /* an old browser: focus still lands on it */ }
  msg.focus();                       // §16: land on the first actionable error
}
