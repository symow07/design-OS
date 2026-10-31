"""A315/3l — the declared-extent assertion for the sanctioned commit path.

SILENT_EXTENT_LOSS (A316): a check whose failure mode is collecting
nothing, read through a channel that cannot represent the difference
between "ran and passed" and "did not run".
test_characterization_protocol.py was zero bytes for the 3h, 3i and 3j
nodes; pytest collects nothing from an empty file and exits 0, so the
gate reported success over half its declared coverage three times.

A count alone will not do it (2p: a count without an enumeration is not
a declaration). "At least N" is satisfied by N tests from the wrong
targets, and would have been satisfied here — the surviving target
alone clears any plausible floor.

This lives in Python rather than in the shell because the shell the
gate runs under does not reliably have grep/sed/sort on PATH, and an
extent check that silently fails to count is the very defect it exists
to close.

Clause 4 collects over what the SUITE ACTUALLY RUNS, not over the
declared list. Collecting only the declared paths would make clause 4
unable to fire by construction — the comparison would be a set against
itself. Found by trying to demonstrate the refusal (A319) and failing
to make it fire.

Usage: extent_gate.py --suite <suite command> -- <path>:<min> ...
Exit 0 = extent met. Non-zero = REFUSE (no commit). Not a warning.
"""
import collections
import os
import subprocess
import sys


def collect_by_file(paths):
    """Per-file collected counts from pytest's own collection report."""
    proc = subprocess.run(
        [os.path.join("venv", "bin", "python"), "-m", "pytest", *paths,
         "--collect-only", "-q", "-p", "no:randomly"],
        capture_output=True, text=True)
    counts = collections.Counter()
    for line in proc.stdout.splitlines():
        if "::" in line:
            counts[line.split("::", 1)[0].strip()] += 1
    return counts, proc


def suite_targets(suite_cmd):
    """The .py paths the suite command will actually run."""
    return [t for t in suite_cmd.split() if t.endswith(".py")]


def assert_extent(declarations, suite_cmd):
    """The four clauses of A315, in order. Returns a list of refusals."""
    declared = {d.rsplit(":", 1)[0]: int(d.rsplit(":", 1)[1])
                for d in declarations}
    refusals = []

    # clause 1 — every declared path exists and is non-empty
    for path in declared:
        if not os.path.exists(path):
            refusals.append(f"MISSING_TARGET: {path} does not exist")
        elif os.path.getsize(path) == 0:
            refusals.append(
                f"EMPTY_TARGET: {path} is zero bytes — this is the 3h defect")

    actual = suite_targets(suite_cmd)
    counts, proc = collect_by_file([p for p in actual if os.path.exists(p)])
    if not counts and proc.returncode not in (0, 5):
        refusals.append(
            "COLLECTION_UNREADABLE: pytest produced no collection report "
            f"(rc={proc.returncode}) — an unreadable report is a refusal, "
            "never an empty pass")

    for path, minimum in declared.items():
        collected = counts.get(path, 0)
        # clause 2 — every declared path appears in the collection report
        if collected == 0:
            refusals.append(f"ABSENT_FROM_COLLECTION: {path} collected 0")
        # clause 3 — per-target count meets its declared floor
        elif collected < minimum:
            refusals.append(
                f"BELOW_DECLARED_FLOOR: {path} collected {collected}, "
                f"declared minimum {minimum}")

    # clause 4 — both directions. Extent can be lost by disappearance and
    # gained by accident; a gate that checks one direction cannot tell you
    # its declared list is still the list being run.
    undeclared = sorted((set(counts) | set(actual)) - set(declared))
    if undeclared:
        refusals.append(
            f"UNDECLARED_TARGET: {', '.join(undeclared)} collected but not "
            "in EXPECTED_TARGETS")

    return refusals


def main(argv):
    suite_cmd = ""
    if argv and argv[0] == "--suite":
        suite_cmd = argv[1]
        argv = argv[3:] if len(argv) > 2 and argv[2] == "--" else argv[2:]
    if not argv:
        print("EXTENT_GATE_REFUSED: no targets declared — an empty "
              "declaration is a refusal, not a vacuous pass", file=sys.stderr)
        return 2
    refusals = assert_extent(argv, suite_cmd)
    if refusals:
        print("GUARDED_COMMIT_REFUSED: declared extent not met (A315/3l)",
              file=sys.stderr)
        for line in refusals:
            print(f"  {line}", file=sys.stderr)
        print("  REFUSE is non-zero exit and no commit. Not a warning.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
