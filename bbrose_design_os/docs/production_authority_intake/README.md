# Owner-supplied spec pack — the intake (§BH46)

**The system never contacts suppliers.** The owners of the companies deal with their suppliers
directly. When they receive the product information — drawings, print zones, decoration
process, material specification — they hand it to the designer, and this system is the
designer. Everything it needs is given to it; it acquires nothing.

This directory is the ruled intake location, beside `production_authority/`.

| Path | What it is |
|---|---|
| `spec_pack/` | Place the documents here, as handed over |
| `spec_pack_manifest.json` | Your mapping: which document satisfies which item, who handed it over, when |
| `intake_state.json` | Derived on every run: one entry per item of gates B–E — MISSING, REFUSED or SATISFIED |
| `intake_provenance.json` | Derived on every run: one entry per accepted document, with the sha256 measured here |
| `dry_run.md` / `dry_run.json` | Derived: what each item needs, and what a placed pack would satisfy or refuse, and why |

## How to place a pack

1. Copy the documents into `spec_pack/` (PDF, DXF, SVG or text for drawings; PDF or text for
   statements, certificates and datasheets — an image or binary CAD is refused by name, so
   add a PDF of the same drawing).
2. Add one entry per document to `spec_pack_manifest.json`:

```json
{
  "record_type": "spec_pack_manifest/1.0",
  "handed_over_by": "the person who handed the pack to you",
  "handed_over_on": "YYYY-MM-DD",
  "documents": [
    {"file": "bottle_drawing.pdf",
     "satisfies": ["B_supplier_geometry/qualified bottle drawing",
                   "B_supplier_geometry/tolerances"],
     "supplier": "the supplier's name, as stated on the document",
     "handed_over_by": "optional override of the top-level value",
     "handed_over_on": "optional override",
     "sha256": "optional: the sha256 as handed over; it must match the file"}
  ]
}
```

3. Run the validator (`spec_pack_intake.validate()`); it reads the location and nothing else,
   refuses what does not satisfy its item — `WRONG_PRODUCT`, `NO_DIMENSIONS`, `NO_CERTIFICATE`,
   `NO_PROVENANCE`, `SHA_MISMATCH`, `FILE_MISSING`, `WRONG_KIND`, `UNREADABLE_KIND`,
   `NOT_INSPECTABLE` — and flips each satisfied item, never the gate. A gate passes when every
   one of its items is satisfied by intaken evidence; the gate record computes that.

## What each item needs

The nineteen items are the gates' `requires` lists, unchanged. What "satisfies" each one means
is written in `spec_pack_intake.py` beside the item, and `dry_run.md` restates it for the pack
as it stands. In short: every document must name **this** product (30 ml, serum / dropper /
frosted); a drawing must carry dimensions with units; a material item needs a certificate,
datasheet or specification sheet; the decoration and colour items must name the process and
the colour systems; and every document needs provenance — who handed it over and when.

Nothing is accepted without provenance. Nothing here is fetched, requested or sent.
