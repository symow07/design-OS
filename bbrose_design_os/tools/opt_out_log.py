"""A328 — the named opt-out is COUNTED, with its reason, per use.

An opt-out exercised routinely is an unproven gate wearing a proven
gate's record: A319's condition returning by a different door. Expected
count per node is zero; a nonzero count is a finding, not a footnote.
"""
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "docs/roadmap/palt_m6/opt_out_log.json")
#: A328 defect found in my own implementation: harness invocations were
#: writing the TRACKED record, so the suite mutated a docs file on every
#: run and the count grew monotonically with test runs. "Expected zero,
#: nonzero is a finding" was dead on arrival — the signal was buried
#: under harness noise. Dry-run uses now go to an ignored path; the
#: tracked record counts only uses that could have produced a commit.
HARNESS_LOG = os.path.join(ROOT, ".opt_out_harness_log")


def record(reason, dry_run):
    dry = bool(int(dry_run))
    path = HARNESS_LOG if dry else LOG
    log = (json.load(open(path)) if os.path.exists(path)
           else {"record_type": "extent_opt_out_log/1.0", "uses": []})
    log["uses"].append({"utc": datetime.datetime.utcnow().isoformat() + "Z",
                        "reason": reason, "dry_run": dry})
    log["count_total"] = len(log["uses"])
    log["count_committing"] = sum(1 for u in log["uses"] if not u["dry_run"])
    json.dump(log, open(path, "w"), indent=1)
    return log


if __name__ == "__main__":
    record(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "0")
