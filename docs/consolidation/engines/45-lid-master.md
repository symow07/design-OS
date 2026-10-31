# 45 · Lid master

`apps/pipeline/services/lid_master.py` · chain step: **None (Day 10); the colour maths**

## What it does today (read from its code)
`build` (:2166–:3030) is Day 10's print master of pick A-2.3: the sketch upscaled, finishes separated, live type, an
engine document (`engine_document` :1779), the relief plate; `master_facts` (:3032). The chain uses `srgb_to_lab`
(:109, sRGB to CIELAB D65, pure numpy), `delta_e00` (:122, CIEDE2000 after Sharma, Wu and Dalal), `REPO` and `rel`
(:1880). Other old modules take its constants and logo paths.

## The run ($0)
Pure red to Lab (the known value is 53.2408, 80.0925, 67.2032); ΔE00 between round 3's three shades; its Day 10
tests run.
Recorded in [runs/45.json](runs/45.json), made by `docs/consolidation/probe.py 45`. What came out:
- `red_lab`: [53.2408, 80.0925, 67.2032]
- `shade_de00`: {"#C9707A→#8E4A5C": 17.8, "#C9707A→#C2553A": 15.93, "#8E4A5C→#C2553A": 20.54}
- own tests (test_day10_master.py): **40 passed, 6 warnings in 34.12s**
- seconds: 35.1; files written: 0 (kept in the run folder, not committed)

## Verdict: PARTLY
Good: the colour maths. Old: the lid master itself.

## Parts worth keeping
- `srgb_to_lab`, `delta_e00` — the colour maths the dial and the fold check use.
