"""RBV-4 — structured visual review harness (``claude_visual_review/1.0``).

Submits a hash-verified RBV-3 review package for structured visual review
and records the findings. Two execution paths, never confusable:

* ``EXECUTION_OFFLINE_FIXTURE`` — deterministic replay of a RECORDED
  fixture. No provider call is made. Every finding is stamped
  ``RECORDED_FIXTURE`` and the fixture's content digest is recorded, so a
  replayed finding can never be read as a provider observation.
* ``EXECUTION_LIVE_PROVIDER`` — a real review call. Owner-budgeted under
  §R1 (10 calls for build sprint 2): the path REFUSES without remaining
  budget in the COMMITTED budget record AND an injected provider. At
  exhaustion it records ``BUDGET_EXHAUSTED`` and the caller continues
  offline — output that came from a fixture is stamped
  ``RECORDED_FIXTURE`` and can never be relabelled live, because the
  source stamp is validated against the path that produced it.

The budget is read from the committed record, never from an inline
argument: a caller-supplied dict would let any caller authorize itself,
which is the same defect class as a self-approval.

AUTHORITY, ENCODED NOT ASSERTED. The contract's rules are binding: the
review NEVER self-approves and the OWNER remains final authority. The
assembled record is scanned for decision keys before it is returned, and a
record that carries one RAISES — there is no branch that emits an approval
and no branch that suppresses the scan.

Provenance follows 3aa: the record carries the identity of every input it
read and of the derivation that produced it, or it is not evidence. A
review that cannot assemble its provenance raises rather than returning
findings with their inputs unrecorded.

READ-ONLY over the review package and the render evidence it references;
no Django ORM; no network except through an explicitly injected provider.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import unicodedata
from collections.abc import Mapping

from apps.pipeline.services.geometry_validation_render import pixel_hash
from apps.pipeline.services.rbv3_review_package import (
    MANIFEST_NAME as RBV3_MANIFEST_NAME,
    MODE_CLIENT_PRESENTATION,
    MODE_GEOMETRY_VALIDATION,
    SCHEMA as RBV3_SCHEMA,
)

SCHEMA = "claude_visual_review/1.0"
RECORD_SCHEMA = "rbv4_claude_review_record/1.0"
FIXTURE_SCHEMA = "claude_visual_review_fixture/1.0"

CONTRACT_FILE = "claude_visual_review_contract.json"
BUDGET_FILE = "rbv4_call_budget.json"
BUDGET_SCHEMA = "rbv4_call_budget/1.0"

#: every ledger entry must carry all of these (§R1a) — a partial entry is
#: an unledgered call wearing a ledger's shape
LEDGER_REQUIRED_FIELDS = ("recorded_at", "package_id", "model",
                          "provider_request_id", "input_tokens",
                          "output_tokens", "cost_usd", "image_transmitted")

#: A row may be marked with this when the call happened but its identity
#: could not be recovered. It is an ESCAPE HATCH, so it is narrow: the flag
#: must carry an explanation, and it is the ONLY way a row may hold
#: unknown values.
LEDGER_DEFECT_FIELD = "DEFECT"

#: the transmitted-image record's own shapes. pixel_hash is 16 hex chars
#: because that is what geometry_validation_render.pixel_hash produces —
#: sha256 over decoded pixels, truncated to 16.
LEDGER_PIXEL_HASH_CHARS = 16
LEDGER_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")

#: a request id must have a BODY, not just the prefix — "req_" alone
#: satisfied the old prefix-only test. 8 is a deliberately loose floor,
#: set well below the 24-character bodies every real row carries, so it
#: refuses placeholders without asserting a format the provider never
#: promised us.
LEDGER_REQUEST_ID_MIN_BODY = 8

#: values that mean "we do not know". Legal ONLY on a DEFECT-flagged row.
LEDGER_UNKNOWN_SENTINELS = frozenset({
    "UNKNOWN", "IDENTITY_LOST_TO_AN_EXECUTOR_DEFECT", "", "N/A", "NONE",
    "TBD", "PENDING",
})

#: what a real Anthropic request id looks like; a row claiming a real call
#: must carry one rather than a placeholder that merely occupies the field
LEDGER_REQUEST_ID_PREFIX = "req_"

#: §U3. The marker for a field that was NEVER PRESENT, as distinct from a
#: field present and blank. These are different §R1a defects — one row
#: never recorded the identity, the other recorded it as empty — and a
#: finding that cannot tell them apart is a false audit statement about
#: whichever one it did not describe.
LEDGER_FIELD_ABSENT = "<FIELD_ABSENT>"

#: §V1(1). What every entry of image_transmitted must actually carry. The
#: field was required to be PRESENT but never inspected, so a row claiming
#: a real call could hold 'UNKNOWN', 0 or False there and be ledgered — the
#: only one of the four residual defects where a bad row was ACCEPTED
#: rather than merely mis-described, and therefore the only one that could
#: let a falsified call into the budget.
LEDGER_IMAGE_REQUIRED_FIELDS = ("role", "path", "pixel_hash")

#: the legacy single-image shape, from before §S2 sent per-view images
#: alongside the sheet. It has no role because there was only one image.
LEDGER_IMAGE_LEGACY_FIELDS = ("path", "pixel_hash")

BUDGET_AVAILABLE = "BUDGET_AVAILABLE"
BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
BUDGET_RECORD_ABSENT = "BUDGET_RECORD_ABSENT"

#: §V2. The 6 unspent §R1 calls carry forward but become spendable ONLY
#: once §V1's fixes have landed AND cleared an independent pass. §V2 says
#: in terms that until then the answer to "may I spend a call" is no, and
#: that this is not a judgement call.
#:
#: IT WAS ENFORCED BY NOBODY. The ruling lived in a markdown file while
#: budget_state reported BUDGET_AVAILABLE with 6 remaining and the live
#: path gated only on absent/exhausted budget, so an injected provider
#: would have spent one. §V2's own reasoning is the argument for closing
#: that: "a budget policed by a check that will accept a falsified row is
#: not a budget; it is a number in a file." A LOCK that no code applies is
#: the same object, and obeying it by restraint is not enforcement.
#: ENFORCEMENT PRECEDES AUTHORIZATION.
#:
#: The value IS the citation, so the lock cannot be lifted by flipping a
#: boolean — whoever lifts it must name the owner ruling that lifted it and
#: the reviewed commit it was granted against. None means locked. Setting
#: it is an OWNER act (§T2b, §U4: the executor may not clear its own code).
V1_INDEPENDENT_CLEARANCE: str | None = None

#: what live execution reports while §V2 stands. Distinct from
#: BUDGET_EXHAUSTED — the calls exist and are authorized; they are not yet
#: spendable — and distinct from NOT_EXECUTED_PENDING_OWNER_BUDGET, which
#: is the pre-§R1 state and must stay unreachable while a budget exists.
LIVE_LOCKED_PENDING_V1_CLEARANCE = "LOCKED_PENDING_V1_CLEARANCE"

EXECUTION_OFFLINE_FIXTURE = "OFFLINE_RECORDED_FIXTURE"
EXECUTION_LIVE_PROVIDER = "LIVE_PROVIDER_CALL"
EXECUTIONS = (EXECUTION_OFFLINE_FIXTURE, EXECUTION_LIVE_PROVIDER)

#: the pre-§R1 state, reachable ONLY when no budget record exists at all.
#: While a budget record is committed this must never be reported — a
#: standing "pending budget" claim against a granted budget is a stale
#: claim, and stale claims are what this programme keeps catching.
NOT_EXECUTED_PENDING_OWNER_BUDGET = "NOT_EXECUTED_PENDING_OWNER_BUDGET"

#: finding provenance stamps — a replayed finding and an observed one are
#: structurally different objects, never the same shape with a flag
SOURCE_RECORDED_FIXTURE = "RECORDED_FIXTURE"
SOURCE_PROVIDER_CALL = "PROVIDER_CALL"
FINDING_SOURCES = (SOURCE_RECORDED_FIXTURE, SOURCE_PROVIDER_CALL)

#: a required category the review did not raise a finding on must be
#: DISPOSED explicitly — silence is never coverage
DISPOSITION_FINDING = "FINDING"
DISPOSITION_NOT_OBSERVED = "NOT_OBSERVED"
DISPOSITION_UNCERTAIN_MISSING_EVIDENCE = "UNCERTAIN_MISSING_EVIDENCE"
DISPOSITIONS = (DISPOSITION_FINDING, DISPOSITION_NOT_OBSERVED,
                DISPOSITION_UNCERTAIN_MISSING_EVIDENCE)

RBV4_PACKAGE_MANIFEST_MISSING = "RBV4_PACKAGE_MANIFEST_MISSING"
RBV4_PACKAGE_SCHEMA_MISMATCH = "RBV4_PACKAGE_SCHEMA_MISMATCH"
RBV4_CONTACT_SHEET_MISSING = "RBV4_CONTACT_SHEET_MISSING"
RBV4_CONTACT_SHEET_HASH_MISMATCH = "RBV4_CONTACT_SHEET_HASH_MISMATCH"
RBV4_VIEW_MISSING = "RBV4_VIEW_MISSING"
RBV4_VIEW_HASH_MISMATCH = "RBV4_VIEW_HASH_MISMATCH"
RBV4_MODE_ABSENT = "RBV4_MODE_ABSENT"
RBV4_EXECUTION_INVALID = "RBV4_EXECUTION_INVALID"
RBV4_BUDGET_NOT_AUTHORIZED = "RBV4_BUDGET_NOT_AUTHORIZED"
RBV4_BUDGET_RECORD_MISSING = "RBV4_BUDGET_RECORD_MISSING"
RBV4_BUDGET_SCHEMA_MISMATCH = "RBV4_BUDGET_SCHEMA_MISMATCH"
RBV4_BUDGET_EXHAUSTED = "RBV4_BUDGET_EXHAUSTED"
RBV4_LEDGER_ENTRY_INCOMPLETE = "RBV4_LEDGER_ENTRY_INCOMPLETE"
RBV4_LEDGER_ENTRY_UNKNOWN_WITHOUT_DEFECT = \
    "RBV4_LEDGER_ENTRY_UNKNOWN_WITHOUT_DEFECT"
RBV4_LEDGER_DEFECT_UNEXPLAINED = "RBV4_LEDGER_DEFECT_UNEXPLAINED"
RBV4_LEDGER_ENTRY_TRANSMISSION_INVALID = \
    "RBV4_LEDGER_ENTRY_TRANSMISSION_INVALID"
RBV4_LEDGER_ENTRY_REPLAYED = "RBV4_LEDGER_ENTRY_REPLAYED"
RBV4_V1_CLEARANCE_ABSENT = "RBV4_V1_CLEARANCE_ABSENT"
RBV4_PROVIDER_ABSENT = "RBV4_PROVIDER_ABSENT"
RBV4_PROVIDER_IDENTITY_INCOMPLETE = "RBV4_PROVIDER_IDENTITY_INCOMPLETE"
RBV4_FIXTURE_MISSING = "RBV4_FIXTURE_MISSING"
RBV4_FIXTURE_SCHEMA_MISMATCH = "RBV4_FIXTURE_SCHEMA_MISMATCH"
RBV4_FIXTURE_ORIGIN_INCOMPLETE = "RBV4_FIXTURE_ORIGIN_INCOMPLETE"
RBV4_CLASSIFICATION_INVALID = "RBV4_CLASSIFICATION_INVALID"
RBV4_CATEGORY_UNKNOWN = "RBV4_CATEGORY_UNKNOWN"
RBV4_CATEGORY_UNADDRESSED = "RBV4_CATEGORY_UNADDRESSED"
RBV4_DISPOSITION_INVALID = "RBV4_DISPOSITION_INVALID"
RBV4_FINDING_SOURCE_MISMATCH = "RBV4_FINDING_SOURCE_MISMATCH"
RBV4_UNCERTAINTY_RESOLVED_BY_ASSUMPTION = \
    "RBV4_UNCERTAINTY_RESOLVED_BY_ASSUMPTION"
RBV4_SELF_APPROVAL_FORBIDDEN = "RBV4_SELF_APPROVAL_FORBIDDEN"
RBV4_PROVENANCE_INCOMPLETE = "RBV4_PROVENANCE_INCOMPLETE"

#: keys that would make this record a decision. The review is EVIDENCE; the
#: owner decides, through the clearance sheet. Matched EXACTLY against every
#: key at every depth of the assembled record — including caller-supplied
#: findings, which is the route an approval would actually arrive by.
FORBIDDEN_DECISION_KEYS = frozenset({
    "approve", "approved", "approval", "approvals",
    "self_approve", "self_approved", "self_approval",
    "grant", "granted", "grants",
    "verdict", "verdicts",
    "clearance", "cleared", "clear_to_proceed",
    "gate_decision", "gate_result", "gate_verdict",
    "accept", "accepted", "acceptance",
    "sign_off", "signoff", "signed_off",
    "passed", "pass_fail", "ruling", "authorised", "authorized",
})

DECISION_CHANNEL = (
    "this record is EVIDENCE ONLY — owner reviews are QUEUED in "
    "OWNER_REVIEW_QUEUE.md and decided ONLY through "
    "OWNER_BLOCKER_CLEARANCE.md; no decision field exists in this record "
    "by rule and none may be added")

_REPO = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
_RBV_DOCS = os.path.join(_REPO, "docs", "visual_quality", "rbv")
_THIS_FILE = os.path.abspath(__file__)

RECORD_NAME = "claude_visual_review_record.json"


class Rbv4Refusal(ValueError):
    """Fail-closed review refusal; ``findings`` lists exact codes."""

    def __init__(self, findings):
        self.findings = list(findings)
        super().__init__("; ".join(self.findings))


def _sha256(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _repo_relative(path: str) -> str:
    return os.path.relpath(os.path.realpath(path), _REPO)


def contract() -> dict:
    """Live-quoted review contract. Status is read at call time — a
    citation never upgrades a PROPOSED contract to ACTIVE."""
    return json.load(open(os.path.join(_RBV_DOCS, CONTRACT_FILE)))


def required_categories() -> tuple:
    """The review's coverage obligation, read LIVE from the contract
    rather than re-listed here: a second copy is a second authority, and
    it would drift silently the first time the contract changed."""
    cats = tuple(contract()["required_findings"])
    if not cats:
        # a zero-length obligation would make coverage vacuously satisfied
        raise Rbv4Refusal([f"{RBV4_PROVENANCE_INCOMPLETE}:"
                           "contract.required_findings is empty"])
    return cats


def classifications() -> tuple:
    return tuple(contract()["classification"])


def _scan_for_decision_keys(node, path="record", visited=None):
    """Walk EVERY key at EVERY depth and refuse any decision key.

    Returns the number of keys visited so the caller can prove the scan was
    not vacuous — a guard reported present but never seen visiting anything
    is the shape this arc has already been burned by twice.
    """
    if visited is None:
        visited = []
    if isinstance(node, dict):
        for key, value in node.items():
            visited.append(f"{path}.{key}")
            if str(key).lower() in FORBIDDEN_DECISION_KEYS:
                raise Rbv4Refusal([
                    f"{RBV4_SELF_APPROVAL_FORBIDDEN}:{path}.{key}"])
            _scan_for_decision_keys(value, f"{path}.{key}", visited)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            _scan_for_decision_keys(item, f"{path}[{i}]", visited)
    return len(visited)


def self_approval_paths_in_source(source_path: str = _THIS_FILE) -> list:
    """Static proof that no code path in this module WRITES a decision key.

    Parses the module and reports every literal string used as a dict key
    or as a ``dict(...)``/call keyword that lands in
    FORBIDDEN_DECISION_KEYS. The refusal-code constants are values, never
    keys, so a clean result means the harness has no self-approval path to
    disable.
    """
    tree = ast.parse(open(source_path).read())
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if (isinstance(key, ast.Constant)
                        and isinstance(key.value, str)
                        and key.value.lower() in FORBIDDEN_DECISION_KEYS):
                    hits.append(f"dict-key:{key.value}:line{key.lineno}")
        elif isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg and kw.arg.lower() in FORBIDDEN_DECISION_KEYS:
                    hits.append(f"kwarg:{kw.arg}:line{node.lineno}")
    return hits


def load_review_package(package_dir: str) -> dict:
    """Hash-verified load of an RBV-3 package.

    Verifies the package manifest schema, the contact sheet's recorded
    decoded-pixel hash, and EVERY referenced view against the render
    evidence it was referenced from (RBV-3 stores views by reference, so
    the bytes actually reviewed live in the render tree and must be
    re-proved here, not assumed).
    """
    findings = []
    manifest_path = os.path.join(package_dir, RBV3_MANIFEST_NAME)
    if not os.path.isfile(manifest_path):
        raise Rbv4Refusal([f"{RBV4_PACKAGE_MANIFEST_MISSING}:{package_dir}"])
    manifest = json.load(open(manifest_path))
    if manifest.get("schema") != RBV3_SCHEMA:
        raise Rbv4Refusal([f"{RBV4_PACKAGE_SCHEMA_MISMATCH}:"
                           f"{manifest.get('schema')}"])
    # §AL3(a) — THE ENTRY THE REGISTER CONTRADICTED ITSELF ABOUT. One
    # entry called the statement read COMPETENT because it is "read by no
    # count, disposition or gate"; another said the same line "launders
    # the absence into the provenance of a recorded review". Both are
    # true, and they are not in tension: nothing computes on it, and it
    # is copied verbatim into `statement` on the review record a human
    # then reads as the subject's own disclosure. Being uncomputed is
    # exactly what makes a fabricated value survive — no arithmetic
    # disagrees with "".
    #
    # It is settled structurally rather than by argument. RBV-3's
    # load_validation_render now REQUIRES `statement` on the render
    # manifest and build_review_package copies it unconditionally, so a
    # package without one did not come from RBV-3 and is refused here.
    if not manifest.get("statement"):
        raise Rbv4Refusal([f"{RBV4_PACKAGE_SCHEMA_MISMATCH}:statement"])

    # §AL3(a)/§R4 — AN ABSENT DECLARATION IS NOT A MISSING FILE, and the
    # defaults made the two indistinguishable. `contact_sheet` absent gave
    # `{}`, `file` absent gave `""`, and `os.path.join(package_dir, "")`
    # is the package DIRECTORY — which `isfile` rejects, so the load did
    # fail closed, but it failed reporting CONTACT_SHEET_MISSING:None. A
    # reviewer reading that goes looking for a sheet that was never
    # declared. Worse, `pixel_hash(...) != sheet.get("pixel_hash")` on an
    # undeclared sheet compares a real hash against None, so the mismatch
    # branch could never name what it expected either.
    #
    # RBV-3 writes both fields unconditionally (build_review_package,
    # `"contact_sheet": {"file": SHEET_NAME, "pixel_hash": ...}`), so
    # requiring them refuses only manifests RBV-3 did not write.
    sheet = manifest.get("contact_sheet")
    if not isinstance(sheet, dict) or not sheet.get("file") \
            or not sheet.get("pixel_hash"):
        raise Rbv4Refusal([f"{RBV4_PACKAGE_SCHEMA_MISMATCH}:"
                           "contact_sheet.file+pixel_hash"])
    sheet_path = os.path.join(package_dir, sheet["file"])
    if not os.path.isfile(sheet_path):
        findings.append(f"{RBV4_CONTACT_SHEET_MISSING}:{sheet['file']}")
    elif pixel_hash(sheet_path) != sheet["pixel_hash"]:
        findings.append(f"{RBV4_CONTACT_SHEET_HASH_MISMATCH}:"
                        f"{sheet['file']}")

    # §R4 judgment: defaulting these to {} let a manifest with no modes,
    # no mode A, or no views load SUCCESSFULLY with zero views — the loop
    # simply never ran and nothing was found to complain about. A package
    # with nothing in it is not a package; it is refused.
    mode_a = (manifest.get("modes") or {}).get(MODE_GEOMETRY_VALIDATION)
    if not isinstance(mode_a, dict):
        raise Rbv4Refusal([f"{RBV4_MODE_ABSENT}:{MODE_GEOMETRY_VALIDATION}:"
                           "manifest carries no geometry-validation mode"])
    if not mode_a.get("view_source_dir"):
        raise Rbv4Refusal([f"{RBV4_PACKAGE_SCHEMA_MISMATCH}:"
                           "modes.GEOMETRY_VALIDATION.view_source_dir"])
    declared_views = mode_a.get("views")
    if not isinstance(declared_views, dict) or not declared_views:
        raise Rbv4Refusal([f"{RBV4_VIEW_MISSING}:"
                           "modes.GEOMETRY_VALIDATION.views is empty"])
    source_dir = os.path.join(_REPO, mode_a["view_source_dir"])
    inputs, views = [], {}
    for view, rec in sorted(declared_views.items()):
        # Same split as the contact sheet above, and it matters more here:
        # `os.path.join(source_dir, "")` is the SOURCE DIRECTORY, and a
        # view whose `pixel_hash` is absent would compare a real hash
        # against None — a mismatch finding that names no expectation. A
        # view declared without a file or without a hash is a manifest
        # defect, not evidence that failed verification, and the two must
        # not arrive under the same code. RBV-3 writes both per view.
        if not isinstance(rec, dict) or not rec.get("source_file") \
                or not rec.get("pixel_hash"):
            raise Rbv4Refusal([f"{RBV4_PACKAGE_SCHEMA_MISMATCH}:"
                               f"views.{view}.source_file+pixel_hash"])
        path = os.path.join(source_dir, rec["source_file"])
        if not os.path.isfile(path):
            findings.append(f"{RBV4_VIEW_MISSING}:{view}:"
                            f"{rec['source_file']}")
            continue
        actual = pixel_hash(path)
        if actual != rec["pixel_hash"]:
            findings.append(f"{RBV4_VIEW_HASH_MISMATCH}:{view}:"
                            f"{rec['source_file']}")
            continue
        views[view] = path
        inputs.append({"role": f"view:{view}",
                       "path": _repo_relative(path),
                       "pixel_hash": actual})
    if findings:
        raise Rbv4Refusal(findings)

    inputs.insert(0, {"role": "review_package_manifest",
                      "path": _repo_relative(manifest_path),
                      "sha256": _sha256(manifest_path)})
    inputs.insert(1, {"role": "contact_sheet",
                      "path": _repo_relative(sheet_path),
                      "pixel_hash": sheet["pixel_hash"]})
    return {"manifest": manifest, "manifest_path": manifest_path,
            "contact_sheet_path": sheet_path, "views": views,
            "inputs_read_in_order": inputs}


def _validate_dispositions(dispositions, *, expected_source):
    """Every required category disposed exactly once, every finding
    classified from the contract's own list, every disposition stamped
    with the source it actually came from."""
    cats = required_categories()
    allowed = classifications()
    findings, out = [], []
    seen = set()
    for d in dispositions or []:
        cat = d.get("category")
        if cat not in cats:
            findings.append(f"{RBV4_CATEGORY_UNKNOWN}:{cat}")
            continue
        disp = d.get("disposition")
        if disp not in DISPOSITIONS:
            findings.append(f"{RBV4_DISPOSITION_INVALID}:{cat}:{disp}")
            continue
        if d.get("source") != expected_source:
            findings.append(f"{RBV4_FINDING_SOURCE_MISMATCH}:{cat}:"
                            f"{d.get('source')}")
            continue
        entry = {"category": cat, "disposition": disp,
                 "source": expected_source,
                 "observation": d.get("observation", "")}
        if disp == DISPOSITION_FINDING:
            klass = d.get("classification")
            if klass not in allowed:
                findings.append(f"{RBV4_CLASSIFICATION_INVALID}:{cat}:"
                                f"{klass}")
                continue
            entry["classification"] = klass
        elif disp == DISPOSITION_UNCERTAIN_MISSING_EVIDENCE:
            # the contract forbids resolving missing-evidence uncertainty
            # by assumption; the record must name what is missing
            missing = d.get("missing_evidence")
            if not missing:
                findings.append(
                    f"{RBV4_UNCERTAINTY_RESOLVED_BY_ASSUMPTION}:{cat}")
                continue
            entry["missing_evidence"] = missing
        seen.add(cat)
        out.append(entry)
    # fixed tuple from the contract, proven non-empty by
    # required_categories(); a missing category cannot be skipped
    for cat in cats:
        if cat not in seen:
            findings.append(f"{RBV4_CATEGORY_UNADDRESSED}:{cat}")
    if findings:
        raise Rbv4Refusal(findings)
    return out


def load_fixture(fixture_path: str) -> dict:
    """A fixture must say WHO recorded it and HOW. An anonymous fixture is
    a set of dispositions with no origin, which is precisely the shape a
    fabricated review would take."""
    if not os.path.isfile(fixture_path):
        raise Rbv4Refusal([f"{RBV4_FIXTURE_MISSING}:{fixture_path}"])
    data = json.load(open(fixture_path))
    if data.get("schema") != FIXTURE_SCHEMA:
        raise Rbv4Refusal([f"{RBV4_FIXTURE_SCHEMA_MISMATCH}:"
                           f"{data.get('schema')}"])
    for field in ("recorded_by", "origin", "recorded_at", "subject_id"):
        if not data.get(field):
            raise Rbv4Refusal([f"{RBV4_FIXTURE_ORIGIN_INCOMPLETE}:{field}"])
    return data


def budget_path() -> str:
    return os.path.join(_RBV_DOCS, BUDGET_FILE)


def load_budget(path: str | None = None) -> dict:
    """The committed call budget. Read from disk, never from a caller —
    a budget an argument can conjure authorizes nothing."""
    path = path or budget_path()
    if not os.path.isfile(path):
        raise Rbv4Refusal([f"{RBV4_BUDGET_RECORD_MISSING}:{path}"])
    data = json.load(open(path))
    if data.get("schema") != BUDGET_SCHEMA:
        raise Rbv4Refusal([f"{RBV4_BUDGET_SCHEMA_MISMATCH}:"
                           f"{data.get('schema')}"])
    # a budget that does not name the authority behind it authorizes
    # nothing, and the citation is persisted into every live record
    for field in ("authorized_calls", "authorized_by"):
        if not data.get(field):
            raise Rbv4Refusal([f"{RBV4_BUDGET_SCHEMA_MISMATCH}:{field}"])
    # §AL3(a)/§R4 — PRESENCE, not truth. `rollover` is legitimately
    # `false` and a truthiness test would refuse every honest budget
    # record ever written, so the check is `not in` and a bool type
    # test. Downstream this is not cosmetic: `rollover` is persisted
    # into docs/visual_quality/rbv/review_records/p1_v4/
    # claude_visual_review_record.json line 38, so defaulting it to
    # False writes "this budget does not roll over" into a committed
    # owner-facing record on the authority of a record that said
    # nothing at all. §R1b happens to make False correct for THIS
    # budget; a default that is right by coincidence is still a
    # fabricated claim about the next one.
    if "rollover" not in data or not isinstance(data["rollover"], bool):
        raise Rbv4Refusal([f"{RBV4_BUDGET_SCHEMA_MISMATCH}:rollover"])
    return data


def budget_state(path: str | None = None) -> dict:
    """Authorized / spent / remaining, computed from the committed
    entries — spend is COUNTED, never asserted."""
    path = path or budget_path()
    if not os.path.isfile(path):
        # pre-§R1 shape: no budget record was ever committed
        return {"state": BUDGET_RECORD_ABSENT,
                "live_state": NOT_EXECUTED_PENDING_OWNER_BUDGET,
                "calls_authorized": 0, "spent": 0, "remaining": 0}
    budget = load_budget(path)
    # NB: the key is `calls_authorized`, never a bare `authorized` — the
    # decision-key scan is exact-match and refused that name, correctly:
    # on a review record a bare `authorized` reads as a gate state, not as
    # a call budget. The guard caught this too.
    calls_authorized = int(budget["authorized_calls"])
    spent = len(budget.get("calls") or [])
    remaining = max(0, calls_authorized - spent)
    return {"state": BUDGET_AVAILABLE if remaining > 0 else BUDGET_EXHAUSTED,
            "live_state": (BUDGET_AVAILABLE if remaining > 0
                           else BUDGET_EXHAUSTED),
            "calls_authorized": calls_authorized, "spent": spent,
            "remaining": remaining,
            # §R4 judgment: this is the citation naming the owner ruling
            # under which provider spend is authorized, and it is PERSISTED
            # into every live review record. Defaulted to "" it would read
            # as "spend authorized by nobody" and look like a formatting
            # gap rather than a missing authority — so load_budget refuses
            # a budget record without it and this read cannot be blank.
            "authorizing_ruling": budget["authorized_by"],
            "rollover": budget["rollover"],
            "source": _repo_relative(path)}


def live_execution_state(path: str | None = None) -> dict:
    """The honest state of LIVE review execution. It never returns
    findings — an unexecuted review has none, and inventing them is the
    failure this node was told to avoid."""
    state = budget_state(path)
    live = state["live_state"]
    # §V2. A reader asking "can a live call happen" was told
    # BUDGET_AVAILABLE while the ruling forbade it. The budget ARITHMETIC
    # is untouched and stays untouched — the 6 carried calls are real and
    # authorized, and restating an owner's number to express a lock would
    # be moving a ruling's value to suit the code. What was wrong was only
    # the claim that they could be spent.
    if path is None and live == BUDGET_AVAILABLE \
            and V1_INDEPENDENT_CLEARANCE is None:
        live = LIVE_LOCKED_PENDING_V1_CLEARANCE
    return {"execution": EXECUTION_LIVE_PROVIDER,
            "state": live,
            "budget": state,
            "v1_clearance": V1_INDEPENDENT_CLEARANCE,
            "dispositions": []}


def _is_pixel_hash(value: str) -> bool:
    """The producer's own contract, not an invented shape.
    geometry_validation_render.pixel_hash is sha256(decoded pixels)
    truncated to 16 hex characters, and every hash in the committed
    ledger and every package manifest has exactly that shape."""
    return (len(value) == LEDGER_PIXEL_HASH_CHARS
            and all(c in "0123456789abcdef" for c in value))


def _image_record_findings(img, label: str, required) -> list:
    """§V1(1) RE-FIX, after four independent refutations.

    The first version tested `not value or str(value).upper() in
    SENTINELS`, which is TRUTHINESS plus a string compare. Four verifiers
    independently ran rows through it and had them ACCEPTED: True, 1,
    'yes', {'a': 1} all passed as a path AND as a pixel hash. That moved
    §V1(1)'s hole one nesting level down instead of closing it — True and
    1 are literally members of the value class §V1(1) names.

    It also reproduced the §V1(2,3,4) defect it sat next to: reading
    img.get(req) meant an ABSENT subfield and a present-null one emitted
    byte-identical findings, fabricating a value the record never held.
    Membership first here too, for the same reason as the caller.
    """
    if not isinstance(img, dict):
        return [f"{RBV4_LEDGER_ENTRY_TRANSMISSION_INVALID}:"
                f"{label}={_safe_repr(img)} is not a record"]
    out = []
    for req in required:
        code = f"{RBV4_LEDGER_ENTRY_TRANSMISSION_INVALID}:{label}.{req}"
        if req not in img:
            out.append(f"{code}={LEDGER_FIELD_ABSENT}")
            continue
        value = img[req]
        # bool is an int and would satisfy a bare isinstance(str) miss;
        # it is named first so True can never reach a text test
        # canonical form for the BLANK and SENTINEL tests, raw value for
        # the path/hash SHAPE tests below — normalising before those would
        # fold fullwidth digits into ASCII and let a non-hex hash pass.
        if isinstance(value, bool) or not isinstance(value, str) \
                or not _canonical(value) \
                or _canonical(value).upper() in LEDGER_UNKNOWN_SENTINELS:
            out.append(f"{code}={_safe_repr(value)}")
            continue
        if req == "path" and not value.lower().endswith(LEDGER_IMAGE_SUFFIXES):
            out.append(f"{code}={_safe_repr(value)} does not name an "
                       "image file")
        elif req == "pixel_hash" and not _is_pixel_hash(value):
            out.append(f"{code}={_safe_repr(value)} is not a "
                       f"{LEDGER_PIXEL_HASH_CHARS}-character pixel hash")
        # role had NO shape rule at all, so it accepted "yes" — the very
        # value class §V1(1) names — and the invisible filler codepoints
        # this module itself defines as not-writing, and even the
        # <FIELD_ABSENT> marker, which would make a present role
        # indistinguishable from a missing one.
        elif req == "role" and _canonical(value) == LEDGER_FIELD_ABSENT:
            out.append(f"{code}={_safe_repr(value)} does not name a view")
    # the legacy shape does not REQUIRE a role — there was only one image
    # to name — but a role it does carry is still a claim about what was
    # sent, and an unchecked field is how the shape became the laxer door.
    if "role" not in required and "role" in img:
        out += _image_record_findings(img, label, ("role",))
    return out


def _transmission_findings(images) -> list:
    """§V1(1). What the row says it sent, actually inspected.

    TWO SHAPES ARE HISTORICALLY VALID and both are real records of real
    calls, so neither may be rejected as falsified:

    * a LIST of per-image records (current, since §S2 began sending the
      primary views alongside the contact sheet). Each names its role;
    * a single DICT (legacy, when the contact sheet WAS the whole
      transmission). It carries no role because there was only one image.

    The shapes were never reconciled when §S2 changed the transmission,
    and that is recorded rather than migrated: rewriting a committed
    ledger row would edit evidence of what was actually sent.
    """
    if isinstance(images, list):
        if not images:
            return [f"{RBV4_LEDGER_ENTRY_TRANSMISSION_INVALID}:"
                    "image_transmitted=[] — a call that transmitted "
                    "nothing is not a review"]
        out = []
        for i, img in enumerate(images):
            out += _image_record_findings(
                img, f"image_transmitted[{i}]", LEDGER_IMAGE_REQUIRED_FIELDS)
        return out
    if isinstance(images, dict):
        # legacy single-image shape: no role to require, because there was
        # only ever one image to name
        return _image_record_findings(
            images, "image_transmitted", LEDGER_IMAGE_LEGACY_FIELDS)
    return [f"{RBV4_LEDGER_ENTRY_TRANSMISSION_INVALID}:"
            f"image_transmitted={_safe_repr(images)} is neither a record "
            "nor a list of records"]


#: what a cost may BE. A guard must not accept a value the ledger cannot
#: store: Decimal/bytes/Fraction satisfied float() but broke json.dump
#: while writing, after the budget file was already truncated.
LEDGER_COST_TYPES = (str, int, float)


def _safe_repr(value) -> str:
    """repr() ITSELF can raise. Under CPython's integer-to-string limit a
    >=4300-digit int — which json.load produces without complaint — makes
    repr() raise ValueError, and the previous fix put that call INSIDE the
    except handler, outside any try. So the refusal path crashed on
    exactly the input it was written to refuse."""
    try:
        return repr(value)
    except Exception:
        return f"<{type(value).__name__} whose repr() is unavailable>"


#: THE ACKNOWLEDGEMENT. To flag a row DEFECT an author must write this
#: string EXACTLY. It is an ALLOWLIST OF ONE, and that is the whole point
#: — see _defect_is_not_an_explanation.
LEDGER_DEFECT_ACK = "THIS ROW RECORDS A CALL WHOSE IDENTITY WAS NOT RECOVERED"

LEDGER_DEFECT_ACK_FIELD = "acknowledgement"
LEDGER_DEFECT_EXPLANATION_FIELD = "explanation"

#: Unicode categories that carry no text: controls, format characters,
#: surrogates, private use, unassigned, and every separator.
#: ...plus the combining marks (Mn/Me), which are not standalone text: a
#: combining mark requires a base character and renders nothing without
#: one, so a string of only marks carries no text. Real Arabic, Devanagari
#: and Hebrew explanations are unaffected, because their base letters
#: survive and the canonical form is non-empty.
LEDGER_NON_CONTENT_CATEGORIES = frozenset({
    "Cc", "Cf", "Cs", "Co", "Cn", "Zs", "Zl", "Zp", "Mn", "Me"})

#: THE ONE legacy free-text flag in the COMMITTED ledger, pinned by the
#: SHA-256 of the WHOLE ROW rather than of the explanation text.
#:
#: Pinning the TEXT was wrong and a panel proved it: the narrative could
#: be pasted into any number of NEW rows, each then flagged by free text
#: and skipping every §V1 check — one was accepted for a package that
#: never existed. The grandfather clause must attach to the row it
#: documents, not to a story anyone can retell.
LEDGER_DEFECT_LEGACY_ROW_SHA256 = frozenset({
    "ac83c684421c39d28c4de0741edb6b07218842a7fd8c4071598c51300f7e40b0",
})


def _canonical(text: str) -> str:
    """ONE normalisation, applied by every text test in this module.

    The previous version hand-listed eleven invisible codepoints — a
    BLOCKLIST, which is the exact error torn out of the DEFECT flag,
    reappearing one field over. A panel found 2,162 non-printing
    codepoints it missed.

    Worse, it created a NORMALISATION GAP. The sentinel test compared
    value.strip().upper() while the role test stripped zero-width
    characters, so role="UNKNOWN\u200b" satisfied BOTH — the sentinel
    check saw a string that was not "UNKNOWN", and the role check saw one
    that was not blank. Two checks, two normalisations, and the gap
    between them is the hole. There is now one.

    Category-based, so it is closed by construction rather than by a
    list: anything that is not a control, format character, surrogate,
    private-use, unassigned or separator survives. NFKC first, so
    fullwidth and compatibility spellings of a sentinel cannot slip past
    an ASCII comparison.
    """
    text = unicodedata.normalize("NFKC", text)
    return "".join(
        c for c in text
        if unicodedata.category(c) not in LEDGER_NON_CONTENT_CATEGORIES
    ).strip()


def _is_blank(value) -> bool:
    """Present-but-carrying-no-text, decided by the module's ONE
    normalisation.

    ROUND SEVEN. The required-field sweep tested `entry[f] == ""`, which
    is the empty string and nothing else, so a single ASCII SPACE
    satisfied `recorded_at`, `package_id` and `model` — the three fields
    no other check in this module reads — and the row validated clean and
    was spendable against the owner's budget.

    It was the one text test that never routed through `_canonical`,
    which is precisely what round six claimed to have eliminated: "there
    is now ONE normalisation". There was not. Stating a property and
    applying it at four of five sites is how the fifth becomes the hole.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return not _canonical(value)
    return False


def _row_digest(entry: dict) -> str | None:
    try:
        return hashlib.sha256(json.dumps(
            entry, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
    except Exception:  # noqa: BLE001
        # DELIBERATELY BROAD, and for the same reason the cost guard below
        # is: this is a DIGEST, and every escape from it unwinds
        # validate_ledger_row and DESTROYS every finding already
        # accumulated on the row — a crash instead of a refusal. The narrow
        # (TypeError, ValueError) form missed RecursionError from deeply
        # nested JSON, which json.load produces happily. Returning None
        # here is always safe: None is not in the legacy pin, so the row
        # takes the REFUSAL branch and all four §V1 checks then run.
        return None


def _defect_is_not_an_explanation(raw, entry: dict) -> str | None:
    """Why this DEFECT value fails to flag a defect, or None.

    THIS IS THE FIFTH VERSION AND THE FIRST WITH THE RIGHT SHAPE. The
    previous four all tried to judge free prose, and three independent
    panels defeated them in turn: `False`, then `"no defect"`, then
    `"no defect"` with a NO-BREAK SPACE, `"no defects"`, `"not a defect"`,
    `"nothing to report"`, and — the finding that settles it —
    `"UNKNOWN UNKNOWN"`, which defeats this module's own sentinel check
    simply by doubling it.

    THE DEFECT WAS STRUCTURAL, NOT LEXICAL. Denial was tested as
    exact-match membership in a finite BLOCKLIST while acceptance was an
    open SHAPE test, so the accepted set was unbounded: the set of
    strings meaning "no defect" is closed under punctuation, pluralisation,
    added words, whitespace substitution and paraphrase. Every blocklist
    round produces the next round. A verifier put it exactly right —
    adding "NO DEFECT." to the set produces round six.

    So the test is INVERTED. Acceptance now requires membership in an
    ALLOWLIST OF ONE: the author must write LEDGER_DEFECT_ACK verbatim,
    a sentence that ASSERTS the defect and which no phrase meaning "no
    defect" can satisfy. It cannot be written by accident, and it is
    bounded by construction rather than by vocabulary.

    A SIDE EFFECT WORTH HAVING: the explanation is now free text with no
    semantic test at all, so the previous version's two-token floor is
    gone. That floor was SCRIPT-DEPENDENT — it refused a correct Chinese
    or Japanese sentence outright, because those scripts are not
    space-delimited, while this repository demonstrably authors ZH and AR
    material. A hatch for recording a genuinely lost call that cannot be
    opened in the author's own language is a real defect, not a
    conservative default.
    """
    if isinstance(raw, str):
        if _row_digest(entry) in LEDGER_DEFECT_LEGACY_ROW_SHA256:
            return None
        return ("a bare string no longer flags a defect. Free text cannot "
                "be distinguished from text that DENIES a defect, which is "
                f"how this hatch was reopened three times. Write "
                f"{{{LEDGER_DEFECT_ACK_FIELD!r}: {LEDGER_DEFECT_ACK!r}, "
                f"{LEDGER_DEFECT_EXPLANATION_FIELD!r}: <what happened>}}")
    if not isinstance(raw, dict):
        return ("the flag must be a record carrying an acknowledgement and "
                "an explanation")
    if LEDGER_DEFECT_ACK_FIELD not in raw:
        return f"the flag carries no {LEDGER_DEFECT_ACK_FIELD}"
    if raw[LEDGER_DEFECT_ACK_FIELD] != LEDGER_DEFECT_ACK:
        return (f"{LEDGER_DEFECT_ACK_FIELD} must be exactly "
                f"{LEDGER_DEFECT_ACK!r} — this is an allowlist of one, so "
                "that no phrasing meaning the opposite can satisfy it")
    if LEDGER_DEFECT_EXPLANATION_FIELD not in raw:
        return f"the flag carries no {LEDGER_DEFECT_EXPLANATION_FIELD}"
    explanation = raw[LEDGER_DEFECT_EXPLANATION_FIELD]
    if not isinstance(explanation, str) or not _canonical(explanation):
        return (f"{LEDGER_DEFECT_EXPLANATION_FIELD} carries no text once "
                "control, format and separator characters are removed, so "
                "it explains nothing")
    return None


def validate_ledger_row(entry: dict) -> dict:
    """§R1a, tightened.

    The first version of this guard checked field PRESENCE only, so the
    row recording a lost call satisfied it while every identity field
    read UNKNOWN — a guard weaker than it looks, which is the class this
    programme keeps catching. Presence is no longer enough:

    * a row NOT flagged DEFECT must carry a REAL provider request id, a
      positive input-token count, a non-negative output-token count and a
      numeric cost. A placeholder that merely occupies the field is
      refused.
    * a row flagged DEFECT may hold unknown values — that is what the flag
      is for — but the flag must explain itself.
    """
    # THE ROW MUST BE A ROW. Every check below indexes and does membership
    # tests on `entry`; for a non-mapping the FIRST of them raises TypeError
    # ("argument of type 'X' is not iterable") straight out of the guard.
    # That is this module's recurring fault in its purest form: the refusal
    # path crashing on exactly the input it exists to refuse, so the caller
    # sees an error rather than a finding and no row is ever recorded as
    # rejected. Refuse it, do not raise through it.
    if not isinstance(entry, Mapping):
        raise Rbv4Refusal([f"{RBV4_LEDGER_ENTRY_INCOMPLETE}:"
                           f"entry_is_not_a_mapping={_safe_repr(entry)}"])

    findings = []
    # membership first, so the sweep reads no defaulted value either. The
    # old form called entry.get(f) twice per field, which made the
    # function-scope claim "no value is read for a field the row never
    # carried" FALSE even though the emitted code quoted nothing — three
    # verifiers refuted it on exactly that. The claim is made true rather
    # than narrowed. (The f != DEFECT carve-out went with it: DEFECT is
    # not in LEDGER_REQUIRED_FIELDS, so the clause was dead.)
    missing = [f for f in LEDGER_REQUIRED_FIELDS
               if f not in entry or _is_blank(entry[f])]
    findings += [f"{RBV4_LEDGER_ENTRY_INCOMPLETE}:{f}" for f in missing]

    # §V1 RE-FIX — THE HATCH THAT DISABLED EVERY OTHER CHECK.
    # The flag was read as "flagged unless the value is None", and its
    # explain-itself guard was `not str(defect).strip()`. For DEFECT=False
    # that guard sees "False" — a non-empty string — so it never fired,
    # and `defect is None` was False, so the ENTIRE block below was
    # skipped. `"DEFECT": false` is what a JSON author writes to mean
    # "this row has NO defect", and it turned off all four §V1 checks at
    # once; 0, [] and {} did the same. An escape hatch that can be opened
    # by a value meaning "no escape needed" is not an escape hatch.
    #
    # AND THAT SENTENCE WAS STILL TRUE OF THE FIX FOR IT. Round two
    # replaced truthiness with "non-empty string", which admitted
    # "no defect", "NONE", "UNKNOWN", "." and a ZERO-WIDTH SPACE — each
    # disabling all four checks, each accepted onto the budget as a spent
    # call. The flag is now an EXPLANATION or it is nothing, and what
    # counts as one is decided by _defect_is_not_an_explanation. Every
    # other value REFUSES rather than being guessed at in either
    # direction — the row is ambiguous about the one thing it exists to
    # record, and resolving that ambiguity by inference is how the hole
    # opened, twice.
    #
    # SCOPE, STATED HONESTLY: this holds for every JSON-REPRESENTABLE
    # value, which is what a ledger loaded by json.load can contain. It
    # is NOT a claim at full function scope — a str subclass overriding
    # __bool__ or strip() can still defeat it, as an independent pass
    # demonstrated. That is unreachable from a ledger file, and saying
    # so is cheaper than an overstatement that has now been refuted
    # twice.
    if LEDGER_DEFECT_FIELD in entry:
        raw = entry[LEDGER_DEFECT_FIELD]
        reason = _defect_is_not_an_explanation(raw, entry)
        if reason:
            findings.append(
                f"{RBV4_LEDGER_DEFECT_UNEXPLAINED}:"
                f"{LEDGER_DEFECT_FIELD}={_safe_repr(raw)} — {reason}")
            raw = None
        defect = raw
    else:
        defect = None

    if defect is None:
        # §U3: an ABSENT field and an EMPTY one are different §R1a
        # defects and must not collapse into one finding. The previous
        # code read the value through a "" default, so a row that never
        # carried provider_request_id produced a finding asserting
        # provider_request_id='' — a value the row never held, and
        # byte-identical to a row that really did carry a blank. The
        # sentinel is now explicit and the two cases diverge.
        # the branch is selected by MEMBERSHIP, and the value is read only
        # inside the branch that has one. An independent §U3b pass noted
        # that an earlier arrangement read the value before the branch —
        # harmlessly, since the read carried no default and the result
        # never reached the predicate, but "no value is read for an absent
        # field" is a stronger and simpler property to state truthfully.
        if "provider_request_id" not in entry:
            findings.append(
                f"{RBV4_LEDGER_ENTRY_UNKNOWN_WITHOUT_DEFECT}:"
                f"provider_request_id={LEDGER_FIELD_ABSENT}")
        else:
            # NO str() COERCION. The previous form coerced first, so the
            # integer 0 produced a finding asserting provider_request_id='0'
            # — a value the row never carried, byte-identical to a row that
            # really held the string "0". That is the §U3 defect this
            # function exists to have fixed, left standing on exactly one of
            # its five fields while the other four were type-faithful.
            rid = entry["provider_request_id"]
            if not isinstance(rid, str):
                findings.append(
                    f"{RBV4_LEDGER_ENTRY_UNKNOWN_WITHOUT_DEFECT}:"
                    f"provider_request_id={_safe_repr(rid)}")
            else:
                body = rid[len(LEDGER_REQUEST_ID_PREFIX):]
                if rid.upper() in LEDGER_UNKNOWN_SENTINELS or \
                        not rid.startswith(LEDGER_REQUEST_ID_PREFIX) or \
                        len(body) < LEDGER_REQUEST_ID_MIN_BODY or \
                        not body.isalnum():
                    findings.append(
                        f"{RBV4_LEDGER_ENTRY_UNKNOWN_WITHOUT_DEFECT}:"
                        f"provider_request_id={_safe_repr(rid)}")
        # §V1(2,3): same membership-first shape as provider_request_id.
        # These read through entry.get(field), so an absent field became a
        # present-null and the finding fabricated =None — a value the row
        # never held, indistinguishable from a row that really carried null.
        for field, floor in (("input_tokens", 1), ("output_tokens", 0)):
            if field not in entry:
                findings.append(
                    f"{RBV4_LEDGER_ENTRY_UNKNOWN_WITHOUT_DEFECT}:"
                    f"{field}={LEDGER_FIELD_ABSENT}")
                continue
            value = entry[field]
            if isinstance(value, bool) or not isinstance(value, int) \
                    or value < floor:
                findings.append(
                    f"{RBV4_LEDGER_ENTRY_UNKNOWN_WITHOUT_DEFECT}:"
                    f"{field}={_safe_repr(value)}")
        # §V1(4)
        if "cost_usd" not in entry:
            findings.append(
                f"{RBV4_LEDGER_ENTRY_UNKNOWN_WITHOUT_DEFECT}:"
                f"cost_usd={LEDGER_FIELD_ABSENT}")
        else:
            cost = entry["cost_usd"]
            try:
                # TYPE FIRST, AND A CLOSED SET OF TYPES. Decimal, bytes,
                # bytearray and Fraction all satisfied float() and passed —
                # then json.dump raised while WRITING, after the budget file
                # had already been truncated by open(path, "w"), leaving the
                # owner's authorization record unparseable. A guard must not
                # accept a value it does not constrain to something the
                # ledger can actually store.
                if isinstance(cost, bool) or \
                        not isinstance(cost, LEDGER_COST_TYPES) or \
                        str(cost).upper() in LEDGER_UNKNOWN_SENTINELS:
                    raise ValueError(cost)
                amount = float(cost)
                # NaN and inf are what float() returns for "nan"/"inf" —
                # they passed the old numeric test while naming no
                # quantity. A negative cost is not a cost either.
                if not math.isfinite(amount) or amount < 0:
                    raise ValueError(cost)
            except Exception:
                # DELIBERATELY BROAD, twice corrected. The first version
                # caught (TypeError, ValueError) and an OverflowError from a
                # huge int escaped; adding OverflowError fixed one exception
                # type rather than closing the class, and a >=4300-digit int
                # then escaped from str()/repr() itself under CPython's
                # integer-to-string limit. A __float__ that raises anything
                # else escaped too. An escape here does not merely skip one
                # check — it unwinds before the raise below and DESTROYS
                # every finding already accumulated on the row.
                findings.append(
                    f"{RBV4_LEDGER_ENTRY_UNKNOWN_WITHOUT_DEFECT}:"
                    f"cost_usd={_safe_repr(cost)}")
        # §V1(1) — THE ONE THAT LET A FALSIFIED ROW THROUGH. image_transmitted
        # was in LEDGER_REQUIRED_FIELDS so it had to be PRESENT, and nothing
        # tested what it held: 'UNKNOWN', 0, False and 'yes' were all
        # accepted on a row claiming a real call. A ledger row is the only
        # evidence a budgeted call happened, so what it transmitted must be
        # a real list of per-image records, each naming a path and a hash.
        if "image_transmitted" not in entry:
            findings.append(
                f"{RBV4_LEDGER_ENTRY_UNKNOWN_WITHOUT_DEFECT}:"
                f"image_transmitted={LEDGER_FIELD_ABSENT}")
        else:
            findings += _transmission_findings(entry["image_transmitted"])
    if findings:
        raise Rbv4Refusal(findings)
    return entry


def append_ledger_entry(entry: dict, path: str | None = None) -> dict:
    """Append one consumed call to the committed budget (§R1a).

    Refuses a partial entry: an entry missing any required field is an
    unledgered call wearing a ledger's shape, and §R1a calls that a
    defect. Refuses to append past the authorization — the count is the
    enforcement, not the intention.
    """
    path = path or budget_path()
    budget = load_budget(path)
    validate_ledger_row(entry)
    if len(budget.get("calls") or []) >= int(budget["authorized_calls"]):
        raise Rbv4Refusal([f"{RBV4_BUDGET_EXHAUSTED}:"
                           f"{budget['authorized_calls']} authorized, "
                           f"{len(budget['calls'])} spent"])
    row = {f: entry[f] for f in LEDGER_REQUIRED_FIELDS}
    # membership, matching validate_ledger_row. A .get here disagreed with
    # the validator about what "carries a DEFECT" means — harmless today
    # because validate runs first and refuses null, but two functions
    # answering the same question differently is how the gaps open.
    if LEDGER_DEFECT_FIELD in entry:
        row[LEDGER_DEFECT_FIELD] = entry[LEDGER_DEFECT_FIELD]

    # ROUND SEVEN — THE LEDGER COUNTS EVENTS, AND NOTHING ASKED IF THIS ONE
    # WAS NEW. Every §V1 round hardened what a row must LOOK like. None
    # asked whether the call it records had already been recorded, so the
    # committed rows were themselves a supply of spendable rows: appending
    # `load_budget()["calls"][0]` was demonstrated to append it AGAIN as
    # fresh spend, and that row is the grandfathered one, so it skipped all
    # four §V1 checks on the way. Six replays would have consumed the
    # owner's entire remaining authorization with no provider call at all.
    #
    # This is the module's own lesson one step further along. Pinning the
    # DEFECT text let the STORY be retold; pinning the ROW stopped that but
    # let the EVENT be re-recorded. A digest identifies a value, and a
    # value can be submitted twice.
    committed = budget.get("calls") or []
    if _row_digest(row) in {_row_digest(c) for c in committed}:
        raise Rbv4Refusal([f"{RBV4_LEDGER_ENTRY_REPLAYED}:"
                           "row is identical to one already committed — a "
                           "record already in the ledger is not a new call"])
    # A REAL provider request id names exactly ONE provider call, so its
    # reappearance is either a replay or a fabrication. Demonstrated: a row
    # with a fresh timestamp, package, tokens and cost, reusing only a
    # committed request id, validated clean and spent a call.
    #
    # The exemption is for rows carrying NO identity, where the placeholder
    # is by construction not unique — and it is bounded by a check that
    # already exists rather than by a new list: §V1 refuses a sentinel id
    # on any row not flagged DEFECT, so this branch is reachable only on
    # the owner-defined lost-call path, and the digest rule above still
    # requires a second lost call to differ from the first somewhere.
    rid = row["provider_request_id"]
    # membership, not .get — the comment further up is this module's own
    # ruling on the point, and a defaulted read here would silently exempt
    # any committed row that never carried the field from the comparison.
    if isinstance(rid, str) and \
            _canonical(rid).upper() not in LEDGER_UNKNOWN_SENTINELS and \
            any(isinstance(c, Mapping) and "provider_request_id" in c
                and c["provider_request_id"] == rid for c in committed):
        raise Rbv4Refusal([f"{RBV4_LEDGER_ENTRY_REPLAYED}:"
                           f"provider_request_id={_safe_repr(rid)} is "
                           "already committed — one request id is one call"])

    budget.setdefault("calls", []).append(row)
    # ATOMIC. `json.dump(budget, open(path, "w"))` truncates the owner's
    # authorization record the instant it opens, so ANY serialisation
    # failure left the ledger at zero bytes and unparseable. Round four
    # closed that for cost_usd by constraining its type — but the
    # destruction mechanism was never cost-specific, and an independent
    # pass demonstrated twelve accepted rows that destroyed the file
    # through fields the type fix never touched. Serialise FIRST, then
    # replace in one operation: the committed record either survives
    # untouched or is replaced whole, and no input can make it vanish.
    try:
        payload = json.dumps(budget, indent=1)
    except (TypeError, ValueError) as exc:
        # a value that validated but cannot be stored is a refusal, not a
        # stray TypeError from the depths of the writer
        raise Rbv4Refusal([f"{RBV4_LEDGER_ENTRY_INCOMPLETE}:"
                           f"row is not serialisable — {exc}"]) from exc
    tmp = f"{path}.tmp"
    with open(tmp, "w") as fh:
        fh.write(payload)
    os.replace(tmp, path)
    return budget


def review_package(package_dir: str, *, execution: str, created_at: str,
                   mode: str = MODE_GEOMETRY_VALIDATION,
                   fixture_path: str | None = None,
                   budget_path_override: str | None = None,
                   provider=None, note: str = "",
                   out_dir: str | None = None) -> dict:
    """Run a structured visual review over an RBV-3 package.

    Returns the ``rbv4_claude_review_record/1.0`` record (written to
    ``out_dir`` when given). Raises ``Rbv4Refusal`` rather than returning a
    record whose inputs, derivation or authority cannot be stated.
    """
    if execution not in EXECUTIONS:
        raise Rbv4Refusal([f"{RBV4_EXECUTION_INVALID}:{execution}"])

    package = load_review_package(package_dir)
    manifest = package["manifest"]

    # §1 two-mode principle: a validation render is never reviewed AS a
    # presentation render. Mode B is ABSENT_BLOCKED and stays absent.
    #
    # §AL3(a) — the refusal is now ONE question instead of three fused
    # into a boolean. `mode != GEOMETRY_VALIDATION` and "the manifest has
    # no such mode" are different facts and used to arrive under the same
    # code with reasons UNKNOWN. They cannot both be true after
    # load_review_package, which refuses a manifest whose modes block or
    # whose mode A is absent — so the second disjunct was unreachable and
    # the `{}` default stood in for a state the loader had already
    # excluded.
    if mode != MODE_GEOMETRY_VALIDATION:
        # The manifest states WHY each absent mode is absent, and those
        # reasons are the useful half of this refusal — a caller asking
        # for mode B should be told RBV2C_PRESENTATION_RENDERER_NOT_BUILT,
        # not merely that it asked for the wrong mode.
        #
        # REVERSAL, recorded where it happened: the first version of this
        # repair dropped them, and
        # test_reviewing_the_absent_presentation_mode_refuses_with_reasons
        # failed on the assertion that the finding names that code. I had
        # read the `or {}` and the `or ["UNKNOWN"]` as pure defaulting and
        # missed that the expression around them was carrying evidence.
        # The single-argument `.get` below is not a fallback: a mode the
        # manifest does not declare at all is a real state with one
        # honest reading, and it is named rather than defaulted.
        declared = manifest["modes"].get(mode)
        reasons = (declared or {}).get("reasons") or [
            f"{mode} is not declared by this package"]
        raise Rbv4Refusal([f"{RBV4_MODE_ABSENT}:{mode}:" + ",".join(reasons)])
    mode_block = manifest["modes"][MODE_GEOMETRY_VALIDATION]

    inputs = list(package["inputs_read_in_order"])
    contract_path = os.path.join(_RBV_DOCS, CONTRACT_FILE)
    live_contract = contract()
    inputs.append({"role": "review_contract",
                   "path": _repo_relative(contract_path),
                   "sha256": _sha256(contract_path)})

    if execution == EXECUTION_OFFLINE_FIXTURE:
        if not fixture_path:
            raise Rbv4Refusal([f"{RBV4_FIXTURE_MISSING}:<none supplied>"])
        fixture = load_fixture(fixture_path)
        fixture_sha = _sha256(fixture_path)
        inputs.append({"role": "recorded_review_fixture",
                       "path": _repo_relative(fixture_path),
                       "sha256": fixture_sha})
        dispositions = _validate_dispositions(
            fixture.get("dispositions"),
            expected_source=SOURCE_RECORDED_FIXTURE)
        execution_block = {
            "execution": EXECUTION_OFFLINE_FIXTURE,
            "provider_call_made": False,
            "state": "REPLAYED_FROM_RECORDED_FIXTURE",
            "fixture": {"path": _repo_relative(fixture_path),
                        "sha256": fixture_sha,
                        "recorded_at": fixture["recorded_at"],
                        "recorded_by": fixture["recorded_by"],
                        "origin": fixture["origin"]},
            "meaning": ("these dispositions were REPLAYED, not observed in "
                        "this run; they carry no provider evidence and "
                        "stand only for the fixture they came from"),
        }
    else:
        # §V2 FIRST, ahead of every other live check, because it is the
        # outermost question: not "is there budget" but "may any of it be
        # spent yet". The lock binds the COMMITTED authorization — the
        # owner's 10 — which is what §V2 is about; a caller supplying its
        # own budget file is spending no part of it and is already outside
        # §R1's authority model by the rule stated at the top of this
        # module. That boundary is stated, not hidden: it is why the
        # harness's own live-path tests still run against a stub.
        if budget_path_override is None and V1_INDEPENDENT_CLEARANCE is None:
            raise Rbv4Refusal([
                f"{RBV4_V1_CLEARANCE_ABSENT}:OWNER_BLOCKER_CLEARANCE.md §V2 "
                "— the carried §R1 calls become spendable only once §V1's "
                "fixes have cleared an INDEPENDENT pass, and no clearance "
                "is recorded"])
        budget = budget_state(budget_path_override)
        if budget["state"] == BUDGET_RECORD_ABSENT:
            raise Rbv4Refusal([
                f"{RBV4_BUDGET_NOT_AUTHORIZED}:"
                f"{NOT_EXECUTED_PENDING_OWNER_BUDGET}"])
        if budget["state"] == BUDGET_EXHAUSTED:
            raise Rbv4Refusal([
                f"{RBV4_BUDGET_EXHAUSTED}:{budget['spent']} of "
                f"{budget['calls_authorized']} spent"])
        if provider is None:
            raise Rbv4Refusal([f"{RBV4_PROVIDER_ABSENT}:live execution "
                               "requires an injected provider"])
        response = provider(package)
        identity = (response or {}).get("provider_identity") or {}
        # §R4 judgment: request_id was read with a "" default while name
        # and model from the SAME dict were refused when absent — so a
        # record could be stamped EXECUTED carrying a blank audit link
        # back to its ledger row. It is now required like the other two.
        if not identity.get("name") or not identity.get("model") \
                or not identity.get("request_id"):
            raise Rbv4Refusal([f"{RBV4_PROVIDER_IDENTITY_INCOMPLETE}:"
                               f"{sorted(identity)}"])
        raw = json.dumps(response, sort_keys=True).encode()
        dispositions = _validate_dispositions(
            (response or {}).get("dispositions"),
            expected_source=SOURCE_PROVIDER_CALL)
        execution_block = {
            "execution": EXECUTION_LIVE_PROVIDER,
            "provider_call_made": True,
            "state": "EXECUTED",
            "provider_identity": {"name": identity["name"],
                                  "model": identity["model"]},
            # the audit link back to the committed ledger row: this record
            # and the spend it caused name each other
            "provider_request_id": identity["request_id"],
            "response_sha256": hashlib.sha256(raw).hexdigest(),
            # re-read AFTER the call so the record shows the spend it
            # caused, not the state that preceded it
            "budget": budget_state(budget_path_override),
        }

    record = {
        "schema": RECORD_SCHEMA,
        "contract": {
            "schema": live_contract["schema"],
            "status": live_contract["status"],
            "source": f"docs/visual_quality/rbv/{CONTRACT_FILE}",
        },
        "subject_id": manifest.get("subject_id"),
        "created_at": created_at,
        "note": note,
        "mode_reviewed": mode,
        "statement": manifest["statement"],
        "presentation_mode": manifest["modes"][MODE_CLIENT_PRESENTATION],
        "execution": execution_block,
        "dispositions": dispositions,
        "counts_by_classification": _counts(dispositions),
        "authority": {
            "rules": list(live_contract["authority_rules"]),
            # NB: this key may not itself be named `self_approval` — the
            # scan below is exact-match over FORBIDDEN_DECISION_KEYS and
            # refused this record's first draft. The guard caught its own
            # author, which is the only kind of proof worth having.
            "no_self_approval_rule": (
                "STRUCTURALLY ABSENT — this record carries no decision key "
                "at any depth and the harness raises if one is present"),
            "gate_relationship": ("EVIDENCE ONLY — findings never override "
                                  "a blocking automated failure and never "
                                  "substitute owner judgment"),
            "decision_channel": DECISION_CHANNEL,
        },
        "provenance": {
            "inputs_read_in_order": inputs,
            "derivation": {
                "module": _repo_relative(_THIS_FILE),
                "code_sha256": _sha256(_THIS_FILE),
                "record_schema": RECORD_SCHEMA,
            },
            "required_categories": list(required_categories()),
            "law": ("3aa — a derived quantity carries the identity of every "
                    "input it read and of the derivation that produced it, "
                    "or it is not evidence"),
        },
    }

    # unconditional, on the ASSEMBLED record: no branch reaches a return
    # without passing through here
    _assert_provenance_complete(record)
    record["decision_key_scan"] = {
        "keys_visited": _scan_for_decision_keys(record),
        "forbidden_keys": sorted(FORBIDDEN_DECISION_KEYS),
    }

    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        json.dump(record, open(os.path.join(out_dir, RECORD_NAME), "w"),
                  indent=1)
    return record


def review_with_budget(package_dir: str, *, created_at: str,
                       fixture_path: str, provider=None,
                       budget_path_override: str | None = None,
                       note: str = "", out_dir: str | None = None) -> dict:
    """§R1b: run LIVE while budget remains, otherwise record
    BUDGET_EXHAUSTED and continue OFFLINE.

    The degradation can never be mislabelled. The offline branch produces
    dispositions stamped RECORDED_FIXTURE, and ``_validate_dispositions``
    rejects any disposition whose stamp disagrees with the path that
    produced it — so an exhausted run cannot emit ``EXECUTED`` or
    provider-sourced findings even if a caller asks it to.
    """
    state = budget_state(budget_path_override)
    # §V2. The lock is a live-UNAVAILABLE condition, so it takes §R1b's
    # existing road: go offline and say why. Letting the refusal propagate
    # would turn a spending lock into a crash for every caller that only
    # wanted a review, and this function's whole design is that the reason
    # for not running live is RECORDED and never mislabelled — it already
    # distinguishes "ran out" from "no provider supplied". Locked is a
    # third reason, and it is neither of those two.
    locked = (budget_path_override is None
              and V1_INDEPENDENT_CLEARANCE is None)
    if state["state"] == BUDGET_AVAILABLE and provider is not None \
            and not locked:
        return review_package(
            package_dir, execution=EXECUTION_LIVE_PROVIDER,
            created_at=created_at, provider=provider,
            budget_path_override=budget_path_override, note=note,
            out_dir=out_dir)
    record = review_package(
        package_dir, execution=EXECUTION_OFFLINE_FIXTURE,
        created_at=created_at, fixture_path=fixture_path, note=note)
    # why this run is offline, distinguishing the two cases honestly: a
    # budget that RAN OUT is a degradation; no provider supplied is simply
    # an offline run and must not be dressed up as one
    if state["state"] == BUDGET_EXHAUSTED:
        record["execution"]["degraded_from_live"] = {
            "budget_state": BUDGET_EXHAUSTED,
            "reason": (f"{state['spent']} of {state['calls_authorized']} "
                       "authorized calls spent"),
            "rule": ("§R1b — at exhaustion the harness records "
                     "BUDGET_EXHAUSTED and continues offline; it never "
                     "labels fixture output as live"),
        }
    elif locked:
        record["execution"]["locked_from_live"] = {
            "budget_state": state["state"],
            "live_state": LIVE_LOCKED_PENDING_V1_CLEARANCE,
            "reason": (f"{state['remaining']} of {state['calls_authorized']} "
                       "authorized calls remain and are NOT spendable"),
            "rule": ("OWNER_BLOCKER_CLEARANCE.md §V2 — the carried §R1 calls "
                     "become spendable only once §V1's fixes have cleared an "
                     "INDEPENDENT pass; no clearance is recorded"),
        }
    else:
        record["execution"]["offline_by_request"] = {
            "budget_state": state["state"],
            "reason": "no provider injected; live execution was not requested",
        }
    # re-scan and re-write: the block above is new content on the record
    record["decision_key_scan"]["keys_visited"] = \
        _scan_for_decision_keys(
            {k: v for k, v in record.items() if k != "decision_key_scan"})
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        json.dump(record, open(os.path.join(out_dir, RECORD_NAME), "w"),
                  indent=1)
    return record


def _counts(dispositions) -> dict:
    counts = {k: 0 for k in classifications()}
    for d in dispositions:
        if d["disposition"] == DISPOSITION_FINDING:
            counts[d["classification"]] += 1
    return counts


def _assert_provenance_complete(record) -> None:
    """A review that cannot state what it read and what produced it does
    not return findings (3aa)."""
    missing = []
    prov = record.get("provenance") or {}
    if not prov.get("inputs_read_in_order"):
        missing.append("inputs_read_in_order")
    for entry in prov.get("inputs_read_in_order", []):
        if not entry.get("path") or not (entry.get("sha256")
                                         or entry.get("pixel_hash")):
            missing.append(f"input-identity:{entry.get('role')}")
    deriv = prov.get("derivation") or {}
    if not deriv.get("code_sha256"):
        missing.append("derivation.code_sha256")
    execution = record.get("execution") or {}
    if execution.get("execution") == EXECUTION_OFFLINE_FIXTURE:
        if not (execution.get("fixture") or {}).get("sha256"):
            missing.append("execution.fixture.sha256")
    elif execution.get("execution") == EXECUTION_LIVE_PROVIDER:
        if not execution.get("response_sha256"):
            missing.append("execution.response_sha256")
    for d in record.get("dispositions", []):
        if d.get("source") not in FINDING_SOURCES:
            missing.append(f"disposition-source:{d.get('category')}")
    if missing:
        raise Rbv4Refusal([f"{RBV4_PROVENANCE_INCOMPLETE}:{m}"
                           for m in missing])
