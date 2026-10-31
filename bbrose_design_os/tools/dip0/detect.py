"""Slice 2 — format detection by magic bytes, with MIME + mismatch reporting.

Signature beats extension. `.ai` is the decisive case: modern Illustrator files
are PDF-wrapped (deep-parseable via PyMuPDF) while legacy ones are raw
PostScript (they are not) — the extension cannot tell them apart, so DIP-0B's
parser choice depends on `signature_kind`, never on the filename.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from . import config as C
from .provenance import Inferred

HEAD_BYTES = 64

# (kind, mime) keyed by a predicate over the first HEAD_BYTES.
_SIG_MIME = {
    "pdf": "application/pdf",
    "postscript": "application/postscript",
    "eps_binary": "image/x-eps",
    "psd": "image/vnd.adobe.photoshop",
    "png": "image/png",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "tiff": "image/tiff",
    "gif": "image/gif",
    "avif": "image/avif",
    "zip": "application/zip",
    "sfnt_otf": "font/otf",
    "sfnt_ttf": "font/ttf",
    "ttc": "font/collection",
    "woff": "font/woff",
    "woff2": "font/woff2",
    "mz_exe": "application/x-msdownload",
    "mp4": "video/mp4",
    "svg_xml": "image/svg+xml",
    "unknown": "application/octet-stream",
}

# Extensions whose container format legitimately differs from the payload,
# so a signature/extension divergence is expected and must not raise a warning.
_CONTAINER_OK = {
    ".xlsx": {"zip"}, ".xls": {"zip", "unknown"}, ".docx": {"zip"},
    ".ai": {"pdf", "postscript", "eps_binary"},
    ".eps": {"postscript", "eps_binary"},
    ".svg": {"svg_xml", "unknown"},
    ".ase": {"unknown"},
    ".url": {"unknown"}, ".txt": {"unknown"}, ".md": {"unknown"},
    ".html": {"unknown", "svg_xml"}, ".htm": {"unknown", "svg_xml"},
    ".xml": {"svg_xml", "unknown"},
    ".fon": {"mz_exe", "unknown"},
    ".db": {"unknown"},
    ".woff": {"woff"}, ".woff2": {"woff2"},
    ".ttc": {"ttc"}, ".otf": {"sfnt_otf", "sfnt_ttf"}, ".ttf": {"sfnt_ttf", "sfnt_otf"},
    ".jpg": {"jpeg"}, ".jpeg": {"jpeg"}, ".tif": {"tiff"}, ".tiff": {"tiff"},
    ".mov": {"mp4", "unknown"},
}


def sniff(head: bytes) -> str:
    """Classify by magic bytes. Order matters: longest/most specific first."""
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"\xc5\xd0\xd3\xc6"):     # DOS binary EPS wrapper
        return "eps_binary"
    if head.startswith(b"%!PS"):
        return "postscript"
    if head.startswith(b"8BPS"):
        return "psd"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "webp"
    if head.startswith(b"II*\x00") or head.startswith(b"MM\x00*"):
        return "tiff"
    if head.startswith(b"GIF8"):
        return "gif"
    if head[4:8] == b"ftyp":
        return "avif" if head[8:12] in (b"avif", b"avis") else "mp4"
    if head.startswith(b"PK\x03\x04") or head.startswith(b"PK\x05\x06"):
        return "zip"
    if head.startswith(b"OTTO"):
        return "sfnt_otf"
    if head.startswith(b"\x00\x01\x00\x00") or head.startswith(b"true"):
        return "sfnt_ttf"
    if head.startswith(b"ttcf"):
        return "ttc"
    if head.startswith(b"wOFF"):
        return "woff"
    if head.startswith(b"wOF2"):
        return "woff2"
    if head.startswith(b"MZ"):
        return "mz_exe"
    stripped = head.lstrip()
    if stripped.startswith(b"<?xml") or stripped.startswith(b"<svg"):
        return "svg_xml"
    return "unknown"


def read_head(path: Path, n: int = HEAD_BYTES) -> bytes:
    try:
        with open(path, "rb") as f:
            return f.read(n)
    except OSError:
        return b""


def _file_mime(path: Path) -> str | None:
    """`file --mime-type` fallback, used only when the signature is unknown."""
    try:
        out = subprocess.run(["file", "--mime-type", "-b", str(path)],
                             capture_output=True, timeout=10, text=True)
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def detect(record: dict, root: Path | None = None) -> dict:
    """Attach signature_kind + mime_detected (with provenance) to a record."""
    root = root or C.REPO_ROOT
    full = Path(root) / record["relative_path"]
    ext = record["extension"]

    head = read_head(full)
    kind = sniff(head)

    if kind != "unknown":
        mime = _SIG_MIME[kind]
        mime_src, parser = "magic_bytes", f"{C.TOOL_NAME}.detect/{C.TOOL_VERSION}"
        conf = 0.97
    else:
        mime = _file_mime(full)
        if mime:
            mime_src, parser, conf = "file(1)", "file(1)", 0.6
        else:
            import mimetypes
            mime = mimetypes.guess_type(record["filename"])[0] or _SIG_MIME["unknown"]
            mime_src, parser, conf = "extension_guess", "mimetypes", 0.3

    record["signature_kind"] = Inferred(
        value=kind, source="magic_bytes",
        evidence=[f"head[0:8]={head[:8]!r}"],
        confidence=0.97 if kind != "unknown" else 0.2,
        parser=f"{C.TOOL_NAME}.detect/{C.TOOL_VERSION}",
    ).to_dict()
    record["mime_detected"] = Inferred(
        value=mime, source=mime_src, evidence=[f"signature={kind}"],
        confidence=conf, parser=parser,
    ).to_dict()

    # Signature/extension divergence — only meaningful for design formats.
    allowed = _CONTAINER_OK.get(ext)
    if allowed is not None:
        if kind not in allowed:
            record["warnings"].append(
                f"signature_ext_mismatch: {ext} contains {kind}")
    elif ext and kind != "unknown":
        expected = {
            ".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".gif": "gif",
            ".webp": "webp", ".pdf": "pdf", ".psd": "psd", ".zip": "zip",
            ".mp4": "mp4", ".avif": "avif",
        }.get(ext)
        if expected and kind != expected:
            record["warnings"].append(
                f"signature_ext_mismatch: {ext} contains {kind}")

    # `.ai` parser routing is decided here, not by the filename.
    if ext == ".ai":
        if kind == "pdf":
            record["parser_support"] = {"status": "supported", "parser": "pymupdf"}
        elif kind in ("postscript", "eps_binary"):
            record["parser_support"] = {"status": "partial", "parser": "postscript-legacy"}
            record["warnings"].append("legacy_postscript_ai: no PDF wrapper")
        else:
            record["parser_support"] = {"status": "unsupported", "parser": None}
            record["warnings"].append(f"ai_unrecognised_signature: {kind}")
    return record
