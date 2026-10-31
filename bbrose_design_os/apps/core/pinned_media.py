"""D-D14-4: serve a master publication only from its current database pins.

The adjacent publication.json marks an orphaned publication; its mutable hashes
are never authority. Unrelated media keeps the existing file-door behavior.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
from pathlib import Path
from tempfile import SpooledTemporaryFile

from django.db import DatabaseError

from apps.pipeline.services import master_tasks as mt

logger = logging.getLogger(__name__)
SPOOL_MEMORY_BYTES = 1 << 20
HASH_CHUNK_BYTES = 1 << 20
SHA256 = re.compile(r"[0-9a-f]{64}")


class IntegrityRefused(Exception):
    """The master publication cannot authorize these download bytes."""


def _refuse(relative: str, reason: str):
    message = f"PINNED_DOWNLOAD_REFUSED: {relative}: {reason}"
    logger.warning(message)
    raise IntegrityRefused(message)


def _namespace(target: Path, media_root: Path, requested_path: str):
    # Keep the normalized requested path as well as its resolved target: replacing
    # a pinned file with an in-root symlink must not turn it into generic media.
    requested = Path(os.path.abspath(media_root / requested_path))
    prefix = Path(mt.MEDIA_FOLDER).parts
    for candidate in (requested, target):
        if not candidate.is_relative_to(media_root):
            continue
        relative = candidate.relative_to(media_root)
        parts = relative.parts
        if parts[:len(prefix)] == prefix and len(parts) > len(prefix) + 1:
            slug = parts[len(prefix)]
            return slug, relative.as_posix()
    return None


def verified_master_file(target: Path, media_root: Path, requested_path: str):
    """Return a verified byte snapshot, or None for unrelated generic media.

Call after the existing authentication, path and reference restrictions. The
caller owns the returned stream and must close it (FileResponse does this).
"""
    namespace = _namespace(target, media_root, requested_path)
    if namespace is None:
        return None
    slug, relative = namespace
    from apps.pipeline.models import DesignTask

    try:
        task = DesignTask.objects.filter(**{f"options__{mt.KEY_OPTION}": slug}).order_by("pk").first()
        output = task.current_output() if task is not None else None
    except DatabaseError:
        _refuse(relative, "current publication record is unavailable")
    if task is None:
        if (media_root / mt.MEDIA_FOLDER / slug / mt.RECORD_NAME).exists():
            _refuse(relative, "published namespace has no current task")
        return None
    spec = output.spec_sheet if output is not None and isinstance(output.spec_sheet, dict) else {}
    publication = spec.get(mt.SPEC_KEY)
    if not isinstance(publication, dict) or publication.get("slug") != slug or publication.get("schema") != mt.RECORD_SCHEMA:
        _refuse(relative, "current output has no valid master publication")
    files = publication.get("files")
    pin = files.get(relative) if isinstance(files, dict) else None
    expected = pin.get("sha256") if isinstance(pin, dict) else None
    if not isinstance(expected, str) or not SHA256.fullmatch(expected):
        _refuse(relative, "current output has no valid SHA256 pin for this file")

    # Never hash one open and then serve another: snapshot while hashing, verify,
    # then serve those same bytes. Large downloads spill out of bounded memory.
    snapshot = SpooledTemporaryFile(max_size=SPOOL_MEMORY_BYTES, mode="w+b")
    try:
        digest = hashlib.sha256()
        try:
            with target.open("rb") as source:
                for chunk in iter(lambda: source.read(HASH_CHUNK_BYTES), b""):
                    digest.update(chunk)
                    snapshot.write(chunk)
        except OSError:
            _refuse(relative, "published bytes could not be read")
        actual = digest.hexdigest()
        if actual != expected:
            _refuse(relative, f"SHA256 mismatch (expected {expected}, got {actual})")
        snapshot.seek(0)
        return snapshot
    except BaseException:
        snapshot.close()
        raise
