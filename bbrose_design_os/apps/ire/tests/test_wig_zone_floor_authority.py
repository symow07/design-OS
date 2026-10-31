"""WI-G (§Y1) — a zone may TIGHTEN a floor. It may not LOOSEN one.

`container_production_method.build_production_methods` read
`z.get("min_text_size_pt") or defaults.get("min_text_pt")`. Three defects sat
in that one line:

* a zone-level value **beat** the §W2 capability table, silently. §W2 bound
  the table because the table describes what the PRESS can hold; a zone is a
  region of a design, and every one of these method records carries
  `authority_state` `INFERRED_NONAUTHORITATIVE` or `USER_REQUESTED_UNVERIFIED`
  — neither has standing to claim the press holds finer type than the method
  allows;
* the record still stamped `constraints_source:
  INFERRED_NONAUTHORITATIVE_TYPE_DEFAULT`, so the provenance field was false
  in **exactly** the case where provenance mattered;
* `or` treats `0.0` as absent, so a zone floor of 0.0 fell through to the type
  default and nothing recorded that it had.

§Y1(a) settles it: **the effective floor is the LARGER of the zone value and
the table value.** Above the table tightens and is honoured. Below the table is
refused, the table stands, and §Y1(b) requires the refusal to be RECORDED with
both numbers and the reason rather than discarded.

THE NEGATIVE CONTROL is `TestTheNegativeControl` below. §Y1 is a rule about a
value NOT taking effect, and a rule like that is only proved by showing the
refused number absent from the outcome — not by reading a provenance string
that says it was refused. `test_the_refused_floor_is_not_in_force_at_the_gate`
emits type the refused floor would have cleared and asserts the gate still
calls it below floor. If §Y1 is ever reverted, that is the test that fails.

**SCOPE — read §Y1(e) before extending anything here.** The ruling is
statistic-scoped. It binds `minimum_text_size_pt`, and binds
`minimum_line_weight_mm` / `registration_tolerance_mm` as to the `is not None`
defect ONLY. `TestTheRulingsScopeIsPinned` exists to make a future session that
"finishes the job" by extending the larger-of rule to all three fields fail a
test and read the ruling: **registration tolerance is a TOLERANCE, so larger is
LOOSER**, and max()ing it would permit precisely the loosening §Y1 forbids.
"""
from __future__ import annotations

import pytest

from apps.ire import container_production_method as cpm
from apps.ire import container_text_floor as ctf
from apps.ire import container_typography_metrics as ctm
from apps.ire.compose_container import HERO_SURFACE
from apps.ire.graph import Color, Document, Group, TextRun

BLACK = Color.from_hex("#000000")
PROFILE = {"archetype": "bottle", "variant": "cylindrical"}

#: The SCREEN_PRINT row of the §W2 capability table. Named rather than inlined
#: so a test that depends on the table's number says which number it depends on.
TABLE_SCREEN_PRINT_PT = 5.0


def _zone(zone_id="Z", surface=HERO_SURFACE, technique="screen_printing",
          **constraints):
    """A confirmed zone. ``constraints`` are passed through verbatim, so a
    test can pin ``min_text_size_pt=0.0`` and mean 0.0 rather than absent."""
    zone = {"zone_id": zone_id, "parent_surface": surface,
            "x_mm": 4.0, "y_mm": 20.0, "width_mm": 30.0, "height_mm": 45.0,
            "permitted_techniques": [technique]}
    zone.update(constraints)
    return zone


def _method(**constraints):
    """The single built method for one zone carrying ``constraints``."""
    return cpm.build_production_methods([_zone(**constraints)],
                                        PROFILE)["methods"][0]


def _doc(*runs):
    return Document(page_w=100.0, page_h=120.0, metadata={},
                    root=Group(name="Root", role="artwork",
                               children=list(runs)))


def _run(size_pt, name="product-name-hero"):
    return TextRun(name=name, text="BBROSE SERUM", x=10.0, y=40.0,
                   font="bold", size_pt=size_pt, color=BLACK)


def _sanity_check_the_table():
    """The table row these tests build on, asserted rather than assumed."""
    assert cpm._METHOD_DEFAULTS["SCREEN_PRINT"]["min_text_pt"] == \
        TABLE_SCREEN_PRINT_PT


class TestAZoneMayTighten:
    """§Y1(a) — a zone can legitimately be stricter than the press."""

    def test_a_zone_above_the_table_becomes_the_effective_floor(self):
        m = _method(min_text_size_pt=9.0)
        _sanity_check_the_table()
        assert m["minimum_text_size_pt"] == 9.0
        assert m["minimum_text_size_source"] == cpm.ORIGIN_ZONE_TIGHTENED
        assert m["refused_zone_constraints"] == []

    def test_a_tightened_floor_is_in_force_at_the_gate(self):
        """The mirror of the negative control: 6.0 pt clears the table's 5.0
        and is below the zone's 9.0, so the tightening must actually bite."""
        zone = _zone(min_text_size_pt=9.0)
        rec = cpm.build_production_methods([zone], PROFILE)
        record = ctf.measure_text_floor(_doc(_run(6.0)), rec)
        assert [r["floor_pt"] for r in record["runs"]] == [9.0]
        assert ctf.below_floor(record) is True
        assert ctm.measure_typography_metrics(
            _doc(_run(6.0)), rec)["below_size_floor"] is True

    def test_a_zone_equal_to_the_table_is_not_dressed_up_as_a_decision(self):
        """A no-op override changed nothing, so the record must not claim the
        zone moved anything. Provenance that inflates is provenance that
        misleads, which is the §Y1(d) defect pointing the other way."""
        m = _method(min_text_size_pt=TABLE_SCREEN_PRINT_PT)
        assert m["minimum_text_size_pt"] == TABLE_SCREEN_PRINT_PT
        assert m["minimum_text_size_source"] == cpm.ORIGIN_TYPE_DEFAULT
        assert m["refused_zone_constraints"] == []

    def test_a_method_type_with_no_table_row_honours_the_zone_and_says_so(self):
        """There is no press capability to contradict, so the zone value is
        taken — under its own label, so it is never read as table-governed."""
        assert "UNSUPPORTED" not in cpm._METHOD_DEFAULTS
        table = dict(cpm._METHOD_DEFAULTS)
        assert cpm._resolve_min_text_size(3.0, None) == (
            3.0, cpm.ORIGIN_ZONE_NO_TABLE, None)
        assert cpm._METHOD_DEFAULTS == table      # no mutation of the table


class TestTheNegativeControl:
    """§Y1(a)/(b) — THE REQUIRED NEGATIVE CONTROL.

    A zone value BELOW the table is refused, recorded, and NOT IN FORCE. Each
    of those three is asserted separately, because the failure modes differ:
    honouring it is the §Y1 defect, discarding it silently is the §Y1(b)
    defect, and recording it while still letting it govern would be the worst
    of the three — a record that documents its own refusal and then ignores it.
    """

    def test_the_table_value_stands_as_the_effective_floor(self):
        m = _method(min_text_size_pt=3.0)
        assert m["minimum_text_size_pt"] == TABLE_SCREEN_PRINT_PT
        assert m["minimum_text_size_source"] == cpm.ORIGIN_ZONE_REFUSED

    def test_the_refusal_is_recorded_with_both_numbers_and_the_reason(self):
        """§Y1(b) — the disagreement stays visible. Both numbers, because a
        record that says only 'an override was refused' cannot be audited."""
        [refusal] = _method(min_text_size_pt=3.0)["refused_zone_constraints"]
        assert refusal["code"] == cpm.REFUSED_ZONE_TEXT_FLOOR
        assert refusal["field"] == "minimum_text_size_pt"
        assert refusal["zone_value_pt"] == 3.0
        assert refusal["table_value_pt"] == TABLE_SCREEN_PRINT_PT
        assert refusal["effective_value_pt"] == TABLE_SCREEN_PRINT_PT
        assert "REFUSED" in refusal["outcome"]
        assert "§Y1(a)" in refusal["reason"]

    def test_the_refused_floor_is_not_in_force_at_the_gate(self):
        """**The negative control proper.**

        4.0 pt is above the zone's refused 3.0 and below the table's 5.0. If
        the refusal is real the gate says below-floor; if the zone value ever
        governs again this is the assertion that catches it — and it catches
        it in the VERDICT, not in a provenance string that could itself be
        wrong. §W2's own headline defect was a four-point-under violation
        reported as a pass.
        """
        zone = _zone(min_text_size_pt=3.0)
        rec = cpm.build_production_methods([zone], PROFILE)
        record = ctf.measure_text_floor(_doc(_run(4.0)), rec)
        assert [r["floor_pt"] for r in record["runs"]] == [TABLE_SCREEN_PRINT_PT]
        assert [r["size_pt"] for r in record["runs"]] == [4.0]
        assert ctf.below_floor(record) is True
        assert ctm.measure_typography_metrics(
            _doc(_run(4.0)), rec)["below_size_floor"] is True

    def test_a_refused_zone_reports_the_table_as_the_floor_source(self):
        """§Y1(d)'s three-way split resolves to TABLE here, and that is not a
        loose end: the table's number is what is actually in force, and the
        refusal is carried on the method record rather than smuggled into a
        run-level label that names a floor nobody applied."""
        rec = cpm.build_production_methods([_zone(min_text_size_pt=3.0)],
                                           PROFILE)
        record = ctf.measure_text_floor(_doc(_run(4.0)), rec)
        assert [r["floor_source"] for r in record["runs"]] == [ctf.SOURCE_TABLE]
        assert rec["any_zone_override_refused"] is True

    def test_the_refusal_rolls_up_so_a_consumer_need_not_walk_the_methods(self):
        rec = cpm.build_production_methods(
            [_zone("A", min_text_size_pt=3.0),
             _zone("B", surface="BODY_BACK", technique="emboss")], PROFILE)
        assert rec["any_zone_override_refused"] is True
        assert [r["zone_value_pt"] for r in rec["refused_zone_constraints"]] \
            == [3.0]

    def test_an_honest_record_carries_no_refusals_at_all(self):
        """The roll-up must be empty when nothing was refused, or 'a refusal
        happened' degrades into noise nobody reads."""
        rec = cpm.build_production_methods([_zone()], PROFILE)
        assert rec["refused_zone_constraints"] == []
        assert rec["any_zone_override_refused"] is False


class TestZeroIsAValueNotAnAbsence:
    """§Y1(c) — ``or`` became ``is not None`` on all three numeric floors.

    ``0.0`` is falsy, so under ``or`` every one of these fell through to the
    type default with nothing recording that it had. The two sibling fields on
    the same record already used ``is not None``, so the file disagreed with
    itself exactly on the fields where 0.0 is both meaningful and dangerous.
    """

    def test_a_zero_text_floor_is_refused_rather_than_silently_replaced(self):
        """Both halves matter. Under ``or`` the effective value was also 5.0 —
        the NUMBER was accidentally right — but the record claimed the zone had
        asked for nothing. §Y1(c) leaves the number alone and fixes the claim,
        so this asserts the recorded 0.0, not just the 5.0."""
        m = _method(min_text_size_pt=0.0)
        assert m["minimum_text_size_pt"] == TABLE_SCREEN_PRINT_PT
        assert m["minimum_text_size_source"] == cpm.ORIGIN_ZONE_REFUSED
        [refusal] = m["refused_zone_constraints"]
        assert refusal["zone_value_pt"] == 0.0

    def test_a_zero_text_floor_never_silently_clears_every_run(self):
        """§Y1(c)'s named hazard. A 0.0 floor honoured is a floor that passes
        any type at any size; 1.0 pt is unreadable at any print method here."""
        rec = cpm.build_production_methods([_zone(min_text_size_pt=0.0)],
                                           PROFILE)
        record = ctf.measure_text_floor(_doc(_run(1.0)), rec)
        assert ctf.below_floor(record) is True

    def test_a_zero_line_weight_is_taken_as_zero_not_as_the_default(self):
        """§Y1(e) binds line weight as to the ``is not None`` defect ONLY, so
        the zone's 0.0 is honoured here. That is deliberate: adjudicating it
        would be inventing a ruling the owner did not make."""
        assert cpm._METHOD_DEFAULTS["SCREEN_PRINT"]["min_line_mm"] != 0.0
        assert _method(min_line_weight_mm=0.0)["minimum_line_weight_mm"] == 0.0

    def test_a_zero_registration_tolerance_is_taken_as_zero(self):
        assert cpm._METHOD_DEFAULTS["SCREEN_PRINT"]["registration_mm"] != 0.0
        assert _method(
            registration_tolerance_mm=0.0)["registration_tolerance_mm"] == 0.0

    def test_absent_still_means_absent_on_all_three(self):
        """The other side of ``is not None``: a zone that pins nothing must
        still take the whole table row, or the fix has broken the normal case."""
        m, d = _method(), cpm._METHOD_DEFAULTS["SCREEN_PRINT"]
        assert m["minimum_text_size_pt"] == d["min_text_pt"]
        assert m["minimum_line_weight_mm"] == d["min_line_mm"]
        assert m["registration_tolerance_mm"] == d["registration_mm"]
        assert m["constraints_source"] == cpm.ORIGIN_TYPE_DEFAULT


class TestTheRulingsScopeIsPinned:
    """§Y1(e) — a scope guard, not a behavioural endorsement.

    **If you are here because you extended the larger-of rule to all three
    numeric fields and this class went red: that is what it is for. Read
    §Y1(e).** The three fields do not share a direction.
    ``minimum_text_size_pt`` and ``minimum_line_weight_mm`` are FLOORS, where
    larger is stricter. ``registration_tolerance_mm`` is a TOLERANCE, where
    larger is **LOOSER** — a max() there would loosen registration on every
    record carrying a zone value, which is the exact move §Y1 exists to forbid,
    performed in the name of enforcing §Y1.
    """

    @pytest.mark.parametrize("zone_mm", [0.05, 0.90])
    def test_registration_is_taken_as_supplied_in_both_directions(self, zone_mm):
        """Tighter and looser alike pass through unadjudicated. The looser
        case is NOT an endorsement — it is the boundary of the ruling, and
        what makes it safe to leave is that the record now says out loud that
        no zone-vs-table comparison was performed on this field."""
        table_mm = cpm._METHOD_DEFAULTS["SCREEN_PRINT"]["registration_mm"]
        assert (zone_mm < table_mm) or (zone_mm > table_mm)
        m = _method(registration_tolerance_mm=zone_mm)
        assert m["registration_tolerance_mm"] == zone_mm
        assert m["constraints_by_field"]["registration_tolerance_mm"] == \
            cpm.ORIGIN_ZONE_UNADJUDICATED

    def test_line_weight_is_also_left_unadjudicated(self):
        m = _method(min_line_weight_mm=0.02)
        assert m["minimum_line_weight_mm"] == 0.02
        assert m["constraints_by_field"]["minimum_line_weight_mm"] == \
            cpm.ORIGIN_ZONE_UNADJUDICATED

    def test_only_the_text_floor_can_ever_be_refused(self):
        """Every refusal record names the one field §Y1(e) adjudicates. A
        refusal naming another field would mean the ruling had been widened
        without one being written."""
        rec = cpm.build_production_methods(
            [_zone(min_text_size_pt=1.0, min_line_weight_mm=0.0,
                   registration_tolerance_mm=9.0, permitted_color_count=0,
                   max_artwork_coverage=0.0)], PROFILE)
        assert {r["field"] for r in rec["refused_zone_constraints"]} == \
            {"minimum_text_size_pt"}


class TestProvenanceStoppedBeingAConstant:
    """§Y1(d) — a provenance field that is a constant is not provenance."""

    def test_the_honest_case_reads_exactly_as_it_always_did(self):
        """The fix must not churn every record. Where every value did come
        from the type default, the old string is still the true one."""
        assert _method()["constraints_source"] == cpm.ORIGIN_TYPE_DEFAULT

    def test_the_source_names_the_field_that_did_not_come_from_the_table(self):
        source = _method(min_text_size_pt=9.0)["constraints_source"]
        assert source != cpm.ORIGIN_TYPE_DEFAULT
        assert "minimum_text_size_pt" in source
        assert cpm.ORIGIN_ZONE_TIGHTENED in source

    def test_a_refused_override_also_moves_the_source_off_the_constant(self):
        """The case §Y1 opens on: the record used to stamp TYPE_DEFAULT while
        a zone value was in play. Refused is still 'a zone had something to
        say', and the field must not go back to claiming otherwise."""
        source = _method(min_text_size_pt=3.0)["constraints_source"]
        assert source != cpm.ORIGIN_TYPE_DEFAULT
        assert cpm.ORIGIN_ZONE_REFUSED in source

    def test_every_constrained_field_reports_a_provenance(self):
        m = _method(min_text_size_pt=9.0)
        assert set(m["constraints_by_field"]) == {
            "permitted_color_count", "minimum_line_weight_mm",
            "minimum_text_size_pt", "maximum_coverage",
            "registration_tolerance_mm"}
        assert all(v for v in m["constraints_by_field"].values())

    def test_the_machine_readable_field_is_the_one_a_consumer_should_use(self):
        """``constraints_source`` is prose for a reader and its shape is not a
        contract; ``constraints_by_field`` is the parseable one. Asserted so a
        future consumer does not start regexing the sentence."""
        m = _method(min_text_size_pt=9.0)
        assert m["constraints_by_field"]["minimum_text_size_pt"] == \
            cpm.ORIGIN_ZONE_TIGHTENED
        assert m["constraints_by_field"]["maximum_coverage"] == \
            cpm.ORIGIN_TYPE_DEFAULT


class TestFloorSourceIsThreeWayNotTwo:
    """§Y1(d) — `floor_source` must distinguish table / zone-tightened /
    fallback. Two of the three were already there; calling a zone's decision
    SOURCE_TABLE attributed it to the capability table, which is the same
    class of false attribution §W2(b) forbids for the fallback."""

    def _sources(self, zones, size_pt=8.0):
        rec = cpm.build_production_methods(zones, PROFILE) if zones else None
        return [r["floor_source"] for r in
                ctf.measure_text_floor(_doc(_run(size_pt)), rec)["runs"]]

    def test_table(self):
        assert self._sources([_zone()]) == [ctf.SOURCE_TABLE]

    def test_zone_tightened(self):
        assert self._sources([_zone(min_text_size_pt=9.0)]) == \
            [ctf.SOURCE_ZONE_TIGHTENED]

    def test_fallback(self):
        assert self._sources(None) == [ctf.SOURCE_FALLBACK]

    def test_the_three_are_distinct_strings(self):
        assert len({ctf.SOURCE_TABLE, ctf.SOURCE_ZONE_TIGHTENED,
                    ctf.SOURCE_FALLBACK}) == 3

    def test_the_tightened_label_still_credits_the_table_for_the_minimum(self):
        """§Y1(a) makes the table the value the zone had to BEAT, so the
        tightened floor is table-derived in a real sense and the string says
        so. It is not, however, the table's number, and the string says that
        too."""
        assert ctf.SOURCE_TABLE in ctf.SOURCE_ZONE_TIGHTENED
        assert "TIGHTENED" in ctf.SOURCE_ZONE_TIGHTENED

    def test_a_surface_is_flagged_tightened_when_any_method_on_it_was(self):
        """Where two methods agree on the number, the honest label is still
        'tightened' if a tightening bought that agreement."""
        rec = cpm.build_production_methods(
            [_zone("A", min_text_size_pt=9.0),
             _zone("B", technique="hot_stamping", min_text_size_pt=9.0)],
            PROFILE)
        resolved = ctf.surface_floors(rec)[HERO_SURFACE]
        assert resolved["ambiguous"] is False and resolved["floor_pt"] == 9.0
        assert resolved["zone_tightened"] is True


class TestTheAdditionsDidNotDisturbWhatWasAlreadyPinned:
    """§Y1 adds provenance to a record whose hash is an identity elsewhere."""

    def test_provenance_fields_do_not_move_the_method_hash(self):
        """``_method_hash`` covers a fixed core key set, so the new fields are
        hash-stable by construction. Asserted rather than assumed, because the
        alternative is discovering it from a downstream identity drift test."""
        plain = _method()
        assert plain["method_hash"] == cpm._method_hash(
            {k: v for k, v in plain.items()
             if k not in ("constraints_by_field", "minimum_text_size_source",
                          "refused_zone_constraints", "constraints_source",
                          "method_hash")})

    def test_but_a_changed_effective_floor_does_move_it(self):
        """The complement, and the one that should be true: the hash tracks
        the constraint VALUES, and a tightened floor is a different constraint.
        A hash that ignored that would be the actual defect."""
        assert _method(min_text_size_pt=9.0)["method_hash"] != \
            _method()["method_hash"]

    def test_a_refused_override_leaves_the_hash_where_it_was(self):
        """Nothing in force changed, so nothing identifying may change."""
        assert _method(min_text_size_pt=3.0)["method_hash"] == \
            _method()["method_hash"]

    def test_the_record_is_still_deterministic(self):
        a = cpm.build_production_methods([_zone(min_text_size_pt=3.0)], PROFILE)
        b = cpm.build_production_methods([_zone(min_text_size_pt=3.0)], PROFILE)
        assert a["method_set_hash"] == b["method_set_hash"] and a == b

    def test_authority_is_untouched_by_any_of_this(self):
        """§Y1 moves a floor. It must not move authority: a zone that tightens
        a floor has still not verified anything with a manufacturer."""
        for pt in (3.0, 9.0, 0.0, None):
            m = _method(min_text_size_pt=pt)
            assert m["authority_state"] == cpm.INFERRED_NONAUTHORITATIVE
            assert m["authority_state"] != cpm.VERIFIED_MANUFACTURER_CAPABILITY
