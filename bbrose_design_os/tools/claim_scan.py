"""A365 — instrument prose may not assert impossibility or universality.

A general claim inspector is not buildable. A PROHIBITION is, and it is
mechanically checkable: instrument docstrings and comments state the
conditions under which the instrument refuses, and do not assert
absolute negatives about future behaviour. The planted false claim of
A338 is removed by the same rule that forbids its successors; its plant
stays recorded in the node record rather than in the instrument.

The scan joins prose lines before matching: a wrapped phrase spans a
line break, so a line-based scan reads a window narrower than its
subject and misses exactly the claims it exists to find. Found by
running it — the planted claim itself split across two lines.

Scoped to INSTRUMENTS. A scan that reaches into law records or boundary
reports is A367's class again — the prohibition is about what an
instrument claims of itself.
"""
import re
import sys

FORBIDDEN = ("can never", "cannot be", "impossible", "always",
             "guaranteed", "no way to", "in all cases")
INSTRUMENTS = ("tools/tier2_gate.py", "tools/extent_gate.py",
               "tools/guarded_commit.sh", "tools/sweep_manifest.py",
               "tools/opt_out_log.py", "tools/flake_gate.py",
               "tools/claim_scan.py", "tools/fixture_diff.py",
               "tools/reserved_copy.py")
PROSE = re.compile(r"^\s*(#|\"\"\"|')|^[^#]*#")


def scan(paths=INSTRUMENTS):
    hits = []
    for p in paths:
        try:
            lines = open(p).read().splitlines()
        except OSError:
            continue
        in_doc = False
        prose = []          # (line_no, text) for prose lines only
        for n, line in enumerate(lines, 1):
            opened = in_doc
            if line.count('"""') % 2:
                in_doc = not in_doc
            if opened or in_doc or line.lstrip().startswith(("#", '"""')):
                prose.append((n, line.strip().lstrip("#: ").strip()))
        # join, keeping a map from joined offset back to line number
        joined, index = "", []
        for n, text in prose:
            joined += text + " "
            index.extend([n] * (len(text) + 1))
        low = joined.lower()
        for phrase in FORBIDDEN:
            for m in re.finditer(re.escape(phrase), low):
                hits.append((p, index[m.start()], phrase,
                             joined[max(0, m.start() - 30):m.start() + 50]))
    return hits


def main():
    hits = scan()
    for p, n, phrase, text in hits:
        print(f"CLAIM_PROHIBITED {p}:{n} [{phrase}] {text[:70]}", file=sys.stderr)
    if hits:
        print(f"REFUSED: {len(hits)} impossibility/universality claim(s) in "
              "instrument prose. State the conditions under which the "
              "instrument refuses instead.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
