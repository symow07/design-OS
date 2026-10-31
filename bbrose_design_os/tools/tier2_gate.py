"""A326/A327/3m — TIER_2: the full suite as DECLARED extent.

A338 PLANT: a false absolute claim was planted in this docstring during
the hostile suite and is removed here under A365's prohibition. The
plant, with its wording and commit, is recorded in
docs/roadmap/palt_m6/a365_claim_prohibition.json — kept out of the
instrument so the instrument carries no absolute claim at all, quoted
or otherwise. This gate refuses under the conditions enumerated in
check_manifest and main.

3l made TIER_1's extent declared. It did not stop ".suite_gate_result
says pass" and "the suite passes" from being the same sentence to a
reader who has only the artifact: the pass was determined in fact over
the TIER_1 files and read in law as the whole suite. That is 3k's shape
(A325).

TIER_2 therefore runs the whole suite, declares its extent as an
ENUMERATION of collected FILES (A327a — a total alone cannot detect a
file's disappearance, demonstrated by mutation), and dispositions the
result into artifact values, of which AMBER is NOT a pass.

    all pass                                   -> GREEN
    failure, ID registered, invocation left    -> consume one, AMBER
    failure, ID registered, invocations SPENT  -> REFUSE
    failure, ID unregistered                   -> REFUSE
    failure, ID registered at allowed 0        -> REFUSE

The last row is what keeps the register honest: registering an ID at
zero records the observation without buying relief. Being known about is
not relief (3m).

Usage:
    tier2_gate.py --check                 run and disposition; NO side effects
    tier2_gate.py --check --commit        as above, but consumes an invocation
    tier2_gate.py --regenerate-manifest   print the diff, then apply+record it
"""
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "docs/roadmap/palt_m6/suite_file_manifest.json")
REGISTER = os.path.join(ROOT, "docs/roadmap/palt_m6/flake_register.json")
DIFF_LOG = os.path.join(ROOT, "docs/roadmap/palt_m6/suite_manifest_diffs.json")
PYTEST = [os.path.join("venv", "bin", "python"), "-m", "pytest", "apps",
          "-q", "-p", "no:randomly"]

# §BH5(c)/§BH8(a) — THE GATE EXTENT WIDENS TO THE GIT-ROOT dip0c SUITE, at its
# FULL measured extent. The owner superseded his own "228": the ruled object is
# the whole suite, because "a widening that leaves 310 passing tests ungated
# while reporting the job done is exactly the defect this programme exists to
# refuse."
#
# IT IS A SEPARATE INVOCATION, AND THAT IS NOT A STYLE CHOICE. Appending the
# path to PYTEST above was tried first and MEASURED: it collects 13 ERRORS in
# apps/ire/tests/* — tests that pass today. Cause, verified with both controls
# rather than assumed: tools/dip0c/tests, tools/dip0c and tools/ each carry an
# __init__.py, so pytest's prepend import mode walks that unbroken chain up to
# the GIT ROOT and inserts it into sys.path. There, `tools` is a REGULAR
# package, while bbrose_design_os/tools is a NAMESPACE package (no __init__.py)
# — and a regular package found on sys.path wins outright, since namespace
# packages only form when no regular package is found. `tools.brand_strings`
# and `tools.reserved_copy` then vanish. One invocation cannot hold both roots'
# meaning of `tools` at once. Breaking 13 passing tests to gate 671 is the same
# defect the owner refused, wearing the other face, so the two roots are run in
# two processes and each keeps its own import context.
GIT_ROOT = os.path.dirname(ROOT); DIP_ROOT = ROOT  # the dip legs run from the app folder since the clean-up of 2026-10-04 (one tools/)
# ABSOLUTE interpreter: cwd is GIT_ROOT here, where "venv/bin/python" does not
# exist. A relative path would fail as a missing binary, not as a red suite.
DIP0C_PYTEST = [os.path.join(ROOT, "venv", "bin", "python"), "-m", "pytest", "-c", os.devnull, "--rootdir", ".", "-p", "no:django", "--confcutdir", "tools",
                os.path.join("tools", "dip0c", "tests"), "-q",
                "-p", "no:randomly"]
# MONOTONIC FLOOR, in code because §BH8(a) rules this commit code-only, so the
# manifest (a record, and digest-pinned) is not written here. Its job is the
# one failure this widening could otherwise hide: an invocation that collects
# NOTHING and reports zero failures is a clean exit with a wrong count — the
# defect class this project has already caught eight times. Measured 671.
DIP0C_FLOOR = 671

# §BH19(a) — A THIRD LEG, AND THE DEFECT THAT CAUSED IT STAYS ON THE RECORD.
# 8fd9541 widened the dip0 corpus walk to a second root and shipped 135 passing
# tests that THIS GATE COLLECTED WITH NEITHER LEG: the apps leg runs `pytest
# apps` from ROOT and cannot see the git root at all, and the dip0c leg targets
# tools/dip0c/tests — a different tree one letter away. That commit's
# TIER_2=GREEN was therefore not evidence about it, and its tests were run by
# hand. From the commit that adds this leg on, a green gate IS evidence about
# tools/dip0 changes. The owner ordered the leg and ruled that the finding
# "stands on the record as the reason", so it is written here and not just in
# the register: once the leg lands, 8fd9541 looks like every other green commit
# in the log, and this comment is the only thing that says otherwise.
#
# ITS OWN PROCESS, for the reason measured and documented above — tools/,
# tools/dip0/ and tools/dip0/tests/ carry the identical unbroken __init__.py
# chain to dip0c's, so this leg reaches sys.path the same way and collides with
# bbrose_design_os/tools the same way. Two roots, three processes, each keeping
# its own meaning of `tools`.
DIP0_PYTEST = [os.path.join(ROOT, "venv", "bin", "python"), "-m", "pytest", "-c", os.devnull, "--rootdir", ".", "-p", "no:django", "--confcutdir", "tools",
               os.path.join("tools", "dip0", "tests"), "-q",
               "-p", "no:randomly"]
# §BH19(a) — "the floor value is yours, by measurement at build time". MEASURED
# 135 at build time, counted the gate's own way (node ids from --collect-only,
# not a summary line), with the collection's own returncode checked as 0 so the
# number is an extent and not the truncated output of a broken collection:
# 111 pre-existing + 24 added by 8fd9541. It is NOT rounded down to leave slack
# — a floor with slack in it is a floor that cannot refuse the first deletion,
# which is the whole failure it exists to catch.
DIP0_FLOOR = 135

# §BH55 Phase 4 — A FOURTH LEG, AND THE SAME DEFECT ONE LETTER FURTHER ALONG. The owner's Phase 4 names "dip0b
# ungated". Measured at build time: tools/dip0b/tests holds 232 tests (test_b1 51, test_b2 56, test_b3 47, test_b4 41,
# test_b5 37), all passing, and NO leg of this gate collected one of them — the apps leg cannot see the git root, the
# dip0c leg targets tools/dip0c/tests and the dip0 leg tools/dip0/tests. That is §BH19(a)'s finding repeating: every
# TIER_2=GREEN since dip0b was written was not evidence about it. From this leg on, it is.
#
# ITS OWN PROCESS, for the reason the two legs above already measure: tools/, tools/dip0b/ and tools/dip0b/tests/ carry
# the same unbroken __init__.py chain to the git root, so a single invocation cannot hold both roots' meaning of
# `tools`. Two roots, four processes.
DIP0B_PYTEST = [os.path.join(ROOT, "venv", "bin", "python"), "-m", "pytest", "-c", os.devnull, "--rootdir", ".", "-p", "no:django", "--confcutdir", "tools",
                os.path.join("tools", "dip0b", "tests"), "-q",
                "-p", "no:randomly"]
# MEASURED 232 at build time, counted the gate's own way (node ids from --collect-only, with the collection's own
# returncode checked), not rounded down: a floor with slack cannot refuse the first deletion.
DIP0B_FLOOR = 232


def collected_counts():
    """Per-file collected counts for the whole run."""
    proc = subprocess.run(PYTEST + ["--collect-only"],
                          capture_output=True, text=True, cwd=ROOT)
    counts = {}
    for line in proc.stdout.splitlines():
        if "::" in line:
            f = line.split("::", 1)[0].strip()
            counts[f] = counts.get(f, 0) + 1
    return counts, proc.returncode


def dip0c_collected():
    """Collected count for the git-root dip0c suite, counted the same way
    collected_counts() counts — by enumerating node ids, not by trusting a
    summary line."""
    proc = subprocess.run(DIP0C_PYTEST + ["--collect-only"],
                          capture_output=True, text=True, cwd=DIP_ROOT)
    n = sum(1 for line in proc.stdout.splitlines() if "::" in line)
    return n, proc.returncode


def dip0c_run():
    """Run the widened extent. Returns (failures, returncode, stdout)."""
    proc = subprocess.run(DIP0C_PYTEST, capture_output=True, text=True,
                          cwd=DIP_ROOT)
    return failed_ids(proc.stdout), proc.returncode, proc.stdout


def dip0_collected():
    """§BH19(a) — collected count for the git-root dip0 suite, counted the
    same way both other legs count: by enumerating node ids, never by
    trusting a summary line."""
    proc = subprocess.run(DIP0_PYTEST + ["--collect-only"],
                          capture_output=True, text=True, cwd=DIP_ROOT)
    n = sum(1 for line in proc.stdout.splitlines() if "::" in line)
    return n, proc.returncode


def dip0_run():
    """§BH19(a) — run the third leg. Returns (failures, returncode, stdout)."""
    proc = subprocess.run(DIP0_PYTEST, capture_output=True, text=True,
                          cwd=DIP_ROOT)
    return failed_ids(proc.stdout), proc.returncode, proc.stdout


def dip0b_collected():
    """§BH55 Phase 4 — collected count for the git-root dip0b suite, counted the way every other leg counts it: by
    enumerating node ids, never by trusting a summary line."""
    proc = subprocess.run(DIP0B_PYTEST + ["--collect-only"],
                          capture_output=True, text=True, cwd=DIP_ROOT)
    n = sum(1 for line in proc.stdout.splitlines() if "::" in line)
    return n, proc.returncode


def dip0b_run():
    """§BH55 Phase 4 — run the fourth leg. Returns (failures, returncode, stdout)."""
    proc = subprocess.run(DIP0B_PYTEST, capture_output=True, text=True,
                          cwd=DIP_ROOT)
    return failed_ids(proc.stdout), proc.returncode, proc.stdout


def manifest_digest():
    return hashlib.sha256(open(MANIFEST, "rb").read()).hexdigest()[:16]


def check_manifest(counts):
    """A327 — (a) file-set equality, (b) TIER_1 floors, (c) total floor."""
    # A352 repair 3: the manifest stays a file, but its DIGEST lives in
    # the hashed corpus, so it can no longer be edited without
    # protocol_identity() moving. Verified BEFORE the file is read.
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from apps.pipeline.services import palette_powder_protocol as _PP
    declared_digest = _PP.EXTENT_DIGESTS["suite_file_manifest"]
    actual = manifest_digest()
    if actual != declared_digest:
        return ([f"MANIFEST_DIGEST_MISMATCH: {actual} != hashed "
                 f"{declared_digest} — the manifest was edited outside "
                 "the identity chain"], 0)
    m = json.load(open(MANIFEST))
    refusals = []

    # (a) THE LOAD-BEARING CLAUSE. The set is enumerated, so a file's
    # disappearance is detectable; a total is not sensitive to it.
    declared, actual_files = set(m["files"]), set(counts)
    for f in sorted(declared - actual_files):
        refusals.append(f"MANIFEST_FILE_MISSING: {f} declared but not collected")
    for f in sorted(actual_files - declared):
        refusals.append(f"MANIFEST_FILE_UNDECLARED: {f} collected but not declared")

    # (b) per-file floors, TIER_1 files only
    for f, floor in m["tier1_floors"].items():
        if counts.get(f, 0) < floor:
            refusals.append(
                f"TIER1_FLOOR: {f} collected {counts.get(f, 0)} < {floor}")

    # (c) coarse backstop, explicitly NOT the declaration
    total = sum(counts.values())
    if total < m["total_floor"]:
        refusals.append(
            f"TOTAL_FLOOR: collected {total} < {m['total_floor']}")
    return refusals, total


#: A352 repair 1. The dimension is HOW A RUN CAN FAIL: clean pass /
#: FAILED assertion / ERROR in setup or teardown / collection error /
#: non-zero exit with no parseable id. The previous implementation
#: enumerated the first failure cell only and silently treated the
#: other three as a pass — an errored suite dispositioned GREEN.
def failed_ids(output):
    return sorted({m.group(1) for m in
                   re.finditer(r"^(?:FAILED|ERROR) (\S+)", output, re.M)})


class UnnormalizableNodeId(RuntimeError):
    """A366 — refuses rather than falling through to UNREGISTERED."""


def normalize_node_id(node_id):
    """A366/A355 — pytest emits ids relative to its invocation rootdir.
    A register key stored in one form and emitted in another makes a
    CORRECTLY registered flake present as UNREGISTERED, collapsing the
    register's most important distinction. The fall-through is the
    dangerous half, so an id that resists rootdir-relative
    normalization REFUSES explicitly instead."""
    path, sep, rest = node_id.partition("::")
    if not sep:
        raise UnnormalizableNodeId(
            f"no '::' in {node_id!r} — not a pytest node id")
    norm = os.path.normpath(path)
    if os.path.isabs(norm):
        try:
            norm = os.path.relpath(norm, ROOT)
        except ValueError as exc:
            raise UnnormalizableNodeId(
                f"{path!r} is not expressible relative to {ROOT}") from exc
    while norm.startswith(".." + os.sep):
        stripped = norm.split(os.sep)
        if ROOT.split(os.sep)[-1] in stripped:
            norm = os.sep.join(stripped[stripped.index(
                ROOT.split(os.sep)[-1]) + 1:])
        else:
            raise UnnormalizableNodeId(
                f"{path!r} escapes {ROOT} and cannot be made relative")
    return f"{norm}::{rest}"


def disposition(failures, register=None, consume=False):
    """A326's five rows. Returns (value, details). AMBER is not a pass."""
    reg = register if register is not None else json.load(open(REGISTER))
    flakes = reg["flakes"]
    details = {"failures": failures, "consumed": [], "refusals": []}
    if not failures:
        return "GREEN", details
    normalized = {}
    for raw in failures:
        try:
            normalized[raw] = normalize_node_id(raw)
        except UnnormalizableNodeId as exc:
            details["refusals"].append(f"UNNORMALIZABLE_NODE_ID: {exc}")
    for raw in failures:
        if raw not in normalized:
            continue
        fid = normalized[raw]
        entry = flakes.get(fid) or flakes.get(raw)
        if entry is None:
            details["refusals"].append(f"UNREGISTERED: {fid}")
        elif entry["invocations_allowed"] == 0:
            details["refusals"].append(
                f"REGISTERED_AT_ZERO: {fid} — being known about is not relief")
        elif entry["invocations_used"] >= entry["invocations_allowed"]:
            details["refusals"].append(f"INVOCATIONS_SPENT: {fid}")
        else:
            remaining = (entry["invocations_allowed"]
                         - entry["invocations_used"] - 1)
            if consume:
                entry["invocations_used"] += 1
            details["consumed"].append({"id": fid, "remaining": remaining})
    if details["refusals"]:
        return "REFUSE", details
    return "AMBER", details


def raised_floors(old_floors, counts):
    """AR3(d)/AR4(3) — floors are MONOTONIC: re-measured on every
    regeneration, and never lowered.

    Both halves are load-bearing and they close opposite defects.

    NEVER LOWERED is the older half. A regeneration that could reduce a
    floor would be the §AL4 move in a different file: run the tool, get a
    smaller number, call the smaller number the standard. Under `max` the
    tool cannot buy relief no matter what it measures, so a caller who
    wants a floor lowered has to say so in a diff, by hand, in writing.

    RE-MEASURED is the half AR exists because of. Until this change the
    floors were carried forward verbatim -- `old.get("tier1_floors", {})`
    -- so a floor moved only when someone hand-edited a file whose digest
    sits in EXTENT_DIGESTS, at the price of a full A391 re-pin to change
    one integer. What that cost bought is measurable rather than
    predictable: between 2026-08-12 and 2026-08-20 nobody paid it, and
    test_characterization_protocol.py sat at 28 against a measured 59 --
    inside the gate that exists because that exact file once went to ZERO
    BYTES. §AJ diagnosed the identical staleness in guarded_commit.sh at
    WI-3G and repaired one of the two copies.

    A tier-1 file that has stopped being collected reports 0 here, so its
    floor holds rather than collapsing; its absence is A327(a)'s to
    refuse on, and one clause failing open into another is how the
    zero-bytes defect happened the first time.
    """
    return {f: max(floor, counts.get(f, 0)) for f, floor in old_floors.items()}


def regenerate_manifest(apply_it=True):
    """A327 — a manifest that can be SILENTLY refreshed is not a manifest.
    This prints the diff it is about to apply, and records it."""
    counts, _ = collected_counts()
    old = json.load(open(MANIFEST)) if os.path.exists(MANIFEST) else {"files": []}
    added = sorted(set(counts) - set(old["files"]))
    removed = sorted(set(old["files"]) - set(counts))
    print("MANIFEST DIFF TO BE APPLIED:")
    print(f"  added   ({len(added)}):")
    for f in added:
        print(f"    + {f}")
    print(f"  removed ({len(removed)}):")
    for f in removed:
        print(f"    - {f}")
    if not apply_it:
        return added, removed
    # A352 repair 5: the diff is not applied until every candidate has
    # been classified. Previously it printed and applied unconditionally
    # — REPORT_BEFORE_CLASSIFY in the one tool built to prevent it.
    import importlib.util
    _s = importlib.util.spec_from_file_location(
        "sweep_manifest", os.path.join(ROOT, "tools", "sweep_manifest.py"))
    SM = importlib.util.module_from_spec(_s)
    _s.loader.exec_module(SM)
    probe = os.path.join(ROOT, ".manifest_regen_candidates.json")
    SM.build_manifest(
        [{"path": f, "match": "added"} for f in added]
        + [{"path": f, "match": "removed"} for f in removed],
        lambda c: "GENUINE" if c["path"].endswith(".py") else None, probe)
    SM.writable(probe)
    stamp = datetime.datetime.utcnow().isoformat() + "Z"
    log = json.load(open(DIFF_LOG)) if os.path.exists(DIFF_LOG) else {
        "record_type": "suite_manifest_diffs/1.0", "diffs": []}
    log["diffs"].append({"utc": stamp, "added": added, "removed": removed,
                         "files_after": len(counts)})
    json.dump(log, open(DIFF_LOG, "w"), indent=1)
    json.dump({"record_type": "suite_file_manifest/1.0",
               "generated": stamp,
               "declaration_is_the_file_set_not_the_total": True,
               "files": sorted(counts),
               "tier1_floors": raised_floors(old.get("tier1_floors", {}),
                                             counts),
               "total_floor": max(old.get("total_floor", 0),
                                  sum(counts.values()))},
              open(MANIFEST, "w"), indent=1)
    return added, removed


def main(argv):
    if "--regenerate-manifest" in argv:
        regenerate_manifest()
        return 0
    counts, rc = collected_counts()
    refusals, total = check_manifest(counts)
    # §BH5(c) — the widened extent is asserted BEFORE it is run, for the same
    # reason the manifest is: a suite that silently collects nothing would
    # otherwise report zero failures and read as a pass.
    dip_n, dip_rc = dip0c_collected()
    if dip_rc != 0:
        refusals.append(
            f"DIP0C_COLLECT_ERROR: exit {dip_rc} collecting {DIP0C_PYTEST[3]} "
            "— a collection that errors is not an extent")
    if dip_n < DIP0C_FLOOR:
        refusals.append(
            f"DIP0C_FLOOR: collected {dip_n} < {DIP0C_FLOOR}")
    # §BH19(a) — the third leg, asserted before it is run for the same reason.
    dip0_n, dip0_rc = dip0_collected()
    if dip0_rc != 0:
        refusals.append(
            f"DIP0_COLLECT_ERROR: exit {dip0_rc} collecting {DIP0_PYTEST[3]} "
            "— a collection that errors is not an extent")
    if dip0_n < DIP0_FLOOR:
        refusals.append(
            f"DIP0_FLOOR: collected {dip0_n} < {DIP0_FLOOR}")
    # §BH55 Phase 4 — the fourth leg, asserted before it is run for the same reason as the other three.
    dip0b_n, dip0b_rc = dip0b_collected()
    if dip0b_rc != 0:
        refusals.append(
            f"DIP0B_COLLECT_ERROR: exit {dip0b_rc} collecting {DIP0B_PYTEST[3]} "
            "— a collection that errors is not an extent")
    if dip0b_n < DIP0B_FLOOR:
        refusals.append(
            f"DIP0B_FLOOR: collected {dip0b_n} < {DIP0B_FLOOR}")
    if refusals:
        print("TIER_2_REFUSED: declared extent not met (A327/3m)",
              file=sys.stderr)
        for r in refusals:
            print(f"  {r}", file=sys.stderr)
        print("TIER_2=REFUSE")
        return 1
    proc = subprocess.run(PYTEST, capture_output=True, text=True, cwd=ROOT)
    # A369/3p — CAPTURE_WITHOUT_RETENTION: a fixed path overwritten each
    # run satisfies the letter of capture-then-display while destroying
    # the series as it is made. Captures are keyed by timestamp and
    # commit and retained.
    caps = os.path.join(ROOT, ".tier2_captures")
    os.makedirs(caps, exist_ok=True)
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True, cwd=ROOT).stdout.strip()
    stamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    open(os.path.join(caps, f"{stamp}_{head}.txt"), "w").write(
        f"returncode={proc.returncode}\n{proc.stdout}")
    failures = failed_ids(proc.stdout)
    # §BH5(c) — the widened half, run in its own process and its own root.
    dip_failures, dip_rc, dip_out = dip0c_run()
    open(os.path.join(caps, f"{stamp}_{head}_dip0c.txt"), "w").write(
        f"returncode={dip_rc}\n{dip_out}")
    # §BH19(a) — the third leg, captured under its own key. A shared capture
    # file would make the series unreadable exactly where two legs disagree.
    dip0_failures, dip0_rc, dip0_out = dip0_run()
    open(os.path.join(caps, f"{stamp}_{head}_dip0.txt"), "w").write(
        f"returncode={dip0_rc}\n{dip0_out}")
    # §BH55 Phase 4 — the fourth leg, captured under its own key for the same reason.
    dip0b_failures, dip0b_rc, dip0b_out = dip0b_run()
    open(os.path.join(caps, f"{stamp}_{head}_dip0b.txt"), "w").write(
        f"returncode={dip0b_rc}\n{dip0b_out}")
    # A352 repair 1: the RETURNCODE is the primary signal. A non-zero
    # exit with nothing parseable is a refusal, never an empty pass.
    # Applied to BOTH halves: the widening must not add a leg that can fail
    # in a way the parser cannot name and be read as silence.
    if proc.returncode != 0 and not failures:
        print(f"TIER_2=REFUSE collected={total} "
              f"unparseable_nonzero_exit={proc.returncode}")
        print("  NONZERO_EXIT_NO_PARSED_ID: the run failed in a way this "
              "parser does not name — refusing rather than reading "
              "silence as success", file=sys.stderr)
        return 1
    if dip_rc != 0 and not dip_failures:
        print(f"TIER_2=REFUSE collected={total + dip_n} "
              f"dip0c_unparseable_nonzero_exit={dip_rc}")
        print("  DIP0C_NONZERO_EXIT_NO_PARSED_ID: the widened extent failed "
              "in a way this parser does not name — refusing rather than "
              "reading silence as success", file=sys.stderr)
        return 1
    if dip0_rc != 0 and not dip0_failures:
        print(f"TIER_2=REFUSE collected={total + dip_n + dip0_n} "
              f"dip0_unparseable_nonzero_exit={dip0_rc}")
        print("  DIP0_NONZERO_EXIT_NO_PARSED_ID: the third leg failed in a "
              "way this parser does not name — refusing rather than reading "
              "silence as success", file=sys.stderr)
        return 1
    if dip0b_rc != 0 and not dip0b_failures:
        print(f"TIER_2=REFUSE collected={total + dip_n + dip0_n + dip0b_n} "
              f"dip0b_unparseable_nonzero_exit={dip0b_rc}")
        print("  DIP0B_NONZERO_EXIT_NO_PARSED_ID: the fourth leg failed in a "
              "way this parser does not name — refusing rather than reading "
              "silence as success", file=sys.stderr)
        return 1
    failures = sorted(set(failures) | set(dip_failures) | set(dip0_failures)
                      | set(dip0b_failures))
    reg = json.load(open(REGISTER))
    # A352 repair 4: --check is SIDE-EFFECT-FREE. Consumption happens
    # only on the committing path (--commit), so observing the gate
    # can no longer spend a finite allowance.
    consume = "--commit" in argv
    value, details = disposition(failures, reg, consume=consume)
    if details["consumed"]:
        json.dump(reg, open(REGISTER, "w"), indent=1, sort_keys=True)
    # 3m — the pass carries its EXTENT. `collected` is now the WIDENED total,
    # and the split is printed beside it so a reader cannot mistake which half
    # was run, nor read the old narrow number as the new wide one.
    print(f"TIER_2={value} collected={total + dip_n + dip0_n + dip0b_n} "
          f"failures={len(failures)} apps={total} dip0c={dip_n} "
          f"dip0={dip0_n} dip0b={dip0b_n}")
    for c in details["consumed"]:
        print(f"  AMBER_CONSUMED: {c['id']} remaining={c['remaining']}")
    for r in details["refusals"]:
        print(f"  {r}", file=sys.stderr)
    return 0 if value in ("GREEN", "AMBER") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
