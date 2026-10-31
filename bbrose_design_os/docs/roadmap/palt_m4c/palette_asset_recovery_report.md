# PALT-M4C §4 — palette asset recovery report

**Date** 2026-08-06 · **Method** metadata scan across every record type,
then **visual inspection** of the leading candidate. Not filename, not
current database target.

## The owner was right

My previous checkpoint concluded "no palette design exists" from the
absence of Palette-target rows. That was wrong, and the owner's
instruction not to rely on the current target is what found it.

**BBROSE palette design information has been in Design OS all along**,
sitting under `packaging` and `product_container` targets where the
palette engine could never reach it.

## Genuine palette assets recovered: 5 records, 2 distinct designs

| record | design | current task | current target | file |
|---|---|---|---|---|
| ConceptReference 6 | **ES3083 — BBROSE "Outer Glow" eyeshadow palette** | 50 | packaging | present |
| ConceptReference 11 | FB3093/FB3090 粉饼 pressed-powder compact | 50 | packaging | present (PNG) |
| ConceptReference 30 | FB3093/FB3090 粉饼 (native .ai) | 51 | product_container | **absent** |
| ConceptReference 48 | FB3093/FB3090 粉饼 (native .ai) | 52 | product_container | **absent** |
| ConceptReference 11 (.ai) | FB3093/FB3090 粉饼 (native .ai) | 50 | packaging | **absent** |

`材料/materials/` is **not present in this working copy**, so the native
`.ai` sources (13,164 vector objects, 12 text blocks) are referenced by
the database but not openable here.

## ES3083 — visually confirmed content

`media/references/ref_ES3083吸塑_展盒刀线.png` was opened and read. It
contains, in one production sheet:

* a **photograph of the physical thermoformed clear tray** (the real pan
  carrier), labelled ES3083;
* a **rendered hinged palette case shown OPEN**, with a visible
  **rectangular pan grid** in a mint-green case;
* **BBROSE / EYE SHADOW / OUTER GLOW / SOMBRA DE OJOS** branding and
  smiley-face letterform motif with bubble/dot scatter;
* **Pantone 621 C and 627 C** brand colour chips;
* a full retail display-box dieline with regulatory panel and barcode;
* a **shade-label strip sheet** (a grid of blank name labels).

## This contradicts the PALT-P1 generic defaults

| feature | PALT-P1 default | ES3083 actual |
|---|---|---|
| pan shape | circular Ø26.0 mm | **rectangular** |
| grid | 3 × 3 = 9 pans | **approximately 4 × 3 = 12** |
| colour | none | **Pantone 621 C / 627 C mint** |
| artwork | none | full brand system + shade labels |
| tray | moulded ABS cup array | **thermoformed clear insert** |

Every one of the pilot's headline assumptions — round pans, nine of them,
26 mm, no artwork — differs from the real BBROSE palette that was already
in the system. This is the concrete cost of the §D architectural defect.

Pan count and grid are read from a small render and are recorded as
`approximately`, requiring owner confirmation. Pan **shape** (rectangular)
is high confidence.

## False positives explicitly excluded: 11

Eleven records matched on "blush" but are **lip products in a blush-pink
colourway** — `LP-2019`, `YB-1026_LP5869_`, `YB-1029_LG5853_`,
`YB-1027_LG5872_`, `FS5817` and similar. "Blush pink" is a colour word,
not a blush palette. They are recorded in the audit with confidence 0.05
and `NOT_A_PALETTE_ASSET`, not silently dropped.

## Selection state

```
PALETTE_SELECTED_CONCEPT: PENDING_OWNER_SELECTION
```

Two distinct palette designs exist (ES3083 eyeshadow palette; FB3093/3090
powder compact) and **no owner selection is recorded on either**. The
owner's selected asset cannot be proven, so no asset is promoted.

## Actions taken and not taken

* **Taken:** audited, hashed, classified and manifested every candidate.
* **NOT taken:** nothing was moved, overwritten, relabelled or retargeted.
  No original asset was touched. Linking a recovered asset to a Palette
  task is prepared but awaits the owner's selection, because attaching the
  wrong concept would be worse than attaching none.

## Authority

All recovered assets remain `REFERENCE_ONLY`, ownership
`HOUSE_PRODUCTION_LINEAGE_UNCONFIRMED`, rights `RIGHTS_UNREVIEWED` /
`UNVERIFIED`, permission `CANDIDATE`. Recovery establishes no rights
clearance and no manufacturing authority.
