# OWNER BLOCKER SESSION — the four things no node can clear

Written 2026-08-11. Verified against the working copy, not against memory.
Every claim below cites the file it came from.

---

## FIRST — A CORRECTION TO WHAT I TOLD YOU

I said "zero of five supplier requests are sent" and told you to spend the hour
there. Two things were wrong with that, and you should know both before you
spend any time.

**One. The five drafted emails are not about the palette.** I read all five
`.eml` files in `docs/production_authority/supplier_emails/`. Every one of them
opens:

> "We are specifying packaging for a 30 ml cylindrical frosted-glass cosmetic
> serum bottle with a metallic collar and dropper closure."

That is P1, the dropper bottle — the fixture you froze. The palette programme
needs ES3083 palette geometry, which those emails never mention. Sending all
five today would move `supplier_requests_sent` from 0 to 5 and would not tell
you one thing about the palette. It would clear a counter, not a blocker.

**Two. You already decided this, deliberately.** `supplier_outreach_deferral.json`,
dated 2026-07-31, records:

> `"SUPPLIER_OUTREACH": "DEFERRED_UNTIL_REAL_SUPPLIER_ENGAGEMENT"`
> `"decided_by": "PROJECT_OWNER"`
> `"reason": "the owner has decided not to contact generic external suppliers
> during the current Design OS development phase"`

So the zero is a decision, not neglect. The record is careful about what that
decision does and does not buy you — it says plainly that
`"deferring the outreach does not pass Gates B to E and does not grant any
production authority. They are simply no longer the active blocker for
platform development."` That is the correct reading and it still holds.

**What survives from what I said.** The four blockers really are the only
things standing between you and a client-approvable deliverable, and none of
them is closed by another closure node. That part was right. The priority
order was wrong. Corrected order is below.

---

## THE ACTUAL BLOCKER SET, AS THE REPOSITORY RECORDS IT

From `docs/roadmap/palt_m4c/palette_roadmap_continuation_state.json`, the
`blockers` array — four entries — plus two more the M6 defect inventory adds
at `docs/roadmap/palt_m6/open_defect_inventory.md` §D:

| id | kind | who can clear it |
|---|---|---|
| `VQ1_HUMAN_STRUCTURAL_REVIEW` | OWNER_JUDGMENT | **you, in a browser, today** |
| `ES3083_DIMENSIONS_UNREADABLE` | EVIDENCE | **you, by obtaining a source** |
| D5 — colour authority absent | EVIDENCE | **you, by specifying shades** |
| `MATERIALS_LIBRARY_ABSENT` | EXTERNAL | you, by locating the sources |
| `SUPPLIER_DATA` | EXTERNAL | deferred by your own decision |
| D6 — 41 renders not produced | CODE | Claude Code, gated behind the above |

The three in bold are the ones that gate M7. Do them in that order.

---

## STEP 1 — CONFIRM THE M4C-4 PANEL — ✅ CLOSED 2026-08-12

**Done.** The panel was confirmed on task 9, three times, each version
surviving by identity: v1 `e2e81bcd60d7f35f` / 20 actions, v2
`ad8dc32c8987f953` / 21 actions, v3 21 actions with `regulatory_zones`
confirmed. Gate decisions 57 and 58. Scope `VISIBLE_COMPOSITION_ONLY`. The
draft `9b3603e17e85746c` was never mutated.

You also corrected and reclassified `pan_count`, `rows` and `columns` to HARD,
which is why the twelve-pan 4×3 grid is now the firmest geometry in the
programme rather than a 0.55-confidence image read.

As the section below always said it would, confirming granted no gate approval.
All four programme flags are unchanged at every version:
`PALT_P1_FINAL_DIMENSIONS NOT_APPROVED`,
`PALT_P1_MANUFACTURING_AUTHORITY NOT_ESTABLISHED`,
`PALT_P1_OWNER_APPROVAL NOT_GRANTED`, `GATE_2 BLOCKED`. That is correct
behaviour, not a shortfall.

**Three blockers remain: steps 2, 3 and 4 below.**

The original instructions are kept below for the record.

`open_defect_inventory.md` D4 was blunt about it:

> "The M4C-4 confirmation panel was served but never confirmed by the owner in
> a browser. No amount of engineering closes this one."

**A naming trap to know about first.** There are two different things wearing
this name. The blocker `VQ1_HUMAN_STRUCTURAL_REVIEW` in the continuation state
points at the *palette* confirmation panel. The file
`docs/visual_quality/vq1/vq1_human_structural_review.json` is about the
*bottle* — its rejection codes are `VQ_BULB_SPEAR_OR_LEAF_SHAPE`,
`VQ_COLLAR_GENERIC_BOX_FALLBACK`, `VQ_SHOULDER_CALIBRATION_POLYGONIZED`, and it
sits at `state: REVISION_REQUIRED` from 2026-07-28. That one belongs to the
parked bottle arc. Do not confirm the palette panel and think you have moved
the bottle record, and do not let a status report conflate them. Flagging it
now because the shared name is exactly the kind of composite the programme's
own 2x amendment exists to catch.

**The route exists and is wired.** From `apps/dashboard/urls.py`:

```
palette/intent-confirmation/              -> read-only preview, no task
palette/intent-confirmation/<int:task_id>/ -> the governed confirmation
```

The bare route is deliberately a preview only. The comment in the file says
why: *"a confirmation needs something to be recorded against."* You must use
the task-scoped URL or nothing is recorded.

**What to do:**

1. In the repo, start the server: `python manage.py runserver`
2. Find the palette task id. If you do not know it, ask Claude Code — the
   `OWNER-BLOCKER-SUPPORT` launcher (delivered separately, in chat) has it as
   its first job, B1.
3. Open `http://127.0.0.1:8000/dashboard/palette/intent-confirmation/<task_id>/`
4. Read the panel. It renders the ES3083 design reading plus an understanding
   overlay. Per-field owner corrections are accepted — `views.py:165` handles
   them.
5. Confirm, or correct and confirm. **Either outcome clears the blocker.** A
   correction is a result. The blocker is that no owner judgment exists, not
   that no approval exists.

**What confirming does NOT do.** `views.py` and the flow service are explicit
that a confirmed reading does not grant gate approval — there is a whole node
in the history titled *"confirmed reading must not grant gate approval"*
(commit `8dfbc49`). You are confirming that the system read your design intent
correctly. You are not approving dimensions and you are not granting
manufacturing authority. Those stay `NOT_ESTABLISHED`.

---

## STEP 2 — GET A READABLE ES3083 DIMENSION SOURCE — ⚠️ LARGELY SUPERSEDED 2026-08-13

**Route A did not need to be requested from anyone. The vector file was already
in the repository**, at `materials/historical AI production designs/ES3083吸塑
展盒刀线.ai`, inside a catalogue of roughly ninety sibling `.ai` files. You told
me it was there; I had written below that it was not. You were right.

Findings are in `ES3083_DIMENSION_FINDINGS.md`. In short: the file is authored
at true scale on exact millimetres, and it yields the display-box dieline, the
lid artwork at **65.00 × 65.00 mm**, the back label at 49.50 mm square, the 24
blank shade labels at 77.00 × 16.00 mm, the two Pantone Lab transforms, and a
declared **NET WT 11 g**. It carries no dimension callout anywhere, and the
palette illustration on it is a stylised perspective drawing that may not be
measured. So the pan cavity is still not measured — but it is now bounded by
two independent measurements rather than unknown.

Route B (the vendor email) survives as a much shorter ask. Route C (calipers)
is now the single thing that would close this outright. Route D is spent — the
tray photograph is a bagged clear blister with a handwritten code, nothing
more. The text below is kept because its reasoning about authority tiers still
governs.

---

I opened `media/references/ref_ES3083吸塑_展盒刀线.png` and read it directly.
The record is accurate: **there is no readable millimetre value anywhere on
that sheet.** What is on it is a display-box dieline, a photograph of the
thermoformed tray, a blank shade-label grid, the two Pantone chips (621 C and
627 C), and the artwork lockups. No dimension callouts, no scale bar, no ruler.

Because of that, `palt_m4c_es3083_authority.json` correctly fences the whole
sheet: the dieline is `PACKAGING_ONLY — MUST NOT be used as palette product
geometry`, and every P1B dimension is
`PROVISIONAL_DESIGN_DEFAULT_NO_AUTHORITATIVE_SOURCE`. Everything geometric
downstream inherits that. `palette_baked_clearance.py:100` stamps the
provisionality onto its own outputs, which is the system behaving correctly.

You have four routes to a real number. They are not equally good.

**Route A — the original vector file. Best, if it exists.**
The filename ends 展盒刀线, "display box dieline." A dieline is authored at
scale in vector form. Somebody sent you a PNG render of a file that has real
coordinates in it. If you can get the source `.ai`, `.pdf`, `.dxf` or `.cdr`
from whoever supplied it, the *packaging* dimensions become exact immediately.
Be clear-eyed about the limit: this gives you the display box, and the
authority file says the display box may not be used as palette product
geometry. Valuable, but it is not the palette.

**Route B — the ES3083 spec sheet from the vendor who catalogues it. Best for
the palette.**
ES3083 is a catalogue code. Whoever assigned it has a spec sheet with case
outer dimensions, pan cavity dimensions, pan count and tray depth. One email to
that vendor asking for the dimensioned drawing for ES3083 is worth more to this
programme than all five drafted bottle emails combined. If you know who they
are, this is a ten-minute task. **This is the single highest-value thing you
can do today.**

**Route C — measure a physical sample. Good, and fully in your control.**
If you hold an ES3083 palette, digital calipers and thirty minutes give you
real numbers. Measure and record: case outer length, width and closed height;
lid height and base height separately; tray outer footprint; pan cavity length,
width and depth; pan pitch centre-to-centre in both axes; wall thickness; hinge
offset from the rear edge. Record each as measured, with the instrument named
and the tolerance you can actually hold — calipers on moulded plastic are good
to roughly ±0.05 mm on the tool and rather worse on the part.

The programme will accept this. But it will accept it as `OWNER_MEASURED`, not
as `MANUFACTURING_AUTHORITY`, because one sample is not a tolerance and a
measurement is not a drawing. That distinction has to survive into the record
or you have manufactured authority you do not have — which is the failure mode
this whole protocol was built to prevent.

**Route D — the tray photograph, at higher resolution. Cheap, worth a look.**
Top-left of the sheet there is a photograph of the thermoformed tray with a
small paper label sitting in it, carrying handwritten text. At the resolution
in the repo it is illegible. If you have the original photograph at full size,
that label may carry the product code and a dimension. Five minutes to check,
and occasionally these things pay.

**Do not do this:** do not let anyone scale off the PNG. There is no scale
reference on that sheet, the tray is photographed in perspective, and
`D_PRESENTATION_ONLY` in the authority file already rules camera perspective
`IGNORED — not actual proportion`. A number derived that way would be a
fabricated measurement wearing a real number's clothes, and the programme has
already had to quarantine three of those.

---

## STEP 3 — ESTABLISH COLOUR AUTHORITY FOR THE TWELVE SHADES — ✅ DECIDED 2026-08-13

**All twelve shades are settled.** Seven ACCEPT, four RECOLOUR, one REPLACE,
and the last open field — Midnight Bloom's finish — closed as POWDER_METALLIC.
The decisions, the reasoning behind each recolour, and the finish distribution
are in `SHADE_AUTHORITY_PROPOSAL.md`.

**Decided is not recorded.** The twelve are still a root-level markdown brief,
and D5 still reads `NO_AUTHORITATIVE_SOURCE_NEUTRAL_PLACEHOLDERS_ONLY`. The
engine also physically refuses these shades today: `PowderShade`
(`palette_powder_engine.py:364–370`) raises on any authority other than
`PROVISIONAL_VISUALIZATION_SHADE`. Closing D5 is therefore a code change with
tests, not an edit to a defect list.

`LAUNCHER_D5_SHADE_AUTHORITY.md` is the paste-ready instruction. **D5 closes
when that launcher reports green**, not now.

Everything below this line is the original framing of the step, kept because it
is why the step mattered.

---

`open_defect_inventory.md` D5 is the one that specifically gates M7's artwork,
and it is the one I did not mention when you asked. It records
`pan_shades: NO_AUTHORITATIVE_SOURCE_NEUTRAL_PLACEHOLDERS_ONLY`. Every shade
in the twelve-shade set is a `PROVISIONAL_VISUALIZATION_SHADE`. The Pantone
tokens 621 C and 627 C are held as symbolic named references with no value
fabricated — which is correct behaviour, and also means the system has no
colour to render.

Think about what that means for the deliverable. M7 produces artwork and an
editable `.ai`. An eyeshadow palette's artwork is substantially its shade
story. If the twelve shades are neutral placeholders, M7 can produce a
structurally perfect, technically valid file that no client would approve —
which is precisely the failure the project charter names as the thing to avoid.
A valid `.ai` containing poor design is a failed result.

**What you need to supply:** twelve shade names, and for each one a colour
specification with a stated authority. In descending order of strength:
a physical Pantone chip you have in hand; a Pantone number you are willing to
own as the specification; a measured Lab or sRGB value from a physical sample;
or an owner-chosen hex that is explicitly marked as a design choice rather than
a match to anything. Also state, per shade, its finish family — matte, satin,
shimmer, metallic, pressed, glitter — because M6 has spent this entire
milestone learning to discriminate those and it needs to know which one each
pan is.

Twelve rows. It is genuinely an afternoon's work and it is the difference
between M7 producing a deliverable and M7 producing a demonstration.

---

## STEP 4 — RESOLVE WHAT `MATERIALS_LIBRARY_ABSENT` ACTUALLY MEANS

The record says only `"native .ai sources not in this working copy."` I checked:
there *are* twenty-odd `.ai` files in the repo, all under `docs/visual_quality/`
and `docs/roadmap/acceptance/`, and all belonging to the bottle arc — `vq2_a1.ai`,
`bbrose_logo_approved.ai`, the Rose Damascena lettering pair, the VQ1 reset
iterations. Notably `bbrose_logo_approved.ai` exists, which is the brand asset
M7 will need.

So the blocker as written is vague, and vagueness in a blocker is its own
defect. Before you go hunting for files, get the record to say what is missing.
That is B4 in the `OWNER-BLOCKER-SUPPORT` launcher, delivered separately in
chat. This document is a self-brief for you; the launcher is the instruction
to Claude Code. Neither is contained in the other.

---

## ORDER, AND WHAT IT BUYS YOU

*Revised 2026-08-13. Step 1 closed. Step 3 fully decided. Step 2 bounded but
not measured. Step 4 untouched.*

Four documents now sit beside this one:

- `SHADE_AUTHORITY_PROPOSAL.md` — step 3, **all twelve decided**, including
  Midnight Bloom as POWDER_METALLIC.
- `LAUNCHER_D5_SHADE_AUTHORITY.md` — the instruction that turns those decisions
  into a repository record and closes D5. Not yet run.
- `ES3083_DIMENSION_FINDINGS.md` — step 2. What the `.ai` actually establishes,
  in four authority tiers, plus the absence claims with their search extents
  and the `CLASS_TYPICAL_NOT_PRODUCT_SPECIFIC` tier for web-sourced comparables.
- `ES3083_VENDOR_REQUEST.md` — demoted. Still valid, now a much shorter ask,
  and only worth sending if you know who catalogues ES3083.

**What happens next, in order of value.** Run the D5 launcher in Claude Code —
that is the only thing standing between the decided twelve and a closed
blocker. The one thing still only you can do is put calipers on a physical
ES3083 if you hold one: six numbers, fifteen minutes, and the geometry moves
from derived to measured. Step 4 is a definition task Claude Code can do
alongside either.

With steps 1, 2 and 3 done, M7 has: an owner-confirmed design reading, real
geometry, and real colour. That is the first point in this programme at which
a finish date means anything, because it is the first point at which the thing
being finished is a design a client could approve rather than a pipeline that
runs.

Until then, every closure node is real work on a system that cannot yet
produce the deliverable it exists to produce.
