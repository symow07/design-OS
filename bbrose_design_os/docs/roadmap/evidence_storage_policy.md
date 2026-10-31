# Repository evidence storage policy

**Status: PROPOSED — no migration performed, no history rewritten.**
Audit: `docs/roadmap/evidence_storage_audit.json` (2026-08-07).

## What the audit found

Tracked at HEAD:

| Kind | Files | Size |
|---|---|---|
| `.png` evidence | 676 | ~657 MB |
| `.pdf` boards | 76 | ~80 MB |
| `.ai` sources | 58 | ~17 MB |

**Git LFS is not installed on this machine**, `.gitattributes` declares no
LFS patterns, and no CI configuration in this working copy declares LFS
support. So LFS is currently *unavailable*, not merely unused.

## The blocker beyond availability

Even with LFS installed, two shipped validators read image bytes directly
from the working tree:

- `a3p_evidence_render.validate_package` — reads PNG metadata and pixels
  to check the eight A3P failure conditions;
- `palette_m4b_b_gate.subject_separation` — measures subject coverage and
  contrast for the legibility gate.

Against an unfetched LFS pointer file both would fail, and the A3P gate
would report evidence as absent when it is merely not downloaded. Any
migration therefore has to be paired with a smudge/fetch guarantee or with
a validator change that fails closed on a pointer file rather than
misreading it. That is a real piece of work, not a `git lfs track`.

## Preferred policy, when LFS is available and compatible

**Normal Git** — source, JSON, manifests, Markdown, small technical
diagrams, hashes, metadata.

**Git LFS** — large PNG evidence, large PDF boards, large rendered binary
artifacts.

## Until then

The roadmap is not blocked on this. Evidence stays in normal Git, and the
cost is recorded here rather than discovered at a clone.

Interim measures already in force:

- render `_obj` export directories are git-ignored, so mesh exports never
  enter history;
- evidence is regenerated in place rather than versioned per run, so a
  re-render replaces bytes instead of adding a new copy.

An alternative retention policy, if LFS stays unavailable: keep the
current milestone's evidence in the repository, and move superseded
milestone evidence to an external artifact store referenced by hash from
the manifests — the manifests already carry pixel hashes, so a moved
artifact stays verifiable.

**Do not migrate historical evidence or rewrite commits without separate
owner approval.**


## M5 evidence retention (2026-08-07)

The M5 characterization campaign produced ~640 MB of intermediate
renders. Retained: the base measurement pair per sub-rig, the mirror
reference, the transmission set, the product crops, the P1A
generalization set, all boards and every measurement JSON — the
numerical authority. Pruned: per-control and per-perturbation
intermediate PNGs/EXRs, whose measurements are recorded in
`reflective_metric_report.json`, `material_negative_controls.json`
and `material_rig_robustness_report.json`, and which are
deterministically reproducible from the pinned rig contracts.
Post-prune size: ~150 MB.
