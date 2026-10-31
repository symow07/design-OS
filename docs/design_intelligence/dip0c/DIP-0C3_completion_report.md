# DIP-0C3 — completion report

**Brand assets, canonical masters, ownership, palettes, permissions and conflict
resolution.** Consolidates C3a (`d0bf01e`…), C3b1–C3b4, C3c (`c34d4a1`), C3d (`1960128`)
and C3e.

---

## The six statements that matter

1. **There is currently no confirmed canonical BBROSE logo master.**
2. **No real brand asset or palette has been approved.**
3. **No real permission has been granted.**
4. **The real decision ledger is empty** — 0 events, 0 compound events.
5. **`Pantone_3519C.ase` is a partially parsed named RGB swatch, not an authoritative
   Pantone spot definition.**
6. **Every audited asset remains non-retrievable and non-automatic-use until a human
   approves it.**

Everything below is machinery and evidence. None of it is a decision.

---

## 1. Which files were originally considered brand masters?

DIP-0A shelved these as brand/logo material: `BBROSE.pdf`, `BBROSE-1.pdf`, `logo.pdf`,
`LOGO6.ai`, plus `ATC LOGO.ai` and `JOJIA LOGO.ai`.

## 2. Which were found to be raster-heavy design compositions?

**`BBROSE.pdf` and `BBROSE-1.pdf`.** C3a measured them: roughly **80% embedded raster**.
They are *design compositions that contain the logo*, not logo masters. A composition is
not a master merely because the mark appears inside it. Both carry a recorded
classification override (`audit_category_override = DESIGN_COMPOSITION`,
`reuse_posture = REFERENCE_ONLY`) — the DIP-0A inventory is **not** rewritten; the
correction sits beside it.

## 3. Which files remain plausible logo-master candidates?

**`logo.pdf`** — clean isolated vector artwork, nominated `BRAND_MASTER_CANDIDATE`.

**A nomination confers nothing.** It is a machine saying "a human should look at this",
and nothing more.

**`LOGO6.ai` is not a candidate.** Its live text reads *"global logistics services"* — a
direct contradiction of any BBROSE brand claim. It is blocked from canonical approval
until a human **acknowledges the contradiction with a reason**.

## 4. Which materials are confirmed third-party candidates?

**`ATC LOGO.ai`** and **`JOJIA LOGO.ai`** — third-party marks sitting inside BBROSE
folders. And `Pantone_3519C.ase`, whose name references a third-party colour system.

**Folder location has never implied ownership.** It does not start now.

The subtle trap, and it is tested: `retrieval_allowed`'s prerequisites *do* admit
`THIRD_PARTY_CONFIRMED`. Confirming *whose* a logo is **settles a question**; it hands out
**no permission**. JOJIA's permissions are all `false` and stay that way.

## 5. Is there a confirmed canonical BBROSE logo master?

**No.**

One file is nominated. Nothing is approved. The ledger holds zero canonical activations.

## 6. What ownership and licence questions remain unresolved?

All of them. Nothing has been confirmed.

- who owns `logo.pdf` — unconfirmed
- whether `LOGO6.ai` is BBROSE's at all — contradicted, unresolved
- whether ATC/JOJIA material may be retained — unconfirmed
- who owns `Pantone_3519C.ase`, and under what licence — unknown / unverified
- whether BBROSE ever used that colour officially — **unknown, and C3 does not guess**

## 7. How do assertions, evidence, confirmation and permissions differ?

Six layers, and **none grants the one below it**:

| Layer | Who | Confers |
|---|---|---|
| machine inference | machine | **nothing** |
| business assertion | BUSINESS_OWNER / BRAND_ADMIN | nothing — a *belief* |
| evidence | submitted, then reviewed | nothing — a *fact on file* |
| human confirmation | an authorised human | settles **one** question |
| canonical / palette approval | **two** humans, dual control | *which file / which colours* are the brand's |
| operational permissions | LEGAL / BRAND_ADMIN, **per flag** | *what the system may do* |

A user saying "this is our logo" creates `business_assertion = BBROSE_OWNED`. It does
**not** create `BBROSE_OWNED_CONFIRMED`, a licence, a canonical master, or a single
permission.

**The core invariant:** *machine code may only ever REDUCE certainty or permission —
never increase it.*

## 8. How are canonical masters approved?

Under **dual control**. The 15-item checklist is split so neither attester is *authorised*
to answer the other's half:

| `TECHNICAL_AND_BRAND` (8 items) | `RIGHTS_AND_OWNERSHIP` (7 items) |
|---|---|
| DESIGN_REVIEWER *or* BRAND_ADMIN | **LEGAL_REVIEWER only** |

Final activation: **BRAND_ADMIN only**, reachable only once both attestations exist.
Separation is by **actor identity** (`technical_reviewer_id != legal_reviewer_id`) — one
person holding both roles is still one person. An unanswered checklist item **blocks**:
`None` is not a pass.

Enforced in `check_canonical_approval()`, again in `ledger.event()`, and again in
`compound.validate()`.

**Canonical status ≠ usable.** An approved master has every permission `false`.

## 9. How are palettes parsed and approved?

**Parsed** by a two-layout protocol. The documented ASE layout first; a non-standard
fallback **only** when the documented one is *provably impossible*, accepted **only** if it
consumes the block exactly, with **one** unique valid reading. Anything ambiguous →
`PARSE_FAILED` + `REQUIRES_HUMAN`. **No interpretation is ever chosen heuristically.**

`Pantone_3519C.ase`: 66 bytes, ASE v1.0, 1 block, **0 groups**, **1 swatch** —
`Pantone 3519 C`, model **RGB**, R 0.478431 / G 0.180392 / B 0.380392, colour type
**GLOBAL (not SPOT)**. It declares **no spot identity, no CMYK, no Lab, no ICC profile**.
Its name-length field reads 80 UTF-16 units inside a 48-byte body — *impossible*, so the
fallback was required. Final status: **`PARTIAL_PARSE` / `REQUIRES_HUMAN` /
`NON_STANDARD_NAME_ENCODING` / `NAME_LENGTH_FIELD_ABSENT`**. It can never be
`TECHNICALLY_PARSED`.

**"Pantone" exists only inside a name string.** It is third-party *naming evidence*, not a
colour definition, and there is nothing here from which any official conversion could be
derived.

**Approved** under palette dual control — `COLOR_AND_BRAND` (BRAND_ADMIN or
DESIGN_REVIEWER) + `RIGHTS_AND_USE` (**LEGAL_REVIEWER only**), two distinct actors, then
`BRAND_ADMIN` activation. A partially parsed file **may** be approved — but the limitation
must be acknowledged **with a reason**, the audit **survives unchanged**, and every
approved value declares its provenance (`RAW_SOURCE` / `DERIVED_PREVIEW` /
`MANUALLY_CONFIRMED`). **A derived preview never becomes source truth by being approved.**

**Approving a palette grants no operational permission.**

## 10. How are canonical and palette conflicts resolved?

Two active authorities over one scope, **within a domain**, is `CANONICAL_CONFLICT`. Both
become unusable *for the affected scope only*. **No winner is chosen** — not by timestamp,
not by filename, not by technical quality.

**Authority domains keep them apart.** `BRAND_MASTER` and `BRAND_PALETTE` answer different
questions, so a logo master and a brand palette **never conflict with each other**, even
over an identical scope. Two palettes conflict. Two masters conflict.

Seven resolution actions — `DEPRECATE_INCUMBENT`, `SUPERSEDE_INCUMBENT`,
`NARROW_INCUMBENT_SCOPE`, `NARROW_NEW_SCOPE`, `RECLASSIFY_AS_VARIANT`,
`REJECT_NEW_CANDIDATE`, `QUARANTINE_BOTH_PENDING_REVIEW` — through **one** domain-aware
resolver that emits only the incumbent domain's event types.

Each resolution is **one atomic compound file**: built in memory → post-state projected →
validated (≤1 active authority per scope per domain) → temp file → fsync → `os.replace`.
**If any step fails, nothing is appended and the ledger is byte-identical.** There is no
interval in which two authorities hold one scope.

**Scope** is compared on a five-axis quad-state (`IDENTICAL` / `OVERLAPPING` / `DISJOINT` /
`UNKNOWN_OVERLAP`) against a human-maintained taxonomy. **Uncertainty fails closed.**
Narrowing uses taxonomy *containment*, not set subtraction. Widening is a **new approval**.

## 11. What remains blocked from retrieval and automatic use?

**Everything.** Every audited asset: `retrieval_allowed = false`,
`automatic_use_allowed = false`, `production_use_allowed = false`, and the six other flags
too.

Permissions are granted **one at a time**, by name, by an authorised human, with
action-specific prerequisites, scope (brand / product / market / **media**) and expiry.
**Expiry fails closed** — the instant the review date passes, use stops, with or without an
audit event. **Reading never writes.**

## 12. What should DIP-1 persist?

- the **append-only decision ledger** (events, evidence, assertions, compound resolutions)
  — the files are the source of truth; the index is derived
- the **authority projection** by domain + scope, with lifecycle
  (ACTIVE / DEPRECATED / SUPERSEDED / REJECTED / QUARANTINED)
- the **scope taxonomy**, versioned and **pinned to every decision**
- the **palette schema**: raw source values and derived previews under **separate keys**,
  never merged
- the **permission set** — derived from one canonical schema, never re-declared
- the **fourteen review queues**, keyed on `queue_id` (letters are display labels)

## 13. What human actions are required next?

Nothing in this system may proceed without a human. In priority order:

1. **`LOGO6.ai`'s contradiction** — acknowledge it with a reason, or reject the file.
2. **`logo.pdf`** — run the 15-item canonical checklist under dual control, or don't.
3. **ATC / JOJIA** — confirm third-party status and decide whether the material is kept.
4. **`Pantone_3519C.ase`** — decide whether BBROSE has any claim to it at all. Today it
   fails on ownership, licence, evidence, unacknowledged PANTONE naming, an unacknowledged
   parser fallback, and undeclared value provenance. All six are real.
5. **Decide whether two-person approval should extend beyond canonical/palette activation.**
6. **Register the market, product and media tokens the business actually uses** — every
   unregistered token fails closed into a review queue.

## 14. What limitations remain?

**Actor identity is asserted, not authenticated.** Four dual-control gates compare IDs
*supplied by the caller*. "Two people" currently means "two names". **This is the largest
gap in C3**, and DIP-1 must close it before any real approval is operationally relied upon.

**Git is versioned history, not cryptographic immutability** — evidential, not tamper-proof.
No commit signing.

**The corpus is thin where it matters.** One `.ase` in 28 GB. Every palette conclusion is
about one downloaded 66-byte file.

**Scope is compared, not enforced at point of use.** DIP-0C can *say* retrieval is false. It
cannot yet *stop* anyone.

**Cross-domain consistency is unmodelled.** Domains do not interfere with each other; they
also cannot depend on each other.

**Concurrent resolutions are not serialised** — no lock; a real DB transaction is DIP-1.

Full detail: `c3a_known_limitations.md`, `c3b1`–`c3b4`, `c3c`, `c3d`, `c3e`.

---

## Verification

| Check | Result |
|---|---|
| `pytest tools/dip0c` | **491 passed** |
| DIP-0A + DIP-0B | **343 passed** |
| Django | **537 passed**, 1 skipped |
| `ruff check tools/` | clean |
| `materials/` integrity | **unchanged** across every run |
| **real decision ledger** | **0 events, 0 compound events; validator clean** |

**DIP-0C3 is complete as a framework. It has approved nothing, and that is the point.**
