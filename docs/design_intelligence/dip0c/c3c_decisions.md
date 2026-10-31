# DIP-0C3c — decisions

## D1. The two-layout protocol (the business's Option A, implemented literally)
The documented ASE layout is tried first. The non-standard fallback is reached **only**
when the standard layout is *provably* impossible — a field cannot fit, or parsing
would cross the declared block boundary — and it is accepted **only** if it consumes
the declared body exactly, leaves no unexplained bytes, and yields a valid model,
channel count and colour type, with **exactly one** valid interpretation. Anything
ambiguous → `PARSE_FAILED` + `REQUIRES_HUMAN`.

This is validation against a length the file itself declares. It is not guessing.

## D2. A fallback is itself a finding
`Pantone_3519C.ase` is capped at `PARTIAL_PARSE` / `REQUIRES_HUMAN`, layout
`NON_STANDARD_NAME_ENCODING`, warning `NAME_LENGTH_FIELD_ABSENT`, `fallback_used=true`.
**It can never reach `TECHNICALLY_PARSED`.** Reading a file successfully is not the same
as the file being well-formed, and that distinction must survive into the record rather
than evaporating the moment the parse succeeds.

## D3. The ambiguity check is real, not ceremonial
A block can have **two** exact readings. The float `0.5` is `0x3F000000` — it *ends in
two NUL bytes* — and the next float's bytes can spell a valid model token. A parser
taking the first NUL would silently choose one reading and never know the other
existed. `_ambiguous()` sweeps every NUL split and refuses if more than one survives
validation. There is a fixture for exactly this shape.

## D4. Raw is authoritative; a preview is a derivative
`raw` and `normalized` live under separate keys and are never merged — the same
discipline as machine inference vs human confirmation. Once mixed, nobody can tell
which one they are looking at. Every derived number carries its conversion method,
library version, warnings and a **capped** confidence.

## D5. RGB, CMYK, Lab and GRAY are not interchangeable
No print-accurate RGB is claimed from CMYK without a declared ICC profile: the
conversion is named `NAIVE_CMYK_TO_SRGB_NO_ICC`, flagged `PREVIEW_ONLY`, capped at 0.5
confidence, and the CMYK is preserved untouched. Lab records its illuminant assumption
and is **not** converted to sRGB at all — that needs a gamut decision, and a
silently-clipped preview is worse than none. A spot's identity and its alternate
preview colour stay separate facts.

## D6. No Pantone conversion is fabricated
Not from a generic formula, not from anything. And for this file there is nothing to
fabricate one *from* — see D7.

## D7. The bytes undercut the filename, and that is the headline
The colour type is **GLOBAL (0), not SPOT**. The file carries **no spot identity, no
CMYK, no Lab, no ICC profile** — a single RGB triple and a name. **"Pantone" exists only
inside a name string.** It is third-party *naming evidence*, not an authoritative
Pantone definition, and no official conversion, ownership, or brand association follows
from it. This is not a footnote in the report; it is the finding.

## D8. Unknown blocks are preserved, never skipped
An unrecognised block keeps its body hash and is recorded as "preserved, not
interpreted — the parser will not guess what it means." Bytes are not discarded merely
because they were not understood.

## D9. Parsing is a technical fact; ownership is a legal one
A palette may parse perfectly and remain entirely unusable. `Pantone_3519C.ase` gets
`OWNERSHIP_UNCONFIRMED`, `LICENSE_UNVERIFIED`, brand association `REQUIRES_HUMAN`, and
**all nine permissions false**. A test asserts that even a *technically perfect* palette
still has every permission false — the two axes never collapse into one score.

## D10. The approval contract rides the existing machinery
The 12-item palette approval checklist mirrors the C3b3 canonical checklist
deliberately, so a future palette approval uses the **same** dual-control, ledger and
permission machinery rather than growing a parallel one. C3c *defines* the contract and
approves nothing.

## D11. No Pantone library is bundled
Only the single source file supplied in `materials/` is audited. Nothing proprietary is
committed, downloaded, or reconstructed.

## D12. Historical colour comparison is deferred, deliberately
The business said C3c *may* compare experimentally. Building a comparison engine off
**one RGB triple** would be a trap that produced confident-looking noise. C3c records
the rule — any such relationship is `HEURISTIC`, confidence-capped, never a brand
association and never a permission — and does not run it. The palette file's existence
does not establish that BBROSE designs ever used it.
