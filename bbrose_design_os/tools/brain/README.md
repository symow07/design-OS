# THE BRAIN — §BH40 (v1, words) and §BH42(a) (v2, meaning)

A retrieval layer every executor session can call. **Derived, gate-checked, consulted by rule. Never
authoritative: every answer cites the file and line that owns the truth.**

- `sources.py` — the sources, enumerated one way for the rebuild, the freshness record and the gate test:
  the register `OWNER_BLOCKER_CLEARANCE.md` and the queue `OWNER_REVIEW_QUEUE.md`; the tracked sitting reports
  under `docs/design_intelligence/sittings/`; the WATCH notes under `docs/design_intelligence/watch/`; the
  launchers (the gate scripts under `bbrose_design_os/tools/`, the `LAUNCHER_*.md` and `NEXT_*_LAUNCHER.md` in `bbrose_design_os/docs/archive/launchers/`
  documents); `CLAUDE.md` and the executor's memory files under `~/.claude/projects/…/memory/` (by absolute
  path); the DIP-0A inventory and the tier record under the git-ignored `var/design_intelligence/audits/dip0/`
  joined to the grant rows of `apps/ire/materials_owner_grant.py` and `apps/ire/container_font_owner_grant.py`.
- `chunker.py` — the register and the queue chunked per §section (blocks, sub-blocks, lettered items); each
  chunk's status MEASURED from the register's own supersession idiom (§BH9(b): no in-place markers, the
  superseding section quotes the superseded passage): `LIVE`, `SUPERSEDED-BY §X` (a later sentence of the same
  file names the chunk whole as superseded), `UNCLASSIFIED` (a block that opens with no id — every block of the
  queue, which rules nothing); partial supersessions by quoting, quoted, conditional, negated and cross-file
  sentences are notes with their line; `ABSENT` (in `ruling`) for an id that heads no block, e.g. §BH11.
- `rebuild.py` — regenerates `var/brain/brain.sqlite` (SQLite FTS5: paragraph windows of every text source
  with file:line, one document per JSONL row, one per inventory row; the sections table; the materials join)
  and `var/brain/freshness.json` (the sha256 of every source at build time) in one run, atomically, in a few
  seconds. No tracked file carries a hash of the register.
- `embed.py` — §BH42(a), MEANING. Every indexed TEXT document (the register, the queue, the sittings, the
  launchers, the WATCH notes, the prompt files — not the materials rows, which the captions front answers)
  carries a 512-dimension vector in `var/brain/vectors.npy`. The model is DATA, never code: a vocabulary and
  a matrix in `var/brain/embed_model.npz`, written once by `export_embed_model.py` from a scratch environment
  so the suite's virtualenv gains no package. Inference is numpy and the standard library — normalise, split
  into word pieces, mean the rows, L2-normalise — and its agreement with the publishing library's own
  tokenizer was measured over the whole corpus, not asserted: 99.370% exact token-id agreement, document
  cosine mean 0.999996 at the library's own 512-piece window, worst case 0.995228. With no model on disk the
  index still builds and the layer reports itself `NO_MODEL`. The rebuild bound is five minutes (§BH42(a)
  raised it from two); the whole rebuild measures about 31 s, of which the vectors are about 28 s.
- `export_embed_model.py` — puts that model under `var/brain/`. Run it from a scratch environment with no gate
  running, as its header says.
- `caption_scope.py` — §BH42(b)+(c), CAPTIONS. The ruled scope is read from the records that define it —
  the 254 design files listed in `docs/design_intelligence/sittings/bh38/design_pdfs.json` and the PRODUCTION
  rows of the tier record — never re-derived (re-deriving from the inventory returns 258 and sweeps in a
  licence agreement that is not a design). 395 paths, 389 distinct contents: six pairs are the same bytes
  under two names, so the content is captioned once and every path that carries it is recorded. Each image is
  rendered locally (pymupdf, else pillow) and its DOMINANT PALETTE IS MEASURED from the rendered pixels — ΔE76
  ≤ 8, §BH38's idiom for this same corpus — never asked of the model, because a hex a model names is a guess.
  A file no local renderer opens is UNCAPTIONABLE with both renderers' reasons, named rather than skipped (5:
  four `.eps` needing Ghostscript, one `.psb`). **Captions are DERIVED and machine-written: evidence of
  nothing about rights.** **The spend is bounded and declared**: a sample is captioned first, the total is
  projected from it, and a projection over the cap REFUSES — the run does not begin without the owner's word.
  Measured: 10 images at $0.0243, projecting $0.95; 384 contents captioned for **$0.9816** against the $50
  cap, no caption errors. Output: the git-ignored `var/brain/captions.json`.
- `server.py` — a local MCP server (stdio, JSON-RPC 2.0, standard library only) with four tools under the
  server name `brain`, so a session sees `brain.search`, `brain.ruling`, `brain.material`, `brain.lessons`:
  `search` (TWO rankings returned together — full text over everything, and meaning; every hit carries `found_by` = `fts` | `semantic` | `fts+semantic`, the full-text hits are kept in their own order and the semantic ranking is beside them, never in place of them, so a hit only meaning found says so), `ruling` (a §section → text, status, line range,
  what supersedes it and the notes against it; `ABSENT` with every mention cited when no block carries the
  id), `material` (the inventory ⋈ tier record ⋈ grants ⋈ §BH42(b) captions, by path fragment, sha256, family, WHAT THE IMAGE SHOWS or a palette colour — tier, tier
  source, evidence, grant, census metadata; no bytes, no locator beyond the repo-relative `materials/` path:
  the §BH39(d) retrieval interface implemented; a row outside the three governed folders is
  `NOT_IN_TIER_RECORD`. §BH42(d): a query of WORDS is answered from the captions by BOTH rankings — the
  caption text and the same vectors `search` uses — and a `#RRGGBB` query is answered from the MEASURED
  palettes within ΔE76 ≤ 12, every row saying which found it. Every row also carries a `placement` verdict:
  only a PRODUCTION row may be placed, and anything else says its bytes may not be, whatever its caption
  says — the §BH37/§BH39 line held inside the brain), `lessons` (first the documents flagged as lessons — the sittings' stop reports,
  refusals and scores, register and queue paragraphs carrying refusal, defect, instrument or hard-stop
  vocabulary — then any register or queue paragraph that matches; by keyword and by pin class). Wired by the
  project `.mcp.json`. The server opens the index read-only and writes nothing anywhere.

Rebuild:

    bbrose_design_os/venv/bin/python bbrose_design_os/tools/brain/rebuild.py

The freshness gate (§BH40(d)) refuses a commit when `var/brain/freshness.json` disagrees with the sources on
disk; `guarded_commit.sh` runs the rebuild before the suite. Consulted by rule (§BH40(e), `CLAUDE.md`):
before proposing, `brain.lessons`; before claiming an asset absent, `brain.material`, the query stated;
before citing a §section, `brain.ruling`, its status cited.
