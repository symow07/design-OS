// === COMPLETE PRODUCT COORDINATOR UX (C3) ===
// Renders the composite project's coordinator surfaces from the additive
// `data.project` read-model on the task status payload (recipe ⋈ children,
// N-stage). The project is a COORDINATOR — a stage breadcrumb + a completed
// summary — never its own Review Board; each child keeps its own frozen board.
//
// Everything here is gated on `data.project` being present, so single-target
// tasks (project=null) render nothing new and stay pixel-identical to before.

// Recipe stage labels for the composer hint at create time (no project exists
// yet then, so the backend read-model can't supply them). Mirrors
// COMPOSITE_RECIPES in apps/pipeline/targets/composite.py — extend both.
var COMPOSITE_STAGES = { complete_product: ['Container', 'Packaging'] };

// --- Stage breadcrumb (areas 1 + 4): where you are + navigation between stages
function renderStageBreadcrumb(project) {
  const host = document.getElementById('stage-breadcrumb');
  if (!host) return;
  const stages = project && Array.isArray(project.stages) ? project.stages : null;
  if (!stages || !stages.length) {          // single-target → no breadcrumb
    host.style.display = 'none';
    host.innerHTML = '';
    return;
  }
  try {
    const pills = stages.map(_stagePill).join('<span class="bc-arrow">→</span>');
    host.innerHTML = `<nav class="stage-bc" aria-label="Project stages">
        <span class="bc-project">${escapeHtml(project.target || 'Project')}</span>
        ${pills}</nav>`;
    host.style.display = 'block';
  } catch (e) {                             // any failure → hide, never break
    console.error('breadcrumb render failed', e);
    host.style.display = 'none';
    host.innerHTML = '';
  }
}

function _stagePill(s, i) {
  const cls = ['bc-pill'];
  if (s.is_current) cls.push('is-current');
  if (s.status === 'completed') cls.push('is-done');
  if (s.status === 'failed') cls.push('is-failed');
  if (s.status === 'pending') cls.push('is-pending');
  if (String(activeTaskId) === String(s.task_id)) cls.push('is-active');
  const mark = s.status === 'completed' ? ' ✓' : s.status === 'failed' ? ' ✕' : '';
  const inner = `<span class="bc-num">${i + 1}</span> ${escapeHtml(s.target)}${mark}`;
  // Clickable only when a child task exists to navigate to (pending = no task).
  return s.task_id != null
    ? `<button type="button" class="${cls.join(' ')}" onclick="loadTask(${s.task_id})">${inner}</button>`
    : `<span class="${cls.join(' ')}">${inner}</span>`;
}

// --- Project Completed summary (areas 2 + 5): both stages' deliverables
// Chosen by render.js only when data.project.status === 'completed'; otherwise
// the untouched single-task showCompleted runs. Groups downloads per stage with
// the child-target label above each group (never a generic "dieline").
function showProjectCompleted(data) {
  const host = document.getElementById('complete-state');
  host.style.display = 'block';
  const project = data.project || {};
  const stages = Array.isArray(project.stages) ? project.stages : [];
  const cards = stages.map(s => {
    const hero = s.hero_url
      ? `<img src="${s.hero_url}" alt="${escapeHtml(s.target)}" class="pc-hero" loading="lazy"
             onclick="window.open('${s.hero_url}', '_blank')" title="Open full size">`
      : '<div class="pc-hero pc-hero-missing">preview unavailable</div>';
    const dls = (s.deliverables || []).map(d =>
      `<a href="${d.url}" download class="btn-download">${escapeHtml(d.label)}</a>`).join('');
    return `<div class="pc-stage">
        <h4>${escapeHtml(s.target)}</h4>
        ${hero}
        <div class="dl-downloads">${dls || '<span class="pc-empty">No downloads</span>'}</div>
      </div>`;
  }).join('');
  host.innerHTML = `
    <h3>✓ ${escapeHtml(project.target || 'Project')} Complete</h3>
    <p>All stages approved — every deliverable below is ready to download.</p>
    <div class="pc-grid">${cards}</div>
  `;
}
