# DIP-0C3c — completion report

**ASE colour palette: technical, ownership and usage audit.**
Builds on C3b4 (`263a912`).

---

## The finding

**The filename says Pantone. The bytes say a named RGB swatch.**

`Pantone_3519C.ase` — 66 bytes, ASE **v1.0**, **1** block, **0** groups, **1** swatch:

| | |
|---|---|
| swatch name | `Pantone 3519 C` |
| colour model | **RGB** — and nothing else |
| channels | R 0.478431 · G 0.180392 · B 0.380392 |
| sRGB preview (derivative) | (122, 46, 97) |
| colour type | **GLOBAL** — *not* SPOT |

The file contains **no spot identity, no CMYK, no Lab, no ICC profile**. "Pantone"
exists **only inside a name string**. It is therefore third-party *naming evidence* —
not an authoritative Pantone definition, not a licence, and not a colour from which any
print-accurate or official conversion could be derived. There is nothing here to
fabricate a Pantone conversion *from*, and none was.

Folder: `DOWNLOADE 2026/نماذج عامة من الانترنيت` — "general models from the internet".
**The filename and the folder prove nothing**, and they never did.

## Parse status — and why it is not "parsed"

| Field | Value |
|---|---|
| `parse_status` | **`PARTIAL_PARSE`** |
| `capability` | **`REQUIRES_HUMAN`** |
| `layout` | **`NON_STANDARD_NAME_ENCODING`** |
| `warning` | **`NAME_LENGTH_FIELD_ABSENT`** |
| `fallback_used` | **`true`** |
| trailing bytes | 0 |

The documented ASE colour block begins with a `uint16` name length. In this file that
field reads **`0x0050` = 80 UTF-16 units = 160 bytes**, inside a body of **48 bytes**.
Not merely wrong — **provably impossible**. The fallback (a NUL-terminated UTF-16BE
name, no length prefix) consumes the declared body **exactly**: `name 30 + "RGB " 4 +
3 floats 12 + type 2 = 48`, zero unexplained bytes, one unique valid reading.

**It never reaches `TECHNICALLY_PARSED`, because a non-standard fallback was required.**
Reading a file successfully is not the same as the file being well-formed.

## The two-layout protocol (D1, exactly as specified)

Standard layout first → fallback **only** when the standard is *provably* impossible (a
field cannot fit, or parsing would cross the block boundary) → accepted **only** if it
consumes the body exactly, leaves nothing unexplained, and yields a valid model, channel
count and colour type, with **one** unique interpretation. Otherwise `PARSE_FAILED` +
`REQUIRES_HUMAN`. **No interpretation is ever chosen heuristically.**

**The ambiguity check earns its keep.** A block can have *two* exact readings: the float
`0.5` is `0x3F000000` — it ends in two NUL bytes — and the next float's bytes can spell
a valid model token. A parser taking the first NUL would silently pick one and never
know the other existed. There is a fixture for precisely that shape, and the parser
refuses it.

## Provenance preserved

Source SHA-256 · declared block length · source byte offsets (18 → 66) · block body
SHA-256 · standard-parser failure reason (recorded verbatim) · fallback name and version
· bytes consumed (48) · unexplained bytes (0) · parser warnings · confidence. Unknown
blocks keep their body hash — bytes are never discarded for not being understood.

## Raw vs derivative

`raw` is marked `authoritative: true`. `normalized` carries previews with their
`conversion_method`, library version, gamut/clipping warnings and a **capped**
confidence. They never share a key.

RGB, CMYK, Lab and GRAY are **not interchangeable**: no print-accurate RGB is claimed
from CMYK without an ICC profile (`NAIVE_CMYK_TO_SRGB_NO_ICC`, preview-only, confidence
≤ 0.5, CMYK preserved); Lab records its illuminant assumption and gets **no** sRGB
preview at all (that would need a gamut decision, and a silently-clipped preview is
worse than none); a spot's identity and its alternate preview colour stay separate.

## Ownership, licence, permissions

| | |
|---|---|
| `ownership_status` | `OWNERSHIP_UNCONFIRMED` |
| `license_status` | `LICENSE_UNVERIFIED` |
| `brand_association` | `REQUIRES_HUMAN` |
| `reuse_posture` | `REFERENCE_ONLY` |
| retrieval / automatic use / production use | **`false`** |
| all nine permissions | **`false`** |

Machine code may emit only `TECHNICALLY_PARSED`, `PARTIAL_PARSE`, `REFERENCE_ONLY`,
`OWNERSHIP_UNCONFIRMED`, `LICENSE_UNVERIFIED`, `REQUIRES_HUMAN`. `machine_palette_state()`
**raises** on `APPROVED_BRAND_PALETTE`, `APPROVED_REUSABLE`, `LICENSE_APPROVED`,
`BBROSE_OWNED_CONFIRMED`.

A test asserts that a *technically perfect* palette **still** has every permission false.
Parsing a colour is a technical fact; owning it is a legal one. They never collapse.

No Pantone library is bundled. Only the single supplied file was audited.

## Review queue

One item, priority HIGH, roles `LEGAL_REVIEWER` + `BRAND_ADMIN`, **never batch-reviewed**.
Machine fields populated; **every human field blank** — reviewer, reviewed_at, ownership
confirmation, brand association, palette approval, approved brands/products/markets,
allowed uses, restrictions, review expiry, notes. The 12-item approval contract is
defined and **entirely unanswered** (`None` is not a pass).

## Verification

| Check | Result |
|---|---|
| `pytest tools/dip0c/tests/test_c3c.py` | **44 passed** |
| `pytest tools/dip0c` | **402 passed** |
| DIP-0A + DIP-0B | **343 passed** |
| Django | **537 passed**, 1 skipped |
| `ruff check tools/` | clean |
| `materials/` integrity | **unchanged** (pre/post snapshot) |
| runtime | 0.16 s |
| committed output | 8 KB (`var/` heavy output git-ignored) |

## Acceptance criteria

| Question | Answer |
|---|---|
| Is the ASE technically parseable? | **Only via a non-standard fallback** → `PARTIAL_PARSE` |
| What blocks and swatches? | 1 colour block, 0 groups, 1 swatch |
| Which values are direct source data? | name, model (RGB), 3 channels, colour type (GLOBAL) |
| Which are derived previews? | sRGB (122,46,97) and Lab — both derivative, capped |
| What remains uncertain? | who wrote the file, who owns it, whether BBROSE ever used it |
| Third-party naming? | **Yes — PANTONE, in the name string only** |
| Is ownership known? | **No** |
| Is BBROSE association confirmed? | **No** |
| What must a human approve before use? | the 12-item contract in `c3c_review_item_sample.json` |
| What schema should DIP-1 persist? | `c3c_parser_schema.md` — raw + derivative, never merged |

## Findings requiring adjustment before C3d

1. **There is no palette-approval event type in the ledger.** The contract is defined but
   has nowhere to be recorded. Wiring it into the C3b3 dual-control/permission machinery
   is the next step — today a human's approval would have nowhere to go. Correct failure
   mode, but it means C3c ends at "ready for review", not "reviewable end-to-end".
2. **The corpus is one file.** Nothing here is a survey of BBROSE's palette practice.
3. **The naive CMYK preview must never become a comparison basis.** Without an ICC
   profile those numbers are not commensurable, and a ΔE computed from them would look
   rigorous and mean nothing.

**HOLD for review before C3d.**
