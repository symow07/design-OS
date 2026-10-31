# DIP-1 — execution roadmap

Four stages. **Permissions are not granted until stage 3, and nothing is retrievable until
stage 4.** The order is the point: a review UI that can grant permissions before identity
is authenticated is worse than no UI at all.

## Stage 1 — read-only audit dashboards
Queue counts · review items · previews · evidence display · coverage table.
**No permission activation. No decisions.** Purely: *look at what we found.*

## Stage 2 — reviewer decisions
Role authorisation · evidence upload · **append-only** decisions · correction workflow
(a correction *appends*, never edits).
**Still no permission grants.** A decision settles a question; it grants nothing.

## Stage 3 — permissions, dual control, approvals
Per-flag permission grants · expiry · **dual control with AUTHENTICATED identity** ·
canonical selection · palette approval · font approval.

> **Stage 3 must not begin until the identity blocker is closed.** Dual control over
> asserted IDs is theatre.

## Stage 4 — activation
Retrieval activation · automatic-use activation · monitoring · re-review · expiry
processing.

**Retrieval and automatic use are activated separately**, and automatic use is strictly
harder. A retrievable asset may still require manual selection.

## The prerequisite that spans all four

**Curate the font library forward.** Do not attempt to clear 4,786 fonts of unknown
provenance. Keep the dump disabled and archived; build from the 46 organised packages and
from newly acquired fonts with documented provenance.
