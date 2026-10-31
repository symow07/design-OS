"""§AV5 — the three §AU5(4)/§AU8(e) closures, WATCHED FIRING.

WHY THIS FILE EXISTS AND WHY IT IS NOT THE §AV3 FILE. ``test_av3_brand_string_
runtime.py`` asks whether ``brand_string_report`` DESCRIBES a document
correctly. That is a different question from the one §AU5(4) asks, which is
whether a described document can still reach an owner. §AV3 answered the first
and shipped believing it had answered the second: the .ai was written 72 lines
before the description was computed, so every §AV3 test passed while the
artefact went out anyway. A file that tests the reporter cannot notice that the
reporter is advisory.

THE ASSERTION THAT ACTUALLY PROVES A CLOSURE IS NOT THE RAISE.
It is ``THE WRITER WAS NEVER CALLED``. The defect being closed was an ORDERING
defect — verdict after artefact — and a test that only asserts "an exception was
raised" passes just as happily against the broken ordering, because the broken
ordering also raised, 105 lines later, having already written the file. So every
case here spies on the writer itself, and the container target case asserts on
what was ATTACHED to the output rather than on what was thrown.

EVERY GATE IS EXERCISED TWICE, AND THE SECOND RUN IS THE LOAD-BEARING ONE.
A gate that raises unconditionally would satisfy every refusal assertion in this
file. The clean-name runs are what distinguish a GATE from a BRICK: they prove
the closure keys on the marker, and that the writer is still reachable when the
copy is the owner's. Written after a real occurrence — the dieline gate's
missing import made that path raise ``NameError`` on EVERY invocation, clean
copy included. It "failed closed" by crashing. Only the clean-path run could
tell the difference, and it is the reason this file has one per gate.

WHY GATES 2 AND 3 USE STUBS AND GATE 1 USES THE DATABASE. Gates 2 and 3 are
module-level functions taking ``output`` as an ARGUMENT — they can be reached
with a plain object and no ORM, so they are, and they run in milliseconds.
``reconstruct_container`` is reached through ``begin_output`` and seeds its own
records; hand-building that spec sheet would be building a fixture that asserts
my belief about production rather than production. It reuses the existing
``ReconstructContainerCase``, which is seeded "exactly as production seeds
them — no hand-built spec sheet", per its own docstring.

WHAT THIS FILE DOES NOT COVER, STATED HERE RATHER THAN DISCOVERED LATER
(§Y2(c)).
* It does not prove there is no FOURTH path. Three were found by grepping for
  the shape; a fourth found the same way would need the same treatment.
* It does not test Illustrator execution. ``run_jsx`` is downstream of every
  gate here, and its non-execution follows from the writer never running.
* It says nothing about whether the DESCRIPTION is right — that is §AV3's file,
  and duplicating it here would give two places to change one idea (§AK3).
"""
from unittest import mock

import pytest
from django.test import SimpleTestCase, override_settings

from apps.ire.brand_string_runtime import (
    BRAND_STRING_ARTEFACT_WITHHELD,
    MARKER,
    brand_string_report,
)
from apps.pipeline.services.native_handoff import (
    HandoffError,
    generate_container_native_handoff,
    generate_native_handoff,
)
from apps.pipeline.targets.container import reconstruct_container

from .test_wif_reconstruct_container import CONFIRMED, ReconstructContainerCase

fitz = pytest.importorskip("fitz")

#: A descriptor the owner has NOT supplied, spelled the one way §AE3 spells it.
#: Built from the imported ``MARKER`` rather than from a literal, because a
#: second spelling of the token is the §AK3 defect this repository has already
#: paid for once, and a test carrying its own copy would keep passing after the
#: real token changed.
PROVISIONAL_NAME = f"{MARKER} Rose Serum"
CLEAN_NAME = "Rose Serum"

#: A well-formed confirmed zone. ``parent_surface`` is not a stylistic choice:
#: ``container_contract.zone_surface`` RAISES on the ``surface`` spelling, and
#: this fixture was written with the wrong one first and refused, which is that
#: contract guard doing its job.
ZONES = [{"zone_id": "front", "parent_surface": "front", "zone_type": "front",
          "x_mm": 2.0, "y_mm": 30.0, "width_mm": 31.0, "height_mm": 40.0,
          "confirmed": True}]


def _doc(name):
    """A composed container document whose product name is ``name``."""
    from apps.ire.compose_container import compose_container_graph
    from apps.pipeline.targets.container.silhouettes import (
        ContainerProfile, build_backbone)
    backbone = build_backbone(ContainerProfile(
        archetype="bottle", variant="cylindrical", width_mm=35.0,
        height_mm=110.0, neck_ratio=0.42, cap_style="screw"))
    return compose_container_graph(
        backbone, product_name=name, name_lines=[name] if name else [],
        zones=ZONES, native=True, colors={})


class _Spy:
    """A writer that records being reached and refuses to do any work.

    It raises rather than returning a stub because reaching it AT ALL is the
    condition under test on the provisional runs; a silent stub would let the
    function continue and turn one clear finding into a confusing traceback
    somewhere further down.
    """

    def __init__(self):
        self.called = False

    def __call__(self, *args, **kwargs):
        self.called = True
        raise AssertionError("the writer was reached")


class TheInputTests(SimpleTestCase):
    """Before any gate: does a provisional descriptor reach PRINTED TEXT?

    If it does not, every refusal below would be testing nothing, and would
    keep passing after the composer stopped printing the name at all. This is
    the case that keeps the rest of the file honest.
    """

    def test_a_provisional_descriptor_reaches_a_live_text_run(self):
        report = brand_string_report(_doc(PROVISIONAL_NAME))
        assert not report["clean"]
        assert any(MARKER in run["text"]
                   for run in report["provisional_runs"]), report

    def test_an_owner_supplied_descriptor_leaves_the_document_clean(self):
        report = brand_string_report(_doc(CLEAN_NAME))
        assert report["clean"], report["codes"]


class _StubTask:
    pk = 990001
    id = 990001
    #: §BH65(b)1 — the container handoff now reads `task.product` to derive the
    #: front descriptor from the product's own record. Every `DesignTask` carries
    #: a nullable `product`; a stub without the attribute is not a task. None is
    #: a task with no product, which derives no descriptor and prints nothing.
    product = None


class TheContainerHandoffClosureTests(SimpleTestCase):
    """§AU5(4) gate 2 — ``generate_container_native_handoff``.

    The worse of the two handoff leaks. ``build_container_handoff_package``
    WRITES the .jsx, manifest and assets into MEDIA_ROOT, and
    ``validate_container_handoff`` did not run until fourteen lines after that;
    with ``run_illustrator`` set, ``run_jsx`` EXECUTED the package before the
    validation it had not yet passed.
    """

    WRITER = ("apps.ire.handoff.container_adapter"
              ".build_container_handoff_package")

    def _output(self, name):
        class Out:
            task = _StubTask()
            approved_image = None
            spec_sheet = {
                "container_profile/1.0": {
                    "archetype": "bottle", "variant": "cylindrical",
                    "fields": {"body_width_mm": {"value": 35.0},
                               "body_height_mm": {"value": 110.0},
                               "neck_ratio": {"value": 0.42},
                               "cap_type": {"value": "screw"}}},
                "container_decoration_zones/1.0": {"zones": ZONES},
                "container_reconstruction": {"ok": True},
                "product_name": name,
                "colors": {},
            }
        return Out()

    def test_provisional_copy_is_refused_before_the_package_is_written(self):
        spy = _Spy()
        with mock.patch(self.WRITER, spy):
            with pytest.raises(HandoffError) as exc:
                generate_container_native_handoff(
                    self._output(PROVISIONAL_NAME), None)
        assert exc.value.code == BRAND_STRING_ARTEFACT_WITHHELD
        assert not spy.called, "the package writer ran despite the refusal"

    def test_nothing_is_written_under_media_root(self):
        """The assertion the ordering defect would have failed.

        Checked on the real configured MEDIA_ROOT rather than a tmpdir,
        because the leak was that the writer used the real one.

        [THE OWNER'S SECOND ANSWER OF 2026-09-25: under the suite the
        configured MEDIA_ROOT is the suite's own directory
        (config/settings.py), so "the real configured" root this reads is
        that one — still the root the writer resolves, which is what the
        check is about.]
        """
        import os

        from django.conf import settings
        out_dir = os.path.join(settings.MEDIA_ROOT, "container_handoff",
                               str(_StubTask.pk))
        with pytest.raises(HandoffError):
            generate_container_native_handoff(
                self._output(PROVISIONAL_NAME), None)
        assert not os.path.isdir(out_dir), out_dir

    def test_owner_supplied_copy_still_reaches_the_writer(self):
        """The load-bearing case: this gate is a gate, not a brick."""
        spy = _Spy()
        with mock.patch(self.WRITER, spy):
            with pytest.raises(AssertionError, match="the writer was reached"):
                generate_container_native_handoff(
                    self._output(CLEAN_NAME), None)
        assert spy.called


class TheDielineHandoffClosureTests(SimpleTestCase):
    """§AU5(4) gate 3 — ``generate_native_handoff``.

    Found by grepping for the SHAPE of the first two leaks rather than from the
    §AU order, which pointed at neither. Closed rather than filed because
    ``compose_vector_art_graph`` takes ``product_name`` and ``subtitle``
    straight into the document — measured, not assumed — so this path carries a
    provisional descriptor to a printable proof exactly like the other two.

    [E5b, the owner's Q2 (the clean-up list, transcribed at b5892f9): the package
    is the carton's own drawing — composed by ``compose_components_graph`` from
    its map front — which takes them the same way: with no panel copy the name
    is set on the back panel, so the gate still has a run to read.]
    """

    #: [E5b] a carton's map front — one band — as its record gives it
    FRONT = {"shapes": {"state": "TRACED", "source_sha256": "ab" * 32,
                        "params": {"version": "x"},
                        "bands": [{"part": "hot pink band", "fill": "#E82878",
                                   "edge_ink": None, "edge_width": 0.0, "edge": [],
                                   "outline": [[0.0, 0.0], [1.0, 0.0], [1.0, 0.2],
                                               [0.0, 0.2]], "drips": 0}]},
             "edge_part": None, "ground": "#FAF0E2"}

    WRITER = "apps.ire.handoff.package.build_handoff_package"

    def _output(self, name):
        from apps.dielines.services.provisional_preview import (
            build_provisional_params)
        params = build_provisional_params(
            inner_mm=(90.0, 32.0, 92.0), board_thickness_mm=0.5,
            product_name=name, product_type="serum carton")

        class Job:
            id = 990002
            pk = 990002
            input_json = params.model_dump()

        class Out:
            task = _StubTask()
            dieline_job = Job()
            approved_image = None
            spec_sheet = {}
        return Out()

    def _run(self, name, spy):
        # [E5b] the map front stood in at the package's own door (`carton_map_front`):
        # this file tests the gate, not the map's reading. The direction's style is
        # never reached — it raises if it is.
        with mock.patch(self.WRITER, spy), \
                mock.patch("apps.pipeline.services.native_handoff.carton_map_front",
                           return_value=self.FRONT), \
                mock.patch("apps.ire.compose_vector_art.compose_vector_art_graph",
                           side_effect=AssertionError("the direction's style drew it")):
            return generate_native_handoff(self._output(name), None)

    def test_provisional_copy_is_refused_before_the_package_is_written(self):
        spy = _Spy()
        with pytest.raises(HandoffError) as exc:
            self._run(PROVISIONAL_NAME, spy)
        assert exc.value.code == BRAND_STRING_ARTEFACT_WITHHELD
        assert not spy.called, "the package writer ran despite the refusal"

    def test_owner_supplied_copy_still_reaches_the_writer(self):
        """This case is why the missing import was found.

        The gate referenced ``brand_string_report`` without importing it into
        this function, so the path raised ``NameError`` on EVERY call. The
        refusal test above still passed — something was raised, the writer was
        still not reached. Only this case could tell a refusal from a crash.
        """
        spy = _Spy()
        with pytest.raises(AssertionError, match="the writer was reached"):
            self._run(CLEAN_NAME, spy)
        assert spy.called


@override_settings(OPENAI_API_KEY="")
class TheContainerTargetClosureTests(ReconstructContainerCase):
    """§AU5(4) gate 1 — ``reconstruct_container``.

    The original finding: ``emit_pdf_ai`` ran 72 lines before the brand-string
    report was computed and 105 before the fail-closed raise, and both files
    were attached to ``output`` and persisted. A BLOCKED reconstruction still
    shipped an editable .ai to ``review_board.py``'s ``editable_ai_url`` and to
    the composite's "Editable Design .ai" row.

    Asserts on the FILE FIELDS, not on the exception. Whether something was
    thrown was never the issue; whether the owner could download it was.
    """

    #: The manifest nests the two filenames under ``views``. Reaching through
    #: it explicitly rather than flattening: a test that asserted
    #: ``manifest["concept_sheet_ai"]`` would read ``None`` on a run that
    #: emitted perfectly well, and pass for the wrong reason on a blocked one.
    def _views(self, out):
        manifest = out.spec_sheet.get("container_native_output_manifest") or {}
        return manifest, (manifest.get("views") or {})

    def _provisional_product(self):
        """Rename the product BEFORE ``begin_output`` seeds the spec sheet.

        Ordering matters and cost a red test to learn: ``begin_output`` copies
        ``product.name`` into ``spec["product_name"]`` once, so renaming the
        Product afterwards leaves the composed document reading the OLD name.
        """
        self.product.name = PROVISIONAL_NAME
        self.product.save()

    def test_no_provisional_copy_reaches_the_editable_ai_and_the_design_goes_on(self):
        """[His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (1): "NO check ever stops a design."] The provisional
        line is left out of the drawing — no file carries the copy the owner did not supply (§AE2(c), unloosened) — and
        the design goes on with its files, the line said beside Approve. It withheld the files and stopped until then."""
        import fitz
        self._provisional_product()
        aria, out = self._at_the_profile_gate()
        reconstruct_container(aria, out, CONFIRMED)                      # never raised
        out.refresh_from_db()
        assert out.design_preview_ai, "the design went on, with its file"
        with fitz.open(out.design_preview_ai.path) as pdf:
            assert all(MARKER not in page.get_text() for page in pdf)
        rows = out.spec_sheet["checks_shown/1.0"]
        assert any(r["code"] == "BRAND_STRING_PROVISIONAL" and "never writes brand copy" in r["what"] for r in rows)

    def test_a_stale_artefact_from_an_earlier_run_is_removed(self):
        """A stale artefact is worse than no artefact.

        A prior clean run attaches a valid .ai; the name then goes
        provisional. Leaving the old file on the output would show the owner
        last week's proof under this week's verdict — the failure the gate
        exists to prevent, one step removed.
        """
        aria, out = self._at_the_profile_gate()
        reconstruct_container(aria, out, CONFIRMED)
        out.refresh_from_db()
        assert out.design_preview_ai, "fixture precondition: a clean run emits"
        stale = out.design_preview_ai.name

        # The SAME output, re-run after the copy goes provisional. Mutating the
        # seeded spec rather than the Product because that is where the
        # composer reads from, and because reusing this output is the whole
        # scenario: a stale artefact is one an EARLIER run of this record left
        # behind.
        spec = out.spec_sheet
        spec["product_name"] = PROVISIONAL_NAME
        out.spec_sheet = spec
        out.save()

        reconstruct_container(aria, out, CONFIRMED)
        out.refresh_from_db()
        # [his goal of 2026-10-13, (1)] drawn again without the provisional line: never last week's proof left standing
        assert out.design_preview_ai and out.design_preview_ai.name != stale, (
            f"the stale artefact {stale} survived the run")

    def test_the_manifest_names_the_files_written_with_the_line_left_out(self):
        """The manifest must name the files that were written, and nothing withheld.

        ``container_native_output_manifest`` reported ``concept_sheet_ai``
        unconditionally. [His goal of 2026-10-13, (1)] the files are written now,
        the provisional line left out of them and kept on the brand-string record.
        """
        self._provisional_product()
        aria, out = self._at_the_profile_gate()
        reconstruct_container(aria, out, CONFIRMED)
        out.refresh_from_db()
        # [his goal of 2026-10-13, (1)] nothing withheld: the line is left out of the drawing, the files made and named
        manifest, views = self._views(out)
        assert views.get("concept_sheet_ai"), views
        assert not manifest.get("artefact_withheld"), manifest
        spec = out.spec_sheet
        assert spec["container_brand_strings/1.0"]["clean"] is True
        assert [r["tier"] for r in spec["container_brand_strings/1.0"]["left_out"]]

    def test_owner_supplied_copy_still_produces_the_editable_ai(self):
        """The load-bearing case, and the one that would catch over-blocking.

        The fixture's product name is the owner's, so a correct gate is
        invisible here — which is the point. If this goes red, the closure has
        started withholding artefacts it has no business withholding.
        """
        aria, out = self._at_the_profile_gate()
        reconstruct_container(aria, out, CONFIRMED)
        out.refresh_from_db()
        assert out.design_preview_ai, "the clean path stopped emitting the .ai"
        manifest, views = self._views(out)
        assert views.get("concept_sheet_ai"), views
        assert not manifest.get("artefact_withheld"), manifest
