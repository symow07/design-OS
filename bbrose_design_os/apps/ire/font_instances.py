"""Static instances of the granted variable faces, and the stem a face actually draws (Day 8 §1a).

A variable face draws its DEFAULT instance wherever a renderer opens the file as it is — reportlab ignores gvar, PIL and
a fontTools glyph set draw the default unless told a location — and the default of Chivo Mono, Montserrat, Raleway,
Josefin Sans and Nunito is their lightest. This module

1. measures the stem a face draws: the vertical stem of ``l`` (else ``I``, else ``H`` — the first the cmap holds),
   rasterised at 1000 px to the em, its thickness across three cuts near mid-height (``H`` below its bar) as a fraction
   of the em, corrected for the italic angle — and compares it with the weight the face declares (OS/2 usWeightClass, or
   the weight word of its name) through the band ``BAND`` states;
2. makes static instances of a variable face with every axis pinned (fontTools ``varLib.instancer``) under
   ``var/fonts/instanced/<family>-<instance>.ttf`` — ``var/`` is git-ignored (.gitignore:66): internal build files,
   never distributed and never granted separately; the GRANTED variable file stays the verification subject — each with
   a provenance JSON beside it (source path and sha256, every axis value, the instance's own sha256, the licence wording,
   any Reserved Font Name from the name table);
3. points the catalogue at them: ``instances_of(stem)`` lists a variable face's static instances (path, wght, other
   axes), ``static_at(stem, wght)`` returns the record ``font_roles.instance_at`` hands the emitter, so a line asking
   Chivo Mono at 900 draws the Black instance's static file, never the Thin default;
4. [Day 9, D-D9-5] lists the faces DERIVED from a GRANTED face (``apps.ire.arabic_display.derive``: an Arabic display
   face made emitter-capable) under ``var/fonts/derived``, each with its provenance beside it — ``derived_face(stem)``
   is the record ``font_roles`` resolves a derived stem through, the GRANTED source staying the verification subject.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]                                  # the repo
INSTANCE_DIR = Path(__file__).resolve().parents[2] / 'var' / 'fonts' / 'instanced'
RECORD_DIR = ROOT / 'docs' / 'audit' / 'day-8' / 'fonts'
SCHEMA = 'day8_font_instance/1'
STEM_GLYPHS = ('l', 'I', 'H', '\u0627')        # alef: the stem of a face that carries no Latin
EM_PX = 1000
#: OS/2 weight class of each weight word a face's name carries (the CSS / OpenType scale)
WEIGHT_WORDS = (('hairline', 100), ('thin', 100), ('extralight', 200), ('ultralight', 200), ('light', 300),
                ('book', 400), ('regular', 400), ('normal', 400), ('medium', 500), ('semibold', 600), ('demibold', 600),
                ('extrabold', 800), ('ultrabold', 800), ('bold', 700), ('heavy', 900), ('black', 900), ('ultra', 900))
#: The band a measured stem is read through. The stem/em each weight is expected to draw (``EXPECTED_STEM``, linear
#: between the anchors) is the middle of the house's own static families measured by ``stem_em`` on 2026-10-20 —
#: Poppins 100–900, Tajawal 200–900, Barlow Condensed 300–800, Chivo Mono 100–900 (their rows are in stem-weights.json
#: under ``calibration``). A face reads 'within' when its measured stem lies between BAND['low'] and BAND['high'] times
#: the expected stem of the weight it declares; below is 'lighter than declared', above 'heavier than declared'. The
#: band is wide on purpose — a didone's hairlines, a mono's even stroke (Chivo Mono Thin draws 1.7× a sans Thin) and a
#: script's loops each draw their own stem at one weight: it catches a face drawing a different weight from the one it
#: names (a default instance, a mislabelled file), not a design.
EXPECTED_STEM = ((100, 0.030), (200, 0.045), (300, 0.062), (400, 0.083), (500, 0.103), (600, 0.125), (700, 0.147),
                 (800, 0.168), (900, 0.190), (1000, 0.210))
BAND = {'low': 0.55, 'high': 1.8}

_lock = threading.Lock()
_index: dict = {}


# --- the stem a face draws -------------------------------------------------------------------------------------------

def _sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _weight_word(text: str) -> str | None:
    low = str(text or '').lower().replace(' ', '').replace('-', '').replace('_', '')
    return next((w for w, _ in WEIGHT_WORDS if w in low), None)


def declared_weight(path, index: int = 0) -> dict:
    """The weight a face declares: OS/2 usWeightClass, and the weight word of its style name — the typographic
    subfamily (name 17) or subfamily (2), else what its full name (4) adds to its typographic family (16), so
    "Chivo Mono Black" (family "Chivo Mono", subfamily "Regular") reads black and "Shadows Into Light Two" never light."""
    from fontTools.ttLib import TTFont
    with TTFont(str(path), lazy=True, fontNumber=index) as ft:
        os2 = ft['OS/2'].usWeightClass if 'OS/2' in ft else None
        name = ft['name']
        sub = name.getDebugName(17) or name.getDebugName(2) or ''
        family, full = name.getDebugName(16) or '', name.getDebugName(4) or ''
    word = _weight_word(sub)
    if word in (None, 'regular', 'bold') and family and full.lower().startswith(family.lower()):
        word = _weight_word(full[len(family):]) or word
    return {'us_weight_class': os2, 'name_word': word, 'name_weight': dict(WEIGHT_WORDS).get(word) if word else None}


def stem_em(path, index: int = 0) -> dict:
    """The face's stem as a fraction of its em: ``{'glyph', 'stem_em', 'stem_px', 'em_px', 'italic_angle', 'cuts'}``;
    stem_em None (with ``why``) where the face holds none of l, I, H or draws no ink."""
    import numpy as np
    from fontTools.ttLib import TTFont
    from PIL import Image, ImageDraw, ImageFont
    with TTFont(str(path), lazy=True, fontNumber=index) as ft:
        cmap = ft.getBestCmap() or {}
        angle = float(getattr(ft['post'], 'italicAngle', 0.0) or 0.0) if 'post' in ft else 0.0
    glyph = next((g for g in STEM_GLYPHS if ord(g) in cmap), None)
    if glyph is None:
        return {'glyph': None, 'stem_em': None, 'why': 'the cmap holds none of l, I, H, alef'}
    font = ImageFont.truetype(str(path), EM_PX, index=index)
    img = Image.new('L', (EM_PX * 2, EM_PX * 2), 0)
    ImageDraw.Draw(img).text((EM_PX // 2, EM_PX // 2), glyph, font=font, fill=255)
    ink = np.asarray(img) > 127
    rows = np.nonzero(ink.any(axis=1))[0]
    if rows.size == 0:
        return {'glyph': glyph, 'stem_em': None, 'why': 'the glyph draws no ink'}
    top, bottom = int(rows.min()), int(rows.max())
    height = bottom - top + 1
    # mid-height for l and I; H's bar sits at mid-height, so its stems are cut at a quarter from the baseline
    fractions = (0.22, 0.27, 0.32) if glyph == 'H' else (0.42, 0.50, 0.58)
    cuts = []
    for f in fractions:
        row = ink[int(round(bottom - f * height))]
        best = run = 0
        for v in row:
            run = run + 1 if v else 0
            best = max(best, run)
        cuts.append(best)
    stem_px = sorted(cuts)[1] * math.cos(math.radians(angle))          # the median cut, across the slant
    return {'glyph': glyph, 'stem_em': round(stem_px / EM_PX, 4), 'stem_px': round(stem_px, 1), 'em_px': EM_PX,
            'italic_angle': angle, 'cuts': cuts}


def expected_stem(weight) -> float:
    """The stem/em a face of ``weight`` is expected to draw (``EXPECTED_STEM``, linear between anchors)."""
    w = min(max(float(weight), EXPECTED_STEM[0][0]), EXPECTED_STEM[-1][0])
    for (w0, s0), (w1, s1) in zip(EXPECTED_STEM, EXPECTED_STEM[1:]):
        if w0 <= w <= w1:
            return s0 + (s1 - s0) * (w - w0) / (w1 - w0)
    return EXPECTED_STEM[-1][1]


def band_verdict(weight, stem) -> str:
    """'within', 'lighter than declared' or 'heavier than declared' through ``BAND``; 'unmeasured' without both."""
    if weight is None or stem is None:
        return 'unmeasured'
    ratio = float(stem) / expected_stem(weight)
    if ratio < BAND['low']:
        return 'lighter than declared'
    if ratio > BAND['high']:
        return 'heavier than declared'
    return 'within'


def measure(path, index: int = 0) -> dict:
    """``stem_em`` beside the declared weights and the band's verdict against each: ``verdict`` against usWeightClass,
    ``verdict_by_name`` against the style name's weight word; ``agrees`` when either reads within (a Thin's OS/2 250 is
    the old GDI floor, not a weight)."""
    stem = stem_em(path, index)
    declared = declared_weight(path, index)
    s = stem.get('stem_em')
    os2, named = declared['us_weight_class'], declared['name_weight']
    out = {**stem, **declared, 'expected_stem_em': round(expected_stem(os2), 4) if os2 else None,
           'verdict': band_verdict(os2, s), 'verdict_by_name': band_verdict(named, s)}
    out['agrees'] = 'within' in (out['verdict'], out['verdict_by_name'])
    return out


# --- static instances ------------------------------------------------------------------------------------------------

def _slug(text) -> str:
    return re.sub(r'[^A-Za-z0-9]+', '', str(text or '')) or 'Face'


def axes_of(path) -> dict:
    """``{tag: (min, default, max)}`` of a variable face; {} for a static one."""
    from fontTools.ttLib import TTFont
    with TTFont(str(path), lazy=True) as ft:
        if 'fvar' not in ft:
            return {}
        return {a.axisTag: (float(a.minValue), float(a.defaultValue), float(a.maxValue)) for a in ft['fvar'].axes}


def named_instances(path) -> list[dict]:
    """The face's own fvar named instances: ``[{'name', 'coordinates'}]``, in the file's order."""
    from fontTools.ttLib import TTFont
    with TTFont(str(path), lazy=True) as ft:
        if 'fvar' not in ft:
            return []
        name = ft['name']
        return [{'name': name.getDebugName(i.subfamilyNameID) or '', 'coordinates': {k: float(v) for k, v in i.coordinates.items()}}
                for i in ft['fvar'].instances]


def reserved_font_names(path) -> list[str]:
    """The Reserved Font Names an OFL face declares — read from its copyright (name 0) and licence (name 13) strings."""
    from fontTools.ttLib import TTFont
    with TTFont(str(path), lazy=True) as ft:
        text = ' '.join(str(ft['name'].getDebugName(i) or '') for i in (0, 13))
    found = []
    for m in re.finditer(r'Reserved\s+Font\s+Names?\s*[:"“]*\s*([^.\n]+)', text, flags=re.I):
        for part in re.split(r'["“”]\s*(?:and|,)\s*["“”]|,\s*|\s+and\s+', m.group(1)):
            part = part.strip(' "“”\'')
            if part and part.lower() not in ('', 'none') and part not in found:
                found.append(part)
    return found


def instance_name(path, coords: dict) -> str:
    """The style name of an instance: the face's own named instance at those coordinates, else 'wght<n>' and each other
    axis away from its default."""
    for inst in named_instances(path):
        if all(abs(inst['coordinates'].get(k, v) - v) < 0.5 for k, v in coords.items()):
            return inst['name']
    axes = axes_of(path)
    standard = {100: 'Thin', 200: 'ExtraLight', 300: 'Light', 400: 'Regular', 500: 'Medium', 600: 'SemiBold', 700: 'Bold',
                800: 'ExtraBold', 900: 'Black'}
    others = [k for k, v in coords.items() if k != 'wght' and abs(v - axes.get(k, (0, v, 0))[1]) >= 0.5]
    italic = 'Italic' if 'italic' in Path(path).name.lower() else ''
    if 'wght' in coords and not others and round(coords['wght']) in standard and abs(coords['wght'] - round(coords['wght'])) < 0.5:
        word = standard[round(coords['wght'])]
        return ('%s %s' % ('' if word == 'Regular' and italic else word, italic)).strip()      # the weight word a face of that weight bears
    parts = ['wght%g' % coords['wght']] if 'wght' in coords else []
    parts += ['%s%g' % (k, v) for k, v in sorted(coords.items()) if k != 'wght' and abs(v - axes.get(k, (0, v, 0))[1]) >= 0.5]
    return ' '.join(parts) or 'Default'


def make_instance(src, coords: dict, *, family: str, licence: str = '', source_stem: str = '', out_dir=None) -> dict:
    """A static instance of the variable face ``src`` with EVERY axis pinned (``coords`` given, the rest at their
    defaults, each clamped to its axis), written as ``<family>-<instance>.ttf`` under ``out_dir`` (default
    ``INSTANCE_DIR``) with ``<same>.json`` provenance beside it. Deterministic bytes (no timestamp recalculation); an
    existing file with the same bytes is kept. Returns the provenance record."""
    import io
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer
    src = Path(src)
    out_dir = Path(out_dir) if out_dir is not None else INSTANCE_DIR
    axes = axes_of(src)
    if not axes:
        raise ValueError('not a variable face: %s' % src)
    pinned = {tag: min(max(float(coords.get(tag, d)), lo), hi) for tag, (lo, d, hi) in axes.items()}
    style = instance_name(src, pinned)
    source_sha = _sha256(src)
    font = TTFont(str(src), recalcTimestamp=False)
    try:
        static = instancer.instantiateVariableFont(font, pinned, updateFontNames=True)
        names_updated = True
    except Exception:          # noqa: BLE001 — a face without a STAT table cannot rename itself; its names are set below
        font = TTFont(str(src), recalcTimestamp=False)
        static = instancer.instantiateVariableFont(font, pinned, updateFontNames=False)
        names_updated = False
    if 'fvar' in static or 'gvar' in static:
        raise RuntimeError('the instance of %s is still variable' % src.name)
    name = static['name']
    if not names_updated:
        ps = '%s-%s' % (_slug(family), _slug(style))
        for rec in list(name.names):
            if rec.nameID in (2, 17):
                rec.string = style
            elif rec.nameID in (4,):
                rec.string = '%s %s' % (family, style)
            elif rec.nameID == 6:
                rec.string = ps
    if 'OS/2' in static and 'wght' in pinned:
        static['OS/2'].usWeightClass = int(round(min(max(pinned['wght'], 1), 1000)))
    buf = io.BytesIO()
    static.save(buf)
    data = buf.getvalue()
    sha = hashlib.sha256(data).hexdigest()
    out_dir.mkdir(parents=True, exist_ok=True)
    base = '%s-%s' % (_slug(family), _slug(style))
    # the plain name belongs to the first source recorded under it; another source's instance carries its digest
    meta = out_dir / (base + '.json')
    if meta.exists():
        held = json.loads(meta.read_text(encoding='utf-8'))
        if held.get('source_sha256') != source_sha:
            base = '%s-%s' % (base, source_sha[:8])
    path = out_dir / (base + '.ttf')
    if not path.exists() or _sha256(path) != sha:
        tmp = path.with_suffix('.tmp')
        tmp.write_bytes(data)
        os.replace(tmp, path)
    postscript = name.getDebugName(6) or base
    record = {'schema': SCHEMA, 'path': _rel(path), 'sha256': sha, 'bytes': len(data), 'postscript': postscript,
              'family': name.getDebugName(16) or name.getDebugName(1) or family, 'style': name.getDebugName(17) or name.getDebugName(2) or style,
              'instance': style, 'axes': pinned, 'wght': pinned.get('wght'),
              'source_stem': source_stem, 'source_path': _rel(src), 'source_sha256': source_sha,
              'source_axes': {k: list(v) for k, v in axes.items()}, 'source_default_instance': instance_name(src, {k: v[1] for k, v in axes.items()}),
              'licence': licence, 'reserved_font_names': reserved_font_names(src), 'names_updated_from_stat': names_updated,
              'made_with': 'fontTools.varLib.instancer.instantiateVariableFont (every axis pinned), recalcTimestamp=False',
              'use': 'internal build file under var/ (git-ignored): never distributed, never granted separately; the GRANTED '
                     'variable file is the verification subject'}
    tmp = (out_dir / (base + '.json.tmp'))
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    os.replace(tmp, out_dir / (base + '.json'))
    with _lock:
        _index.clear()
    return record


def _rel(path) -> str:
    path = Path(path).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _abs(path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def index(out_dir=None) -> list[dict]:
    """Every provenance record under ``out_dir`` whose instance file is present with the recorded bytes (cached per
    change of the directory)."""
    out_dir = Path(out_dir) if out_dir is not None else INSTANCE_DIR
    try:
        key = (str(out_dir), out_dir.stat().st_mtime_ns, len(os.listdir(out_dir)))
    except OSError:
        return []
    with _lock:
        if _index.get('key') == key:
            return _index['records']
    records = []
    for meta in sorted(out_dir.glob('*.json')):
        try:
            rec = json.loads(meta.read_text(encoding='utf-8'))
        except ValueError:
            continue
        if rec.get('schema') != SCHEMA:
            continue
        path = _abs(rec['path'])
        if path.exists() and path.stat().st_size == rec.get('bytes'):
            records.append(dict(rec, path=str(path)))
    with _lock:
        _index['key'], _index['records'] = key, records
    return records


def index_key(out_dir=None):
    """A key that changes whenever the instance directory's files change (for callers that cache an overlay)."""
    out_dir = Path(out_dir) if out_dir is not None else INSTANCE_DIR
    try:
        return (str(out_dir), out_dir.stat().st_mtime_ns, len(os.listdir(out_dir)))
    except OSError:
        return (str(out_dir), None, 0)


def instances_of(stem: str = '', source_sha256: str = '', out_dir=None) -> list[dict]:
    """A variable face's static instances — ``[{path, sha256, wght, axes, instance, postscript}]`` by weight — found by
    its catalogue stem or the digest of its GRANTED file."""
    rows = [r for r in index(out_dir) if (source_sha256 and r.get('source_sha256') == source_sha256)
            or (stem and r.get('source_stem') == stem)]
    return [{'path': r['path'], 'sha256': r['sha256'], 'wght': r.get('wght'), 'axes': r['axes'], 'instance': r['instance'],
             'postscript': r['postscript']} for r in sorted(rows, key=lambda r: (r.get('wght') or 0, r['instance']))]


def static_at(stem: str, source_sha256: str, weight: float, out_dir=None) -> dict | None:
    """The pre-made static instance of the variable face (``stem``, its GRANTED digest) at exactly ``weight`` with every
    other axis at its default, re-hashed — shaped as ``font_roles.instance_at``'s record — or None."""
    for r in index(out_dir):
        if r.get('source_sha256') != source_sha256 or r.get('wght') is None or abs(r['wght'] - float(weight)) >= 0.5:
            continue
        defaults = {k: v[1] for k, v in (r.get('source_axes') or {}).items()}
        if any(abs(r['axes'].get(k, d) - d) >= 0.5 for k, d in defaults.items() if k != 'wght'):
            continue
        if _sha256(r['path']) != r['sha256']:
            continue
        return {'postscript': r['postscript'], 'family': r['family'], 'style': r['style'], 'path': r['path'],
                'sha256': r['sha256'], 'axes': {'wght': float(weight)}, 'derived_from': stem or r.get('source_stem'),
                'derived_from_sha256': source_sha256, 'source_default_instance': r.get('source_default_instance', ''),
                'premade': True}
    return None


#: [Day 9, D-D9-5] faces DERIVED from a GRANTED face — internal build files, git-ignored as the instances are
#: (.gitignore:66 ``var/``), never distributed and never granted separately; each provenance record (DERIVED_SCHEMA)
#: names its derived stem, its bytes, and the GRANTED source (stem and digest) it was made from
DERIVED_DIR = Path(__file__).resolve().parents[2] / 'var' / 'fonts' / 'derived'
DERIVED_SCHEMA = 'day9_derived_face/1'
_derived: dict = {}


def derived_index(out_dir=None) -> list[dict]:
    """Every derived face's provenance under ``out_dir`` (default ``DERIVED_DIR``) whose file is present with the
    recorded bytes (cached per change of the directory) — ``index``'s counterpart for derived faces."""
    out_dir = Path(out_dir) if out_dir is not None else DERIVED_DIR
    try:
        key = (str(out_dir), out_dir.stat().st_mtime_ns, len(os.listdir(out_dir)))
    except OSError:
        return []
    with _lock:
        if _derived.get('key') == key:
            return _derived['records']
    records = []
    for meta in sorted(out_dir.glob('*.json')):
        try:
            rec = json.loads(meta.read_text(encoding='utf-8'))
        except ValueError:
            continue
        if rec.get('schema') != DERIVED_SCHEMA:
            continue
        path = _abs(rec['path'])
        if path.exists() and path.stat().st_size == rec.get('bytes'):
            records.append(dict(rec, path=str(path)))
    with _lock:
        _derived['key'], _derived['records'] = key, records
    return records


def derived_face(stem: str, out_dir=None) -> dict | None:
    """The derived face ``stem``'s provenance record with its file re-hashed against it, or None (not derived here —
    ``var/`` is git-ignored, so a fresh clone holds none until ``arabic_display`` derives it — or its bytes moved)."""
    for r in derived_index(out_dir):
        if r.get('stem') == stem:
            return dict(r) if _sha256(r['path']) == r['sha256'] else None
    return None


def derived_of(source_stem: str, source_sha256: str, out_dir=None) -> list[dict]:
    """The faces derived from the GRANTED face (``source_stem``, its digest): ``[{stem, path, sha256, postscript,
    wght}]`` — a field on the source's catalogue entry, as its instances are."""
    return [{'stem': r['stem'], 'path': r['path'], 'sha256': r['sha256'], 'postscript': r['postscript'], 'wght': r.get('wght')}
            for r in derived_index(out_dir) if r.get('source_stem') == source_stem and r.get('source_sha256') == source_sha256]


def instance_plan(path, catalogue_entry: dict | None = None) -> list[dict]:
    """The coordinates a variable face is instanced at: its default, each of its fvar named instances, and the weights
    the catalogue names for it (the regular 400 and the heaviest, each clamped to the axis) — every other axis at its
    default."""
    axes = axes_of(path)
    defaults = {k: v[1] for k, v in axes.items()}
    plan = [dict(defaults)]
    for inst in named_instances(path):
        coords = dict(defaults, **inst['coordinates'])
        plan.append(coords)
    if 'wght' in axes:
        lo, _d, hi = axes['wght']
        for w in (min(max(400.0, lo), hi), lo, hi):
            plan.append(dict(defaults, wght=w))
        if not named_instances(path):
            # no named instances: the weights the catalogue names for the family's static files — every hundred on the axis
            plan += [dict(defaults, wght=float(w)) for w in range(100, 1001, 100) if lo <= w <= hi]
    out, seen = [], set()
    for coords in plan:
        # an instance that moves an axis other than wght off its default is kept only when the face names it
        key = tuple(sorted((k, round(v, 1)) for k, v in coords.items()))
        if key not in seen:
            seen.add(key)
            out.append(coords)
    return out


# --- the Day 8 §1a records -------------------------------------------------------------------------------------------

def write_variable_instances(stems=None) -> dict:
    """variable-instances.json: static instances (``instance_plan``) of the theme's variable faces and the GRANTED pool's
    variable faces (or ``stems``), provenance beside each, the stem of the default and of every instance measured, and
    what ``font_roles.instance_at`` resolves at the axis ends — the catalogue pointed at the files."""
    import datetime
    import subprocess
    import time
    from apps.ire import font_pool, font_roles
    from apps.ire import type_book as TB
    t0 = time.time()
    faces, _excluded = TB.gather()
    by_stem = {f['stem']: f for f in faces}
    cat = font_roles.catalogue()
    theme = font_roles.theme_faces()
    if stems is None:
        theme_var = sorted({r['stem'] for r in theme['resolutions'].values() if r.get('stem') and cat[r['stem']].get('variable')})
        pool_var = sorted(k for k, e in cat.items() if e['origin'] == font_pool.ORIGIN and e.get('variable'))
        groups = (('theme', theme_var), ('pool', pool_var))
    else:
        groups = (('asked', list(stems)),)
    ignored = subprocess.run(['git', '-C', str(ROOT), 'check-ignore', '-v', str(INSTANCE_DIR / 'x.ttf')],
                             capture_output=True, text=True).stdout.strip()
    rows = []
    for group, names in groups:
        for stem in names:
            e = cat[stem]
            src = e['path']
            lic = (by_stem.get(stem) or {}).get('licence') or {}
            default = measure(src)
            made = []
            for coords in instance_plan(src):
                rec = make_instance(src, coords, family=e.get('family') or stem, source_stem=stem, licence='%s — %s %s (sha256 %s)' % (
                    lic.get('licence'), lic.get('evidence'), lic.get('evidence_path'), lic.get('evidence_sha256')))
                m = measure(_abs(rec['path']))
                made.append({'instance': rec['instance'], 'axes': rec['axes'], 'path': rec['path'], 'sha256': rec['sha256'],
                             'postscript': rec['postscript'], 'reserved_font_names': rec['reserved_font_names'],
                             'stem_em': m['stem_em'], 'glyph': m['glyph'], 'declared_weight': m['us_weight_class'], 'verdict': m['verdict']})
            wl = [x for x in made if x['stem_em']]
            light = min(wl, key=lambda x: x['axes'].get('wght', 0)) if wl else None
            heavy = max(wl, key=lambda x: x['axes'].get('wght', 0)) if wl else None
            resolves = {}
            for x in (light, heavy):
                if x and 'wght' in x['axes']:
                    font_roles._instance_cache.pop('%s|wght=%g' % (stem, x['axes']['wght']), None)
                    inst = font_roles.instance_at(stem, x['axes']['wght'])
                    resolves['%g' % x['axes']['wght']] = {'path': _rel(inst['path']) if inst else None, 'premade': bool(inst and inst.get('premade')),
                                                          'same_file': bool(inst and _rel(inst['path']) == x['path'])}
            rows.append({'group': group, 'stem': stem, 'family': e.get('family'), 'source_path': _rel(src), 'source_sha256': e['sha256'],
                         'origin': e['origin'], 'axes': {k: list(v) for k, v in e['axes'].items()}, 'licence': lic.get('licence'),
                         'default_instance': {'name': e.get('variable_default_instance'), 'postscript': e.get('postscript'),
                                              'stem_em': default['stem_em'], 'glyph': default['glyph']},
                         'instances': made,
                         'lightest': light and {'wght': light['axes'].get('wght'), 'stem_em': light['stem_em']},
                         'heaviest': heavy and {'wght': heavy['axes'].get('wght'), 'stem_em': heavy['stem_em']},
                         'heaviest_over_lightest': round(heavy['stem_em'] / light['stem_em'], 2) if light and heavy and light['stem_em'] else None,
                         'heaviest_over_default': round(heavy['stem_em'] / default['stem_em'], 2) if heavy and default['stem_em'] else None,
                         'catalogue_resolves': resolves})
    findings = [{'stem': r['stem'], 'family': r['family'], 'axes': r['axes'], 'heaviest_over_lightest': r['heaviest_over_lightest'],
                 'finding': 'the GRANTED variable file does not vary along wght: its outlines are the same at the axis ends, so '
                            'every instance — pre-made or derived — draws its lightest; the band reads its heavy instances '
                            '"lighter than declared". The family\'s static files carry the weights; a direction must not name '
                            'this variable file for a heavy weight.'}
                for r in rows if r['axes']['wght'][2] - r['axes']['wght'][0] >= 400 and (r['heaviest_over_lightest'] or 0) < 1.2]
    record = {'schema': 'day8_variable_instances/1', 'built_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'rule': 'a variable face never draws its default instance: static instances with every axis pinned (fontTools '
                      'varLib.instancer) at its default, each fvar named instance and the weights the catalogue names (400 and '
                      'the axis ends; every hundred where the face names no instance); font_roles.instance_at / instance_for '
                      'return the pre-made file at exactly the weight asked (re-hashed against its provenance), else derive as before',
              'scope': 'the theme\'s variable faces and the GRANTED pool\'s variable faces (Day 8 §1a, scoped); the type book '
                       'also made the regular and heaviest instance of every other variable family it shows',
              'instance_dir': _rel(INSTANCE_DIR), 'git_ignored_by': ignored or 'NOT IGNORED',
              'use': 'internal build files: never distributed, never granted separately; the GRANTED variable file is the verification subject',
              'generator': 'apps.ire.font_instances.write_variable_instances',
              'faces': rows, 'findings': findings,
              'narrow_axes': [{'stem': r['stem'], 'family': r['family'], 'wght': r['axes']['wght'], 'heaviest_over_lightest': r['heaviest_over_lightest']}
                              for r in rows if r['axes']['wght'][2] - r['axes']['wght'][0] < 400],
              'counts': {'variable_faces': len(rows), 'instances': sum(len(r['instances']) for r in rows),
                         'heaviest_at_least_1_5x_lightest': sum(1 for r in rows if (r['heaviest_over_lightest'] or 0) >= 1.5),
                         'catalogue_resolves_premade': sum(1 for r in rows for v in r['catalogue_resolves'].values() if v['premade'] and v['same_file'])},
              'seconds': round(time.time() - t0, 1)}
    chivo = next((k for k in cat if 'chivo-mono-wght' in k and cat[k].get('variable')), None)
    if chivo:
        font_roles._instance_cache.pop('%s|wght=900' % chivo, None)
        black = font_roles.instance_at(chivo, 900.0)
        bm = measure(black['path'])
        static_black = 'fonts_chivo-mono-black_chivomono-black_7d517bb62416f8b2'
        record['request_chivo_mono_black'] = {
            'asked': 'Chivo Mono Black = the variable Chivo Mono at wght 900', 'stem': chivo, 'resolved_path': _rel(black['path']),
            'premade': bool(black.get('premade')), 'stem_em': bm['stem_em'], 'verdict': bm['verdict'],
            'default_instance_stem_em': next(r for r in rows if r['stem'] == chivo)['default_instance']['stem_em'] if any(r['stem'] == chivo for r in rows) else measure(cat[chivo]['path'])['stem_em'],
            'static_black_file_stem_em': measure(cat[static_black]['path'])['stem_em'] if static_black in cat else None}
    from apps.ire.type_book import _write_json
    _write_json(RECORD_DIR / 'variable-instances.json', record)
    return record


def write_stem_weights() -> dict:
    """stem-weights.json: every catalogue face (house and GRANTED pool) — a static file as it is, a variable face at its
    default instance — its stem against its declared weight through ``BAND``; the calibration rows beside."""
    import collections
    import datetime
    import time
    from apps.ire import font_roles
    from apps.ire.type_book import _write_json
    t1 = time.time()
    cat = font_roles.catalogue()
    cal = []
    brand = Path(__file__).resolve().parents[2] / 'static' / 'fonts' / 'brand2026'
    for fam in ('Poppins', 'Tajawal', 'Barlow_Condensed'):
        for p in sorted((brand / fam).glob('*.ttf')):
            if 'Italic' not in p.name:
                m = measure(p)
                cal.append({'file': _rel(p), 'us_weight_class': m['us_weight_class'], 'name_weight': m['name_weight'], 'stem_em': m['stem_em']})
    for k, e in sorted(cat.items()):
        if 'chivo-mono' in k and not e.get('variable') and 'italic' not in k:
            m = measure(e['path'])
            cal.append({'file': _rel(e['path']), 'us_weight_class': m['us_weight_class'], 'name_weight': m['name_weight'], 'stem_em': m['stem_em']})
    items = []
    for k, e in sorted(cat.items()):
        try:
            m = measure(e['path'])
        except Exception as exc:     # noqa: BLE001 — the row says why
            items.append({'stem': k, 'path': _rel(e['path']), 'error': '%s: %s' % (type(exc).__name__, str(exc)[:100])})
            continue
        items.append({'stem': k, 'path': _rel(e['path']), 'sha256': e['sha256'], 'origin': e['origin'], 'family': e.get('family'),
                      'variable': bool(e.get('variable')), 'measured_at': 'default instance (the file as it is)' if e.get('variable') else 'the file',
                      'declared_weight': m['us_weight_class'], 'name_word': m['name_word'], 'name_weight': m['name_weight'],
                      'glyph': m['glyph'], 'stem_em': m['stem_em'], 'expected_stem_em': m['expected_stem_em'],
                      'band_verdict': m['verdict'], 'band_verdict_by_name': m['verdict_by_name'], 'agrees': m['agrees']})
    record = {'schema': 'day8_stem_weights/1', 'built_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'generator': 'apps.ire.font_instances.write_stem_weights',
              'method': 'the vertical stem of l (else I, else H, else alef — the first the cmap holds) rasterised by FreeType (PIL) '
                        'at 1000 px to the em; the median of three horizontal cuts near mid-height (H at a quarter, below its bar), '
                        'longest ink run, times cos(italic angle), over the em',
              'band': {'expected_stem_em': [list(x) for x in EXPECTED_STEM], 'low': BAND['low'], 'high': BAND['high'],
                       'reads': 'within when measured/expected lies in [low, high]; verdict against OS/2 usWeightClass, '
                                'verdict_by_name against the style name\'s weight word; agrees when either is within'},
              'calibration': cal, 'faces': len(items),
              'by_verdict': dict(collections.Counter(i.get('band_verdict', 'error') for i in items)),
              'disagree': [i['stem'] for i in items if i.get('agrees') is False],
              'variable_at_default_outside_band': [i['stem'] for i in items if i.get('variable') and i.get('agrees') is False],
              'items': items, 'seconds': round(time.time() - t1, 1)}
    _write_json(RECORD_DIR / 'stem-weights.json', record)
    return record
