"""WI-G (§Y2) — a source-string guard must say that is what it is.

§Y2 keeps both of the guards that survived sprint 9's M3 mutation (§Y2(a)):
they are cheap and they catch the one thing they are for, somebody deleting a
call site outright. The defect is that **their names claim more than they
check**, so a mutation-survivor report listing them reads as though a
behaviour were covered when nothing behavioural was asserted at all.

§Y2(b) therefore requires every source-string guard in the repo to declare
itself in its NAME and its DOCSTRING, and §Y2(c) forbids ever citing one as
evidence that a behaviour is covered — in a close report, a ledger row, a
tracker validation count or a survivor analysis. §Y2(d): **the rule is
general.** It is not scoped to the two tests that prompted it.

WHY THIS IS A META-TEST AND NOT A ONE-TIME SWEEP
------------------------------------------------
A sweep discharges §Y2(b) on the day it is run and starts decaying the next
day, when guard number 63 is written without a declaration and nothing
notices. §Y's own preamble names that failure mode — *a rule you wrote down is
not a rule you have applied* — about a rule this programme had already
written down and then broke one sprint later. A rule that is general in FORCE
needs a mechanism, so the census that found the guards is committed here and
runs as a test.

WHAT IS AND IS NOT DISCHARGED — read this before citing §Y2 as done
------------------------------------------------------------------
* **In force, repo-wide, from this commit**: no NEW undeclared source-string
  guard can enter any app. That is §Y2(d)'s generality, mechanically enforced.
* **Declared**: every guard in `apps/ire`, the subject area of §Y.
* **Converted, WI-S (§AA)**: the eight `dielines` provider guards. Not
  renamed — replaced. Each now runs the real path with every provider
  boundary armed to raise and requires the run to have reached the module,
  so it leaves this census because it asserts on behaviour, not because it
  acquired a label. See `apps/dielines/tests/provider_tripwire.py`.
* **NOT converted**: the **52** guards still in `REGISTERED_UNDECLARED`,
  across `accounts`, `dielines` and `pipeline`. They are registered, counted
  and committed rather than silently exempt, and the register can only
  shrink — **except when the classifier's reach widens**, which is what took
  it 50 -> 52 and is the one exception the register's own comment did not
  anticipate. **This is a backlog, not a discharge**, and §Y2 should not be
  cited as fully applied while the register is non-empty.

Totals: **64 pure source-string guards at WI-G — 6 declared (all in
`apps/ire`), 58 registered. 66 after WI-L's follow-up, which wrote two new
guards, was caught by the no-new rule, and declared them: 8 declared, still 58
registered. After WI-S: 58 guards, 8 declared, 50 registered.** The eight that
left are gone from the census because they stopped being source-string guards,
which is the only exit that counts.

The declared count is stated at each step because the first draft of this line
carried WI-G's "6 declared" forward to WI-S and got the post-conversion total
wrong by two. The register was never wrong — it is asserted to the digit — but
a total quoted from memory instead of from `census()` was, and the anti-vacuity
floor below is what caught it.

A NOTE ON THE NUMBER, because it moved four times
-------------------------------------------------
The count is the interesting artefact here, so its history is kept rather than
tidied away.

1. **61** — the first census. It missed every guard that reads source through
   a HELPER METHOD rather than a local assignment, which is how the error came
   to light: the two guards §Y2(a) names by hand were both absent from a list
   that was supposed to contain them. A census that cannot find its own
   worked example is not a census.
2. **94** — after teaching it about helpers. Now over-counting in the other
   direction: it swept in tests that read a committed RECORD and assert its
   content. That is a behavioural assertion about whatever produced the
   record, and counting it would have filled this register with tests doing
   exactly the right thing.
3. **62** — restricted to reads of Python/JS/template source. Still wrong,
   twice, in ways that cancelled to within two: `Path(__file__).parent /
   "x.json"` was read as a source read because `__file__` appeared anywhere in
   it, while `src.count(literal) == 1` had been dropped as behavioural.
4. **64** — both corrected, and each correction pinned by a test in
   `TestTheCensusItselfIsNotVacuous` so neither can silently come back.
5. **68** — the census repair, which fixed three blind spots at once because
   measurement showed no proper subset of them was enough. The classifier
   learned `.sh`, learned that `i = src.index(a)` binds a POSITION, and
   learned `self.assertX`. The third was the big one and it had nothing to do
   with what tests assert: **the census had only ever been able to see
   pytest-style tests**, so every number above measures one dialect of this
   repository and none of them said so. The 4 new entries are 2 declared
   guards that were already declared and 2 undeclared guards older than this
   file; none is new code.

The sprint's own lesson, arrived at twice: **a number is not a measurement
until you know what it counted, and a count that lands near the right answer
may be two errors cancelling.** The repair adds a third arrival and a
corollary: **an instrument's blind spot does not show up as a wrong number,
it shows up as a number that is right about a smaller population than the one
you named.** 64 was never wrong. It was the answer to a question nobody had
written down.
"""
from __future__ import annotations

import ast
import pathlib

APPS = pathlib.Path(__file__).resolve().parents[3] / "apps"

#: §Y2(b) — the two halves of a declaration. Both are required: the docstring
#: alone leaves the misleading NAME in the survivor report, which is the
#: defect §Y2 opens on, and the name alone does not say what the limit is.
DECLARING_NAME = "test_source_guard_"
DECLARING_MARKER = "SOURCE-STRING GUARD"

#: Reads that return SOURCE. A read of a produced artifact is deliberately NOT
#: here — asserting on a record the code under test wrote is a behavioural
#: assertion about the writer, and counting it would inflate this register
#: with tests that are doing exactly the right thing.
#:
#: ``.sh`` added at the census repair. It was blind spot 1 of three, and on its
#: own it changed NOTHING — see the classifier test's docstring, which measured
#: that before the repair and is why all three were fixed in one act.
_SOURCE_SUFFIXES = (".py", ".js", ".html", ".jsx", ".sh")

#: Checked FIRST. A read whose path names one of these is a read of an
#: artifact — a fixture, a committed record, a manifest — and asserting on one
#: is a behavioural claim about whatever produced it.
_ARTIFACT_SUFFIXES = (".json", ".txt", ".md", ".csv", ".svg", ".pdf", ".ai")

#: String searches over file text. ``src.count(lit) == 1`` and
#: ``src.index(a) < src.index(b)`` are source-string assertions as surely as
#: ``lit in src`` is — they ask where and how often, not what the code does.
_SEARCH_METHODS = ("count", "index", "find", "rindex")

#: ``unittest`` assertions, by the shape of what they claim. Blind spot 3, and
#: the only one of the three that was a property of the INSTRUMENT rather than
#: of one guard: ``visit_Assert`` fires on ``ast.Assert`` only, so every
#: ``self.assertX`` in the repository was invisible to this census until the
#: repair. Grouped by shape because the argument that must read source differs:
#: membership takes the container SECOND, comparisons take positions in either
#: of the first two, and the truth forms take a whole expression.
_MEMBERSHIP_METHODS = ("assertIn", "assertNotIn")
_COMPARE_METHODS = ("assertEqual", "assertNotEqual", "assertLess",
                    "assertLessEqual", "assertGreater", "assertGreaterEqual")
_TRUTH_METHODS = ("assertTrue", "assertFalse")

#: §Y2(b) applied to `apps/ire` only. Everything else is the registered
#: backlog above. Kept as a constant so the boundary is one grep away.
CONVERTED_AREAS = ("apps/ire/",)

#: The pre-existing guards, as of WI-G. ONE-WAY: entries may be removed when a
#: guard is converted or deleted; an addition means a new undeclared guard got
#: in, which is what this module exists to prevent.
#:
#: **50 -> 52 AT THE CENSUS REPAIR, AND IT IS THE ONE ADDITION THE SENTENCE
#: ABOVE DOES NOT COVER.** Both entries are older than this file. Nothing got
#: in; the instrument's eyesight improved, and two guards that were always
#: there became countable. The rule as written cannot tell that case from a
#: regression, because it reads an addition as evidence about the REPO when an
#: addition is really evidence about the CENSUS. A widening of the classifier
#: is therefore the one act that may add here, and only with the new entries
#: named and their age shown — which is why they are listed in the classifier
#: test's docstring with what each asserts, rather than merely counted.
REGISTERED_UNDECLARED = frozenset({
    "apps/accounts/test_attestation.py|test_no_activation_or_permission_surface",
    "apps/accounts/test_authz_policy.py|test_production_settings_do_not_hack_sys_path_for_policy",
    "apps/accounts/test_decision_chain.py|test_no_approval_permission_or_retrieval_surface",
    "apps/accounts/test_role_services.py|test_no_approval_permission_retrieval_or_activation_surface",
    "apps/dielines/tests/test_version_visibility.py|ChooserJsTests::test_chooser_renders_recommended_and_legacy_by_class",
    "apps/dielines/tests/test_version_visibility.py|ChooserJsTests::test_selector_carries_version",
    "apps/pipeline/tests/test_2b3v_confirm_resume.py|ConfirmedUiTests::test_confirmed_state_replaces_the_form",
    "apps/pipeline/tests/test_2b3v_confirm_resume.py|ConfirmedUiTests::test_failed_state_shows_code_and_resume_action",
    "apps/pipeline/tests/test_2b3v_confirm_resume.py|ConfirmedUiTests::test_running_and_complete_states_render",
    "apps/pipeline/tests/test_2b3v_profile_zone_ui.py|FrontendBindingTests::test_frontend_combined_action_not_legacy_reconstruct",
    "apps/pipeline/tests/test_2b3v_profile_zone_ui.py|FrontendBindingTests::test_frontend_posts_zones_with_confirmation_state",
    "apps/pipeline/tests/test_2b3v_profile_zone_ui.py|FrontendBindingTests::test_frontend_renders_depth",
    "apps/pipeline/tests/test_2b3v_profile_zone_ui.py|FrontendBindingTests::test_frontend_renders_refusal_detail_without_reset",
    "apps/pipeline/tests/test_2b3v_profile_zone_ui.py|FrontendBindingTests::test_frontend_renders_versioned_contract",
    "apps/pipeline/tests/test_2b3v_profile_zone_ui.py|FrontendBindingTests::test_frontend_shows_hashes_and_authority",
    "apps/pipeline/tests/test_2c1_composite_activation.py|UiActivationTests::test_workflow_preview_steps",
    "apps/pipeline/tests/test_b4b1_reference_core.py|TestBoundariesHeld::test_the_validator_reaches_no_network_or_provider",
    "apps/pipeline/tests/test_b4b1_reference_core.py|TestOptionalAndNoRegression::test_no_second_reference_model_was_introduced_by_this_slice",
    "apps/pipeline/tests/test_b4b1_reference_core.py|TestOrphanProtection::test_the_view_dispatches_on_commit_not_inline",
    "apps/pipeline/tests/test_brand_component_library.py|TestPurity::test_the_library_reaches_no_provider_and_no_database",
    "apps/pipeline/tests/test_characterization_protocol.py|CloseoutBarTests::test_the_mirrored_camera_angles_match_the_production_script",
    "apps/pipeline/tests/test_confirm_profile_ui1.py|TestArchetypeCatalog::test_no_duplicate_catalog_in_the_browser",
    "apps/pipeline/tests/test_confirm_profile_ui1.py|TestFrontendContractStrings::test_no_dead_confirm_and_no_new_endpoint",
    "apps/pipeline/tests/test_confirm_profile_ui1.py|TestFrontendContractStrings::test_other_never_renders_as_bottle",
    "apps/pipeline/tests/test_confirm_profile_ui1.py|TestFrontendContractStrings::test_preview_is_local_and_honest",
    "apps/pipeline/tests/test_gate_a_corr1.py|TestNothingDownstreamStarted::test_this_slice_makes_no_provider_call_at_all",
    "apps/pipeline/tests/test_gate_a_corr2.py|TestNothingDownstreamStarted::test_this_slice_makes_no_provider_call",
    "apps/pipeline/tests/test_gate_a_final.py|TestGateAGrantsNothingElse::test_this_slice_makes_no_provider_call",
    "apps/pipeline/tests/test_gate_a_roundtrip1.py|TestGateAStillBlocked::test_this_slice_makes_no_provider_call",
    "apps/pipeline/tests/test_p1_pilot_geometry.py|P1MaskPipelineTests::test_mask_scene_is_lighting_independent_by_construction",
    "apps/pipeline/tests/test_palette_profile_offset.py|CorrectedTrayTests::test_no_blender_boolean_dependency",
    "apps/pipeline/tests/test_production_authority_preflight.py|TestBlockersAndCalls::test_the_renderer_has_no_provider_call_path",
    "apps/pipeline/tests/test_rbv2b_validation_render.py|IsolationTests::test_no_provider_no_models_no_gate_touch",
    "apps/pipeline/tests/test_rbv3_review_package.py|TestPurity::test_no_provider_or_orm_imports",
    "apps/pipeline/tests/test_rbv4_claude_review.py|TestProvenance::test_no_provider_or_orm_imports",
    "apps/pipeline/tests/test_rbv5_comparison_gate.py|TestProvenanceAndPurity::test_no_provider_or_orm_imports",
    "apps/pipeline/tests/test_rbv5_comparison_gate.py|TestTheSilhouetteTruthIsShared::test_source_module_defines_no_second_profile",
    "apps/pipeline/tests/test_selected_concept_fidelity.py|AiLibraryTests::test_descriptors_contain_no_source_paths",
    "apps/pipeline/tests/test_structure_projection_2a9.py|PhysicalTestApprovalTests::test_no_provider_calls_in_the_correction_path",
    "apps/pipeline/tests/test_vq1_closeout.py|TestFitterFixDoesNotTouchM3::test_corrected_fitter_is_not_wired_into_the_vq1_path",
    "apps/pipeline/tests/test_vq1_corr4.py|TestPerceivedValidationAndPreservation::test_no_provider_call_paths_in_corr4",
    "apps/pipeline/tests/test_vq1_corr5.py|TestPreservationAndProvenance::test_no_provider_call_paths",
    "apps/pipeline/tests/test_vq1_reset1.py|TestProviderBoundary::test_inspector_never_generates_images",
    "apps/pipeline/tests/test_vq1_reset1b.py|TestBoundaries::test_web_access_is_ledgered_not_apicallrecord",
    "apps/pipeline/tests/test_vq1_reset2.py|TestVisualizerLoop::test_renderer_and_inspector_are_separate",
    "apps/pipeline/tests/test_vqr2b_concept_analysis.py|IsolationTests::test_no_provider_no_dispatch_no_gate_writes",
    "apps/pipeline/tests/test_vqr2b_concept_analysis.py|IsolationTests::test_no_reconstruction_imports",
    "apps/pipeline/tests/test_vqr2b_reconstruction_measurement.py|TestThePremiseGuardRunsBeforeTheVerdict::test_the_floor_and_the_verdict_share_one_arithmetic",
    "apps/pipeline/tests/test_vqr2b_reconstruction_measurement.py|TestTheSilhouetteTruthIsShared::test_the_module_defines_no_second_profile",
})


# --- the census, as code rather than as a number in a report -----------------

class _Scan(ast.NodeVisitor):
    """Names bound to source text, and whether each assert reads one."""

    def __init__(self, text_names, helper_names):
        self.text_names = set(text_names)
        self.helper_names = set(helper_names)
        #: Names bound to a POSITION or COUNT within source text, as opposed to
        #: ``text_names``, which are bound to the text itself. Blind spot 2:
        #: ``i = src.index(a)`` then ``i < j`` is the same claim as
        #: ``src.index(a) < src.index(b)`` and was scored differently.
        self.pos_names: set[str] = set()
        self.asserts: list[bool] = []

    def reads_source(self, node) -> bool:
        if node is None:
            return False
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and sub.id in self.text_names:
                return True
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                if sub.func.attr in self.helper_names or \
                        sub.func.attr == "getsource":
                    return True
                if sub.func.attr in ("read_text", "read"):
                    blob = ast.unparse(sub)
                    # A path that names a NON-source artifact is not a source
                    # read even when `__file__` appears in it — the fixture
                    # load `(Path(__file__).parent / "x.json").read_text()`
                    # is the case that caught this out.
                    if any(f"{s}'" in blob or f'{s}"' in blob
                           for s in _ARTIFACT_SUFFIXES):
                        continue
                    if "__file__" in blob or "SCRIPT" in blob or any(
                            f"{s}'" in blob or f'{s}"' in blob
                            for s in _SOURCE_SUFFIXES):
                        return True
        return False

    def _is_search_call(self, node) -> bool:
        """``<source text>.index(...)`` and friends, as an expression."""
        return (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in _SEARCH_METHODS
                and self.reads_source(node.func.value))

    def _is_position(self, expr) -> bool:
        """A position or a count WITHIN source text, however it is spelled.

        `src.index(a) < src.index(b)`, `src.count(a) == 1` — a claim about
        WHERE or HOW OFTEN a literal appears in a file. Still a source-string
        assertion, and still says nothing about behaviour.

        Narrow on purpose, in both directions: an early draft flagged every
        non-membership comparison whose left side touched source text, which
        swept in behavioural equality assertions; tightening it to `.index(`
        alone then dropped the `.count(` form, which is a real guard.

        The comment this replaces claimed the branch was "keyed on the
        string-search call, not on the comparison operator". IT WAS KEYED ON
        THAT CALL BEING WRITTEN INLINE, which is not the same claim and is
        blind spot 2 — the `pos_names` branch below is the repair. A guard
        that binds the positions to names first reads better and scored zero.
        """
        if isinstance(expr, ast.Name) and expr.id in self.pos_names:
            return True
        return bool(expr is not None and self.reads_source(expr) and any(
            f".{meth}(" in ast.unparse(expr) for meth in _SEARCH_METHODS))

    def _is_source_claim(self, expr) -> bool:
        """Does this expression, anywhere inside it, compare against source?

        Shared by the bare-`assert` and `assertTrue`/`assertFalse` paths so the
        two cannot drift — which is exactly how blind spot 3 got in.
        """
        hit = False
        for sub in ast.walk(expr):
            if not isinstance(sub, ast.Compare):
                continue
            membership = any(isinstance(o, (ast.In, ast.NotIn)) for o in sub.ops)
            if membership and self.reads_source(
                    sub.comparators[0] if sub.comparators else None):
                hit = True
            elif self._is_position(sub.left):
                hit = True
        return hit

    def visit_Assign(self, node):
        if self.reads_source(node.value):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    self.text_names.add(t.id)
        if self._is_search_call(node.value):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    self.pos_names.add(t.id)
        self.generic_visit(node)

    def visit_Assert(self, node):
        self.asserts.append(self._is_source_claim(node.test))
        self.generic_visit(node)

    def visit_Call(self, node):
        """``self.assertX(...)``. Blind spot 3, and the widest of the three.

        Dispatched on the METHOD's shape rather than on the argument's, because
        which position must read source is a property of the assertion:
        ``assertIn(needle, haystack)`` puts the container second, while
        ``assertLess(i, j)`` puts positions in both.
        """
        fn = node.func
        if isinstance(fn, ast.Attribute):
            args = node.args
            if fn.attr in _MEMBERSHIP_METHODS and len(args) >= 2:
                self.asserts.append(self.reads_source(args[1]))
            elif fn.attr in _COMPARE_METHODS:
                self.asserts.append(
                    any(self._is_position(a) for a in args[:2]))
            elif fn.attr in _TRUTH_METHODS and args:
                self.asserts.append(self._is_source_claim(args[0]))
        self.generic_visit(node)


def _source_helpers(node) -> set[str]:
    """Non-test methods that RETURN file text. The first pass of this census
    had no such notion and therefore missed both guards §Y2(a) names."""
    out = set()
    probe = _Scan((), ())
    for stmt in node.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and \
                not stmt.name.startswith("test"):
            for sub in ast.walk(stmt):
                if isinstance(sub, ast.Return) and probe.reads_source(sub.value):
                    out.add(stmt.name)
    return out


def _text_names(node, helpers) -> set[str]:
    out, probe = set(), _Scan((), helpers)
    for stmt in node.body:
        if isinstance(stmt, ast.Assign) and probe.reads_source(stmt.value):
            out |= {t.id for t in stmt.targets if isinstance(t, ast.Name)}
    return out


def _is_pure_guard(fn, text_names, helpers) -> bool:
    """EVERY assertion is a literal-in-source claim, and there is one.

    A test that also asserts on behaviour is MIXED, not a guard: §Y2 speaks
    about guards, and widening the definition here would be inventing a
    ruling rather than applying one.
    """
    scan = _Scan(text_names, helpers)
    for stmt in fn.body:
        scan.visit(stmt)
    return bool(scan.asserts) and all(scan.asserts)


def _declared(fn) -> bool:
    return fn.name.startswith(DECLARING_NAME) and \
        DECLARING_MARKER in (ast.get_docstring(fn) or "")


def census() -> dict[str, bool]:
    """``"path|Class::test_name" -> declared?`` for every pure guard found."""
    found: dict[str, bool] = {}
    for path in sorted(APPS.rglob("test_*.py")):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:                             # pragma: no cover
            continue
        rel = str(path.relative_to(APPS.parent))

        def walk(node, prefix, names, helpers):
            helpers = helpers | _source_helpers(node)
            names = names | _text_names(node, helpers)
            for child in node.body:
                if isinstance(child, ast.ClassDef):
                    walk(child, f"{prefix}{child.name}::", names, helpers)
                elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and child.name.startswith("test") \
                        and _is_pure_guard(child, names, helpers):
                    found[f"{rel}|{prefix}{child.name}"] = _declared(child)

        walk(tree, "", set(), set())
    return found


def declarations() -> dict[str, tuple[bool, bool]]:
    """``"path|Class::test" -> (has the name, has the marker)``, for every test
    in ``apps/`` that has EITHER half of a §Y2(b) declaration.

    WI-3F. This is the OTHER count, and it exists because ``census()`` counts
    what the classifier RECOGNISES while §Y2(b) is a rule about what authors
    WRITE. Reading either one as the other is what put the word "fourteen" in
    the docstring of ``TestTheCensusItselfIsNotVacuous.test_it_finds_a_
    meaningful_number_of_guards_overall``, wrong by 8 on the day it shipped.

    THE CROSS-REFERENCE ABOVE WAS MISCAST UNTIL §AV5 and said
    ``test_the_census_itself_is_not_vacuous``, a test-shaped name for what is
    actually a CLASS. Two other docstrings copied it. §AV5 went looking for
    that test to check a number against it, could not find it in the repo, and
    recorded — wrongly, for the length of one measurement — that it had been
    fabricated. It had not: the referent is real, one casing away, and
    ``grep -rn "not_vacuous"`` found it in seconds. AD0(a) cuts both ways, and
    the false reading is left written down here because a docstring that
    records only the corrections that flattered the author is not a record.
    A cross-reference is a claim; this file asserts its numbers and merely
    narrated its names, which is the same asymmetry §Y2 is about.

    It takes no view on whether a test is really a guard, and it must not: a
    test that declares itself under §Y2(b) is one by its author's own
    statement, and the thirteen declared guards this function sees that the
    census does not are the whole point of measuring separately. Keys use the
    census's format so the two are directly comparable.
    """
    out: dict[str, tuple[bool, bool]] = {}
    for path in sorted(APPS.rglob("test_*.py")):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:                                 # pragma: no cover
            continue
        rel = str(path.relative_to(APPS.parent))

        def walk(node, prefix):
            for child in node.body:
                if isinstance(child, ast.ClassDef):
                    walk(child, f"{prefix}{child.name}::")
                elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    named = child.name.startswith(DECLARING_NAME)
                    marked = DECLARING_MARKER in (ast.get_docstring(child) or "")
                    if named or marked:
                        out[f"{rel}|{prefix}{child.name}"] = (named, marked)

        walk(tree, "")
    return out


def _undeclared() -> set[str]:
    return {k for k, declared in census().items() if not declared}


# --- §Y2(b)/(d) in force -----------------------------------------------------

class TestTheRuleIsGeneralAndInForce:
    """§Y2(d) — not scoped to the two tests that prompted it."""

    def test_no_new_undeclared_source_string_guard_enters_the_repo(self):
        """**This is the load-bearing assertion of §Y2.**

        Everything else here is bookkeeping; this is the part that makes the
        rule general rather than a sweep that decays. A guard written anywhere
        in ``apps/`` without a declaring name and docstring fails here, and the
        failure message tells the author what to write.
        """
        new = _undeclared() - REGISTERED_UNDECLARED
        assert not new, (
            "§Y2(b): these tests assert only that a literal is present or "
            "absent in a source file, so each needs a name starting "
            f"'{DECLARING_NAME}' and a docstring containing "
            f"'{DECLARING_MARKER}' that says it asserts nothing about "
            f"behaviour:\n  " + "\n  ".join(sorted(new)))

    def test_the_subject_area_of_this_ruling_is_fully_converted(self):
        """`apps/ire` is where §Y is working, so it carries no backlog. If
        this fails, a guard was added to the container work without a
        declaration — the exact regression §Y2 is about."""
        assert not {k for k in _undeclared()
                    if k.startswith(CONVERTED_AREAS)}

    def test_the_register_only_shrinks(self):
        """A registered entry that no longer exists — converted, renamed or
        deleted — must come OUT of the register. Otherwise the backlog count
        drifts away from the repo and the number stops meaning anything, which
        is the defect this sprint corrected in its own arithmetic."""
        stale = REGISTERED_UNDECLARED - _undeclared()
        assert not stale, (
            "these are registered as undeclared but the census no longer "
            "finds them; remove them from REGISTERED_UNDECLARED:\n  "
            + "\n  ".join(sorted(stale)))

    def test_the_backlog_is_stated_as_a_number_not_as_an_impression(self):
        """§Y2 is NOT fully discharged while this is non-zero, and the count
        is asserted so that saying so stays cheap and stays true.

        58 at WI-G. **50 after WI-S**, which converted the eight `dielines`
        provider guards. The number that matters is the one still standing
        here, not the eight that left.

        **50 -> 52 AT THE CENSUS REPAIR, AND THE BACKLOG DID NOT GROW.** Every
        other move in this file's history was work: a conversion took it down,
        a new undeclared guard would take it up. This move was neither. Two
        guards that predate this file became VISIBLE when the classifier
        learned ``self.assertX``, and §Y2's backlog was 52 all along while
        this assertion said 50. The honest reading of the whole series is
        therefore that the earlier numbers were floors, not counts, and the
        sentence "§Y2 is NOT fully discharged while this is non-zero" was
        always safe for a reason it did not state — a census that cannot see a
        guard also cannot see that the guard is undischarged.
        """
        # §BH69(1), 2026-09-26: 52 -> 49 — the three supplier-outreach guards left the tree with their test files,
        # removed on the owner's approval (his sentence overruling §BH46(a) for that code); the set is still counted
        # whole, and the census below still finds every guard it names.
        assert len(REGISTERED_UNDECLARED) == 49
        assert len(_undeclared()) == 49


class TestTheCensusItselfIsNotVacuous:
    """A meta-test whose classifier quietly stops classifying goes green and
    stays green. Sprint 9's M3 is the precedent: executed by everything,
    asserted by nobody. These pin the census to known-true facts so it cannot
    become an empty loop that passes."""

    def test_it_finds_the_two_guards_section_y2_names(self):
        found = census()
        base = ("apps/ire/tests/test_container_text_floor.py|"
                "TestTheTableActuallyReachesTheProducer::")
        assert found.get(base + "test_source_guard_the_call_site_literal_is_present") is True
        assert found.get(
            base + "test_source_guard_the_build_literal_precedes_the_measure_literal") is True

    def test_it_finds_a_meaningful_number_of_guards_overall(self):
        """A classifier that broke would most likely return nothing at all.

        **The floor was `>= 60` and WI-S's conversion took the total to 58, so
        this test failed on work that was going the right way.** That is worth
        keeping rather than quietly re-baselining: a floor pinned to the total
        has to be lowered at every conversion, and a threshold that is
        routinely lowered has stopped being a check. It is also the only thing
        that caught the docstring above quoting a declared count from memory.

        So the two halves are pinned differently. The undeclared half is
        already asserted to the digit by ``REGISTERED_UNDECLARED`` and is
        *meant* to fall, so all this needs is a floor loose enough not to
        require editing on every conversion. The declared half is the part
        conversions do not touch, so it is pinned exactly — 6 from WI-G plus
        WI-L's follow-up two. If a conversion ever changes THAT number,
        something has been relabelled rather than replaced, which is the one
        failure mode this register exists to prevent.

        **8 -> 10 at WI-V**, and the distinction the paragraph above draws is
        the whole reason that is allowed. A CONVERSION moving this number
        would mean an undeclared guard had been renamed instead of rewritten,
        and ``REGISTERED_UNDECLARED`` would have fallen by the same amount.
        It did not: it is still 50, asserted two tests above, and §AB4(d)
        holds it there. What happened instead is that WI-V wrote two guards
        that did not exist in any form before —
        ``test_wiv_leading_comparison.py``'s probes for the §AB3(c) comment —
        and declared them on the way in, which is §Y2(d)'s generality doing
        the job it was built for rather than being worked around. A third
        probe in that file declares itself too and is deliberately NOT in
        this count: it reads through ``git show``, the census does not follow
        a subprocess, and inflating the number by hand to include something
        the instrument cannot see would make this assertion an opinion.

        **10 -> 11 at WI-Y**, by the same route and subject to the same test.
        ``REGISTERED_UNDECLARED`` did not fall: it is still 50, and the ire
        backlog is still empty, so nothing was relabelled. The mover is
        ``test_wiy_leading_metric_floor.py``'s probe for the un-wired
        ``product_name``, in a file that did not exist at HEAD, declared on
        the way in rather than caught by the register afterwards.

        And WI-Y hit the blind spot the paragraph above describes for a
        SECOND, unrelated reason, which is recorded because it bounds what
        this number means. That file declares TWO guards; the census sees
        one. ``test_source_guard_the_verdict_holds_no_1_362_literal_to_go_
        stale`` reads its subject through ``ast.get_source_segment`` and its
        first assertion is ``assert code`` — a bare truthiness check that the
        function has an executable body at all. ``_is_pure_guard`` therefore
        scores it ``[False, True, True, True]`` and calls it MIXED. That is
        the classifier being RIGHT by its own definition, not a bug: a test
        asserting something other than a literal-in-source claim is not a
        pure guard, and widening the definition to capture a test that
        declared itself anyway would be inventing a ruling. It is counted
        here as 11, not 12, for the same reason WI-V's third probe was
        counted as 10 and not 11.

        **11 -> 12 at WI-Z**, and this one arrived the OTHER way round, which
        is worth the sentence. The mover is
        ``test_wiz_surface_plan.py``'s ``test_source_guard_the_module_needs_no
        _django_and_no_fonts``, and it was not declared on the way in — it
        went in undeclared, ``REGISTERED_UNDECLARED`` read 51, and
        ``test_the_subject_area_of_this_ruling_is_fully_converted`` named the
        exact test in its failure message. So the register fired on the sprint
        that caused it and the declaration is what cleared it. That is the
        first time in this arc the mechanism has been observed catching
        something rather than being satisfied in advance, and it is recorded
        because §AA's standard is that a guard nobody has seen fire is not
        evidence of anything. ``REGISTERED_UNDECLARED`` is 50 again, by
        declaration and not by relabelling.

        The blind spot recurred a THIRD time in the same file, consistently.
        ``test_wiz_surface_plan.py`` declares TWO guards and the census sees
        one: ``test_source_guard_the_module_holds_no_zone_id_and_no_surface_
        word`` asserts through a helper call and a ``re.search``, neither of
        which is a literal-in-source claim, so it is not classified as a pure
        guard and never reaches the register in either direction. Counted as
        12, not 13, for the reason given twice above.

        **12 -> 12 AT WI-2A, AND THE FLAT NUMBER IS THE FINDING.**
        ``test_wi2a_split_packer.py`` adds TWO guards that satisfy §Y2(b) by
        name and by docstring — ``test_source_guard_the_packer_holds_no_
        ordering_heuristic`` and ``test_source_guard_the_packer_names_no_
        layer_count`` — and the census sees NEITHER. The first asserts a list
        equality against lines filtered out of the source and then loops over
        a tuple of banned substrings; the second parses the module with ``ast``
        and asserts over the module-level assignment names. Both are claims
        about literal source text in every ordinary sense, and neither is a
        literal-in-source claim in the census's sense.

        That is the FOURTH and FIFTH instance of the same blind spot, and the
        pattern is now worth naming rather than re-noting: the classifier
        recognises a guard by the SHAPE of its assertions, so the more
        carefully a guard is written — through a helper, through a filter,
        through the AST — the less likely it is to be counted. The crude
        guards are visible and the careful ones are invisible. That is §AD0(b)
        exactly: an instrument that recognises a thing by the shape of its
        implementation reports on STYLE, and the qualification belongs beside
        the number. ``12`` is therefore not "the number of source-string
        guards in the repo"; it is the number of them written in a way the
        classifier can see.

        **12 -> 12 AT WI-3C, sixth and seventh instances**, and the entry is
        made only to say the pattern did not break: ``test_wix_label_
        construction.py``'s ``test_source_guard_no_caller_hard_codes_the_old_
        baseline`` and ``test_wi3a_unique_column_census.py``'s ``test_source_
        guard_the_classifier_states_that_it_is_syntactic`` both satisfy §Y2(b)
        and neither is visible here. Both go through a helper.

        WHAT WI-3F FOUND WHEN IT WENT TO WRITE THAT DOWN
        ------------------------------------------------
        The sentence that used to close this docstring said the gap was
        "between that and the **fourteen** now declared by name". Fourteen was
        never measured. Parsing the tree at ``e1572a9`` — the commit that
        wrote the word — gives **22**. It was wrong by 8 on the day it shipped.

        The likely construction, stated as inference and not as fact: 12 seen
        by the census, plus the 2 guards WI-2A had just written, equals 14.
        That is a number adjusted by arithmetic instead of re-measured, in a
        docstring whose own opening warns that "a total quoted from memory
        instead of from ``census()``" is how the last one went wrong. The
        warning was correct and did not protect the line beneath it, because
        the census total is ASSERTED and the declared-by-name total was only
        NARRATED. Prose rots; an assertion cannot.

        So WI-3F pins both, in ``TestBothCountsAreMeasuredAndNeitherIsProse``
        below. Measured at that commit, all four from the tool:

        * census-visible declared: **12**
        * declared by §Y2(b) across ``apps/``: **24**
        * half-declarations (name without marker, marker without name): **0**
          and **0** — never previously asserted in either direction
        * ``REGISTERED_UNDECLARED``: **50**, and census-undeclared **50**

        The two counts are now BOTH assertions and the gap between them is
        derived from them rather than typed, so it cannot be stale while they
        are right.

        THE CLASSIFIER IS STILL NOT WIDENED, and deliberately so: widening it
        would re-classify tests across the whole repo and move
        ``REGISTERED_UNDECLARED`` off 50, which sprint 14's invariants hold
        fixed. §AE1 permits that work in ONE commit with a full
        re-classification; this is not that commit. Recorded here so the
        number is read correctly by whoever does open it.

        **12 -> 13 AT WI-3I, and for once the classifier saw it.** Seven
        instances of the blind spot are recorded above; this is the
        counter-instance. WI-3I's rbv3 guard reads
        ``Path(rp.__file__).read_text()`` and asserts a literal ``not in``
        it — the crudest possible shape, written that way because the claim
        genuinely is about the text of the module and nothing subtler would
        have been honest. It is also the FIRST census-visible declared guard
        outside ``apps/ire/``, which refuted a universal two classes below.
        See §AM.

        **13 -> 14 AT §AV3, AND THIS RULE WROTE THE ENTRY ITSELF.** The new
        guard is ``apps/ire/tests/test_av3_brand_string_runtime.py|
        TestTheImportFailsClosed::test_source_guard_no_fallback_literal_behind_
        the_import``. It reads the brand-string runtime module as text and
        asserts the provisional marker is absent from its body — a claim about
        what is WRITTEN, made because a fallback literal is reachable only on
        an import failure and so is not observable at runtime.

        HOW IT ARRIVED IS THE PART WORTH KEEPING. It was first written as
        ``test_there_is_no_fallback_literal_behind_the_import``, and this file
        refused it by name in the same run that took ``REGISTERED_UNDECLARED``
        from 50 to 51. It was renamed and marked, NOT added to the register.
        That is §Y2(b) catching a guard on the way IN — the first entry in this
        block that was not declared voluntarily, and the first evidence that
        the rule works on new code and not only on a cleared backlog.

        It is inside ``CONVERTED_AREAS``, so
        ``VISIBLE_DECLARED_OUTSIDE_CONVERTED_AREAS`` does not move and the
        enumeration two classes below is untouched.

        **14 -> 16 AT THE CENSUS REPAIR, AND THIS IS THE FIRST MOVE IN THE
        BLOCK ABOVE THAT NO AUTHOR CAUSED.** Every earlier entry names a guard
        somebody wrote. These two were written weeks ago and were already
        declared under §Y2(b); the classifier simply began to see them. That
        makes the distinction this docstring draws — a conversion must not move
        this number, only new declared guards may — incomplete rather than
        wrong. A THIRD cause exists: the instrument's reach changing. It is
        distinguishable from the other two by ``REGISTERED_UNDECLARED``, which
        moved UP by two in the same act instead of down.

        **16 -> 18 AT §BH55 PHASE 4, AND BOTH ARE THE FIRST CAUSE, NOT THE
        THIRD.** Two guards written and declared in the same act — the colour
        dict's, in ``apps/pipeline/tests/test_container_target.py`` — so this
        is the ordinary move this docstring describes: an author wrote them,
        the classifier saw them at once, and ``REGISTERED_UNDECLARED`` did not
        move (still 52, still the same set). The distinction the census repair
        made incomplete is intact here: the instrument's reach did not change.
        They sit OUTSIDE ``CONVERTED_AREAS``, which §Y2(b) permits and
        ``VISIBLE_DECLARED_OUTSIDE_CONVERTED_AREAS`` now names — the third and
        fourth entries in an enumeration that was written precisely because
        "there are none outside apps/ire" was a description wearing an
        invariant's clothes.
        """
        found = census()
        assert len(found) >= 30, len(found)
        assert sum(1 for declared in found.values() if declared) == 18

    def test_it_does_not_classify_a_behavioural_test_as_a_guard(self):
        """The other direction: over-classifying would force declarations onto
        tests that assert real behaviour, and the register would fill with
        tests doing exactly the right thing."""
        found = census()
        assert not any("test_one_run_one_size_and_the_method_decides" in k
                       for k in found)
        assert not any("test_the_refused_floor_is_not_in_force_at_the_gate" in k
                       for k in found)

    def test_a_read_of_a_produced_record_is_not_a_source_read(self):
        """The distinction that took the count from 94 to 62. Asserting on a
        record the code under test WROTE is a behavioural assertion about the
        writer; only reads of Python/JS/template source are guards."""
        scan = _Scan((), ())
        assert scan.reads_source(ast.parse(
            "Path(mod.__file__).read_text()", mode="eval").body) is True
        assert scan.reads_source(ast.parse(
            "json.loads((out / RECORD_NAME).read_text())",
            mode="eval").body) is False

    def test_a_fixture_path_built_from_dunder_file_is_not_a_source_read(self):
        """Correction 3→4, first half. ``__file__`` appearing ANYWHERE in the
        expression used to be enough, so a JSON fixture loaded relative to the
        test file counted as source and dragged a purely behavioural test
        (``test_container_contract.test_surfaces_match_golden``) into the
        register."""
        scan = _Scan((), ())
        assert scan.reads_source(ast.parse(
            '(Path(__file__).parent / "fixtures" / "x.json").read_text()',
            mode="eval").body) is False

    def test_counting_a_literal_in_source_is_still_a_source_assertion(self):
        """Correction 3→4, second half. ``src.count(lit) == 1`` asks how often
        a literal appears in a file. Narrowing the ordering rule to ``.index(``
        dropped it, which would have quietly excused a real guard."""
        scan = _Scan(("src",), ())
        scan.visit(ast.parse('assert src.count("a / b") == 1').body[0])
        assert scan.asserts == [True]

    def test_an_equality_on_behaviour_is_not_swept_in_by_that(self):
        """The complement, because the ``.count(`` rule keys on a method call
        and not on the operator: an ordinary equality must stay behavioural
        even when the test elsewhere reads source."""
        scan = _Scan(("src",), ())
        scan.visit(ast.parse("assert widget.surfaces() == expected").body[0])
        assert scan.asserts == [False]


class TestADeclarationSaysBothThings:
    """§Y2(b) requires the name AND the docstring. Either alone leaves half
    the defect: a bare docstring leaves the misleading name in the survivor
    report, and a bare name does not say what the limit is."""

    def _fn(self, src):
        return ast.parse(src).body[0]

    def test_name_alone_is_not_a_declaration(self):
        assert _declared(self._fn(
            'def test_source_guard_x():\n    """Checks a thing."""')) is False

    def test_docstring_alone_is_not_a_declaration(self):
        assert _declared(self._fn(
            'def test_x():\n    """SOURCE-STRING GUARD."""')) is False

    def test_both_together_are(self):
        assert _declared(self._fn(
            'def test_source_guard_x():\n    """SOURCE-STRING GUARD."""')) is True


# --- WI-3F: both counts, measured -------------------------------------------

class TestBothCountsAreMeasuredAndNeitherIsProse:
    """WI-3F. The repair for a number that rotted in a docstring.

    Two different quantities live in this module and they are not the same
    quantity:

    * how many source-string guards the CLASSIFIER can see (``census()``),
      which is a statement about the style the guard was written in; and
    * how many tests DECLARE themselves under §Y2(b) (``declarations()``),
      which is a statement about what authors wrote.

    Only the first was ever asserted. The second was narrated in prose as
    "fourteen", was 22 when the word was written, and nothing failed. A number
    that only appears in a sentence has no instrument behind it and will be
    wrong the first time anything moves — §AD0(a), a prediction about a count
    is not a measurement of it, applied to a count that was never even a
    prediction.

    So both are pinned here, and the GAP between them is derived rather than
    typed. When a guard is added, the message says which quantity moved. That
    is the whole design: a single assertion over a single number is what let
    14 and 22 coexist.

    **The sentence above used to read "exactly one of these fails", and §AM4
    records that WI-3I refuted it.** There are three cases, not two, and only
    two had ever occurred:

    * an UNDECLARED guard moves the register alone;
    * a DECLARED but census-invisible guard moves ``declarations()`` alone;
    * a guard that is declared AND census-visible moves BOTH, and both tests
      fail together.

    The third had never happened, so the sentence was true of everything
    observed and false as a rule — in the docstring of the class built to stop
    numbers rotting in prose, which is the joke and also the point. It is
    corrected in place rather than deleted, with the false words quoted here so
    the correction is auditable against the original. The design claim survives
    the case analysis; only the arithmetic in it was wrong.
    """

    #: §AM3. The census-visible declared guards that live OUTSIDE
    #: ``CONVERTED_AREAS``, by name. This replaces an ``assert all(...)`` that
    #: said there were none — see the docstring below for why that was a
    #: description of the present wearing an invariant's clothes.
    VISIBLE_DECLARED_OUTSIDE_CONVERTED_AREAS = (
        # §BH55 Phase 4 — the colour dict's two, declared on the way in. First because the comparison is against
        # `sorted(...)`: this tuple's order is the sort's, not the order the entries were written.
        "apps/pipeline/tests/test_container_target.py|"
        "PipelineHandoffColourTests::"
        "test_source_guard_the_native_handoff_reads_the_spec_colours",
        "apps/pipeline/tests/test_container_target.py|"
        "PipelineHandoffColourTests::"
        "test_source_guard_the_rebind_still_discards_a_computed_value",
        "apps/pipeline/tests/test_palette_statistics.py|"
        "GuardedCommitTests::"
        "test_source_guard_the_ledger_is_staged_between_dry_run_and_commit",
        "apps/pipeline/tests/test_rbv3_review_package.py|"
        "TestTheHonestyFieldsAreRequiredNotDefaulted::"
        "test_source_guard_the_banner_sample_is_text_that_is_drawn",
    )

    def test_the_classifier_sees_sixteen_and_that_is_a_claim_about_style(self):
        """The census-visible declared count, asserted from the other side of
        the arithmetic in ``test_the_gap_is_derived_from_the_two_and_not_typed``
        so that the two cannot be edited apart by hand.

        **THE OPENING LINE USED TO READ "Same 13 as ``test_the_census_itself_
        is_not_vacuous``" AND BOTH HALVES OF IT WERE WRONG.** The number said
        13 while the assertion four lines down said 14 — §AV3 moved the
        assertion and left the prose, in the one file whose entire subject is
        prose drifting from assertions. The name was a miscast reference to the
        CLASS ``TestTheCensusItselfIsNotVacuous``; see ``declarations()``. Both
        corrected at §AV5, and the false text is quoted rather than deleted so
        the correction is auditable.

        §AD0(b): the qualification travels with the number. This is not "the
        guards in the repo", it is the guards written crudely enough to be
        recognised by shape.

        **12 -> 13 AT WI-3I, AND THE CLAUSE BELOW USED TO BE A UNIVERSAL.**
        It read ``assert all(k.startswith("apps/ire/") for k in seen)``, and
        its message said that a visible declared guard elsewhere meant
        ``CONVERTED_AREAS`` had moved. ``CONVERTED_AREAS`` did not move.
        ``REGISTERED_UNDECLARED`` is still 50 and still the same SET, asserted
        two tests below, so nothing was relabelled. What happened is §Y2(d)
        working: WI-3I's rbv3 repair needed a guard to hold a removed
        expression out of the module, and it was declared on the way in — in
        ``apps/pipeline/``, which is not converted and is not required to be.

        The universal conflated two sets that were only accidentally equal:
        where the retroactive backlog was CLEARED, and where declared guards
        LIVE, which §Y2(b) makes the whole repo. They agreed for exactly as
        long as nobody wrote a visible declared guard outside ``apps/ire/``.
        That is a fact about what had been written so far, promoted to an
        ``assert all``. It penalised the behaviour the rule wants and it would
        have fired on the first correct act.

        §AD0(a) says a prediction about a count is not a measurement of it.
        The corollary this adds, and the reason §AM exists: **a description of
        the present is not a law about the future**, and ``assert all`` cannot
        tell them apart. An enumeration can — it says what is true without
        claiming it is all that can ever be true.

        The failure mode the universal was reaching for loses no coverage.
        ``test_the_register_and_the_census_agree_on_fifty_two`` asserts set
        equality against the register and
        ``test_the_subject_area_of_this_ruling_is_fully_converted`` asserts the
        converted area holds no undeclared guard; any widening of
        ``CONVERTED_AREAS`` fails both. See §AM3.

        **13 -> 14 AT §AV3**, both counts moving together. The enumeration
        below did NOT move: the new guard is in ``apps/ire/tests/``, inside
        ``CONVERTED_AREAS``. (§AV3 delegated this story to a test that does not
        exist under that name, which meant it was recorded nowhere; it is
        written out here at §AV5 instead.)

        **14 -> 14 AT §AV5, AND THAT IS THE ENTRY WORTH READING.** The declared
        count moved 26 -> 27 and this one did not, which is the first time the
        two have come apart — the case the sibling test's docstring had called
        "the interesting case" while recording that it had never yet happened.
        The new guard reads ``tools/guarded_commit.sh``. TWO independent blind
        spots keep it invisible, and they compose, so neither alone explains
        it:

        1. ``_SOURCE_SUFFIXES`` is ``('.py', '.js', '.html', '.jsx')``. A shell
           script is not source to this instrument, though it is the commit
           path itself.
        2. The ``_SEARCH_METHODS`` branch requires the ``.index(`` call to
           appear LITERALLY on the left of the comparison. The guard binds
           ``invoke = body.index(...)`` and ``tier2 = body.index(...)`` first,
           so the left side unparses to a bare Name.

        Measured, not inferred: adding ``.sh`` to ``_SOURCE_SUFFIXES`` and
        re-running ``census()`` leaves this number at 14. It flips the two
        membership asserts to True and leaves ``invoke < tier2`` False, and
        ``_is_pure_guard`` requires ALL asserts to be source claims. Fixing
        only the suffix would have looked like a fix and changed nothing.

        Blind spot 2 is the sharper one, and it indicts the comment above
        ``_SEARCH_METHODS`` that says the branch is "keyed on the string-search
        call, not on the comparison operator". It is keyed on that call being
        written INLINE. The guard used the inline form first, failed
        ``8950 < 2569`` because the first textual "TIER_2" is a comment 140
        lines above the block that runs it, and was refactored to named
        intermediates to fix it. **The refactor that made the guard correct is
        the refactor that made it invisible here** — the instrument scores the
        clearer form lower, which is AD0(b) pointing inward.

        NEITHER IS REPAIRED HERE, and that is a decision rather than an
        omission. The gap is this design's product, not its defect: a declared
        guard the classifier cannot see is exactly what the gap counts, and the
        one honest instance the file has ever had is worth more standing than
        absorbed. Widening the classifier on the tranche whose own test is the
        sample would be fitting the instrument to the sample — AD0(b) in the
        mirror. Proposed as separate work; §AC forbids chaining it here.

        **A THIRD BLIND SPOT, AND "THE ONE HONEST INSTANCE" IS NOW TWO.** That
        phrase is quoted rather than corrected in place, on this file's own
        discipline. The second instance arrived with the ledger-staging fix to
        ``guarded_commit.sh``; its guard is declared, reads the same shell
        script, and is invisible here for a reason neither 1 nor 2 explains:

        3. ``visit_Assert`` fires on ``ast.Assert`` ONLY. That guard sits in a
           unittest-style class and asserts through ``self.assertLess``, which
           is an ``ast.Call``. ``scan.asserts`` therefore stays empty, and
           ``_is_pure_guard`` requires ``bool(scan.asserts)``.

        Measured, not inferred, and this is the sharpest of the three: adding
        ``.sh`` to ``_SOURCE_SUFFIXES`` leaves this number at 14 with the new
        guard STILL invisible. Its scale is not one guard — **58 of the 369
        test files under ``apps/`` contain no bare ``assert`` anywhere (16%)**.
        So 14 is a measurement of the pytest-styled corner of this repository
        and never was a measurement of the whole. Blind spots 1 and 2 are
        properties of one guard; 3 is a property of the instrument, and it is
        the one that should worry a reader.

        **TWO CLAIMS IN THE PARAGRAPHS ABOVE SHIPPED FALSE AT 4cda10f, AND
        BOTH ARE QUOTED HERE RATHER THAN EDITED OUT.**

        The first was an inference dressed as a measurement. It read: "so 3 is
        independent of 1 and sufficient on its own", resting on the sentence
        before it, which is true. It does not follow, and unlike the other
        corrections here the CONCLUSION is false too. Holding the count at 14
        while adding ``.sh`` shows only that 1 alone is insufficient; blind
        spot 2 is still in force in that configuration, so the experiment
        cannot separate 2 from 3 at all.

        Measured properly — all eight subsets, each fix switched off in turn
        and ``census()`` re-read — the count is:

        ==========  ==========  ==========  =====  =============================
        1 (``.sh``) 2 (pos)     3 (unittest) count  what becomes visible
        ==========  ==========  ==========  =====  =============================
        no          no          no             14  (baseline)
        YES         no          no             14  nothing
        no          YES         no             14  nothing
        no          no          YES            14  nothing
        YES         no          YES            14  nothing
        YES         YES         no             15  the §AV5 guard
        no          YES         YES            15  the ledger guard
        YES         YES         YES            16  both
        ==========  ==========  ==========  =====  =============================

        NO FIX MOVES THIS NUMBER ALONE, and 3 alone least of all — the opposite
        of what was claimed. What the lattice shows instead is sharper: **2 is
        necessary for every movement and sufficient for none**, and the two
        invisible guards need DIFFERENT partners for it. The §AV5 guard needs
        1+2; the ledger guard needs 2+3 and does not need 1 at all, because it
        builds its path from ``__file__`` and ``reads_source`` accepts any
        ``read_text`` whose expression mentions ``__file__`` regardless of
        suffix. So blind spot 1 never applied to the ledger guard, and only the
        three together clear both.

        THAT TABLE REPLACED A SENTENCE READING "NO PROPER SUBSET OF THE THREE
        MOVES THIS NUMBER", written in this docstring, in the paragraph
        immediately after the one condemning unmeasured counts, and false —
        two proper subsets move it to 15. It was caught by running the eight
        cases rather than the four that had been run. Recorded because the
        interval between stating a rule and breaking it was one paragraph, and
        because what caught it was not care but the measurement itself.

        The second was a cost estimate with no measurement behind it: "teaching
        the scanner ``self.assertX`` would reclassify tests across 58 files".
        MEASURED, THE ANSWER IS **2 TESTS IN 2 FILES** — an overstatement of
        29x, and it was the stated §AC justification for declining the repair.
        The 58 is a real number measuring a real thing; it is the population
        where the blind spot COULD bite, and it was reported as the population
        where it DOES. That is the same error shape as the two failed ledger
        criteria in the same commit: a proxy that measures a superset, read out
        as the quantity itself. Third instance in one session, so it is a habit
        rather than an accident, and the rule it earns is that a count of
        affected things must be produced by counting them.

        **ALL THREE REPAIRED HERE, AND "NEITHER IS REPAIRED HERE" ABOVE IS
        SUPERSEDED RATHER THAN WRONG** — it was a true report of the §AV5
        decision, taken when the cost was believed to be 29x what it is.

        The objection recorded with that decision does not depend on the cost
        and had to be answered on its own terms: widening the classifier on the
        tranche whose own test is the sample is fitting the instrument to the
        sample, AD0(b) in the mirror. The answer is that a widened classifier
        which is CORRECT ON SAMPLES THE AUTHOR DID NOT WRITE is not fitted to
        the author's. The repair pulls in four entries; two are the declared
        guards it was built to see, and the other two are strangers:

        * ``test_characterization_protocol.py|CloseoutBarTests::test_the_
          mirrored_camera_angles_match_the_production_script`` — reads
          ``palt_p1_m4b_evidence.SCRIPT`` and asserts a formatted az/el literal
          is IN it. A source-string guard by any reading of §Y2.
        * ``test_palette_profile_offset.py|CorrectedTrayTests::test_no_blender_
          boolean_dependency`` — reads ``po.__file__`` and asserts ``import
          bpy``, ``bpy.`` and ``modifiers.new`` are absent. The textbook form.

        Both predate this file, neither was written by the author of the
        repair, and BOTH ARE TRUE POSITIVES: the false-positive rate over the
        four newly classified entries is 0/4. The arithmetic also closes with
        nothing left over — 64+4=68, 14+2=16, 50+2=52 — so no existing member
        changed class, and the widening is purely additive.

        The counter-argument that survives is that 0/4 is four samples. It is
        the whole population of what changed, which is the right population for
        "did this widening misclassify anything", and it is still four.

        **THE GAP FALLS 14 -> 12, THE FIRST FALL IN ITS HISTORY.** Its own
        docstring had just recorded two consecutive rises and drawn the
        conclusion that the instrument was "falling further behind the rule it
        implements". That reading was right, and this is what closing the
        distance looks like: the two guards that were declared and invisible —
        §AV5's and the ledger fix's — are now counted, which is the whole
        purpose the gap existed to serve. A gap that only rises is a backlog;
        one that can fall is a measurement.

        **16 -> 18 AT §BH55 PHASE 4**, the same two guards as the count above,
        and the enumeration below moves with them rather than the assertion
        being relaxed: a count and the names behind it are edited in one act or
        they drift, which is this file's whole subject.
        """
        seen = sorted(k for k, declared in census().items() if declared)
        assert len(seen) == 18, "\n".join(seen)
        outside = tuple(k for k in seen if not k.startswith(CONVERTED_AREAS))
        assert outside == self.VISIBLE_DECLARED_OUTSIDE_CONVERTED_AREAS, (
            "a census-visible declared guard outside the converted area is "
            "permitted and is §Y2(d) working — but it is enumerated, not "
            "assumed. Add it to VISIBLE_DECLARED_OUTSIDE_CONVERTED_AREAS, or "
            "if this list has grown long enough to stop being read, convert "
            "the area properly and shrink it (§AM5).\n" + "\n".join(outside))

    def test_twenty_eight_tests_declare_themselves_under_y2b(self):
        """The number the docstring got wrong. Measured, not carried forward.

        History, each from ``ast`` at the named commit rather than from
        memory: **20** at WI-Z (``c4b47ae``), **22** at WI-2A (``e1572a9``,
        the commit whose prose said fourteen), **23** at the head of sprint 15,
        **24** at WI-3F, **25** at WI-3I, **26** at §AV3, **27** at §AV5,
        **28** at the ``guarded_commit.sh`` ledger-staging fix.

        The §AV3 entry is the same one that moved the classifier count two
        tests above, and the two counts moving TOGETHER is the expected
        reading: a guard crude enough to be recognised by shape is also a guard
        that declares itself, so it lands in both.

        **§AV5 IS THE OTHER CASE, AND THIS PARAGRAPH USED TO DENY IT EXISTED.**
        It closed: "The interesting case — the blind spot recorded at length
        above — is a declaration that moves THIS number and not that one, and
        this is not that." §AV5 is exactly that: 26 -> 27 here, 14 -> 14 there.
        The sentence was true when written and is quoted rather than deleted
        because a docstring that anticipated a case, then met it, is worth more
        with both halves visible than with the first half tidied away. The two
        composed causes are measured at the classifier test above, not restated
        here — one place, per §AK3.

        **AND IT HAS NOW HAPPENED TWICE, WHICH RETIRES THE WORD "INTERESTING".**
        27 -> 28 here, 14 -> 14 there, for the ledger-staging guard. When a
        case has occurred once it is an anomaly worth a paragraph; twice, in
        consecutive entries, it is the file's normal behaviour and the prose
        should stop treating it as a surprise. The two instances do NOT share
        a cause — §AV5 turns on how its guard was refactored, the second on
        the assertion dialect of the class it lives in — and that is the
        stronger reading: these counts come apart for unrelated reasons, so
        the pair being separately maintained is load-bearing rather than
        redundant. Causes are measured at the classifier test above, not
        restated here — one place, per §AK3.

        The test's own NAME moved with the number, 27 -> 28, because a name
        carrying a stale count is the exact defect ``test_the_classifier_sees_
        sixteen`` was written to stop. The rename is the sixth time and is
        recorded as routine, not as an event.

        **THE SENTENCE ABOVE SAID "sees_fourteen" UNTIL THE CENSUS REPAIR AND
        WAS ITSELF STALE**, which is the joke the file keeps telling on itself:
        a cross-reference naming a test by its count, inside the sentence
        explaining that names carrying counts go stale. Two references in this
        file broke on that rename and neither was found by reading — ``grep``
        found both in one call. §AV5 recorded the same lesson after a miscast
        reference and drew the conclusion that a cross-reference is a claim.
        The unlearned half is the mechanical one: A COUNT IN A NAME MAKES EVERY
        REFERENCE TO IT PERISHABLE, and nothing in this repository checks
        prose-to-symbol references. Filed rather than fixed — the alternative
        is names without counts, and the counts in these names are what stopped
        the drift this whole file exists to catch.
        """
        full = sorted(k for k, (n, m) in declarations().items() if n and m)
        # §BH55 Phase 4: 28 -> 30, the colour dict's two declared guards. The name of this test carries a count and
        # is therefore perishable — the defect its own docstring files above, unfixed and now one move older.
        # §BH61(c) 2026-09-21: 30 -> 31. `test_container_production_method.py|NothingFallsBackToBottleTests::test_source_guard_no_bottle_fallback_survives_on_the_route` —
        # the guard the owner asked for, that no bottle fallback reappears on the route he walked.
        # §BH64(b) 2026-09-22: 31 -> 32. `test_container_confirmation_2c2e.py|ZoneProfileDivergenceTests::test_source_guard_the_zone_block_is_built_in_exactly_one_place` —
        # the ONE SOURCE the owner ruled, enforced: production holds exactly one line that builds a zone block.
        # §BH64(c) 2026-09-22: 32 -> 33. `test_container_production_method.py|NothingFallsBackToBottleTests::test_source_guard_no_archetype_default_hides_in_a_get_or_an_or` —
        # the shape the owner asked for after the eleventh fallback hid in a `.get()` default, and the FIRST
        # guard in this repository that reads JavaScript, which is where the twelfth and thirteenth were.
        # [His goal of 2026-10-13, (4): "No browser pop-ups anywhere"] 2026-10-13: 33 -> 34.
        # `test_browser_recon_result.py|CalmPageServerTests::test_source_guard_goal_1013_popups_no_script_calls_the_browsers_own_dialogs`
        # — beside the browser tests that hold the behaviour (no dialog raised, every question in the page), the
        # guard that no script the site serves calls the browser's own alert, confirm or prompt again.
        assert len(full) == 34, "\n".join(full)

    def test_no_test_declares_itself_by_half(self):
        """Never asserted before, in either direction, and true today: 0 tests
        carry the name without the marker and 0 carry the marker without the
        name.

        ``TestADeclarationSaysBothThings`` proves ``_declared`` REQUIRES both
        on constructed input. It says nothing about the repo, where a
        half-declaration is the realistic failure — somebody renames a test to
        clear the register and does not write the docstring. That test leaves
        the census as declared under a rule it does not satisfy, and no
        existing assertion notices.
        """
        found = declarations()
        name_only = sorted(k for k, (n, m) in found.items() if n and not m)
        mark_only = sorted(k for k, (n, m) in found.items() if m and not n)
        assert name_only == [], (
            "§Y2(b): declaring name without the SOURCE-STRING GUARD marker:\n"
            + "\n".join(name_only))
        assert mark_only == [], (
            "§Y2(b): marker without the test_source_guard_ name:\n"
            + "\n".join(mark_only))

    def test_the_gap_is_derived_from_the_two_and_not_typed(self):
        """Fourteen declared guards are invisible to the census. That number is
        computed from the two measurements above, so it cannot be the stale
        one — which is exactly what "fourteen" was.

        **READ THE TWO FOURTEENS CAREFULLY: THEY ARE UNRELATED.** As of the
        ledger-staging fix the gap equals the classifier count, 14 and 14, by
        coincidence and not by construction — one is "declared guards the
        census cannot see", the other is "guards the census can see". They
        were 13 and 14 yesterday and will part again on the next entry. This
        note exists because a reader who meets two equal numbers in adjacent
        tests will reach for a relationship, and the honest answer is that
        there is none.

        **12 -> 13 AT §AV5, AND IT WIDENED RATHER THAN MOVING.** Every earlier
        entry in this file moved both counts together, which holds the gap
        still; §AV5 moved the declared count alone, so the gap grew for the
        first time. A gap that only ever holds still is not measuring anything
        — it is two numbers with a constant between them, and nothing would
        have told us which. This is the first evidence that the subtraction is
        load-bearing.

        **13 -> 14 AT THE LEDGER-STAGING FIX, AND ONCE IS NOT A TREND BUT
        TWICE IS.** The second consecutive widening settles what the paragraph
        above could only claim: the gap tracks something real, because it has
        now moved twice for two DIFFERENT reasons, and a constant offset
        cannot do that. It also changes what the number means. A gap that
        grows on consecutive entries is not a backlog being worked off — it is
        an instrument falling further behind the rule it implements, and the
        classifier test now measures why at 58 files rather than at one guard.

        It is also why this assertion is worth more than the two it is derived
        from: had the gap been TYPED, §AV5 would have had three numbers to
        edit and the cheapest honest-looking move would have been to leave this
        one at 12 and call the classifier's blind spot a rounding difference.
        Derivation removes that option. The causes are at the classifier test.

        **14 -> 12 AT THE CENSUS REPAIR. THE FIRST FALL, AND THE PARAGRAPH
        ABOVE PREDICTED THE WRONG SIGN.** It concluded from two consecutive
        rises that the number tracked "an instrument falling further behind
        the rule it implements". The trend reading was right about the cause
        and wrong to treat two points as a direction: what actually happened
        next is that the instrument was taught to see both of the guards it
        had been missing, and the distance closed. A quantity that had only
        ever risen has now fallen, which retires the last reading of it as a
        backlog. It is a distance between a rule and an instrument, and it
        moves in whichever direction the more recent work pushed.

        The note above about the two fourteens can now be read as settled
        rather than as a warning: they were 14 and 14 by coincidence, the
        prediction was that they "will part again on the next entry", and they
        parted to 16 and 12 in opposite directions on that very entry. Kept
        because a prediction that came true is worth as much on the record as
        the two in the classifier docstring that did not.
        """
        visible = {k for k, declared in census().items() if declared}
        full = {k for k, (n, m) in declarations().items() if n and m}
        # §BH61(c) 2026-09-21: 12 -> 13, and it rose because the new guard is DECLARED but not
        # census-VISIBLE — the gap is exactly that distance between the rule and the instrument,
        # and this entry widened it by one.
        # §BH64(b) 2026-09-22: 13 -> 14, the EIGHTH instance of the blind spot the classifier docstring
        # names, and it was predicted before it was measured rather than discovered by the failure:
        # the new guard walks the tree and asserts through `re.search`, so it is a claim about literal
        # source text in every ordinary sense and not one in the census's sense. Written the careful way
        # on purpose — the pattern is that the more carefully a guard is written the less likely the
        # instrument is to count it, and writing it crudely to be counted would be tuning the work to
        # the instrument.
        # §BH64(c) 2026-09-22: 14 -> 15, the NINTH instance and predicted for the same reason as the
        # eighth: the new guard walks two trees and asserts through `re.search`. The pattern the
        # classifier docstring names has now held for nine consecutive entries without a counter-example,
        # which is long enough to stop calling it a blind spot and start calling it the instrument's scope.
        # [his goal of 2026-10-13, (4)] 2026-10-13: 15 -> 16, the TENTH instance, predicted for the same reason as
        # the eighth and ninth: the new guard walks the site's scripts and templates and asserts through a compiled
        # pattern — declared, not census-visible.
        assert len(full - visible) == 16, "\n".join(sorted(full - visible))
        assert len(full) - len(visible) == len(full - visible)

    def test_everything_the_census_calls_declared_really_is(self):
        """The subset that must hold for the gap to mean anything. If the
        census ever calls something declared that a direct parse does not,
        ``_declared`` and §Y2(b) have come apart and both numbers are junk.
        """
        visible = {k for k, declared in census().items() if declared}
        full = {k for k, (n, m) in declarations().items() if n and m}
        assert visible - full == set()

    def test_the_register_and_the_census_agree_on_fifty_two(self):
        """Both fifty-twos, side by side. ``REGISTERED_UNDECLARED`` is a
        committed frozenset and census-undeclared is a measurement; they are
        asserted to be the same set, not merely the same length, because two
        sets of 52 with one swap have the same length.

        **50 -> 52 AT THE CENSUS REPAIR, AND SET EQUALITY IS WHY THAT WAS
        SAFE.** The repair had to add two names to a committed frozenset whose
        comment says additions are the thing this module exists to prevent. A
        length assertion would have been discharged by adding any two strings.
        This one names them: the measurement supplies the set, and the only
        way to make it pass is to write down exactly the two guards the
        widened classifier actually found. See the classifier test for what
        they assert and why an addition here is not a regression.
        """
        # §BH69(1), 2026-09-26: 52 -> 49 — the three supplier-outreach guards left the tree with their test files,
        # removed on the owner's approval (his sentence overruling §BH46(a) for that code); the set is still counted
        # whole, and the census below still finds every guard it names.
        assert len(REGISTERED_UNDECLARED) == 49
        assert _undeclared() == set(REGISTERED_UNDECLARED)

    def test_declarations_does_not_quietly_become_a_second_census(self):
        """``declarations()`` must stay a syntactic reader of names and
        docstrings. If it ever starts judging whether a test is a guard, it
        stops being an independent measurement of the same subject and the
        cross-check above becomes a tautology.
        """
        assert declarations.__code__.co_names.count("_is_pure_guard") == 0
        assert "_Scan" not in declarations.__code__.co_names
