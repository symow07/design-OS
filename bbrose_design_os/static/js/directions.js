// === DIRECTION SELECTION (Phase 2A-4) ===
// The pre-render creative-planning choice: Design Intent + three direction
// cards, shown BEFORE any image is generated. NOT Gate 1 — the user picks a
// reasoning direction here, then picks a rendered concept at Gate 1 later.
// §BH55 Phase 3: in a designer's words — the banner (docs/design_intelligence/dip1/Phase-2A-4_direction_review_
// selection.md) keeps its meaning in a sentence, not capitals; each reference's provenance and its BLOCKED badge are
// words, not codes; the page no longer says "Gate 1"

const DIP_WARNING =
  'References inform the design\'s patterns only. They never go into the print ' +
  'file, and must not be copied.';

const DIP_SOURCE_WORDS = {MACHINE_DERIVED: 'found by the machine', HUMAN_VERIFIED: 'checked by a person'};

function esc(text) {
  const div = document.createElement('div');
  div.textContent = String(text == null ? '' : text);
  return div.innerHTML;
}

// [the owner's answer to the UI directions of 2026-09-25, (d) "No engine codes on screen": the planner writes its
// vocabulary's names into its prose ("The LOGO_FIRST hierarchy suits…") — shown in words ("the logo first hierarchy");
// the record keeps what it wrote]
function plainCodes(text) {
  return String(text == null ? '' : text).replace(/\b[A-Z]{2,}(?:_[A-Z]{2,})+\b/g, m => m.toLowerCase().replace(/_/g, ' '))
    .replace(/\bgate ?([12])\b/gi, (m, n) => (n === '1' ? 'the concept choice' : 'the review'));   // its two stops, in words
}

function fieldRow(label, value) {
  if (!value || (Array.isArray(value) && !value.length)) return '';
  const body = Array.isArray(value) ? value.map(v => esc(plainCodes(v))).join('; ') : esc(plainCodes(value));
  return `<div class="dir-field"><span class="dir-label">${esc(label)}</span> ${body}</div>`;
}

function dipReferenceRows(refs) {
  if (!refs || !refs.length) return '';
  const rows = refs.map(ref => {
    // every reference is DESCRIPTIVE_REFERENCE_ONLY (design_intent.REFERENCE_LABEL): described to the planner, never an input
    const badges = ['a description only', DIP_SOURCE_WORDS[ref.source] || ref.source]
      .concat(ref.blocked ? ['withheld'] : [])
      .map(b => `<span class="dip-badge">${esc(b)}</span>`).join(' ');
    return `<div class="dip-ref">${badges} ${esc(ref.note || `library item ${ref.corpus_item_id || ''}`)}</div>`;
  }).join('');
  return `<div class="dir-field"><span class="dir-label">References it draws on</span>${rows}</div>`;
}

function intentBlock(intent) {
  const rows = [
    ['Visual objective', intent.visual_objective],
    ['Audience & market', intent.audience_interpretation],
    ['Hierarchy', intent.hierarchy],
    ['Focal point', intent.focal_point],
    ['Composition', intent.composition],
    ['Typography', intent.typography_strategy],
    ['Color', intent.color_strategy],
    ['Motif & graphics', intent.motif_strategy],
    ['For this product', intent.target_structural_guidance],
    ['What must stay original', intent.originality_constraints],
    ['What to avoid', intent.forbidden_choices],
    ['Questions still open', intent.unresolved_questions],
    ['How sure the plan is', intent.confidence],
  ].map(([label, value]) => fieldRow(label, value)).join('');
  return `<section class="design-intent"><h3>Design intent</h3>${rows}</section>`;
}

function directionCard(direction, taskId) {
  const rows = [
    ['What leads it', direction.design_axis],
    ['Concept', direction.concept_statement],
    ['Layout structure', direction.layout_structure],
    ['Focal hierarchy', direction.focal_hierarchy],
    ['Color system', direction.color_system],
    ['Typography', direction.typography],
    ['Motif & graphic language', direction.graphic_elements],
    ['Imagery approach', direction.imagery_approach],
    ['Material & finish', direction.material_finish_direction],
    ['Emotional tone', direction.emotional_tone],
    ['Product fit', direction.product_target_fit],
    ['For this product', direction.target_structural_guidance],
    ['What is original', direction.originality_notes],
    ['What to avoid', direction.prohibited_choices],
    ['Risks', direction.risks],
    ['The picture it asks for', direction.prompt_seed],
  ].map(([label, value]) => fieldRow(label, value)).join('');
  return `<article class="direction-card" data-direction-id="${esc(direction.direction_id)}">
    <h4>${esc(plainCodes(direction.name))}</h4>
    ${rows}
    ${dipReferenceRows(direction.dip_references)}
    <button type="button" class="btn-approve select-direction-btn"
            data-task-id="${esc(taskId)}" data-direction-id="${esc(direction.direction_id)}">
      Choose this direction
    </button>
  </article>`;
}

// §BH55 Phase 3: what choosing a direction spends, before the click — measured on this system's own ledger
// (apps/pipeline/spend_estimates.py), never a quote; without a measurement it says only that the step is paid
function directionCostWords(data) {
  const est = (data && data.spend_estimates) || {};
  const step = (est.steps || {}).choose_direction || {};
  const machine = est.machine || {};
  if (!step.usd) return 'Choosing a direction draws three concepts — a paid step.';
  const drawn = `${machine.image_model || 'the picture model'}${machine.image_size ? ', ' + machine.image_size : ''}`;
  return `Choosing a direction spends about $${Number(step.usd).toFixed(2)} — the prompts, ${step.images} drawings `
    + `(${drawn}) and a check on each, measured on past designs.`;
}

function showDirectionSelection(data) {
  const state = document.getElementById('direction-state');
  const view = document.getElementById('direction-view');
  if (!state || !view) return;
  state.style.display = 'block';

  const brief = data.brief || {};
  const intent = brief.design_intent || {};
  const directions = brief.directions || [];

  view.innerHTML = `
    <div class="direction-header">
      <h2>Choose a design direction</h2>
      <p>Choose one direction. Three concepts are then drawn in it for you to choose from. Nothing has been
      drawn yet.</p>
      <p class="spend-note">${esc(directionCostWords(data))}</p>
      <p class="dip-warning"><strong>${esc(DIP_WARNING)}</strong></p>
    </div>
    <div class="direction-cards">
      ${directions.map(d => directionCard(d, data.id)).join('')}
    </div>
    <details class="intent-fold"><summary>The thinking behind all three</summary>${intentBlock(intent)}</details>`;

  view.querySelectorAll('.select-direction-btn').forEach(btn => {
    btn.addEventListener('click', () => selectDirection(
      btn.dataset.taskId, btn.dataset.directionId, btn));
  });
}

async function selectDirection(taskId, directionId, btn) {
  btn.disabled = true;
  btn.textContent = 'Choosing…';
  try {
    const res = await fetch(`/api/tasks/${taskId}/select_direction/`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCsrf()},
      body: JSON.stringify({direction_id: directionId}),
    });
    const payload = await res.json();
    if (!res.ok) {
      sayInPage(payload.error || 'The direction was not chosen');
      btn.disabled = false;
      btn.textContent = 'Choose this direction';
      return;
    }
    loadTask(taskId);
  } catch (err) {
    sayInPage('The direction was not chosen: ' + err);
    btn.disabled = false;
    btn.textContent = 'Choose this direction';
  }
}
