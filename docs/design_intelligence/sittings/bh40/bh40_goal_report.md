# §BH40 GOAL REPORT — THE BRAIN, v1

Owner goal §BH40 (OWNER_BLOCKER_CLEARANCE.md:20015–20120; T40 landed d058685, 8/8). The front was interrupted
after (a)'s second attempt by the flush deadlock (the arc's third infrastructure refusal → §BH41, root-caused and
fixed at 6ad65f0) and resumed at (a) with the restored import, as the owner's sentence ordered. Order executed as
typed: transcription → (a) → (b) → (c) → (d) → (e) → this report. Every commit predicted (§AD0(a), sealed before
git add) and scored after; the seals in `~/bh40_work/seals.txt`, the scores in `score_*.txt`.

## The chain
| commit | concern | score |
|---|---|---|
| d058685 | T40 transcription | 8/8 |
| da56c06 | (a) the sitting reports imported, one atomic commit (298 paths; attempt 1 6/8 unlaunched, attempt 2 refused by the deadlock → §BH41, attempt 3 landed) | 8/8 |
| bcb7eca | (b) the index and the rebuild (sources.py, chunker.py, rebuild.py) | 8/8 |
| c00f2b3 | (c) the server and .mcp.json | 8/8 |
| 9f75253 | (d) the freshness gate (the test in the apps leg + the rebuild step in guarded_commit.sh) | 8/8 |
| 0d210d5 | (e) CLAUDE.md created at the git root, the three standing lines | 8/8 |

## (a) THE SOURCES
**The import** (`~/bh40_work/import_sittings.py`, preview sealed c4f7f7c896ceb377, the same 298-file content at
attempts 2 and 3): 697 files under `~/bh*_work/` examined by rule. COPIED 288 — reports 28, measurements 88,
predictions 89, scores 56, stop reports 13, renders 9 (png, small), refusals 3 (tracked as `<name>.log.txt`
because the outer `.gitignore:13` refuses `*.log`), launchers 2. REDUCED 9 — 8 measurements and `bh35_report.md`
(its line 118 listed a quarantined zip's internal entries; the text reduction `bh35_report.reduced.md` carries the
report without them). EXCLUDED 400 — not-text 115, run logs 93, commit messages 76, transcription drafts 45, exit
codes 34, instruments 12, drafts 9, process listings 7, empty 5, quarantine records 3, an instrument cache 1. The
298 paths (297 content files + `INDEX.json`, record `sittings_import/1.0`) landed under
`docs/design_intelligence/sittings/<goal>/` in one atomic commit — the executor's stated choice — 564,839
insertions, no font or material bytes (0 forbidden extensions), 0 quarantine-content lines, 0 register-hash hits,
all measured before the write and re-measured at HEAD (297 content files re-hashed == their manifest sha256).

**The register chunked** (`tools/brain/chunker.py`): 834 sections — 110 level-2 blocks, 420 level-3, 304 level-4
— each with its line range and its status MEASURED from the register's own supersession idiom, never inferred:
819 LIVE; 1 SUPERSEDED-BY §AI (the AD6(d) block at :2853–2873, superseded at :3889); 14 UNCLASSIFIED (sub-headings
that carry no §id — the six sprint-precedent sections at :555–1336, two "HARD STOPS AND THE QUEUE, AS TYPED"
sub-headings, five "Executor's reading" sub-headings, one "3d." sub-heading — the status lives on their parent
blocks). 149 supersession sentences read; partial, quoted, conditional and negated supersessions kept as NOTES on
the target (§BH24's retirement by §BH41(4) is one such note: the register's sentence is conditional, so §BH24
measures LIVE with the note, not SUPERSEDED-BY). 17 unresolved targets — ids a sentence names as superseded or
adopted that head no block of their own (§A9, §A10, §A11, §B3, §B5, §B6, §BH1, §BH11, §C4, §C9, §Q4) — recorded
in the index's meta, resolved nowhere. 6,795 §-mentions indexed (id → the line that mentions it), which is how
`ruling` answers ABSENT for §BH11 with every mention cited. **The queue** (`OWNER_REVIEW_QUEUE.md`): 556 chunks,
all UNCLASSIFIED — the queue carries no supersession idiom to measure, and the ruling says UNCLASSIFIED when
unmeasurable.

**The other sources** (`tools/brain/sources.py`, one enumeration for the rebuild and the freshness record): the
WATCH notes (179 docs), the launchers (312 docs), CLAUDE.md and the executor's memory files (119 prompt docs), and
the DIP-0A inventory joined to the tier record and the grant rows — 12,473 material records: 141 PRODUCTION by
OWNER_GRANT, 4,691 REFERENCE by MACHINE, 7,641 with no tier row (the inventory is wider than the tier record;
`material` answers tier null for them, with the inventory line cited); 190 rows carry a grant cite, 4,794 a family
name from the fonts census. Sources enumerated at the last rebuild: 415 (414 + CLAUDE.md from (e)).

## (b) THE INDEX
`tools/brain/rebuild.py` regenerates `var/brain/brain.sqlite` (SQLite FTS5, external-content table over the docs)
and `var/brain/freshness.json` (`brain_freshness/1.0`, every source path with its sha256, the record written LAST)
atomically (tmp + rename) in one run. **Rebuild time, stated before the wiring as ruled: 2.56–2.80 s** across
every run (2.64 s inside the (d) gate, 2.70 s inside the (e) gate) against the ruled 120 s bound. Contents at the
last rebuild: 43,758 docs (sitting 29,340; record 12,473; register 822; queue 513; launcher 312; watch 179;
prompt 119), 834 + 556 sections, 12,473 material rows, 1,176 docs flagged as lessons by vocabulary, 76.9 MB.
`var/` is git-ignored: the index and the record are derived, untracked, and **no tracked file carries a hash of
the register** (git grep for the register's sha256[:16] at every HEAD of the chain: 0; the hash lives only in the
untracked record).

## (c) THE SERVER
`tools/brain/server.py` (185 lines, standard library only — JSON-RPC 2.0 over stdio, the database opened
`mode=ro`, nothing written), server name `brain`, four tools: `search` (FTS over everything, ranked, file:line
cited), `ruling` (a §section → its text, measured status, line range, what supersedes it, the notes against it;
ABSENT with every mention cited for an id that heads no block), `material` (the inventory joined to the tier
record and the grants by path fragment, sha256 or family — tier, tier source, evidence, grant, census metadata;
no bytes, no locator beyond the repo-relative `materials/` path: the §BH39(d) retrieval interface implemented),
`lessons` (stop reports, refusals, scores, defect classes and instrument errors by keyword and by pin class).
Wired by the project-scoped `.mcp.json` at the git root. Smoke-tested over stdio (`~/bh40_work/mcp_client.py`);
the server's sources' hashes were unchanged across its calls (it writes nothing). Reading recorded: Claude Code
exposes them as `mcp__brain__search` etc. — the API's tool-name grammar admits no dot, so the goal's
`brain.search` is read as server `brain`, tool `search`.

## (d) THE FRESHNESS GATE
`BrainFreshnessGateTests` (four tests) in `apps/pipeline/tests/test_two_roots_collision_guard.py` — an existing
collected file, so the suite manifest and the protocol identity did not move — loads `tools/brain/sources.py` by
file path from the git root and refuses when the on-disk record disagrees with the current hashes: a source
changed, a source appeared, a source vanished, or no record at all, each named (SOURCE_CHANGED / SOURCE_NEW /
SOURCE_GONE / NO_FRESHNESS_RECORD). **The negative control, measured before the seal:** with `BRAIN_DIR` pointing
at a stale record the test FAILED by name; the live record itself was stale at rehearsal (SOURCE_CHANGED on the
executor's memory file and on `guarded_commit.sh` just edited) and FAILED by name; after one rebuild (2.62 s) the
four tests passed twice. `guarded_commit.sh` runs the rebuild before the tier-1 suite the way it appends the
ledger: its own output artifact (`.brain_rebuild_output`, in the inner `.gitignore`), its true exit code honoured,
a failing rebuild refusing the commit, the step skipped only when `SUITE_CMD` is overridden (the gate's nested
dry-runs), so no rebuild runs under a running gate. The (d) gate was the first to run it: `BRAIN_REBUILD_OK
seconds=2.64` is line 2 of its log, before the suite line, and the freshness test passed against the record that
step wrote; the gate's ledger append came after the rebuild and the test still passed — the ledger is not a source.
GuardedCommitTests (6) green with the step in place; claim_scan clean on the modified instrument.

## (e) CONSULTED BY RULE
0d210d5 — `CLAUDE.md` CREATED at the outer root (no CLAUDE.md existed at either root or at `~/.claude`, measured
before the copy; "gains three standing lines" executed as a creation, recorded as reading 8 below): 7 lines — a head
naming the server, its four tools and the rebuild command, and the three standing lines as executor text under
§AZ0(u) (annotate, never rewrite): before proposing, query `brain.lessons` (by keyword and by pin class) and read
what it cites; before claiming an asset absent, query `brain.material` and state the query in the claim; before
citing a §section, query `brain.ruling` and cite its measured status with the section. The gate's rebuild step
enumerated the file as the 415th source and the freshness test passed against that record; the fresh-session
re-proof below ran with this CLAUDE.md loaded. The file carries no register hash and none of the seven phrases.

## THE GOAL STATE — a fresh Claude Code session, four calls, matched by hand
**The fresh session** (`~/bh40_work/proof_fresh_session.sh` → `c_proof_fresh_session.json`): `claude -p` from the git root with the tracked `.mcp.json` (`--strict-mcp-config`), no prior context, 6 turns, no permission denials, cost $0.44. Its four answers, verbatim:

```
1.
status: ABSENT
mentions[0].cite: OWNER_BLOCKER_CLEARANCE.md:14571
mentions[1].cite: OWNER_BLOCKER_CLEARANCE.md:14575

2.
hits[0].cite: OWNER_BLOCKER_CLEARANCE.md:20047-20086
hits[1].cite: OWNER_BLOCKER_CLEARANCE.md:20087-20116
hits[2].cite: OWNER_BLOCKER_CLEARANCE.md:16805-16824
snippet (cite OWNER_BLOCKER_CLEARANCE.md:16805-16824):
```
 … The DIP-0A inventory
>     relabelled OFL.txt-class files as LICENSE_EVIDENCE — search by
>     class AND by filename, state both search extents in the report
>     ([search-key-shape] class: two shapes minimum … 
```

3.
relative_path: materials/17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/BATH OIL/bath oil lorenza.ai
tier: PRODUCTION
tier_source: OWNER_GRANT
evidence: docs/design_intelligence/dip0a/own_work_declaration_bh39.json sha256:06d9cfcc324935898d0eaea4f0b7fbf0b901b231d3847cf536523cf84598943a
grant_terms_class: OWNER_DECLARATION

4.
status: LIVE
cite: OWNER_BLOCKER_CLEARANCE.md:18811-18926
superseded_by: null
supersession_notes count: 3
text first line: ## 2026-09-04 — OWNER RULING §BH32(h): the (e) hard stop ruled — NARROW THE LAYER'S SCOPE: the theme is the default only for surfaces carrying no owner-ruled typography evidence; a path-literal exemption list (the nine WI evidence surfaces by emitter entry point, the 2A-7 confirmed-concept golden path, the regulatory sticker) resolving exactly as at 41604ac; the 70 WI pins, 3 golden baselines and the sticker test pass UNCHANGED; the §BH26 call-site proofs re-anchor to a ruled skipped-candidate contract; the sticker finding and the EAN widget queued; the four repairs ratified; the exercise documents non-exempt
```

**Matched by hand against the register at HEAD:**
- §BH11 → ABSENT; `OWNER_BLOCKER_CLEARANCE.md:14571` reads `**§BH11 IS SKIPPED, AND IT IS LEFT SKIPPED.**` and `:14575` `the ruling is transcribed at the number he typed. **No §BH11 is invented to fill` — the skipped letter, cited from the §BH12 block.
- "search-key-shape" → the hit `OWNER_BLOCKER_CLEARANCE.md:16805-16824` is the §BH25 goal (1) window; its lines 16811–16814 read `search by class AND by filename, state both search extents in the report (search-key-shape class: two shapes minimum, counts reconciled)` — the rule, in the owner's words. The two hits ranked before it are the §BH40 goal text and the transcription's reading, which name the lesson by its key; they are flagged as lessons by their vocabulary.
- bath oil lorenza.ai → PRODUCTION, OWNER_GRANT, evidence `docs/design_intelligence/dip0a/own_work_declaration_bh39.json sha256:06d9cfcc…`, OWNER_DECLARATION — the §BH39(c) ruling (52 of the 53 LORENZA files PRODUCTION by declaration; the withheld PSD answers REFERENCE).
- §BH32(h) → LIVE, `OWNER_BLOCKER_CLEARANCE.md:18811-18926`, nothing supersedes it, three notes (a partial supersession by §BH33 at :19041 — §BH33(1) supersedes rows of the Arabic chains — and two mentions in §BH40 at :20102); the first text line is the register's line 18811 verbatim, and the server's full text equals the register's lines 18811–18926 byte for byte (measured over stdio).


**The freshness gate, proven both ways.** A stale record is refused by name — the live control at rehearsal
(SOURCE_CHANGED on the executor's memory file and on `guarded_commit.sh` itself) and the synthetic controls (one
source's hash altered; a record naming no source; no record at all: BRAIN_STALE / NO_FRESHNESS_RECORD) — and a
fresh record passes (the four tests twice after one rebuild, then inside the (d) and (e) gates against the record
the step wrote). **Rebuild time:** 2.56–2.80 s on this content (2.64 s inside the (d) gate, 2.70 s inside the (e)
gate) against the ruled 120 s bound — stated before the wiring, as ruled. **Gate GREEN at every commit**
(TIER_2=GREEN, failures=0; collected 8,594 → 8,598 when the four freshness tests joined the apps leg).
**Worktree clean** at 0d210d5 (porcelain empty; `var/brain/` untracked by rule). **Every commit
predicted-then-scored:** six seals in `seals.txt` before git add, six scores of 8/8 on the landed commits; (a)'s
two earlier attempts scored as history (6/8 unlaunched; refused by the deadlock). **The fresh-session proof
repeated at the final HEAD** (`~/bh40_work/e_fresh_session.json`: `claude -p` from the git root over the tracked
`.mcp.json`, 6 turns, no denials, $0.41) returned the same four answers value for value, the register unchanged
since the first proof (20,213 lines, db241ccf0b258e35).

## Readings for the owner's word (recorded, not resolved; the owner's sentence governs each)
1. **Tool names.** The goal names `brain.search`, `brain.ruling`, `brain.material`, `brain.lessons`. Claude Code
   exposes an MCP server's tools as `mcp__<server>__<tool>` and a tool name admits no dot, so the server is named
   `brain` and its tools `search` / `ruling` / `material` / `lessons`; the dotted names in the goal are read as
   server.tool. The README and CLAUDE.md say so.
2. **§BH24 after §BH41(4).** The register's sentence retiring §BH24's bounded re-runs is conditional ("once (3)
   lands"), so the chunker records it as a CONDITIONAL note on §BH24 and §BH24 measures LIVE with that note, not
   SUPERSEDED-BY §BH41 — measured from the idiom, as ruled, never inferred. One unconditional sentence in the
   register would move it.
3. **7,641 inventory rows without a tier row.** The DIP-0A inventory (12,473 files) is wider than the tier record
   (4,832 rows); for the difference `material` answers tier null / tier_source null with the inventory line cited.
   A reading, not a defect: those files were never admitted or refused.
4. **The lessons ranking.** `lessons` ranks FTS matches by bm25; for "search-key-shape" the §BH40 goal text and its
   transcription (which name the key densely) outrank the §BH25 window that owns the rule, which is hit 3. Weighting
   by source kind is v2 work, not done here.
5. **The queue's 556 chunks are UNCLASSIFIED** and the register's 14 id-less sub-headings likewise — "UNCLASSIFIED
   when unmeasurable", as ruled; the parent block carries the status for the sub-headings.
6. **The 17 unresolved supersession targets** (§A9, §A10, §A11, §B3, §B5, §B6, §BH1, §BH11, §C4, §C9, §Q4) are ids a
   sentence names that head no block; recorded in the index's meta, resolved nowhere.
7. **The memory files are machine-local sources**, indexed by absolute path under `~/.claude/projects/…/memory/`.
   On another machine the record reports them SOURCE_GONE and the gate refuses until a rebuild there — by design
   (the ruled behaviour outside a gate is: run the rebuild).
8. **CLAUDE.md was CREATED, not "gained".** No CLAUDE.md existed at either root or at `~/.claude` (measured); the
   file at the outer root carries a one-line head naming the server, its tools and the rebuild command, and the
   three standing lines, under §AZ0(u) (annotate, never rewrite).
9. **The interactive approval prompt.** A project-scoped `.mcp.json` server asks for the owner's approval once in
   an interactive session; the fresh-session proof ran non-interactively with `--strict-mcp-config`, where no
   prompt appears. The owner will see the prompt on first use.
10. **The five screenshot-capture harnesses** were swapped to the drained live server under §BH41 and are unchanged
    by this front; the brain indexes their tests' evidence only through the sitting reports.
11. **v2** (embeddings, vision captions for the renders and the materials) is the next goal, not this one; nothing
    of it was started.

12. **Evidence that postdates the import.** The (a) import's content was frozen at its sealed preview (attempt 2,
    before §BH41); everything written since sits under `~/bh*_work/` and is not yet tracked: the whole of
    `~/bh41_work` (417 files, 0 in `INDEX.json` — the deadlock's captures, the pg_locks samples, the controls, the
    §BH41 goal report) and 54 later files under `~/bh40_work` (20 of them scores, predictions, reports and the
    seals — this report among them). A goal's own report is written after its import, so no import holds its own
    goal's report; the next front's import (or a one-commit top-up on the owner's word — same script, same rules,
    preview sealed as the prediction) brings them in. Not launched here: (a) sits before (b) in the ruled ORDER and
    the sentence named one import.

## Hard stops (as typed) — none fired in the resumed run
A tool contradicting the register at HEAD: none (the four goal answers matched by hand; the server's §BH32(h)
text equals the register's lines byte for byte). A brain write to a source: none (the sources' hashes unchanged
across the server's calls; the rebuild writes only `var/brain/`). A tracked register hash: none (git grep at every
HEAD: 0). Rebuild > 2 min: 2.56–2.80 s. An import copying quarantine content or material bytes: none (0 forbidden
extensions, 0 quarantine-content lines; the one quarantine listing reduced to text). The one hard stop that fired
in this goal's first run — the flush deadlock refusing (a)'s second attempt — became §BH41 and was cleared there.
