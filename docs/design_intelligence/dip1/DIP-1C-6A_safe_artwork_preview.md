# DIP-1C-6A — Safe In-Browser Artwork Preview

## The reviewer problem

DIP-1C-5C stalled on an honest gap. Descriptors must come from the artwork, but the review
page showed only hashes, machine labels and technical facts — so a reviewer had to leave the
platform, find the file on disk, and open Illustrator. Workable for ten items; not workable
at all beyond that, and it meant the system could never show *what* a reviewer had looked at.

This renders a bounded preview inside the review page. **It is presentation, not authority**:
not classification, not approval, not ownership, not licence, not permission. The source is
never modified and its bytes are never served.

## Renderer

**PyMuPDF 1.28.0 / MuPDF 1.29.0**, already a project dependency and already the DIP-0B
inspection tool. **No new dependency was installed.** Pillow 12.2.0 (also already present)
handles EPS-embedded previews and font specimens.

Capabilities were measured before choosing: Ghostscript, Inkscape, pdftoppm and ImageMagick
are all **absent**, so PDF-backed rendering through PyMuPDF is the only deterministic local
path. `sips`/`qlmanage` exist but are macOS-only and non-deterministic across machines, so
they were not used.

| Source | Path | Result |
|---|---|---|
| `.ai` / `.pdf` (PDF-backed) | PyMuPDF page render, scaled to bounds | works |
| `.ttf` / `.otf` / `.ttc` | Pillow glyph specimen, fixed text | works |
| binary `.eps` | embedded TIFF preview → Pillow | **fails on this corpus**, see below |
| ASCII `.eps` | — | no embedded preview; needs Ghostscript |
| anything else | — | `UNSUPPORTED_FORMAT` |

### The EPS limitation, measured not assumed

Binary EPS carries an embedded TIFF preview, and DIP-0C1 measured one in 412 of 536 files.
The block is self-contained (strip offsets are payload-relative — verified). But the two
curated-expansion EPS files in the pilot embed **palette TIFFs with an extra sample**, and
Pillow rejects that combination outright (`SyntaxError: unknown pixel mode`). Decoding it
would mean writing a raster decoder, which is well outside a preview slice.

Those items report `NOT_RENDERABLE` with the reason rather than showing a broken image. The
honest fix is the already-designed, deliberately-absent Ghostscript adapter (DIP-0C1 C1B) —
**a dependency requirement, reported rather than installed.**

## Source-root boundary

The browser never supplies a path. A `SourceArtifact.source_location` names a configured root
plus a repository-relative path, and resolution is server-side:

1. root name must be in `INTELLIGENCE_SOURCE_ROOTS`;
2. path normalized through the existing `normalize_relative_path` — rejects absolute paths,
   `..`, and ambiguous components;
3. path must sit under an allowed prefix (`INTELLIGENCE_ALLOWED_SOURCE_PREFIXES`);
4. `resolve()` follows symlinks, **then** containment under the root is re-checked — so a
   symlink pointing outside fails even though its own path looked contained;
5. file must exist and sit under a size bound.

A path is never trusted for merely being in the database.

## No raw source serving

There is no endpoint that returns an `.ai`, `.eps`, `.psd`, font, archive or arbitrary PDF.
Only generated PNG leaves the process, with `Content-Type: image/png`,
`X-Content-Type-Options: nosniff`, `Content-Disposition: inline`, an explicit
`Content-Length`, `Cache-Control: private, max-age=300` and `Referrer-Policy: no-referrer`.

## Preview identity

The cache key is a SHA-256 over: source artifact id · **source SHA-256** · evidence reference
id · locator schema version · page/artboard/face identity · renderer identifier · renderer
version · configuration hash. The configuration hash covers the PyMuPDF version, pixel
bounds, specimen text and output format.

Because the source hash is *in the key*, a preview generated from different bytes can never
be served as though it belonged to this version. The hash is additionally re-verified on
every fresh render (`HASH_MISMATCH` if it differs).

## Cache

`var/design_intelligence/previews/<key[:2]>/<key>.png` — inside the already-git-ignored
`var/`, never inside `materials/`, never committed. Writes go to a temporary file in the same
directory and are committed with `os.replace`, so a crashed or failed render cannot leave a
partial file. **A failed render never replaces a valid cached preview** — the cache is
written only after a successful render.

Bounds: 1400 px longest edge, 4 MP total, 6 MB per preview, 512 MB source ceiling.

**No migration.** Filesystem cache identity is sufficient because every field that would
belong in a preview record is already derivable from the `SourceArtifact` and
`EvidenceReference` rows, and the cache key binds them.

## Page/unit mapping

Each preview card is keyed to the same `EvidenceReference` list the checkboxes render, so a
reviewer can match a picture to a checkbox. `SOURCE_FILE`, `FILE_PAGE_UNIT` and
`ILLUSTRATOR_ARTBOARD` stay distinct, and the card states plainly when it is showing a page
view: *"This is a view of the page within the same source, not a separate original artwork."*

There is no per-unit crop: the `file_page/1.0` locator records `page` and `unit_key` but no
bounding box, so a unit's preview is its page. Claiming otherwise would present an extracted
region as a separate original.

## Access control

The existing `require_reviewer_action(REVIEW_EVIDENCE)` decorator, with the candidate's
`CorpusItem` as subject. Denied: unauthenticated, inactive, no reviewer profile, disabled
reviewer, unauthorized role. Actor and role are derived server-side and never read from the
request. **Operational `RETRIEVAL` permission is deliberately not required** — this is
internal review, not operational use.

URLs are not predictable-and-unauthenticated: the route needs both a candidate id and an
evidence id, and the evidence reference must belong to *that candidate's item*, so a
reference id from elsewhere returns 404 rather than reaching an unrelated source.

## Failure states

`AVAILABLE` · `NOT_RENDERABLE` · `SOURCE_UNAVAILABLE` · `HASH_MISMATCH` · `RENDER_FAILED` ·
`UNSUPPORTED_FORMAT` · `REVIEW_REQUIRED`.

An unavailable preview is *stated*, never shown as a broken image, and the page says that
visual review cannot be completed in the browser for that evidence. Technical evidence stays
fully available. The endpoint returns the bare status with HTTP 422 — no path, no stack
trace.

Status cards are computed **without rendering**, so a slow or failing source never blocks the
page.

## Pilot coverage — 47 of 49 evidence references

| Segment | Items | Refs | AVAILABLE |
|---|---|---|---|
| historical | 4 | 43 | **43** |
| c2_assets | 2 | 2 | **2** |
| fonts | 2 | 2 | **2** (specimens) |
| curated_assets | 2 | 2 | **0** — `NOT_RENDERABLE` |

Fonts render a fixed-text glyph specimen from the local file. The card states that it carries
**no licence finding and authorizes no production use** — possession is not permission, and a
specimen is not a licence.

## Limitations

* Two curated EPS assets cannot be previewed (above). Ghostscript would resolve it and is not
  installed.
* Page-level previews only; no per-unit crops, because no bounding box is recorded.
* No preview for archives, PSD, or non-PDF-backed `.ai`.
* The specimen text is fixed; no user-supplied string is ever rendered.

## No authority

A preview creates zero DecisionEvents, zero assertions, zero governance decisions, zero
permissions and zero candidate status changes. No "last viewed" or analytics state is
recorded. GET stays read-only. No external request of any kind is made — no OpenAI, no
rendering provider, no automated visual classification, no image embedding.
