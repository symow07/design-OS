# TWELVE-SHADE COLOUR AUTHORITY — SETTLED

Addresses blocker **D5 — colour authority absent**
(`docs/roadmap/palt_m6/open_defect_inventory.md`), currently recorded as
`pan_shades: NO_AUTHORITATIVE_SOURCE_NEUTRAL_PLACEHOLDERS_ONLY`.

Proposed 2026-08-13. Owner decisions returned the same day: **seven ACCEPT,
four RECOLOUR, one REPLACE.** The last open field — Midnight Bloom's finish —
was closed by the owner the same day: **POWDER_METALLIC.** All twelve rows are
settled.

This is **not yet a repository record.** It becomes one when the launcher in
`LAUNCHER_D5_SHADE_AUTHORITY.md` is run.

---

## YOUR CORRECTION, ACCEPTED

You wrote:

> I would not optimize this palette around exercising eight or nine engine
> finish families. That is useful for testing `palette_powder_protocol.py`, but
> it is the wrong authority for a real product. The hierarchy should be:
> commercial colour story → usability → visual harmony → finish distribution →
> engine coverage, not: engine finish coverage → product design.

You are right and this reverses a bias I built into the first draft. I had
"family coverage: eight of nine" sitting in the proposal as though it were a
score. It is not a score. It is a side effect.

The consequence, stated plainly rather than apologised for: **GLITTER and CREAM
are now both unused.** Under your ruling that is the correct outcome, not a
shortfall, and the record should not carry a note implying a gap. If the engine
needs those families exercised, that is a test fixture's job, not this
palette's.

---

## THE SETTLED TWELVE

Rows run light to deep, which is also how the pans are used.

| Pos | Shade name | Hex | Finish family | Role | Disposition |
|---|---|---|---|---|---|
| R1C1 | Petal Veil | `#F2E3D8` | POWDER_MATTE | brow-bone / all-over base | ACCEPT |
| R1C2 | First Light | `#E9CBAE` | POWDER_SATIN | inner corner, warm wash | ACCEPT |
| R1C3 | Dew | `#E4D8D4` | SHIMMER | warm pearl highlight | RECOLOUR |
| R1C4 | Damascena | `#D9A2A6` | POWDER_MATTE | soft rose transition | ACCEPT |
| R2C1 | Blush Hour | `#C57E82` | POWDER_SATIN | mid rose lid | ACCEPT |
| R2C2 | Attar | `#C9916B` | BAKED | antique rose-gold lid | RECOLOUR |
| R2C3 | Copper Leaf | `#A85B33` | POWDER_METALLIC | copper statement | ACCEPT |
| R2C4 | Sage Stem | `#7F846E` | POWDER_MATTE | olive-taupe, ties to the case | RECOLOUR |
| R3C1 | Old Rose | `#8D5459` | PRESSED_POWDER | crease depth | ACCEPT |
| R3C2 | Thorn | `#5D3A42` | POWDER_MATTE | outer-V plum brown | ACCEPT |
| R3C3 | Moss Garden | `#48583F` | MARBLED | deep olive hero pan | RECOLOUR |
| R3C4 | Midnight Bloom | `#4A2E3B` | POWDER_METALLIC | deep plum depth shade | REPLACE |

**The backbone, in your words:** Damascena → Blush Hour → Old Rose → Thorn.
Soft rose, mid rose, antique rose, deep plum. Every other pan in the palette
serves that run.

**Moss Garden carries a finish note, not just a family.** MARBLED here means
restrained antique-gold and olive marbling, not bright gold veining. That
distinction has to travel with the record or the renderer will produce the
thing you rejected.

**What each recolour fixed**, kept so the reasoning survives the decision:

- *Dew* `#DED7DB` → `#E4D8D4`. The original was too grey and too cool and would
  have gone icy-white on skin.
- *Attar* `#D79F5C` → `#C9916B`. The original read as conventional yellow-gold
  bronze. The replacement is antique rose-gold, which belongs to this palette.
- *Sage Stem* `#99A392` → `#7F846E`. Your clearest rejection — the original was
  a lifeless grey-green. Olive-taupe khaki instead.
- *Moss Garden* `#3C5A46` → `#48583F`. Warmer and more olive. You called this
  the potential hero pan of the palette.
- *Midnight Bloom* `#2A1B22` GLITTER → `#4A2E3B`. A near-black glitter topper
  spends a pan on a shade most customers rarely reach for. A deep plum earns
  its place.

---

## THE LAST FIELD, CLOSED

You marked Midnight Bloom **SHIMMER / POWDER_METALLIC** and then chose:
*"POWDER_METALLIC it is then."*

The reasoning kept, so the decision survives the decision: `#4A2E3B` is dark
enough that a soft pearl load disappears into its own base, which is the same
failure the near-black glitter topper was rejected for. A metallic load reads at
that depth. The honest cost, recorded rather than dropped: Midnight Bloom now
shares POWDER_METALLIC with Copper Leaf. They sit at opposite ends of the depth
run and would not be confused, but the duplication is real and the record should
carry it rather than pretend the choice was free.

**Finish distribution of the settled twelve:**

POWDER_MATTE 4 (Petal Veil, Damascena, Sage Stem, Thorn) · POWDER_SATIN 2
(First Light, Blush Hour) · POWDER_METALLIC 2 (Copper Leaf, Midnight Bloom) ·
SHIMMER 1 (Dew) · BAKED 1 (Attar) · PRESSED_POWDER 1 (Old Rose) · MARBLED 1
(Moss Garden).

GLITTER and CREAM are unused. Per your ruling that is a correct outcome, not a
gap, and no downstream record may annotate it as one.

---

## THE AUTHORITY QUESTION — UNCHANGED, AND IT STILL APPLIES

Every hex in the table is **chosen, not measured.** Nothing here matches a
physical chip, a Pantone number, or a spectrophotometer reading. Your four
recolours are owner corrections to my proposals, which makes them better design
decisions — it does not make them measurements.

In the programme's strength order this is the weakest tier:

1. a physical Pantone chip you hold — strongest
2. a Pantone number you are willing to own as the specification
3. a measured Lab or sRGB value from a physical sample
4. **an owner-chosen hex, explicitly marked a design choice rather than a match**
   ← what this is

These enter the record as `OWNER_CHOSEN_DESIGN_INTENT`. That is enough to
render, enough to make artwork, and enough for M7 to produce a deliverable a
client can respond to. It is **not** manufacturing colour authority and must
never be recorded as one.

Upgrading a shade later is cheap: replace the hex with a Pantone number or a
measured value and raise that shade's authority field. Names, positions and
finish families do not have to change when the colour does.

---

## WHAT DOES NOT COME FROM THIS DOCUMENT

- **PANTONE 621 C and 627 C are the case colours, not shade colours.**
  `palette_es3083_intent.py:95`, HARD, OWNER_STATED. Both are greens. The
  ES3083 `.ai` now also gives their Lab transforms — 621 C at Lab 87.8431,
  −7.0, 2.0 and 627 C at Lab 18.0392, −14.0, 0.0. No downstream record may
  treat either as a pan shade.
- **The reference sheet's shade-name grid is blank.** Twenty-four blank
  77.00 × 16.00 mm labels, measured off the `.ai`. There were never any
  existing shade names to recover; they had to be authored, and now they are.
- **Typography is already fixed:** EYE SHADOW (primary), OUTER GLOW
  (secondary), BBROSE (endorsing), SOMBRA DE OJOS.
- **Twelve pans, four columns by three rows, RECTANGULAR** —
  `palette_es3083_intent.py:44–58`, reclassified to HARD by you during the
  M4C-4 confirmation. Note that the palette illustration on the reference sheet
  draws each cavity with one strongly curved edge rather than as a plain
  rectangle. That drawing is a stylised perspective render and is not evidence,
  but it is worth a look before RECTANGULAR is treated as final.

---

## ON LANDING

All twelve are decided. What remains is mechanical, and it is a Claude Code job,
not a decision:

1. Write the twelve into the repository as a shade authority record, with
   `OWNER_CHOSEN_DESIGN_INTENT` stamped **per shade** — not once at the top of
   the file, because per-shade stamping is what lets a single shade be upgraded
   to a Pantone or a measured Lab value later without touching the other eleven.
2. Attach Moss Garden's marbling note to the shade, not to a comment. A renderer
   that reads MARBLED without the note will produce bright gold veining — the
   thing that was rejected.
3. Attach the POWDER_METALLIC duplication note to Midnight Bloom.
4. Flip `pan_shades` in `docs/roadmap/palt_m6/open_defect_inventory.md` from
   `NO_AUTHORITATIVE_SOURCE_NEUTRAL_PLACEHOLDERS_ONLY` to the new record, citing
   it by path and digest.

The paste-ready instruction for all four is `LAUNCHER_D5_SHADE_AUTHORITY.md`.
D5 closes when that launcher reports green — not when this document was
approved. This document is the decision; the record is the evidence.
