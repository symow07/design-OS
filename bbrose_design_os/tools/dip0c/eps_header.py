"""EPS header-native audit — C1A (DIP-0C1).

No tool here opens EPS geometry (PyMuPDF raises `FileDataError`; Ghostscript is
absent). But the EPS *header* is rich and read directly: the DOS-EPS binary
wrapper (magic `C5 D0 D3 C6`), the DSC comments (BoundingBox / HiResBoundingBox /
process + custom/spot colours / fonts / creator), embedded-image and AI-private
markers, and the TIFF preview (offset/length/validated magic). All of this is
`DIRECT_FROM_EPS_HEADER`.

What is NOT available without Ghostscript — path/clip/group geometry, editable
vector structure, a rendered raster — is left to the C1B adapter, which is
currently `BLOCKED_TOOL_UNAVAILABLE`. This module never claims geometry it cannot
see. `HEADER_AUDITED` is the honest ceiling of C1A.
"""
from __future__ import annotations

import re
import struct
from pathlib import Path

from tools.dip0.provenance import Inferred

from . import config as C

PARSER = f"{C.TOOL_NAME}.eps_header/{C.TOOL_VERSION}"

DOS_MAGIC = b"\xc5\xd0\xd3\xc6"
HEADER_WINDOW = 65_536               # DSC comments live at the top of the PS section
IMAGE_MARKERS = (b" image", b" colorimage", b"BeginData", b"%%BeginBinary",
                 b"beginimage")


def _inf(value, tier, source, evidence, confidence):
    d = Inferred(value=value, source=source, evidence=list(evidence),
                 confidence=round(confidence, 3), parser=PARSER).to_dict()
    d["tier"] = tier
    return d


def _dsc(blob: bytes, key: str):
    m = re.search(rb"%%" + re.escape(key.encode()) + rb":\s*([^\r\n]*)", blob)
    if not m:
        return None
    val = m.group(1)
    # gather all consecutive DSC continuation lines (%%+ ...): each must follow
    # immediately after the previous line, so advance the cursor as we go.
    pos = m.end()
    cont = re.compile(rb"\r?\n%%\+[ \t]*([^\r\n]*)")
    while (mm := cont.match(blob, pos)) is not None:
        val += b" " + mm.group(1)
        pos = mm.end()
    return val.decode("latin-1").strip()


def audit(rel_path: str) -> dict:
    full = C.physical_path(rel_path, C.REPO_ROOT)
    size_bytes = full.stat().st_size
    with full.open("rb") as fh:
        prefix = fh.read(32)
        is_binary = prefix.startswith(DOS_MAGIC)
        preview = {"present": False}
        truncated_header = False
        if is_binary and len(prefix) >= 28:
            ps_off, ps_len, wmf_off, wmf_len, tiff_off, tiff_len = struct.unpack(
                "<IIIIII", prefix[4:28])
            fh.seek(ps_off)
            ps_head = fh.read(min(HEADER_WINDOW, ps_len or HEADER_WINDOW))
            preview = _tiff_preview(fh, tiff_off, tiff_len, wmf_off, wmf_len)
        elif is_binary:
            # DOS-EPS magic but the 30-byte header is truncated
            truncated_header = True
            fh.seek(0)
            ps_head = fh.read(HEADER_WINDOW)
        else:
            fh.seek(0)
            ps_head = fh.read(HEADER_WINDOW)

    signature_ok = ps_head[:2] == b"%!" or b"%!PS" in ps_head[:64]
    warnings = []
    if truncated_header:
        warnings.append("DOS-EPS magic present but 30-byte binary header "
                        "truncated; read PostScript from offset 0")
    bbox = _parse_bbox(_dsc(ps_head, "BoundingBox"))
    hires = _parse_bbox(_dsc(ps_head, "HiResBoundingBox"), floats=True)
    if bbox is None and hires is None:
        warnings.append("no BoundingBox / HiResBoundingBox in header window")

    spot = _spot_colors(ps_head)
    process = _process_colors(ps_head)
    fonts = _fonts(ps_head)
    creator = _dsc(ps_head, "Creator")
    title = _dsc(ps_head, "Title")
    has_images = any(m in ps_head for m in IMAGE_MARKERS)
    ai_private = bool(re.search(rb"AIPrivateData|%AI\d|%%AI", ps_head))
    if not signature_ok:
        warnings.append("missing %! PostScript signature at PS section start")

    return {
        "format": ".eps",
        "parser": PARSER,
        "size_bytes": size_bytes,
        "eps_capability_state": (C.EPS_HEADER_ONLY_PARTIAL if truncated_header
                                 else C.EPS_HEADER_AUDITED),
        "binary_dos_eps": is_binary,
        "postscript_signature": signature_ok,
        "bounding_box": _inf(bbox, C.TIER_DIRECT_FROM_EPS_HEADER, "dsc_boundingbox",
                             [f"BoundingBox={bbox}" if bbox else "absent"],
                             1.0 if bbox else 0.0),
        "hires_bounding_box": _inf(hires, C.TIER_DIRECT_FROM_EPS_HEADER,
                                   "dsc_hiresboundingbox",
                                   [f"HiRes={hires}" if hires else "absent"],
                                   1.0 if hires else 0.0),
        "spot_colors": _inf(spot, C.TIER_DIRECT_FROM_EPS_HEADER,
                            "dsc_customcolors",
                            [f"{len(spot)} spot/custom colours"], 1.0),
        "process_colors": _inf(process, C.TIER_DIRECT_FROM_EPS_HEADER,
                               "dsc_processcolors",
                               [f"{len(process)} process inks"], 1.0),
        "fonts": _inf(fonts, C.TIER_DIRECT_FROM_EPS_HEADER, "dsc_documentfonts",
                      [f"{len(fonts)} declared fonts"], 1.0),
        "creator": creator,
        "title": title,
        "embedded_image_markers": _inf(has_images, C.TIER_HEURISTIC,
                                       "ps_image_operators",
                                       ["image/colorimage operators present"
                                        if has_images else "none in header window"],
                                       0.6),
        "ai_private_data": _inf(ai_private, C.TIER_REQUIRES_ILLUSTRATOR,
                                "ai_private_markers",
                                ["Illustrator private data present; native "
                                 "semantics unavailable" if ai_private
                                 else "no AI-private markers"], 0.0),
        "tiff_preview": preview,
        # geometry is NOT available from the header — never fabricate it
        "vector_geometry": _inf(None, C.TIER_REQUIRES_TOOL, "no_eps_interpreter",
                                ["paths/clips/groups require Ghostscript (C1B); "
                                 "not audited by header-native pass"], 0.0),
        "warnings": warnings,
        "technical_readiness": _readiness(bbox or hires, spot, process,
                                          preview["present"]),
    }


def _tiff_preview(fh, tiff_off, tiff_len, wmf_off, wmf_len) -> dict:
    if not tiff_off or not tiff_len:
        note = ("WMF preview present (not TIFF)" if wmf_off and wmf_len
                else "no bitmap preview in DOS-EPS header")
        return {"present": False, "note": note}
    fh.seek(tiff_off)
    magic = fh.read(4)
    valid = magic[:2] in (b"II", b"MM") and magic[2:4] in (b"\x2a\x00", b"\x00\x2a")
    return {
        "present": True,
        "type": "TIFF",
        "offset": tiff_off,
        "length": tiff_len,
        "magic_valid": valid,
        "extractable": valid,
        "note": ("valid TIFF preview; extractable to previews/ (deferred)"
                 if valid else "declared TIFF preview but magic invalid"),
    }


def _parse_bbox(raw, floats=False):
    if not raw or raw.lower().startswith("(atend"):
        return None
    parts = raw.split()
    if len(parts) < 4:
        return None
    try:
        conv = float if floats else int
        return [conv(float(p)) for p in parts[:4]]
    except ValueError:
        return None


def _spot_colors(blob: bytes) -> list[str]:
    names: list[str] = []
    for key in ("DocumentCustomColors", "CMYKCustomColor"):
        raw = _dsc(blob, key)
        if raw:
            names += re.findall(r"\(([^)]+)\)", raw)
    # dedupe, drop registration
    out, seen = [], set()
    for n in names:
        n = n.strip()
        if n and n.lower() not in seen and "registration" not in n.lower():
            seen.add(n.lower())
            out.append(n)
    return out


def _process_colors(blob: bytes) -> list[str]:
    raw = _dsc(blob, "DocumentProcessColors")
    if not raw:
        return []
    return [t for t in re.split(r"\s+", raw) if t and t != "(atend)"]


def _fonts(blob: bytes) -> list[str]:
    out = []
    for key in ("DocumentFonts", "DocumentNeededFonts", "DocumentSuppliedFonts"):
        raw = _dsc(blob, key)
        if raw and not raw.lower().startswith("(atend"):
            out += [t for t in re.split(r"\s+", raw) if t]
    return sorted(set(out))


def _readiness(has_bbox, spot, process, has_preview):
    """Axis A, header-only. Geometry unknown, so this can never be
    TECHNICALLY_READY — the honest ceiling is REFERENCE_ONLY pending C1B."""
    ev = []
    if has_bbox:
        ev.append("bbox known")
    if spot or process:
        ev.append(f"{len(spot)} spot / {len(process)} process inks declared")
    if has_preview:
        ev.append("TIFF preview available for visual reference")
    ev.append("editable vector geometry requires Ghostscript (C1B, blocked)")
    return _inf(C.READY_REFERENCE_ONLY, C.TIER_DIRECT_FROM_EPS_HEADER,
                "header_only", ev, 0.6)
