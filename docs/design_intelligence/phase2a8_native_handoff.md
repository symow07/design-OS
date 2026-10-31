# Phase 2A-8 — Native Illustrator Named-Layer Handoff

Completes the designer handoff: the canonical Design Graph becomes a
deterministic Illustrator handoff package alongside (never replacing) the
existing PDF-compatible preview deliverables.

## Output modes

| Mode | What it is |
|---|---|
| `PDF_COMPATIBLE_AI_PREVIEW` | The existing ReportLab `.ai`/PDF deliverables — unchanged. |
| `ILLUSTRATOR_JSX_NATIVE_HANDOFF` | `design_handoff.jsx` + `design_graph.json` + `handoff_manifest.json` (+ `assets/` with the controlled logo fallback), generated **explicitly** via `POST /api/tasks/<id>/generate_handoff/`. |

## Package contents

- **design_handoff.jsx** — data-driven ExtendScript: the serialized
  `illustrator_handoff_graph/1.0` embedded as a plain object literal (no
  eval) + a fixed bounded runtime that reconstructs the native document.
- **design_graph.json** — the bounded reconstruction input (versioned
  schema; no prompts/credentials/source paths/timestamps).
- **handoff_manifest.json** — schema/emitter versions, task id, graph /
  geometry / jsx / layer-tree hashes, font references (no binaries),
  swatch + spot inventories, expected census + layer tree, linked assets,
  production blockers, execution-verification state.

## Illustrator document structure

Root layers `00_REFERENCE_NONPRINTING` … `14_TECHNICAL_NOTES` in mandated
order; `05_PANEL_ARTWORK` carries FRONT/BACK/SIDE_*/flap sublayers; semantic
groups come from the Design Graph (`constellation-core`, `logo-frame`,
`product-name`, `panel-continuation`, …) — never anonymous. Cut/fold live
isolated on locked layers stroked in the `CUT`/`CREASE` spot swatches;
reference/guide/notes layers are non-printing. Finish layers
(`10_FINISH_SPOT_UV` … `13_FINISH_FOIL`) hold dashed outline **spot masks**,
never process-painted decoration; final overprint/separation settings
require prepress review.

## Typography and assets

Live point text in the exact requested PostScript faces (task #50:
`BarlowCondensed-Bold` for the name, `NotoSans-Regular` supporting). A
missing face → `ILLUSTRATOR_FONT_MISSING`; never a silent substitute, never
auto-outlining. Fonts ship as *references* — install the listed faces
before running the script. The BBROSE logo remains
`BRAND_LOGO_RASTER_FALLBACK` on `06_BRAND`, the package's only asset.

## Verification

`validate_handoff` (§12 codes) compares Design Graph ↔ serialized graph ↔
expected layer tree ↔ a **real Illustrator inspection** captured by
`apps/ire/handoff/illustrator_exec.run_jsx` (osascript `do javascript`).
Without a real run the state is `ILLUSTRATOR_EXECUTION_VERIFICATION_REQUIRED`
— a mocked object model never counts. First real execution (Illustrator
2026, this machine): 15 root layers, 16 groups, 4 live text frames, 187
path items, 11 swatches + 6 spots, zero runtime errors;
`ILLUSTRATOR_FONT_MISSING` correctly reported because the referenced faces
are not installed system-wide — the honest, designed behavior.

## Script safety

No eval, no network, no shell, no writes; assets resolve only from
`./assets` next to the script; all text ships ASCII-escaped inside the data
literal; modal dialogs are suppressed during automated runs and restored.

## Determinism

Same graph → byte-identical jsx/json/manifest; hashes cover graph, jsx and
layer tree; IDs are traversal-ordered; floats rounded to 4 decimals; no
timestamps in canonical content.
