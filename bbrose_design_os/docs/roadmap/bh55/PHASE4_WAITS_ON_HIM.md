# §BH55 PHASE 4 — WHAT IS MEASURED AND WAITS ON HIS LINE

> "PHASE 4 — THE QUEUE, EMPTIED. Every open item in the reports and the brain's queue: the untracked tier record,
> dip0b ungated, the wall-clock fixtures, the media stubs, the dead colour dict, the exempt surfaces, the Kufi and
> Sahel hunt, the dark-accent and ink roles, CMYK print intent, the stale July audit, the vault-note skip, the
> reference captions, and the ACCEPTANCE-TIME list. Nothing carried forward."
> — OWNER STANDING ORDER §BH55 (1dabb79), transcribed at `OWNER_BLOCKER_CLEARANCE.md:21995-22001`

**Why this file exists.** Phase 4 says nothing is carried forward. For an item that is a MEASUREMENT, emptying it
means taking it, and each of those is a commit of this phase. For an item his own words reserve to him, emptying it
means measuring it exactly and putting the decision in ONE place he can read — not leaving it in a report he has
already read, in a commit message, or in an executor's head. That is what this file is. Nothing here is acted on
from here.

**And his own sentence already parked most of it.** Closing §BH43 he wrote:

> "This closes §BH34's four fronts. The long tail — the exempt surfaces, the Kufi and Sahel hunt, my purchase
> sitting, the dark accent and ink roles, CMYK print intent, and a fresh audit to replace the stale July one —
> waits for me to open it." — `OWNER_BLOCKER_CLEARANCE.md:20382-20385`

§BH55 Phase 4 names five of those six and is him opening them. **This is recorded as a reading, not taken as a
clause-4 stop**: the two sentences are not in direct collision — §BH55 is later, names the same items, and calls the
phase "THE QUEUE, EMPTIED". What it changes is only what emptying MEANS for each: measure it, and where the decision
is his, put it here. The seventh item in his line, "my purchase sitting", is in §BH43's list and NOT in §BH55's, so
it is not this phase's and is not measured here.

---

## 1. The seven exempt surfaces — one ruling each

**His words.** `apps/ire/font_roles.py:97`, the list's own header: the exemption list is "path-literal, one surface
per line, in the layer's own config, **reversible only by ruling**". And the queue line
(`docs/design_intelligence/sittings/bh33/bh33_goal_report.md:77`): "Queued from §BH32, still queued: **each exempt
surface's adoption of the theme (one ruling each)**".

**Measured 2026-09-20, read-only.** Seven entries remain — §BH48(a) lifted the three container composers by his word
on 2026-09-12, and the note there says the rest "are not product composers and stay exempt". **Every one of the
seven entry points still exists**, checked by `def <name>` in the file the entry names, so no exemption is protecting
a dead emitter:

| # | surface | what it is, in the list's own words |
|---|---------|--------------------------------------|
| 1 | `apps/ire/compose_vector_art.py::compose_vector_art_graph` | the Phase 2A-7 confirmed-concept golden path — concept-only |
| 2 | `apps/dielines/exporters/production_pdf.py::_resolve_fonts` | the regulatory sticker / production PDF — the Noto trio |
| 3 | `apps/dielines/exporters/production_pdf.py::_resolve_arabic_font` | the same, Arabic |
| 4 | `apps/dielines/exporters/info_panel.py::draw_info_panel` | the sticker |
| 5 | `apps/dielines/exporters/info_panel.py::svg_info_panel` | the sticker's SVG twin |
| 6 | `apps/dielines/exporters/design_preview.py::export_design_preview_ai` | dieline previews — the sticker family |
| 7 | `apps/ire/handoff/graph_schema.py::serialize_handoff_graph` | the 2A handoff — the concept face's name |

**What one sentence from him would change:** a named surface leaves the list and resolves through the theme, faces
and colours, with its typography pins re-measured and re-pinned in that commit — the shape §BH48(a) already used for
the three it lifted, where "the owner may veto any single re-pin by one line".

**And the sticker carries a measured consequence, which is why it is not a formality.** §BH32(h)(4), still queued
(`bh32_goal_report.md:89`): "under Poppins metrics the regulatory sticker's auto-fit **drops the Spanish 'external
use only' line** at the test panel size; the sticker stays on the Noto trio by (h)(1)." Surfaces 2–6 are that
sticker family. A ruling that lifts them without an answer to the auto-fit drops a regulatory line from a printed
sticker.

## 2. The EAN-13 widget's Helvetica — §BH32(h)(5)

In the same queue line and **not named in §BH55's Phase 4 list**, so it is recorded here rather than assumed closed.
`bh32_goal_report.md:87`: "the EAN-13 widget draws its digits in built-in Helvetica **outside the layer**; the usage
record counts it and names it under `outside_layer`". The open question is his: whether the widget adopts a theme
face. It is honest today — counted and named, not hidden.

## 3. The Kufi and Sahel hunt — §BH32(g), "own front"

**His words**, `OWNER_BLOCKER_CLEARANCE.md:18715`: "(g) QUEUED, not built: the Noto Kufi Arabic + Sahel evidence
hunt (own front); Manal and Hacen Liner XL stay deferred."

**Measured 2026-09-20.** The query, stated as CLAUDE.md requires before claiming an asset absent: a family-substring
match over every `faces[].family` in all 4,084 rows of the fonts census
(`docs/design_intelligence/sittings/bh27/census_rows.json`, the record `tools/brain/sources.FONTS_CENSUS` names).
**ZERO rows match "Noto Kufi" and ZERO match "Sahel".** So the hunt is not a census read: both are candidate faces
named in §BH32's Arabic-role table (`OWNER_BLOCKER_CLEARANCE.md:18758`) — referenced by the house's own design files,
absent from this machine. Evidence for them means §BH29's method: the upstream repository, its licence file, and a
hash match, against a GitHub API that allows 60 requests an hour. That is a front, as his sentence says, not a step.

## 4. A pirated face is sitting in the governed corpus — FOUND 2026-09-20, not previously recorded anywhere

Found while reading the census for item 3, and recorded here because it belongs to no front that exists.
`census_rows.json` holds two faces, **"Pen Kufi"** and **"Pen Kufi Shadow"**, whose embedded copyright string reads:

> `Cracked by Al-Amri` / `Email: khamri97@hotmail.com`

Their `postscript_name` is a row of bullet characters, which is what a tampered name table looks like. This is a
rights question about the corpus, and the corpus is read-only, so nothing is done to the files. **It is his**: the
tier record governs what may be placed, and these are faces, not placeable assets — no row governs them. What a
sentence from him would decide: whether a face whose own bytes say they were cracked may remain in the corpus the
system reads, and whether the fonts census should carry a rights state per face at all.

## 5. The dark-accent and ink roles — a data ruling

`docs/design_intelligence/sittings/bh39/report_goal_and_rest.md`, item 1: "The two roles with no brand colour today
are `accent_dark` (`#231916`) and `ink`; the layer records them as the surface's literal **until a PRODUCTION
candidate or a naming arrives**." Nothing is missing from the build: the layer behaves correctly and records the
literal honestly with `SOURCE_SURFACE_FALLBACK`. What is missing is data — a brand colour for those two roles, or a
name. His.

## 6. CMYK print intent — a data ruling

Same report, item 7: "**brand_gov swatches carry no CMYK.** The layer emits a brand role as an RGB fill (the hex)
unless a CMYK is ruled; the design language's swatches carry their own CMYK and are exempt-surface literals. **A
print-intent CMYK per brand swatch is a data ruling, not built.**" His, per swatch.


## 7. The REFERENCE captions — §BH43(b), ruled and budgeted, and the account cannot buy them

This one is not a ruling of his that is missing. It is work he already authorised, measured to the dollar here, that
**one thing** blocks: money in the API account.

**His words**, `OWNER_BLOCKER_CLEARANCE.md:20334-20343`, measured LIVE by `brain.ruling`: "(b) THE REFERENCE LIBRARY
IS CAPTIONED — budgeted batch, own commit(s). Scope: every REFERENCE-tier asset in the governed corpus whose bytes
can be rendered. Sample first as §BH42(c) ruled, project the total, and STOP for my word if the projection exceeds
$15 (this batch's cap, inside the §AE $50). Uncaptionable formats are named with their reason, never skipped in
silence. Byte-identical duplicates captioned once, every path recorded."

**Measured 2026-09-20, by running it.** The probe — the half that costs nothing and is the ruling's own first step,
because whether a file renders "is a question for the render probe, never for its extension":

* **4,830** contents in scope with the REFERENCE arm switched on, over **5,086** paths (256 share bytes);
* **4,431 render** and **399 do not**, each named with its reason (`.ttf` 203, `.otf` 86, `.txt` 46, `.zip` 18,
  `.rar` 17, and a tail of `.js`, `.css`, `.html`, one `.mov`, one `.mp4`, one `.psb` with a bad PSD version);
* **4,035 renderable contents are not yet captioned**, and at the record's own measured rate of **$0.00255** a
  content that is **$10.29 — inside his $15 cap**, so no stop of his is reached.

**AND GHOSTSCRIPT ARRIVED SINCE §BH43(a) WAS WRITTEN.** `gs 10.08.0` is on this machine at `/opt/homebrew/bin/gs`;
it was not when the record was built. The committed record still names **1,718** files as uncaptionable, of which
**648 `.eps`** carry the reason `POSTSCRIPT_NEEDS_GHOSTSCRIPT` and **671 are `.ai`**. All **1,319** of those render
today. The true census is 399, not 1,718, and the scope is wider than the extension-based guess the §BH43
transcription made ($8.56 for 3,345 contents; measured, it is $10.29 for 4,035).

**THE BATCH CANNOT BEGIN.** `ANTHROPIC_API_KEY` is set, but a key is not a balance. The first call of the run
returned, verbatim:

> `anthropic.BadRequestError: Error code: 400 — invalid_request_error: Your credit balance is too low to access the
> Anthropic API.`

Nothing was spent, nothing was written, the tree was left clean. Topping up an account is a purchase and is outside
this repository; it is his, and it is the only thing between the measurement above and the captions.

**AND THE MEASUREMENT HAS A CONSEQUENCE HE SHOULD SEE.** Ghostscript widens the RULED scope too, not only the
REFERENCE arm. Four `.eps` files inside the already-ruled scope — `116297-OPHTK5-790.eps`, `18207.eps`,
`16260.eps`, `7077.eps` — were NAMED as uncaptionable for want of Ghostscript and now render, so they are in scope
and uncaptioned, and the coverage gate correctly reports `UNCAPTIONED` instead of `COMPLETE`. **That is why the
probe's corrected census is not committed**: landing the true 399-row census refuses the suite gate, and the four
captions that would clear it cost about one cent the account cannot pay. The committed record therefore still says
1,718, knowingly, and this paragraph is the reason. One top-up closes the census, the four, and the batch together.

**What running it uncovered, and is already fixed:** the probe destroyed the tracked caption record — 396 captions,
$1.01 already paid — while printing "Nothing was spent". Repaired in its own commit (`67d70b3`): the record is read
by default rather than under `--resume`, and the writer refuses to shrink.

---

## What is NOT here

The instrument questions — bands, thresholds, margins, ceilings, units, axes, rules — are on
`ACCEPTANCE_TIME_LIST.md` by §BH55 clause 3, which is a different list with a different rule for leaving it. The
twelve entries there are not repeated here. Everything in Phase 4 that was a measurement was taken; each of those is
a commit, and the phase report lists them in order.
