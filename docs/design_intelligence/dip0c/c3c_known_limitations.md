# DIP-0C3c — known limitations

## L1. The corpus is one file, 66 bytes
There is exactly **one** `.ase` in all of `materials/` (28 GB, 7,586 files). Everything
C3c concludes about *BBROSE's palettes* is therefore a conclusion about **one downloaded
swatch**, not about a palette practice. The parser is built for the format; the findings
are about this file. Do not read the completion report as a survey.

## L2. The non-standard layout is inferred from one specimen
`NON_STANDARD_NAME_ENCODING` is a layout I named after seeing it once. I do not know
which tool wrote it, whether that tool is consistent, or whether other files from the
same source would parse the same way. The acceptance rule is strict enough that a
*different* malformation will fail closed rather than be forced into this shape — but
the layout is a description of one file, not a documented variant.

## L3. `_ambiguous()` only sweeps NUL splits within the fallback
It proves the *fallback* reading is unique. It does not prove the standard and fallback
readings could never both be valid — that case is handled by ordering (standard wins if
it consumes exactly), not by a search. The two together are sufficient for the rule the
business set, but the uniqueness guarantee is narrower than "there is exactly one way to
read these bytes."

## L4. Colour conversions are previews, and the CMYK one is naive
`NAIVE_CMYK_TO_SRGB_NO_ICC` is `(1-c)(1-k)` — a formula for the eye, not colour
management. It is labelled, capped at 0.5 confidence, and never replaces the CMYK. But
if a future slice starts *comparing* colours across models, this preview must not be the
thing it compares: without an ICC profile the numbers are not commensurable, and a ΔE
computed from them would look rigorous and mean nothing.

## L5. Lab has no sRGB preview at all
Deliberate (a gamut decision would be required), but it means a Lab swatch has no visual
preview in the review item. A reviewer would see numbers, not a colour. Acceptable for
one file; a real palette library would need a proper, profile-aware renderer.

## L6. ASE GRAY inversion is an assumption
I treat GRAY as ink coverage (0 = white, 1 = black) and invert it for the preview. That
matches Adobe's behaviour as commonly understood, but **no file in `materials/` exercises
it**, so the assumption is untested against reality. It is flagged `PREVIEW_ONLY` and
capped, and the raw value is preserved.

## L7. "Pantone 3519 C" is not verified as a real Pantone
The parser reports the name string. It does **not** check whether a Pantone 3519 C
exists, and it must not: verifying a name against a proprietary library would require
the library, which we neither have nor may bundle. The name is evidence of *naming*.
Whether it names anything real is a question for a human with a licensed ink book.

## L8. Naming detection is regex on strings
`PANTONE`, `RAL`, `NCS`, `HKS`, `TOYO`, `DIC`. It will miss an unlisted system and it
can fire on a coincidental substring. It produces *evidence*, never a decision, and a
human reviews it — so a false positive costs a glance and a false negative costs a
missed flag, which is why the list errs toward inclusion.

## L9. Historical colour comparison is not implemented
Deferred deliberately (D12). C3c therefore cannot answer "did BBROSE actually use this
colour?" — and nothing in it should be read as suggesting so.

## L10. No palette has been approved, and none can be from here
The approval contract is defined and unexercised. There is no palette approval event
type in the ledger yet: wiring the contract into the C3b3 dual-control and permission
machinery is the C3d/DIP-1 step. Today a human's approval would have nowhere to be
recorded — which is the correct failure mode, but it does mean C3c ends at "ready for
review", not "reviewable end-to-end".
