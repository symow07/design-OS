# Reference dielines for design 119 (tuck end, 22 × 22 × 105 mm, board 0.45 mm)

Research run 2026-10-07, time-boxed at about 2 h. Everything here is under `/Users/symow/dl_work/research/`:
- reference files: `refs/`
- their terms and hashes: `refs/TERMS.md`
- my scripts and logs: `work/`

Nothing in `/Users/symow/Desktop/bbrose-systemOS` was changed.

## 0. Bottom line

- **THE reference, for both STE and RTE: Box Blanks (boxblanks.com).**
  - It is a free parametric generator that takes the exact 22 × 22 × 105 mm and a 0.45 mm caliper.
  - It says whether those numbers are inside, crease-to-crease or outside.
  - Its terms explicitly let us use, modify and share the files, commercially included.
  - It needs no account.
  - It exports a layered DXF (CUT/CREASE).
  - Its "checked against the plate" badge is **not** a reason for the pick; see the caveats in §4.
  - Files: `refs/boxblanks_{STE,RTE}_22x22x105_{inside,crease,outside}_t0.45.{pdf,svg,dxf}`.
- **Cross-check: Die Cut Studio (diecutstudio.com).** Also free, no account, "yours to use for personal and commercial projects". It is independent of Box Blanks but hobby-oriented (it is pitched at Cricut/Silhouette/laser cutters), so it is a second opinion, not the benchmark. Files: `refs/diecutstudio_{STE,RTE}_22x22x105_{outer,inner}_t0.45.{pdf,svg,dxf}`.
- **What I could not get:** no converter's or printer's *production* die (an ArtiosCAD/Kasemake-grade file from a real converter) was obtainable free and without login. The professional platforms either require an account (diecuttemplates.com, Boxshot), forbid download without a paid licence (Pacdora), or restrict content to shopping (cefBox). Box Blanks is the strongest *independent* reference available on those terms. Do not present it as a converter's die: its own terms disclaim accuracy and ask for a cut-and-fold sample.
- **DDR68/Rhino_Packaging_Toolkit (MIT) is NOT a reference.** Our `ecma_ste.py` and `opposed_tuck.py` are adapted from it, so comparing against it would compare us with our own source. It also needs Rhino to run.

## 1. Candidates tried and terms found

| # | Candidate | Exact-size parametric? | Account / payment | Terms (quoted) | Result |
|---|---|---|---|---|---|
| 1 | **Box Blanks**, boxblanks.com (`/#/ecma-a1001-straight-tuck`, `/#/ecma-a1050-reverse-tuck`) | Yes: L/W/H in mm, caliper, inside / crease / outside | None | "Dielines you generate here, on this site, are yours to use for any purpose, including commercial work. You may modify them, share them, send them to a converter…" Forbidden: "Systematically scrape, harvest or bulk-download the catalogue by automated means", "Copy the site's code and run it as your own service". Robots: allow all | **OBTAINED** STE + RTE × inside/crease/outside × PDF/SVG/DXF (18 files) |
| 2 | **Die Cut Studio**, diecutstudio.com (`/templates/straight-tuck-end`, `/templates/reverse-tuck-end`) | Yes: L/W/H, thickness, Outer/Inner, bleed | None | "generates free in your browser — no signup and no watermark — and is yours to use for personal and commercial projects." No terms page (404). Robots: allow all, AI crawlers explicitly welcome | **OBTAINED** STE + RTE × outer/inner × PDF/SVG/DXF (12 files) |
| 3 | Pacdora (pacdora.com) | Yes | Account. Free plan has **no** AI/PDF/DXF export (pricing page) | ToS: "You may not copy, publish, link to, download, transmit, modify, adapt … or otherwise exploit any content without a license agreement with PACDORA." Robots disallow `/dielines-detail/`, `/share-dieline`, and any query string | Not downloaded (licence + paywall) |
| 4 | diecuttemplates.com (BoxesNBoxes Ltd) | Yes | **Login**: every download shows "Please log in to continue" | T&Cs: "limited, personal, non-transferable license … solely for your internal business purposes"; "Use any robot, bot, spider, scraper, or other automated means to access the Services for any purpose without our express written permission" is prohibited | Not downloaded (login) |
| 5 | Boxshot dielines (dielines.boxshot.com/make/ecma-a20200301/), ECMA-coded editor | Yes (cm, paper thickness, slit/friction lock, thumb cut) | **Login**: "Please log in to see 3D models, download artwork templates, … make dielines" | No terms seen without logging in | Not downloaded (login). It would be a strong professional candidate if the owner has an account |
| 6 | cefBox (cefbox.com/dielines/foldingBox/{straightTuckEnd,reverseTuckEnd}) | Yes (inner/outer, thickness, TFW/TFR/GFW/DFW) | Not established | Terms: "You may use the content of this site only for the purpose of shopping on this site or placing an order on this site and for no other purposes." "No materials from this site may be copied, reproduced … without cefBox.com prior written permission." | Not downloaded (terms) |
| 7 | Newprint (newprint.com/free-dieline-generator) | Yes (STE, RTE; paper weight) | No login stated | Terms of Use: "you may download or copy Content for personal use only … do not modify the material"; "It is prohibited to … use Content for public or commercial purposes without written permission"; "You agree not to use bots, spiders, robots, or other automated means to access the Website" | Not downloaded. It is personal-use only, and an agent can only fetch it by automation. **The owner could download one by hand** for a private look |
| 8 | templatemaker.nl (`/en/cardbox`, a tuck box; no STE/RTE choice) | Yes | None | Licence forbids: "Resell, redistribute, or share the templates … in any digital format", "Include the templates in software, web applications, design tools, or plugins", "Use the templates for training AI models, generating NFTs, or other automated or blockchain-based applications" | Not downloaded. Benchmarking a software generator and a digital side-by-side conflicts with these clauses |
| 9 | PackagingTools.io (`/design/dieline-generator/`) | Yes (STE, RTE, caliper, grain, bleed/safe) | Download form carries "I agree to be contacted about packaging solutions" | ToS §9: "You may generally use outputs … for legitimate commercial and personal purposes"; §3 forbids "Scrape, crawl, copy, harvest, or systematically extract Site data without permission" | Not downloaded. Getting a file means a contact-consent form, which means handing over the owner's contact details. Not done |
| 10 | Custom Packly (custompackly.com/dieline-generator) | STE only (no RTE) | None stated | Only a privacy policy; "© 2026 Custom Packly. All rights reserved." No licence for generated files. Robots `Disallow: /api/` | Not downloaded (no licence statement, no RTE) |
| 11 | BD Print (bdprint.com/free-dieline-generator/) | Yes (STE/RTE listed), PDF/AI | "no account required" | Terms page not read (time-box) | Not downloaded |
| 12 | BrandMyDispo box-template-generator | Yes | Not established | HTTP 429 (rate-limited); not retried | Not downloaded |
| 13 | packmyman.com (ECMA tuck end generator) | Yes | Not established | Vercel "Security Checkpoint" (bot challenge). **Not bypassed** | Not downloaded |
| 14 | DDR68/Rhino_Packaging_Toolkit (GitHub, MIT) | Yes (Rhino IronPython) | None | MIT | Not used as a reference: it is the source of our own STE/RTE formulas (`ecma_ste.py`, `opposed_tuck.py`, FORMULA_PROVENANCE), so it is not independent, and it needs Rhino |
| 15 | Other GitHub generators (search "dieline generator") | Varied | None | Most repos have **no licence** (all rights reserved); a few MIT hobby repos (≤ 1 star) | Not evaluated (time-box) |
| 16 | PakFactory, Packhelp | No exact-size tuck generator found | — | — | Nothing found in the time-box |

## 2. What was obtained

30 dieline files in `refs/`, plus a parameter-panel screenshot per configuration. Inputs, terms and SHA-256 are in `refs/TERMS.md`.

| Reference | STE | RTE | Modes | Formats |
|---|---|---|---|---|
| Box Blanks | ✓ | ✓ | inside, crease-to-crease, outside | PDF (1:1 page with legend), SVG (mm), DXF R12 (mm) |
| Die Cut Studio | ✓ | ✓ | outer, inner | PDF (1:1, page = die + 3.18 mm bleed), SVG (pt), DXF R12 (mm) |

The flat size agrees across the three formats to 0.001 mm in every file (SVG path extents = PDF stroke extents = DXF `$EXTMIN/$EXTMAX`), so the formats are interchangeable for measurement. The SVG/DXF are the easiest to read; the PDF is what the owner would open.

## 3. Measurements

Method: I parsed the SVG paths (Box Blanks: M/L only, already in mm; Die Cut Studio: M/L/Q, converted pt→mm ×25.4/72). I took the creases first (they give the panel grid) and then read the cut vertices against that grid. Line styles were taken from the SVG group attributes, and the PDFs were checked with PyMuPDF `get_drawings()` (colour, width, dash) plus an xref scan for `/Separation` and `/OCG`. DXFs were parsed as text: layers, ACI colours, `$INSUNITS`. Panels are numbered **from the glue flap**: panel 1 is the first full panel after the glue flap; the blank lies with the glue flap on the left and the top closure up. All values are in mm. "t" = 0.45.

### 3a. Box Blanks: STE and RTE (identical except where the lids hang)

| Feature | inside 22×22×105 | crease 22×22×105 | outside 22×22×105 |
|---|---|---|---|
| Flat (cut) size W × H | **101.80 × 166.35** | **100.00 × 165.00** | **98.20 × 163.65** |
| Panel 1 / 2 / 3 / 4, crease-to-crease | 22.45 / 22.45 / 22.45 / 22.45 | 22.00 ×4 | 21.55 ×4 |
| Body height (top to bottom body crease) | 105.45 | 105.00 | 104.55 |
| Board compensation visible | crease = inside **+ t** on every panel and the height; no per-panel difference (the glue-side panel gets no extra t) | none | crease = outside **− t**, uniform |
| Glue flap width | 12.00 | 12.00 | 12.00 |
| Glue flap crease length / free-edge length | 105.45 / 97.45 | 105.00 / 97.00 | 104.55 / 96.55 |
| Glue flap end taper | straight slant from the crease end to a point 4.00 inboard on the free edge (12 across × 4 down, about 18.4° to the end line), both ends; no radius | same | same |
| Tuck lid hinge crease (body line) | 22.00 long, stops t/2 = 0.225 short of each vertical crease | 21.55 | 21.10 |
| Tuck lid cut width | 22.00 (panel − t; inset t/2 each side) | 21.55 | 21.10 |
| **Lid depth** (hinge crease → tuck crease) | **22.45** (= the side panel's crease width) | **22.00** | **21.55** |
| Tuck (tongue) crease length | 19.36 (inset 1.32 each side) | 18.964 (inset 1.293) | 18.568 (inset 1.266) |
| **Tongue length** (tuck crease → tip) | **8.00** (rule: max(8, 0.26 × lid depth), so 8 here) | **8.00** | **8.00** |
| Friction shoulder ("nick") at the tongue root | the cut steps in 1.32 along the tuck crease, then runs diagonally back out to full lid width 2.80 above the crease: a V nick on each side; no separate slit | 1.293 × 2.80 | 1.266 × 2.80 |
| Tongue side, after the nick | straight, 3.651 | 3.683 | 3.715 |
| Tongue corners | 45° chamfers 1.549 (no radius anywhere) | 1.517 | 1.485 |
| Tongue tip edge | 18.902 | 18.516 | 18.130 |
| Slit locks | **none** | none | none |
| Dust flap cut width at root | 22.00 (panel − t) | 21.55 | 21.10 |
| **Dust flap depth** | **10.225** (rule: min(W − t, L/2 − 1); L/2 − 1 governs) | **10.00** | **9.775** |
| Dust flap profile | lid side straight. Far side: straight 1.278, then a 45° step in 1.278 (shoulder), then a straight taper to a top edge 4.62 inboard (0.21 × width; taper dx 3.342 over dy 7.669). Top edge 17.38 | shoulder 1.25; top inset 4.525; top edge 17.025 | shoulder 1.222; top inset 4.431; top edge 16.669 |
| Dust taper faces | the panel the lid's free edge lands on (STE: toward panel 3 at both ends; RTE: top toward panel 3, bottom toward panel 1) | same | same |
| Clearance between adjacent flaps at the root | **0.45 = t** slot (each flap inset t/2 from the vertical crease) | 0.45 | 0.45 |
| Thumb notch | **none** (the template has no thumb-notch option) | none | none |
| Window, hang slot | off (options exist) | off | off |
| Bleed / safe area | not drawn (an optional 3 mm bleed guide exists, off by default); no safe area | same | same |

**Closure topology (Box Blanks):**
- **STE**: top and bottom lids both on **panel 1** (labelled "Back", next to the glue flap). Dust flaps on panels 2 and 4 at both ends. Panel 3 ("Front") has a plain cut edge at both ends.
- **RTE**: top lid on **panel 1**, bottom lid on **panel 3**. Dust flaps on panels 2 and 4 at both ends. Panel 1's bottom edge and panel 3's top edge are plain cuts.

**Line types (Box Blanks):**
- SVG groups `id="CUT"`: stroke `#e5007d`, solid, 0.25 mm. `id="CREASE"`: stroke `#0072ce`, dash `3 2` (mm), 0.25 mm. Also `id="BOXBLANKS_INFO"` (a grey credit text line). 10 mm margin.
- PDF: DeviceRGB magenta (229, 0, 125) for cut and blue (0, 114, 206) for crease, 0.709 pt (0.25 mm); crease dash 8.504/5.669 pt (3/2 mm).
  - **No spot colour, no `/Separation`, no OCG layers.**
  - The page (128.2 × 215.65 mm) also carries a title line ("22 × 22 × 105 mm outside · 0.45 mm board · blank 98 × 164 mm") and a cut/crease legend.
- DXF: R12 (AC1009), `$INSUNITS` 4 (mm), LINE entities. Layers `CUT` (ACI 6 magenta), `CREASE` (ACI 5 blue), `BOXBLANKS_INFO` (ACI 8). Every linetype is CONTINUOUS (the crease dash is not carried in the DXF).

### 3b. Die Cut Studio: STE

| Feature | outer 22×22×105 | inner 22×22×105 |
|---|---|---|
| Flat (cut) size W × H | **100.70 × 173.20** (page incl. bleed 107.06 × 179.56) | **104.30 × 176.89** |
| Panel 1 / 2 / 3 / 4 | 22.00 ×4 | 22.90 ×4 |
| Body height | 105.00 | 105.90 |
| Board compensation visible | **none in Outer mode** (outer typed = crease-to-crease, so the folded outside comes out about t larger) | crease = inner **+ 2t**, uniform |
| Glue flap | 12.70 wide (a fixed 0.5 in); crease 105.0; free edge 94.84; 45° corner chamfers 5.08 × 5.08, then square to the crease | 12.70; crease 105.9; chamfer 5.08 |
| Lids | both on **panel 1**; cut width = full panel 22.00 (no inset) | 22.90 |
| Lid depth | 22.00 | 22.90 |
| Tuck crease | full lid width 22.00 (no nick) | 22.90 |
| Tongue length | **12.10** (0.55 × panel) | 12.595 |
| Tongue shape | straight sides tapering 5.50 in on each side to an 11.00 tip; no nick, no radius | tip 11.45 |
| Slit locks | none | none |
| Dust flaps | panels 2 and 4, both ends. Depth **9.90** (0.45 × panel), full panel width, symmetric 45° chamfers 4.95 on both outer corners | depth 10.305, chamfer 5.152 |
| Clearance lid ↔ dust | **zero**: they share one cut line (a knife slit), no relief slot | zero |
| Thumb notch | panel 3 (front), top and bottom edges: semicircle **R 3.96** (Ø 7.92), centred on the panel | R 4.122 |

### 3c. Die Cut Studio: RTE

| Feature | outer 22×22×105 | inner 22×22×105 |
|---|---|---|
| Flat (cut) size W × H | **105.60 × 171.00** (page incl. bleed 111.96 × 177.36) | **109.92 × 174.60** |
| Panel 1 / 2 / 3 / 4 | 22.00 ×4 | 22.90 ×4 |
| Body height | 105.00 | 105.90 |
| Glue flap | **17.60** wide (0.8 × panel; the STE uses 12.70). Crease 105.0, free edge 97.0, 45° chamfers 4.0 | 18.32; chamfer 4.0 |
| Top lid | **panel 1**, depth 22.00 | 22.90 |
| Bottom lid | **panel 3**, depth 22.00 | 22.90 |
| Tongue length | **11.00** (0.5 × panel) | 11.45 |
| Tongue shape | 45° shoulders 5.445 from the crease ends, straight 0.605, then quadratic round corners of about **R 4.95**, flat tip 1.21: a "bullet" tongue | shoulders 5.668, R 5.152 |
| Dust flaps | panels 2 and 4, both ends. Depth **20.00** (panel − 2.0), full width, 45° chamfers 4.0 both corners | depth 20.90 |
| Clearance | zero (shared cut line) | zero |
| Thumb notch | none (the "Thumb cut" option is off by default) | none |

**Line types (Die Cut Studio, both styles):**
- SVG groups `cut` `#1f3bb3` solid 1 pt (0.353 mm), `crease` `#e0322b` dash `4 3` pt, `glue` grey hatch `#b9b9b9` 0.5 pt. The viewBox is in **points**, translated by the bleed (9.0142 pt = 3.18 mm).
- PDF: written by pdf-lib, DeviceRGB, **no spot colour, no OCG layers**. The bleed is only page margin; **no bleed line and no safe area are drawn**.
- DXF: R12, `$INSUNITS` 4 (mm), POLYLINE entities. Layers `CUT` (ACI 5 blue) and `CREASE` (ACI 1 red), CONTINUOUS.
- Note that the colours are the opposite way round from Box Blanks: Die Cut Studio cuts in blue and creases in red.

### 3d. Where the two references disagree (22 × 22 × 105, inside/inner, t = 0.45)

| Feature | Box Blanks (inside) | Die Cut Studio (inner) |
|---|---|---|
| Panel crease width | 22.45 (inner + t) | 22.90 (inner + 2t) |
| Body height | 105.45 | 105.90 |
| Tongue length | 8.0 | 12.6 (STE) / 11.45 (RTE) |
| Tongue root | V friction nick 1.32 × 2.8 | none (STE) / 45° shoulders (RTE) |
| Dust flap depth | 10.2 | 10.3 (STE) / 20.9 (RTE) |
| Flap clearance | 0.45 slot | none |
| Glue flap | 12, 4 mm slant | 12.7 (STE) / 18.3 (RTE), 45° chamfers |
| Thumb notch | none | Ø 8.2 on the front (STE default) |

Both references agree on:
- the **topology**: STE lids both on panel 1; RTE top on panel 1, bottom on panel 3;
- dust flaps on panels 2 and 4;
- lid depth = the side panel's crease width;
- no slit locks;
- no spot colours, no layers in the PDF, no safe area.

## 4. Recommendation

**THE professional reference: Box Blanks, for both the 22 × 22 × 105 STE and the RTE.** Reasons:
1. Its terms are the cleanest of every candidate: use, modify and share, commercial included, no attribution, no account.
2. It takes the exact size and the 0.45 caliper, and says explicitly what the numbers mean (inside / crease / outside). Its compensation can therefore be read straight off the files: ±t per panel and on the height, with flaps inset t/2 and a t relief slot.
3. It ships a DXF with CUT/CREASE layers, which is what a die-maker asks for.
4. It has trade-like details: a friction nick at the tongue root, tapered dust flaps that face the lid's free edge, and a t-wide relief between flaps.

Which of the three files to set beside 119 depends only on what 119's 22 × 22 × 105 means. The caller must decide this from 119's own record:
- `*_inside_t0.45` if the numbers went in as the box's **inside**. Our `ecma_ste.py` and `opposed_tuck.py` docstrings treat W/D/H as inner, but I did not check which engine drew 119.
- `*_outside_t0.45` if they are the box's **outside**. The brief says "outside-ish".
- `*_crease_t0.45` if they are crease-to-crease, or as the zero-allowance control.

All three are in `refs/` for both styles.

**Use Die Cut Studio as a second opinion only**, to show where generators legitimately vary: tongue length, dust depth, thumb notch, glue width.

Caveats to state to the owner:
- Box Blanks is a parametric generator, not a converter's production die. Its terms say: "we do not warrant that any dieline is accurate … cut and fold a sample".
- **Its "Checked against the plate" badge contradicts itself, so do not lean on it:**
  - Both STE and RTE style pages carry boilerplate saying the blank was "compared side by side with the drawing in the FEFCO Code, 12th Edition". FEFCO is the corrugated standard, and these are ECMA cartons.
  - The ECMA index page says "The comparison that settles this for corrugated cannot yet do it for cartons."
  - The RTE note says it was "scored 0.952" against ECMA A20.20.03.01 but "BADGED BY HAND".
  - The STE note gives no score. Its code was "Found from the coding rules on ECMA p.16".
- **ECMA code discrepancy, logged and not resolved.** Box Blanks's STE page says STE = **A20.20.01.01**, which is also the code our `ecma_ste.py` uses. But Box Blanks's own ECMA index page lists A20.20.01.01 as "Aerotuck to Back" and **A20.20.03.03** as "Same Panel Tuck". Only the ECMA Code book itself can settle which is right, and I did not obtain it.

## 5. Contract cross-walk with our engine (read from docstrings only; NOT measured from 119)

These figures are arithmetic from the coordinate contracts in `apps/dielines/geometry/ecma_ste.py` and `opposed_tuck.py`, taking inner 22/22/105 and t = 0.45. Which engine and version actually drew 119 was **not** checked, so treat this as a list of *what to measure*, not as findings.

- **Panel widths**
  - `ecma_ste.py` (STE) emits its vertical creases at x1, x2, x3b and x4 (checked read-only in the `fold_lines` list). x3 is only where the relief cut starts, not a crease.
  - So, crease to crease, the panels are: glue G | back x2 − x1 = L − t = **22.45** | side_left x3b − x2 = P = **22.90** (the last t of it is a relief zone: the dust-flap hinge stops at x3) | front L = **22.90** | side_right P − t = **22.45** (free edge).
  - The pattern is **22.45 / 22.90 / 22.90 / 22.45**, the same as `opposed_tuck.py`.
  - Box Blanks (inside) is 22.45 on all four panels. Expect panels 2 and 3 to be +0.45 each, and a t relief at the panel 2 / panel 3 crease.
  - Our STE tuck lid runs from x1 − t to x2. That is L = 22.90 wide, so it overhangs the glue crease by t. Box Blanks's lid is 22.00 wide, inset t/2 inside panel 1.
- **Body height**
  - Ours: H_inner = **105.00**, with the back-panel creases offset ±t.
  - Box Blanks (inside): 105.45 on every panel.
- **Lid depth (closure face)**
  - Ours: P − 2t = **22.00**.
  - Box Blanks (inside): 22.45.
- **Tongue**
  - Ours: hook **18 mm** past the fold, plus 2t lock ears.
  - Box Blanks: **8 mm**; Die Cut Studio: 11–12.6 mm.
  - This is likely to be the most visible difference on a 22 mm carton.
- **Locks**
  - Ours: entry slits 7 × 2.5 at each fold end, and quadratic (Bezier) tuck shoulders with k = 0.635.
  - Box Blanks: no slits, a straight V nick, chamfered tongue corners.
- **Dust flap depth**
  - Ours: min((P + hook − t)/2, L/2) = min(20.2, 11.45) = **11.45**.
  - Box Blanks (inside): 10.225.
- **Glue flap**: both 12 by default.
- **RTE** (`opposed_tuck.py`): panels glue | L − t = 22.45 | P = **22.90** | L = **22.90** | P − t = 22.45. The top lid is on main_a (panel 1) and the bottom lid on main_b (panel 3), which is the same topology as both references.

## 6. Reproduction and files

- `work/fetch_bb.py`: drives boxblanks.com in headless Chromium and saves PDF/SVG/DXF plus a screenshot for each style × mode. Logs: `work/boxblanks_fetch_log_inside_outside.json`, `work/boxblanks_fetch_log_crease.json`.
- `work/fetch_dcs.py`: the same for diecutstudio.com. Log: `work/diecutstudio_fetch_log.json`.
- `work/measure_bb.py`: the SVG parser used for the Box Blanks tables. Die Cut Studio paths were dumped in mm with an inline parser.
- Playwright and Chromium were run from the existing bbrose venv **as execution only**. Nothing was installed or changed in it. No new venv was needed.
- Full SHA-256 list: `refs/TERMS.md` §3.
