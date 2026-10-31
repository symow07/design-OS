"""Back-panel translation service EN -> ES + AR (2026-07-07)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from apps.pipeline.services.panel_translate import translate_panel_info

_INFO = {
    "product_name": "BBROSE Amber Hour Eyeshadow Palette",
    "description": "A 9-shade warm neutral eyeshadow palette.",
    "ingredients": "MICA, TALC, CI 77491.",
    "how_to_use": "Apply with a brush.",
    "warnings": "For external use only.",
    "barcode_ean": "5061030633823",     # non-translatable, must not be sent
}


def _claude_response(json_data):
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(json_data, ensure_ascii=False)
    resp = MagicMock()
    resp.content = [block]
    return resp


class TranslatePanelInfoTests(SimpleTestCase):
    def test_disabled_under_pytest_returns_empty(self):
        # settings.py forces PANEL_TRANSLATE_ENABLED=False under pytest
        assert translate_panel_info(_INFO) == {}

    @override_settings(PANEL_TRANSLATE_ENABLED=True, ANTHROPIC_API_KEY="k")
    @patch("apps.pipeline.services.claude_service.call_claude")
    def test_translates_both_languages(self, mock_claude):
        mock_claude.return_value = _claude_response({
            "es": {"description": "Paleta de sombras de 9 tonos.",
                   "warnings": "Solo para uso externo."},
            "ar": {"description": "باليت ظلال عيون من 9 درجات.",
                   "warnings": "للاستعمال الخارجي فقط."},
        })
        result = translate_panel_info(_INFO)
        assert set(result) == {"es", "ar"}
        assert result["es"]["description"].startswith("Paleta")
        assert "ظلال" in result["ar"]["description"]
        # only translatable keys were sent, codes stayed home
        sent = mock_claude.call_args.args[1]
        assert "5061030633823" not in sent
        assert mock_claude.call_args.kwargs["operation"] == "panel_translation"

    @override_settings(PANEL_TRANSLATE_ENABLED=True, ANTHROPIC_API_KEY="k")
    @patch("apps.pipeline.services.claude_service.call_claude")
    def test_unknown_keys_and_bad_shapes_dropped(self, mock_claude):
        mock_claude.return_value = _claude_response({
            "es": {"description": "Bien.", "barcode_ean": "999", "junk": 3},
            "ar": "not a dict",
            "fr": {"description": "non"},
        })
        result = translate_panel_info(_INFO)
        assert result == {"es": {"description": "Bien."}}

    @override_settings(PANEL_TRANSLATE_ENABLED=True, ANTHROPIC_API_KEY="k")
    @patch("apps.pipeline.services.claude_service.call_claude")
    def test_model_failure_degrades_to_empty(self, mock_claude):
        mock_claude.side_effect = RuntimeError("api down")
        assert translate_panel_info(_INFO) == {}

    @override_settings(PANEL_TRANSLATE_ENABLED=True, ANTHROPIC_API_KEY="k")
    def test_nothing_translatable_makes_no_call(self):
        with patch("apps.pipeline.services.claude_service.call_claude") as m:
            assert translate_panel_info({"barcode_ean": "5061030633823"}) == {}
            m.assert_not_called()
