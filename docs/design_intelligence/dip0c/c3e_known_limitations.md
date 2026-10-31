# DIP-0C3e — known limitations

## L1. Actor identity is asserted, not authenticated
Unchanged, and now four dual-control gates rest on it (canonical approval, canonical
replacement, palette approval, palette replacement). Every one compares **actor IDs
supplied by the caller**. The system refuses a decision only one *named* actor touched; it
cannot tell whether one human is behind two names. This is the single biggest gap in the
whole C3 milestone, and it is DIP-1's to close.

## L2. Git is versioned history, not cryptographic immutability
Content hashes, an append-only validator, atomic compound writes, protected branches,
reviewed PRs — but no commit signing and no tamper-proof store. Evidential, not
cryptographic.

## L3. Concurrent resolutions are still not serialised
`os.replace()` makes one resolution atomic. Two *concurrent* resolutions touching the same
scope could both validate against the same pre-state; `expected_pre_state_hash` catches
the second **only if the first has already landed**. There is no lock. Single-operator and
git-mediated today; a real DB transaction under DIP-1.

## L4. A resolution cannot span two domains
By design (D3) — but it means a genuine cross-domain decision has no expression. If
retiring a brand palette *ought* to force a re-review of a typography system that depends
on it, nothing models that. Cross-domain **non-interference** is enforced; cross-domain
**consistency** is not modelled at all. See C3d L4.

## L5. `RECLASSIFY_AS_VARIANT` for palettes reuses `CLASSIFY_VARIANT` authz
Both domains map the action to the same authz action (`CLASSIFY_VARIANT`, held by
BRAND_ADMIN and DESIGN_REVIEWER). A designer who may classify a *logo* variant may
therefore also classify a *palette* variant. That is probably right — both are design
judgements — but it was a default, not a deliberated decision, and the business may want
them separated.

## L6. The resolver validates provenance is *declared*, not that it is *true*
`SUPERSEDE_INCUMBENT` refuses a replacement whose swatch values carry no provenance
label. It cannot check that a value labelled `RAW_SOURCE` really came from the bytes — a
human could label a preview as source truth and the system would record it. The label
makes the claim **visible and attributable**; it does not verify it. That is the honest
limit of what a record can do.

## L7. The pilot is synthetic and the real ledger is empty
Every resolution in C3e runs on `TEST_ONLY_*` assets. No real conflict has been resolved,
because no real palette or master has been approved — so none can conflict yet. The
machinery is proven against fixtures, not against BBROSE's actual brand history.
