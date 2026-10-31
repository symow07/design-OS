"""Django system check for the decision-event signing configuration (DIP-1A-1).

**Error-level when DEBUG is off.** A production instance that cannot sign must not
pretend it can: an unsigned or unverifiable decision event is worse than a missing one,
because it looks like evidence. In development the same problem is a warning — nothing is
being appended, and a developer without the secret should still be able to run the app.
"""
from django.conf import settings
from django.core.checks import Error, Warning, register

from .signing import signing_available

# Distinct ids: an "E" id attached to a Warning object reads as an error in every log
# aggregator and every reviewer's eye. Same condition, different severity, different id.
SIGNING_MISCONFIGURED = "accounts.security.E001"      # production: blocks the deploy
SIGNING_MISCONFIGURED_DEV = "accounts.security.W001"  # development: nothing is appending


@register("security")
def check_decision_event_signing(app_configs, **kwargs):
    ok, detail = signing_available()
    if ok:
        return []

    msg = f"Decision-event signing is not configured: {detail}"
    hint = (
        "Set DECISION_EVENT_HMAC_KEYS (a JSON object of {key_id: secret}) and "
        "DECISION_EVENT_ACTIVE_KEY_ID in the environment or secret store. This is a "
        "DEDICATED secret: never SECRET_KEY, never stored in the database, never "
        "committed. Until it is set, no decision event can be created — which is the "
        "correct failure mode, not a bug."
    )
    if settings.DEBUG:
        return [Warning(msg, hint=hint, id=SIGNING_MISCONFIGURED_DEV)]
    return [Error(msg, hint=hint, id=SIGNING_MISCONFIGURED)]
