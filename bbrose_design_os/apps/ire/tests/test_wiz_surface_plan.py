"""WI-Z / §AC2(b) — the abstract ``(N, B)`` plan, and the ledger's half of it.

§AC2(b): *"The ledger and the construction model take `(N, B)` — N surfaces,
budget B per surface — with N unbound. Surfaces are addressed positionally as
`surface[0] … surface[N-1]`. No zone name appears anywhere in the multi-layer
path."*

Two subjects. `apps/ire/surface_plan.py` is the form on its own — pure, no
geometry, no fonts. `back_panel_ledger.surface_budget` is the wiring that
measures B off a real surface and hands `(N, B)` over. They are tested apart
because the point of splitting them is that the thing which counts lines and
the thing which counts surfaces cannot quietly become one thing.

THE ASSERTIONS THAT LOOK LIKE PEDANTRY AND ARE NOT
---------------------------------------------------
Three of the tests below assert that a function REFUSES. `plan()` with no N,
`plan()` with N below one, `plan()` with a negative budget. §AB1(f) says the
layer count is not yet a number and *"nothing may be built assuming exactly
two"*, and the only mechanism that keeps that true through an import chain is
that the bottom of the chain has no default to inherit. A test that only ever
called `plan(2, 16)` would pass just as happily against a module with
`def plan(n=2, budget=16)`, which is the module §AC2 forbids. So the refusals
are the load-bearing cases and the successes are the easy ones.

`TestNothingIsNamed` reads the source. It overlaps deliberately with
`test_wiz_zone_contract.py`'s scan of the same file, and the overlap is the
point: that one asserts the whole multi-layer path is clean, this one asserts
it about the module whose docstring makes the promise, so deleting either
still leaves the claim tested.
"""
from __future__ import annotations

import ast
import inspect
import pathlib
import re

import pytest

from apps.ire import back_panel_ledger as led
from apps.ire import surface_plan as sp
from apps.ire.tests.test_wik_back_panel_floor import _X2_COPY

ROOT = pathlib.Path(__file__).resolve().parents[3]

#: the confirmed back surface's geometry, the same pair WI-W measures against.
#: Imported by value rather than from that module so a change there does not
#: silently redefine what this file thinks it measured.
ZONE_W, ZONE_H = 22.0, 42.3


#: §AC2's own phrase for the work item, which is not a surface name. See
#: `test_source_guard_the_module_holds_no_zone_id_and_no_surface_word`.
_WORK_ITEM_NAME = re.compile(r"\bback[- ]panel\b", re.IGNORECASE)


def _without_the_work_item_name(text: str) -> str:
    return _WORK_ITEM_NAME.sub("", text)


def _faces():
    """The WI-K gotcha, paid again. An unregistered face makes `wrap_lines`
    return None, `layout` fall back to one line per field, and every capacity
    below read as a roomier panel. Resolved the way the composer resolves it
    and asserted, so an order-dependent measurement fails loudly."""
    from apps.ire.text_metrics import resolve_metric_faces

    faces = resolve_metric_faces({})
    regular = (faces.get("regular") or (None,))[0]
    bold = (faces.get("bold") or (None,))[0]
    assert regular and bold, "no measurable face — the lines below are not real"
    return regular, bold


class TestTheFormIsNBAndNIsUnbound:
    """§AC2(b), first clause."""

    def test_a_plan_reports_the_n_and_b_it_was_given(self):
        record = sp.plan(2, 16)
        assert record["schema_version"] == "abstract_surface_plan/1.0"
        assert record["surfaces"] == 2
        assert record["budget_lines_per_surface"] == 16
        assert record["total_capacity_lines"] == 32

    @pytest.mark.parametrize("n", [1, 2, 3, 4, 7, 40])
    def test_n_is_genuinely_unbound_upward(self, n):
        """No `MAX_SURFACES`. §AC2(d) says the count is fixed ONCE, later, by
        an owner ruling — and a ceiling is a guess about the count in the
        opposite direction from a default. Forty is not a plausible label; it
        is here because the module must not have an opinion about that.
        """
        record = sp.plan(n, 16)
        assert record["surfaces"] == n
        assert len(record["addresses"]) == n
        assert record["total_capacity_lines"] == n * 16

    def test_there_is_no_maximum_constant_to_find(self):
        """Asserted on the source, because "we did not add a ceiling" is a
        claim about what is ABSENT and the test above would pass against a
        module whose ceiling happened to sit above forty.

        By AST, and the first draft of this was a substring check that went
        red on the module's own docstring — which says, usefully, that there
        is no `MAX_SURFACES` here. That is a signpost telling a reader not to
        go looking, and it is NOT the §AC2(b) case: the ruling forbids ZONE
        NAMES in this path, because a zone name is a claim about the object,
        and a named-but-absent constant is a claim about this file. So the
        instrument was changed to match what is actually forbidden — a
        module-level BINDING — instead of the mention of one.
        """
        tree = ast.parse((ROOT / "apps/ire/surface_plan.py").read_text())
        bound = {t.id for node in tree.body
                 if isinstance(node, ast.Assign)
                 for t in node.targets if isinstance(t, ast.Name)}
        assert not {b for b in bound if "MAX" in b.upper()}, sorted(bound)


class TestItRefusesRatherThanDefaults:
    """The load-bearing class. See the module docstring."""

    def test_n_has_no_default_in_the_signature(self):
        """Read off the signature itself. An assertion about behaviour can be
        satisfied by a default that happens to be rejected downstream; this
        one cannot."""
        params = inspect.signature(sp.plan).parameters
        assert params["n"].default is inspect.Parameter.empty
        assert params["budget"].default is inspect.Parameter.empty

    def test_a_missing_n_raises_and_names_itself(self):
        with pytest.raises(ValueError) as exc:
            sp.plan(None, 16)
        assert sp.SURFACE_COUNT_REQUIRED in str(exc.value)

    def test_plan_cannot_be_called_with_no_arguments_at_all(self):
        """The §AB1(f) case in its most direct form: a caller that does not
        know how many surfaces it has must not be able to get a plan."""
        with pytest.raises(TypeError):
            sp.plan()

    @pytest.mark.parametrize("bad", [0, -1, -40])
    def test_a_count_below_one_raises(self, bad):
        with pytest.raises(ValueError) as exc:
            sp.plan(bad, 16)
        assert sp.SURFACE_COUNT_INVALID in str(exc.value)

    def test_a_negative_budget_raises_and_zero_does_not(self):
        """Zero is legal and negative is not, and the boundary is not
        arbitrary. A surface with a zero-line budget is a real state — it is
        what a surface too short for one line at this size measures as — and
        refusing it would make the plan unable to describe the case the
        ledger's own floor already produces. A NEGATIVE budget is not a state
        anything can be in; it is arithmetic that went wrong upstream, and
        passing it through would produce a total capacity that silently
        cancels another surface's room.
        """
        with pytest.raises(ValueError) as exc:
            sp.plan(2, -1)
        assert sp.BUDGET_INVALID in str(exc.value)
        assert sp.plan(2, 0)["total_capacity_lines"] == 0


class TestSurfacesAreAddressedPositionally:
    """§AC2(b), second clause — *"`surface[0] … surface[N-1]`"*."""

    def test_the_addresses_are_the_spelling_the_ruling_gives(self):
        assert sp.plan(3, 16)["addresses"] == [
            "surface[0]", "surface[1]", "surface[2]"]

    def test_the_last_address_is_n_minus_one(self):
        record = sp.plan(7, 4)
        assert record["addresses"][-1] == sp.address(6)
        assert record["addresses"][-1] == "surface[6]"

    def test_a_negative_index_has_no_address(self):
        """Python would happily give `surface[-1]` a meaning. §AC2(b) gives
        the range as 0 to N-1 and nothing outside it, so the address function
        refuses rather than rendering a position the ruling does not
        describe."""
        with pytest.raises(ValueError) as exc:
            sp.address(-1)
        assert sp.INDEX_OUT_OF_RANGE in str(exc.value)

    def test_the_addresses_are_unique_and_ordered(self):
        addresses = sp.plan(12, 1)["addresses"]
        assert len(set(addresses)) == 12
        assert addresses == sorted(addresses, key=lambda a: int(a[8:-1]))


class TestNothingIsNamed:
    """§AC2(b), third clause — *"No zone name appears anywhere in the
    multi-layer path."*"""

    def test_the_record_carries_no_names_and_says_so(self):
        record = sp.plan(2, 16)
        assert record["surface_names"] is None
        assert record["count_authority"] is None

    def test_source_guard_the_module_holds_no_zone_id_and_no_surface_word(self):
        """SOURCE-STRING GUARD (§Y2(b)). Every assertion is a literal-in-source
        claim: it reads `surface_plan.py` and says certain strings are absent.
        It would pass against a module that had been emptied and says nothing
        about behaviour — which is why the classes above exist. Declared on the
        way in; the §Y2 register stays 50 this sprint and is not worked.

        The zone-id half REUSES `test_wiz_zone_contract.zone_names_in` rather
        than spelling a second regex. Two scanners for one rule is how two
        files come to disagree about what a zone name looks like, and that one
        already carries the word-boundary fix and its own negative control.

        THE ONE EXCEPTION, NAMED RATHER THAN GLOBBED. `back-panel` is
        permitted and nothing else containing the word is. §AC2 calls the work
        *"the back-panel work"* — that is the name of a WORK ITEM, and the
        module's opening paragraph quotes the ruling that created it. §AC2(b)
        forbids naming a SURFACE. Removing the compound before scanning keeps
        the ruling quotable while leaving the bare positional word forbidden,
        and `test_the_exception_is_a_compound_and_not_the_word` below proves
        the hole is exactly that wide.
        """
        from apps.ire.tests.test_wiz_zone_contract import zone_names_in

        raw = (ROOT / "apps/ire/surface_plan.py").read_text()
        assert zone_names_in(raw) == set()
        text = _without_the_work_item_name(raw)
        for word in ("inner", "outer", "front", "back", "peel", "booklet",
                     "bottom", "wrap"):
            assert not re.search(rf"\b{word}\b", text), word

    def test_the_exception_is_a_compound_and_not_the_word(self):
        """NEGATIVE CONTROL for the exception above. An exception that also
        swallowed the bare word would make the whole scan decorative, so:
        the compound survives stripping, the bare word does not.
        """
        assert _without_the_work_item_name("the back-panel work") == \
            "the  work"
        assert "back" in _without_the_work_item_name("the back surface")
        assert re.search(r"\bback\b",
                         _without_the_work_item_name("SURFACE = 'back'"))

    def test_source_guard_the_module_needs_no_django_and_no_fonts(self):
        """SOURCE-STRING GUARD (§Y2(b)). It reads `surface_plan.py` and says
        four import strings are absent; it never imports the module, so a
        dependency reached through a name it does not spell would pass it, and
        a comment mentioning any of the four would fail it.

        Declared here rather than in the §Y2 backlog, and it was NOT declared
        first: the register went 50 -> 51 on this one test and `apps/ire`'s
        must-be-empty backlog caught it. That is the register doing its job on
        the sprint that added the file, which is the case §Y2 was written for.
        The rest of this sprint's source reads were already declared or were
        classified MIXED and never reached the register.

        WHAT IT IS ACTUALLY FOR, since a substring scan is a weak instrument:
        an abstract form that imported the composer could not be reused by
        whatever fixes the count in §AD. The stronger version — import it in a
        bare subprocess and see it load — is WI-X's
        `test_the_module_imports_with_no_django_and_no_settings`, which exists
        and covers `container_label_construction.py`. This is the cheap
        version for the newer module and is labelled as such.
        """
        text = (ROOT / "apps/ire/surface_plan.py").read_text()
        for forbidden in ("django", "import back_panel", "reportlab",
                          "apps.pipeline"):
            assert forbidden not in text, forbidden


class TestFitsIsNecessaryAndNotSufficient:
    """`fits` answers the UNALLOCATED question and the module docstring says
    so. Asserted here, because an honest limit stated only in prose is one
    refactor away from being forgotten."""

    def test_it_measures_against_the_total_and_not_one_surface(self):
        record = sp.plan(3, 10)
        assert sp.fits(record, 30) is True
        assert sp.fits(record, 31) is False

    def test_it_says_yes_to_a_document_no_allocation_can_place(self):
        """The case that makes `fits` necessary-not-sufficient, exercised
        rather than described: 3 surfaces of 10 lines hold 30, and a single
        indivisible 12-line section cannot go anywhere — but 12 <= 30, so
        `fits` says True. §AC3 exists because of exactly this gap, and a
        caller reading True as "it will lay out" is the misreading this test
        pins down.
        """
        record = sp.plan(3, 10)
        assert sp.fits(record, 12) is True
        assert 12 > record["budget_lines_per_surface"]

    def test_capacity_is_read_from_the_record_and_not_recomputed(self):
        """A plan built once cannot disagree with itself when read twice.
        Mutating the stored total must move `capacity_for`; if it did not,
        the function would be re-deriving and the record would be decorative.
        """
        record = sp.plan(3, 10)
        record["total_capacity_lines"] = 7
        assert sp.capacity_for(record) == 7
        assert sp.fits(record, 8) is False

    def test_a_missing_record_is_zero_capacity_and_not_a_crash(self):
        assert sp.capacity_for(None) == 0
        assert sp.capacity_for({}) == 0
        assert sp.fits({}, 1) is False
        assert sp.fits({}, 0) is True


class TestTheLedgerTakesNB:
    """§AC2(b) — *"The ledger and the construction model take `(N, B)`"*. This
    is the ledger's half, and B here is MEASURED off a real surface rather
    than supplied, which is the only part of the pair that touches fonts."""

    def _budget(self, n, size_pt=5.0, sections=6, w=ZONE_W, h=ZONE_H):
        regular, bold = _faces()
        return led.surface_budget(
            n=n, width_mm=w, height_mm=h, size_pt=size_pt,
            sections_per_surface=sections, regular=regular, bold=bold)

    def test_it_returns_a_plan_record_with_a_measured_budget(self):
        record = self._budget(2)
        assert record["schema_version"] == "abstract_surface_plan/1.0"
        assert record["surfaces"] == 2
        assert record["budget_lines_per_surface"] > 0
        assert record["budget_basis"] == "lines_held_for_this_many_sections"

    def test_b_is_the_gapped_figure_and_the_ungapped_one_is_carried(self):
        """Both readings, and the gapped one is the budget. Quoting the
        ungapped figure as "the panel holds N lines" overstates every real
        multi-section document, which is the disclosure `capacity` was built
        to make and this wrapper must not undo."""
        record = self._budget(2, sections=6)
        provenance = record["budget_provenance"]
        assert record["budget_lines_per_surface"] == \
            provenance["lines_held_for_this_many_sections"]
        assert record["budget_lines_if_one_section"] == \
            provenance["lines_held_in_one_section"]
        assert record["budget_lines_if_one_section"] > \
            record["budget_lines_per_surface"]

    def test_the_ledger_wrapper_has_no_default_n_either(self):
        """§AB1(f) survives one import further out, or it does not survive.
        A default here would be the forbidden assumption with a nicer
        signature in front of it."""
        params = inspect.signature(led.surface_budget).parameters
        assert params["n"].default is inspect.Parameter.empty
        with pytest.raises(ValueError):
            self._budget(None)

    def test_the_measured_budget_matches_the_numbers_wi_w_reports(self):
        """CROSS-CHECK, not a restatement. §AA1's committed docstring says the
        panel holds 16 lines at 5.0 pt and 13 at 6.0. `surface_budget` reaches
        those through `capacity`, so if the wiring ever measured a different
        surface or passed the wrong size through, this fails on numbers the
        repository already published.

        THE FULL 2x2, AND I GOT IT WRONG FIRST. The published 16 and 13 are
        the GAPPED figures for the six-section §X2 document; the ungapped
        readings are 18 and 15. The first version of this test asserted 16
        against `budget_lines_if_one_section` and read `18 == 16` — the code
        was right and the assertion was wrong. Pinning all four values, with
        which is which stated, means the next reader cannot make the same
        substitution silently: swapping the two basis keys now fails twice
        instead of passing.
        """
        five = self._budget(1, size_pt=5.0, sections=6)
        six = self._budget(1, size_pt=6.0, sections=6)
        assert five["budget_lines_per_surface"] == 16      # gapped, 6 sections
        assert five["budget_lines_if_one_section"] == 18   # ungapped
        assert six["budget_lines_per_surface"] == 13       # gapped, 6 sections
        assert six["budget_lines_if_one_section"] == 15    # ungapped

    def test_the_gap_charge_is_what_separates_the_two_readings(self):
        """And the two are not two arbitrary numbers: the difference is the
        gap charge, which is why the budget must name its basis. A surface
        told it holds one section pays no gaps and the readings converge —
        stated as an assertion so "gapped" stays a mechanism rather than a
        label.
        """
        alone = self._budget(1, size_pt=5.0, sections=1)
        assert alone["budget_lines_per_surface"] == \
            alone["budget_lines_if_one_section"] == 18
        assert alone["budget_provenance"]["section_gaps_paid_mm"] == 0.0
        crowded = self._budget(1, size_pt=5.0, sections=6)
        assert crowded["budget_provenance"]["section_gaps_paid_mm"] > 0.0

    def test_total_capacity_scales_with_n_and_the_surface_is_unchanged(self):
        """The whole reason for the form: asking for more surfaces changes the
        total and does not change what one surface holds. If B moved with N
        the model would be smuggling an allocation policy into a
        multiplication."""
        one, three = self._budget(1), self._budget(3)
        assert one["budget_lines_per_surface"] == \
            three["budget_lines_per_surface"]
        assert three["total_capacity_lines"] == \
            3 * one["budget_lines_per_surface"]

    def test_it_reports_capacity_the_x2_document_still_does_not_fit_in_one(self):
        """Anchored to the document that actually exists, so the model is
        exercised against real copy and not only against round numbers.

        This asserts the SHAPE of the finding, not a layer count: the §X2
        copy's total line cost at 5.0 pt exceeds one surface's budget, which
        is the fact §AB1(e) was raised about. It deliberately does NOT assert
        how many surfaces would be enough — that is WI-2A's re-enumeration
        under §AC3, and §AC2(d) says the count is fixed by §AD and not here.
        """
        regular, bold = _faces()
        record = led.ledger(_X2_COPY, width_mm=ZONE_W, height_mm=ZONE_H,
                            regular=regular, bold=bold)
        cost = sum(s["cost"]["5.0"]["lines"] for s in record["sections"])
        one = self._budget(1, sections=len(_X2_COPY))
        assert sp.fits(one, cost) is False
        assert cost > one["budget_lines_per_surface"]
