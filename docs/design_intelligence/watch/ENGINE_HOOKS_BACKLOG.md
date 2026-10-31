# ENGINE HOOKS BACKLOG — the WATCH corpus, reduced to actionable engine work

**This is a BACKLOG. It is not authority.** Nothing here is a decision, a bar, a
spec, or an acceptance. Every entry is a *candidate* piece of engine work
distilled from a watched source. An entry existing here grants no permission to
implement it, and certainly none to move anything the owner has ruled on.

Generated from all **60 notes across 21 domains** in `docs/design_intelligence/watch/`,
landed by commits `dd5f6ff..889c701`. Written 2026-08-24 against HEAD `ac3bd18`.

---

## THE ONE THING TO READ BEFORE USING THIS FILE

`NOT_WIRED` here means **"no line of code in this repository traces to this
note."** That is true of all 118 entries below, uniformly, and it is not
surprising: all eight corpus commits (`dd5f6ff`, `0ec5b74`, `70c1dc4`, `a8911b9`,
`c2fe871`, `738e874`, `5288c37`, `889c701`) are dated **2026-08-24** — the corpus
landed hours before this file was written, and nothing has had the chance to cite it.

It does **not** mean the engine fails to do the thing. Those are different
questions, and conflating them would have made this document false at its most
prominent entry. The corpus's single most convergent rule — *"enumerate spot
swatches, assert every one maps to a declared ink"*, arrived at independently by
**six** sources (H019) — turns out to be **already implemented**, in
`apps/ire/handoff/container_adapter.py:404`:

```python
orphans = spot_set - used
if orphans:
    codes.append("HANDOFF_ORPHAN_SPOT_SWATCH: " + ",".join(sorted(orphans)))
```

Nobody wired that from the corpus. The engine arrived there on its own. Had this
file said `NOT_WIRED` and stopped, it would have proposed re-building a check
that already ships.

So every entry carries **two** fields:

| field | question it answers |
|---|---|
| `NOT_WIRED` / `WIRED` | Did anything get built *because of this note*? |
| `engine:` | Does the engine do this *anyway*, for its own reasons? |

This row used to read "`NOT_WIRED` … (always: no)", which was true when the file
was written and is now false: **1 of 118** entries is `WIRED` (H020, commit
below). The parenthetical is removed rather than left to rot — a legend that
asserts a constant which its own entries have since falsified is the same defect
this file exists to catch.

`engine:` is one of **NOT_PRESENT** / **PARTIAL** / **PRESENT** — and where it is
not `NOT_PRESENT`, the entry names the file and says what the existing code
actually covers. Unmeasured entries say `engine: UNMEASURED` rather than guess.

---

## MARKERS

**`OWNER-GATED`** — the hook touches a bar the owner has ruled. Three bars are
live, and no entry below may be implemented in a way that moves any of them:

- the **1.0× cap-height clear space**
- the **12.0 mm size floor** (§C2)
- **`BACKGROUNDS_PERMITTED = ("brand_light_ground", "pure_white")`**
  — `bbrose_design_os/apps/ire/container_brand_usage.py:59`

An `OWNER-GATED` entry may be *specified* and *measured*. It may not be *ruled*.

**`CEILING-A5`** — the hook's own text names supplier contact as its delivery
route. **§C2 withdrew supplier outreach permanently**; per `OWNER_INPUT_MANIFEST.md`
A5, *"No work item, no autonomous run, and no agent may contact a supplier to
obtain this. It arrives from the owner or it does not arrive."*

This is not a small footnote. **13 of the 60 notes** (22%) name a supplier-contact
route in their hooks. The corpus was distilled without reference to §C2, so its
hook language routinely proposes forbidden work. A backlog that copied that
language forward would be a work plan for something no one is allowed to do.
The correct reading of every `CEILING-A5` entry is: *the spec field is real and
should exist; it stays **UNRESOLVED** until the owner supplies the value.*

The 13 notes: `bottle_decoration/roetell_glass_decoration_techniques.md`,
`bottle_decoration/silkscreen_printing_beauty_packaging_9step.md`,
`glass_manufacturing/how_glass_is_made_composition.md`,
`glass_manufacturing/roetell_glass_bottle_process.md`,
`jars_closures/airless_pump_mechanism.md`,
`jars_closures/us_bottle_jar_suppliers_skincare.md`,
`label_substrates/pressure_sensitive_label_materials_overview.md`,
`luxury_teardowns/iphone_box_cost_breakdown.md`,
`print_finishing/emboss_blocks_flexo_label_printing.md`,
`print_finishing/hot_foil_guru_explanation_of_foils.md`,
`print_finishing/hot_foil_stamping_animation_technoshell.md`,
`printing_processes/domino_flexo_digital_hybrid.md`,
`printing_processes/labeltech_flexo_basics.md`.

---

## EVIDENCE DISCIPLINE

A hook must trace to a claim carrying a timestamp. Measured across the corpus:

```
notes with a TIME/FRAME anchor in Claims : 59 / 60
notes without                            :  1 / 60
   print_finishing/hot_foil_stamping_animation_technoshell.md
```

The corpus uses **three** timestamp conventions — `` `t=0:15` ``, `[t=0:37]`, and
`[frame 02, ≈0:12]`. A single-convention regex reports 25/60 and is wrong; the
59/60 figure comes from matching all three. Where a hook's only support is a
claim with no time anchor, the entry says so:

- **`⚠ NO-TIME-ANCHOR`** — derived from the one note with no timestamps. Three
  entries carry this (H079, H094, H100).
- **`⚠ CONVENTION-NOT-SOURCED`** — the number is industry convention, explicitly
  *not* evidenced by the video the note came from. The note flags this itself.
- **`⚠ LOW-CONFIDENCE`** — the source note itself marks the figure low-confidence.
- **`⚠ UNSOURCED-GAP`** — the corpus names a parameter it has **not** evidenced.
  These are *refusal* hooks: the engine must not emit a value.

**Convergence** is counted as *distinct notes independently supporting the same
rule*. "6-source" means six notes, not six mentions. Convergence is recorded
because it is the corpus's main signal: three independent trade sources
converging on a rule is a far stronger basis for engine work than one video.

---

## SURFACE INDEX

| § | surface | entries |
|---|---|---|
| 1 | Color spec & QC | H001–H018 |
| 2 | Preflight & prepress | H019–H034 |
| 3 | Dieline & structure params | H035–H062 |
| 4 | Proof & supplier emitters | H063–H078 |
| 5 | Mockup-render routes | H079–H090 |
| 6 | Materials & sustainability | H091–H100 |
| 7 | Shelf & brand psychology | H101–H118 |

---

## §1 — COLOR SPEC & QC

**H001 — Carry a `delta_e_tolerance` on the colour spec, against a declared PMS standard.**
Replace percentage talk ("97% match") with a numeric tolerance bound to a standard.
`color_management/eguru_delta_e.md` · 1-source · **NOT_WIRED** · engine: **PARTIAL** — CIE76 ΔE math already exists at `bbrose_design_os/apps/pipeline/services/image_checks.py:90`, but it measures *a generated image against brand hexes*, not *print output against a PMS standard*. No tolerance lives on a colour spec.

**H002 — Do not reuse `PALETTE_TOLERANCE_DE` for a print tolerance.**
The existing constant is `25.0` (`image_checks.py:45`), correct for "is this image roughly on-brand" and roughly an order of magnitude looser than any brand-critical print tolerance. Wiring a print spec to it yields a check that cannot fail.
derived from `color_management/eguru_delta_e.md` + measurement · **NOT_WIRED** · engine: **PRESENT** (the constant) — *refusal hook*

**H003 — Store brand colours as Lab (or PMS→Lab), with CMYK/RGB as derived outputs.**
ΔE only exists in Lab; prepress works in Lab for this reason.
`color_management/eguru_delta_e.md` (c3) · 1-source · **NOT_WIRED** · engine: **PARTIAL** — `_rgb_to_lab` exists but converts hex on the fly; storage is sRGB hex.

**H004 — Cite ΔE ≤ 2 as convention, never as sourced measurement.** ⚠ CONVENTION-NOT-SOURCED
The note evidences only the ΔE 0.3 imperceptibility claim; the ≤ 2 brand-critical band is industry convention the video does not establish.
`color_management/eguru_delta_e.md` · **NOT_WIRED** · engine: NOT_PRESENT

**H005 — Never cite printer accuracy percentages as measurements.**
Two printers use them loosely and in **opposite directions** — INNORHINO scores Pantone-vs-screen, Lil Packaging scores CMYK-vs-Pantone. Record as sales heuristics.
`ink_color_systems/innorhino_pantone_vs_cmyk.md` (c4), `ink_color_systems/lilpackaging_cmyk_vs_pms.md` (c3) · 2-source · **NOT_WIRED** · engine: NOT_PRESENT · *refusal hook*

**H006 — Reject or query a declared PMS with no C/U suffix as an incomplete spec.**
Coated/uncoated absorption is the mechanism behind Pantone shipping C/U pairs.
`color_management/oppaca_screen_vs_print.md` (c3) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H007 — Require substrate context on every colour spec line.**
A PMS number does not pin appearance; substrate moves it.
`ink_color_systems/lilpackaging_cmyk_vs_pms.md` (c5), `color_management/oppaca_screen_vs_print.md` (c3), `ink_color_systems/ryonet_pantone_ink_mixing.md` (c6), `glass_manufacturing/how_glass_is_made_composition.md` (c4) · **4-source** · **NOT_WIRED** · engine: UNMEASURED

**H008 — Flag specific out-of-gamut hues rather than warning generically.**
Magenta/fuchsia, neon green and pure blue are the named screen colours that collapse in CMYK; palette entries near those hues get "will shift in CMYK; spot or reformulate".
`color_management/proprinters_cmyk_vs_rgb.md` (c2) · 1-source · **NOT_WIRED** · engine: **NOT_PRESENT** — `gamut` appears in 0 `.py` files under `apps/`.

**H009 — Record that colour QC has two instruments, and that uncalibrated on-screen approval is invalid.**
Spectrophotometer for output ΔE; colorimeter for the display.
`color_management/oppaca_screen_vs_print.md` (c2) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H010 — Encode the accuracy hierarchy: software colour management < printer craft < physical test print.**
`color_management/oppaca_screen_vs_print.md` (c5,c6), `ink_color_systems/ryonet_pantone_ink_mixing.md`, `artwork_prepress/lumi_dielines_proofs_prepress101.md` · **3-source** · **NOT_WIRED** · engine: UNMEASURED

**H011 — Treat a spot colour over a non-white substrate as carrying an implicit white underbase — an extra pass and an extra plate.** `OWNER-GATED`
Touches `BACKGROUNDS_PERMITTED`: the hook only bites where the mark sits on a ground the permitted set does not contain. Specify the cost consequence; do not widen the permitted set.
`ink_color_systems/ryonet_pantone_ink_mixing.md` (c6), `bottle_decoration/silkscreen_printing_beauty_packaging_9step.md` · 2-source · **NOT_WIRED** · engine: NOT_PRESENT

**H012 — Flag pastel brand colours as higher-risk spots.**
A PMS recipe is dominated by white (~94.6%); tiny tint components carry the identity, so pastels are mix-sensitive.
`ink_color_systems/ryonet_pantone_ink_mixing.md` (c2,c5) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H013 — Emit a PMS reference for the brand colour even on CMYK-only jobs.**
It is the communication anchor when something prints wrong.
`ink_color_systems/innorhino_pantone_vs_cmyk.md` (c1), `ink_color_systems/lilpackaging_cmyk_vs_pms.md` (c4) · 2-source · **NOT_WIRED** · engine: UNMEASURED

**H014 — Derive the ink recommendation from (brand-colour criticality, run size), not from quality alone.**
`ink_color_systems/innorhino_pantone_vs_cmyk.md` (c5) · 1-source · **NOT_WIRED** · engine: **NOT_PRESENT** — `run_quantity` appears in 0 `.py` files under `apps/`.

**H015 — On a digital route, mark PMS colours "gamut-simulated, request drawdown" instead of costing them as plates.**
No plates exist on a digital press; expanded gamut (CMYK+OV+white) simulates spots. The plate-cost rule genuinely does not apply.
`printing_processes/domino_flexo_digital_hybrid.md` (c5,c11) · 1-source · **NOT_WIRED** · engine: **NOT_PRESENT** — `drawdown` appears in 0 `.py` files under `apps/`.

**H016 — Emit a one-slide screen-vs-print comparison per palette (sRGB swatch vs CMYK-converted swatch).**
An owner-review artifact, not a gate.
`color_management/proprinters_cmyk_vs_rgb.md` · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H017 — Distinguish in-melt glass colour from applied glass colour as different spec classes.**
In-melt is permanent, whole-batch, volume-gated; spray/frost is per-order. Small-batch work lands on applied colour.
`glass_manufacturing/how_glass_is_made_composition.md` (c4), `bottle_decoration/roetell_glass_decoration_techniques.md` · 2-source · **NOT_WIRED** · engine: NOT_PRESENT

**H018 — Treat value-matched chroma contrast and a single accent hue as palette dials.**
`cosmetics_packaging/zested_skincare_full_process.md` (c2,c10) · 1-source · **NOT_WIRED** · engine: UNMEASURED

---

## §2 — PREFLIGHT & PREPRESS

**H019 — Enumerate every spot swatch and assert each maps to a declared ink.**
The canonical prepress error: a stray named spot swatch is a plate the owner pays for.
`artwork_prepress/papp_prepress_stages_plates.md` (c8), `artwork_prepress/indesignology_prepress_pdfx1a.md` (c4), `printing_processes/labeltech_flexo_basics.md` (c3), `printing_processes/expresscards_offset_printing.md` (c3), `ink_color_systems/lilpackaging_cmyk_vs_pms.md` (c4,c6), `ink_color_systems/innorhino_pantone_vs_cmyk.md` (c1) · **6-source — the corpus's strongest convergence** · **NOT_WIRED** · engine: **PRESENT** on the container path — `apps/ire/handoff/container_adapter.py:404` computes `orphans = spot_set - used` → `HANDOFF_ORPHAN_SPOT_SWATCH`.

**H020 — Extend the orphan-swatch check to the second handoff path.**
The two handoff paths run **opposite directions**. `container_adapter.py` checks both *missing* and *orphan*. `apps/ire/handoff/package.py` `validate_handoff()` computed only `required_spots - have_spots` — the **missing** direction. A stray spot swatch passed `package.py` silently. *(Symbol, not line number: this entry originally cited `package.py:135-139`, and the commit that wired it moved that code to 165+. A citation that its own fix invalidates is the rot this file warns about two sections down.)*
derived from H019 + measurement · **WIRED** — the first entry in this file wired *because of* it · engine: **PRESENT** — as of this commit, `apps/ire/handoff/package.py` `_painted_swatch_names()` → `HANDOFF_ORPHAN_SPOT_SWATCH`.

> **This entry's own prescription was wrong, and the measurement corrected it.**
> It used to end: *"The set is already in hand at line 137; the gap is one
> set-difference."* That is false. Copying `container_adapter.py:404`'s
> `spot_set - used` here would have produced a check that **can never fire**:
> on the container path both sides come from persisted records and vary with
> the data, but on this path `required_spots` (a set literal local to
> `validate_handoff`) and `graph_schema.SPOT_SWATCHES` (a module constant) hold
> **the same six names** — measured identical — and `have_spots` is rebuilt
> verbatim from `SPOT_SWATCHES` every time the graph is serialized. So the
> name-level difference is identically empty for every document, forever. It
> would have been an AD0(b) instrument: recognising its subject by an
> incidental feature.
>
> *(An audit corrected this paragraph too: it first called both sides "module
> constants". Only `SPOT_SWATCHES` is one. The conclusion is unchanged — a
> function-local literal is just as fixed at every call — but "measured
> identical" has to survive being checked, and half of it was not.)*
>
> The direction that *can* vary is **usage**: the emitter creates every entry in
> `spot_swatches` (`jsx_emitter.py:100`), so a swatch no printable object paints
> with ships as an **empty separation plate**. That is what was built.
>
> **It fired on the first document it was pointed at.** The pinned task-50
> golden package defines `DEBOSS` and paints nothing with it —
> `HANDOFF_ORPHAN_SPOT_SWATCH: DEBOSS`, asserted in
> `apps/ire/tests/test_handoff.py::OrphanSpotSwatchTests`. The finding is
> recorded in the tests rather than silenced; the artwork fix (drop the plate or
> use it) is upstream and is **not** taken here, because task-50 is a pinned
> regression artefact and moving it to flatter a new instrument is backwards.
>
> **And the first version of the check was wrong in the dangerous direction.**
> An audit found it read only `stroke`, `fill` and `finish`. Live text is the
> one object type whose colour the serializer writes as a **flat** `swatch` on
> the record, so a spot ink used only for typography read as unused — a FALSE
> orphan, reporting a plate that prints. A test had already pinned the miss as
> intended behaviour. Both were fixed before commit. A checker that cries wolf
> is worse than the silence it replaced, because it trains the reader to skip
> the code.
>
> **Known, not fixed:** `HANDOFF_ORPHAN_SPOT_SWATCH` now carries two meanings —
> *registered but no separation* on the container path, *defined but unpainted*
> here — and both reach the dashboard as the same string. Splitting the code
> would edit the container path, which this tranche has no business touching.
> Recorded so the next reader is not misled by a shared name.

**H021 — Treat "every declared ink is a press station" as process-independent.**
True for offset (plate + blanket per station) and flexo (anilox → plate, no blanket) alike, so the rule can be stated unconditionally.
`printing_processes/labeltech_flexo_basics.md` (c3,c4), `printing_processes/expresscards_offset_printing.md` (c3) · 2-source · **NOT_WIRED** · engine: UNMEASURED

**H022 — Make bleed a per-printer parameter with a confirmed value, never a constant.**
The corpus **disagrees with itself** — 0.125 in here, 0.25 in Munes, 3 mm European convention. The disagreement is the evidence: no constant is defensible.
`dielines_structure/illustrator_dielines_bleed_cutlines.md` (c6), `dielines_structure/munes_studio_dieline_step_by_step.md` (c8), `artwork_prepress/indesignology_prepress_pdfx1a.md` (c3), `dielines_structure/packmojo_folding_carton_dieline_101.md` (c2) · **4-source** · **NOT_WIRED** · engine: **PARTIAL** — `bleed` appears in 102 `.py` files under `apps/`; whether any treats it as a per-printer parameter is UNMEASURED.

**H023 — Enforce trim / bleed / safe as three distinct zones; a safe-zone violation is a preflight FAIL.**
`cosmetics_packaging/product_packaging_full_process_3d_mockups.md` (c4), `dielines_structure/packmojo_folding_carton_dieline_101.md` (c2) · 2-source · **NOT_WIRED** · engine: UNMEASURED

**H024 — Machine-check outlined type, image effective-dpi and embedded images before export.**
`artwork_prepress/indesignology_prepress_pdfx1a.md` (c5,c6), `cosmetics_packaging/product_packaging_full_process_3d_mockups.md` (c10) · 2-source · **NOT_WIRED** · engine: **PARTIAL** — `HANDOFF_TEXT_OUTLINED` exists at `apps/ire/handoff/package.py:141`; dpi and embedded-image checks UNMEASURED.

**H025 — Default the export ask to PDF/X-1a:2001 + marks + bleed, but let the printer's own preset win when one exists.**
Two sources, one overriding the other — the override is the rule, not a conflict.
`artwork_prepress/indesignology_prepress_pdfx1a.md` (c7), `artwork_prepress/papp_prepress_stages_plates.md` (c4) · 2-source · **NOT_WIRED** · engine: UNMEASURED (`apps/dielines/exporters/output_intent.py` is the surface)

**H026 — Never butt two flat colours at a knockout edge without recording trap responsibility.**
Usually the printer's job, but the file must not prevent it.
`artwork_prepress/papp_prepress_stages_plates.md` (c5,c6) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H027 — Order the emission QA chain: preflight before proof, proof before anything is called done.**
`artwork_prepress/papp_prepress_stages_plates.md` (c1,c2), `artwork_prepress/lumi_dielines_proofs_prepress101.md` (c7) · 2-source · **NOT_WIRED** · engine: UNMEASURED

**H028 — Reserve mandatory-furniture zones, and switch the element set by target market.**
Identity, net quantity, ingredients, responsible party (US); batch/expiry/notification seen on real cosmetics cartons; transit packaging has its own set.
`label_substrates/fda_cosmetic_labeling_rules.md` (c2,c6), `cosmetics_packaging/paola_skincare_brand_ep2_packaging.md` (c3), `mockup_render/blender_mockup_from_dieline_fold.md` (c3), `dielines_structure/shipping_carton_dieline_kraft_design.md` (c4-c6), `jars_closures/neck_finish_construction_illing.md` (c7) · **5-source** · **NOT_WIRED** · engine: **PARTIAL** — `apps/ire/back_panel.py` / `back_panel_packer.py` / `apps/dielines/exporters/info_panel.py` exist; market-switching UNMEASURED.

**H029 — Lint generated copy for banned claims.**
Regulatory: treat/cure/heal and structure-function verbs. Commercial: sustainability claims may only assert what the spec sheet supports (PCR %, cullet fraction). Cheap check, high consequence.
`label_substrates/fda_cosmetic_labeling_rules.md` (c5), `sustainable_materials/nosco_pcr_flexible_film.md` (c1,c3), `sustainable_materials/pcr_bottle_intro.md` (c2), `shelf_retail/brand_persuasion_packaging_psychology.md` (c3,c7), `glass_manufacturing/how_glass_is_made_composition.md` (c7) · **5-source** · **NOT_WIRED** · engine: NOT_PRESENT

**H030 — Put net-quantity zone position in the template, not in layout taste.**
Placement is regulated.
`label_substrates/fda_cosmetic_labeling_rules.md` (c4) · 1-source · **NOT_WIRED** · engine: UNMEASURED

**H031 — Give pouch formats an `artwork_side: surface|reverse` parameter; never assume surface print for laminated film.**
Reverse-printed lamination is why pouch production files are often mirrored.
`printing_processes/labeltech_flexo_basics.md` (c7) · 1-source · `CEILING-A5` (source hook defers image capability to the converter) · **NOT_WIRED** · engine: **NOT_PRESENT** — `artwork_side` appears in 0 `.py` files under `apps/`.

**H032 — Encode the inline decoration order: cold foil and white underbase before the digital print unit; die-cut and matrix stripping after.**
`printing_processes/domino_flexo_digital_hybrid.md` (c11) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H033 — Export CMYK mode with recorded Pantone C equivalents at handoff.**
`dielines_structure/packmojo_folding_carton_dieline_101.md` (c8) · 1-source · **NOT_WIRED** · engine: UNMEASURED

**H034 — Mirror male emboss die artwork, and preflight the mirroring.**
Same orientation-transform family as the fold rotations (H040).
`print_finishing/emboss_blocks_flexo_label_printing.md` (c8) · 1-source · `CEILING-A5` · **NOT_WIRED** · engine: **PARTIAL** — `apps/ire/corr_mirror.py` exists; scope UNMEASURED.

---

## §3 — DIELINE & STRUCTURE PARAMS

**H035 — Generate the tuck-end carton as a deterministic function of (W, D, H) plus small constants.**
Tuck 1.5 cm, glue 1.5 cm, dust ≈ tuck/2, chamfer nudges; lid depth = side depth.
`dielines_structure/munes_studio_dieline_step_by_step.md` (c2-c6), `dielines_structure/illustrator_dielines_bleed_cutlines.md` (c1,c2), `dielines_structure/packmojo_folding_carton_dieline_101.md` · **3-source, triangulated** · **NOT_WIRED** · engine: **PRESENT** — `apps/dielines/geometry/ecma_ste.py`, `panels.py`, `engine.py`. The archetype is built; the corpus corroborates it.

**H036 — Distinguish cut from crease by colour AND dash pattern, on separate layers, and ship an in-file legend.**
The corpus **conflicts**: Munes says the convention is safe to hard-code; Lumi says it varies by house. The legend is what resolves it — carry the convention *and* declare it in the file.
`dielines_structure/munes_studio_dieline_step_by_step.md` (c7), `dielines_structure/illustrator_dielines_bleed_cutlines.md` (c7), `dielines_structure/packmojo_folding_carton_dieline_101.md`, `artwork_prepress/lumi_dielines_proofs_prepress101.md` (c5), `corrugated_shipper/designdreamscape_mailer_dieline.md` (c5) · **5-source** · **NOT_WIRED** · engine: **PARTIAL** — `apps/dielines/exporters/artwork_layers.py` exists; legend emission UNMEASURED.

**H037 — Auto-generate bleed as a round-join offset of the cut path.**
`dielines_structure/munes_studio_dieline_step_by_step.md` (c8) · 1-source · **NOT_WIRED** · engine: UNMEASURED

**H038 — Carry a panel-adjacency map, and a per-archetype/per-option panel orientation lookup.**
`dielines_structure/packmojo_folding_carton_dieline_101.md` (c3,c5,c6), `cosmetics_packaging/zested_skincare_full_process.md` (c4,c9) · 2-source · **NOT_WIRED** · engine: **PARTIAL** — `apps/dielines/geometry/panels.py`; adjacency map UNMEASURED.

**H039 — Give each closure type a hidden-zone mask that artwork placement must avoid.**
The repo's `straight_tuck_end_carton/1.1` baseline has a hidden-flap mask that differs from snap-lock.
`dielines_structure/packmojo_folding_carton_dieline_101.md` (c5) · 1-source · **NOT_WIRED** · engine: UNMEASURED

**H040 — Apply the 180° top-panel rotation for Option-1 fronts in any fold preview or unfold/refold check.**
Without it the fold preview lies. Same family: components must be verified in the assembled state, not the flat file.
`dielines_structure/packmojo_folding_carton_dieline_101.md` (c3), `cosmetics_packaging/product_packaging_full_process_3d_mockups.md` (c7), `mockup_render/blender_mockup_from_dieline_fold.md` (c1,c2,c4), `luxury_teardowns/bulgari_luxury_unboxing_teardown.md` (c2) · **4-source** · **NOT_WIRED** · engine: **PARTIAL** — `apps/dielines/exporters/folded_diagnostic.py` exists; rotation correctness UNMEASURED.

**H041 — Add the RSC shipping carton as a second parametric archetype.**
Slotted flaps — different closure geometry from the tuck-end retail carton.
`dielines_structure/shipping_carton_dieline_kraft_design.md` (c1) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H042 — Split rigid boxes into `rigid_setup` vs `rigid_collapsible` format vocabulary.**
Rigid is not one construction: collapsible/magnetic folds flat with a continuous outer wrap as hinge; classic set-up boxes are erected and stay erected. Different dieline logic, different freight story.
`rigid_box_construction/zypack_magnetic_folding_box.md` (c1,c3), `rigid_box_construction/otoole_rigid_box_gluing_up.md` (c1) · 2-source · **NOT_WIRED** · engine: NOT_PRESENT

**H043 — State which walls overlap when computing rigid-box internal dimensions.**
Butt-joint geometry: internal dims = base minus 2× board caliper on the overlapping axis.
`rigid_box_construction/otoole_rigid_box_gluing_up.md` (c4) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H044 — Treat structure, wrap and fitment as independent spec lines.**
Hand-craft order (carcass → wrap → lining) is the same separation the industrial teardowns show. The tin analogue: decoration, body and seal compound are independent.
`rigid_box_construction/otoole_rigid_box_gluing_up.md` (c1), `metal_tin_packaging/howitsmade_tins.md` (c7), `luxury_teardowns/bulgari_luxury_unboxing_teardown.md` · **3-source** · **NOT_WIRED** · engine: NOT_PRESENT

**H045 — Model `pouch_standup` as 3-web construction and treat the bottom gusset as a printable third face.**
Not a fold-under.
`flexible_pouches/packmojo_pouch_dieline.md` (c3,c4) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H046 — Add a `seal` line class for pouch formats, and treat seal zones as corner keep-outs.**
Pouch dielines carry curved seal geometry (gusset arcs), unlike cartons' straight creases; the cut/crease/bleed vocabulary is insufficient.
`flexible_pouches/hashhcm_coffee_pouch_dieline.md` (c3,c4), `flexible_pouches/packmojo_pouch_dieline.md` (c5,c6) · 2-source · **NOT_WIRED** · engine: NOT_PRESENT

**H047 — Never generate pouch seal geometry from scratch.**
Even tutorial authors start from a supplier's pouch dieline.
`flexible_pouches/hashhcm_coffee_pouch_dieline.md` (c5), `flexible_pouches/packmojo_pouch_dieline.md` (c1) · 2-source · **NOT_WIRED** · engine: NOT_PRESENT · *refusal hook*

**H048 — Record the pouch dimension anchor as a ratio sanity-check, not a spec.** ⚠ LOW-CONFIDENCE
250 g coffee ≈ 140 mm wide × 80 mm gusset (height ~240 mm from dialogue at 0:31, marked low-confidence by the note itself). Usable as gusset ≈ 55–60% of width.
`flexible_pouches/hashhcm_coffee_pouch_dieline.md` (c2) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H049 — Add board-caliper allowances between nested corrugate panels, in 0.125 in steps.**
Corrugate's differentiator from folding cartons; allowance ≈ flute caliper.
`corrugated_shipper/designdreamscape_mailer_dieline.md` (c2) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H050 — Construct corner radii as real path work; do not fake them with rounded strokes on a rectangle.**
`corrugated_shipper/designdreamscape_mailer_dieline.md` (c4) · 1-source · **NOT_WIRED** · engine: UNMEASURED · *refusal hook*

**H051 — Require BOTH axes on a board callout: ply/wall count AND flute grade.**
"3-ply / E-flute" is complete; either alone is ambiguous. Ply count = wall count (3↔single, 5↔double, 7↔triple); flute grade = wave geometry.
`corrugated_shipper/cuboid_corrugated_terminology.md` (c2,c3), `corrugated_shipper/guka_flute_guide.md` (c3) · 2-source · **NOT_WIRED** · engine: **NOT_PRESENT** — `flute` appears in 0 `.py` files under `apps/`.

**H052 — Take the MAX of the weight-derived and fragility-derived board recommendations.**
Weight gives a floor (12 glass bottles ≈ 6–8 kg → 3-ply); fragility overrides upward (glassware → BC double-wall).
`corrugated_shipper/cuboid_corrugated_terminology.md` (c4), `corrugated_shipper/guka_flute_guide.md` (c6) · 2-source · **NOT_WIRED** · engine: NOT_PRESENT

**H053 — Do not emit GSM (paper grammage) numbers.** ⚠ UNSOURCED-GAP
The corpus names GSM as a third board parameter and has **not** evidenced it. An open intake gap, recorded as a refusal rather than a value.
`corrugated_shipper/cuboid_corrugated_terminology.md` (c5) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT · *refusal hook*

**H054 — Store wall count canonically; render "ply" or "wall" per supplier locale.**
Indian-supplier "ply" and Western "wall" describe the same structure.
`corrugated_shipper/cuboid_corrugated_terminology.md` · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H055 — Carry a max-sheet parameter per supplier, and segment oversized dielines with glue flaps.**
`luxury_teardowns/last_crumb_dtc_teardown.md` (c3) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H056 — Encode three insert-generation constraints: nest parts in parent-sheet waste, minimise fold complexity, angle platforms toward the opener.**
Pack-out time is an explicit cost term.
`luxury_teardowns/last_crumb_dtc_teardown.md` (c5,c6) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H057 — Keep the tail-crimp zone clear on tube artwork.**
The crimp is the filler's step; the tube arrives filled-ready except for it.
`tube_packaging/idealpak_extruded_tube_process.md` (c5,c6), `tube_packaging/weltrade_tube_manufacturing.md` (c2,c7) · 2-source · **NOT_WIRED** · engine: NOT_PRESENT

**H058 — Bound tube concepts to the 20–220 ml envelope for extruded tubes.**
`tube_packaging/idealpak_extruded_tube_process.md` (c8) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H059 — Add a tube construction field (extruded vs laminate), chosen partly by artwork complexity.**
Photographic/fine artwork wants PBL/ABL printed flat; extruded mono-tubes are the silkscreen/offset/foil register. Same flat-vs-curved logic as bottle decoration.
`tube_packaging/weltrade_tube_manufacturing.md` (c4), `tube_packaging/idealpak_extruded_tube_process.md` (c1,c2) · 2-source · **NOT_WIRED** · engine: NOT_PRESENT

**H060 — Reserve vertical height for the pump functional stack; artwork may not borrow from actuator travel.** `OWNER-GATED`
The stack (actuator → rod → spring → ball check → dip tube) is a fixed vertical order and the rod-hole/piston valving imposes a minimum stroke. This is C10-adjacent (dropper composer, SIZE axis) — **C10 is the owner's**; specify the constraint, do not compose against it.
`dropper_pump_dispensing/soap_pump_mechanism_3d.md`, `dropper_pump_dispensing/lotion_pump_airlock_priming.md` (c7) · 2-source · **NOT_WIRED** · engine: NOT_PRESENT

**H061 — Make neck finish (T-series, e.g. 20-410, 24-415) a required field on every bottle/closure component; two parts mate only if codes match.**
The compatibility key across bottle, cap, pump and dropper — and what cross-supplier interchangeability relies on. The finish is molded, not added, and is machine-inspected.
`jars_closures/neck_finish_construction_illing.md` (c3,c4), `jars_closures/us_bottle_jar_suppliers_skincare.md` (c4,c5), `glass_manufacturing/roetell_glass_bottle_process.md` (c3,c4), `glass_manufacturing/how_glass_is_made_composition.md` (c6) · **4-source** · **NOT_WIRED** · engine: **PARTIAL** — `neck_finish` appears in 4 non-test service modules (`geometry_evidence.py`, `reference_manifest.py`, `web_geometry_research.py`, `p1_pilot_geometry.py`) as *evidence/research*, not as a component mate-key.

**H062 — Add liner type, land, adhesive type and S-dimension as explicit spec lines.**
Seal quality lives in land + liner, not threads. Adhesive is a required line item, not implied. S-dimension controls closure orientation — it matters when cap artwork must align with the front label.
`jars_closures/neck_finish_construction_illing.md` (c1,c6), `label_substrates/pressure_sensitive_label_materials_overview.md` (c6) · 2-source · **NOT_WIRED** · engine: NOT_PRESENT

---

## §4 — PROOF & SUPPLIER EMITTERS

**H063 — Request the supplier's dieline rather than asserting ours as final.**
The corpus's second-strongest convergence, and it is a rule about *restraint*: magnet slots and pre-glued gussets, tin draw-distortion compensation, stock mold sizes and pouch seal geometry are all supplier-owned. The emitter should not attempt them.
`artwork_prepress/lumi_dielines_proofs_prepress101.md` (c4), `rigid_box_construction/zypack_magnetic_folding_box.md` (c4,c6), `metal_tin_packaging/howitsmade_tins.md` (c5), `metal_tin_packaging/xinpengda_tin_factory.md` (c4), `flexible_pouches/hashhcm_coffee_pouch_dieline.md` (c5), `flexible_pouches/packmojo_pouch_dieline.md` (c1) · **6-source** · `CEILING-A5` (the *request* is the withdrawn route; the restraint is not) · **NOT_WIRED** · engine: UNMEASURED · *refusal hook*

**H064 — Treat proof approval as a contract: a bar that cannot move afterwards.** `OWNER-GATED`
This is exactly the D-section acceptance semantics already in force. It is listed to record the corroboration, **not** to propose new acceptance machinery — §AE0(a) forbids the executor writing acceptance states.
`artwork_prepress/lumi_dielines_proofs_prepress101.md` (c7) · 1-source · **NOT_WIRED** · engine: **PRESENT** (existing owner-acceptance gates)

**H065 — Bind colour approval to physical samples, not screens.**
Drawdowns against a standard for labels/film; paper-overlay test for new dielines; a fold test in the handoff checklist; preflight → proof → done.
`artwork_prepress/lumi_dielines_proofs_prepress101.md` (c6,c7), `color_management/oppaca_screen_vs_print.md` (c2,c5,c6), `ink_color_systems/ryonet_pantone_ink_mixing.md` (c7), `printing_processes/labeltech_flexo_basics.md` (c5), `cosmetics_packaging/paola_skincare_brand_ep2_packaging.md` (c5), `artwork_prepress/papp_prepress_stages_plates.md` (c1,c2) · **6-source** · **NOT_WIRED** · engine: UNMEASURED

**H066 — Offer a ±1 PMS bracket on proof requests whenever substrate ≠ plain coated paper.**
The concrete N−1/N/N+1 recipe, extending the adjacent-PMS fallback.
`color_management/oppaca_screen_vs_print.md` (c7), `ink_color_systems/ryonet_pantone_ink_mixing.md` (c7) · 2-source · **NOT_WIRED** · engine: NOT_PRESENT

**H067 — Require both supplier authorities on pouch jobs: dieline AND orientation guide.**
`flexible_pouches/packmojo_pouch_dieline.md` (c1) · 1-source · `CEILING-A5` · **NOT_WIRED** · engine: NOT_PRESENT

**H068 — Make an in-file legend plus a W/H/D size caption a standard emitter output for corrugated formats.**
Self-documenting template, same pattern as the pouch orientation guide.
`corrugated_shipper/designdreamscape_mailer_dieline.md` (c5) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H069 — Make the emitted artwork declare its ink plan explicitly.**
`artwork_prepress/papp_prepress_stages_plates.md` (c8) · 1-source · **NOT_WIRED** · engine: **PARTIAL** — `separation_inventory` exists in the container handoff graph.

**H070 — Emit emboss tooling as a male/female PAIR with a GSM-parameterised path offset (0.5–2 mm), built by offsetting paths rather than strokes.**
Three hard-checkable rules in one hook, if the OS ever emits finishing tooling.
`print_finishing/emboss_blocks_flexo_label_printing.md` (c5-c7) · 1-source · `CEILING-A5` · **NOT_WIRED** · engine: NOT_PRESENT

**H071 — Bound emboss depth by paper GSM.** ⚠ UNSOURCED-GAP
The relationship is evidenced (tearing at excessive depth); the numeric GSM→max-offset table is not. Pairs with H053 — the engine has no sourced GSM values.
`print_finishing/emboss_blocks_flexo_label_printing.md` (c6) · 1-source · `CEILING-A5` · **NOT_WIRED** · engine: NOT_PRESENT

**H072 — Spec foil against supplier chart codes with a "nearest-available" caveat, never as a Pantone promise.**
`print_finishing/hot_foil_guru_explanation_of_foils.md` (c6,c9) · 1-source · `CEILING-A5` · **NOT_WIRED** · engine: NOT_PRESENT

**H073 — Derive the process recommendation from run-quantity and SKU-count fields.**
Process choice is quantity-driven, not quality-driven. Digital's short-run advantage is make-ready cost plus ~30% changeover downtime; offset/flexo invert at volume.
`printing_processes/domino_flexo_digital_hybrid.md` (c3,c5,c8,c9), `ink_color_systems/innorhino_pantone_vs_cmyk.md` (c5), `printing_processes/expresscards_offset_printing.md` (c4), `printing_processes/lilpackaging_litho_vs_flexo.md` · **4-source** · `CEILING-A5` · **NOT_WIRED** · engine: NOT_PRESENT

**H074 — Treat flexo image quality as supplier-dependent, not process-forbidden.**
A 2020 "stick to line work" claim is tempered by a capable house claiming process imagery today; converters run both processes, so "flexo or digital?" is a per-job question. Do not hardcode either way.
`printing_processes/labeltech_flexo_basics.md` (c8), `printing_processes/domino_flexo_digital_hybrid.md` (c7) · 2-source · `CEILING-A5` · **NOT_WIRED** · engine: NOT_PRESENT · *refusal hook*

**H075 — Default shipper artwork to flexo-safe, and flag litho-lam as a premium with an explicit ~+40% cost delta.**
You cannot run corrugate through a litho press; photographic print on a shipper means a laminated second substrate.
`printing_processes/lilpackaging_litho_vs_flexo.md` (c5) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H076 — Treat a shipment as TWO specs with different artwork registers: unit carton and shipper.**
Unit carton = litho/offset, print-facing E/F flute or folding carton. Shipper = flexo, freight-facing B/C. No photographic imagery or fine gradients on the shipper.
`printing_processes/lilpackaging_litho_vs_flexo.md` (c2-c4), `corrugated_shipper/guka_flute_guide.md` (c3,c6) · 2-source · **NOT_WIRED** · engine: NOT_PRESENT

**H077 — Allow single-colour flexo repeat patterns on shipper interiors without triggering the litho-lam premium.**
The motif-as-surface direction can ride one-colour flexo on tissue and inside-box prints.
`printing_processes/lilpackaging_litho_vs_flexo.md` (c3) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H078 — Record supplier-shortlist and RFQ-vocabulary hooks as UNRESOLVED spec fields, not as outreach work.** `CEILING-A5`
The corpus names US low-MOQ channels, mono-material pump vendors, and RFQ process terms ("V-cut turned edge", "wet-press molded pulp", glass QC defect names). All are real; **none may be acted on**. §C2 withdrew supplier outreach permanently.
`jars_closures/us_bottle_jar_suppliers_skincare.md` (c2,c3,c6), `sustainable_materials/monomaterial_advancements.md`, `luxury_teardowns/iphone_box_cost_breakdown.md` (c2,c5), `glass_manufacturing/roetell_glass_bottle_process.md` (c6) · **4-source** · **NOT_WIRED** · engine: NOT_PRESENT · *refusal hook*

---

## §5 — MOCKUP-RENDER ROUTES

**H079 — Name which of four mockup tiers a deliverable requires.** ⚠ NO-TIME-ANCHOR *(partial — the foil-decoration leg comes from the untimestamped note)*
The ladder, cheapest first: (1) Photoshop-on-photo, (2) Dimension starter-asset + decals, (3) Blender UV-cube, (4) Blender fold-the-dieline.
`mockup_render/trouvaille_photoshop_box_mockup.md`, `mockup_render/zero2graphic_dimension_box_mockup.md`, `mockup_render/blender_quick_box_mockup_uv.md`, `mockup_render/blender_mockup_from_dieline_fold.md` · **4-source** · **NOT_WIRED** · engine: **PARTIAL** — `apps/dielines/exporters/mockup_3d.py` exists; tier selection UNMEASURED.

**H080 — Derive the folded preview mechanically from existing fold-line data.**
The manual Blender workflow (cut mesh at fold lines → rotate panels) is exactly what the dieline already encodes: the fold lines *are* the mesh cuts and rotation axes.
`mockup_render/blender_mockup_from_dieline_fold.md` (c1,c2,c4) · 1-source · **NOT_WIRED** · engine: **PARTIAL** — `apps/dielines/exporters/folded_diagnostic.py`.

**H081 — Never use the photo-based route for dieline sign-off.**
It validates perspective and mood only — no geometry check, no real dimensions.
`mockup_render/trouvaille_photoshop_box_mockup.md` · 1-source · **NOT_WIRED** · engine: NOT_PRESENT · *refusal hook*

**H082 — Never use the decal route to validate artwork geometry.**
Decal placement is eyeballed onto faces; it validates LOOK, not dieline fidelity.
`mockup_render/zero2graphic_dimension_box_mockup.md` · 1-source · **NOT_WIRED** · engine: NOT_PRESENT · *refusal hook*

**H083 — Emit per-panel rasters alongside the full dieline PDF.**
Three independent consumers named it: Dimension decals, Vanishing Point panes, Blender UV faces.
`mockup_render/zero2graphic_dimension_box_mockup.md` (c3), `mockup_render/trouvaille_photoshop_box_mockup.md` (c1), `mockup_render/blender_quick_box_mockup_uv.md` (c2) · **3-source** · **NOT_WIRED** · engine: NOT_PRESENT

**H084 — Give render shells thickness so open-box and edge shots read as board.**
Edges are where quality is read — the same attention the physical teardowns pay to V-cut edges.
`mockup_render/blender_quick_box_mockup_uv.md` (c4) · 1-source · **NOT_WIRED** · engine: UNMEASURED

**H085 — Pass true physical dimensions into the mockup, not just ratios.**
`mockup_render/zero2graphic_dimension_box_mockup.md` (c5) · 1-source · **NOT_WIRED** · engine: UNMEASURED

**H086 — Approximate finish with PBR Roughness/Metallic before paying for physical proofs.**
Matte vs gloss vs foil, previewed; 16-bit PSD export as the handoff.
`mockup_render/zero2graphic_dimension_box_mockup.md` (c2,c6) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H087 — Keep substrate shadow and highlight alive under flat art (Multiply + split Blend-If).**
Applies to any photo-based mockup, including smart-object template PSDs.
`mockup_render/trouvaille_photoshop_box_mockup.md` (c5,c6) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H088 — Check artwork continuity across folds and panel adjacency as mockup QA.**
The visible failure modes a folded preview catches before print.
`mockup_render/blender_mockup_from_dieline_fold.md` (c5) · 1-source · **NOT_WIRED** · engine: UNMEASURED

**H089 — Render substrate texture as a layer under artwork, clipped to the cut path — not as a filter.**
How kraft/uncoated stocks should preview.
`dielines_structure/shipping_carton_dieline_kraft_design.md` (c3) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H090 — Render pump and airless formats with their functional geometry visible.**
A pump head drawn with no collar/travel gap reads as fake; airless bottles have a flat internal follower piston, so their base is flat/near-flat, not a punt.
`dropper_pump_dispensing/soap_pump_mechanism_3d.md`, `dropper_pump_dispensing/airless_pump_bottle_materials.md`, `jars_closures/airless_pump_mechanism.md` (c1,c3) · **3-source** · **NOT_WIRED** · engine: NOT_PRESENT

---

## §6 — MATERIALS & SUSTAINABILITY

**H091 — Give the material trade-off table a date/state field rather than fixed rules.**
Mono-material variants are marketed by matching legacy performance specs; the barrier-vs-recyclability trade-off is actively being engineered away. A fixed rule will decay.
`sustainable_materials/monomaterial_advancements.md` (c2,c3,c4) · 1-source · `CEILING-A5` · **NOT_WIRED** · engine: NOT_PRESENT

**H092 — Make PCR percentage a spec field AND a design-register variable.** `OWNER-GATED`
PCR fraction trades directly against aesthetic control — darker colour, lower clarity, more surface imperfection. High-PCR reads honest/raw; low-PCR preserves the pristine surface. "PCR" spans 10–100% and 10% still gets the label, so copy claims need the number. **Touches `BACKGROUNDS_PERMITTED`**: a darker PCR substrate is a ground the permitted set does not contain. Specify the axis; do not widen the set.
`sustainable_materials/pcr_bottle_intro.md` (c2,c3,c4,c6), `sustainable_materials/nosco_pcr_flexible_film.md` (c1,c3) · 2-source · **NOT_WIRED** · engine: **NOT_PRESENT** — `pcr` appears in 0 `.py` files under `apps/`.

**H093 — Never conflate LOOK-sustainable with BE-sustainable in concept scoring.**
Kraft surface vs actual waste-stream diversion are different claims; a foil core blocks mono-material recyclability while delivering shelf life.
`sustainable_materials/nosco_pcr_flexible_film.md` (c2,c4) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT · *refusal hook*

**H094 — Record decoration-and-material vocabulary per component family.** ⚠ NO-TIME-ANCHOR *(the molded-plastic foil leg)*
Glass: decal-fire / rotary screen / spray coat / acid frost — four processes with different coverage (motif vs 360° vs all-over vs surface effect); 360° wraparound is one-pass manufacturable on automated lines; partial frosting is masking-based (frost field + clear window). Tubes: PCR, sugarcane PE, EVOH at the resin level. Plastic parts: hot foil onto molded lids/caps with a fixture.
`bottle_decoration/roetell_glass_decoration_techniques.md` (c1-c6), `tube_packaging/weltrade_tube_manufacturing.md` (c1), `print_finishing/hot_foil_stamping_animation_technoshell.md` (c4) · **3-source** · `CEILING-A5` · **NOT_WIRED** · engine: NOT_PRESENT

**H095 — Report colour count as the cost driver for direct bottle decoration.**
One film + one screen + one dry cycle per colour: price and time scale with colour count.
`bottle_decoration/silkscreen_printing_beauty_packaging_9step.md` (c2,c5) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H096 — Flag substrate ↔ product-chemistry conflicts explicitly.**
The recurring pattern: chemistry gates aesthetics. Textured/uncoated paper carries the luxury-artisan read but fails against oil contact; formula viscosity and fill method gate an airless pump; PE/PP need flame pretreatment before decoration; curved/squeezable containers need film, not paper.
`label_substrates/pressure_sensitive_label_materials_overview.md` (c2,c4,c5), `jars_closures/airless_pump_mechanism.md` (c4), `bottle_decoration/silkscreen_printing_beauty_packaging_9step.md` (c4) · **3-source** · `CEILING-A5` · **NOT_WIRED** · engine: NOT_PRESENT

**H097 — Encode a finish→register enum for labels, including the no-label look.**
Glossy = mainstream retail; matte/uncoated = craft; kraft = artisan/natural; clear = modern no-label-look. Clear film reads as direct-on-glass decoration at label cost — a cheap alternative to silkscreen/decal routes. At low volumes labels are hand-applied on curves, so avoid full-wrap registration-critical seams.
`label_substrates/choosing_label_material_examples.md` (c1,c3,c4,c5,c6), `label_substrates/pressure_sensitive_label_materials_overview.md` · 2-source · **NOT_WIRED** · engine: NOT_PRESENT

**H098 — Treat tooling as a distinct cost class from decoration.**
Embossed glass logos are a custom-mold tooling line item, not a decoration line item — different cost class and lead time from silkscreen. For tins, default to stock mold sizes and treat custom draw tooling as a cost flag; the recommendation query is "closest stock size", not "exact custom size".
`glass_manufacturing/how_glass_is_made_composition.md` (c5), `metal_tin_packaging/xinpengda_tin_factory.md` (c4) · 2-source · `CEILING-A5` · **NOT_WIRED** · engine: NOT_PRESENT

**H099 — Model metal tins as decorated FLAT before forming, with a real body seam.**
The inversion from bottle decoration (which prints onto an already-formed 3D surface): artwork for formed tin lids must anticipate draw distortion, and the compensation is converter-owned. Both body constructions (welded, lock seam) leave a vertical seam — place it like a label overlap, do not pretend the cylinder is seamless. Format vocabulary: `slip_lid`, `seamed_ends`, `hinged_rect`, `shaped`. Because decoration is offset on flat sheet, solid-colour and full-art tins cost the same press pass.
`metal_tin_packaging/howitsmade_tins.md` (c1,c5,c6,c7), `metal_tin_packaging/xinpengda_tin_factory.md` (c1,c5,c6) · 2-source · **NOT_WIRED** · engine: NOT_PRESENT

**H100 — Carry cost and lead-time anchors as directional sanity checks.** ⚠ NO-TIME-ANCHOR *(the foil-area leg)*
Complete rigid-box + pulp-tray kit ≈ $1.27/unit @ 50k. Custom tubes ≈ 10-week landed lead time. Glass carries a shipping-weight penalty, so score it surgically (small formats). Small-MOQ launches preserve rebrand optionality. Foil cost scales with stamped bounding area and web width waste, not preciousness — small marks are cheap to foil. Crosscut vs V-groove is a cost/quality dial for rigid-box inserts. E/F corrugate is an inner-fitment alternative to paperboard.
`luxury_teardowns/iphone_box_cost_breakdown.md` (c7), `tube_packaging/weltrade_tube_manufacturing.md` (c7), `jars_closures/us_bottle_jar_suppliers_skincare.md` (c7,c8), `print_finishing/hot_foil_guru_explanation_of_foils.md` (c4,c5), `print_finishing/hot_foil_stamping_animation_technoshell.md` (c3), `cosmetics_packaging/being_haircare_teardown_brand_building.md` (c3,c8), `corrugated_shipper/guka_flute_guide.md` (c7) · **7-source** · `CEILING-A5` · **NOT_WIRED** · engine: NOT_PRESENT

---

## §7 — SHELF & BRAND PSYCHOLOGY

**H101 — Score shelf-facing concepts against a 7-second read horizon.**
Brand + register must resolve in one glance.
`shelf_retail/brand_persuasion_packaging_psychology.md` (c1) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H102 — Approximate first-fixation, time-to-find and dwell with contrast/distinctiveness heuristics against competitor shelves.**
Shelf performance is measurable, not taste.
`shelf_retail/package_design_affects_sales_casestudies.md` (c1) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H103 — Record intended market on palette decisions.** `OWNER-GATED`
Cultural colour coding is a checkable dimension, and the mandatory-element set switches on the same field (H028). Palette decisions are the owner's; this records the field, not the choice.
`shelf_retail/brand_persuasion_packaging_psychology.md` (c6), `label_substrates/fda_cosmetic_labeling_rules.md` (c6) · 2-source · **NOT_WIRED** · engine: NOT_PRESENT

**H104 — Preserve recognition equity across redesigns; treat distinctive assets as capital.**
The premium read is fragile in both directions — one brand gained it (muted + rustic + hand-drawn = artisan), another lost it (generic imagery = cheaper, and the discarded straw was the equity).
`shelf_retail/package_design_affects_sales_casestudies.md` (c3,c4) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H105 — Keep radical-transparency layout in the concept space as a counterpoint register.**
Ingredients as hero is a proven mainstream device, opposite to the restraint register.
`shelf_retail/package_design_affects_sales_casestudies.md` (c2) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H106 — Score kit/coffret concepts on a monotonic-anticipation curve.**
Each layer ≥ the previous in brand intensity; no unbranded step after the first branded one. A checkable structural rule.
`luxury_teardowns/bulgari_luxury_unboxing_teardown.md` (c5) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H107 — Put unboxing pacing in the structural spec, not only in graphics.**
The opening sequence is a designable surface; the slow-lid effect is the mainstream proof.
`shelf_retail/brand_persuasion_packaging_psychology.md` (c5), `luxury_teardowns/bulgari_luxury_unboxing_teardown.md` (c5) · 2-source · **NOT_WIRED** · engine: NOT_PRESENT

**H108 — Require inner components to hold the same quality grade as the shell.**
The luxury→generic→luxury failure, seen from both the teardown and the cost side.
`luxury_teardowns/iphone_box_cost_breakdown.md` (c6), `luxury_teardowns/bulgari_luxury_unboxing_teardown.md` · 2-source · **NOT_WIRED** · engine: NOT_PRESENT

**H109 — Make one-pull opening a checkable per-component requirement, and check extraction orientation.**
Inner components must be removable by lifting toward the user with correct product orientation.
`luxury_teardowns/iphone_box_cost_breakdown.md` (c9), `luxury_teardowns/bulgari_luxury_unboxing_teardown.md` (c2) · 2-source · **NOT_WIRED** · engine: NOT_PRESENT

**H110 — Treat magnet pull and tissue acoustics as tunable spec windows, not maxima.**
Sensory parameters with a correct range, not a "more is better" axis.
`luxury_teardowns/bulgari_luxury_unboxing_teardown.md` (c3,c6) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H111 — Keep the vellum veil as a reusable luxury device.**
Consistent with the restraint register.
`luxury_teardowns/bulgari_luxury_unboxing_teardown.md` (c7) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H112 — Treat usability defects as brand defects.**
Functionality is a perception gate — it connects the closure mechanics of §3 to shelf psychology.
`shelf_retail/brand_persuasion_packaging_psychology.md` (c4) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H113 — Require a non-generic USP before visual work starts.**
A concept-brief gate, upstream of layout.
`cosmetics_packaging/zested_skincare_full_process.md` (c1) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H114 — Emit an information inventory with priority ranking as a pre-layout artifact for owner review.**
`cosmetics_packaging/product_packaging_full_process_3d_mockups.md` (c6) · 1-source · **NOT_WIRED** · engine: NOT_PRESENT

**H115 — Apply copy-layout quotas: cap-interior storytelling ≈ 5 short blocks; decorative type for hero and titles only, info text in plain sans; a mandatory product-descriptor line.**
Candidate VQR checks.
`cosmetics_packaging/being_haircare_teardown_brand_building.md` (c4), `cosmetics_packaging/zested_skincare_full_process.md` (c5,c7) · 2-source · **NOT_WIRED** · engine: **PARTIAL** — `apps/ire/back_panel_copy.py`, `apps/ire/container_typography_metrics.py` exist; quotas UNMEASURED.

**H116 — Run a decode test on molded or abstract SKU icons.** `OWNER-GATED`
Icon risk is legibility risk, and legibility is what the **12.0 mm size floor** (§C2) and the **1.0× cap-height clear space** exist to protect. Specify the test; do not move either bar to pass it.
`cosmetics_packaging/being_haircare_teardown_brand_building.md` (c7) · 1-source · **NOT_WIRED** · engine: **PARTIAL** — `apps/ire/container_text_floor.py`, `container_line_weight.py`, `container_logo_metrics.py` exist.

**H117 — Keep concept-generation constraints from the teardowns: restraint outside / story inside, single-deboss hero marks, proportion inversion as a novelty axis, and a single large foil hit on a one-colour box as the luxury-economy default.**
The foil device is **third-source confirmed** and explicitly called safe as a default concept device; emboss+foil is the compound premium move. Complexity lives in craft, not clutter.
`cosmetics_packaging/being_haircare_teardown_brand_building.md` (c1,c6,c7), `luxury_teardowns/last_crumb_dtc_teardown.md` (c4), `print_finishing/hot_foil_guru_explanation_of_foils.md`, `print_finishing/emboss_blocks_flexo_label_printing.md` (c3) · **4-source** · **NOT_WIRED** · engine: NOT_PRESENT

**H118 — Support procedural imperfect lettering, cross-panel continuous artwork, and tear-strip copy zones as layout devices.**
Vary repeated glyphs and liquify terminals for custom lettering; cross-panel artwork and a repeated bridging motif need the panel-adjacency map (H038); tear strips and flaps are copy real estate and a candidate zone type. "Structure constant, recolor for variants" maps the palette programme onto product-line renders.
`cosmetics_packaging/zested_skincare_full_process.md` (c6,c4,c9), `luxury_teardowns/last_crumb_dtc_teardown.md` (c2), `cosmetics_packaging/product_packaging_full_process_3d_mockups.md` (c8) · **3-source** · **NOT_WIRED** · engine: **PARTIAL** — `apps/ire/container_motif.py`, `compose_vector_art.py` exist.

---

## FURTHER INTAKE HOOKS (not engine work)

Two hooks in the corpus are about growing the corpus rather than the engine, and
are recorded here so they are not lost among implementation entries:

- **Scan owned physical reference packs into traceable dielines with panel
  semantics.** A cheap way to grow the carton archetype library from real luxury
  references BBROSE already owns.
  `cosmetics_packaging/paola_skincare_brand_ep2_packaging.md` (c1,c2)
- **The corpus rates one channel as a trusted repeat source** (samples-in-hand
  format, three notes, consistently usable heuristics).
  `printing_processes/lilpackaging_litho_vs_flexo.md`

---

## MEASUREMENT LOG

Every count in this file, and the query that produced it. Stated because two
regex failures during this session produced confident wrong numbers, and because
`\b` does not work on this platform's grep.

| claim | value | how measured |
|---|---|---|
| notes in corpus | 60 | `find docs/design_intelligence/watch -name '*.md'` minus README + WATCH_QUEUE — **and now minus this file too**: see SELF-INCLUSION below |
| domains | 21 | `ls docs/design_intelligence/watch/` minus README.md, WATCH_QUEUE.md and this file. Was written as "= 23 entries − README.md − WATCH_QUEUE.md"; `ls` now returns **24** |
| notes with a hooks section | 60 | 59 use `## Engine hooks`; `ink_color_systems/ryonet_pantone_ink_mixing.md` uses `## Claims → Engine hooks` |
| notes with a time/frame anchor | 59 / 60 | regex over all **three** conventions: `` `t=M:SS` ``, `[t=M:SS]`, `[frame NN, ≈M:SS]`. A single-convention regex reports 25/60 and is wrong. |
| notes naming a supplier-contact route | 13 / 60 | `awk` over the extracted hook sections for `supplier outreach\|supplier question\|supplier RFQ\|RFQs\|ask the converter\|ask a supplier\|supplier-confirmed\|supplier confirms` |
| `delta_e` in app code | 2 `.py` files | `grep -rli delta_e --include='*.py' apps/` — **not** zero, as an earlier measurement in this session wrongly concluded |
| `gamut`, `drawdown`, `pcr`, `flute`, `run_quantity`, `artwork_side` | 0 `.py` files each | `grep -rli <token> --include='*.py' apps/` |
| `bleed` | 102 `.py` files | same query — present, but parameterisation UNMEASURED |
| `neck_finish` | 10 `.py` files, 4 non-test | same query, then `| grep -v tests` |
| `spot_swatch` | 7 `.py` files | same query — and reading them is what produced H019/H020 |
| `PALETTE_TOLERANCE_DE` | `25.0` | `apps/pipeline/services/image_checks.py:45` |
| entries | 118 | `grep -cE '^\*\*H[0-9]{3} '` — and `comm` against `seq 1 118` to prove no gap and no duplicate |
| `OWNER-GATED` entries | 6 | H011, H060, H064, H092, H103, H116 |
| `CEILING-A5` entries | 15 | H031, H034, H063, H067, H070–H074, H078, H091, H094, H096, H098, H100 |
| `NO-TIME-ANCHOR` entries | 3 | H079, H094, H100 |
| `UNSOURCED-GAP` entries | 2 | H053, H071 |
| refusal hooks | 11 | H002, H005, H047, H050, H053, H063, H074, H078, H081, H082, H093 |
| `engine:` states | 79 NOT_PRESENT / 18 UNMEASURED / 16 PARTIAL / 5 PRESENT | sums to 118. Was `17 PARTIAL / 4 PRESENT` until H020 was wired and moved between them |
| `WIRED` entries | 1 / 118 | H020. Every other entry is still `NOT_WIRED` |

**How the marker counts were measured, and the trap in them.** By parsing the
file into its 118 entry blocks and counting *blocks containing the marker* — not
by `grep -c`. A whole-file `grep -c` over-counts, because the MARKERS section
above **defines** each marker by name and those definitions match the same
pattern. The inflated numbers are wrong by exactly the number of times each
marker is discussed rather than applied. This bit once already in this session,
in a draft of the tracker node that cited 9 and 18.

**SELF-INCLUSION — this correction was itself wrong, twice, for the same reason.**

*First.* The sentence above originally read: *"A whole-file `grep -c` returns
9 / 18 / 4 / 3"*. On the committed file it returns **10 / 19 / 5 / 4**. The extra
one in each is *this very paragraph and the table rows above it*, which name each
marker in the course of correcting the count. A note explaining an over-count
joined the population it was describing. The four-value list also sat under the
words "the five marker counts": refusal hooks are the fifth and are **not**
over-counted (11 both ways), because they are named nowhere outside the entries.

*Second.* The two note-count recipes in the table were written before this file
existed and were committed unchanged. `find … -name '*.md'` now returns **63**,
not 62; after subtracting README and WATCH_QUEUE it gives **61**, not 60, and
`ls` returns **24**, not 23. The corpus is still 60 notes across 21 domains —
the VALUES were never wrong — but the queries stopped reproducing them the
moment this file landed in the directory it counts.

Both are the same defect as the marker trap and are left visible rather than
silently rewritten: an instrument that recognises its subject by an incidental
feature will eventually recognise itself.

**Denominators.** "N-source" counts *distinct notes*, out of 60. `engine:` values
are measured against `bbrose_design_os/apps/` only — not `tools/`, not `docs/`.
`UNMEASURED` means exactly that: not looked at, not "probably absent". Marker and
`engine:` counts are over the **118 entry blocks — H001 through H118** — and
exclude the legend above and this log; the whole file is the wrong population
for them. Note the entries do **not** run to this log: `## FURTHER INTAKE HOOKS`
sits between them, so a parser that stops at the log heading has an upper stop
later than the entries' true end. That does not change any count here, because
nothing in that section matches `^\*\*H[0-9]{3} `.

**The line numbers that used to be printed here are gone, and their history is
the argument for removing them.** They read `135–616`; wiring H020 shifted them;
an audit caught the correction (`143–660`) using the parser's stop instead of
the entries' end; the *re-*correction to `143–643` was falsified within minutes
by the very paragraph above that explains the rot, which pushed H118 down again.
Three wrong values, one commit, each honestly derived. A bound that cannot
survive its own edit is not documentation, it is a liability — so the boundary
is named by **symbol**, and the recipe parses blocks between
`^\*\*H[0-9]{3} ` matches. The parse is the instrument; prose numbers were only
ever a courtesy, and this one cost more than it paid.

*Third self-inclusion, caught before commit.* The H020 entry was first written
`engine: now **PRESENT**`. The word "now" sits between the label and the value,
so the census regex matched nothing and silently reported a **4th** category of
one. The entry was reworded — the recipe is the contract, and prose that reads
well to a human but defeats the file's own instrument is a defect in the prose.

---

## WHAT THIS FILE DOES NOT DO

It moves no bar, advances no acceptance gate, and takes no owner decision. It
adds no lettered clearance section. It changes no application code — writing it
touched nothing under `bbrose_design_os/apps/`. Where a hook would require an
owner ruling it is marked `OWNER-GATED` and left as a specification, and where a
hook's delivery route was permanently withdrawn it is marked `CEILING-A5` and
left as an unresolved field.

Nothing here is scheduled. Ordering is the owner's.
