# 40 · zilal_display

`apps/pipeline/services/zilal_display.py` · chain step: **None**

## What it does today (read from its code)
Day 12's family display sketch round: `sheet` (:60), the paid `sketch` (:115) and `rank` (:264), `crop` (:182) at the
die's proportion, `lettering_box` (:156), `header_facts` (:39). `drawn_panel` (:147) finds the drawn panel in a picture
(rows and columns more than half non-white, inset 2 px); the engine map says the face builder takes it, but nothing in
the flow calls it today (grep).

## The run ($0)
`drawn_panel` on round 3's drawn header, bottle and cap faces.
Recorded in [runs/40.json](runs/40.json), made by `docs/consolidation/probe.py 40`. What came out:
- `header`: {"size": [1223, 928], "panel": [2, 2, 1221, 926]}
- `front`: no face.png (the round has none for this face)
- `bottle`: {"size": [309, 1440], "panel": [2, 2, 306, 1438]}
- `cap`: {"size": [720, 1440], "panel": [4, 2, 718, 1438]}
- seconds: 0.1; files written: 0 (kept in the run folder, not committed)

## Verdict: UNUSED BY THE GOAL

## Parts worth keeping
- nothing the chain calls.
