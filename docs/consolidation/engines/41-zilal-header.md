# 41 · zilal_header

`apps/pipeline/services/zilal_header.py` · chain step: **None**

## What it does today (read from its code)
`build` (:186) makes Day 12's display header master from the ranked sketch (`the_pick` :38 reads ranking-map.json):
it splits the painted words into hero, name and logo (`word_groups` :97, `merge_lines` :119, `name_likeness` :139),
takes the lid's vectors (`lid_assets` :151) and writes header-master.pdf, a 300 ppi flat and a finish proof into Day 12's
folder.

## The run ($0)
Its Day 12 pick read; its master built again into a scratch folder.
Recorded in [runs/41.json](runs/41.json), made by `docs/consolidation/probe.py 41`. What came out:
- `the_pick`: ('S3', "J1's first, by default (no PICK file or word from the owner in the 20 minutes)")
- `build`: {"error": "ValueError: '/private/tmp/claude-501/-Users-symow-Desktop-bbrose-systemOS/30f0304e-e898-4b25-abe2-64d34d90a910/scratchpad/runs/41/header/header-master.pdf' is not in the subpath of '/Users/symow/Desktop/bbrose-systemOS…
- seconds: 94.7; files written: 9 (kept in the run folder, not committed)

## Verdict: UNUSED BY THE GOAL
Its build refuses any folder outside the repository (every record path is made relative to it).

## Parts worth keeping
- nothing the chain needs (round_files_dial places the round's header type).
