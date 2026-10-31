"""Permanent governance rules derived from defects this programme found.

Each rule here exists because something shipped that looked correct and
was not. They are enforced as callable checks rather than written down,
because every one of these defects survived a review that had the rule
written down somewhere.

A — FALSIFIABILITY. A check that cannot fail is not evidence.
B — EVIDENCE IDENTITY. Mesh identity alone cannot identify an evidence
    revision; A3F and A3M legitimately share geometry.
C — CONFIRMATION GOVERNANCE. Confirming a reading never grants a gate.
D — AUDIT TRAIL. A revision records what changed, not a replayed history.
E — TYPED INTENT. Semantic types survive the UI, storage and mapping.
F — REVISION REACHABILITY. A governed action must exist, not just a log.
G — TEST DATABASE ISOLATION. Overlapping runs produce invalid evidence.
"""
from __future__ import annotations

from dataclasses import dataclass

SCHEMA = "palette_governance/1.0"

DISCRIMINATING = "DISCRIMINATING"
NON_DISCRIMINATING = "NON_DISCRIMINATING_BY_CONSTRUCTION"

#: Statuses a design-intent confirmation may never set by itself.
FORBIDDEN_IMPLICIT_STATUSES = ("gate_1_approved", "gate_2_approved")

#: What an evidence reference must carry to be resolvable.
EVIDENCE_IDENTITY_FIELDS = (
    "milestone", "revision", "purpose", "geometry_identity",
    "contract_identity", "evidence_identity",
)

#: What a revision record may contain. Anything else is replayed history.
REVISION_RECORD_FIELDS = (
    "field", "old_value", "new_value", "actor", "timestamp",
    "source_revision", "resulting_revision",
)


class GovernanceViolation(AssertionError):
    """Raised when a governance rule is broken."""


# --------------------------------------------------------------------------
# Rule A — falsifiability
# --------------------------------------------------------------------------

@dataclass
class NegativeControl:
    """A case a check MUST reject, paired with one it must accept."""
    name: str
    passing_input: object
    failing_input: object


def assert_falsifiable(check, control: NegativeControl):
    """A check must accept the passing case and REJECT the failing one.

    A check that returns the same verdict for both is comparing a constant
    with itself, is hardcoded, or reads its expected value out of its own
    input — the three shapes this programme found repeatedly.
    """
    good = check(control.passing_input)
    bad = check(control.failing_input)
    if not good:
        raise GovernanceViolation(
            f"{control.name}: the check rejected its own passing case")
    if bad:
        raise GovernanceViolation(
            f"{control.name}: the check ACCEPTED its negative control, so "
            "it cannot fail and is not evidence")
    return True


def classify_metric(*, can_fail_for_a_valid_build: bool) -> str:
    """A metric whose pass condition is also the construction rule is
    NON_DISCRIMINATING_BY_CONSTRUCTION and must be excluded from
    owner-facing scores rather than quietly inflating them."""
    return DISCRIMINATING if can_fail_for_a_valid_build \
        else NON_DISCRIMINATING


def owner_facing_score(rows) -> dict:
    """Score only the metrics that can discriminate."""
    disc = [r for r in rows
            if r.get("discriminating_power", DISCRIMINATING)
            == DISCRIMINATING]
    excluded = [r["metric"] for r in rows if r not in disc]
    passed = [r["metric"] for r in disc if r.get("verdict") == "PASS"]
    failed = [r["metric"] for r in disc if r.get("verdict") == "FAIL"]
    return {"discriminating_passed": passed, "discriminating_failed": failed,
            "excluded_from_score": excluded,
            "score": round(len(passed) / len(disc), 6) if disc else None}


# --------------------------------------------------------------------------
# Rule B — evidence identity
# --------------------------------------------------------------------------

def assert_evidence_resolvable(reference: dict):
    """Mesh identity alone cannot identify an evidence revision.

    A3F and A3M share one corrected geometry and legitimately require
    different labels, so resolving evidence by geometry alone silently
    mislabels one of them.
    """
    missing = [f for f in EVIDENCE_IDENTITY_FIELDS if not reference.get(f)]
    if missing:
        raise GovernanceViolation(
            f"evidence reference cannot be resolved: missing {missing}. "
            "Geometry identity alone is ambiguous across milestones.")
    return True


# --------------------------------------------------------------------------
# Rule C — confirmation governance
# --------------------------------------------------------------------------

def assert_no_implicit_gate_approval(status_before, status_after):
    """Confirming a READING may not grant a gate."""
    if status_after in FORBIDDEN_IMPLICIT_STATUSES \
            and status_before not in FORBIDDEN_IMPLICIT_STATUSES:
        raise GovernanceViolation(
            f"a design-intent confirmation moved the task to "
            f"{status_after!r}. Only a separate governed gate action may "
            "do that.")
    return True


# --------------------------------------------------------------------------
# Rule D — audit trail
# --------------------------------------------------------------------------

def revision_delta(old_fields: dict, new_fields: dict, *, actor,
                   timestamp, source_revision, resulting_revision) -> list:
    """The minimal record: only what actually changed.

    Replaying a canonical historical decision set and attributing it to
    the current actor produces a record that says someone decided things
    they never touched.
    """
    rows = []
    for name in sorted(set(old_fields) | set(new_fields)):
        old, new = old_fields.get(name), new_fields.get(name)
        if old == new:
            continue
        rows.append({"field": name, "old_value": old, "new_value": new,
                     "actor": actor, "timestamp": timestamp,
                     "source_revision": source_revision,
                     "resulting_revision": resulting_revision})
    return rows


def assert_revision_record_minimal(rows):
    for row in rows:
        extra = set(row) - set(REVISION_RECORD_FIELDS)
        if extra:
            raise GovernanceViolation(
                f"revision record carries {sorted(extra)}, which is not a "
                "record of what changed")
        if row["old_value"] == row["new_value"]:
            raise GovernanceViolation(
                f"revision record includes {row['field']!r}, which did not "
                "change — that is replayed history, not a decision")
    return True


# --------------------------------------------------------------------------
# Rule E — typed intent
# --------------------------------------------------------------------------

class TypeCoercionError(ValueError):
    """Raised when a submitted value cannot become the field's type."""


def coerce_to_type(current, raw):
    """Coerce a submitted string to the type the field already holds.

    Every form value arrives as a string. Persisting "12" where the field
    holds 12 breaks every downstream comparison, and the failure surfaces
    far from its cause.
    """
    if current is None:
        return raw
    if isinstance(current, bool):
        low = str(raw).strip().lower()
        if low in ("true", "yes", "1", "on"):
            return True
        if low in ("false", "no", "0", "off"):
            return False
        raise TypeCoercionError(
            f"expected a yes/no value, got {raw!r}")
    if isinstance(current, int):
        try:
            return int(str(raw).strip())
        except ValueError:
            raise TypeCoercionError(
                f"expected a whole number, got {raw!r}") from None
    if isinstance(current, float):
        try:
            return float(str(raw).strip())
        except ValueError:
            raise TypeCoercionError(
                f"expected a number, got {raw!r}") from None
    if isinstance(current, (list, tuple)):
        return [p.strip() for p in str(raw).split(",") if p.strip()]
    if isinstance(current, dict):
        raise TypeCoercionError(
            "structured objects cannot be edited as a single text value")
    return raw


def assert_type_preserved(before, after):
    if type(before) is not type(after):
        raise GovernanceViolation(
            f"semantic type changed from {type(before).__name__} to "
            f"{type(after).__name__}")
    return True


# --------------------------------------------------------------------------
# Rules F and G
# --------------------------------------------------------------------------

def assert_revision_reachable(*, action_exists: bool, history_shown: bool):
    """History-only display is insufficient."""
    if history_shown and not action_exists:
        raise GovernanceViolation(
            "revision history is displayed but no governed action creates a "
            "new revision; the loop is unreachable from the interface")
    return True


RULES = {
    "A_FALSIFIABILITY": {
        "statement": "every validator or fidelity metric has a negative "
                     "control that demonstrably fails it",
        "enforced_by": "assert_falsifiable / classify_metric",
        "kind": "ENFORCED",
    },
    "B_EVIDENCE_IDENTITY": {
        "statement": "evidence resolution carries milestone, revision, "
                     "purpose and all three identities",
        "enforced_by": "assert_evidence_resolvable",
        "kind": "ENFORCED",
    },
    "C_CONFIRMATION_GOVERNANCE": {
        "statement": "confirming a reading never sets gate_1_approved or "
                     "gate_2_approved",
        "enforced_by": "assert_no_implicit_gate_approval",
        "kind": "ENFORCED",
    },
    "D_AUDIT_TRAIL": {
        "statement": "a revision records only what changed",
        "enforced_by": "revision_delta / assert_revision_record_minimal",
        "kind": "ENFORCED",
    },
    "E_TYPED_INTENT": {
        "statement": "semantic types survive UI, persistence and mapping",
        "enforced_by": "coerce_to_type / assert_type_preserved",
        "kind": "ENFORCED",
    },
    "F_REVISION_REACHABILITY": {
        "statement": "a governed action creates a new revision from a "
                     "confirmed one",
        "enforced_by": "assert_revision_reachable",
        "kind": "ENFORCED",
    },
    "G_TEST_DATABASE_ISOLATION": {
        "statement": "no two database-mutating processes run against one "
                     "test database; a result produced during overlap is "
                     "invalid evidence",
        "enforced_by": "OPERATIONAL_CONVENTION",
        "kind": "CONVENTION",
        "why_not_enforced": "a process cannot observe another process's "
                            "database use from inside the suite. Asserting "
                            "it here would be a check that cannot fail — "
                            "which rule A forbids.",
    },
}
