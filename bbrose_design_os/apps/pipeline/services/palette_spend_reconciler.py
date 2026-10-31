"""2l — declared spend reconciles both ways. The runner's completion
report is invalid without this; divergence in EITHER direction raises.
"""


class SpendDivergence(RuntimeError):
    """Declared spend and executed spend diverge. Never swallowed."""


def reconcile(declared: dict, executed: dict) -> dict:
    """Per-unit reconciliation. Raises SpendDivergence listing every
    divergent unit, both directions, before any completion may be
    reported."""
    problems = []
    for unit, dec in declared.items():
        got = executed[unit] if unit in executed else None
        if got is None:
            got = 0
        if got < dec:
            problems.append(f"{unit}: UNDER — declared {dec}, "
                            f"executed {got} (coverage gap, not a "
                            f"saving)")
        elif got > dec:
            problems.append(f"{unit}: OVER — declared {dec}, executed "
                            f"{got} (declaration failure, not an "
                            f"efficiency)")
    for unit in executed:
        if unit not in declared:
            problems.append(f"{unit}: UNDECLARED unit executed")
    if problems:
        raise SpendDivergence("; ".join(problems))
    return {"reconciled": True, "units": len(declared)}


def reconcile_calibration_unit(unit, frames_min, frames_max, realised,
                               iteration_log, window):
    """2r — a ranged calibration unit reconciles against the realised
    frame count AND the mechanism that produced it (the iteration
    log), never against the envelope. An envelope-internal count the
    law does not account for raises."""
    if not frames_min <= realised <= frames_max:
        raise SpendDivergence(
            f"{unit}: realised {realised} outside the declared "
            f"envelope [{frames_min}, {frames_max}]")
    n = len(iteration_log)
    if realised != 2 + n:
        raise SpendDivergence(
            f"{unit}: realised {realised} frames but the mechanism "
            f"accounts for probe+base+{n} iterations = {2 + n} — a "
            "count the law does not account for")
    if not 1 <= n <= 4:
        raise SpendDivergence(
            f"{unit}: {n} iterations is outside the law's own cap")
    lo, hi = window
    for i, it in enumerate(iteration_log):
        gate = it["clipped"] == 0 and lo <= it["peak"] <= hi
        final = i == n - 1
        if final and not gate:
            raise SpendDivergence(
                f"{unit}: final iteration fails the law's gate (peak "
                f"{it['peak']}, clipped {it['clipped']}) — an "
                "unconverged calibration reconciles nothing")
        if not final and gate:
            raise SpendDivergence(
                f"{unit}: iteration {i + 1} satisfied the gate yet "
                f"iteration {i + 2} ran — an envelope-internal count "
                f"the law does not account for")
    return {"unit": unit, "realised": realised, "iterations": n,
            "reconciled": True}


def reconcile_down_retry_unit(unit, realised, attempts, window_low):
    """2r/A122 — the down-side re-derivation: 1 frame reconciles only
    with an in-window unclipped first attempt; 2 frames only with a
    REFUSED first attempt (below window or clipped) followed by the
    declared retry — whatever the retry's own outcome, which maps to
    family disposition, not spend validity. A clean first attempt
    followed by a retry is an unexplained envelope-internal count."""
    if realised == 1:
        if len(attempts) != 1 or attempts[0]["clipped"] != 0 \
                or attempts[0]["peak"] < window_low:
            raise SpendDivergence(
                f"{unit}: 1 realised frame requires exactly one "
                "in-window unclipped attempt — the mechanism does not "
                "account for this count")
    elif realised == 2:
        if len(attempts) != 2:
            raise SpendDivergence(
                f"{unit}: 2 realised frames require exactly two "
                "recorded attempts")
        first_refused = attempts[0]["clipped"] != 0 \
            or attempts[0]["peak"] < window_low
        if not first_refused:
            raise SpendDivergence(
                f"{unit}: the first attempt satisfied the gate yet a "
                "retry ran — an envelope-internal count the law does "
                "not account for")
    else:
        raise SpendDivergence(
            f"{unit}: realised {realised} outside the declared "
            "envelope [1, 2]")
    return {"unit": unit, "realised": realised, "reconciled": True}


def reconcile_retry_unit(unit, realised, up_frames):
    """2r/A115b — the energy-control up-frame retry contingency:
    2 frames reconcile only with an unclipped up-frame; 3 frames only
    with a clipped first attempt and an unclipped declared retry."""
    if realised == 2:
        if len(up_frames) != 1 or up_frames[0]["clipped"] != 0:
            raise SpendDivergence(
                f"{unit}: 2 realised frames require exactly one "
                "unclipped up-frame — the mechanism does not account "
                "for this count")
    elif realised == 3:
        if len(up_frames) != 2 or up_frames[0]["clipped"] == 0 \
                or up_frames[1]["clipped"] != 0:
            raise SpendDivergence(
                f"{unit}: 3 realised frames require a clipped first "
                "up-frame and an unclipped declared retry — the "
                "mechanism does not account for this count")
    else:
        raise SpendDivergence(
            f"{unit}: realised {realised} outside the declared "
            "envelope [2, 3]")
    return {"unit": unit, "realised": realised, "reconciled": True}
