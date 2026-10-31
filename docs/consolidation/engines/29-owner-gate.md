# 29 · Owner gate

`apps/pipeline/services/round_files_gate.py` · chain step: **The owner accepts or redraws each face; Make my files**

## What it does today (read from its code)
The face as the unit: `work` (:297) draws each face job (a stand face cut from the flat painting, a product face as one
edit), places its type, previews it and asks the eye once (`advise` :206, advice only); `accept` (:365), `redraw`
(:383, one edit with a one-line note; a stand face repaints only its own face), `ready` (:414), `make_files` (:426) and
`make` (:440: every accepted face checked by hash, the objects written, the die's files from counter_display_files,
the zip). `flat_page`, `open_flat`, `flatten`, `migrate`, `restand` move older builds onto the die-first method.

## The run ($0)
Each face's size on round 3's die; the gate's tests (accept, redraw, make) in the face file run.
Recorded in [runs/29.json](runs/29.json), made by `docs/consolidation/probe.py 29`. What came out:
- `face_sizes_mm`: {"header": [107.0, 78.25], "header_back": [107.0, 79.75], "front": [107.0, 18.2], "side": [82.0, 143.78], "left": [82.0, 143.78], "back": [107.0, 143.78], "bottle": [15.0, 70.0], "cap": [15.0, 30.0]}
- own tests (test_round_files_faces.py, -k "accept or redraw or make or gate"): **5 passed, 16 deselected, 9 warnings in 23.23s**
- seconds: 24.3; files written: 0 (kept in the run folder, not committed)

## Verdict: GOOD

## Parts worth keeping
- `work`, `accept`, `redraw`, `ready`, `make_files`, `make`, `die_sizes`, `restand`.
