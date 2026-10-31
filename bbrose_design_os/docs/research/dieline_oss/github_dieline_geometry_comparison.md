# Geometry comparison — candidates vs the Pacdora structural reference

Reference (task #50, user-verified from the Pacdora page, vector file still
pending): straight-tuck-end folding carton, inner 90 × 32 × 92 mm, board
0.5 mm, panel sequence glue | 90 main | 32 side | 90 main | 32 side, wide
shaped major tuck flaps, shaped dust flaps, cut interruptions, crease
shortening/segmentation, glue-flap taper, full-contour bleed.

**Parity discipline:** width/depth/height agreement alone proves nothing.
The table scores each candidate against the *shape* features. Even the best
candidate is not claimed to reproduce the Pacdora die exactly — that
verification is only possible against the actual customer vector file and
is enforced by `apps/dielines/services/customer_dieline.py` (0.1 mm gate,
commit d59a8e4).

| Feature (reference requirement) | DDR68 ECMA A20.20.01.01 (MIT) | Chinnakrit05 tuckEnd.ts (no licence) | boxes.py paperbox/tuckbox (GPL-3.0) | BBROSE current generic STE 1.1 |
|---|---|---|---|---|
| Panel sequence glue\|main\|side\|main\|side | ✅ inc\|L−S\|P−S\|[S relief]\|L\|P−S | ✅ | ❌ (wrap layout, single lid) | ✅ |
| Customer-defined dimensions | ✅ L/P/A prompt | ✅ BoxParams | ✅ x/y/h | ✅ |
| Board-thickness compensation | ✅ throughout (panels, creases, reliefs, diagonal crease-start) | ⚠️ partial (glue width, dust inset only) | ⚠️ kerf/burn model, not board compensation | ⚠️ partial |
| Inner/mfg/outer dimension model | ⚠️ external-only input (inner→external must be derived; PoC uses inner+2S) | ⚠️ unclear | ⚠️ inside/outside toggle | ⚠️ single nominal |
| Major tuck flaps top+bottom (STE closure) | ✅ both from P1, hook 18 mm, ear 2S | ✅ | ❌ single tuck lid only | ⚠️ generic straight tucks |
| Curved shoulder transitions on tucks | ✅ quadratic Bézier, k = 0.635 | ⚠️ unverified | ⚠️ lid radius only | ❌ |
| Shaped dust flaps | ✅ 45° chamfer + taper, depth (P+hook−S)/2 ≤ L/2 | ✅ inset formula | ❌ | ⚠️ rectangular |
| Tuck-entry slits / slit-locks | ✅ 7 × 2.5 mm with 2S ear | ⚠️ unverified | ✅ "locking cut" on lid | ❌ |
| Cut interruptions at panel steps | ✅ relief cuts at P2\|P3 and P3\|P4 | ⚠️ unverified | n/a | ❌ |
| Crease shortening / segmentation | ✅ tuck-fold crease shortened by slit width; glue crease shortened by S | ⚠️ unverified | n/a | ❌ |
| Glue-flap taper/chamfer | ✅ 3 mm chamfer + 2 mm taper diagonals | ✅ thickness-driven width | n/a | ⚠️ plain rectangle |
| Cut/crease layer separation | ✅ Taglio/Cordone layers | ✅ path roles | ⚠️ cut + etch | ✅ CUT/CREASE spots |
| Full-contour bleed | ❌ absent | ❌ absent | ❌ absent | ✅ engine adds bleed |
| Safe-area generation | ❌ | ❌ | ❌ | ✅ |
| Deterministic output | ✅ | ✅ | ✅ | ✅ |
| Collision / fold-clearance validation | ⚠️ input validation only (P ≥ glue+3, A > 2S) | ❌ | ⚠️ | ⚠️ |
| Structural geometry unit tests | ❌ | ❌ | ✅ (framework-level) | ✅ (2,103-test suite hosts the gates) |
| Export formats | Rhino layers (+PDF via prepress script) | SVG 1:1 mm | SVG/PS/LBRN2 | PDF (CUT/CREASE spots), AI preview |

## Implementation notes from source inspection (DDR68, the top candidate)

- **Coordinate model:** flat 2D, y-up, panels along x; all coordinates are
  closed-form expressions of L, P, A, S plus seven named constants (glue
  width 18, hook 18, chamfer 3, taper 2, slit 7 × 2.5, Bézier k 0.635).
- **Thickness compensation:** body height A−2S; P1 creases offset ±S; P1
  narrowed to L−S while P3 keeps L; sides P−S; an S-wide relief cut between
  P2|P3; the P1 crease start compensated by `S·2S/(2S+taper)` where the
  glue diagonal meets it. This is a real manufacturing model, not cosmetic.
- **Curves:** degree-2 NURBS with 3 control points — mathematically a
  quadratic Bézier, portable to SVG `Q` and PDF `v/y` operators exactly.
- **Topology:** cut and crease are separate open polylines per layer
  (57 cut segments incl. 4 Béziers, 12 creases for our parameters); no
  closed-path assembly, no self-intersection handling (not needed —
  segments are analytically disjoint by construction).
- **Gaps vs the reference:** no bleed contour, external-dimension input
  only, no tests, Rhino-bound emission. All four gaps are covered by
  existing BBROSE machinery (bleed/safe-area generation, dimension
  conversion, pytest gates, PDF/JSX emitters).

## Proof of concept (rendered locally, read-only)

`poc/ste_dieline_poc.py` ports the DDR68 formulas (MIT, attribution in the
header) to a standalone SVG emitter with no Rhino and no BBROSE imports:

- inputs: inner 90 × 32 × 92 mm, S = 0.5 → external 91 × 33 × 93
- body height between main creases: **92.0 mm** (= inner height)
- panels: 18 | 90.5 | 32.5 | 0.5 | 91 | 32.5 (thickness-compensated)
- flat size 265.0 × 193.0 mm; dust-flap depth 25.25 mm
- output: `poc/ste_90x32x92_t05.svg` — DIELINE_CUT (blue) and
  DIELINE_CREASE (red) groups, labelled panels, **no artwork**
- raster check: `poc/ste_90x32x92_t05.png`; DDR68's own Rhino render for
  the same archetype: `poc/ddr68_reference_render_MIT.png`

The PoC deliberately stops at "clean structural drawing": bleed, exact
Pacdora flap contours and mfg allowances stay blocked on the customer
vector file per the parity mandate.
