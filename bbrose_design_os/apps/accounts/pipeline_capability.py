"""§BH58(d) — capabilities a DESIGN RUN may exercise, decided apart from review authority.

The owner: "Reading the house library to inform a design is not reviewing evidence, and a
background job is not a person. Split the capability … and reviewing stays what it was."

WHY THIS IS A SEPARATE MODULE AND NOT A BRANCH IN `authorization.py`. That module's
`authorize_actor` checks reviewer standing at step 2 — before it looks the action up — and
then requires an active role at step 4 and an authorizing role at step 5. Opening one
role-less read through it would need a carve-out at all three, in the function that guards
45 review actions. Here, `authorization.py` is untouched: a reviewer confirms that by
reading the diff instead of by reasoning about a conditional.

WHAT A CAPABILITY IS, AND WHAT IT IS NOT. A capability in this module may only READ, may
never supply an asset, a path, a font, a layout or a permission, and may never decide
anything a reviewer decides. `READ_DESIGN_INTELLIGENCE_CONTEXT` qualifies because
`design_context` already guarantees exactly that by contract — descriptive text only, no
file locator, `production_input_references()` empty, fail-soft on absence and fail-CLOSED
on leakage. The set below is a literal tuple of ONE. Adding to it is a governance act.

IDENTITY IS STILL REQUIRED. "A background job is not a person" removes the REVIEWER
requirement, not the actor: the caller is the workflow's user, exactly as
`design_context`'s own rule says ("Authorization is the caller's identity, never the
brief's"). An absent or inactive actor is refused, and the refusal names which.
"""
from __future__ import annotations

from dataclasses import dataclass

#: The only capability in this class. A literal tuple of one, by intent.
READ_DESIGN_INTELLIGENCE_CONTEXT = "read_design_intelligence_context"
PIPELINE_CAPABILITIES = (READ_DESIGN_INTELLIGENCE_CONTEXT,)

#: This capability's OWN outcome codes. §BH58(e): a refusal names the cause it measured,
#: so none of these is a reviewer reason code — the reviewer checks do not run here.
CAPABILITY_GRANTED = "PIPELINE_CAPABILITY_GRANTED"
CAPABILITY_UNKNOWN = "PIPELINE_CAPABILITY_UNKNOWN"
NO_ACTOR = "PIPELINE_NO_ACTOR"
ACTOR_INACTIVE = "PIPELINE_ACTOR_INACTIVE"

DENIAL_REASONS = (CAPABILITY_UNKNOWN, NO_ACTOR, ACTOR_INACTIVE)


@dataclass(frozen=True)
class CapabilityResult:
    allowed: bool
    reason_code: str
    capability: str
    actor_id: int | None

    def __post_init__(self):
        # An allow reads GRANTED and names no role, because this class of decision has
        # none. A denial names a reason this module measured.
        if self.allowed:
            assert self.reason_code == CAPABILITY_GRANTED
        else:
            assert self.reason_code in DENIAL_REASONS


def authorize_pipeline_read(user, capability: str) -> CapabilityResult:
    """Decide whether a design run may exercise `capability`. Pure; deny by default.

    Deliberately does NOT consult reviewer standing, roles or the reviewer policy. It
    cannot reach a review action: `PIPELINE_CAPABILITIES` is a closed tuple and nothing
    in it appears in `authz_policy.ACTIONS` — asserted by test.
    """
    actor_id = getattr(user, "pk", None) if getattr(user, "is_authenticated", False) \
        else None
    if capability not in PIPELINE_CAPABILITIES:
        return CapabilityResult(False, CAPABILITY_UNKNOWN, capability, actor_id)
    if user is None or not getattr(user, "is_authenticated", False):
        return CapabilityResult(False, NO_ACTOR, capability, None)
    if not getattr(user, "is_active", False):
        return CapabilityResult(False, ACTOR_INACTIVE, capability, actor_id)
    return CapabilityResult(True, CAPABILITY_GRANTED, capability, actor_id)
