"""Synthetic fixture tree — never touches the real materials/ library."""
from __future__ import annotations

import os
import struct
import zipfile
from pathlib import Path

import pytest

# Minimal valid magic-byte payloads for signature sniffing tests.
PDF_AI = b"%PDF-1.5\n% Adobe Illustrator\n"
PS_AI = b"%!PS-Adobe-3.0\n%%Creator: Adobe Illustrator\n"
EPS_ASCII = b"%!PS-Adobe-3.0 EPSF-3.0\n"
EPS_BIN = struct.pack("<I", 0xC6D3D0C5) + b"\x00" * 24
PSD = b"8BPS\x00\x01" + b"\x00" * 20
PNG = bytes.fromhex("89504e470d0a1a0a") + b"\x00" * 16
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
OTF = b"OTTO" + b"\x00" * 20
TTF = b"\x00\x01\x00\x00" + b"\x00" * 20


def _w(p: Path, data: bytes) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def _real_font(p: Path) -> Path:
    """A genuinely valid TTF so font inspection is tested against a real parse,
    not a magic-byte stub. 11 Latin codepoints → script coverage is detectable."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    p.parent.mkdir(parents=True, exist_ok=True)
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder([".notdef", "A"])
    fb.setupCharacterMap({cp: "A" for cp in range(0x41, 0x4C)})
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((0, 500))
    pen.lineTo((500, 500))
    pen.closePath()
    g = pen.glyph()
    fb.setupGlyf({".notdef": g, "A": g})
    fb.setupHorizontalMetrics({".notdef": (500, 0), "A": (500, 0)})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "PilotTest", "styleName": "Regular",
                       "psName": "PilotTest-Regular",
                       "licenseDescription": "Test licence evidence"})
    fb.setupOS2(sTypoAscender=800, usWeightClass=400, fsType=8)
    fb.setupPost()
    fb.save(str(p))
    return p


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """A materials/-shaped fixture with dupes, junk, symlinks, mixed formats."""
    from tools.dip0 import config as C

    repo = tmp_path / "repo"
    src = repo / "materials"
    src.mkdir(parents=True)

    # historical designs (unique)
    _w(src / "historical AI production designs" / "LP5526-E.ai", PDF_AI + b"a")
    _w(src / "historical AI production designs" / "ES3089.ai", PS_AI + b"legacy")
    _w(src / "historical AI production designs" / "(2).ai", PDF_AI + b"bad-name")

    # exact duplicates across folders (same bytes)
    dup = b"%!PS-Adobe-3.0 EPSF-3.0\nshared-vector\n"
    _w(src / "DOWNLOADE 2026" / "floral-pattern" / "rose.eps", dup)
    _w(src / "DOWNLOADE 2026" / "DOWNLOADS 12-2025" / "floral-pattern" / "rose.eps", dup)
    # license evidence beside them
    _w(src / "DOWNLOADE 2026" / "floral-pattern" / "License premium.txt", b"freepik")
    _w(src / "DOWNLOADE 2026" / "DOWNLOADS 12-2025" / "floral-pattern" / "License premium.txt", b"freepik")

    # backgrounds / raster
    _w(src / "DOWNLOADE 2026" / "glowing-particles-background" / "bg.jpg", JPG)
    _w(src / "DOWNLOADE 2026" / "premium-abstract-shape-collection" / "shapes.eps", EPS_BIN)

    # brand + third-party logos (folder must NOT establish ownership)
    office = src / "DOWNLOADE 2026" / "office"
    _w(office / "BBROSE.pdf", b"%PDF-1.4 brand")
    _w(office / "LOGO6.ai", PDF_AI + b"logo6")
    _w(office / "ATC LOGO.ai", PDF_AI + b"atc")
    _w(office / "JOJIA LOGO.ai", PDF_AI + b"jojia")

    # out of scope
    _w(office / "Q Cargo China Receipt (1).xlsx", b"PK\x03\x04xlsx")
    _w(office / "Weixin Videos2025-11-03.mp4", b"\x00\x00\x00\x20ftypmp42")

    # fonts: licensed download folder vs suspected system dump
    _w(src / "DOWNLOADE 2026" / "sinkin-sans" / "SinkinSans.otf", OTF)
    _w(src / "DOWNLOADE 2026" / "sinkin-sans" / "readme.html", b"<html>license</html>")
    _w(src / "Fonts" / "Brand.otf", OTF)
    _w(src / "Fonts" / "3333" / "mingliub.ttc", b"ttcf" + b"\x00" * 20)
    _w(src / "Fonts" / "3333" / "Arial.ttf", TTF)

    # psd + unsupported
    _w(src / "DOWNLOADE 2026" / "mockup" / "shirt.psd", PSD)
    _w(src / "DOWNLOADE 2026" / "legacy" / "old.fon", b"MZ" + b"\x00" * 20)

    # a real, parseable TrueType font (fontTools round-trip target)
    _real_font(src / "DOWNLOADE 2026" / "sinkin-sans" / "PilotTest-Regular.ttf")

    # signature/extension mismatch: JPEG bytes wearing a .png extension
    _w(src / "DOWNLOADE 2026" / "mockup" / "mislabelled.png", JPG)

    # archive (with a nested zip entry + a traversal entry)
    zp = src / "DOWNLOADE 2026" / "bundle.zip"
    zp.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("inner/art.eps", b"x" * 500)
        z.writestr("inner/nested.zip", b"PK\x03\x04nested")
        z.writestr("../escape.txt", b"traversal")

    # corrupt archive
    _w(src / "DOWNLOADE 2026" / "broken.zip", b"PK\x03\x04garbage-not-a-zip")

    # byte-identical archives → exact duplicate
    for name in ("dupA.zip", "dupB.zip"):
        with zipfile.ZipFile(src / "DOWNLOADE 2026" / name, "w",
                             zipfile.ZIP_STORED) as z:
            z.writestr("a.eps", b"same" * 100)
    # same manifest, different container bytes → probable duplicate
    with zipfile.ZipFile(src / "DOWNLOADE 2026" / "manifestA.zip", "w",
                         zipfile.ZIP_STORED) as z:
        z.writestr("b.eps", b"payload" * 200)
    with zipfile.ZipFile(src / "DOWNLOADE 2026" / "manifestB.zip", "w",
                         zipfile.ZIP_DEFLATED) as z:
        z.writestr("b.eps", b"payload" * 200)

    # junk (must be excluded but counted, and NOT deleted)
    _w(src / "Thumbs.db", b"junk")
    _w(src / "DOWNLOADE 2026" / ".DS_Store", b"junk")
    _w(src / "DOWNLOADE 2026" / "~$lock.doc", b"junk")

    # skipped dir
    _w(src / "__MACOSX" / "._art.eps", b"resource fork")
    _w(src / ".cache" / "blob", b"cache")

    # symlinks: internal + escaping + loop
    os.symlink(src / "historical AI production designs" / "LP5526-E.ai",
               src / "link_internal.ai")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside")
    os.symlink(outside, src / "link_escape.txt")
    os.symlink(src / "DOWNLOADE 2026", src / "DOWNLOADE 2026" / "link_loop")

    monkeypatch.setattr(C, "REPO_ROOT", repo)
    monkeypatch.setattr(C, "SOURCE_ROOT", src)
    out = repo / "var" / "design_intelligence" / "audits" / "dip0"
    monkeypatch.setattr(C, "OUTPUT_ROOT", out)
    monkeypatch.setattr(C, "OUT_INVENTORY", out / "inventory")
    monkeypatch.setattr(C, "OUT_PREVIEWS", out / "previews")
    monkeypatch.setattr(C, "OUT_REPORTS", out / "reports")
    monkeypatch.setattr(C, "OUT_MANIFESTS", out / "manifests")
    monkeypatch.setattr(C, "OUT_TEMP", out / "temporary")
    return repo
