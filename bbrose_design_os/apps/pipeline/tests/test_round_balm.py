"""Round 1 physical geometry and protected-pixel contracts (no providers)."""
import json
import numpy as np
import pytest
from PIL import Image


def test_one_complete_json_fence_allows_outside_notes_but_not_ambiguous_blocks():
    from apps.pipeline.services.round_calls import parse_response_text
    assert parse_response_text('```json\n{"eligible": false}\n```\nInspection notes.') == {'eligible':False}
    assert parse_response_text('Inspection notes.\n\n```json\n{"eligible": false}\n```') == {'eligible':False}
    for bad in ['```json\n{"eligible": false}', '```json\n{}\n```\n```json\n{}\n```', '{"a":1} trailing']:
        with pytest.raises(ValueError):parse_response_text(bad)


def pair(a,b,winner):return {'pair':[a,b],'winner':winner,'relationship':'The cap changes the bottom label reading.'}


