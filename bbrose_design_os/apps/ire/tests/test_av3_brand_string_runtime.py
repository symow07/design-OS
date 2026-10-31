"""§AV3 — the RUNTIME half of the §AE2(c) guard, watched refusing.

WHAT THIS FILE HAS TO PROVE THAT §AV2's DOES NOT. ``tools/brand_strings.py``
reads source. §AU8(e) is a claim about EMISSIONS: "no emission carrying a
⟪PROVISIONAL⟫ descriptor reaches print, a proof, or any owner-facing artefact."
A descriptor arriving from a database row, a fixture, or the owner-supplied C9
string that does not exist yet is in no ``.py`` file at all, and §AV2's own
docstring says so in as many words. So the case that matters most here is the
one the static half is structurally blind to: a marked string that exists
NOWHERE IN SOURCE, injected into a composed document, and refused anyway.
``test_a_descriptor_that_exists_in_no_source_file_is_still_refused`` is that
case, and it is the reason this file exists rather than three more assertions
appended to §AV2's.

§AA, counted rather than characterised: of 23 tests, TEN watch the guard
refuse, SEVEN are controls that would catch it refusing unconditionally or
counting nothing, TWO pin the §AD0(b) discipline that a node name may label a
finding but never decide one, and FOUR assert the wiring — including the one
that measures what the pre-§AV1 reader would have done with the same code,
which is the evidence for why AV1 came first.

One of those controls is here in a shape I did not choose. It was written as
``gate2_refusal(clean) is None``, it failed, and the failure turned out to be a
fact about the repository rather than about §AV3 — see
``test_the_gate_cannot_currently_pass_at_all_and_that_is_recorded``.
"""
import pytest

from apps.ire import brand_string_runtime as bsr
from apps.ire import container_production_readiness as cpr
from apps.ire.graph import Color, Document, Group, TextRun

MARKER = bsr.MARKER


def _text(name, text, size_pt=8.0):
    return TextRun(name=name, text=text, x=0.0, y=0.0, size_pt=size_pt,
                   color=Color.from_hex("#000000"))


def _doc(*runs, title="probe"):
    return Document(page_w=40.0, page_h=110.0, title=title,
                    root=Group(name="root", children=list(runs)))


#: THE PROBE STRING, AND WHY IT IS DELIBERATELY NOT BRAND-SHAPED.
#:
#: The first draft of this file used the fabricated descriptor §AV2 found —
#: five times — and §AV2's own drift census went RED on it: a new file naming
#: the string that no owner has ever ratified. That census was written one
#: commit ago with the sentence "a fabricated descriptor spreading is exactly
#: how a placeholder becomes established by attrition", and then the very next
#: file I wrote spread it. Widening the census to admit this file would have
#: been the §AL4 move, so the STRING changed instead, and the census still
#: names exactly two files.
#:
#: What a guard for provisional strings needs from its fixture is a string
#: carrying the marker. It does not need — and must not have — a plausible
#: descriptor, because a plausible descriptor in a test file is a candidate
#: somebody eventually promotes. This one cannot be mistaken for copy.
PROBE = "Probe Descriptor"


class TestItRefuses:
    """§AA — the guard is watched failing, not merely watched passing."""

    def test_a_marked_descriptor_in_an_emission_is_refused(self):
        codes = bsr.readiness_codes(
            _doc(_text("front-descriptor", f"{MARKER} {PROBE}")))
        assert codes == [f"{bsr.BRAND_STRING_PROVISIONAL}: descriptor"]

    def test_an_unmarked_emission_passes(self):
        """THE NEGATIVE CONTROL. Without it every assertion here would hold
        just as well on a guard that refused unconditionally."""
        assert bsr.readiness_codes(
            _doc(_text("front-descriptor", PROBE),
                 _text("product-name-hero", "ROSE NECTAR"))) == []

    def test_an_empty_document_passes(self):
        assert bsr.readiness_codes(_doc()) == []

    def test_a_descriptor_that_exists_in_no_source_file_is_still_refused(self):
        """THE WHOLE REASON THERE ARE TWO HALVES.

        This string is assembled at runtime from fragments, so the literal
        never appears in any ``.py`` file and ``tools/brand_strings.py`` cannot
        see it by construction — which is not a criticism of it, it is what a
        static scan IS. §AU8(e) is about emissions, and here the emission is
        refused regardless of where the text came from.

        The companion assertion is the one that makes this a measurement
        rather than a story: the same value is fed to the STATIC half, which
        reports nothing, because there is nothing in source to report.

        DEFECT, CAUGHT IN THIS FILE AND FIXED HERE: the first draft spelled the
        needle out in full on the ``assert not any(...)`` line, which put the
        very literal this test claims is absent from source INTO source. The
        assertion would still have passed, so nothing would have caught it —
        the needle is now derived from ``secret`` itself, and the test's own
        premise is the thing being asserted rather than a sentence beside it.
        """
        from tools import brand_strings as bs

        secret = MARKER + " " + "".join(["Bot", "anical ", "Radiance"])
        codes = bsr.readiness_codes(_doc(_text("front-descriptor", secret)))
        assert codes == [f"{bsr.BRAND_STRING_PROVISIONAL}: descriptor"]

        needle = secret.split(" ", 1)[1]
        assert needle not in open(__file__, encoding="utf-8").read(), \
            "the needle leaked into source; this test no longer measures what " \
            "it claims to"

        # the static half, on the same repository, has nothing to say about it
        problems, _ = bs.check()
        assert not any(needle in p for p in problems)

    def test_the_marker_is_found_anywhere_in_the_run_not_only_at_the_front(self):
        assert bsr.readiness_codes(
            _doc(_text("front-descriptor", f"{PROBE} {MARKER}"))) == \
            [f"{bsr.BRAND_STRING_PROVISIONAL}: descriptor"]

    def test_a_marked_product_name_is_refused_under_its_own_tier(self):
        assert bsr.readiness_codes(
            _doc(_text("product-name-hero", f"{MARKER} ROSE NECTAR"))) == \
            [f"{bsr.BRAND_STRING_PROVISIONAL}: product_name"]

    def test_a_marked_run_under_an_unrecognised_node_name_still_blocks(self):
        """The halting discipline, same as ``BRAND_KINDS`` and
        ``UNDECLARED_READINESS_SECTION``. A node name this module does not
        know is NOT a reason to let a provisional string through — the finding
        is reported under the node's own name so it can be diagnosed."""
        codes = bsr.readiness_codes(
            _doc(_text("some-future-node", f"{MARKER} Limited Edition")))
        assert codes == [f"{bsr.BRAND_STRING_PROVISIONAL}: "
                         f"{bsr.UNDECLARED_TIER_PREFIX}:some-future-node"]

    def test_a_marked_run_nested_deep_in_groups_is_still_found(self):
        deep = Group(name="a", children=[Group(name="b", children=[
            Group(name="c", children=[
                _text("front-descriptor", f"{MARKER} Buried")])])])
        doc = Document(page_w=40.0, page_h=110.0,
                       root=Group(name="root", children=[deep]))
        assert bsr.readiness_codes(doc) == \
            [f"{bsr.BRAND_STRING_PROVISIONAL}: descriptor"]

    def test_two_marked_tiers_produce_two_codes_deduplicated_and_sorted(self):
        """THE COUNTING CONTROL. An assertion that a clean document yields []
        is worth nothing until something has been shown to yield more than one
        — and the dedupe is asserted in the same breath so that "sorted set"
        is a measured property rather than a docstring claim."""
        codes = bsr.readiness_codes(_doc(
            _text("front-descriptor", f"{MARKER} One"),
            _text("front-descriptor", f"{MARKER} Two"),
            _text("product-name-hero", f"{MARKER} Three")))
        assert codes == [f"{bsr.BRAND_STRING_PROVISIONAL}: descriptor",
                         f"{bsr.BRAND_STRING_PROVISIONAL}: product_name"]

    def test_the_report_keeps_the_runs_that_produced_the_codes(self):
        report = bsr.brand_string_report(_doc(
            _text("front-descriptor", f"{MARKER} {PROBE}")))
        assert report["clean"] is False
        assert report["schema_version"] == bsr.SCHEMA
        assert report["provisional_runs"] == [
            {"node": "front-descriptor", "tier": "descriptor",
             "text": f"{MARKER} {PROBE}"}]

    def test_a_clean_report_says_so_rather_than_saying_nothing(self):
        report = bsr.brand_string_report(_doc(_text("front-descriptor", "Oil")))
        assert report["clean"] is True and report["codes"] == []


class TestTheTierLabelNeverDecidesTheVerdict:
    """§AD0(b) — an instrument recognising a thing by the shape of its
    implementation reports on style. The verdict must key on CONTENT."""

    def test_the_hero_name_is_matched_by_equality_not_by_prefix(self):
        """``container_motif_fidelity.py:255`` records this repository already
        paying for a ``startswith("product-name")`` test that saw
        ``product-name-hero-1`` and missed ``flat-product-name-hero-1``. So
        the prefix behaviour is pinned: a name that merely STARTS WITH the
        hero name is not silently treated as the hero — it is reported as
        undeclared, which blocks either way."""
        assert bsr._tier_of("product-name-hero") == "product_name"
        assert bsr._tier_of("product-name-hero-1").startswith(
            bsr.UNDECLARED_TIER_PREFIX)
        assert bsr._tier_of("flat-product-name-hero-1").startswith(
            bsr.UNDECLARED_TIER_PREFIX)

    def test_every_name_gets_a_label_including_the_empty_one(self):
        """``_tier_of`` is total on purpose: a finding it cannot classify must
        still be a finding, so there is no input for which it returns None and
        lets a caller skip."""
        for name in ("", "front-", "x", "front-descriptor", None):
            assert isinstance(bsr._tier_of(name), str)
            assert bsr._tier_of(name)

    def test_a_node_that_is_not_text_is_not_inspected(self):
        """The scan reads printed text. A Group named like a tier carries no
        text and must not be reported — otherwise the guard would be keying on
        names, which is the defect this class exists to prevent."""
        doc = Document(page_w=40.0, page_h=110.0, root=Group(
            name="root", children=[Group(name=f"front-descriptor", children=[])]))
        assert bsr.readiness_codes(doc) == []


class TestItReachesTheVerdictThroughTheAV1RepairedPath:
    """§AV3's ruling: the runtime half is a readiness code carried by exactly
    the aggregation path §AV1 repaired. These are what make that a wire and
    not a claim."""

    _AMBIENT = ("CONTAINER_PRINT_DATA_INCOMPLETE",
                "CONTAINER_RECONSTRUCTION_ABSENT",
                cpr.MISSING_OUTPUT_INTENT,
                cpr.HUMAN_VISUAL_ACCEPTANCE_REQUIRED)

    def _signal(self, report):
        return [c for c in report["blocking_codes"]
                if not c.startswith(self._AMBIENT)]

    def _spec(self, **sections):
        clean = {name: [] for name in cpr._SECTIONS}
        return {"container_production_readiness_codes": dict(clean, **sections)}

    def test_the_section_is_declared(self):
        assert "brand_strings" in cpr._SECTIONS

    def test_a_provisional_code_blocks_production_readiness(self):
        code = f"{bsr.BRAND_STRING_PROVISIONAL}: descriptor"
        report = cpr.build_readiness(self._spec(brand_strings=[code]))
        assert code in report["blocking_codes"]
        assert report["ready"] is False

    def test_a_clean_brand_string_section_contributes_nothing(self):
        """THE CONTROL for the test above — the declared section must be
        capable of being silent, or 'it blocks' means only 'it always
        blocks'."""
        report = cpr.build_readiness(self._spec())
        assert self._signal(report) == []

    def test_gate2_refuses_on_a_provisional_brand_string(self):
        """§AU5(4)/§AU8(e) at the gate: the closure is watched FIRING, not
        assumed. A provisional descriptor must be able to refuse Gate-2
        approval on its own, so the spec here is otherwise as clean as this
        repository can make one — a human acceptance on record and every other
        section empty."""
        code = f"{bsr.BRAND_STRING_PROVISIONAL}: descriptor"
        spec = self._spec(brand_strings=[code])
        spec[cpr.ACCEPTANCE_KEY] = {"state": cpr.HDA_ACCEPTED,
                                    "decided_by": "owner"}
        refusal = cpr.gate2_refusal(spec)
        assert refusal is not None
        assert refusal["error"] == "PRODUCTION_NOT_READY"
        assert code in refusal["failures"]

    def test_the_same_spec_without_the_marker_differs_by_exactly_one_code(self):
        """THE CONTROL that makes the refusal above mean something.

        WRITTEN FIRST AS ``gate2_refusal(clean) is None``, AND IT FAILED. The
        measurement (below) is why, and the failure is the more useful half of
        this test: Gate-2 cannot return None in this repository AT ALL, for
        reasons that have nothing to do with §AV3. Raising the assertion to
        match — or configuring an ICC profile in a fixture to buy the None —
        would have been §AL4, so the control was re-cut as a DIFFERENCE
        instead, which is strictly the stronger claim anyway: the two specs
        differ by exactly one input, and the refusal differs by exactly one
        code. That is what "§AV3 blocks" has to mean.
        """
        code = f"{bsr.BRAND_STRING_PROVISIONAL}: descriptor"
        accepted = {"state": cpr.HDA_ACCEPTED, "decided_by": "owner"}

        marked = self._spec(brand_strings=[code])
        marked[cpr.ACCEPTANCE_KEY] = accepted
        clean = self._spec()
        clean[cpr.ACCEPTANCE_KEY] = accepted

        with_code = cpr.gate2_refusal(marked)["failures"]
        without = cpr.gate2_refusal(clean)["failures"]
        assert set(with_code) - set(without) == {code}
        assert set(without) - set(with_code) == set()

    def test_the_gate_cannot_currently_pass_at_all_and_that_is_recorded(self):
        """§Y2(c) — THE LIMIT, STATED HERE RATHER THAN DISCOVERED LATER.

        Measured, an otherwise-spotless spec with a human acceptance on record
        still carries four blocking codes, and every one of them is a §AE2
        input this executor may not supply: three container print-data facts
        (the live product name, the SKU, the bottom coding zone) and the print
        shop's CMYK profile, whose own detail string says it "is a business
        decision and is never guessed".

        So §AV3's blocking code is, TODAY, not the thing standing between this
        repository and production authority — and saying so is the point. When
        the owner supplies those four, the brand-string code is what remains,
        which is exactly the state §AU8(e) is written for. A guard whose value
        depends on being the last one standing would be worth less, not more.
        """
        spec = self._spec()
        spec[cpr.ACCEPTANCE_KEY] = {"state": cpr.HDA_ACCEPTED,
                                    "decided_by": "owner"}
        report = cpr.build_readiness(spec)
        assert report["ready"] is False
        # [the owner's answer of 2026-09-27: the print shop's CMYK profile is the maker's printing specification —
        # a production note, never a blocker; the three print-data facts are what remain of the four]
        # [§BH71 (0b), the owner's goal of 2026-09-28: the code place is a production note since, so two print-data
        # facts remain of the three]
        # [His answers after 122 was redrawn, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 0b0c7e7), (1): "a design started from a brief may be approved without an SKU. 'SKU missing' shows as a production note, never a block."] the SKU a note since, so one print-data fact remains of the two
        assert sorted(report["blocking_codes"]) == sorted([
            f"{cpr.CONTAINER_PRINT_DATA_INCOMPLETE}: product_name_present",
        ])
        assert any(n.startswith(cpr.SKU_NOT_GIVEN) for n in report["production_notes"])
        assert report["production_notes"][-1] == f"{cpr.MISSING_OUTPUT_INTENT}: NOT_CONFIGURED"
        assert [n for n in report["production_notes"] if n.startswith(cpr.BATCH_CODE_PLACE_NOT_CONFIRMED)]
        # and none of them is §AV3's — the difference test above stays honest
        assert not any(c.startswith(bsr.BRAND_STRING_PROVISIONAL)
                       for c in report["blocking_codes"])

    def test_the_pre_av1_reader_would_have_dropped_this_code_entirely(self):
        """WHY §AV1 CAME FIRST, AS ARITHMETIC RATHER THAN AS A STORY.

        Before §AV1, ``_SECTIONS`` was an eight-name FILTER and the loop
        aggregated only the categories it named. Re-run that logic against a
        spec carrying a brand-string code and the code does not appear —
        anywhere. So had §AV3 been built first, the runtime half of the
        §AE2(c) remedy would have been a guard wired to a wire that goes
        nowhere, reporting green while blocking exactly zero. That is §AA
        freshly manufactured, and this test is the receipt.

        The eight names are quoted from 77c144f's parent, not re-derived, so
        this is a historical fact and not a re-run of today's code.
        """
        pre_av1 = ("font", "material", "material_attribution",
                   "production_method", "production_metrics",
                   "quantitative_fidelity", "separations", "wrap_alignment")
        code = f"{bsr.BRAND_STRING_PROVISIONAL}: descriptor"
        persisted = dict({n: [] for n in pre_av1}, brand_strings=[code])

        dropped = [c for name in pre_av1 for c in persisted.get(name, [])]
        assert dropped == [], "the pre-AV1 filter surfaced nothing"
        assert code not in dropped

        # and the repaired reader does surface it — the same input, both ways
        assert code in cpr.build_readiness(
            {"container_production_readiness_codes": persisted}
        )["blocking_codes"]


class TestTheImportFailsClosed:
    def test_the_marker_has_exactly_one_spelling(self):
        """§AK3. ``MARKER`` is imported, never re-spelled, and this pins that
        the import actually resolves to the same token the static half and the
        §AE3 record use. A second spelling is the defect this repository has
        already paid for once."""
        from tools import brand_strings as bs
        from tools import reserved_copy as rc

        assert bsr.MARKER == rc.PROVISIONAL_TOKEN == bs.MARKER
        assert bsr.MARKER == "⟪PROVISIONAL⟫"

    def test_source_guard_no_fallback_literal_behind_the_import(self):
        """SOURCE-STRING GUARD — §Y2(b). This asserts NOTHING about behaviour.

        It reads ``brand_string_runtime.py`` as text and asserts a literal is
        absent from it. A module that failed this could still behave perfectly
        at runtime, and a module that passes it could still be broken; the
        claim is about what is WRITTEN, not what happens.

        Worth having anyway, and here is the exact reason: a guard that
        silently degrades to a default when its vocabulary is missing is worse
        than one that refuses to load. The absence of a fallback is not
        observable at runtime — by construction, since the fallback would only
        ever run on an import failure — so source is the only place it can be
        checked at all.

        The name and this marker are §Y2(b)'s doing, not mine. The first draft
        was called ``test_there_is_no_fallback_literal_behind_the_import`` and
        ``test_wig_source_string_guards.py`` refused it by name, which is the
        rule catching a guard entering the repository undeclared — exactly what
        it was built to do, on the same day as §AV2's census catching a
        fabricated descriptor spreading into this same file.
        """
        import inspect

        source = inspect.getsource(bsr)
        body = source.split('"""', 2)[-1]      # past the module docstring
        assert "⟪PROVISIONAL⟫" not in body
        assert "except ImportError" not in source
        assert "PROVISIONAL_TOKEN" in source
