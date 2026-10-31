"""A298 — the manifest gate: no bulk write to search results.

Four instances of report-before-classify (1,441 / 680 / 67 / 94) and
the fourth WROTE to 43 records that had made no claim. A reminder to be
careful is not a control; this is.

  1. the search produces candidates
  2. candidates are written to a manifest — path, match, classification
  3. the manifest is committed as its own artifact
  4. the write step reads the MANIFEST, never the search output

The manifest existing as a separate committed artifact is the
load-bearing part: it makes classification something that has to be
done rather than something skipped when the count looks plausible.
"""
import json


class UnclassifiedCandidate(RuntimeError):
    """A candidate reached the write step without a classification."""


def build_manifest(candidates, classifier, path):
    """candidates: [{path, match}]. classifier returns GENUINE or a
    reason string. Every candidate gets a row; none is dropped."""
    rows = [dict(c, classification=classifier(c)) for c in candidates]
    with open(path, "w") as f:
        json.dump({"record_type": "sweep_manifest/1.0",
                   "candidates": len(rows),
                   "genuine": sum(1 for r in rows
                                  if r["classification"] == "GENUINE"),
                   "rows": rows}, f, indent=1)
    return rows


def writable(manifest_path):
    """The ONLY sanctioned input to a bulk write. Reads the committed
    manifest and yields genuine entries; raises on any unclassified."""
    with open(manifest_path) as f:
        rows = json.load(f)["rows"]
    missing = [r for r in rows if not r.get("classification")]
    if missing:
        raise UnclassifiedCandidate(
            f"{len(missing)} candidate(s) carry no classification — the "
            "manifest is not a permission to write")
    return [r for r in rows if r["classification"] == "GENUINE"]
