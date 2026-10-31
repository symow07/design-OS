"""§AA1 — the compressed copy, the source behind every cut, and the two floors.

The thing worth testing here is not that a shorter document is shorter. It is
that the cuts which could not be sourced **were not made**, and that the one
which could be sourced was made for a reason a reader can check. §AA1(c) is a
rule about restraint, and restraint is invisible in output — a panel compressed
by taste and a panel compressed by permission produce the same millimetres.
What tells them apart is the record, so the record is what these assert.

Four claims carry the file:

  * **an unsourced cut changes nothing** (`TestAnUnsourcedCutIsNotMade`). The
    three ``SOURCE_REQUIRED`` sections come out of both candidates character
    for character as they went in, and they are worth 4 lines at 5.0 pt — so
    the restraint costs something real and the test says how much;

  * **the citations are checked, in both directions**
    (`TestTheSourcesAreReal`). The one permission claimed to be in this
    repository is looked up in this repository and the licensing phrase found;
    the ones claimed NOT to be are grepped for and their absence asserted. If
    regulatory text ever lands here, the second test fails and the cuts resting
    on it must be reclassified — which is the correct thing to happen;

  * **nothing fits, at either floor, under any candidate**
    (`TestItStillDoesNotFit`), including the deliberately unlawful document
    with every cut applied at once. §AA1(b) ruled the panel keeps blocking and
    this is the measurement that earns the ruling rather than assuming it;

  * **the effect on production output is zero and the reason is checkable**
    (`TestThereIsNoLiveCopyToCompress`). Not asserted from a diff: the live
    section builder is called and four of its sections come back as
    ``CONTENT_VERIFICATION_REQUIRED`` placeholders. There is no INCI list on a
    live sheet to shorten.

The numbers are locked on purpose. They are the deliverable of the work item,
they are quoted in the owner queue, and a metrics change that moves them should
fail here loudly rather than silently making the queue entry wrong.

§Y2 HAS A HOLE AND THIS FILE FELL INTO IT — a finding, not a fix
------------------------------------------------------------------------------
Two guards here are source-string guards under §Y2's own definition, and
``test_wig_source_string_guards`` passed on this file without seeing either.
Its census finds a source read by looking for ``read_text``/``open`` on a
``.py``/``.js``/``.html``/``.jsx``/``.sh`` path bound to a name; these go
through ``git grep`` in a subprocess, so no path is ever opened and no name is
ever bound. The census is not wrong about what it counts — it cannot see this
shape at all.

The suffix list above gained ``.sh`` at the census repair, which fixed three
OTHER blind spots and left this one exactly where it was. Worth stating: a
repair that widens an instrument is not evidence that a known hole in it
closed, and the two get conflated whenever the repair is the more recent news.
Re-measured after it, not assumed — this file still contributes 0 to the
census, and the count of files in the hole is still one.

Measured: **one file in the repo runs a subprocess source scan, and it is this
one.** So the hole has exactly one occupant and the occupant is the executor
who wrote §Y2's enforcement, one sprint after writing it. The two guards are
declared here by hand — renamed to ``test_source_guard_*`` with the marker and
their limits in the docstring — because the rule applies, not because a
mechanism made it apply.

The census is NOT widened here. §AA4(c) forbids chained fixes, WI-S is the work
item whose subject is §Y2's register, and widening the detector is a change to
the count that §AA4(a) freezes. It is written down instead, with its number, so
WI-S inherits a measured defect rather than a suspicion.
"""
import pathlib
import subprocess

import pytest

from apps.ire import back_panel as bp
from apps.ire import back_panel_copy as bpc
from apps.ire import text_metrics
from apps.ire.tests.test_back_panel import _BACK_ZONE, _INCI, _REAL
from apps.ire.tests.test_wik_back_panel_floor import (_X2_COPY,
                                                      _X2_MANUFACTURER,
                                                      _X2_WARNINGS)

#: the confirmed BACK_PRINT_ZONE. Not a number chosen for this test.
PANEL = (_BACK_ZONE["width"], _BACK_ZONE["height"])

REPO = pathlib.Path(__file__).resolve().parents[4]


def _grep(pattern, *pathspec):
    """Whole-word, and untracked files included.

    Both halves were learned the hard way in the same run. Without ``-w`` the
    module-name search matched ``test_back_panel_copy_in_the_strip_is_...``, a
    test METHOD NAME in another file, and reported this module as wired into
    something it has never been imported by. Without ``--untracked`` a search
    for files that must not exist trivially passes for every file that has not
    been committed yet — including, on the first run, the two files under test.
    A guard that cannot see the thing it guards against is not a guard.

    ``pathspec`` narrows the search, and the reason it exists is the third
    lesson from the same run: the import guard below fired on the WI-O entry in
    ``OWNER_REVIEW_QUEUE.md``, which names the module in its provenance list.
    That is the guard working — and it is also the guard claiming more than it
    means, because naming a module in a report is not importing it. Restricting
    that one search to ``*.py`` makes the assertion say what it checks.
    """
    argv = ["git", "grep", "-lw", "--untracked", pattern]
    if pathspec:
        argv += ["--", *pathspec]
    out = subprocess.run(argv, cwd=REPO, capture_output=True,
                         text=True).stdout
    return sorted(out.split())


def _faces():
    faces = text_metrics.resolve_metric_faces({})
    return (faces.get("regular") or (None,))[0], (faces.get("bold") or (None,))[0]


def _report(sections=None, inci=_INCI):
    regular, bold = _faces()
    return bpc.report(_X2_COPY if sections is None else sections, PANEL,
                      regular=regular, bold=bold, inci=inci)


def _measure(sections, size_pt):
    regular, bold = _faces()
    return bpc.measure(sections, PANEL, size_pt, regular=regular, bold=bold)


def _section(sections, heading):
    return next(s for s in sections if s["heading"] == heading)


class TestTheDocumentIsTheReconstructionAndSaysSo:
    """§AA1(d) — 608 is the authority and the five characters stay open."""

    def test_the_document_measured_is_the_608_character_reconstruction(self):
        """If this number moves, every other number in this file is about a
        different document and the owner queue is quoting the wrong one."""
        assert _report()["as_supplied"]["5.0"]["characters_supplied"] == 608

    def test_the_two_owner_owed_sections_are_present_and_unwritten_by_me(self):
        """§AA1(d) — WARNINGS and MANUFACTURER are owner-supplied strings that
        have not been supplied. What is measured here is the sprint-8 probe's
        reconstruction, and no cut in this module rewrites either of them: the
        two that propose to are both SOURCE_REQUIRED."""
        assert _section(_X2_COPY, "WARNINGS")["text"] == _X2_WARNINGS
        assert _section(_X2_COPY, "MANUFACTURER")["text"] == _X2_MANUFACTURER
        proposing = {c["cut_id"] for c in bpc.CUTS
                     if c["section"] in ("WARNINGS", "MANUFACTURER")}
        assert proposing == {"WARNINGS_TO_MANDATORY_MINIMUM",
                             "MANUFACTURER_ADDRESS_ABBREVIATED"}
        assert all(c["source_state"] == bpc.SOURCE_REQUIRED for c in bpc.CUTS
                   if c["cut_id"] in proposing)


class TestAnUnsourcedCutIsNotMade:
    """§AA1(c) — 'where you cannot source the permission, do not make the cut'."""

    @pytest.mark.parametrize("name", [bpc.STRICT, bpc.CITED])
    def test_every_source_required_section_survives_character_for_character(
            self, name):
        """The behavioural form. A module that recorded SOURCE_REQUIRED in its
        table and shortened the section anyway would pass every count in this
        file and fail here."""
        regular, bold = _faces()
        after, _ = bpc.candidate(_X2_COPY, name)
        for cut in bpc.cuts_by_state(bpc.SOURCE_REQUIRED):
            assert _section(after, cut["section"])["text"] == \
                _section(_X2_COPY, cut["section"])["text"]
            assert cut["removes"] in _section(after, cut["section"])["text"]
        assert regular and bold

    @pytest.mark.parametrize("name", [bpc.STRICT, bpc.CITED])
    def test_no_candidate_applies_an_unsourced_or_refused_cut(self, name):
        applied = {r["cut_id"] for r in _report()["candidates"][name]
                   ["cuts_applied"]}
        forbidden = {c["cut_id"] for c in bpc.CUTS
                     if c["source_state"] in (bpc.SOURCE_REQUIRED,
                                              bpc.REFUSED_MANDATORY)}
        assert applied and not (applied & forbidden)

    def test_the_restraint_costs_four_lines_and_the_cost_is_stated(self):
        """A rule that never costs anything is a rule nobody has tested. The
        three unsourced cuts are worth 4 lines of a 16-line panel at 5.0 pt —
        a quarter of the surface, left on the panel because the permission to
        remove it could not be found."""
        savings = {c["cut_id"]: c for c in _report()["cut_savings"]["5.0"]}
        unsourced = [savings[c["cut_id"]]
                     for c in bpc.cuts_by_state(bpc.SOURCE_REQUIRED)]
        assert [s["lines_saved"] for s in unsourced] == [2, 2, 0]
        assert sum(s["lines_saved"] for s in unsourced) == 4
        assert all(s["matched"] for s in unsourced), (
            "an unsourced cut that no longer matches its document would report "
            "a saving of zero and make the restraint look free")

    def test_the_refusal_is_of_something_worth_refusing(self):
        """§AA1(c)'s 'deleting something mandatory is the same defect as a
        lower floor'. The forbidden cut is the LARGEST single saving in the
        table at both floors — which is exactly why it needed refusing in
        writing rather than being left off the list."""
        for floor, expected in (("5.0", 3), ("6.0", 4)):
            savings = _report()["cut_savings"][floor]
            refused = next(s for s in savings
                           if s["source_state"] == bpc.REFUSED_MANDATORY)
            assert refused["lines_saved"] == expected
            assert refused["applied_in_any_candidate"] is False
            assert refused["lines_saved"] == max(s["lines_saved"]
                                                 for s in savings)

    def test_a_cut_that_no_longer_matches_says_so_instead_of_saving_nothing(
            self):
        """A silent no-op is how a compression report overstates itself: the
        millimetres it prints are real millimetres from a real layout, and the
        cut it credits them to never happened."""
        moved = [dict(s, text="Apply sparingly.") if s["heading"] == "DIRECTIONS"
                 else s for s in _X2_COPY]
        _, records = bpc.apply_cuts(moved, ["DIRECTIONS_SHORTENED"])
        assert [r["applied"] for r in records] == [False]
        assert records[0]["codes"] == [bpc.TARGET_NOT_PRESENT]
        assert records[0]["characters_removed"] == 0


class TestTheSourcesAreReal:
    """A citation nobody checked is a citation."""

    def test_the_in_repo_permission_is_in_this_repo_and_says_what_is_claimed(
            self):
        """The one cut this executor may make on its own authority is the one
        the owner licensed by name. That licence is looked up rather than
        remembered."""
        cut = next(c for c in bpc.CUTS
                   if c["source_state"] == bpc.OWNER_RULING_IN_REPO)
        assert cut["cut_id"] == "DIRECTIONS_SHORTENED"
        path = REPO / cut["source"].split(" §")[0]
        assert path.is_file(), f"cited source does not exist: {path}"
        text = path.read_text(encoding="utf-8")
        assert "DIRECTIONS shortened" in text
        assert "### AA1." in text

    def test_source_guard_the_external_citations_are_not_in_this_repo(self):
        """SOURCE-STRING GUARD (§Y2(b)). Greps repo CONTENT for the citation
        string; asserts nothing about behaviour.

        The other direction, and the one that keeps the taxonomy honest.
        CITED_EXTERNAL_UNVERIFIED asserts the text is NOT here; if it ever
        arrives, this fails and those cuts stop being unverifiable — which is
        an improvement that should not happen quietly.

        Its limit, stated because §Y2(c) forbids citing it as more: it proves
        no file CONTAINS the string. Regulatory text could arrive in a PDF, a
        vendored package or an owner's head and this would still pass.
        """
        cited = [c for c in bpc.CUTS
                 if c["source_state"] == bpc.CITED_EXTERNAL_UNVERIFIED]
        assert cited
        # the marker is a constant and not a turn of phrase. The first draft
        # wrote one of these as "NEITHER IS IN THIS REPOSITORY" — the same
        # claim to a reader, invisible to this assertion, and that near-miss is
        # why bpc.NOT_IN_THIS_REPO exists at all.
        assert all(bpc.NOT_IN_THIS_REPO in c["source"] for c in cited)
        # two files, and the second one is this file: a guard that names its
        # own pattern matches itself. That is not a weakness — a THIRD file
        # gaining the citation is what this detects, and that is the event
        # that would make CITED_EXTERNAL_UNVERIFIED the wrong class.
        assert _grep("1223/2009") == [
            "bbrose_design_os/apps/ire/back_panel_copy.py",
            "bbrose_design_os/apps/ire/tests/test_wio_on_pack_copy.py"], (
            "regulatory text has entered the repo; the "
            "CITED_EXTERNAL_UNVERIFIED cuts must be re-examined and may no "
            "longer be unverifiable")

    def test_every_cut_carries_a_state_a_permission_and_a_named_risk(self):
        states = {bpc.OWNER_RULING_IN_REPO, bpc.CITED_EXTERNAL_UNVERIFIED,
                  bpc.SOURCE_REQUIRED, bpc.REFUSED_MANDATORY}
        for cut in bpc.CUTS:
            assert cut["source_state"] in states
            assert cut["permission"] and cut["residual_risk"]
            assert (cut["source"] is None) == \
                (cut["source_state"] == bpc.SOURCE_REQUIRED)

    def test_the_table_contains_cuts_the_executor_wanted_and_did_not_get(self):
        """§AA1(c) exists to produce refusals. A table with none would mean the
        executor found a source for everything it wanted to delete, which is
        the failure mode the clause is written against."""
        assert len(bpc.cuts_by_state(bpc.SOURCE_REQUIRED)) == 3
        assert len(bpc.cuts_by_state(bpc.REFUSED_MANDATORY)) == 1
        assert len(bpc.cuts_by_state(bpc.OWNER_RULING_IN_REPO)) == 1


class TestItStillDoesNotFit:
    """§AA1(b) — the panel keeps blocking, and here is why it must."""

    @pytest.mark.parametrize("floor,lines,over", [(5.0, 39, 47.25),
                                                  (6.0, 48, 86.62)])
    def test_as_supplied_at_both_floors_in_mm_and_lines(self, floor, lines,
                                                        over):
        record = _measure(_X2_COPY, floor)
        assert record["fits"] is False
        assert record["lines_required"] == lines
        assert record["overflow_mm"] == over
        assert record["codes"] == [bp.COPY_EXCEEDS_PANEL]

    @pytest.mark.parametrize("floor,holds", [(5.0, 16), (6.0, 13)])
    def test_the_budget_is_quoted_with_its_section_gaps_paid(self, floor,
                                                             holds):
        """A line budget quoted without the gaps is a budget nobody can spend.
        Six sections pay five gaps — 4.0 mm — before the first line is set, and
        that is very nearly two of the sixteen lines at 5.0 pt."""
        record = _measure(_X2_COPY, floor)
        assert record["sections_supplied"] == 6
        assert record["section_gaps_paid_mm"] == 4.0
        assert record["lines_the_panel_holds"] == holds
        assert record["lines_the_panel_holds_in_one_section"] == holds + 2

    @pytest.mark.parametrize("name", [bpc.STRICT, bpc.CITED])
    @pytest.mark.parametrize("floor", ["5.0", "6.0"])
    def test_no_candidate_fits_at_either_floor(self, name, floor):
        fit = _report()["candidates"][name]["fit"][floor]
        assert fit["fits"] is False
        assert fit["codes"] == [bp.COPY_EXCEEDS_PANEL]

    def test_the_two_candidates_differ_in_characters_and_not_in_millimetres(
            self):
        """The whole sourcing question — does a citation to a regulation that
        is not in this repo count? — is worth 23 characters and exactly zero
        millimetres. That is the answer to give the owner: the ruling they were
        going to be asked for does not change the outcome."""
        report = _report()
        for floor in ("5.0", "6.0"):
            strict = report["candidates"][bpc.STRICT]["fit"][floor]
            cited = report["candidates"][bpc.CITED]["fit"][floor]
            assert strict["characters_supplied"] - \
                cited["characters_supplied"] == 23
            assert strict["height_required_mm"] == cited["height_required_mm"]
            assert strict["lines_required"] == cited["lines_required"]

    @pytest.mark.parametrize("floor,lines,over", [("5.0", 31, 30.317),
                                                  ("6.0", 38, 61.22)])
    def test_breaking_every_rule_in_aa1c_still_does_not_fit(self, floor, lines,
                                                            over):
        """The unlawful document, measured once so the question closes. Every
        cut applied — the three with no source and the mandatory one — and the
        panel is still 30 mm over at the live floor. No sourcing ruling and no
        editorial judgement reaches this."""
        fit = _report()["every_cut_regardless_of_source"]["fit"][floor]
        assert fit["fits"] is False
        assert fit["lines_required"] == lines
        assert fit["overflow_mm"] == over

    @pytest.mark.parametrize("floor,held", [("5.0", 17), ("6.0", 11)])
    def test_the_panel_does_not_hold_the_ingredient_list_alone(self, floor,
                                                               held):
        """The finding. Delete PRODUCT, DIRECTIONS, WARNINGS, MANUFACTURER and
        NET CONTENT — an unlawful panel by any reading — give the whole surface
        to INGREDIENTS, and three of the twenty ingredients still do not fit at
        the floor that ships today. §AA1(a)'s target is not reachable by
        writing."""
        ceiling = _report()["ingredient_ceiling"][floor]
        assert ceiling["ingredients_supplied"] == 20
        assert ceiling["ingredients_held"] == held
        assert ceiling["codes"] == [bpc.CANNOT_HOLD_INCI]

    @pytest.mark.parametrize("floor,tall", [(5.0, 89.55), (6.0, 128.92)])
    def test_the_panel_that_would_hold_it_is_named_in_millimetres(self, floor,
                                                                  tall):
        """Not a proposal — §X2's ban on a new surface stands and this module
        proposes nothing. It is the size of the problem stated in the unit the
        owner's container decision is made in: a 42.3 mm panel would have to be
        roughly twice as tall at 5.0 pt and three times at 6.0."""
        assert _measure(_X2_COPY, floor)[
            "panel_height_that_would_fit_mm"] == tall
        assert PANEL[1] == 42.3


class TestNothingForbiddenHappensOnTheWay:
    """§AA1(b) — no shrink-to-fit, no truncation, no reorder, no floor drop."""

    @pytest.mark.parametrize("name", [bpc.STRICT, bpc.CITED])
    def test_the_sections_keep_their_order_and_their_headings(self, name):
        after, _ = bpc.candidate(_X2_COPY, name)
        assert [s["heading"] for s in after] == \
            [s["heading"] for s in _X2_COPY]

    @pytest.mark.parametrize("name", [bpc.STRICT, bpc.CITED])
    def test_net_content_is_present_in_every_candidate(self, name):
        """§AA1(a) — 'NET CONTENT above all, since that is the section the
        6.0 pt case drops'. It is never cut to nothing; the one cut that
        touches it removes the US declaration and leaves the metric one."""
        after, _ = bpc.candidate(_X2_COPY, name)
        assert _section(after, "NET CONTENT")["text"].startswith("30 ml")

    def test_the_module_names_no_size_below_either_floor(self):
        """A compression module is exactly where a 4.5 would get introduced as
        'nearly 5'. There is no size constant here at all: the floors are the
        two §AA1(e) names and nothing else numeric is a point size."""
        assert bpc.FLOORS == (5.0, 6.0)
        sizes = {v for k, v in vars(bpc).items()
                 if k.endswith("_PT") and isinstance(v, float)}
        assert sizes == {5.0, 6.0}

    def test_the_fixture_floor_is_named_a_fixture_where_it_is_quoted(self):
        """§AA's standing rule. 6.0 reaches this document through a
        hand-written HOT_STAMP record in a test file, and every record that
        quotes the number carries that sentence with it."""
        assert "FIXTURE" in bpc.FLOOR_PROVENANCE[6.0]
        assert "test_back_panel.py" in bpc.FLOOR_PROVENANCE[6.0]
        for floor in ("5.0", "6.0"):
            assert _report()["as_supplied"][floor]["size_provenance"]
            assert _report()["ingredient_ceiling"][floor]["size_provenance"]

    def test_copy_is_preserved_by_the_cutting_itself(self):
        """Every character the candidates remove is removed by a NAMED cut, and
        the arithmetic closes: supplied minus the cuts' own character counts is
        what the candidate document contains. A module that shortened something
        it did not record would fail here."""
        report = _report()
        for name in (bpc.STRICT, bpc.CITED):
            removed = sum(r["characters_removed"]
                          for r in report["candidates"][name]["cuts_applied"])
            assert report["as_supplied"]["5.0"]["characters_supplied"] - \
                removed == report["candidates"][name]["fit"]["5.0"][
                    "characters_supplied"]


class TestThereIsNoLiveCopyToCompress:
    """§AA's rule — the zero-effect sentence, asserted rather than claimed."""

    def test_the_live_section_builder_supplies_placeholders_not_copy(self):
        """Why this work item cannot change an emitted byte, checked at the
        source of the copy rather than inferred from a diff. SIX of the seven
        live sections are CONTENT_VERIFICATION_REQUIRED placeholders — there is
        no INCI list on a live sheet to shorten, and writing one to have
        something to compress is what §AA1(d) forbids.

        It was FIVE until 2026-08-20. This test asserted, in the same breath,
        that the live builder does not supply copy AND that its NET CONTENT
        equals `_REAL`'s — and `_REAL` is a fixture. The assertion that the
        two agreed was true, and what it was actually recording is that a
        MANDATORY QUANTITY DECLARATION was hardcoded on the production path
        and matched the reconstruction character for character. §AK4 ruled
        the literal out; the sixth placeholder is that ruling arriving here.

        The old line is kept below as the shape it must NOT return to,
        because "NET CONTENT agrees with the fixture" is the assertion that
        made the defect look like a passing test for four sprints.
        """
        from apps.pipeline.targets.container import (
            CONTENT_VERIFICATION_REQUIRED, _back_sections_from_record)

        class _P:
            name = "Rose Damascena Serum"

        sections, codes = _back_sections_from_record(_P())
        placeholder = {s["heading"] for s in sections
                       if s["text"] == CONTENT_VERIFICATION_REQUIRED}
        assert placeholder == {"DESCRIPTION", "INGREDIENTS", "DIRECTIONS",
                               "WARNINGS", "MANUFACTURER", "NET CONTENT"}
        assert _section(sections, "PRODUCT")["text"] == _P.name
        # was: == _section(_REAL, "NET CONTENT")["text"] — see the docstring
        assert _section(sections, "NET CONTENT")["text"] != \
            _section(_REAL, "NET CONTENT")["text"]
        assert len(codes) == 6
        assert "CONTENT_VERIFICATION_REQUIRED:net_content" in codes

    def test_his_answer_his_briefs_back_copy_is_his_copy_for_acceptance(self):
        """His answers after 117 was redrawn on his rules (2026-10-02, OWNER_BLOCKER_CLEARANCE.md, transcribed at
        a18911a), answer 3: "My brief's back copy counts as my copy for acceptance." Where his copy channel holds no words
        for a piece and his brief's back copy gives them, the back carries his brief's words, said by their source, and no
        code holds it; a piece neither gives stays the marker with its code; a piece of his brief no slot names follows
        them, his copy too; and without his brief's back copy the back is exactly what it was."""
        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.targets.container import CONTENT_VERIFICATION_REQUIRED, _back_sections_from_record

        class _P:
            name = "Coconut Rose Body Lotion"
        brief = ("Coconut Rose Body Lotion\n\nBack copy: How to use: Smooth over clean skin. / Ingredients: Aqua, Cocos "
                 "Nucifera Oil, Rosa Damascena Flower Water. / Batch code place / Made in UAE\n")
        back = dm.brief_back_copy(brief)
        sections, codes = _back_sections_from_record(_P(), back)
        by = {s["heading"]: s for s in sections}
        his = {s["heading"]: s["text"] for s in back["sections"]}            # his words, as his brief gives them
        assert by["DIRECTIONS"]["text"] == his["How to use"] and by["DIRECTIONS"]["source"] == dm.BRIEF_BACK_COPY
        assert by["INGREDIENTS"]["text"] == his["Ingredients"] and by["INGREDIENTS"]["source"] == dm.BRIEF_BACK_COPY
        assert not {f"{CONTENT_VERIFICATION_REQUIRED}:directions", f"{CONTENT_VERIFICATION_REQUIRED}:ingredients"} & set(
            codes), codes
        assert by["WARNINGS"]["text"] == CONTENT_VERIFICATION_REQUIRED
        assert f"{CONTENT_VERIFICATION_REQUIRED}:warnings" in codes and len(codes) == 4, codes
        assert sections[-1] == {"heading": "", "text": his[""], "source": dm.BRIEF_BACK_COPY}, sections[-1]
        assert _back_sections_from_record(_P(), None) == _back_sections_from_record(_P())
        assert len(_back_sections_from_record(_P())[1]) == 6

    def test_source_guard_this_module_is_named_by_nothing_that_emits(self):
        """SOURCE-STRING GUARD (§Y2(b)). Greps repo CONTENT for this module's
        name; asserts nothing about behaviour.

        The name says *named by* and not *wired into* on purpose. The first
        draft said "wired into nothing that emits", which is a behavioural
        claim checked by a grep — the exact defect §Y2 opens on, in a file
        written by the executor who wrote §Y2's enforcement. It is renamed
        rather than argued for.

        Its limit, per §Y2(c): a module reached by ``importlib``, by a settings
        string or by any name built at runtime would not appear here. What it
        catches is the thing it is for — somebody adding a plain import — and
        the zero-effect claim in the module's docstring rests on the stronger
        fact that WI-O modified no existing file at all.

        ONE Python file mentions this module by name and it is this one. The
        module itself is absent because ``git grep`` searches content and the
        module never names itself — worth stating, because the first version of
        this assertion expected the module to be in the list and was writing
        down an expectation rather than reading a result.

        Scoped to ``*.py`` after it fired on ``OWNER_REVIEW_QUEUE.md``, which
        names the module in WI-O's provenance list. A report that mentions a
        module has not wired it into anything, and a guard that cannot tell
        those apart is the kind §Y2 exists to stop being cited.

        ONE -> THREE at WI-W, and the second assertion is why that is not a
        weakening. WI-W's ledger imports this module's §AA1 vocabulary —
        `SOURCE_REQUIRED` and the rest — rather than restating it, which is the
        right call and which also means the census can no longer be one file.
        Bumping the list and stopping there would have left a real hole: the
        chain `back_panel_copy <- back_panel_ledger <- ?` would be unguarded at
        its new end, and somebody wiring the LEDGER into an emitter later would
        reach this module transitively with this guard still green. So the new
        link is guarded too, and the zero-effect claim now rests on two pinned
        censuses instead of one.

        MEASURED, and the measuring corrected me twice. The first pass used
        ``import .*back_panel_copy`` to tell importers from mentioners and
        reported ONE importer — because `from apps.ire.back_panel_copy import
        (...)` puts the module BEFORE the word `import`, so the ledger's own
        import did not match. A census built on that pattern would have been
        false in the direction that flatters the guard. All three files in the
        first list do import this module; the pattern, not the repo, was wrong.

        The second correction is the limit, stated per §Y2(c) rather than
        engineered away. This is a CONTENT grep, so a module named in a Python
        COMMENT counts. Two entries in the second list are exactly that:
        `test_wio_on_pack_copy.py` names the ledger only in the assertion below,
        and `test_wit_unit_analysis.py` only in the note recording why its
        denominator moved at WI-W. Neither imports it. They are kept in the list
        rather than filtered out, because a filter would be this guard deciding
        which mentions count, and a grep that has started exercising judgement
        is the thing §Y2 opens on. The cost is that a future comment naming the
        module turns this red; the benefit is that a future IMPORT cannot turn
        it anything else. That trade is the guard's whole point.

        Kept to grep and literal lists on purpose. Walking the AST for real
        import statements would be a better instrument and a worse GUARD — §Y2's
        census classifies a test as a source-string guard only when every
        assertion is a literal-in-source claim, so the structured version would
        quietly leave the declared-guard population it is counted in.

        FOUR -> SIX AT WI-Z, and the two additions are different from each
        other in the way this guard cares about.

        `test_wiz_surface_plan.py` genuinely IMPORTS the ledger — it exercises
        `surface_budget`, the §AC2(b) ``(N, B)`` wiring — so it is a real new
        edge. It is a TEST, which is why it is added rather than treated as
        the regression this guard watches for: the claim being protected is
        that no EMITTER reaches this copy, and a test calling the ledger is
        the mechanism by which the ledger stays measured. If a file under
        `targets/` or an `emit_*` module ever appears in this list, that is
        the failure, and the list is literal so it has to be looked at.

        `test_wiz_zone_contract.py` is the mention case the paragraph above
        already describes: it names the ledger inside a list of file PATHS it
        scans for zone names, and does not import it. Kept in, unfiltered, for
        the reason given — a filter would be this guard deciding which
        mentions count.

        THE CHAIN DID NOT LENGTHEN, which is the thing worth checking and is
        not visible from the list alone. WI-Z's other new module,
        `surface_plan`, is imported BY the ledger and imports nothing; the
        arrow points down, not up. So `back_panel_copy <- back_panel_ledger`
        still terminates where it did, and nothing reaches this copy through
        the new file. That is why `surface_plan` needs no census of its own
        here and why the first assertion below is unchanged.

        SIX -> SEVEN AT WI-2A, AND THIS GUARD CAUGHT A REAL DEFECT ON THE WAY.
        §AC3's `back_panel_packer` arrived importing `FLOORS` from this copy
        module to default a `floors=` argument it then never read. That is a
        genuine new edge into the copy — the exact regression the first
        assertion exists to catch — and it was created by a vestigial parameter
        copied from the ledger's signature. The guard went red, the parameter
        and the import were both deleted, and the packer now prices ONE size
        per call, which is what it always actually did.

        What remains is a MENTION, not an edge: the packer's docstring records
        the removed import so the next person to reach for a `floors=` argument
        reads why it is not there. Kept unfiltered, on the same principle as
        `test_wiz_zone_contract.py` above — this file does not get to decide
        which mentions count. So the chain did NOT lengthen at WI-2A either:
        `back_panel_copy <- back_panel_ledger` still terminates where it did,
        and the packer reaches the ledger for `capacity` only, which points
        down and away from the copy.

        FOUR -> SIX AT WI-3H, AND IT FIRED TWICE — the second time on the
        executor's own arithmetic. `tools/reserved_copy.py` arrived naming
        this module in its docstring and turned this guard red on the run
        that first built it. That much was expected, and the list was edited
        to FIVE. The edit was WRONG, and this guard is why that is a
        sentence and not a silent defect: the same work item also added
        `apps/ire/tests/test_wi3h_reserved_copy.py`, which names this module
        at line 263 inside the pinned assertion of the guard's own THREE
        unresolved blind spots. I counted the file I was thinking about and
        not the files that exist. §AD0(a) — a prediction about a count is
        not a measurement of it — and the number is now the one `git grep`
        returned rather than the one I expected.

        Both additions are MENTIONS and neither is an edge. The tool imports
        nothing from here; it reads `apps/` as TEXT through `ast.parse`, so
        importing this module would change what it is. The test names a file
        PATH in a literal set, which is the `test_wiz_zone_contract.py` case
        already described above. The tool is also the opposite of an emitter
        — it is the instrument that refuses when reserved copy is
        unregistered — but that argument is exactly the one this guard
        exists to not accept on trust, so both entries go in the literal
        list unfiltered like the three before them. The chain did NOT
        lengthen at WI-3H: `back_panel_copy <- back_panel_ledger` still
        terminates where it did.

        SIX -> SEVEN AT §AV2, and it is a MENTION of the same kind as WI-3H's
        two. `tools/brand_strings.py` is the §AE2(c) sibling guard; it names
        this module once, in the comment pinning `RESERVED_COPY_BLIND_SPOT`,
        which records that "30 ml" is a registered reconstruction pinned to
        `apps/ire/back_panel_copy.py` and has nevertheless travelled to a
        second file unrefused. So the mention exists to describe a hole in
        `reserved_copy`'s cover of THIS module — the opposite of an edge into
        it.

        It imports nothing from here, and cannot: like `reserved_copy` it
        reads `apps/` as TEXT through `ast.parse`, so importing the copy would
        change what the instrument is. The chain did NOT lengthen at §AV2 —
        `back_panel_copy <- back_panel_ledger` still terminates where it did.
        """
        assert _grep("back_panel_copy", "*.py") == [
            "bbrose_design_os/apps/ire/back_panel_ledger.py",
            "bbrose_design_os/apps/ire/back_panel_packer.py",
            "bbrose_design_os/apps/ire/tests/test_wi3h_reserved_copy.py",
            "bbrose_design_os/apps/ire/tests/test_wio_on_pack_copy.py",
            "bbrose_design_os/apps/ire/tests/test_wiw_line_ledger.py",
            "bbrose_design_os/tools/brand_strings.py",
            "bbrose_design_os/tools/reserved_copy.py"]
        #: SIX -> EIGHT AT WI-2A. Both additions are real edges and both point
        #: at the LEDGER, which is the direction that is allowed to grow: the
        #: ledger is the thing that measures, and being measured by more
        #: callers is what it is for. `back_panel_packer.py` imports it inside
        #: `capacity_for_pieces` so that the gap charge is derived in ONE place
        #: — two modules each deriving it from the panel dimensions is two
        #: modules that can come to disagree. `test_wi2a_split_packer.py`
        #: imports it to run the mandated negative control, which compares the
        #: packer's line arithmetic against the ledger's millimetre verdict on
        #: all 63 subsets. Neither reaches the copy; see the paragraph above.
        assert _grep("back_panel_ledger", "*.py") == [
            "bbrose_design_os/apps/ire/back_panel_ledger.py",
            "bbrose_design_os/apps/ire/back_panel_packer.py",
            "bbrose_design_os/apps/ire/tests/test_wi2a_split_packer.py",
            "bbrose_design_os/apps/ire/tests/test_wio_on_pack_copy.py",
            "bbrose_design_os/apps/ire/tests/test_wit_unit_analysis.py",
            "bbrose_design_os/apps/ire/tests/test_wiw_line_ledger.py",
            "bbrose_design_os/apps/ire/tests/test_wiz_surface_plan.py",
            "bbrose_design_os/apps/ire/tests/test_wiz_zone_contract.py"]
