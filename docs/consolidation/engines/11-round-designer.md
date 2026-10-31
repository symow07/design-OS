# 11 · Round designer (New design)

`apps/pipeline/services/round_designer.py` · chain step: **Research, boards, board pick, the die first, designs, the pick**

## What it does today (read from its code)
The ideas half as one module. `research` (:304): six Tavily searches from fixed topic words (`search_queries` :114,
never the brand), the library's twelve matches (`library_matches` :243, house-tier previews by the brief's words and
each shade's colour, the image guard's denylist), one Claude call that keeps every source with a takeaway. `boards`
(:490): one plan call, three board pictures (bold, refined, unexpected) with at most three library references.
`board_pick` (:530), `die_first` (:549: the stand solved from the brief by round_files_stand and its flat template by
counter_display_files), `designs` (:650: each design one edit of the template with the board as style), `flat_drawings`
(:626: folded and loaded drawings), the quick check (`check_prompt` :702), `pick_page` (:753) and `finalize_pick` (:789).
It takes COPY_START/COPY_END, `_line`, `_validation` and `read` from round_ideas.

## The run ($0)
Round 3's brief at $0: the six queries; the library's matches compared with the round's own library.json; the die
solved from the brief alone and its template sheet drawn; the boards prompt built; the designer tests of the round flow
file run.
Recorded in [runs/11.json](runs/11.json), made by `docs/consolidation/probe.py 11`. What came out:
- `queries`: [{"topic": "category", "query": "lip gloss packaging and counter display design"}, {"topic": "launches", "query": "new lip gloss launches 2026"}, {"topic": "materials", "query": "lip gloss packaging materials"}, {"topic": "finish…
- `library`: {"matches": 12, "same_as_round3": true, "round3_matches": 12}
- `die_first_from_brief`: {"stand_mm": {"width": 110.0, "depth": 85.0, "height": 160.0, "board_thickness": 1.5}, "header_mm": [107.0, 58.5], "frame": "1024x1536", "dpi_at_1to1": 78.1, "sheet": {"size_px": [1024, 1600], "mode": "RGB", "bytes": 41642, "sha2…
- `boards_prompt_chars`: 10580
- own tests (test_round_flow.py, -k "designer"): **6 passed, 35 deselected, 7 warnings in 9.60s**
- seconds: 33.2; files written: 8 (kept in the run folder, not committed)

## Verdict: GOOD

## Parts worth keeping
- `search_queries`, `tavily_searches`, `library_matches`, `research` — research as a designer does it, every source kept.
- `boards_prompt`, `board_image_prompt`, `boards`, `board_pick` — the three boards.
- `die_first`, `designs_prompt`, `design_image_prompt`, `designs`, `flat_drawings`, `check_prompt`, `pick_page`.
