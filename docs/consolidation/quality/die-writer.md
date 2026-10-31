# The die writer — quality

**Job:** every die's files at 1:1: the layered PDF (CutContour and Crease spot plates, registration on All, TrimBox and
BleedBox, title block), DXF, CF2, the nest and the assembly drawing; for the stand also the flat template, the die
applied again to a painting, the proof and the read-back. File: `apps/dielines/exporters/counter_display_files.py`.

**The bar, in numbers:** cut and crease read back from each file within 0.01 mm of the engine's geometry, both ways;
the boxes within 0.01 mm; every font embedded; DXF and CF2 for every die; one writer for stand and carton.

**Before → after, same input.** Cartons (three house cartons, `runs/carton-before/` → `runs/carton-after/`; donors
production_pdf, svg_exporter, ai_exporter): the stand (round 3's die, `engines/runs/chain-before.json` → now; donors
pdf_layers and the 0.1 sheets' apply_layers):

| | Before | After |
|---|---|---|
| Carton PDF cut / crease read-back | 0.0 / 0.0 mm | 0.0 / 0.0 mm |
| Carton TrimBox, BleedBox | 0.0, 0.0 mm | 0.0, 0.0 mm |
| Carton fonts | Noto embedded + an unembedded Helvetica | all embedded |
| Carton DXF | none | 591 entities (reverse tuck 1.4), cut/crease read back 0.0001 mm |
| Carton CF2 | none | 185 lines, cut read back 0.0007 mm, crease 0.0003 mm |
| Stand die.pdf read-back cut / crease / art | 0.0003 / 0.0002 / 0.0001 mm | 0.0003 / 0.0002 / 0.0002 mm (the art now a 300 ppi raster) |
| Stand DXF, CF2 | written | byte-identical |
| Writers of a die | four (pdf_layers, 0.1 sheets, production_pdf + svg_exporter + ai_exporter, 1.0) | one |

Every part moved in is identical to its donor (7 of 7, `runs/moved-parts.json`).

**Verdict: BETTER** — cartons gain DXF and CF2 read back within 0.0007 mm and lose the unembedded font; one writer.

**Weakest point:** no CF2 has yet been verified by a die shop (`verified_by_a_die_shop: false`), and no press CMYK
profile exists: the separations are named spots on an RGB/CMYK document with no output intent.
