# DIP-0C3c — the ASE parser schema

## The file format

```
HEADER (12 bytes)
  "ASEF"                     4 bytes
  major, minor               uint16 × 2
  block_count                uint32

BLOCK (repeated)
  type                       uint16   0xC001 group-start · 0xC002 group-end · 0x0001 colour
  length                     uint32   the body length — THE authority for every bounds check
  body                       `length` bytes
```

### Colour-entry body — the documented (`STANDARD`) layout

```
  name_length                uint16   UTF-16 code units, INCLUDING the trailing NUL
  name                       UTF-16BE, NUL-terminated
  model                      4 bytes  "RGB " | "CMYK" | "LAB " | "GRAY"
  channels                   float32 × {3, 4, 3, 1}
  color_type                 uint16   0 GLOBAL · 1 SPOT · 2 NORMAL
```

### Colour-entry body — the `NON_STANDARD_NAME_ENCODING` layout

Identical, **minus the `name_length` field**: the name is simply a NUL-terminated
UTF-16BE string. This is not a format variant anyone documents; it is what the one ASE
in `materials/` actually contains.

## The two-layout protocol

The parser is not permitted to guess which layout a block uses. It follows a fixed
order, and every step is validated against the block length the *file itself* declares.

1. **Try `STANDARD`.** If it parses **and consumes the declared body exactly**, done →
   the swatch is `TECHNICALLY_PARSED`.

2. **If the standard layout parsed but left bytes unexplained** → `PARSE_FAILED`. A
   reading that does not account for the whole block is not a reading.

3. **Try the fallback — but only when the standard layout is *provably* impossible.**
   Provable means: a declared field cannot fit inside the block, or parsing it would
   cross the block boundary. In the real file, `name_length` reads **80 UTF-16 units =
   160 bytes** inside a **48-byte** body. Not merely wrong — impossible.

4. **Accept the fallback only if ALL of these hold.** It consumes the declared body
   **exactly** · leaves **no unexplained bytes** · yields a **valid colour model** ·
   yields the **right number of channels** for that model · yields a **valid colour
   type** · and has **exactly one** valid interpretation.

5. **Otherwise → `PARSE_FAILED` + `REQUIRES_HUMAN`.** If both layouts look valid, if
   neither consumes the block exactly, if more than one fallback reading works, or if
   model/channel/type validation fails — the parser stops. It never picks the first
   reading that happens to work.

### Why step 5's ambiguity check is not paranoia

A block can genuinely have two exact readings. One channel float — `0.5` is
`0x3F000000` — **ends in two NUL bytes**, and the next float's bytes can spell a valid
model token. A parser that took the first NUL would silently choose one reading and
never know the other existed. `_ambiguous()` sweeps every NUL split, and refuses if
more than one survives validation. There is a fixture for exactly this.

## A fallback is itself a finding

**A file that needed the fallback can never be `TECHNICALLY_PARSED`.** It is capped at
`PARTIAL_PARSE` + `REQUIRES_HUMAN` and stamped with `NON_STANDARD_NAME_ENCODING` and
`NAME_LENGTH_FIELD_ABSENT`. Reading a file successfully is not the same as the file
being well-formed, and the distinction must survive into the record.

## Statuses

| Status | Meaning |
|---|---|
| `TECHNICALLY_PARSED` | every block parsed under the documented layout, nothing unexplained |
| `PARTIAL_PARSE` | parsed, but with a finding: a fallback was used, bytes trail, a block is truncated, the block count disagrees, groups are unbalanced |
| `UNSUPPORTED_BLOCK` | an unknown block type was found — **preserved, not interpreted** |
| `PARSE_FAILED` | the parser refuses to guess |

Capability is `DIRECT` only for `TECHNICALLY_PARSED`; everything else is
`REQUIRES_HUMAN`.

## What is preserved for every swatch

`source_offset` · `source_end` · `declared_block_length` · `body_sha256` ·
`bytes_consumed` · `unexplained_bytes` · `layout` · `fallback_used` ·
`standard_failure_reason` · the source file's SHA-256. An unknown block keeps its body
hash too — the bytes are never discarded just because they were not understood.

## Raw vs derivative

`raw` holds the source values and is marked `authoritative: true`. `normalized` holds
previews (sRGB, Lab), each with its `conversion_method`, library version, gamut and
clipping warnings, and a **capped confidence**. They live under separate keys and are
never merged. A preview never replaces the source representation.

Conversion methods are named so a reader always knows what produced a number:
`DIRECT_SOURCE_VALUE` · `sRGB_to_LAB_D65` · `NAIVE_CMYK_TO_SRGB_NO_ICC` (a preview, not
colour management) · `GRAY_TO_SRGB_LINEARLESS` · `NO_SAFE_CONVERSION`.

Lab is **not** converted to sRGB at all: it would need a gamut decision, and a
silently-clipped preview is worse than no preview.
