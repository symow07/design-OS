"""§W2 — the print-method capability table governs minimum text size.

The defect this file guards is a FALSE FAIL. §W2 says so in its own words:
you cannot emboss at 5 pt, and forbidding a 2.0 pt bottom inkjet code that is
standard practice is a false FAIL. A flat number cannot express either, so
the number left the gate and the table took over — per run, matched by the
print method recorded for that run's surface.

The second risk is the fallback. §W2(b) allows 5.0 pt where no method is
recorded and requires the record to SAY it is a fallback. A fallback reported
as a measurement is the defect class this programme keeps catching, so the
source is asserted on every run rather than once on the record.
"""
import pytest

from apps.ire import container_method_provenance as cmp_
from apps.ire import container_production_method as cpm
from apps.ire import container_text_floor as ctf
from apps.ire import container_typography_metrics as ctm
from apps.ire.compose_container import HERO_SURFACE, SURFACE_GROUP_PREFIX
from apps.ire.graph import Color, Document, Group, TextRun

BLACK = Color.from_hex("#000000")
PROFILE = {"archetype": "bottle", "variant": "cylindrical"}


def _run(name="product-name-hero", size_pt=8.0, text="BBROSE SERUM"):
    return TextRun(name=name, text=text, x=10.0, y=40.0, font="bold",
                   size_pt=size_pt, color=BLACK)


def _doc(children, page_w=100.0, page_h=120.0):
    return Document(page_w=page_w, page_h=page_h, metadata={},
                    root=Group(name="Root", role="artwork", children=children))


def _zone(zone_id, surface, technique, zone_type=None):
    zone = {"zone_id": zone_id, "parent_surface": surface,
            "x_mm": 4.0, "y_mm": 20.0, "width_mm": 30.0, "height_mm": 45.0,
            "permitted_techniques": [technique]}
    if zone_type is not None:
        zone["zone_type"] = zone_type
    return zone


def _methods(*zones):
    return cpm.build_production_methods(list(zones), PROFILE)


def _floor(doc, *zones):
    return ctf.measure_text_floor(doc, _methods(*zones) if zones else None)


def _flag(doc, *zones):
    """``below_size_floor`` as the gate will see it, or ``"ABSENT"``."""
    record = ctm.measure_typography_metrics(
        doc, _methods(*zones) if zones else None)
    return record.get("below_size_floor", "ABSENT")


class TestTheTableGovernsNotTheFlatNumber:
    """The old gate compared every container against 5.0 pt. §W2: minimum
    legible size is a physical property of how the type meets the substrate,
    so the same run passes or fails depending on how it is printed."""

    # (technique, table floor, whether a 5.5 pt run is below it)
    @pytest.mark.parametrize("technique,floor,below", [
        ("emboss", 8.0, True),        # you cannot emboss at 5.5 pt
        ("deboss", 8.0, True),
        ("hot_stamping", 6.0, True),
        ("screen_printing", 5.0, False),
        ("pad_printing", 5.0, False),
        ("adhesive_label", 4.0, False),
        ("wrap_label", 4.0, False),
        ("shrink_sleeve", 5.0, False),
    ])
    def test_one_run_one_size_and_the_method_decides(self, technique, floor,
                                                     below):
        doc = _doc([_run(size_pt=5.5)])
        record = _floor(doc, _zone("Z", HERO_SURFACE, technique))
        assert [r["floor_pt"] for r in record["runs"]] == [floor]
        assert ctf.below_floor(record) is below
        assert _flag(doc, _zone("Z", HERO_SURFACE, technique)) is below

    def test_the_flat_five_would_have_passed_the_embossed_run(self):
        """5.5 pt clears the old flat 5.0 and cannot be embossed. If this
        ever passes, the table has been replaced by a number again."""
        doc = _doc([_run(size_pt=5.5)])
        assert 5.5 > ctf.FALLBACK_FLOOR_PT
        assert ctf.below_floor(_floor(doc, _zone("Z", HERO_SURFACE,
                                                 "emboss"))) is True

    def test_the_two_pt_bottom_code_is_not_a_defect(self):
        """§W2's own example of a false FAIL. A bottom inkjet code at 2.0 pt
        is standard practice; the flat 5.0 called it a defect."""
        doc = _doc([_run(name="code-batch", size_pt=2.0, text="L2408A")])
        zone = _zone("CODE", HERO_SURFACE, "screen_printing",
                     zone_type="BOTTOM_CODE_ZONE")
        assert cpm.method_type_for(zone) == "BOTTOM_INKJET_CODE"
        assert 2.0 < ctf.FALLBACK_FLOOR_PT      # the old flat number failed it
        record = _floor(doc, zone)
        assert [r["floor_pt"] for r in record["runs"]] == [2.0]
        assert ctf.below_floor(record) is False
        assert _flag(doc, zone) is False

    def test_only_the_hero_surface_is_reachable_from_the_container_view(self):
        """A limit, recorded rather than left to be discovered. §W2(a) matches
        a run to its surface, but ``_surface_panels`` wraps every NON-hero
        surface into the schematic strip, so every run the container view
        contains resolves to the hero. The per-surface machinery is real and
        barely exercised until §W1/WI-E emits a full-scale back panel."""
        record = _floor(_doc([_run(), _run(name="claim-line", size_pt=6.0)]),
                        _zone("F", HERO_SURFACE, "screen_printing"),
                        _zone("B", "BODY_BACK", "adhesive_label"))
        assert {r["surface"] for r in record["runs"]} == {HERO_SURFACE}
        assert set(record["surface_floors"]) == {HERO_SURFACE, "BODY_BACK"}


class TestTheRuleReachesEveryRunNotJustProductName:
    """§W2(a) extends the table from ``product-name*`` runs to ALL runs. The
    old scan read the minimum off product-name alone, so a 3 pt claim line
    beside a 12 pt product name was measured as 12."""

    def test_a_run_that_is_not_a_product_name_is_measured(self):
        doc = _doc([_run(size_pt=12.0), _run(name="claim-line", size_pt=3.0,
                                             text="WITH NIACINAMIDE")])
        record = _floor(doc, _zone("Z", HERO_SURFACE, "screen_printing"))
        assert {r["node_name"] for r in record["runs"]} == {
            "product-name-hero", "claim-line"}
        assert [r["node_name"] for r in record["below_floor"]] == ["claim-line"]

    def test_the_finding_names_the_run_its_size_and_its_floor(self):
        """WI-N widened this dict by two keys and the widening is the point.

        A finding says a run is below a floor. Until WI-N it could not say
        who decided that floor. ``method_confirmed``/``method_stages`` travel
        with the finding so the floor it names carries its own authority —
        here MACHINE_PROPOSED, because ``_methods`` runs the real producer.
        The exact comparison is kept deliberately: it locks the shape, and a
        third key arriving unannounced should fail this test again.
        """
        doc = _doc([_run(name="claim-line", size_pt=3.0, text="WITH ZINC")])
        found = _floor(doc, _zone("Z", HERO_SURFACE, "hot_stamping"))["below_floor"]
        # §BH50(f)(1) announced three more keys: how the run came into scope
        # (this one by inference: the fixture declares nothing), the zone the
        # composer placed it in, and whether the copy is a placeholder
        assert found == [{"node_name": "claim-line", "surface": HERO_SURFACE,
                          "size_pt": 3.0, "floor_pt": 6.0,
                          "floor_source": ctf.SOURCE_TABLE,
                          "method_types": ["HOT_STAMP"], "below": True,
                          "method_confirmed": False,
                          "method_stages": [cmp_.STAGE_MACHINE_PROPOSED],
                          "scope_source": ctf.SCOPE_INFERRED, "zone_id": None,
                          "placeholder": False}]


class TestTheFallbackSaysItIsAFallback:
    """§W2(b). The 5.0 survives, demoted. A fallback reported as a
    measurement is the defect class this programme keeps catching."""

    @pytest.mark.parametrize("zones", [None, "empty", "other-surface"])
    def test_every_unrecorded_run_carries_the_fallback_and_names_it(self, zones):
        doc = _doc([_run(size_pt=8.0)])
        record = (_floor(doc) if zones in (None, "empty")
                  else _floor(doc, _zone("Z", "BODY_BACK", "emboss")))
        assert record["any_floor_is_a_fallback"] is True
        for run in record["runs"]:
            assert run["floor_pt"] == 5.0
            assert run["floor_source"] == ctf.SOURCE_FALLBACK
            assert "FALLBACK" in run["floor_source"]

    def test_a_recorded_method_is_never_labelled_a_fallback(self):
        record = _floor(_doc([_run()]), _zone("Z", HERO_SURFACE, "emboss"))
        assert record["any_floor_is_a_fallback"] is False
        assert all(r["floor_source"] == ctf.SOURCE_TABLE
                   for r in record["runs"])

    def test_the_fallback_still_fails_a_run_below_it(self):
        """Demoted is not disabled — an unrecorded surface is not a licence
        to draw 1 pt type."""
        assert ctf.below_floor(_floor(_doc([_run(size_pt=1.0)]))) is True

    def test_the_gate_thresholds_no_longer_define_that_key(self):
        """CONSTANT-ABSENCE GUARD (§Y2) — asserts a key is absent from a dict.

        §W2(c): a constant that does not name its domain is a conflation
        waiting to happen, and two copies is the worst case of it.

        Renamed under §Y2(b). The old name — ``test_the_gate_no_longer_
        carries_a_second_copy_of_the_number`` — read as a claim about what the
        gate DOES, and this checks only that one key is not defined. **The
        gate could still apply a flat floor from anywhere else and this would
        stay green.** The behavioural cover for which floor is actually
        applied is ``TestTheTableGovernsNotTheFlatNumber`` above.
        """
        from apps.pipeline.services import visual_quality_gate as vqg
        assert "typography_min_text_pt" not in vqg.THRESHOLDS


class TestTheMatchIsPerSurfaceNotOneGlobalMinimum:
    """The conflation §W2(a) names: ONE global minimum checked against EVERY
    method let the smallest run anywhere condemn every other method's panel."""

    def test_a_method_is_silent_about_a_surface_it_does_not_print(self):
        doc = _doc([Group(name="Decoration", children=[_run(size_pt=3.0)])])
        record = _methods(_zone("F", HERO_SURFACE, "screen_printing"),
                          _zone("B", "BODY_BACK", "emboss"))
        result = cpm.validate_production_methods(record, [], PROFILE, doc)
        fired = {pm["method_type"] for pm in result["per_method"]
                 if cpm.MINIMUM_TEXT_SIZE_FAILED in pm["codes"]}
        # 3.0 pt is below SCREEN_PRINT's 5.0 and below EMBOSS's 8.0 — but
        # nothing is drawn on the embossed surface, so EMBOSS says nothing.
        assert fired == {"SCREEN_PRINT"}

    def test_the_geometry_scan_reads_every_run_not_only_product_name(self):
        doc = _doc([Group(name="Decoration", children=[
            _run(size_pt=12.0), _run(name="claim-line", size_pt=3.0,
                                     text="WITH ZINC")])])
        geom = cpm._decoration_geometry(doc)
        assert geom["min_text_size_pt"] == 3.0
        assert geom["min_text_size_pt_by_surface"] == {HERO_SURFACE: 3.0}

    def test_surface_floors_keeps_the_surfaces_apart(self):
        floors = ctf.surface_floors(
            _methods(_zone("F", HERO_SURFACE, "screen_printing"),
                     _zone("B", "BODY_BACK", "adhesive_label")))
        assert floors[HERO_SURFACE]["floor_pt"] == 5.0
        assert floors["BODY_BACK"]["floor_pt"] == 4.0


class TestTheCaseSectionW2DoesNotResolve:
    """§W2(a) matches a run to its SURFACE. A surface carrying two methods
    with DIFFERENT floors has no answer: the larger invents the false FAIL
    §W2 was written to stop, the smaller passes type a recorded method cannot
    hold. Nothing is supplied and the axis blocks."""

    def _conflicted(self):
        return (_zone("PANEL", HERO_SURFACE, "screen_printing"),
                _zone("CREST", HERO_SURFACE, "emboss"))

    def test_no_floor_is_supplied_for_the_contested_surface(self):
        record = _floor(_doc([_run()]), *self._conflicted())
        assert record["ambiguous_surfaces"] == [HERO_SURFACE]
        assert record["runs"] == []
        assert ctf.below_floor(record) is None

    def test_the_gate_field_goes_absent_and_the_axis_blocks(self):
        from apps.pipeline.services import visual_quality_gate as vqg
        doc = _doc([_run()])
        assert _flag(doc, *self._conflicted()) == "ABSENT"
        record = ctm.measure_typography_metrics(doc,
                                                _methods(*self._conflicted()))
        assert record["unmeasured"] == ["below_size_floor"]
        axis = vqg._typography_axis({ctm.SCHEMA: record}, {})
        assert axis["state"] == vqg.UNMEASURED

    def test_the_reason_names_the_surface_and_the_competing_methods(self):
        record = _floor(_doc([_run()]), *self._conflicted())
        reason = ctf.unresolved_reason(record)
        assert HERO_SURFACE in reason
        assert "SCREEN_PRINT" in reason and "EMBOSS" in reason
        assert "5.0" in reason and "8.0" in reason

    def test_two_methods_that_agree_are_not_contested(self):
        record = _floor(_doc([_run()]),
                        _zone("A", HERO_SURFACE, "screen_printing"),
                        _zone("B", HERO_SURFACE, "pad_printing"))
        assert record["ambiguous_surfaces"] == []
        assert [r["floor_pt"] for r in record["runs"]] == [5.0]

    def test_a_run_found_below_its_floor_survives_a_contested_neighbour(self):
        """The sprint-7 asymmetry: a positive finding is about the run that
        was found. Only a False is a universal claim over every run."""
        record = _floor(_doc([_run(size_pt=1.0)]), _zone("Z", "BODY_BACK",
                                                         "emboss"))
        record["ambiguous_surfaces"] = ["BODY_BACK"]
        assert ctf.below_floor(record) is True


class TestTheStripIsNotMeasuredHarder:
    """§W1(c) — the surface strip is a map. It is a schematic at diagram
    scale, so a PRINT legibility floor applied to it fails the container for
    a property of its own thumbnail. This is the sprint-7 finding that read
    1.5 pt off a panel caption, and extending §W2 to all runs re-armed it."""

    def _with_strip(self):
        return _doc([
            Group(name="Decoration", children=[_run(size_pt=8.0)]),
            Group(name=f"{SURFACE_GROUP_PREFIX}BODY_BACK", children=[
                _run(name="back-section-0-copy", size_pt=1.16,
                     text="Aqua, Glycerin, Niacinamide.")]),
        ])

    def test_the_schematic_run_is_excluded_and_counted(self):
        record = _floor(self._with_strip(), _zone("F", HERO_SURFACE,
                                                  "screen_printing"))
        assert [r["node_name"] for r in record["runs"]] == \
            ["product-name-hero"]
        assert record["surface_strip_runs_excluded"] == 1

    def test_the_schematic_run_does_not_fail_the_container(self):
        doc = self._with_strip()
        zones = (_zone("F", HERO_SURFACE, "screen_printing"),
                 _zone("B", "BODY_BACK", "adhesive_label"))
        assert _flag(doc, *zones) is False
        result = cpm.validate_production_methods(_methods(*zones), [],
                                                 PROFILE, doc)
        assert cpm.MINIMUM_TEXT_SIZE_FAILED not in result["codes"]
        assert result["measurements"]["text_runs_excluded_as_schematic"] == 1

    def test_the_exclusion_is_stated_not_merely_performed(self):
        record = _floor(self._with_strip())
        assert "map" in record["surface_strip_exclusion"] or \
            "thumbnail" in record["surface_strip_exclusion"]
        assert "§W1(c)" in record["surface_strip_exclusion"]


class TestTheGateReadsTheVerdictNotTheNumber:
    """A per-run floor cannot be decided by comparing one scalar against one
    constant, so the comparison left the gate. What is left must still fire."""

    def test_the_axis_fails_and_names_the_print_method(self):
        from apps.pipeline.services import visual_quality_gate as vqg
        record = ctm.measure_typography_metrics(
            _doc([_run(size_pt=3.0)]),
            _methods(_zone("Z", HERO_SURFACE, "screen_printing")))
        axis = vqg._typography_axis({ctm.SCHEMA: record}, {})
        assert axis["state"] == vqg.FAIL
        assert axis["reason"] == "type is below its print method's minimum size"

    def test_the_field_is_required_so_an_absent_one_cannot_read_as_false(self):
        from apps.pipeline.services import visual_quality_gate as vqg
        record = ctm.measure_typography_metrics(
            _doc([_run(size_pt=8.0)]),
            _methods(_zone("Z", HERO_SURFACE, "screen_printing")))
        assert vqg._typography_axis({ctm.SCHEMA: record}, {})["state"] == \
            vqg.PASS
        withheld = {k: v for k, v in record.items() if k != "below_size_floor"}
        assert vqg._typography_axis({ctm.SCHEMA: withheld}, {})["state"] == \
            vqg.UNMEASURED

    def test_the_measurement_is_still_published_beside_the_verdict(self):
        record = ctm.measure_typography_metrics(
            _doc([_run(size_pt=3.0)]),
            _methods(_zone("Z", HERO_SURFACE, "screen_printing")))
        assert record["min_text_pt"] == 3.0
        assert record["size_floor_status"] == "OWNER_CALIBRATED"
        assert record["runs_below_size_floor"][0]["floor_pt"] == 5.0
        assert record["size_floor_is_a_fallback"] is False
        # a verdict published without the rule that reached it reads as a
        # measurement; §W2(d)'s status has to travel with the number.
        assert record["size_floor_rule"] == ctf.RULE


class TestTheStatusIsAPolicyChoiceNotAMeasurement:
    """§W2(d). The table is INFERRED_NONAUTHORITATIVE type defaults — a PASS
    against it is not manufacturer authority and must not read as one."""

    def test_the_record_declares_owner_calibrated(self):
        assert ctf.STATUS == "OWNER_CALIBRATED"
        assert _floor(_doc([_run()]))["status"] == "OWNER_CALIBRATED"

    def test_the_rule_says_a_pass_is_not_manufacturer_authority(self):
        assert "not manufacturer" in ctf.RULE
        assert "OWNER_CALIBRATED" in ctf.RULE

    def test_the_domains_of_the_surviving_constants_are_stated(self):
        """§W2(c) — 5.5 pt vector and 4.5 pt dieline keep their domains and
        each must name it IN THE FILE.

        MIXED, and deliberately not renamed (§Y2(b)). The ``_MIN_TEXT_PT``
        assertions are behavioural — they read the live constant. The two
        ``in source`` assertions are SOURCE-STRING assertions and carry the
        usual limit: they prove the words are written, not that the domain
        they name is the one the constant is used in. Only the first half is
        citable as coverage (§Y2(c)).
        """
        from apps.dielines.validators import production, production_readiness
        from apps.ire import compose_vector_art
        for module, constant in ((compose_vector_art, 5.5),
                                 (production, 4.5),
                                 (production_readiness, 4.5)):
            source = open(module.__file__).read()
            assert module._MIN_TEXT_PT == constant
            assert "DOMAIN" in source, module.__name__
            assert "container_text_floor" in source, module.__name__


class TestTheTableActuallyReachesTheProducer:
    """§W2(a) is only in force if the emitter hands the table over. Drop the
    argument and every run silently takes the 5.0 fallback while the axis
    stays green — a PASS that is no longer the table's verdict, which is the
    failure this whole work item exists to remove.

    CORRECTED (§Y3). This docstring used to say that "NOTHING exercises
    ``reconstruct_container``: its only caller is ``aria.py``, and no test
    reaches it." That was false, and the distinction it got wrong is the whole
    lesson: the function was **UNASSERTED, NOT UNREACHED**.

    ``aria.py`` is indeed the only production caller, but tests reach it
    through that caller. ``apps/pipeline/tests/test_container_target.py``'s
    ``ContainerFlowTests`` drives it via
    ``aria.resume_after_container_profile`` — three of its tests
    (``test_reconstruct_produces_editable_native_vector_ai``,
    ``test_supported_motif_reconstructs_natively``,
    ``test_unsupported_motif_fails_closed``) enter the function once each.
    That is measured, not read: a profile hook keyed on the function's own
    code object, because reading the call chain is exactly what produced the
    false claim. Since WI-F there are DIRECT tests as well, in
    ``test_wif_reconstruct_container``.

    What no test did was assert on the RECORDS the mutation changed. An
    unasserted path and an unreached one look identical from a green suite and
    call for opposite remedies — the first needs assertions on code that
    already runs, the second needs a caller. Sprint 9's M2 sat in the first
    case and was read as the second, so the remedy proposed for it was a
    stronger-sounding source assertion, which caught nothing.

    The two guards below therefore stay for the reason §Y2(a) gives — they
    catch outright deletion of the call site — and for no stronger reason.
    They are not the cover for this behaviour and are not citable as such.
    """

    def _source(self):
        from apps.pipeline.targets import container
        return open(container.__file__).read()

    def test_source_guard_the_call_site_literal_is_present(self):
        """SOURCE-STRING GUARD (§Y2). Asserts that a literal appears in a
        file. **It asserts nothing about behaviour** and may never be cited as
        evidence that this call site is covered (§Y2(c)).

        What it does catch is real and worth keeping (§Y2(a)): somebody
        deleting the call site outright. What it cannot catch is anything that
        leaves the characters intact — sprint 9's M2 passed the producer an
        empty record at this very line and this guard stayed green, because
        the literal it greps for was untouched. The behavioural cover is
        ``test_wif_reconstruct_container``.
        """
        assert "measure_typography_metrics(doc, methods_record)" in self._source()

    def test_source_guard_the_build_literal_precedes_the_measure_literal(self):
        """SOURCE-STRING GUARD (§Y2). Asserts the ORDER of two literals in a
        file. **It asserts nothing about behaviour** — text order is not
        execution order, and a branch, an early return or a rebinding between
        them would leave this green. Not citable as coverage (§Y2(c)).
        """
        source = self._source()
        assert source.index("methods_record = build_production_methods(") < \
            source.index("measure_typography_metrics(doc, methods_record)")


class TestTheScopeIsTheSurfaceTheComposerDeclares:
    """§BH50(f)(1), OWNER RULED: the §W2 floor is product copy only, scoped
    by the surface the composer declares on each run (``TextRun.print_scope``).
    Annotations leave scope and are listed; depictions are counted, never
    judged; a surface whose product copy is drawn only as a depiction is not
    measured and blocks; an undeclared run is judged by inference and
    disclosed; and the acceptance-side instrument reads the same declaration.
    """

    @staticmethod
    def _declared(name, size_pt, kind, surface=None, zone_id=None,
                  text="COPY"):
        from apps.ire.graph import PrintScope
        run = _run(name=name, size_pt=size_pt, text=text)
        run.print_scope = PrintScope(kind=kind, surface=surface,
                                     zone_id=zone_id)
        return run

    def test_a_declared_printed_run_is_judged_at_its_declared_surfaces_floor_whatever_its_name(self):
        run = self._declared("anything-at-all", 5.0, "PRINTED_ON_PRODUCT",
                             "BODY_BACK", "z_back")
        record = _floor(_doc([run]),
                        _zone("F", HERO_SURFACE, "screen_printing"),
                        _zone("B", "BODY_BACK", "hot_stamping"))
        [r] = record["runs"]
        assert r["surface"] == "BODY_BACK" and r["floor_pt"] == 6.0
        assert r["scope_source"] == ctf.SCOPE_DECLARED
        assert r["zone_id"] == "z_back" and r["below"] is True
        assert record["scope_declared_runs"] == 1
        assert ctf.below_floor(record) is True

    def test_a_declared_annotation_is_out_of_scope_and_listed(self):
        printed = self._declared("product-name-hero", 8.0,
                                 "PRINTED_ON_PRODUCT", HERO_SURFACE)
        note = self._declared("panel-label-1", 2.0, "SHEET_ANNOTATION")
        doc = _doc([printed, note])
        zone = _zone("F", HERO_SURFACE, "screen_printing")
        record = _floor(doc, zone)
        assert [r["node_name"] for r in record["runs"]] == ["product-name-hero"]
        assert record["out_of_scope_annotations"] == [
            {"node_name": "panel-label-1", "size_pt": 2.0}]
        assert ctf.below_floor(record) is False
        assert _flag(doc, zone) is False
        metrics = ctm.measure_typography_metrics(doc, _methods(zone))
        assert metrics["min_text_pt"] == 8.0            # the printed run
        assert metrics["min_annotation_pt"] == 2.0      # beside it, named

    def test_a_surface_whose_copy_is_drawn_only_as_a_depiction_is_not_measured_and_blocks(self):
        printed = self._declared("product-name-hero", 8.0,
                                 "PRINTED_ON_PRODUCT", HERO_SURFACE)
        code = self._declared("bottom-code-batch", 1.8,
                              "DEPICTION_OF_PRODUCT_COPY", "BOTTOM",
                              text="BATCH — MFG — EXP —")
        doc = _doc([printed, code])
        zones = (_zone("F", HERO_SURFACE, "screen_printing"),
                 _zone("CODE", "BOTTOM", "screen_printing",
                       zone_type="BOTTOM_CODE_ZONE"))
        record = _floor(doc, *zones)
        assert record["depicted_product_copy_by_surface"] == {"BOTTOM": 1}
        assert record["surface_strip_runs_excluded"] == 1
        [nm] = record["surfaces_not_measured"]
        assert nm["surface"] == "BOTTOM" and nm["floor_pt"] == 2.0
        assert record["below_floor"] == []
        assert ctf.below_floor(record) is None
        assert _flag(doc, *zones) == "ABSENT"
        reason = ctf.unresolved_reason(record)
        assert "BOTTOM" in reason and "§BH50(f)(1)" in reason
        # a printed run on the surface measures it again
        printed_code = self._declared("bottom-code", 2.0, "PRINTED_ON_PRODUCT",
                                      "BOTTOM", text="L2408A")
        record = _floor(_doc([printed, code, printed_code]), *zones)
        assert record["surfaces_not_measured"] == []
        assert ctf.below_floor(record) is False

    def test_an_undeclared_run_is_judged_by_inference_and_disclosed(self):
        record = _floor(_doc([_run(size_pt=8.0)]),
                        _zone("F", HERO_SURFACE, "screen_printing"))
        [r] = record["runs"]
        assert r["scope_source"] == ctf.SCOPE_INFERRED and r["zone_id"] is None
        assert record["scope_undeclared_runs"] == ["product-name-hero"]
        assert record["scope_declared_runs"] == 0
        assert ctf.below_floor(record) is False

    def test_a_placeholder_run_is_judged_for_size_only_and_marked(self):
        run = self._declared("back-panel-1-copy-0", 6.0, "PRINTED_ON_PRODUCT",
                             "BODY_BACK", text="CONTENT_VERIFICATION_REQUIRED")
        record = _floor(_doc([run]), _zone("B", "BODY_BACK", "hot_stamping"))
        [r] = record["runs"]
        assert r["below"] is False and r["placeholder"] is True

    def test_the_rule_and_the_record_say_what_they_cover(self):
        assert "printed on the product" in ctf.RULE.lower()
        assert "annotations are out of its scope" in ctf.RULE
        record = _floor(_doc([_run()]))
        assert record["scope"].startswith("§BH50(f)(1)")

    def test_a_scope_needs_its_surface_and_an_annotation_refuses_one(self):
        from apps.ire.graph import PrintScope
        with pytest.raises(ValueError):
            PrintScope(kind="PRINTED_ON_PRODUCT")
        with pytest.raises(ValueError):
            PrintScope(kind="SHEET_ANNOTATION", surface="BODY_FRONT")
        assert PrintScope(kind="SHEET_ANNOTATION").surface is None

    def test_a_declared_document_dumps_byte_identically_to_an_undeclared_one(self):
        from apps.ire.graph import PrintScope
        doc = _doc([_run()])
        before = doc.model_dump_json()
        doc.root.children[0].print_scope = PrintScope(kind="SHEET_ANNOTATION")
        assert doc.model_dump_json() == before
        assert doc.root.children[0].print_scope is not None

    def test_the_container_composer_declares_every_run_it_emits(self):
        from apps.ire.compose_container import compose_container_graph
        from apps.ire.print_scope import undeclared_runs
        from apps.pipeline.services import container_contract as cc
        from apps.pipeline.targets.container.silhouettes import (
            ContainerProfile, build_backbone)
        zones = cc.propose_zones(cc.build_inferred_profile("bottle"))
        doc = compose_container_graph(
            build_backbone(ContainerProfile(archetype="bottle", height_mm=110,
                                            width_mm=40)),
            product_name="Rose Nectar", name_lines=["Rose Nectar"],
            zones=zones, native=True, sku="RN-001",
            # a heading OUTSIDE §AE2(b)'s reserved set: the first full preview refused
            # this fixture for placing a word beside INGREDIENTS (tools/reserved_copy.py)
            back_sections=[{"heading": "STORY", "text": "x"}])
        assert undeclared_runs(doc) == []
        census = doc.metadata["print_scope_census"]
        assert census["declared"] >= 3 and census["undeclared"] == []
        kinds = {str(n.name): n.print_scope.kind for n, _ in doc.walk()
                 if n.type == "text"}
        assert kinds["sheet-title"] == "SHEET_ANNOTATION"
        assert kinds["sku"] == "SHEET_ANNOTATION"
        assert kinds["back-section-0-copy"] == "DEPICTION_OF_PRODUCT_COPY"
        assert kinds["panel-BODY_BACK-label"] == "SHEET_ANNOTATION"
        assert all(v == "PRINTED_ON_PRODUCT" for k, v in kinds.items()
                   if k.startswith("product-name"))

    def test_the_acceptance_instrument_reads_the_same_declaration(self):
        """§BD(c): one rule, one scope. A printed run outside every
        allow-listed group is measured on its declared surface; a depiction is
        schematic; a surface with depicted copy only is unmeasured, and the
        method that prints it says so with its own code."""
        printed = self._declared("odd-name", 3.0, "PRINTED_ON_PRODUCT",
                                 "BODY_BACK")
        code = self._declared("bottom-code-batch", 1.8,
                              "DEPICTION_OF_PRODUCT_COPY", "BOTTOM")
        note = self._declared("panel-label-9b", 1.0, "SHEET_ANNOTATION")
        doc = _doc([Group(name="Loose", children=[printed, code, note])])
        zones = (_zone("B", "BODY_BACK", "adhesive_label"),
                 _zone("CODE", "BOTTOM", "screen_printing",
                       zone_type="BOTTOM_CODE_ZONE"))
        result = cpm.validate_production_methods(_methods(*zones), [],
                                                 PROFILE, doc)
        geom = result["measurements"]
        assert geom["min_text_size_pt_by_surface"] == {"BODY_BACK": 3.0}
        assert geom["text_runs_excluded_as_schematic"] == 1
        assert geom["depicted_text_surfaces"] == ["BOTTOM"]
        assert cpm.MINIMUM_TEXT_SIZE_FAILED in result["codes"]
        assert cpm.MINIMUM_TEXT_SIZE_UNMEASURED in result["codes"]
        by_method = {pm["method_type"]: pm for pm in result["per_method"]}
        assert by_method["BOTTOM_INKJET_CODE"]["text_size_unmeasured_surfaces"] == ["BOTTOM"]
