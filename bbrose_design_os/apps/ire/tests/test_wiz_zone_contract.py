"""WI-Z / §AC2(c) — the zone-contract guard, and the thing it caught.

§AC2(c), in full: *"A test asserts the confirmed zone set is exactly
`{z_front, z_back, z_bottom_code}` and that no module emits geometry to any
other zone name. Its negative control: a deliberately introduced emission to a
fourth name must FAIL the guard. A guard that has never fired on anything is
§AA's case."*

This module is that test. It has three subjects and each carries its own
negative control, because §AC2(c)'s last sentence is the operative one: a
guard whose failing branch has never executed is a guard nobody has evidence
about.

  1. THE SET. The confirmed zone set is read out of the contract module by
     AST — the same route WI-X used — and asserted to be exactly the named
     subjects, and to be that many. Three when this was written, four since
     §AH. Control: the extractor must find nothing when pointed at a file that
     confirms no zones, so "it returned the right set" is distinguishable from
     "it returned everything it saw".

  2. THE PATH. §AC2(b) — *"No zone name appears anywhere in the multi-layer
     path"* — is checked by reading the source of the four modules that path
     is made of and asserting zero matches. Control: the same scanner, run
     over source with a zone name spliced in, must find it. Without that, a
     regex that matches nothing and a regex that is broken read identically.

  3. THE EMISSIONS. Every archetype is composed and its emitted zone ids are
     compared against the confirmed set. Control: a fourth-name placement is
     appended to a REAL document and re-measured through the SAME function, so
     the failing branch runs on the actual instrument rather than on a
     hand-made list that proves only that `set.difference` works.

WHAT SUBJECT 3 FOUND, AND WHAT WAS DONE ABOUT IT
------------------------------------------------
The guard fired on this repository the day it was written. Measured then:

    bottle   proposed [z_front, z_back, z_cap_top]        emitted [z_front]
    tube     proposed [z_front, z_back, z_cap, z_crimp..] emitted [z_front]
    jar      proposed [z_wrap, z_cap_top]                 emitted [z_wrap]

`z_wrap` was not in the confirmed set. **The jar emitted geometry to a zone the
contract did not confirm**, and it was production code, reachable that day, not
a fixture. Under sprint 14's rules there were only three moves, and all three
were bad: confirming the zone was adding one, which §AC2 forbade outright
(*"no zone is added in sprint 14"*); narrowing the guard until the jar passed
was §AA's case arriving by the front door; landing it red moved a count the
owner was tracking for a different reason. So it was pinned as a MEASUREMENT
in `KNOWN_EMISSIONS_OUTSIDE` below and sent to `OWNER_REVIEW_QUEUE.md` to await
the ruling §AC2(d) says fixes the count.

**§AH (sprint 15, WI-3C) is that ruling, and it confirmed `z_wrap`.** The
question the ruling had to answer first was the one this docstring left open:
whether the jar's wrap is a fourth surface or the front under another name. It
is a fourth surface, and the deciding fact is a measurement rather than a
preference — at a 40 mm body, BODY_FRONT is 40.00 mm wide and BODY_WRAP is
125.66 mm, because the wrap is the developed cylinder and 40π is 125.66. A
factor of π is not a spelling difference. A wrap label is also one artwork with
one seam and no reverse, where a front/back pair is two artworks and two
keylines, so the two cannot share a zone even if the widths had agreed.

The confirmation was made EXACTLY as the jar already emitted — no coverage
re-tuned, `permitted_techniques` left at one member — so that no `zone_hash`,
`zone_set_hash` or `combined_confirmation_hash` moves. §AH4 states that as a
prediction the fix must satisfy, and it is checked below rather than asserted
in prose.

TWO FINDINGS FROM THE SAME MEASUREMENT ARE STILL OPEN. `z_bottom_code` is
CONFIRMED and proposed by no archetype, and the tube proposes `z_crimp_code`
for what looks like the same job under a different name. §AH5 explicitly
declines to rule on those: whether they are one surface under two names is a
question about a physical part nobody has measured. They stay asserted, in
`TestWhatTheProposalLayerOffers`, with a number attached.
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]

#: The contract module that CONFIRMS zones. Read, never imported: the claim is
#: about what the source says, and importing would let a monkeypatch or an
#: import-time side effect answer for it.
CONTRACT_SOURCE = ROOT / "apps/pipeline/services/selected_concept_contract.py"

#: §AC2(c)'s set, typed once, HERE. This file is allowed to name them —
#: naming them is its entire job, and §AC2(b)'s prohibition is on the
#: multi-layer path, not on the guard that pins the path to the contract. The
#: assertion below is that this typed set equals what the contract confirms,
#: so if it ever drifts the test fails rather than lying quietly.
#:
#: FOUR since §AH. `z_wrap` joined the three when the ruling confirmed the
#: jar's wrap as its own surface — see the module docstring. The name of this
#: constant still says AC2C because §AC2(c) is what commissioned the guard;
#: what it holds is the confirmed set as of today, not as of that sprint.
AC2C_SET = {"z_front", "z_back", "z_bottom_code", "z_wrap"}

#: The four modules §AC2(b) scopes: the construction axis §AB1 put in
#: question, the abstract surface plan WI-Z built, and the two back-panel
#: modules §AC2 names as the work being built *"against an ABSTRACT surface
#: list of unbound length"*.
MULTI_LAYER_PATH = (
    "apps/ire/container_label_construction.py",
    "apps/ire/surface_plan.py",
    "apps/ire/back_panel.py",
    "apps/ire/back_panel_ledger.py",
)

#: A zone name as this repository spells them. `\b` matters more than it
#: looks: without it this matches `z_zone` inside `test_wiz_zone_contract`,
#: and the guard fails on the filename of the module that mentions it. That
#: is not hypothetical — it happened while this was being written, and it is
#: the reason the scanner has a control of its own.
ZONE_NAME = re.compile(r"\bz_[a-z][a-z0-9_]*")

#: Emitted zone ids that are outside the confirmed set, per archetype,
#: measured today. An archetype that starts emitting outside the set fails; so
#: does one that stops, because a disappearing violation is as much a change as
#: an arriving one and this sprint's rule is that *"a drop is as suspicious as
#: a rise"*.
#:
#: The jar's entry read `["z_wrap"]` from WI-Z until §AH confirmed the zone.
#: It is empty now for the ONE acceptable reason — the contract grew to meet
#: the emission — and the structure is deliberately kept rather than collapsed
#: to three `[]`s, because the next violation needs somewhere to be recorded
#: and a dict of empties still fails loudly when one stops being empty.
KNOWN_EMISSIONS_OUTSIDE = {
    "bottle": [],
    "jar": [],
    "tube": [],
}

ARCHETYPES = ("bottle", "jar", "tube")


# --------------------------------------------------------------------------
# the instruments
# --------------------------------------------------------------------------

def confirmed_zone_ids(source: pathlib.Path) -> set[str]:
    """The zone ids a contract source CONFIRMS, by AST.

    A confirmation is a dict literal whose `decision` ends `_ZONE_CONFIRMED`
    and which carries a `subject`. Same extraction as WI-X's pin, lifted here
    so both tests read the contract the same way; if the contract ever states
    confirmations differently, both go red together rather than one of them
    silently reading an empty set as agreement.
    """
    tree = ast.parse(source.read_text())
    subjects = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        pairs = {k.value: v.value for k, v in zip(node.keys, node.values)
                 if isinstance(k, ast.Constant) and isinstance(v, ast.Constant)}
        if str(pairs.get("decision", "")).endswith("_ZONE_CONFIRMED") \
                and "subject" in pairs:
            subjects.add(str(pairs["subject"]))
    return subjects


def zone_names_in(text: str) -> set[str]:
    """Every zone name appearing in a blob of source, comments included.

    Comments and docstrings are deliberately IN SCOPE. §AC2(b) gives the
    mechanism as *"an invented name in a comment becomes an invented name in a
    variable becomes an invented name in an emitter"*, so a scanner that
    parsed the code and skipped the prose would be blind to step one of the
    exact sequence it exists to stop.
    """
    return set(ZONE_NAME.findall(text))


def emissions_outside_contract(emitted, confirmed) -> list[str]:
    """THE GUARD. Emitted zone ids that the contract does not confirm.

    Sorted so a failure message is stable and two runs are diffable. Takes the
    confirmed set as an ARGUMENT rather than reading `AC2C_SET`: a guard that
    closes over its own expectation cannot be pointed at a different contract,
    and the negative controls below need to point it at one.
    """
    return sorted({str(z) for z in emitted} - {str(z) for z in confirmed})


def _emitted_zone_ids(archetype: str) -> list[str]:
    """Compose one archetype and read the zone ids it actually places.

    Imports are deferred into the function on purpose: this module's other two
    subjects are pure source reads and must stay runnable without touching the
    composer, so an import error in the pipeline cannot take the §AC2(b)
    scanner down with it.
    """
    from apps.pipeline.services import container_contract as cc
    from apps.ire.compose_container import compose_container_graph
    from apps.pipeline.targets.container.silhouettes import (
        ContainerProfile, build_backbone)

    profile = cc.build_inferred_profile(archetype, estimates={
        "body_width_mm": 40.0, "body_height_mm": 110.0,
        "cap_width_mm": 20.0, "cap_height_mm": 13.0})
    zones = cc.propose_zones(profile)
    backbone = build_backbone(ContainerProfile(
        archetype=archetype, width_mm=40, height_mm=110))
    doc = compose_container_graph(
        backbone, product_name="Rose Nectar", name_lines=["Rose Nectar"],
        zones=zones, native=True)
    return _ids_of(doc)


def _ids_of(doc) -> list[str]:
    placements = (doc.metadata or {}).get("placements") or []
    return sorted({p.get("zone_id") for p in placements if p.get("zone_id")})


# --------------------------------------------------------------------------
# 1. the set
# --------------------------------------------------------------------------

class TestTheConfirmedSetIsExactlyFour:
    """§AC2(c), first clause.

    RENAMED by §AH from `TestTheConfirmedSetIsExactlyThree`, and the old name
    is written here on purpose. WI-3B spent its only UNCLASSIFIED row on a
    class rename: a node id in a stored run record stopped resolving, and
    nothing in the tree said what it had become, so the id had to be chased
    through two commits to prove it had not been deleted. A rename costs
    nothing if the old name stays greppable, so it stays.
    """

    def test_the_contract_confirms_exactly_the_four(self):
        assert confirmed_zone_ids(CONTRACT_SOURCE) == AC2C_SET

    def test_it_is_four_and_the_count_is_stated_as_a_measurement(self):
        """The count, separately, because §AC2(a) is about the count and not
        about the spelling. If a fifth is ever confirmed this fails on the
        number even if somebody also updated `AC2C_SET` above — the two
        assertions have to be edited independently, which is a small amount of
        friction placed exactly where §AC2(d) says a contract change goes.

        That friction worked. Both assertions went red on §AH's contract edit
        and both had to be changed by hand, which is the behaviour the docstring
        claimed and had never demonstrated until now.
        """
        assert len(confirmed_zone_ids(CONTRACT_SOURCE)) == 4

    def test_the_extractor_finds_nothing_where_nothing_is_confirmed(self, tmp_path):
        """NEGATIVE CONTROL for the extractor.

        A file with a dict that looks structurally identical but whose
        `decision` is not a zone confirmation must yield the empty set. This
        separates "the extractor selected the three" from "the extractor
        returned every subject it walked past", which are indistinguishable
        from the passing assertion above alone.
        """
        decoy = tmp_path / "decoy.py"
        decoy.write_text(
            'DECISIONS = [\n'
            '    {"decision": "PALETTE_CONFIRMED", "subject": "z_front"},\n'
            '    {"decision": "SOMETHING_ELSE", "subject": "z_back"},\n'
            ']\n')
        assert confirmed_zone_ids(decoy) == set()

    def test_the_extractor_does_find_one_more_when_one_more_is_confirmed(self, tmp_path):
        """And the complement of the complement: pointed at a source that
        confirms one beyond the set, it returns the set plus one. An extractor
        hard-wired to the confirmed count would pass every other test in this
        class.

        Written against `AC2C_SET` rather than a typed number, which is why it
        survived §AH unedited while the two assertions above went red. That is
        the difference between a control and a second copy of the claim.
        """
        four = tmp_path / "four.py"
        four.write_text(
            'DECISIONS = [\n'
            + "".join(f'    {{"decision": "X_ZONE_CONFIRMED", '
                      f'"subject": "{z}"}},\n'
                      for z in sorted(AC2C_SET))
            + '    {"decision": "X_ZONE_CONFIRMED", "subject": "z_peel_back"},\n'
              ']\n')
        assert confirmed_zone_ids(four) == AC2C_SET | {"z_peel_back"}


# --------------------------------------------------------------------------
# 2. the path
# --------------------------------------------------------------------------

class TestNoZoneNameInTheMultiLayerPath:
    """§AC2(b) — *"No zone name appears anywhere in the multi-layer path."*"""

    @pytest.mark.parametrize("relative", MULTI_LAYER_PATH)
    def test_the_module_names_no_zone(self, relative):
        path = ROOT / relative
        assert path.exists(), relative
        found = zone_names_in(path.read_text())
        assert found == set(), (
            f"{relative} names {sorted(found)}. §AC2(b): an invented name in "
            f"a comment becomes an invented name in a variable becomes an "
            f"invented name in an emitter. The names belong in the contract "
            f"and in this guard, not here.")

    def test_the_scanner_finds_a_name_when_there_is_one(self):
        """NEGATIVE CONTROL for the scanner, and the reason it exists.

        Four files scored zero above. Four zeroes from a scanner nobody has
        seen succeed is §AA's case exactly — the guard and a broken regex
        produce the same report. So: real source, one name spliced in, and the
        scanner must find it and only it.
        """
        real = (ROOT / MULTI_LAYER_PATH[0]).read_text()
        assert zone_names_in(real) == set()
        assert zone_names_in(real + '\nSURFACE = "z_peel_back"\n') == \
            {"z_peel_back"}

    def test_it_catches_a_name_in_a_comment_and_not_only_in_code(self):
        """The step-one case §AC2(b) names, exercised on its own. A scanner
        that only read code would pass the assertion above (the splice was a
        string literal) and still be blind to the mechanism in the ruling.
        """
        assert zone_names_in("# the four surfaces, one of them z_peel_back\n") \
            == {"z_peel_back"}
        assert zone_names_in('"""...on z_peel_back, later."""\n') == \
            {"z_peel_back"}

    def test_it_does_not_fire_on_a_word_that_merely_contains_the_prefix(self):
        """The false positive that actually occurred while writing this.

        `test_wiz_zone_contract` contains the characters `z_zone`. Without the
        word boundary the scanner reports a zone name in every module that
        mentions this file — including two of the four above, which reference
        it by name. A guard that fires on its own filename is noise, and noise
        is how a real hit gets waved through.
        """
        assert zone_names_in("see test_wiz_zone_contract.py") == set()
        assert zone_names_in("horiz_offset, sz_index, buzz_zone") == set()
        assert zone_names_in("z_front") == {"z_front"}


# --------------------------------------------------------------------------
# 3. the emissions
# --------------------------------------------------------------------------

class TestNoModuleEmitsOutsideTheContract:
    """§AC2(c), second clause — and the clause that found something."""

    @pytest.mark.parametrize("archetype", ARCHETYPES)
    def test_emissions_match_what_was_measured(self, archetype):
        """Each archetype's out-of-contract emissions equal the RECORDED set.

        Not written as `== []` even now that all three are empty. The jar's was
        `["z_wrap"]` for the whole of sprint 14, and the shape is what let the
        violation be carried as a reading instead of as a comment. Equality in
        BOTH directions: a new name fails, and so does a violation that quietly
        disappears — which is the check that matters here, because §AH is
        supposed to have closed the jar by moving the CONTRACT, and a jar that
        simply stopped emitting would produce the same empty list.
        `test_the_wrap_finding_closed_by_confirmation_and_not_by_silence`
        below is the one that tells those two apart.
        """
        outside = emissions_outside_contract(
            _emitted_zone_ids(archetype), AC2C_SET)
        assert outside == KNOWN_EMISSIONS_OUTSIDE[archetype], (
            f"{archetype} emits {outside} outside the confirmed set; the "
            f"recorded reading is {KNOWN_EMISSIONS_OUTSIDE[archetype]}. If "
            f"this is a deliberate contract change it needs §AD, not an edit "
            f"to this literal.")

    def test_the_wrap_finding_closed_by_confirmation_and_not_by_silence(self):
        """The jar's violation, closed — and closed the RIGHT way, asserted.

        This method replaces `test_the_finding_is_asserted_as_a_finding_and
        _not_left_in_prose`, which asserted the violation was present and whose
        own docstring said it *"goes red the day somebody confirms the wrap
        zone, which is the day the queue entry should be closed"*. §AH was that
        day and it did go red. The old name is written out here so a stored run
        record naming it can be resolved to its successor.

        What replaces it is not nothing, because "the jar has no out-of-contract
        emission" is true in two very different worlds: the contract grew to
        meet the emission (what §AH did), or the jar stopped emitting (a
        regression that would read as a clean guard). Three assertions, in the
        order that distinguishes them:
        """
        emitted = _emitted_zone_ids("jar")

        # 1. the emission is still there. This is the one that would catch a
        #    jar that went quiet, and it is deliberately first.
        assert "z_wrap" in emitted, (
            "the jar no longer emits z_wrap. §AH confirmed that zone on the "
            "strength of the jar emitting it; if the emission is gone the "
            "confirmation is now describing a surface nothing draws on.")

        # 2. the contract confirms it, read from source rather than from the
        #    literal above, so this fails if the contract is reverted and only
        #    `AC2C_SET` was edited.
        assert "z_wrap" in confirmed_zone_ids(CONTRACT_SOURCE)

        # 3. and therefore nothing is outside.
        assert emissions_outside_contract(emitted, AC2C_SET) == []

    def test_a_fourth_name_emitted_into_a_real_document_fails_the_guard(self):
        """**§AC2(c)'s NEGATIVE CONTROL**, run through the real instrument.

        *"a deliberately introduced emission to a fourth name must FAIL the
        guard."* The bottle is composed for real, measured clean, then a
        placement carrying a fourth name is appended to the document it
        actually produced and the SAME reader is run again. Building the list
        by hand would test `set.difference`; this tests the path from a
        document to a verdict, which is the path that would carry a real
        regression.
        """
        from apps.pipeline.services import container_contract as cc
        from apps.ire.compose_container import compose_container_graph
        from apps.pipeline.targets.container.silhouettes import (
            ContainerProfile, build_backbone)

        profile = cc.build_inferred_profile("bottle", estimates={
            "body_width_mm": 40.0, "body_height_mm": 110.0,
            "cap_width_mm": 20.0, "cap_height_mm": 13.0})
        zones = cc.propose_zones(profile)
        backbone = build_backbone(ContainerProfile(
            archetype="bottle", width_mm=40, height_mm=110))
        doc = compose_container_graph(
            backbone, product_name="Rose Nectar", name_lines=["Rose Nectar"],
            zones=zones, native=True)

        assert emissions_outside_contract(_ids_of(doc), AC2C_SET) == []

        doc.metadata["placements"].append({"zone_id": "z_peel_back"})
        assert emissions_outside_contract(_ids_of(doc), AC2C_SET) == \
            ["z_peel_back"]

    def test_the_guard_is_not_vacuous_on_an_empty_emission(self):
        """A container that emits nothing has no violation, and that must read
        as a PASS rather than as a guard that cannot see. Stated because the
        assertion above is `== []` for two of three archetypes, and `[]` is
        also what a guard returns when it has been handed nothing at all.
        """
        assert emissions_outside_contract([], AC2C_SET) == []
        assert emissions_outside_contract(["z_front"], AC2C_SET) == []
        assert emissions_outside_contract(["z_front", "z_x"], AC2C_SET) == \
            ["z_x"]


class TestWhatTheProposalLayerOffers:
    """Proposals are not emissions, and the difference is where the finding
    is. §12 PROPOSES zones per archetype; the contract CONFIRMS three; the
    composer EMITS some subset. All three counts differ and the module
    docstring reports them, so they are asserted here rather than described.
    """

    def test_three_proposed_names_are_outside_the_confirmed_set(self):
        """Four until §AH, three after it, and the one that left was `z_wrap`.

        Renamed from `test_four_proposed_names_are_outside_the_confirmed_set`;
        the old name is here to be found. The number in a test name is a claim
        with a shelf life, which is an argument for not putting numbers in test
        names — but the alternative on offer was a name that no longer matched
        its assertion, and a stale name is worse than a renamed one.
        """
        from apps.pipeline.services import container_contract as cc

        proposed = set()
        for archetype in ARCHETYPES:
            profile = cc.build_inferred_profile(archetype, estimates={
                "body_width_mm": 40.0, "body_height_mm": 110.0,
                "cap_width_mm": 20.0, "cap_height_mm": 13.0})
            proposed |= {z["zone_id"] for z in cc.propose_zones(profile)}
        assert proposed - AC2C_SET == {"z_cap_top", "z_cap", "z_crimp_code"}

    def test_a_confirmed_zone_is_proposed_by_no_archetype(self):
        """The finding in the other direction, and the one a guard looking
        only for excess would never see: `z_bottom_code` is CONFIRMED and
        nothing proposes it. The tube proposes `z_crimp_code` for what reads
        like the same surface. Whether they are one zone under two names is a
        contract question — §AC2(d) said the contract opens once, later, and
        this test existed so the question would be on the record with a number
        attached rather than noticed again in six sprints.

        THE CONTRACT HAS SINCE OPENED, AND THIS IS STILL OPEN. §AH went in and
        confirmed `z_wrap`; it did NOT touch this, and §AH5 says why in one
        line — deciding whether `z_bottom_code` and `z_crimp_code` are one
        surface means knowing where the code is stamped on a physical part, and
        nobody has measured one. §AE2(a): there is no such thing as a derived
        measurement. So the assertion is unchanged, which is itself the
        finding: an open question survived the sprint that was supposed to be
        its chance, for a stated reason, rather than being closed by whoever
        was holding the file open.
        """
        from apps.pipeline.services import container_contract as cc

        proposed = set()
        for archetype in ARCHETYPES:
            profile = cc.build_inferred_profile(archetype, estimates={
                "body_width_mm": 40.0, "body_height_mm": 110.0,
                "cap_width_mm": 20.0, "cap_height_mm": 13.0})
            proposed |= {z["zone_id"] for z in cc.propose_zones(profile)}
        assert AC2C_SET - proposed == {"z_bottom_code"}


#: §AH4's prediction, transcribed from the ruling BEFORE the fix was written.
#: A jar at 40 × 110 with a 20 × 13 cap. The ruling's own words: *"If any of
#: those five values moves, the fix did more than this ruling authorises and
#: must be reverted rather than re-baselined."*
AH4_PREDICTED = {
    "profile_hash": "97efcd7cc3f79e0a3ec16fb84080283d",
    "zone_set_hash": "6856950c90d624a3becdb8a16529f05a",
    "combined_confirmation_hash": "fb312550042ccfa5b867a1af86f59ab8",
    "z_wrap": "c91feaa1d2d767c2cb24fb58ac7f4c0f",
    "z_cap_top": "2903e4539d3a2b1c5beee285b91779fb",
}

AH4_JAR = {"body_width_mm": 40.0, "body_height_mm": 110.0,
           "cap_width_mm": 20.0, "cap_height_mm": 13.0}


class TestAH4sPredictionHeld:
    """§AH confirmed a zone WITHOUT moving a hash, and this is the check.

    The claim in §AH2 is that `z_wrap` was confirmed *exactly as the jar
    already emitted it* — no coverage re-tuned, `permitted_techniques` left at
    one member — so that no stored confirmation is invalidated and no persisted
    `spec_sheet` needs re-deriving. That claim is worth nothing as prose,
    because "I didn't change the geometry" is exactly what someone says after
    changing the geometry by one decimal place.

    The five values below were written into `OWNER_BLOCKER_CLEARANCE.md` at
    commit `f49934a`, before a line of the fix existed. That ordering is the
    only thing that makes this a prediction rather than a transcription of
    whatever the code happened to produce afterwards.
    """

    def _measured(self):
        from apps.pipeline.services import container_contract as cc

        profile = cc.build_inferred_profile("jar", estimates=AH4_JAR)
        zones = cc.propose_zones(profile)
        by_id = {z["zone_id"]: z for z in zones}
        return {
            "profile_hash": cc.profile_hash(profile),
            "zone_set_hash": cc.zone_set_hash(zones),
            "combined_confirmation_hash":
                cc.combined_confirmation_hash(profile, zones),
            "z_wrap": cc.zone_hash(by_id["z_wrap"]),
            "z_cap_top": cc.zone_hash(by_id["z_cap_top"]),
        }

    def test_all_five_are_byte_identical_to_what_the_ruling_predicted(self):
        assert self._measured() == AH4_PREDICTED, (
            "a hash moved across the z_wrap confirmation. §AH4 says this is "
            "reverted, not re-baselined: editing the literals above to match "
            "the new output is the one response the ruling forbids by name.")

    def test_the_confirmation_is_a_decision_record_and_not_a_geometry_edit(self):
        """WHY the hashes could not move, asserted rather than trusted.

        `zone_set_hash` hashes the zone dicts — id, type, surface, geometry,
        curvature, margins, coverage, techniques, source, verification. It does
        not hash confirmed-set membership, and `propose_zones` is not where a
        confirmation lives. So the two facts that make the prediction true are:
        the confirmed set grew, and the proposal layer did not move. Both, in
        one place, so a future edit that quietly moves the geometry cannot
        satisfy this class by also updating the literals.
        """
        from apps.pipeline.services import container_contract as cc

        assert "z_wrap" in confirmed_zone_ids(CONTRACT_SOURCE)

        profile = cc.build_inferred_profile("jar", estimates=AH4_JAR)
        wrap = {z["zone_id"]: z for z in cc.propose_zones(profile)}["z_wrap"]
        assert tuple(wrap["permitted_techniques"]) == ("wrap_label",), (
            "§AH3 left this tuple at one member on purpose — a wrap label is "
            "one artwork with one seam, and widening the tuple is a taste "
            "decision reserved to the owner under §AE2(c)")

    def test_the_wrap_is_the_developed_cylinder_and_the_front_is_not(self):
        """§AH1's deciding measurement, re-measured here.

        The ruling turned on ONE number: at a 40 mm body, BODY_FRONT is
        40.00 mm and BODY_WRAP is 125.66 mm, because the wrap is the cylinder
        unrolled and 40π is 125.66. That is what settled "fourth surface"
        against "the front under another name", and it is a fact about the
        contract rather than an opinion about labels — so it is asserted, and
        if it ever stops being true the ruling that rests on it is void.

        THE QUANTITY IS THE SURFACE, NOT THE ZONE, AND THE FIRST DRAFT OF THIS
        TEST REACHED FOR THE WRONG ONE. It asked the zone dict for `width_mm`
        and got a `KeyError`, which is the only reason the mistake was caught:
        the zone dict spells it `width`, and had the key existed the assertion
        would have compared 40π against **106.8** — the zone width, which is
        0.85 × 125.66 because `propose_zones` centres the wrap at 85 % coverage
        — and failed by 19 mm. The obvious repair at that point is to widen the
        tolerance until it passes, and the tolerance was already there in the
        draft, waiting. §AD2(d) is why it did not happen: the fix was to dump
        the whole zone dict and read it, rather than to adjust the number that
        was in front of me.

        The two quantities differ by the coverage factor and BOTH sustain the
        ruling — 125.66 vs 40.00 at the surface, 106.8 vs 28.0 at the zone —
        so this records a near-miss rather than a correction. It would have
        been a correction if the coverage factors had happened to agree.
        """
        import math

        from apps.pipeline.services import container_contract as cc

        jar = cc.build_inferred_profile("jar", estimates=AH4_JAR)
        geom = cc.surface_geometry(jar)

        # THE RULING'S NUMBER. Both surfaces on ONE profile — which is the
        # sharper form of the argument, because it means the contract's own
        # surface model already distinguishes them and no cross-archetype
        # comparison is needed to make the point.
        assert geom["BODY_FRONT"]["w"] == 40.0
        assert geom["BODY_WRAP"]["w"] == pytest.approx(40.0 * math.pi, abs=0.01)
        assert geom["BODY_WRAP"]["w"] > geom["BODY_FRONT"]["w"] * 3

        # AND THE ZONE, stated separately with its own number, so the two are
        # never again confused for each other in this file.
        wrap = {z["zone_id"]: z for z in cc.propose_zones(jar)}["z_wrap"]
        assert wrap["parent_surface"] == "BODY_WRAP"
        assert wrap["width"] == 106.8
        assert wrap["units"] == "mm"
