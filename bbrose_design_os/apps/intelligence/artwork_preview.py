"""Safe, authenticated, read-only artwork previews — DIP-1C-6A.

The DIP-1C-5C pilot stalled on an honest problem: descriptors must come from the artwork,
but the review page showed only hashes, machine labels and technical facts, so a reviewer had
to leave the platform and open Illustrator. This renders a bounded preview *inside* the
review page.

**It is presentation, not authority.** A preview is not classification, approval, ownership,
licence or permission, and it never modifies the source.

Three boundaries hold this together:

1. **Source resolution is server-side and root-bounded.** The browser never supplies a path.
   A `SourceArtifact.source_location` names a *configured root* plus a repository-relative
   path; the path is normalized (no `..`, no absolute), resolved through symlinks, and then
   checked to still sit under that root and under an allowed prefix. A path in the database
   is not trusted for being there.
2. **The original bytes are never served.** Only a generated PNG leaves the process. There is
   no endpoint that returns an `.ai`, `.eps`, `.psd`, font or archive.
3. **Preview identity includes the source hash.** The cache key binds renderer, configuration
   and `SourceArtifact.sha256`, so a preview made from different bytes can never be served as
   though it belonged to this version. The hash is re-verified on every render.
"""
from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import os
import struct
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError

from .locator_schemas import normalize_relative_path

RENDERER_IDENTIFIER = "bbrose.intelligence.artwork_preview"
RENDERER_VERSION = "1.0"
PREVIEW_SCHEMA = "intelligence_artwork_preview/1.0"

# --- statuses ---------------------------------------------------------------------
AVAILABLE = "AVAILABLE"
NOT_RENDERABLE = "NOT_RENDERABLE"
SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
HASH_MISMATCH = "HASH_MISMATCH"
RENDER_FAILED = "RENDER_FAILED"
UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
REVIEW_REQUIRED = "REVIEW_REQUIRED"

# --- bounded, deterministic render configuration ----------------------------------
# Frozen: a change here changes the configuration hash and therefore every cache key, so
# stale previews can never be served under a new configuration.
MAX_EDGE_PIXELS = 1400
MAX_TOTAL_PIXELS = 4_000_000
MAX_PREVIEW_BYTES = 6 * 1024 * 1024
MAX_SOURCE_BYTES = 512 * 1024 * 1024
SPECIMEN_SIZE = (1000, 320)
SPECIMEN_TEXT = "ABCDEFGHIJKLM\nabcdefghijklm\n0123456789"
PREVIEW_CONTENT_TYPE = "image/png"

PDF_BACKED_SUFFIXES = {".ai", ".pdf"}
EPS_SUFFIXES = {".eps"}
FONT_SUFFIXES = {".ttf", ".otf", ".ttc"}
#: binary (DOS/EPSF) EPS container magic — the only EPS variant carrying an extractable
#: raster preview. ASCII EPS has no preview and is reported NOT_RENDERABLE.
EPS_BINARY_MAGIC = b"\xc5\xd0\xd3\xc6"


class PreviewError(RuntimeError):
    """A preview could not be produced safely. Carries a status, never a path."""

    def __init__(self, status, detail=""):
        self.status = status
        super().__init__(f"{status}: {detail}" if detail else status)


def _configuration_hash() -> str:
    import fitz
    document = {
        "preview_schema": PREVIEW_SCHEMA,
        "renderer_identifier": RENDERER_IDENTIFIER,
        "renderer_version": RENDERER_VERSION,
        "pymupdf_version": fitz.VersionBind,
        "max_edge_pixels": MAX_EDGE_PIXELS,
        "max_total_pixels": MAX_TOTAL_PIXELS,
        "specimen_size": list(SPECIMEN_SIZE),
        "specimen_text": SPECIMEN_TEXT,
        "format": "PNG",
    }
    return hashlib.sha256(json.dumps(
        document, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def renderer_description() -> dict:
    import fitz
    return {
        "renderer_identifier": RENDERER_IDENTIFIER,
        "renderer_version": RENDERER_VERSION,
        "pymupdf_version": fitz.VersionBind,
        "mupdf_version": fitz.VersionFitz,
        "configuration_hash": _configuration_hash(),
    }


# --- source resolution ------------------------------------------------------------

def preview_root() -> Path:
    root = getattr(settings, "INTELLIGENCE_PREVIEW_ROOT", None)
    if root:
        return Path(root)
    return Path(settings.BASE_DIR).parent / "var" / "design_intelligence" / "previews"


def resolve_source_path(source_artifact) -> Path:
    """Resolve a `SourceArtifact` to a real path inside a configured root, or refuse.

    Never accepts a caller-supplied path. Rejects absolute paths, traversal, unconfigured
    roots, disallowed prefixes and symlink escape — the escape check runs **after**
    `resolve()`, so a symlink pointing outside the root fails even though its own path
    looked contained.
    """
    location = source_artifact.source_location or ""
    root_name, _, relative = location.partition(":")
    roots = getattr(settings, "INTELLIGENCE_SOURCE_ROOTS", {})
    if not root_name or root_name not in roots:
        raise PreviewError(SOURCE_UNAVAILABLE, "source root is not configured")
    try:
        relative = normalize_relative_path(relative)
    except (TypeError, ValidationError) as exc:
        raise PreviewError(SOURCE_UNAVAILABLE, "source path is invalid") from exc

    prefixes = getattr(settings, "INTELLIGENCE_ALLOWED_SOURCE_PREFIXES", {}).get(
        root_name, ())
    if prefixes and not any(
            relative == prefix or relative.startswith(f"{prefix}/") for prefix in prefixes):
        raise PreviewError(SOURCE_UNAVAILABLE, "source path is outside an allowed prefix")

    root = Path(roots[root_name]).resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:                    # symlink or traversal escape
        raise PreviewError(SOURCE_UNAVAILABLE, "source path escapes its root") from exc
    from apps.ire.materials_paths import resolve_material_file, MaterialPathError
    try:
        path = resolve_material_file(path, repo_root=root)   # mapping only: verify_source_hash owns HASH_MISMATCH
    except MaterialPathError as exc:
        raise PreviewError(SOURCE_UNAVAILABLE, 'material migration invalid') from exc
    if not path.is_file():
        raise PreviewError(SOURCE_UNAVAILABLE, "source file is not present")
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise PreviewError(UNSUPPORTED_FORMAT, "source exceeds the size bound")
    return path


def verify_source_hash(path: Path, source_artifact) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    observed = digest.hexdigest()
    if observed != source_artifact.sha256:
        # the bytes are not the bytes this record describes; a preview from them would be
        # attributed to the wrong source version
        raise PreviewError(HASH_MISMATCH, "source bytes do not match the recorded hash")
    return observed


# --- preview identity + cache -----------------------------------------------------

@dataclasses.dataclass(frozen=True)
class PreviewIdentity:
    source_artifact_id: str
    source_sha256: str
    evidence_reference_id: str
    locator_schema_version: str
    unit_identity: str
    renderer_identifier: str
    renderer_version: str
    configuration_hash: str

    def cache_key(self) -> str:
        return hashlib.sha256("|".join([
            self.source_artifact_id, self.source_sha256, self.evidence_reference_id,
            self.locator_schema_version, self.unit_identity,
            self.renderer_identifier, self.renderer_version, self.configuration_hash,
        ]).encode()).hexdigest()

    def cache_path(self) -> Path:
        key = self.cache_key()
        return preview_root() / key[:2] / f"{key}.png"


def _unit_identity(reference) -> str:
    locator = reference.locator if isinstance(reference.locator, dict) else {}
    schema = reference.locator_schema_version or ""
    if schema == "file_page/1.0":
        return f"page:{locator.get('page', 0)}"
    if schema == "illustrator_artboard/1.0":
        return f"artboard:{locator.get('artboard', 0)}"
    if schema == "font_face/1.0":
        return f"face:{locator.get('face_index', 0)}"
    return "source"


def build_identity(reference) -> PreviewIdentity:
    source = reference.source_artifact
    return PreviewIdentity(
        source_artifact_id=str(source.pk), source_sha256=source.sha256,
        evidence_reference_id=str(reference.pk),
        locator_schema_version=reference.locator_schema_version or "",
        unit_identity=_unit_identity(reference),
        renderer_identifier=RENDERER_IDENTIFIER, renderer_version=RENDERER_VERSION,
        configuration_hash=_configuration_hash())


def _write_atomically(path: Path, payload: bytes):
    """Temp file in the same directory, then `os.replace`. A crashed or failed render can
    never leave a partial file where a valid preview was."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=str(path.parent), suffix=".part")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


# --- renderers --------------------------------------------------------------------

def _bounded_png_from_pixmap(pixmap) -> bytes:
    payload = pixmap.tobytes("png")
    if len(payload) > MAX_PREVIEW_BYTES:
        raise PreviewError(RENDER_FAILED, "rendered preview exceeds the size bound")
    return payload


def _render_pdf_backed(path: Path, page_number: int) -> bytes:
    import fitz
    try:
        with fitz.open(path) as document:
            if document.page_count == 0:
                raise PreviewError(NOT_RENDERABLE, "source has no renderable page")
            index = page_number if 0 <= page_number < document.page_count else 0
            page = document.load_page(index)
            rect = page.rect
            longest = max(rect.width, rect.height) or 1
            scale = min(MAX_EDGE_PIXELS / longest, 4.0)
            if rect.width * scale * rect.height * scale > MAX_TOTAL_PIXELS:
                scale = (MAX_TOTAL_PIXELS / (rect.width * rect.height)) ** 0.5
            pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            return _bounded_png_from_pixmap(pixmap)
    except PreviewError:
        raise
    except Exception as exc:                     # a corrupt or non-PDF-backed .ai
        raise PreviewError(NOT_RENDERABLE, type(exc).__name__) from exc


def _eps_embedded_tiff(path: Path) -> bytes:
    """The embedded TIFF preview of a binary EPS, or a precise refusal.

    DIP-0C1 measured an embedded TIFF in 412 of 536 EPS files, and its strip offsets are
    payload-relative, so the block is self-contained. Whether Pillow can *decode* it is a
    separate question — see `_render_eps_preview`.
    """
    header = path.read_bytes()[:32]
    if not header.startswith(EPS_BINARY_MAGIC):
        # This path renders from an EMBEDDED preview only; it does not shell out to a
        # rasteriser, so the refusal says what is missing from the FILE rather than
        # what is missing from the machine (§BH44(a)(2)).
        raise PreviewError(NOT_RENDERABLE,
                           "ASCII EPS carries no embedded preview, and this path "
                           "renders only from an embedded preview")
    tiff_offset, tiff_length = struct.unpack("<II", header[20:28])
    if not tiff_offset or not tiff_length or tiff_length > MAX_PREVIEW_BYTES * 8:
        raise PreviewError(NOT_RENDERABLE, "EPS declares no usable TIFF preview")
    with path.open("rb") as handle:
        handle.seek(tiff_offset)
        return handle.read(tiff_length)


def _render_eps_preview(path: Path) -> bytes:
    """Render a binary EPS from its embedded TIFF preview.

    **Measured limitation.** The two curated-expansion EPS files in the pilot embed *palette*
    TIFFs carrying an extra sample, and Pillow rejects that combination outright
    (`SyntaxError: unknown pixel mode`). Decoding it would mean writing a raster decoder,
    which is far outside a preview slice. Those items are reported `NOT_RENDERABLE` with the
    reason rather than shown as a broken image, and the honest fix is the already-designed,
    deliberately-absent Ghostscript adapter (DIP-0C1 C1B) — not new decoding code here.
    """
    from PIL import Image
    payload = _eps_embedded_tiff(path)
    try:
        with Image.open(io.BytesIO(payload)) as image:
            image.load()
            image = image.convert("RGB")
            image.thumbnail((MAX_EDGE_PIXELS, MAX_EDGE_PIXELS))
            buffer = io.BytesIO()
            image.save(buffer, format="PNG", optimize=True)
    except PreviewError:
        raise
    except Exception as exc:
        raise PreviewError(
            NOT_RENDERABLE,
            f"embedded TIFF preview is not decodable ({type(exc).__name__}); "
            "Ghostscript rendering is absent") from exc
    data = buffer.getvalue()
    if len(data) > MAX_PREVIEW_BYTES:
        raise PreviewError(RENDER_FAILED, "rendered preview exceeds the size bound")
    return data


def _eps_is_decodable(path: Path) -> tuple[bool, str]:
    """Cheap check used by the status card so it never promises a preview it cannot make."""
    from PIL import Image
    try:
        payload = _eps_embedded_tiff(path)
    except PreviewError as exc:
        return False, str(exc).split(": ", 1)[-1]
    try:
        with Image.open(io.BytesIO(payload)) as image:
            image.load()
        return True, ""
    except Exception as exc:
        return False, (f"embedded TIFF preview is not decodable ({type(exc).__name__}); "
                       "Ghostscript rendering is absent")


def _render_font_specimen(path: Path) -> bytes:
    """A glyph specimen — letterforms only, from the local file, with no licence meaning.

    Rendering a specimen for review is not a licence finding, an approval or a production
    use, and the caller states that in the UI. The specimen text is fixed so the output is
    deterministic, and no user-supplied string is ever rendered.
    """
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype(str(path), 64)
    except Exception as exc:
        raise PreviewError(NOT_RENDERABLE, type(exc).__name__) from exc
    try:
        image = Image.new("RGB", SPECIMEN_SIZE, "white")
        draw = ImageDraw.Draw(image)
        draw.multiline_text((30, 30), SPECIMEN_TEXT, font=font, fill="black", spacing=18)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
    except Exception as exc:
        raise PreviewError(RENDER_FAILED, type(exc).__name__) from exc
    return buffer.getvalue()


def _render(path: Path, reference) -> bytes:
    suffix = path.suffix.lower()
    locator = reference.locator if isinstance(reference.locator, dict) else {}
    if suffix in PDF_BACKED_SUFFIXES:
        return _render_pdf_backed(path, int(locator.get("page", 0) or 0))
    if suffix in EPS_SUFFIXES:
        return _render_eps_preview(path)
    if suffix in FONT_SUFFIXES:
        return _render_font_specimen(path)
    raise PreviewError(UNSUPPORTED_FORMAT, f"no renderer for {suffix or 'this source'}")


# --- the public entry point -------------------------------------------------------

def render_preview(reference, *, use_cache=True) -> tuple[bytes, PreviewIdentity]:
    """PNG bytes for one evidence reference. Read-only with respect to the source.

    A failed render raises and **never** replaces a valid cached preview: the cache is only
    written after a successful render, atomically.
    """
    if getattr(reference, "is_test_only", False):
        raise PreviewError(REVIEW_REQUIRED, "test-only evidence is not previewable")
    identity = build_identity(reference)
    cached = identity.cache_path()
    if use_cache and cached.is_file():
        payload = cached.read_bytes()
        if payload:
            return payload, identity          # key includes the source hash: never stale
    path = resolve_source_path(reference.source_artifact)
    verify_source_hash(path, reference.source_artifact)
    payload = _render(path, reference)
    content_hash = hashlib.sha256(payload).hexdigest()
    if use_cache:
        _write_atomically(cached, payload)
    object.__setattr__(identity, "_content_hash", content_hash)
    return payload, identity


def preview_status(reference) -> dict:
    """Status for one reference **without** rendering — for the page, which must stay fast
    and must never claim a preview exists when it does not."""
    identity = build_identity(reference)
    card = {
        "evidence_reference_id": str(reference.pk),
        "evidence_kind": reference.evidence_kind,
        "locator_schema_version": reference.locator_schema_version or "",
        "unit_identity": identity.unit_identity,
        "source_sha256_prefix": reference.source_artifact.sha256[:12],
        "cache_key": identity.cache_key(),
        "status": AVAILABLE,
        "detail": "",
        "cached": identity.cache_path().is_file(),
        # a page view of the source, NOT an isolated artwork: stated so the reviewer cannot
        # mistake an extracted unit for a separate original
        "is_page_view": identity.unit_identity.startswith(("page:", "artboard:")),
        "is_specimen": False,
    }
    if getattr(reference, "is_test_only", False):
        card.update(status=REVIEW_REQUIRED, detail="test-only evidence")
        return card
    try:
        path = resolve_source_path(reference.source_artifact)
    except PreviewError as exc:
        card.update(status=exc.status, detail=str(exc).split(": ", 1)[-1])
        return card
    suffix = path.suffix.lower()
    card["is_specimen"] = suffix in FONT_SUFFIXES
    if suffix not in (PDF_BACKED_SUFFIXES | EPS_SUFFIXES | FONT_SUFFIXES):
        card.update(status=UNSUPPORTED_FORMAT, detail=f"no renderer for {suffix}")
    elif suffix in EPS_SUFFIXES:
        decodable, detail = _eps_is_decodable(path)
        if not decodable:
            card.update(status=NOT_RENDERABLE, detail=detail)
    return card


def preview_cards(references) -> list:
    return [preview_status(reference) for reference in references]
