"""H2 design-request pipeline — the PROMOTED fail-closed stage validators.

PROMOTION, NOT A REWRITE (§O-session work item 2): this module is the
docs-side ``h2_pipeline.py`` promoted into engine code verbatim in logic —
same stages, same finding codes, same refusal semantics — proven by the
regression that both live run trees (es3083_lid_alt_01, fb3093_compact_01,
fb3093_compact_02) validate UNCHANGED under this module. The docs file
remains as a thin delegating shim so launchers keep their CLI.

THE CONTRACT ENCODED HERE (h2_brief_contract.json + §H2 + §L amendment):
- THE_RULE: a missing brief field is resolved IN-REQUEST (ask, or take a
  web PRIOR with URL provenance) — it may NEVER become a standing owner-
  side blocker. The validators enforce the residue: every measurement
  carries tier MEASURED|PRIOR and a source; PRIOR requires a URL.
- The web-harvest stage is FIRST-CLASS: a ledger with zero entries is a
  FAIL by the milestone's own terms (creativity via real web inspiration
  is the system's main idea), and every entry carries provenance plus an
  originality note (inspired-by, never copied).
- Generation cites its inspiration: 4-6 candidates, each citing >=1 real
  ledger entry, SVG + PNG on disk.
- The quiet-minimal DEFAULT (recorded owner taste, C3-over-C1) requires
  one quiet_minimal candidate — waivable ONLY by a signed owner mandate
  in the request's round_pointer.json (§L amendment; owner authority
  outranks the recorded default).
- Every validator refuses rather than defaults: a stage that did not run
  is a visible FAIL, never a silent pass (the composed-gate lesson).

Stdlib-only on purpose: the docs shim and future cron/headless contexts
import this without Django or the venv.
"""

import json
from pathlib import Path

MEASUREMENT_TIERS = ("MEASURED", "PRIOR")
LEDGER_ENTRY_REQUIRED = ("source_url", "source_kind", "observed",
                         "idea_contributed", "originality_note")
CANDIDATE_REQUIRED = ("candidate_id", "title", "svg", "png",
                      "inspired_by_ledger_entries", "direction",
                      "originality_statement")
CANDIDATE_MIN, CANDIDATE_MAX = 4, 6

#: the run trees the pipeline has produced (ground truth for the
#: promotion regression and the dashboard); relative to docs/roadmap/palt_h2
KNOWN_REQUEST_DIRS = ("es3083_lid_alt_01", "fb3093_compact_01",
                      "fb3093_compact_02")


def _fail(findings, code, detail):
    findings.append({"code": code, "detail": detail})


def validate_brief(brief_path):
    """Brief must satisfy the contract's required set and THE_RULE's shape:
    every measurement carries a tier and a source; nothing is
    blank-as-omission."""
    findings = []
    brief = json.loads(Path(brief_path).read_text())
    if brief.get("record_type") != "h2_design_request_brief/1.0":
        _fail(findings, "BRIEF_WRONG_RECORD_TYPE",
              str(brief.get("record_type")))
    for field in ("request_id", "submitted_by", "submitted_on",
                  "product_identity", "physical_measurements",
                  "deliverables_wanted", "brand_constraints"):
        if field not in brief:
            _fail(findings, "BRIEF_REQUIRED_FIELD_ABSENT", field)
    for m in brief.get("physical_measurements", []):
        for k in ("name", "value", "unit", "tier", "source"):
            if k not in m:
                _fail(findings, "MEASUREMENT_FIELD_ABSENT",
                      "%s missing %s" % (m.get("name", "?"), k))
        if m.get("tier") not in MEASUREMENT_TIERS:
            _fail(findings, "MEASUREMENT_TIER_INVALID",
                  "%s: %s" % (m.get("name", "?"), m.get("tier")))
        if m.get("tier") == "PRIOR" and "http" not in str(m.get("source", "")):
            _fail(findings, "PRIOR_WITHOUT_URL_PROVENANCE",
                  m.get("name", "?"))
    if not brief.get("deliverables_wanted"):
        _fail(findings, "BRIEF_NO_DELIVERABLES", "deliverables_wanted empty")
    return {"stage": "brief", "path": str(brief_path), "findings": findings,
            "verdict": "PASS" if not findings else "FAIL"}


def validate_ledger(ledger_path):
    """0 entries = FAILED by the launcher's own terms. Every entry carries
    a real source URL, what was observed, the idea it contributes, and an
    originality note (inspired-by, never copied)."""
    findings = []
    p = Path(ledger_path)
    if not p.exists():
        return {"stage": "ledger", "path": str(ledger_path),
                "findings": [{"code": "LEDGER_ABSENT",
                              "detail": "no harvest ever landed"}],
                "verdict": "FAIL"}
    ledger = json.loads(p.read_text())
    entries = ledger.get("entries", [])
    if not entries:
        _fail(findings, "LEDGER_EMPTY",
              "0 entries — the harvest did not run or landed nothing; "
              "item FAILED")
    seen_urls = set()
    for i, e in enumerate(entries):
        for k in LEDGER_ENTRY_REQUIRED:
            if not e.get(k):
                _fail(findings, "LEDGER_ENTRY_FIELD_ABSENT",
                      "entry %d missing %s" % (i, k))
        url = e.get("source_url", "")
        if not url.startswith("http"):
            _fail(findings, "LEDGER_ENTRY_NOT_A_URL",
                  "entry %d: %s" % (i, url))
        if url in seen_urls:
            _fail(findings, "LEDGER_DUPLICATE_URL", url)
        seen_urls.add(url)
    if not ledger.get("harvest_executor"):
        _fail(findings, "HARVEST_EXECUTOR_UNRECORDED",
              "the ledger must say WHAT ran the searches (session tools "
              "or engine module)")
    return {"stage": "ledger", "path": str(ledger_path),
            "findings": findings,
            "verdict": "PASS" if not findings else "FAIL",
            "entry_count": len(entries)}


def validate_candidates(request_dir, ledger_path):
    """4-6 candidates; each cites >=1 real ledger entry; SVG and PNG both
    on disk; at least one candidate declares the quiet/minimal direction
    (waivable only by a signed owner mandate — §L amendment)."""
    findings = []
    req = Path(request_dir)
    reg_path = req / "candidates" / "candidate_register.json"
    if not reg_path.exists():
        return {"stage": "candidates", "path": str(reg_path),
                "findings": [{"code": "CANDIDATE_REGISTER_ABSENT",
                              "detail": "generation never ran"}],
                "verdict": "FAIL"}
    register = json.loads(reg_path.read_text())

    # §AO3(c) line 137. The default failed CLOSED — 0 is not in [4,6] — but
    # reported "0 not in [4,6]", which is what a register listing zero
    # candidates says too. Right verdict, wrong cause, and no reader could
    # tell them apart from the finding.
    cands = register.get("candidates")
    if cands is None:
        _fail(findings, "CANDIDATE_REGISTER_MALFORMED",
              "register declares no `candidates` key at all")
        cands = []
    elif not isinstance(cands, list):
        _fail(findings, "CANDIDATE_REGISTER_MALFORMED",
              "`candidates` is %s, not a list" % type(cands).__name__)
        cands = []
    if not (CANDIDATE_MIN <= len(cands) <= CANDIDATE_MAX):
        _fail(findings, "CANDIDATE_COUNT_OUT_OF_RANGE",
              "%d not in [%d,%d]" % (len(cands), CANDIDATE_MIN,
                                     CANDIDATE_MAX))

    # §AO3(c) line 143. The default failed closed LOUD and blamed the wrong
    # artifact: an `entries`-less ledger emptied `valid_ids`, so every
    # citation became CANDIDATE_CITES_UNKNOWN_ENTRY and the finding accused
    # the CANDIDATES of citing badly when the LEDGER is the broken record.
    ledger = json.loads(Path(ledger_path).read_text())
    entries = ledger.get("entries")
    if not isinstance(entries, list):
        _fail(findings, "LEDGER_MALFORMED",
              "%s declares no `entries` list (got %s); candidate citations "
              "cannot be checked against it"
              % (Path(ledger_path).name, type(entries).__name__))
        entries = []
    valid_ids = {e["entry_id"] for e in entries if "entry_id" in e}
    minimal_present = False
    for index, c in enumerate(cands):
        # §AO3(c) lines 150/155/160/164. `"?"` was a label, and a label
        # that is the same for every unnamed candidate cannot tell two of
        # them apart. The register index always exists and always
        # distinguishes; it costs nothing and says strictly more.
        who = c.get("candidate_id") or "register index %d (no candidate_id)" \
            % index
        for k in CANDIDATE_REQUIRED:
            if k not in c:
                _fail(findings, "CANDIDATE_FIELD_ABSENT",
                      "%s missing %s" % (who, k))
        for art_key in ("svg", "png"):
            # §AO3(a)+(b) — THE FAIL-OPEN. `req / "candidates" / ""` and
            # `... / "."` both yield the candidates DIRECTORY, and that
            # directory is guaranteed present because candidate_register
            # .json was read out of it above. So `.exists()` collapsed
            # from "is this artwork on disk" to "did we get this far",
            # and the answer to the second is always yes. Measured: a
            # register with `"png": ""` returned PASS with an EMPTY
            # findings list. The name is validated BEFORE it is joined.
            name = c.get(art_key)
            if not isinstance(name, str) or not name.strip() \
                    or name.strip() in (".", "..") or "/" in name \
                    or "\\" in name:
                _fail(findings, "CANDIDATE_ARTIFACT_NAME_INVALID",
                      "%s: %s is %r, which is not a plain filename"
                      % (who, art_key, name))
                continue
            art = req / "candidates" / name
            # is_file(), not exists(): a directory is not artwork.
            if not art.is_file():
                _fail(findings, "CANDIDATE_ARTIFACT_ABSENT",
                      "%s: %s" % (who, name))
        cited = c.get("inspired_by_ledger_entries") or []
        if not cited:
            _fail(findings, "CANDIDATE_CITES_NO_INSPIRATION", who)
        for eid in cited:
            if eid not in valid_ids:
                _fail(findings, "CANDIDATE_CITES_UNKNOWN_ENTRY",
                      "%s cites %s" % (who, eid))
        if c.get("direction") == "quiet_minimal":
            minimal_present = True
    if cands and not minimal_present:
        # The quiet_minimal default encodes the C3-era taste. A SIGNED
        # owner mandate in the request (round_pointer.json citing an
        # OWNER_BLOCKER_CLEARANCE section, e.g. §L's complexity mandate)
        # supersedes it — owner authority outranks the recorded default.
        rp = Path(request_dir) / "round_pointer.json"
        waived = False
        if rp.is_file():
            # §AO3(c) REGISTERED THIS LINE COMPETENT AND THAT WAS WRONG.
            # The old code coerced a defaulted lookup of the mandate key
            # to text and asked whether the result contained the token.
            # The comment here argued that the coercion hardened it,
            # "because a mandate that is not text is not a signed citation
            # either". It did the opposite. A list or dict naming the
            # file stringifies to a representation CONTAINING the token,
            # so `["OWNER_BLOCKER_CLEARANCE §L"]` and
            # `{"cite": "OWNER_BLOCKER_CLEARANCE"}` both set `waived` —
            # a value that is not a signed citation waived a recorded
            # owner requirement. A fail-open on OWNER AUTHORITY, the one
            # direction this is not allowed to fail.
            #
            # Repaired, not registered: the mandate must BE text. Absent,
            # null, numeric, list and dict all leave `waived` False and
            # NO_QUIET_MINIMAL_CANDIDATE firing. Only a human-signed
            # string citing the clearance file can waive owner taste.
            mandate = json.loads(rp.read_text()).get("mandate")
            waived = (isinstance(mandate, str)
                      and "OWNER_BLOCKER_CLEARANCE" in mandate)
        if not waived:
            _fail(findings, "NO_QUIET_MINIMAL_CANDIDATE",
                  "recorded owner taste (C3-over-C1) requires at least "
                  "one direction == quiet_minimal (waivable only by a "
                  "signed owner mandate in round_pointer.json)")
    return {"stage": "candidates", "path": str(reg_path),
            "findings": findings,
            "verdict": "PASS" if not findings else "FAIL",
            "candidate_count": len(cands)}


def validate_request(request_dir):
    """Whole-request gate: brief, ledger, candidates, contact sheet."""
    req = Path(request_dir)
    results = [
        validate_brief(req / "brief.json"),
        validate_ledger(req / "inspiration_ledger.json"),
        validate_candidates(req, req / "inspiration_ledger.json"),
    ]
    sheet = req / "contact_sheet.png"
    results.append({
        "stage": "contact_sheet", "path": str(sheet),
        "findings": [] if sheet.exists() else
        [{"code": "CONTACT_SHEET_ABSENT",
          "detail": "review board never rendered"}],
        "verdict": "PASS" if sheet.exists() else "FAIL"})
    return {"record_type": "h2_request_validation/1.0",
            "request_dir": str(req), "stages": results,
            "verdict": "PASS" if all(r["verdict"] == "PASS"
                                     for r in results) else "FAIL"}


# ------------------------------------------------- read-only review layer
# The CORR-1 lesson: committed files are not a human review boundary. The
# functions below derive request state for the dashboard and the run-tree
# index — READ-ONLY over the run trees; picks still land through the owner
# clearance sheet, never through this layer.

#: §AN3(a) — THE TWO COMMITTED DECISION VOCABULARIES, enumerated rather
#: than pattern-matched. Both are on disk under a signed owner authority
#: citation and one declared schema version, `h2_owner_pick_ingestion/1.0`:
#: `fb3093_compact_01` and `_02` carry `verdict`/`verdict_verbatim`;
#: `es3083_lid_alt_01` carries `pick_verbatim`/`picked_candidate` and no
#: `verdict` field at all. Reading only one of them and calling the other
#: malformed would substitute the executor's preference for what the owner
#: actually recorded.
#:
#: Matching any field whose NAME contains "verdict" or "pick" was the
#: obvious alternative and is rejected under §AD0(b): an instrument that
#: recognises a decision by the spelling of its container reports on
#: spelling. A third vocabulary costs one line here, levied exactly when a
#: new one appears — which is the event a human should look at.
PICK_DECISION_DIALECTS = (
    ("verdict_field", ("verdict", "verdict_verbatim")),
    ("pick_verbatim_field", ("pick_verbatim", "picked_candidate")),
)
PICK_DECISION_UNDECLARED = "PICK_DECISION_UNDECLARED"
STAGE_PICK_UNDECLARED = "pick_recorded_decision_undeclared"

#: §AN2 — rendered where a field the record does not carry would otherwise
#: be rendered as "". The distinction is the point: "" says the owner wrote
#: nothing there, `FIELD_ABSENT` says the record has no such field. On an
#: owner decision surface those are different claims, and only one of them
#: is true.
FIELD_ABSENT = "FIELD_ABSENT"


def _absent(record, field):
    """The field's value, or a marker naming it as absent — never ""."""
    value = record.get(field)
    if value is None or (isinstance(value, str) and not value.strip()):
        return f"{FIELD_ABSENT}:{field}"
    return value


def _list_field(record, field, what):
    """``(items, defect_or_None)`` for a list-valued field on a run-tree
    record, distinguishing THREE states that a defaulted-to-empty-list
    lookup merged into one empty list (the expression is described rather
    than quoted — quoting it made the composed gate flag this DOCSTRING,
    §AD0(b), the fifth time this sprint that my own prose about a defect
    was mistaken for the defect):

    * ``record is None`` — the stage has not run. ``[]`` is the truth and
      there is no defect. This is the ordinary early-stage case.
    * the record is present and carries a list — normal.
    * the record is present and carries no list — MALFORMED, and the
      empty list that used to stand in for it was reported to the owner
      as a fact: ``ledger_entries: 0`` reads as "the harvest found
      nothing", which is a finding about the WORK; the truth was a
      finding about the RECORD.

    A defect is returned rather than raised because this is a summary, not
    a validator. Crashing the review surface would hide the other three
    requests to report one, and the four stage validators are where a
    refusal belongs. §AN3(d) leaves genuinely corrupt JSON to propagate;
    a well-formed record with a missing field is a different thing and
    gets named instead.
    """
    if record is None:
        return [], None
    value = record.get(field)
    if isinstance(value, list):
        return value, None
    return [], "%s: `%s` is %s, not a list" % (
        what, field, "absent" if value is None else type(value).__name__)


def _pick_dialect(pick):
    """Which committed vocabulary this pick record states its decision in.

    Returns ``(dialect_name, verbatim_text)``, or ``(None, "")`` when the
    record declares its decision in neither — the state §AN3(b) makes
    explicit. No record on disk is in it, which is exactly why it is
    asserted rather than assumed.
    """
    for name, fields in PICK_DECISION_DIALECTS:
        for field in fields:
            value = pick.get(field)
            if isinstance(value, str) and value.strip():
                return name, value
            if isinstance(value, dict) and value:
                # `picked_candidate` is an object; its title is the
                # owner's own words for what was chosen.
                title = value.get("title") or value.get("candidate_id")
                if title:
                    return name, str(title)
    return None, ""


def _load(p):
    """Read a run-tree record. ABSENT is None; CORRUPT is not.

    §AN3(d) — this used to catch ``(OSError, ValueError)`` together and
    return None for both, which made a ``brief.json`` full of garbage
    indistinguishable from no ``brief.json`` at all. The first is a defect
    in a committed record; the second is an ordinary early stage. A
    corrupt committed record is not a stage, so the parse error is left to
    propagate.

    Counted, not assumed: four call sites, all in ``request_summary``, all
    over files whose absence is already handled by an explicit ``is None``
    or ``or {}`` downstream.
    """
    path = Path(p)
    if not path.is_file():
        return None
    return json.loads(path.read_text())


def _emissions_for(emission_record, request_name):
    """Emissions belonging to one request, from a record whose shape is
    CHECKED rather than defaulted.

    Three states, and the whole point is that they are three:

    * ``emission_record is None`` — the caller chose not to consider
      emissions. The parameter is optional and this is what optional means.
    * an entry with **no** ``h2_request`` key — not an H2-sourced emission.
      Measured at the moment of writing: **3 of the 6** committed emissions
      are in this state (``es3083_lid_C3.ai``, ``es3083_label_sheet_T1.ai``,
      ``es3083_back_label_DRAFT.ai``), all M7 work with no H2 lineage. Their
      absence is MEANINGFUL, so it is tested for by name.
    * an entry that HAS the key but cannot say which request — a malformed
      committed record, refused.

    This replaces ``str(e.get("h2_request") or "").endswith(...)``, which I
    wrote earlier in this same sprint while removing fallbacks, and which
    collapsed the second and third states into one. It also swapped two
    ``lookup_default`` hits for one ``or_default`` hit — a change in which
    shape the detector sees, not a change in whether the code is honest.
    Recorded here because it happened here.
    """
    if emission_record is None:
        return []
    entries = emission_record.get("emissions")
    if not isinstance(entries, list):
        raise ValueError(
            "emission record carries no `emissions` list (got %s); a "
            "malformed record is not an absence — §AN3(d)"
            % type(entries).__name__)
    out = []
    for entry in entries:
        if "h2_request" not in entry:
            continue                      # not H2-sourced; see above
        target = entry.get("h2_request")
        if not isinstance(target, str) or not target.strip():
            raise ValueError(
                "emission %r claims H2 lineage but does not say which "
                "request (h2_request=%r)" % (entry.get("ai"), target))
        if target.endswith(request_name):
            out.append(entry)
    return out


def request_summary(request_dir, emission_record=None):
    """One request's state, derived from what is actually on disk."""
    req = Path(request_dir)
    # Kept as None-or-record rather than collapsed to `{}` on load: an
    # ABSENT brief and a brief with no measurements are different states,
    # and `_list_field` below can only tell them apart if the distinction
    # survives this line.
    brief = _load(req / "brief.json")
    ledger = _load(req / "inspiration_ledger.json")
    register = _load(req / "candidates" / "candidate_register.json")
    pick = _load(req / "owner_pick_ingestion.json")
    emissions = _emissions_for(emission_record, req.name)

    # §AN2 — the decision, read from whichever vocabulary the record uses.
    # `dialect` is None only when the record states its decision in
    # neither, which is the state the old defaulted verdict lookup was
    # silently standing in for. (That lookup is described rather than
    # quoted: quoting it here tripped the composed gate's regex on a
    # COMMENT — §AD0(b), an instrument recognising a thing by the shape
    # of its implementation, and the fourth time my own prose has done
    # it this sprint.)
    dialect, verbatim = _pick_dialect(pick) if pick else (None, "")

    if register is None:
        stage = "harvest" if ledger else "brief"
    elif not (req / "contact_sheet.png").exists():
        stage = "candidates"
    elif pick is None:
        stage = "awaiting_pick"
    elif dialect is None:
        # §AN3(b). NOT a pass-through: a pick record that declares no
        # decision is its own state, and it is named. The default it
        # replaces returned "" and fell through to the stages below, so a
        # REJECTION recorded in a vocabulary this reader did not know
        # would have been indexed as accepted.
        stage = STAGE_PICK_UNDECLARED
    elif "REJECT" in verbatim.upper():
        stage = "rejected"
    elif not emissions:
        stage = "picked_awaiting_finalisation"
    elif all(e.get("owner_approved") for e in emissions):
        stage = "accepted"
    else:
        stage = "emitted_awaiting_acceptance"

    # §AN2 — an owner decision is never rendered with a blank where its
    # content belongs. The old shape defaulted `verdict` and
    # `verdict_verbatim` to "", so `es3083_lid_alt_01` displayed a real
    # signed §J(J1) citation beside two empty strings: the authority to
    # decide, and no decision. `_absent` says which field is missing
    # instead of pretending it is present and empty.
    decisions = []
    if pick:
        decisions.append({
            "record": "owner_pick_ingestion",
            "authority": _absent(pick, "authority"),
            # §AN3(c) — the dialect rides along. A divergence smoothed
            # over is a divergence that recurs; carried in the record, the
            # next reader sees two vocabularies instead of inferring one.
            "decision_dialect": dialect or PICK_DECISION_UNDECLARED,
            "verdict": verbatim or PICK_DECISION_UNDECLARED,
            "verdict_verbatim": _absent(pick, "verdict_verbatim")
            if dialect == "verdict_field" else _absent(pick, "pick_verbatim"),
            "date": _absent(pick, "ingested_on")})
    for e in emissions:
        acc = e.get("owner_acceptance") or (
            e.get("superseded_acceptance") or {}).get("acceptance_as_given")
        if acc:
            decisions.append({
                "record": "emission acceptance (%s)" % e["ai"],
                "authority": _absent(acc, "authority"),
                "decision_dialect": "acceptance_record",
                "verdict": "SUPERSEDED per §O — re-verification pending"
                if e.get("superseded_acceptance") and not
                e.get("owner_approved") else "ACCEPTED",
                "verdict_verbatim": _absent(acc, "verdict_verbatim"),
                "date": _absent(acc, "accepted_on")})

    # §AO — the summary's own fields, which are what the dashboard renders.
    # `"?"` was the house placeholder here, and `"?"` is a claim: it says
    # "there is a value and I could not read it". For a product name that
    # is merely unhelpful. For a MEASUREMENT TIER it is not — a tier is the
    # difference between MEASURED and PRIOR, the reserved-input boundary
    # §AE2(a) draws, and a brief entry with no tier rendered as `?`
    # alongside real MEASURED entries invites exactly the reading the
    # charter forbids. `_absent` names the missing field instead.
    measurements, m_defect = _list_field(
        brief, "physical_measurements", "brief.json")
    entries, l_defect = _list_field(
        ledger, "entries", "inspiration_ledger.json")
    cands, c_defect = _list_field(
        register, "candidates", "candidate_register.json")
    record_defects = [d for d in (m_defect, l_defect, c_defect) if d]
    return {
        "request_id": req.name,
        "product": _absent((brief or {}).get("product_identity") or {},
                           "name"),
        "stage": stage,
        "brief_measurement_tiers": sorted(
            {_absent(m, "tier") for m in measurements}),
        "ledger_entries": len(entries),
        # §AO — a malformed record used to be indistinguishable from an
        # empty one. `ledger_entries: 0` read as "the harvest found
        # nothing" (a finding about the WORK) when the truth was "the
        # ledger has no entries list" (a finding about the RECORD).
        "record_defects": record_defects,
        "candidates": [
            {"candidate_id": c.get("candidate_id"),
             "title": c.get("title"), "direction": c.get("direction"),
             "png": c.get("png")}
            for c in cands],
        "contact_sheet": (req / "contact_sheet.png").exists(),
        "emissions": [
            {"ai": e["ai"], "ai_sha256": e["ai_sha256"],
             "owner_approved": e.get("owner_approved"),
             "superseded": bool(e.get("superseded_acceptance"))}
            for e in emissions],
        "owner_decisions": decisions,
    }


def design_request_index(palt_h2_dir, emission_record_path):
    """The machine-readable run-tree index: every known request and its
    outcome, so dashboards and sessions stop re-deriving state from
    directory listings.

    §AO — ``emission_record_path`` may be None, meaning "do not consider
    emissions". It may NOT be a path that is not there. The old
    ``_load(...) or {}`` turned a missing emission record into an empty
    one, and an empty one into zero emissions for every request — which
    silently moves every accepted request back to
    ``picked_awaiting_finalisation``. A typo in a path would have quietly
    rewritten the outcome of the entire arc.
    """
    root = Path(palt_h2_dir)
    if emission_record_path is None:
        record = None
    elif not Path(emission_record_path).is_file():
        raise FileNotFoundError(
            "emission record %s is not on disk. Pass None to index without "
            "emissions; do not pass a path that is not there — every "
            "request would silently lose its emission stage."
            % emission_record_path)
    else:
        record = _load(emission_record_path)
    return {
        "record_type": "h2_design_request_index/1.0",
        "source_of_truth": "DERIVED read-only from the run trees + the "
                           "emission record — regenerate via "
                           "h2_design_request.design_request_index; owner "
                           "decisions land ONLY through the clearance "
                           "sheet",
        "requests": [request_summary(root / d, record)
                     for d in KNOWN_REQUEST_DIRS if (root / d).is_dir()],
    }


#: §AO — the serialisation of the committed index, in ONE place. There was
#: no writer: every session that regenerated the index hand-rolled the
#: `json.dumps` arguments, and this session's first attempt produced a
#: 29-line diff that was entirely `—` becoming `—`. Content and
#: formatting drift are different events and a reviewer should not have to
#: separate them by eye.
INDEX_SERIALISATION = {"indent": 1, "ensure_ascii": False}


def write_design_request_index(palt_h2_dir, emission_record_path):
    """Regenerate the committed index IN PLACE and return it.

    §R4(a) requires this to run in the same commit as any change to an
    index input. Use this rather than `json.dumps` at a call site, so the
    convention cannot drift again.
    """
    index = design_request_index(palt_h2_dir, emission_record_path)
    (Path(palt_h2_dir) / "design_request_index.json").write_text(
        json.dumps(index, **INDEX_SERIALISATION) + "\n", encoding="utf-8")
    return index
