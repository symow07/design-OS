"""A518/3z — RECORD_ONLY: a commit whose diff touches only record paths.

3z licenses landing the record OF a refusal while the refusal stands.
It is not a bypass: such a commit still runs the full gate, and it
carries the refusal verbatim in its message. This control exists so the
licence cannot widen — the first commit taking this path with a single
code file in it must fail loudly.
"""
import subprocess
import sys

RECORD_PREFIXES = ("bbrose_design_os/docs/", "docs/")


class NotRecordOnly(RuntimeError):
    """A code path reached a licence written for records."""


def offending(paths):
    return sorted(p for p in paths
                  if not any(p.startswith(x) for x in RECORD_PREFIXES))


def staged_paths():
    out = subprocess.run(["git", "diff", "--cached", "--name-only"],
                         capture_output=True, text=True).stdout
    return [p for p in out.split() if p]


def main():
    bad = offending(staged_paths())
    if bad:
        print("RECORD_ONLY_REFUSED: these are not record paths — 3z does "
              "not license them:", file=sys.stderr)
        for p in bad:
            print(f"  {p}", file=sys.stderr)
        return 1
    print("RECORD_ONLY=OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
