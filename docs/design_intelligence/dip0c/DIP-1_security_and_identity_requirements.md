# DIP-1 — security and identity requirements

## The blocker

> **Actor identity is asserted, not authenticated. No real dual-control approval may
> become operational until this is fixed.**

Four dual-control gates — canonical approval, canonical replacement, palette approval,
palette replacement — enforce `technical_reviewer_id != legal_reviewer_id`. Those IDs are
**supplied by the caller**. The system refuses a decision that only one *named* actor
touched; it **cannot tell whether one human is behind two names**.

Dual control is today a strong **procedural** control. It is not a **cryptographic** one.
That gap is the single largest risk in the entire DIP-0 programme, and it is a
**production-readiness blocker**, not a nice-to-have.

## Required before any real approval is relied upon

- **authenticated user identity** — SSO / OIDC, not a string in a JSON field
- **role assignments** with **expiry**
- **separation of duties** enforced against authenticated principals
- **audit logs** for every decision, grant and revocation
- **protected decision actions** — a permission check at the point of decision, not only
  at the point of display
- **distinct-actor enforcement** against authenticated identities
- **revocation** that takes effect immediately and fails closed
- **tamper-resistant event history** — commit signing at minimum

## Git is versioned history, not cryptographic immutability

**What exists today:** content hashes on every record · an append-only validator that
detects modification and deletion · atomic compound writes · protected branches · reviewed
PRs · a full commit history.

**What does not:** commit signing · verified author identity · a tamper-*proof* store.
Anyone with write access could rewrite history; the validator would notice a changed hash,
but a determined rewrite could regenerate the hashes too.

**The audit trail is evidential, not cryptographic.** Say so plainly, and fix it in DIP-1.
