"""The one thing that must stay true about Illustrator verification.

This string has now moved three times — REQUIRED_BEFORE_PRODUCTION_AUTHORITY,
then PENDING_HUMAN_EXECUTION, then FAILED_PENDING_CORRECTED_SOURCE, then
FAILED_PENDING_GATE_A_R2_SOURCE — and each move broke a batch of tests that had
pinned the literal of the slice they were written in. Enumerating the allowed
values just queues up the same breakage for the next revision.

What actually has to hold is that verification has never passed. Assert that,
and a new failure or pending state costs nothing while a false pass is still
caught.
"""

_PASS_MARKERS = ("PASS", "VERIFIED", "COMPLETE", "GRANTED", "APPROVED")


def not_passed(state):
    """True when this state does not claim Illustrator verification succeeded.

    Deliberately permissive about HOW it has not passed and strict about
    whether it has.

    Scope: the VERIFICATION-state fields only — vq2_state's
    ILLUSTRATOR_EXECUTION_VERIFICATION, the receipts' verification_state, the
    checklist's state. Do NOT apply it to a field that legitimately reports a
    sub-result: "INITIAL_OPEN_PASSED_ROUNDTRIP_PENDING" is an accurate
    correction state and contains PASSED, so this would reject it. For those,
    assert the specific invariant (roundtrip_performed is False, gate state
    BLOCKED) rather than reaching for this.
    """
    s = (state or "").upper()
    return bool(s) and not any(m in s for m in _PASS_MARKERS)


def assert_not_passed(state, label=""):
    assert not_passed(state), f"{label} claims a pass: {state!r}"


# --------------------------------------------------------------------------
# After Gate A
# --------------------------------------------------------------------------
# Gate A passed on 2026-07-31, after four failed Illustrator runs. The slices
# that RECORDED those failures had tests asserting the LIVE gate state, which
# has legitimately moved on. Those slices should assert their own preserved
# evidence instead — the failure each of them captured is still true and still
# on disk. What stays true globally is narrower: Gate A is the only gate that
# passed, and nothing downstream of it started.

SUPPLIER_GATES = ("B_supplier_geometry", "C_flat_artwork",
                  "D_colour_separation", "E_material_specification")


def assert_only_gate_a_passed(gates):
    """Gate A passed; the four supplier gates did not, and nothing started."""
    assert gates["gates"]["A_illustrator_execution"]["state"] == "PASSED"
    assert gates["gates_passed"] == 1
    for name in SUPPLIER_GATES:
        assert gates["gates"][name]["state"] == "BLOCKED", name
        assert gates["gates"][name]["evidence_present"] is False, name
    assert gates["packaging_may_begin_now"] is False
    assert gates["supplier_requests_sent"] == 0
