# DIP-0C3b4 — known limitations

## L1. Git is versioned history, not cryptographic immutability
This matters, so it is stated plainly rather than implied.

**What we actually have today:** content hashes on every record; an append-only
validator that detects modification and deletion; compound files installed atomically
via `os.replace()`; a full commit history; protected-branch and reviewed-PR workflow.

**What we do NOT have:** commit signing; verified author identity; a tamper-*proof*
store. Anyone with write access to the repository could rewrite history, and while the
validator would notice a changed record's hash, a sufficiently determined rewrite
could regenerate the hashes too. The audit trail is *evidential*, not *cryptographic*.

Commit signing, protected identity, and DB-backed transactional persistence are DIP-1
requirements, not shipped controls.

## L2. Actor identity is asserted, not authenticated — and dual control leans on it
Unchanged from C3b3 and still the largest gap. `technical_reviewer_id !=
legal_reviewer_id` is enforced against IDs **supplied by the caller**. The system
refuses an approval that only one *named* actor touched; it cannot tell whether one
human is behind two names. Dual control is a strong procedural control, not a
cryptographic one.

## L3. The taxonomy is small, and deliberately so
Nine markets, twelve products, six lockups, five variant roles — seeded from what
DIP-0A/0C actually observed plus the examples the business gave. It is **not** a
complete model of BBROSE's commercial reality, and it is not meant to be: an
unregistered token fails safely (UNKNOWN → review), so a short honest registry beats a
long speculative one. Expect queue D to carry real traffic until the registry catches
up with the business.

## L4. `mutually_exclusive_roots` is a strong claim, and markets makes it
`EU` vs `US` is DISJOINT because the markets axis declares its roots mutually
exclusive. That is correct for the axis as currently drawn — but it means adding a
root token that *does* overlap an existing one (say `EMEA`, which contains the EU)
would silently produce a wrong DISJOINT. Anyone adding a root must either declare it a
parent of the tokens it contains, or set `mutually_exclusive_roots: false` on that
axis. **This is the sharpest edge in the taxonomy file**, and the reviewer notes in
`scope_taxonomy.json` say so.

## L5. Lockups is honest rather than convenient
`PRIMARY` vs `STACKED` returns UNKNOWN, because a stacked lockup may well *be* a
primary one and nothing in the taxonomy says otherwise. That is the right answer and
it will generate review items. Declaring them disjoint to quiet the queue would be
exactly the inference this milestone forbids.

## L6. Compound atomicity is per-file, not cross-file
`os.replace()` makes one resolution atomic. Two *concurrent* resolutions touching the
same scope are not serialised: both could validate against the same pre-state and both
write. The `expected_pre_state_hash` catches this **on the second write only if the
first has already landed** — there is no lock. In practice C3b4 is single-operator and
git-mediated, so this is theoretical; under DIP-1 it becomes a real DB transaction with
real isolation. Recorded, not hand-waved.

## L7. `fsync` is best-effort
The directory fsync after `os.replace()` is wrapped in a try/except: not every
platform or filesystem supports it. On a filesystem that reorders the rename against
the data write, a crash at exactly the wrong instant could leave a zero-length file.
The content hash would catch it on the next validate.

## L8. Scope is compared, not enforced at the point of use
The read model can tell you that `master_eu_v2.ai` is canonical for the EU. Nothing in
DIP-0C *stops* a designer opening the superseded file — retrieval is still `false` for
everything, and enforcement at point-of-use is a DIP-1 concern.

## L9. Scope-locality over-blocks on a sibling of a conflicted scope
With an `EU` master and an `FR` master in conflict, querying `DE` returns
`CANONICAL_CONFLICT` — even though `FR` is provably disjoint from `DE`, so only the
`EU` master could apply there and there is no genuine ambiguity. `canonical_for()`
blocks whenever *any* conflicting master's scope touches the query, rather than
re-deriving which masters actually contend for that precise scope.

This errs in the safe direction (it denies rather than guessing), but it does mildly
undercut the "an asset may remain valid for a separate scope" promise: the guarantee
holds fully for a *disjoint* scope like `US`, and partially for a scope that shares an
ancestor with the conflict. Worth tightening when queue B has real traffic; not worth
adding cleverness to a blocking path today.

## L10. Queue D conflates two kinds of uncertainty
Scope-overlap uncertainty (an unregistered token) and taxonomy-version drift both land
in queue D. They have different fixes — register a token vs re-confirm an old decision
— and a future slice should split them.

## L11. The pilot is synthetic
Six scenarios prove the machinery refuses what it should refuse. No real BBROSE asset
has been through any of it. The real ledger holds **zero** events and **zero** compound
events, by design.
