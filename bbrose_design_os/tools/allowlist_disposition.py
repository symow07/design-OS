"""3c — the ONLY writer of the allowlist baseline.

There is no refresh operation. This tool refuses to write unless every
divergent key carries a disposition from the mover, and each
disposition is recorded with its reason in the baseline's own log:

  cosmetic  the expression's text moved, the shape and the claim did
            not — the old key is superseded in place per 2k
  changed   the guarded expression means something different — a new
            occurrence, and it goes through review as one
  removed   the occurrence is gone, the count drops — progress, made
            visible as progress rather than as noise

Usage:
  allowlist_disposition.py --show
  allowlist_disposition.py --disposition 'KEY=cosmetic:reason sentence'
                           [--disposition ...] --commit
"""
import argparse
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone

_spec = importlib.util.spec_from_file_location(
    "allowlist_census",
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "allowlist_census.py"))
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)

VALID = ("cosmetic", "changed", "removed")


class DispositionRequired(SystemExit):
    """A divergence without a stated reason. Never written."""


def load_baseline():
    with open(C.BASELINE) as f:
        return json.load(f)


def divergences(base):
    found = C.current()
    out = {}
    for section in ("fallbacks", "a32"):
        d = C.diff(found[section], base[section])
        if d:
            out[section] = d
    return found, out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--disposition", action="append", default=[])
    ap.add_argument("--commit", action="store_true")
    args = ap.parse_args(argv)

    base = load_baseline()
    found, div = divergences(base)

    if args.show or not args.commit:
        if not div:
            print("NO DIVERGENCE — baseline agrees with the code")
            return 0
        for section, keys in div.items():
            for k, v in sorted(keys.items()):
                print(f"{section}\t{k}\tfound={v['found']} "
                      f"allowed={v['allowed']}")
        if not args.commit:
            print("\nNo write performed. A baseline is not refreshed "
                  "(3c): supply --disposition KEY=<cosmetic|changed|"
                  "removed>:<reason> for EVERY key above, with "
                  "--commit.")
        return 0

    if not div:
        # 3c: with nothing divergent there is nothing to bring into
        # agreement. Writing here would append an empty log entry and
        # run the write path for no reason — a refresh in all but name.
        print("NOTHING TO DISPOSITION — baseline already agrees with "
              "the code; no write performed")
        return 0

    stated = {}
    for spec in args.disposition:
        key, _, rest = spec.partition("=")
        kind, _, reason = rest.partition(":")
        if kind not in VALID:
            raise DispositionRequired(
                f"unknown disposition {kind!r} for {key!r}; "
                f"expected one of {VALID}")
        if not reason.strip():
            raise DispositionRequired(
                f"disposition for {key!r} carries no reason — 3c "
                "requires the reason, and it is the whole cost")
        stated[key] = {"disposition": kind, "reason": reason.strip()}

    undispositioned = [k for keys in div.values() for k in keys
                       if k not in stated]
    if undispositioned:
        raise DispositionRequired(
            "REFUSED — a baseline is not refreshed (3c). "
            f"{len(undispositioned)} divergent key(s) carry no "
            f"disposition: {undispositioned[:5]}")
    extraneous = [k for k in stated if not any(
        k in keys for keys in div.values())]
    if extraneous:
        raise DispositionRequired(
            f"REFUSED — disposition supplied for non-divergent key(s): "
            f"{extraneous}")

    for section in ("fallbacks", "a32"):
        base[section] = found[section]
    base.setdefault("disposition_log", []).append({
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "law": "3c", "dispositions": stated})
    with open(C.BASELINE, "w") as f:
        json.dump(base, f, indent=1, sort_keys=True)
    print(f"baseline superseded with {len(stated)} stated "
          f"disposition(s); log appended")
    return 0


if __name__ == "__main__":
    sys.exit(main())
