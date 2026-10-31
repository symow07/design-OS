# DIP-0A — Inventory record schema

One JSON object per file, one per line, in
`var/design_intelligence/audits/dip0/inventory/inventory.jsonl` (flattened
companion: `inventory.csv`). Every record preserves its project-relative
`materials/...` path, so it traces back to its source file.

## Provenance envelope

Every **machine-inferred** value is an envelope, never a bare scalar:

```json
{
  "value": "HISTORICAL_DESIGN",
  "source": "path_rule",
  "evidence": ["under materials/historical AI production designs", "ext=.ai"],
  "confidence": 0.95,
  "extracted_at": "2026-07-10T01:52:07+00:00",
  "parser": "dip0.classify/0.1.0"
}
```

`source` ∈ `path_rule` · `filename_rule` · `extension_rule` · `extension_fallback`
· `folder_hint` · `magic_bytes` · `file(1)` · `mimetypes` · `folder_evidence` ·
`no_rule_matched` · `default` · `absent`.

**Machine inference and human curation never share a key.** Human values live in
a separate `human_confirmed` block that machine code never writes.

## Fields

| Field | Type | Notes |
|---|---|---|
| `relative_path` | str | Always `materials/…`, forward slashes. The join key. |
| `filename`, `extension` | str | Extension lowercased, `""` if none. |
| `size_bytes` | int | From `stat`. |
| `sha256` | str | Streaming SHA-256 of the original bytes. |
| `mtime_iso`, `mtime_ns` | str, int | Modification time. |
| `signature_kind` | *envelope* | Magic-byte class: `pdf`, `postscript`, `eps_binary`, `psd`, `png`, `jpeg`, `webp`, `tiff`, `gif`, `avif`, `zip`, `sfnt_otf`, `sfnt_ttf`, `ttc`, `woff`, `woff2`, `mz_exe`, `mp4`, `svg_xml`, `unknown`. |
| `mime_detected` | *envelope* | From magic bytes; falls back to `file(1)`, then extension guess. |
| `parser_support` | obj | `{status, parser}`. `status` ∈ `supported` · `partial` · `archive` · `evidence` · `unsupported`. |
| `category` | *envelope* | See taxonomy below. |
| `category_subtype` | str? | e.g. `FONT_METADATA`, `SWATCH_FILE`. |
| `associated_branch` | str? | e.g. `materials/Fonts` for font metadata. |
| `posture` | obj | `{knowledge_class, excluded_from_retrieval_by_rule, retrieval_allowed, automatic_use_allowed, reason}`. |
| `ownership_status` | *envelope* | `LIKELY_BBROSE_UNCONFIRMED` · `UNCONFIRMED_THIRD_PARTY` · `UNKNOWN`. |
| `excluded_from_brand_retrieval` | bool? | Present and `true` only for third-party marks. |
| `license_status` | *envelope* | `UNVERIFIED` · `PENDING_HUMAN_CONFIRMATION`. Confidence pinned to `0.0`. |
| `license_evidence` | list | `{path, filename, strength, scope, distance}`. `scope` ∈ `same_dir` · `ancestor_dir`. |
| `license_evidence_strength` | str | `strong` · `weak` · `none`. |
| `font` | obj? | Present for fonts: `{parsed, parser, faces[]}`. |
| `font_posture` | obj? | `{license_status, source_classification, review_required, automatic_use_allowed, embedding_allowed, redistribution_allowed, quarantined}`. |
| `archive` | obj? | Present for zips: `{readable, encrypted, corrupt, empty, entry_count, expanded_bytes, expansion_ratio, suspicious[], manifest_sha256}`. |
| `duplicate_group` | str? | `dup-NNNN`, or `null`. |
| `review_required` | bool | |
| `review_reasons` | list[str] | e.g. `font_license_unverified`, `ownership_unconfirmed`, `archive_contents_unverified`, `palette_unparsed_and_ownership_unconfirmed`, `parser_partial`, `has_warnings`. |
| `warnings` | list[str] | e.g. `signature_ext_mismatch`, `legacy_postscript_ai`, `archive_empty_failed_download`. |
| `human_confirmed` | obj | `{category, license_status, ownership_status, reviewed_by, reviewed_at, notes}` — all `null`/`""` until a person edits them. |

### Font face record (`font.faces[]`)

`family`, `subfamily`, `full_name`, `postscript_name`, `version`,
`typographic_family`, `typographic_subfamily`, `license_description` (nameID 13),
`license_url` (nameID 14), `weight_class`, `width_class`, `vendor_id`, `italic`,
`units_per_em`, `glyph_count`, `scripts[]`, `variable`, `variable_axes[]`,
`fs_type_raw`, `fs_type_meaning`, `no_subsetting`, `bitmap_embed_only`.

`fs_type_*` records the foundry's embedding **permission hint**. It is evidence,
never a rights grant. `parsed` is true only when a usable *identity* was
recovered (a name table), not merely because the file opened.

## Taxonomy

**Knowledge classes** — `HISTORICAL_DESIGN`, `REUSABLE_VECTOR_ASSET`,
`RASTER_DESIGN_ASSET`, `BACKGROUND`, `PATTERN`, `MOTIF`, `ICON`, `BRAND_MASTER`,
`LOGO`, `FONT`, `COLOR_PALETTE`, `PHOTOGRAPHY_REFERENCE`, `PRODUCT_REFERENCE`,
`DIELINE_REFERENCE`.

**Not knowledge classes** (`excluded_from_retrieval_by_rule = true`) —
`ARCHIVE`, `LICENSE_EVIDENCE`, `SUPPORTING_METADATA`, `OUT_OF_SCOPE`, `UNKNOWN`.

Nothing in DIP-0A is `retrieval_allowed`: the retrieval contract does not exist
until DIP-1. `posture.reason` distinguishes *excluded by rule* (permanent) from
*gated pending a contract* (`COLOR_PALETTE`, `FONT`).

## Classification rule order

First match wins; each records its own evidence.

1. licence/readme/EULA/terms material → `LICENSE_EVIDENCE` (strength graded)
2. `.zip` → `ARCHIVE`
3. out-of-scope: non-design extensions, then path rules, then unrelated-subject mockups
4. fonts (quarantine branch first), then `COLOR_PALETTE`, then `SUPPORTING_METADATA`
5. brand / third-party marks — **filename evidence only**, master extensions only
6. historical production designs (`materials/historical AI production designs/*.ai`)
7. folder-name hints — *hints, never truth*, confidence capped at 0.55
8. structural fallback by media type (vector / raster), confidence 0.4
9. `UNKNOWN`, confidence 0.0

Extension-driven rules (4) precede folder hints (7) so a swatch in a
`*-background/` folder is not misfiled.

## Reproducing

```bash
bbrose_design_os/venv/bin/python -m tools.dip0.run --full-hash-verify --milestone
bbrose_design_os/venv/bin/python -m pytest tools/dip0/tests -q
```

Exit code is non-zero if the source tree changed, a hash drifted, or the output
root resolved inside `materials/`. `reports/divergence.json` compares each run to
the recorded counts instead of silently absorbing drift.
