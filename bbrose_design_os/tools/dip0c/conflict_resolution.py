"""The seven conflict-resolution actions (DIP-0C3b4).

An action is a **request**; the ledger records **events**. The two are kept separate
so there is exactly one vocabulary of facts — the C3b3 event types — rather than a
parallel one invented here.

Every resolution is assembled in memory, projected, validated, and only then written
as a single compound file. **No action overwrites the incumbent event**: the incumbent
is deprecated or superseded by a *new* event, and history stays complete.

**No resolution grants an operational permission.** Deciding which file is
authoritative is not deciding what may be done with it, and resolving a fight between
two masters certainly is not.
"""
from __future__ import annotations

from . import authz
from . import canonical_read as CR
from . import canonical_scope as S
from . import compound as CP
from . import config as C
from . import ledger as L
from . import palette_approval as PA

PARSER = f"{C.TOOL_NAME}.conflict_resolution/{C.TOOL_VERSION}"

DEPRECATE_INCUMBENT = "DEPRECATE_INCUMBENT"
SUPERSEDE_INCUMBENT = "SUPERSEDE_INCUMBENT"
NARROW_INCUMBENT_SCOPE = "NARROW_INCUMBENT_SCOPE"
NARROW_NEW_SCOPE = "NARROW_NEW_SCOPE"
RECLASSIFY_AS_VARIANT = "RECLASSIFY_AS_VARIANT"
REJECT_NEW_CANDIDATE = "REJECT_NEW_CANDIDATE"
QUARANTINE_BOTH_PENDING_REVIEW = "QUARANTINE_BOTH_PENDING_REVIEW"
ACTIONS = (DEPRECATE_INCUMBENT, SUPERSEDE_INCUMBENT, NARROW_INCUMBENT_SCOPE,
           NARROW_NEW_SCOPE, RECLASSIFY_AS_VARIANT, REJECT_NEW_CANDIDATE,
           QUARANTINE_BOTH_PENDING_REVIEW)

# Which action ACTIVATES a master — and therefore drags the full dual-control
# requirement along with it, conflict or no conflict.
ACTIVATING_ACTIONS = (SUPERSEDE_INCUMBENT,)

# --- AUTHORITY-DOMAIN AWARENESS (C3e) -----------------------------------------
# One resolver, two domains. The ACTIONS are the same seven; the EVENTS they emit are
# not. A palette resolution must never emit a brand-master event type, nor the reverse
# — that would smuggle a decision about colours into the register of decisions about
# files, and the read model would happily believe it.
DOMAIN_SPEC = {
    L.DOMAIN_BRAND_MASTER: {
        "deprecate_event": L.CANONICAL_MASTER_DEPRECATED,
        "replace_event": L.CANONICAL_MASTER_REPLACED,
        "scope_event": L.SCOPE_REDUCED,
        "variant_event": L.VARIANT_RECLASSIFIED,
        "reject_event": L.CANONICAL_MASTER_DEPRECATED,
        "quarantine_event": L.ASSET_QUARANTINED,
        "active_state": C.CANONICAL_BRAND_MASTER,
        "deprecated_state": C.DEPRECATED_VERSION,
        "rejected_state": C.REJECTED_CANDIDATE,
        "default_variant_state": C.ALTERNATE_LOCKUP,
        "forbidden_variant_state": C.CANONICAL_BRAND_MASTER,
        "authz": {
            DEPRECATE_INCUMBENT: authz.DEPRECATE_CANONICAL,
            SUPERSEDE_INCUMBENT: authz.APPROVE_CANONICAL_MASTER,
            NARROW_INCUMBENT_SCOPE: authz.DEPRECATE_CANONICAL,
            NARROW_NEW_SCOPE: authz.DEPRECATE_CANONICAL,
            RECLASSIFY_AS_VARIANT: authz.CLASSIFY_VARIANT,
            REJECT_NEW_CANDIDATE: authz.APPROVE_CANONICAL_MASTER,
            QUARANTINE_BOTH_PENDING_REVIEW: authz.QUARANTINE_ASSET,
        },
    },
    L.DOMAIN_BRAND_PALETTE: {
        "deprecate_event": L.PALETTE_DEPRECATED,
        "replace_event": L.PALETTE_SUPERSEDED,
        "scope_event": L.SCOPE_REDUCED,          # carries authority_domain=PALETTE
        "variant_event": L.PALETTE_VARIANT_APPROVED,
        "reject_event": L.PALETTE_APPROVAL_REVOKED,
        "quarantine_event": L.PALETTE_QUARANTINED,
        "active_state": PA.APPROVED_BRAND_PALETTE,
        "deprecated_state": PA.DEPRECATED_PALETTE,
        "rejected_state": PA.REJECTED_PALETTE,
        "default_variant_state": PA.APPROVED_PALETTE_VARIANT,
        "forbidden_variant_state": PA.APPROVED_BRAND_PALETTE,
        "authz": {
            DEPRECATE_INCUMBENT: authz.DEPRECATE_PALETTE,
            SUPERSEDE_INCUMBENT: authz.APPROVE_BRAND_PALETTE,
            NARROW_INCUMBENT_SCOPE: authz.DEPRECATE_PALETTE,
            NARROW_NEW_SCOPE: authz.DEPRECATE_PALETTE,
            RECLASSIFY_AS_VARIANT: authz.CLASSIFY_VARIANT,
            REJECT_NEW_CANDIDATE: authz.APPROVE_BRAND_PALETTE,
            QUARANTINE_BOTH_PENDING_REVIEW: authz.QUARANTINE_ASSET,
        },
    },
}

# The master domain's authz map, kept under its old name for C3b4 callers.
ACTION_AUTHZ = DOMAIN_SPEC[L.DOMAIN_BRAND_MASTER]["authz"]

# Every domain must map every action, or a resolution could silently fall through.
for _d, _spec in DOMAIN_SPEC.items():
    assert set(_spec["authz"]) == set(ACTIONS), _d


def _block(domain: str, state: str, *, scope: dict, checklist: dict,
           attestations: list, palette_audit: dict = None,
           value_provenance: dict = None, parser_limitation_ack: dict = None,
           third_party_ack: dict = None, version_or_date: str = None) -> dict:
    """Build the canonical block for THIS domain — never the other one's."""
    if domain == L.DOMAIN_BRAND_PALETTE:
        return PA.canonical_block(
            state, scope=scope, checklist=checklist or {},
            attestations=attestations or [], parser_audit=palette_audit or {},
            value_provenance=value_provenance or {},
            parser_limitation_ack=parser_limitation_ack,
            third_party_ack=third_party_ack, version_or_date=version_or_date)
    return L.canonical_block(
        state, scope=scope, checklist=checklist or {},
        attestations=attestations or [], version_or_date=version_or_date,
        authority_domain=L.DOMAIN_BRAND_MASTER)


def _carry_forward(domain: str, incumbent: dict, state: str) -> dict:
    """Retire the incumbent WITHOUT rewriting a word of its audit.

    A palette's parser status, warnings, raw values, provenance and acknowledgements
    are carried through VERBATIM. Deprecating a palette must not quietly clean up its
    history — the whole point of the record is that it still says what it said.
    """
    if domain == L.DOMAIN_BRAND_PALETTE:
        prev = incumbent.get("palette") or {}
        blk = L.canonical_block(
            state, scope=incumbent["scope"], checklist={},
            attestations=incumbent.get("attestations") or [],
            authority_domain=L.DOMAIN_BRAND_PALETTE,
            palette=dict(prev))          # verbatim: warnings, provenance, acks, all
        return blk
    return L.canonical_block(
        state, scope=incumbent["scope"], checklist={},
        attestations=incumbent.get("attestations") or [],
        authority_domain=L.DOMAIN_BRAND_MASTER)


class ResolutionError(RuntimeError):
    """A resolution was refused. Nothing was written."""


def machine_may_not_resolve(*_a, **_k):
    """A machine may FLAG a conflict. It may never resolve one."""
    raise C.HumanOnlyStateViolation(
        "a canonical conflict is resolved by a human. Machine code may raise "
        "POSSIBLE_CONFLICT and enumerate the permitted resolutions; choosing between "
        "two masters is a judgement about the brand, and it is not reachable from "
        "here.")


def resolve(action: str, *, incumbent_event_id: str, existing_events: list,
            actor_id: str, actor_role: str, occurred_at: str, reason: str,
            new_asset: str = None, new_scope: dict = None,
            narrowed_scope: dict = None, evidence_refs: list = None,
            attestations: list = None, checklist: dict = None,
            variant_state: str = None, palette_audit: dict = None,
            value_provenance: dict = None, parser_limitation_ack: dict = None,
            third_party_ack: dict = None, dry_run: bool = False):
    """Build + validate + atomically commit ONE resolution, IN THE INCUMBENT'S DOMAIN.

    The domain is read from the incumbent itself, never passed in and trusted: a
    resolution operates on the authority that actually exists, and it emits only that
    domain's event types.

    Raises before writing anything if the request is not permitted, not complete, or
    would leave two active authorities overlapping.
    """
    if action not in ACTIONS:
        raise ResolutionError(f"{action!r} is not a permitted resolution action")

    inc = next((m for m in CR.masters(existing_events)
                if m["activation_event_id"] == incumbent_event_id), None)
    if inc is None:
        raise ResolutionError(
            f"resolution REFUSED — nothing was appended:\n  - no activation event "
            f"{incumbent_event_id!r} in the ledger")

    domain = inc["authority_domain"]
    spec = DOMAIN_SPEC[domain]

    problems: list[str] = []
    try:
        authz.authorize(actor_role, spec["authz"][action], actor_id=actor_id)
    except authz.NotAuthorized as e:
        problems.append(f"unauthorized: {e}")
    if not (reason or "").strip():
        problems.append("a resolution must record an explicit reason")
    if problems:
        raise ResolutionError("resolution REFUSED — nothing was appended:\n  - "
                              + "\n  - ".join(problems))

    asset = inc["asset"]
    constituents: list[dict] = []

    def _ev(event_type, on_asset, *, canonical=None, supersedes=None):
        return L.event(on_asset, event_type=event_type, actor_id=actor_id,
                       actor_role=actor_role, occurred_at=occurred_at,
                       decision_reason=reason, evidence_refs=evidence_refs or [],
                       canonical=canonical, supersedes_event_id=supersedes)

    if action == DEPRECATE_INCUMBENT:
        constituents.append(_ev(
            spec["deprecate_event"], asset, supersedes=incumbent_event_id,
            canonical=_carry_forward(domain, inc, spec["deprecated_state"])))

    elif action == SUPERSEDE_INCUMBENT:
        if not new_asset or not new_scope:
            raise ResolutionError(
                "SUPERSEDE_INCUMBENT must name the replacement asset and its scope")
        if domain == L.DOMAIN_BRAND_PALETTE:
            # A palette replacement must carry its OWN technical audit and declare the
            # provenance of every value it approves. A replacement that arrived with no
            # audit would launder an unaudited file into brand authority.
            if not palette_audit:
                raise ResolutionError(
                    "a palette replacement must carry its technical audit — parse "
                    "status, warnings and all. A replacement may not launder an "
                    "unaudited file into brand authority.")
            names = palette_audit.get("swatch_names") or []
            vp = value_provenance or {}
            bad = [n for n in names if vp.get(n) not in PA.PROVENANCE]
            if bad:
                raise ResolutionError(
                    f"every approved value must declare its provenance ({bad}). A "
                    "derived preview does not become source truth by surviving a "
                    "replacement.")
        # the incumbent retires FIRST, in the same atomic file — so the post-state
        # never holds two actives, not even for an instant
        constituents.append(_ev(
            spec["deprecate_event"], asset, supersedes=incumbent_event_id,
            canonical=_carry_forward(domain, inc, spec["deprecated_state"])))
        constituents.append(_ev(
            spec["replace_event"], new_asset, supersedes=incumbent_event_id,
            canonical=_block(domain, spec["active_state"], scope=new_scope,
                             checklist=checklist or {},
                             attestations=attestations or [],
                             palette_audit=palette_audit,
                             value_provenance=value_provenance,
                             parser_limitation_ack=parser_limitation_ack,
                             third_party_ack=third_party_ack,
                             version_or_date=occurred_at)))

    elif action in (NARROW_INCUMBENT_SCOPE, NARROW_NEW_SCOPE):
        target_asset = asset if action == NARROW_INCUMBENT_SCOPE else new_asset
        target = inc if action == NARROW_INCUMBENT_SCOPE else next(
            (m for m in CR.masters(existing_events)
             if m["asset"] == new_asset and m["lifecycle"] == CR.ACTIVE), None)
        if target is None:
            raise ResolutionError(f"{new_asset!r} is not an active authority")
        if target["authority_domain"] != domain:
            raise ResolutionError(
                f"{new_asset!r} is in the {target['authority_domain']} domain, not "
                f"{domain} — a resolution never reaches across domains")
        if not narrowed_scope:
            raise ResolutionError("a narrowing must state the resulting scope")
        delta = S.narrowing_delta(target["scope"], narrowed_scope)
        if delta["is_widening"] or delta["problems"]:
            raise ResolutionError(
                "scope change REFUSED — nothing was appended:\n  - "
                + "\n  - ".join(delta["problems"]))
        if not delta["is_narrowing"]:
            raise ResolutionError(
                "this scope change removes nothing: a scope reduction must actually "
                "reduce the scope")
        constituents.append(_ev(
            spec["scope_event"], target_asset,
            supersedes=target["activation_event_id"],
            canonical=_carry_forward(domain, {**target, "scope": narrowed_scope},
                                     spec["active_state"])))

    elif action == RECLASSIFY_AS_VARIANT:
        state = variant_state or spec["default_variant_state"]
        if state == spec["forbidden_variant_state"]:
            raise ResolutionError(
                "a variant reclassification may not make something the authoritative "
                "master or palette — that is an activation, and it takes full dual "
                "control")
        target_asset = new_asset or asset
        target = next((m for m in CR.masters(existing_events)
                       if m["asset"] == target_asset), inc)
        constituents.append(_ev(
            spec["variant_event"], target_asset,
            supersedes=target["activation_event_id"],
            canonical=_carry_forward(domain, target, state)))

    elif action == REJECT_NEW_CANDIDATE:
        if not new_asset:
            raise ResolutionError("REJECT_NEW_CANDIDATE must name the candidate")
        target = next((m for m in CR.masters(existing_events)
                       if m["asset"] == new_asset), None)
        if target is None:
            raise ResolutionError(f"{new_asset!r} is not an authority")
        constituents.append(_ev(
            spec["reject_event"], new_asset,
            supersedes=target["activation_event_id"],
            canonical=_carry_forward(domain, target, spec["rejected_state"])))

    elif action == QUARANTINE_BOTH_PENDING_REVIEW:
        if not new_asset:
            raise ResolutionError(
                "QUARANTINE_BOTH_PENDING_REVIEW must name the second asset")
        for a in sorted({asset, new_asset}):
            constituents.append(_ev(spec["quarantine_event"], a))

    # every emitted event must belong to THIS domain — nothing smuggled across
    allowed = {spec[k] for k in ("deprecate_event", "replace_event", "scope_event",
                                 "variant_event", "reject_event", "quarantine_event")}
    for e in constituents:
        if e["event_type"] not in allowed:
            raise ResolutionError(
                f"{e['event_type']} is not a {domain} event — a resolution may never "
                "emit another domain's event types")

    pre = CP.state_hash(existing_events)
    post = CP.state_hash(existing_events + constituents)
    rec = CP.build(
        action, asset=asset, actor_id=actor_id, actor_role=actor_role,
        occurred_at=occurred_at, reason=reason, constituents=constituents,
        incumbent_event_id=incumbent_event_id,
        replacement_event_id=(constituents[-1]["event_id"]
                              if action in ACTIVATING_ACTIONS else None),
        resulting_scopes=_resulting(action, inc, new_asset, new_scope,
                                    narrowed_scope),
        evidence_refs=evidence_refs, attestations=attestations,
        pre_state_hash=pre, post_state_hash=post)
    rec["authority_domain"] = domain

    path = CP.commit(rec, existing_events=existing_events, dry_run=dry_run)
    return path, rec


def _resulting(action, inc, new_asset, new_scope, narrowed_scope) -> dict:
    out = {"incumbent": {"asset": inc["asset"], "scope": inc["scope"]}}
    if action == SUPERSEDE_INCUMBENT:
        out["incumbent"]["becomes"] = CR.SUPERSEDED
        out["replacement"] = {"asset": new_asset, "scope": new_scope,
                              "becomes": CR.ACTIVE}
    elif action == DEPRECATE_INCUMBENT:
        out["incumbent"]["becomes"] = CR.DEPRECATED
    elif action in (NARROW_INCUMBENT_SCOPE, NARROW_NEW_SCOPE):
        out["narrowed"] = {"asset": (inc["asset"] if action == NARROW_INCUMBENT_SCOPE
                                     else new_asset),
                           "scope": narrowed_scope}
    elif action == REJECT_NEW_CANDIDATE:
        out["rejected"] = {"asset": new_asset, "becomes": CR.REJECTED}
    elif action == QUARANTINE_BOTH_PENDING_REVIEW:
        out["quarantined"] = sorted({inc["asset"], new_asset})
    out["grants_permissions"] = False
    out["note"] = ("resolving a conflict decides WHICH file is authoritative. It "
                   "grants no operational permission.")
    return out
