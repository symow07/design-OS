# DIP-0C3b3 — known limitations

## L1. RESOLVED — canonical approval is now under DUAL CONTROL
This was an open question at review; the business has answered it. A canonical master
now requires **two attestations from two distinct people**, and the rule is enforced
in `check_canonical_approval()` *and* again at the point of recording in `ledger.event()`.
See `c3b3_canonical_and_permissions.md` §3. The residual risk is L2 below: the
distinctness we enforce is between asserted actor IDs, not between authenticated
humans.

## L2. Actor identity is asserted, not authenticated — and dual control leans on it
Carried over from C3b2, but it now carries more weight. Dual control requires
`technical_reviewer_id != legal_reviewer_id`, and those IDs are **supplied by the
caller**. The event model refuses an approval that only one *named* actor touched; it
cannot yet tell whether one human is behind two names. Real authentication is DIP-1,
and until it lands, dual control is a strong procedural control rather than a
cryptographic one. Worth stating plainly rather than overselling.

## L3. Scope overlap is exact-match on strings
`scopes_overlap()` compares brand, lockup, product and market identifiers as exact
strings. `"EU"` and `"Europe"` do not overlap; `"EU"` and `"FR"` do not overlap even
though France is in the EU. A market taxonomy with containment (EU ⊃ FR) is not
modelled, so a canonical master scoped to `["FR"]` will **not** conflict with one
scoped to `["EU"]` — and it probably should. Until a taxonomy exists, scope lists
should use one consistent level of granularity.

## L4. Periods are compared as ISO strings
`_periods_overlap()` relies on ISO-8601 timestamps sorting lexicographically. This
holds for the `+00:00` timestamps the ledger writes, but a mixed-offset timestamp
(`+02:00`) would compare wrongly. All ledger timestamps are UTC today; nothing yet
*enforces* that at the schema level.

## L5. No permission is scoped to a *purpose* at evaluation time
A grant records its `purpose`, and `check_grant()` requires one for purpose-bound
flags — but `effective_permissions()` filters on brand, product and market only. A
grant made for `internal_design` will evaluate as effective for any caller who does
not say why they want it. Purpose-scoped evaluation is deferred; it needs a calling
convention that carries purpose, which is a DIP-1 API question.

## L6. Expiry has no warning window
A permission is fully effective the moment before its review date and fully denied the
moment after. There is no "expires in 14 days" state to drive a review queue, so a
lapse is discovered by denial rather than anticipated. `detect_expired()` gives
C3b4 what it needs to build that queue; the warning window itself is not in C3b3.

## L7. Deprecation and replacement events exist but have no workflow
`CANONICAL_MASTER_DEPRECATED`, `CANONICAL_MASTER_REPLACED`, `VARIANT_RECLASSIFIED`
and `SCOPE_REDUCED` are defined event types with ledger validation, and
`detect_conflict()` names them as the permitted resolutions. But the guided
*workflow* that walks a human through resolving a conflict — and the check that a
replacement actually deprecates the incumbent in the same transaction — is not built.
Today the two events are independent appends, so an operator could record a
replacement without deprecating the former master and leave two actives in the
read model. C3b4 should add that consistency check.

## L8. Re-running the pilot re-touches the committed example files' timestamps
"An immutable record whose file changes on every test run" is a contradiction a
reviewer will rightly notice, so: the `examples_TEST_ONLY/` records are **regenerated**
each run, and `recorded_at` / `generated_at` move with the wall clock. Nothing
substantive changes — `content_hash()` excludes those fields by design, and the
hashes stay byte-identical — but it does mean `git status` shows churn after a test
run. The real ledger is unaffected (it is empty, and `append()` refuses to overwrite).
Making the examples byte-stable would need a frozen clock in the runner; deferred.

> **RE-MEASURED AND HALF-CLOSED 2026-09-20 — §BH55 Phase 4, "the wall-clock fixtures".** Nothing above is rewritten
> (CLAUDE.md, §AZ0(u)). **The frozen clock this paragraph asked for exists**: `tools/dip0/provenance.py` reads
> `DIP0_CLOCK`, an ISO-8601 instant, and every `recorded_at` / `generated_at` takes it; unset, nothing changes; a
> value that will not parse is refused rather than ignored. Two runs of `run_c3b3` under one frozen clock are now
> byte-identical, proved by running it — `tools/dip0c/tests/test_frozen_artifacts.py`.
>
> **What this paragraph did not know.** All five pilots (`run_c3b2`, `c3b3`, `c3b4`, `c3d`, `c3e`) were run into a
> temp root and diffed against the committed `examples_TEST_ONLY/`. The whole difference is 46 lines over 11 files,
> in three classes: (1) `recorded_at` in four files, 2026-07-13/14 against today — this paragraph's own claim, and
> the larger part; (2) ONE reason text in `c3b4_pilot.json`, where July's copy says a variant reclassification "may
> not make something the canonical master" and today's code says "the authoritative master or palette" — the same
> refusal, widened to name palettes; (3) four derived ids and two event filenames, all downstream of (2), because
> `make_id` hashes the record's substance. **Nothing stopped being refused**: the refusal counts are identical on
> both sides (6 and 6 in the c3b3 pilot, 8 and 8 in the c3b4), and every event kind July recorded is produced today.
>
> **The examples were NOT regenerated.** Overwriting them would destroy the only copy of July's answers before
> anyone has compared them, and it would do it for a wording change, which is a question about the rights model and
> not about a clock. So the committed records remain July's, they are now known to differ from today's run in
> exactly the three classes above, and the clock is no longer what keeps them from agreeing.

## L9. The pilot proves the gates, not the corpus
Four synthetic scenarios exercise the machinery. They demonstrate that the rules
refuse what they should refuse. They say nothing about whether BBROSE's real logos
would pass a real checklist — no real asset has been through this, by design.
