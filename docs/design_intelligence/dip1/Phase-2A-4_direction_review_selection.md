# Phase 2A-4 — Direction Review, Selection, and Gate-1 Resume

The first visible Phase 2A workflow: the pipeline **pauses after reasoning and before
rendering**. The user reads the Design Intent and three direction cards, chooses one, and
only then are images generated — three controlled variations of the chosen direction, which
proceed to the unchanged Gate 1.

## Workflow pause

`ARIAAgent.run()` routes on durable state, so a restart lands in the same place:

1. **planned + selected** → render variations of the chosen direction;
2. **planned, unselected** → re-assert `awaiting_direction_selection` and return — a
   restart never re-plans and never re-calls the Creative Director;
3. **legacy brief** (directions without `design_intent`) → the pre-2A pipeline, unchanged;
4. **nothing yet** → `_run_direction_planning()`: read-only DIP context (fail-soft, actor =
   `task.created_by`) → `run_structured()` → persist → pause.

No PromptEngineer call, no image call, no Gate-1 concepts exist while paused. No worker
waits: the pause is rows + status, nothing else.

## Persistence

One additive migration (`pipeline.0016_direction_selection`, `sqlmigrate` = three
`ADD COLUMN` + a no-op status-choices alter):

- `CreativeBrief.design_intent` — the `design_intent/1.1` document **minus** its directions
- `CreativeBrief.directions` — reused for the canonical three 1.1 direction cards
- `CreativeBrief.selected_direction_id` — the **stable** direction id; a list index is
  rejected as authority because display order carries none
- `CreativeBrief.direction_selected_at`

Resume reassembles `{**design_intent, "directions": directions}` and re-validates through
`validate_design_intent_document` before any use. Generator/context metadata goes to
`AgentLog.payload` (the existing observability channel), not to new fields.

## Task state

`awaiting_direction_selection` — Design Intent exists, three valid directions exist,
nothing selected, nothing prompted, nothing rendered. **Deliberately not a gate**: choosing
a reasoning direction is a pre-render planning decision; choosing a rendered concept at
Gate 1 remains a separate decision with its own audit trail.

## Direction review page

A new dashboard state panel (existing vanilla-JS conventions: `direction-state` div,
`render.js` dispatch, `directions.js`). It shows the full DESIGN INTENT block, exactly three
cards with every contract field (axis, concept, layout, hierarchy, color, typography, motif,
imagery, material/finish, tone, fit, target guidance, originality, prohibited choices,
risks, prompt seed), labelled DIP references (provenance + BLOCKED badges), and the banner:

**"REFERENCES INFORM DESIGN PATTERNS ONLY. THEY ARE NOT PRODUCTION INPUTS AND MUST NOT BE
COPIED."**

All values are HTML-escaped; no filesystem path, binary handle or operational control is
rendered.

## Selection

`POST /api/tasks/<id>/select_direction/` → `select_design_direction(task, user,
direction_id)` — Reviewer/Admin only, POST-only, CSRF-enforced. Inside one transaction with
`select_for_update` on task and brief: state must be `awaiting_direction_selection`, the
persisted document must re-validate, and `direction_id` must match exactly one persisted
card. Only the id crosses the trust boundary — a request cannot supply a direction object,
prompt, DIP references, target guidance, or an actor.

**Idempotency:** repeating the accepted choice returns the existing selection, changes no
timestamp and enqueues nothing. Choosing a different direction afterwards fails
`DIRECTION_ALREADY_SELECTED` (409) — switching after rendering begins needs a separately
designed restart workflow, out of scope. The resume job is enqueued via
`transaction.on_commit`, so only a committed selection generates.

## Resume and the three variations

`_generate_from_selected_direction()`: **zero** Creative Director calls, **zero** DIP
searches. One `PromptEngineerAgent` call in `variation_mode` — the same system prompt with
its "three DIFFERENT designs" clause surgically replaced (asserted at import) by the
variation contract: three executions of ONE direction, varying only composition emphasis,
typography placement, graphic density, imagery crop, finish emphasis and secondary color
distribution, preserving axis, concept, subject story, structure, originality constraints
and prohibited choices. Exactly **3** prompts or fail-closed before any image; then exactly
3 images, QA, and the existing bounded QA revision loop (re-running PE variations, never the
Creative Director). Gate-1 rejection and prompt reruns on 2A-4 tasks rebuild variations of
the **same** persisted direction.

## Gate 1

Unchanged mechanics, three concepts as always — now three variations inside the chosen
direction, each `GeneratedImage` carrying the direction name, prompt and variation number,
with the selection id and schema version in the brief and `AgentLog`. Review Board behavior
after rendering is untouched.

## Legacy compatibility

Legacy briefs (`design_intent == {}`) take the old path end-to-end — no pause, no
selection, no reinterpretation; old direction dicts stay readable through the compatibility
projection; serializers tolerate empty new fields. No data migration touches historical
rows, and no selection is back-filled.

## Failure and retry

Failed planning → `failed` with the validation codes, **no partial brief, no image call**.
Failed rendering after selection → `selected_direction_id` stays durable; retry reuses it.
Invalid persisted data or an unresolvable selected id → fail closed, never a fallback to
another direction.

## Exclusions

No DecisionEvent, governance decision, or permission of any kind; DIP references stay
text-only; no image request attaches a DIP asset or historical artwork; no semantic search;
no automatic asset/font selection; no IRE/Design Graph changes.
