# DIP-0C2c — Known limitations

Standing limits, recorded so no later stage mistakes them for results.

## 1. EPS cannot be compared perceptually

Its TIFF previews are not decodable (and would not represent editable objects even
if they were). EPS candidates therefore get **no hash**: their relationships rest
on SHA / filename / folder / package evidence only and stay
`UNKNOWN_RELATIONSHIP`. A visual duplicate of an EPS is undetectable until
Ghostscript lands.

## 2. A logo element matching the background vanishes from the silhouette

The silhouette for an opaque image is a background-difference mask. An element the
same colour as the background is, by construction, invisible in it — a black mark
on a black field is genuinely not separable. Such a pair will show a *degraded*
silhouette match (measured: Hamming 9 vs a threshold of 8, i.e. just missed). This
is a real blind spot, not a tuning artefact.

## 3. Crop detection is coarse and will miss crops

Perceptual hashes are not crop-invariant, so a crop is proposed only when it
matches one of the parent's **region** hashes (halves, quadrants, centre). A crop
that does not align with one of those regions — an off-centre or oddly-shaped
sub-region — will simply **not** be detected. This is deliberate: the alternative
(guessing "crop" from a shared folder plus a different aspect ratio) is not visual
evidence and produced pure false positives.

## 3b. Large buckets are skipped by the blocker

A blocking bucket with more than 400 members is skipped entirely rather than
exploding into pairs. On the pilot no bucket comes close, but on the full
7,586-file library a very large folder or package would be compared **only** via
its pHash bands, not via its folder bucket. That is a real recall gap to address
before C2c is run at library scale.

## 4. Near-uniform and mostly-transparent images are undecidable

Their hashes collide with every other such image. They are capped at
`REVIEW_REQUIRED`. This means a genuine duplicate of two blank-ish assets will
*also* not be confirmed — the guard costs recall to buy precision, deliberately.

## 5. Rotation is only tested at 90° steps

Identity, mirror, 90°, 180°, 270°. Arbitrary rotations (e.g. 30°) and skews are
**not** detected.

## 6. Colour-only comparison is coarse

The palette signature is a 4×4×4 RGB histogram over the foreground. It will not
distinguish subtle tonal shifts, and it can be fooled by heavy compression
artefacts.

## 7. Components are a convenience, not a truth

A connected component is a *review grouping*. Weak bridges are split, but a chain
of genuinely-strong edges can still span a broader family than a human would draw.
The edges remain authoritative; the component is only a lens.

## 8. The pilot contains no true visual duplicate candidate pair

`LIKELY_NEAR_DUPLICATE` and `EXACT_VISUAL_DUPLICATE` are therefore **0 on real
data**, and those paths are proven only by synthetic fixtures. The cross-format
family *is* visually near-identical at source level (dHash 1 / pHash 2), but the
`.jpg` is segmented into stickers while the `.ai` is a single whole-page candidate,
so no candidate pair is a comparable unit — the link is recorded as **source**
evidence and deliberately not promoted to candidate equivalence.

## 9. Nothing here activates anything

An edge, a family or a canonical nomination grants no ownership, licence,
permission, retrieval eligibility, automatic use or brand status. Every member
keeps its own rights record, and final canonical selection is a human field.
