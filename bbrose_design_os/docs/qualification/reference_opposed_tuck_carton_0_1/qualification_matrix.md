# Qualification matrix — reference_opposed_tuck_carton/0.1

Phase 2A-9B §5/§6/§7. Every SUPPORTED row passed all §3 invariants AND the four-stage folded-closure checks on the actual flap outlines. Rendered previews live in `renders/` (all previews as SVG; three representative folded diagnostics kept as PNG — the rest regenerate deterministically).

| Case | inner W×D×H | t | outcome | geometry hash | folded | closure face | dust depth | mfg | outer | binding violation |
|---|---|---|---|---|---|---|---|---|---|---|
| small_shallow | 34.0×12.0×61.0 | 0.5 | SUPPORTED | `7c2612a4c1c6` | ALL PASS | 12.0 | 15.25 | 35.0×13.0×62.0 | 36.0×14.0×63.0 | — |
| small_deep | 40.0×19.0×65.0 | 0.5 | SUPPORTED | `b2d45f8a4bf7` | ALL PASS | 19.0 | 18.75 | 41.0×20.0×66.0 | 42.0×21.0×67.0 | — |
| medium_shallow | 70.0×15.0×100.0 | 0.5 | SUPPORTED | `23efd35f4ede` | ALL PASS | 15.0 | 16.75 | 71.0×16.0×101.0 | 72.0×17.0×102.0 | — |
| medium_deep | 70.0×49.0×110.0 | 0.5 | SUPPORTED | `2fc5c597ba46` | ALL PASS | 49.0 | 33.75 | 71.0×50.0×111.0 | 72.0×51.0×112.0 | — |
| large_shallow | 250.0×40.0×300.0 | 0.8 | SUPPORTED | `8a1cf6b5abe5` | ALL PASS | 40.0 | 29.4 | 251.6×41.6×301.6 | 253.2×43.2×303.2 | — |
| large_deep | 279.0×258.0×320.0 | 0.8 | SUPPORTED | `c157c49cd6c9` | ALL PASS | 258.0 | 138.4 | 280.6×259.6×321.6 | 282.2×261.2×323.2 | — |
| tall_narrow | 33.0×12.0×590.0 | 0.3 | SUPPORTED | `dc54e1018a13` | ALL PASS | 12.0 | 15.15 | 33.6×12.6×590.6 | 34.2×13.2×591.2 | — |
| nearly_square | 95.0×74.0×96.0 | 0.5 | SUPPORTED | `ef15c2832127` | ALL PASS | 74.0 | 46.25 | 96.0×75.0×97.0 | 97.0×76.0×98.0 | — |
| task_50_exact | 90.0×32.0×92.0 | 0.5 | SUPPORTED | `0f5b8bf6bc2a` | ALL PASS | 32.0 | 25.25 | 91.0×33.0×93.0 | 92.0×34.0×94.0 | — |
| inside_dust_pair_boundary | 52.5×32.0×92.0 | 0.5 | SUPPORTED | `05819cdbbc5d` | ALL PASS | 32.0 | 25.25 | 53.5×33.0×93.0 | 54.5×34.0×94.0 | — |
| outside_dust_pair_boundary | 52.0×32.0×92.0 | 0.5 | REJECTED_BY_DOMAIN | `` | — | — | — | — | — | DUST_PAIR_CLEARANCE |
| outside_height_rule | 92.0×32.0×92.0 | 0.5 | REJECTED_BY_DOMAIN | `` | — | — | — | — | — | HEIGHT_GT_WIDTH |
| inside_board_max | 90.0×32.0×92.0 | 1.0 | SUPPORTED | `324f84a74a85` | ALL PASS | 32.0 | 25.5 | 92.0×34.0×94.0 | 94.0×36.0×96.0 | — |
| outside_board_max | 90.0×32.0×92.0 | 1.01 | REJECTED_BY_DOMAIN | `` | — | — | — | — | — | BOARD_RANGE |
| outside_glue_clearance | 34.0×12.0×61.0 | 0.5 | REJECTED_BY_DOMAIN | `` | — | — | — | — | — | GLUE_CLEARANCE |
| inside_depth_floor | 90.0×12.0×92.0 | 0.5 | SUPPORTED | `a18de635d3be` | ALL PASS | 12.0 | 15.25 | 91.0×13.0×93.0 | 92.0×14.0×94.0 | — |
| outside_depth_floor | 90.0×11.9×92.0 | 0.5 | REJECTED_BY_DOMAIN | `` | — | — | — | — | — | DEPTH_RANGE |

Dimension conversion (§7): inner = requested; manufacture = inner + 2t per axis; outer = manufacture + 2t; closure stack 2t/end; score compression NOT modelled in 0.1 (physical-sample assumption); headspace 0. Conversions vary with t — see the t column (0.3 / 0.5 / 0.8 / 1.0 rows).

Task #50 is one row among nine structural fixtures — not the only golden fixture.
