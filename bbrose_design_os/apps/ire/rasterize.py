"""Verified PDF previews; publish only a complete render at the requested DPI."""
import logging
import os
import tempfile
from pathlib import Path
from .pdf_raster import render_verified
logger = logging.getLogger(__name__)


def pdf_to_png(src, out, dpi=150):
    src, out = Path(src), Path(out)
    if not src.is_file():
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(dir=out.parent) as directory:
            candidate = Path(directory) / 'preview.png'
            render_verified(str(src), str(candidate), dpi)
            os.replace(candidate, out)
        return True
    except Exception:
        logger.exception('Preview could not be rendered at %s DPI', dpi)
        return False
