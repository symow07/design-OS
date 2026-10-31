# 49 · Live type and fonts

`apps/ire/font_pool.py (+2)` · chain step: **Live type (the fonts the writer may use)**

## What it does today (read from its code)
`font_pool` (223 lines) reads the GRANTED, unverified and blocked font census (Day 6) and the exclusions (Day 7):
`pool` (:14), `files_of` (:19), `excluded` (:55), `is_excluded` (:68), plus the type book's `classify`,
`catalogue_entries`, `chain`, `day7_grants`. The writer uses only `files_of('granted')` and `is_excluded`.
`lettering` (1,668 lines) builds a logotype from a licensed face's outlines (`set_word` :590, `logotype` :1292);
`arabic_display` (1,334 lines) derives Arabic display fonts through HarfBuzz (`derive` :405, `ensure_chosen` :1141).

## The run ($0)
The GRANTED census's size, the exclusions, and the two faces the writer validates; the Day 7 font tests run.
Recorded in [runs/49.json](runs/49.json), made by `docs/consolidation/probe.py 49`. What came out:
- `granted_files`: 337
- `excluded`: 4028
- `writer_fonts`: {'latin': {'path': '/Users/symow/Desktop/bbrose-systemOS/materials/fonts/dm-sans/fonts_dm-sans_dmsans-regular_1adb096acaa3d14f.ttf', 'sha256': '1adb096acaa3d14f5ed678e99b808b0c8800f62cb342fa5c276298ad8030b458', 'postscript_name':…
- own tests (test_day7_fonts.py): **4 passed in 0.83s**
- seconds: 1.7; files written: 0 (kept in the run folder, not committed)

## Verdict: PARTLY
Good: the census reader. Unused by the chain: `lettering` and `arabic_display` (the old pipeline's type book).

## Parts worth keeping
- `font_pool.files_of`, `is_excluded` — the licence check the writer makes on its two pinned faces.
