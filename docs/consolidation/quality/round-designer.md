# The round designer — quality

**Job:** research, the three mood boards, the three designs painted on the flat die, the pick page.
File: `apps/pipeline/services/round_designer.py`.

**The bar, in numbers:** research from six Tavily searches with their sources, the house library by words and colours;
three boards; per board pick, three designs, each painted on the engine's flat die template (0 pixels off the die
differing from the template); a sealed `flat_die_handoff/1`; never a call bought twice.

**Before → after, same input.** The parts moved in — the Tavily connector (21), the brief contract (14), the copy
delimiters, `_line`, `_validation`, `read` (13) — are identical to their donors, 7 of 7 (`runs/moved-parts.json`), so
on any input the output is the donors' own. The flow's own test on its fixture input
(T/test_round_flow.py::test_designer_flow_runs_from_start_to_the_frozen_handoff_with_one_redo_per_pick) passes at
26db887 and now: 6 Tavily queries, 3 boards, 12 design images (with one redo per pick), stand template schema
`counter_tray_header/product-grid-2`, proof `differing_from_template == 0`, the sealed handoff.

**Verdict: SAME.** Reason: the merge moved its parts verbatim and ended three duplicate homes for them; it was not
meant to change what the designer makes. Since then the hand-off it seals reaches the files build (it was refused:
`FLAT_PICK_WAITS`, removed in `15cbaac`).

**Weakest point:** the paid steps (research, boards, designs) cannot be measured at $0, and nothing scores a design's
quality before the owner sees it; a flat pick's faces carry no live type until the files build sets it.
