# The writer — quality

**Job:** the layered .ai per object: live type in the pinned fonts, the approved logo, the die locked on its layer;
Illustrator's own save and reopen. File: `apps/pipeline/services/round_files_export.py`.

**The bar, in numbers:** every object's read-back checks pass (15); Illustrator saves and reopens it with its save (14)
and reopen (13) checks passing; Arabic shaped (arabic_reshaper + bidi), every glyph in the pinned face (no missing).

**Before → after, same input.** The parts moved in (`glyph_metrics`, `shaped`, `FONT_PATHS`, `rgb`, `set_layers`,
`raster`) are identical to their donor, 6 of 6 (`runs/moved-parts.json`). Round 3's objects:

| | Before (`chain-after-native.json`, stand-in faces) | After (`chain-live-1029.json`, the real faces) |
|---|---|---|
| bottle-front.ai, cap.ai, stand.ai read-back | 15 checks each, 0 failed | 15 checks each, 0 failed |
| Illustrator save / reopen | 14 / 13 each, 0 failed | 14 / 13 each, 0 failed |
| the stand's raster in stand.ai | 59.8 ppi | 300 ppi |

**Verdict: SAME.** Reason: the writer's own code moved verbatim and writes the same layers and type; the stand's raster
is better because the face builder composes it at 300 ppi, not because the writer changed.

**Weakest point:** the live type's layout on the bottle front (the eye's note: the Arabic line small and crowded,
"Lip Gloss" near the wordmark's size) is the type setter's and was not changed here; the writer needs Illustrator on the
machine for its native checks.

Annotation, 2026-10-30 (the owner's part 1, CURRENT_DECISIONS.md): the writer's layers are now PAINTING, FOIL, RELIEF, TYPE, LOGO, DIE and GUIDES. It refuses a fitted piece, and `print_check` reads every written file: round 4's stand of revision 2 fails it (five layers a print file never has, 4,053 pieces over the painting, 449.9 mm² off the die).
