# DIP-0C3a — Known limitations

## 1. An outlined wordmark is unreadable

5 of the pilot's files have **zero** live-text spans, so any wordmark is outlined
geometry. Their brand identity is **not machine-knowable** — including `logo.pdf`,
one of only two brand-master candidates. If a human cannot identify it by eye,
**DIP-0E (OCR) becomes the blocking dependency for the brand question.**

## 2. Brand names are matched against a KNOWN token list

Only BBROSE / ATC / JOJIA are recognised. A logo bearing some *other* brand will
come back `REQUIRES_HUMAN` with its text attached — correct, but it means an
unknown third-party brand is not automatically flagged as third-party.

## 3. No visual matching between logos

C3a compares geometry counts, spot inks and readable text. It does **not**
visually match two marks, so `POSSIBLE_LOCKUP_VARIANT` and
`POSSIBLE_COLOR_VARIANT` are weak by design and explicitly carry the contradiction
"the marks were NOT visually matched".

## 4. "Isolated logo" is a heuristic

It means *little geometry, no raster dependency*. It does not mean the artwork is
a logo. Two Queue-I assets (a background, a sticker sheet) satisfy it and are
plainly not logos — which is why nomination is role-gated.

## 5. C3a establishes no ownership at all

Not for BBROSE, not for ATC/JOJIA. `detected_third_party_brand` is **evidence**
that a third-party mark is present, not a determination of who owns the file.
Ownership is C3b, and its confirmed state is human-only.

## 6. The composition threshold is a heuristic

`>=60 % raster coverage AND >=5 embedded images`. Both BBROSE PDFs clear it by a
wide margin (80 %/81 %, 18/29 images), so the override is safe here — but a
borderline file could fall either side.
