"""A188/A191 — the one-invocation condition, bound mechanically.

A191 splits the act in two, because the renewable bypass entered
through REGISTRATION rather than through the binding grain:

  registering a flake is recording an observation — free, the
  executor's, and to be done honestly and immediately, INCLUDING for a
  migrated symptom suspected of being the same underlying pollution,
  because the suspicion is data;

  granting the one pre-committed re-run is an authorization, and is
  not the executor's (2j).

A new registration therefore confers NO invocation: it records, stops
the node, and returns to the owner.

KNOWN LIMIT, recorded rather than closed: invocations bind to a TEST
ID. A flake whose symptom migrates to a neighbouring test presents as
an unregistered failure and will be reported as a finding. Binding to
a cause class instead is unavailable today — the cause is unestablished
(A189) — and inventing one would be the 3d defect. The split above is
what makes the limit survivable: an honestly-registered migrated
symptom still cannot buy a retry.

"Pre-commit to one more full run and report either way" is legitimate
exactly once against a given flake. Invoked a second time it becomes
run-it-until-green with a declaration stapled on, which looks governed
and is therefore worse than an ungoverned retry.

This runs inside the commit guard whenever the suite fails. It reads
the failing test ids, compares them against the registered flakes, and
either permits the single pre-committed re-run (consuming it, in the
register, in writing) or STOPS the node.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTER = os.path.join(ROOT, "docs", "roadmap", "palt_m6",
                        "flake_register.json")
FAILED = re.compile(r"^FAILED (\S+)", re.M)


def main(output_path):
    with open(output_path, errors="replace") as f:
        failures = set(FAILED.findall(f.read()))
    if not os.path.exists(REGISTER) or not failures:
        return 1
    with open(REGISTER) as f:
        reg = json.load(f)
    entries = reg.setdefault("flakes", {})

    stop, permitted, unknown, ungranted = [], [], [], []
    for test in sorted(failures):
        e = entries.get(test)
        if e is None:
            unknown.append(test)
        elif e.get("status") != "OPEN":
            unknown.append(test)
        elif e.get("invocations_allowed", 0) == 0:
            ungranted.append(test)
        elif e.get("invocations_used", 0) >= e.get("invocations_allowed", 0):
            stop.append(test)
        else:
            e["invocations_used"] = e.get("invocations_used", 0) + 1
            permitted.append(test)
    with open(REGISTER, "w") as f:
        json.dump(reg, f, indent=1, sort_keys=True)

    if unknown:
        print("SUITE FAILURE IS NOT A REGISTERED FLAKE — it is a "
              f"finding, not a retry: {unknown}", file=sys.stderr)
        return 1
    if ungranted:
        print("STOP AND RETURN TO OWNER (A191): these flakes are "
              "REGISTERED but carry NO GRANTED invocation. Registering "
              "is recording an observation and is free; GRANTING the "
              "pre-committed re-run is an authorization and is not the "
              f"executor's (2j): {ungranted}", file=sys.stderr)
        return 2
    if stop:
        print("STOP AND RETURN TO OWNER (A188): these flakes are "
              "already registered OPEN and their single pre-committed "
              f"re-run is spent: {stop}. A second occurrence is not "
              "retried.", file=sys.stderr)
        return 2
    print("ONE pre-committed re-run permitted and now CONSUMED for: "
          f"{permitted}. It cannot be invoked again for these.",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
