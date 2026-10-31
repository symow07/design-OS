"""RBV-4 — structured visual review harness: authority, refusals, the
provenance separation between replayed and observed findings, and the REAL
committed P1_V4 package.

Synthetic dispositions here are ENGINEERING_REGRESSION_FIXTURES (§4). They
keep the harness honest and are never visual-quality evidence — the only
dispositions with any standing are the committed recorded fixture's, and
those are stamped RECORDED_FIXTURE wherever they appear.
"""
import hashlib
import json
import os
import unicodedata
from pathlib import Path

import pytest

from apps.pipeline.services import rbv4_claude_review as rv

REPO = Path(__file__).resolve().parents[3]
RBV = REPO / "docs" / "visual_quality" / "rbv"
REAL_PACKAGE = RBV / "review_packages" / "p1_v4"
REAL_FIXTURE = RBV / "review_fixtures" / "p1_v4_recorded_review.json"


def _dispositions(source, *, drop=None, mutate=None):
    """All 14 contract categories disposed NOT_OBSERVED, unless the test
    drops or mutates one."""
    out = []
    for cat in rv.required_categories():
        if cat == drop:
            continue
        entry = {"category": cat,
                 "disposition": rv.DISPOSITION_NOT_OBSERVED,
                 "source": source,
                 "observation": "synthetic regression fixture"}
        if mutate and cat == mutate[0]:
            entry.update(mutate[1])
        out.append(entry)
    return out


def _fixture_file(tmp_path, dispositions, **overrides):
    data = {"schema": rv.FIXTURE_SCHEMA, "subject_id": "SYNTHETIC",
            "recorded_at": "2026-08-17", "recorded_by": "regression fixture",
            "origin": "SYNTHETIC_ENGINEERING_FIXTURE — no inspection, no "
                      "provider call",
            "dispositions": dispositions}
    data.update(overrides)
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(data))
    return str(path)


def _stub_provider(dispositions, identity=None):
    def call(package):
        return {"provider_identity": identity if identity is not None else
                {"name": "stub-provider", "model": "regression-stub",
                 # required like name/model: a record stamped EXECUTED
                 # must carry the audit link back to its ledger row
                 "request_id": "req_011StubStubStubStub"},
                "dispositions": dispositions}
    return call


def _offline(tmp_path, dispositions=None, **kw):
    fixture = _fixture_file(
        tmp_path,
        _dispositions(rv.SOURCE_RECORDED_FIXTURE)
        if dispositions is None else dispositions)
    return rv.review_package(str(REAL_PACKAGE),
                             execution=rv.EXECUTION_OFFLINE_FIXTURE,
                             created_at="2026-08-17",
                             fixture_path=fixture, **kw)


def _deep_keys(node, out=None):
    out = [] if out is None else out
    if isinstance(node, dict):
        for k, v in node.items():
            out.append(str(k).lower())
            _deep_keys(v, out)
    elif isinstance(node, list):
        for item in node:
            _deep_keys(item, out)
    return out


class TestContractBinding:
    def test_contract_status_is_quoted_live_and_still_proposed(self,
                                                              tmp_path):
        record = _offline(tmp_path)
        assert record["contract"]["schema"] == rv.SCHEMA
        # the harness never upgrades the contract by citing it
        assert "PROPOSED" in record["contract"]["status"]
        assert record["contract"]["status"] == rv.contract()["status"]

    def test_required_categories_come_from_the_contract_not_a_copy(self):
        assert rv.required_categories() == tuple(
            rv.contract()["required_findings"])
        # non-vacuity: an empty obligation would make coverage trivially
        # satisfied, so the count is asserted non-zero here and refused
        # inside required_categories()
        assert len(rv.required_categories()) == 14
        assert rv.classifications() == ("BLOCKING", "MAJOR", "MINOR",
                                        "VISUAL_POLISH")


class TestSelfApprovalIsStructurallyAbsent:
    """The contract's binding rule: the review NEVER self-approves. Proven
    three ways — statically, by a FIRING scan, and on the real record."""

    def test_no_decision_key_is_written_anywhere_in_the_source(self):
        assert rv.self_approval_paths_in_source() == []

    def test_scan_fires_on_a_planted_decision_key(self):
        planted = {"schema": "x",
                   "dispositions": [{"category": "c", "verdict": "PASS"}]}
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv._scan_for_decision_keys(planted)
        assert exc.value.findings == [
            "RBV4_SELF_APPROVAL_FORBIDDEN:record.dispositions[0].verdict"]

    def test_scan_fires_on_a_top_level_approval(self):
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv._scan_for_decision_keys({"schema": "x", "approved": True})
        assert exc.value.findings == [
            "RBV4_SELF_APPROVAL_FORBIDDEN:record.approved"]

    def test_scan_is_not_vacuous_it_visits_every_key_at_every_depth(self):
        # exact count, not ">= 0": a scan that silently visited nothing
        # would return 0 and satisfy any loose assertion. Keys here are
        # a, b, b.c, d, d[0].e = 5.
        assert rv._scan_for_decision_keys(
            {"a": 1, "b": {"c": 2}, "d": [{"e": 3}]}) == 5

    def test_real_record_carries_no_decision_key_and_records_the_scan(
            self, tmp_path):
        record = _offline(tmp_path)
        keys = set(_deep_keys(record))
        assert not (keys & rv.FORBIDDEN_DECISION_KEYS)
        assert record["decision_key_scan"]["keys_visited"] > 50
        assert record["authority"]["decision_channel"] == rv.DECISION_CHANNEL

    def test_fixture_supplied_approval_never_reaches_the_record(self,
                                                                tmp_path):
        """Even a fixture that plants an approval cannot get one into the
        record: dispositions are rebuilt field-by-field from a whitelist,
        never copied through."""
        planted = _dispositions(
            rv.SOURCE_RECORDED_FIXTURE,
            mutate=("silhouette differences",
                    {"approved": True, "verdict": "PASS"}))
        record = _offline(tmp_path, dispositions=planted)
        assert not (set(_deep_keys(record)) & rv.FORBIDDEN_DECISION_KEYS)

    def test_authority_rules_are_carried_verbatim_from_the_contract(
            self, tmp_path):
        record = _offline(tmp_path)
        assert record["authority"]["rules"] == \
            rv.contract()["authority_rules"]
        assert any("must not self-approve" in r
                   for r in record["authority"]["rules"])
        assert any("OWNER remains final authority" in r
                   for r in record["authority"]["rules"])


def _budget_file(tmp_path, *, authorized=10, spent=0):
    calls = [{f: (1 if f.endswith("tokens") else "x")
              for f in rv.LEDGER_REQUIRED_FIELDS} for _ in range(spent)]
    path = tmp_path / "budget.json"
    path.write_text(json.dumps(
        {"schema": rv.BUDGET_SCHEMA, "authorized_calls": authorized,
         "authorized_by": "owner §R1", "rollover": False, "calls": calls}))
    return str(path)


class TestOwnerBudgetedLiveExecution:
    """§R1: 10 calls for build sprint 2, counted from the COMMITTED
    record. A budget a caller can hand itself authorizes nothing."""

    def test_committed_budget_is_the_ten_calls_the_owner_authorized(self):
        budget = rv.load_budget()
        assert budget["authorized_calls"] == 10
        assert "§R1" in budget["authorized_by"]
        assert budget["rollover"] is False
        assert len(budget["calls"]) <= 10

    def test_spend_is_counted_from_entries_never_asserted(self, tmp_path):
        state = rv.budget_state(_budget_file(tmp_path, spent=3))
        assert (state["calls_authorized"], state["spent"],
                state["remaining"]) == (10, 3, 7)
        # the key is deliberately NOT a bare `authorized` — that name is a
        # decision key and the scan refuses it on a review record
        assert "authorized" not in state
        assert state["state"] == rv.BUDGET_AVAILABLE

    def test_exhausted_budget_reports_exhausted(self, tmp_path):
        state = rv.budget_state(_budget_file(tmp_path, authorized=2, spent=2))
        assert state["state"] == rv.BUDGET_EXHAUSTED
        assert state["remaining"] == 0

    def test_absent_budget_record_is_the_pre_r1_state(self, tmp_path):
        state = rv.budget_state(str(tmp_path / "nope.json"))
        assert state["state"] == rv.BUDGET_RECORD_ABSENT
        assert state["live_state"] == rv.NOT_EXECUTED_PENDING_OWNER_BUDGET

    def test_pending_budget_is_unreachable_while_a_budget_exists(self):
        """A standing 'pending budget' claim against a granted budget is a
        stale claim — the exact shape this programme keeps catching."""
        assert rv.live_execution_state()["state"] != \
            rv.NOT_EXECUTED_PENDING_OWNER_BUDGET

    def test_live_without_a_budget_record_refuses(self, tmp_path):
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv.review_package(str(REAL_PACKAGE),
                              execution=rv.EXECUTION_LIVE_PROVIDER,
                              created_at="2026-08-17",
                              budget_path_override=str(tmp_path / "no.json"))
        assert exc.value.findings == [
            f"{rv.RBV4_BUDGET_NOT_AUTHORIZED}:"
            f"{rv.NOT_EXECUTED_PENDING_OWNER_BUDGET}"]

    def test_live_on_an_exhausted_budget_refuses(self, tmp_path):
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv.review_package(
                str(REAL_PACKAGE), execution=rv.EXECUTION_LIVE_PROVIDER,
                created_at="2026-08-17",
                budget_path_override=_budget_file(tmp_path, authorized=1,
                                                  spent=1),
                provider=_stub_provider(
                    _dispositions(rv.SOURCE_PROVIDER_CALL)))
        assert exc.value.findings[0].startswith(rv.RBV4_BUDGET_EXHAUSTED)

    def test_budgeted_but_providerless_refuses_rather_than_inventing(
            self, tmp_path):
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv.review_package(str(REAL_PACKAGE),
                              execution=rv.EXECUTION_LIVE_PROVIDER,
                              created_at="2026-08-17",
                              budget_path_override=_budget_file(tmp_path))
        assert exc.value.findings[0].startswith(rv.RBV4_PROVIDER_ABSENT)

    @pytest.mark.parametrize("identity", [
        {"name": "p", "model": "m"},                       # no request_id
        {"name": "p", "request_id": "req_x"},              # no model
        {"model": "m", "request_id": "req_x"},             # no name
    ])
    def test_every_identity_field_is_required_not_just_two(self, tmp_path,
                                                           identity):
        """§R4 judgment: request_id used to default to "" while name and
        model from the same dict were refused — a record could be stamped
        EXECUTED with a blank audit link back to its ledger row."""
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv.review_package(
                str(REAL_PACKAGE), execution=rv.EXECUTION_LIVE_PROVIDER,
                created_at="2026-08-17",
                budget_path_override=_budget_file(tmp_path),
                provider=_stub_provider(
                    _dispositions(rv.SOURCE_PROVIDER_CALL),
                    identity=identity))
        assert exc.value.findings[0].startswith(
            rv.RBV4_PROVIDER_IDENTITY_INCOMPLETE)

    def test_provider_without_identity_refuses(self, tmp_path):
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv.review_package(
                str(REAL_PACKAGE), execution=rv.EXECUTION_LIVE_PROVIDER,
                created_at="2026-08-17",
                budget_path_override=_budget_file(tmp_path),
                provider=_stub_provider(
                    _dispositions(rv.SOURCE_PROVIDER_CALL), identity={}))
        assert exc.value.findings[0].startswith(
            rv.RBV4_PROVIDER_IDENTITY_INCOMPLETE)

    def test_live_path_executes_and_records_provider_identity(self,
                                                              tmp_path):
        record = rv.review_package(
            str(REAL_PACKAGE), execution=rv.EXECUTION_LIVE_PROVIDER,
            created_at="2026-08-17",
            budget_path_override=_budget_file(tmp_path),
            provider=_stub_provider(_dispositions(rv.SOURCE_PROVIDER_CALL)))
        ex = record["execution"]
        assert ex["execution"] == rv.EXECUTION_LIVE_PROVIDER
        assert ex["provider_call_made"] is True
        assert ex["provider_identity"]["name"] == "stub-provider"
        assert len(ex["response_sha256"]) == 64
        assert all(d["source"] == rv.SOURCE_PROVIDER_CALL
                   for d in record["dispositions"])


def _real_row(**over):
    """A row that looks like an actual call — the tightened guard rejects
    placeholder rows, so tests must use realistic ones."""
    row = {"recorded_at": "2026-08-17T00:00:00+00:00",
           "package_id": "p1_v4", "model": "claude-opus-5",
           "provider_request_id": "req_011TestTestTestTestTest",
           "input_tokens": 1234, "output_tokens": 567,
           "cost_usd": "0.012345",
           # §V1(1): a real row names what it sent — an empty list means the
           # call transmitted nothing, which is not a review
           "image_transmitted": [{"role": "contact_sheet",
                                  "path": "docs/x/sheet.png",
                                  "pixel_hash": "d6a752cb655cc2d3"}]}
    row.update(over)
    return row


class TestTheFalsifiedRowsFourVerifiersACTUALLYRAN:
    """§V1 RE-FIX, NEGATIVE CONTROLS.

    Every row below was CONSTRUCTED AND RUN by an independent verifier
    against the first §V1 fix, ACCEPTED by validate_ledger_row, and — for
    several — appended by append_ledger_entry and counted by budget_state
    as one spent call from the owner's authorization of 10. They are
    transcribed here as the regression set rather than paraphrased,
    because the first fix passed a green suite while every one of these
    walked through it.

    A ledger row is the ONLY evidence a budgeted call happened. Each row
    below claims a call that did not happen.
    """

    def _refused(self, row):
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv.validate_ledger_row(row)
        return exc.value.findings

    def test_no_bare_string_flags_a_defect_any_more(self):
        """ROUND FIVE. Four versions tried to JUDGE free prose and three
        panels defeated them in turn: False, then "no defect", then "no
        defect" with a NO-BREAK SPACE, "no defects", "not a defect",
        "nothing to report" — and "UNKNOWN UNKNOWN", which defeats this
        module's own sentinel check by doubling it.

        The defect was STRUCTURAL: denial was an exact-match BLOCKLIST
        while acceptance was an open SHAPE test, so the accepted set was
        unbounded. Free text is no longer a flag at all.
        """
        for flag in (False, 0, 0.0, [], {}, [0], "", "   ", "\t\n",
                     "no defect", "no\u00a0defect", "no defect.",
                     "no defects", "No defect found", "not a defect",
                     "nothing to report", "no issue", "call was fine",
                     "UNKNOWN UNKNOWN", "N/A N/A", "false false", "ok ok",
                     "NONE", "UNKNOWN", "TBD", ".", "-", "x", "a b",
                     "\u3164 \u3164", "\u115f \u115f", "\u200b",
                     "IDENTITY_LOST_TO_AN_EXECUTOR_DEFECT",
                     "a genuine sounding explanation of a lost call"):
            row = _real_row(provider_request_id="UNKNOWN",
                            input_tokens="UNKNOWN", output_tokens="UNKNOWN",
                            cost_usd="UNKNOWN", image_transmitted="yes",
                            **{rv.LEDGER_DEFECT_FIELD: flag})
            findings = self._refused(row)
            assert any(rv.RBV4_LEDGER_DEFECT_UNEXPLAINED in f
                       for f in findings), (flag, findings)

    def test_the_acknowledgement_is_an_allowlist_of_one(self):
        """Acceptance requires writing LEDGER_DEFECT_ACK verbatim — a
        sentence that ASSERTS the defect, which no phrasing meaning the
        opposite can satisfy. Near misses are refused, so the set stays
        bounded by construction rather than by vocabulary."""
        for ack in ("", "no defect", rv.LEDGER_DEFECT_ACK.lower(),
                    rv.LEDGER_DEFECT_ACK + ".",
                    rv.LEDGER_DEFECT_ACK.replace(" ", "\u00a0"),
                    rv.LEDGER_DEFECT_ACK[:-1], True, 1, None):
            self._refused(_real_row(
                provider_request_id="UNKNOWN",
                **{rv.LEDGER_DEFECT_FIELD: {
                    rv.LEDGER_DEFECT_ACK_FIELD: ack,
                    rv.LEDGER_DEFECT_EXPLANATION_FIELD: "the call was lost"}}))

    def test_a_properly_acknowledged_defect_still_opens_the_hatch(self):
        """The hatch must still WORK — it is how a genuinely lost call is
        recorded honestly, and sealing it shut is also a defect."""
        assert rv.validate_ledger_row(_real_row(
            provider_request_id="UNKNOWN", input_tokens="UNKNOWN",
            output_tokens="UNKNOWN", cost_usd="UNKNOWN",
            **{rv.LEDGER_DEFECT_FIELD: {
                rv.LEDGER_DEFECT_ACK_FIELD: rv.LEDGER_DEFECT_ACK,
                rv.LEDGER_DEFECT_EXPLANATION_FIELD:
                    "the command parsed the response and dropped the id"}}))

    def test_the_explanation_may_be_written_in_any_script(self):
        """The previous version imposed a two-token floor, which was
        SCRIPT-DEPENDENT: it refused a correct Chinese or Japanese
        sentence outright because those scripts are not space-delimited,
        while this repository demonstrably authors ZH and AR material. A
        hatch that cannot be opened in the author's own language is a
        real defect, not a conservative default."""
        for text in ("网络中断，调用丢失", "接続失敗で応答を失いました",
                     "انقطع الاتصال", "timeout"):
            assert rv.validate_ledger_row(_real_row(
                provider_request_id="UNKNOWN",
                **{rv.LEDGER_DEFECT_FIELD: {
                    rv.LEDGER_DEFECT_ACK_FIELD: rv.LEDGER_DEFECT_ACK,
                    rv.LEDGER_DEFECT_EXPLANATION_FIELD: text}}))

    def test_an_explanation_of_pure_non_text_is_refused(self):
        """A panel enumerated all 0x110000 codepoints and found 2,162 that
        the previous hand-written list of eleven "invisible" characters
        missed — a BLOCKLIST, the exact shape torn out of the DEFECT flag,
        still standing in the helper the fix depended on. The test is now
        category-based and therefore closed by construction.
        """
        for text in ("", "   ", "\u200b", "\u00ad", "\u2062", "\u2061",
                     "\u206a", "\u034f", "\ufe0f", "\u17b4", "\ufff9",
                     "\u3000", "\x00", "\U000e0020", "\u200b\u00ad\u2062",
                     5, None, {}, []):
            self._refused(_real_row(
                provider_request_id="UNKNOWN",
                **{rv.LEDGER_DEFECT_FIELD: {
                    rv.LEDGER_DEFECT_ACK_FIELD: rv.LEDGER_DEFECT_ACK,
                    rv.LEDGER_DEFECT_EXPLANATION_FIELD: text}}))

    def test_what_the_text_rule_does_NOT_claim(self):
        """STATED, NOT PAPERED OVER. U+2800 BRAILLE PATTERN BLANK and
        U+3164 HANGUL FILLER are a Symbol and a Letter by Unicode
        category, and they are ACCEPTED. They render blank in most fonts
        — but "renders blank" is a property of the font, not of the
        string, and enumerating such characters would be another
        blocklist.

        They are in the same class as the explanation "x", which is also
        accepted: this module deliberately does not judge whether an
        explanation is MEANINGFUL, only that text is present. The
        protection is the acknowledgement, which is exact-match and
        asserts the defect. Asserted so it cannot drift unnoticed.
        """
        for text in ("\u2800", "\u3164", "x"):
            assert rv.validate_ledger_row(_real_row(
                provider_request_id="UNKNOWN",
                **{rv.LEDGER_DEFECT_FIELD: {
                    rv.LEDGER_DEFECT_ACK_FIELD: rv.LEDGER_DEFECT_ACK,
                    rv.LEDGER_DEFECT_EXPLANATION_FIELD: text}}))

    def test_the_legacy_flag_is_bound_to_ITS_ROW_not_to_its_text(self):
        """A panel pasted the committed legacy narrative into a NEW row —
        for a package that never existed, every identity field UNKNOWN —
        and it was ACCEPTED, skipping all four §V1 checks while asserting
        a specific historical failure that was not that row's provenance.
        The grandfather clause was pinned to the TEXT. A story anyone can
        retell is not evidence; it is now pinned to the whole ROW.
        """
        row0 = rv.load_budget()["calls"][0]
        assert rv.validate_ledger_row(row0)
        assert len(rv.LEDGER_DEFECT_LEGACY_ROW_SHA256) == 1
        # the same narrative, a different row
        self._refused(_real_row(
            package_id="a_package_that_never_existed",
            provider_request_id="UNKNOWN",
            **{rv.LEDGER_DEFECT_FIELD: row0[rv.LEDGER_DEFECT_FIELD]}))
        # the same row, one field altered
        tampered = dict(row0)
        tampered["package_id"] = "something_else"
        self._refused(tampered)

    def test_a_lone_surrogate_refuses_instead_of_crashing(self):
        """FILE-REACHABLE. json.loads('{"DEFECT": "\\ud800 lost"}') yields a
        legal Python str whose .encode("utf-8") raises. The previous
        version hashed the flag text directly, so the refusal path
        crashed on exactly the input it existed to refuse — the lesson
        _safe_repr's docstring records, recurring two lines above it."""
        row = json.loads('{"x": "\\ud800 lost"}')
        self._refused(_real_row(
            provider_request_id="UNKNOWN",
            **{rv.LEDGER_DEFECT_FIELD: row["x"]}))

    def test_a_role_is_bounded_BY_SHAPE_and_the_rest_is_queued(self):
        """role had NO shape rule, so it accepted invisible filler
        codepoints and the <FIELD_ABSENT> marker — which would make a
        present role indistinguishable from a missing one. Those are now
        refused, along with non-strings and the module's own sentinels.

        WHAT IS *NOT* CLAIMED, stated rather than papered over: role="yes"
        is still ACCEPTED. Bounding it further means checking the role
        against the view names the package actually declares, which is
        PROVENANCE binding — the queued owner item — and inventing a
        denylist of meaningless words is precisely the unbounded
        blocklist that had to be torn out of the DEFECT flag.
        """
        for role in (7, True, None, "\u200b", "\x00", "  ", "",
                     "UNKNOWN", "NONE", "UNKNOWN\u200b", "\uff35\uff2e"
                     "\uff2b\uff2e\uff2f\uff37\uff2e", "N/A\u200b",
                     rv.LEDGER_FIELD_ABSENT,
                     rv.LEDGER_FIELD_ABSENT + "\u200b"):
            self._refused(_real_row(image_transmitted=[
                {"role": role, "path": "docs/x/sheet.png",
                 "pixel_hash": "d6a752cb655cc2d3"}]))
        # the honest residual, asserted so it cannot drift unnoticed
        assert rv.validate_ledger_row(_real_row(image_transmitted=[
            {"role": "yes", "path": "docs/x/sheet.png",
             "pixel_hash": "d6a752cb655cc2d3"}]))

    def test_the_legacy_shape_checks_a_role_it_carries(self):
        """The legacy dict does not REQUIRE a role — there was one image
        to name — but a role it DOES carry is still a claim about what
        was sent, and an unchecked field is how the shape became the
        laxer door: role was never inspected there at all."""
        assert rv.validate_ledger_row(_real_row(image_transmitted={
            "path": "docs/x/sheet.png", "pixel_hash": "d6a752cb655cc2d3"}))
        for role in (7, True, "\u200b", rv.LEDGER_FIELD_ABSENT):
            self._refused(_real_row(image_transmitted={
                "role": role, "path": "docs/x/sheet.png",
                "pixel_hash": "d6a752cb655cc2d3"}))

    def test_true_is_not_a_path_and_not_a_hash(self):
        """RUN AND ACCEPTED. `true` passed as both a path and a pixel
        hash — the fix moved §V1(1)'s value hole one nesting level down
        rather than closing it."""
        self._refused(_real_row(image_transmitted=[
            {"role": True, "path": True, "pixel_hash": True}]))
        self._refused(_real_row(image_transmitted=[
            {"role": 1, "path": 1, "pixel_hash": 1}]))

    def test_the_word_yes_is_not_a_path_and_not_a_hash(self):
        """RUN AND ACCEPTED. Truthiness was the only test applied."""
        self._refused(_real_row(image_transmitted=[
            {"role": "yes", "path": "yes", "pixel_hash": "yes"}]))

    def test_a_container_is_not_a_path_and_not_a_hash(self):
        """RUN AND ACCEPTED."""
        self._refused(_real_row(image_transmitted=[
            {"role": {"a": 1}, "path": {"b": 2}, "pixel_hash": [3]}]))

    def test_the_legacy_shape_is_not_a_way_back_in(self):
        """RUN AND ACCEPTED. The legacy single-dict shape is real
        evidence and stays valid, but it is not a laxer door: its values
        answer to the same value class."""
        self._refused(_real_row(
            image_transmitted={"path": True, "pixel_hash": True}))
        self._refused(_real_row(
            image_transmitted={"path": "UNKNOWN.png",
                               "pixel_hash": "UNKNOWN0"}))

    def test_a_boolean_cost_is_not_a_cost(self):
        """RUN AND ACCEPTED, then APPENDED and counted as spent=1.
        str(False).upper() is not a sentinel and float(False) raises
        nothing, so the row bought a call for free."""
        self._refused(_real_row(cost_usd=False))

    def test_a_cost_that_is_not_a_number_is_not_a_cost(self):
        """RUN AND ACCEPTED. float("nan") and float("inf") both succeed,
        so the guard's numeric test admitted values that are not
        quantities."""
        for junk in ("nan", "inf", "-inf", float("nan"), float("inf")):
            self._refused(_real_row(cost_usd=junk))

    def test_a_negative_cost_is_not_a_cost(self):
        self._refused(_real_row(cost_usd="-1.0"))

    def test_an_enormous_cost_refuses_rather_than_crashing(self):
        """RUN. A huge integer cost — which json.load produces happily —
        raised OverflowError THROUGH the guard, turning a fail-closed
        refusal into an unhandled crash in the caller."""
        self._refused(_real_row(cost_usd=10 ** 400))

    def test_a_cost_the_ledger_cannot_STORE_is_refused(self):
        """RUN AND ACCEPTED, then it DESTROYED THE BUDGET FILE. Decimal,
        bytes, bytearray and Fraction all satisfy float() and passed the
        guard — then json.dump raised while writing, AFTER open(path,"w")
        had truncated the owner's authorization record, leaving it
        unparseable. A guard must not accept a value it does not
        constrain to something the ledger can store."""
        from decimal import Decimal
        from fractions import Fraction
        for junk in (Decimal("0.01"), b"0.01", bytearray(b"0.01"),
                     Fraction(1, 100)):
            self._refused(_real_row(cost_usd=junk))

    def test_the_refusal_path_does_not_itself_crash(self):
        """RUN. A >=4300-digit int — which json.load produces without
        complaint — makes repr() raise ValueError under CPython's
        integer-to-string limit, and the previous fix placed that repr()
        INSIDE the except handler, outside any try. The refusal path
        crashed on exactly the input it existed to refuse."""
        self._refused(_real_row(cost_usd=10 ** 5000))

    def test_a_conversion_that_raises_anything_else_is_still_refused(self):
        """The except tuple was closed, so a __float__ raising an
        unlisted exception escaped — and an escape here does not skip one
        check, it unwinds before the raise and destroys every finding
        already accumulated on the row.

        BaseException is deliberately NOT caught. Swallowing
        KeyboardInterrupt or SystemExit to harden a ledger guard is a
        worse defect than the one being fixed, and neither can arrive
        from a ledger file: json.load produces only str/int/float/bool/
        None/list/dict, so no object with a custom __float__ is reachable
        that way at all. This whole class is reachable through the API,
        not through the record.
        """
        class Hostile(float):
            def __float__(self):
                raise RecursionError("not a listed exception")
        self._refused(_real_row(cost_usd=Hostile(1.0)))

    def test_a_request_id_finding_never_coerces_the_type(self):
        """§U3 ON THE ONE FIELD IT WAS LEFT OFF. str() coercion made the
        integer 0 emit provider_request_id='0' — a value the row never
        carried, byte-identical to a row that really held the string."""
        as_int = self._refused(_real_row(provider_request_id=0))
        as_str = self._refused(_real_row(provider_request_id="0"))
        assert as_int != as_str, as_int

    def test_a_bare_prefix_is_not_a_request_id(self):
        """RUN AND ACCEPTED. Conformance was prefix-only, so the string
        "req_" satisfied it."""
        self._refused(_real_row(provider_request_id="req_"))

    def test_an_absent_subfield_never_reports_a_value_it_never_held(self):
        """§V1(2,3,4) ONE LEVEL DOWN. The helper written to FIX §V1(1)
        reproduced the very defect §V1(2,3,4) named: a record missing
        pixel_hash and a record carrying pixel_hash=None emitted
        BYTE-IDENTICAL findings, fabricating a value the row never held.
        Absent and present-null are different defects."""
        absent = self._refused(_real_row(image_transmitted=[
            {"role": "contact_sheet", "path": "docs/x/sheet.png"}]))
        null = self._refused(_real_row(image_transmitted=[
            {"role": "contact_sheet", "path": "docs/x/sheet.png",
             "pixel_hash": None}]))
        assert absent != null, (
            "absent and present-null collapsed into one finding again: "
            f"{absent}")
        assert any(rv.LEDGER_FIELD_ABSENT in f for f in absent), absent

    def test_no_finding_anywhere_fabricates_a_value_for_an_absent_field(self):
        """§U3/§V1 AT FUNCTION SCOPE. Three verifiers refuted the claim
        "no value is read for a field the row never carried" because the
        presence sweep read every required field through a defaulted get
        BEFORE the membership branches. The claim is now made true rather
        than narrowed: strip a field entirely and no finding may quote a
        value for it."""
        for field in ("provider_request_id", "input_tokens", "output_tokens",
                      "cost_usd", "image_transmitted"):
            row = _real_row()
            del row[field]
            for f in self._refused(row):
                if f.split(":", 1)[-1].startswith(field):
                    tail = f.split("=", 1)[1] if "=" in f else ""
                    assert tail in ("", rv.LEDGER_FIELD_ABSENT), (
                        f"finding fabricates a value for absent {field}: {f}")


class TestV2IsEnforcedNotIntended:
    """§V2 — ENFORCEMENT PRECEDES AUTHORIZATION.

    §V2 carries 6 unspent §R1 calls forward and makes them spendable only
    once §V1's fixes clear an independent pass, "and it is not a judgement
    call". Nothing in code knew that. budget_state reported
    BUDGET_AVAILABLE with 6 remaining and the live path gated on absent
    and exhausted budget only, so an injected provider would have spent
    one against the owner's committed authorization.

    §V2's own reasoning is the argument for closing it: "a budget policed
    by a check that will accept a falsified row is not a budget; it is a
    number in a file." A lock no code applies is that same object.
    """

    def test_live_against_the_committed_budget_refuses_while_locked(self):
        """THE ONE THAT MATTERS: the real committed path, a real provider
        argument, and no clearance recorded."""
        assert rv.V1_INDEPENDENT_CLEARANCE is None, (
            "a clearance is recorded in the source — if that was an owner "
            "act this test should assert the citation instead")
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv.review_package(str(REAL_PACKAGE),
                              execution=rv.EXECUTION_LIVE_PROVIDER,
                              created_at="2026-08-18",
                              provider=_stub_provider(
                                  _dispositions(rv.SOURCE_PROVIDER_CALL)))
        assert any(rv.RBV4_V1_CLEARANCE_ABSENT in f
                   for f in exc.value.findings), exc.value.findings

    def test_the_lock_is_checked_before_the_provider_is_called(self):
        """A gate that fires after the call has not saved the call. The
        provider must never be invoked while the lock stands."""
        called = []

        def _tripwire(package):
            called.append(package)
            raise AssertionError("provider was invoked under a §V2 lock")

        with pytest.raises(rv.Rbv4Refusal):
            rv.review_package(str(REAL_PACKAGE),
                              execution=rv.EXECUTION_LIVE_PROVIDER,
                              created_at="2026-08-18", provider=_tripwire)
        assert called == []

    def test_the_reported_live_state_says_locked_not_available(self):
        """A reader asking 'can a live call happen' was told
        BUDGET_AVAILABLE while the ruling forbade it."""
        state = rv.live_execution_state()
        assert state["state"] == rv.LIVE_LOCKED_PENDING_V1_CLEARANCE
        assert state["v1_clearance"] is None

    def test_the_owners_numbers_are_not_restated_by_the_lock(self):
        """A ruling is the NUMBER. §V2 carried 6 calls forward; they are
        authorized and real. Expressing a lock by zeroing them would be
        moving an owner's value to suit the code."""
        budget = rv.budget_state()
        assert budget["calls_authorized"] == 10
        assert budget["spent"] == len(rv.load_budget()["calls"])
        assert budget["remaining"] == 10 - budget["spent"]
        assert budget["state"] == rv.BUDGET_AVAILABLE

    def test_degrade_path_goes_offline_and_says_locked_not_exhausted(self):
        """§R1b's road, not a crash. The reason must be RECORDED and must
        not be confusable with exhaustion — 6 calls remain; they are
        simply not spendable."""
        record = rv.review_with_budget(
            str(REAL_PACKAGE), created_at="2026-08-18",
            fixture_path=str(REAL_FIXTURE),
            provider=_stub_provider(_dispositions(rv.SOURCE_RECORDED_FIXTURE)))
        ex = record["execution"]
        assert ex["execution"] == rv.EXECUTION_OFFLINE_FIXTURE
        assert "locked_from_live" in ex
        assert "degraded_from_live" not in ex
        assert "offline_by_request" not in ex
        assert "§V2" in ex["locked_from_live"]["rule"]
        assert all(d["source"] == rv.SOURCE_RECORDED_FIXTURE
                   for d in record["dispositions"])

    def test_pending_owner_budget_stays_unreachable(self):
        """The lock must not be confusable with the pre-§R1 state — a
        standing 'pending budget' claim against a granted budget is the
        stale-claim shape this programme keeps catching."""
        assert rv.LIVE_LOCKED_PENDING_V1_CLEARANCE != \
            rv.NOT_EXECUTED_PENDING_OWNER_BUDGET
        assert rv.live_execution_state()["state"] != \
            rv.NOT_EXECUTED_PENDING_OWNER_BUDGET


class TestRoundSevenPathProperties:
    """§V1 ROUND SEVEN — asserted as PATH PROPERTIES, not as the inputs
    that refuted round six.

    Round six stated two properties and applied each at some of its sites:
    "there is now ONE normalisation" (four text tests of five), and repr
    safety (one field of eight). Both statements were true of the code
    quoted and false of the module, and a panel walked through the gap in
    each. Testing the specific strings that got through would repeat the
    blocklist error one level up — the sprint's whole lesson — so these
    generate their space instead.
    """

    def _outcome(self, row):
        try:
            rv.validate_ledger_row(row)
            return "accepted"
        except rv.Rbv4Refusal:
            return "refused"

    def test_blank_after_canonical_is_refused_in_every_required_field(self):
        """PROPERTY: a value carrying no text, in ANY required field, is a
        missing value.

        The sweep tested `entry[f] == ""` — the empty string and nothing
        else — so one ASCII space satisfied recorded_at, package_id and
        model, the three fields no other check in this module reads.

        The blanks are DERIVED FROM THE MODULE'S OWN NORMALISATION rather
        than listed, so the test cannot fall behind the code: every
        codepoint _canonical discards is generated and tried. A hand-list
        here would be a blocklist wearing a test's hat.
        """
        discarded = [chr(cp) for cp in range(0x110000)
                     if unicodedata.category(chr(cp))
                     in rv.LEDGER_NON_CONTENT_CATEGORIES]
        blanks = [c for c in discarded if not rv._canonical(c)]
        assert len(blanks) > 900_000, "normalisation discards suspiciously few"
        # a sample plus every boundary-ish case, and pairs to catch
        # combination effects; the full cross product is ~11.7M rows and is
        # run in the sweep, not in the suite
        sample = blanks[::4001] + blanks[:40] + blanks[-40:]
        sample += ["".join(p) for p in zip(sample[::2], sample[1::2])]
        sample += ["", "  \t  ", "​ ﻿"]
        for field in rv.LEDGER_REQUIRED_FIELDS:
            for blank in sample:
                row = _real_row(**{field: blank})
                assert self._outcome(row) == "refused", (
                    f"{field}={ascii(blank)} accepted — a field carrying no "
                    "text satisfied a required field")

    def test_no_entry_value_can_escape_by_any_exit_but_refusal(self):
        """PROPERTY (TOTALITY): validate_ledger_row leaves by `return
        entry` or Rbv4Refusal. Nothing a row carries may raise through it.

        This is the module's oldest recurring fault: the refusal path
        CRASHING on exactly the input it exists to refuse, so the caller
        sees an error rather than a finding and the row is never recorded
        as rejected. It was fixed for cost_usd, then for one repr site,
        each time as an exception type rather than as a path property.
        Round six left six bare !r sites on entry-supplied values, and a
        >=4300-digit int — which CPython refuses to stringify at all —
        crashed four of them.

        Every hostile value is tried in EVERY required field, in an
        unknown extra field, and as the entry itself.
        """
        big = 10 ** 5000

        class Exploding:
            def __repr__(self):
                raise RuntimeError("repr detonated")

            def __str__(self):
                raise RuntimeError("str detonated")

        recursive = {}
        recursive["self"] = recursive
        deep = cur = {}
        for _ in range(20_000):
            cur["n"] = {}
            cur = cur["n"]

        hostile = [big, -big, [big], {"k": big}, Exploding(), [Exploding()],
                   recursive, deep, b"\xff\xfe", float("nan"), float("inf"),
                   {1, 2, 3}, len, None, True, [], {},
                   [{"role": Exploding(), "path": big,
                     "pixel_hash": recursive}]]

        for field in list(rv.LEDGER_REQUIRED_FIELDS) + ["surprise_field"]:
            for value in hostile:
                row = _real_row(**{field: value})
                # the assertion is that this does not RAISE anything other
                # than Rbv4Refusal; the verdict itself is not the property
                self._outcome(row)

        for value in hostile + ["a string", ["a list"], 7]:
            # a non-mapping indexes nowhere: every check below the entry
            # point raised TypeError straight out of the guard
            assert self._outcome(value) == "refused", (
                f"{type(value).__name__} entry was not refused")

    def test_the_committed_rows_still_validate(self):
        """A guard that cannot reproduce the record it guards has changed
        the record's meaning. Every committed row must still pass."""
        for i, call in enumerate(rv.load_budget()["calls"]):
            assert self._outcome(dict(call)) == "accepted", (
                f"committed row {i} no longer validates")


class TestALedgerCountsEventsNotRows:
    """§V1 ROUND SEVEN — REPLAY.

    Every §V1 round hardened what a row must LOOK like. None asked whether
    the call it records had already been recorded, so the committed rows
    were themselves a supply of spendable rows: appending
    `load_budget()["calls"][0]` appended it AGAIN as fresh spend — and
    that row is the grandfathered one, so it skipped all four §V1 checks
    on the way. Six replays would have consumed the owner's entire
    remaining authorization with no provider call at all.

    The module's own lesson, one step further along: pinning the DEFECT
    TEXT let the story be retold; pinning the ROW stopped that but let the
    EVENT be re-recorded.
    """

    def _budget_with(self, tmp_path, calls):
        tmp_path.mkdir(parents=True, exist_ok=True)
        path = tmp_path / "budget.json"
        path.write_text(json.dumps(
            {"schema": rv.BUDGET_SCHEMA, "authorized_calls": 10,
             "authorized_by": "owner §R1", "rollover": False,
             "calls": calls}))
        return str(path)

    def _lost_call(self, **over):
        row = _real_row(
            provider_request_id="IDENTITY_LOST_TO_AN_EXECUTOR_DEFECT",
            **{rv.LEDGER_DEFECT_FIELD: {
                rv.LEDGER_DEFECT_ACK_FIELD: rv.LEDGER_DEFECT_ACK,
                "explanation": "the executor crashed before the id landed"}})
        row.update(over)
        return row

    def test_any_committed_row_resubmitted_is_refused(self, tmp_path):
        """PROPERTY: a record already in the ledger is not a new call.
        Asserted over the REAL committed rows, each of which was a live
        replay vector."""
        committed = rv.load_budget()["calls"]
        for i, call in enumerate(committed):
            path = self._budget_with(tmp_path / f"r{i}", [dict(c)
                                                          for c in committed])
            with pytest.raises(rv.Rbv4Refusal) as exc:
                rv.append_ledger_entry(dict(call), path=path)
            assert any(rv.RBV4_LEDGER_ENTRY_REPLAYED in f
                       for f in exc.value.findings), (i, exc.value.findings)

    def test_a_real_request_id_names_exactly_one_call(self, tmp_path):
        """PROPERTY: reusing a committed request id is a replay or a
        fabrication either way. A row with a fresh timestamp, package,
        token counts and cost, reusing ONLY the id, validated clean and
        spent a call."""
        first = _real_row(provider_request_id="req_011RealLookingId0001")
        path = self._budget_with(tmp_path, [first])
        forged = _real_row(provider_request_id="req_011RealLookingId0001",
                           recorded_at="2026-08-18T10:00:00+00:00",
                           package_id="p9_v4", input_tokens=77,
                           output_tokens=5, cost_usd="1.25")
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv.append_ledger_entry(forged, path=path)
        assert any(rv.RBV4_LEDGER_ENTRY_REPLAYED in f
                   for f in exc.value.findings), exc.value.findings

    def test_a_genuine_new_call_is_still_admitted(self, tmp_path):
        """POSITIVE CONTROL. A guard that refuses everything is not a
        guard, and a budget that cannot be spent at all is not the ruling
        either — §V2 locks spending by AUTHORIZATION, not by breaking the
        ledger."""
        path = self._budget_with(tmp_path, [_real_row()])
        after = rv.append_ledger_entry(
            _real_row(provider_request_id="req_011NeverSeenBefore01",
                      recorded_at="2026-08-18T11:00:00+00:00"), path=path)
        assert len(after["calls"]) == 2

    def test_a_second_lost_call_is_admitted_but_not_twice(self, tmp_path):
        """The sentinel id is by construction not unique, so uniqueness
        cannot be asserted of it — the exemption is bounded by a check
        that already exists (§V1 refuses a sentinel id on any row not
        flagged DEFECT) rather than by a new list. The digest rule still
        requires a second lost call to differ from the first somewhere."""
        path = self._budget_with(tmp_path, [])
        rv.append_ledger_entry(self._lost_call(), path=path)
        rv.append_ledger_entry(
            self._lost_call(recorded_at="2026-08-18T12:00:00+00:00"),
            path=path)
        assert len(json.loads(Path(path).read_text())["calls"]) == 2
        with pytest.raises(rv.Rbv4Refusal):
            rv.append_ledger_entry(self._lost_call(), path=path)

    def test_the_grandfather_pin_still_does_not_survive_mutation(self,
                                                                 tmp_path):
        """ROUND FIVE, RE-ASSERTED. The replay rule must not have given
        the legacy row a second way in: change any field and the SHA-256
        pin is lost, so its legacy free-text flag is judged by the
        allowlist of one and refused."""
        legacy = dict(rv.load_budget()["calls"][0])
        legacy["recorded_at"] = "2026-08-18T12:00:00+00:00"
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv.validate_ledger_row(legacy)
        assert any(rv.RBV4_LEDGER_DEFECT_UNEXPLAINED in f
                   for f in exc.value.findings), exc.value.findings


class TestLedgerIsEnforcedNotIntended:
    """§R1a: an unledgered call is a defect."""

    def test_partial_entry_refuses_by_field(self, tmp_path):
        path = _budget_file(tmp_path)
        entry = _real_row()
        del entry["provider_request_id"]
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv.append_ledger_entry(entry, path)
        assert f"{rv.RBV4_LEDGER_ENTRY_INCOMPLETE}:provider_request_id" \
            in exc.value.findings

    def test_zero_output_tokens_is_a_value_not_a_missing_field(self,
                                                               tmp_path):
        path = _budget_file(tmp_path)
        entry = _real_row(output_tokens=0)
        assert len(rv.append_ledger_entry(entry, path)["calls"]) == 1

    def test_zero_input_tokens_is_not_a_real_call(self, tmp_path):
        """Every call that reached the provider consumed input tokens, so
        zero there means the row is not describing a real call."""
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv.validate_ledger_row(_real_row(input_tokens=0))
        assert any("input_tokens" in f for f in exc.value.findings)

    def test_append_past_the_authorization_refuses(self, tmp_path):
        path = _budget_file(tmp_path, authorized=1, spent=1)
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv.append_ledger_entry(_real_row(), path)
        assert exc.value.findings[0].startswith(rv.RBV4_BUDGET_EXHAUSTED)

    def test_committed_ledger_entries_are_complete(self):
        for call in rv.load_budget().get("calls") or []:
            for field in rv.LEDGER_REQUIRED_FIELDS:
                assert field in call, field

    def test_every_committed_row_passes_the_tightened_guard(self):
        """Presence was never enough. Each committed row must either look
        like a real call or admit it is a defect."""
        for call in rv.load_budget().get("calls") or []:
            rv.validate_ledger_row(call)

    def test_a_placeholder_request_id_is_refused_without_a_defect_flag(self):
        """NEGATIVE CONTROL for the weakness this guard was strengthened
        to close: a row whose fields are all PRESENT but whose identity is
        UNKNOWN used to pass."""
        entry = {f: 1 for f in rv.LEDGER_REQUIRED_FIELDS}
        entry.update({"provider_request_id": "UNKNOWN",
                      "cost_usd": "UNKNOWN", "input_tokens": 0,
                      "output_tokens": 0})
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv.validate_ledger_row(entry)
        codes = exc.value.findings
        assert any("provider_request_id" in c for c in codes)
        assert any("cost_usd" in c for c in codes)
        assert any("input_tokens" in c for c in codes)
        assert all(
            c.startswith(rv.RBV4_LEDGER_ENTRY_UNKNOWN_WITHOUT_DEFECT)
            or c.startswith(rv.RBV4_LEDGER_ENTRY_TRANSMISSION_INVALID)
            for c in codes)

    def test_the_same_row_is_accepted_once_it_admits_the_defect(self):
        """The hatch still works, now through the structured flag.

        NOTE, because a verifier fairly charged the previous version of
        this test with ENSHRINING a hole: it built {f: 1 for f in
        LEDGER_REQUIRED_FIELDS}, so a PASSING test asserted that
        image_transmitted=1 is acceptable on a DEFECT row. What a
        defect-flagged row may ASSERT is an owner policy question and is
        queued; this test no longer pretends to settle it, and uses a row
        whose transmission is real.
        """
        entry = _real_row(provider_request_id="UNKNOWN",
                          cost_usd="UNKNOWN", input_tokens=0,
                          output_tokens=0,
                          **{rv.LEDGER_DEFECT_FIELD: {
                              rv.LEDGER_DEFECT_ACK_FIELD: rv.LEDGER_DEFECT_ACK,
                              rv.LEDGER_DEFECT_EXPLANATION_FIELD:
                                  "call billed; identity lost before the "
                                  "ledger write"}})
        assert rv.validate_ledger_row(entry) is entry

    def test_an_empty_defect_flag_does_not_buy_the_exemption(self):
        entry = {f: 1 for f in rv.LEDGER_REQUIRED_FIELDS}
        entry.update({"provider_request_id": "UNKNOWN",
                      rv.LEDGER_DEFECT_FIELD: "   "})
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv.validate_ledger_row(entry)
        assert any(c.startswith(rv.RBV4_LEDGER_DEFECT_UNEXPLAINED)
                   for c in exc.value.findings)

    def test_an_absent_field_and_an_empty_one_are_distinguishable(self):
        """§U3 NEGATIVE CONTROL. These two rows used to produce
        byte-identical findings, so the refusal asserted
        provider_request_id='' about a row that never carried the field.
        They must now diverge."""
        absent = _real_row()
        del absent["provider_request_id"]
        empty = _real_row(provider_request_id="")

        with pytest.raises(rv.Rbv4Refusal) as a:
            rv.validate_ledger_row(absent)
        with pytest.raises(rv.Rbv4Refusal) as e:
            rv.validate_ledger_row(empty)

        assert a.value.findings != e.value.findings, (
            "an absent provider_request_id and an empty one still produce "
            "identical findings — the §U3 defect has returned")
        # and each says which case it is, rather than one borrowing the
        # other's description
        assert any(rv.LEDGER_FIELD_ABSENT in f for f in a.value.findings)
        assert not any(rv.LEDGER_FIELD_ABSENT in f for f in e.value.findings)
        assert any("provider_request_id=''" in f for f in e.value.findings)
        assert not any("provider_request_id=''" in f
                       for f in a.value.findings)

    def test_both_cases_are_still_refused(self):
        """Distinguishability must not have been bought by letting one of
        them through."""
        absent = _real_row()
        del absent["provider_request_id"]
        for row in (absent, _real_row(provider_request_id="")):
            with pytest.raises(rv.Rbv4Refusal):
                rv.validate_ledger_row(row)

    def test_a_real_looking_row_passes(self):
        entry = {"recorded_at": "2026-08-17T00:00:00+00:00",
                 "package_id": "p1_v4", "model": "claude-opus-5",
                 "provider_request_id": "req_011Ce7vK9W58YKue3dLAnZuj",
                 "input_tokens": 6471, "output_tokens": 4112,
                 "cost_usd": "0.135155",
                 "image_transmitted": [{"role": "contact_sheet",
                                        "path": "docs/x/sheet.png",
                                        "pixel_hash": "d6a752cb655cc2d3"}]}
        assert rv.validate_ledger_row(entry) is entry


class TestExhaustionDegradesHonestly:
    """§R1b: at exhaustion the harness continues offline and NEVER labels
    fixture output as live."""

    def test_exhausted_budget_degrades_to_a_fixture_sourced_record(
            self, tmp_path):
        record = rv.review_with_budget(
            str(REAL_PACKAGE), created_at="2026-08-17",
            fixture_path=str(REAL_FIXTURE),
            provider=_stub_provider(_dispositions(rv.SOURCE_PROVIDER_CALL)),
            budget_path_override=_budget_file(tmp_path, authorized=1,
                                              spent=1))
        ex = record["execution"]
        assert ex["execution"] == rv.EXECUTION_OFFLINE_FIXTURE
        assert ex["provider_call_made"] is False
        assert ex["degraded_from_live"]["budget_state"] == \
            rv.BUDGET_EXHAUSTED
        # an offline run that was NOT a degradation must not claim to be one
        assert "offline_by_request" not in ex
        # the decisive assertion: nothing in a degraded record is live
        assert all(d["source"] == rv.SOURCE_RECORDED_FIXTURE
                   for d in record["dispositions"])
        assert ex["state"] == "REPLAYED_FROM_RECORDED_FIXTURE"

    def test_an_exhausted_run_cannot_be_relabelled_executed(self, tmp_path):
        """Structural, not conventional: the source stamp is validated
        against the path that produced it, so provider-stamped findings
        cannot enter through the offline branch even if a caller tries."""
        with pytest.raises(rv.Rbv4Refusal) as exc:
            _offline(tmp_path,
                     dispositions=_dispositions(rv.SOURCE_PROVIDER_CALL))
        assert any(f.startswith(rv.RBV4_FINDING_SOURCE_MISMATCH)
                   for f in exc.value.findings)

    def test_available_budget_with_a_provider_runs_live(self, tmp_path):
        record = rv.review_with_budget(
            str(REAL_PACKAGE), created_at="2026-08-17",
            fixture_path=str(REAL_FIXTURE),
            provider=_stub_provider(_dispositions(rv.SOURCE_PROVIDER_CALL)),
            budget_path_override=_budget_file(tmp_path))
        assert record["execution"]["execution"] == rv.EXECUTION_LIVE_PROVIDER


class TestReplayedAndObservedNeverMix:
    """3aa applied to findings: a replayed disposition and an observed one
    are different evidence and must never share a shape."""

    def test_fixture_sourced_dispositions_are_rejected_on_the_live_path(
            self, tmp_path):
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv.review_package(
                str(REAL_PACKAGE), execution=rv.EXECUTION_LIVE_PROVIDER,
                created_at="2026-08-17",
                budget_path_override=_budget_file(tmp_path),
                provider=_stub_provider(
                    _dispositions(rv.SOURCE_RECORDED_FIXTURE)))
        codes = exc.value.findings
        # BOTH facts are refused, and both are true: each disposition is
        # mis-sourced, and rejecting it leaves its category undisposed —
        # a mis-sourced finding is never quietly counted as coverage
        assert sum(1 for f in codes
                   if f.startswith(rv.RBV4_FINDING_SOURCE_MISMATCH)) == 14
        assert sum(1 for f in codes
                   if f.startswith(rv.RBV4_CATEGORY_UNADDRESSED)) == 14

    def test_provider_sourced_dispositions_are_rejected_on_the_offline_path(
            self, tmp_path):
        with pytest.raises(rv.Rbv4Refusal) as exc:
            _offline(tmp_path,
                     dispositions=_dispositions(rv.SOURCE_PROVIDER_CALL))
        codes = exc.value.findings
        assert sum(1 for f in codes
                   if f.startswith(rv.RBV4_FINDING_SOURCE_MISMATCH)) == 14
        assert sum(1 for f in codes
                   if f.startswith(rv.RBV4_CATEGORY_UNADDRESSED)) == 14

    def test_offline_record_states_it_was_replayed_not_observed(
            self, tmp_path):
        ex = _offline(tmp_path)["execution"]
        assert ex["provider_call_made"] is False
        assert ex["state"] == "REPLAYED_FROM_RECORDED_FIXTURE"
        assert "REPLAYED, not observed" in ex["meaning"]
        assert len(ex["fixture"]["sha256"]) == 64
        assert ex["fixture"]["recorded_by"] and ex["fixture"]["origin"]

    def test_anonymous_fixture_refuses(self, tmp_path):
        for field in ("recorded_by", "origin", "recorded_at", "subject_id"):
            path = _fixture_file(
                tmp_path, _dispositions(rv.SOURCE_RECORDED_FIXTURE),
                **{field: ""})
            with pytest.raises(rv.Rbv4Refusal) as exc:
                rv.review_package(str(REAL_PACKAGE),
                                  execution=rv.EXECUTION_OFFLINE_FIXTURE,
                                  created_at="2026-08-17", fixture_path=path)
            assert exc.value.findings == [
                f"{rv.RBV4_FIXTURE_ORIGIN_INCOMPLETE}:{field}"]


class TestCoverageIsNeverVacuous:
    def test_an_undisposed_category_refuses_by_name(self, tmp_path):
        dropped = rv.required_categories()[3]
        with pytest.raises(rv.Rbv4Refusal) as exc:
            _offline(tmp_path,
                     dispositions=_dispositions(rv.SOURCE_RECORDED_FIXTURE,
                                                drop=dropped))
        assert exc.value.findings == [
            f"{rv.RBV4_CATEGORY_UNADDRESSED}:{dropped}"]

    def test_empty_dispositions_refuse_on_all_fourteen(self, tmp_path):
        # the coverage loop runs over the contract's fixed tuple, so it
        # cannot iterate zero times: an empty submission fails 14 times,
        # it does not pass silently
        with pytest.raises(rv.Rbv4Refusal) as exc:
            _offline(tmp_path, dispositions=[])
        assert len(exc.value.findings) == 14

    def test_unknown_category_refuses(self, tmp_path):
        extra = _dispositions(rv.SOURCE_RECORDED_FIXTURE)
        extra.append({"category": "vibes", "disposition": "NOT_OBSERVED",
                      "source": rv.SOURCE_RECORDED_FIXTURE})
        with pytest.raises(rv.Rbv4Refusal) as exc:
            _offline(tmp_path, dispositions=extra)
        assert exc.value.findings == [f"{rv.RBV4_CATEGORY_UNKNOWN}:vibes"]

    def test_finding_outside_the_contract_classification_refuses(
            self, tmp_path):
        cat = rv.required_categories()[0]
        with pytest.raises(rv.Rbv4Refusal) as exc:
            _offline(tmp_path, dispositions=_dispositions(
                rv.SOURCE_RECORDED_FIXTURE,
                mutate=(cat, {"disposition": rv.DISPOSITION_FINDING,
                              "classification": "CRITICAL"})))
        assert f"{rv.RBV4_CLASSIFICATION_INVALID}:{cat}:CRITICAL" in \
            exc.value.findings

    def test_uncertainty_must_name_what_is_missing(self, tmp_path):
        """The contract forbids resolving missing-evidence uncertainty by
        assumption; an unnamed gap is exactly that."""
        cat = rv.required_categories()[0]
        with pytest.raises(rv.Rbv4Refusal) as exc:
            _offline(tmp_path, dispositions=_dispositions(
                rv.SOURCE_RECORDED_FIXTURE,
                mutate=(cat, {"disposition":
                              rv.DISPOSITION_UNCERTAIN_MISSING_EVIDENCE})))
        assert f"{rv.RBV4_UNCERTAINTY_RESOLVED_BY_ASSUMPTION}:{cat}" in \
            exc.value.findings

    def test_invalid_disposition_refuses(self, tmp_path):
        cat = rv.required_categories()[0]
        with pytest.raises(rv.Rbv4Refusal) as exc:
            _offline(tmp_path, dispositions=_dispositions(
                rv.SOURCE_RECORDED_FIXTURE,
                mutate=(cat, {"disposition": "FINE"})))
        assert f"{rv.RBV4_DISPOSITION_INVALID}:{cat}:FINE" in \
            exc.value.findings


class TestPackageIntegrityIsReProved:
    def test_missing_manifest_refuses(self, tmp_path):
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv.load_review_package(str(tmp_path))
        assert exc.value.findings[0].startswith(
            rv.RBV4_PACKAGE_MANIFEST_MISSING)

    def test_schema_mismatch_refuses(self, tmp_path):
        (tmp_path / "review_package_manifest.json").write_text(
            json.dumps({"schema": "something_else/1.0"}))
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv.load_review_package(str(tmp_path))
        assert exc.value.findings == [
            f"{rv.RBV4_PACKAGE_SCHEMA_MISMATCH}:something_else/1.0"]

    def test_tampered_view_hash_refuses(self, tmp_path):
        manifest = json.loads(
            (REAL_PACKAGE / "review_package_manifest.json").read_text())
        manifest["modes"]["GEOMETRY_VALIDATION"]["views"]["front"][
            "pixel_hash"] = "0" * 16
        (tmp_path / "review_package_manifest.json").write_text(
            json.dumps(manifest))
        os.link(REAL_PACKAGE / "review_contact_sheet.png",
                tmp_path / "review_contact_sheet.png")
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv.load_review_package(str(tmp_path))
        assert any(f.startswith(f"{rv.RBV4_VIEW_HASH_MISMATCH}:front")
                   for f in exc.value.findings)

    def test_tampered_contact_sheet_hash_refuses(self, tmp_path):
        manifest = json.loads(
            (REAL_PACKAGE / "review_package_manifest.json").read_text())
        manifest["contact_sheet"]["pixel_hash"] = "0" * 16
        (tmp_path / "review_package_manifest.json").write_text(
            json.dumps(manifest))
        os.link(REAL_PACKAGE / "review_contact_sheet.png",
                tmp_path / "review_contact_sheet.png")
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv.load_review_package(str(tmp_path))
        assert any(f.startswith(rv.RBV4_CONTACT_SHEET_HASH_MISMATCH)
                   for f in exc.value.findings)

    def test_a_manifest_with_no_views_refuses_instead_of_loading_empty(
            self, tmp_path):
        """§R4 judgment: `manifest.get("modes", {})` let a manifest with
        no modes / no mode A / no views load SUCCESSFULLY with zero views
        — the loop simply never ran, so nothing was found to complain
        about. A package with nothing in it is refused."""
        manifest = json.loads(
            (REAL_PACKAGE / "review_package_manifest.json").read_text())
        manifest["modes"]["GEOMETRY_VALIDATION"]["views"] = {}
        (tmp_path / "review_package_manifest.json").write_text(
            json.dumps(manifest))
        os.link(REAL_PACKAGE / "review_contact_sheet.png",
                tmp_path / "review_contact_sheet.png")
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv.load_review_package(str(tmp_path))
        assert any("views is empty" in f for f in exc.value.findings)

    def test_a_manifest_with_no_modes_refuses(self, tmp_path):
        manifest = json.loads(
            (REAL_PACKAGE / "review_package_manifest.json").read_text())
        del manifest["modes"]
        (tmp_path / "review_package_manifest.json").write_text(
            json.dumps(manifest))
        os.link(REAL_PACKAGE / "review_contact_sheet.png",
                tmp_path / "review_contact_sheet.png")
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv.load_review_package(str(tmp_path))
        assert exc.value.findings[0].startswith(rv.RBV4_MODE_ABSENT)

    def test_a_budget_without_its_authority_refuses(self, tmp_path):
        """§R4 judgment: authorizing_ruling is persisted into every live
        record; blank it reads as 'spend authorized by nobody'."""
        path = tmp_path / "b.json"
        path.write_text(json.dumps(
            {"schema": rv.BUDGET_SCHEMA, "authorized_calls": 10,
             "calls": []}))
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv.load_budget(str(path))
        assert exc.value.findings == [
            f"{rv.RBV4_BUDGET_SCHEMA_MISMATCH}:authorized_by"]

    def test_missing_contact_sheet_refuses(self, tmp_path):
        (tmp_path / "review_package_manifest.json").write_text(
            (REAL_PACKAGE / "review_package_manifest.json").read_text())
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv.load_review_package(str(tmp_path))
        assert any(f.startswith(rv.RBV4_CONTACT_SHEET_MISSING)
                   for f in exc.value.findings)

    def test_invalid_execution_refuses(self):
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv.review_package(str(REAL_PACKAGE), execution="VIBES",
                              created_at="2026-08-17")
        assert exc.value.findings == [f"{rv.RBV4_EXECUTION_INVALID}:VIBES"]

    def test_offline_without_a_fixture_refuses(self):
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv.review_package(str(REAL_PACKAGE),
                              execution=rv.EXECUTION_OFFLINE_FIXTURE,
                              created_at="2026-08-17")
        assert exc.value.findings[0].startswith(rv.RBV4_FIXTURE_MISSING)


class TestTwoModePrincipleHolds:
    def test_reviewing_the_absent_presentation_mode_refuses_with_reasons(
            self, tmp_path):
        fixture = _fixture_file(
            tmp_path, _dispositions(rv.SOURCE_RECORDED_FIXTURE))
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv.review_package(str(REAL_PACKAGE),
                              execution=rv.EXECUTION_OFFLINE_FIXTURE,
                              created_at="2026-08-17", fixture_path=fixture,
                              mode="CLIENT_PRESENTATION")
        finding = exc.value.findings[0]
        assert finding.startswith(f"{rv.RBV4_MODE_ABSENT}:CLIENT_PRESENTATION")
        assert "RBV2C_PRESENTATION_RENDERER_NOT_BUILT" in finding
        assert "OWNER_GATE_PILOT_GEOMETRY_INSPECTION_PENDING" in finding

    def test_record_carries_mode_b_absence_forward(self, tmp_path):
        record = _offline(tmp_path)
        assert record["mode_reviewed"] == "GEOMETRY_VALIDATION"
        assert record["presentation_mode"]["status"] == "ABSENT_BLOCKED"
        assert "NOT A REAL BOTTLE COMPARISON" in record["statement"]


class TestProvenance:
    def test_record_names_every_input_and_the_derivation(self, tmp_path):
        prov = _offline(tmp_path)["provenance"]
        roles = [i["role"] for i in prov["inputs_read_in_order"]]
        assert roles[0] == "review_package_manifest"
        assert roles[1] == "contact_sheet"
        assert "review_contract" in roles
        assert "recorded_review_fixture" in roles
        assert sum(1 for r in roles if r.startswith("view:")) == 8
        for entry in prov["inputs_read_in_order"]:
            assert entry["path"] and (entry.get("sha256")
                                      or entry.get("pixel_hash"))
        assert len(prov["derivation"]["code_sha256"]) == 64
        assert prov["derivation"]["module"].endswith(
            "rbv4_claude_review.py")
        assert prov["law"].startswith("3aa")

    def test_provenance_guard_fires_when_identity_is_stripped(self):
        record = {"provenance": {"inputs_read_in_order":
                                 [{"role": "view:front", "path": "x"}],
                                 "derivation": {}},
                  "execution": {"execution": rv.EXECUTION_OFFLINE_FIXTURE,
                                "fixture": {}},
                  "dispositions": [{"category": "c", "source": "GUESSED"}]}
        with pytest.raises(rv.Rbv4Refusal) as exc:
            rv._assert_provenance_complete(record)
        codes = exc.value.findings
        assert f"{rv.RBV4_PROVENANCE_INCOMPLETE}:input-identity:view:front" \
            in codes
        assert f"{rv.RBV4_PROVENANCE_INCOMPLETE}:derivation.code_sha256" \
            in codes
        assert f"{rv.RBV4_PROVENANCE_INCOMPLETE}:execution.fixture.sha256" \
            in codes
        assert f"{rv.RBV4_PROVENANCE_INCOMPLETE}:disposition-source:c" in codes

    def test_same_inputs_same_record(self, tmp_path):
        assert _offline(tmp_path) == _offline(tmp_path)

    def test_record_is_written_when_out_dir_given(self, tmp_path):
        out = tmp_path / "out"
        record = _offline(tmp_path, out_dir=str(out))
        written = json.loads((out / rv.RECORD_NAME).read_text())
        assert written == record

    def test_no_provider_or_orm_imports(self):
        src = (REPO / "apps" / "pipeline" / "services" /
               "rbv4_claude_review.py").read_text()
        for banned in ("import requests", "import anthropic", "import openai",
                       "from django.db", "models.", "urllib.request"):
            assert banned not in src, banned


class TestTrackerClaimHonesty:
    """The node may not claim an execution the engine reports did not
    happen. Same shape as RBV-3's guard, and for the same reason: a leaf
    node's percentage propagates straight into the program rollups, and
    nothing else catches inflation at the leaf."""

    def _node(self):
        from apps.pipeline.management.commands.roadmap_status import (
            load_tracker)
        return {n["id"]: n for n in load_tracker()["nodes"]}[
            "quality.rbv4_claude_review"]

    def test_node_does_not_claim_live_execution_while_it_is_unexecuted(self):
        node = self._node()
        if rv.live_execution_state()["state"] == \
                rv.NOT_EXECUTED_PENDING_OWNER_BUDGET:
            assert rv.NOT_EXECUTED_PENDING_OWNER_BUDGET in node["scope"], (
                "live execution is NOT_EXECUTED in the engine — the tracker "
                "node must say so, not imply the review ran")
            assert "NOT_EXECUTED" in node["title"]

    def test_node_claims_no_visual_quality(self):
        # the no-inflation rule: visual quality moves only on owner review
        # of real pilot output, never on a harness landing
        assert (self._node()["visual_quality_percent"] or 0) == 0


class TestTheCommittedRecordedFixture:
    """The fixture is real evidence about the real package — it is checked
    against the package, not merely parsed."""

    def test_committed_fixture_loads_and_declares_its_origin(self):
        fixture = rv.load_fixture(str(REAL_FIXTURE))
        assert fixture["subject_id"] == "P1_V4"
        assert "NO PROVIDER API CALL WAS MADE" in fixture["origin"]

    def test_committed_fixture_reviews_the_real_committed_package(self):
        record = rv.review_package(
            str(REAL_PACKAGE), execution=rv.EXECUTION_OFFLINE_FIXTURE,
            created_at="2026-08-17", fixture_path=str(REAL_FIXTURE))
        assert record["subject_id"] == "P1_V4"
        assert len(record["dispositions"]) == 14
        assert record["counts_by_classification"] == {
            "BLOCKING": 0, "MAJOR": 2, "MINOR": 2, "VISUAL_POLISH": 0}

    def test_the_four_reference_dependent_categories_stay_uncertain(self):
        record = rv.review_package(
            str(REAL_PACKAGE), execution=rv.EXECUTION_OFFLINE_FIXTURE,
            created_at="2026-08-17", fixture_path=str(REAL_FIXTURE))
        by_cat = {d["category"]: d for d in record["dispositions"]}
        for cat in ("silhouette differences", "shoulder differences",
                    "neck differences", "closure differences"):
            assert by_cat[cat]["disposition"] == \
                rv.DISPOSITION_UNCERTAIN_MISSING_EVIDENCE, cat
            # never resolved by assumption — the gap is named
            assert by_cat[cat]["missing_evidence"], cat

    def test_committed_record_equals_fresh_regeneration(self):
        """A committed derived artifact that drifts from its inputs is a
        stale claim wearing an evidence badge. Regenerating from the same
        committed package + fixture must reproduce it byte-for-byte, so a
        stale record is a visible suite failure by design."""
        committed = json.loads(
            (RBV / "review_records" / "p1_v4" /
             rv.RECORD_NAME).read_text())
        if committed["execution"]["execution"] != rv.EXECUTION_OFFLINE_FIXTURE:
            # a LIVE record cannot be regenerated without spending another
            # owner-authorized call; its integrity is pinned by the ledger
            # entry and response digest instead
            pytest.skip("committed record is a live provider record")
        # regenerated the way the command produced it — review_with_budget,
        # no provider — so the offline-reason block is reproduced too
        fresh = rv.review_with_budget(
            str(REAL_PACKAGE), created_at=committed["created_at"],
            fixture_path=str(REAL_FIXTURE), note=committed["note"])
        assert fresh == committed

    def test_a_live_committed_record_names_a_ledgered_call(self):
        """A live record cannot be regenerated (that would spend another
        owner-authorized call), so its integrity guard is the audit link
        instead: the call it reports must appear in the committed ledger."""
        committed = json.loads(
            (RBV / "review_records" / "p1_v4" /
             rv.RECORD_NAME).read_text())
        ex = committed["execution"]
        if ex["execution"] != rv.EXECUTION_LIVE_PROVIDER:
            pytest.skip("committed record is an offline replay")
        request_id = ex["provider_request_id"]
        assert request_id, "a live record must name its provider request"
        ledgered = {c["provider_request_id"]
                    for c in rv.load_budget()["calls"]}
        assert request_id in ledgered, (
            "the committed live record reports a call that is not in the "
            "budget ledger — §R1a")
        assert len(ex["response_sha256"]) == 64

    def test_committed_record_describes_the_package_as_it_stands_now(self):
        """A live record cannot be regenerated for free, which makes it
        exactly the kind of artifact that goes stale unnoticed when the
        package underneath it is rebuilt. §S2 rebuilt the sheet; this
        fails if a committed record still cites the old digests."""
        committed = json.loads(
            (RBV / "review_records" / "p1_v4" /
             rv.RECORD_NAME).read_text())
        current = json.loads(
            (REAL_PACKAGE / "review_package_manifest.json").read_text())
        by_role = {i["role"]: i
                   for i in committed["provenance"]["inputs_read_in_order"]}
        assert by_role["contact_sheet"]["pixel_hash"] == \
            current["contact_sheet"]["pixel_hash"], (
                "the committed review record was taken against a different "
                "contact sheet than the one committed now — regenerate the "
                "record (it costs one owner-authorized call) or explain")
        fresh_manifest_sha = hashlib.sha256(
            (REAL_PACKAGE / "review_package_manifest.json").read_bytes()
        ).hexdigest()
        assert by_role["review_package_manifest"]["sha256"] == \
            fresh_manifest_sha

    def test_committed_record_states_no_provider_call_was_made(self):
        committed = json.loads(
            (RBV / "review_records" / "p1_v4" /
             rv.RECORD_NAME).read_text())
        ex = committed["execution"]
        if ex["execution"] == rv.EXECUTION_OFFLINE_FIXTURE:
            assert ex["provider_call_made"] is False
            assert "no provider call was made" in committed["note"]
        else:
            # a live record must name the provider it actually called
            assert ex["provider_call_made"] is True
            assert ex["provider_identity"]["name"]
        assert not (set(_deep_keys(committed))
                    & rv.FORBIDDEN_DECISION_KEYS)

    def test_client_presentability_is_never_judged_from_mode_a(self):
        record = rv.review_package(
            str(REAL_PACKAGE), execution=rv.EXECUTION_OFFLINE_FIXTURE,
            created_at="2026-08-17", fixture_path=str(REAL_FIXTURE))
        by_cat = {d["category"]: d for d in record["dispositions"]}
        pres = by_cat["client-presentability"]
        assert pres["disposition"] == rv.DISPOSITION_NOT_OBSERVED
        assert "NOT ASSESSABLE" in pres["observation"]
