"""1g — the degenerate-statistic guard and its structural enforcement.

Owner ruling A1 (M6_DRIVER_COMPLETENESS_PROMPT.md): the third instance
of DEGENERATE_INPUT_PLAUSIBLE_OUTPUT gets a structural guard, not a
fix. These tests are the structure: the guard refuses, and the source
scan makes an unguarded rank correlation in the services tree a test
failure rather than a code-review hope.
"""
import collections
import importlib.util
import json
import pathlib
import re

from django.test import SimpleTestCase

from apps.pipeline.services import palette_statistics as ST

SERVICES = pathlib.Path(__file__).resolve().parents[1] / "services"
_ROOT = pathlib.Path(__file__).resolve().parents[3]

#: A182/3c — the census lives in tools/ (outside the scanned tree) and
#: is shared by this gate and the disposition tool, so neither can
#: drift from the other. The baseline is DATA, and
#: tools/allowlist_disposition.py is its only writer: there is no
#: refresh operation, only supersession with a stated reason.
_spec = importlib.util.spec_from_file_location(
    "allowlist_census", _ROOT / "tools" / "allowlist_census.py")
CENSUS = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(CENSUS)

MEASUREMENT_MODULES = CENSUS.MEASUREMENT_MODULES
_BASELINE = json.loads(CENSUS.BASELINE.read_text())
A32_MEASUREMENT_DEFAULTS = _BASELINE["a32"]
KNOWN_FALLBACKS = _BASELINE["fallbacks"]


class GuardBehaviourTests(SimpleTestCase):
    def test_constant_vector_raises_not_a_number(self):
        """The committed SHADOW|GRANULARITY 1.0 came from exactly this
        input shape — twelve identical readings."""
        with self.assertRaises(ST.DegenerateStatisticError):
            ST.guarded_spearman([0.089844] * 12, list(range(12)))

    def test_constant_on_either_side_raises(self):
        with self.assertRaises(ST.DegenerateStatisticError):
            ST.guarded_spearman(list(range(12)), [5.0] * 12)

    def test_too_few_points_raise(self):
        with self.assertRaises(ST.DegenerateStatisticError):
            ST.guarded_spearman([1.0, 2.0], [2.0, 1.0])

    def test_non_degenerate_input_is_unchanged_behaviour(self):
        self.assertAlmostEqual(
            ST.guarded_spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
        self.assertAlmostEqual(
            ST.guarded_spearman([1, 2, 3, 4], [40, 30, 20, 10]), -1.0)

    def test_the_defect_class_is_registered_with_its_instances(self):
        self.assertEqual(ST.DEFECT_CLASS,
                         "DEGENERATE_INPUT_PLAUSIBLE_OUTPUT")
        self.assertEqual(len(ST.DEFECT_INSTANCES), 3)


class SourceScanTests(SimpleTestCase):
    """No rank correlation may exist outside the guard."""

    RANK_PATTERN = re.compile(r"argsort\(np\.argsort|scipy\.stats"
                              r"|spearmanr")

    FALLBACK_SHAPES = re.compile(
        r"except\s*:"                      # bare except
        r"|except [A-Za-z]+\s*:\s*pass"    # swallow-and-continue
        r"|else 0\.0\b"                    # the raking-rig shape
        r"|else 1\.0\b")

    # A182 — the gate and the disposition tool share ONE census
    # (tools/allowlist_census.py), so the thing that fails the suite
    # and the thing that writes the baseline cannot disagree.
    symbol_of = staticmethod(CENSUS.symbol_of)
    key_of = staticmethod(CENSUS.key_of)
    census = staticmethod(CENSUS.census)

    @staticmethod
    def _diff(found, known):
        return [f"{k} (found {v['found']}, allowed {v['allowed']})"
                for k, v in sorted(CENSUS.diff(found, known).items())
                if v["found"] > v["allowed"]]

    def test_no_silent_plausible_fallback_shapes(self):
        """1q — SILENT_PLAUSIBLE_FALLBACK: an operation that, given
        malformed input, silently produces a plausible in-range result
        instead of raising. Scope: every measurement path. Allowlist:
        declared refusal-recording (writes an INSTRUMENT_REFUSED/
        STIMULUS_NOT_REALIZED record) is a refusal, not a fallback.
        A179: keys are line-independent and carry counts."""
        offenders = self._diff(
            self.census(self.FALLBACK_SHAPES, skip_refusals=True),
            KNOWN_FALLBACKS)
        self.assertEqual(offenders, [],
                         f"silent-fallback shapes: {offenders}")

    A32_SHAPES = re.compile(r"\.get\([^)]+,\s*[^)]+\)"
                            r"|getattr\([^)]+,[^)]+,[^)]+\)")

    def test_a32_extended_shapes_in_measurement_code(self):
        """1q scope check: the four original shapes missed
        lookup-with-default. Counted and located, not dispositioned —
        this test fails the suite on NEW occurrences only. A179: keys
        are line-independent and carry counts."""
        offenders = self._diff(
            self.census(self.A32_SHAPES, only=set(MEASUREMENT_MODULES)),
            A32_MEASUREMENT_DEFAULTS)
        self.assertEqual(offenders, [],
                         f"new lookup-default sites: {offenders}")

    def test_no_allowlist_key_is_line_positional(self):
        """A179 — the structural guard on the rekey itself: a key that
        embeds a line number reintroduces the defect that has now been
        paid for four times."""
        positional = re.compile(r"\.py:\d+|::\d+$|^\d+$")
        offenders = [k for k in
                     list(KNOWN_FALLBACKS) + list(A32_MEASUREMENT_DEFAULTS)
                     if positional.search(k)]
        self.assertEqual(offenders, [],
                         f"line-positional allowlist keys: {offenders}")

    def test_keys_survive_line_movement_demonstrated(self):
        """A179 — not asserted, DEMONSTRATED: inserting blank lines at
        the top of a scanned source moves every line number and must
        move no key."""
        import tempfile
        src = ("def outer(cfg):\n"
               "    v = cfg.get('k', 1.6)\n"
               "    return v\n")
        shifted = "\n\n\n\n\n" + src
        with tempfile.TemporaryDirectory() as td:
            a = pathlib.Path(td) / "m.py"
            a.write_text(src)
            k1 = self.key_of("m.py", src, src.index(".get"),
                             ".get('k', 1.6)")
            k2 = self.key_of("m.py", shifted, shifted.index(".get"),
                             ".get('k', 1.6)")
        self.assertEqual(k1, k2)
        self.assertNotIn(":2", k1)
        self.assertIn("outer", k1)

    def test_every_rank_correlation_goes_through_the_guard(self):
        offenders = []
        for path in SERVICES.rglob("*.py"):
            if path.name == "palette_statistics.py":
                continue
            text = path.read_text()
            if self.RANK_PATTERN.search(text):
                offenders.append(path.name)
            # a local spearman def must delegate to the guard
            for m in re.finditer(r"def spearman\(", text):
                tail = text[m.start():m.start() + 600]
                if "guarded_spearman" not in tail:
                    offenders.append(f"{path.name} (unguarded def)")
        self.assertEqual(offenders, [],
                         f"unguarded rank correlation in: {offenders}")


class FiringTraceTests(SimpleTestCase):
    """A38 — the trace instrument's positive control, before the
    manifest: a deliberate firing must be recorded, and failure to
    log must raise rather than skip."""

    def test_positive_control_a_firing_is_recorded(self):
        import json
        import os
        import tempfile
        from apps.pipeline.services import palette_firing_trace as FT
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "trace.jsonl")
            os.environ[FT.TRACE_PATH_ENV] = path
            try:
                FT.log_firing("test_site:1", "positive_control",
                              {"denominator": 0.0}, 0.0)
            finally:
                del os.environ[FT.TRACE_PATH_ENV]
            rows = [json.loads(x) for x in open(path)]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["site"], "test_site:1")

    def test_failure_to_log_raises_not_skips(self):
        import os
        from apps.pipeline.services import palette_firing_trace as FT
        os.environ.pop(FT.TRACE_PATH_ENV, None)
        with self.assertRaises(FT.TraceWriteError):
            FT.log_firing("test_site:2", "unset_destination", {}, None)


class GuardCorpusTests(SimpleTestCase):
    """1z — every declared structural guard carries a seeded corpus;
    the suite fails if the detector misses a member. Seeded with every
    shape this arc surfaced."""

    CORPUS = [
        ("ratio_guard", "x = a / m if m > 1e-9 else 0.0"),
        ("ratio_guard_linebreak",
         "x = (a / m\n     if m > 1e-9 else\n     0.0)"),
        ("ratio_guard_one", "y = a / m if m else 1.0"),
        ("except_swallow", "try:\n    f()\nexcept ValueError:\n    x = 3\n"),
        ("bare_except", "try:\n    f()\nexcept:\n    pass\n"),
        ("lookup_default_literal", "v = cfg.get('k', 1.6)"),
        ("getattr_default", "v = getattr(o, 'k', 0.3)"),
        ("kwonly_default",
         "def g(*, detail=3.0):\n    return detail\n"),
        ("or_default", "v = compute() or 0.0"),
    ]

    @staticmethod
    def _detect(src):
        import ast as _ast
        import re as _re
        found = set()
        tree = _ast.parse(src)
        for n in _ast.walk(tree):
            if isinstance(n, _ast.IfExp) and isinstance(
                    n.orelse, _ast.Constant) and isinstance(
                    n.orelse.value, (int, float)):
                found.add("ifexp_default")
            if isinstance(n, _ast.ExceptHandler):
                exits = [x for x in _ast.walk(n) if isinstance(
                    x, (_ast.Raise, _ast.Return))]
                if not (exits and isinstance(
                        n.body[-1], (_ast.Raise, _ast.Return))):
                    found.add("except_swallow")
            if isinstance(n, _ast.Call):
                f = n.func
                if isinstance(f, _ast.Attribute) and f.attr == "get" \
                        and len(n.args) >= 2 and isinstance(
                        n.args[1], _ast.Constant):
                    found.add("lookup_default")
                if getattr(f, "id", None) == "getattr" \
                        and len(n.args) >= 3 and isinstance(
                        n.args[2], _ast.Constant):
                    found.add("getattr_default")
            if isinstance(n, _ast.FunctionDef):
                for d in list(n.args.defaults) + [
                        x for x in n.args.kw_defaults if x]:
                    if isinstance(d, _ast.Constant) and isinstance(
                            d.value, (int, float)) and not isinstance(
                            d.value, bool):
                        found.add("numeric_default_arg")
            if isinstance(n, _ast.BoolOp) and isinstance(
                    n.op, _ast.Or) and isinstance(
                    n.values[-1], _ast.Constant):
                found.add("or_default")
        return found

    def test_detector_catches_every_corpus_member(self):
        missed = []
        for name, src in self.CORPUS:
            if not self._detect(src):
                missed.append(name)
        self.assertEqual(missed, [],
                         f"guard detector misses corpus shapes: "
                         f"{missed}")

def composed_gate(src):
    """2b — the ENFORCING detector: union of the regex shapes and the
    AST reference detector. Detectors compose; none are removed."""
    import ast as _ast
    import re as _re
    hits = set()
    for m in _re.finditer(r"except\s*:|except [A-Za-z]+\s*:\s*pass"
                          r"|else 0\.0\b|else 1\.0\b"
                          r"|\.get\([^)]+,\s*[^)]+\)"
                          r"|getattr\([^)]+,[^)]+,[^)]+\)", src):
        hits.add(("regex", src[:m.start()].count("\n") + 1))
    try:
        tree = _ast.parse(src)
    except SyntaxError:
        return hits
    for n in _ast.walk(tree):
        if isinstance(n, _ast.IfExp) and isinstance(
                n.orelse, _ast.Constant) and isinstance(
                n.orelse.value, (int, float)) and not isinstance(
                n.orelse.value, bool):
            hits.add(("ifexp", n.lineno))
        if isinstance(n, _ast.ExceptHandler):
            exits = [x for x in _ast.walk(n) if isinstance(
                x, (_ast.Raise, _ast.Return))]
            if not (exits and isinstance(
                    n.body[-1], (_ast.Raise, _ast.Return))):
                hits.add(("except_swallow", n.lineno))
        if isinstance(n, _ast.Call):
            f = n.func
            if isinstance(f, _ast.Attribute) and f.attr == "get" \
                    and len(n.args) >= 2 and isinstance(
                    n.args[1], _ast.Constant):
                hits.add(("lookup_default", n.lineno))
            if getattr(f, "id", None) == "getattr" and len(n.args) >= 3 \
                    and isinstance(n.args[2], _ast.Constant):
                hits.add(("getattr_default", n.lineno))
        if isinstance(n, _ast.FunctionDef):
            for d in list(n.args.defaults) + [x for x in
                                              n.args.kw_defaults if x]:
                if isinstance(d, _ast.Constant) and isinstance(
                        d.value, (int, float)) and not isinstance(
                        d.value, bool):
                    hits.add(("numeric_default_arg", n.lineno))
        if isinstance(n, _ast.BoolOp) and isinstance(n.op, _ast.Or) \
                and isinstance(n.values[-1], _ast.Constant):
            hits.add(("or_default", n.lineno))
    return hits


def _symbol_of(src, lineno):
    import ast as _ast
    try:
        tree = _ast.parse(src)
    except SyntaxError:
        return "<module>"
    best = "<module>"
    for n in _ast.walk(tree):
        if isinstance(n, (_ast.FunctionDef, _ast.ClassDef)) \
                and n.lineno <= lineno <= (n.end_lineno or n.lineno):
            best = n.name
    return best


class ComposedGateTests(SimpleTestCase):
    """2b — the corpus runs against the gate that enforces, the
    baseline is the competent 194 enumeration keyed stably, and a new
    occurrence outside the baseline fails the suite."""

    def _baseline(self):
        import json as _json
        path = SERVICES.parent.parent.parent / (
            "docs/roadmap/palt_m6/enforcement_closure/"
            "gate_baseline.json")
        return set(map(tuple, _json.loads(path.read_text())["keys"]))

    def test_corpus_against_the_composed_gate(self):
        missed = [name for name, src in GuardCorpusTests.CORPUS
                  if not composed_gate(src)]
        self.assertEqual(missed, [],
                         f"the ENFORCING gate misses: {missed}")

    def test_no_new_occurrences_outside_the_baseline(self):
        base = self._baseline()
        new = []
        for path in SERVICES.rglob("*.py"):
            src = path.read_text()
            for shape, line in composed_gate(src):
                key = (path.name, _symbol_of(src, line), shape)
                if key not in base:
                    new.append(key)
        found = sorted(set(new))
        # Count and per-file tally lead, and nothing is truncated. This message
        # used to end in `[:8]`; keys sort by filename, so those 8 were all from
        # the two alphabetically-first files, and a sprint launcher recorded the
        # failure as "8 occurrences in two files" — hiding half the set for a
        # sprint.
        tally = collections.Counter(key[0] for key in found)
        self.assertEqual(found, [],
                         f"{len(found)} new fallback-class occurrences "
                         f"across {len(tally)} file(s) {dict(tally)}, "
                         f"in full: {found}")

    def test_gate_fails_on_a_new_occurrence_demonstration(self):
        src = "def q(v, m):\n    return v / m if m > 1e-9 else 0.0\n"
        self.assertTrue(composed_gate(src))


class TracedZeroTests(SimpleTestCase):
    """A89.2 — reflexive corpus run of the wired trace path."""

    def test_traced_zero_records_when_active(self):
        import json
        import os
        import tempfile
        from apps.pipeline.services import palette_firing_trace as FT
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "t.jsonl")
            os.environ[FT.TRACE_PATH_ENV] = path
            try:
                v = FT.traced_zero("corpus:site", "guard")
            finally:
                del os.environ[FT.TRACE_PATH_ENV]
            self.assertEqual(v, 0.0)
            rows = [json.loads(x) for x in open(path)]
            self.assertEqual(rows[0]["site"], "corpus:site")

    def test_traced_zero_behavior_unchanged_when_inactive(self):
        import os
        from apps.pipeline.services import palette_firing_trace as FT
        os.environ.pop(FT.TRACE_PATH_ENV, None)
        self.assertEqual(FT.traced_zero("corpus:site2", "guard"), 0.0)


class SpendReconcilerTests(SimpleTestCase):
    """2l — the reconciler raises both directions; a clean plan
    reconciles."""

    def test_raises_on_under_and_over(self):
        from apps.pipeline.services.palette_spend_reconciler import (
            SpendDivergence, reconcile)
        with self.assertRaises(SpendDivergence):
            reconcile({"a": 5, "b": 2}, {"a": 3, "b": 4})

    def test_clean_plan_reconciles(self):
        from apps.pipeline.services.palette_spend_reconciler import (
            reconcile)
        self.assertTrue(reconcile({"a": 2}, {"a": 2})["reconciled"])


class SplitIdentityTests(SimpleTestCase):
    """A173/2x — the flake composite is split: content moves on content,
    law era moves on the law, and the composite moves on either."""

    def test_law_era_identity_tracks_the_protocol_only(self):
        from unittest import mock
        from apps.pipeline.services import palette_flake_rig as FR
        content = FR.declaration_content_identity()
        era = FR.declaration_law_era_identity()
        composite = FR.declaration_identity()
        with mock.patch.object(FR.PP, "protocol_identity",
                               return_value="deadbeefdeadbeef"):
            self.assertEqual(FR.declaration_content_identity(), content)
            self.assertNotEqual(FR.declaration_law_era_identity(), era)
            self.assertNotEqual(FR.declaration_identity(), composite)

    def test_content_identity_tracks_content_only(self):
        from unittest import mock
        from apps.pipeline.services import palette_flake_rig as FR
        content = FR.declaration_content_identity()
        era = FR.declaration_law_era_identity()
        with mock.patch.object(FR, "PASS_BAR", 0.26):
            self.assertNotEqual(FR.declaration_content_identity(),
                                content)
            self.assertEqual(FR.declaration_law_era_identity(), era)

    def test_recipes_are_co_located_2w(self):
        from apps.pipeline.services import palette_flake_rig as FR
        for fn in (FR.declaration_content_identity,
                   FR.declaration_law_era_identity,
                   FR.declaration_identity):
            self.assertIn("RECIPE", fn.__doc__ or "")


class ThresholdKindTests(SimpleTestCase):
    """3e/A192 — a bound combines by worst observed excursion and may
    only tighten; a kindless threshold may not enter a gate."""

    def test_bound_takes_the_worst_not_the_latest(self):
        from apps.pipeline.services import palette_threshold_kind as TK
        self.assertEqual(TK.combine([0.16569, 0.14703], TK.BOUND),
                         0.16569)
        # a kinder third ensemble must NOT lower the floor
        self.assertEqual(TK.combine([0.16569, 0.14703, 0.10], TK.BOUND),
                         0.16569)

    def test_estimate_has_no_default_combiner(self):
        from apps.pipeline.services import palette_threshold_kind as TK
        with self.assertRaises(TK.ThresholdKindError):
            TK.combine([1.0, 2.0], TK.ESTIMATE)

    def test_kindless_is_refused_everywhere(self):
        from apps.pipeline.services import palette_threshold_kind as TK
        with self.assertRaises(TK.ThresholdKindError):
            TK.combine([1.0], "UNSTATED")
        with self.assertRaises(TK.ThresholdKindError):
            TK.assert_gate_usable({"value": 1.0})
        with self.assertRaises(TK.ThresholdKindError):
            TK.combine([], TK.BOUND)

    def test_rule_identity_reproduces_from_its_recipe(self):
        import hashlib
        import json
        from apps.pipeline.services import palette_threshold_kind as TK
        expected = hashlib.sha256(json.dumps(
            TK.RULE, sort_keys=True).encode()).hexdigest()[:16]
        self.assertEqual(TK.combining_rule_identity(), expected)


class VerdictIdentityTests(SimpleTestCase):
    """A150/2x — all four states, and the refusal on a one-identity
    record. The third state is the one that was invisible before."""

    REC = {"value_identity": "V0", "provenance_identity": "P0"}

    def test_all_four_states(self):
        from apps.pipeline.services import palette_verdict_identity as VI
        cases = {
            ("V0", "P0"): VI.FRESH,
            ("V1", "P0"): VI.STALE_VALUE_MOVED,
            ("V0", "P1"): VI.AGREEMENT_ACROSS_INSTRUMENT_CHANGE,
            ("V1", "P1"): VI.STALE_BOTH_MOVED,
        }
        for (v, p), expected in cases.items():
            out = VI.evaluate(self.REC, v, p)
            self.assertEqual(out["state"], expected)
            self.assertEqual(out["citable_as_fresh"],
                             expected == VI.FRESH)

    def test_agreement_state_requires_adjudication_and_is_not_fresh(self):
        from apps.pipeline.services import palette_verdict_identity as VI
        out = VI.evaluate(self.REC, "V0", "P_CHANGED")
        self.assertTrue(out["requires_adjudication"])
        self.assertFalse(out["citable_as_fresh"])
        self.assertIn("agreeing", out["note"])

    def test_one_identity_record_is_refused(self):
        from apps.pipeline.services import palette_verdict_identity as VI
        for bad in ({"value_identity": "V0"},
                    {"provenance_identity": "P0"}, {}):
            with self.assertRaises(VI.VerdictIdentityError):
                VI.evaluate(bad, "V0", "P0")

    def test_committed_estimates_carry_both(self):
        import json
        import pathlib
        et = (pathlib.Path(__file__).resolve().parents[3]
              / "docs/roadmap/palt_m6/establishment_closure"
              / "establishment_table.json")
        blk = json.loads(et.read_text())[
            "A143_forward_identities_2026_08_11"]["forward_identities"]
        for name, entry in blk.items():
            self.assertIn("value_identity", entry, name)
            self.assertIn("provenance_identity", entry, name)


class GuardedCommitTests(SimpleTestCase):
    """A137 — the commit path cannot swallow an exit code: a red suite
    must make the path REFUSE, demonstrated in both directions."""

    #: THESE TESTS RUN THE REAL SCRIPT, AND USED TO LEAVE REAL MARKS.
    #:
    #: What is under test is the script's own exit-code handling, so a
    #: copy would not be the thing. But running it real meant it wrote
    #: where it really writes, and cwd is the real repo root:
    #:
    #:   * ``guarded_commit.sh`` wrote ``.suite_gate_result``, clobbering
    #:     the artifact a concurrently running real gate is about to read
    #:     — the A137 shape this very class exists to guard.
    #:   * it then ran ``tools/record_integrity.py``, which APPENDED to
    #:     the tracked ``docs/roadmap/palt_m6/record_gate_ledger.jsonl``.
    #:     ``--dry-run`` exits well after both.
    #:
    #: Changing cwd would not have fixed the second one: that script
    #: derives its ROOT from ``__file__``, not from where it is invoked.
    #: Both destinations are therefore redirected by environment variable.
    #:
    #: Measured, not inferred. Each guarded commit left THREE ledger
    #: lines, not one — TIER_1 test, the script's own run, TIER_2 test —
    #: visible in the committed file as +8s/+590s and +10s/+596s triples.
    #: At 295 lines with 70 sub-60s gaps, roughly two in three lines were
    #: this class rather than a commit attempt, in a file whose own commit
    #: message describes it as runs of the gate "on every commit attempt
    #: through the sanctioned path".
    #: §BB7(g)(c) — that fix covered the ARTIFACT and the LEDGER and stopped
    #: there. Two OUTPUT files were still hardcoded, and on 2026-08-28 they
    #: were caught in the act rather than inferred: with a real gate running
    #: since 15:08, this class fired at 15:18 and left
    #: ``.suite_gate_output`` truncated 198 bytes -> 0, and
    #: ``.record_integrity_output`` replaced 74 bytes -> 250 announcing a
    #: ``/var/folders`` temp ledger. The live run's own evidence, destroyed
    #: by a test inside the suite that run was executing.
    #:
    #: The irony is the useful part: this class already redirected
    #: ``RECORD_INTEGRITY_LEDGER`` so as not to pollute the real ledger, and
    #: said so in the output it wrote over the report ABOUT the real ledger.
    #: It guarded the data and clobbered the record of the data.
    #:
    #: ``.reserved_copy_output`` and ``.brand_strings_output`` are written by
    #: the nested run too and were measured byte-IDENTICAL — they lose
    #: nothing TODAY, because those two tools' output does not vary with
    #: anything this class varies. That is contingent, not structural, and it
    #: is disclosed rather than fixed: §BB7(g)(c) ruled two files.
    def setUp(self):
        import os
        import tempfile
        self._td = tempfile.TemporaryDirectory()
        self.artifact = os.path.join(self._td.name, "suite_gate_result")
        self.ledger = os.path.join(self._td.name, "ledger.jsonl")
        self.suite_output = os.path.join(self._td.name, "suite_gate_output")
        self.integrity_output = os.path.join(
            self._td.name, "record_integrity_output")
        # §BH55 Phase 4: the last two output files the script hard-coded are redirectable now, and redirected here —
        # the class's own note said they lose nothing TODAY, "contingent, not structural", and this closes the class
        self.reserved_output = os.path.join(self._td.name, "reserved_copy_output")
        self.strings_output = os.path.join(self._td.name, "brand_strings_output")

    def tearDown(self):
        self._td.cleanup()

    def _run(self, suite_cmd):
        import os
        import subprocess
        # A315/3l: overriding SUITE_CMD does not waive the declared
        # extent — the opt-out has to be named. These tests exercise the
        # exit-code path, not the extent path, so they name it.
        env = dict(os.environ, SUITE_CMD=suite_cmd,
                   SUITE_GATE_ARTIFACT=self.artifact,
                   RECORD_INTEGRITY_LEDGER=self.ledger,
                   SUITE_GATE_OUTPUT=self.suite_output,
                   RECORD_INTEGRITY_OUTPUT=self.integrity_output,
                   RESERVED_COPY_OUTPUT=self.reserved_output,
                   BRAND_STRINGS_OUTPUT=self.strings_output,
                   EXTENT_ASSERTION_OPT_OUT="1",
                   EXTENT_ASSERTION_OPT_OUT_REASON=(
                       "A137 exit-code test: forces a red suite, so the "
                       "declared extent belongs to a different command"))
        return subprocess.run(
            ["zsh", "tools/guarded_commit.sh", "--dry-run", "-m", "x"],
            capture_output=True, text=True, env=env,
            cwd=os.getcwd())

    def test_red_suite_refuses(self):
        r = self._run("false")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("GUARDED_COMMIT_REFUSED", r.stderr)

    def test_green_suite_passes_gate(self):
        r = self._run("true")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("GUARDED_COMMIT_DRY_RUN_OK", r.stdout)

    def test_artifact_carries_the_true_exit_code(self):
        import json
        import os
        import stat
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".sh",
                                         delete=False) as f:
            f.write("#!/bin/sh\nexit 7\n")
            path = f.name
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
        try:
            self._run(path)
        finally:
            os.unlink(path)
        art = json.load(open(self.artifact))
        self.assertEqual(art["suite_exit"], 7)

    def test_the_real_ledger_and_artifact_are_left_alone(self):
        """THE REGRESSION THIS CLASS ITSELF WAS.

        Not a check that the write was disabled — a check that it MOVED.
        Asserting only that the real ledger is unchanged would pass just
        as well if the append had been deleted outright, and deleting it
        would have quietly destroyed the record the gate exists to keep.
        So both halves are asserted: the real file is byte-identical, AND
        the redirected file actually received a well-formed line.

        ``_run("true")`` is the case that reaches the append. The other
        two tests refuse earlier, on the exit code, before the record
        gate is ever invoked."""
        import os
        import pathlib
        real = (pathlib.Path(__file__).resolve().parents[3]
                / "docs/roadmap/palt_m6/record_gate_ledger.jsonl")
        before = real.read_bytes()
        r = self._run("true")
        self.assertEqual(r.returncode, 0, r.stderr)

        self.assertEqual(
            real.read_bytes(), before,
            "the suite appended to the tracked record ledger. It is "
            "APPEND_ONLY, so this does not fail the integrity gate — it "
            "just silently makes the file mostly test output.")
        self.assertFalse(
            os.path.exists(os.path.join(os.getcwd(), "suite_gate_result")),
            "the redirected artifact was resolved relative to the repo "
            "root instead of to the temp path")

        self.assertTrue(
            os.path.exists(self.ledger),
            "nothing was written to the redirected ledger, so this test "
            "would also pass with the append removed altogether — which "
            "is the failure mode it exists to exclude")
        line = json.loads(open(self.ledger).read().splitlines()[-1])
        for key in ("utc", "verdict", "records_checked", "refusal_count",
                    "failing_set"):
            self.assertIn(key, line)
        self.assertEqual(line["verdict"], "OK", line.get("failing_set"))

    def test_the_real_output_files_are_left_alone(self):
        """§BB7(g)(c) EXTENDED to the two OUTPUT files, same shape as above.

        THE DEFECT, CAUGHT IN THE ACT rather than inferred. On 2026-08-28 a
        real gate started at 15:08 and was still in TIER_2 at 15:18 when this
        class fired inside it. Fingerprints taken before and after:
        ``.suite_gate_output`` 198 bytes -> 0, and
        ``.record_integrity_output`` 74 bytes -> 250 bytes reporting a
        ``/var/folders`` temp ledger. Both mtimes moved to 15:18. The running
        gate's own evidence, overwritten by a test in the suite it was running
        — so anyone reading those files to see why the live gate passed is
        reading this class's output instead.

        ``.tier2_gate_output`` was NOT touched, and that is the control: it is
        written at line 286, past the ``--dry-run`` exit at 311, so the nested
        run never reaches it. A defect that spared exactly the file the
        control structure says it should spare is the defect, not a coincidence.

        WHY BOTH HALVES, per the sibling above: asserting only that the real
        files are unchanged would pass just as well if the redirect had been
        deleted and nothing were written anywhere. So the redirected files are
        asserted to have RECEIVED the writes. That is the same two-directional
        check H020 needed — one side proves nothing was clobbered, the other
        proves the work still happens."""
        import os
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[3]
        suite_out = root / ".suite_gate_output"
        integrity_out = root / ".record_integrity_output"
        before_suite = suite_out.read_bytes() if suite_out.exists() else None
        before_integrity = (integrity_out.read_bytes()
                            if integrity_out.exists() else None)

        r = self._run("true")
        self.assertEqual(r.returncode, 0, r.stderr)

        # .suite_gate_output is asserted PREFIX-PRESERVED, not equal, and the
        # asymmetry is deliberate. When this test runs inside a real gate it
        # runs inside the very pytest whose stdout IS that file, held open by
        # the redirect at guarded_commit.sh:199. A flush landing between the
        # two reads would grow the file for an entirely legitimate reason, so
        # equality here would be a guard that fails on innocent timing. What
        # is actually claimed is that the nested run did not DESTROY what was
        # there — and the measured defect was truncation, 198 bytes to 0,
        # which prefix-preservation catches and concurrent growth does not.
        after_suite = suite_out.read_bytes() if suite_out.exists() else None
        if before_suite is None:
            self.assertIsNone(
                after_suite,
                ".suite_gate_output was CREATED by the nested run")
        else:
            self.assertIsNotNone(
                after_suite, ".suite_gate_output was deleted by the nested run")
            self.assertTrue(
                after_suite.startswith(before_suite),
                ".suite_gate_output no longer begins with what it held "
                "before the nested run, so the nested run truncated or "
                "replaced it — 198 bytes to 0 is the measured shape.")

        # .record_integrity_output is written at guarded_commit.sh:227, AFTER
        # the suite has exited, so no legitimate writer touches it while this
        # test runs and exact equality is the right claim.
        after_integrity = (integrity_out.read_bytes()
                           if integrity_out.exists() else None)
        self.assertEqual(
            after_integrity, before_integrity,
            ".record_integrity_output was written by the nested run, "
            "destroying the evidence of any real gate running concurrently. "
            "This is the A137 shape this class exists to guard, committed "
            "by the guard itself.")

        for stray in ("suite_gate_output", "record_integrity_output"):
            self.assertFalse(
                os.path.exists(os.path.join(os.getcwd(), stray)),
                f"{stray} was resolved relative to the repo root instead "
                "of to the temp path")

        self.assertTrue(
            os.path.exists(self.suite_output),
            "nothing reached the redirected suite output, so this test "
            "would also pass with the redirect removed altogether — the "
            "failure mode it exists to exclude")
        self.assertTrue(
            os.path.exists(self.integrity_output),
            "nothing reached the redirected integrity output")
        self.assertIn(
            "RECORD_INTEGRITY", open(self.integrity_output).read(),
            "the redirected integrity output exists but carries no verdict, "
            "so the record gate did not actually run")

    def test_source_guard_the_ledger_is_staged_between_dry_run_and_commit(
            self):
        """SOURCE-STRING GUARD — §Y2(b). This asserts NOTHING about behaviour.

        THE DEFECT IT PINS. ``tools/record_integrity.py`` appends a verdict
        line to the tracked gate ledger on every run of the commit path, and
        it runs long after the caller staged — staging is the CALLER's act,
        and the script only ever ran ``git commit`` on an index it did not
        build. So each commit carried the PREVIOUS run's verdict and left its
        own behind unstaged: the ledger was permanently one run behind, and a
        clean tree was unreachable through the sanctioned path by
        construction. Measured at 9456e7d, which contains the
        2026-08-22T11:24:55Z line while its own 2026-08-24T01:28:50Z line was
        still a working-tree modification after it returned.

        WHY THE ORDER IS THE WHOLE CLAIM, and why this is not a presence
        check. ``git add`` placed before the ``--dry-run`` exit would make a
        dry run mutate the index, which is the one thing a dry run must not
        do; placed after ``git commit`` it would stage into the NEXT commit
        and change nothing at all. Only between them is the fix, so what is
        asserted is the ordering.

        §Y2(c), THE LIMIT, stated rather than engineered away: **this cannot
        prove the block runs, only that it is written.** The sibling tests
        in this class cannot reach it — every one of them passes
        ``--dry-run`` and exits above it, which is the same property that
        makes the fix safe for them. The proof that it runs was taken BY
        HAND on the commit that introduced it: the run printed
        ``GUARDED_COMMIT_LEDGER_STAGED`` and the resulting commit contained
        the line its own gate run had just written.

        HOW OFTEN THE DEFECT ACTUALLY BIT, with the population stated
        (§A564), because the first answer drafted here was "every commit in
        the file's history" and that is not what the repository says. Over
        the 50 consecutive ledger-commit pairs: **10 commits omitted a
        ledger line that was already on disk when they were made**, the
        worst by 926 minutes. The other 40 committed a complete ledger —
        they did not go through this script, so they had no line of their
        own to leave behind. The structural claim is the universal one and
        does not need the count: staging precedes the append, so a commit
        THROUGH THIS PATH cannot contain its own line. The count says how
        often that path was taken, which is a different question, and two
        earlier drafts of this measurement got it wrong in both directions
        — one criterion could not tell the fixed case from the broken one
        at all, the next was defeated by dry-run lines landing between
        commits.
        """
        import pathlib
        body = (pathlib.Path(__file__).resolve().parents[3]
                / "tools/guarded_commit.sh").read_text(encoding="utf-8")
        # Each anchor verified to occur EXACTLY once before being relied on.
        # The neighbouring §AV2 guard records what skipping that check costs:
        # it anchored on "TIER_2", matched a comment 140 lines above the block
        # that runs it, and failed 8950 < 2569 — AD0(b), an instrument
        # recognising a thing by an incidental feature of how it is written.
        dry_run_exit = body.index("GUARDED_COMMIT_DRY_RUN_OK")
        redirect_guard = body.index("GUARDED_COMMIT_LEDGER_NOT_STAGED")
        stage = body.index('git add -- "${GC_LEDGER}"')
        commit = body.index('git commit "$@"')
        self.assertLess(
            dry_run_exit, stage,
            "the ledger is staged BEFORE the --dry-run exit, so a dry run "
            "now mutates the real index — including on every run of this "
            "very class")
        self.assertLess(
            stage, commit,
            "the ledger is staged after the commit is made, so its line "
            "still lands one run behind: the defect this guard pins")
        self.assertLess(
            redirect_guard, stage,
            "the redirect check no longer precedes the staging, so a run "
            "with RECORD_INTEGRITY_LEDGER set would stage the real ledger "
            "it never wrote to")


class EnergyRecoveryTests(SimpleTestCase):
    """A100/2f — the census-energy reading instrument: committed
    values read, derivations exact against the committed law, and
    families with no record REFUSED rather than estimated."""

    def test_cached_family_reads_committed_value(self):
        from apps.pipeline.services import palette_energy_recovery as ER
        r = ER.read_cached_energy("POWDER_MATTE")
        self.assertEqual(r["status"], "COMMITTED_VALUE")
        self.assertGreater(r["energy"], 0)

    def test_derivation_matches_the_committed_law_by_hand(self):
        from apps.pipeline.services import palette_energy_recovery as ER
        from apps.pipeline.services import (
            palette_powder_texture_axes as TX)
        r = ER.derive_census_energy("BAKED")
        i = r["inputs"]
        by_hand = i["ref"] * (TX.CAL_TARGET - i["base_peak"]) / (
            i["probe_peak"] - i["base_peak"])
        self.assertEqual(r["energy"], by_hand)
        self.assertEqual(r["status"],
                         "EXACT_IFF_SINGLE_ITERATION_CONVERGENCE")

    def test_all_four_derivable_families_derive(self):
        from apps.pipeline.services import palette_energy_recovery as ER
        for fam in ER.DERIVABLE:
            self.assertGreater(ER.derive_census_energy(fam)["energy"],
                               0)

    def test_no_record_refuses_never_estimates(self):
        from apps.pipeline.services import palette_energy_recovery as ER
        with self.assertRaises(ER.EnergyRecoveryError):
            ER.derive_census_energy("GLITTER")
        with self.assertRaises(ER.EnergyRecoveryError):
            ER.derive_census_energy("POWDER_MATTE")
        with self.assertRaises(ER.EnergyRecoveryError):
            ER.read_cached_energy("SHIMMER")


class MechanismReconcilerTests(SimpleTestCase):
    """2r/A116 — ranged units reconcile against the realised mechanism,
    never the envelope; an envelope-internal unexplained count raises."""

    WINDOW = (0.35, 0.92)

    def test_legitimate_two_iteration_unit_reconciles(self):
        from apps.pipeline.services.palette_spend_reconciler import (
            reconcile_calibration_unit)
        log = [{"peak": 1.4, "clipped": 120},
               {"peak": 0.88, "clipped": 0}]
        r = reconcile_calibration_unit("recal_X", 3, 6, 4, log,
                                       self.WINDOW)
        self.assertTrue(r["reconciled"])

    def test_envelope_internal_unexplained_count_raises(self):
        from apps.pipeline.services.palette_spend_reconciler import (
            SpendDivergence, reconcile_calibration_unit)
        # 5 frames sits inside [3, 6], but iteration 1 already passed
        # the gate — the second iteration is a count the law does not
        # account for, and it must raise even inside the envelope
        log = [{"peak": 0.88, "clipped": 0},
               {"peak": 0.89, "clipped": 0},
               {"peak": 0.90, "clipped": 0}]
        with self.assertRaises(SpendDivergence):
            reconcile_calibration_unit("recal_X", 3, 6, 5, log,
                                       self.WINDOW)

    def test_count_mechanism_mismatch_and_unconverged_raise(self):
        from apps.pipeline.services.palette_spend_reconciler import (
            SpendDivergence, reconcile_calibration_unit)
        good = [{"peak": 0.88, "clipped": 0}]
        with self.assertRaises(SpendDivergence):
            reconcile_calibration_unit("recal_X", 3, 6, 4, good,
                                       self.WINDOW)  # 4 != 2+1
        bad_final = [{"peak": 1.4, "clipped": 33}]
        with self.assertRaises(SpendDivergence):
            reconcile_calibration_unit("recal_X", 3, 6, 3, bad_final,
                                       self.WINDOW)

    def test_down_retry_unit_both_directions(self):
        from apps.pipeline.services.palette_spend_reconciler import (
            SpendDivergence, reconcile_down_retry_unit)
        ok1 = reconcile_down_retry_unit(
            "d_X", 1, [{"peak": 0.41, "clipped": 0}], 0.35)
        self.assertTrue(ok1["reconciled"])
        ok2 = reconcile_down_retry_unit(
            "d_X", 2, [{"peak": 0.31, "clipped": 0},
                       {"peak": 0.44, "clipped": 0}], 0.35)
        self.assertTrue(ok2["reconciled"])
        # refused single attempt cannot reconcile as 1 frame
        with self.assertRaises(SpendDivergence):
            reconcile_down_retry_unit(
                "d_X", 1, [{"peak": 0.31, "clipped": 0}], 0.35)
        # clean first attempt with an unexplained retry raises
        with self.assertRaises(SpendDivergence):
            reconcile_down_retry_unit(
                "d_X", 2, [{"peak": 0.41, "clipped": 0},
                           {"peak": 0.45, "clipped": 0}], 0.35)

    def test_retry_unit_both_directions(self):
        from apps.pipeline.services.palette_spend_reconciler import (
            SpendDivergence, reconcile_retry_unit)
        ok2 = reconcile_retry_unit("ctl_X", 2, [{"clipped": 0}])
        self.assertTrue(ok2["reconciled"])
        ok3 = reconcile_retry_unit("ctl_X", 3, [{"clipped": 512},
                                                {"clipped": 0}])
        self.assertTrue(ok3["reconciled"])
        with self.assertRaises(SpendDivergence):
            reconcile_retry_unit("ctl_X", 3, [{"clipped": 0},
                                              {"clipped": 0}])
        with self.assertRaises(SpendDivergence):
            reconcile_retry_unit("ctl_X", 2, [{"clipped": 512}])


class StampedAxisTests(SimpleTestCase):
    """A114 — the stamp stops the citing path mechanically; vigilance
    is not the mechanism."""

    RECORD = {"families": {"BAKED": {"axes": {
        "GRANULARITY_INDEX": {
            "stamp": "ENERGY_INVARIANT_AT_CONDITION",
            "reference_value": 0.15, "cleared_range": [0.35, 0.92]},
        "GRAZING_BAND_CONTRAST": {
            "stamp": "NOT_ENERGY_INVARIANT_AT_CONDITION",
            "reference_value": 0.4},
        "SURFACE_AUTOCORRELATION_MM": {
            "reference_value": 1.2},
    }}}}

    def test_invariant_stamp_reads(self):
        from apps.pipeline.services import palette_energy_recovery as ER
        e = ER.read_stamped_axis(self.RECORD, "BAKED",
                                 "GRANULARITY_INDEX")
        self.assertEqual(e["cleared_range"], [0.35, 0.92])

    def test_not_invariant_and_unstamped_raise(self):
        from apps.pipeline.services import palette_energy_recovery as ER
        with self.assertRaises(ER.StampedAxisError):
            ER.read_stamped_axis(self.RECORD, "BAKED",
                                 "GRAZING_BAND_CONTRAST")
        with self.assertRaises(ER.StampedAxisError):
            ER.read_stamped_axis(self.RECORD, "BAKED",
                                 "SURFACE_AUTOCORRELATION_MM")
        with self.assertRaises(ER.StampedAxisError):
            ER.read_stamped_axis(self.RECORD, "SHIMMER",
                                 "GRANULARITY_INDEX")


class QueueControlTests(SimpleTestCase):
    """A98/2o — the run-level control: a queue proves its trace live
    as its FIRST act, and the citing path REJECTS a queue with no
    control record rather than warning about it."""

    def _fresh(self):
        import importlib
        from apps.pipeline.services import palette_queue_control as QC
        importlib.reload(QC)
        return QC

    def test_controlled_queue_is_readable_including_as_zero(self):
        import os
        import tempfile
        from apps.pipeline.services import palette_firing_trace as FT
        QC = self._fresh()
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "trace.jsonl")
            ledger = {"frames_rendered": 0, "done": []}
            try:
                with self.assertRaises(QC.QueueControlError):
                    QC.begin_traced_queue("test_q", path, ledger, "")
                stamp = QC.begin_traced_queue("test_q", path, ledger,
                                              "decl@test0001")
                self.assertEqual(stamp["declaration_identity"],
                                 "decl@test0001")
                self.assertEqual(ledger[QC.LEDGER_KEY], [stamp])
                QC.assert_process_controlled(ledger)
                # zero real firings reads as zero, not as unknown
                self.assertEqual(
                    QC.read_trace_evidence(ledger, path), [])
                FT.log_firing("site:x", "comp", {"branch": "f"}, 0.0)
            finally:
                del os.environ[FT.TRACE_PATH_ENV]
            rows = QC.read_trace_evidence(ledger, path)
            self.assertEqual([r["site"] for r in rows], ["site:x"])

    def test_suppressed_control_is_rejected_by_the_citing_path(self):
        import os
        import tempfile
        from apps.pipeline.services import palette_firing_trace as FT
        QC = self._fresh()
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "trace.jsonl")
            os.environ[FT.TRACE_PATH_ENV] = path
            try:
                FT.log_firing("site:y", "comp", {"branch": "f"}, 0.0)
            finally:
                del os.environ[FT.TRACE_PATH_ENV]
            uncontrolled = {"frames_rendered": 1, "done": ["t"]}
            with self.assertRaises(QC.QueueControlError):
                QC.read_trace_evidence(uncontrolled, path)
            with self.assertRaises(QC.QueueControlError):
                QC.assert_process_controlled(uncontrolled)

    def test_stamp_without_travelling_record_is_rejected(self):
        import os
        import tempfile
        QC = self._fresh()
        stamp = {"control_site": QC.CONTROL_SITE, "queue": "q",
                 "trace_path": "/nowhere", "ts": 1.0}
        ledger = {QC.LEDGER_KEY: [stamp]}
        with tempfile.TemporaryDirectory() as td:
            absent = os.path.join(td, "absent.jsonl")
            with self.assertRaises(QC.QueueControlError):
                QC.read_trace_evidence(ledger, absent)
            empty = os.path.join(td, "empty.jsonl")
            open(empty, "w").close()
            with self.assertRaises(QC.QueueControlError):
                QC.read_trace_evidence(ledger, empty)

    def test_control_not_first_act_is_rejected(self):
        import os
        import tempfile
        from apps.pipeline.services import palette_firing_trace as FT
        QC = self._fresh()
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "trace.jsonl")
            os.environ[FT.TRACE_PATH_ENV] = path
            try:
                # a frame firing lands BEFORE the control is emitted
                FT.log_firing("site:z", "comp", {"branch": "f"}, 0.0)
                ledger = {}
                QC.begin_traced_queue("late_q", path, ledger,
                                      "decl@test0002")
            finally:
                del os.environ[FT.TRACE_PATH_ENV]
            with self.assertRaises(QC.QueueControlError):
                QC.read_trace_evidence(ledger, path)
