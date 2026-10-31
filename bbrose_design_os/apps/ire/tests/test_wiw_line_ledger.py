"""WI-W (§AB1(e)) — the per-section line ledger, checked against the numbers
the ruling itself quotes.

§AB1(f) states two of these figures in the owner's own words: WARNINGS costs 7
lines and MANUFACTURER 3, "10 of the panel's 16", owed since §B. §AA1's
committed docstring states three more: the panel holds 16 lines at 5.0 pt and
13 at 6.0, and the five non-ingredient sections plus the word INGREDIENTS cost
20 lines at 5.0 and 23 at 6.0.

Those numbers were produced by `back_panel_copy.measure`, which lays out the
whole document at once. This ledger reaches them from the other end — each
section measured ALONE — so the agreement is a cross-check between two paths
and not a restatement of one. `TestTheCostsCompose` is the test that makes that
claim explicit rather than incidental.

THE FONT GOTCHA, WHICH WI-K PAID FOR ALREADY. Naming 'NotoSans' as a string
would work, and would work only because some earlier test in the process had
registered the face as a side effect. Unregistered, `wrap_lines` returns None,
`layout` falls back to one line per field, and every mm below reads as a panel
that got roomier. `_faces()` resolves the way the composer resolves and asserts
it got something, so a measurement that depends on test order fails loudly
instead of passing quietly.
"""
from __future__ import annotations

import inspect
import itertools
import subprocess
import sys
from pathlib import Path

from apps.ire import back_panel as bp
from apps.ire import back_panel_ledger as led
from apps.ire.back_panel_copy import (CITED_EXTERNAL_UNVERIFIED,
                                      OWNER_RULING_IN_REPO, SOURCE_REQUIRED)
from apps.ire.tests.test_wik_back_panel_floor import _X2_COPY

ROOT = Path(__file__).resolve().parents[3]

#: the confirmed BACK_PRINT_ZONE. The budget this ledger is USUALLY asked
#: about, and deliberately not baked in — see `TestTheBudgetIsAParameter`.
ZONE_W, ZONE_H = 22.0, 42.3


def _faces():
    from apps.ire.text_metrics import resolve_metric_faces

    faces = resolve_metric_faces({})
    regular = (faces.get("regular") or (None,))[0]
    bold = (faces.get("bold") or (None,))[0]
    assert regular and bold, "no measurable face — the mm below are not real"
    return regular, bold


def _ledger(sections=None, width=ZONE_W, height=ZONE_H, **kw):
    regular, bold = _faces()
    return led.ledger(_X2_COPY if sections is None else sections,
                      width_mm=width, height_mm=height,
                      regular=regular, bold=bold, **kw)


def _lines(record, heading, floor="5.0"):
    for section in record["sections"]:
        if section["heading"] == heading:
            return section["cost"][floor]["lines"]
    raise AssertionError(f"no section {heading!r}")


class TestTheNumbersTheRulingQuotes:
    """§AB1(f) and §AA1 both quote figures from this document. If the ledger
    disagrees with them, one of the two is wrong and that is a finding — so
    they are asserted rather than assumed to still hold."""

    def test_warnings_costs_seven_lines_and_manufacturer_three(self):
        """§AB1(f), verbatim: "WARNINGS (7 lines) + MANUFACTURER (3 lines) =
        10 of the panel's 16, owed since §B". Both sections are OWNER-SUPPLIED
        strings that have never been supplied; the text measured here is the
        sprint-8 probe's reconstruction, which §AA1(d) makes the authority for
        exactly this purpose."""
        record = _ledger()
        assert _lines(record, "WARNINGS") == 7
        assert _lines(record, "MANUFACTURER") == 3
        assert _lines(record, "WARNINGS") + _lines(record, "MANUFACTURER") == 10

    def test_the_panel_holds_sixteen_lines_at_five_and_thirteen_at_six(self):
        """§AA1's committed figure, and the denominator in "10 of the panel's
        16". Capacity is quoted FOR SIX SECTIONS because the six-section
        document pays five gaps; the ungapped figure is larger and is reported
        separately so the two can never be confused for one another."""
        record = _ledger()
        assert record["capacity"]["5.0"]["lines_held_for_this_many_sections"] == 16
        assert record["capacity"]["6.0"]["lines_held_for_this_many_sections"] == 13
        assert record["capacity"]["5.0"]["lines_held_in_one_section"] == 18
        assert record["capacity"]["6.0"]["lines_held_in_one_section"] == 15

    def test_the_non_ingredient_sections_plus_the_word_cost_twenty_and_twenty_three(self):
        """§AA1: "The five sections that are not the ingredient list, plus the
        word INGREDIENTS itself, already cost 20 lines at 5.0 pt and 23 at
        6.0." Reproduced here from per-section costs, which is a different
        arithmetic reaching the same number."""
        record = _ledger()
        for floor, expected in (("5.0", 20), ("6.0", 23)):
            others = sum(_lines(record, h, floor) for h in
                         ("PRODUCT", "DIRECTIONS", "WARNINGS", "MANUFACTURER",
                          "NET CONTENT"))
            assert others + 1 == expected, (floor, others)


class TestTheCostsCompose:
    """The ledger measures each section ALONE. That is only legitimate if a
    section's line count is independent of what sits beside it — so the claim
    is checked rather than asserted in a docstring."""

    def test_isolated_section_costs_sum_to_the_whole_document_layout(self):
        regular, bold = _faces()
        record = _ledger()
        for floor in ("5.0", "6.0"):
            whole = bp.layout(_X2_COPY, ZONE_W, ZONE_H, size_pt=float(floor),
                              regular=regular, bold=bold)
            isolated = sum(s["cost"][floor]["lines"]
                           for s in record["sections"])
            assert isolated == whole["lines_required"], floor
            assert isolated == record["as_supplied"][floor]["lines_required"]


class TestWhatTheLedgerActuallyFinds:
    """The point of the instrument, stated as tests so it cannot quietly stop
    being true."""

    def test_the_whole_document_fits_neither_floor(self):
        record = _ledger()
        assert record["as_supplied"]["5.0"]["fits"] is False
        assert record["as_supplied"]["6.0"]["fits"] is False

    def test_no_subset_containing_the_ingredient_list_fits_at_either_floor(self):
        """THE FINDING. INGREDIENTS costs 20 lines at 5.0 pt and 26 at 6.0
        against a panel that holds 16 and 13 — so it does not fit ALONE, and
        therefore appears in no fitting combination whatsoever. §AA1 reached
        the same conclusion by deleting everything else; this reaches it by
        enumeration, which also says which combinations DO fit."""
        record = _ledger()
        for floor in ("5.0", "6.0"):
            assert all("INGREDIENTS" not in kept
                       for kept in record["subsets"]["fitting"][floor]), floor

    def test_the_maximal_sets_are_the_ones_an_owner_would_read(self):
        """Five maximal sets at 5.0 pt, four at 6.0 — each of them a real
        answer to "what is the most I can print". Pinned by count and by one
        exact member so a change to the wrap shows up here."""
        record = _ledger()
        maximal = record["subsets"]["maximal_fitting"]
        assert len(maximal["5.0"]) == 5
        assert len(maximal["6.0"]) == 4
        assert ["PRODUCT", "DIRECTIONS", "WARNINGS", "MANUFACTURER"] \
            in maximal["5.0"]

    def test_every_maximal_set_is_genuinely_maximal(self):
        """The property, checked directly against the layout rather than
        against the enumeration that produced it: adding ANY dropped section to
        a maximal set must break the fit. A bug in the subset algebra would
        otherwise show up as an owner being told he can print less than he can.
        """
        regular, bold = _faces()
        record = _ledger()
        for floor in ("5.0", "6.0"):
            for row in record["subsets"]["maximal_fitting_records"][floor]:
                kept = set(row["indices"])
                for extra in range(len(_X2_COPY)):
                    if extra in kept:
                        continue
                    bigger = [_X2_COPY[i] for i in sorted(kept | {extra})]
                    grown = bp.layout(bigger, ZONE_W, ZONE_H,
                                      size_pt=float(floor), regular=regular,
                                      bold=bold)
                    assert grown["fits"] is False, (floor, row["kept"], extra)

    def test_the_enumeration_is_exhaustive(self):
        record = _ledger()
        assert record["subsets"]["subsets_examined"] == 2 ** len(_X2_COPY) - 1


class TestTheBudgetIsAParameter:
    """§AB1(e): "the subsets that fit a given surface budget, which is a
    parameter". The zone's 22.0 × 42.3 is where the question usually gets
    asked; it is not where the answer is hard-coded."""

    def test_a_larger_surface_changes_the_answer(self):
        """§AB0(c)'s negative control. A ledger that reported the same refusal
        whatever surface it was handed would not be measuring the surface, and
        the INGREDIENTS finding above would be an artefact of the instrument
        rather than a fact about the panel."""
        roomy = _ledger(height=400.0)
        assert roomy["as_supplied"]["5.0"]["fits"] is True
        assert any("INGREDIENTS" in kept
                   for kept in roomy["subsets"]["fitting"]["5.0"])

    def test_the_width_is_part_of_the_budget_and_changes_line_costs(self):
        """Width sets the column and therefore the wrap, which is why a line
        cost measured at one width does not transfer to another. Asserted
        because a ledger that ignored width would still look plausible."""
        narrow = _ledger(width=12.0)
        wide = _ledger(width=40.0)
        assert _lines(narrow, "WARNINGS") > _lines(wide, "WARNINGS")

    def test_the_budget_is_echoed_exactly_and_never_scaled(self):
        """§AB1(f) — no layer count is assumed, and the cheapest way to assume
        one silently would be to measure against a budget larger than the one
        supplied.

        THE FIRST VERSION OF THIS TEST ASSERTED ONLY THE FIRST LINE BELOW, and
        a negative control caught that. Doubling the height inside `_layout` —
        the exact defect this test is named for — left `budget_mm` untouched and
        this test green; three OTHER tests failed instead. Echoing a budget is
        not the same claim as measuring against it, and a ledger whose printed
        surface and measured surface disagree is worse than one that is simply
        wrong, because the report looks right. So the measured height is now
        read back out of the record and tied to the supplied one.
        """
        record = _ledger(width=22.0, height=42.3)
        assert record["budget_mm"] == [22.0, 42.3]

        regular, bold = _faces()
        truth = bp.layout(_X2_COPY, 22.0, 42.3, size_pt=5.0, regular=regular,
                          bold=bold)["height_available_mm"]
        measured = {row["fit"][floor]["height_available_mm"]
                    for row in record["subsets"]["subsets"]
                    for floor in ("5.0", "6.0")}
        assert measured == {truth}, measured
        for floor in ("5.0", "6.0"):
            assert record["capacity"][floor]["height_available_mm"] == truth

    def test_nothing_fits_is_reported_rather_than_an_empty_table(self):
        tiny = _ledger(height=2.0)
        assert led.NOTHING_FITS in tiny["codes"]
        assert tiny["subsets"]["fitting"]["5.0"] == []

    def test_an_unenumerable_document_is_refused_not_sampled(self):
        """2**n - 1 subsets. Thirteen sections is 8191 and the next steps are
        worse, so the ledger refuses with a code. A table that had quietly
        stopped being exhaustive would still look like a table."""
        many = [{"heading": f"S{i}", "text": "x"}
                for i in range(led.MAX_SECTIONS_FOR_EXHAUSTIVE + 1)]
        record = _ledger(sections=many)
        assert led.TOO_MANY_SECTIONS in record["codes"]
        assert record["subsets"]["subsets"] == []


class TestItDoesNotDecideWhatIsMandatory:
    """No regulatory text exists in this repository — §AA1 grepped for it. A
    hard-coded mandatory set here would be an executor's judgement printed as
    a fact, which is the defect §AA1(c) is written against."""

    def test_an_unclaimed_section_is_source_required_not_optional(self):
        record = _ledger()
        assert {s["mandatory_state"] for s in record["sections"]} == \
            {SOURCE_REQUIRED}

    def test_a_supplied_claim_is_honoured_with_its_state(self):
        record = _ledger(mandatory_claims={
            "INGREDIENTS": {"state": CITED_EXTERNAL_UNVERIFIED},
            "WARNINGS": {"state": OWNER_RULING_IN_REPO}})
        by_heading = {s["heading"]: s["mandatory_state"]
                      for s in record["sections"]}
        assert by_heading["INGREDIENTS"] == CITED_EXTERNAL_UNVERIFIED
        assert by_heading["WARNINGS"] == OWNER_RULING_IN_REPO
        assert by_heading["PRODUCT"] == SOURCE_REQUIRED

    def test_a_nonsense_claim_does_not_become_a_state(self):
        assert led.mandatory_state("X", {"X": {"state": "DEFINITELY_FINE"}}) \
            == SOURCE_REQUIRED
        assert led.mandatory_state("X", {"X": "MANDATORY"}) == SOURCE_REQUIRED

    def test_each_subset_says_what_it_drops_and_on_whose_authority(self):
        """"Cut with numbers in front of him" means the table has to show the
        cost AND what the cut spends. A subset that dropped a section without
        naming it would be a number with no decision attached."""
        record = _ledger()
        for row in record["subsets"]["subsets"]:
            assert sorted(row["kept"] + row["dropped"]) == sorted(
                s["heading"] for s in record["sections"])
            assert set(row["dropped_states"]) == set(row["dropped"])
            assert row["drops_something_unsourced"] is bool(row["dropped"])


class TestTheThreeProhibitions:
    """§AB1(e): "Do not invent cuts. Do not compress. Do not assume a layer
    count." Each one checked as structure, because a prohibition kept only by
    intention is kept until the next commit."""

    def test_no_section_text_is_altered_by_running_the_ledger(self):
        """No invented cuts and no compression, in the only form that settles
        it: the document handed in is byte-identical afterwards, and every
        subset is a SELECTION over it rather than a rewrite of it."""
        before = [dict(s) for s in _X2_COPY]
        record = _ledger()
        assert [dict(s) for s in _X2_COPY] == before
        headings = {s["heading"] for s in record["sections"]}
        assert headings == {s["heading"] for s in before}

    def test_the_ledger_never_chooses_a_type_size(self):
        """Both floors are reported and neither is preferred. A `recommended`
        or `best` key would be the ledger making the decision it prices."""
        record = _ledger()
        assert set(record["as_supplied"]) == {"5.0", "6.0"}
        assert record["floors_pt"] == [5.0, 6.0]
        flat = repr(sorted(record.keys()))
        assert "recommend" not in flat and "best" not in flat

    def test_no_public_function_takes_a_layer_count(self):
        """§AB1(f) leaves the count unruled and `container_label_construction
        .require_layer_count` raises rather than returning one. A `layers=`
        parameter here would answer in arithmetic what that module refuses to
        answer in words."""
        for name in led.__all__:
            obj = getattr(led, name)
            if not callable(obj) or isinstance(obj, type):
                continue
            params = set(inspect.signature(obj).parameters)
            assert not {"layers", "layer_count", "n_layers"} & params, name

    def test_the_floor_provenance_travels_with_the_numbers(self):
        """§AA's standing rule: 6.0 pt reaches this document only through a
        hand-written fixture, and saying so every time the number is quoted is
        the rule. Imported from `back_panel_copy` rather than restated, so the
        two files cannot drift into two wordings."""
        record = _ledger()
        assert "FIXTURE" in record["floor_provenance"]["6.0"]
        assert record["floor_provenance"]["5.0"]


class TestPurity:
    def test_the_module_needs_no_django_settings_to_be_imported(self):
        """It reaches `back_panel` and `back_panel_copy`, both pure. Run as a
        subprocess rather than asserted about, because the claim is about what
        importing DOES."""
        proc = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, sys.argv[1])\n"
             "import apps.ire.back_panel_ledger as m\n"
             "assert m.SCHEMA.startswith('container_back_panel_line_ledger')\n"
             "print(sorted(k for k in sys.modules if k == 'django'))",
             str(ROOT)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip().endswith("[]"), proc.stdout

    def test_the_subset_algebra_is_plain_combinatorics(self):
        """A sanity floor on the enumeration itself: the count of subsets of
        each size matches the binomial coefficients, so no combination is
        dropped or double-counted."""
        record = _ledger()
        sizes: dict[int, int] = {}
        for row in record["subsets"]["subsets"]:
            sizes[len(row["indices"])] = sizes.get(len(row["indices"]), 0) + 1
        n = len(_X2_COPY)
        for size in range(1, n + 1):
            assert sizes[size] == len(
                list(itertools.combinations(range(n), size)))
