"""Real generic media steps with deterministic fake providers, no design inputs."""
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image, ImageDraw


def test_ideas_contract_generic_gloss_palette_and_unknown_measurements():
    from apps.pipeline.services.round_designer import SCHEMA, gloss_brief, normalize_ideas_brief, printed_copy
    gloss = gloss_brief()
    assert gloss['stand']['count'] == 12 and gloss['stand']['provisional']
    assert gloss['measurements_provisional'] and gloss['dimensions_mm']['cap_height'] == 30
    palette = normalize_ideas_brief({'schema': SCHEMA, 'name': 'Pressed palette', 'product_type': 'Palette',
        'material': 'Metal case', 'stand': {'count': 6}, 'copy': {'brand': 'BBROSE', 'product': 'Colour'},
        'panels': [{'id': 'do-not-use'}], 'copy_instruction': 'NEVER PRINT THIS',
        'content_roles': {'material': 'COPY'}, 'truths': ['A hinged compact holds pressed powder.']})
    assert palette['dimensions_mm'] == {} and palette['stand']['dimensions_mm'] == {}
    assert 'panels' not in palette and 'content_roles' not in palette
    assert printed_copy(palette) == {'brand': 'BBROSE', 'product': 'Colour', 'shade_names': []}
    for brief in (gloss, palette):
        assert normalize_ideas_brief(brief) == brief
    for number in (-1, 0, float('nan'), float('inf'), True):
        with pytest.raises(ValueError, match='positive'):
            normalize_ideas_brief(dict(palette, dimensions_mm={'width': number}))


