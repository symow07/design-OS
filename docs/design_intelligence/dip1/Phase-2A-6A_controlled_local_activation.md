# Phase 2A-6A — Controlled Local Activation Smoke Test

Activated the standard vector packaging pipeline **in local development only**
and ran it. The committed default stays `False`; the flag lives in the
git-ignored `.env`.

Commits: `2ecdcfd` auto-bottom provisional classification · `1362a90`
activation guard + five defects found by running it · this document.

## Outcome: NEEDS_PIPELINE_CORRECTION (corrections applied, re-validation required)

The workflow works end to end, but only after five defects that the 1 770-test
suite did not catch. One of them destroyed real data. A second local
validation is needed after the task-#47 printed-information record is
re-entered.

## Auto-bottom classification

`tuck_top_auto_bottom_carton/1.1` is `PROVISIONAL_STRUCTURE` /
`PRODUCTION_INELIGIBLE`, blocking code `MEASURED_REFERENCE_REQUIRED`, with its
limitations recorded (crash-lock panels not independently modelled, adhesive
regions incomplete, diagonal folds unmeasured, the four lock flaps merge into
one shape). The production chooser offers exactly:

- `straight_tuck_end_carton/1.1`
- `reverse_tuck_end_carton/1.1`
- `skynte_foundation_tuck_carton/1.0`

Excluded: all generic `1.0` (defective creases, `NON_PRODUCTION_TEMPLATE_VERSION`)
and both auto-bottom versions. Everything stays buildable for inspection and
historical reproduction.

## Activation guard

`apps/dielines/checks.py` refuses activation unless `ENVIRONMENT` **declares
itself** `LOCAL_DEVELOPMENT`, `DEBUG` is on, the database is an allow-listed
local one (name *and* host — a tunnelled production DB also answers on
localhost), and every migration is applied. A missing ICC profile warns rather
than blocks, since that is the expected local state.

## Defects found only by running it

1. **libpq/GSSAPI fork crash.** Celery prefork children died with SIGSEGV and
   no Python traceback. The macOS crash report named
   `pg_GSS_have_cred_cache → gss_acquire_cred → xpc_connection_resume`: libpq
   negotiates GSSAPI on connect and XPC is not fork-safe. Fixed with
   `DB_GSSENCMODE` (default `disable`). Solo pool was unaffected, which is
   what isolated it.
2. **The dimension gate dropped the structural fields.** It built a fixed
   six-key dict, so an explicitly chosen template and the supplied
   inner/outer dimension sets never reached ARIA — selection could not see a
   user choice, and reconciliation silently fell back to model-derived values.
   It also validated every request as generic STE.
3. **Panel typography read the wrong source.** It used the dieline metadata
   instead of the verified print-data record, so a task with no `Product` row
   composed with **no product name on the front panel**.
4. **Regeneration destroyed verified printed data.** `panel_info` was rebuilt
   from `Product`/`Brand` defaults and written over the stored record. See the
   incident below. Precedence is now stored record → defaults, reviewer
   override last, plus a hard `VERIFIED_PRINT_DATA_WOULD_BE_LOST` stop.
5. **The structural comparison was Skynte-specific.** It indexed side-seam-only
   derived keys (crashing the standard path for every generic template) and
   its required-feature list was the Skynte die's, producing false
   `MISSING_CLOSURE_GEOMETRY`. Required features are now derived from the
   **template registry** — each template is checked against what it declared —
   and the engine publishes its geometry version so a v1.0 job is checked
   against v1.0's contract.

Also: the suite was **not hermetic** against the flag. Three tests read the
ambient environment and flipped when a developer activated locally. They now
pin the setting, and "the committed default is off" is asserted against the
settings **source**.

## DATA INCIDENT — task #47 printed information

The first replay (before defect 4 was found) overwrote task #47's verified
printed-information record: product name, description, directions, warnings,
net weight, item number, barcode, QR, regulatory block and the ES/AR
translations.

**No structured copy survives** in the database or on disk. The content is
still visible in the accepted DIE-5 artifacts
(`design_preview_task_47_corrected.ai`, `_production.pdf`), which are intact,
but it was **not** re-typed from rendered output: reflowing wrapped regulatory
text risks corrupting legal copy, and inventing regulatory data is forbidden.

Task #47 was restored to its accepted DIE-5 deliverables and left at
`awaiting_gate_2`, unapproved, with the incident recorded on the output as
`panel_info_incident`. **Action required: re-enter the printed information at
the dimension gate.** Until then Gate 2 stays blocked.

## Validation results

**Task #47 standard-path replay** — reached Gate 2 through the normal flow
with no task-specific script: template resolved through the registry as
`skynte_foundation_tuck_carton/1.0` from `EXPLICIT_USER_CONFIRMATION`, panel
order `glue_tab | side_left 32.3 | front 42.0 | side_right 32.3 | back 42.6`,
reconciled with the supplied inner/outer sets and all assumptions reported, no
discrepancies, all six collision checks pass, artwork
`NATIVE_VECTOR_RECONSTRUCTION` with **0 decorative rasters** and the single
`BRAND_LOGO_RASTER_FALLBACK`. **Zero** Creative Director, DIP, Prompt Engineer
or image calls — `ApiCallRecord` unchanged at 164 throughout.

**STE 1.1 diagnostic** — explicit version selected, panel order matches the
registry, cut/fold conflict 0 mm, hinges present, slits and notches cut,
bleed/safe valid, structure page renders, confirmation idempotent, no artwork
before confirmation, then native-vector composition with 0 decorative rasters
and panel-specific emphasis. Gate 2 blocked **only** by `MISSING_OUTPUT_INTENT`
and print data — no structural or artwork failures.

**Reverse tuck 1.1** — opposing tuck orientation confirmed, panel roles match
the registry, 0 mm conflict, no mirrored slit error, production-ready, and an
unpinned caller resolves to 1.1 rather than the defective 1.0.

## UI

Present and correct: template ID/version, panel sequence, dimensions, closure,
structure source, confidence, assumptions, geometry hash, collision results.
**Added during this phase** (they were missing): production eligibility with
the ineligibility code and limitations, the cut/fold result, contour state,
confirmation timestamp, and the `PREVIEW_ONLY_NO_OUTPUT_INTENT` warning.

## Guardrails held

No DecisionEvent (still 3), no permission change (Designer 1, Reviewer 0,
Admin 0), no governance selection, no semantic query, no automatic asset or
font selection, no OpenAI or Anthropic call, no invented regulatory data, and
Phase-1 quarantined metadata untouched. The committed default remains
`STANDARD_VECTOR_PACKAGING_PIPELINE=False`.

## Before local default

1. Re-enter task #47's printed information; re-run the replay.
2. Confirm the prefork fix on a clean worker boot.
3. Supply a CMYK press profile if any file is to clear Gate 2.
