"""Reference upload validation — the one place that knows about files.

Every format decision lives here: the size limit, the extension allowlist, the
signature table and the filename strategy. The model, the view, the tests and
(later) the rendered UI all read from this module, so the numbers cannot drift
apart across five files.

Two things this module is careful NOT to claim. Signature detection establishes
that a file belongs to the permitted reference class; it does not establish
that the file is safe production artwork, and nothing here upgrades a reference
into a specification. And a browser-supplied Content-Type is never trusted: the
detected type comes from the bytes.
"""
from __future__ import annotations

import os
import re
import unicodedata
import uuid
from dataclasses import dataclass, field

from django.conf import settings

# --------------------------------------------------------------------------
# Configuration — one authoritative limit
# --------------------------------------------------------------------------
#: Per-file ceiling. 20 MB comfortably holds a layered .ai or a print-resolution
#: photograph while keeping a single request bounded. Override in settings.
DEFAULT_MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def max_upload_bytes() -> int:
    """The configured per-file limit. Read this; never copy the number."""
    return int(getattr(settings, "REFERENCE_MAX_UPLOAD_BYTES",
                       DEFAULT_MAX_UPLOAD_BYTES))


def max_upload_mb() -> float:
    return round(max_upload_bytes() / (1024 * 1024), 1)


STORAGE_ROOT = "task_refs"

MEDIA_PNG = "image/png"
MEDIA_JPEG = "image/jpeg"
MEDIA_WEBP = "image/webp"
MEDIA_PDF = "application/pdf"
MEDIA_PS = "application/postscript"
MEDIA_AI = "application/vnd.adobe.illustrator"

#: extension -> the detected types that extension may legitimately carry.
#: `.ai` is the interesting one: Illustrator writes both PDF-based and
#: PostScript-based documents under the same extension, and both are real.
ALLOWED = {
    ".png": {MEDIA_PNG},
    ".jpg": {MEDIA_JPEG},
    ".jpeg": {MEDIA_JPEG},
    ".webp": {MEDIA_WEBP},
    ".pdf": {MEDIA_PDF},
    ".eps": {MEDIA_PS, MEDIA_AI},
    ".ai": {MEDIA_PDF, MEDIA_PS, MEDIA_AI},
}

ALLOWED_EXTENSIONS = sorted(ALLOWED)

#: Explicitly named so the refusal is a decision, not an accident of the
#: allowlist. SVG is excluded because it is a script-bearing document format.
EXPLICITLY_REJECTED = {
    ".svg": "SVG can carry script and is not supported for references",
    ".exe": "executable", ".dll": "executable", ".so": "executable",
    ".sh": "shell script", ".bat": "shell script", ".ps1": "shell script",
    ".js": "script", ".mjs": "script",
    ".html": "HTML document", ".htm": "HTML document",
    ".zip": "archive", ".tar": "archive", ".gz": "archive",
    ".rar": "archive", ".7z": "archive",
    ".docm": "macro-enabled office file", ".xlsm": "macro-enabled office file",
    ".pptm": "macro-enabled office file",
}

# error codes, for the UI to render later
TOO_LARGE = "REFERENCE_FILE_TOO_LARGE"
EXT_NOT_ALLOWED = "REFERENCE_EXTENSION_NOT_ALLOWED"
SIGNATURE_INVALID = "REFERENCE_SIGNATURE_INVALID"
TYPE_MISMATCH = "REFERENCE_EXTENSION_TYPE_MISMATCH"
FILENAME_INVALID = "REFERENCE_FILENAME_INVALID"
CATEGORY_INVALID = "REFERENCE_CATEGORY_INVALID"
STORAGE_FAILED = "REFERENCE_STORAGE_FAILED"
EMPTY_FILE = "REFERENCE_FILE_EMPTY"

_SNIFF = 1024


def detect_media_type(head: bytes) -> str | None:
    """The type the BYTES say it is. Never the browser's Content-Type."""
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return MEDIA_PNG
    if head.startswith(b"\xff\xd8\xff"):
        return MEDIA_JPEG
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return MEDIA_WEBP
    if head.startswith(b"%PDF-"):
        return MEDIA_PDF
    if head.startswith(b"%!PS-Adobe"):
        # An Illustrator EPS says so in its own header. When it does not, keep
        # the container type rather than inventing Illustrator certainty.
        if b"Illustrator" in head[:_SNIFF]:
            return MEDIA_AI
        return MEDIA_PS
    return None


def sanitise_filename(name: str) -> str:
    """A safe, human-readable record of what the user called the file.

    This value is for display and audit only — it never becomes the storage
    identity, so it cannot influence where anything is written.
    """
    if not name:
        return ""
    # take the basename under BOTH separators: a Windows client can send
    # backslashes that posixpath would happily keep
    name = name.replace("\\", "/").split("/")[-1]
    name = unicodedata.normalize("NFKD", name)
    name = name.replace("\x00", "")
    name = re.sub(r"[^\w.\- ]", "_", name).strip(" .")
    name = re.sub(r"\.{2,}", ".", name)
    return name[:120]


def stored_name(extension: str) -> str:
    """Storage identity, generated independently of anything the user sent."""
    return f"{STORAGE_ROOT}/{uuid.uuid4().hex}{extension}"


@dataclass
class Rejection:
    code: str
    message: str
    filename: str = ""
    category: str = ""
    # Position of the file within its CATEGORY, counting every file sent for
    # that category in multipart order. Duplicate filenames are legal, so the
    # client must never correlate an error by name alone — category plus this
    # index identifies exactly one staged entry (B4b-2B §10).
    file_index: int = -1


@dataclass
class Accepted:
    category: str
    upload: object
    original_filename: str
    media_type: str
    file_size: int
    extension: str
    ordering: int = 0


@dataclass
class Outcome:
    accepted: list = field(default_factory=list)
    rejections: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.rejections


def _extension(name: str) -> str:
    return os.path.splitext(name or "")[1].lower()


def validate_file(upload, category: str, valid_categories) -> tuple:
    """Validate one upload. Returns (Accepted | None, Rejection | None)."""
    raw = getattr(upload, "name", "") or ""
    safe = sanitise_filename(raw)

    if category not in valid_categories:
        return None, Rejection(CATEGORY_INVALID,
                               f"'{category}' is not a reference category.",
                               safe, category)
    if not safe:
        return None, Rejection(FILENAME_INVALID,
                               "That file has no usable filename.",
                               raw, category)

    size = getattr(upload, "size", None)
    if size is None:
        size = upload.seek(0, os.SEEK_END) or upload.tell()
        upload.seek(0)
    if size == 0:
        return None, Rejection(EMPTY_FILE, f"{safe} is empty.", safe, category)
    if size > max_upload_bytes():
        return None, Rejection(
            TOO_LARGE,
            f"{safe} is larger than the {max_upload_mb()} MB limit.",
            safe, category)

    ext = _extension(safe)
    if ext in EXPLICITLY_REJECTED:
        return None, Rejection(
            EXT_NOT_ALLOWED,
            f"{safe} is a {EXPLICITLY_REJECTED[ext]} and cannot be used as a "
            "reference.", safe, category)
    if ext not in ALLOWED:
        return None, Rejection(
            EXT_NOT_ALLOWED,
            f"{safe} is not a supported reference file. Supported: "
            + ", ".join(ALLOWED_EXTENSIONS) + ".", safe, category)

    upload.seek(0)
    head = upload.read(_SNIFF)
    upload.seek(0)
    detected = detect_media_type(head)
    if detected is None:
        return None, Rejection(
            SIGNATURE_INVALID,
            f"{safe} does not look like a {ext} file inside.", safe, category)
    if detected not in ALLOWED[ext]:
        return None, Rejection(
            TYPE_MISMATCH,
            f"{safe} is named {ext} but its contents are {detected}.",
            safe, category)

    return Accepted(category=category, upload=upload, original_filename=safe,
                    media_type=detected, file_size=int(size),
                    extension=ext), None


def validate_all(files_by_category, valid_categories) -> Outcome:
    """Validate EVERY file before anything is written.

    All-or-nothing on purpose: accepting the good files and quietly dropping a
    sibling would leave the user with a task they think has five references and
    which actually has four.
    """
    out = Outcome()
    order = 0
    for category, uploads in files_by_category:
        for index, upload in enumerate(uploads):
            ok, bad = validate_file(upload, category, valid_categories)
            if bad:
                bad.file_index = index
                out.rejections.append(bad)
            else:
                ok.ordering = order
                order += 1
                out.accepted.append(ok)
    return out


def error_payload(outcome: Outcome, form_text: dict | None = None) -> dict:
    """A precise, renderable refusal that keeps the user's typing."""
    return {
        "error": "REFERENCE_VALIDATION_FAILED",
        "message": "No task was created. Fix the files below and submit again.",
        "rejections": [
            {"code": r.code, "message": r.message, "filename": r.filename,
             "category": r.category, "file_index": r.file_index}
            for r in outcome.rejections],
        "accepted_count": len(outcome.accepted),
        "task_created": False,
        "references_created": 0,
        # section 7: valid form text survives a rejection
        "preserved": form_text or {},
        "limits": {"max_file_bytes": max_upload_bytes(),
                   "max_file_mb": max_upload_mb(),
                   "allowed_extensions": ALLOWED_EXTENSIONS},
    }
