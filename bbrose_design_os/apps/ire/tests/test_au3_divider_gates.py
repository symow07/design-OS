"""§AU order 3 / AU2 — THE DIVIDER HAS THREE GATES, AND THIS MEASURES THEM.

AU2 named a condition the A10 manifest row had missed, and then refused to let
it be assumed: *"the executor must confirm which concepts satisfy it before
claiming the divider is drawable — per AD0(a), that is a measurement to take,
not a condition to assume is met."*

The three gates, read off ``compose_container.py`` rather than off the
manifest:

1. ``native`` — otherwise the raster-label path runs and there is no front.
2. ``direct_print``, i.e. ``bool(hierarchy_lines)`` — the C8 gate.
3. ``language is not None`` — a SUPPORTED motif language.

MEASURED ANSWER, AND IT IS NOT THE ONE THE GATE'S FRAMING SUGGESTS. All
thirteen classified families clear gate 3. What fails it is the ABSENCE of a
motif signal, which is a different thing from a family being unsupported — so
the divider is not blocked by which concept was chosen, it is blocked by
whether the concept said anything about a motif at all.

AND THE MEASUREMENT FOUND A DEFECT IT WAS NOT LOOKING FOR — see
``TestTheNegationScrubDoesNotDoWhatItsCommentSays``. That class asserts
CURRENT BEHAVIOUR THAT IS WRONG, and says so in its own docstring, so that the
fix has to flip a visible assertion rather than quietly change a number.
"""
from __future__ import annotations

import pytest

from apps.ire import container_motif as cm
from apps.ire.compose_container import _render_motif, compose_container_graph
from apps.pipeline.targets.container.silhouettes import (
    ContainerProfile, build_backbone,
)

#: the contract spells the key ``parent_surface``; ``surface`` is the
#: misspelling ``container_contract.zone_surface`` raises on, and it raised on
#: the first draft of this file — the guard working on its own author.
ZONES = [{"zone_id": "z-front", "parent_surface": "BODY_FRONT",
          "surface_family": "body"}]

FAMILIES = [name for name, _ in cm._FAMILY_KEYWORDS]


def _spec(signature: str, title: str = "T") -> dict:
    return cm.build_motif_spec(
        {"motif_signature": signature, "title": title, "variation_id": "v"},
        {}, ZONES, {})


def _rule_widths(doc) -> list:
    out = []
    for node, _parent in doc.walk():
        if str(getattr(node, "name", "") or "") != "rule-front-single":
            continue
        stroke = getattr(node, "stroke", None)
        if stroke is not None:
            out.append(round(float(stroke.width_mm), 4))
    return out


class TestGateThreeMeasuredFamilyByFamily:
    """AD0(a): a measurement, not a condition assumed to be met."""

    @pytest.mark.parametrize("family", FAMILIES)
    def test_every_classified_family_clears_gate_three(self, family):
        keyword = dict(cm._FAMILY_KEYWORDS)[family][0]
        spec = _spec(f"a {keyword} motif")
        assert spec["reconstruction_capability"] == cm.CAP_SUPPORTED, spec
        assert cm.language_for_spec(spec) is not None, spec

    def test_the_count_is_sixteen_and_the_record_says_sixteen(self):
        """``container_line_weight.third_gate_measured`` states this number.
        A record that names a count nothing recomputes goes stale silently.
        It was thirteen until §BH65(c)4 gave the composing classifier the
        ENGRAVED_LINEWORK and HALO_RINGS families; this test caught the record
        going stale on that commit, which is its job. [the owner's second answer
        of 2026-09-25: "The lid is missing the concept's rule, ring and radial
        lines." It was fifteen until RADIAL_LINES joined, with its own language;
        re-measured, it clears gate three with the rest — 16 of 16.]"""
        from apps.ire import container_line_weight as clw
        measured = clw.ELEMENTS["container_front_rule"]["third_gate_measured"]
        assert measured["families_total"] == len(FAMILIES) == 16
        assert measured["families_clearing"] == 16
        assert measured["blocked_families"] == []

    def test_the_approximate_families_still_clear_it(self):
        """An APPROXIMATION is still a supported language — the spec surfaces
        ``rendered_via_is_approximate`` so the label never outruns the
        geometry, and that honesty is not a reason to withhold the rule."""
        for family in cm._APPROXIMATE_FAMILIES:
            keyword = dict(cm._FAMILY_KEYWORDS)[family][0]
            spec = _spec(f"a {keyword} motif")
            assert cm.language_for_spec(spec) is not None, family


class TestWhatActuallyFailsGateThree:
    """Not a family. The absence of one."""

    def test_a_concept_with_no_motif_signal_at_all(self):
        spec = cm.build_motif_spec(None, {}, ZONES, {})
        assert spec["reconstruction_capability"] == cm.CAP_NONE
        assert cm.language_for_spec(spec) is None

    def test_an_empty_signature(self):
        spec = _spec("", title="")
        assert spec["reconstruction_capability"] == cm.CAP_NONE
        assert cm.language_for_spec(spec) is None

    def test_unclassified_prose_fails_CLOSED_rather_than_guessing(self):
        """The lexical resolver refuses below its evidence floor, which is the
        correct direction to fail in: no rule is better than a rule drawn
        because a sentence was long enough to look like a motif brief."""
        spec = _spec("a calm considered presence")
        assert spec["reconstruction_capability"] == cm.CAP_REVIEW_REQUIRED
        assert spec["review_code"] == cm.VECTOR_RECONSTRUCTION_REVIEW_REQUIRED
        assert cm.language_for_spec(spec) is None


class TestTheNegationScrubDoesNotDoWhatItsCommentSays:
    """A MEASURED DEFECT, PINNED RATHER THAN FIXED HERE.

    ``container_motif.py:119`` states the intent in capitals: *"NEGATED
    vocabulary must never summon a motif."* The 2C-2E repair that follows it
    works — ``classify_family`` correctly returns None for the live pilot's
    "no decorative motif … no botanical or floral element". But classification
    returning None does not end the story. ``build_motif_spec`` then falls
    through to ``resolve_language(direction=None, variation=structured)``,
    which is a DIFFERENT resolver that the negation scrub was never added to,
    and it re-summons ``petal_scatter`` — labelled, in the record it writes,
    "Petal Scatter (abstract botanical motif)". Capability SUPPORTED,
    verification VERIFIED.

    So the concept that excludes botanical elements by name gets an abstract
    botanical motif, marked verified, and a field is drawn for it. THE SCRUB
    MOVED THE SUMMONING ONE FUNCTION TO THE RIGHT.

    Per §AC this is not fixed in the tranche that found it, and per §AW5(c)
    the failing measurement is committed first. These assertions describe what
    the code DOES, not what it SHOULD do, and the fix must invert them.

    §BH67(b)1 INVERTED THEM, OWNER RULED 2026-09-24: "Draw the family the concept
    named, or refuse by name if it cannot be drawn." A concept whose own motif
    sentence names no motif gets none, and says why (``why_none``); and the
    fallback never counts a negated word.
    """

    NEGATED = ("no decorative motif, no botanical or floral element")

    def test_the_scrub_itself_works_at_the_classify_step(self):
        """The half of the repair that did land. Kept so the fix cannot be
        mistaken for having to redo this part."""
        assert cm.classify_family(self.NEGATED) is None
        assert cm.classify_family("without any floral motif") is None
        # and it has not become blind to the un-negated case
        assert cm.classify_family("floral motif") == "FLORAL_ABSTRACT"
        assert cm.classify_family("a botanical or floral element") == \
            "BOTANICAL_LINE_ART"

    def test_and_the_fallthrough_resolver_summons_nothing_since_bh67(self):
        """§BH67(b)1: was "DEFECT. This assertion is expected to be inverted by the fix." — inverted."""
        spec = _spec(self.NEGATED, title="Quiet Ground")
        assert spec["requested_family"] is None
        assert spec["rendered_via"] is None and spec["motif_variant"] is None
        assert spec["reconstruction_capability"] == cm.CAP_NONE
        assert spec["why_none"].startswith("the concept's own motif sentence names no motif")

    def test_and_no_decorative_field_is_drawn_for_it_since_bh67(self):
        """§AA — measured on the path that production runs: with no language, no MOTIF FIELD is drawn (§BH67(b)1
        inverted the "<- wrong" assertions that stood here)."""
        spec = _spec(self.NEGATED, title="Quiet Ground")
        assert cm.language_for_spec(spec) is None

    def test_w6_a_sentence_that_names_the_type_alone_names_no_motif(self):
        """[His answer of 2026-10-05, W6: "type-only is a real design style".] A concept that says its lid prints its
        type alone — "type only", "the mark and the name alone", "only the name" — names no motif: none is drawn and the
        design is rebuilt, where the lexical fallback had refused it (VECTOR_RECONSTRUCTION_REVIEW_REQUIRED). A motif it
        does name is still drawn, even beside "the name only"."""
        for words in ("type only, no motif or window", "no decorative motif — the mark and the name alone",
                      "only the name and the mark, typographic", "the lettering alone"):
            spec = _spec(words, title="A_TYPE_ONLY")
            assert spec["reconstruction_capability"] == cm.CAP_NONE, (words, spec.get("review_detail"))
            assert cm.language_for_spec(spec) is None
        named = _spec("a soft liquid veil behind the name only", title="B_LIQUID_VEIL")
        assert named["reconstruction_capability"] == cm.CAP_SUPPORTED and named["rendered_via"] == "liquid_veil"


class TestTheThreeGatesTogether:
    """The gates measured on a composed document rather than on the spec."""

    def _compose(self, *, hierarchy=None, motif=None):
        return compose_container_graph(
            build_backbone(ContainerProfile(archetype="bottle", )), product_name="Liquid Veil",
            sku="LV-01", native=True, zones=ZONES,
            hierarchy_lines=hierarchy, motif_spec=motif)

    def test_all_three_open_and_the_rule_is_drawn_at_the_ruled_weight(self):
        doc = self._compose(
            hierarchy=[{"text": "Rose Nectar", "rel": 1.0,
                        "kind": "product_name"}],
            motif=_spec("a ribbon motif"))
        assert _rule_widths(doc) == [0.30], "the §AU2 weight is not drawn"

    def test_gate_two_shut_draws_no_rule(self):
        doc = self._compose(hierarchy=None, motif=_spec("a ribbon motif"))
        assert _rule_widths(doc) == []

    def test_gate_three_shut_draws_no_rule_even_with_a_hierarchy(self):
        """The gate AU2 said the manifest had missed. A front with copy on it
        and no supported motif composes WITHOUT its divider — silently, which
        is why the condition needed naming."""
        doc = self._compose(
            hierarchy=[{"text": "Rose Nectar", "rel": 1.0,
                        "kind": "product_name"}],
            motif=_spec("a calm considered presence"))
        assert _rule_widths(doc) == []


# ---------------------------------------------------------------------------------------------------------------
# §BH65(c) — THE ONE CONTRACT's per-run record (apps/ire/composer_vocabulary.realization), measured on the front
# these three gates open: the direct-print hierarchy with a SUPPORTED motif, where gate 3 draws the divider IN THE
# MOTIF'S PLACE. The record reads the Document the composer built, and only its PRODUCT artwork — never the sheet's
# title, swatches or reference photo.
# ---------------------------------------------------------------------------------------------------------------

#: task 89's own concept as its structured record reads (A_PETAL_WINDOW, read-only 2026-09-23), shortened
_PETAL_WINDOW = {
    "verified": True, "variation_id": "A_PETAL_WINDOW", "title": "Contour Petal — Controlled Window",
    "motif_signature": "Seven closed Bézier petal-droplets in a loose radial cluster inside the cartouche window",
    "finish_signature": "Matte soft-touch laminate ground; rose-gold hot-stamp foil on petal outlines, window rule "
                        "and circumference rule ring; spot gloss UV over the cartouche interior",
    "typography_signature": "Tall classical serif wide-tracked small caps (EN) + matching-weight calligraphic "
                            "Arabic (AR), stacked above and below the petal window",
    "color_field_signature": "Warm Cream #FAF3EC ground; radial gradient within the window",
}


class TestTheContractRecordsWhatTheFrontDiscards:
    def _front(self):
        spec = cm.build_motif_spec(_PETAL_WINDOW, {}, ZONES, {})
        doc = compose_container_graph(
            build_backbone(ContainerProfile(archetype="bottle", height_mm=110, width_mm=40)),
            product_name="Focus Pressed Powder", sku="BBR-CO-2060", native=True, zones=ZONES,
            hierarchy_lines=[{"text": "Focus Pressed Powder", "rel": 1.0, "kind": "product_name"}],
            motif_spec=spec)
        return doc, spec

    def test_the_record_names_every_discard_with_its_own_code(self):
        from apps.ire import composer_vocabulary as V
        doc, spec = self._front()
        rec = V.realization(_PETAL_WINDOW, doc, spec)
        assert rec["schema_version"] == V.SCHEMA and rec["state"] == "READ"
        rows = {r["term"]: r for r in rec["terms"]}
        # the concept's finishes and type treatments: asked for, not drawn, each named
        for key in ("foil", "spot_uv", "soft_touch", "tracking", "small_caps"):
            assert rows[key]["drawn"] is False and f"{V.UNDRAWN_CODE}:{key}" in rec["codes"], key
        # §BH65(c)3: the window, the ring and the bilingual line are GOVERNED on the container front — §AU1 (C8)
        # decides whether they print there — and are still named, and still not drawn
        for key in ("window", "frame_ring", "bilingual"):
            assert rows[key]["drawn"] is False and f"{V.GOVERNED_CODE}:{key}" in rec["codes"], key
        # a capability the composer HAS and did not use here is undrawn too — the radial gradient in the window
        assert rows["gradient"]["status"] == V.DRAWN and rows["gradient"]["drawn"] is False
        # the motif: its language resolves, and gate 3 draws the divider in its place
        assert spec["reconstruction_capability"] == cm.CAP_SUPPORTED
        assert rec["motif"]["drawn"] is False
        assert f"{V.UNDRAWN_CODE}:motif:{spec['requested_family']}" in rec["codes"]
        assert _rule_widths(doc) == [0.30]
        # what the front DOES draw reads as drawn, from its own nodes
        assert rows["centred_stack"]["drawn"] is True
        # the face words are the role layer's to decide — named, never counted as undrawn
        assert rows["typeface"]["status"] == V.GOVERNED and f"{V.GOVERNED_CODE}:typeface" in rec["codes"]
        assert "typeface" not in rec["undrawn"]

    def test_no_structured_record_is_said_rather_than_guessed(self):
        from apps.ire import composer_vocabulary as V
        doc, spec = self._front()
        rec = V.realization(None, doc, spec)
        assert rec["state"] == "NO_STRUCTURED_RECORD" and rec["terms"] == [] and rec["codes"] == []

    def test_the_evidence_is_the_product_artwork_never_the_sheet(self):
        """The sheet carries its own solid swatches, a title and a SKU — none is the product's decoration, and a
        record that counted them would read every concept's flat colour as drawn."""
        from apps.ire import composer_vocabulary as V
        doc, _spec = self._front()
        sheet = {"sheet-title", "sku", "reference-label"} | {
            n.name for n, _ in doc.walk() if (n.name or "").startswith(("swatch", "reference"))}
        for capability in V.EVIDENCE_READERS:
            assert not set(V.evidence(capability, doc)) & sheet, capability
        assert "rule-front-single" not in V.evidence("motif", doc)


class TestTheFinishesLandWhereTheSentenceSays:
    """§BH65(c)2 on the direct-print front: each clause of the concept's finish sentence lands on the elements its
    targets name; a target the front does not draw is NOT_DRAWN by name; the lockup — a raster — is refused."""

    def _front(self, finishes):
        structured = dict(_PETAL_WINDOW, finish_signature=finishes)
        spec = cm.build_motif_spec(structured, {}, ZONES, {})
        doc = compose_container_graph(
            build_backbone(ContainerProfile(archetype="bottle", height_mm=110, width_mm=40)),
            product_name="Focus Pressed Powder", sku="BBR-CO-2060", native=True, zones=ZONES,
            hierarchy_lines=[{"text": "Focus Pressed Powder", "rel": 1.0, "kind": "product_name"}],
            motif_spec=spec)
        return doc, spec, structured

    def test_task_89s_sentence_lands_on_the_ground_and_names_every_target_the_front_does_not_draw(self):
        from apps.ire import container_finishes as F
        doc, spec, _ = self._front(_PETAL_WINDOW["finish_signature"] + "; BBROSE wordmark in rose-gold foil")
        rows = F.apply(doc, spec["finish_assignments"], brand_metallic_hex="#C9A24B")["applied"]
        state = {(r["finish"], r["target"]): r["state"] for r in rows}
        assert state[("soft_touch", "ground")] == F.APPLIED
        assert state[("foil", "motif")] == F.NOT_DRAWN            # the front draws the §BB4 divider, no motif
        assert state[("foil", "window")] == F.NOT_DRAWN
        assert state[("foil", "ring")] == F.NOT_DRAWN
        assert state[("foil", "lockup")] == F.REFUSED_NO_VECTOR_MASTER
        assert state[("spot_uv", "window_interior")] == F.NOT_DRAWN
        front = [n for n, _ in doc.walk() if n.name == "FRONT_DIRECT_PRINT"][0]
        assert [(f.kind, f.plate) for f in front.finishes] == [("soft_touch", "SOFT_TOUCH")]
        # the divider is a rule and never takes a motif's finish
        assert all(not n.finishes for n, _ in doc.walk() if n.name == "rule-front-single")

    def test_a_foil_name_that_is_also_embossed_keeps_both_plates(self, tmp_path):
        """Measured on the first render of this commit: with one finish per element the emboss OVERWROTE the foil on
        the same name and the foil plate vanished. An element takes a list; the first ink paints it."""
        import fitz
        from apps.ire import container_finishes as F
        from apps.ire.emitters.pdf_ai import emit_pdf_ai
        doc, spec, _ = self._front("rose-gold hot-stamp foil on the product name; blind emboss on the name")
        F.apply(doc, spec["finish_assignments"], brand_metallic_hex="#C9A24B")
        # the name wraps on this 40 mm front, so it is two runs — both take both finishes
        names = [n for n, _ in doc.walk() if (n.name or "").startswith("product-name-hero")]
        assert len(names) == 2 and all([f.kind for f in n.finishes] == ["foil", "emboss"] for n in names)
        usage = {}
        out = emit_pdf_ai(doc, str(tmp_path / "two.ai"), usage_out=usage)
        runs = sorted(n.name for n in names)
        assert [(p["plate"], p["items"]) for p in usage[F.SCHEMA]["plates"]] == [
            ("FOIL_ROSE_GOLD", runs), ("EMBOSS", runs)]
        assert b".788235 .635294 .294118 rg" in fitz.open(out)[0].read_contents()   # the name prints in the metal

    def test_a_foil_name_is_drawn_in_the_metal_and_plated_on_its_own_page(self, tmp_path):
        import fitz
        from apps.ire import composer_vocabulary as V
        from apps.ire import container_finishes as F
        from apps.ire.emitters.pdf_ai import emit_pdf_ai
        doc, spec, structured = self._front("rose-gold hot-stamp foil on the product name; matte soft-touch ground")
        applied = F.apply(doc, spec["finish_assignments"], brand_metallic_hex="#C9A24B")
        rec = V.realization(structured, doc, spec, finishes=applied)
        rows = {r["term"]: r for r in rec["terms"]}
        assert rows["foil"]["drawn"] is True and rows["soft_touch"]["drawn"] is True
        assert any(r["target"] == "name" and r["state"] == F.APPLIED for r in rec["finishes"])
        usage = {}
        out = emit_pdf_ai(doc, str(tmp_path / "front.ai"), usage_out=usage)
        pdf = fitz.open(out)
        plates = usage[F.SCHEMA]["plates"]
        assert [p["plate"] for p in plates] == ["SOFT_TOUCH", "FOIL_ROSE_GOLD"] or \
            sorted(p["plate"] for p in plates) == ["FOIL_ROSE_GOLD", "SOFT_TOUCH"]
        assert pdf.page_count == 1 + len(plates) == usage[F.SCHEMA]["pages"]
        for p in plates:
            assert f"FINISH PLATE {p['plate']}" in pdf[p["page"] - 1].get_text()
        # the colour counter still agrees with the artefact, every page read
        from apps.ire.colour_roles import USAGE_SCHEMA
        assert usage[USAGE_SCHEMA]["reconciliation"]["agree"] is True


#: task 91's own finish sentence (A_PETAL_WINDOW, the clean §BH65(d) run, read-only 2026-09-24), verbatim — the run
#: that cut an EMBOSS plate from "tactile contrast" and plated every droplet
_TASK_91_FINISHES = ("Matte soft-touch laminate over full lid; rose-gold hot-foil on cartouche border stroke, two petal "
                     "fills, BBROSE wordmark and sidewall band; spot-UV opportunity on remaining five petal surfaces "
                     "for tactile contrast")


class TestAFinishNotSpecifiedIsNotApplied:
    """§BH67(b)3, OWNER RULED 2026-09-24: "THE FINISH READER INVENTS AN EMBOSS from "tactile contrast". A finish that
    was not specified is not applied, the same rule as a colour." Measured on task 91's real run: one clause cut a
    SPOT_UV and an EMBOSS plate, foil and spot UV landed on every droplet, and "cartouche border" added a row for a
    ring the concept never asked for."""

    def test_task_91s_sentence_plates_only_what_it_specifies(self):
        from apps.ire import container_finishes as F
        doc, _spec, _concept = _face("89_A_PETAL_WINDOW")
        out = F.apply(doc, F.assignments(_TASK_91_FINISHES), brand_metallic_hex="#C9A24B")
        assert not [n for n, _ in doc.walk() if any(f.kind == "emboss" for f in getattr(n, "finishes", ()))]
        rows = {(r["finish"], r["target"], r["state"]) for r in out["applied"]}
        assert {t for f, t, _s in rows if f == "foil"} == {"window", "motif", "lockup", "band"}     # no ring
        assert ("emboss", None, F.EVOKED_NOT_SPECIFIED) in rows
        assert "CONTAINER_FINISH_EVOKED_NOT_SPECIFIED:emboss:tactile" in out["codes"]

    def test_a_count_is_a_limit_and_the_remaining_are_the_others(self):
        from apps.ire import container_finishes as F
        doc, _spec, _concept = _face("89_A_PETAL_WINDOW")
        rows = F.apply(doc, F.assignments(_TASK_91_FINISHES), brand_metallic_hex="#C9A24B")["applied"]
        foil = next(r["count"] for r in rows if (r["finish"], r["target"]) == ("foil", "motif"))
        uv = next(r["count"] for r in rows if (r["finish"], r["target"]) == ("spot_uv", "motif"))
        assert foil["count"] == 2 == len(foil["units"]) and not foil["from_remaining"]
        assert uv["count"] == 5 == len(uv["units"]) and uv["from_remaining"]
        assert not set(foil["units"]) & set(uv["units"])
        for kind, units in (("foil", foil["units"]), ("spot_uv", uv["units"])):
            # §BH67(b)1: the 89A face draws its petals as petals now — the units are petal-N, not dewdrop-*
            plated = [n for n, _ in doc.walk() if (n.name or "").startswith(("dewdrop", "petal"))
                      and any(f.kind == kind for f in getattr(n, "finishes", ()))]
            assert sorted(F._units(plated)) == sorted(units), kind

    def test_bh71_the_picture_says_which_units_take_the_metal(self):
        """§BH71 PART 1, the owner's goal of 2026-09-28: \"The concept's hero element (e.g. 91's rose-gold flower
        emblem), its finish and its material carry into the drawing.\" 91's sentence says \"two petal fills\" take the
        rose-gold foil; its picture shows which two — the units its measured hero records lit like metal. The foil
        lands on those, the spot UV on the remaining five; with no measured hero the choice is spread as before."""
        from apps.ire import container_finishes as F
        doc, _spec, _concept = _face("89_A_PETAL_WINDOW")
        units = list(F._units([n for n, _ in doc.walk() if (n.name or "").startswith("petal")]))
        shown = [units[1], units[4]]
        doc.metadata.setdefault("concept_front", {}).setdefault("face", {})["hero"] = {
            "units": units, "metal_units": shown}
        rows = F.apply(doc, F.assignments(_TASK_91_FINISHES), brand_metallic_hex="#C9A24B")["applied"]
        foil = next(r["count"] for r in rows if (r["finish"], r["target"]) == ("foil", "motif"))
        uv = next(r["count"] for r in rows if (r["finish"], r["target"]) == ("spot_uv", "motif"))
        assert foil["units"] == shown and foil["chosen"].startswith("the ones the concept picture shows lit like metal")
        assert len(uv["units"]) == 5 and not set(uv["units"]) & set(shown)
        foiled = [n for n, _ in doc.walk() if (n.name or "").startswith("petal")
                  and any(f.kind == "foil" for f in getattr(n, "finishes", ()))]
        assert sorted(F._units(foiled)) == sorted(shown)
        plain, _s, _c = _face("89_A_PETAL_WINDOW")                      # no measured hero: spread, as before
        rows = F.apply(plain, F.assignments(_TASK_91_FINISHES), brand_metallic_hex="#C9A24B")["applied"]
        spread = next(r["count"] for r in rows if (r["finish"], r["target"]) == ("foil", "motif"))
        assert spread["chosen"].startswith("spread evenly")

    def test_only_a_process_word_cuts_a_plate(self):
        from apps.ire import composer_vocabulary as V
        from apps.ire import container_finishes as F
        for words in ("tactile relief on the lid", "sculpted raised sidewall", "matte glossy satin pearl lid"):
            assert [f for c in F.assignments(words)["clauses"] for f in c["finishes"]] == [], words
        for key, process in V.FINISH_PROCESS_WORDS.items():
            assert set(process) <= set(V.TERM_BY_KEY[key].words), key
            for word in V.TERM_BY_KEY[key].words:
                clauses = F.assignments(f"{word} on the lid")["clauses"]
                specified = [f["kind"] for c in clauses for f in c["finishes"]]
                evoked = [e["kind"] for c in clauses for e in c["evoked"]]
                assert (specified, evoked) == (([key], []) if word in process else ([], [key])), (word, clauses)
        for words, kinds in (("metallic rose-gold ink on the name", ["metallic_ink"]),
                             ("velvet lamination over the lid", ["soft_touch"]),
                             ("matte laminate over the lid", []), ("pearl-white gloss cap", []),
                             ("engraved fields, tactile relief and spot-UV gloss", ["spot_uv"])):
            assert [f["kind"] for c in F.assignments(words)["clauses"] for f in c["finishes"]] == kinds, words

    def test_a_windows_own_border_is_the_window_and_never_a_ring(self):
        from apps.ire import container_finishes as F
        for words in ("cartouche border stroke", "window border", "medallion outline", "cartouche frame"):
            assert F.assignments(f"rose-gold foil on the {words}")["clauses"][0]["targets"] == ["window"], words
        assert "ring" in F.assignments("rose-gold foil on the circumference rule ring")["clauses"][0]["targets"]

    def test_the_contract_records_an_evoked_finish_and_not_an_undrawn_one(self):
        from apps.ire import composer_vocabulary as V
        from apps.ire import container_finishes as F
        doc, spec, concept = _face("89_A_PETAL_WINDOW")
        applied = F.apply(doc, F.assignments(_TASK_91_FINISHES), brand_metallic_hex="#C9A24B")
        rec = V.realization(dict(concept, finish_signature=_TASK_91_FINISHES), doc, spec, finishes=applied)
        assert not [r for r in rec["terms"] if r["term"] == "emboss" and r["drawn"]]
        assert f"{V.EVOKED_CODE}:emboss" in rec["codes"] and f"{V.UNDRAWN_CODE}:emboss" not in rec["codes"]
        assert "emboss" in rec["evoked"] and "emboss" not in rec["undrawn"]



#: task 89's own confirmed lid zone, as its record holds it (read-only, 2026-09-23), on its own 110 x 95 case
_LID_ZONE = [{"zone_id": "z_lid", "parent_surface": "LID_TOP", "zone_type": "FRONT_PRINT_ZONE", "x": 9.9, "y": 10.5,
              "width": 90.2, "height": 74.1, "safe_margin_mm": 3.0, "max_artwork_coverage": 0.8}]
_PETAL_WINDOW_FULL = dict(
    _PETAL_WINDOW,
    composition_signature="Vertically centred cartouche window on lid face, with product names anchored above and "
                          "below the window in open cream ground; circular rule ring frames the entire lid",
    motif_signature="Seven closed Bézier petal-droplets in a loose radial cluster inside the cartouche window, "
                    "alternating filled blush and rose-gold outline forms")


class TestTheFrontDrawsTheConceptWhereAU1LetsItPrint:
    """§BH65(c)3 on task 89's own geometry. The composer can draw the concept's window, ring and motif; WHERE any of
    it prints on the container front is §AU1's (C8, OWNER_BLOCKER_CLEARANCE.md:5652): decoration above or behind,
    nothing else, and the ruled stack never moves to make room. On task 89 nothing concept-side lands — recorded with
    its millimetres — and on a zone with room above the mark the window prints there.

    §BH66(a) SCOPED THIS: §AU1 governs bottle, jar and tube fronts, and a compact's lid is a FACE, arranged as the
    concept's own words put it (``TestTheFaceIsArrangedAsTheConceptSays``). The pipeline hands a face run the
    reading of those words; these tests hand in the plan WITHOUT one, which is exactly what every FRONT form's run
    does, so they keep proving §AU1's placement policy — on the lid's geometry, because its 7.703 mm is the case that
    policy was measured on. Their numbers are the front path's, never a compact run's since §BH66(a)."""

    def _compose(self, plan, zones=_LID_ZONE, structured=_PETAL_WINDOW_FULL):
        from apps.ire.front_hierarchy import ruled_front_hierarchy
        spec = cm.build_motif_spec(structured, {}, zones, {})
        doc = compose_container_graph(
            build_backbone(ContainerProfile(archetype="compact", height_mm=95, width_mm=110)),
            product_name="Focus Pressed Powder", sku="BBR-CO-2060", native=True, zones=zones,
            logo_path="media/brand/logo.png",
            hierarchy_lines=ruled_front_hierarchy("Focus Pressed Powder", descriptor="pressed powder compact"),
            motif_spec=spec, colors={"body": "#B4A390", "cap": "#FAF3EC"}, concept_front=plan)
        return doc, spec

    def _plan(self, structured=_PETAL_WINDOW_FULL, zones=_LID_ZONE):
        from apps.ire import concept_front as CF
        return CF.plan(structured, cm.build_motif_spec(structured, {}, zones, {}), ground_hex="#FAF3EC",
                       edge_hex="#F7DDE3")

    @staticmethod
    def _stack(doc):
        from apps.ire.graph import TextRun
        return sorted((n.name, round(n.y, 6), n.size_pt) for n, _ in doc.walk() if isinstance(n, TextRun)
                      and (n.name or "").startswith(("product-name", "front-"))) + [
            (n.name, [round(getattr(s, "y", 0.0), 6) for s in n.segments]) for n, _ in doc.walk()
            if n.name == "rule-front-single"]

    def test_the_plan_reads_task_89s_own_words(self):
        plan = self._plan()
        assert (plan["layout"], plan["ring"], plan["outlines"], plan["behind"]) == ("window", True, True, False)
        assert plan["window_fill"] == {"kind": "radial", "centre": "#FAF3EC", "edge": "#F7DDE3"}

    def test_on_task_89_nothing_concept_side_lands_and_every_reason_is_recorded(self):
        doc, _ = self._compose(self._plan())
        without, _ = self._compose(None)
        assert "FRONT_CONCEPT" not in {n.name for n, _ in doc.walk()}
        assert self._stack(doc) == self._stack(without)                   # the ruled stack does not move
        assert _rule_widths(doc) == [0.30]                                 # §BB4's divider stays, at §AU2's weight
        rec = doc.metadata["concept_front"]
        assert rec["drawn"] == []
        ring, window = rec["not_placed"]
        assert ring["element"] == "frame-ring" and "OWNER_BLOCKER_CLEARANCE.md:5652" in ring["reasons"][0]
        assert window["element"] == "window" and window["above_mm"] == 7.703
        assert "under the 8.0 mm floor" in window["reasons"][0]
        assert "OWNER_BLOCKER_CLEARANCE.md:5652" in window["reasons"][1]
        assert "panel behind the names" in window["reasons"][2]

    def test_with_room_above_the_mark_the_window_prints_there_with_its_motif_and_fill(self):
        from apps.ire.graph import GradientFill
        from apps.pipeline.services.container_projection import validate_zone_containment
        roomy = [dict(_LID_ZONE[0], y=6.2, height=78.4)]
        doc, _ = self._compose(self._plan(zones=roomy), zones=roomy)
        rec = doc.metadata["concept_front"]
        assert rec["placed"] == "above the mark's clear space"
        assert rec["drawn"] == ["window-interior", "motif-window", "window-frame"]
        interior = [n for n, _ in doc.walk() if n.name == "window-interior"][0]
        assert isinstance(interior.fill, GradientFill) and interior.fill.kind == "radial"
        motif = [n for n, _ in doc.walk() if n.name == "motif-window"][0]
        assert motif.clip is not None
        # §BH67(b)1: "seven closed Bézier petal-droplets … alternating filled blush and rose-gold outline forms" is
        # drawn as SEVEN PETALS — it was drawn as the dewdrop family, the classifier's substring vote
        leaves = [x for x in motif.children if x.type == "path" and x.name.startswith("petal-")]
        assert len(leaves) == 7                                           # the window's own motif, not the strips
        assert any(x.fill is None and x.stroke is not None for x in leaves)   # the alternating outline forms
        assert any(x.fill is not None for x in leaves)
        new = [p for p in doc.metadata["placements"] if p["kind"] in ("window", "motif")]
        assert validate_zone_containment(new, roomy, {"archetype": "compact", "variant": ""}) == []
        # the window's ink stays out of the mark's clear space
        from apps.ire.container_brand_usage import clear_space_mm, measure_cap_ratio
        logo = [n for n, _ in doc.walk() if n.name == "logo"][0]
        clear = clear_space_mm(logo.h, measure_cap_ratio("media/brand/logo.png")["cap_ratio"])
        frame = [n for n, _ in doc.walk() if n.name == "window-frame"][0]
        assert max(s.y for s in frame.segments if hasattr(s, "y")) + 0.15 <= logo.y - clear + 1e-9

    def test_behind_the_type_only_when_the_concept_says_so_and_never_under_the_mark(self):
        veil = {"verified": True, "variation_id": "B", "title": "Liquid Veil",
                "motif_signature": "a flowing liquid veil of ribbons running behind the name across the whole face"}
        doc, _ = self._compose(self._plan(structured=veil), structured=veil)
        rec = doc.metadata["concept_front"]
        assert rec["placed"] == "behind the type, below the mark's clear space"
        names = [n.name for n, _ in doc.walk()]
        assert names.index("FRONT_CONCEPT_BEHIND") < names.index("FRONT_DIRECT_PRINT")   # drawn first: behind
        behind = [n for n, _ in doc.walk() if n.name == "FRONT_CONCEPT_BEHIND"][0]
        logo = [n for n, _ in doc.walk() if n.name == "logo"][0]
        assert min(s.y for s in behind.clip if hasattr(s, "y")) >= logo.y + logo.h      # never under the mark

    def test_the_ring_draws_when_called_and_is_never_called_on_the_container_front(self):
        from apps.ire.compose_container import draw_ring
        from apps.ire.graph import Color
        ring = draw_ring(10, 10, 40, 30, Color.from_hex("#5A2C3A"))
        assert ring.name == "frame-ring" and ring.stroke.width_mm == 0.30
        roomy = [dict(_LID_ZONE[0], y=6.2, height=78.4)]
        doc, _ = self._compose(self._plan(zones=roomy), zones=roomy)
        assert "frame-ring" not in {n.name for n, _ in doc.walk()}

    def test_the_record_calls_the_window_governed_and_names_the_undrawn_motif(self):
        from apps.ire import composer_vocabulary as V
        doc, spec = self._compose(self._plan())
        rec = V.realization(_PETAL_WINDOW_FULL, doc, spec)
        rows = {r["term"]: r for r in rec["terms"]}
        assert rows["window"]["status"] == V.GOVERNED and rows["window"]["drawn"] is False
        assert f"{V.GOVERNED_CODE}:window" in rec["codes"] and f"{V.GOVERNED_CODE}:frame_ring" in rec["codes"]
        # on the FRONT path the motif is not on the lid — the sheet's surface strip draws a "LID TOP" panel with it as
        # a reduced continuation, and the record says exactly where. §BH66(a)'s face path draws the lid once, as its
        # own hero, with the motif in its window
        assert rec["motif"]["status"] == V.DRAWN and rec["motif"]["evidence"] == ["motif-LID_TOP"]
        assert rec["front"]["not_placed"][1]["above_mm"] == 7.703

    def test_no_geometry_is_recorded_never_guessed(self):
        doc, _ = self._compose(self._plan(zones=ZONES), zones=ZONES)
        assert doc.metadata["concept_front"]["not_placed"] == [
            {"element": "all", "reason": "the confirmed zone carries no geometry"}]



class TestTheEngravedFieldPrintsWhereAU1LetsIt:
    """§BH65(c)4 end to end: an engraved concept is classified as itself, drawn as a hatching PatternFill above the
    mark where the zone has room, and the family check finds its geometry — through the unchanged instrument, with
    only a lookup row for the new language's node names."""

    def test_an_engraved_concept_draws_hatching_and_the_family_check_passes(self):
        from apps.ire import concept_front as CF
        from apps.ire.container_motif_fidelity import validate_motif_fidelity
        from apps.ire.front_hierarchy import ruled_front_hierarchy
        from apps.ire.graph import PatternFill
        roomy = [dict(_LID_ZONE[0], y=6.2, height=78.4)]
        concept = {"verified": True, "variation_id": "E", "title": "Engraved",
                   "motif_signature": "fine engraved guilloche linework across a band"}
        spec = cm.build_motif_spec(concept, {}, roomy, {})
        assert spec["rendered_via"] == "engraved_field"
        plan = CF.plan(concept, spec, ground_hex="#FAF3EC", edge_hex=None)
        doc = compose_container_graph(
            build_backbone(ContainerProfile(archetype="compact", height_mm=95, width_mm=110)),
            product_name="Focus Pressed Powder", sku="S", native=True, zones=roomy, logo_path="media/brand/logo.png",
            hierarchy_lines=ruled_front_hierarchy("Focus Pressed Powder", descriptor="pressed powder compact"),
            motif_spec=spec, colors={"body": "#B4A390", "cap": "#FAF3EC"}, concept_front=plan)
        hatch = [n for n, _ in doc.walk() if (n.name or "").startswith("engraved-field")]
        assert hatch and all(isinstance(n.fill, PatternFill) and n.fill.kind == "lines" for n in hatch)
        assert validate_motif_fidelity(doc, spec)["axes"]["motif_family"]["state"] == "MEASURED_PASS"



def test_the_concepts_own_blend_word_sets_the_mode_on_its_motif_and_nowhere_else():
    """§BH65(c)5: "printed in multiply over the ground" — the concept's own word — prints the concept's motif in
    multiply; the ruled type, the mark and the §BB4 divider print Normal."""
    from apps.ire import concept_front as CF
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    roomy = [dict(_LID_ZONE[0], y=6.2, height=78.4)]
    concept = {"verified": True, "variation_id": "M", "title": "Multiply",
               "motif_signature": "scattered powder constellation printed in multiply over the ground"}
    spec = cm.build_motif_spec(concept, {}, roomy, {})
    plan = CF.plan(concept, spec, ground_hex="#FAF3EC", edge_hex=None)
    assert plan["blend"] == "multiply" and plan["why"]["blend"] == ["multiply"]
    doc = compose_container_graph(
        build_backbone(ContainerProfile(archetype="compact", height_mm=95, width_mm=110)),
        product_name="Focus", sku="S", native=True, zones=roomy, logo_path="media/brand/logo.png",
        hierarchy_lines=ruled_front_hierarchy("Focus", descriptor="pressed powder compact"),
        motif_spec=spec, colors={"body": "#B4A390", "cap": "#FAF3EC"}, concept_front=plan)
    blended = {n.name for n, _ in doc.walk() if getattr(n, "blend_mode", None)}
    assert blended == {"motif-field"}



def test_the_concepts_own_fade_and_glow_words_fade_its_motif_and_light_it():
    """§BH65(c)6: "a constellation that fades toward the base, with a soft glow" — the concept's own words — fades
    the concept's motif downward through a soft mask and draws a glow behind it; nothing else is masked."""
    from apps.ire import concept_front as CF
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    roomy = [dict(_LID_ZONE[0], y=6.2, height=78.4)]
    concept = {"verified": True, "variation_id": "F", "title": "Fade",
               "motif_signature": "a scattered powder constellation that fades toward the base, with a soft glow"}
    spec = cm.build_motif_spec(concept, {}, roomy, {})
    plan = CF.plan(concept, spec, ground_hex="#FAF3EC", edge_hex=None)
    assert plan["fade"] == "down" and plan["glow"] is True
    doc = compose_container_graph(
        build_backbone(ContainerProfile(archetype="compact", height_mm=95, width_mm=110)),
        product_name="Focus", sku="S", native=True, zones=roomy, logo_path="media/brand/logo.png",
        hierarchy_lines=ruled_front_hierarchy("Focus", descriptor="pressed powder compact"),
        motif_spec=spec, colors={"body": "#B4A390", "cap": "#FAF3EC"}, concept_front=plan)
    masked = {n.name: n.opacity_mask.kind for n, _ in doc.walk() if getattr(n, "opacity_mask", None)}
    assert masked == {"motif-field": "linear", "concept-glow": "radial"}
    names = [n.name for n, _ in doc.walk()]
    assert "motif-field" in names[names.index("concept-glow"):]              # the glow is drawn first: BEHIND



def test_the_concepts_own_shadow_words_put_a_soft_shadow_under_its_motif_and_under_nothing_ruled():
    """§BH65(c)7: "petals casting a soft shadow" — the concept's own words — lay an approximated soft shadow under the
    concept's motif; the ruled type, the mark and the §BB4 divider cast none."""
    from apps.ire import concept_front as CF
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    roomy = [dict(_LID_ZONE[0], y=6.2, height=78.4)]
    concept = {"verified": True, "variation_id": "S", "title": "Shadow",
               "motif_signature": "a scattered powder constellation casting a soft shadow"}
    spec = cm.build_motif_spec(concept, {}, roomy, {})
    plan = CF.plan(concept, spec, ground_hex="#FAF3EC", edge_hex=None)
    assert plan["shadow"] is True
    doc = compose_container_graph(
        build_backbone(ContainerProfile(archetype="compact", height_mm=95, width_mm=110)),
        product_name="Focus", sku="S", native=True, zones=roomy, logo_path="media/brand/logo.png",
        hierarchy_lines=ruled_front_hierarchy("Focus", descriptor="pressed powder compact"),
        motif_spec=spec, colors={"body": "#B4A390", "cap": "#FAF3EC"}, concept_front=plan)
    assert {n.name for n, _ in doc.walk() if getattr(n, "shadow", None) is not None} == {"motif-field"}



def test_the_concepts_own_tracking_and_small_caps_words_set_the_name_and_only_the_name():
    """§BH65(c)8 on task 89's own words — "Tall classical serif wide-tracked small caps (EN)" — the name tier prints in
    capitals at 0.15 em tracking, wraps on the WIDER estimate so the clip never eats its ends, and nothing else on the
    front takes the treatment."""
    from apps.ire import concept_front as CF
    from apps.ire.compose_container import wrap_name
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    from apps.ire.graph import TextRun
    plan = CF.plan(dict(_PETAL_WINDOW_FULL), cm.build_motif_spec(_PETAL_WINDOW_FULL, {}, _LID_ZONE, {}),
                   ground_hex="#FAF3EC", edge_hex=None)
    assert plan["name_style"] == {"tracking_em": 0.15, "text_case": "upper"}
    spec = cm.build_motif_spec(_PETAL_WINDOW_FULL, {}, _LID_ZONE, {})
    doc = compose_container_graph(
        build_backbone(ContainerProfile(archetype="compact", height_mm=95, width_mm=110)),
        product_name="Focus Pressed Powder", sku="S", native=True, zones=_LID_ZONE, logo_path="media/brand/logo.png",
        hierarchy_lines=ruled_front_hierarchy("Focus Pressed Powder", descriptor="pressed powder compact"),
        motif_spec=spec, colors={"body": "#B4A390", "cap": "#FAF3EC"}, concept_front=plan)
    styled = {n.name for n, _ in doc.walk() if isinstance(n, TextRun) and (n.tracking_em or n.text_case)}
    assert styled and all(name.startswith("product-name-hero") for name in styled)
    # the wider estimate wraps a name the plain estimate would have passed whole
    # 40 mm sits between the plain estimate (33.3 mm) and the tracked-capitals one (49.0 mm)
    assert wrap_name("Focus Pressed Powder", 9.0, 40.0) == ["Focus Pressed Powder"]
    assert wrap_name("Focus Pressed Powder", 9.0, 40.0, tracking_em=0.15, upper=True) != ["Focus Pressed Powder"]



def test_a_band_of_the_motif_is_a_field_where_au1_lets_it_print():
    """§BH65(c)9: "a banded stripe of engraved linework" — the concept's own band words — is the motif as a FIELD
    across the region §AU1 gives it; on task 89's own zone that region is too short, and the record says so."""
    from apps.ire import concept_front as CF
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    concept = {"verified": True, "variation_id": "B", "title": "Band",
               "composition_signature": "a banded stripe of linework",
               "motif_signature": "fine engraved guilloche linework"}
    for zones, drawn in (([dict(_LID_ZONE[0], y=6.2, height=78.4)], True), (_LID_ZONE, False)):
        spec = cm.build_motif_spec(concept, {}, zones, {})
        plan = CF.plan(concept, spec, ground_hex="#FAF3EC", edge_hex=None)
        assert plan["layout"] == "field" and plan["why"]["layout"] == ["banded", "stripe"]
        doc = compose_container_graph(
            build_backbone(ContainerProfile(archetype="compact", height_mm=95, width_mm=110)),
            product_name="Focus", sku="S", native=True, zones=zones, logo_path="media/brand/logo.png",
            hierarchy_lines=ruled_front_hierarchy("Focus", descriptor="pressed powder compact"),
            motif_spec=spec, colors={"body": "#B4A390", "cap": "#FAF3EC"}, concept_front=plan)
        assert ("motif-field" in {n.name for n, _ in doc.walk()}) is drawn



def test_a_finish_lands_on_the_product_and_never_on_the_sheets_depiction_panels():
    """§BH65(c)10 — found by task 89's REAL run at (c)9: on a compact the sheet also draws a "LID TOP" strip panel, a
    depiction of the surface at sheet scale, with the motif's continuation in it; the foil clause "on petal outlines"
    found two outline sparkles THERE and a foil plate was cut from them. A plate is for the product: on task 89's lid
    no motif prints, so the clause is NOT_DRAWN, and no plate is cut from the sheet."""
    from apps.ire import container_finishes as F
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    concept = dict(_PETAL_WINDOW_FULL, finish_signature="rose-gold hot-stamp foil on petal outlines")
    spec = cm.build_motif_spec(concept, {}, _LID_ZONE, {})
    doc = compose_container_graph(
        build_backbone(ContainerProfile(archetype="compact", height_mm=95, width_mm=110)),
        product_name="Focus", sku="S", native=True, zones=_LID_ZONE, logo_path="media/brand/logo.png",
        hierarchy_lines=ruled_front_hierarchy("Focus", descriptor="pressed powder compact"),
        motif_spec=spec, colors={"body": "#B4A390", "cap": "#FAF3EC"})
    strip = [n for n, _ in doc.walk() if (n.name or "") == "motif-LID_TOP"]
    assert strip, "the sheet draws the LID TOP depiction panel with the motif in it"
    rows = F.apply(doc, spec["finish_assignments"], brand_metallic_hex="#C9A24B")["applied"]
    assert [(r["finish"], r["target"], r["state"]) for r in rows] == [("foil", "motif", F.NOT_DRAWN)]
    assert not [n for n, _ in doc.walk() if getattr(n, "finishes", None)]



# ---------------------------------------------------------------------------------------------------------------
# §BH66(a) — ON A FACE THE CONCEPT'S OWN ARRANGEMENT GOVERNS. OWNER RULED 2026-09-23 (OWNER_BLOCKER_CLEARANCE.md:23254,
# LIVE): "§AU1 governs bottle, jar and tube fronts as it always has. It does NOT govern a compact lid ... On such a
# surface the concept's own arrangement governs, inside two limits that stand: the mark's clear space on every side
# (§AY2), and no motif field as a ground behind the mark (§BA / C12). Draw the window, the ring, the Arabic line and
# their finishes where the concept puts them, and refuse by name only what those two limits actually forbid."
# ---------------------------------------------------------------------------------------------------------------

#: every face-form concept on record — tasks 84, 88 and 89, three variations each — as their structured records read
#: (dev database, read-only, 2026-09-24): the words the reader was measured against before it was written
_FACE_CONCEPTS = {
    '84_A_PETAL_WINDOW': {
        'composition_signature': 'Vertically stacked three-zone lid: BBROSE lockup anchored top-left / display type block upper-centre / bounded petal-window lower-centre / Arabic name below window; strict bilateral symmetry on the centre axis',
        'typography_signature': "High-contrast didone display serif for 'ROSE GLOW' (tracking −10, full lid width) + small-caps 'PALETTE' at 30% scale + centred Naskh bilingual at 60% cap height; all live type, Deep Rose fill, Warm Cream on ground",
        'decoration_zone_signature': 'Centred front-panel window strategy: all decorative motif energy contained inside a rose-gold hairline oval Bézier frame; typography occupies the zone above and below the window, never overlapping it',
        'motif_signature': 'Seven to nine closed Bézier petal-droplet forms clustered in a near-oval window frame, each filled with a blush-to-cream radial gradient at 65% opacity, arranged as an organic overlapping bloom',
        'finish_signature': 'High-gloss acrylic clear-coat over full lid face; rose-gold hot-foil on BBROSE lockup and oval hairline border; spot-UV gloss mask aligned to each petal Bézier path; matte laminate on compact body',
        'color_field_signature': 'Single matte blush ground (#F2C4CE) across full lid face; Pale Petal-to-Warm Cream radial gradient fills inside the petal window only; Deep Rose type block as the darkest value element',
    },
    '84_B_LIQUID_VEIL': {
        'composition_signature': 'Asymmetric vertical-spine layout: veil as full-height central motif; product name as left-edge vertical type spine; category word at lower centre; brand lockup at bottom-right; Arabic name floating in upper quarter above the veil density',
        'typography_signature': "Light italic didone 'ROSE GLOW' rotated 90° along left edge (vertical spine) + widely tracked uppercase Warm Gold sans 'PALETTE' at lower centre + centred Naskh bilingual in upper quarter; all live type, materially different hierarchy from A",
        'decoration_zone_signature': 'Full-bleed veil motif strategy with no hard frame: gradient veil occupies entire lid face as ambient field; type elements occupy edge zones (left spine, lower centre, upper horizontal band), keeping the veil centre clear',
        'motif_signature': 'Two overlapping tall vertical vector gradient-mesh veil ribbons, soft-feathered Bézier edges dissolving into the ivory ground, billowing rightward in the lower third, Pale Petal through Warm Cream through blush at 40–75% layered opacity',
        'finish_signature': 'Satin-gloss lid face coating; soft-touch matte laminate on compact body; rose-gold hot-foil on BBROSE lockup at bottom-right and on hinge-line stripe; no spot-UV on this variation — gloss is ambient from the satin coat, not localised',
        'color_field_signature': 'Ivory (#FAF3EC) full-bleed ground; overlapping gradient veil in Pale Petal/Warm Cream/blush at layered opacities reads as a warm translucent column; Deep Rose type spine as accent; Warm Gold type as second accent',
    },
    '84_C_DEWDROP_CONSTELLATION': {
        'composition_signature': 'Asymmetric edge-led diagonal layout: dewdrop constellation anchored lower-left sweeping to upper-right; open negative space on the right half hosts the flush-right type block; brand lockup crowns top-centre; composition has no enclosing frame or central axis symmetry',
        'typography_signature': "Large uppercase didone 'ROSE GLOW' in Warm Cream flush-right / italic serif 'PALETTE' at 25% scale flush-right beneath / BBROSE lockup top-centre / Arabic Naskh as small supporting footnote flush-right at base; all live type, right-edge editorial hierarchy distinct from A and B",
        'decoration_zone_signature': 'Asymmetric edge-led strategy: no centred window, no full-bleed field; constellation occupies lower-left-to-upper-right diagonal zone; right-side negative space is deliberately reserved for the editorial type block; open ground shows throughout the upper-left quadrant',
        'motif_signature': 'Sparse-to-dense dewdrop constellation of closed teardrop Bézier paths, progressing from three to four large drops at lower-left to small isolated drops at upper-right, each filled with a near-white-to-Pale Petal radial gradient simulating a glass bead of rose water',
        'finish_signature': 'Peach-glass lacquer on full compact lid and body; spot-UV localised to the large lower-left dewdrops only (liquid specular gleam on those forms); rose-gold hot-foil on BBROSE lockup and base-edge band; no spot-UV on type; matte-satin on body sides',
        'color_field_signature': 'Warm peach-glass lacquer ground (pale rose-amber, semi-transparent character); near-white/Pale Petal/Warm Cream gradient fills inside each droplet; Warm Cream type; Deep Rose Arabic footnote; rose-gold foil base band as warm metallic accent',
    },
    '88_A_PETAL_WINDOW': {
        'composition_signature': 'Centred front decoration window flanked vertically by bilingual name tiers above and below; BBROSE seal anchors base; type sits outside the window boundary, never over it',
        'typography_signature': "High-contrast hairline serif 'Rose Glow' (blush, headline scale, left-aligned above window) + matching-optical-scale high-contrast Naskh 'توهج الورد' (Deep Rose, left-aligned below window) + small tracked geometric sans 'Palette / باليت' beneath each tier; BBROSE foil seal bottom-center, last in hierarchy",
        'decoration_zone_signature': 'Bounded centred window strategy: all motif energy contained within a rose-gold hairline-framed rectangular zone; typography occupies the zones above and below the window on open cream ground',
        'motif_signature': 'Seven to nine closed Bézier petal-droplet vector forms in warm-gold at 65% opacity, radially clustered inside the hairline rose-gold window frame, spot-UV outline on each petal edge',
        'finish_signature': 'Satin laminate lid ground; spot-UV on petal-droplet outlines inside window for glass-gloss ridge effect; rose-gold hot-foil on window frame hairline rule, BBROSE seal, and cap pinstripe; pearl-white gloss on compact body',
        'color_field_signature': 'Warm Cream (#FAF3EC) ground full lid; Blush (#F2C4CE) type field above; Deep Rose (#8B3A52) type field below; Warm Gold (#CBA87D) petal fill inside window; rose-gold metallic accents at border and seal',
    },
    '88_B_LIQUID_VEIL': {
        'composition_signature': 'Vertical asymmetric split: flowing veil occupies centre-left vertical band; typography occupies right-column zone beside veil; BBROSE at top-right, product names mid-right, category copy lower-right — top-to-bottom reading order down one side',
        'typography_signature': "BBROSE wordmark as brand header at upper-right lid (rose-gold foil, mid-scale, first in hierarchy); 'Rose Glow' hairline serif + 'توهج الورد' Naskh stacked right-column (Deep Rose + Warm Gold, medium editorial scale); 'Palette / باليت' tracked sans base of column; hierarchy inverts from A",
        'decoration_zone_signature': 'Full-height vertical band strategy: veil runs nearly edge-to-edge in height, anchored centre-left; type column occupies the breathing zone to the right of the veil boundary — no enclosed window frame',
        'motif_signature': 'Single continuous compound-Bézier nectar-veil form, Warm Gold at 55% opacity, undulating silhouette narrowing at mid-point, with centre-axis spot-UV gloss stripe suggesting poured liquid',
        'finish_signature': 'Gloss laminate full body for gradient luminosity; spot-UV vertical stripe along veil central axis for liquid-specular effect; rose-gold hot-foil on BBROSE wordmark, horizontal rule, cap-body seam band; satin-matte surround zones flanking the veil',
        'color_field_signature': 'Ivory-to-blush vertical vector gradient body (#FAF3EC → #F2C4CE); Warm Gold veil fill (#CBA87D 55% opacity) centre-left band; Deep Rose and Warm Gold type in right column; deep rose-plum cap as tonal cap of the gradient',
    },
    '88_C_DEWDROP_CONSTELLATION': {
        'composition_signature': 'Strong diagonal tension: constellation dense at lower-left corner, dissipating toward upper-right; type column occupies upper-right open sky zone; asymmetric edge-led composition, no centring anywhere on the lid face',
        'typography_signature': "Arabic 'توهج الورد' high-contrast Naskh as headline (Deep Rose, large, first name in reading order — inverted from A and B); 'Rose Glow' hairline serif beneath (blush, slightly smaller); BBROSE wordmark horizon mark top-right (rose-gold foil, small, wide-tracked); 'باليت / Palette' tracked sans base; all type right-aligned",
        'decoration_zone_signature': 'Asymmetric edge-led constellation strategy: motif energy originates at lower-left corner and radiates diagonally; type occupies the opposing upper-right zone; no enclosed window, no vertical band — the decoration zone is the entire lid surface read as a diagonal field',
        'motif_signature': 'Twelve to twenty-two closed elliptical Bézier dewdrop forms in sparse-to-dense constellation from lower-left, near-transparent blush fill with rose-gold hairline strokes, spot-UV gloss dome caps on three densest droplets, density decreasing toward upper-right until isolated hairline ellipses',
        'finish_signature': 'Iridescent pearl gloss laminate on compact body for transparent-glass suggestion; spot-UV dome caps on three key dewdrop ellipses for liquid-meniscus glimmer; rose-gold hot-foil on BBROSE wordmark, droplet hairline strokes, and single name-separator rule; matte finish on cap — no foil on cap',
        'color_field_signature': 'Pale warm peach ground (#FDE8DC) with rose-darkened lower-left radial vignette; blush dewdrop fills (#F2C4CE 30–50% opacity); Deep Rose Arabic headline (#8B3A52); blush English name (#F2C4CE); rose-gold hairline strokes on droplets; matte deep rose cap; iridescent pearl-peach body',
    },
    '89_A_PETAL_WINDOW': {
        'composition_signature': 'Vertically centred cartouche window on lid face, with product names anchored above and below the window in open cream ground; BBROSE wordmark below centre; circular rule ring frames the entire lid',
        'typography_signature': 'Tall classical serif wide-tracked small caps (EN) + matching-weight calligraphic Arabic (AR), both in Deep Rose, stacked above and below the petal window; BBROSE wordmark in rose-gold foil below the window; claims in geometric sans-serif bilingual pairs on side band',
        'decoration_zone_signature': 'Centred cartouche window concentrates all motif energy; typography occupies the open cream zones above and below the window, never overlapping motif',
        'motif_signature': 'Seven closed Bézier petal-droplets in a loose radial cluster inside the cartouche window, alternating filled blush and rose-gold outline forms, suggesting a pressed bloom without literal florality',
        'finish_signature': 'Matte soft-touch laminate ground; rose-gold hot-stamp foil on petal outlines, window rule, circumference rule ring and BBROSE wordmark; spot gloss UV over the cartouche interior; gloss lacquer on side band',
        'color_field_signature': 'Warm Cream #FAF3EC ground across the full lid face; radial gradient within the window from cream centre to pale petal blush edge; Deep Rose type; rose-gold foil accents',
    },
    '89_B_LIQUID_VEIL': {
        'composition_signature': 'Full-face vertical veil strands flow freely from upper-centre to lid perimeter; wordmark pins the top; bilingual product names anchor the lower third; no contained window or cartouche',
        'typography_signature': 'BBROSE wordmark in rose-gold foil at top rim (anchor); stacked bilingual pair AR-above-EN in tall classical serif / calligraphic Arabic (Deep Rose) in lower third of lid — hierarchy and placement materially distinct from A',
        'decoration_zone_signature': 'Full-face open-field strategy — veil strands fill the entire lid face without a contained zone; typography claims the top rim and lower third as distinct anchored bands within the open field',
        'motif_signature': 'Six-to-eight sinuous closed Bézier nectar-filament veil strands in a vertical waterfall, fanning outward, grading from blush-fill at centre to rose-gold hairline outlines at outer edge',
        'finish_signature': 'Matte soft-touch laminate ground; rose-gold hot-stamp foil on outer veil strands, BBROSE wordmark and rim rule; spot gloss UV on inner two veil strands creating wet dimensionality; gloss lacquer on side band; gloss acrylic body',
        'color_field_signature': 'Vertical vector gradient from Warm Cream #FAF3EC at top to pale blush rose #F2D5DC at base, filling the entire lid; Deep Rose for type; rose-gold foil for outer veil strands and wordmark',
    },
    '89_C_DEWDROP_CONSTELLATION': {
        'composition_signature': 'Asymmetric edge-led constellation originating from lower-left, radiating toward upper-right; typography occupies upper third horizontally and right edge vertically; no centred zone, no contained frame — fully open asymmetric field',
        'typography_signature': 'FOCUS in tall classical serif tracked extremely wide across upper third (editorial scale); Arabic product name rotated 90° along right rim edge (separate graphic voice); BBROSE wordmark flush upper-left as a small seal — three-way hierarchy distinct from A and B',
        'decoration_zone_signature': 'Asymmetric edge-led field strategy — motif density anchors the lower-left quadrant and dissolves toward upper-right; typography claims the upper horizontal band and the right vertical edge as separate autonomous zones; no centred decoration window',
        'motif_signature': 'Sparse-to-dense dewdrop constellation of closed Bézier teardrop and sphere paths, grading from dense spot-UV domes at lower-left through rose-gold outlined mid-zone to solid rose-gold foil isolated droplets at upper-right',
        'finish_signature': 'Matte soft-touch laminate on peach-rose lid ground; spot gloss UV on dense inner dewdrop cluster; rose-gold hot-stamp foil on mid-zone droplet outlines, outer solid droplets and BBROSE wordmark; no spot UV centre clearing; no foil rule ring — finish is motif-concentrated, not perimeter-framed',
        'color_field_signature': 'Flat peach-rose #F4C5B2 matte ground across full lid face; Deep Rose #8B3A52 for EN product name; rose-gold foil for wordmark, outlined droplets and solid outer droplets; spot gloss UV for inner droplet cluster; blush-tinted rules on side band',
    },
}

#: what the reader takes from each: the mark, the name and the Arabic line as (slot, side), and where the motif sits
_FACE_READINGS = {
    "84_A_PETAL_WINDOW": (("top", "left"), ("upper", "centre"), ("below_window", "centre"), "window"),
    "84_B_LIQUID_VEIL": (("bottom", "right"), ("middle", "left"), ("top", "centre"), "full"),
    "84_C_DEWDROP_CONSTELLATION": (("top", "centre"), ("upper", "right"), ("bottom", "right"), "corner_lower_left"),
    "88_A_PETAL_WINDOW": (("bottom", "centre"), ("above_window", "left"), ("below_window", "left"), "window"),
    "88_B_LIQUID_VEIL": (("top", "right"), ("middle", "right"), ("middle", "right"), "band_left"),
    "88_C_DEWDROP_CONSTELLATION": (("top", "right"), ("upper", "right"), ("upper", "right"), "corner_lower_left"),
    "89_A_PETAL_WINDOW": (("below_window", "centre"), ("above_window", "centre"), ("above_window", "centre"),
                          "window"),
    "89_B_LIQUID_VEIL": (("top", "centre"), ("lower", "centre"), ("lower", "centre"), "full"),
    "89_C_DEWDROP_CONSTELLATION": (("upper", "left"), ("top", "centre"), ("middle", "right"), "corner_lower_left"),
}
_FACE_NAMES = {"84": ("Rose Glow Palette", "باليت روز جلو"), "88": ("Rose Glow Palette", "باليت روز جلو"),
               "89": ("Focus Pressed Powder", "فوكس بودرة مضغوطة")}


def _face(key, zones=_LID_ZONE):
    """A face run exactly as the pipeline hands it to the composer: the §BH65(c)3 plan, the reading of the concept's
    own words, the lid's declared surface and the product's Arabic name as held."""
    from apps.ire import concept_face as CFA
    from apps.ire import concept_front as CF
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    concept = dict(_FACE_CONCEPTS[key], verified=True, variation_id=key.split("_", 1)[1], title=key)
    name, name_ar = _FACE_NAMES[key[:2]]
    spec = cm.build_motif_spec(concept, {}, zones, {})
    plan = CF.plan(concept, spec, ground_hex="#FAF3EC", edge_hex="#F7DDE3")
    plan["face"] = dict(CFA.read(concept, layout=plan["layout"], has_arabic=True, product_name=name),
                        surface="LID_TOP", name_ar=name_ar)
    doc = compose_container_graph(
        build_backbone(ContainerProfile(archetype="compact", height_mm=95, width_mm=110)),
        product_name=name, sku="S", native=True, zones=zones, logo_path="media/brand/logo.png",
        hierarchy_lines=ruled_front_hierarchy(name, descriptor="pressed powder compact"),
        motif_spec=spec, colors={"body": "#B4A390", "cap": "#FAF3EC"}, concept_front=plan)
    return doc, spec, concept


def _box(node):
    from apps.ire.compose_container import _leaf_box
    return _leaf_box(node)


@pytest.mark.parametrize("key", sorted(_FACE_CONCEPTS))
def test_the_face_reader_reads_every_face_concept_on_record_as_its_words_say(key):
    """The reader was MEASURED against these nine before it was written, and each answer is the concept's own words:
    84A "BBROSE lockup anchored top-left / display type block upper-centre / ... / Arabic name below window"; 88A
    "left-aligned above window" and "left-aligned below window"; 89A's pair "stacked above and below the petal window"
    stays together above it (the arrangement he saw drawn and ruled on); 89C's Arabic "rotated 90° along right rim
    edge" is set level at the right, and says so."""
    from apps.ire import concept_face as CFA
    from apps.ire import concept_front as CF
    concept = dict(_FACE_CONCEPTS[key], verified=True)
    plan = CF.plan(concept, {"reconstruction_capability": "SUPPORTED"}, ground_hex="#FAF3EC", edge_hex=None)
    reading = CFA.read(concept, layout=plan["layout"], has_arabic=True, product_name=_FACE_NAMES[key[:2]][0])
    els = reading["elements"]
    got = tuple((els[k]["slot"], els[k]["align"]) for k in (CFA.MARK, CFA.NAME, CFA.NAME_AR))
    mark, name, name_ar, region = _FACE_READINGS[key]
    assert got == (mark, name, name_ar), (key, got, {k: v["why"] for k, v in els.items()})
    assert reading["region"]["kind"] == region
    turned = {a["element"] for a in reading["approximated"]}
    assert turned == {"84_B_LIQUID_VEIL": {CFA.NAME}, "89_C_DEWDROP_CONSTELLATION": {CFA.NAME_AR}}.get(key, set())


_T91_TYPOGRAPHY = ("High-contrast old-style Latin serif ('Focus') over matching Naskh ('فوكس'), identical cap-height, "
                   "tracked evenly, set above the petal window in Deep Rose; BBROSE wordmark in rose-gold hot-foil at "
                   "the crown arc")


def test_bh67b2_the_display_wordmark_is_the_records_own_leading_phrase_and_nothing_else():
    """§BH67(b)2: "THE DISPLAY WORDMARK IS LOST … Find where it drops." Task 91's concept sets 'Focus' over 'فوكس' —
    the leading word of each of the record's names — and the lid printed the whole record name. The display name is
    taken ONLY as the record's own words; an invented one is refused by name; a concept that quotes none prints the
    record's name as it always has."""
    from apps.ire import display_name as DN
    r = DN.read({"typography_signature": _T91_TYPOGRAPHY}, product_name="Focus Pressed Powder",
                product_name_ar="فوكس بودرة مضغوطة")
    assert (r["name"]["source"], r["name"]["text"]) == (DN.DISPLAY, "Focus")
    assert (r["name_ar"]["source"], r["name_ar"]["text"]) == (DN.DISPLAY, "فوكس")
    assert [(o["element"], o["text"]) for o in r["off_the_face"]] == [("name", "Pressed Powder"),
                                                                      ("name_ar", "بودرة مضغوطة")]
    invented = DN.read({"typography_signature": "display name 'Lumière' in serif"}, product_name="Focus Pressed Powder")
    assert invented["name"] == {"source": DN.RECORD_NAME, "text": "Focus Pressed Powder"}
    assert [x["code"] for x in invented["refused"]] == [DN.NOT_THE_RECORDS_WORDS]
    quiet = DN.read({"typography_signature": "Tall classical serif wide-tracked small caps (EN)"},
                    product_name="Focus Pressed Powder")
    assert quiet["name"]["source"] == DN.RECORD_NAME and quiet["quoted"] == [] and quiet["refused"] == []


def test_bh67b2_a_concept_that_sets_more_of_the_name_keeps_it_whole_and_its_own_words_are_never_refused():
    """The trim is taken only when the concept sets the leading phrase ALONE. A concept that sets the rest of the name
    too — quoted after the display name, quoted before it, or in its plain words — keeps the record's name whole and
    says why, so the face never drops a line its concept sets; a quoted later part of the record's name is the
    record's own words and is not refused; words that are not the record's are; and a display name the concept sets in
    other letter case prints in the record's spelling, noted where it drops."""
    from apps.ire import display_name as DN
    name, name_ar = "Focus Pressed Powder", "فوكس بودرة مضغوطة"
    for words in ("'Focus' in serif over 'Pressed Powder' in small caps",
                  "'Pressed Powder' in small caps under 'Focus'",
                  "'Focus' with PRESSED POWDER beneath in small caps",
                  "'Focus' and 'Focus Pressed' stacked"):
        r = DN.read({"typography_signature": words}, product_name=name, product_name_ar=name_ar)
        assert (r["name"]["source"], r["name"]["text"]) == (DN.RECORD_NAME, name), words
        assert "nothing is trimmed" in r["name"]["why"] and r["off_the_face"] == [] and r["refused"] == [], words
    part = DN.read({"typography_signature": "'Pressed Powder' in small caps"}, product_name=name)
    assert (part["name"]["source"], part["refused"]) == (DN.RECORD_NAME, [])
    face = DN.read({"typography_signature": "'Focus' set in 'Playfair Display'"}, product_name=name)
    assert face["name"]["text"] == "Focus" and [x["quoted"] for x in face["refused"]] == ["Playfair Display"]
    caps = DN.read({"typography_signature": "'FOCUS' in wide capitals"}, product_name=name)
    assert (caps["name"]["text"], caps["name"]["case"]["concept"]) == ("Focus", "FOCUS")
    text = DN.drops(caps, typeface=None, name_size_pt=9.0, drawn_face="Poppins-Light")[0]
    assert text["state"] == "CONCEPT" and "letter case" in text["why"]


def test_bh67b2_the_face_prints_the_display_wordmark_and_says_where_the_rest_drops():
    """Through the composer: the name and the Arabic line print the concept's display name; the record's remainder is
    on the face record, off the face; and ``drops`` names the three attributes — text settled by the record, face the
    role layer's (the concept names a style), size the tier's, waiting on §Z1(b)."""
    from apps.ire import concept_face as CFA
    from apps.ire import concept_front as CF
    from apps.ire import display_name as DN
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    concept = dict(_FACE_CONCEPTS["89_A_PETAL_WINDOW"], verified=True, typography_signature=_T91_TYPOGRAPHY)
    spec = cm.build_motif_spec(concept, {}, _LID_ZONE, {})
    plan = CF.plan(concept, spec, ground_hex="#FAF3EC", edge_hex="#F7DDE3")
    plan["face"] = dict(CFA.read(concept, layout=plan["layout"], has_arabic=True, product_name="Focus Pressed Powder"),
                        surface="LID_TOP", name_ar="فوكس بودرة مضغوطة")
    plan["face"]["display_name"] = DN.read(concept, product_name="Focus Pressed Powder",
                                           product_name_ar="فوكس بودرة مضغوطة")
    doc = compose_container_graph(
        build_backbone(ContainerProfile(archetype="compact", height_mm=95, width_mm=110)),
        product_name="Focus Pressed Powder", sku="S", native=True, zones=_LID_ZONE, logo_path="media/brand/logo.png",
        hierarchy_lines=ruled_front_hierarchy("Focus Pressed Powder", descriptor="pressed powder compact"),
        motif_spec=spec, colors={"body": "#B4A390", "cap": "#FAF3EC"}, concept_front=plan)
    texts = {n.name: n.text for n, _ in doc.walk() if (n.name or "").startswith("product-name")}
    assert texts == {"product-name-hero": "Focus", "product-name-ar": "فوكس"}
    face = doc.metadata["concept_front"]["face"]
    assert [o["text"] for o in face["display_name"]["off_the_face"]] == ["Pressed Powder", "بودرة مضغوطة"]
    drops = {d["attribute"]: d["state"] for d in DN.drops(plan["face"]["display_name"], typeface=None,
                                                             name_size_pt=9.0, drawn_face="Poppins-Light")}
    assert drops == {"text": "CONCEPT", "face": "ROLE_LAYER", "size": "TIER_SIZE"}


#: §BH67(d)1's own read of task 91's approved concept (GeneratedImage 135) — claude-opus-4-7 on the pixel grid,
#: 2026-09-24, $0.094905 on task 91's ledger; its boxes as fractions of the surface, verbatim; the words it saw came
#: back under `text` at prompt 2 and are held here under `seen_text`, prompt 3's key; the fixture every (d)2 test draws
#: from
_T91_VISION = {
    "schema_version": "container_concept_layout/1.0", "state": "READ", "surface": "LID_TOP",
    "surface_box": [140.0, 385.0, 950.0, 1180.0], "surface_shape": "round",
    "elements": [
        {"kind": "mark", "box": [0.3593, 0.0553, 0.5926, 0.1006], "align": "centre", "seen_text": "BBROSE"},
        {"kind": "name", "box": [0.3605, 0.1585, 0.6049, 0.2377], "align": "centre", "seen_text": "Focus"},
        {"kind": "name_ar", "box": [0.4136, 0.2516, 0.5802, 0.2906], "align": "centre", "seen_text": "فوكس"},
        {"kind": "window", "box": [0.3457, 0.3585, 0.6975, 0.7547], "align": "centre", "shape": "oval"},
        {"kind": "motif", "box": [0.3889, 0.3962, 0.6605, 0.7296], "align": "centre"},
        {"kind": "other_text", "box": [0.4259, 0.8742, 0.6728, 0.9094], "align": "centre",
         "seen_text": "03 Medium Beige"},
        {"kind": "finish", "box": [0.0, 0.0, 1.0, 1.0], "align": "centre", "shape": "round"}],
    "unread": []}
#: the lid face since §BH67(c)3: the whole plan less the 6.0 mm hinge band, on the 110 x 95 case
_WHOLE_LID = [dict(_LID_ZONE[0], x=0.0, y=6.0, width=110.0, height=89.0)]


def _t91_face(vision):
    from apps.ire import concept_face as CFA
    from apps.ire import concept_front as CF
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    concept = dict(_FACE_CONCEPTS["89_A_PETAL_WINDOW"], verified=True, typography_signature=_T91_TYPOGRAPHY)
    spec = cm.build_motif_spec(concept, {}, _WHOLE_LID, {})
    plan = CF.plan(concept, spec, ground_hex="#FAF3EC", edge_hex="#F7DDE3")
    plan["face"] = dict(CFA.read(concept, layout=plan["layout"], has_arabic=True, product_name="Focus Pressed Powder"),
                        surface="LID_TOP", name_ar="فوكس بودرة مضغوطة", vision_layout=vision)
    doc = compose_container_graph(
        build_backbone(ContainerProfile(archetype="compact", height_mm=95, width_mm=110)),
        product_name="Focus Pressed Powder", sku="S", native=True, zones=_WHOLE_LID, logo_path="media/brand/logo.png",
        hierarchy_lines=ruled_front_hierarchy("Focus Pressed Powder", descriptor="pressed powder compact"),
        motif_spec=spec, colors={"body": "#B4A390", "cap": "#FAF3EC"}, concept_front=plan)
    return doc


def test_bh68b_the_lid_name_is_the_largest_step_of_the_scale_the_lid_holds_for_the_concepts_layout(monkeypatch):
    """§BH68(b), OWNER RULED 2026-09-24: "the size is a step on the typographic scale, and the step chosen is the
    largest one the lid's own zone holds for the concept's layout. No computed sizes, and no bottle size on a lid."
    Task 91's lid, drawn from its own concept's read: every step from 72 pt down is tried; 18 pt squeezes the concept's
    window and 21 pt and above cannot place it; 16 pt holds — the name and the Arabic line both 16 pt, steps of the
    scale, nothing colliding, nothing unplaced, the window at the concept's height, moved the least distance and
    recorded. Unread, the words' layout holds 10 pt: from 11 pt the window narrows from its designed width. And the lid
    never reads the bottle front's tier: move it, and the lid's step does not."""
    from apps.ire import compose_container as CC
    doc = _t91_face(_T91_VISION)
    face = doc.metadata["concept_front"]["face"]
    step = face["name_size"]
    runs = [n for n, _ in doc.walk() if (n.name or "").startswith("product-name-hero")]
    ar = [n for n, _ in doc.walk() if (n.name or "") == "product-name-ar"]
    assert step["step_pt"] == 16.0 and [r.size_pt for r in runs] == [16.0]
    assert ar[0].size_pt == step["ar_step_pt"] == 16.0
    assert {step["step_pt"], step["ar_step_pt"]} <= set(CC.TYPE_SCALE_PT)
    refused = {r["step_pt"]: r["why"] for r in step["larger_steps_refused"]}
    assert sorted(refused) == [18.0, 21.0, 24.0, 36.0, 48.0, 60.0, 72.0]
    assert any("squeezed" in w for w in refused[18.0])
    assert any("window cannot be placed" in w for w in refused[21.0])
    assert face["collisions"] == [] and face["not_placed"] == [] and step["at_every_step"] == []
    plain = _t91_face(None).metadata["concept_front"]["face"]["name_size"]
    assert plain["step_pt"] == 10.0
    assert any("narrows" in w for w in {r["step_pt"]: r["why"] for r in plain["larger_steps_refused"]}[11.0])
    monkeypatch.setattr(CC, "HERO_NAME_PT", 99.0)
    assert _t91_face(_T91_VISION).metadata["concept_front"]["face"]["name_size"]["step_pt"] == 16.0


def test_bh68b_the_display_wordmark_drops_at_its_scale_step():
    """The drop record's SIZE attribute says the step the face drew and why, larger steps refused by name — no longer
    "waits on §Z1(b)"; a caller that hands in no step record keeps the tier's state."""
    from apps.ire import display_name as DN
    step = _t91_face(_T91_VISION).metadata["concept_front"]["face"]["name_size"]
    size = DN.drops({}, typeface=None, name_size_pt=step["step_pt"], drawn_face="Poppins-Light", name_size=step)[2]
    assert (size["attribute"], size["state"], size["drawn"]) == ("size", "SCALE_STEP", 16.0)
    assert "18 pt — the window is squeezed" in size["why"] and "§BH68(b)" in size["why"]
    assert DN.drops({}, typeface=None, name_size_pt=9.0, drawn_face=None)[2]["state"] == "TIER_SIZE"


#: §BH68(f)'s own concept — task 110, GeneratedImage 138, variation A_RADIANT_AXIS "Radiant Axis" — its structured fields
#: verbatim, and the vision read the run recorded for it (claude-opus-4-7, on task 110's ledger): the windowless face
#: that showed (b) had no containment check
_T110_CONCEPT = {
    "composition_signature": "Strict vertical axis: BBROSE band / bilingual title block / radial veil atmosphere / claims band — all elements centred on the lid's vertical centre line, reading top-to-bottom with clear zone boundaries",
    "typography_signature": "Didone high-contrast serif (English 'Focus') over geometric Arabic serif ('فوكس') at matched cap-height and visual weight, centred bilingual title block; BBROSE wordmark in Rose Gold foil at top; claims in small-caps geometric sans at base — full live-type hierarchy, nothing outlined",
    "decoration_zone_signature": "Lid face carries the complete typographic and atmospheric composition; side band is a single-line secondary information strip; base underside is a minimal regulatory label — decoration is lid-face-dominant, sides subordinate",
    "color_field_signature": "Single warm cream (#FAF3EC) full-face ground; Deep Rose (#8B3A52) for all name type and rim rule; Blush (#F2C4CE) particle field lines; Rose Gold hot-foil on BBROSE lockup and hairline rule — four named colour roles, no gradients on the ground field",
    "motif_signature": "Radial particle veil: fine Bézier stroked lines emanating from a single centre point behind the type, each ending in a small filled circular node, all in Blush #F2C4CE at reduced opacity, density tapering toward the rim",
    "finish_signature": "Matte soft-touch laminate over entire lid face; spot-UV gloss mask precisely matching the 'Focus / فوكس' letterform paths for gloss-on-matte relief; Rose Gold hot-foil mask on BBROSE wordmark and hairline rule — three distinct finish layers, each on its own named vector mask",
    "title": "Radiant Axis"
}
_T110_VISION = {"schema_version": "container_concept_layout/1.0", "state": "READ", "surface": "LID_TOP", "surface_box": [116.0, 315.0, 895.0, 1160.0], "surface_shape": "round", "elements": [{"box": [0.3081, 0.0828, 0.6547, 0.1538], "kind": "mark", "align": "centre", "finish": "rose-gold foil", "seen_text": "BBROSE", "confidence": 0.94}, {"box": [0.2811, 0.3018, 0.7047, 0.5089], "kind": "name", "align": "centre", "finish": "gloss", "seen_text": "Focus", "confidence": 0.96}, {"box": [0.294, 0.529, 0.6598, 0.5408], "kind": "rule", "align": "centre", "finish": "rose-gold foil", "confidence": 0.8}, {"box": [0.2811, 0.574, 0.6919, 0.7101], "kind": "name_ar", "align": "centre", "finish": "gloss", "seen_text": "فوكس", "confidence": 0.9}, {"box": [0.0822, 0.1006, 0.9166, 0.9053], "kind": "motif", "align": "centre", "finish": "matte", "confidence": 0.85}, {"box": [0.2811, 0.8876, 0.6085, 0.9231], "kind": "descriptor", "align": "centre", "finish": "none", "seen_text": "02 BEIGE | PRESSED POWDER", "confidence": 0.9}, {"box": [0.018, 0.0059, 0.9936, 0.9882], "kind": "ring", "align": "centre", "shape": "round", "finish": "none", "confidence": 0.88}], "unread": []}


def _face_of(concept, vision, colors=None):
    # [the owner's second answer of 2026-09-25: ``colors`` — the colours the run sources and hands the composer, so a
    # test can draw the face's own lines in the colour its record names; unchanged when none is handed in]
    from apps.ire import concept_face as CFA
    from apps.ire import concept_front as CF
    from apps.ire import display_name as DN
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    concept = dict(concept, verified=True)
    spec = cm.build_motif_spec(concept, {}, _WHOLE_LID, {})
    plan = CF.plan(concept, spec, ground_hex="#FAF3EC", edge_hex="#F7DDE3")
    plan["face"] = dict(CFA.read(concept, layout=plan["layout"], has_arabic=True, product_name="Focus Pressed Powder"),
                        surface="LID_TOP", name_ar="فوكس بودرة مضغوطة", vision_layout=vision)
    plan["face"]["display_name"] = DN.read(concept, product_name="Focus Pressed Powder",
                                           product_name_ar="فوكس بودرة مضغوطة")
    return compose_container_graph(
        build_backbone(ContainerProfile(archetype="compact", height_mm=95, width_mm=110)),
        product_name="Focus Pressed Powder", sku="S", native=True, zones=_WHOLE_LID, logo_path="media/brand/logo.png",
        hierarchy_lines=ruled_front_hierarchy("Focus Pressed Powder", descriptor=None),
        motif_spec=spec, colors=colors if colors is not None else {"body": "#B4A390", "cap": "#FAF3EC"},
        concept_front=plan)


def test_bh68b2_a_step_that_pushes_an_element_off_the_lid_is_not_one_the_lid_holds():
    """§BH68(b)2, found by (f): task 110's concept has no window, so nothing in (b)'s test stopped the name; at 72 pt the
    follow pass, left no room, pushed the BBROSE mark above the lid face — and nothing collided, so nothing refused the
    step. Every element must stay inside its region: the steps that push the mark out are refused by name, and the one
    drawn keeps every element inside the lid."""
    face = _face_of(_T110_CONCEPT, _T110_VISION).metadata["concept_front"]["face"]
    step = face["name_size"]
    refused = {r["step_pt"]: r["why"] for r in step["larger_steps_refused"]}
    # [the owner's second answer of 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block headed "Before I start testing"):
    # "The lid is missing the concept's rule, ring and radial lines." Task 110's rim rule is drawn now, and the type keeps
    # its one-em GAP inside it — concept_face's GAP, not softened to win a step back. With no ring this lid held 48 pt,
    # 60 and 72 refused because the mark left its region; with the ring 36 pt is the largest step it holds: 48 is
    # refused because the mark and the name leave their regions (10.89 and 6.25 mm), 60 and 72 for the text width too.]
    assert step["step_pt"] == 36.0 and sorted(refused) == [48.0, 60.0, 72.0]
    assert refused[48.0] == ["the mark leaves its region by 10.89 mm", "the name leaves its region by 6.25 mm"]
    assert any("the mark leaves its region" in w for w in refused[60.0])
    assert all(any("past the" in w for w in refused[s]) for s in (60.0, 72.0))
    mx, my, mw, mh = face["placed"]["mark"]["clear_box"]
    rx, ry, rw, rh = face["regions"]["mark"]
    assert ry - 1e-3 <= my and my + mh <= ry + rh + 1e-3
    tx, ty, tw, th = face["regions"]["text"]
    for element in ("name", "name_ar"):
        assert ty - 1e-3 <= face["placed"][element]["ink_top"] and face["placed"][element]["ink_bottom"] <= ty + th + 1e-3


# ---------------------------------------------------------------------------------------------------------------
# THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block headed "Before I start testing"):
# "The lid is missing the concept's rule, ring and radial lines." The lid draws each where the concept puts it, every
# standing rule holding — the mark's clear space (§AY2), no motif field as a ground behind the mark (§BA, C12), no
# colour or finish that nothing specified (§BH67's hard stop). Two instruments read GREEN on this defect and are not
# what these tests read: the vocabulary record marks "stroke_rule" DRAWN with particle ticks for evidence, and the
# motif-family check passes the powder scatter. Every assertion below is on a node's NAME, its geometry, a placement
# or a MEASURE ROW.
# ---------------------------------------------------------------------------------------------------------------

#: the brand ColorSystem's swatches as task 110's run reads them (``_brand_palette``: the product's own system, then
#: every canonical one — printed read-only by the investigation of this defect, 2026-09-25)
_T110_PALETTE = [
    {"role": "Primary", "name": "Blush", "hex": "#F2C4CE", "usage": "Main surfaces, hero cartons"},
    {"role": "Secondary", "name": "Pale Petal", "hex": "#F7DDE3", "usage": "Interior, secondary panels"},
    {"role": "Accent", "name": "Deep Rose", "hex": "#8B3A52", "usage": "Typography, fine detail lines"},
    {"role": "Metallic", "name": "Rose Gold", "hex": "Metallic 10122 C", "usage": "Caps, closures, foil detail"},
    {"role": "Ground", "name": "Warm Cream", "hex": "#FAF3EC", "usage": "Base packaging, backgrounds"},
    {"role": "Ground", "name": "Warm Gold", "hex": "#CBA87D", "usage": "Warm gold ground panels, gold fields behind type"},
    {"role": "Primary", "name": "Warm Nude", "hex": "#E8C9B3", "usage": "Main surfaces, warm hero packaging"},
    {"role": "Secondary", "name": "Soft Sand", "hex": "#F0DECB", "usage": "Secondary panels, interiors"},
    {"role": "Accent", "name": "Cocoa Rose", "hex": "#7A4A42", "usage": "Typography, fine detail lines"},
    {"role": "Metallic", "name": "Rose Gold", "hex": "Metallic 10122 C", "usage": "Caps, closures, foil detail"},
    {"role": "Ground", "name": "Warm Cream", "hex": "#FAF3EC", "usage": "Base packaging, backgrounds"},
    {"role": "Ground", "name": "Warm Gold", "hex": "#CBA87D", "usage": "Warm gold ground panels, gold fields behind type"},
]


def _t110_colours(concept=None):
    """The colours task 110's run hands the composer: its record (``container_colour_sources/1.0``) and the face's
    own lines, each through the reader the run calls."""
    from apps.pipeline.targets.container import colour_sources as CS
    concept = dict(concept or _T110_CONCEPT, verified=True)
    colors = {"cap": "#FAF3EC", "body": "#FAF3EC", "product": "#FAF3EC", "ink": "#8B3A52",
              "motif": ["#F2C4CE", "#8B3A52"]}
    # [the same answer, the ring: sourced beside the rule, as the run sources it for every face]
    for line in ("rule", "ring"):
        hx, _src = CS.line_colour(concept, _T110_PALETTE, element=line, stand_in="#C9A24B")
        colors[line] = hx
    return colors


def test_the_concepts_rule_is_read_from_every_sentence_and_never_from_a_window_a_band_or_a_stroke():
    """The rule is read from every sentence of the concept's design through the finish reader's own targets, the
    longest phrase winning its span. Measured on every face concept on record and on task 110 before the reader was
    written: exactly three name a rule of their own — 88 B "horizontal rule", 88 C "single name-separator rule", task
    110 "hairline rule" (its colour field and its finish sentence). 89 A is the negative control: its "window rule" is
    the window's frame and its "rule ring" the ring, in the plan and in the finish reader alike."""
    from apps.ire import concept_front as CF
    from apps.ire import container_finishes as F
    concepts = dict(_FACE_CONCEPTS, **{"110_A_RADIANT_AXIS": _T110_CONCEPT})
    got = {key: CF.plan(dict(c, verified=True), {"reconstruction_capability": "SUPPORTED"}, ground_hex="#FAF3EC",
                        edge_hex=None)["why"].get("rule") for key, c in concepts.items()}
    assert {k: v for k, v in got.items() if v} == {
        "88_B_LIQUID_VEIL": ["horizontal rule (finish_signature)"],
        "88_C_DEWDROP_CONSTELLATION": ["single name-separator rule (finish_signature)"],
        "110_A_RADIANT_AXIS": ["hairline rule (color_field_signature)", "hairline rule (finish_signature)"]}
    # the traps, each in the words of a concept on record
    assert CF.lines({"finish_signature": "rose-gold hot-foil on window frame hairline rule, BBROSE seal"})["rule"] == []
    assert CF.lines({"finish_signature": "rose-gold hot-foil on BBROSE wordmark, droplet hairline strokes"})["rule"] == []
    assert CF.lines({"color_field_signature": "spot gloss UV for inner droplet cluster; blush-tinted rules on side "
                                              "band"})["rule"] == []
    assert CF.lines({"finish_signature": "no foil rule ring — finish is motif-concentrated"})["rule"] == []
    a89 = _FACE_CONCEPTS["89_A_PETAL_WINDOW"]["finish_signature"].lower()
    phrases = {w: t for _s, _e, t, w in F.target_phrases(a89)}
    assert phrases["window rule"] == "window" and phrases["rule ring"] == "ring" and "rule" not in phrases.values()


def test_the_lid_draws_the_concepts_rule_between_the_name_and_the_arabic_line_at_no_cost_to_the_name(monkeypatch):
    """Task 110's "Rose Gold hot-foil on BBROSE lockup and hairline rule", which its picture draws under "Focus" and
    over "فوكس": ONE straight stroke at the §AU2 weight, midway in the gap the stack already keeps between the two
    lines (as the ruled front sets its rule, §BH66(b)), the concept's own width (0.3658 of the surface, 40.24 mm) on the
    name's axis. It is not an element of the stack, so it costs the name no step: 48 pt with it and without it, 60 and
    72 pt refused for the mark exactly as before, every other element where it was. The concept's foil lands on it."""
    from apps.ire import concept_front as CF
    from apps.ire import container_finishes as F
    from apps.ire.compose_container import FACE_RULE
    from apps.ire.container_brand_usage import evaluate_brand_usage
    from apps.ire.graph import LineTo, MoveTo
    from apps.pipeline.services.container_projection import validate_zone_containment
    colors = _t110_colours()
    doc = _face_of(_T110_CONCEPT, _T110_VISION, colors=colors)
    face = doc.metadata["concept_front"]["face"]
    names = [n.name for n, _ in doc.walk()]
    assert names.count(FACE_RULE) == 1 and "rule-front-single" not in names        # §AU1's own rule is not a face's
    rule = next(n for n, _ in doc.walk() if n.name == FACE_RULE)
    assert [type(sg) for sg in rule.segments] == [MoveTo, LineTo] and len({sg.y for sg in rule.segments}) == 1
    assert rule.stroke.width_mm == 0.30 and rule.stroke.color.to_hex() == colors["rule"] == "#C9A24B"
    y, (x0, x1) = rule.segments[0].y, (rule.segments[0].x, rule.segments[1].x)
    name, arabic = face["placed"]["name"], face["placed"]["name_ar"]
    assert name["ink_bottom"] < y < arabic["ink_top"]
    assert abs(y - (name["ink_bottom"] + arabic["ink_top"]) / 2.0) < 1e-3
    assert abs((x1 - x0) - 0.3658 * 110.0) < 1e-2 and abs((x0 + x1) / 2.0 - name["x"]) < 1e-3
    tx, _ty, tw, _th = face["regions"]["text"]
    assert tx <= x0 and x1 <= tx + tw and FACE_RULE in face["drawn"]
    step = face["name_size"]
    # [the same answer, the ring: 48 pt with the rule alone — 60 and 72 refused for the mark exactly as before it; the
    # rim rule's GAP then takes the lid to 36 pt, pinned with its reasons in the §BH68(b)2 test above. The rule's own
    # cost is still nothing: the rule-less face below steps where this one does.]
    assert step["step_pt"] == 36.0
    # the rule recorded as the strip its ink prints, the §BB4 divider's kind, inside the lid's safe area
    divider = [p for p in doc.metadata["placements"] if p["kind"] == "divider"]
    assert len(divider) == 1 and divider[0]["nh"] < 0.01
    assert validate_zone_containment(doc.metadata["placements"], _WHOLE_LID, {"archetype": "compact", "variant": ""}) == []
    assert evaluate_brand_usage(doc)["meets_clear_space"] is True
    # its finish is the concept's own: the foil clause's "hairline rule" lands on it, and only on it
    spec = cm.build_motif_spec(dict(_T110_CONCEPT, verified=True), {}, _WHOLE_LID, {})
    rows = F.apply(doc, spec["finish_assignments"], brand_metallic_hex="#C9A24B")["applied"]
    assert [(r["state"], r["nodes"]) for r in rows if (r["finish"], r["target"]) == ("foil", "rule")] == [
        (F.APPLIED, [FACE_RULE])]
    # NO NAME STEP: the same face with the rule's words unread draws no rule and everything else where it was
    # [the same answer, the ring: only the rule's words are unread — the ring's stay, so the two faces differ by the rule]
    monkeypatch.setattr(CF, "lines", lambda structured, _real=CF.lines: dict(_real(structured), rule=[]))
    plain = _face_of(_T110_CONCEPT, _T110_VISION, colors=colors).metadata["concept_front"]["face"]
    # [the same answer, the ring: the rule lies in the gap between the two lines, so where a step pushes them out of
    # their region it goes with them and says so ("the rule leaves its region", at 72 pt) — never alone. Strike the
    # rule's own lines and the refusal record is the rule-less face's, step for step: the rule refuses no step. With the
    # rule alone the two records were equal outright.]
    assert FACE_RULE not in plain["drawn"] and {plain["name_size"]["step_pt"], step["step_pt"]} == {36.0}
    strike = [(r["step_pt"], [w for w in r["why"] if not w.startswith("the rule ")]) for r in step["larger_steps_refused"]]
    assert all(why for _s, why in strike)
    assert strike == [(r["step_pt"], r["why"]) for r in plain["name_size"]["larger_steps_refused"]]
    assert plain["placed"] == {k: v for k, v in face["placed"].items() if k != "rule"}


def test_the_rule_prints_in_the_colour_its_own_words_give_it_else_the_fine_detail_swatch_never_the_type_ink():
    """§BH67's hard stop over the rule: "a finish or colour applied that nothing specified". Task 110's words give its
    rule Rose Gold — the brand's Metallic, which carries no hex — so it prints in the metal's depiction, the stand-in
    the brand record names, and the finish plates it; a rule the words give a hex prints in it; a rule the words give
    no colour prints in the brand swatch whose usage names fine detail lines. The type's colour is never borrowed: a
    concept that sets its type in Cocoa Rose keeps its rule in Deep Rose. And the audit reads the rule's own stroke —
    unsourced, it is refused by name."""
    from apps.ire.compose_container import FACE_RULE, declared_tints
    from apps.pipeline.targets.container import colour_sources as CS
    hx, why = CS.line_colour(dict(_T110_CONCEPT), _T110_PALETTE, element="rule", stand_in="#C9A24B")
    assert hx == "#C9A24B" and "`color_field_signature` — Rose Gold, a metal" in why and "10122 C" in why
    assert CS.line_colour({"color_field_signature": "Deep Rose (#8B3A52) hairline rule"}, _T110_PALETTE,
                          element="rule", stand_in="#C9A24B")[0] == "#8B3A52"
    cocoa = {"typography_signature": "Didone name in Cocoa Rose", "finish_signature": "hot-foil on the hairline rule"}
    assert CS.type_ink(cocoa, _T110_PALETTE)[0] == "#7A4A42"
    hx, why = CS.line_colour(cocoa, _T110_PALETTE, element="rule", stand_in="#C9A24B")
    assert hx == "#8B3A52" and "fine detail lines" in why and "give its rule no colour" in why
    assert CS.line_colour(cocoa, [], element="rule", stand_in="#C9A24B")[0] is None
    colors = _t110_colours()
    doc = _face_of(_T110_CONCEPT, _T110_VISION, colors=colors)
    sourced = dict({"#FAF3EC": "cap", "#8B3A52": "ink", "#F2C4CE": "motif"}, **declared_tints(colors))
    read = CS.printed_colour_audit(doc, dict(sourced, **{colors["rule"]: "rule"}))
    assert read["codes"] == [] and read["printed"]["#C9A24B"]["nodes"] == [FACE_RULE]
    assert CS.printed_colour_audit(doc, sourced)["codes"] == ["%s:#C9A24B:%s" % (CS.UNSOURCED_CODE, FACE_RULE)]


def test_the_concepts_rule_is_measured_against_the_rule_it_drew():
    """The layout measure reads the rule beside the window and the ring (``face_drawn_boxes``, the reading
    ``reconstruct_container`` makes, moved out unchanged so it is read here without the database). Task 110's rule row
    was NOT_DRAWN; it is MEASURED — the concept's own width, 2.37 mm below the concept's place in the same gap, the
    midway rule. Every other row reads exactly what the run recorded before it (task 110's layout measure)."""
    from apps.pipeline.services import concept_layout as L
    from apps.pipeline.targets.container import face_drawn_boxes
    surface, drawn = face_drawn_boxes(_face_of(_T110_CONCEPT, _T110_VISION, colors=_t110_colours()))
    rows = {r["element"]: r for r in L.measure(_T110_VISION, drawn)}
    assert surface == [137.5, 17.4, 110.0, 89.0]
    # [the same answer, the ring: the rim rule's GAP takes the lid to 36 pt, and the rows move with the step. With the
    # rule alone the rule read [0.31, 0.5614, 0.6758, 0.5614], dx 0.016, dy 0.0265, and every other row exactly what the
    # run recorded (mark dy 0.0366; name dy -0.0336, 1.194 x 0.858; name_ar dy 0.1102, 0.749 x 1.306; motif as below).
    # At 36 pt the rule sits midway in a 12.70 mm gap, 1.63 mm above the concept's own place; the ring is measured too]
    assert rows["rule"]["state"] == "MEASURED" and rows["rule"]["drawn"] == [0.31, 0.5166, 0.6758, 0.5166]
    assert (rows["rule"]["dx"], rows["rule"]["dy"], rows["rule"]["width_ratio"]) == (0.016, -0.0183, 1.0)
    # [the same answer, the radial lines: the motif is the concept's own rays now, where the powder scatter read (0.0277,
    # 0.0621, 0.946, 0.953). Drawn [0.0902, 0.278, 0.9153, 0.9044] against the concept's [0.0822, 0.1006, 0.9166, 0.9053]:
    # its width within 1.1 %, its foot within 0.001; its top 0.177 lower, held there by the mark's clear space, at which
    # the upward rays are shortened]
    assert {k: (r["dx"], r["dy"], r["width_ratio"], r["height_ratio"]) for k, r in rows.items()
            if k in ("mark", "name", "name_ar", "motif")} == {
        "mark": (0.0, 0.0434, 1.0, 1.258), "name": (0.0, -0.0311, 0.895, 0.643),
        "name_ar": (0.0, 0.0176, 0.562, 0.979), "motif": (0.0034, 0.0882, 0.989, 0.778)}
    assert rows["motif"]["drawn"] == [0.0902, 0.278, 0.9153, 0.9044]
    assert rows["ring"]["state"] == "MEASURED" and rows["ring"]["drawn"] == [0.03, 0.0371, 0.97, 0.9629]


def test_a_rule_the_face_cannot_set_between_its_two_lines_is_not_placed_and_says_why():
    """Room, never a refusal: a face with no Arabic line has nothing to separate, and a face whose window sits between
    the name and the Arabic line (88 A's arrangement) has no gap to put it in — each NOT_PLACED with its reason. On
    the face concepts on record the rule is drawn on 88 B and 88 C, whose names stand together, and on nothing else —
    89 A, the negative control, draws none."""
    from apps.ire import concept_face as CFA
    from apps.ire.compose_container import FACE_RULE
    rec = {"placed": {"name": {"x": 50.0, "align": "centre", "ink_top": 10.0, "ink_bottom": 20.0}},
           "regions": {"text": [0.0, 0.0, 100.0, 100.0]}, "not_placed": [], "rules": {}}
    CFA.place_rule(rec, rule_mm=0.30)
    assert "rule" not in rec["placed"] and "no Arabic line" in rec["not_placed"][0]["reason"]
    rec["placed"].update(name_ar={"x": 50.0, "align": "centre", "ink_top": 70.0, "ink_bottom": 80.0},
                         window=[20.0, 30.0, 60.0, 30.0])
    rec["not_placed"] = []
    CFA.place_rule(rec, rule_mm=0.30)
    assert "rule" not in rec["placed"] and "the window sits between" in rec["not_placed"][0]["reason"]
    drawn = {key: FACE_RULE in _face(key)[0].metadata["concept_front"]["face"]["drawn"] for key in _FACE_CONCEPTS}
    assert {k for k, v in drawn.items() if v} == {"88_B_LIQUID_VEIL", "88_C_DEWDROP_CONSTELLATION"}


def test_the_concepts_ring_is_read_from_every_sentence_beside_its_frame_words():
    """THE RING. The finish reader has read "rim rule" and "rule ring" as the ring since §BH65(c)2; the plan read its
    ring only from the arrangement's frame words, so the two disagreed and task 110's "Deep Rose (#8B3A52) for all name
    type and rim rule" drew nothing. Read now from every sentence, ADDED to the frame words, which stand: of the face
    concepts on record 89 B ("... BBROSE wordmark and rim rule") and task 110 gain a ring; 84 A, 88 A and 89 A keep
    theirs; 89 C's "no foil rule ring" asks for none."""
    from apps.ire import concept_front as CF
    concepts = dict(_FACE_CONCEPTS, **{"110_A_RADIANT_AXIS": _T110_CONCEPT})
    plans = {key: CF.plan(dict(c, verified=True), {"reconstruction_capability": "SUPPORTED"}, ground_hex="#FAF3EC",
                          edge_hex=None) for key, c in concepts.items()}
    assert {k for k, p in plans.items() if p["ring"]} == {"84_A_PETAL_WINDOW", "88_A_PETAL_WINDOW", "89_A_PETAL_WINDOW",
                                                          "89_B_LIQUID_VEIL", "110_A_RADIANT_AXIS"}
    assert plans["89_B_LIQUID_VEIL"]["why"]["ring"] == ["rim rule (finish_signature)"]
    assert plans["110_A_RADIANT_AXIS"]["why"]["ring"] == ["rim rule (color_field_signature)"]
    assert plans["84_A_PETAL_WINDOW"]["why"]["ring"] == ["frame"] and "rule ring" in plans["89_A_PETAL_WINDOW"]["why"]["ring"]
    assert CF.lines({"finish_signature": _FACE_CONCEPTS["89_C_DEWDROP_CONSTELLATION"]["finish_signature"]})["ring"] == []


def test_the_lid_draws_the_concepts_ring_round_the_lid_on_its_own_outline_in_its_own_colour():
    """Task 110's rim rule: ONE ring at the §AU2 weight, in the colour its words give it — "Deep Rose (#8B3A52) for all
    name type and rim rule" — traced on the lid's own outline one stroke inside the safe line. The concept draws its
    ring round; this lid is a rounded rectangle, so the ring follows the lid's outline (corner 7.60 mm, less its 3.30 mm
    inset: 4.30 mm) and the record says SUBSTITUTED, by name. The concept puts its ring 0.53 mm from its edge; the safe
    margin holds this one 3.15 mm in, and says so. No finish lands on it: nothing specified one."""
    from apps.ire import container_finishes as F
    from apps.ire.container_brand_usage import evaluate_brand_usage
    from apps.pipeline.services.container_projection import validate_zone_containment
    from apps.pipeline.targets.container import colour_sources as CS
    colors = _t110_colours()
    hx, why = CS.line_colour(dict(_T110_CONCEPT), _T110_PALETTE, element="ring", stand_in="#C9A24B")
    assert (hx, why) == (colors["ring"], "the concept's own `color_field_signature` — Deep Rose, named for its ring "
                                         "('rim rule')")
    doc = _face_of(_T110_CONCEPT, _T110_VISION, colors=colors)
    face = doc.metadata["concept_front"]["face"]
    rings = [n for n, _ in doc.walk() if n.name == "frame-ring"]
    assert len(rings) == 1 and rings[0].stroke.width_mm == 0.30 and rings[0].stroke.color.to_hex() == "#8B3A52"
    assert _box(rings[0]) == (140.8, 20.7, 103.4, 82.4) == tuple(face["ring"])
    assert abs(rings[0].segments[0].x - 140.8 - 4.3) < 1e-9          # the outline's corner, less the inset
    assert face["ring_shape"] == {
        "state": "SUBSTITUTED", "concept_shape": "round", "drawn_shape": "rounded_rect", "corner_mm": 4.3,
        "lid_corner_mm": 7.6, "path_inset_mm": 3.3, "ink_inset_mm": 3.15, "concept_inset_mm": 0.525,
        "reason": face["ring_shape"]["reason"]}
    assert "least move" in face["ring_shape"]["reason"] and "the safe margin holds" in face["ring_shape"]["reason"]
    # its ink recorded as the four strips it prints; inside the lid's safe area; the mark's clear space inside it
    assert len([p for p in doc.metadata["placements"] if p["kind"] == "frame"]) == 4
    assert validate_zone_containment(doc.metadata["placements"], _WHOLE_LID, {"archetype": "compact", "variant": ""}) == []
    usage = evaluate_brand_usage(doc)
    assert usage["meets_clear_space"] is True and usage["motif_strands_over_mark"] == 0
    cx, cy, cw, ch = face["placed"]["mark"]["clear_box"]
    assert 140.8 < cx and cx + cw < 140.8 + 103.4 and 20.7 < cy and cy + ch < 20.7 + 82.4
    spec = cm.build_motif_spec(dict(_T110_CONCEPT, verified=True), {}, _WHOLE_LID, {})
    rows = F.apply(doc, spec["finish_assignments"], brand_metallic_hex="#C9A24B")["applied"]
    assert not [r for r in rows if r["target"] == "ring"] and rings[0].finishes == []


def test_a_ring_prints_in_its_own_record_and_never_in_the_type_ink_by_accident():
    """Until now ``draw_ring`` took the type ink. On task 110 the two are the same Deep Rose, so it proves nothing: a
    concept that sets its type in Cocoa Rose and names no colour for its rim rule draws its ring in the brand swatch whose
    usage is fine detail lines — Deep Rose — and its type in Cocoa Rose. 89 A's foil words sit nearest its "circumference
    rule ring", so its ring is the metal's depiction. And every face concept on record whose plan draws a ring has a
    sourced colour for it, so none falls back to the stand-in the audit refuses."""
    from apps.ire import concept_front as CF
    from apps.ire.compose_container import declared_tints
    from apps.pipeline.targets.container import colour_sources as CS
    cocoa = dict(_T110_CONCEPT, typography_signature="Didone name in Cocoa Rose, centred",
                 color_field_signature="Single warm cream (#FAF3EC) full-face ground; a fine rim rule; Blush (#F2C4CE) "
                                       "particle field lines")
    assert CS.type_ink(cocoa, _T110_PALETTE)[0] == "#7A4A42"
    ring_hex, why = CS.line_colour(cocoa, _T110_PALETTE, element="ring", stand_in="#C9A24B")
    assert ring_hex == "#8B3A52" and "fine detail lines" in why
    colors = dict(_t110_colours(cocoa), ink="#7A4A42")
    doc = _face_of(cocoa, _T110_VISION, colors=colors)
    inks = {n.name: (n.stroke.color if getattr(n, "stroke", None) else getattr(n, "color", None)).to_hex()
            for n, _ in doc.walk() if n.name in ("frame-ring", "product-name-hero", "product-name-ar")}
    assert inks == {"frame-ring": "#8B3A52", "product-name-hero": "#7A4A42", "product-name-ar": "#7A4A42"}
    sourced = dict({"#FAF3EC": "cap", "#7A4A42": "ink", "#F2C4CE": "motif", "#8B3A52": "ring", "#C9A24B": "rule"},
                   **declared_tints(colors))
    assert CS.printed_colour_audit(doc, sourced)["codes"] == []
    assert CS.line_colour(_FACE_CONCEPTS["89_A_PETAL_WINDOW"], _T110_PALETTE, element="ring",
                          stand_in="#C9A24B")[0] == "#C9A24B"
    for key, concept in _FACE_CONCEPTS.items():
        if CF.plan(dict(concept, verified=True), {"reconstruction_capability": "SUPPORTED"}, ground_hex="#FAF3EC",
                   edge_hex=None)["ring"]:
            assert CS.line_colour(concept, _T110_PALETTE, element="ring", stand_in="#C9A24B")[0], key


def test_the_motif_is_held_to_the_rings_inside_and_the_type_keeps_its_gap():
    """§BH68(b) with the ring: the step the lid holds is the largest with every element inside its region. The type is
    held ONE EM inside the ring — concept_face's GAP, untouched — and the motif, which is not type, to the ring's inside:
    task 110's motif runs past the text region and stays inside the ring (held to the text region the name fell to 12
    pt, measured). A face with no ring has one region for both, so nothing it draws can move."""
    face = _face_of(_T110_CONCEPT, _T110_VISION, colors=_t110_colours()).metadata["concept_front"]["face"]
    mx, my, mw, mh = face["regions"]["mark"]
    tx, ty, tw, th = face["regions"]["text"]
    gap = face["gap_mm"]
    assert face["name_size"]["step_pt"] == 36.0 and abs(gap - 36.0 * 25.4 / 72.0) < 1e-3
    assert (round(tx - mx, 3), round(ty - my, 3), round(mw - tw, 3), round(mh - th, 3)) == (gap, gap, 2 * gap, 2 * gap)
    x, y, w, h = face["placed"]["motif_region"]
    assert mx <= x and x + w <= mx + mw and my <= y and y + h <= my + mh
    assert x < tx and x + w > tx + tw                                 # past the type's region, inside the ring's
    for key in _FACE_CONCEPTS:
        f = _face(key)[0].metadata["concept_front"]["face"]
        if f["ring"] is None:
            assert f["regions"]["mark"] == f["regions"]["text"], key


def test_the_lid_draws_the_concepts_radial_lines_in_their_own_colour_and_none_into_the_marks_clear_space():
    """THE RADIAL LINES. Task 110's "fine Bézier stroked lines emanating from a single centre point behind the type,
    each ending in a small filled circular node, all in Blush #F2C4CE at reduced opacity, density tapering toward the
    rim" is drawn as rays, where a powder scatter was drawn. ONE colour, the motif's own Blush — the sourced motif
    palette also holds the colour field's Deep Rose, the type's, and no ray or node prints in it — at the declared
    reading of "reduced opacity". The rays that would reach into the mark's clear space are SHORTENED at it, their nodes
    moved with them — 24 of 72, none removed — so the whole-leaf refusal takes nothing and nothing enters the clear
    space. The family check now reads the geometry that is drawn: the rays pass the radial family, and the scatter
    that was drawn for it would fail it."""
    from apps.ire import concept_face as CFA
    from apps.ire.container_brand_usage import evaluate_brand_usage
    from apps.ire.container_motif_fidelity import MOTIF_FAMILY_MISMATCH, validate_motif_fidelity
    doc = _face_of(_T110_CONCEPT, _T110_VISION, colors=_t110_colours())
    face = doc.metadata["concept_front"]["face"]
    leaves = list(next(n for n, _ in doc.walk() if n.name == "motif-field").children)
    rays = [lf for lf in leaves if lf.name.startswith("radial-ray-")]
    nodes = {lf.name.rsplit("-", 1)[1]: lf for lf in leaves if lf.name.startswith("radial-node-")}
    assert len(rays) == len(nodes) == 72 and len(leaves) == 144
    assert {lf.stroke.color.to_hex() for lf in rays} | {n.fill.color.to_hex() for n in nodes.values()} == {"#F2C4CE"}
    assert {lf.stroke.opacity for lf in rays} | {n.fill.opacity for n in nodes.values()} == {0.5}
    for ray in rays:
        nx, ny, nw, nh = _box(nodes[ray.name.rsplit("-", 1)[1]])
        assert abs(nx + nw / 2.0 - ray.segments[-1].x) < 1e-6 and abs(ny + nh / 2.0 - ray.segments[-1].y) < 1e-6
    clear = face["placed"]["mark"]["clear_box"]
    assert CFA.refuse_behind_mark([(lf.name, _box(lf)) for lf in leaves], clear) == []
    assert (face["trimmed"][0]["count"], face["trimmed"][0]["removed_count"], face["refused"]) == (24, 0, [])
    usage = evaluate_brand_usage(doc)
    assert usage["motif_strands_over_mark"] == 0 and usage["meets_clear_space"] is True
    spec = cm.build_motif_spec(dict(_T110_CONCEPT, verified=True), {}, _WHOLE_LID, {})
    assert validate_motif_fidelity(doc, spec)["axes"]["motif_family"]["state"] == "MEASURED_PASS"
    scatter = _face_of(dict(_T110_CONCEPT, motif_signature="Particle veil: fine lines, each ending in a small node"),
                       _T110_VISION, colors=_t110_colours())
    assert any((n.name or "").startswith("particle-") for n, _ in scatter.walk())
    assert validate_motif_fidelity(scatter, spec)["axes"]["motif_family"]["code"] == MOTIF_FAMILY_MISMATCH


def test_bh67d2_unread_the_face_keeps_its_fixed_slots_and_says_so():
    """"Where the vision step cannot read an element, it says so and the fixed slot is used — reported, never
    silent." A failed read moves nothing and names every element it left in its slot."""
    plain = _t91_face(None)
    failed = _t91_face({"state": "FAILED", "why": "the vision call raised RuntimeError"})
    placed = lambda d: d.metadata["concept_front"]["face"]["placed"]              # noqa: E731
    assert placed(failed) == placed(plain)
    follow = failed.metadata["concept_front"]["face"]["concept_layout"]
    assert follow["state"] == "FAILED" and follow["followed"] == [] and follow["moves"] == []
    assert {r["element"] for r in follow["fixed_slot"]} >= {"mark", "name", "name_ar", "window"}
    assert all("FAILED" in r["reason"] for r in follow["fixed_slot"])


def test_bh67d2_the_face_follows_the_concept_and_every_rule_wins_by_the_least_move_recorded_by_name():
    """Task 91 drawn from its own concept's read: each element to where the concept puts it on the real lid, then the
    rules. The concept sets BBROSE at the lid's very top and the name 1 mm under it — inside the safe margin and the
    mark's clear space — so the mark moves down into the safe area and each element below keeps one gap, every move
    named with its rule; the instruments that own the two limits read them held."""
    from apps.ire.container_brand_usage import evaluate_brand_usage
    from apps.pipeline.services.container_projection import validate_zone_containment
    doc = _t91_face(_T91_VISION)
    face = doc.metadata["concept_front"]["face"]
    follow = face["concept_layout"]
    assert [f["element"] for f in follow["followed"]] == ["mark", "name", "name_ar", "window", "motif"]
    assert follow["followed"][-1]["inside"] == "window" and follow["fixed_slot"] == []
    rules = [(m["element"], m["rule"].split(" —")[0].split(" (")[0]) for m in follow["moves"]]
    # the concept's mark sits at the lid's very crown, inside the safe margin and the ring: it moves down into its
    # region with its clear space, and the name and the Arabic line keep one gap below it — the least movement, each
    # moved once; the window is where the concept puts it and does not move
    # [§BH68(b), 2026-09-24: the name is now the largest step of the typographic scale the lid holds for the concept's
    # layout — 16 pt, where it printed at the bottle's 9 pt tier — and the Arabic line 16 pt with it; at that size the
    # stack's gaps push the window down too, the least distance, recorded, its size the concept's own. At 9 pt the
    # window did not move.]
    assert rules == [("mark", "the stack's rules"), ("name", "the stack's rules"), ("name_ar", "the stack's rules"),
                     ("window", "the stack's rules")]
    assert face["collisions"] == [] and face["refused"] == [] and face["not_placed"] == []
    # the window is the concept's own box on the real lid (0.352 x 0.396 of 110 x 89 mm), the mark the concept's own
    # width (0.233 of the lid, 25.7 mm, above the 12.0 mm floor and under a third of the face); the type keeps its tier
    wx, wy, ww, wh = face["placed"]["window"]
    assert abs(ww - 38.698) < 1e-3 and abs(wh - 35.262) < 1e-3
    assert abs(face["placed"]["mark"]["box"][2] - 25.663) < 1e-3
    # §BH68(b): the scale's step the lid holds, never the bottle's 9 pt tier
    assert {n.size_pt for n, _ in doc.walk() if (n.name or "").startswith("product-name")} == {16.0}
    usage = evaluate_brand_usage(doc)
    assert usage["meets_clear_space"] is True and usage["motif_strands_over_mark"] == 0
    assert validate_zone_containment(doc.metadata["placements"], _WHOLE_LID, {"archetype": "compact", "variant": ""}) == []


def test_bh67d2_the_window_is_drawn_in_the_shape_the_concept_draws_it():
    """Task 91's words — "oval petal-window cartouche", "rose-gold oval cartouche" — and its picture (the vision read's
    window: "shape": "oval") draw an oval; words that give no shape keep the rounded window it always drew."""
    from apps.ire import concept_front as CF
    from apps.ire.graph import CubicTo, LineTo
    t91 = dict(_FACE_CONCEPTS["89_A_PETAL_WINDOW"],
               composition_signature="Vertical axis centred: BBROSE wordmark at crown → bilingual name block → oval "
                                     "petal-window cartouche at disc centre")
    assert CF.plan(t91, {"reconstruction_capability": "SUPPORTED"}, ground_hex="#FAF3EC",
                   edge_hex=None)["window_shape"] == "oval"
    doc = _t91_face(_T91_VISION)
    frame = next(n for n, _ in doc.walk() if (n.name or "") == "window-frame")
    assert [type(sg) for sg in frame.segments].count(CubicTo) == 4
    assert not any(isinstance(sg, LineTo) for sg in frame.segments)
    plain = CF.plan(_FACE_CONCEPTS["89_A_PETAL_WINDOW"], {"reconstruction_capability": "SUPPORTED"},
                    ground_hex="#FAF3EC", edge_hex=None)
    assert plain["window_shape"] is None


def test_bh67c5_the_face_marks_its_name_for_the_concepts_own_granted_face():
    """§BH67(c)5 through the composer: a face whose concept names a granted face marks its name runs for it and
    writes the lead for the layer; task 89's own words name only a style, and its name prints as it always has."""
    from apps.ire import concept_typeface as CT
    from apps.ire.font_roles import CONCEPT_NAME, CONCEPT_TYPEFACE_KEY, catalogue
    doc, _spec, concept = _face("89_A_PETAL_WINDOW")
    assert [n.font for n, _ in doc.walk() if (n.name or "") == "product-name-hero"] == ["bold"]
    assert CONCEPT_TYPEFACE_KEY not in doc.metadata
    from apps.ire import concept_face as CFA
    from apps.ire import concept_front as CF
    named = dict(concept, typography_signature="Product name in Poppins SemiBold, wide-tracked small caps, above "
                                                "the petal window; matching calligraphic Arabic below")
    spec = cm.build_motif_spec(named, {}, _LID_ZONE, {})
    plan = CF.plan(named, spec, ground_hex="#FAF3EC", edge_hex="#F7DDE3")
    plan["face"] = dict(CFA.read(named, layout=plan["layout"], has_arabic=True, product_name="Focus Pressed Powder"),
                        surface="LID_TOP", name_ar="فوكس بودرة مضغوطة")
    plan["typeface"] = CT.read(named, catalogue())
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    led = compose_container_graph(
        build_backbone(ContainerProfile(archetype="compact", height_mm=95, width_mm=110)),
        product_name="Focus Pressed Powder", sku="S", native=True, zones=_LID_ZONE, logo_path="media/brand/logo.png",
        hierarchy_lines=ruled_front_hierarchy("Focus Pressed Powder", descriptor="pressed powder compact"),
        motif_spec=spec, colors={"body": "#B4A390", "cap": "#FAF3EC"}, concept_front=plan)
    fonts = {n.name: n.font for n, _ in led.walk() if (n.name or "").startswith("product-name")}
    assert fonts["product-name-ar"] == "regular"                          # the Arabic line keeps Naskh
    assert {f for k, f in fonts.items() if k != "product-name-ar"} == {CONCEPT_NAME}
    assert led.metadata[CONCEPT_TYPEFACE_KEY]["stem"] == "Poppins-SemiBold"


class TestTheFaceIsArrangedAsTheConceptSays:
    """§BH66(a) on task 89's own lid and task 89's own concept, verbatim. The face is laid out inside the confirmed
    zone less its safe margin; the two limits are proved by the instruments that read them (the brand-usage verdict
    and zone containment), never by the layout's own arithmetic."""

    def test_task_89s_face_follows_its_concept_inside_both_limits(self):
        from apps.ire.container_brand_usage import evaluate_brand_usage
        from apps.pipeline.services.container_projection import validate_zone_containment
        doc, _spec, _c = _face("89_A_PETAL_WINDOW")
        nodes = {n.name: n for n, _ in doc.walk()}
        name, arabic, frame, logo = (nodes["product-name-hero"], nodes["product-name-ar"], nodes["window-frame"],
                                     nodes["logo"])
        window_top = min(p.y for p in frame.segments if hasattr(p, "y"))
        window_bottom = max(p.y for p in frame.segments if hasattr(p, "y"))
        # top to bottom as the concept arranges it: the name, the Arabic line, the window, the mark
        assert name.y < arabic.y < window_top < window_bottom < logo.y
        assert "frame-ring" in nodes and "motif-window" in nodes
        assert name.text_case == "upper" and name.tracking_em == 0.15      # "wide-tracked small caps"
        # the ruled front is not drawn on a face: no §AU1 rule, no supporting line — and the descriptor says why
        assert "rule-front-single" not in nodes
        assert not [n for n in nodes.values() if getattr(n, "text", None) == "pressed powder compact"]
        face = doc.metadata["concept_front"]["face"]
        assert face["governed_by"] == "§BH66(a)"
        assert [r["element"] for r in face["not_in_arrangement"]] == ["descriptor"]
        assert face["refused"] == [] and face["collisions"] == [] and face["not_placed"] == []
        # LIMIT 1, read by the instrument that owns it: the mark's clear space holds on every side
        usage = evaluate_brand_usage(doc)
        assert usage["meets_clear_space"] is True
        # LIMIT 2: no motif behind the mark
        assert usage["motif_strands_over_mark"] == 0
        assert validate_zone_containment(doc.metadata["placements"], _LID_ZONE,
                                         {"archetype": "compact", "variant": ""}) == []
        # a face is its own hero: the lid is drawn once, never again as a LID TOP strip panel
        assert doc.metadata["surface_inventory"] == {"LID_TOP": "hero"}
        assert {n.print_scope.surface for n in (name, arabic)} == {"LID_TOP"}

    def test_the_mark_takes_a_third_of_the_face_and_never_passes_the_print_floor(self):
        from apps.ire import concept_face as CFA
        aspect, cap = 0.2085, 0.8567
        assert CFA.mark_width(62.1, 30.0, aspect, cap)[0] == 30.0                       # fits: the composer's own
        w, why = CFA.mark_width(62.1, 50.16, aspect, cap)                               # task 89: shrunk to a third
        block = w * aspect * (1.0 + 2.0 * cap)          # the mark's height and its clear space above and below
        assert abs(block - 62.1 / 3.0) < 1e-9 and "§AY2 step 2" in why
        assert CFA.mark_width(15.0, 50.16, aspect, cap)[0] == CFA.MARK_FLOOR_MM == 12.0  # never under the floor

    def test_a_veil_across_the_face_refuses_by_name_only_what_meets_the_marks_clear_space(self):
        from apps.ire.container_brand_usage import evaluate_brand_usage
        from apps.pipeline.services.container_projection import validate_zone_containment
        doc, _spec, _c = _face("89_B_LIQUID_VEIL")          # "wordmark pins the top" of a full-face veil
        face = doc.metadata["concept_front"]["face"]
        refused = face["refused"][0]
        assert refused["count"] > 0 and "§BH66(a)" in refused["limit"]
        clear = face["placed"]["mark"]["clear_box"]
        field = [n for n, _ in doc.walk() if n.name == "motif-field"][0]
        leaves, stack = [], list(field.children)
        while stack:
            node = stack.pop()
            if getattr(node, "children", None):
                stack.extend(node.children)
            elif _box(node):
                leaves.append(node)
        assert leaves, "the veil is drawn where it does not meet the mark"
        for leaf in leaves:
            x, y, w, h = _box(leaf)
            assert not (x < clear[0] + clear[2] and clear[0] < x + w and y < clear[1] + clear[3] and clear[1] < y + h)
        assert evaluate_brand_usage(doc)["motif_strands_over_mark"] == 0
        assert validate_zone_containment(doc.metadata["placements"], _LID_ZONE,
                                         {"archetype": "compact", "variant": ""}) == []

    def test_turned_type_is_set_level_and_recorded_approximated(self):
        doc, _spec, _c = _face("89_C_DEWDROP_CONSTELLATION")
        arabic = [n for n, _ in doc.walk() if n.name == "product-name-ar"][0]
        assert arabic.rotation_deg == 0.0 and arabic.align == "right"
        turned = doc.metadata["concept_front"]["face"]["reading"]["approximated"]
        assert [(a["element"], a["words"]) for a in turned] == [("name_ar", "rotated")]

    def test_a_governed_term_the_face_draws_is_drawn_and_carries_no_governed_code(self):
        from apps.ire import composer_vocabulary as V
        doc, spec, concept = _face("89_A_PETAL_WINDOW")
        rec = V.realization(concept, doc, spec)
        rows = {r["term"]: r for r in rec["terms"]}
        for term in ("window", "frame_ring", "bilingual"):
            assert rows[term]["status"] == V.GOVERNED and rows[term]["drawn"] is True, term
            assert f"{V.GOVERNED_CODE}:{term}" not in rec["codes"]
        assert rows["bilingual"]["evidence"] == ["product-name-ar"]
        # the motif is ON the lid now, in its window — not in a strip panel
        assert rec["motif"]["drawn"] and all(not e.endswith("LID_TOP") for e in rec["motif"]["evidence"])

    def test_the_concepts_finishes_land_on_the_face(self):
        from apps.ire import container_finishes as F
        doc, spec, _c = _face("89_A_PETAL_WINDOW")
        rows = {(r["finish"], r["target"]): r["state"]
                for r in F.apply(doc, spec["finish_assignments"], brand_metallic_hex="#C9A24B")["applied"]}
        assert rows[("foil", "ring")] == rows[("foil", "window")] == rows[("foil", "motif")] == F.APPLIED
        assert rows[("spot_uv", "window_interior")] == F.APPLIED
        assert rows[("foil", "lockup")] == F.REFUSED_NO_VECTOR_MASTER          # the lockup is a raster

    def test_a_front_form_keeps_the_ruled_front_and_its_default_hero(self):
        """The face is the compact's. Every front run — no face reading handed in — keeps §AU1's ruled front, and the
        strip skip defaults to the hero it always skipped."""
        import inspect
        from apps.ire import compose_container as C
        assert inspect.signature(C._surface_panels).parameters["hero_surface"].default == C.HERO_SURFACE == "BODY_FRONT"
        from apps.ire.front_hierarchy import ruled_front_hierarchy
        spec = cm.build_motif_spec(_PETAL_WINDOW, {}, ZONES, {})
        doc = compose_container_graph(
            build_backbone(ContainerProfile(archetype="bottle", height_mm=110, width_mm=40)),
            product_name="Focus", sku="S", native=True, zones=ZONES, logo_path="media/brand/logo.png",
            hierarchy_lines=ruled_front_hierarchy("Focus", descriptor="pressed powder compact"), motif_spec=spec)
        names = {n.name for n, _ in doc.walk()}
        assert "rule-front-single" in names and "product-name-ar" not in names and "frame-ring" not in names
        assert "face" not in (doc.metadata.get("concept_front") or {})


# ---------------------------------------------------------------------------------------------------------------
# §BH66(b) — THE RULE SITS BELOW THE NAME. OWNER RULED 2026-09-23 (OWNER_BLOCKER_CLEARANCE.md:23254, LIVE): "§W4 and
# §AU1 are three days apart and mine; the later governs, and §AU1 is the later. The code has been drawing it above for
# a month ... Move it." §AU1's order: "the product name; below it a single fine horizontal rule; below that exactly
# one supporting line of type."
# ---------------------------------------------------------------------------------------------------------------

def _ruled_bottle(name):
    from django.conf import settings
    from apps.ire.front_hierarchy import ruled_front_hierarchy
    from apps.pipeline.services import container_contract as cc
    prof = cc.build_inferred_profile("bottle", estimates={"body_width_mm": 40.0, "body_height_mm": 110.0})
    zones = cc.propose_zones(prof)
    spec = cm.build_motif_spec({"motif_signature": "a ribbon motif", "title": "T", "variation_id": "v"}, {}, zones,
                               prof)
    return compose_container_graph(
        build_backbone(ContainerProfile(archetype="bottle", width_mm=40, height_mm=110)),
        logo_path=settings.BRAND_LOGO_PATH, product_name=name, sku="S", native=True, zones=zones, motif_spec=spec,
        hierarchy_lines=ruled_front_hierarchy(name, descriptor="night repair oil"))


def _rule_and_runs(doc):
    """(the rule's y, the baseline of the name line nearest ABOVE it, the ink top of the supporting run nearest BELOW
    it) — read off the front the rule is drawn on, never another panel of the sheet."""
    from apps.ire.container_brand_usage import text_ink_top
    from apps.ire.graph import TextRun
    rule = [n for n, _ in doc.walk() if (n.name or "").endswith("rule-front-single")][0]
    rule_y = rule.segments[0].y
    runs = [n for n, _ in doc.walk() if isinstance(n, TextRun)]
    names = [r for r in runs if "product-name-hero" in (r.name or "") and r.y < rule_y]
    support = [r for r in runs if (r.name or "").endswith(("front-descriptor", "front-support")) and r.y > rule_y]
    nearest_name = max(names, key=lambda r: r.y)
    nearest_support = min(support, key=lambda r: r.y)
    return rule_y, nearest_name.y, text_ink_top(nearest_support.y, nearest_support.size_pt)


class TestTheRuleSitsBelowTheName:
    """§BH66(b) on every front §AU1 governs — the container composer's ruled front and the dropper's: the name's last
    baseline, then the rule, then the supporting line's ink. The tiers do not move for it."""

    @pytest.mark.parametrize("name", ["Rose Damascena", "Rose Nectar Lip Gloss"])
    def test_the_ruled_front_prints_the_name_then_the_rule_then_the_supporting_line(self, name):
        doc = _ruled_bottle(name)
        rule_y, name_baseline, support_top = _rule_and_runs(doc)
        assert name_baseline < rule_y < support_top          # a wrapped name: the rule after its LAST line
        assert _rule_widths(doc) == [0.30]                   # §AU2's weight, unchanged

    def test_the_dropper_front_prints_its_rule_below_the_name(self):
        from django.conf import settings
        from apps.ire.compose_dropper import compose_dropper_sheet
        from apps.ire.tests.test_back_panel import _FRONT_RECORD
        from apps.ire.tests.test_container_line_weight import _GEOMETRY
        # §BH67(c)2: the supporting line is the product record's now — handed in, as the production call does
        doc = compose_dropper_sheet(_GEOMETRY, zones=[{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE",
                                                       "x": 5.5, "y": 10.0, "width": 22.0, "height": 40.0}],
                                    reference_path=None, logo_path=settings.BRAND_LOGO_PATH,
                                    product_name="Rose Damascena", sku="X",
                                    back_sections=[{"heading": "P", "text": "x"}], revision_status="TEST",
                                    **_FRONT_RECORD)
        rule_y, name_baseline, support_top = _rule_and_runs(doc)
        assert name_baseline < rule_y < support_top

    def test_the_keep_out_is_sized_by_the_type_and_the_divider_is_recorded_where_the_rule_is(self):
        from apps.ire.container_brand_usage import evaluate_brand_usage
        doc = _ruled_bottle("Rose Damascena")
        assert evaluate_brand_usage(doc)["meets_clear_space"] is True        # the name still clears the mark
        rule_y, _b, _s = _rule_and_runs(doc)
        # the divider's box is a 0.04-high band centred on the DRAWN rule — never the retired `0.22 + shift / zh`
        front = [n for n, _ in doc.walk() if n.name == "FRONT_DIRECT_PRINT"][0]
        ys = [p.y for p in front.clip if hasattr(p, "y")]
        zy, zh = min(ys), max(ys) - min(ys)
        divider = [p for p in doc.metadata["placements"] if p["kind"] == "divider"][0]
        assert divider["nh"] == 0.04
        assert abs(divider["ny"] - round((rule_y - zy) / zh - 0.02, 3)) < 1e-9


class TestTheLockupTakesItsFoilWhenDrawnFromItsApprovedMaster:
    """THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803, the block headed "Before I start
    testing"): "When I approve the logo trace, switch the mark to it so gold foil can print." Handed an approved vector
    master — a SYNTHETIC fixture (apps/ire/tests/brand_mark_fixtures.py) — the lockup takes the concept's foil and its
    plate is cut from the master's outlines. The raster and "no lockup is drawn" stay refused, word for word."""

    RASTER_HOW = ("the lockup is placed as a raster (media/brand/logo.png, the controlled fallback until a vector "
                  "master exists) and a finish plate cannot be cut from a raster")

    def _front(self, master, logo_path="media/brand/logo.png"):
        structured = dict(_PETAL_WINDOW, finish_signature="BBROSE wordmark in rose-gold foil")
        spec = cm.build_motif_spec(structured, {}, ZONES, {})
        doc = compose_container_graph(
            build_backbone(ContainerProfile(archetype="bottle", height_mm=110, width_mm=40)),
            product_name="Focus Pressed Powder", sku="BBR-CO-2060", native=True, zones=ZONES,
            hierarchy_lines=[{"text": "Focus Pressed Powder", "rel": 1.0, "kind": "product_name"}],
            motif_spec=spec, logo_path=logo_path, logo_master=master)
        return doc, spec

    def test_the_foil_lands_on_the_lockup_and_its_plate_is_the_masters_outlines(self, tmp_path):
        import fitz
        import numpy as np

        from apps.ire import brand_mark as B
        from apps.ire import container_finishes as F
        from apps.ire.emitters.pdf_ai import emit_pdf_ai
        from apps.ire.tests import brand_mark_fixtures as FX
        master = B.read_master(FX.POTRACE_STYLE)
        doc, spec = self._front(master)
        result = F.apply(doc, spec["finish_assignments"], brand_metallic_hex="#C9A24B")
        lockup = [r for r in result["applied"] if r["target"] == "lockup"]
        assert [(r["finish"], r["plate"], r["state"], r["nodes"]) for r in lockup] == [
            ("foil", "FOIL_ROSE_GOLD", F.APPLIED, ["logo"])]
        assert not [c for c in result["codes"] if c.endswith(":lockup")]
        mark = next(n for n, _ in doc.walk() if n.name == "logo")
        assert B.is_mark(mark) and [f.plate for f in mark.finishes] == ["FOIL_ROSE_GOLD"]
        usage = {}
        out = emit_pdf_ai(doc, str(tmp_path / "foil.ai"), usage_out=usage)
        plates = usage[F.SCHEMA]["plates"]
        assert [(p["plate"], p["items"]) for p in plates] == [("FOIL_ROSE_GOLD", ["logo"])]
        with fitz.open(out) as pdf:
            pix = pdf[1].get_pixmap(dpi=600, alpha=True)
            cov = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[..., 3] / 255.0
        k = 600 / 25.4
        region = cov[int(mark.y * k):int((mark.y + mark.h) * k), int(mark.x * k):int((mark.x + mark.w) * k)]
        share = float(region.mean())
        assert abs(share - float(B.coverage(master, 400, margin=0).mean())) < 0.03   # the outlines' own share, 44.8 %
        assert share < 0.5                                                          # never the box

    def test_the_raster_and_the_absent_lockup_stay_refused_word_for_word(self):
        from apps.ire import container_finishes as F
        for logo_path, how in (("media/brand/logo.png", self.RASTER_HOW), (None, "no lockup is drawn")):
            doc, spec = self._front(None, logo_path=logo_path)
            rows = F.apply(doc, spec["finish_assignments"], brand_metallic_hex="#C9A24B")["applied"]
            assert [(r["state"], r["how"], r["nodes"]) for r in rows if r["target"] == "lockup"] == [
                (F.REFUSED_NO_VECTOR_MASTER, how, [])]

    def test_a_refused_approval_on_file_is_said_in_the_row_with_its_code(self):
        """[Review of 2026-09-25, §BH58(e).] A master and its approval ARE on file and the approval does not hold: the
        raster lockup's row says so with the approval's code — never "until a vector master exists", which would name
        a cause nobody measured — and carries the codes; the finish codes are the ones they always were. With no
        lockup drawn the row still says "no lockup is drawn", and still carries the refused approval."""
        from apps.ire import container_finishes as F
        refused = {"codes": ["BRAND_MARK_APPROVAL_INCOMPLETE"], "reason": "the owner's words are missing"}
        doc, spec = self._front(None)
        out = F.apply(doc, spec["finish_assignments"], brand_metallic_hex="#C9A24B", refused_approval=refused)
        [row] = [r for r in out["applied"] if r["target"] == "lockup"]
        assert (row["state"], row["nodes"], row["approval_refused"]) == (F.REFUSED_NO_VECTOR_MASTER, [], refused)
        assert row["how"] == ("the lockup is placed as a raster (media/brand/logo.png) because the brand-mark approval "
                              "on file is refused (BRAND_MARK_APPROVAL_INCOMPLETE: the owner's words are missing), "
                              "and a finish plate cannot be cut from a raster")
        assert "until a vector master exists" not in row["how"]
        plain_doc, plain_spec = self._front(None)
        plain = F.apply(plain_doc, plain_spec["finish_assignments"], brand_metallic_hex="#C9A24B")
        assert out["codes"] == plain["codes"]                       # the finish codes are unchanged
        assert f"CONTAINER_FINISH_{F.REFUSED_NO_VECTOR_MASTER}:foil:lockup" in out["codes"]
        [plain_row] = [r for r in plain["applied"] if r["target"] == "lockup"]
        assert "approval_refused" not in plain_row and plain_row["how"] == self.RASTER_HOW
        bare, bare_spec = self._front(None, logo_path=None)
        [none_drawn] = [r for r in F.apply(bare, bare_spec["finish_assignments"], brand_metallic_hex="#C9A24B",
                                           refused_approval=refused)["applied"] if r["target"] == "lockup"]
        assert (none_drawn["how"], none_drawn["approval_refused"]) == ("no lockup is drawn", refused)

    def test_on_the_lid_the_mark_keeps_its_clear_space_and_takes_its_foil(self):
        """Task 89's own lid, its concept verbatim: the face laid out round the mark drawn from the master; the brand-
        usage instrument measures the mark's clear space off its BOX — its own outlines are never an intrusion — and
        the concept's foil on the wordmark is APPLIED where the raster's was refused."""
        from apps.ire import brand_mark as B
        from apps.ire import concept_face as CFA
        from apps.ire import concept_front as CF
        from apps.ire import container_finishes as F
        from apps.ire.container_brand_usage import evaluate_brand_usage
        from apps.ire.front_hierarchy import ruled_front_hierarchy
        from apps.ire.tests import brand_mark_fixtures as FX
        master = B.read_master(FX.REG_STYLE)
        concept = dict(_FACE_CONCEPTS["89_A_PETAL_WINDOW"], verified=True, variation_id="A_PETAL_WINDOW",
                       title="89_A_PETAL_WINDOW")
        name, name_ar = _FACE_NAMES["89"]
        spec = cm.build_motif_spec(concept, {}, _LID_ZONE, {})
        plan = CF.plan(concept, spec, ground_hex="#FAF3EC", edge_hex="#F7DDE3")
        plan["face"] = dict(CFA.read(concept, layout=plan["layout"], has_arabic=True, product_name=name),
                            surface="LID_TOP", name_ar=name_ar)
        doc = compose_container_graph(
            build_backbone(ContainerProfile(archetype="compact", height_mm=95, width_mm=110)),
            product_name=name, sku="S", native=True, zones=_LID_ZONE, logo_path="media/brand/logo.png",
            hierarchy_lines=ruled_front_hierarchy(name, descriptor="pressed powder compact"),
            motif_spec=spec, colors={"body": "#B4A390", "cap": "#FAF3EC"}, concept_front=plan, logo_master=master)
        from apps.ire import container_logo_metrics as clm
        mark = next(n for n, _ in doc.walk() if n.name == "logo")
        assert B.is_mark(mark)
        # the face lays its boxes out at three decimals of a millimetre, the raster's as the master's (the raster's
        # deviation on this lid measured 4.6e-05); the instrument that owns distortion reads the master's aspect
        metrics = clm.measure_logo_metrics(doc)
        assert metrics["materially_distorted"] is False
        assert metrics["placements"][0]["intrinsic_aspect"] == round(master.aspect, 6)
        assert metrics["placements"][0]["aspect_deviation"] < 1e-4
        usage = evaluate_brand_usage(doc)
        assert usage["placements"][0]["cap_ratio"] == B.cap_band(master)["cap_ratio"]
        assert usage["meets_clear_space"] is True and usage["motif_strands_over_mark"] == 0
        rows = F.apply(doc, spec["finish_assignments"], brand_metallic_hex="#C9A24B")["applied"]
        assert [r["state"] for r in rows if r["target"] == "lockup"] == [F.APPLIED]
