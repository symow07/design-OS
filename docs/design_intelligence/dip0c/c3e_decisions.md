# DIP-0C3e — decisions

## D1. One resolver, made domain-aware — not a second resolver
The seven actions are unchanged. What changes is the **event mapping**: a `DOMAIN_SPEC`
table gives each authority domain its own deprecate/replace/scope/variant/reject/
quarantine event types, its own authz actions, and its own canonical states.

A separate palette resolver would have duplicated the atomic-write path, the post-state
projection, the dual-control check and the narrowing logic — four places for the rules to
drift apart, and drift is how a second master slips through.

## D2. The domain is read from the incumbent, never supplied by the caller
`resolve()` looks up the incumbent's activation event and takes `authority_domain` from
it. A caller cannot *assert* which domain it is operating in and be believed — the
resolution operates on the authority that actually exists.

## D3. A resolution may never emit another domain's event types
Enforced twice: the `DOMAIN_SPEC` lookup means only that domain's types are ever
constructed, **and** a final sweep asserts every constituent's `event_type` is in the
domain's allowed set. Emitting `CANONICAL_MASTER_REPLACED` from a palette resolution
would smuggle a decision about colours into the register of decisions about files, and
the read model would believe it.

Cross-domain reach is refused explicitly too: `NARROW_NEW_SCOPE` naming an asset from the
other domain raises rather than silently narrowing the wrong thing.

## D4. The incumbent's audit is carried forward VERBATIM
A palette deprecation copies the incumbent's entire palette block — parse status,
warnings, layout, raw values, value provenance, parser-limitation acknowledgement,
third-party naming acknowledgement — into the retiring event, unchanged.

**Retiring a palette must not quietly clean up its history.** The whole point of the
record is that it still says what it said. A `PARTIAL_PARSE` that was approved with
`DERIVED_PREVIEW` values stays exactly that, forever.

## D5. A replacement must carry its own audit and declare its own provenance
A palette supersession is refused if the replacement arrives with **no technical audit**
(that would launder an unaudited file into brand authority) or with **undeclared value
provenance** (a derived preview does not become source truth by surviving a
replacement). Both are checked before a single event is constructed.

## D6. Dual control survives the conflict path, in both domains
`PALETTE_SUPERSEDED` is in `DUAL_CONTROL_EVENTS`, so a palette replacement needs both
attestations from two distinct actors — enforced in `palette_approval`, again in
`ledger.event()`, and again in `compound.validate()`. A conflict is not an emergency that
suspends the rules.

## D7. The post-state check is domain-partitioned and still fails closed
`compound.validate()` projects the prospective post-state and refuses any overlapping
**active authority within a domain**. Superseding one of two conflicting palettes with a
*third* palette is refused — because it would leave the second one still active over the
same scope. That is not a bug in the resolver; it is the resolver noticing that the
proposed resolution does not actually resolve anything.

## D8. Resolution grants no operational permission — in either domain
Every constituent carries `grants_permissions: false`, and the effective permissions of
the newly active palette are all `false`. Deciding which colours are the brand's is not
deciding what may be done with them, and settling a fight between two palettes certainly
is not.

## D9. The palette lifecycle now projects fully
`PALETTE_VARIANT_APPROVED` demotes an asset out of the authoritative role (it remains a
recorded, approved variant). `PALETTE_APPROVAL_REVOKED` marks a rejected candidate as
`REJECTED` — it never was the brand's palette. Both are read by the projection, so a
resolution's effect is visible rather than merely recorded.
