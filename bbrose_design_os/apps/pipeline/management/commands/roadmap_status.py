"""roadmap_status — read-only roadmap tracker validation and report.

The tracker (docs/roadmap/progress_tracker.json) is the ONE machine-readable
progress authority (roadmap rebase 2026-08-03). This command:

* validates the tracker against the consistency rules the rebase brief
  requires (§14) — duplicate ids, illegal statuses, weight sums, percentage
  bounds, rejection/acceptance/production coherence, evidence requirements,
  milestone pointers, staleness of stored rollups;
* recomputes every program-level percentage from LEAF data (stored rollups
  are a cache, never an authority — the validator fails when they drift);
* prints the current commit, active/next milestones, blockers, pending owner
  decisions and per-domain percentages.

It reads the repository and the tracker file. It writes nothing, dispatches
nothing and calls no provider.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

TRACKER_PATH = (Path(__file__).resolve().parents[4]
                / "docs" / "roadmap" / "progress_tracker.json")

VALID_STATUSES = {
    "NOT_STARTED", "AUDITED", "DESIGNED", "IN_PROGRESS", "IMPLEMENTED",
    "VALIDATED", "OWNER_ACCEPTED", "PRODUCTION_AUTHORIZED", "BLOCKED",
    "DEFERRED", "PRESERVED", "REJECTED", "SUPERSEDED",
}
# statuses that must carry evidence (commits or tests)
EVIDENCE_REQUIRED = {"VALIDATED", "OWNER_ACCEPTED", "PRODUCTION_AUTHORIZED"}
# statuses that may never claim owner acceptance
NEVER_OWNER_ACCEPTED = {"REJECTED", "DEFERRED", "PRESERVED", "NOT_STARTED",
                        "BLOCKED"}
PERCENT_FIELDS = ("implementation_percent", "validation_percent",
                  "visual_quality_percent", "owner_acceptance_percent",
                  "production_readiness_percent")
WEIGHT_TOLERANCE = 1e-6
ROLLUP_TOLERANCE = 0.51          # stored caches are rounded to 1 decimal

#: §AE0(a) — `owner_acceptance` is untouchable, and no status containing
#: OWNER_ACCEPTED is written by the executor for any node, EVER. Until
#: 2026-08-24 nothing here could tell an owner's acceptance from an executor's.
#: The only evidence EVIDENCE_REQUIRED would take for OWNER_ACCEPTED was
#: `evidence_commits` or `evidence_tests` — both written by the executor — so
#: the one rule allowed to hold absolutely was the one rule with no instrument.
#: Measured before this field existed: of the 56 nodes an executor could raise
#: 0->100, ZERO were caught by any of the 39 tracker tests; of the 95 nodes not
#: already accepted, 32 could be flipped to OWNER_ACCEPTED in silence, one of
#: them a REJECTED pilot record.
#:
#: WHAT THIS BUYS IS FALSIFIABILITY, NOT UNFORGEABILITY, and the difference is
#: the whole honest description of it. An executor can still write a locator.
#: What changes is that the claim must now name a specific commit and quote a
#: sentence that is really in it, so a false acceptance has to be TOLD, in a
#: dated place, where it can be checked — instead of being told by silence.
ACCEPTANCE_EVIDENCE_FIELD = "owner_acceptance_evidence"
ACCEPTANCE_EVIDENCE_KINDS = {
    "OWNER_RULING_COMMIT",        # locator = commit sha, quote = owner's words
    "OWNER_MANIFEST_SECTION",     # locator = OWNER_INPUT_MANIFEST.md heading
    "UNRECORDED_PREDATES_FIELD",  # grandfathered only — see below
}

#: Nodes carrying owner acceptance from BEFORE the field existed, for which no
#: owner artifact is on record anywhere in the repository. Established by
#: measurement over all 37 commits that had ever touched the tracker: exactly
#: three ever wrote an acceptance with an owner's words attached, and the other
#: nine nodes were BORN at 100 in 7bc9293, the same commit that invented the
#: dimension.
#:
#: THIS IS NOT A CLAIM THAT THESE WERE NEVER ACCEPTED. It is the narrower and
#: checkable claim that the repository cannot show that they were. The list may
#: only SHRINK — an entry leaves when the owner supplies the missing record —
#: and nothing may ever be added to it, because any acceptance made after
#: 2026-08-24 has the field or is invalid. A grandfather clause that can grow
#: is not a grandfather clause, it is a loophole with a date on it.
ACCEPTANCE_EVIDENCE_GRANDFATHERED = frozenset({
    "core_platform.front_half",
    "core_platform.target_selector",
    "pc.reference_system",
    "pc.reconstruction_infra",
    "pkg.archetypes",
    "ire.gate_a_roundtrip",
    "review_board.references",
    "quality.single_authority",
})

#: The invariant that stops the 2026-08-07 reconciliation from
#: recurring: a milestone whose closure record exists on disk may not
#: be reported NOT_STARTED. The tracker was contradicted by five
#: commits' worth of closure records while remaining the sole source
#: of the project's progress percentage — a checkable fact, not a
#: discipline problem. Paths are repo-relative; a directory counts
#: when it exists and is non-empty.
CLOSURE_RECORDS = {
    "palettes.palt_m1_foundation": "docs/roadmap/palt_m1",
    "palettes.palt_m2_geometry_layout": "docs/roadmap/palt_m2",
    "palettes.palt_m3_mechanism": "docs/roadmap/palt_m3",
    "palettes.palt_m4_powder_materials": "docs/roadmap/palt_m4b_b",
    "palettes.palt_m5_pilot_p1":
        "docs/roadmap/palt_m5/m5_validation_report.json",
    "palettes.palt_m6_powder_material_engine": "docs/roadmap/palt_m6",
}


def _closure_record_exists(repo_root, rel_path):
    p = repo_root / rel_path
    return p.is_file() or (p.is_dir() and any(p.iterdir()))


def _acceptance_evidence_findings(nid, ev):
    """Structural checks on one node's acceptance evidence. Deliberately does
    NOT resolve the locator — see ``verify_acceptance_evidence`` — so that
    ``validate_tracker`` stays pure and runs anywhere."""
    if not isinstance(ev, dict):
        return [f"{nid}: {ACCEPTANCE_EVIDENCE_FIELD} must be an object"]
    kind = ev.get("kind")
    if kind not in ACCEPTANCE_EVIDENCE_KINDS:
        return [f"{nid}: unknown acceptance evidence kind {kind!r}"]
    if kind == "UNRECORDED_PREDATES_FIELD":
        if nid not in ACCEPTANCE_EVIDENCE_GRANDFATHERED:
            return [f"{nid}: UNRECORDED_PREDATES_FIELD is not available to a "
                    "node outside the frozen grandfather set"]
        return []
    return [f"{nid}: acceptance evidence missing {key}"
            for key in ("locator", "quote", "dated")
            if not str(ev.get(key) or "").strip()]


def acceptance_evidence_claims(tracker):
    """Every (node_id, evidence) pair that names a resolvable owner artifact.
    The grandfathered entries are excluded because they name nothing."""
    out = []
    for n in tracker.get("nodes", []):
        ev = n.get(ACCEPTANCE_EVIDENCE_FIELD)
        if isinstance(ev, dict) and ev.get("kind") == "OWNER_RULING_COMMIT":
            out.append((n["id"], ev))
    return out


def verify_acceptance_evidence(tracker, repo_root=None):
    """Resolve every OWNER_RULING_COMMIT locator against real git history and
    check the quoted words are REALLY in that commit's message.

    Kept out of ``validate_tracker`` because it shells out. What it can prove:
    the commit exists and contains the sentence. What it CANNOT prove: that the
    sentence means the owner accepted THIS node. An executor pointing a real
    owner ruling at the wrong node still passes here — that residue is stated
    rather than papered over, and it is a far narrower hole than the silence
    this replaces."""
    findings = []
    cwd = str(repo_root) if repo_root else str(TRACKER_PATH.parents[2])
    for nid, ev in acceptance_evidence_claims(tracker):
        sha, quote = str(ev.get("locator") or ""), str(ev.get("quote") or "")
        try:
            body = subprocess.check_output(
                ["git", "log", "-1", "--format=%B", sha],
                cwd=cwd, stderr=subprocess.DEVNULL).decode()
        except (subprocess.CalledProcessError, OSError):
            findings.append(f"{nid}: acceptance evidence names commit {sha!r}, "
                            "which does not resolve")
            continue
        if quote.strip() not in " ".join(body.split()):
            findings.append(
                f"{nid}: quoted owner words are not in commit {sha}")
    return findings


def load_tracker(path=TRACKER_PATH):
    return json.loads(Path(path).read_text())


def _children(nodes, parent_id):
    return [n for n in nodes if n.get("parent_id") == parent_id]


def rollup(nodes, node_id, field):
    """Weighted percentage for ``field`` at ``node_id``, computed from LEAF
    values. ``None`` marks a dimension as not applicable — such children are
    excluded and sibling weights renormalized; an all-None subtree is None."""
    by_id = {n["id"]: n for n in nodes}
    node = by_id[node_id]
    kids = _children(nodes, node_id)
    if not kids:
        return node.get(field)
    total_weight = 0.0
    acc = 0.0
    for child in kids:
        value = rollup(nodes, child["id"], field)
        if value is None:
            continue
        total_weight += child["weight"]
        acc += child["weight"] * value
    if total_weight == 0:
        return None
    return acc / total_weight


def program_percent(tracker, node_id, field):
    """Rollup with owner-review semantics (V3 amendment §3): while an
    end-to-end acceptance gate node is REJECTED, the gated parent's
    owner-acceptance readiness is 0 — accepted SUBSYSTEM reviews are real
    but they are component_review_coverage, never end-to-end acceptance."""
    nodes = tracker["nodes"]
    value = rollup(nodes, node_id, field)
    if field != "owner_acceptance_percent":
        return value
    gates = (tracker.get("meta") or {}).get("acceptance_gates") or {}
    gate_id = gates.get(node_id)
    if gate_id:
        gate = next((n for n in nodes if n["id"] == gate_id), None)
        if gate is not None and gate["status"] == "REJECTED":
            return 0.0
    return value


def component_review_coverage(tracker, node_id):
    """The UNgated owner-review rollup — how much of the subsystem surface
    has been owner-reviewed, explicitly not end-to-end acceptance."""
    return rollup(tracker["nodes"], node_id, "owner_acceptance_percent")


# statuses that count as descendant activity for an IN_PROGRESS parent
_ACTIVE_STATUSES = {"IN_PROGRESS", "IMPLEMENTED", "VALIDATED",
                    "OWNER_ACCEPTED", "PRODUCTION_AUTHORIZED", "REJECTED",
                    "PRESERVED"}


def _descendants(nodes, node_id):
    out = []
    for child in _children(nodes, node_id):
        out.append(child)
        out.extend(_descendants(nodes, child["id"]))
    return out


def validate_tracker(tracker, *, git_head=None):
    """All §14 consistency findings as a list of strings (empty = valid)."""
    findings = []
    nodes = tracker.get("nodes", [])
    meta = tracker.get("meta", {})
    by_id = {}
    for n in nodes:
        if n["id"] in by_id:
            findings.append(f"duplicate roadmap id: {n['id']}")
        by_id[n["id"]] = n

    roots = [n for n in nodes if n.get("parent_id") is None]
    if len(roots) != 1:
        findings.append(f"exactly one root required, found {len(roots)}")

    for n in nodes:
        nid = n["id"]
        if n.get("status") not in VALID_STATUSES:
            findings.append(f"{nid}: invalid status {n.get('status')!r}")
        if n.get("parent_id") is not None and n["parent_id"] not in by_id:
            findings.append(f"{nid}: unknown parent {n['parent_id']!r}")
        for field in PERCENT_FIELDS:
            value = n.get(field)
            if value is not None and not (0 <= value <= 100):
                findings.append(f"{nid}: {field} out of range ({value})")
        # rejection / acceptance / production coherence
        status = n.get("status")
        if status in NEVER_OWNER_ACCEPTED and \
                (n.get("owner_acceptance_percent") or 0) > 0:
            findings.append(
                f"{nid}: status {status} may not carry owner acceptance")
        if status == "REJECTED" and \
                (n.get("visual_quality_percent") or 0) >= 100:
            findings.append(f"{nid}: REJECTED with full visual quality")
        if status == "PRODUCTION_AUTHORIZED" and \
                (n.get("owner_acceptance_percent") or 0) < 100:
            findings.append(
                f"{nid}: production authorized before owner acceptance")
        if status in EVIDENCE_REQUIRED and not (
                n.get("evidence_commits") or n.get("evidence_tests")):
            findings.append(f"{nid}: {status} requires evidence")
        # §AE0(a): an owner acceptance must name the owner's act. Both halves
        # of the rule are covered — the status clause (which binds at node
        # CREATION, where no delta exists) and the dimension clause.
        claims = (status == "OWNER_ACCEPTED"
                  or (n.get("owner_acceptance_percent") or 0) > 0)
        ev = n.get(ACCEPTANCE_EVIDENCE_FIELD)
        if claims and ev is None:
            findings.append(
                f"{nid}: owner acceptance carries no "
                f"{ACCEPTANCE_EVIDENCE_FIELD}")
        elif ev is not None and not claims:
            findings.append(
                f"{nid}: {ACCEPTANCE_EVIDENCE_FIELD} on a node that claims no "
                "owner acceptance")
        elif ev is not None:
            findings.extend(_acceptance_evidence_findings(nid, ev))
        # a leaf marked complete must actually be complete
        if not _children(nodes, nid) and status in (
                "VALIDATED", "OWNER_ACCEPTED", "PRODUCTION_AUTHORIZED"):
            if (n.get("implementation_percent") or 0) < 100:
                findings.append(
                    f"{nid}: {status} with implementation < 100")

    # weights sum within each parent
    for parent in nodes:
        kids = _children(nodes, parent["id"])
        if kids:
            total = sum(k.get("weight", 0) for k in kids)
            if abs(total - 1.0) > WEIGHT_TOLERANCE:
                findings.append(
                    f"{parent['id']}: child weights sum to {total:.6f}")

    # parent completion cannot exceed its children (computed, so this guards
    # hand-written parent values)
    for parent in nodes:
        if _children(nodes, parent["id"]):
            for field in ("implementation_percent",):
                stored = parent.get(field)
                if stored is not None:
                    computed = rollup(nodes, parent["id"], field)
                    if computed is not None and \
                            abs(stored - computed) > ROLLUP_TOLERANCE:
                        findings.append(
                            f"{parent['id']}: stored {field} {stored} "
                            f"drifted from computed {computed:.1f}")

    # milestone pointers
    active = meta.get("active_milestone")
    if active:
        if active not in by_id:
            findings.append(f"active milestone {active!r} is not a node")
        elif by_id[active]["status"] in ("VALIDATED", "OWNER_ACCEPTED",
                                         "PRODUCTION_AUTHORIZED"):
            findings.append(f"active milestone {active} is already complete")
    nxt = meta.get("next_milestones") or []
    for m in nxt:
        if m not in by_id:
            findings.append(f"next milestone {m!r} is not a node")
        elif by_id[m]["status"] in ("VALIDATED", "OWNER_ACCEPTED",
                                    "PRODUCTION_AUTHORIZED"):
            findings.append(f"next milestone {m} points to a completed item")
    if meta.get("primary_active_milestones") and \
            len(meta["primary_active_milestones"]) > 1:
        findings.append("more than one primary active milestone")

    # global coherence with the recorded program state
    program = meta.get("program_state", {})
    if program.get("PRODUCT_CONTAINER_END_TO_END_ACCEPTANCE") == "REJECTED":
        pc_acc = by_id.get("pc.owner_acceptance")
        if pc_acc and ((pc_acc.get("owner_acceptance_percent") or 0) > 0
                       or pc_acc.get("status") != "REJECTED"):
            findings.append(
                "pc.owner_acceptance must be REJECTED at 0% while the "
                "program records an active rejection")

    # V3 amendment §8: a parent may not be IN_PROGRESS when nothing under
    # it has ever been active or implemented
    for parent in nodes:
        kids = _descendants(nodes, parent["id"])
        if kids and parent.get("status") == "IN_PROGRESS" and not any(
                k["status"] in _ACTIVE_STATUSES for k in kids):
            findings.append(
                f"{parent['id']}: IN_PROGRESS with no active or "
                "implemented descendant")

    # V3 amendment §3: gated owner-acceptance rollups
    for gated_id, gate_id in ((tracker.get("meta") or {})
                              .get("acceptance_gates") or {}).items():
        if gated_id not in by_id or gate_id not in by_id:
            findings.append(
                f"acceptance gate {gated_id}->{gate_id} names unknown node")
            continue
        if by_id[gate_id]["status"] == "REJECTED":
            cached = (tracker.get("computed_views") or {}).get(
                gated_id, {}).get("owner_acceptance_percent")
            if cached not in (None, 0, 0.0):
                findings.append(
                    f"{gated_id}: owner acceptance must be 0 while gate "
                    f"{gate_id} is REJECTED (cached {cached})")

    # V3 amendment §10: every critical-path item is a real node and the
    # declared order respects dependencies
    path = (tracker.get("meta") or {}).get("critical_path_nodes") or []
    for i, nid in enumerate(path):
        if nid not in by_id:
            findings.append(f"critical path names unknown node {nid!r}")
            continue
        earlier = set(path[:i])
        for dep in by_id[nid].get("dependencies") or []:
            if dep in path and dep not in earlier:
                findings.append(
                    f"critical path order invalid: {nid} depends on {dep} "
                    "which appears later")

    # stored program views must match recomputation (owner-acceptance is
    # compared through the gate, §3)
    for view_id, stored in (tracker.get("computed_views") or {}).items():
        if view_id not in by_id:
            findings.append(f"computed view {view_id!r} is not a node")
            continue
        for field, value in stored.items():
            if field == "component_review_coverage_percent":
                computed = component_review_coverage(tracker, view_id)
            elif field in PERCENT_FIELDS:
                computed = program_percent(tracker, view_id, field)
            else:
                continue
            if value is None and computed is None:
                continue
            if value is None or computed is None or \
                    abs(value - computed) > ROLLUP_TOLERANCE:
                findings.append(
                    f"{view_id}: cached {field}={value} drifted from "
                    f"computed "
                    f"{'None' if computed is None else round(computed, 1)}")

    # commit consistency is informational unless the tracker claims a commit
    # that never existed
    if git_head and meta.get("latest_validated_commit") and \
            len(meta["latest_validated_commit"]) < 7:
        findings.append("latest_validated_commit is not a commit hash")

    # a milestone with a closure record on disk may not read NOT_STARTED
    repo_root = TRACKER_PATH.parents[2]
    for node_id, rel_path in CLOSURE_RECORDS.items():
        node = by_id.get(node_id)
        if node is None:
            findings.append(
                f"closure-record invariant names unknown node {node_id}")
            continue
        if node.get("status") == "NOT_STARTED" and \
                _closure_record_exists(repo_root, rel_path):
            findings.append(
                f"{node_id}: NOT_STARTED but its closure record "
                f"{rel_path} exists on disk")
    return findings


def _git_head():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parents[4],
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return None


class Command(BaseCommand):
    help = ("Validate the roadmap progress tracker and print the program "
            "status. Read-only.")

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true",
                            help="emit the computed views as JSON")

    def handle(self, *args, **options):
        tracker = load_tracker()
        head = _git_head()
        findings = validate_tracker(tracker, git_head=head)
        if findings:
            for f in findings:
                self.stderr.write(f"INVALID: {f}")
            raise CommandError(
                f"tracker failed validation ({len(findings)} finding(s))")

        nodes = tracker["nodes"]
        meta = tracker["meta"]
        recorded = meta.get("latest_validated_commit")
        self.stdout.write(f"current commit:            {head or 'unknown'}")
        self.stdout.write(f"latest validated commit:   {recorded}"
                          + ("" if head in (None, recorded)
                             else "  (HEAD is ahead — docs/tracker commits "
                                  "are expected to lead)"))
        self.stdout.write(f"tracker schema:            "
                          f"{tracker.get('schema')}")
        self.stdout.write(f"calculated at:             "
                          f"{meta.get('calculated_at')}")
        active = meta.get("active_milestone")
        self.stdout.write(f"active milestone:          {active}")
        self.stdout.write("next milestones:           "
                          + ", ".join(meta.get("next_milestones") or []))

        gates = meta.get("acceptance_gates") or {}
        if options["json"]:
            out = {}
            for n in nodes:
                if n.get("parent_id") is None or n.get("program_view"):
                    entry = {
                        f: (None if program_percent(tracker, n["id"], f)
                            is None
                            else round(program_percent(tracker, n["id"], f),
                                       1))
                        for f in PERCENT_FIELDS}
                    if n["id"] in gates:
                        cov = component_review_coverage(tracker, n["id"])
                        entry["component_review_coverage_percent"] = (
                            None if cov is None else round(cov, 1))
                    out[n["id"]] = entry
            self.stdout.write(json.dumps(out, indent=1))
            return

        self.stdout.write("\nprogram percentages "
                          "(impl / validated / visual / owner / production):")
        for n in nodes:
            if n.get("parent_id") is None or n.get("program_view"):
                vals = []
                for f in PERCENT_FIELDS:
                    v = program_percent(tracker, n["id"], f)
                    vals.append("  n/a" if v is None else f"{v:5.1f}")
                note = ""
                if n["id"] in gates:
                    cov = component_review_coverage(tracker, n["id"])
                    note = (f"   [component review coverage "
                            f"{cov:.1f}% — NOT end-to-end acceptance]"
                            if cov is not None else "")
                self.stdout.write(f"  {n['id']:<28} {' '.join(vals)}{note}")

        blockers = [(n["id"], b) for n in nodes
                    for b in (n.get("blockers") or [])]
        if blockers:
            self.stdout.write("\nblockers:")
            for nid, b in blockers:
                self.stdout.write(f"  {nid}: {b}")
        decisions = [n["id"] for n in nodes if n.get("owner_decision_required")]
        if decisions:
            self.stdout.write("\nowner decisions required:")
            for nid in decisions:
                self.stdout.write(f"  {nid}")
        self.stdout.write(self.style.SUCCESS("\ntracker valid"))
