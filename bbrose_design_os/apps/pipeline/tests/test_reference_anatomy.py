"""Deep reference anatomy study + injection (2026-07-07)."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.core.models import Brand, DesignReference, Product
from apps.pipeline.models import DesignTask
from apps.pipeline.services.reference_index import (
    analyze_reference_anatomy,
    anatomy_digest,
    select_reference_records,
)

_ANATOMY = {
    "layout": {"logo_position": "upper third, centered",
               "logo_scale": "60% of panel width",
               "title_treatment": "serif caps under the mark",
               "composition_grid": "engraved roses frame the wordmark"},
    "typography": {"case": "UPPERCASE", "weights": ["bold"],
                   "serif_sans": "serif", "hierarchy": "logo, name, type"},
    "motifs": [{"element": "line-engraved rose",
                "placement": "corner clusters", "style": "single-weight etching"}],
    "palette_hex": ["#EFE9E4", "#8B5A3C"],
    "finishes": ["gold foil"],
    "back_panel": {"sticker_frame": True, "trilingual": True,
                   "barcode_placement": "bottom left", "blocks": ["title", "desc"]},
}


def _claude_response(json_data):
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(json_data, ensure_ascii=False)
    resp = MagicMock()
    resp.content = [block]
    return resp


class AnatomyStudyTests(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, True)
        (Path(self.media) / "r1.png").write_bytes(b"\x89PNG fake")
        self.ref = DesignReference.objects.create(
            name="r1", image_path="r1.png", category="CO",
            product_type="lip gloss", tags=["rose"], summary="x",
        )

    @patch("apps.pipeline.services.claude_service.call_claude")
    def test_anatomy_saved(self, mock_claude):
        mock_claude.return_value = _claude_response(_ANATOMY)
        with self.settings(MEDIA_ROOT=self.media, ANTHROPIC_API_KEY="k"):
            assert analyze_reference_anatomy(self.ref) is True
        self.ref.refresh_from_db()
        assert self.ref.anatomy["motifs"][0]["element"] == "line-engraved rose"
        assert mock_claude.call_args.kwargs["operation"] == "reference_anatomy"

    @patch("apps.pipeline.services.claude_service.call_claude")
    def test_failure_leaves_anatomy_empty(self, mock_claude):
        mock_claude.side_effect = RuntimeError("down")
        with self.settings(MEDIA_ROOT=self.media, ANTHROPIC_API_KEY="k"):
            assert analyze_reference_anatomy(self.ref) is False
        self.ref.refresh_from_db()
        assert self.ref.anatomy == {}

    def test_digest_is_capped_and_numbered(self):
        self.ref.anatomy = _ANATOMY
        digest = anatomy_digest([self.ref], max_chars=300)
        assert digest.startswith("reference 1 (lip gloss):")
        assert len(digest) <= 360
        refs_no_anatomy = [self.ref, DesignReference(name="r2")]
        assert "reference 2" not in anatomy_digest(refs_no_anatomy)


class AnatomyInjectionTests(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, True)
        (Path(self.media) / "r1.png").write_bytes(b"\x89PNG fake")
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.product = Product.objects.create(
            brand=self.brand, product_id="CO-1", name="Silk Gloss",
            category="CO", year=2026, product_type="lip gloss")
        self.task = DesignTask.objects.create(
            brand=self.brand, product=self.product,
            task_text="lip gloss carton", status="running")
        DesignReference.objects.create(
            name="r1", image_path="r1.png", category="CO",
            product_type="lip gloss", tags=["rose"], summary="x",
            anatomy=_ANATOMY,
        )

    def test_select_reference_records_returns_rows(self):
        with self.settings(MEDIA_ROOT=self.media):
            rows = select_reference_records(self.task, 2)
        assert rows and rows[0].anatomy["finishes"] == ["gold foil"]

    @patch("apps.pipeline.agents.prompt_engineer.call_claude")
    def test_prompt_engineer_receives_house_vocabulary(self, mock_claude):
        from apps.pipeline.agents.prompt_engineer import PromptEngineerAgent
        mock_claude.return_value = _claude_response({"prompts": []})
        PromptEngineerAgent([{"name": "d"}], None,
                            reference_anatomy=_ANATOMY).run()
        sent = mock_claude.call_args.args[1]
        assert "House composition vocabulary" in sent
        assert "line-engraved rose" in sent

    @patch("apps.pipeline.agents.creative_director.call_claude")
    def test_creative_director_receives_anatomy_digest(self, mock_claude):
        from apps.pipeline.agents.creative_director import CreativeDirectorAgent
        mock_claude.return_value = _claude_response({"directions": []})
        with self.settings(MEDIA_ROOT=self.media):
            CreativeDirectorAgent(self.task, self.brand.id).run()
        content = mock_claude.call_args_list[0].args[1]
        # content is blocks (images + final text block)
        text = content[-1]["text"] if isinstance(content, list) else content
        assert "Measured anatomy of the attached references" in text
        assert "corner clusters" in text
