"""SYNTHETIC vector masters for the brand-mark switch's tests — the owner's second answer of 2026-09-25
(OWNER_BLOCKER_CLEARANCE.md:23803): "When I approve the logo trace, switch the mark to it so gold foil can print."

THESE ARE FIXTURES AND NOTHING ELSE. No byte of the owner's trace is here, and no test places a master anywhere but a
pytest ``tmp_path``: the switch is thrown only by his approved file placed with its approval record
(``tools/brand_mark_place.py``). Each fixture reproduces a GRAMMAR the approval covers, drawn small enough to reason
about by hand:

* ``POTRACE_STYLE`` — potrace's own shape: a DOCTYPE, a metadata block, ONE ``<g transform="translate(0,H)
  scale(s,-s)" fill="#000000" stroke="none">`` of paths in integer, relative ``m``/``l``/``c``/``z`` with repeated
  arguments and ``m`` after ``z``. Two shapes: a block with two COUNTERS (x 10..45, y 10..30 in user units; counters
  x 15..40, y 13..19 and 21..27), and a RING (centre 70,20; radii 10 and 5). Every hole runs against its outline, as
  potrace writes them. The ink is x 10..80, y 10..30 — aspect 20/70 — inside a PADDED viewBox of 100 x 40 (aspect
  0.4), as potrace's viewBox is the traced PNG's whole canvas.
* ``REG_STYLE`` — the ® redraw's shape: the same group, and beside it two ABSOLUTE ``M/L/C/Z`` paths with decimals,
  ``fill="#000000" fill-rule="nonzero"``: a small ring (centre 90,7; radii 5 and 3) and an island in its hole.
* ``SAME_DIRECTION`` — the fill-rule trap: a square inside a square, BOTH running clockwise. By the nonzero rule the
  master declares, the inner square is FILLED (winding 2); by even-odd — reportlab's default — it is a hole.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

_HEAD = b'''<?xml version="1.0" standalone="no"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 20010904//EN"
 "http://www.w3.org/TR/2001/REC-SVG-20010904/DTD/svg10.dtd">
<svg version="1.0" xmlns="http://www.w3.org/2000/svg"
 width="100.000000pt" height="40.000000pt" viewBox="0 0 100.000000 40.000000"
 preserveAspectRatio="xMidYMid meet">
<metadata>
a potrace-style SYNTHETIC fixture (apps/ire/tests/brand_mark_fixtures.py) - not a trace of any mark
</metadata>
'''

_GROUP = b'''<g transform="translate(0.000000,40.000000) scale(0.010000,-0.010000)"
fill="#000000" stroke="none">
<path d="M1000 1000 l3500 0 0 2000 -3500 0 0 -2000 z m500 300 l0 600 2500 0
0 -600 -2500 0 z m0 800 l0 600 2500 0 0 -600 -2500 0 z"/>
<path d="M8000 2000 c0 552 -448 1000 -1000 1000 -552 0 -1000 -448 -1000 -1000
0 -552 448 -1000 1000 -1000 552 0 1000 448 1000 1000 z m-500 0 c0 -276 -224
-500 -500 -500 -276 0 -500 224 -500 500 0 276 224 500 500 500 276 0 500 -224
500 -500 z"/>
</g>
'''

_REG_PATHS = b'''<path fill="#000000" fill-rule="nonzero" d="M 90.000 2.000 C 92.761 2.000 95.000 4.239 95.000 7.000 C 95.000 9.761 92.761 12.000 90.000 12.000 C 87.239 12.000 85.000 9.761 85.000 7.000 C 85.000 4.239 87.239 2.000 90.000 2.000 Z M 90.000 4.000 C 88.343 4.000 87.000 5.343 87.000 7.000 C 87.000 8.657 88.343 10.000 90.000 10.000 C 91.657 10.000 93.000 8.657 93.000 7.000 C 93.000 5.343 91.657 4.000 90.000 4.000 Z"/>
<path fill="#000000" fill-rule="nonzero" d="M 88.750 5.750 L 91.250 5.750 L 91.250 8.250 L 88.750 8.250 Z"/>
'''

POTRACE_STYLE = _HEAD + _GROUP + b"</svg>\n"
REG_STYLE = _HEAD + _GROUP + _REG_PATHS + b"\n</svg>\n"
SAME_DIRECTION = b'''<?xml version="1.0" standalone="no"?>
<svg version="1.0" xmlns="http://www.w3.org/2000/svg" width="60pt" height="60pt" viewBox="0 0 60 60">
<path fill="#000000" fill-rule="nonzero" d="M 10 10 L 50 10 L 50 50 L 10 50 Z M 20 20 L 40 20 L 40 40 L 20 40 Z"/>
</svg>
'''

#: potrace's own DOCTYPE, as POTRACE_STYLE carries it (over two lines) — a refusal fixture replaces it whole
POTRACE_DOCTYPE_BYTES = (b'<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 20010904//EN"\n'
                         b' "http://www.w3.org/TR/2001/REC-SVG-20010904/DTD/svg10.dtd">')

#: a TEST register for the placement tool: a quoted paragraph wrapped over two lines with its blockquote markers, a
#: quoted paragraph break, and a second paragraph the first one's words never reach. Nothing here speaks for the owner.
REGISTER_FILE = "TEST_FIXTURE.md"
REGISTER_TEXT = """# A TEST REGISTER - apps/ire/tests/brand_mark_fixtures.py, not the owner's

> A TEST FIXTURE - these are not the owner's words
>    and approve nothing.
>
> A second paragraph the words above never reach.
"""
#: where REGISTER_TEXT's first quoted paragraph starts, and its words as the tool is handed them (one line)
REGISTER_LINE = REGISTER_FILE + ":3"
REGISTER_WORDS = "A TEST FIXTURE - these are not the owner's words and approve nothing."
REGISTER_OTHER_PARAGRAPH = "A second paragraph the words above never reach."


def write_register(folder) -> str:
    """REGISTER_TEXT written as ``folder``/TEST_FIXTURE.md; returns ``folder`` — the tool's ``register_root``."""
    Path(folder).mkdir(parents=True, exist_ok=True)
    Path(folder, REGISTER_FILE).write_text(REGISTER_TEXT, encoding="utf-8")
    return str(folder)


#: POTRACE_STYLE's ink, its aspect and its viewBox's — the two the aspect trap tells apart
POTRACE_INK = (10.0, 10.0, 80.0, 30.0)
POTRACE_INK_ASPECT = 20.0 / 70.0
POTRACE_VIEWBOX_ASPECT = 40.0 / 100.0
#: points inside POTRACE_STYLE, in user units: in the block's ink, in each counter, in the ring, in its hole
POTRACE_INKED = ((12.0, 20.0), (42.0, 20.0), (61.5, 20.0))
POTRACE_HOLES = ((27.5, 16.0), (27.5, 24.0), (70.0, 20.0))


def variant(old: bytes, new: bytes, base: bytes = POTRACE_STYLE) -> bytes:
    """``base`` with ``old`` replaced by ``new`` once — a refusal fixture is the covered grammar plus one thing."""
    assert base.count(old) >= 1, old
    return base.replace(old, new, 1)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_approval(root, svg: bytes, **overrides) -> dict:
    """An approval record and its master under ``root``/docs/brand/mark — a TEST root, never the tree's. The record
    says in its own words that it is a fixture: nothing here speaks for the owner."""
    from apps.ire import brand_mark as B
    folder = Path(root, *B.MARK_DIR)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / B.MASTER_FILE).write_bytes(svg)
    record = {"schema_version": B.APPROVAL_SCHEMA, "master": B.MASTER_FILE, "master_sha256": sha256(svg),
              "owner_words": REGISTER_WORDS, "register": REGISTER_LINE, "date": "2026-09-25",
              "source_png": {"path": "fixture.png", "sha256": "0" * 64},
              "tracer": {"name": "a synthetic fixture", "settings": ""},
              "match": {"emitter_vs_mupdf": {"passed": True, "px_disagreeing_over_half": 0}}}
    record.update(overrides)
    (folder / B.APPROVAL_FILE).write_text(json.dumps(record))
    return record


def source_png(path, svg: bytes = POTRACE_STYLE, scale: float = 4.0) -> str:
    """A PNG of ``svg``'s outlines at ``scale`` px per user unit, the whole viewBox — the 'traced PNG' of a fixture,
    drawn by the switch's own nonzero rasteriser (not by the emitter the placement tool measures)."""
    import re

    import numpy as np
    from PIL import Image as PILImage

    from apps.ire import brand_mark as B
    master = B.read_master(svg)
    x0, y0, x1, y1 = master.bounds
    ink_h = int(round((y1 - y0) * scale))
    ink = B.coverage(master, ink_h, margin=0)
    _vx, _vy, vw, vh = (float(v) for v in re.search(rb'viewBox="([^"]*)"', svg).group(1).split())
    canvas = np.zeros((int(vh * scale), int(vw * scale)), dtype=bool)
    oy, ox = int(round(y0 * scale)), int(round(x0 * scale))
    canvas[oy:oy + ink.shape[0], ox:ox + ink.shape[1]] = ink
    rgba = np.zeros(canvas.shape + (4,), dtype=np.uint8)
    rgba[canvas, 3] = 255
    PILImage.fromarray(rgba, "RGBA").save(path)
    return str(path)
