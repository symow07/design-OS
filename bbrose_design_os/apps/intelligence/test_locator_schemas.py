import pytest
from django.core.exceptions import ValidationError

from .locator_schemas import SCHEMAS, normalize_locator


def test_all_required_locator_schemas_are_explicit():
    assert set(SCHEMAS) == {
        "json_path/1.0", "jsonl_record/1.0", "file_page/1.0",
        "illustrator_artboard/1.0", "archive_member/1.0", "font_face/1.0",
        "source_file/1.0",
    }


def test_locator_normalization_and_bounds():
    assert normalize_locator("source_file/1.0", {"path": "materials/a.ai"}) == {
        "path": "materials/a.ai"}
    assert normalize_locator("json_path/1.0", {
        "path": "var/a.json", "segments": ["candidates", 2]}) == {
            "path": "var/a.json", "segments": ["candidates", 2]}
    assert normalize_locator("file_page/1.0", {"page": 0, "unit_key": "p0-u1"})


@pytest.mark.parametrize("schema,value", [
    ("source_file/1.0", {"path": "../secret"}),
    ("source_file/1.0", {"path": "/etc/passwd"}),
    ("json_path/1.0", {"path": "a.json", "segments": ["x"] * 33}),
    ("file_page/1.0", {"page": -1}),
    ("archive_member/1.0", {"archive_path": "a.zip", "member_path": "../x"}),
    ("font_face/1.0", {"face_index": True}),
    ("unknown/1.0", {}),
])
def test_locator_rejects_traversal_unbounded_and_unknown_values(schema, value):
    with pytest.raises(ValidationError):
        normalize_locator(schema, value)
