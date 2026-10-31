"""Bounded, non-executable evidence locator schemas for the DIP-1B MVP."""
from __future__ import annotations

import re
from pathlib import PurePosixPath

from django.core.exceptions import ValidationError

MAX_PATH = 1024
MAX_TEXT = 255
MAX_SEGMENTS = 32
MAX_INDEX = 1_000_000
_WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[/\\]")


def _bounded_text(value, name, *, maximum=MAX_TEXT):
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValidationError(f"{name} must be a non-empty string of at most {maximum} chars")
    if "\x00" in value:
        raise ValidationError(f"{name} contains a null byte")
    return value


def normalize_relative_path(value):
    value = _bounded_text(value, "path", maximum=MAX_PATH).replace("\\", "/")
    if value.startswith("/") or _WINDOWS_ABSOLUTE.match(value):
        raise ValidationError("absolute paths are not permitted")
    parts = PurePosixPath(value).parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise ValidationError("path traversal or ambiguous path components are not permitted")
    normalized = PurePosixPath(*parts).as_posix()
    if len(normalized) > MAX_PATH:
        raise ValidationError("normalized path is too long")
    return normalized


def _index(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_INDEX:
        raise ValidationError(f"{name} must be an integer from 0 to {MAX_INDEX}")
    return value


def _keys(locator, allowed, required):
    if not isinstance(locator, dict):
        raise ValidationError("locator must be an object")
    unknown = set(locator) - set(allowed)
    missing = set(required) - set(locator)
    if unknown or missing:
        raise ValidationError(
            f"invalid locator keys; missing={sorted(missing)}, unknown={sorted(unknown)}")


def _source_file(locator):
    _keys(locator, {"path"}, {"path"})
    return {"path": normalize_relative_path(locator["path"])}


def _file_page(locator):
    _keys(locator, {"page", "unit_key"}, {"page"})
    result = {"page": _index(locator["page"], "page")}
    if "unit_key" in locator:
        result["unit_key"] = _bounded_text(locator["unit_key"], "unit_key")
    return result


def _illustrator_artboard(locator):
    _keys(locator, {"artboard", "unit_key"}, {"artboard"})
    result = {"artboard": _index(locator["artboard"], "artboard")}
    if "unit_key" in locator:
        result["unit_key"] = _bounded_text(locator["unit_key"], "unit_key")
    return result


def _json_path(locator):
    _keys(locator, {"path", "segments"}, {"path", "segments"})
    segments = locator["segments"]
    if not isinstance(segments, list) or len(segments) > MAX_SEGMENTS:
        raise ValidationError(f"segments must be a list of at most {MAX_SEGMENTS} values")
    normalized = []
    for value in segments:
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise ValidationError("JSON path segments must be strings or nonnegative integers")
        normalized.append(_index(value, "segment") if isinstance(value, int)
                          else _bounded_text(value, "segment"))
    return {"path": normalize_relative_path(locator["path"]), "segments": normalized}


def _jsonl_record(locator):
    _keys(locator, {"path", "line", "record_key"}, {"path", "line"})
    line = _index(locator["line"], "line")
    if line == 0:
        raise ValidationError("JSONL line numbers are one-based")
    result = {"path": normalize_relative_path(locator["path"]), "line": line}
    if "record_key" in locator:
        result["record_key"] = _bounded_text(locator["record_key"], "record_key")
    return result


def _archive_member(locator):
    _keys(locator, {"archive_path", "member_path"}, {"archive_path", "member_path"})
    return {"archive_path": normalize_relative_path(locator["archive_path"]),
            "member_path": normalize_relative_path(locator["member_path"])}


def _font_face(locator):
    _keys(locator, {"face_index", "face_id"}, {"face_index"})
    result = {"face_index": _index(locator["face_index"], "face_index")}
    if "face_id" in locator:
        result["face_id"] = _bounded_text(locator["face_id"], "face_id")
    return result


SCHEMAS = {
    "source_file/1.0": _source_file,
    "file_page/1.0": _file_page,
    "illustrator_artboard/1.0": _illustrator_artboard,
    "json_path/1.0": _json_path,
    "jsonl_record/1.0": _jsonl_record,
    "archive_member/1.0": _archive_member,
    "font_face/1.0": _font_face,
}


def normalize_locator(schema_version, locator):
    if schema_version == "1":
        # The DIP-1B-1 generic structured locator remains readable; new imports use the
        # explicit schemas above. This compatibility branch does not accept expressions.
        from .models import _validate_locator
        _validate_locator(locator)
        return locator
    try:
        normalizer = SCHEMAS[schema_version]
    except KeyError as exc:
        raise ValidationError(f"unknown locator schema {schema_version!r}") from exc
    return normalizer(locator)
