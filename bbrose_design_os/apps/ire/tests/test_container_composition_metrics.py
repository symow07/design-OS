"""VQR-3 — the composition record must not invent the field it cannot measure.

``visual_quality_gate._composition_axis`` has read
``container_composition_metrics/1.0`` since VQR-2A and nothing has produced
it, so the axis has been UNMEASURED — blocking — for the whole arc. It reads
three fields:

* ``elements_outside_artboard`` — geometry against the page. MEASURABLE.
* ``front_hierarchy_nonempty`` — did any type tier reach the front. MEASURABLE.
* ``blocking_overlaps`` — which overlaps are DEFECTS. A motif behind type is
  intentional; two names on top of each other is not. MEASURABLE SINCE §W3,
  which ruled exactly that line for this axis and the typography axis at
  once. Until then, inventing it here would have been a design policy wearing
  a measurement's name.

The tests that pinned the third field ABSENT were right when they were
written and are now wrong, and the difference matters: the field moved
because an owner ruled, through OWNER_BLOCKER_CLEARANCE.md, not because a
later session got tired of an UNMEASURED axis. What those tests were really
guarding — that the record never invents a zero — is still guarded, by
§W3(d): where the rule cannot be applied to a run, the count is still absent
and the axis still blocks.

These tests exist mostly to stop a future session "finishing" the record.
"""
import pytest

from apps.ire import container_composition_metrics as ccm
from apps.ire.graph import (Color, Document, Group, Image, MoveTo, LineTo,
                            Path, Stroke, TextRun)

BLACK = Color.from_hex("#000000")
PAGE_W = 100.0
PAGE_H = 120.0


def _doc(children, page_w=PAGE_W, page_h=PAGE_H, metadata=None):
    return Document(page_w=page_w, page_h=page_h, metadata=metadata or {},
                    root=Group(name="Root", role="artwork", children=children))


def _name_run(x=10.0, y=40.0, text="BBROSE SERUM", size_pt=12.0):
    return TextRun(name="product-name-hero", text=text, x=x, y=y,
                   font="bold", size_pt=size_pt, color=BLACK)


def _oblique_run(x=10.0, y=80.0, text="POLVO HORNEADO"):
    """A run set at an angle §W3(d) leaves UNMEASURED — ``_text_bbox_mm``
    returns the UNROTATED box off-axis, so its geometry is not available and
    neither an intersection nor its absence can be read off it."""
    return TextRun(name="product-name-vertical", text=text, x=x, y=y,
                   font="bold", size_pt=9.0, color=BLACK, rotation_deg=30.0)


class TestTheOverlapFieldMovedBecauseAnOwnerRuled:
    """This class used to pin ``blocking_overlaps`` ABSENT, and was right to.

    §W3 supplied the ruling it was waiting on — type over type blocks at any
    opacity, type over a rule, motif, medallion or colour field does not — so
    the field is now measurable and the axis is decidable. It did not become
    measurable because a later session wanted a green axis; the property that
    guarded that is now guarded by §W3(d) below, which still refuses a count
    the rule cannot produce.
    """

    def test_the_ruled_field_is_now_in_the_record(self):
        record = ccm.measure_composition_metrics(_doc([_name_run()]))
        assert record is not None
        assert record["blocking_overlaps"] == 0
        assert record["unmeasured"] == []

    def test_the_record_carries_the_rule_it_applied(self):
        """A zero from a reader that discriminated and a zero from a reader
        that looked at nothing are different facts."""
        record = ccm.measure_composition_metrics(_doc([_name_run()]))
        assert "§W3" in record["overlap_rule"]
        assert record["overlap_runs_examined"] == 1

    def test_the_gate_axis_can_now_reach_pass(self):
        from apps.pipeline.services import visual_quality_gate as vqg
        record = ccm.measure_composition_metrics(_doc([_name_run()]))
        assert record["elements_outside_artboard"] == 0
        assert record["front_hierarchy_nonempty"] is True
        assert vqg._composition_axis({ccm.SCHEMA: record})["state"] == vqg.PASS


class TestTheGateKeepsWhatItWasGiven:
    """An UNMEASURED axis still has to report what it DID receive. The
    incomplete branch built its refusal with no ``measured`` at all, so the
    two facts the producer measured were dropped on the floor between the
    record and the report — a diagnostic reporting less than it found."""

    def test_the_unmeasured_axis_carries_the_measured_fields(self):
        from apps.pipeline.services import visual_quality_gate as vqg
        record = ccm.measure_composition_metrics(
            _doc([_name_run(), _oblique_run()]))
        axis = vqg._composition_axis({ccm.SCHEMA: record})
        assert axis["state"] == vqg.UNMEASURED
        assert axis["measured"]["elements_outside_artboard"] == 0
        assert axis["measured"]["front_hierarchy_nonempty"] is True

    def test_the_unmeasured_axis_names_the_missing_field(self):
        from apps.pipeline.services import visual_quality_gate as vqg
        record = ccm.measure_composition_metrics(
            _doc([_name_run(), _oblique_run()]))
        axis = vqg._composition_axis({ccm.SCHEMA: record})
        assert "blocking_overlaps" in axis["measured"]["unmeasured"]


class TestElementsOutsideTheArtboard:
    """The page IS the artboard. Leaving it is already a defect elsewhere in
    this codebase (``container_logo_metrics._clip_findings`` reports
    ``page_bounds``), so the definition is reused, not invented."""

    def test_a_clean_document_reports_zero(self):
        record = ccm.measure_composition_metrics(_doc([_name_run()]))
        assert record["elements_outside_artboard"] == 0
        assert record["outside_elements"] == []

    def test_a_path_off_the_page_is_counted_and_named(self):
        stray = Path(name="rule-stray",
                     segments=[MoveTo(x=PAGE_W + 5.0, y=10.0),
                               LineTo(x=PAGE_W + 25.0, y=10.0)],
                     stroke=Stroke(color=BLACK, width_mm=0.25))
        record = ccm.measure_composition_metrics(_doc([_name_run(), stray]))
        assert record["elements_outside_artboard"] == 1
        assert [e["node_name"] for e in record["outside_elements"]] \
            == ["rule-stray"]

    def test_a_negative_coordinate_counts_too(self):
        stray = Image(name="logo-off", src="/no/such.png",
                      x=-20.0, y=10.0, w=10.0, h=10.0)
        record = ccm.measure_composition_metrics(_doc([_name_run(), stray]))
        assert record["elements_outside_artboard"] == 1

    def test_an_element_touching_the_edge_is_inside(self):
        """Flush with the trim is a placement, not a defect — the tolerance
        exists to absorb mm-space float noise, nothing more."""
        edge = Image(name="logo-flush", src="/no/such.png",
                     x=PAGE_W - 10.0, y=0.0, w=10.0, h=10.0)
        record = ccm.measure_composition_metrics(_doc([_name_run(), edge]))
        assert record["elements_outside_artboard"] == 0

    def test_a_text_run_is_judged_by_its_measured_extent(self):
        """Derived, not asserted: the run is placed so that the CHAR-COUNT
        GUESS and the real advance width disagree about whether it leaves the
        page. Whichever way the real face answers, the record must agree with
        the face — so a producer that fell back to the guess fails here."""
        from apps.ire import text_metrics as tm
        from apps.dielines.exporters.counter_display_files import _resolve_fonts
        _, bold = _resolve_fonts()
        text, size_pt = "BBROSE SERUM", 12.0
        size_mm = size_pt / 2.835
        measured = tm.text_width_mm_measured(text, size_mm, bold)
        guess = len(text) * size_mm * tm._FALLBACK_ADVANCE_EM
        assert measured is not None
        assert abs(measured - guess) > 0.5, (
            "this face's advance and the guess agree too closely for the "
            "placement below to distinguish them")
        # anchor the run so the page edge falls BETWEEN the two answers
        x = PAGE_W - (measured + guess) / 2.0
        run = _name_run(x=x, y=40.0, text=text, size_pt=size_pt)
        record = ccm.measure_composition_metrics(_doc([run]))
        expected = 1 if x + measured > PAGE_W else 0
        assert record["elements_outside_artboard"] == expected

    def test_every_outside_element_states_how_its_extent_was_obtained(self):
        stray = Path(name="rule-stray",
                     segments=[MoveTo(x=PAGE_W + 5.0, y=10.0),
                               LineTo(x=PAGE_W + 25.0, y=10.0)],
                     stroke=Stroke(color=BLACK, width_mm=0.25))
        record = ccm.measure_composition_metrics(_doc([_name_run(), stray]))
        for entry in record["outside_elements"]:
            assert entry["extent_source"] in ("geometry", "measured_text",
                                              "estimated_text")


class TestFrontHierarchy:
    """``front_hierarchy_nonempty`` asks whether any type tier reached the
    front at all — the emptiness the gate calls a defect."""

    def test_a_document_with_a_product_name_is_nonempty(self):
        record = ccm.measure_composition_metrics(_doc([_name_run()]))
        assert record["front_hierarchy_nonempty"] is True
        assert record["front_hierarchy"] == ["product-name-hero"]

    def test_a_document_with_no_live_type_is_empty(self):
        art = Path(name="rule-front-single",
                   segments=[MoveTo(x=10.0, y=10.0), LineTo(x=40.0, y=10.0)],
                   stroke=Stroke(color=BLACK, width_mm=0.25))
        record = ccm.measure_composition_metrics(_doc([art]))
        assert record["front_hierarchy_nonempty"] is False
        assert record["front_hierarchy"] == []

    def test_sheet_furniture_is_not_the_front_hierarchy(self):
        """A spec sheet's SKU label is live text on the artboard and is not
        front artwork. Counting it would let a document with no product name
        report a non-empty hierarchy."""
        sku = TextRun(name="sku", text="ES3083", x=5.0, y=115.0,
                      font="regular", size_pt=6.0, color=BLACK)
        record = ccm.measure_composition_metrics(_doc([sku]))
        assert record["front_hierarchy_nonempty"] is False

    def test_type_the_emitter_put_on_another_surface_is_not_front(self):
        """The back panel's INCI block is artwork type, not sheet furniture —
        no name prefix excludes it, and the first version of this record
        counted it. Only the emitted ``Surface-*`` ancestry says it is not on
        the front, and the run sits TWO groups deep inside it because a
        parent-only check would have believed it."""
        from apps.ire.compose_container import SURFACE_GROUP_PREFIX
        back = Group(
            name=f"{SURFACE_GROUP_PREFIX}BODY_BACK", role="decoration",
            children=[Group(name="BACK_DIRECT_PRINT", role="decoration",
                            children=[TextRun(name="back-section-0-copy",
                                              text="Aqua, Glycerin", x=6.0,
                                              y=100.0, font="regular",
                                              size_pt=5.0, color=BLACK)])])
        record = ccm.measure_composition_metrics(_doc([back]))
        assert record["front_hierarchy"] == []
        assert record["front_hierarchy_nonempty"] is False
        # excluded from the FRONT question, still measured against the
        # artboard — it is a real element wherever it sits
        assert record["element_count"] == 1

    def test_the_hero_surface_is_front_when_the_emitter_names_it(self):
        """The surface comes from the emitter, not from an assumption that an
        unwrapped run is the front — so a hero-surface group is front type."""
        from apps.ire.compose_container import (HERO_SURFACE,
                                                SURFACE_GROUP_PREFIX)
        hero = Group(name=f"{SURFACE_GROUP_PREFIX}{HERO_SURFACE}",
                     role="decoration", children=[_name_run()])
        record = ccm.measure_composition_metrics(_doc([hero]))
        assert record["front_hierarchy"] == ["product-name-hero"]


class TestTheRecordSaysWhereItsTextExtentsCameFrom:
    """WI-F made text extents measurable and made them SAY whether they were
    measured. A composition record built on top of them inherits that duty —
    an artboard verdict resting on an estimated extent is an estimated
    verdict."""

    def test_the_record_carries_the_per_role_provenance(self):
        record = ccm.measure_composition_metrics(_doc([_name_run()]))
        prov = record["text_metrics_provenance"]
        assert set(prov["faces_by_role"]) == {"regular", "bold", "arabic"}
        assert prov["all_roles_measured"] is False
        assert prov["roles_estimated"] == ["arabic"]

    def test_an_empty_document_yields_no_record(self):
        """Mirrors ``container_logo_metrics``: nothing to measure means no
        record, never a record full of confident zeros."""
        assert ccm.measure_composition_metrics(_doc([])) is None


def _stray():
    return Path(name="rule-stray",
                segments=[MoveTo(x=PAGE_W + 5.0, y=10.0),
                          LineTo(x=PAGE_W + 25.0, y=10.0)],
                stroke=Stroke(color=BLACK, width_mm=0.25))


class TestAMeasuredDefectIsAFindingNotAnAbsence:
    """The axis collapsed two different states into one word.

    ``blocking_overlaps`` was never emitted — by design — so the axis took the
    incomplete branch on EVERY record this producer made, and reported
    "composition metrics are incomplete" even when the record it held said, in
    a field it did measure, that elements were off the artboard. An unmeasured
    neighbour does not un-see a defect that was found. Both states block, so
    no gate outcome changes; what changes is whether the owner is told
    something was found.

    This is the asymmetry the typography axis already carries: FAIL is a
    positive finding about one field, PASS is a universal claim over all of
    them. One incomplete field forbids the second and says nothing about the
    first.

    §W3 made the third field measurable, so the incomplete record is now
    produced by the §W3(d) case — an obliquely rotated run — rather than by
    every document. The asymmetry is unchanged and still has to hold.
    """

    def _axis(self, record):
        from apps.pipeline.services import visual_quality_gate as vqg
        return vqg._composition_axis({ccm.SCHEMA: record})

    def test_an_element_off_the_artboard_fails_an_incomplete_record(self):
        from apps.pipeline.services import visual_quality_gate as vqg
        record = ccm.measure_composition_metrics(
            _doc([_name_run(), _oblique_run(), _stray()]))
        assert "blocking_overlaps" not in record, (
            "the record became complete, which would make this test pass for "
            "the wrong reason — it must exercise the INCOMPLETE branch")
        assert record["elements_outside_artboard"] == 1
        axis = self._axis(record)
        assert axis["state"] == vqg.FAIL, axis
        assert axis["code"] == vqg.VQ_COMPOSITION_DEFECTIVE

    def test_an_empty_front_hierarchy_fails_an_incomplete_record(self):
        from apps.ire.compose_container import SURFACE_GROUP_PREFIX
        from apps.pipeline.services import visual_quality_gate as vqg
        back = Group(name=f"{SURFACE_GROUP_PREFIX}BODY_BACK", role="decoration",
                     children=[_name_run()])
        record = ccm.measure_composition_metrics(_doc([back]))
        assert record["front_hierarchy_nonempty"] is False
        assert self._axis(record)["state"] == vqg.FAIL

    def test_the_reason_names_only_the_findings_that_fired(self):
        """The old reason recited all three defects whichever one fired. On an
        incomplete record that is an assertion about a field nobody measured —
        the same move as the absent flag, made in the prose instead."""
        record = ccm.measure_composition_metrics(_doc([_name_run(), _stray()]))
        reason = self._axis(record)["reason"]
        assert "outside the artboard" in reason
        assert "overlap" not in reason, reason
        assert "hierarchy" not in reason, reason

    def test_the_failing_axis_still_discloses_what_it_could_not_measure(self):
        """A FAIL is not licence to drop the record's own disclosure: the
        owner reading the finding must still see that a third field exists and
        was not measured, or the FAIL reads as the whole story."""
        record = ccm.measure_composition_metrics(
            _doc([_name_run(), _oblique_run(), _stray()]))
        measured = self._axis(record)["measured"]
        assert measured["unmeasured"] == ["blocking_overlaps"]
        assert measured["unmeasured_reasons"]["blocking_overlaps"]
        assert "blocking_overlaps" not in measured

    def test_a_clean_incomplete_record_is_still_unmeasured(self):
        """The guard on the change above: making a measured defect speak must
        not have made an unmeasured axis stop blocking."""
        from apps.pipeline.services import visual_quality_gate as vqg
        record = ccm.measure_composition_metrics(
            _doc([_name_run(), _oblique_run()]))
        axis = self._axis(record)
        assert axis["state"] == vqg.UNMEASURED
        assert axis["code"] == vqg.VQ_COMPOSITION_COMPARISON_UNAVAILABLE
        assert axis["missing_measurement"]

    def test_the_incomplete_reason_names_the_field_that_is_missing(self):
        record = ccm.measure_composition_metrics(
            _doc([_name_run(), _oblique_run()]))
        assert "blocking_overlaps" in self._axis(record)["reason"]


class TestAnUnmeasuredHierarchyIsNotAnEmptyOne:
    """The same defect read the other way round.

    ``front_hierarchy_nonempty`` was read with ``.get()`` and coerced with
    ``bool()``, so an ABSENT flag became False — and False here means
    DEFECTIVE. Where the typography flags turned silence into a clean bill of
    health, this one turned silence into an accusation: the axis reported "the
    front hierarchy is empty" about a hierarchy nobody had looked at. Both
    block. Neither is true.
    """

    def _axis(self, metrics):
        from apps.pipeline.services import visual_quality_gate as vqg
        return vqg._composition_axis({ccm.SCHEMA: metrics})

    def test_an_absent_hierarchy_flag_is_unmeasured_not_failed(self):
        from apps.pipeline.services import visual_quality_gate as vqg
        axis = self._axis({"elements_outside_artboard": 0,
                           "blocking_overlaps": 0})
        assert axis["state"] == vqg.UNMEASURED, axis
        assert "the front hierarchy is empty" not in axis["reason"]
        assert "front_hierarchy_nonempty" in axis["reason"]

    def test_a_measured_empty_hierarchy_still_fails(self):
        """The guard: the axis must still catch the real defect, or the fix
        above would be indistinguishable from deleting the check."""
        from apps.pipeline.services import visual_quality_gate as vqg
        axis = self._axis({"elements_outside_artboard": 0,
                           "blocking_overlaps": 0,
                           "front_hierarchy_nonempty": False})
        assert axis["state"] == vqg.FAIL
        assert axis["reason"] == "the front hierarchy is empty"

    def test_an_explicit_null_is_not_a_measurement(self):
        from apps.pipeline.services import visual_quality_gate as vqg
        axis = self._axis({"elements_outside_artboard": 0,
                           "blocking_overlaps": 0,
                           "front_hierarchy_nonempty": None})
        assert axis["state"] == vqg.UNMEASURED
        assert "front_hierarchy_nonempty" not in axis["measured"]

    def test_a_complete_clean_record_still_passes(self):
        from apps.pipeline.services import visual_quality_gate as vqg
        axis = self._axis({"elements_outside_artboard": 0,
                           "blocking_overlaps": 0,
                           "front_hierarchy_nonempty": True})
        assert axis["state"] == vqg.PASS

    def test_malformed_counts_are_unmeasured_not_defective(self):
        from apps.pipeline.services import visual_quality_gate as vqg
        axis = self._axis({"elements_outside_artboard": "two",
                           "blocking_overlaps": 0,
                           "front_hierarchy_nonempty": True})
        assert axis["state"] == vqg.UNMEASURED
        assert "malformed" in axis["reason"]
