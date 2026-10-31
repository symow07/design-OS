"""§Z3 — the back panel's copy is set at BODY_BACK's own capability-table floor.

The 15 `back-panel-*` runs sat at 5.0 pt under a 6.0 pt floor. The number was
never the defect. The defect was that the COMPOSER and the AXIS read different
sources for the same surface: the composer held no `container_production_method`
record and took §W2(b)'s disclosed fallback, while the axis resolved
`BODY_BACK`'s recorded method and got the capability table's 6.0. §Z3(a) ruled
the direction — **a floor from an actual capability table outranks a fallback**
— and the fix threads ONE record to both, so the two can no longer disagree.
That is a stronger property than getting today's number right, and it is what
this file measures.

Three things are checked here that a test of "the panel is 6.0 pt now" would
miss:

  * **the resolution only ever moves the size UP** (`TestTheSizeOnlyMovesUp`).
    A table floor BELOW 5.0 — an `ADHESIVE_LABEL`'s 4.0 — is a perfectly
    legitimate floor for the axis, but setting the copy at it would shrink the
    type and buy panel height, which is the thing §X2(b) forbids by name. The
    size and the floor are two different quantities and the record says so;

  * **the ambiguous surface is not settled by the composer**
    (`TestAnAmbiguousSurfaceIsNotSettledHere`). §W2 reserves that case for the
    owner and leaves the axis UNMEASURED on it; a composer that picked the
    larger would be adjudicating it in a file nobody reads for rulings;

  * **what the fix actually cost** (`TestWhatItCost`). Raising the type made
    the panel stop holding NET CONTENT on TODAY's copy. Two of the fifteen runs
    stopped being below floor by ceasing to exist, not by getting bigger, and
    the block moved from the typography axis to the composition one. §Z3(c)
    predicted the overflow would get worse; this states by how much, and §Z3(d)
    is why it is written down here rather than smoothed over.
"""
import pytest

from apps.ire import back_panel as bp
from apps.ire import container_production_method as cpm
from apps.ire.compose_container import HERO_SURFACE
from apps.ire.compose_dropper import compose_dropper_sheet
from apps.ire.container_text_floor import (FALLBACK_FLOOR_PT, SOURCE_FINE,
                                           SOURCE_TABLE, measure_text_floor)
from apps.ire.tests.test_back_panel import (_BACK_ZONE, _CONFIRMED_METHODS, _FRONT_ZONE,
                                            _GEOMETRY, _LIVE, _METHODS, _REAL)


#: §X2's document, as far as it can be reconstructed. Four sections are the
#: committed `_REAL`; WARNINGS and MANUFACTURER are the two the sprint-8 probe
#: had and the repo never got. See
#: `TestWhatItCost.test_the_x2_document_itself_and_what_could_not_be_reproduced`
#: for what this reproduces exactly and the five characters it does not.
_X2_WARNINGS = ("For external use only. Avoid contact with eyes. Discontinue "
                "use if irritation occurs. Keep out of reach of children.")
_X2_MANUFACTURER = "BBROSE Ltd, London N1 6NT, Great Britain."
_X2_COPY = [_REAL[0], _REAL[1], _REAL[2],
            {"heading": "WARNINGS", "text": _X2_WARNINGS},
            {"heading": "MANUFACTURER", "text": _X2_MANUFACTURER},
            _REAL[3]]


def _method(method_type, floor, surface=bp.SURFACE, method_id="m_back"):
    # [His correction of 2026-10-07] confirmed: a method someone confirmed is what holds a label at its own minimum —
    # one nobody confirmed is an assumption, and a label under it shrinks evenly to his 3 pt
    # (TestHisCorrectionOf20261007)
    return {"method_id": method_id, "method_type": method_type,
            "minimum_text_size_pt": floor, "target_surfaces": [surface],
            "authority_state": cpm.INFERRED_NONAUTHORITATIVE,
            "confirmed_by": "BBrose (a test fixture's confirmation)"}


def _doc(methods=None, sections=None):
    return compose_dropper_sheet(
        _GEOMETRY, zones=[_FRONT_ZONE, _BACK_ZONE], reference_path=None,
        logo_path=None, product_name="Rose Damascena", sku="X",
        back_sections=_LIVE if sections is None else sections,
        revision_status="TEST", methods_record=methods)


def _panel(doc):
    return doc.metadata[bp.SCHEMA]


def _faces():
    """The faces the panel is ACTUALLY set in, resolved the way the composer
    resolves them.

    Naming ``'NotoSans'`` as a string here would have worked — and would have
    worked only because some earlier test in the process had already registered
    the face as a side effect. Unregistered, ``wrap_lines`` returns None,
    ``layout`` falls back to one line per field and reports ``fits`` as None,
    and the mm assertions below would read as a fit that got roomier. A
    measurement that depends on test order is the thing this programme keeps
    finding underneath a green result.
    """
    from apps.ire.text_metrics import resolve_metric_faces
    faces = resolve_metric_faces({})
    regular = (faces.get("regular") or (None,))[0]
    bold = (faces.get("bold") or (None,))[0]
    assert regular and bold, "no measurable face — the mm below are not real"
    return regular, bold


def _at(sections, size_pt):
    regular, bold = _faces()
    record = bp.layout(sections, _BACK_ZONE["width"], _BACK_ZONE["height"],
                       size_pt=size_pt, regular=regular, bold=bold)
    assert record["fit_measured"] is True, \
        "the face was not measured, so these millimetres are not measurements"
    return record


class TestTheTableOutranksTheFallback:
    """§Z3(a) — the whole of the ruling, applied to the producer."""

    def test_a_recorded_method_sets_the_copy_at_its_own_floor(self):
        record = _panel(_doc(_CONFIRMED_METHODS))
        assert record["size_pt"] == 6.0
        assert record["size_source"]["source"] == bp.SIZE_TABLE
        assert record["size_source"]["method_types"] == ["HOT_STAMP"]
        assert record["size_source"]["surface_floor_pt"] == 6.0

    def test_no_record_is_still_the_disclosed_fallback_and_says_so(self):
        """§W2(b) is not repealed by §Z3 — it is the case §Z3 outranks. A
        record that reported the fallback as a table value would be the defect
        this whole rule exists to name."""
        record = _panel(_doc(None))
        assert record["size_pt"] == FALLBACK_FLOOR_PT
        assert record["size_source"]["source"] == bp.SIZE_FALLBACK
        assert record["size_source"]["source"].startswith("FALLBACK")
        assert record["size_source"]["surface_floor_pt"] is None

    def test_a_record_silent_about_this_surface_is_the_same_as_none(self):
        """§W2(b): absent, empty and silent-about-the-surface are one case."""
        front_only = {"methods": [_method("ADHESIVE_LABEL", 4.0,
                                          surface=HERO_SURFACE,
                                          method_id="m_front")]}
        for methods in (None, {}, {"methods": []}, front_only):
            source = _panel(_doc(methods))["size_source"]
            assert source["source"] == bp.SIZE_FALLBACK, methods
            assert source["size_pt"] == FALLBACK_FLOOR_PT

    @pytest.mark.parametrize("method_type,floor", [("HOT_STAMP", 6.0),
                                                   ("CAP_HOT_STAMP", 6.0),
                                                   ("EMBOSS", 8.0),
                                                   ("DEBOSS", 8.0)])
    def test_it_follows_the_table_and_is_not_a_second_hardcoded_six(
            self, method_type, floor):
        """A fix that wrote 6.0 into the composer would pass every test above
        and would be a fourth constant disagreeing with the table — which is
        the exact situation §W2 was written to end."""
        record = _panel(_doc({"methods": [_method(method_type, floor)]}))
        assert record["size_pt"] == floor
        assert record["size_source"]["method_types"] == [method_type]

    def test_the_axis_then_finds_nothing_below_floor_on_this_surface(self):
        """The point of the exercise: the runs stop failing because the type
        got bigger (§Z3(b)), not because anything was reinterpreted."""
        record = measure_text_floor(_doc(_CONFIRMED_METHODS), _CONFIRMED_METHODS)
        panel = [r for r in record["runs"]
                 if r["node_name"].startswith("back-panel-")]
        assert panel
        assert {r["size_pt"] for r in panel} == {6.0}
        assert {r["floor_pt"] for r in panel} == {6.0}
        assert {r["floor_source"] for r in panel} == {SOURCE_TABLE}
        assert [r for r in panel if r["below"]] == []


class TestTheSizeOnlyMovesUp:
    """§X2(b) — the one direction this resolution may not travel. [His correction of 2026-10-07] the size a table floor
    resolves to still never sets the copy lower; a label that does not stand at it now shrinks whole, evenly, to his
    3 pt or a confirmed method's minimum (the third test here; TestHisCorrectionOf20261007)."""

    @pytest.mark.parametrize("method_type,floor", [("ADHESIVE_LABEL", 4.0),
                                                   ("WRAP_LABEL", 4.0),
                                                   ("BOTTOM_INKJET_CODE", 2.0)])
    def test_a_table_floor_below_five_does_not_shrink_the_copy(
            self, method_type, floor):
        """§X2(b): "buying 47 mm by dropping type size is the purest form of
        moving a bar to make something pass". A 4.0 pt label floor is a real
        floor and the axis judges against it; it is not an instruction to set
        regulatory copy at 4.0 and recover 8 mm of panel."""
        record = _panel(_doc({"methods": [_method(method_type, floor)]}))
        assert record["size_pt"] == FALLBACK_FLOOR_PT
        assert record["size_source"]["held_up_by_fallback"] is True
        assert record["size_source"]["surface_floor_pt"] == floor
        assert record["size_source"]["held_up_reason"] == \
            bp.SIZE_HELD_UP_BY_FALLBACK

    def test_the_axis_still_judges_those_runs_against_the_lower_floor(self):
        """Floor and size are different quantities with different jobs, and
        holding the size up must not quietly raise the floor too — that would
        be the composer editing what the axis is allowed to conclude."""
        methods = {"methods": [_method("ADHESIVE_LABEL", 4.0)]}
        record = measure_text_floor(_doc(methods), methods)
        panel = [r for r in record["runs"]
                 if r["node_name"].startswith("back-panel-")]
        assert {r["floor_pt"] for r in panel} == {4.0}
        assert {r["size_pt"] for r in panel} == {5.0}
        assert [r for r in panel if r["below"]] == []

    def test_a_label_that_does_not_stand_shrinks_to_the_confirmed_floor_and_no_further(self):
        """[His correction of 2026-10-07: "Shrink the whole label evenly until everything fits ... Floor: 3 pt. Only
        if it still doesn't fit at 3 pt, stop and tell me".] Where this test once held the 4.0 pt panel and the
        fallback panel to the same height (§X2(b)'s "no shrink-to-fit"), a label that does not stand now shrinks
        whole: with no method recorded, to 3.75 pt, where all of the real copy stands; under a CONFIRMED 4.0 pt
        label it shrinks to that method's 4.0 and no further, and stops by name with what it could not hold."""
        low = _panel(_doc({"methods": [_method("ADHESIVE_LABEL", 4.0)]},
                          sections=_REAL))
        none = _panel(_doc(None, sections=_REAL))
        assert (none["size_pt"], none["fits"], none["overflow_mm"]) == (3.75, True, 0.0)
        assert none["lines_emitted"] == none["lines_required"]
        assert (low["size_pt"], low["fits"]) == (4.0, False)
        assert low["codes"] == [bp.COPY_EXCEEDS_PANEL] and low["overflow_mm"] > 0

    def test_an_explicit_caller_size_is_named_as_the_callers(self):
        """`size_pt=` is kept for callers that have already decided, and is
        never dressed up as something the capability table said."""
        size, source = bp.size_for_surface(_METHODS, size_pt=3.0)
        assert size == 3.0
        assert source["source"] == bp.SIZE_CALLER
        assert source["surface_floor_pt"] is None


class TestHisCorrectionOf20261007:
    """[His correction of 2026-10-07 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a6b2092): "when the label doesn't fit,
    the text gets SMALLER ... Shrink the whole label evenly until everything fits, keeping its layout, spacing and
    order. Floor: 3 pt. Only if it still doesn't fit at 3 pt, stop and tell me".] His rule for every design lifts
    §X2(b)'s "no shrink-to-fit" on a back label (§X2 and §Z3 still LIVE in the brain at 2026-10-07T04:42Z; his newer
    word is followed and the collision told him): a back that does not stand at its size shrinks whole to 3 pt — unless
    a CONFIRMED print method records more, the executor's reading, his to veto. A method nobody confirmed — every live
    container's (§AA3(c)) — is an assumption and holds nothing up."""

    def test_an_unconfirmed_hot_stamp_no_longer_holds_the_label_above_his_floor(self):
        record = _panel(_doc(_METHODS))                     # the hot stamp's 6.0 pt, which nobody confirmed
        assert record["size_source"]["method_confirmed"] is False
        assert record["fits"] is True and record["codes"] == []
        assert record["size_pt"] == 5.25                    # shrunk evenly from its 6.0 until all of it stands
        assert record["lines_emitted"] == record["lines_required"] == 15        # NET CONTENT kept
        axis = measure_text_floor(_doc(_METHODS), _METHODS)
        panel = [r for r in axis["runs"] if r["node_name"].startswith("back-panel-")]
        assert len(panel) == 15 and {r["size_pt"] for r in panel} == {5.25}
        assert {r["floor_pt"] for r in panel} == {bp.LABEL_FLOOR_PT} and not [r for r in panel if r["below"]]
        assert {r["floor_source"] for r in panel} == {SOURCE_FINE}

    def test_a_confirmed_one_holds_it_and_the_panel_stops_by_name(self):
        record = _panel(_doc(_CONFIRMED_METHODS))
        assert record["size_source"]["method_confirmed"] is True
        assert record["size_pt"] == 6.0 and record["fits"] is False and bp.COPY_EXCEEDS_PANEL in record["codes"]

    def test_the_floor_is_one_answer_for_the_panel_and_the_axis(self):
        assert bp.label_floor_pt() == bp.label_floor_pt(6.0, False) == bp.label_floor_pt(6.0, None) == 3.0
        assert bp.label_floor_pt(6.0, True) == 6.0 and bp.label_floor_pt(2.0, True) == 3.0
        _size, source = bp.size_for_surface(_METHODS, size_pt=4.5)
        assert bp.label_floor_of(source) == 4.5             # a size its caller named is the size it decided


class TestAnAmbiguousSurfaceIsNotSettledHere:
    """§W2's ambiguity is the owner's, and a composer is not the owner."""

    _AMBIGUOUS = {"methods": [_method("HOT_STAMP", 6.0, method_id="m_a"),
                              _method("SCREEN_PRINT", 5.0, method_id="m_b")]}

    def test_it_takes_the_fallback_and_names_the_ambiguity(self):
        record = _panel(_doc(self._AMBIGUOUS))
        assert record["size_pt"] == FALLBACK_FLOOR_PT
        assert record["size_source"]["source"] == bp.SIZE_AMBIGUOUS
        assert "DIFFERENT minimum" in record["size_source"]["source"]

    def test_the_axis_is_still_unmeasured_on_it(self):
        """Which is why the composer picking a size could not have helped: the
        axis refuses to judge these runs at all, so a larger size would buy no
        pass and would only hide that the surface is unresolved."""
        record = measure_text_floor(_doc(self._AMBIGUOUS), self._AMBIGUOUS)
        assert bp.SURFACE in record["ambiguous_surfaces"]
        assert not [r for r in record["runs"]
                    if r["node_name"].startswith("back-panel-")]


class TestWhatItCost:
    """§Z3(c)/(d) — the honest outcome, measured rather than predicted.

    §X2(e) said the panel "passes today, it blocks the day the content is
    real". Raising the type to 6.0 pt ends that: it blocks TODAY, on the
    placeholder copy, because a 42.3 mm panel at 6.0 pt holds 13 lines where
    it held 15. The section it drops is NET CONTENT — a mandatory declaration.
    [His correction of 2026-10-07] measured on the hot stamp CONFIRMED: only a
    confirmed method still holds a label at its minimum.
    """

    def test_the_panel_stops_fitting_on_todays_copy(self):
        at_5 = _panel(_doc(None))
        at_6 = _panel(_doc(_CONFIRMED_METHODS))
        assert at_5["fits"] is True and at_5["codes"] == []
        assert at_6["fits"] is False
        assert bp.COPY_EXCEEDS_PANEL in at_6["codes"]
        assert at_5["overflow_mm"] == 0.0
        assert at_6["overflow_mm"] == 3.6

    def test_the_section_it_drops_is_the_net_content_declaration(self):
        cut = [s for s in _panel(_doc(_CONFIRMED_METHODS))["sections"]
               if s["lines_emitted"] < s["lines_required"]]
        assert [s["heading"] for s in cut] == ["NET CONTENT"]
        assert cut[0]["lines_emitted"] == 0 and cut[0]["lines_required"] == 2
        assert cut[0]["characters_emitted"] == 0
        assert cut[0]["characters_supplied"] == 31

    def test_two_of_the_fifteen_stopped_failing_by_ceasing_to_exist(self):
        """The number that must not be reported as fifteen runs made legible.
        Thirteen got bigger; two left the document, and they left because the
        panel can no longer hold them. A count that fell without this sentence
        beside it would be a better-looking lie."""
        blind = measure_text_floor(_doc(None), _CONFIRMED_METHODS)
        wired = measure_text_floor(_doc(_CONFIRMED_METHODS), _CONFIRMED_METHODS)
        before = [r for r in blind["runs"]
                  if r["node_name"].startswith("back-panel-")]
        after = [r for r in wired["runs"]
                 if r["node_name"].startswith("back-panel-")]
        assert len(before) == 15 and len(after) == 13
        assert all(r["below"] for r in before)
        assert not any(r["below"] for r in after)
        # the two that went are the NET CONTENT runs, and nothing else moved.
        gone = {r["node_name"] for r in before} - {r["node_name"] for r in after}
        assert len(gone) == 2
        assert blind["runs_examined"] - wired["runs_examined"] == 2
        assert len(blind["below_floor"]) - len(wired["below_floor"]) == 15

    def test_the_overflow_gets_worse_on_real_copy_and_that_is_the_outcome(self):
        """§Z3(c) — stated in mm and in characters, from the committed
        regulatory fixture. Taller type on a fixed 19.0 x 39.30 mm column can
        only reduce what fits, and this is not a reason to reconsider §Z3(b)."""
        at_5, at_6 = _at(_REAL, 5.0), _at(_REAL, 6.0)
        assert at_5["height_available_mm"] == at_6["height_available_mm"] == 39.3
        assert at_5["column_mm"] == at_6["column_mm"] == 19.0
        assert (at_5["height_required_mm"], at_5["overflow_mm"]) == (63.783,
                                                                    24.483)
        assert (at_6["height_required_mm"], at_6["overflow_mm"]) == (93.84,
                                                                    54.54)
        # 30.057 mm worse; 84 fewer characters reach the page, of 431 supplied.
        assert round(at_6["overflow_mm"] - at_5["overflow_mm"], 3) == 30.057
        assert at_5["characters_emitted"] - at_6["characters_emitted"] == 84
        assert (at_5["characters_emitted"], at_6["characters_emitted"]) == (259,
                                                                           175)
        assert at_5["characters_supplied"] == at_6["characters_supplied"] == 431

    def test_the_x2_document_itself_and_what_could_not_be_reproduced(self):
        """§Z3(c) against the document §X2 actually quoted — with the part of
        it that is NOT in this repo said out loud.

        §X2's headline (19.0 mm column, 39.30 mm available, 86.55 mm required,
        47.25 mm over, 259 of 613 characters, INGREDIENTS cut at line 15 of 20)
        was taken against a copy fixture from a sprint-8 probe that never
        landed. Four of its six sections are the committed ``_REAL``; WARNINGS
        and MANUFACTURER are reconstructed here from the arithmetic §X2's own
        numbers pin — 39 lines x 2.11667 mm + 5 gaps x 0.8 mm = 86.55 mm, and
        613 - 431 = 182 characters over 39 - 29 = 10 lines.

        EVERY structural number reproduces: 39 lines, 86.55 mm, 47.25 mm over,
        259 characters emitted, INGREDIENTS at 15 of 20, four sections absent
        entirely. The supplied-character DENOMINATOR does not — 608, five
        short of 613 — and it cannot be closed: §X2's MANUFACTURER needs 46
        characters of text on two lines, and 41 is the measured ceiling for two
        lines in a 19.0 mm column at 5.0 pt (``'BBROSE Ltd, London'`` 17.08 mm
        + ``'N1 6NT, Great Britain.'`` 18.14 mm). Five characters is not worth
        inventing copy to hide, and a re-measurement that quietly used a
        different document than the one it claims to re-measure is worth less
        than one that says where it differs.
        """
        at_5, at_6 = _at(_X2_COPY, 5.0), _at(_X2_COPY, 6.0)

        # §X2, reproduced.
        assert at_5["column_mm"] == 19.0
        assert at_5["height_available_mm"] == 39.3
        assert at_5["height_required_mm"] == 86.55
        assert at_5["overflow_mm"] == 47.25
        assert at_5["lines_required"] == 39
        assert at_5["characters_emitted"] == 259
        by_5 = {s["heading"]: s for s in at_5["sections"]}
        assert (by_5["INGREDIENTS"]["lines_emitted"],
                by_5["INGREDIENTS"]["lines_required"]) == (15, 20)
        assert [h for h, s in by_5.items() if s["lines_emitted"] == 0] == \
            ["DIRECTIONS", "WARNINGS", "MANUFACTURER", "NET CONTENT"]

        # the one number that does not, recorded as a number and not as prose.
        assert at_5["characters_supplied"] == 608
        assert 613 - at_5["characters_supplied"] == 5

        # §Z3(c): worse, and by how much.
        assert at_6["height_required_mm"] == 125.92
        assert at_6["overflow_mm"] == 86.62
        assert round(at_6["overflow_mm"] - at_5["overflow_mm"], 2) == 39.37
        assert at_5["characters_emitted"] - at_6["characters_emitted"] == 84
        assert at_6["characters_emitted"] == 175

    def test_the_ingredients_cut_moves_up_the_list(self):
        """The consequence in the form a regulator would read it: the INCI list
        is truncated earlier, and the three sections after it are still absent
        entirely."""
        by_heading = {s["heading"]: s for s in _at(_REAL, 6.0)["sections"]}
        assert by_heading["INGREDIENTS"]["lines_emitted"] == 12
        assert by_heading["INGREDIENTS"]["lines_required"] == 26
        assert by_heading["DIRECTIONS"]["lines_emitted"] == 0
        assert by_heading["NET CONTENT"]["lines_emitted"] == 0
