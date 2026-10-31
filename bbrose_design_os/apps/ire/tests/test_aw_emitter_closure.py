"""§AW1 / §AU order 1(a)–(d) — the brand-string closure AT THE EMITTER.

WHY THESE TESTS ASSERT ON THE FILESYSTEM AND NOT ON THE EXCEPTION.
``test_av5_artefact_withheld.py:281`` already states the standard for this
family: "Asserts on the FILE FIELDS, not on the exception. Whether something
was thrown was never the issue; whether the owner could download it was." The
same standard applies one level down. An emitter that raises AFTER writing the
file has refused nothing, so every check here reads ``os.path.exists`` on the
target path after the call.

WHAT THIS COVERS THAT THE THREE §AV5 CALL-SITE GATES DID NOT. Those closed
``reconstruct_container`` and the two handoff services by hand and the tranche
declared the paths covered. An audit then found a FOURTH:
``dielines/services/export_service.py`` composes with ``product_name=`` and
writes an editable .ai at :280 and again at :337, and
``grep -rn brand_string apps/dielines/`` returned nothing at all. §AW1 ruled the
closure down to ``emit_pdf_ai`` because a list of call sites has to stay correct
forever, while a writer is one object every artefact passes through.

§AA — A GUARD NOBODY HAS SEEN FIRE IS NOT EVIDENCE. The chokepoint is INERT for
every document that carries no marker, which is every document in the rest of
this suite; that is what makes it safe to add and simultaneously means its
existence proves nothing. These tests exist to watch it refuse REAL composed
documents from the two composers that actually feed the unguarded paths.
"""
from __future__ import annotations

import os

import pytest

from apps.dielines.geometry.engine import calculate_dieline
from apps.dielines.validators.schema import DielineInputJSON
from apps.ire.brand_string_runtime import (
    BRAND_STRING_ARTEFACT_WITHHELD,
    MARKER,
    BrandStringRefusal,
    brand_string_report,
)
from apps.ire.compose_vector_art import VectorArtStyle, compose_vector_art_graph
from apps.ire.emitters.pdf_ai import emit_pdf_ai
from apps.ire.graph import Color, Document, Group, TextRun

_INFO = {"net_weight": "30 ml", "warnings": "For external use only."}


def _coords():
    return calculate_dieline(DielineInputJSON(
        template="skynte_foundation_tuck_carton", unit="mm",
        dimensions={"width_mm": 42.0, "depth_mm": 32.0, "height_mm": 140.0},
        print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
        construction={"glue_tab_mm": 10.0, "board_thickness_mm": 0.30,
                      "thickness_compensation": True},
        metadata={"product_name": "Skynte Foundation",
                  "product_type": "foundation"}))


def _vector_doc(product_name: str):
    """A document composed the way ``export_service.py:258`` composes one —
    the fourth path, through the ``product_name=`` argument it really uses."""
    return compose_vector_art_graph(
        _coords(), style=VectorArtStyle(), logo_path=None,
        product_name=product_name, subtitle="Silk Veil Fluid Foundation",
        panel_info=_INFO)


def _minimal_doc(text: str):
    """The smallest document that can carry printed copy. Used only where the
    question is about the EMITTER's ordering rather than about a composer."""
    run = TextRun(name="product-name", text=text, x=25.0, y=15.0,
                  size_pt=8.0, align="center",
                  color=Color(r=0.1, g=0.1, b=0.1))
    return Document(
        page_w=50.0, page_h=30.0, title="minimal",
        root=Group(name="Root", role="artwork",
                   children=[Group(name="Copy", role="typography",
                                   children=[run])]))


class TestTheEmitterRefusesAndWritesNothing:
    """§AU order 1(b) — watch it refuse a REAL violation."""

    def test_the_clean_document_still_emits(self, tmp_path):
        """The closure must not be a wall. A document with no provisional copy
        emits exactly as before — this is the regression half, and it is what
        makes the refusal below meaningful rather than universal."""
        doc = _vector_doc("Skynte Foundation")
        assert brand_string_report(doc)["clean"] is True
        out = str(tmp_path / "clean.ai")
        assert emit_pdf_ai(doc, out) == out
        assert os.path.exists(out)
        assert os.path.getsize(out) > 1000

    def test_the_fourth_path_refuses_and_leaves_no_file(self, tmp_path):
        """THE PATH THE AUDIT FOUND. A provisional descriptor arriving through
        the same ``product_name=`` argument ``export_service`` passes."""
        doc = _vector_doc(f"{MARKER} product name")
        report = brand_string_report(doc)
        assert report["clean"] is False, report

        out = str(tmp_path / "fourth_path.ai")
        with pytest.raises(BrandStringRefusal) as exc:
            emit_pdf_ai(doc, out)

        # The assertion that matters: the owner cannot download it.
        assert not os.path.exists(out)
        assert exc.value.code == BRAND_STRING_ARTEFACT_WITHHELD
        assert exc.value.artefact == "fourth_path.ai"

    def test_nothing_at_all_is_written_to_the_directory(self, tmp_path):
        """Not merely "the named file is absent" — reportlab writes its output
        in one pass at ``save()``, but a partial or differently-named artefact
        would still be an artefact. The directory stays empty."""
        with pytest.raises(BrandStringRefusal):
            emit_pdf_ai(_minimal_doc(f"{MARKER} name"),
                        str(tmp_path / "nothing.ai"))
        assert os.listdir(str(tmp_path)) == []


class TestTheClosureRunsBeforeAnythingElse:
    """§AW1 placed the call ahead of every byte, including the font
    registration that mutates a process-global reportlab registry."""

    def test_it_refuses_before_touching_the_filesystem(self, tmp_path):
        """Emitting into a directory that does not exist must raise the
        REFUSAL, not ``FileNotFoundError``. If the guard ran after the canvas
        was constructed this test would report the filesystem error instead,
        so it pins the ORDER rather than merely the presence of the check."""
        missing = str(tmp_path / "no_such_dir" / "x.ai")
        with pytest.raises(BrandStringRefusal):
            emit_pdf_ai(_minimal_doc(f"{MARKER} name"), missing)

    def test_a_clean_document_still_reaches_the_filesystem_error(self, tmp_path):
        """The control for the test above. Without the marker the same call
        must get PAST the guard and fail for the real reason — otherwise the
        test above would pass even if the guard refused everything."""
        missing = str(tmp_path / "no_such_dir" / "x.ai")
        with pytest.raises(Exception) as exc:
            emit_pdf_ai(_minimal_doc("a clean name"), missing)
        assert not isinstance(exc.value, BrandStringRefusal)


class TestTheRefusalIsVisibleToHandlersThatAlreadyExist:
    """A closure that escapes the handlers written against the old spelling
    fails closed by CRASHING, which §AV5 already paid for once."""

    def test_it_is_a_value_error_subclass(self, tmp_path):
        """``targets/container/__init__.py:1521`` raises a bare ``ValueError``
        carrying this code, and ``export_service.py:353`` catches broad
        ``Exception``. Both must see this."""
        with pytest.raises(ValueError):
            emit_pdf_ai(_minimal_doc(f"{MARKER} name"), str(tmp_path / "a.ai"))

    def test_the_message_names_the_code_and_the_offending_run(self, tmp_path):
        """``export_service.py:354`` logs ``str(exc)`` and nothing else, so
        everything a reader needs to diagnose this has to be in the message.
        A refusal that cannot say WHICH string stopped it is one somebody
        eventually switches off rather than diagnoses."""
        with pytest.raises(BrandStringRefusal) as exc:
            emit_pdf_ai(_minimal_doc(f"{MARKER} name"), str(tmp_path / "a.ai"))
        text = str(exc.value)
        assert text.startswith(BRAND_STRING_ARTEFACT_WITHHELD)
        assert "a.ai" in text
        assert exc.value.report["provisional_runs"], exc.value.report

    def test_the_report_survives_on_the_exception(self, tmp_path):
        """Carried as an object, not only formatted into a string, so a caller
        that has to persist the finding does not have to re-parse a message."""
        with pytest.raises(BrandStringRefusal) as exc:
            emit_pdf_ai(_minimal_doc(f"{MARKER} name"), str(tmp_path / "a.ai"))
        report = exc.value.report
        assert report["clean"] is False
        assert report["codes"]
        assert report["marker"] == MARKER
