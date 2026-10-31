"""§W4 — the weight rationale, checked against the documents that are emitted.

§W4 ruled that the Gate-A divider and the container front rule are DIFFERENT
OBJECTS and that both numbers stand. Neither number is changed here and this
file's first job is to keep it that way: each one is asserted against its own
site, so a future edit to either constant fails here rather than passing
quietly because the rationale transcribed a copy.

Its second job is the thing recording the rationale turned up. §W4(b) was
written about ``compose_container.py``'s 0.25 mm, and that rule is on a branch
no caller in the repo reaches. The rule production DOES draw is a different
element on the dropper sheet. Both facts are pinned from emitted documents,
not from reading the source, because reading the source is what made the
ruling look settled in the first place.

THAT SENTENCE ENDED "at 0.20 mm" UNTIL §BB7(e), and the width half of it is
now false. C16(b) ruled the dropper sheet's rule to 0.30 mm at opacity 1.0,
which is the width the unreached rule already carried, so the two no longer
differ by width — they differ by whether they are drawn, and the tests below
tell them apart by ``emitted`` for that reason.

AND THE OTHER HALF IS FALSE AS OF §BB7(c). "A branch no caller in the repo
reaches" was already narrowed once (no PRODUCTION caller) and is now simply
wrong: the owner ruled both production call sites wired, they supply
``hierarchy_lines``, and the container front rule is drawn. So ``emitted`` no
longer tells the two rules apart either — BOTH paragraphs above described a
distinction that has since been ruled away, which is why the tests below tell
them apart by COMPOSER, the one ground §W4 actually ruled on. The paragraphs
stay because two successive rulings each falsifying the previous re-proof is
the history a reader needs to understand why the third one is phrased as it
is. No weight is restated in this docstring; each is asserted against the
emitted document below.
"""
from pathlib import Path

from apps.ire import container_line_weight as clw
from apps.ire import container_motif as cm
from apps.ire import container_production_method as cpm
from apps.ire.compose_container import compose_container_graph
from apps.ire.compose_dropper import compose_dropper_sheet
from apps.ire.front_hierarchy import ruled_front_hierarchy
from apps.pipeline.services import ai8_color
from apps.pipeline.services import container_contract as cc
from apps.pipeline.targets.container import ContainerProfile
from apps.pipeline.targets.container.silhouettes import build_backbone

REPO = Path(clw.__file__).parents[2]

_GEOMETRY = {"total_height_mm": 104.0, "body_height_mm": 70.5,
             "body_diameter_mm": 31.5, "collar_height_mm": 9.5,
             "bulb_height_mm": 21.5, "collar_diameter_mm": 21.5,
             "bulb_width_mm": 11.0, "visible_neck_mm": 2.5,
             "neck_diameter_mm": 9.0, "base_thickness_mm": 3.5,
             "shoulder_radius_mm": 3.0, "frost_intensity": 0.7,
             "translucency": 0.35}


def _strokes(doc, node_name):
    """Every stroked node called ``node_name``, as (width_mm, opacity)."""
    found = []

    def walk(node):
        if str(getattr(node, "name", "")) == node_name:
            stroke = getattr(node, "stroke", None)
            if stroke is not None and getattr(stroke, "width_mm", None):
                found.append((float(stroke.width_mm),
                              float(getattr(stroke, "opacity", 1.0) or 1.0)))
        for child in getattr(node, "children", []) or []:
            walk(child)

    walk(doc.root)
    return found


def _container_kwargs():
    profile = cc.build_inferred_profile("bottle", estimates={
        "body_width_mm": 40.0, "body_height_mm": 110.0,
        "cap_width_mm": 20.0, "cap_height_mm": 13.0})
    zones = cc.propose_zones(profile)
    spec = cm.build_motif_spec(
        {"verified": True, "motif_signature": "powder constellation"},
        {"fields": {}}, zones, profile)
    backbone = build_backbone(ContainerProfile(
        archetype="bottle", width_mm=40, height_mm=110))
    return backbone, {"product_name": "Rose Nectar",
                      "name_lines": ["Rose Nectar"], "zones": zones,
                      "native": True, "motif_spec": spec}


def _dropper_document():
    return compose_dropper_sheet(
        _GEOMETRY,
        zones=[{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE",
                "x": 5.5, "y": 10.0, "width": 22.0, "height": 40.0}],
        reference_path=None, logo_path=None, product_name="Rose Damascena",
        sku="X", back_sections=[{"heading": "P", "text": "x"}],
        revision_status="TEST")


class TestNeitherNumberChanged:
    """§W4: both numbers stand. The record may not be the only copy of either.

    AMENDED AT §AU2, AND THE CLASS NAME IS NOW HALF WRONG — deliberately left
    standing rather than renamed, because the name is the record of what §W4
    believed and the amendment is the record of what superseded it. **One
    number changed**: the container front rule is 0.30 mm on OWNER authority.
    The Gate-A divider is untouched, and the reason is the whole point of §W4's
    "different objects" ruling — 0.362384 pt was MEASURED out of an accepted
    proof, and no ruling supersedes a measurement.

    WHAT THIS CLASS ACTUALLY GUARDS, and it is unchanged: that the record is
    not the only copy of either number. The site and the record must agree, so
    a value edited in one place and not the other fails here. Updating the
    literals below to a ruled value is not weakening that detector; deleting
    the second half of either assertion would be.
    """

    def test_the_gate_a_divider_is_read_from_the_proofs_own_constant(self):
        assert clw.ELEMENTS["gate_a_divider"]["width_pt"] == \
            ai8_color.DIVIDER_WIDTH_PT

    def test_the_container_front_rule_is_the_weight_the_composer_draws(self):
        backbone, kwargs = _container_kwargs()
        doc = compose_container_graph(backbone, hierarchy_lines=[
            {"text": "Rose Nectar", "rel": 1.0, "kind": "product_name"}],
            **kwargs)
        assert _strokes(doc, "rule-front-single") == [(0.30, 1.0)]
        assert clw.ELEMENTS["container_front_rule"]["width_mm"] == 0.30
        # The superseded value is kept in the record, not erased from it, so
        # that "0.25 was here" survives as history instead of as a puzzle.
        element = clw.ELEMENTS["container_front_rule"]
        assert element["superseded_value_mm"] == 0.25
        assert element["authority"].startswith("OWNER_RULED — §AU2")

    def test_emitted_flipped_on_reachability_and_not_on_the_width_ruling(self):
        """§AU2: "`emitted` flips to True ONLY when the branch is genuinely
        reached — not as part of the same edit, and not on the strength of this
        ruling." A ruling about a WEIGHT is not evidence about REACHABILITY,
        and `emitted` is the field built to catch exactly that substitution.

        THE FLIP HAS HAPPENED AND §AU2'S CONDITION IS WHAT PERMITTED IT: not
        the width ruling, but §BB7(c), which wired both production call sites.
        So this test inverts its literal and keeps its whole job. What it
        guards is the SUBSTITUTION, and the substitution is now the live risk
        rather than the dormant one — an `emitted: True` resting on a ruling
        about anything other than reachability is the failure §AU2 named, and
        `is False` can no longer detect it.

        Asserted instead: the flip cites the WIRING. §AU2 is the width
        authority and appears in `authority`; it must not appear in
        `emitted_because`, because a width ruling explaining an emission claim
        is precisely the swap. The reachability itself is re-derived from
        source in `test_both_ruled_production_callers_supply_it` below — this
        one checks that the RECORD says the right kind of thing, that one
        checks that the thing it says is true."""
        element = clw.ELEMENTS["container_front_rule"]
        assert element["emitted"] is True
        because = element["emitted_because"]
        assert "§BB7(c)" in because
        assert "apps/pipeline/targets/container/__init__.py" in because
        assert "apps/pipeline/services/native_handoff.py" in because
        assert "§AU2" not in because, \
            "the width ruling is being offered as evidence of reachability"
        # §AZ0(u) — the pre-wiring rationale is retained beside the flip, so
        # "it was unreached" survives as history instead of as a puzzle
        assert "no PRODUCTION caller passes it" in \
            element["superseded_unreached_because"]

    def test_the_dropper_front_rule_is_the_weight_that_sheet_draws(self):
        drawn = _strokes(_dropper_document(), "rule-front-single")
        assert drawn == [(0.30, 1.0)]
        element = clw.ELEMENTS["dropper_front_rule"]
        assert (element["width_mm"], element["opacity"]) == drawn[0]
        # §BB7(e) moved this element; the pre-ruling pair stays readable in the
        # record rather than being erased from it, as §AU2 did for the other.
        assert element["superseded_value_mm"] == 0.2
        assert element["superseded_opacity"] == 0.8
        assert element["authority"].startswith("OWNER_RULED — §BB7(e)")

    def test_the_flat_view_draws_it_too_which_the_record_claimed_untested(self):
        """The record has said "on both the dimensional and the flat view"
        since before §BB7(e), and nothing proved the second half: `_strokes`
        matches names EXACTLY, the flat copy is built with `prefix="flat-"`,
        so every assertion above sees one of the two nodes and calls it the
        set. Measured here rather than reasoned about — the flat view is laid
        out at a scale factor (`flat_s`), so "it is the same call" is not an
        argument that the stroke came through unscaled."""
        doc, found = _dropper_document(), []

        def walk(node):
            if str(getattr(node, "name", "")).endswith("rule-front-single"):
                stroke = getattr(node, "stroke", None)
                found.append((str(node.name), float(stroke.width_mm),
                              float(getattr(stroke, "opacity", 1.0) or 1.0)))
            for child in getattr(node, "children", []) or []:
                walk(child)

        walk(doc.root)
        element = clw.ELEMENTS["dropper_front_rule"]
        pair = (element["width_mm"], element["opacity"])
        assert found == [("rule-front-single",) + pair,
                         ("flat-rule-front-single",) + pair]

    def test_the_two_ruled_objects_still_stand_apart_by_the_ruled_ratio(self):
        """§W4's ratio was 1.9556 and is now 2.3467, because §AU2 moved the
        numerator and nothing may move the denominator. THE RATIO WAS NEVER
        THE RULED THING — §W4 ruled that these are different objects, and the
        ratio is a consequence of two independently-held numbers, which is
        why it is recomputed here rather than stored anywhere. Pinning it
        keeps a silent drift in EITHER number visible; it does not claim the
        ratio itself means anything."""
        divider_mm = ai8_color.DIVIDER_WIDTH_PT * clw.MM_PER_PT
        ratio = clw.ELEMENTS["container_front_rule"]["width_mm"] / divider_mm
        assert round(ratio, 4) == 2.3467
        # and they are still two objects, which IS the ruled thing
        assert clw.ELEMENTS["container_front_rule"]["width_mm"] != \
            round(divider_mm, 6)


class TestTheRecordSaysWhichRuleIsActuallyDrawn:
    """The fact §W4 could not have known: it ruled about an unreached number.

    IT IS NO LONGER UNREACHED. §BB7(c) wired both production call sites, so
    this class's subject changed from "which of the two is drawn" to "both are
    drawn, and here is what still tells them apart". The old sentence is kept
    above because §W4's ruling was made under it and reads as nonsense
    without it."""

    def test_the_ruled_rule_is_absent_when_the_argument_is_absent(self):
        """RENAMED FROM ``..._from_the_document_the_target_emits``, because
        §BB7(c) made that name false: the document the target emits is now the
        one built WITH ``hierarchy_lines``, measured in the test below. What
        this measures is unchanged and still worth measuring — the branch is
        gated on the ARGUMENT, not on a flag or a setting, so a caller that
        stops passing it silently loses the front rule."""
        backbone, kwargs = _container_kwargs()
        doc = compose_container_graph(backbone, **kwargs)
        assert _strokes(doc, "rule-front-single") == []

    def test_the_ruled_rule_is_drawn_in_the_document_the_target_now_emits(self):
        """THE MEASUREMENT THAT EARNS ``emitted: True`` — taken on the emitted
        document, through the same helper both production call sites use, not
        inferred from the fact that they call it. §AU2 required the flip to
        rest on the branch being "genuinely reached"; this is what reached
        means, measured."""
        backbone, kwargs = _container_kwargs()
        # §BH65(b)1: the descriptor is the caller's to name. This test measures
        # the RULE, and the Rose Nectar fixture is the serum §BB7(a) ruled for.
        doc = compose_container_graph(
            backbone, hierarchy_lines=ruled_front_hierarchy(
                "Rose Nectar", descriptor="FACIAL SERUM"),
            **kwargs)
        element = clw.ELEMENTS["container_front_rule"]
        assert _strokes(doc, "rule-front-single") == [(0.30, 1.0)]
        assert element["width_mm"] == 0.30
        assert element["emitted"] is True

    def test_what_still_tells_the_two_rules_apart_is_the_composer(self):
        """THIS TEST HAS BEEN RE-PROVED TWICE AND BOTH GROUNDS ARE GONE.

        It told them apart by WIDTH until §BB7(e) ruled both to 0.30 mm. It
        then told them apart by EMISSION, on the owner's own re-proof — "the
        real difference between the two rules is that one is drawn and one is
        not" — and §BB7(c) has now wired the container front, so both are
        drawn. Two owner rulings, and the second falsified the first's stated
        distinction; recorded here per §AC rather than repaired in passing,
        and queued for the owner, because a sentence in a ruling going stale
        is the owner's to re-word, not mine.

        What is left is not a weaker distinction, it is the original one:
        §W4 ruled these are DIFFERENT OBJECTS. Different composers, different
        sheets, two independently-held numbers that presently agree. The
        agreement is the thing that could drift silently, so it is asserted —
        as a coincidence of two records, never as one number read twice."""
        container = clw.ELEMENTS["container_front_rule"]
        dropper = clw.ELEMENTS["dropper_front_rule"]
        assert container["emitted"] is True and dropper["emitted"] is True
        assert container["width_mm"] == dropper["width_mm"]
        assert container["site"].split(" ", 1)[0] != \
            dropper["site"].split(" ", 1)[0]
        assert container["authority"] != dropper["authority"]

    def test_wiring_the_branch_up_forces_the_rationale_to_be_revisited(self):
        """``emitted: False`` is a claim about the whole repo, so the whole repo
        is what checks it. Supplying ``hierarchy_lines`` from anywhere makes the
        ruled width reachable and turns an unreached number into a printed one
        — which is a different rationale, not the same one with a new caller.

        THAT SENTENCE READ ``the 0.25 mm`` UNTIL §AU2 AND WAS THEN WRONG FOR
        THE LENGTH OF ONE EDIT. §AU2 moved the width to 0.30 and this docstring
        kept quoting the superseded number — the exact rot the census file
        records at WI-3F, arriving in this file. It is written as ``the ruled
        width`` now so that the next ruling cannot falsify it: the number lives
        in ``container_line_weight.ELEMENTS`` and the assertions below read it
        from there, so prose that names no number cannot go stale.

        AMENDED BY SPRINT 13 WI-T, and the amendment is the interesting part.
        This assertion went RED because WI-T's own test began exercising the
        direct-print branch, in order to measure what WI-T's fix cost on it
        (the descriptor tier was 3.85 pt at 40x110 and is now 3.2). The
        tempting repair was to spell the keyword some way this grep could not
        see — ``**{"hierarchy_lines": ...}`` — which would have satisfied the
        guard by defeating it, and is precisely the evasion §Y2 exists to
        forbid. So the file is added by name instead.

        The claim is UNCHANGED and worth restating, because a fourth entry
        could be read as it weakening: no PRODUCTION caller supplies
        ``hierarchy_lines``. All three of the entries that are not the
        composer are a test or its rationale module, and a test exercising a
        branch is what makes it measured, not what makes it shipped.

        FOUR -> FIVE AT §AV2, AND THIS ENTRY IS WEAKER THAN ALL FOUR BEFORE
        IT — it is PROSE. ``test_av2_brand_strings.py`` does not call the
        composer, does not import it, and never spells the keyword outside a
        docstring: it quotes §AU5's sentence about what happens "if the
        executor feeds a placeholder descriptor into ``hierarchy_lines``
        today". That is the justification for the sibling guard existing, so
        deleting the sentence to keep this grep green would be shaping the
        record to suit the instrument — the same move as respelling the
        keyword, applied to a comment instead of a call. The file goes in the
        list unfiltered, on ``test_wio_on_pack_copy.py``'s principle that a
        guard which has started deciding which mentions count is the thing
        §Y2 opens on.

        THE TRIPWIRE IS STILL ARMED, which is the only thing that matters
        here. §AU5(3) — supplying ``hierarchy_lines`` with a ⟪PROVISIONAL⟫
        descriptor — has NOT been done at the time of this amendment. The
        assertion is exact equality, so the file that does it will be a SIXTH
        entry and will turn this red exactly as designed. What this amendment
        must not become is a habit: if a future entry is an edge rather than
        a mention, the answer is to revisit §W4's rationale, never to extend
        the list again.

        FIVE -> SIX AT §AU2, AND THE PREVIOUS PARAGRAPH TOLD ME NOT TO DO
        THIS. Recorded plainly rather than quietly complied with, because an
        instruction I wrote and then overrode is worth more visible than
        obeyed. The sixth entry, ``test_au3_divider_gates.py``, is a MENTION
        by that paragraph's own distinction — it composes documents to measure
        the THIRD gate AU2 named, exactly as this file already composes them
        to measure the weight. It is not a production caller. So the sentence
        that fits it is the one about mentions, and the instruction it
        violates was written about mentions accumulating. Both are true, and
        the tie is broken by strengthening rather than by argument:

        **The list was always a PROXY for a claim, and the claim is now
        asserted directly** in ``test_no_production_caller_supplies_it``
        below. That assertion does not care how many test files exist and
        cannot be satisfied by editing a list, so if the two ever disagree it
        is the one to believe. The list stays because it still catches the
        thing a categorical rule cannot — a new mention nobody thought about —
        but it is no longer the only thing standing between this repository
        and a silently-wired front.

        §AU2 also did what the paragraph above asks for: the rationale in
        ``container_line_weight.py`` WAS revisited, and the number changed
        with it, from 0.25 mm to a ruled 0.30 mm.

        SIX -> SEVEN AT §AY2, THE SECOND CONSECUTIVE TRANCHE TO DO THE THING
        THE LIST'S OWN NOTE FORBIDS. Two in a row is no longer a story about
        either tranche; it is evidence about the LIST, and it is recorded here
        rather than resolved quietly. ``test_au3_brand_usage.py`` is a MENTION
        by the same distinction that admitted the sixth: it composes fronts in
        four states to measure whether the mark's clear space is respected,
        and a state that supplies no hierarchy cannot be compared against one
        that does without naming the keyword. It is not a production caller.
        The honest reading is that the "never extend the list again"
        instruction was written about an instrument that had already stopped
        being the right one for this claim — which is why §AU2 replaced it
        with ``test_no_production_caller_supplies_it`` rather than tightening
        it. The list survives as a catcher of the unthought-of mention. It is
        no longer the claim.

        **AND THE TRIPWIRE THAT PARAGRAPH ARMED HAS NOW FIRED.** The §AU2
        amendment said "§AU5(3) — supplying ``hierarchy_lines`` with a
        ⟪PROVISIONAL⟫ descriptor — has NOT been done at the time of this
        amendment". As of §AY2 it has: ``_SUPPORT_TIER`` in the seventh entry
        is ``{"text": "⟪PROVISIONAL⟫ PLACEHOLDER-SUPPORT", "kind":
        "descriptor"}`` and it reaches the composer. What fired is worth
        stating exactly, because "the tripwire fired" and "§AU5(3) happened"
        are not the same event:

          * §AZ5(e) rules that measuring the geometry a real front will occupy
            is not emitting one, and that a probe with visibly synthetic
            strings is the sanctioned way to measure the future state. Nothing
            here is written to disk.
          * The marker is present ON PURPOSE. An unmarked placeholder would
            have refused the commit; the marker is what makes the string a
            measurement instead of copy.

            THIS BULLET RECORDED A READING OF ``tools/brand_strings.py`` AND
            §BB7(a) FALSIFIED IT. It said the guard "reads the file and reports
            ``2 sites, 2 already marked``". Measured after §BB7(a): ``sites: 2
            (1 already marked, 1 ruled)``. Both sites are still there and this
            one is still marked — what changed is the OTHER one, the front
            descriptor, which the owner ruled and which is now carried by a
            register entry rather than by a marker. Nothing in the suite
            asserted that sentence, so it would have stayed green and false;
            it is corrected here because the commit that falsified it is the
            commit that should carry the correction.
          * The guard that would actually stop this becoming an artefact is
            ``refuse_if_provisional``, called from ``emitters/pdf_ai.py:56``
            — at the EMITTER, per §AW1. Any of these four documents handed to
            a PDF or AI emitter is refused there. That is the closure. This
            grep is a notice board.

        So the list grew by one and the claim it proxies for did not move:
        ``test_no_production_caller_supplies_it`` is still green and still
        asserts ``callers == set()``.

        SEVEN -> NINE AT §BB7(c), AND THIS IS THE ONE THE LIST WAS BUILT FOR.
        Every previous growth was a MENTION, and each time the note said so
        apologetically. These two are not mentions and not tests:
        ``apps/pipeline/targets/container/__init__.py`` and
        ``apps/pipeline/services/native_handoff.py`` are the two PRODUCTION
        call sites the owner named at OWNER_BLOCKER_CLEARANCE.md:10559 — "Wire
        both call sites ... One front from every path. My ruling." This is
        exactly the edge the §AU5 amendment reserved: "if a future entry is an
        edge rather than a mention, the answer is to revisit §W4's rationale,
        never to extend the list again."

        BOTH HAPPENED, AND THAT IS NOT A CONTRADICTION. §W4's rationale WAS
        revisited — ``container_line_weight.py`` now records ``emitted: True``
        with the wiring as its reason and keeps the superseded unreached-ness
        beside it — and the list is extended too, because the list's job was
        never to hold the claim. Its job is to make an unthought-of appearance
        of this keyword loud, and it did that here: this assertion is the one
        that went red when the wiring landed. The instruction was written to
        stop the list ABSORBING an edge in place of revisiting the rationale.
        Doing the revision and then recording the new set is the opposite of
        absorbing it.

        The claim below moved with the ruling rather than being edited around
        it: ``test_both_ruled_production_callers_supply_it`` now asserts the
        callers ARE those two, and no others.

        NINE -> TWELVE AT §BB7(g)(a), AND THE THIRD ENTRY IS A CATEGORY THIS
        LIST HAD NOT SEEN. Two of the three are ordinary: ``test_wiu_front_
        collision.py`` composes dropper sheets from a hierarchy to measure
        what arrives, and ``test_wiy_leading_metric_floor.py`` names the
        keyword as a string literal inside a §Y2 guard. Mentions, both.

        ``apps/ire/compose_dropper.py`` is neither a mention nor a caller. It
        is a THIRD COMPOSER that now ACCEPTS ``hierarchy_lines`` and destructures
        it, and accepting is not passing. Every previous growth of this list
        could be sorted into "prose about the keyword" or "a site that supplies
        it"; this one is a site that RECEIVES it, and the distinction is the
        whole reason the claim below stays green while this assertion went red.

        §W4'S RATIONALE WAS NOT REVISITED, AND THAT IS A FINDING RATHER THAN A
        DUCKED INSTRUCTION. The §AU5 note says an EDGE requires revisiting the
        rationale. The rationale is about ``compose_container.py
        rule-front-single`` — whether the CONTAINER front rule is drawn — and
        ``emitted: True`` rests on the two ruled call sites still passing the
        keyword into ``compose_container_graph``. A different composer accepting
        the same keyword does not touch that: it draws no container front rule.
        So the rationale is unchanged because it is still exactly true, which is
        a different state from "unchanged because nobody looked". Recorded so
        the next reader can tell the two apart.

        WHY THE CATEGORICAL GUARD IS STILL TOTAL OVER THE NEW ACCEPTOR, measured
        rather than asserted. ``compose_dropper_sheet``'s ``hierarchy_lines`` is
        KEYWORD-ONLY (it sits after ``methods_record`` in ``kwonlyargs``), so a
        production module cannot feed the dropper front without writing
        ``hierarchy_lines=`` at a call site — which is precisely the shape the
        AST walk below detects. Had the parameter been positional-or-keyword, a
        third production path could have been wired past that guard entirely,
        and this list would have been the only thing left. It is not, and the
        parameter's kind is the reason.
        """
        import subprocess

        result = subprocess.run(
            ["grep", "-rln", "hierarchy_lines", "--include=*.py", "."],
            cwd=str(REPO), capture_output=True, text=True)
        touching = {line.lstrip("./") for line in
                    result.stdout.strip().splitlines() if line}
        assert touching == {"apps/ire/compose_container.py",
                            "apps/ire/compose_dropper.py",
                            "apps/ire/container_line_weight.py",
                            # §BH70(1), 2026-09-27: a MENTION — its tests compose the ruled front production draws to
                            # prove a name the front would cut is refused, never drawn cut (§BD(b)); not a caller
                            "apps/ire/tests/test_compose_container.py",
                            "apps/ire/tests/test_au3_brand_usage.py",
                            "apps/ire/tests/test_au3_divider_gates.py",
                            "apps/ire/tests/test_av2_brand_strings.py",
                            "apps/ire/tests/test_container_line_weight.py",
                            "apps/ire/tests/test_wit_unit_analysis.py",
                            "apps/ire/tests/test_wiu_front_collision.py",
                            "apps/ire/tests/test_wiy_leading_metric_floor.py",
                            "apps/pipeline/services/native_handoff.py",
                            # [his test day finding 3, 2026-09-30] a MENTION — its test composes the ruled front
                            # production draws to prove the name stack begins below the concept's colour split; not a
                            # caller
                            "apps/pipeline/tests/test_2b3v_corr4_geometry.py",
                            # [his look at 117 drawn from its map, 2026-10-02] a MENTION — its test composes the ruled
                            # front production draws to prove the traced drips are drawn as curves; not a caller
                            "apps/pipeline/tests/test_vqr2b_concept_analysis.py",
                            "apps/pipeline/targets/container/__init__.py"}

    def test_both_ruled_production_callers_supply_it(self):
        """THE CLAIM THE LIST ABOVE WAS ALWAYS A PROXY FOR, asserted so that
        it survives the list being edited.

        RENAMED AND INVERTED AT §BB7(c), NOT WEAKENED — THE OWNER INVERTED ITS
        PREMISE. It was ``test_no_production_caller_supplies_it`` and asserted
        ``callers == set()``, guarding ``emitted: False`` against a silent
        wiring. The owner ruled the wiring at OWNER_BLOCKER_CLEARANCE.md:10559,
        so the set that was empty is now the two named call sites, and the
        thing worth guarding flipped with it: not "did anyone wire this" but
        "is what is wired still exactly what was ruled".

        The instrument is unchanged and that is deliberate. The same AST walk
        over the same non-test tree now asserts SET EQUALITY against the two
        ruled paths, so it still fails on a third production caller appearing
        — which is the same detection, pointed at the state the ruling
        created. Deleting it and trusting the record would have been the
        weakening; an equality against a named set is not.

        ``emitted: True`` means production DOES draw the front rule. That is
        false the moment both these modules stop passing ``hierarchy_lines=``,
        and overstated the moment a third one starts. A test file exercising
        the branch is still only what makes it measured; these two are what
        make it shipped, and they are the only two that may.

        PARSED, NOT GREPPED, and the first draft of this test is why. A
        pattern like ``hierarchy_lines\\s*=`` cannot tell a CALL from a
        SENTENCE: it missed the composer's own signature (which reads
        ``hierarchy_lines: Optional[list] = None``, with a type annotation in
        between) and it flagged ``container_line_weight.py``, whose only
        mention is the prose string "compose_container_graph(hierarchy_lines=
        ...)" explaining why the branch is unreached. A guard that reports a
        rationale as a caller would be the §Y2 failure mode running in
        reverse — noise until somebody switches it off.

        ``ast`` answers the actual question, which is whether a keyword
        argument is PASSED at a call site. ``test_wit_unit_analysis.py``
        already parses ``apps/`` this way, so this is the house instrument
        rather than a new one.
        """
        import ast

        callers = set()
        for path in sorted((REPO / "apps").rglob("*.py")):
            rel = str(path.relative_to(REPO))
            if "/tests/" in rel or path.name.startswith("test_"):
                continue
            try:
                tree = ast.parse(path.read_text())
            except SyntaxError:                     # pragma: no cover
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and any(
                        kw.arg == "hierarchy_lines" for kw in node.keywords):
                    callers.add(rel)

        assert callers == {"apps/pipeline/targets/container/__init__.py",
                           "apps/pipeline/services/native_handoff.py"}, (
            "the set of NON-TEST modules passing hierarchy_lines is no longer "
            "the two call sites §BB7(c) ruled. Fewer means the direct-print "
            "front has silently stopped being reached from some path and "
            "container_line_weight's `emitted: True` is a lie; more means a "
            "front is being emitted from a path the owner never ruled on: "
            f"{sorted(callers)}")
        assert clw.ELEMENTS["container_front_rule"]["emitted"] is True

        # and the parameter really is still declared where the record says,
        # so a rename cannot make this pass by making the search meaningless
        assert "hierarchy_lines: Optional[list] = None" in \
            (REPO / "apps/ire/compose_container.py").read_text()

        # §BB7(g)(a). The walk above finds KEYWORD arguments, so it is only
        # total over a composer whose parameter cannot be passed positionally.
        # The sibling grep's docstring says the dropper's is keyword-only and
        # that this is why the guard survives a third acceptor; an unasserted
        # sentence about a signature is how that file's own record went stale
        # twice, so the sentence is measured here instead of trusted.
        for module, fname in (("apps/ire/compose_dropper.py",
                               "compose_dropper_sheet"),
                              ("apps/ire/compose_container.py",
                               "compose_container_graph")):
            fn = next(n for n in ast.walk(
                ast.parse((REPO / module).read_text()))
                if isinstance(n, ast.FunctionDef) and n.name == fname)
            assert "hierarchy_lines" in [a.arg for a in fn.args.kwonlyargs], (
                f"{fname} takes hierarchy_lines positionally, so a production "
                "call site could feed a front without writing the keyword the "
                "assertion above searches for")
            assert fn.args.kwarg is None, (
                f"{fname} accepts **kwargs, so hierarchy_lines could arrive "
                "under a splat this assertion cannot see")


class TestEachElementNamesItsContext:
    """§W4(a) — record them as distinct elements, each naming its context."""

    def test_every_element_points_at_a_site_that_exists(self):
        for element_id, element in clw.ELEMENTS.items():
            path, symbol = element["site"].split(" ", 1)
            source = (REPO / path)
            assert source.exists(), f"{element_id} names a missing file"
            assert symbol in source.read_text(), \
                f"{element_id}'s site no longer contains {symbol}"

    def test_every_element_points_at_the_right_one(self):
        """Two of the three elements are called ``rule-front-single``, so a site
        that merely exists and merely contains that name proves nothing — the
        record could name the other composer and still look well formed. The
        map below is this file's own statement of which weight lives where; the
        emission tests above are what establish it."""
        assert {i: e["site"].split(" ", 1)[0] for i, e in clw.ELEMENTS.items()} \
            == {"gate_a_divider": "apps/pipeline/services/ai8_color.py",
                "container_front_rule": "apps/ire/compose_container.py",
                "dropper_front_rule": "apps/ire/compose_dropper.py"}

    def test_every_site_points_back_at_the_record(self):
        """A rationale a reader at the site cannot find is not a rationale."""
        for element_id, element in clw.ELEMENTS.items():
            path = element["site"].split(" ", 1)[0]
            assert "container_line_weight" in (REPO / path).read_text(), \
                f"{path} does not name the record that explains its weight"

    def test_only_the_measured_element_claims_a_measurement(self):
        for element_id, element in clw.ELEMENTS.items():
            assert element["context"].strip()
            claims_proof = element["authority"].startswith("ACCEPTED_PROOF")
            assert claims_proof is (element_id == "gate_a_divider"), \
                f"{element_id} claims authority no proof gave it"

    def test_the_reached_element_says_what_reached_it(self):
        """WAS ``test_the_unreached_element_says_why_it_is_unreached`` and read
        ``unreached_because``. §BB7(c) reached it, so the field it read no
        longer exists under that name — the record renamed it
        ``superseded_unreached_because`` and kept its text (§AZ0(u)), adding
        ``emitted_because`` for the state that replaced it. Both are required
        here: the reason it is drawn, and the retained reason it was not."""
        element = clw.ELEMENTS["container_front_rule"]
        assert element["emitted_because"]
        assert element["superseded_unreached_because"]
        assert "unreached_because" not in element, \
            "the superseded field is back under its old name, which would let " \
            "an unreached-ness claim sit beside emitted: True unchallenged"

    def test_the_record_carries_the_context_and_not_only_the_verdict(self):
        """A standing-against-the-table with the context stripped off is the
        unexplained number §W4(b) exists to remove, wearing a schema."""
        for element_id, element in clw.ELEMENTS.items():
            record = clw.weight_record(element_id)
            assert record["element_id"] == element_id
            for field, value in element.items():
                assert record[field] == value, f"{element_id}.{field}"


class TestTheStandingIsComputedNotTranscribed:
    """A comment restating the table goes stale silently; this cannot."""

    def test_a_change_to_the_table_changes_the_record(self, monkeypatch):
        monkeypatch.setattr(cpm, "_METHOD_DEFAULTS",
                            {"INVENTED_METHOD": {"min_line_mm": 9.9}})
        record = clw.weight_record("container_front_rule")
        assert record["standing_by_method"] == {
            "INVENTED_METHOD": {"floor_mm": 9.9, "standing": clw.BELOW}}
        assert record["below"] == ["INVENTED_METHOD"]
        assert record["clears"] == []

    def test_every_method_in_the_table_is_placed_exactly_once(self):
        for element_id in clw.ELEMENTS:
            record = clw.weight_record(element_id)
            placed = record["clears"] + record["below"] + record["exactly_on"]
            assert sorted(placed) == sorted(cpm._METHOD_DEFAULTS), element_id
            assert len(placed) == len(set(placed)), element_id

    def test_a_weight_that_equals_its_floor_is_on_it_not_over_it(self):
        standing = clw.position_against_table(0.25)
        assert standing["PAD_PRINT"]["standing"] == clw.EXACTLY_ON
        assert standing["CAP_PRINT"]["standing"] == clw.EXACTLY_ON
        assert standing["SCREEN_PRINT"]["standing"] == clw.CLEARS
        assert standing["EMBOSS"]["standing"] == clw.BELOW

    def test_the_live_rule_now_clears_every_floor_but_the_two_deepest(self):
        """RENAMED AND RE-MEASURED AT §BB7(e), NOT WEAKENED. This test was
        ``test_the_live_rule_sits_on_the_screen_print_floor`` and asserted
        SCREEN_PRINT EXACTLY_ON and PAD_PRINT BELOW. At 0.20 mm both held. The
        ruled 0.30 mm falsifies both AND the old name, so the name goes with
        them — a test called "sits on the screen print floor" that asserts it
        clears the floor is worse than no test.

        The number that changed is the element's; the floors are untouched.
        What C16(b) bought, measured rather than asserted: the rule production
        actually draws was BELOW six of the eleven method floors and is now
        below two."""
        standing = clw.position_against_table(
            clw.ELEMENTS["dropper_front_rule"]["width_mm"])
        assert standing["SCREEN_PRINT"]["standing"] == clw.CLEARS
        assert standing["PAD_PRINT"]["standing"] == clw.CLEARS
        below = sorted(m for m, s in standing.items()
                       if s["standing"] == clw.BELOW)
        assert below == ["DEBOSS", "EMBOSS"]
        # and it lands exactly on the two hot-stamp floors, which is a
        # different standing from clearing them
        assert standing["HOT_STAMP"]["standing"] == clw.EXACTLY_ON
        assert standing["CAP_HOT_STAMP"]["standing"] == clw.EXACTLY_ON


class TestClearingTheTableIsNotApproval:
    """The only table in the repo is labelled INFERRED_NONAUTHORITATIVE."""

    def test_the_record_carries_the_tables_own_disclaimer(self):
        record = clw.weight_record("container_front_rule")
        assert "INFERRED_NONAUTHORITATIVE" in record["table_authority"]
        assert "not thereby approved" in record["table_authority"]

    def test_source_guard_the_table_module_still_says_that_about_itself(self):
        """SOURCE-STRING GUARD (§Y2). Asserts a literal appears in a file and
        **asserts nothing about behaviour** — the word being present does not
        mean any method record carries that authority state at runtime, and
        this is not citable as coverage of the authority rule (§Y2(c)). The
        behavioural cover is ``test_container_production_method.
        test_authority_is_unverified_by_construction``.
        """
        source = (REPO / "apps/ire/container_production_method.py").read_text()
        assert "INFERRED_NONAUTHORITATIVE" in source

    def test_the_status_says_no_weight_here_has_been_measured(self):
        assert clw.STATUS == "OWNER_RULED_PENDING_MEASUREMENT"
        assert clw.weight_record("dropper_front_rule")["status"] == clw.STATUS

    def test_the_rule_that_reached_the_record_travels_with_it(self):
        record = clw.weight_record("gate_a_divider")
        assert record["rule"] == clw.RULE
        # a rationale that cites a ruling has to say where the ruling is
        assert "OWNER_BLOCKER_CLEARANCE.md §W4" in record["rule"]
        assert record["schema_version"] == clw.SCHEMA
