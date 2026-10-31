# Folding-carton dieline standards: STE, RTE, tuck top with auto-lock bottom

Research date: 2026-10-07. Time-boxed desk research. Every rule names its source (see `sources.md` for URLs).
The code was read only; nothing in `/Users/symow/Desktop/bbrose-systemOS` was changed.

## 0. How to read this file

**What this research found first.** Nobody publishes a numeric "industry standard" for flap sizes.
The ECMA Code is the trade's reference catalogue, and it says so itself (ECMA p.4, "The 'non-goals' of the
ECMA Code"): it "was never developed with the intention of becoming a mandatory construction manual". It
calls its drawings "purely generic", says "some details ... are not specified or shown", and leaves the
details to the user. What the trade does share is:

- the **topology** of each style: which panel carries which flap, and the fold directions;
- the **dimension convention**;
- the **line conventions**;
- the **print and finishing rules** that converters publish (bleed, safe area, glue areas, dieline file setup).

Numbers for the tuck, dust flap, glue flap, lock slit and thumb notch are house standards. They live in each
converter's CAD library (ArtiosCAD/Impact standards are configurable and proprietary). The rules below
therefore separate what is established from what is a range or a proposal.

**Evidence grades** (on every rule):

| Grade | Meaning |
|---|---|
| **[P]** | Primary or authoritative document, read in full by me (ECMA Code PDF, Iggesund Graphics Handbook) |
| **[C]** | Converter or printer technical guide, read by me (PaperWorks, Lewisburg, HLP Klearfold, GLBC, Sttark, pack.ly) |
| **[G]** | Generator or CAD default, read by me (DDR68 Rhino toolkit source, Boxshot parameter list, svg.design) |
| **[D]** | Measured by me off a published drawing. Proportions only. ECMA calls its drawings generic, so not normative |
| **[S]** | Search-engine excerpt only. The page was not opened, or could not be (404, bot wall). Unverified; never used alone for a rule |
| **[X]** | My synthesis or proposal from the evidence above. Needs a converter's or a physical sample's confirmation |

Units: mm. `t` is the board caliper (thickness), typically 0.30–0.60 mm for SBS/FBB.

---

## 1. Dimension convention

| # | Rule | Grade / source |
|---|---|---|
| D1 | Carton dimensions are measured **centre-to-centre of the creases** (score-to-score), preferably on the flat blank. | [P] ECMA p.6 §2 |
| D2 | ECMA names them **A × B × H**, always written in that order. **A** is the base dimension *parallel to the hinge of the flap that closes last*: the tuck lid's hinge, so A is the width of the panel that carries the tuck. **B** is the second base dimension. **H** is the height between the flaps that close first at the top and bottom (the dust flaps). | [P] ECMA p.6–7, illustration 1 |
| D3 | North American converters write **L × W × D**, usually as *inside* dimensions. L is the longer dimension of the opening (the front-panel width), W the shorter (the side-panel width), D the depth between the open ends. HLP Klearfold's STE sheet reads "Inside Dimensions 4" × 2" × 5"" with L = 4" front, W = 2" side, D = 5" height. CCL Healthcare writes L × W × H with the same meaning. One search excerpt adds "all dimensions ... measured from center of score" [S Fortis]. | [C] Klearfold p.1, CCL blog |
| D4 | **Naming collision in our code.** Our `width_mm × depth_mm × height_mm` is ECMA **A × B × H** and US **L × W × D**. Our "depth" is a printer's "width" (W, B), and our "height" is a printer's "depth" (D). Any message to a printer must translate. | [X] from D2/D3 and `validators/schema.py:81-83` |
| D5 | **Inside, score-to-score and outside.** The crease sits on the board's mid-plane, so each wall takes t/2 off the inside and adds t/2 outside: **inside ≈ score-to-score − t, outside ≈ score-to-score + t, outside − inside = 2t**. ArtiosCAD models the same thing as "inside loss / outside gain = ½ caliper" [S, Esko guide excerpt]. Pacdora's figures, as recorded in our own repo doc `docs/phase2a9_ecma_ste_archetype.md` (inner 90 × 32 → mfg ≈ 90.6 × 32.6 → outer ≈ 91 × 33 at t = 0.5), agree: score-to-score ≈ inner + t (+0.1 rollover), outer = inner + 2t. | [X] geometry, supported by [S] and repo-recorded Pacdora numbers |

## 2. The three styles: topology and ECMA codes

How ECMA codes Group A ("long-seam-glued folding cartons with rectangular surfaces"), ECMA p.17:

- 1st 2-digit group: bottom closure type.
- 2nd group: top closure type (20 = "tuck in flap closure system"; 60 = "automatic (2P glued) closure").
- 3rd group: the panel the bottom tuck (last-closing flap) hangs from.
- 4th group: the panel the top tuck hangs from.
- **Panels are numbered 1 to 4 from the glue seam.** The drawings (ECMA p.24–25, 29) show panel 1 is the A-wide panel the glue flap hinges on. Then come panel 2 (B), panel 3 (A) and panel 4 (B), whose right edge is free.

| # | Style | ECMA code(s) | Topology (which panel carries what) | Grade / source |
|---|---|---|---|---|
| S1 | **Straight Tuck End (STE)**, US "Airplane Straight Tuck End (ASTE)" | **A20.20.01.01** (both tucks on panel 1; old ECMA code **A2320**). Also **A20.20.03.03** (both on panel 3; old **A2420**). Old codes from the ECMA conversion table, p.101. | **Both tucks hang from the SAME main panel**, so both closures fold the same way. Dust flaps hang top and bottom from the two B panels (2 and 4). | [P] ECMA p.17, p.24/25, p.101; [C] Klearfold ("both top and bottom panels ... hinge off the carton's front panel"); [C] Lewisburg ("Both closure tucks from the rear to the front"); [C] MOD-PAC ("Top and bottom tuck panels are positioned on the same side of the carton") |
| S2 | **Reverse Tuck End (RTE)**, US "French Reverse Tuck End (FRTE)" | **A20.20.03.01** (bottom tuck on panel 3, top on panel 1; old **A2120**) and **A20.20.01.03** (bottom on 1, top on 3; old **A2220**) | **Top and bottom tucks hang from OPPOSITE main panels**, so the two closures fold in opposite directions. Dust flaps sit on panels 2 and 4. | [P] ECMA p.17, p.24/25, p.101; [C] Lewisburg ("The top closure tucks from the front to the rear, and the bottom closure tucks from the rear to the front"); [C] MOD-PAC ("Top tuck panel folds from back to front, while the bottom panel folds from front to back"); [C] JohnsByrne |
| S3 | **Tuck top, auto-lock (crash-lock / "Hymes") bottom** | **A60.20.00.03** (old **A6020**): automatic, 2-point-glued bottom; top tuck on **panel 3**. The bottom's panel group is "00" because no single panel carries it. | Top: tuck lid on panel 3 plus dust flaps on 2 and 4. Bottom: four flaps, one on each body panel. The A flaps (panels 1 and 3) are the large hook flaps, each with a **diagonal glue crease** from the panel-2/4 corner and a **stepped lock notch** on the bottom edge. The B flaps (panels 2 and 4) are smaller, with a 45° edge. The flaps are glued at two points by the converter, so the bottom erects automatically when the tube is squared. | [P] ECMA p.29 drawing; [C] Lewisburg ("Tuck Top Auto-Bottom (Hymes) ... glued on the bottom by the folding cartons manufacturer"); [C] Klearfold p.2 ("Bottom panels are pre-glued during the carton's manufacturing process"; labels "Glue Tab", "Glue Dot") |

| # | Rule | Grade / source |
|---|---|---|
| S4 | **Which main panel is "front" is a matter of convention.** Klearfold (interior view) hangs both STE tucks off the *front* panel, folding "from the front and tuck to the rear, providing a clean front panel appearance". Lewisburg and the search-indexed Fortis sheet describe the airplane STE as folding "from the rear to the front". ECMA avoids the words front and back and writes the panel number (01.01 vs 03.03). **What is invariant: STE = one panel carries both tucks; RTE = opposite panels.** | [C] Klearfold, Lewisburg; [P] ECMA |
| S5 | **Panel order in the flat.** Seen from the print side with the glue flap on the left: **glue flap \| panel 1 (A) \| panel 2 (B) \| panel 3 (A) \| panel 4 (B, free edge)**. Klearfold's interior view reads Glue Flap \| Back \| Side \| Front \| Side. pack.ly letters it C (glue) / A1 back / B1 / A2 front / B2. **The glue flap hangs from a main (A) panel. The manufacturer's joint sits at a rear corner** (Lewisburg: ASTE "glue joint is in the right rear corner"; FRTE "in the left rear corner"), so the front panel is unbroken. | [P] ECMA drawings; [C] Klearfold, pack.ly, Lewisburg |
| S6 | **The glued joint.** The glue flap (on panel 1) laps under the free edge of panel 4 and is glued to panel 4's inside face. Glue goes on the glue flap's **print side**, which therefore stays free of ink and varnish (see G4). Lewisburg's rule legend separates "PrintSide GlueArea" from "Inside GlueArea", so dielines must say which face carries glue. | [C] Lewisburg legend, PaperWorks; [X] for "laps inside panel 4" (standard long-seam practice; no source I read states it word for word) |
| S7 | **RTE vs STE in use.** RTE is commonly said to nest better on the press sheet (cheaper to run). STE keeps both closures on one panel, which suits windows: one converter says STE avoids "interference between the tuck and the window film, a common problem with reverse tuck". | [S] search summaries of converter pages (Accord Carton). Not used for any geometry rule. |

## 3. Board-caliper allowances (thickness compensation)

**Finding: no authoritative numeric allowance table is published.** ECMA gives none (p.4). Converters apply
measured allowances inside their CAD standards. Below is everything I could establish, then a worked comparison.

| # | Rule | Grade / source |
|---|---|---|
| T1 | Panel sizes on the die are **score-to-score** and differ from inside dimensions by the caliper (D1, D5). | [P] ECMA p.6; [X] |
| T2 | **The panel opposite the glue flap (the free-edge B panel, panel 4) is sized by the thickness compensation**, so the joint closes square over the glue flap's extra ply. | [C] pack.ly ("the size of the right side panel, positioned opposite the glue flap, is determined by the thickness compensation (thickness offset)") |
| T3 | **The main panels that carry the closures get an extra offset** "to allow the top and bottom flaps to overlap the box walls and inner flaps". The tuck lid closes on top of the dust flaps (one extra ply, t), so **its hinge crease sits about t further out than the dust-flap hinge creases**. | [C] pack.ly (qualitative); [G] DDR68 (`y_top_t = y_top + S`, `y_bot_t = y_bot − S`: the tuck-panel creases are offset by t, so the tuck panel measures H + 2t crease-to-crease while the dust-flap panels measure H) |
| T4 | **The tuck (closure) panel is a little narrower than its body panel, and the tongue is set back**: "Slit Lock Tuck / Closure Panel Width Reduction: 1/32" or board thickness" and "Slit Lock Tuck / Tuck Setback: 1/32" or board thickness" (≈0.8 mm or t). | [S] Fortis "How to Measure a Folding Carton" (search excerpt; the PDF now returns 404) |
| T5 | **Rollover allowance.** Dominant (display) panels carry a rollover allowance for the width of the fold and minor die shift: **0.6 mm for board ≤ 600 µm, 0.8 mm above** (graphics registration to the panel; not a structural panel size). | [C] PaperWorks spec guide p.4 |
| T6 | **DDR68 scheme** (open-source Rhino generator; inputs are *outside* dims L, P, A and caliper S): panel 1 = L − S, panel 2 = P (crease to crease, including an S-wide relief strip at the panel 2/3 crease), panel 3 = L, panel 4 = P − S to the free edge. Glue crease shortened by S at each end. Tuck-panel creases offset ±S. Lid face = P − 2S (= inside depth). | [G] DDR68 `ECMA_A20_20_01_01.py:110-123` |
| T7 | **Proposed baseline** for a converter to confirm. Input **inside** dims A_i × B_i × H_i and caliper t, then: body panels score-to-score = inside + t; panel 4 (free edge) = B_i + t minus about t/2–t for the glue-flap ply; dust-flap hinge creases H_i + t apart; tuck-lid hinge creases about t further out at each end; lid depth crease-to-fold ≈ B_i + t; tongue width = A − 2·(t…0.8 mm) (T4). | [X] from D5, T2–T4, T6 |

**Worked comparison.** Target inside 42 × 32 × 140 mm, t = 0.35 mm, glue flap 10 mm. The engine rows were run
read-only with `PYTHONDONTWRITEBYTECODE`, dimensions entered as the engine's "manufacture" W × D × H.

- The dimension gate sends `thickness_compensation` **checked by default** (`static/js/gates.js:348-349, 370`), so the comp-on row is what a gate-confirmed design gets.
- A caller that omits the key gets comp off (`schema.py:108`, `dieline_agent.py:389-391`).

| Rule set | Panel 1 | Panel 2 | Panel 3 | Panel 4 (to edge) | Tuck-lid crease offset | Lid depth (crease→fold) | Tongue |
|---|---|---|---|---|---|---|---|
| Half-caliper baseline T7 [X] | 42.35 | 32.35 | 42.35 | ≈ 32.0–32.2 | +0.35 each end | ≈ 32.35 | house value (§4) |
| DDR68 / our `ecma_ste.py` [G] | 42.35 | 32.70 (incl. 0.35 relief) | 42.70 | 32.35 | +0.35 each end | 32.00 (= B_i) | 18.0 |
| `engine.py` v1.3, comp on (gate default) | 42.70 (back +2t) | 32.35 | 42.00 | 32.35 | **0** | 32.35 | 15.65 |
| `engine.py` v1.3, comp off (key absent) | 42.00 | 32.00 | 42.00 | 32.00 | **0** | 32.00 | 16.0 |

Gaps against the baseline:

- With comp on, the engine adds **2t to panel 1 and nothing to panel 3**. Both other schemes treat the two A panels within t of each other.
- With comp off, every panel is t small.
- No rule set except DDR68 offsets the lid crease.

**Corroboration from measured generator dies.** A sibling agent downloaded Box Blanks STE and RTE dies for
22 × 22 × 105 at t = 0.45 (licensed for any use) and measured them; see `REFERENCES.md` §3a in this directory.
That is a generator default [G], measured by that agent, not by me. It agrees with this file on:

- **T7:** creases = inside + t on every panel and on the height.
- **T4:** lid and dust-flap cut widths = panel − t (inset t/2 each side, a t slot between adjacent flaps).
- **K3:** lid depth = the side panel's crease width.
- **K4:** **tongue = max(8, 0.26 × lid depth)**.
- **F2:** dust depth = min(W − t, L/2 − 1).
- **F3:** dust flap straight on the lid side, with a 45° shoulder plus taper toward the panel the lid lands on.
- **G2/G3:** glue flap 12 mm with an ≈ 18° end taper.

It differs on two points: **no slit locks** (a V-nick friction shoulder at the tongue root instead) and no thumb notch.
Its STE puts both lids on panel 1; its RTE puts them on panels 1 and 3 (S1/S2).
- Even the open-source scheme puts panel 3 0.35 mm *larger* than panel 1. The "right" allowance is disputed, so a printer's CAD standard or a physical sample must settle it.

## 4. Tuck flap (lid + tongue)

| # | Rule | Grade / source |
|---|---|---|
| K1 | The **lid** (closure panel) hangs from the tuck panel's top or bottom crease and **spans the opening's depth B**. Its far edge is the **tuck fold** (a crease), past which the **tongue** (tuck lip) slides down inside the opposite main panel. | [P] ECMA drawings p.24–25 (lid crease → tuck-fold crease ≈ B); [C] Klearfold ("Top Panel" + "Top Tuck Flap") |
| K2 | **Lid width = the tuck panel's width A, flush with its side creases** (less the T4 width reduction). | [P/D] ECMA drawings; [S] T4 |
| K3 | **Lid depth crease-to-fold ≈ B** (inside depth plus about t, so the fold lands on the far wall's outer edge). | [D] ECMA p.24: lid ≈ 0.97 B; [G] DDR68 lid face = P − 2S; [X] |
| K4 | **Tongue length.** No published standard value. The evidence splits into two families.<br>**Proportional (≈ 0.23–0.30 B):**<br>• ECMA generic drawings ≈ 0.25–0.30 B [D].<br>• Klearfold 4×2×5" sheet: tongue ≈ 0.5" = **12.7 mm at B = 50.8 mm (≈ 0.25 B)** [D, from the drawing's labelled overall sizes: 10" = 5" + 2 × (2" lid + 0.5" tongue)].<br>• **The owner's own professional reference file**, as measured in our repo (DECISION-016, `SLIMMING_CREAM_R-108-A.ai`, a square 28 × 28 section): tuck total = 1.227 × 28 = 34.4 mm. With the lid = B = 28, the **tongue ≈ 6.4 mm (0.227 B)**, and its shoulders span 6.1 mm down by 6.4 mm across. The whole tongue is two near-quarter-circle corners of r ≈ 6 mm. (This reading assumes lid = B; the square section cannot separate W from D, which DECISION-019 itself notes.)<br>**Fixed and long:**<br>• DDR68 default **18 mm** [G].<br>• diecuttemplates "top tuck flap 0.5 in" (12.7 mm) [S].<br>• Our engine **16 mm** (v1.2+). The 16 mm was recorded as an *assumption* in DECISION-019, not a measurement.<br>**Proposed rule:** tongue = clamp(0.25·B, 8, 20) mm, shorter than about H/3 and clear of the product's shoulder. Confirm against one more professional die at a non-square section. | [D][G][X], plus our repo's measurement |
| K5 | **Tongue shape.** Both outer corners strongly rounded, with radius ≈ the tongue length. ECMA draws it that way, and the owner's reference file measures shoulder ≈ 6.1 × 6.4 mm on a 6.4 mm tongue. Klearfold draws angled-and-rounded corners. The tongue narrows toward its free edge so it enters between the wall and the product. svg.design exposes "tuck-in tab corners" from straight (0%) to fully rounded (100%), default 60%. **Corner size follows the tongue length, not the carton width.** | [D] ECMA; DECISION-016 measurement; [C] Klearfold; [G] svg.design |
| K6 | **Lock slits ("notch locks", "slit lock", "safety locks").** "**Slit locks generally consist of slits cut in the fold line of the closure flap**". The minor (dust) flaps fold first, the closure flap folds over them and tucks in, and "the slit locks interlock with the minor flaps" [patent US 2004/0031843 A1, background]. MOD-PAC calls the same thing "dust flap shoulders and tuck panel slits that interlock". Placement: **at both ends of the tuck-fold crease**, where the crease stops short of the lid edges and the ends are cut. ECMA draws a short cut tick at each end of every tuck-fold crease (p.24/25/29); Klearfold labels them "Notch Locks". Size: pack.ly says "the dimensions of the safety locks depend strictly on the size of the box and the thickness of the material"; DDR68 cuts 7 mm along the fold from each edge plus 2.5 mm across it. **Friction-only lids** (no slits) are the other recognised option: Boxshot offers "Tuck Lock: Slit / Frictional", and cosmetics often use slit lock at the bottom and friction at the top (pack.ly "open/close"). **Terminology clash:** MOD-PAC uses "friction lock" for the slit + shoulder lock, while Boxshot and others use "friction" for no slits. Name the geometry, not the term. | [P/D] ECMA; [C] patent, MOD-PAC, Klearfold, pack.ly; [G] DDR68, Boxshot |
| K7 | **No source shows a hole or slot in the tongue itself.** A "friction slit" stadium cut near the tongue tip appears in no standard, converter sheet or generator I found. | absence across [P][C][G] (stated as a search result, not proof) |

## 5. Dust flaps

| # | Rule | Grade / source |
|---|---|---|
| F1 | One dust flap hangs from **each B panel (2 and 4) at each end**, hinged on the body crease. Dust flaps fold first, then the lid closes over them. | [P] ECMA p.7 (H "between the flaps which are closed first") + drawings; [C] Klearfold "Minor Flap" |
| F2 | **Length** (hinge to tip): ECMA drawings ≈ **0.62–0.66 B** [D]; Klearfold ≈ 0.6 B [D]; DDR68 = (P + hook − S)/2, capped at A/2 [G]; diecuttemplates "dust flap 1.5 in" [S]. **Constraints:** each flap shorter than A/2 so the two do not collide; shorter than the lid depth, so the lid covers them and the tongue clears them. | [D][G][X] |
| F3 | **Shape is asymmetric.** The edge on the lid-hinge side is straight (flush with the tuck panel's lid edge). The edge on the side where the tongue enters (toward the panel the tongue tucks behind) carries a small **45° shoulder notch at the base** (ECMA ≈ 0.07–0.08 B deep, beginning ≈ 0.07 B above the hinge), then a **taper of about 15° from the hinge normal** to the tip. Outer corners rounded. Klearfold labels the base step "Minor Flap Shoulder". The shoulder is what the lid's lock slit catches. | [D] ECMA p.24/25 (identical in A20.20.01.01, A20.20.03.01, A60.20.00.03); [C] Klearfold |
| F4 | Taper and rounding make the flap guide the tongue and clear it. svg.design: "Flaps always taper in slightly toward the top". | [G] svg.design; [D] ECMA |

## 6. Glue flap (manufacturer's joint)

| # | Rule | Grade / source |
|---|---|---|
| G1 | Hangs from the **free edge of panel 1** across the full body height H. Its crease runs the body height only, shortened about t at each end in DDR68. | [P] ECMA drawings; [G] DDR68 |
| G2 | **Width**: Klearfold 4×2×5" sheet ≈ **0.5" = 12.7 mm** [D, from 12.5" = 2 × (4" + 2") + 0.5"]; DDR68 default **18 mm** [G]; search excerpts "0.625–0.75 in (16–19 mm)" and "10–15 mm" [S, unverified]. **Hard constraint:** the glue flap must stay clear of the panel 3/4 crease once folded. DDR68 refuses B < glue + 3 mm. **Proposed:** 12–15 mm standard, never above B − 3 mm, never below about 8 mm on small cosmetic cartons. | [D][G][X] |
| G3 | **Ends tapered.** ECMA draws a shallow taper of ≈ **15°** (relative to the horizontal crease) from each crease end to the free edge. Our engine instead cuts a 45° chamfer at the free edge only. | [D] ECMA p.24/25/29 |
| G4 | **Glue area free of ink and coating**: "Glue Areas must be free of any ink or coating" [C PaperWorks]; Lewisburg's legend marks "PrintSide GlueArea", "Inside GlueArea" and "Print Side UV Knockouts" [C]; pack.ly's glue area "generally must not contain printed elements" [C]. **But bleed runs 6.35 mm (¼") over the score onto the glue flap** so no white shows at the joint [C PaperWorks]. Knock out the rest of the flap's glue zone. | [C] |

## 7. Thumb notch

| # | Rule | Grade / source |
|---|---|---|
| N1 | A half-round (half-moon) cut, **centred on the top edge of the panel the tongue tucks behind**, so a thumb can reach the lid. svg.design: "Diameter of the half-circle cut on the front top edge"; PakFactory: "Added to tuck top designs"; Boxshot's ECMA A20.20.03.01 offers "Thumb Cut" as a top or bottom feature with its own width parameter. | [G] svg.design, Boxshot; [C] PakFactory |
| N2 | **Size: not established.** No source I read gives a standard diameter. | — |

## 8. Lines: cut, crease, perforation, partial cut

| # | Rule | Grade / source |
|---|---|---|
| L1 | **ECMA drawing symbols:** CL solid = "contours of erected boxes or cutting lines of blanks"; FL dashed = "crease or folding line"; PL dotted = "perforation line". Fibre direction is drawn as an MD (machine-direction) or CD arrow pattern. | [P] ECMA p.6 |
| L2 | **Converter rule legend** (Lewisburg/LPC design spec sheet): Knife, Crease, Reverse Crease, Partial Cut, Perforation, Final Trim Size, Bleed, Type Safety, Chip Position, Print-Side Glue Area, Inside Glue Area, Print-Side Hand Glue Area, Inside Hand Glue Area, Print-Side UV Knockouts. The spec block also carries "Board", "Grain Dir", "Side shown", carton size, blank size and total rule length. | [C] Lewisburg p.2 |
| L3 | **A crease never runs over a cut edge, and crease ends stop at cuts.** Where a crease meets a lock slit, the crease is shortened and the slit cut takes over (ECMA's tuck folds; DDR68 "fold crease spans only the middle"). | [P/D] ECMA; [G] DDR68 |
| L4 | **Fold toward the bead.** In carton creasing the bead faces inward into the fold, so "creasing should therefore be done with the print side up". Folding the wrong way turns the crease inside-out. | [P] Iggesund Graphics Handbook p.25, p.39–40 |
| L5 | **Nicks.** Blanks stay attached to the skeleton by nicks. "Nicks in the machine direction ... are twice as strong as those in the cross-fibre direction." Nick placement is the die-maker's job; do not draw nicks in a design dieline unless the converter asks. | [P] Iggesund p.37–38; [X] |
| L6 | **Creasing tool.** The crease forms where the creasing rule pushes board into a matrix groove. Crease width and depth follow board thickness ("the thickness is the most important variable"). Thick board needs double creasing or scoring. | [P] Iggesund p.24–25, 38–39 |

## 9. Bleed, safe area, die registration

| # | Rule | Grade / source |
|---|---|---|
| B1 | **Bleed 3 mm past every knife cut (⅛")**: PaperWorks 3.2 mm, GLBC ⅛", Sttark 3.175 mm. **On the glue flap the bleed runs 6.35 mm over its score.** | [C] |
| B2 | **Safe area / type safety:** PaperWorks **2 mm** from crease and trim; GLBC **⅛" (3.2 mm)** from any score, hole or window and from the dieline edge; Sttark **6.35 mm**. **Range 2–6.35 mm.** 3 mm is the common middle; our default of 4 mm sits inside the range. | [C] |
| B3 | **Die-cut registration tolerance** (print to cut): GLBC "+/- 1/16" and 1/8"" (±1.6–3.2 mm). This is why the safe area exists. Panel alignment within about ±0.5 mm is also quoted [S]. | [C] GLBC; [S] |

## 10. The dieline file printers expect

| # | Rule | Grade / source |
|---|---|---|
| E1 | The dieline sits on **its own layer**, drawn in a **separate, overprinting spot colour**. All descriptor text on the original dieline stays in the file. | [C] PaperWorks p.4 ("utilize a separate (overprinting) spot dieline color. This should be placed on a separate layer") |
| E2 | **Spot colour names, tints and line colours vary by printer. There is no single colour standard.**<br>Read first-hand:<br>• The Print Remedy: a layer named "Dieline", a spot swatch named "Dieline", stroke 1 pt, fill none, "tick Overprint Stroke", artwork on layers below.<br>• Willowpack: "a separate top layer named 'Dieline' using a spot color ... Set it to 'Overprint'".<br>• packagingtools.io (a generator): **red solid = cut, blue dashed = fold**, green bleed, orange safe, purple glue, as DXF layers CUT/FOLD/BLEED/SAFE/GLUE.<br>From search summaries: knife "CutContour"/"Die Cut" 100% magenta solid; "Crease" 100% cyan dashed [S].<br>**Consistent across all of them:** cut solid, crease dashed (as ECMA L1); die lines on their own layer, in a named spot colour, set to overprint. | [C] The Print Remedy, Willowpack (both label printers); [G] packagingtools.io; [S] |
| E3 | Layers or marks a converter expects: knife, crease, reverse crease, partial cut, perforation, bleed, type safety, glue areas (print side / inside), varnish-free and UV knock-outs, **grain direction**, board, side shown (print side or inside). | [C] Lewisburg legend; [C] PaperWorks ("Wax or Varnish Free Area ... must be identified on digital dieline") |
| E4 | Deliver the PDF and native file 1:1. LPC sends "PDF & EPS (Files will be identical & 1:1 ratio)". | [C] Lewisburg |

## 11. Grain (fibre) direction

| # | Rule | Grade / source |
|---|---|---|
| R1 | **Mark it on the dieline** (ECMA defines the symbol; LPC's spec block has a "Grain Dir" field). | [P] ECMA p.6; [C] Lewisburg |
| R2 | "**A crease parallel to the fibre direction is always best.**" It is easier to make a perfect crease along MD, and closely spaced creases should run along MD. | [P] Iggesund p.38 |
| R3 | **For tube (tuck-end) cartons, sources disagree** on whether the grain should run with the height (parallel to the four body creases, so they fold easily, and the tuck and dust hinges run across the grain, which stiffens the flaps), or around the girth (panel stiffness, bulge resistance). One converter article says body grain parallel to the body creases and tuck flaps with grain perpendicular to their creases (these agree: grain runs with H) [S pmpackaging]. Lewisburg notes grain choice per style (e.g. "grain in the short direction to encourage the front panel curl" for a header sleeve). **Not settled.** Treat it as the converter's call and print it on the die. | [S][C] |

## 12. Tolerances and common failure modes

| # | Failure | What prevents it | Source |
|---|---|---|---|
| M1 | Lid does not reach, or the tongue rides up: lid shorter than the opening | Lid depth ≈ B (K3); tuck-lid crease offset t over the dust flaps (T3) | [P][C][G] |
| M2 | Tongue binds on dust flaps or the wall; lid bulges | Tongue width reduced and set back by about t (T4); dust flaps tapered and notched on the tongue side (F3) | [S][D] |
| M3 | Dust flaps collide or block the lid | Each dust flap < A/2 and < lid depth (F2) | [D][G] |
| M4 | Glue flap hits the panel 3/4 crease once folded | Glue width ≤ B − 3 mm (G2) | [G] |
| M5 | Joint not square, panel 4 short or long | Thickness offset on the panel opposite the glue flap (T2) | [C] |
| M6 | Lid pops open (friction too low) | Slit-lock ends on the tuck fold engaging the dust-flap shoulders (K6, F3) | [P][C] |
| M7 | Cracked creases | Crease along the grain where possible; fold toward the bead; crease tooling matched to caliper (R2, L4, L6) | [P] |
| M8 | Glue fails on the folder-gluer | Ink and coating knocked out on the glue area (G4) | [C] |
| M9 | White edge or art cut off | 3 mm bleed (6.35 mm on the glue flap), 2–3 mm type safety, ±1.6–3.2 mm die registration (§9) | [C] |
| M10 | A crease scored over a knife line tears the panel on the folder-gluer | Creases only where a flap actually hinges (L3) | [P] |

---

## 13. Differences between our current code and the standard

Files read: `apps/dielines/geometry/engine.py` (the production path: `straight_tuck_end_carton` at v1.3, per
`registry.py:734-737` and `pipeline/agents/dieline_agent.py:33`), `geometry/ecma_ste.py`,
`geometry/opposed_tuck.py`, `geometry/panels.py`, `docs/geometry_decisions.md`, `exporters/production_pdf.py`,
`exporters/svg_exporter.py`. Paths are relative to `/Users/symow/Desktop/bbrose-systemOS/bbrose_design_os/apps/dielines/`.

| # | Where | What our code does | What the standard says | Source |
|---|---|---|---|---|
| X1 | `geometry/engine.py:355-359`; `docs/geometry_decisions.md:38-49` (DECISION-003); `docs/MEASUREMENT_NEEDED.md` ("both active tuck flaps (top back and bottom front)") | The style named **`straight_tuck_end_carton` puts the top tuck on the back (panel 1) and the bottom tuck on the front (panel 3)**. That is ECMA **A20.20.03.01, a REVERSE tuck end**. It is the production template (`dieline_agent.py:33`, drawn at v1.3). **Our own docs say the owner's approved references have this same opposed topology** (DECISION-003: "matches the approved Pacdora-style reference layout"; the SLIMMING_CREAM file: "top back and bottom front"). So the *geometry* is probably what he approved, and the defect is the **name**. | STE = both tucks on the **same** panel (A20.20.01.01 / A2320 or A20.20.03.03 / A2420). Opposed tucks = RTE (A20.20.03.01 / A2120). **This is the owner's call, not a code fix:** either rename the style to RTE (keep the geometry he approved), or, if his briefs mean a true same-panel STE, add one. **Do not move the bottom tuck onto the back panel without his word**: that would take production away from his own reference. | ECMA p.17, p.24/25, p.101; Klearfold; Lewisburg; MOD-PAC |
| X2 | `geometry/engine.py:360-367` | `reverse_tuck_end_carton` = top on front (panel 3), bottom on back (panel 1) = **A20.20.01.03**, also an RTE. **The generic engine therefore offers no same-panel STE.** Its two styles are the same topology mirrored; the comment "Mirror of the STE column assignment" states it. | RTE = opposite panels; STE = same panel. Only `ecma_ste.py` (non-production) draws a true STE. | ECMA p.17 |
| X3 | `geometry/opposed_tuck.py:9-17, 101-119` | Records that the first archetype (`ecma_ste.py`, both tucks on one panel, a correct STE) was judged a "TOPOLOGY MISMATCH" against a Pacdora reference that "visibly opposes" the tucks, and builds an opposed-tuck (RTE) die to match. | The Pacdora reference was an **RTE**. It was never evidence that an STE should have opposed tucks. `ecma_ste.py`'s topology (`derived` "top_tuck_panel"/"bottom_tuck_panel" both "back", lines 443) is the correct STE. | ECMA p.17, p.24 |
| X4 | `geometry/engine.py:368-374` | Tuck-top auto-bottom puts the top tuck on the back (panel 1). | ECMA catalogues **A60.20.00.03**: top tuck on **panel 3**. Panel 1 is not wrong in itself, but it is not the catalogued style. | ECMA p.29 |
| X5 | `geometry/engine.py:408, 582, 895-906` | Auto-lock bottom = four **plain trapezoids**, depth min(W, D) × 0.75: no hook, no lock notch, no glue crease or glue points. | A crash-lock bottom is a two-point-glued 4-flap lock: A flaps with diagonal glue creases and stepped lock notches, B flaps with 45° edges, glued by the converter. The current shape cannot lock. | ECMA p.29; Lewisburg; Klearfold p.2 |
| X6 | `geometry/engine.py:35-47` (docstring), `:619-627` | Calls back = W + 2t, sides = D + t, front = W "the standard folding-carton (ECMA) allowance rule". | **ECMA publishes no allowance rule** (p.4: generic, not a construction manual). The only published hints: thickness offset on the panel opposite the glue flap (pack.ly), offset on the closure panels (pack.ly), DDR68's scheme (§3 T6). The engine's rule matches none of them (§3 table: panel 3 is 0.35–0.70 mm smaller than DDR68). | ECMA p.4; pack.ly; DDR68 |
| X7 | `static/js/gates.js:348-349, 370`; `validators/schema.py:108`; `pipeline/agents/dieline_agent.py:389-391`; `pipeline/views.py:1215` | The dimension gate sends `thickness_compensation` **checked by default**, so gate-confirmed dies get the X6 scheme. Any caller that omits the key gets **False**: zero caliper allowance and zero lock notch (`engine.py:620, 627`). The schema comment calls False the "legacy" layout. | Every converter compensates for caliper (§3). Without it, inside dimensions come out about t smaller than intended and the joint is out of square. Compensation should not be optional for production dies. | pack.ly; DDR68; D5 |
| X8 | `geometry/engine.py:44-47, 963-971`; `_hinge_creases` `:506-553` | "Vertical (height) allowances are intentionally NOT applied". The tuck-lid hinge crease and the dust-flap hinge creases sit on the **same line** (y1 / y2). | The closure panels get an extra offset so the lid closes **over** the dust flaps: lid crease about t further out (DDR68 offsets the tuck-panel crease by t; pack.ly states the offset). | pack.ly; DDR68 |
| X9 | `geometry/engine.py:1000-1012` | inner = manufacture − 2t and outer = manufacture + 2t, so **outer − inner = 4t**. | Walls are one caliper thick: outer − inner = 2t (score-to-score ± t when the crease sits on the mid-plane). Pacdora's numbers in our own doc give outer − inner = 2t. | D5; `docs/phase2a9_ecma_ste_archetype.md` table |
| X10 | `geometry/engine.py:403, 428-434`; `:239-241` | An **unpinned** caller still gets **v1.1**: tuck total = **W × 1.227**, so the lid depth follows the *front width*, not the opening depth. For a non-square section the lid does not span the opening (DECISION-019 admits this). Production pins 1.3; anything that does not pin gets 1.1. | Lid depth ≈ B, the opening depth (K1, K3). | ECMA drawings; DECISION-019 itself |
| X11 | `geometry/engine.py:812-818, 830-836`; DECISION-010/012 (`geometry_decisions.md:78-115`); `:246, 254-256` | A **stadium "friction slit" hole is cut in the tongue**, 3 mm from its tip, W × 0.327 wide (≥ 5 mm), 1.5 mm high. | **No standard, converter sheet or generator I read shows a hole in the tongue.** The recognised locks are the **slit-lock cuts at the ends of the tuck fold** (K6) or plain friction. The Box Blanks dies a sibling agent measured have neither slits nor holes, only a V-nick at the tongue root. **But our repo says the owner's reference has tongue slits**: DECISION-012 says they "match the reference geometry", and MEASUREMENT_NEEDED.md asks for their extremes in the file. Note the position: the slit sits 3–4.5 mm from the tip on what the DECISION-016 ratios read as a ≈ 6.4 mm tongue, right where a **tuck fold with lock slits** would be. It may be a misread fold-line slit lock. **Verify against `SLIMMING_CREAM_R-108-A.ai` before keeping or removing it**; that file was not found (§14). | absence across ECMA, Klearfold, Lewisburg, pack.ly, DDR68, Boxshot; set against DECISION-012 / MEASUREMENT_NEEDED |
| X12 | `geometry/engine.py:280-282, 976-987` (v1.3) | Lock slits = cuts **along the tuck fold** from each lid edge, 15% of the tuck width clamped to **2–4 mm**, with no hook across the fold. | ECMA draws a short cut plus a tick at each fold end; DDR68 uses 7 mm along plus 2.5 mm across; Klearfold "notch locks"; pack.ly says lock size depends on box size and caliper. Our 2–4 mm is short against DDR68's 7 mm, and the slit has no catch geometry. **The engine's slit and the dust-flap shoulder are not designed as a pair** (the dust notch is a fixed 3 mm, `:243`). | ECMA p.24/25; DDR68; pack.ly |
| X13 | `geometry/engine.py:242, 847-850` | Dust flap height = D × 0.631 (DECISION-016, measured from one professional file). | Agrees with the generic drawings: ECMA ≈ 0.62–0.66 B, Klearfold ≈ 0.6 B. **Consistent.** | [D] ECMA, Klearfold |
| X14 | `geometry/engine.py:243-245, 859-872` | Dust flap **symmetric**: a 3 mm 45° base notch on *both* sides, a 6 mm top chamfer on both sides. | ECMA draws **asymmetric** flaps: straight on the lid-hinge side, shoulder notch plus ~15° taper only on the side where the tongue enters. Klearfold likewise ("Minor Flap Shoulder"). The symmetric notch takes material from the lid-hinge side, where the lid needs support. | ECMA p.24/25/29; Klearfold |
| X15 | `geometry/engine.py:240-241, 432, 719-753` | The **tongue is the full panel width W** down to the shoulder curve, and the lid edges are flush with no width reduction. v1.2/1.3 keep the shoulder **inset at W × 0.227** (9.5 mm per side at W = 42, 20.4 mm at W = 90) over a curve height of only 8 mm, so wide cartons get a flat, wide shoulder that narrows the tongue tip to 0.55 W. | Closure panel width reduced and tongue set back by about 1/32" or t (T4, unverified excerpt). Tongue corners near quarter-circles of radius ≈ the tongue length (ECMA; the owner's reference file measures 6.1 × 6.4 mm on a 6.4 mm tongue). The 0.227 factor was measured on a **square** carton, where 0.227·W also equals 0.227·B, the tongue length. It most likely describes the **tongue's corner**, not a fraction of the width. | [S] Fortis; [D] ECMA; DECISION-016 |
| X16 | `geometry/engine.py:415-416, 977-981` (v1.3) | Tongue = **16 mm − t, fixed** for every size; the 16 mm lip is an assumption carried from DECISION-019 (Skynte). | No standard value. Proportional evidence ≈ 0.23–0.30 B: ECMA, Klearfold, and **the owner's own reference file (≈ 6.4 mm at B = 28)**. DDR68 uses 18 mm. At B = 28 the engine's tongue is about 2.5 × the professional reference's. **Proposed:** clamp(0.25·B, 8, 20), then confirm on one professional die with B ≠ A. | [D][G][X]; DECISION-016 |
| X17 | `geometry/engine.py:257-258, 584, 662-667` | Glue flap: 45° corner cut of min(0.3 G, 4 mm) **at the free edge only**. The flap runs the full body height from the crease ends (no taper starting at the crease, no crease shortening). Default width 10 mm (`constants.py`), schema range 6–15. | ECMA tapers each end about 15° from the crease end. DDR68 shortens the glue crease by t. Width evidence 12.7 mm (Klearfold) to 18 mm (DDR68); 10 mm is at the narrow end and 6 mm is below anything found. | ECMA; Klearfold; DDR68 |
| X18 | `geometry/engine.py:283-285, 651-658` | Thumb notch: half-round, centred on the top edge of the panel the lid closes onto, r = min(9, 0.22 × panel width). | Placement **matches** (N1). Size: no standard found. | svg.design, PakFactory, Boxshot |
| X19 | `docs/geometry_decisions.md:70-76` (DECISION-006); `exporters/svg_exporter.py:4-7, 128-178` | SVG and preview: cut **blue #0000FF**, crease **red #FF0000**, bleed and safe green, called "industry-standard ... non-negotiable". | **No colour is the industry standard.** One generator uses the exact opposite (red cut, blue fold: packagingtools.io), and printer guides use magenta/cyan spots or a single "Dieline" spot. The production PDF itself uses magenta CutContour and cyan Crease (`production_pdf.py:64-65`). Two schemes in one system confuse a printer. Make the SVG/AI match the PDF, name the spots, and keep the line *styles* (solid cut, dashed crease), which are the only universal rule. | [P] ECMA p.6 (line styles); [C] PaperWorks, The Print Remedy, Willowpack; [G] packagingtools.io |
| X20 | `exporters/production_pdf.py:64-65, 378-392` | CutContour and Crease are real spot separations on named layers (good). **No overprint is set** on the die strokes (no `setStrokeOverprint` anywhere in `exporters/`). Line widths 0.5 pt cut, 0.4 pt crease (`:164-167`). | Dieline in a **separate overprinting spot colour on its own layer** (PaperWorks). Without overprint, a die line placed over artwork knocks out the art on press if the die plate is ever imaged. | [C] PaperWorks p.4 |
| X21 | `exporters/` (all), `geometry/` (all) | **No grain-direction mark** and no "side shown" (print side / inside) note on any output (`grep -i grain` finds none). | ECMA defines the fibre-direction symbol; converters print "Grain Dir" and "Side shown" in the spec block. | ECMA p.6; Lewisburg |
| X22 | `geometry/engine.py:945-950`; DECISION-009 | Safe area = one rectangle over the body only, inset 4 mm. No safe zone on lid, tongue or flaps; no separate bleed rule for the glue flap. | Bleed 3 mm past cuts but **6.35 mm over the score on the glue flap**, with the glue area itself knocked out. Type safety 2–3.2 mm from *every* crease and cut, flaps included. | [C] PaperWorks, GLBC |
| X23 | `geometry/ecma_ste.py:130, 143-144`; `opposed_tuck.py:139` | Correct STE topology (both tucks on back) and DDR68's caliper scheme. Hook 18 mm and slit 7 × 2.5 mm are taken from DDR68's defaults; the glue flap uses our schema's 10 mm while DDR68's default is 18. | Topology matches ECMA A20.20.01.01. The numbers are one open-source author's defaults, not a standard (see K4, K6, G2). | DDR68 source |
| X25 | `geometry/engine.py:49-52, 624-627, 723-749`; DECISION-015 (`geometry_decisions.md:166-177`) | With comp on (the gate default), a **2t × 2t square notch is cut at each corner of the lid's HINGE** (where the lid meets the body), and the hinge crease is shortened by 2t each end. | The recognised "notch locks" sit at the **tuck FOLD** (lid to tongue), not at the lid hinge (ECMA p.24/25/29 ticks; Klearfold "Notch Locks" label at the tuck fold). ECMA and Klearfold draw no notch at the lid-hinge corners: the dust flap's base shoulder gives the clearance there. DDR68 has only a small diagonal relief at one hinge corner. The hinge notch is not a standard feature. Confirm with a converter or remove it. | ECMA; Klearfold; DDR68 |
| X24 | `geometry/panels.py` (all) | A plain rectangle record (name, x, y, w, h). It carries no panel number or ECMA role. | ECMA identifies flaps by **panel number from the glue seam** (1–4). Adding `ecma_panel` (1–4) to `Panel` would let the code state its topology as an ECMA code and test it (e.g. assert STE ⇒ top and bottom tuck on the same panel number). | ECMA p.17 |

## 14. What I could not establish

- A **numeric** industry standard for tongue length, dust-flap length, glue-flap width, lock-slit size or
  thumb-notch size. ECMA expressly gives none; ArtiosCAD/Impact standard libraries are proprietary and were not
  readable without a login. The values above are drawing proportions, one open-source generator's defaults,
  and converter sheets.
- A published, authoritative **caliper allowance table**. The Fortis "1/32 or board thickness" reduction and
  setback is only a search excerpt (the PDF returns 404).
- **Grain direction** for tube cartons. The primary source (Iggesund) only says creases along the grain are
  best. The carton-level recommendation is contested and left to the converter.
- **Spot-colour names and stroke weights** are printer-specific. Only PaperWorks (separate overprinting spot on
  its own layer) was read first-hand.
- The Iggesund *Reference Manual* chapters "Design and carton construction", "Die-cutting and creasing" and
  "Creasability" (`www2.iggesund.com`) no longer resolve. The web archive is not reachable from this tool.
- **The owner's professional reference file `SLIMMING_CREAM_R-108-A.ai` was not found.** I ran
  `brain.material` with query "SLIMMING_CREAM": no row by that name (only semantic matches on other cream
  artwork). `find . -iname "*SLIMMING*"` under `/Users/symow/Desktop/bbrose-systemOS` found nothing. That file
  alone would settle X1 (topology), K4/X16 (tongue length, inferred here from ratios on a square section) and
  X11 (what the tongue "slit" is).
- **The gate does not say which dimensions to type.** Its fields read only "Width (mm)", "Depth (mm)",
  "Height (mm)" (`static/js/gates.js:240-243`), while the schema treats them as score-to-score "manufacture"
  dimensions (`validators/schema.py:62-66`). If the owner types inside dimensions, each panel comes out about t
  small before any allowance, and the X9 (4t) error compounds. I did not establish what he actually types.
