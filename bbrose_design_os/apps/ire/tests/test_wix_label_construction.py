"""WI-X (§AB1) — the multi-layer label recorded, not drawn.

§AB1 ruled the label MULTI-LAYER on the same bottle. WI-X's whole instruction
is to record that "in the form WI-N built: OWNER_DIRECTED / UNCONFIRMED, axis
blocking, no supplier contact", and to note that it "is a provenance and
structure item, not a dieline". So the assertions here are about WHICH STAGE
SUPPLIED WHAT, and about the two things the module refuses to do.

THE ONE THAT MATTERS is `test_an_owner_ruling_does_not_confirm
_manufacturability`. §AB1(b) is the whole reason this module exists: an owner
choosing a target is total authority over what is being built and zero
evidence that it can be built, and the defect WI-N found was precisely those
two facts sharing one field. If that test ever goes green because
`OWNER_DIRECTED` started confirming, the module has re-acquired the bug it was
written to prevent.

WHY THERE IS A NEGATIVE CONTROL HERE. §AB0(c) — "a negative control separates
a defect from a regression". An axis hard-wired to block always is not
measuring anything; it just looks careful. `test_the_block_is_a_measurement
_and_not_a_hard_wired_no` drives the record to the state where both conditions
clear and requires the axis to PASS. Nothing in this sprint can reach that
state — §C2 is permanent, so `SUPPLIER_CONFIRMED` is unreachable — but the
code path must exist and be exercised, or the block is decoration.
"""
from __future__ import annotations

import ast
import pathlib
import subprocess
import sys

from apps.ire import container_label_construction as lc

ROOT = pathlib.Path(__file__).resolve().parents[3]

#: The §X2-confirmed zones, as this repository confirmed them. Pinned to the
#: contract module by `TestTheZoneClaimIsTiedToItsSource` rather than retyped
#: and left to drift.
#:
#: FOUR since §AH added `z_wrap`, and this constant is the reason that ruling
#: has a defect recorded against it: §AH4 predicted the hash consequences of
#: the confirmation and named three functions, and it did not name this. The
#: length of this tuple is `BASELINE`, and `BASELINE` is the arithmetic
#: `zone_set_covers` does to decide whether a construction has an extra
#: surface, at fifteen call sites in this file. A ruling that states its blast
#: radius and understates it is defective even when the fix turns out safe,
#: which this one did: see `TestTheBaselineMovedWithoutMovingAVerdict`.
CONFIRMED_TODAY = ("z_front", "z_back", "z_bottom_code", "z_wrap")

#: HOW MANY the contract confirms, which is the only thing `zone_set_covers`
#: is allowed to know after §AC2(b) de-named it. Derived from the tuple above
#: rather than typed as `3`, so that if the contract's count ever changes this
#: constant follows it and does not have to be found and edited.
#:
#: The callers below pass this EXPLICITLY. `zone_set_covers` has no default
#: for it and returns False when it is missing, which is deliberate: a
#: function that no longer holds the zone names cannot infer the baseline, and
#: guessing one would be §AC2(a)'s "guess with a hash on it". Fail-closed
#: means an un-updated caller reads as "no extra surface", never as "yes".
BASELINE = len(CONFIRMED_TODAY)

def _numeric_contracted_count(source: str) -> list[int]:
    """Line numbers where a NUMBER is passed as `contracted_count=`.

    AST rather than text: a keyword argument on a real call, whose value is a
    numeric constant. Prose that mentions the spelling, a docstring that quotes
    it, and a string literal containing it are all invisible to this by
    construction — which is the entire reason it is written this way. See
    `test_source_guard_no_caller_hard_codes_the_old_baseline`.
    """
    tree = ast.parse(source)
    return [kw.value.lineno
            for node in ast.walk(tree) if isinstance(node, ast.Call)
            for kw in node.keywords
            if kw.arg == "contracted_count"
            and isinstance(kw.value, ast.Constant)
            and isinstance(kw.value.value, int)
            and not isinstance(kw.value.value, bool)]


#: The record §AB1 actually produces: an owner chose a multi-layer label, and
#: nobody has confirmed anyone can make it.
AB1_RECORD = {
    "construction": lc.MULTI_LAYER,
    "provenance_stage": lc.STAGE_OWNER_DIRECTED,
}


class TestTheProvenanceSplitAB1b:
    """§AB1(b). The target's author and the target's manufacturability are two
    facts, and WI-N exists because they were once one field."""

    def test_an_owner_ruling_does_not_confirm_manufacturability(self):
        """The load-bearing assertion of this module.

        An owner ruling is authority over WHAT WE ARE BUILDING and no evidence
        whatsoever that a converter can build it. §AB1(b) says so in the
        ruling itself, which is why this is applying a rule rather than
        inventing caution.
        """
        assert lc.manufacturability(lc.STAGE_OWNER_DIRECTED) == lc.UNCONFIRMED

    def test_only_a_supplier_confirms_and_nothing_else_does(self):
        confirming = {s for s in lc._STAGE_MEANING
                      if lc.manufacturability(s) == lc.CONFIRMED}
        assert confirming == {lc.STAGE_SUPPLIER_CONFIRMED}
        assert lc.MANUFACTURABILITY_CONFIRMING_STAGES == confirming

    def test_a_record_that_signs_nothing_is_unattributed_not_defaulted(self):
        """WI-N's actual defect: a default and a fixture returning the same
        string, so a PROPOSAL read as a CONFIRMATION. An unsigned record must
        be legible AS unsigned."""
        for empty in ({}, None, "OWNER_DIRECTED", 7, {"provenance_stage": ""},
                      {"provenance_stage": "OWNER_SAID_SO"}):
            assert lc.construction_stage(empty) == lc.STAGE_UNATTRIBUTED
        assert lc.manufacturability(lc.STAGE_UNATTRIBUTED) == lc.UNCONFIRMED

    def test_every_stage_says_what_it_means_in_words(self):
        for stage in lc._STAGE_MEANING:
            assert lc.stage_meaning(stage).strip()
        assert lc.stage_meaning("NOT_A_STAGE") == \
            lc._STAGE_MEANING[lc.STAGE_UNATTRIBUTED]


class TestTheLayerCountIsFailClosedAB1f:
    """§AB1(f) — "Two is the working assumption and it is not ruled. Do not
    build anything that assumes exactly two.\""""

    def test_asking_for_the_count_raises_rather_than_answering(self):
        try:
            lc.require_layer_count()
        except lc.LabelLayerCountNotRuled as exc:
            assert exc.code == lc.LAYER_COUNT_NOT_RULED
            assert lc.LAYER_COUNT_NOT_RULED in str(exc)
        else:                                            # pragma: no cover
            raise AssertionError("require_layer_count() returned a count")

    def test_the_module_exports_no_integer_at_all(self):
        """The working assumption is a sentence in the ruling, not a constant
        here. A module-level `2` is a number a consumer can multiply a surface
        area by, and the distance from that to a dimension nobody ruled is one
        commit. Asserted structurally so it cannot be reintroduced quietly."""
        ints = {n: v for n, v in vars(lc).items()
                if not n.startswith("__") and isinstance(v, int)
                and not isinstance(v, bool)}
        assert ints == {}

    def test_the_measurement_reports_the_count_as_absent(self):
        report = lc.measure_label_construction(
            AB1_RECORD, confirmed_zones=CONFIRMED_TODAY)
        assert report["layer_count"] is None


class TestTheVariantIsNamedAndNotRuled:
    def test_both_variants_are_named_and_neither_is_chosen(self):
        """§AB1 says peel-reveal OR booklet and picks neither. "The owner
        mentioned it" and "the owner chose it" are different facts, and the
        second is the one that is missing."""
        assert lc.RULED_VARIANT is None
        assert set(lc.VARIANTS_NAMED_NOT_RULED) == {"PEEL_REVEAL", "BOOKLET"}
        assert lc.measure_label_construction(AB1_RECORD)["variant"] is None


class TestX2IsNarrowedNotLifted:
    """§AB1(a) narrowed what the ban was ABOUT. It did not repeal it."""

    def test_each_banned_object_still_fires(self):
        for kind in lc.BANNED_SEPARATE_OBJECTS:
            assert lc.is_banned_separate_object(kind) is True

    def test_it_normalises_the_ways_a_caller_would_actually_spell_them(self):
        for spelling in ("carton", "  Carton  ", "leaflet in box",
                         "Outer Wrap", "larger_container"):
            assert lc.is_banned_separate_object(spelling) is True

    def test_a_layer_of_one_label_is_not_a_separate_object(self):
        """The complement, and the reason the check is a list rather than a
        mood: if it fired on the ruled target it would be vetoing §AB1."""
        for ok in ("PEEL_REVEAL", "BOOKLET", "LAYER", "", None, "z_front"):
            assert lc.is_banned_separate_object(ok) is False


class TestTheZoneConditionWIXFoundItself:
    """The second block — found here, not handed down. Reported under §AB0(b)
    as a condition on the same axis, never as a refusal of the target."""

    def test_the_confirmed_set_has_no_surface_for_a_multi_layer_label(self):
        """`BASELINE` is passed rather than left out ON PURPOSE, and the
        distinction is the whole point of the §AC2(b) de-naming.

        Omitting it also returns False — but by the fail-closed path, which
        means "I was not told the baseline", not "the set has no extra
        surface". Two different facts with one boolean between them. Stating
        the baseline makes this assertion measure the thing it is named after:
        the confirmed set passed in whole, nothing left over.

        Deliberately written with no number in it, which is why §AH's move from
        three to four did not touch this line.
        """
        assert lc.zone_set_covers(lc.MULTI_LAYER, CONFIRMED_TODAY,
                                  contracted_count=BASELINE) is False

    def test_a_single_layer_label_is_covered_by_what_exists(self):
        """The container prints today. Whatever else is unresolved, the
        current construction is not blocked on a missing surface."""
        assert lc.zone_set_covers(lc.SINGLE_LAYER, CONFIRMED_TODAY) is True

    def test_an_empty_zone_set_covers_nothing(self):
        assert lc.zone_set_covers(lc.SINGLE_LAYER, ()) is False
        assert lc.zone_set_covers(lc.MULTI_LAYER, ()) is False

    def test_a_zone_outside_the_confirmed_set_clears_the_condition(self):
        """And this is the function's HONEST LIMIT, asserted so it is on the
        record rather than in a comment.

        The check is a proxy: it asks "is there a zone beyond what §X2
        confirmed", not "is there a zone that is a multi-layer surface". Those
        coincide today and would stop coinciding the moment a further zone is
        confirmed for some unrelated purpose — a shoulder batch code, say.
        This module cannot tell those apart and must not guess, so the drift
        is caught by pinning the set to its source (below) and letting a
        human read the diff, not by a cleverer predicate here.

        THAT PREDICTION HAS NOW BEEN TESTED ONCE AND SURVIVED. §AH confirmed a
        fourth zone. It was `z_wrap` — a print surface, the jar's body label —
        so the proxy and the real question still coincide and no verdict moved.
        The docstring named the shoulder-batch-code case as the one that would
        break it; that case has not arrived. A prediction that correctly
        described a risk which then failed to materialise is worth exactly as
        much as it sounds, and it is recorded here rather than upgraded into
        evidence that the proxy is sound.

        §AC2(b) NARROWED THIS FURTHER AND THE LIMIT IS NOW WIDER, NOT
        NARROWER. `zone_set_covers` no longer holds the three names, so it can
        no longer ask "is there a zone beyond THESE THREE" — it asks "are
        there more than `contracted_count`". Those agree while the confirmed
        set contains the baseline and diverge if three DIFFERENT zones are
        ever confirmed. `"z_peel_back"` survives here as a caller's string,
        which is where §AC2(b) permits a name to be: this file is a test
        naming a hypothetical fourth surface, not the multi-layer path
        deciding a contract question from typed-in strings.
        """
        assert lc.zone_set_covers(
            lc.MULTI_LAYER, (*CONFIRMED_TODAY, "z_peel_back"),
            contracted_count=BASELINE) is True


class TestTheZoneClaimIsTiedToItsSource:
    """`CONFIRMED_TODAY` is a claim ABOUT another module. Retyped constants
    drift; this one is pinned.

    IT WORKED. §AH edited the contract and this went red in the same run,
    carrying the failure message below — which had, since WI-X, told whoever
    hit it exactly what to do next: decide whether the new zone is a
    multi-layer surface, then update `BASELINE`. That is the message doing the
    job it was written for, on a change made a sprint after it was written, by
    someone who had forgotten `BASELINE` existed. §AA asks for guards that have
    been seen to fire; this one has now been seen to fire usefully, which is a
    stronger thing and worth recording separately.
    """

    def test_the_confirmed_zones_are_the_ones_the_contract_confirms(self):
        src = ROOT / "apps/pipeline/services/selected_concept_contract.py"
        tree = ast.parse(src.read_text())
        subjects = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            pairs = {k.value: v.value for k, v in zip(node.keys, node.values)
                     if isinstance(k, ast.Constant)
                     and isinstance(v, ast.Constant)}
            decision = str(pairs.get("decision", ""))
            if decision.endswith("_ZONE_CONFIRMED") and "subject" in pairs:
                subjects.add(str(pairs["subject"]))
        assert subjects == set(CONFIRMED_TODAY), (
            "the confirmed zone set moved. This file's CONFIRMED_TODAY and "
            "BASELINE are now the only place apps/ire holds it — §AC2(b) took "
            "the names out of container_label_construction.py at WI-Z — so a "
            "human has to decide whether the new zone is a multi-layer "
            "surface and update BASELINE, which is the number zone_set_covers "
            "compares against")


class TestTheAxisAB1b:
    """§AB1(b) — "axis blocking"."""

    def test_it_blocks_in_the_vocabulary_that_already_exists(self):
        """UNMEASURED, not MEASURED_FAIL. Nothing here has been shown to be
        WRONG — a converter may well run this label tomorrow. What is true is
        that the claim has never been measured, and `required: True` is what
        makes an unmeasured required axis block instead of passing quietly.

        The constants are imported from `container_fidelity` rather than
        retyped, so this also pins that the axis speaks the existing language
        instead of a second one invented alongside it.
        """
        from apps.ire.container_fidelity import UNMEASURED

        axis = lc.label_construction_axis(
            lc.measure_label_construction(AB1_RECORD,
                                          confirmed_zones=CONFIRMED_TODAY,
                                          contracted_count=BASELINE))
        assert axis["state"] == UNMEASURED
        assert axis["required"] is True
        assert lc.MANUFACTURABILITY_UNCONFIRMED in axis["codes"]
        assert lc.ZONE_SET_LACKS_SURFACE in axis["codes"]

    def test_the_block_is_a_measurement_and_not_a_hard_wired_no(self):
        """§AB0(c) — the negative control. An axis that blocks unconditionally
        is not measuring anything, it is only wearing the costume of care.

        Nothing authorized in this sprint can reach the state below: §C2 is
        permanent, so `SUPPLIER_CONFIRMED` cannot be produced, and the fourth
        zone would be the §X2(a) contract change. That is exactly why the path
        has to be exercised HERE — it is the only place it can be, and an
        unexercised clearing path is indistinguishable from no path at all.
        """
        from apps.ire.container_fidelity import MEASURED_PASS

        cleared = lc.measure_label_construction(
            {"construction": lc.MULTI_LAYER,
             "provenance_stage": lc.STAGE_SUPPLIER_CONFIRMED},
            confirmed_zones=(*CONFIRMED_TODAY, "z_peel_back"),
            contracted_count=BASELINE)
        assert cleared["codes"] == []
        assert cleared["blocking"] is False
        assert lc.label_construction_axis(cleared)["state"] == MEASURED_PASS

    def test_each_condition_blocks_on_its_own(self):
        """Two independent conditions, so neither may be load-bearing for the
        other. Clearing one at a time must still block."""
        supplier_only = lc.measure_label_construction(
            {"construction": lc.MULTI_LAYER,
             "provenance_stage": lc.STAGE_SUPPLIER_CONFIRMED},
            confirmed_zones=CONFIRMED_TODAY, contracted_count=BASELINE)
        assert supplier_only["codes"] == [lc.ZONE_SET_LACKS_SURFACE]
        assert supplier_only["blocking"] is True

        zone_only = lc.measure_label_construction(
            AB1_RECORD, confirmed_zones=(*CONFIRMED_TODAY, "z_peel_back"),
            contracted_count=BASELINE)
        assert zone_only["codes"] == [lc.MANUFACTURABILITY_UNCONFIRMED]
        assert zone_only["blocking"] is True


class TestTheBlockIsScopedToWhatAB1RuledOn:
    """The correction this file found by asking what wiring the axis in would
    actually do. §AB1(b) put the MULTI-LAYER target's manufacturability in
    question; it said nothing about the label the repository already prints."""

    def test_todays_single_layer_container_measures_clean(self):
        """**The test that decides whether the axis is wireable at all.**

        Every container in this repository is single-layer with the three
        confirmed zones. If that state blocked, wiring `label_construction
        _axis` into the fidelity report would fail every container it measured
        — and a gate that fails everything has stopped measuring. So this is
        not a convenience case, it is the one that says the block discriminates.
        """
        from apps.ire.container_fidelity import MEASURED_PASS

        report = lc.measure_label_construction(
            {"construction": lc.SINGLE_LAYER}, confirmed_zones=CONFIRMED_TODAY)
        assert report["codes"] == []
        assert report["blocking"] is False
        assert lc.label_construction_axis(report)["state"] == MEASURED_PASS

    def test_the_field_stays_literally_true_even_where_it_does_not_block(self):
        """Scoping the BLOCK is not the same as claiming a confirmation.

        Nobody has confirmed the single-layer label either — §C2 means nobody
        has been asked — so `manufacturability` still reads UNCONFIRMED. What
        changes is that §AB1(b)'s block does not reach past its subject. The
        two facts stay separate, which is this module's entire premise applied
        to itself.
        """
        report = lc.measure_label_construction(
            {"construction": lc.SINGLE_LAYER}, confirmed_zones=CONFIRMED_TODAY)
        assert report["manufacturability"] == lc.UNCONFIRMED
        assert lc.MANUFACTURABILITY_UNCONFIRMED not in report["codes"]

    def test_the_multi_layer_target_still_blocks_on_it(self):
        """The complement: scoping must not have quietly disarmed §AB1(b)."""
        report = lc.measure_label_construction(
            AB1_RECORD, confirmed_zones=(*CONFIRMED_TODAY, "z_peel_back"),
            contracted_count=BASELINE)
        assert report["codes"] == [lc.MANUFACTURABILITY_UNCONFIRMED]


class TestTheRecordReadsAsWhatItIs:
    def test_the_ab1_record_measures_as_owner_directed_and_unconfirmed(self):
        report = lc.measure_label_construction(
            AB1_RECORD, confirmed_zones=CONFIRMED_TODAY)
        assert report["schema_version"] == "container_label_construction/1.0"
        assert report["construction"] == lc.MULTI_LAYER
        assert report["provenance_stage"] == lc.STAGE_OWNER_DIRECTED
        assert report["manufacturability"] == lc.UNCONFIRMED
        assert report["blocking"] is True
        assert report["confirmed_zones_examined"] == sorted(CONFIRMED_TODAY)

    def test_a_disclosure_field_is_absent_when_there_is_nothing_to_disclose(self):
        """Shaped like `measure_method_provenance`: a reader never has to
        distinguish "no finding" from "the field was not populated"."""
        blocked = lc.measure_label_construction(
            AB1_RECORD, confirmed_zones=CONFIRMED_TODAY,
            contracted_count=BASELINE)
        assert blocked["assumption"] and blocked["zone_note"]

        cleared = lc.measure_label_construction(
            {"construction": lc.MULTI_LAYER,
             "provenance_stage": lc.STAGE_SUPPLIER_CONFIRMED},
            confirmed_zones=(*CONFIRMED_TODAY, "z_peel_back"),
            contracted_count=BASELINE)
        assert cleared["assumption"] is None
        assert cleared["zone_note"] is None

    def test_the_default_construction_is_todays_and_not_the_target(self):
        """An unsigned record is SINGLE_LAYER — what the repository actually
        builds. Defaulting to the ruled target would make every unattributed
        record claim the new construction had arrived."""
        assert lc.measure_label_construction({})["construction"] == \
            lc.SINGLE_LAYER


class TestItIsProvenanceAndStructureNotADieline:
    """WI-X: "This is a provenance and structure item, not a dieline — do not
    draw a peel-reveal label this sprint.\""""

    def test_the_module_imports_with_no_django_and_no_settings(self):
        """Purity, run rather than asserted about: a subprocess with no
        DJANGO_SETTINGS_MODULE loads the module by path. The one import of
        `container_fidelity` is deferred into `label_construction_axis`
        precisely so this holds, since that module reaches into
        `apps.pipeline.services`.
        """
        proc = subprocess.run(
            [sys.executable, "-c",
             "import importlib.util as u, sys\n"
             "s = u.spec_from_file_location('lc', sys.argv[1])\n"
             "m = u.module_from_spec(s); s.loader.exec_module(m)\n"
             "assert m.RULED_VARIANT is None\n"
             "print(sorted(k for k in sys.modules if k.startswith('django')))",
             str(ROOT / "apps/ire/container_label_construction.py")],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip().endswith("[]"), proc.stdout

    def test_it_produces_no_geometry_of_any_kind(self):
        """The refusal, made checkable. Every value the module returns is a
        string, a bool, None or a container of those — there is no coordinate,
        no dimension and no length anywhere in the record, which is what "not
        a dieline" means when written as a test rather than as an intention.
        """
        report = lc.measure_label_construction(
            AB1_RECORD, confirmed_zones=CONFIRMED_TODAY)

        def scalars(value):
            if isinstance(value, dict):
                for item in value.values():
                    yield from scalars(item)
            elif isinstance(value, (list, tuple, set, frozenset)):
                for item in value:
                    yield from scalars(item)
            else:
                yield value

        assert all(v is None or isinstance(v, (str, bool))
                   for v in scalars(report))
        assert all(v is None or isinstance(v, (str, bool))
                   for v in scalars(lc.label_construction_axis(report)))


class TestTheBaselineMovedWithoutMovingAVerdict:
    """§AH raised `BASELINE` from 3 to 4. This class is the evidence that no
    construction verdict moved with it — and the record of why that had to be
    checked rather than reasoned about.

    §AH4 predicted the hash consequences of confirming `z_wrap` and named three
    functions: `zone_hash`, `zone_set_hash`, `combined_confirmation_hash`. All
    three held. But `BASELINE` is a fourth consumer of the confirmed set's
    LENGTH, in a different app, feeding the arithmetic `len(zones) >
    contracted_count` at every `zone_set_covers` call site in this file, and
    the ruling did not mention it. The fix turned out safe. A ruling that
    understates its own blast radius is defective anyway, because "it was safe"
    was discovered afterwards and could as easily have gone the other way.
    """

    def test_the_verdict_is_relative_to_the_baseline_not_to_the_number_three(self):
        """WHY nothing moved, stated as the property rather than as the result.

        `zone_set_covers` compares a length against a baseline it is handed. If
        every caller hands it `BASELINE`, then raising both the set and the
        baseline together is a no-op by construction — the same set is still
        "exactly the confirmed set", one more is still "one more". Asserted at
        three and at four explicitly, so the invariant is visible rather than
        inferred from the suite passing.
        """
        for n in (3, 4, 5):
            confirmed = tuple(f"z_{i}" for i in range(n))
            assert lc.zone_set_covers(
                lc.MULTI_LAYER, confirmed, contracted_count=n) is False
            assert lc.zone_set_covers(
                lc.MULTI_LAYER, (*confirmed, "z_extra"),
                contracted_count=n) is True

    def test_source_guard_no_caller_hard_codes_the_old_baseline(self):
        """SOURCE-STRING GUARD.

        The property above holds *only if every caller passes `BASELINE`*. A
        caller that typed `contracted_count=3` would have been correct until
        §AH and silently wrong after it — reporting "there is an extra surface"
        for a jar carrying exactly the four confirmed zones, which is the
        false positive that would send a label into multi-layer handling it
        does not need.

        This is the failure mode §AH4 should have named and did not, so it gets
        a guard rather than a sentence. Scoped to this file plus the module
        under test, because those are the only places `contracted_count` is
        spelled; a wider scan would be a different instrument with a different
        denominator and is not what this claims to be.

        IT IS AST AND NOT A REGEX, AND THE FIRST DRAFT WAS THE REGEX. That
        draft matched `contracted_count=3` inside the paragraph above and
        inside its own negative control, and reported three offenders in a file
        with none — the identical false positive WI-Z hit when its zone-name
        scanner fired on the word `z_zone` in its own filename, and the reason
        that scanner grew a word boundary. A guard that cannot tell a call from
        a sentence about a call fails on any file that documents itself, which
        makes the documentation the thing you delete to get green. Matching a
        real `ast.keyword` on a real `ast.Call` is not a stricter regex; it
        removes the class.
        """
        watched = (
            pathlib.Path(__file__),
            ROOT / "apps/ire/container_label_construction.py",
        )
        offenders = []
        for path in watched:
            offenders += [f"{path.name}:{line}" for line
                          in _numeric_contracted_count(path.read_text())]
        assert offenders == [], (
            "a numeric literal is being passed as contracted_count. It has to "
            "be BASELINE, which follows CONFIRMED_TODAY, which is pinned to "
            "the contract: " + "; ".join(offenders))

    def test_the_guard_above_would_see_a_hard_coded_baseline(self):
        """NEGATIVE CONTROL for it. §AA — the guard returned an empty list, and
        an empty list is also what a scanner returns when it is looking for the
        wrong node type. Real source, one offending call spliced in.

        The third assertion is the one that earns the rewrite: the same text
        sitting in a string literal must NOT be found, because that is the
        shape the regex version tripped on.
        """
        real = (ROOT / "apps/ire/container_label_construction.py").read_text()
        assert _numeric_contracted_count(real) == []
        assert _numeric_contracted_count(
            real + "\nzone_set_covers(1, (), contracted_count=3)\n") != []
        assert _numeric_contracted_count(
            real + '\nDOC = "pass contracted_count=3 here"\n') == []
        assert _numeric_contracted_count(
            "f(contracted_count=BASELINE)") == []
