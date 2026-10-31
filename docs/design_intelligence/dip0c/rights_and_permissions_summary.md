# Rights and permissions summary

## Machine may recommend. Only a human may decide.

Two **disjoint** vocabularies — a shared value would be a doorway from "the machine thinks"
to "a human decided", and an import-time assertion forbids it.

**Machine recommendations (13):**
`RECOMMEND_INCLUDE_AS_REFERENCE_MEMORY` · `RECOMMEND_EXCLUDE_FROM_MEMORY` · `REUSABLE_AFTER_REVIEW` · `TECHNICALLY_READY` · `NEEDS_CLEANUP` · `NEEDS_VECTOR_RECONSTRUCTION` · `REFERENCE_ONLY` · `RIGHTS_REVIEW_REQUIRED` · `PROVENANCE_MISSING` · `QUARANTINE_CANDIDATE` · `OUT_OF_SCOPE` · `REQUIRES_TOOL` · `REQUIRES_HUMAN`

**Human decisions (14):**
`APPROVE_REFERENCE_MEMORY` · `APPROVE_REUSABLE_ASSET` · `APPROVE_BRAND_ASSET` · `APPROVE_CANONICAL_MASTER` · `APPROVE_PALETTE` · `APPROVE_FONT` · `APPROVE_LIMITED_USE` · `REJECT` · `QUARANTINE` · `DEFER` · `REQUEST_EVIDENCE` · `REQUEST_CLEANUP` · `SUPERSEDE` · `DEPRECATE`

**No machine recommendation becomes a human decision automatically.**
**No human decision grants a permission** — a permission is granted separately, by flag, by
an authorised human.

## The two gates, and they never collapse

**Retrieval** — a human may *find* it and look at it.
**Automatic use** — the system may *reach for it unasked*. **Strictly harder**: it requires
retrieval **plus** an explicit separate grant, suitable readiness, a valid rights decision,
an active review period, matching brand/product/market/media scope, no contradiction, no
quarantine, no expired evidence, and no canonical conflict.

**A retrievable asset may still require manual selection — and usually should.**

Font **installation**, **embedding** and **production use** are separate again, and are
implied by neither.

**Both default to `false`. Both fail closed.**

## Current state

**0** retrieval-enabled · **0** automatic-use-enabled · **0** approvals · **0** permission
grants. The real ledger is **empty**.
