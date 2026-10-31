"""Day 9 (D-D9-5): the Arabic line in a display face the PDF emitter can draw — measured, derived, registered.

THE PROBLEM. The emitter draws Arabic as arabic_reshaper presentation forms (U+FB50–FDFF, U+FE70–FEFF) through
reportlab (``text_intl.shape_ar``, then ``drawString``): no GSUB and no GPOS — no cursive attachment, no mark
positioning, no kerning. A face is emitter-capable when its cmap carries the 36 basic letters, every presentation form
the reshaper emits for them in every joining position and every mark the path keeps, and reportlab reads the file
(``type_book.EMITTER_CAPABLE_MEANS``). The type book's Arabic display faces are not: El Messiri and Mirza lack the 36
isolated forms, Reem Kufi and Aref Ruqaa all 119. Reem Kufi and Aref Ruqaa also lack the lam-alef ligatures the reshaper
writes (U+FEF5–FEFC), which fall outside the 119 the check counts — ظلال needs U+FEFC — and none of the four carries the
Allah ligature U+FDF2 the reshaper writes by default.

THE DERIVATION (``derive``). Every form the emitter's path writes is covered: the joining forms the check counts
(``font_roles._arabic_forms_the_emitter_emits``), the eight lam-alef ligatures and U+FDF2 (``emitted_forms``). For each
form we ask the face what it draws for those letters in that joining position. HarfBuzz shapes the letters alone in a
zero-width-joiner context (isol X, init X+ZWJ, medi ZWJ+X+ZWJ, fina ZWJ+X), with the face's own GSUB (ccmp, locl,
isol/init/medi/fina, rlig, liga, calt …) and GPOS. The HarfBuzz used is the build Pillow ships, the one its raqm layout
links (``harfbuzz``), so the reference and the derivation shape alike. One glyph at no offset and at its own advance:
the form's cmap entry points at that glyph. Several glyphs (a dotless body and the dots GPOS places on it, or Reem
Kufi's lam and alef): a new composite glyph of exactly those glyphs at exactly those offsets, with their advance. A form
the face's cmap already carries keeps the face's own glyph. The family is renamed "<family> PF" (OFL good practice)
and DSIG is dropped, since a changed file cannot keep a signature. The timestamps are kept, so the bytes are
deterministic. The file is written under ``font_instances.DERIVED_DIR`` (``var/`` is git-ignored: an internal build
file, never distributed, never granted separately; the GRANTED face is the verification subject), with its provenance
and its OFL text beside it.

THE MEASURE (``measure``). The descriptor is drawn two ways at one size. The REFERENCE is fully shaped by PIL's raqm
layout (features on). The EMITTER WAY draws the reshaper + bidi presentation-form string with PIL's basic layout (cmap
and advances only, as reportlab draws) from the derived face. A third raster comes from reportlab's own drawString of
the same string, through MuPDF. Compared: ink IoU after aligning the ink boxes (centred, then a ±3 px search); the
connected ink components each side holds that the other lacks (a dot lost, a join broken: missing, extra, split,
merged); and the joins read from the shaping itself — the vertical and horizontal moves GPOS makes between two joined
letters, which the emitter does not make. Noto Naskh Arabic Bold, emitter-capable as granted and the production
fallback, is the control.
"""
from __future__ import annotations

import ctypes
import datetime
import hashlib
import io
import json
import math
import os
import tempfile
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]                                  # the repo
RECORD_DIR = ROOT / 'docs' / 'audit' / 'day-9' / 'fonts'
SPECIMEN_NAME = 'arabic-display-specimen.png'
RECORD_NAME = 'arabic-display.json'
SCHEMA = 'day9_arabic_display/1'
#: the surface the emitter proof's document declares (not in font_roles.EXEMPT_SURFACES: drawn by the layer's own path)
SURFACE = 'apps/ire/arabic_display.py::emitter_proof'
#: the brief's Arabic descriptor, verbatim (truthful_concept.COPY['descriptor_ar'])
DESCRIPTOR = 'باليت ظلال العيون'
ZWJ = '‍'
FAMILY_SUFFIX = ' PF'
POSITIONS = {'<isolated>': 'isol', '<initial>': 'init', '<medial>': 'medi', '<final>': 'fina'}
#: the ligatures the reshaper writes by default beyond the joining forms the check counts: lam with each alef, alone and
#: joined (U+FEF5–FEFC), and the word Allah (U+FDF2) — arabic_reshaper 3's default configuration
LIGATURE_PROBES = ('لا', 'لأ', 'لإ', 'لآ', 'بلا', 'بلأ', 'بلإ', 'بلآ', 'الله')
#: the measure's scale: 160 px to the em (about 19.8 mm of em at the lid's 8.08 px/mm) — large enough that one pixel of
#: antialiasing is not a measured difference
MEASURE_EM_PX = 160
#: the lid's working scale (1536 px across the 190 mm lid) and the Arabic descriptor's alif on Day 8's directions
LID_PX_PER_MM = 1536 / 190.0
LID_ALIF_MM = 3.1
#: ink is a pixel at least half covered
INK_LEVEL = 128
#: the alignment search after the ink boxes are centred on one another
SHIFT_PX = 3
#: the specimen's scale: 80 px to the em
SPECIMEN_EM_PX = 80
#: every drawing is made at 4 × and brought down by Lanczos, as the engine's own render is (truthful_concept.render):
#: measured on El Messiri 500 at 160 px, drawn directly, PIL's basic layout rounds each advance to a whole hinted pixel
#: (110 for 109.92) and raqm's fractional placing leaves antialiased gaps at joins (19 components against 16) — IoU
#: 0.9445 between two drawings of the same glyphs; at 4 × it reads 0.984 and 16 components each
SUPERSAMPLE = 4
#: COMPOSITE_FLAGS: ROUND_XY_TO_GRID, as font editors write a component
COMPOSITE_FLAGS = 0x0004

#: The candidates (catalogue stems from the type book's Arabic part, docs/audit/day-8/fonts/type-book.json), each
#: family at 500 and 700 where it has them: El Messiri 500/700 and Mirza 500/600 (the GRANTED pool, D-D7-1), Reem Kufi
#: at static instances of its variable file at 500 and 700 (font_instances.static_at), Aref Ruqaa 400/700 (the house).
CANDIDATES = (
    {'key': 'el-messiri-500', 'family': 'El Messiri', 'stem': 'fonts_el-messiri_elmessiri-medium_55c1644f5da510f6', 'weight': 500.0},
    {'key': 'el-messiri-700', 'family': 'El Messiri', 'stem': 'fonts_el-messiri_elmessiri-bold_0a187df176398376', 'weight': 700.0},
    {'key': 'mirza-500', 'family': 'Mirza', 'stem': 'fonts_mirza-medium_mirza-medium_6650a32018359d62', 'weight': 500.0},
    {'key': 'mirza-600', 'family': 'Mirza', 'stem': 'fonts_mirza-semibold_mirza-semibold_5d2c26a81c411a8a', 'weight': 600.0},
    {'key': 'reem-kufi-500', 'family': 'Reem Kufi', 'stem': 'ReemKufi[wght]', 'weight': 500.0},
    {'key': 'reem-kufi-700', 'family': 'Reem Kufi', 'stem': 'ReemKufi[wght]', 'weight': 700.0},
    {'key': 'aref-ruqaa-400', 'family': 'Aref Ruqaa', 'stem': 'ArefRuqaa-Regular', 'weight': 400.0},
    {'key': 'aref-ruqaa-700', 'family': 'Aref Ruqaa', 'stem': 'ArefRuqaa-Bold', 'weight': 700.0},
)
#: the control: emitter-capable as granted, the production fallback (D-D9-5), drawn from its own file
CONTROL = {'key': 'noto-naskh-700', 'family': 'Noto Naskh Arabic', 'stem': 'NotoNaskhArabic-Bold', 'weight': 700.0,
           'control': True}


class HarfBuzzUnavailable(RuntimeError):
    """No HarfBuzz library this process can load: the derivation and the join measure cannot run."""


# --- HarfBuzz, the build Pillow's raqm layout links ------------------------------------------------------------------

class _GlyphInfo(ctypes.Structure):
    _fields_ = [('codepoint', ctypes.c_uint32), ('mask', ctypes.c_uint32), ('cluster', ctypes.c_uint32),
                ('var1', ctypes.c_uint32), ('var2', ctypes.c_uint32)]


class _GlyphPosition(ctypes.Structure):
    _fields_ = [('x_advance', ctypes.c_int32), ('y_advance', ctypes.c_int32), ('x_offset', ctypes.c_int32),
                ('y_offset', ctypes.c_int32), ('var', ctypes.c_uint32)]


_CLUSTER_LEVEL_CHARACTERS = 2          # HB_BUFFER_CLUSTER_LEVEL_CHARACTERS: every character keeps its own cluster
_HB: dict = {}


def _harfbuzz_path() -> Path:
    """The libharfbuzz Pillow ships beside its own modules (macOS ``PIL/.dylibs``, Linux ``pillow.libs``), else the
    system's; HarfBuzzUnavailable where there is none."""
    import ctypes.util

    import PIL
    base = Path(PIL.__file__).resolve().parent
    found = (sorted(base.glob('.dylibs/libharfbuzz*')) + sorted(base.parent.glob('pillow.libs/libharfbuzz*'))
             + sorted(base.parent.glob('Pillow.libs/libharfbuzz*')))
    if found:
        return found[0]
    name = ctypes.util.find_library('harfbuzz')
    if name:
        return Path(name)
    raise HarfBuzzUnavailable('no libharfbuzz beside Pillow and none on the system')


def harfbuzz() -> dict:
    """``{'lib', 'path', 'version', 'raqm_harfbuzz', 'same_build'}`` — the loaded library, its version, and the
    version Pillow reports for the HarfBuzz its raqm layout links."""
    if 'lib' in _HB:
        return _HB
    from PIL import features
    path = _harfbuzz_path()
    lib = ctypes.CDLL(str(path))
    vp, c_uint, c_int = ctypes.c_void_p, ctypes.c_uint, ctypes.c_int
    sig = {'hb_version_string': ([], ctypes.c_char_p), 'hb_blob_create_from_file': ([ctypes.c_char_p], vp),
           'hb_face_create': ([vp, c_uint], vp), 'hb_face_get_upem': ([vp], c_uint),
           'hb_face_get_glyph_count': ([vp], c_uint), 'hb_font_create': ([vp], vp),
           'hb_font_set_scale': ([vp, c_int, c_int], None), 'hb_buffer_create': ([], vp),
           'hb_buffer_add_utf32': ([vp, ctypes.POINTER(ctypes.c_uint32), c_int, c_uint, c_int], None),
           'hb_buffer_set_cluster_level': ([vp, c_int], None), 'hb_buffer_guess_segment_properties': ([vp], None),
           'hb_shape': ([vp, vp, vp, c_uint], None),
           'hb_buffer_get_glyph_infos': ([vp, ctypes.POINTER(c_uint)], ctypes.POINTER(_GlyphInfo)),
           'hb_buffer_get_glyph_positions': ([vp, ctypes.POINTER(c_uint)], ctypes.POINTER(_GlyphPosition)),
           'hb_buffer_destroy': ([vp], None), 'hb_font_destroy': ([vp], None), 'hb_face_destroy': ([vp], None),
           'hb_blob_destroy': ([vp], None)}
    for fn, (args, res) in sig.items():
        f = getattr(lib, fn)
        f.argtypes, f.restype = args, res
    version = lib.hb_version_string().decode()
    raqm = features.version('harfbuzz')
    if version != raqm:
        raise HarfBuzzUnavailable('the HarfBuzz loaded (%s, %s) is not the one raqm links (%s): the joins would be read '
                                  'from another shaper than the reference' % (version, path, raqm))
    _HB.update(lib=lib, path=str(path), version=version, raqm_harfbuzz=raqm, same_build=True)
    return _HB


def shape(path, text: str) -> list[dict]:
    """``text`` shaped by HarfBuzz with the face's own GSUB and GPOS (its default features; direction, script and
    language guessed: Arabic, right to left), every character its own cluster. ``[{'gid', 'name', 'cluster', 'pen',
    'x', 'y', 'x_advance'}]`` in visual order (left to right), in font units — ``pen`` where the glyph's advance starts,
    ``x``/``y`` where it is drawn (pen plus offset); ``cluster`` the index of the character it came from."""
    from fontTools.ttLib import TTFont
    hb = harfbuzz()['lib']
    with TTFont(str(path), lazy=True) as ft:
        order = ft.getGlyphOrder()
    blob = hb.hb_blob_create_from_file(str(path).encode())
    face = hb.hb_face_create(blob, 0)
    font = hb.hb_font_create(face)
    buf = hb.hb_buffer_create()
    try:
        if hb.hb_face_get_glyph_count(face) != len(order):
            raise HarfBuzzUnavailable('HarfBuzz did not read %s (%d glyphs, the file holds %d)'
                                      % (path, hb.hb_face_get_glyph_count(face), len(order)))
        upem = hb.hb_face_get_upem(face)
        hb.hb_font_set_scale(font, upem, upem)
        codes = (ctypes.c_uint32 * len(text))(*[ord(c) for c in text])
        hb.hb_buffer_add_utf32(buf, codes, len(text), 0, len(text))
        hb.hb_buffer_set_cluster_level(buf, _CLUSTER_LEVEL_CHARACTERS)
        hb.hb_buffer_guess_segment_properties(buf)
        hb.hb_shape(font, buf, None, 0)
        n = ctypes.c_uint()
        infos = hb.hb_buffer_get_glyph_infos(buf, ctypes.byref(n))
        places = hb.hb_buffer_get_glyph_positions(buf, ctypes.byref(n))
        out, pen = [], 0
        for i in range(n.value):
            gi, gp = infos[i], places[i]
            out.append({'gid': int(gi.codepoint), 'name': order[gi.codepoint], 'cluster': int(gi.cluster), 'pen': pen,
                        'x': pen + gp.x_offset, 'y': int(gp.y_offset), 'x_advance': int(gp.x_advance)})
            pen += gp.x_advance
        return out
    finally:
        hb.hb_buffer_destroy(buf)
        hb.hb_font_destroy(font)
        hb.hb_face_destroy(face)
        hb.hb_blob_destroy(blob)


# --- the forms the emitter's path writes -----------------------------------------------------------------------------

def _is_form(ch: str) -> bool:
    return 0xFB50 <= ord(ch) <= 0xFDFF or 0xFE70 <= ord(ch) <= 0xFEFF


def form_of(ch: str) -> tuple[str, str] | None:
    """``(position, letters)`` of a presentation-form character from its Unicode decomposition — ``('fina', 'لا')``
    for U+FEFC — or None for any other character."""
    if not _is_form(ch):
        return None
    tag, _, rest = unicodedata.decomposition(ch).partition(' ')
    position = POSITIONS.get(tag)
    if position is None or not rest:
        return None
    return position, ''.join(chr(int(h, 16)) for h in rest.split())


def emitted_forms() -> dict[int, dict]:
    """Every presentation form the emitter's path writes — the joining forms of the 36 letters in every position the
    check counts (``font_roles._arabic_forms_the_emitter_emits``) and the ligatures the reshaper writes by default
    (``LIGATURE_PROBES``) — ``{codepoint: {'char', 'name', 'position', 'letters', 'counted_by_check'}}``."""
    from apps.dielines.exporters.text_intl import _libs
    from apps.ire import font_roles
    counted = set(font_roles._arabic_forms_the_emitter_emits())
    reshape = _libs(True)[0]
    cps = set(counted)
    for probe in LIGATURE_PROBES:
        cps |= {ord(ch) for ch in reshape(probe) if _is_form(ch)}
    out = {}
    for cp in sorted(cps):
        form = form_of(chr(cp))
        if form is None:
            raise ValueError('U+%04X is not a presentation form with a joining position' % cp)
        out[cp] = {'char': chr(cp), 'name': unicodedata.name(chr(cp)), 'position': form[0], 'letters': form[1],
                   'counted_by_check': cp in counted}
    return out


def _context(letters: str, position: str) -> tuple[str, range]:
    """The string the letters are shaped in to draw them at ``position``, and their indices in it."""
    if position == 'isol':
        return letters, range(0, len(letters))
    if position == 'init':
        return letters + ZWJ, range(0, len(letters))
    if position == 'medi':
        return ZWJ + letters + ZWJ, range(1, len(letters) + 1)
    if position == 'fina':
        return ZWJ + letters, range(1, len(letters) + 1)
    raise ValueError('no joining position %r' % position)


def drawn_form(path, letters: str, position: str, *, advances: dict | None = None) -> dict:
    """What the face at ``path`` draws for ``letters`` at ``position``: ``{'glyphs': [{'name', 'x', 'y'}], 'advance',
    'single'}`` — the glyphs of the letters' clusters placed from the first one's pen, in font units; ``single`` when it
    is one glyph at no offset and at its own advance (``advances``: the face's hmtx widths, read when not given)."""
    text, idx = _context(letters, position)
    glyphs = [g for g in shape(path, text) if g['cluster'] in idx]
    if not glyphs or any(g['gid'] == 0 for g in glyphs):
        raise ValueError('%s draws no glyph for %r at %s' % (Path(path).name, letters, position))
    origin = min(g['pen'] for g in glyphs)
    parts = [{'name': g['name'], 'x': int(g['x'] - origin), 'y': int(g['y'])} for g in glyphs]
    advance = int(sum(g['x_advance'] for g in glyphs))
    if advances is None:
        from fontTools.ttLib import TTFont
        with TTFont(str(path), lazy=True) as ft:
            advances = {p['name']: ft['hmtx'][p['name']][0] for p in parts}
    single = len(parts) == 1 and parts[0]['x'] == 0 and parts[0]['y'] == 0 and advances[parts[0]['name']] == advance
    return {'glyphs': parts, 'advance': advance, 'single': single}


# --- the source of a candidate, and the derived face -----------------------------------------------------------------

def _sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rel(path) -> str:
    p = Path(path).resolve()
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _licence_evidence(stem: str, entry: dict) -> dict:
    """The licence and its evidence for the catalogue face ``stem``, as the type book reads it: a pool face's wording
    embedded in the face and the Day 7 grant's evidence file; a house face's licence file (its digest as PROVENANCE.json
    records it)."""
    from apps.ire import font_pool
    from apps.ire import type_book as TB
    if entry.get('origin') == font_pool.ORIGIN:
        return {'licence': entry['licence'], 'evidence': 'licence text embedded in the face (name IDs 13/14), drawn from '
                                                         'the Day 6 census; the Day 7 grant\'s evidence file',
                'evidence_path': _rel(font_pool.EVIDENCE), 'evidence_sha256': font_pool.GRANTED_EVIDENCE_SHA256,
                'licence_file': None}
    path = Path(entry['path']).resolve()
    prov = json.loads((path.parents[1] / 'PROVENANCE.json').read_text()) if (path.parents[1] / 'PROVENANCE.json').exists() else {}
    for folder, fam in (prov.get('families') or {}).items():
        for f in fam.get('files') or []:
            if f.get('licence_file') and (path.parents[1] / folder / f['file']).resolve() == path:
                lic = TB._licence_file_evidence(path.parents[1] / folder / f['licence_file'], f.get('licence_sha256'))
                if lic is None:
                    raise ValueError('the licence file of %s is missing or its digest moved' % stem)
                return dict(lic, licence_file=lic['evidence_path'])
    noto = TB._licence_file_evidence(path.parent / ('%s.OFL.txt' % path.stem), None) or TB._licence_file_evidence(
        path.parent / 'OFL.txt', None)
    if noto is None:
        raise ValueError('no licence evidence for %s' % stem)
    return dict(noto, licence_file=noto['evidence_path'])


def source_of(candidate: dict) -> dict:
    """The file a candidate draws and the GRANTED face it is: a static face its own file; a variable face its static
    instance at the candidate's weight (``font_instances.static_at``; made first, as the type book makes one, where it
    is absent), every other axis at its default."""
    from apps.ire import font_instances, font_roles
    stem = candidate['stem']
    entry = font_roles.catalogue()[stem]
    granted = Path(entry['path'])
    made_now = False
    if entry.get('variable'):
        lic = _licence_evidence(stem, entry)
        made = font_instances.static_at(stem, entry['sha256'], candidate['weight'])
        if made is None:
            font_instances.make_instance(granted, {'wght': candidate['weight']}, family=entry.get('family') or stem,
                                         licence=lic['licence'], source_stem=stem)
            made = font_instances.static_at(stem, entry['sha256'], candidate['weight'])
            made_now = True
        if made is None:
            raise ValueError('no static instance of %s at %g' % (stem, candidate['weight']))
        drawn, axes = Path(made['path']), dict(made['axes'])
    else:
        drawn, axes = granted, {}
    return {'key': candidate['key'], 'family': candidate['family'], 'stem': stem, 'weight': float(candidate['weight']),
            'origin': entry.get('origin'), 'granted_path': str(granted), 'granted_sha256': entry['sha256'],
            'postscript': entry['postscript'], 'path': str(drawn), 'sha256': _sha256(drawn), 'axes': axes,
            'instance_made_now': made_now, 'licence': _licence_evidence(stem, entry)}


def _renamed(font, suffix: str, unique_tail: str) -> dict:
    """The face's names with ``suffix`` after its family (name IDs 1, 4, 16, 18, 21), its PostScript name (6) with the
    suffix's letters after the family's, and a unique ID (3) of its own; ``{'family', 'postscript', 'was'}``."""
    name = font['name']
    family = name.getDebugName(16) or name.getDebugName(1)
    ps_old = name.getDebugName(6)
    ps_family = family.replace(' ', '')
    tag = suffix.replace(' ', '')
    if ps_old.startswith(ps_family):
        ps_new = ps_family + tag + ps_old[len(ps_family):]
    else:
        head, sep, tail = ps_old.partition('-')
        ps_new = head + tag + sep + tail
    was = {'family': family, 'postscript': ps_old, 'full': name.getDebugName(4)}
    for rec in name.names:
        text = rec.toUnicode()
        if rec.nameID in (1, 4, 16, 18, 21):
            rec.string = (family + suffix + text[len(family):]) if text.startswith(family) else text + suffix
        elif rec.nameID == 6:
            rec.string = ps_new
        elif rec.nameID == 3:
            rec.string = '%s;%s' % (ps_new, unique_tail)
    return {'family': family + suffix, 'postscript': ps_new, 'full': name.getDebugName(4), 'was': was}


def _licence_text(src: dict, base: str, out_dir: Path) -> dict:
    """The derived face's licence text beside it, as OFL 1.1 asks of a Modified Version (the copyright notice and the
    licence): a house face's own licence file, byte for byte; a pool face's copyright notice (its name ID 0) above the
    OFL 1.1 text of a tracked licence file. ``{'path', 'sha256', 'made_from'}``."""
    from fontTools.ttLib import TTFont
    path = out_dir / (base + '.OFL.txt')
    held = src['licence'].get('licence_file')
    if held:
        data = (ROOT / held).read_bytes()
        made_from = {'licence_file': held, 'sha256': _sha256(ROOT / held), 'how': 'the source family\'s own licence file, verbatim'}
    else:
        body_file = Path(__file__).resolve().parents[2] / 'static' / 'fonts' / 'brand2026' / 'Reem_Kufi' / 'OFL.txt'
        body = body_file.read_text(encoding='utf-8')
        start = body.index('This Font Software is licensed under the SIL Open Font License, Version 1.1.')
        with TTFont(src['granted_path'], lazy=True) as ft:
            notice = ft['name'].getDebugName(0) or ''
        data = ('%s\n\n%s' % (notice.strip(), body[start:])).encode('utf-8')
        made_from = {'copyright_notice': 'the face\'s own name ID 0', 'licence_body': _rel(body_file),
                     'licence_body_sha256': _sha256(body_file),
                     'how': 'the face\'s copyright notice above the OFL 1.1 text (from "This Font Software is licensed '
                            'under ..." to its end) of a tracked OFL licence file'}
    if not path.exists() or path.read_bytes() != data:
        tmp = path.with_suffix('.tmp')
        tmp.write_bytes(data)
        os.replace(tmp, path)
    return {'path': _rel(path), 'sha256': hashlib.sha256(data).hexdigest(), 'made_from': made_from}


def derive(src: dict, *, out_dir=None) -> dict:
    """The emitter-capable face derived from ``src`` (``source_of``): every form ``emitted_forms`` lists that the
    face's cmap lacks mapped to what the face draws for it (``drawn_form``: its glyph, or a composite of its glyphs at
    their offsets), the family renamed "<family> PF", DSIG dropped, timestamps kept. Written as ``<PostScript>.ttf`` under
    ``out_dir`` (default ``font_instances.DERIVED_DIR``) with ``<PostScript>.json`` provenance and ``<PostScript>.OFL.txt``
    beside it; an existing file with the same bytes is kept, and its provenance with it. Returns the provenance."""
    from fontTools import version as fonttools_version
    from fontTools.ttLib import TTFont
    from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphComponent

    from apps.ire import font_instances, font_roles
    out_dir = Path(out_dir) if out_dir is not None else font_instances.DERIVED_DIR
    font = TTFont(src['path'], recalcTimestamp=False)
    if 'glyf' not in font:
        raise ValueError('only TrueType outlines are derived here (glyf composites): %s' % src['path'])
    cmap = font.getBestCmap()
    glyf, hmtx = font['glyf'], font['hmtx']
    for tag in ('post', 'maxp', 'hhea', 'head'):
        font[tag]                                                              # recompiled with the new glyphs
    advances = {g: hmtx[g][0] for g in font.getGlyphOrder()}
    added, kept, composites = [], [], 0
    for cp, form in emitted_forms().items():
        drawn = drawn_form(src['path'], form['letters'], form['position'], advances=advances)
        names = [p['name'] for p in drawn['glyphs']]
        if cp in cmap:
            kept.append({'codepoint': 'U+%04X' % cp, 'glyph': cmap[cp], 'shaped': names,
                         'agrees': drawn['single'] and names == [cmap[cp]]})
            continue
        if drawn['single']:
            glyph_name = names[0]
        else:
            glyph_name = 'uni%04X.pf' % cp
            g = Glyph()
            g.numberOfContours = -1
            g.components = []
            for part in drawn['glyphs']:
                comp = GlyphComponent()
                comp.glyphName, comp.x, comp.y, comp.flags = part['name'], part['x'], part['y'], COMPOSITE_FLAGS
                g.components.append(comp)
            glyf[glyph_name] = g
            g.recalcBounds(glyf)
            hmtx[glyph_name] = (drawn['advance'], int(getattr(g, 'xMin', 0)))
            composites += 1
        for table in font['cmap'].tables:
            if table.isUnicode() and table.format != 14:
                table.cmap[cp] = glyph_name
        added.append({'codepoint': 'U+%04X' % cp, 'char': form['char'], 'name': form['name'], 'letters': form['letters'],
                      'position': form['position'], 'counted_by_check': form['counted_by_check'], 'glyph': glyph_name,
                      'components': None if drawn['single'] else drawn['glyphs'], 'advance': drawn['advance']})
    if glyf.glyphOrder is not font.getGlyphOrder():
        font.setGlyphOrder(list(glyf.glyphOrder))
    names = _renamed(font, FAMILY_SUFFIX, 'derived from sha256 %s' % src['sha256'][:16])
    dropped = [t for t in ('DSIG', 'hdmx', 'LTSH', 'VDMX') if t in font]
    for t in dropped:
        del font[t]
    buf = io.BytesIO()
    font.save(buf)
    data = buf.getvalue()
    sha = hashlib.sha256(data).hexdigest()
    base = names['postscript']
    if base in font_roles.catalogue():
        raise ValueError('the derived stem %s is a catalogue stem' % base)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / (base + '.ttf')
    if not path.exists() or _sha256(path) != sha:
        tmp = path.with_suffix('.tmp')
        tmp.write_bytes(data)
        os.replace(tmp, path)
    meta = out_dir / (base + '.json')
    if meta.exists():
        held = json.loads(meta.read_text(encoding='utf-8'))
        if held.get('sha256') == sha and held.get('schema') == font_instances.DERIVED_SCHEMA:
            ofl = out_dir / Path(held['licence_text']['path']).name
            if ofl.exists() and _sha256(ofl) == held['licence_text']['sha256']:
                return held          # else the licence text is written again, below, with the record
    licence_text = _licence_text(src, base, out_dir)
    with TTFont(src['granted_path'], lazy=True) as ft:
        n = ft['name']
        notice, description, url = n.getDebugName(0), n.getDebugName(13), n.getDebugName(14)
    from PIL import __version__ as pillow_version
    import arabic_reshaper
    record = {
        'schema': font_instances.DERIVED_SCHEMA, 'stem': base, 'path': _rel(path), 'sha256': sha, 'bytes': len(data),
        'postscript': base, 'family': names['family'], 'style': font['name'].getDebugName(17) or font['name'].getDebugName(2),
        'full_name': names['full'], 'wght': src['weight'],
        'source_stem': src['stem'], 'source_path': _rel(src['granted_path']), 'source_sha256': src['granted_sha256'],
        'source_postscript': src['postscript'], 'source_axes': src['axes'],
        'drawn_from': _rel(src['path']), 'drawn_from_sha256': src['sha256'],
        'licence': src['licence']['licence'], 'licence_evidence': {k: v for k, v in src['licence'].items() if k != 'licence_file'},
        'licence_text': licence_text, 'copyright': notice, 'licence_description': description, 'licence_url': url,
        'reserved_font_names': sorted(set(font_instances.reserved_font_names(src['granted_path']))
                                      | set(_reserved_in_licence_file(src))),
        'renamed': {'from': names['was'], 'family': names['family'], 'postscript': base,
                    'why': 'OFL good practice for a Modified Version: a name of its own, whether or not the original '
                           'reserves its name'},
        'cmap_added': added, 'cmap_added_count': len(added), 'composites': composites,
        'cmap_kept': {'count': len(kept), 'agree_with_shaping': sum(1 for k in kept if k['agrees']),
                      'differ': [k for k in kept if not k['agrees']]},
        'tables_dropped': dropped,
        'method': 'every presentation form the emitter writes (font_roles._arabic_forms_the_emitter_emits, the lam-alef '
                  'ligatures U+FEF5–FEFC and U+FDF2) that the face\'s cmap lacks: its letters shaped alone in a ZWJ context '
                  '(isol X, init X+ZWJ, medi ZWJ+X+ZWJ, fina ZWJ+X) by HarfBuzz with the face\'s own GSUB and GPOS; one glyph '
                  'at no offset and its own advance is mapped as it is, several become one composite glyph at their offsets',
        'tool': {'generator': 'apps.ire.arabic_display.derive', 'harfbuzz': harfbuzz()['version'],
                 'harfbuzz_path': harfbuzz()['path'], 'raqm_harfbuzz': harfbuzz()['raqm_harfbuzz'],
                 'fonttools': fonttools_version, 'pillow': pillow_version, 'arabic_reshaper': arabic_reshaper.__version__,
                 'save': 'fontTools TTFont(recalcTimestamp=False): head.modified kept, the bytes deterministic'},
        'made_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'use': 'internal build file under var/ (git-ignored): never distributed, never granted separately; the GRANTED '
               'source is the verification subject (font_roles.resolve_line_face verifies it through the seam and draws '
               'this file)'}
    tmp = out_dir / (base + '.json.tmp')
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    os.replace(tmp, meta)
    return record


def _reserved_in_licence_file(src: dict) -> list[str]:
    """The Reserved Font Names a house face's licence FILE declares (Reem Kufi's reserves "Josefin Sans" there, not in
    its name table)."""
    import re
    held = src['licence'].get('licence_file')
    if not held:
        return []
    text = (ROOT / held).read_text(encoding='utf-8', errors='replace')
    # the copyright header only: the licence body below it defines the term ("Reserved Font Name(s) unless …")
    text = text.split('This Font Software is licensed under', 1)[0]
    out = []
    for m in re.finditer(r'Reserved\s+Font\s+Names?\s*[:"“]*\s*([^.\n]+)', text, flags=re.I):
        for part in re.split(r'["“”]\s*(?:and|,)\s*["“”]|,\s*|\s+and\s+', m.group(1)):
            part = part.strip(' "“”\'')
            if part and part.lower() != 'none' and part not in out:
                out.append(part)
    return out


# --- drawing the line -------------------------------------------------------------------------------------------------

def _shaped() -> str:
    from apps.dielines.exporters.text_intl import shape_ar
    return shape_ar(DESCRIPTOR, keep_harakat=True)


def render_reference(path, text: str = DESCRIPTOR, *, em_px: int):
    """``text`` fully shaped by PIL's raqm layout (HarfBuzz, every default feature on, right to left), ink as 0–255."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(str(path), em_px, layout_engine=ImageFont.Layout.RAQM)
    box = font.getbbox(text, direction='rtl', language='ar')
    pad = em_px // 2
    im = Image.new('L', (box[2] - box[0] + 2 * pad, box[3] - box[1] + 2 * pad), 0)
    ImageDraw.Draw(im).text((pad - box[0], pad - box[1]), text, font=font, fill=255, direction='rtl', language='ar')
    return np.asarray(im)


def render_basic(path, text: str, *, em_px: int):
    """``text`` (already in presentation forms, in visual order) drawn by PIL's basic layout — the cmap and the
    advances, no shaping and no GPOS, as reportlab draws — ink as 0–255."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(str(path), em_px, layout_engine=ImageFont.Layout.BASIC)
    box = font.getbbox(text)
    pad = em_px // 2
    im = Image.new('L', (box[2] - box[0] + 2 * pad, box[3] - box[1] + 2 * pad), 0)
    ImageDraw.Draw(im).text((pad - box[0], pad - box[1]), text, font=font, fill=255)
    return np.asarray(im)


def supersampled(render, *args, em_px: int):
    """``render(*args, em_px=em_px × SUPERSAMPLE)`` brought down by Lanczos to ``em_px`` to the em."""
    import numpy as np
    from PIL import Image
    big = Image.fromarray(render(*args, em_px=em_px * SUPERSAMPLE))
    small = big.resize((max(1, round(big.size[0] / SUPERSAMPLE)), max(1, round(big.size[1] / SUPERSAMPLE))), Image.LANCZOS)
    return np.asarray(small)


def _pdf_ink(pdf_path, *, px_per_pt: float):
    """Page 1 of a PDF rasterised by MuPDF in grey at ``px_per_pt``, ink as 0–255."""
    import fitz
    import numpy as np
    with fitz.open(str(pdf_path)) as pdf:
        pix = pdf[0].get_pixmap(matrix=fitz.Matrix(px_per_pt, px_per_pt), colorspace=fitz.csGRAY, alpha=False)
        grey = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.stride)[:, :pix.w]
    return 255 - grey


def render_reportlab(path, text: str, *, em_px: int):
    """``text`` (presentation forms, visual order) through the emitter's own draw call: reportlab registers the face and
    ``drawString``s the string; MuPDF rasterises the page at ``em_px`` to the em. Ink as 0–255."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont as RLFont
    from reportlab.pdfgen import canvas
    label = 'AD-' + _sha256(path)[:14]
    if label not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(RLFont(label, str(path)))
    size_pt = 100.0
    line_pt = pdfmetrics.stringWidth(text, label, size_pt)
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / 'line.pdf'
        c = canvas.Canvas(str(pdf), pagesize=(line_pt + 2 * size_pt, 3 * size_pt))
        c.setFont(label, size_pt)
        c.drawString(size_pt, size_pt, text)
        c.save()
        return _pdf_ink(pdf, px_per_pt=em_px / size_pt)


# --- comparing two drawings --------------------------------------------------------------------------------------------

def _crop(mask):
    import numpy as np
    rows, cols = np.nonzero(mask.any(axis=1))[0], np.nonzero(mask.any(axis=0))[0]
    if rows.size == 0:
        return mask[:0, :0]
    return mask[rows.min():rows.max() + 1, cols.min():cols.max() + 1]


def _centred(mask, rows: int, cols: int):
    import numpy as np
    out = np.zeros((rows, cols), dtype=bool)
    top, left = (rows - mask.shape[0]) // 2, (cols - mask.shape[1]) // 2
    out[top:top + mask.shape[0], left:left + mask.shape[1]] = mask
    return out


def _iou(a, b) -> float:
    import numpy as np
    union = int(np.logical_or(a, b).sum())
    return float(np.logical_and(a, b).sum()) / union if union else 0.0


def compare(reference, drawn, *, shift_px: int = SHIFT_PX) -> dict:
    """``drawn`` against ``reference`` (ink 0–255 arrays): each cut to its ink box at half coverage, the boxes centred on
    one another, then the best alignment within ±``shift_px``. ``iou`` there and ``iou_centred`` before the search; the
    ink boxes; and the connected ink components (8-connected): the reference's that ``drawn`` misses entirely
    (``missing``: a dot or a letter lost), ``drawn``'s that the reference lacks (``extra``), a reference component
    ``drawn`` breaks into two or more (``split``: a join broken) and a ``drawn`` component joining two or more of the
    reference's (``merged``)."""
    import numpy as np
    from scipy import ndimage
    a, b = _crop(np.asarray(reference) >= INK_LEVEL), _crop(np.asarray(drawn) >= INK_LEVEL)
    if a.size == 0 or b.size == 0:
        return {'iou': 0.0, 'iou_centred': 0.0, 'shift_px': None, 'why': 'no ink on one side'}
    rows = max(a.shape[0], b.shape[0]) + 2 * shift_px
    cols = max(a.shape[1], b.shape[1]) + 2 * shift_px
    big_a, big_b = _centred(a, rows, cols), _centred(b, rows, cols)
    centred = _iou(big_a, big_b)
    best = (centred, 0, 0)
    for dy in range(-shift_px, shift_px + 1):
        for dx in range(-shift_px, shift_px + 1):
            score = _iou(big_a, np.roll(np.roll(big_b, dy, axis=0), dx, axis=1))
            if score > best[0] + 1e-12:
                best = (score, dy, dx)
    score, dy, dx = best
    moved = np.roll(np.roll(big_b, dy, axis=0), dx, axis=1)
    eight = np.ones((3, 3), dtype=bool)
    la, na = ndimage.label(big_a, structure=eight)
    lb, nb = ndimage.label(moved, structure=eight)
    missing = extra = split = merged = 0
    for i in range(1, na + 1):
        hits = set(np.unique(lb[la == i])) - {0}
        missing += not hits
        split += len(hits) >= 2
    for j in range(1, nb + 1):
        hits = set(np.unique(la[lb == j])) - {0}
        extra += not hits
        merged += len(hits) >= 2
    return {'iou': round(score, 4), 'iou_centred': round(centred, 4), 'shift_px': [int(dx), int(dy)],
            'ink_box_px': {'reference': [int(a.shape[1]), int(a.shape[0])], 'drawn': [int(b.shape[1]), int(b.shape[0])]},
            'ink_px': {'reference': int(a.sum()), 'drawn': int(b.sum())},
            'components': {'reference': int(na), 'drawn': int(nb), 'missing': int(missing), 'extra': int(extra),
                           'split': int(split), 'merged': int(merged)}}


def joins(source_path, drawn_path, text: str = DESCRIPTOR) -> dict:
    """The joins of ``text`` read from the shaping itself. The reference is HarfBuzz on the source face with its GSUB
    and GPOS. The emitter way is the presentation-form string from the drawn face's cmap at its advances, every glyph on
    the baseline. For each pair of joined letters: ``dy``, the vertical move GPOS (cursive attachment) makes between them
    and the emitter does not make, and ``dx``, the difference in the distance between them. ``drift`` is how far any
    letter stands from where the shaping puts it, measured from the line's right end, where it starts (a letter's left
    edge is its leftmost glyph with an advance: a ligature shaped as two glyphs starts where its first does). All in
    font units and as fractions of the em. ``units_glyphs_differ`` counts the letters whose reference glyphs (a
    contextual form, marks) are not the ones the emitter draws."""
    from fontTools.ttLib import TTFont

    from apps.dielines.exporters.text_intl import _libs
    reshape, display = _libs(True)
    logical = reshape(text)
    visual = display(logical)
    if visual != logical[::-1]:
        return {'measured': False, 'why': 'the line is not one right-to-left run'}
    spans, i = [], 0
    for ch in logical:
        n = len(unicodedata.normalize('NFKC', ch)) if _is_form(ch) else 1
        spans.append((i, i + n))
        i += n
    if i != len(text):
        return {'measured': False, 'why': 'the presentation forms do not cover the text one to one'}
    ref = shape(source_path, text)
    ref_total = sum(g['x_advance'] for g in ref)
    with TTFont(str(drawn_path), lazy=True) as ft:
        upem = ft['head'].unitsPerEm
        cmap = ft.getBestCmap()
        names = [cmap.get(ord(ch)) for ch in visual]
        widths = {g: ft['hmtx'][g][0] for g in set(names) if g}
        parts = {g: [c.glyphName for c in ft['glyf'][g].components] for g in set(names)
                 if g and g.endswith('.pf') and ft['glyf'][g].isComposite()}
    pen, emit_x = 0, []
    for g in names:
        emit_x.append(pen)
        pen += widths.get(g, 0)
    emit_total = pen
    count = len(logical)
    units = []
    for k, (ch, (a, b)) in enumerate(zip(logical, spans)):
        mine = [g for g in ref if a <= g['cluster'] < b]
        # the unit's left edge is its leftmost advancing glyph (a ligature the face shapes as two glyphs, Noto Naskh's
        # lam-alef, starts at its alef); its vertical move is its widest glyph's (a cursive attachment moves the body)
        advancing = [g for g in mine if g['x_advance']] or mine
        base = max(mine, key=lambda g: abs(g['x_advance'])) if mine else None
        drawn_glyph = names[count - 1 - k]
        form = form_of(ch)
        units.append({'char': ch, 'form': form[0] if form else None,
                      'ref_x': min(g['x'] for g in advancing) if mine else None, 'ref_y': base['y'] if base else 0,
                      'emit_x': emit_x[count - 1 - k],
                      'ref_glyphs': sorted(g['name'] for g in mine),
                      'emit_glyphs': sorted(parts.get(drawn_glyph, [drawn_glyph] if drawn_glyph else []))})
    pairs, written = [], 0
    for k in range(count - 1):
        u, v = units[k], units[k + 1]
        if u['form'] in ('init', 'medi') and v['form'] in ('medi', 'fina'):
            written += 1
        if u['form'] in ('init', 'medi') and v['form'] in ('medi', 'fina') and None not in (u['ref_x'], v['ref_x']):
            dy = (u['ref_y'] - v['ref_y'])
            dx = (u['ref_x'] - v['ref_x']) - (u['emit_x'] - v['emit_x'])
            pairs.append({'pair': 'U+%04X U+%04X' % (ord(u['char']), ord(v['char'])), 'dy_units': int(dy),
                          'dx_units': int(dx)})
    drift = [abs((ref_total - u['ref_x']) - (emit_total - u['emit_x'])) for u in units if u['ref_x'] is not None]
    worst_dy = max((abs(p['dy_units']) for p in pairs), default=0)
    worst_dx = max((abs(p['dx_units']) for p in pairs), default=0)
    worst_drift = max(drift, default=0)
    if len(pairs) != written:
        # a letter HarfBuzz folded into another cluster: its join is not read, so the joins are not measured
        return {'measured': False, 'why': '%d of the %d joins the reshaper wrote could not be read' % (written - len(pairs), written),
                'missing_in_cmap': [ch for ch, g in zip(visual, names) if g is None and not ch.isspace()]}
    return {'measured': True, 'upem': upem, 'joins': len(pairs), 'pairs': pairs,
            'worst_dy_units': worst_dy, 'worst_dy_em': round(worst_dy / upem, 4),
            'worst_dx_units': worst_dx, 'worst_dx_em': round(worst_dx / upem, 4),
            'worst_drift_units': int(worst_drift), 'worst_drift_em': round(worst_drift / upem, 4),
            'joins_moved_vertically': sum(1 for p in pairs if p['dy_units']),
            'units': len(units), 'units_glyphs_differ': sum(1 for u in units if u['ref_glyphs'] != u['emit_glyphs']),
            'missing_in_cmap': [ch for ch, g in zip(visual, names) if g is None and not ch.isspace()]}


def context_sensitivity(path) -> dict:
    """How often the face draws a letter in context from other glyphs than the emitter's form for it alone. Every one
    of the 36 letters is set beside every one of them (N+X, X+N, N+X+N), and the letter's glyphs in that word are compared
    with what the face draws for that presentation form alone (``drawn_form``). A face whose forms never change with
    their neighbours (no contextual alternates) is drawn by the emitter as its shaping draws it in every word.
    ``{'contexts', 'differ', 'share', 'forms': {'U+XXXX': n}}``."""
    from apps.dielines.exporters.text_intl import _libs
    from apps.ire import font_roles
    reshape = _libs(True)[0]
    letters = [chr(c) for c in sorted(font_roles._ARABIC_LETTERS)]
    alone: dict = {}
    total = differ = 0
    forms: dict = {}
    for x in letters:
        for n in letters:
            for word, at in ((n + x, 1), (x + n, 0), (n + x + n, 1)):
                pf = reshape(word)
                if len(pf) != len(word) or not _is_form(pf[at]):
                    continue                                       # a ligature took the letter in
                cp = ord(pf[at])
                if cp not in alone:
                    position, lets = form_of(chr(cp))
                    alone[cp] = sorted(p['name'] for p in drawn_form(path, lets, position)['glyphs'])
                got = sorted(g['name'] for g in shape(path, word) if g['cluster'] == at)
                total += 1
                if got != alone[cp]:
                    differ += 1
                    key = 'U+%04X' % cp
                    forms[key] = forms.get(key, 0) + 1
    return {'contexts': total, 'differ': differ, 'share': round(differ / total, 4) if total else None,
            'forms': dict(sorted(forms.items(), key=lambda kv: -kv[1]))}


#: further lines the measure reads beyond the descriptor — common cosmetic copy chosen to meet the letters the
#: descriptor does not (heh, hah, jeem, kaf, sad, shin, feh, qaf, reh, hamza on alef); probes only, never brief copy
EXTRA_LINES = ('رحيق الورد', 'أحمر شفاه لامع', 'كحل أسود طويل الأمد', 'ظل جفون مخملي', 'بشرة ناعمة ومشرقة', 'صنع في الصين')
#: D-D9-3's print limits for foil: lines at least 0.1 mm, gaps at least 0.2 mm (finer goes to metallic ink)
FOIL_LINE_MM = 0.1
FOIL_GAP_MM = 0.2
#: the raster the print limits are read at: 100 px to the millimetre
PRINT_RASTER_PX_PER_MM = 100.0


def _disk(diameter_px: float):
    import numpy as np
    r = diameter_px / 2.0
    n = int(np.ceil(r))
    y, x = np.mgrid[-n:n + 1, -n:n + 1]
    return (x * x + y * y) <= r * r


def print_limits(drawn_path, *, alif_em: float, alif_mm: float = LID_ALIF_MM) -> dict:
    """The descriptor as the emitter draws it with its alif ``alif_mm`` tall, against D-D9-3's foil limits: the ink a
    ``FOIL_GAP_MM`` disc cannot pass between (``gaps_under_limit_mm2``: closing minus the ink) and the ink a
    ``FOIL_LINE_MM`` disc cannot fill (``lines_under_limit_mm2``: the ink minus its opening), in square millimetres."""
    import numpy as np
    from scipy import ndimage
    em_px = round(alif_mm * PRINT_RASTER_PX_PER_MM / alif_em)
    ink = render_basic(drawn_path, _shaped(), em_px=em_px) >= INK_LEVEL
    if not ink.any():
        raise ValueError('the descriptor drew no ink at alif %s mm: there are no print limits to read' % alif_mm)
    narrow = ndimage.binary_closing(ink, structure=_disk(FOIL_GAP_MM * PRINT_RASTER_PX_PER_MM)) & ~ink
    thin = ink & ~ndimage.binary_opening(ink, structure=_disk(FOIL_LINE_MM * PRINT_RASTER_PX_PER_MM))
    lab, places = ndimage.label(narrow)
    largest = float(np.max(ndimage.sum(narrow, lab, range(1, places + 1)))) if places else 0.0
    area = PRINT_RASTER_PX_PER_MM ** 2
    # the narrow places that lie BETWEEN two separate shapes (two dots, a dot and its letter) — foil would join them —
    # each with the distance between the two shapes; the rest are a single shape's own corners
    shapes, _count = ndimage.label(ink, structure=np.ones((3, 3), bool))
    between = []
    for place in range(1, places + 1):
        zone = ndimage.binary_dilation(lab == place, structure=np.ones((3, 3), bool))
        touching = sorted(set(np.unique(shapes[zone & ink])) - {0})
        if len(touching) < 2:
            continue
        ys, xs = np.nonzero(zone)
        y0, y1 = max(0, ys.min() - 8), ys.max() + 9
        x0, x1 = max(0, xs.min() - 8), xs.max() + 9
        a, b = shapes[y0:y1, x0:x1] == touching[0], shapes[y0:y1, x0:x1] == touching[1]
        apart_px = float(ndimage.distance_transform_edt(~a)[b].min()) - 1.0
        between.append(round(apart_px / PRINT_RASTER_PX_PER_MM, 3))
    between.sort()
    return {'alif_mm': alif_mm, 'em_mm': round(em_px / PRINT_RASTER_PX_PER_MM, 3),
            'line_length_mm': round(_crop(ink).shape[1] / PRINT_RASTER_PX_PER_MM, 2),
            'gaps_under_limit_mm2': round(float(narrow.sum()) / area, 4), 'gap_places': int(places),
            'largest_gap_place_mm2': round(largest / area, 4),
            'lines_under_limit_mm2': round(float(thin.sum()) / area, 4), 'ink_mm2': round(float(ink.sum()) / area, 2),
            'gaps_between_shapes': len(between), 'gaps_between_shapes_mm': between}


def foil_clear_alif(drawn_path, *, alif_em: float, start_mm: float = LID_ALIF_MM, step_mm: float = 0.1,
                    stop_mm: float = 8.0):
    """The smallest alif (mm, in ``step_mm`` steps from ``start_mm``) at which no two of the descriptor's shapes stand
    closer than the foil gap (``print_limits``' gaps_between_shapes is 0); None where none up to ``stop_mm`` does."""
    alif = start_mm
    while alif <= stop_mm + 1e-9:
        if print_limits(drawn_path, alif_em=alif_em, alif_mm=round(alif, 3))['gaps_between_shapes'] == 0:
            return round(alif, 2)
        alif += step_mm
    return None


def _alif_em(path) -> float:
    from apps.ire.text_metrics import ink_extent_em
    return float(ink_extent_em('ا', str(path))[0])


def measure(candidate: dict, *, work_dir) -> dict:
    """One candidate measured: its source (``source_of``), the face derived from it into ``work_dir`` (the control is
    drawn from its own file), the reference, the emitter way and reportlab's own draw at ``MEASURE_EM_PX`` (each made at
    ``SUPERSAMPLE`` ×), the joins, the further lines, the context share and the print limits. The specimen's drawings
    ride under ``'_images'``."""
    from apps.dielines.exporters.text_intl import shape_ar
    from apps.ire import font_roles
    t0 = time.time()
    src = source_of(candidate)
    if candidate.get('control'):
        drawn, prov = Path(src['path']), None
    else:
        prov = derive(src, out_dir=Path(work_dir) / candidate['key'])
        drawn = ROOT / prov['path'] if not Path(prov['path']).is_absolute() else Path(prov['path'])
    shaped = _shaped()
    ref = supersampled(render_reference, src['path'], DESCRIPTOR, em_px=MEASURE_EM_PX)
    basic = supersampled(render_basic, drawn, shaped, em_px=MEASURE_EM_PX)
    rl = supersampled(render_reportlab, drawn, shaped, em_px=MEASURE_EM_PX)
    capability = font_roles._inspect(Path(drawn))
    alif_em = _alif_em(src['path'])
    from fontTools.ttLib import TTFont
    with TTFont(src['path'], lazy=True) as ft:
        held = set((ft.getBestCmap() or {}).keys())
    lines = []
    for line in EXTRA_LINES:
        got = compare(supersampled(render_reference, src['path'], line, em_px=MEASURE_EM_PX),
                      supersampled(render_basic, drawn, shape_ar(line, keep_harakat=True), em_px=MEASURE_EM_PX))
        j = joins(src['path'], drawn, line)
        lines.append({'line': line, 'iou': got['iou'], 'components': got['components'],
                      'worst_dy_units': j.get('worst_dy_units'), 'worst_dy_em': j.get('worst_dy_em'),
                      'worst_drift_units': j.get('worst_drift_units'), 'units_glyphs_differ': j.get('units_glyphs_differ'),
                      'missing_in_cmap': j.get('missing_in_cmap')})
    row = {'key': candidate['key'], 'family': candidate['family'], 'stem': candidate['stem'], 'weight': candidate['weight'],
           'control': bool(candidate.get('control')),
           'source': {k: (_rel(v) if k in ('granted_path', 'path') else v) for k, v in src.items() if k != 'licence'},
           'licence': src['licence']['licence'],
           'source_carries': {'forms_the_check_counts_missing': len(set(font_roles._arabic_forms_the_emitter_emits()) - held),
                              'lam_alef_ligatures': sum(1 for cp in range(0xFEF5, 0xFEFD) if cp in held),
                              'allah_ligature': 0xFDF2 in held},
           'drawn_face': {'path': _rel(drawn), 'sha256': _sha256(drawn),
                          'postscript': capability['postscript'], 'arabic_forms_missing': capability['arabic_forms_missing'],
                          'arabic_marks_missing': capability['arabic_marks_missing'], 'emitter_capable_cmap': capability['arabic']},
           'forms': ({'added': prov['cmap_added_count'], 'composites': prov['composites'], 'kept': prov['cmap_kept']['count'],
                      'kept_agree_with_shaping': prov['cmap_kept']['agree_with_shaping'],
                      'reserved_font_names': prov['reserved_font_names']} if prov else None),
           'emitter_way': compare(ref, basic), 'reportlab': compare(ref, rl), 'reportlab_vs_basic': compare(basic, rl),
           'joins': joins(src['path'], drawn),
           'further_lines': {'lines': lines, 'iou_min': min(x['iou'] for x in lines), 'iou_max': max(x['iou'] for x in lines),
                             'worst_dy_em': _worst([x['worst_dy_em'] for x in lines]),
                             'worst_drift_units': _worst([x['worst_drift_units'] for x in lines]),
                             'units_glyphs_differ': _worst([x['units_glyphs_differ'] for x in lines], sum)},
           'context': context_sensitivity(src['path']),
           'print_limits': print_limits(drawn, alif_em=alif_em),
           'alif_em': round(alif_em, 4)}
    j = row['joins']
    if j.get('measured'):
        j['worst_dy_px'] = round(j['worst_dy_em'] * MEASURE_EM_PX, 1)
        j['worst_drift_px'] = round(j['worst_drift_em'] * MEASURE_EM_PX, 1)
        j['worst_dy_mm_at_lid_alif'] = round(j['worst_dy_em'] * LID_ALIF_MM / alif_em, 3)
    row['seconds'] = round(time.time() - t0, 1)
    row['_images'] = {'reference': supersampled(render_reference, src['path'], DESCRIPTOR, em_px=SPECIMEN_EM_PX),
                      'emitter': supersampled(render_basic, drawn, shaped, em_px=SPECIMEN_EM_PX)}
    return row


def _worst(values: list, combine=max):
    """The further lines' aggregate: unmeasured (None) when any line's joins were not measured — never read as 0."""
    return None if any(v is None for v in values) else combine(values)


# --- the choice ---------------------------------------------------------------------------------------------------------

#: THE THRESHOLD, from the measurements of 2026-10-20 (arabic-display.json): the descriptor's ink IoU, emitter way against
#: raqm, 160 px to the em drawn at 4 ×. The faces whose glyphs and joins the emitter reproduces exactly (no join moved, no
#: letter drawn from other glyphs) read 0.984–0.995 (El Messiri 500/700, Reem Kufi 500/700) and the control, Noto Naskh
#: Arabic Bold, reads 0.989; the residue is FreeType's rounding (El Messiri 500 drawn at 1 × read 0.9445 for the same
#: glyphs). The faces the emitter does not reproduce read at most 0.884 (Mirza: contextual forms and kerning lost; Aref
#: Ruqaa 0.16–0.24: cursive steps of 0.26 em). 0.95 lies 0.034 under the lowest faithful reading and 0.066 over the
#: highest unfaithful one.
IOU_FAITHFUL = 0.95
#: a join the emitter leaves where GPOS moves it: at most 0.01 em (El Messiri's cursive attachment moves joins by at most
#: 5 units of 1000 on the further lines, 0.02 mm at the lid's alif; Aref Ruqaa's by 259)
JOIN_DY_EM_MAX = 0.01
#: the share of letter-beside-letter contexts in which the face draws a letter from other glyphs than the emitter's form:
#: at most 0.5 % — the control's own share (Noto Naskh Arabic Bold, 13 of 3,872: 0.34 %) rounded up; El Messiri 0, Mirza
#: 0.7 %, Reem Kufi 3.5 % (its required contextual alternates), Aref Ruqaa 27 %
CONTEXT_SHARE_MAX = 0.005
#: display character, strongest first — the executor's reading of the four designs, stated, not measured: Aref Ruqaa a
#: calligraphic Ruqʿa hand; Reem Kufi a decorative Fatimid-style Kufi; El Messiri a display Naskh with calligraphic
#: terminals and open counters; Mirza a Naskh drawn for text
DISPLAY_RANK = ('Aref Ruqaa', 'Reem Kufi', 'El Messiri', 'Mirza')


def faithful(row: dict) -> dict:
    """Whether the emitter draws the face as its own shaping does: ``{'faithful', 'tests'}``."""
    e, j, lines, ctx = row['emitter_way'], row['joins'], row['further_lines'], row['context']
    tests = {'descriptor_iou_at_least_%.2f' % IOU_FAITHFUL: e['iou'] >= IOU_FAITHFUL,
             'no_ink_component_missing_or_split': e['components']['missing'] == 0 and e['components']['split'] == 0,
             'joins_within_%.2f_em' % JOIN_DY_EM_MAX: (j.get('measured') is True and j['worst_dy_em'] <= JOIN_DY_EM_MAX
                                                      and lines['worst_dy_em'] is not None
                                                      and lines['worst_dy_em'] <= JOIN_DY_EM_MAX),
             'context_share_at_most_%.3f' % CONTEXT_SHARE_MAX: ctx['share'] is not None and ctx['share'] <= CONTEXT_SHARE_MAX,
             'every_form_in_the_cmap': 'missing_in_cmap' in j and j['missing_in_cmap'] == [] and row['drawn_face']['emitter_capable_cmap']}
    if not row['control']:
        # a wrong letter form can read a high IoU (ح for خ, 0.995): the candidates must also draw every ink component
        # once, every further line whole and above the threshold, and every letter from the glyphs its face shapes
        parts = ('missing', 'split', 'extra', 'merged')
        tests['no_ink_component_extra_or_merged'] = e['components']['extra'] == 0 and e['components']['merged'] == 0
        tests['further_lines_whole_and_at_least_%.2f' % IOU_FAITHFUL] = all(
            x['iou'] >= IOU_FAITHFUL and all(x['components'][k] == 0 for k in parts) for x in lines['lines'])
        tests['glyphs_as_the_face_shapes_them'] = j.get('units_glyphs_differ') == 0 and lines['units_glyphs_differ'] == 0
    return {'faithful': all(tests.values()), 'tests': tests}


def choose(rows: list[dict]) -> dict:
    """The face: among the candidates the emitter draws faithfully (``faithful``), the family with the strongest
    display character (``DISPLAY_RANK``), at its heaviest faithful weight; where none is faithful, Noto Naskh Arabic Bold
    as it is granted (D-D9-5)."""
    verdicts = {r['key']: faithful(r) for r in rows}
    ok = [r for r in rows if not r['control'] and verdicts[r['key']]['faithful']]
    if not ok:
        control = next(r for r in rows if r['control'])
        return {'key': control['key'], 'derived': False, 'verdicts': verdicts,
                'why': 'no display face renders faithfully the emitter way: the Arabic line falls back to Noto Naskh Arabic '
                       'Bold (D-D9-5)'}
    best = min(ok, key=lambda r: (DISPLAY_RANK.index(r['family']), -r['weight']))
    return {'key': best['key'], 'family': best['family'], 'weight': best['weight'], 'derived': True, 'verdicts': verdicts,
            'faithful': sorted(r['key'] for r in ok)}


# --- the engine's own proof ---------------------------------------------------------------------------------------------

def emitter_proof(stem: str, weight: float, *, work_dir, source_path) -> dict:
    """The descriptor through the engine: a Document on a non-exempt surface holding one TextRun in the line face
    ``line-face:<stem>@<weight>``, emitted by ``emit_pdf_ai``, read back — the fonts the page embeds, the text MuPDF
    extracts (the visual presentation-form string the emitter drew, and the logical text it stands for), the usage
    record's row for the face and its reconciliation, and the page rasterised against the raqm reference."""
    import fitz

    from apps.ire import font_roles
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, Document, Group, TextRun
    resolved = font_roles.resolve_line_face(stem, weight)
    if resolved.get('refused'):
        raise RuntimeError('the line face %s@%g does not resolve: %s' % (stem, weight, resolved.get('tried')))
    size_pt = 36.0
    run = TextRun(name='descriptor_ar', text=DESCRIPTOR, x=95.0, y=26.0, font=font_roles.line_face_key(stem, weight),
                  size_pt=size_pt, color=Color.from_hex('#000000'), align='center')
    doc = Document(page_w=190.0, page_h=40.0, title='Arabic display proof', metadata={'typography_surface': SURFACE},
                   root=Group(name='root', role='artwork', children=[run]))
    pdf = Path(work_dir) / 'arabic-display-proof.ai'
    usage: dict = {}
    emit_pdf_ai(doc, str(pdf), usage_out=usage)
    with fitz.open(str(pdf)) as f:
        page = f[0]
        embedded = sorted({str(e[3]).split('+', 1)[-1] for e in page.get_fonts(full=True)})
        text = page.get_text('text').strip()
    import numpy as np
    from PIL import Image
    page_ink = _crop_box(_pdf_ink(pdf, px_per_pt=MEASURE_EM_PX * SUPERSAMPLE / size_pt))
    raster = np.asarray(Image.fromarray(page_ink).resize(
        (max(1, round(page_ink.shape[1] / SUPERSAMPLE)), max(1, round(page_ink.shape[0] / SUPERSAMPLE))), Image.LANCZOS))
    reference = supersampled(render_reference, source_path, DESCRIPTOR, em_px=MEASURE_EM_PX)
    row = next((r for r in usage.get('faces', []) if r['postscript'] == resolved.get('postscript')), None)
    return {'pdf': pdf.name, 'line_face': font_roles.line_face_key(stem, weight), 'embedded_fonts': embedded,
            'postscript': resolved.get('postscript'), 'derived_embedded': resolved.get('postscript') in embedded,
            'drawn_path': _rel(resolved['path']), 'granted_path': _rel(resolved['granted_path']),
            'text_extracted': text, **extracted_order(text),
            'usage_row': row, 'reconciliation': (usage.get('reconciliation') or {}),
            'iou_vs_reference': compare(reference, raster)}


def extracted_order(text: str) -> dict:
    """How a PDF's extracted presentation forms stand for the descriptor. The emitter draws the visual (left-to-right)
    string; MuPDF hands it back in logical order (it reorders right-to-left runs). ``order`` is 'logical' or 'visual'
    (None where neither gives the descriptor), ``forms_drawn`` whether the characters are exactly the presentation forms
    the emitter writes, and ``descriptor`` the text their compatibility decomposition (NFKC) spells."""
    from apps.dielines.exporters.text_intl import _libs
    logical_forms = _libs(True)[0](DESCRIPTOR)
    if unicodedata.normalize('NFKC', text) == DESCRIPTOR:
        order, forms = 'logical', text == logical_forms
    elif unicodedata.normalize('NFKC', text[::-1]) == DESCRIPTOR:
        order, forms = 'visual', text == _shaped()
    else:
        order, forms = None, False
    spelled = unicodedata.normalize('NFKC', text if order != 'visual' else text[::-1])
    return {'order': order, 'forms_drawn': forms, 'descriptor': spelled, 'descriptor_recovered': spelled == DESCRIPTOR}


def _crop_box(ink):
    """``ink`` (0–255) cut to its half-covered ink box with a quarter-em margin kept."""
    import numpy as np
    mask = np.asarray(ink) >= INK_LEVEL
    rows, cols = np.nonzero(mask.any(axis=1))[0], np.nonzero(mask.any(axis=0))[0]
    if rows.size == 0:
        return np.asarray(ink)
    pad = MEASURE_EM_PX * SUPERSAMPLE // 4
    top, left = max(0, rows.min() - pad), max(0, cols.min() - pad)
    return np.asarray(ink)[top:rows.max() + pad + 1, left:cols.max() + pad + 1]


# --- the specimen and the record ----------------------------------------------------------------------------------------

def write_specimen(rows: list[dict], path, *, chosen: str) -> dict:
    """Per candidate (and the control) one band: its name and measures; the descriptor as raqm shapes it (the
    reference); as the emitter draws it (the derived face's presentation forms, PIL basic layout); and the two overlaid —
    dark where both ink, red where only the reference does, blue where only the emitter does."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    static = Path(__file__).resolve().parents[2] / 'static' / 'fonts'
    label = ImageFont.truetype(str(static / 'NotoSans-Regular.ttf'), 17)
    bold = ImageFont.truetype(str(static / 'NotoSans-Bold.ttf'), 20)
    col_px = 760
    left_px = 470
    band_px = 150
    header_px = 92
    out = Image.new('RGB', (left_px + 3 * col_px + 40, header_px + band_px * len(rows) + 20), (255, 255, 255))
    draw = ImageDraw.Draw(out)
    draw.text((20, 14), 'The Arabic descriptor: reference (raqm, every feature)  |  emitter way (the derived face\'s presentation forms, '
                        'no GSUB, no GPOS)  |  overlay', font=bold, fill=(20, 20, 20))
    draw.text((20, 46), 'overlay: dark = both, red = reference only, blue = emitter only · %d px to the em, drawn at %d × · IoU at %d px to '
                        'the em · faithful: IoU at least %.2f, no ink lost or split, joins within %.2f em, context share at most %.1f %%'
              % (SPECIMEN_EM_PX, SUPERSAMPLE, MEASURE_EM_PX, IOU_FAITHFUL, JOIN_DY_EM_MAX, CONTEXT_SHARE_MAX * 100), font=label,
              fill=(60, 60, 60))
    for n, r in enumerate(rows):
        y0 = header_px + n * band_px
        if r['key'] == chosen:
            draw.rectangle((4, y0 + 2, out.size[0] - 4, y0 + band_px - 4), outline=(176, 128, 32), width=4)
        v = faithful(r)
        e, j, ctx, pl = r['emitter_way'], r['joins'], r['context'], r['print_limits']
        short = {'descriptor': 'IoU', 'no': 'ink lost, split, extra or merged', 'joins': 'joins', 'context': 'context',
                 'every': 'cmap', 'further': 'further lines', 'glyphs': 'glyphs'}
        lines = ['%s %g%s%s' % (r['family'], r['weight'], ' (control)' if r['control'] else '', '  — CHOSEN' if r['key'] == chosen else ''),
                 'IoU %.3f · reportlab %.3f' % (e['iou'], r['reportlab']['iou']),
                 ('joins dy %d u · drift %d u · %d letters differ' % (j['worst_dy_units'], j['worst_drift_units'], j['units_glyphs_differ'])
                  if j.get('measured') is True else 'joins unmeasured'),
                 ('context %.1f %%' % (100 * ctx['share']) if ctx['share'] is not None else 'context unmeasured')
                 + ' · foil gaps < 0.2 mm: %.2f mm²' % pl['gaps_under_limit_mm2'],
                 'faithful' if v['faithful'] else 'not faithful: ' + ', '.join(dict.fromkeys(short[k.split('_')[0]] for k, ok in v['tests'].items() if not ok))]
        for i, text in enumerate(lines):
            draw.text((20, y0 + 10 + i * 26), text, font=bold if i == 0 else label,
                      fill=(20, 20, 20) if i == 0 else ((30, 110, 50) if (i == 4 and v['faithful']) else (60, 60, 60) if i < 4 else (170, 40, 40)))
        ref, emit = r['_images']['reference'], r['_images']['emitter']
        a, b = _crop(ref >= INK_LEVEL), _crop(emit >= INK_LEVEL)
        rows_px, cols_px = max(a.shape[0], b.shape[0]), max(a.shape[1], b.shape[1])
        over = np.full((rows_px, cols_px, 3), 255, np.uint8)
        A, B = _centred(a, rows_px, cols_px), _centred(b, rows_px, cols_px)
        over[A & B] = (40, 40, 40)
        over[A & ~B] = (220, 40, 40)
        over[~A & B] = (40, 90, 220)
        for k, img in enumerate((Image.fromarray(255 - _crop_grey(ref)), Image.fromarray(255 - _crop_grey(emit)), Image.fromarray(over))):
            img = img.convert('RGB')
            scale = min(1.0, (col_px - 20) / img.size[0], (band_px - 16) / img.size[1])
            if scale < 1.0:
                img = img.resize((max(1, int(img.size[0] * scale)), max(1, int(img.size[1] * scale))), Image.LANCZOS)
            x = left_px + k * col_px + (col_px - img.size[0]) // 2
            out.paste(img, (x, y0 + (band_px - img.size[1]) // 2))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.save(path, optimize=True)
    return {'path': _rel(path), 'sha256': _sha256(path), 'size_px': list(out.size)}


def _crop_grey(ink):
    import numpy as np
    mask = np.asarray(ink) >= 1
    rows, cols = np.nonzero(mask.any(axis=1))[0], np.nonzero(mask.any(axis=0))[0]
    return np.asarray(ink)[rows.min():rows.max() + 1, cols.min():cols.max() + 1] if rows.size else np.asarray(ink)


#: the face chosen on 2026-10-20 by ``build`` (arabic-display.json says why): the record's derived stem, weight and
#: candidate, so a fresh clone (``var/`` is git-ignored) re-derives the same bytes (``ensure_chosen``)
CHOSEN = {'key': 'el-messiri-700', 'stem': 'ElMessiriPF-Bold', 'weight': 700.0}


def ensure_chosen(out_dir=None) -> dict:
    """The chosen derived face's provenance (``CHOSEN``), derived — deterministically, the same bytes — where ``out_dir``
    (default ``font_instances.DERIVED_DIR``) holds none."""
    from apps.ire import font_instances
    held = font_instances.derived_face(CHOSEN['stem'], out_dir)
    if held is not None:
        return held
    candidate = next(c for c in CANDIDATES if c['key'] == CHOSEN['key'])
    derive(source_of(candidate), out_dir=out_dir)
    made = font_instances.derived_face(CHOSEN['stem'], out_dir)
    if made is None:
        raise RuntimeError('the derivation of %s did not produce %s' % (CHOSEN['key'], CHOSEN['stem']))
    return made


def _clean(row: dict) -> dict:
    return {k: v for k, v in row.items() if k != '_images'}


def build(*, record_dir=RECORD_DIR, derived_dir=None) -> dict:
    """The whole step: every candidate and the control measured (each derived into a scratch folder), the choice, the
    chosen face derived into ``derived_dir`` (default ``font_instances.DERIVED_DIR``, the same bytes the measure drew),
    the engine's proof, the specimen and the record (``arabic-display.json``) under ``record_dir``."""
    from apps.ire import font_instances
    from apps.ire.type_book import _write_json
    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        rows = [measure(c, work_dir=tmp) for c in CANDIDATES + (CONTROL,)]
    choice = choose(rows)
    record_dir = Path(record_dir)
    specimen = write_specimen(rows, record_dir / SPECIMEN_NAME, chosen=choice['key'])
    prov = proof = None
    if choice['derived']:
        if choice['key'] != CHOSEN['key']:
            raise RuntimeError('the measure chose %s, the module names %s: update CHOSEN with the record' % (choice['key'], CHOSEN['key']))
        candidate = next(c for c in CANDIDATES if c['key'] == choice['key'])
        src = source_of(candidate)
        prov = derive(src, out_dir=derived_dir)
        measured = next(r for r in rows if r['key'] == choice['key'])['drawn_face']['sha256']
        if prov['sha256'] != measured:
            raise RuntimeError('the derived bytes %s are not the bytes measured %s' % (prov['sha256'][:12], measured[:12]))
        font_instances._derived.clear()
        if derived_dir is None or Path(derived_dir).resolve() == font_instances.DERIVED_DIR.resolve():
            with tempfile.TemporaryDirectory() as tmp:
                proof = emitter_proof(prov['stem'], prov['wght'], work_dir=tmp, source_path=src['path'])
        else:
            proof = {'skipped': 'the derived face resolves only from font_instances.DERIVED_DIR; it was written to %s'
                                % derived_dir}
        if 'skipped' not in proof:
            got = proof['iou_vs_reference']
            if not (got['iou'] >= IOU_FAITHFUL and got['components']['missing'] == got['components']['extra']
                    == got['components']['split'] == 0 and proof['order'] == 'logical' and proof['forms_drawn']
                    and proof['descriptor_recovered']):
                raise RuntimeError('the engine\'s proof of the derived face does not hold: %s' % {k: proof[k] for k in proof if k != '_images'})
    by_key = {r['key']: r for r in rows}
    if choice['derived']:
        # the derived face kept (the bytes measured) read at rising alifs until its shapes stand clear of the foil gap
        chosen_row = by_key[choice['key']]
        chosen_row['print_limits']['foil_clear_from_alif_mm'] = foil_clear_alif(
            font_instances._abs(prov['path']), alif_em=chosen_row['alif_em'])
    record = {
        'schema': SCHEMA, 'built_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'decision': 'D-D9-5: the Arabic line is set in a display face; one display face may be made emitter-capable today '
                    '(≤ 1 h), otherwise Noto Naskh Arabic Bold',
        'descriptor': DESCRIPTOR, 'descriptor_as_the_emitter_draws_it': _shaped(),
        'method': {
            'reference': 'PIL ImageFont.Layout.RAQM (libraqm, HarfBuzz %s, every default feature on), right to left, the '
                         'source face' % harfbuzz()['raqm_harfbuzz'],
            'emitter_way': 'apps.dielines.exporters.text_intl.shape_ar(text, keep_harakat=True) — arabic_reshaper '
                           'presentation forms, python-bidi visual order — drawn by PIL ImageFont.Layout.BASIC (cmap and '
                           'advances only) from the derived face',
            'reportlab': 'the same string drawn by reportlab drawString (the emitter\'s own call) and rasterised by MuPDF',
            'scale': '%d px to the em, every drawing made at %d × and brought down by Lanczos (the engine\'s own render '
                     'path)' % (MEASURE_EM_PX, SUPERSAMPLE),
            'iou': 'ink (coverage ≥ 50 %%) cut to its box, the boxes centred on one another, then the best alignment within '
                   '±%d px' % SHIFT_PX,
            'components': '8-connected ink components: missing (a reference component the emitter has no ink on), extra, '
                          'split (a reference component the emitter breaks: a join broken), merged',
            'joins': 'from the shaping: the vertical move GPOS makes between two joined letters (dy), the difference in '
                     'their distance (dx), how far any letter drifts from where shaping puts it; the letters drawn from '
                     'other glyphs than the reference\'s',
            'context': 'every letter beside every letter (N+X, X+N, N+X+N): the share of contexts in which the face '
                       'draws the letter from other glyphs than the emitter\'s form for it alone',
            'print_limits': 'the descriptor as the emitter draws it at the lid\'s alif (%.1f mm, Day 8\'s directions) against '
                            'D-D9-3\'s foil limits (gaps ≥ %.1f mm, lines ≥ %.1f mm), by closing and opening with discs'
                            % (LID_ALIF_MM, FOIL_GAP_MM, FOIL_LINE_MM)},
        'thresholds': {'iou_faithful': IOU_FAITHFUL, 'join_dy_em_max': JOIN_DY_EM_MAX, 'context_share_max': CONTEXT_SHARE_MAX,
                       'why': 'see apps/ire/arabic_display.py IOU_FAITHFUL, JOIN_DY_EM_MAX, CONTEXT_SHARE_MAX: each set '
                              'between the faithful faces\' readings and the unfaithful ones, the control beside them',
                       'readings': {k: {'iou': r['emitter_way']['iou'], 'reportlab_iou': r['reportlab']['iou'],
                                        'worst_join_dy_em': r['joins'].get('worst_dy_em'),
                                        'further_lines_worst_dy_em': r['further_lines']['worst_dy_em'],
                                        'context_share': r['context']['share'], 'faithful': choice['verdicts'][k]['faithful']}
                                    for k, r in by_key.items()}},
        'display_rank': list(DISPLAY_RANK),
        'candidates': [_clean(r) for r in rows if not r['control']],
        'control': _clean(next(r for r in rows if r['control'])),
        'choice': choice, 'why': _why(choice, by_key),
        'derived': prov, 'derived_sha256': prov['sha256'] if prov else None,
        'emitter_proof': proof, 'specimen': specimen, 'findings': _findings(rows, proof),
        'harfbuzz': {k: v for k, v in harfbuzz().items() if k != 'lib'},
        'generator': 'apps.ire.arabic_display.build', 'seconds': round(time.time() - t0, 1)}
    _write_json(record_dir / RECORD_NAME, record)
    return record


def _findings(rows: list[dict], proof: dict | None) -> list[str]:
    """What the measure found beside the choice, for the owner — none repaired here."""
    from apps.ire import font_roles
    cands = [r for r in rows if not r['control']]
    no_lam_alef = sorted({r['family'] for r in cands if r['source_carries']['lam_alef_ligatures'] == 0})
    out = ['The emitter-capable check counts the %d joining forms of the 36 letters; the reshaper also writes the lam-alef '
           'ligatures U+FEF5–FEFC and the Allah ligature U+FDF2, which it does not count. %s carry none of U+FEF5–FEFC '
           '(ظلال would lose its لا on the emitter with all 119), no candidate carries U+FDF2; every derived face carries '
           'all %d forms.' % (len(font_roles._arabic_forms_the_emitter_emits()),
                              ' and '.join(no_lam_alef) or 'No candidate', len(emitted_forms())),
           'Reserved Font Names, against the premise that none declares one: %s. No derived name uses them.'
           % '; '.join(sorted({'%s reserves %s' % (r['family'], ', '.join('"%s"' % n for n in r['forms']['reserved_font_names']))
                               for r in cands if r['forms'] and r['forms']['reserved_font_names']})),
           'Reem Kufi at 500 had no static instance before this step (var/fonts/instanced held its Regular and Bold; '
           'font_instances.static_at returned None): font_instances.make_instance made ReemKufi-Medium.ttf there '
           '(git-ignored) on the step\'s first run, as the type book makes one, and it is measured there; a later run '
           'finds it made (its row\'s instance_made_now is then false).',
           'Drawn directly at 160 px to the em, PIL\'s basic layout rounds every advance to a whole hinted pixel and raqm '
           'places glyphs fractionally: El Messiri 500 read IoU 0.9445 between two drawings of the same glyphs. Every '
           'drawing is therefore made at %d × and brought down by Lanczos, as the engine\'s own render is.' % SUPERSAMPLE,
           'The emitter applies a run\'s tracking (charSpace) after every glyph, joined Arabic letters included: a tracked '
           'Arabic line opens its joins in any face. Never track the Arabic line.']
    if proof and proof.get('usage_row'):
        out.append('The usage record counts the Arabic run in a line face that also carries Latin under the script %s '
                   '(pdf_ai counts "arabic" only where the Arabic face differs from the Latin one): the record\'s script '
                   'column, not the drawing, is wrong for such a face.' % proof['usage_row']['scripts'])
    return out


def _why(choice: dict, by_key: dict) -> list[str]:
    """The choice in words, every number read from the rows."""
    if not choice['derived']:
        return [choice['why']]
    r = by_key[choice['key']]
    e, j, lines, ctx, pl = r['emitter_way'], r['joins'], r['further_lines'], r['context'], r['print_limits']
    out = ['%s %g renders faithfully the emitter way: descriptor IoU %.4f against raqm (reportlab through MuPDF %.4f), '
           '%d ink components each side, none missing, extra, split or merged; %d joins, none moved (dy %d, dx %d units), no '
           'letter drawn from other glyphs; over the %d letter-beside-letter contexts its forms change %d times (no '
           'contextual alternates in its GSUB); on the six further lines IoU %.3f–%.3f with joins moved by at most %.3f em '
           '(its GPOS cursive attachment). %d forms were added (%d of them a composite), the %d it carried are the glyphs '
           'its own GSUB produces.'
           % (r['family'], r['weight'], e['iou'], r['reportlab']['iou'], e['components']['reference'], j['joins'],
              j['worst_dy_units'], j['worst_dx_units'], ctx['contexts'], ctx['differ'], lines['iou_min'], lines['iou_max'],
              lines['worst_dy_em'], r['forms']['added'], r['forms']['composites'], r['forms']['kept'])]
    if pl['gaps_between_shapes'] == 0:
        gaps = ('no two of its shapes stand closer than the %.1f mm foil gap (%.2f mm² of its own corners under it, the '
                'control (Noto Naskh Bold) %.2f mm²)' % (FOIL_GAP_MM, pl['gaps_under_limit_mm2'],
                                                          by_key[CONTROL['key']]['print_limits']['gaps_under_limit_mm2']))
    else:
        gaps = ('%d place(s) between two of its shapes stand under the %.1f mm foil gap (the nearest %.3f mm apart — a '
                'dot pair), so foil would join them' % (pl['gaps_between_shapes'], FOIL_GAP_MM, pl['gaps_between_shapes_mm'][0]))
        if 'foil_clear_from_alif_mm' in pl and pl['foil_clear_from_alif_mm'] is not None:
            gaps += ('; they stand clear from an alif of %.1f mm (measured in 0.1 mm steps), so below that the '
                     'descriptor is printed ink, not foil' % pl['foil_clear_from_alif_mm'])
        else:
            gaps += '; no alif up to 8 mm clears them, so the descriptor is printed ink, not foil'
    out.append('Of the faithful faces it carries the strongest display character the measure leaves standing: a display '
               'Naskh with calligraphic terminals and open counters, drawn for headings. At the lid\'s descriptor size '
               '(alif %.1f mm) %s. The heaviest of its faithful weights, as the owner\'s fallback names a Bold.'
               % (pl['alif_mm'], gaps))
    rk = [by_key[k] for k in by_key if by_key[k]['family'] == 'Reem Kufi']
    if rk:
        k0 = rk[0]
        out.append('Reem Kufi has the stronger display voice and its descriptor is faithful (IoU %s), but it is not chosen: '
                   'its required contextual alternates change %.1f %% of letter contexts (%d forms; "أحمر شفاه لامع" reads IoU %.2f, '
                   'its isolated heh after alef narrower in context than alone), and at the lid\'s alif its alef–lam gaps '
                   'close under the foil limit (%.2f mm² of gaps under %.1f mm).'
                   % (' / '.join('%.3f' % x['emitter_way']['iou'] for x in rk), 100 * k0['context']['share'],
                      len(k0['context']['forms']), next(x['iou'] for x in k0['further_lines']['lines'] if x['line'] == 'أحمر شفاه لامع'),
                      k0['print_limits']['gaps_under_limit_mm2'], FOIL_GAP_MM))
    ar = [by_key[k] for k in by_key if by_key[k]['family'] == 'Aref Ruqaa']
    if ar:
        out.append('Aref Ruqaa, the most calligraphic, drifts: its joins hang on GPOS cursive attachment (dy up to %d units, '
                   '%.2f em), IoU %s, %.0f %% of contexts differ.'
                   % (ar[0]['joins']['worst_dy_units'], ar[0]['joins']['worst_dy_em'],
                      ' / '.join('%.3f' % x['emitter_way']['iou'] for x in ar), 100 * ar[0]['context']['share']))
    mz = [by_key[k] for k in by_key if by_key[k]['family'] == 'Mirza']
    if mz:
        out.append('Mirza, a Naskh drawn for text, loses contextual forms and kerning: IoU %s.'
                   % ' / '.join('%.3f' % x['emitter_way']['iou'] for x in mz))
    return out


__all__ = ['DESCRIPTOR', 'CANDIDATES', 'CONTROL', 'CHOSEN', 'IOU_FAITHFUL', 'JOIN_DY_EM_MAX', 'CONTEXT_SHARE_MAX',
           'DISPLAY_RANK', 'HarfBuzzUnavailable', 'harfbuzz', 'shape', 'form_of', 'emitted_forms', 'drawn_form',
           'source_of', 'derive', 'render_reference', 'render_basic', 'render_reportlab', 'supersampled', 'compare',
           'joins', 'context_sensitivity', 'print_limits', 'measure', 'faithful', 'choose', 'emitter_proof',
           'extracted_order', 'write_specimen', 'ensure_chosen', 'build']
