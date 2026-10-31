"""A368 — a differential fixture is diffed against the control.

The `_pad` key made one refusal fire in all three conditions of A349's
own demonstration: a constant reason across distinct conditions, which
is verbatim what A349 exists to detect. Third time this arc a principle
was violated inside the node that established it.

Cheap, mechanical, and it runs BEFORE the demonstration rather than
after: assert each condition's fixture differs from the control by
exactly the one intended perturbation.
"""


class FixtureContaminated(AssertionError):
    """The fixture differs from the control by more than the perturbation."""


def assert_single_perturbation(control, condition, expect, name=""):
    """expect: ('removed', key) | ('added', key) | ('changed', key)."""
    removed = sorted(set(control) - set(condition))
    added = sorted(set(condition) - set(control))
    changed = sorted(k for k in set(control) & set(condition)
                     if control[k] != condition[k])
    actual = ([("removed", k) for k in removed]
              + [("added", k) for k in added]
              + [("changed", k) for k in changed])
    if actual != [expect]:
        raise FixtureContaminated(
            f"{name}: fixture differs from control by {actual}, "
            f"intended exactly [{expect}]")
    return True
