# DIP-0C3b4 — completion report

**Canonical conflict resolution, review queues, consolidated reports.**
Completes the C3b ownership-and-permission framework. Builds on C3b3 (`8685f3f`).

---

## 1. Taxonomy schema and version

`docs/design_intelligence/dip0c/scope_taxonomy.json` — schema `scope_taxonomy/1.0`,
taxonomy **v1.0.0**. Human-maintained; it is the only place a scope token's meaning is
declared.

| Axis | Tokens | Closed-world | Notes |
|---|---|---|---|
| markets | 9 | yes | `EU` is a PARENT of FR/DE/IT/ES/NL; roots mutually exclusive |
| products | 12 | yes | `COSMETICS > MAKEUP > {LIP_GLOSS, MASCARA, …}`; `PACKAGING` is GENERAL |
| lockups | 6 | yes | `PRIMARY` is a parent; roots **not** mutually exclusive |
| variant_roles | 5 | yes | `MASTER` and the subordinate roles |

**Every relation the business specified is reproduced exactly** (14 parametrised
tests): `EU`/`FR` → OVERLAPPING · `FR`/`DE` → DISJOINT · `EU`/`US` → DISJOINT ·
`EU`/unknown → UNKNOWN · `LIP_GLOSS`/`MASCARA` → DISJOINT · `MAKEUP`/`LIP_GLOSS` →
OVERLAPPING · `COSMETICS`/`MAKEUP` → OVERLAPPING · `PRIMARY`/`PRIMARY_HORIZONTAL` →
OVERLAPPING · `PRIMARY_HORIZONTAL`/`PRIMARY_VERTICAL` → DISJOINT.

`PRIMARY` vs `STACKED` returns **UNKNOWN** — a stacked lockup may well *be* a primary
one, and nothing declares otherwise. That is the honest answer, and it queues.

## 2. Identical / overlapping / disjoint / unknown

The quad-state (`SCOPE_IDENTICAL`, `SCOPE_OVERLAPPING`, `SCOPE_DISJOINT`,
`SCOPE_UNKNOWN_OVERLAP`) is implemented **once**, in `canonical_scope.relate()`, and
every workflow routes through it — approval, conflict detection, replacement,
narrowing/widening, the read model, the queues. The C3b3 boolean helper is **deleted**,
and a test greps the whole package to prove nothing still defines or calls it.

Fail-closed rules: an unregistered token, unresolved alias, incomplete axis, malformed
or naive timestamp → `UNKNOWN` → blocks. Omission means `ALL` (recorded as a mode, not
implied by an empty list); *incompleteness* never silently becomes `ALL`. Periods are
half-open, so touching intervals are disjoint. A **proven** DISJOINT on any one axis is
the only thing that beats UNKNOWN elsewhere.

## 3. Scope-local conflict behaviour

Two masters fighting over France do **not** invalidate a master approved only for the
United States. Verified in the pilot: with `EU`, `US` and `FR` masters active, querying
`US` returns `master_us.ai` as usable, while querying `FR` returns `CANONICAL_CONFLICT`
with both assets named and no winner chosen.

The conflict record reports the affected scope, the uncertain axes, whether the overlap
is **proven** or merely **uncertain**, the involved events, and the seven permitted
resolutions.

## 4. Taxonomy-version behaviour

Every scope pins `taxonomy_version` at the moment of decision. `taxonomy_drift()`
compares each activation's pinned version against the current one and reports
`TAXONOMY_REVIEW_REQUIRED` — the original interpretation is preserved, and a human must
confirm the meaning has not moved before operational behaviour relies on it.

## 5. Compound-event atomicity

A resolution is **one immutable file** with its constituent events embedded — never
separate ledger files. Procedure: build in memory → project the post-state → validate
(≤1 active master per scope) → temp file on the same filesystem → `fsync` → `os.replace`
→ `fsync` the directory. If anything fails before the rename, **nothing becomes
visible**. There is no torn state to detect because there is no interval in which one
can exist.

Verified: supersession leaves `{eu: SUPERSEDED, eu_v2: ACTIVE, us: ACTIVE}` with **zero**
conflicts, and `nothing_written_on_failure = true` across seven refused attempts.

## 6. Invalid compound events rejected

`compound.validate()` catches: malformed events · duplicate compound IDs · duplicate
constituent IDs · tampered constituent hashes · a missing or non-ACTIVE incumbent ·
incomplete dual-control attestations · taxonomy-version mismatch · pre-state mismatch ·
post-state mismatch · **a post-state holding two overlapping active masters** · widening
disguised as narrowing.

`ledger_store.validate()` gained `overlapping_active_masters` and
`invalid_compound_events`, so a hand-edited or badly-merged ledger is caught too — not
just the write path.

## 7. Projections

`ACTIVE` · `DEPRECATED` (historically authoritative; not for new work) · `SUPERSEDED`
(names its successor explicitly) · `REJECTED` (never was a master) · `QUARANTINED`.
Plus supersession chains, unresolved conflicts, expired approvals, and effective
permissions. **Pure** — a test snapshots the ledger directory around the whole
projection and asserts nothing was written.

## 8. Queues

Ten queues (A–J), deterministic (built twice from reversed input, compared byte-for-byte).
Queue totals on the synthetic pilot: `A=1, B=1, C=0, D=3, E=0, F=0, G=1, H=0, I=0, J=1`.
**Queues A, B and C are never batch-approved.**

## 9. Illegal resolutions rejected (7/7, nothing written)

`supersede with no legal attestation` · `supersede where one person attests both halves`
· `widening disguised as a narrowing` · `SYSTEM_ADMIN supersedes a master` · `a variant
reclassified INTO the canonical master` · `a resolution with no reason` · `a machine
resolving a conflict`.

## 10. Three bugs the guards caught in my own code

**Timestamp ordering was unsound.** A supersession writes both constituents at one
instant, so ties broke on `event_id` and the deprecation could sort *ahead* of the
activation it superseded — the incumbent never left ACTIVE and two masters appeared to
hold one scope. Ordering is now **causal**: an event that supersedes another is always
processed after it.

**`SCOPE_REDUCED` was invisible to the projection.** It is a corrective event, not a
member of `CANONICAL_EVENTS`, so every narrowing was silently ignored.

**Narrowing used set difference.** `EU → FR` removes nothing from a set point of view,
so a genuine reduction was reported as a **widening** and would have demanded a full
reapproval. Narrowing now asks the taxonomy about **containment**, not set membership.

## 10b. Two gaps closed at review

**The atomic writer had never actually run.** Every resolution in the pilot and the
tests used `dry_run=True`, and the failure-path tests raise *before* any write — so
`os.replace`, both fsyncs, `load_all()` and `expand()` were unexecuted code. An atomic
writer that has never written once is not evidence of anything. Now exercised for real:
a resolution commits, round-trips, projects to exactly one active master per scope,
refuses a second write (append-only), and a tampered file is caught by its hash.

**`project()["active"]` still listed both conflicted masters.** `canonical_for()` — the
dangerous path — correctly refused to name a winner, but a caller reading the projection
would have seen two overlapping actives side by side, which is the literal thing the
acceptance criterion forbids. Conflicted masters now move to a separate `conflicted`
bucket, and a test asserts directly that no two masters listed as `active` overlap.

## 11. Verification

| Check | Result |
|---|---|
| `pytest tools/dip0c/tests/test_c3b4.py` | **60 passed** |
| `pytest tools/dip0c` | **358 passed** |
| DIP-0A + DIP-0B | **343 passed** |
| Django | **537 passed**, 1 skipped |
| `ruff check tools/` | clean |
| `materials/` integrity | **unchanged** |
| real ledger | **0 events, 0 compound events**; validator clean |

Machine-readable: [c3b4_reconciliation.json](c3b4_reconciliation.json).

## 12. Acceptance criteria

| Criterion | Status |
|---|---|
| the read model cannot expose two active overlapping masters | ✅ fails closed, incl. UNKNOWN |
| every replacement resolves its incumbent explicitly | ✅ refused otherwise |
| scope widening requires complete reapproval | ✅ containment-checked |
| scope narrowing is auditable | ✅ `SCOPE_REDUCED` records removed tokens, reason, actor |
| conflicts fail closed | ✅ and **locally** |
| all review queues are deterministic | ✅ tested |
| ownership, licence, canonical status and permissions stay independent | ✅ |
| the real ledger is free of fabricated decisions | ✅ **0 events** |

**C3b is now a complete ownership and permission framework.**

**HOLD for review before C3c.**
