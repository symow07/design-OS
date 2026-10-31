# ES3083 VENDOR REQUEST — V2, THE SHRUNKEN ASK (NOT SENT)

Supersedes the request in `ES3083_VENDOR_REQUEST.md` (now banner-marked).
**Status: DOCUMENT ONLY.** Supplier outreach remains DEFERRED by the owner
(`supplier_outreach_deferral.json`); whether that deferral covers this named
vendor is surfaced as a decision to re-make in
`supplier_outreach_deferral_d9_check.json`. Nothing here is dispatched,
drafted as .eml, or queued.

**The test this version passes:** every line asks for something no record in
this repository holds. Each removal below names the record that made it
redundant.

---

**Subject:** ES3083 — five items: pan cavity, case heights, label die, label stock, label use

Hello,

We are working from your ES3083 production sheet, which we hold as the source
vector file. We have already taken exact measurements from it — the lid decal
(65.00 × 65.00 mm), the shade-label sheet (24 labels of 77.00 × 16.00 mm at
83.00 × 22.00 mm pitch on a 263.00 × 190.00 mm sheet), the back label
(49.50/55.00 mm), the display box panels (275.00 mm), and the two PANTONE
separations — so we do not need any of that re-supplied. What the sheet cannot
tell us:

1. **Pan cavity and pitch** — cavity length, width and depth, and the
   centre-to-centre pitch in both axes, with the manufacturing tolerance you
   hold on each.
2. **Case heights** — closed height, and lid and base heights separately,
   with tolerance.
3. **Label-sheet die** — are the 24 label rectangles on the sheet kiss-cut,
   thru-cut, or printed keylines? A die drawing or one-line answer is equally
   useful.
4. **Label stock** — the label material, adhesive, and any lamination or
   varnish, as specified for this sheet.
5. **Label use** — which surface are the 77 × 16 mm labels applied to, and
   why 24 per sheet?

A dimensioned drawing (.ai/.pdf/.dxf/.step) answering 1–2 is ideal; short
answers are welcome for 3–5.

Thank you,
BBrose

---

## WHAT WAS REMOVED FROM V1, AND WHY

| V1 request | Fate | Record that discharged it |
|---|---|---|
| "we cannot take any measurement from it" | **FALSE since 2026-08-13** | `ES3083_DIMENSION_FINDINGS.md` — measured at true scale |
| pan count and grid arrangement | held — 12 pans, 4×3, owner-confirmed HARD | `m4c4_panel_confirmation.json` |
| display box source vector | held — the .ai IS the source vector, in `materials/` | `ES3083_DIMENSION_FINDINGS.md` header |
| inner tray outer footprint / wall thickness / hinge offset | folded into item 1's drawing; hinge offset serves no current artwork record | substrate — no consumer |
| case outer length and width | derived-bounded ~65 held; heights kept, footprint folded into item 2's drawing | `es3083_artwork_geometry_substrate.json` |

**Added since V1** (questions that did not exist then): items 3, 4, 5 — from
`die_cut_question`, `STOCK_PARAMETER_2026_08_14` and the
`SEVENTY_SEVEN_MM_QUESTION` / 24-vs-12 allocation, all recorded UNDETERMINED
in the geometry substrate.

**Deliberately excluded:** anything touching formulation, INCI, approval
numbers, or barcodes. Those belong to the deferred SUPPLIER_DATA production
workflow and are unresolved questions this email must not imply answers to.

## V1 NOTES THAT REMAIN TRUE

- *Why tolerance is in the list*: a number with no error bar enters only as
  provisional; with it, real authority. (Unchanged from V1.)
- *The display box is not the palette*: `palt_m4c_es3083_authority.json`
  fences the dieline as PACKAGING_ONLY. (Unchanged from V1.)
