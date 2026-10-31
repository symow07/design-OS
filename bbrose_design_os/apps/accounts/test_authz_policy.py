"""Canonical authorization policy — purity, integrity, deterministic selection (1A-2).

The point of the decoupling is that the ONE policy lives inside the deployable app package
and depends on nothing external. These tests defend that: the module must import with no
Django and no `tools`, the policy must be internally consistent, and role selection must
be deterministic and least-privilege — never influenced by row order or request input.
"""
from __future__ import annotations

import ast
from pathlib import Path

from apps.accounts import authz_policy as p


# === import purity ===============================================================
def test_canonical_policy_imports_no_tools_and_no_django():
    """Removing the tools package (or Django) must not stop the app importing its policy.

    Proven structurally: the source imports neither. If it did, a partial deploy or a
    standalone audit run could fail to load the very policy everything authorizes against.
    """
    src = Path(p.__file__).read_text()
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "tools" not in imported, "canonical policy must not import the audit tools"
    assert "django" not in imported, "canonical policy must be Django-free"


def test_canonical_policy_uses_only_stdlib_at_module_scope():
    # __future__ is the only non-stdlib-looking name and is a language directive.
    src = Path(p.__file__).read_text()
    tree = ast.parse(src)
    top = {n.names[0].name.split(".")[0]
           for n in tree.body if isinstance(n, ast.Import)}
    top |= {n.module.split(".")[0]
            for n in tree.body if isinstance(n, ast.ImportFrom) and n.module}
    assert top <= {"__future__"}, f"unexpected module-scope imports: {top}"


# === policy integrity ============================================================
def test_roles_and_actions_are_distinct():
    assert len(p.ROLES) == len(set(p.ROLES))
    assert len(p.ACTIONS) == len(set(p.ACTIONS))


def test_policy_keys_and_values_are_known():
    assert set(p.POLICY).issubset(set(p.ACTIONS))
    for roles in p.POLICY.values():
        assert set(roles).issubset(set(p.ROLES))


def test_observer_is_read_only():
    assert all(p.OBSERVER not in roles for roles in p.POLICY.values())
    for action in p.ACTIONS:
        assert not p.may(p.OBSERVER, action)


def test_system_admin_forbidden_actions_are_actually_denied():
    for action in p.SYSTEM_ADMIN_FORBIDDEN:
        assert not p.may(p.SYSTEM_ADMIN, action), action
        assert p.SYSTEM_ADMIN not in p.POLICY.get(action, ())


def test_intelligence_policy_is_explicitly_versioned_and_old_mapping_is_frozen():
    assert p.POLICY_VERSION == "authz/1.4"
    assert p.POLICY_VERSION_1_3 == "authz/1.3"
    assert p.POLICY_VERSION_1_2 == "authz/1.2"
    assert p.POLICY_VERSION_1_1 == "authz/1.1"
    assert p.POLICY_VERSION_1_0 == "authz/1.0"
    assert p.RECORD_INTELLIGENCE_CLASSIFICATION not in p.POLICY_V1_0
    assert p.FINALIZE_CANONICAL_BRAND_ASSET not in p.POLICY_V1_1
    # DIP-1C-5B added the human semantic-metadata actions in 1.3; 1.2 stays frozen without
    # them. DIP-1C-5C-CORR-4 added conflict resolution in 1.4; 1.3 stays frozen without it.
    assert p.RECORD_HUMAN_SEMANTIC_METADATA not in p.POLICY_V1_2
    assert p.CORRECT_HUMAN_SEMANTIC_METADATA not in p.POLICY_V1_2
    assert p.RESOLVE_HUMAN_SEMANTIC_METADATA_CONFLICT not in p.POLICY_V1_3
    assert all(p.POLICY[action] == roles for action, roles in p.POLICY_V1_3.items())
    assert p.POLICY[p.RESOLVE_HUMAN_SEMANTIC_METADATA_CONFLICT] == (
        p.BUSINESS_OWNER, p.BRAND_ADMIN, p.DESIGN_REVIEWER)
    assert p.RESOLVE_HUMAN_SEMANTIC_METADATA_CONFLICT in p.SYSTEM_ADMIN_FORBIDDEN
    for action in (
        p.RECORD_HUMAN_SEMANTIC_METADATA,
        p.CORRECT_HUMAN_SEMANTIC_METADATA,
    ):
        assert p.POLICY[action] == (p.BUSINESS_OWNER, p.BRAND_ADMIN, p.DESIGN_REVIEWER)
        assert action in p.SYSTEM_ADMIN_FORBIDDEN
    assert p.POLICY[p.RECORD_INTELLIGENCE_CLASSIFICATION] == (
        p.BUSINESS_OWNER, p.BRAND_ADMIN, p.DESIGN_REVIEWER)
    for action in (
        p.RECORD_INTELLIGENCE_CLASSIFICATION,
        p.CORRECT_INTELLIGENCE_CLASSIFICATION,
        p.RECORD_INTELLIGENCE_EVIDENCE_ASSESSMENT,
        p.REQUEST_INTELLIGENCE_CLARIFICATION,
    ):
        assert p.SYSTEM_ADMIN not in p.POLICY[action]
    for action in (
        p.FINALIZE_CANONICAL_BRAND_ASSET,
        p.FINALIZE_PRIMARY_BRAND_PALETTE,
    ):
        assert p.POLICY[action] == (p.BRAND_ADMIN,)
        assert action in p.SYSTEM_ADMIN_FORBIDDEN
    for action in (
        p.REVOKE_CANONICAL_BRAND_ASSET,
        p.REVOKE_PRIMARY_BRAND_PALETTE,
    ):
        assert p.SYSTEM_ADMIN in p.POLICY[action]


def test_authorize_raises_for_unknown_and_denied():
    import pytest
    with pytest.raises(p.NotAuthorized):
        p.authorize("NOPE", p.CONFIRM_OWNERSHIP)
    with pytest.raises(p.NotAuthorized):
        p.authorize(p.SYSTEM_ADMIN, p.APPROVE_LICENSE)
    assert p.authorize(p.LEGAL_REVIEWER, p.APPROVE_LICENSE) == p.APPROVE_LICENSE


# === deterministic role selection ================================================
def test_authorizing_roles_returns_only_qualifying_roles_in_canonical_order():
    got = p.authorizing_roles(p.CONFIRM_OWNERSHIP,
                              [p.BRAND_ADMIN, p.LEGAL_REVIEWER, p.DESIGN_REVIEWER])
    # DESIGN_REVIEWER cannot confirm ownership; the rest come back in ROLES order.
    assert got == (p.BRAND_ADMIN, p.LEGAL_REVIEWER)


def test_select_role_used_prefers_least_privileged_specialist():
    # ownership: a legal determination, attributed to LEGAL_REVIEWER not the broader admin
    assert p.select_role_used(
        p.CONFIRM_OWNERSHIP, {p.BRAND_ADMIN, p.LEGAL_REVIEWER}) == p.LEGAL_REVIEWER
    # design quality: attributed to the design specialist
    assert p.select_role_used(
        p.CONFIRM_DESIGN_QUALITY, {p.BRAND_ADMIN, p.DESIGN_REVIEWER}) == p.DESIGN_REVIEWER
    # a revocation: attributed to the reduce-only SYSTEM_ADMIN over the broader roles
    assert p.select_role_used(
        p.REVOKE_DECISION,
        {p.LEGAL_REVIEWER, p.BRAND_ADMIN, p.SYSTEM_ADMIN}) == p.SYSTEM_ADMIN


def test_select_role_used_is_order_independent():
    a = p.select_role_used(p.CONFIRM_OWNERSHIP, [p.BRAND_ADMIN, p.LEGAL_REVIEWER])
    b = p.select_role_used(p.CONFIRM_OWNERSHIP, [p.LEGAL_REVIEWER, p.BRAND_ADMIN])
    c = p.select_role_used(p.CONFIRM_OWNERSHIP, {p.LEGAL_REVIEWER, p.BRAND_ADMIN})
    assert a == b == c == p.LEGAL_REVIEWER


def test_select_role_used_none_when_no_role_qualifies():
    assert p.select_role_used(p.APPROVE_LICENSE, {p.DESIGN_REVIEWER, p.OBSERVER}) is None
    assert p.select_role_used(p.CONFIRM_OWNERSHIP, set()) is None


def test_role_breadth_orders_broad_above_narrow():
    # BRAND_ADMIN is the broadest generalist; OBSERVER authorizes nothing.
    assert p.role_breadth(p.OBSERVER) == 0
    assert p.role_breadth(p.BRAND_ADMIN) == max(p.role_breadth(r) for r in p.ROLES)


# === production independence from the audit tools ================================
# These run under normal Django collection (from bbrose_design_os) and prove the
# production app owns its policy: it neither imports `tools` nor needs a sys.path hack.
def test_production_settings_do_not_hack_sys_path_for_policy():
    from pathlib import Path

    from django.conf import settings
    src = (Path(settings.BASE_DIR) / "config" / "settings.py").read_text()
    assert "REPO_ROOT" not in src, "the repo-root sys.path insert must stay removed"
    assert "sys.path.insert" not in src


def test_no_accounts_module_imports_the_tools_package():
    import ast
    from pathlib import Path

    from django.conf import settings
    acc = Path(settings.BASE_DIR) / "apps" / "accounts"
    offenders = []
    for py in acc.rglob("*.py"):
        if py.name.startswith("test_"):
            continue                    # tests may add the path to check parity
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods = [node.module]
            if any(m == "tools" or m.startswith("tools.") for m in mods):
                offenders.append(py.name)
    assert not offenders, f"accounts modules must not import tools: {offenders}"


# === §AT — parity, measured where import order cannot reach it ==================
# The previous version of this test inserted the repo root into `sys.path` and
# imported `tools.dip0c.authz` in-process. It PASSED ALONE and failed in the
# suite, and the reason was inside its own docstring ("adds the repo root to
# sys.path itself — proving parity"): there are two directories named `tools`,
# the git-root one WITH `__init__.py` holding dip0c and the pytest-root one
# WITHOUT. Once anything has done `import tools.anything`, `tools` is bound as a
# PEP 420 namespace package rooted at the pytest root, and recomputation of a
# namespace `__path__` collects only namespace portions — so a directory
# carrying `__init__.py` cannot join it. The insert is a no-op the moment it is
# not first, and the verdict tracked WHICH MODULE BOUND `tools` FIRST while the
# name and the assertions said parity. AD0(b).
#
# The parity CLAIM was never in doubt and is unchanged below. What moved is the
# instrument. `sys.modules` surgery would also work and would buy this test's
# correctness with 7,360 other tests' interpreter state, so the check runs in a
# fresh interpreter instead — which is also the claim stated exactly: in a
# process where both are imported, they are the same object.
_PARITY_CHILD = r"""
import sys
repo_root, extra = sys.argv[1], sys.argv[2]
sys.path.insert(0, repo_root)
from tools.dip0c import authz as wrapper
from apps.accounts import authz_policy as p

assert wrapper.ROLES == p.ROLES
assert wrapper.ACTIONS == p.ACTIONS
assert wrapper.POLICY is p.POLICY                 # the SAME object, not a copy
assert wrapper.SYSTEM_ADMIN_FORBIDDEN == p.SYSTEM_ADMIN_FORBIDDEN
for name in list(p.__all__) + ([extra] if extra else []):
    assert getattr(wrapper, name) is getattr(p, name), name
print("PARITY_OK %d" % len(p.__all__))
"""

# Proved the MECHANISM §AT ruled on (two `tools` directories, a namespace one winning); since the clean-up of
# 2026-10-04 there is ONE regular `tools` package in the app folder, holding the gate and dip0c both. The child now
# proves the hazard is gone, in a fresh interpreter so no host state is mutated.
_MECHANISM_CHILD = r"""
import sys
pytest_root, repo_root = sys.argv[1], sys.argv[2]
sys.path.insert(0, pytest_root)
import tools.tier2_gate                     # binds `tools` at the app folder
import tools
assert tools.__file__ is not None, "expected ONE regular package, got a PEP 420 namespace again"
from tools.dip0c import authz               # noqa: F401 — the same package holds dip0c
print("ONE_TOOLS_PACKAGE")
"""

def _roots():
    from pathlib import Path

    from django.conf import settings
    return str(settings.BASE_DIR), str(Path(settings.BASE_DIR))  # one `tools` package, in the app folder, since 2026-10-04


def _run_child(source, *args, cwd=None):
    """Run a child interpreter. ``cwd`` is NOT cosmetic: ``python -c`` puts the
    working directory at ``sys.path[0]``, so it decides which of the two `tools`
    directories the child resolves before any insert of ours is consulted. The
    parity child runs from the git root (the regular package, which holds
    dip0c); the mechanism child runs from the pytest root, because that is where
    the suite runs and the namespace binding is the thing being reproduced."""
    import subprocess
    import sys
    _, repo_root = _roots()
    # §AD2(d): the exit code is read off CompletedProcess, never through a
    # shell pipeline, where it would be the last command's and not the child's.
    return subprocess.run([sys.executable, "-c", source, *args],
                          cwd=(cwd or repo_root), capture_output=True,
                          text=True)


def test_wrapper_parity_when_tools_is_available():
    """When the audit tools ARE importable, the wrapper re-exports the canonical policy
    object-for-object. Measured in a fresh interpreter, so the verdict does not depend
    on what bound `tools` first; the tests above prove production never has to."""
    _, repo_root = _roots()
    result = _run_child(_PARITY_CHILD, repo_root, "")
    assert result.returncode == 0, result.stdout + result.stderr
    # the child asserted over EVERY exported name, not a shorter list it
    # happened to see — a loop that quietly got cheaper is the failure mode
    # a bare "it exited 0" cannot report.
    assert result.stdout.strip() == f"PARITY_OK {len(p.__all__)}"
    assert len(p.__all__) == 77, "__all__ moved; update deliberately"


def test_the_parity_check_survives_tools_being_bound_at_the_pytest_root():
    """§AT(3)(1) — the case that FAILED. This test binds `tools` at the pytest root
    itself rather than relying on some earlier test having done it, so the property
    is asserted here and does not depend on collection order."""
    import tools.tier2_gate  # noqa: F401 — binds `tools` at the PYTEST root
    _, repo_root = _roots()
    result = _run_child(_PARITY_CHILD, repo_root, "")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.startswith("PARITY_OK")


def test_the_two_tools_packages_are_one_since_the_clean_up():
    """§AT(0)'s measurement, re-taken after the clean-up of 2026-10-04 merged the git root's tools/ into the app's:
    `tools` binds as ONE regular package and dip0c is importable through it. If this ever fails, a second `tools`
    directory came back and §AT's namespace hazard with it."""
    pytest_root, repo_root = _roots()
    result = _run_child(_MECHANISM_CHILD, pytest_root, repo_root,
                        cwd=pytest_root)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ONE_TOOLS_PACKAGE" in result.stdout


def test_the_parity_child_fails_when_a_name_does_not_match():
    """§AT(3)(2) — the negative control. Without it, a child that silently stopped
    asserting would exit 0 and this file would report parity it never checked."""
    _, repo_root = _roots()
    bogus = "a_name_the_canonical_policy_does_not_export"
    assert not hasattr(p, bogus)
    result = _run_child(_PARITY_CHILD, repo_root, bogus)
    assert result.returncode != 0, result.stdout
    assert bogus in (result.stdout + result.stderr)
