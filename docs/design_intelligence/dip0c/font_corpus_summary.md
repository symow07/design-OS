# Font corpus summary

## Six layers, never conflated

| Layer | Established by | Confers |
|---|---|---|
| technical identity | SHA-256 | **nothing about rights** |
| family grouping | name ID 16 / 1 + corroboration | nothing about rights |
| source provenance | package, path, acquisition | the *basis* for a rights question |
| licence evidence | a document, read | nothing — evidence is not approval |
| human rights decision | an authorised human | settles the question |
| operational permission | granted per flag, by name | *what the system may do* |

**No layer grants the one below it.** A family is not a licence. A licence is not a
permission. Identical bytes are not identical rights.

## Scale

| | |
|---|---|
| font files | **4,883** (2.2 GB) |
| unique by SHA-256 | **3,941** |
| font **faces** | **3,966** — *a file is not a font* |
| technical families | **2,832** |
| source packages | **47** (46 credible + 1 duplicated dump) |
| technical duplicate groups | 941 |
| provenance-rights subgroups | **1,880** |
| rights-batchable duplicate groups | **0** |

## The corpus is two populations

**4,715 of 4,883 files** live in `Fonts/` + `Fonts/3333/` — and `Fonts` is **92.5%
byte-identical** to `Fonts/3333`. One dump, twice. It holds essentially **no licence
evidence**.

The **46 `DOWNLOADE 2026` packages** (~168 files) are the only credible rights batches —
and they hold **all** the licence evidence there is.

## Formats and health

`.ttf` 3,686 · `.otf` 1,116 · `.fon` 38 (**unsupported**) · `.ttc` 38 → 85 faces ·
`.woff`/`.woff2` 5. **32 unique `.fon`** cannot be parsed at all; **0** parse failures.

## Scripts

Dominant: latin 3,120 · arabic_presentation_b 248 · cjk 107 · thai 33 · arabic 29 ·
hangul 19. (The CJK figure is only correct because C4a fixed the BMP-only script ranges —
`mingliub.ttc` was reporting as *latin* on the strength of 165 Latin glyphs while carrying
42,711 CJK Extension-B codepoints.)
