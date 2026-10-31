# DIP-1A — signing-key rotation runbook

## Generating a key

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

48 url-safe bytes ≈ 64 chars, comfortably over the 32-byte minimum. **Never** reuse
`SECRET_KEY`. **Never** commit it. **Never** put it in the database.

## Configuring

```
DECISION_EVENT_HMAC_KEYS='{"2026-07":"<new secret>"}'
DECISION_EVENT_ACTIVE_KEY_ID='2026-07'
```

Key ids are free-form strings; a date-based id (`2026-07`) makes rotation self-documenting.

## Rotating

**Rotation must never invalidate history.** The old key stays in the registry as
verification-only.

1. Generate a new secret.
2. **Add** it to `DECISION_EVENT_HMAC_KEYS` — do **not** remove the old one:
   ```
   DECISION_EVENT_HMAC_KEYS='{"2026-07":"<old>","2027-01":"<new>"}'
   DECISION_EVENT_ACTIVE_KEY_ID='2027-01'
   ```
3. Deploy. From this moment new events sign with `2027-01`; every event signed under
   `2026-07` still verifies.
4. Run `manage.py verify_decision_chain` (available from 1A-5) and confirm it is green.

**Do not remove a retired key while any event still names it.** The verifier fails closed
on an unknown key id — by design — so removing it turns valid history into unverifiable
history.

## Suspected key compromise

A compromised key means events could have been **forged**, not merely read. The MAC can no
longer distinguish a genuine application-produced event from an attacker-produced one for
the period the key was exposed.

1. Rotate immediately (above).
2. `verify_decision_chain` — a mismatch proves tampering; **a pass does not prove
   innocence**, because a holder of the compromised key could produce events that verify.
3. Treat every event signed under the compromised key id as **suspect** and reconcile it
   against `AuthorizationAudit` and application logs.
4. This is precisely the gap that **per-user asymmetric signing** closes, and precisely why
   it is a named follow-up milestone rather than a "nice to have".

## Checking configuration

```bash
python manage.py check          # W001 in dev, E001 (non-zero exit) in production
```

A production instance that cannot sign **must not start clean**. An unverifiable decision
event is worse than a missing one, because it looks like evidence.
