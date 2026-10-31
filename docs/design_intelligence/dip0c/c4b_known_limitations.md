# DIP-0C4b — known limitations

## L1. The batch leverage is smaller than it first looked — and I overstated it
I initially claimed exact duplicates were safe as **one rights decision**. They are not.
Identical bytes prove identical *files*, never identical *rights* — rights attach to
provenance and acquisition. Corrected: duplicates are safe as one **technical identity**
decision, and rights stay provenance-aware.

The real number: **941 duplicate groups produce 1,880 provenance-rights subgroups, and
ZERO are rights-batchable**, because nearly every duplicate spans the unverified dump. The
942-file "saving" I reported was a technical saving only, and it bought no rights review
at all.

Realistically, a reviewer still faces roughly: **1 dump quarantine decision** (3,780 files,
if they accept it as one) + **46 package decisions** + **190 family-conflict reviews** +
**30 family × package conflicts** + **32 unparseable**. That is a few hundred decisions,
not four thousand — but it is not the handful the word "batch" might suggest, and the
single biggest one (quarantine the whole dump) is also the one carrying the most risk.

## L2. `SYSTEM_FONT_STATUS_UNCERTAIN` is now nearly empty, and that is honest
After the D2 fix it holds only faces that are byte-duplicates of a suspect without their
own name-table evidence. The 2,972 faces it previously held were there **because of their
folder**, which was wrong. The queue being small is the correct outcome, not a regression.

## L3. Vendor ID is four bytes of self-declared metadata
`MS`, `ADBE`, `MONO` are meaningful. `XXXX` (257 faces) and `\x00\x00\x00\x00` (143) are
not. A font can claim any vendor tag it likes. It is evidence, weighted below the
copyright string, and capped.

## L4. The foundry pattern list is hand-written
Eight foundries (Microsoft, Apple, Monotype, Adobe, Linotype, DynaComware, Ascender,
Founder) plus eleven vendor IDs. A system font from an unlisted foundry will not be
suspected. It errs toward **silence**, which means false negatives — a font we should
have questioned and did not. That is the safer failure for a *suspicion* engine, but it is
a real gap and C4c should not read "no suspicion" as "clean".

## L5. Licence classification is regex over the first 20 KB
It distinguishes OFL / Apache / MIT / EULA / personal-use / demo / stock-asset / readme /
URL-only. It will mislabel an unusual licence as `UNKNOWN_LICENSE_TEXT` (38 documents —
the largest category). **Unknown is not permissive**; those go to review like everything
else.

## L6. `mentions_fonts` is a keyword test, not comprehension
A licence that governs fonts without using the words *font*, *typeface*, *glyph*,
*opentype* or *truetype* would be wrongly flagged `EVIDENCE_MAY_NOT_COVER_FONTS`. That
errs toward review, which is safe — but it does mean the "only 72 of 97 mention fonts"
figure is a floor, not a precise count.

## L7. The 4,786 fonts with NO evidence are the real problem, and C4b does not solve it
Ninety-eight percent of the corpus has no licence documentation of any kind associated
with it. C4b can say so loudly; it cannot conjure evidence that does not exist. The
answer is either (a) BBROSE finds the paperwork, or (b) the library is quarantined and
rebuilt from fonts whose provenance is known. **That is a business decision, and it is the
most consequential one in DIP-0C4.**

## L8. Nothing is confirmed, and nothing is cleared
No ownership confirmed, no licence approved, no font recommended, no permission granted,
no file moved or deleted. Every conclusion here is a question with evidence attached. The
answers are a human's.
