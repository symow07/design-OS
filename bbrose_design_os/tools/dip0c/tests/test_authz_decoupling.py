"""The audit tool sees EXACTLY the production policy (DIP-1A-2 decoupling).

`tools/dip0c/authz.py` is now a thin wrapper over the canonical policy that lives inside
the deployable app package (`apps/accounts/authz_policy.py`). These tests prove the DIP
tooling and Django resolve the identical roles, actions and mappings — so the wrapper can
never drift from what production enforces — while the wrapper still provides the
DIP-specific state glue that Django does not need.
"""
from __future__ import annotations

from tools.dip0c import authz  # the wrapper (adds the app package to sys.path)
from apps.accounts import authz_policy as canon  # the canonical policy


def test_wrapper_reexports_every_canonical_name_identically():
    for name in canon.__all__:
        assert hasattr(authz, name), f"wrapper is missing re-exported {name!r}"
        assert getattr(authz, name) is getattr(canon, name), (
            f"wrapper {name!r} is not the SAME object as the canonical policy — "
            "a copy would drift")


def test_django_and_dip_see_identical_roles_and_actions():
    assert authz.ROLES == canon.ROLES
    assert authz.ACTIONS == canon.ACTIONS
    assert authz.POLICY == canon.POLICY
    assert authz.SYSTEM_ADMIN_FORBIDDEN == canon.SYSTEM_ADMIN_FORBIDDEN


def test_only_one_policy_mapping_exists():
    # The wrapper must not define its own POLICY; it must be the canonical object.
    assert authz.POLICY is canon.POLICY


def test_wrapper_keeps_dip_specific_state_glue():
    # STATE_ACTION / action_for_state are DIP-ledger concepts and stay in the wrapper.
    assert hasattr(authz, "STATE_ACTION") and authz.STATE_ACTION
    assert not hasattr(canon, "STATE_ACTION"), (
        "state mapping must NOT leak into the pure canonical policy")
    for action in authz.STATE_ACTION.values():
        assert action in canon.ACTIONS


def test_policy_document_unchanged_shape():
    doc = authz.policy_document()
    assert doc["policy_version"] == canon.POLICY_VERSION
    assert doc["roles"] == list(canon.ROLES)
    assert doc["actions"] == list(canon.ACTIONS)
    assert set(doc["state_requires_action"]) == set(authz.STATE_ACTION)
    assert "git authorship is PROVENANCE, not AUTHORISATION" in doc["notes"]


def test_system_admin_forbidden_still_enforced_through_the_wrapper():
    for action in authz.SYSTEM_ADMIN_FORBIDDEN:
        assert not authz.may(authz.SYSTEM_ADMIN, action)
