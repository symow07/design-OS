"""Day 10 §2 — the open palette in the lid's language: the tray and the inside of the lid (D-D10-4).

THE TRAY: 18 square pans in 3 rows of 6 (brief 124, 10-10), each shade's name under its pan in the master's support face,
Latin; the case colour from the lid; the pans' colours and finishes read from ONE tray picture the image model makes from
the 18 names with the pick as its style reference (``make_picture``; ``tray_picture.read_tray_picture`` reads it at $0)
— recorded per pan with hex and finish (10-12's matte / shimmer / glitter), never from shadow. The print layer is the
case colour and the names; the pans are shown in a proof, not printed.

THE INSIDE OF THE LID: the brief's "soft lilac rose-petal pattern" made abstract — a soft lilac tonal pattern in the lid's
light-through-louvres language, no literal petals (D-D8-12): one image call with the pick as style reference, then the
master's preservation path (``lid_master.upscale``, the picture's own edges mirrored for bleed; nothing redrawn).

Every image call goes through the image guard (Day 10's log; the pick and the approved logo are its only inputs) and the
ledger; the owner's $0.60 a picture is checked on settled spend by the runner.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from contextlib import ExitStack
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from apps.pipeline.services import lid_master as lm
from apps.pipeline.services.round_files_faces import delta_e00, srgb_to_lab

OUT = lm.REPO / 'docs' / 'audit' / 'day-10'
TRAY = OUT / 'tray'
SCHEMA = 'day10_open_palette/1'
SURFACE = 'apps/pipeline/services/palette_open.py::tray_artwork'
PREFIX = 'day10/images/'
CAP_USD = 2.20
SIZE = '1536x1024'
QUALITY = 'high'
CASE_MM = (190.0, 120.0)
INSIDE_MM = (184.0, 114.0)          # the lid's inside: the tray's insert (palette_tray.layout)
NAME_TRACKING_EM = 0.06
NAME_INK = '#F1D9C7'                # the lid's small type
GOLD = '#C69559'                    # the lid's name gold (lid_master.ink_gold)
DE_FLAG = 20.0                      # a pan read further than ΔE00 20 from its working colour is flagged
CASE_DE_FLOOR = 10.0                # a pan closer than ΔE00 10 to the case colour reads into the case: flagged
CUT_STROKE_MM = 0.25

TRAY_PROMPT = (
    "Image 1 is the closed lid of an eyeshadow palette: the house's chosen design and the style reference. Image 2 is the "
    "BBROSE logo, for reference only. Draw the same palette OPEN, seen from directly above and square to the eye, filling "
    "the frame: its open tray holding 18 square pans in 3 rows of 6, all one size, evenly spaced in a neat grid, each pan "
    "a pressed eyeshadow in its own shade — left to right, row by row: {names} — each shade's name printed in clean small "
    "capitals under its own pan. The tray in the closed lid's deep teal-ink shadow colour, the pans' rims soft gold. Each "
    "pan shows its finish as its name suggests: matte (flat powder), shimmer (a soft sheen toward one corner) or glitter "
    "(fine dense sparkle). The same colours and materials as the closed lid. Plain flat front-on view; no hands, no "
    "brushes, no props, no reflections, no logo, no roses, no petals, no arches, no glowing frames, no extra words.")
INSIDE_PROMPT = (
    "Image 1 is the closed lid of an eyeshadow palette: the house's chosen design and the style reference. Image 2 is the "
    "BBROSE logo, for reference only — do not draw it. Draw the INSIDE of the same lid as flat print artwork, front-on, "
    "filling the frame edge to edge: a soft lilac tonal pattern in the lid's own language — late light through a louvred "
    "window falling as soft parallel bars across lilac lime plaster, lilac on lilac, quiet and abstract, the plaster's "
    "fine trowel texture as on the lid. No petals, no flowers, no roses, no arches, no frames, no gold, no metal, no "
    "words, no letters, no logo, no product, no 3D, no perspective, no props.")


def make_picture(name, prompt, *, client, out=OUT, prefix=PREFIX, cap_usd=None):
    """One gpt-image-2 edit through the image guard and the ledger: the owner's pick (the style reference) and the
    approved logo as the only inputs. Resumes: a picture already made is read back, never bought twice. The picture
    goes to ``out``/``name`` under the operation ``prefix``+``name`` within ``cap_usd`` (Day 10's folder, prefix and cap
    — ``CAP_USD``, resolved here when None — by default; [Day 11] Golden Hour's new tray under
    ``day-11/golden-hour/tray/`` and ``day11/``)."""
    from django.conf import settings
    from apps.pipeline.services import round_calls as image_guard
    from apps.pipeline.services.spend_reservation import paid_operation
    if cap_usd is None:
        cap_usd = CAP_USD
    dest = Path(out) / name
    done = dest / 'picture.json'
    if done.exists():
        return json.loads(done.read_text())
    pick_path, pick_sha = image_guard.APPROVED_PICK
    logo_path, logo_sha = image_guard.APPROVED_LOGO
    items = [{'role': "the owner's pick — the style reference", 'path': str(pick_path)},
             {'role': 'the approved BBROSE logo', 'path': str(logo_path)}]
    dest.mkdir(parents=True, exist_ok=True)
    (dest / 'request.json').write_text(json.dumps({'model': settings.IMAGE_MODEL, 'quality': QUALITY, 'size': SIZE,
                                                   'inputs': items, 'pick_sha256': pick_sha, 'logo_sha256': logo_sha,
                                                   'prompt': prompt}, ensure_ascii=False, indent=1) + '\n')
    operation = prefix + name

    def invoke(checked):
        api = client
        if api is None:
            from openai import OpenAI
            api = OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=0, timeout=400)
        with ExitStack() as stack:
            files = [stack.enter_context(open(i['path'], 'rb')) for i in checked]
            response = paid_operation(api.images.edit, provider='openai', operation=operation, reservation_prefix=prefix,
                                      reservation_cap=cap_usd, model=settings.IMAGE_MODEL, image=files, prompt=prompt,
                                      n=1, size=SIZE, quality=QUALITY)
        saved = response._rescue_paid_images
        if len(saved) != 1:
            raise RuntimeError('the paid response is kept, but exactly one picture was not recovered')
        shutil.copyfile(saved[0], dest / 'picture.png')
        return {'reservation_id': response._rescue_reservation_id,
                'usage': response.model_dump(mode='json')['usage'],
                'output_sha256': hashlib.sha256((dest / 'picture.png').read_bytes()).hexdigest()}

    result = image_guard.guarded_call(invoke, operation=operation, inputs=items, prompt=prompt, quality=QUALITY,
                                      size=SIZE, picture=name)
    record = dict(result, picture=lm.rel(dest / 'picture.png'), prompt=prompt)
    done.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n')
    return record


def tray_names():
    from apps.ire import palette_tray
    brief = (lm.REPO / 'bbrose_design_os' / 'apps' / 'pipeline' / 'tests' / 'fixtures_124' / 'brief_124.txt').read_text()
    return palette_tray.read_tray(brief)


def tray_prompt(tray):
    names = '; '.join(', '.join(row) for row in tray['names'])
    return TRAY_PROMPT.format(names=names)


def working_colours():
    """A-2's working shade map (the spec's own values: names → hex and kind)."""
    spec = json.loads((lm.REPO / 'docs' / 'audit' / 'day-9' / 'directions' / 'A-2.json').read_text())
    return {row['name']: {'hex': row['hex'], 'kind': row['kind']} for row in spec['shade_map']}


def pans(tray, read):
    """pans.json's rows: every pan its name, its hex and finish as the tray picture shows them (or, where the picture is
    not read, A-2's working colour and the finish its name suggests — flagged), beside the working colour (ΔE00), the
    finish its name suggests, and a flag wherever the sources disagree."""
    from apps.pipeline.targets.container import tray_picture as tp
    work = working_colours()
    rows = []
    for r, names in enumerate(tray['names']):
        for c, name in enumerate(names):
            w = work[name] if name in work else None
            by_name = tp.finish_from_name(name)
            if read['state'] == tp.READ:
                pan = read['pans'][r][c]
                hex_, finish, source, measures = pan['hex'], pan['finish'], 'the tray picture', pan['measures']
            else:
                hex_, finish, source, measures = w['hex'], by_name, 'A-2\'s working colour (the picture was not read)', None
            row = {'row': r + 1, 'col': c + 1, 'name': name, 'hex': hex_, 'finish': finish, 'source': source,
                   'measures': measures, 'finish_from_name': by_name, 'working_hex': None, 'working_kind': None,
                   'de00_to_working': None, 'flags': []}
            if w is not None:
                row['working_hex'], row['working_kind'] = w['hex'], w['kind']
                de = delta_e00(srgb_to_lab(np.array([[int(hex_[i:i + 2], 16) for i in (1, 3, 5)]])),
                                  srgb_to_lab(np.array([[int(w['hex'][i:i + 2], 16) for i in (1, 3, 5)]])))
                row['de00_to_working'] = round(float(de[0]), 2)
                if de[0] > DE_FLAG:
                    row['flags'].append('the picture\'s colour stands ΔE00 %.1f from A-2\'s working %s' % (de[0], w['hex']))
                if w['kind'] != finish:
                    row['flags'].append('the picture reads %s; A-2\'s working map says %s' % (finish, w['kind']))
            if by_name != finish:
                row['flags'].append('its name suggests %s' % by_name)
            if source != 'the tray picture':
                row['flags'].append('not read from a picture')
            rows.append(row)
    return rows


def tray_artwork(tray, pan_rows, case_hex, out_dir):
    """tray-artwork.pdf (page 1 the print: the case colour to 3 mm past the insert, the 18 names live in the support face;
    page 2 the cut: the insert's outline and the pans' wells) and tray-proof.png (the pans drawn in their colours and
    finishes over the print, as the engine draws an open tray — shown, never printed)."""
    import fitz
    from apps.ire import font_roles, palette_tray
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, Document, Group, Rect, SolidFill, Stroke, TextRun
    out = Path(out_dir)
    face = font_roles.resolve_line_face(lm.SUPPORT_STEM, lm.SUPPORT_WEIGHT)
    grid = [[{'row': p['row'] - 1, 'col': p['col'] - 1, 'name': p['name'], 'hex': p['hex'], 'finish': p['finish'],
              'source': p['source']} for p in pan_rows if p['row'] == r + 1] for r in range(tray['rows'])]
    inset = ((CASE_MM[0] - INSIDE_MM[0]) / 2, (CASE_MM[1] - INSIDE_MM[1]) / 2)     # the insert centred in the case
    group, record = palette_tray.compose_open_tray(tray, CASE_MM[0], CASE_MM[1], inset[0], inset[1], ground_hex=case_hex,
                                                   ink_hex=NAME_INK, edge_hexes=[GOLD, GOLD], face=face['label'],
                                                   pans=grid, rim_hex=GOLD, glow_hex=None, name_hex=NAME_INK)

    def walk(node):
        yield node
        if hasattr(node, 'children'):
            for child in node.children:
                yield from walk(child)

    brief_words = {n.upper(): n for row in tray['names'] for n in row}

    def restyled(node):
        """The engine's names set in the support face, tracked as the engine measured them, carrying the brief's own
        words (printed in capitals by the run's case)."""
        if isinstance(node, TextRun):
            words = node.text
            if node.text.upper() in brief_words:
                words = brief_words[node.text.upper()]
            return node.model_copy(update={'text': words, 'font': face['role'], 'tracking_em': NAME_TRACKING_EM,
                                           'text_case': 'upper'})
        if hasattr(node, 'children'):
            return node.model_copy(update={'children': [restyled(c) for c in node.children]})
        return node

    group = restyled(group)
    # the engine's rule round the pan field is not in the tray picture: left out of the proof (it never prints)
    group = group.model_copy(update={'children': [c for c in group.children if c.name != 'tray-pan-field-edge']})
    by_name = {c.name: c for c in group.children}
    names = by_name['SHADE NAMES']
    wells = by_name['PAN WELLS (cut)']
    # the cut carries the insert's own outline beside its wells (the review of Day 10: only the wells were cut)
    outline = by_name['tray-insert-ground'].model_copy(update={
        'name': 'insert outline (cut)', 'fill': None, 'stroke': Stroke(color=Color.from_hex(GOLD), width_mm=CUT_STROKE_MM)})
    ground = Rect(name='case colour (to 3 mm past the insert)', x=-3.0, y=-3.0, w=CASE_MM[0] + 6.0, h=CASE_MM[1] + 6.0,
                  fill=SolidFill(color=Color.from_hex(case_hex)))
    meta = {'typography_surface': SURFACE, 'logical_text/1.0': True}
    engine = out / 'engine'
    engine.mkdir(parents=True, exist_ok=True)
    print_ai = engine / 'tray-print.ai'
    emit_pdf_ai(Document(page_w=CASE_MM[0], page_h=CASE_MM[1], metadata=meta,
                         root=Group(name='TRAY PRINT', children=[ground, names])), str(print_ai))
    cut_ai = engine / 'tray-cut.ai'
    emit_pdf_ai(Document(page_w=CASE_MM[0], page_h=CASE_MM[1], metadata=meta,
                         root=Group(name='TRAY CUT', children=[outline, wells])), str(cut_ai))
    proof_ai = engine / 'tray-proof.ai'
    emit_pdf_ai(Document(page_w=CASE_MM[0], page_h=CASE_MM[1], metadata=meta,
                         root=Group(name='TRAY PROOF', children=[ground, group])), str(proof_ai))
    pdf = fitz.open()
    trim = fitz.Rect(lm.pt(inset[0]), lm.pt(inset[1]), lm.pt(inset[0] + INSIDE_MM[0]), lm.pt(inset[1] + INSIDE_MM[1]))
    for src_path in (print_ai, cut_ai):
        with fitz.open(str(src_path)) as src:
            p = pdf.new_page(width=src[0].rect.width, height=src[0].rect.height)
            p.show_pdf_page(p.rect, src, 0)
        p.set_bleedbox(p.rect)
        p.set_trimbox(trim)                 # the insert's 184 × 114 edge, the case colour 3 mm past it
    pdf.set_page_labels([{'startpage': 0, 'prefix': '1 print: case colour and names ', 'style': ''},
                         {'startpage': 1, 'prefix': '2 cut: insert and wells ', 'style': ''}])
    pdf.set_metadata({'title': 'Enchanted Rose open tray: print layer', 'creator': SURFACE})
    pdf.save(str(out / 'tray-artwork.pdf'), garbage=3, deflate=True)
    pdf.close()
    lm.render_png(proof_ai, 0, lm.FLAT_PPI, out / 'tray-proof.png')
    fonts = {}
    with fitz.open(str(out / 'tray-artwork.pdf')) as d:
        for f in d[0].get_fonts(full=True):
            fonts[f[3]] = f[1] not in ('', 'n/a')
    spans = lm.actual_texts(print_ai, 0)
    want = [n for row in tray['names'] for n in row]
    with fitz.open(str(out / 'tray-artwork.pdf')) as d:
        cut = d[1].get_drawings()
        trim_mm = [round(v * lm.MM_PER_INCH / 72.0, 2) for v in d[0].trimbox]
    sizes = sorted({round(v * lm.MM_PER_INCH / 72.0, 2) for c in cut for v in (c['rect'].width, c['rect'].height)})
    return {'record': {k: record[k] for k in record if k not in ('pans',)}, 'fonts_embedded': fonts,
            'names_live': spans, 'names_word_for_word': [s for s in spans if s] == want,
            'cut': {'paths': len(cut), 'sizes_mm': sizes,
                    'insert_outline': any(abs(c['rect'].width * lm.MM_PER_INCH / 72.0 - INSIDE_MM[0]) < 0.05
                                          and abs(c['rect'].height * lm.MM_PER_INCH / 72.0 - INSIDE_MM[1]) < 0.05
                                          for c in cut)},
            'print_trim_mm': trim_mm}


def _lab(hex_):
    return srgb_to_lab(np.array([[int(hex_[i:i + 2], 16) for i in (1, 3, 5)]]))


def case_colour(pan_rows, lid_dir=None):
    """The case in the lid's teal-ink shadow (the ground the master's small type stands on), so the open tray repeats
    the lid; every pan read against it (ΔE00 and contrast), a pan under ΔE00 10 flagged as reading into the case, and
    the names' contrast in the lid's warm white. Returns the hex, the reason said from the readings, and the rows. The
    shadow is read from the lid master in ``lid_dir`` (Day 10's when None)."""
    if lid_dir is None:
        lid_dir = lm.OUT
    checks = json.loads((Path(lid_dir) / 'checks.json').read_text())
    case = [r for r in checks['contrast'] if r['line'] == 'descriptor_en'][0]['under']
    against = []
    for r in pan_rows:
        de = float(delta_e00(_lab(r['hex']), _lab(case))[0])
        against.append({'name': r['name'], 'hex': r['hex'], 'de00': round(de, 2),
                        'contrast': round(lm.contrast_ratio(r['hex'], case), 2), 'reads_into_the_case': de < CASE_DE_FLOOR})
    low = [a for a in against if a['reads_into_the_case']]
    why = ('the lid\'s teal-ink shadow, the ground its small type stands on, so the open tray repeats the lid; the names '
           'in the lid\'s warm white at %.1f : 1. %d of %d pans stand ΔE00 %g or more from it' % (
               lm.contrast_ratio(NAME_INK, case), len(against) - len(low), len(against), CASE_DE_FLOOR))
    if low:
        why += '; %s read into it — flagged for the owner' % ', '.join('%s (ΔE00 %.1f, %.2f : 1)' % (
            a['name'], a['de00'], a['contrast']) for a in low)
    return case, why, against


def build_tray(read, *, out_dir=None, picture_dir=None, lid_dir=None, lift=False):
    """pans.json, tray-artwork.pdf and tray-proof.png from the tray picture as ``tray_picture.read_tray_picture``
    read it, at $0. Returns the record. Day 10's tray by default; [Day 11, D-D11-5.2] Golden Hour's new tray writes to
    ``out_dir``, reads its picture's record from ``picture_dir`` and the case from the lid in ``lid_dir``, and with
    ``lift`` every pan under ΔE00 10 from the case is lightened by the least L* step that reaches it (``lift_from_case``),
    listed, its row 3's teal pans counted (``teal_pans``)."""
    out = TRAY
    if out_dir is not None:
        out = Path(out_dir)
    if picture_dir is None:
        picture_dir = out
    tray = tray_names()
    rows = pans(tray, read)
    case, why, against = case_colour(rows, lid_dir)
    lifted = []
    if lift:
        lifted = lift_from_case(rows, case)
        case, why, against = case_colour(rows, lid_dir)
    for r, a in zip(rows, against):
        r['against_the_case'] = {k: a[k] for k in ('de00', 'contrast')}
        if a['reads_into_the_case']:
            r['flags'].append('it reads into the case colour (ΔE00 %.1f)' % a['de00'])
    art = tray_artwork(tray, rows, case, out)
    picture = json.loads((Path(picture_dir) / 'picture.json').read_text())
    record = {'schema': 'container_tray_pans/1.0+day10', 'grid': [3, 6], 'shape': 'square',
              'picture': {'file': picture['picture'], 'sha256': picture['output_sha256'],
                          'reservation_id': picture['reservation_id'],
                          'inputs': 'the owner\'s pick (style reference) and the approved logo',
                          'read': {k: read[k] for k in ('state', 'params', 'rim', 'glow', 'names_ink') if k in read}},
              'definitions': '10-12: shimmer — a soft, subtle sheen toward one corner; glitter — fine, dense sparkle; '
                             'matte — neither (tray_picture: glitter where flakes stand out, shimmer where a fine grain or '
                             'a sheen runs across it)',
              'case': {'hex': case, 'why': why, 'pans_against_it': against},
              'rims': {'hex': GOLD, 'why': 'soft gold, as the tray picture shows them (10-12 (11)); the reader measured '
                                           '%s on the rim ring (its shadow included)' % read['rim']},
              'names': {'face': lm.line_face('descriptor_en')['label'], 'pt': art['record']['name_pt'],
                        'tracking_em': NAME_TRACKING_EM, 'ink': NAME_INK, 'case': 'capitals'},
              'pans': rows,
              'counts': {f: sum(1 for r in rows if r['finish'] == f) for f in ('matte', 'shimmer', 'glitter')},
              'flagged': [r['name'] for r in rows if r['flags']],
              'said': 'colours and finishes from the tray picture (made once), never from shadow; the picture holds no '
                      'teal pan though the brief\'s palette is rose, lilac and teal — row 3 reads browns, plums and navy, '
                      'ΔE00 27–50 from A-2\'s working teals: flagged for the owner',
              'artwork': art, 'mirror': 'no mirror in the brief: brief 124 names none, and no case record calls for one'}
    if lift:
        teal = teal_pans(read)
        record.update({'schema': 'container_tray_pans/1.0+day11', 'lifted_from_the_case': lifted, 'teal_row_3': teal,
                       'said': 'colours and finishes from the tray picture, never from shadow; row 3 holds %d teal pans '
                               '(%s; D-D11-5.2 asks three or more); %d pans lightened off the case by the least L* step '
                               '(%s)' % (teal['count'], _listed(teal['names']), len(lifted),
                                         _listed(['%s +%.1f L*' % (x['name'], x['l_step']) for x in lifted]))})
    lm.write_json(out / 'pans.json', record)
    return record


def _listed(items):
    """Items said in a sentence: joined by commas, or "none"."""
    if not items:
        return 'none'
    return ', '.join(items)


TEAL_HUE = (150.0, 250.0)           # a teal pan: its CIELAB hue between 150° and 250° (blue-green, sea glass to peacock) …
TEAL_CHROMA_MIN = 10.0              # … and chroma 10 or more (a grey-blue is not teal)
LIFT_STEP_L = 0.5                   # the pan rule's step: a pan under ΔE00 10 from the case lightened 0.5 L* at a time


def lab_to_srgb(lab):
    """CIE L*a*b* (D65) → sRGB 0–255 (clipped), the inverse of ``round_files_faces.srgb_to_lab``."""
    lab = np.asarray(lab, dtype=np.float64)
    fy = (lab[..., 0] + 16) / 116
    f = np.stack([fy + lab[..., 1] / 500, fy, fy - lab[..., 2] / 200], axis=-1)
    d = 6.0 / 29.0
    t = np.where(f > d, f ** 3, 3 * d * d * (f - 4.0 / 29.0)) * np.array([0.95047, 1.0, 1.08883])
    m = np.array([[3.2404542, -1.5371385, -0.4985314], [-0.9692660, 1.8760108, 0.0415560],
                  [0.0556434, -0.2040259, 1.0572252]])
    lin = np.clip(t @ m.T, 0, 1)
    c = np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * lin ** (1 / 2.4) - 0.055)
    return np.clip(c * 255, 0, 255)


def _hex(rgb):
    return '#%02X%02X%02X' % tuple(int(round(v)) for v in rgb)


def lift_from_case(pan_rows, case_hex):
    """D-D11-5.2's pan rule: every pan ΔE00 10 or more from the case, or lightened by the least L* step that reaches it
    — its L* raised 0.5 at a time (a* and b* kept), the colour read again from the hex it prints as, until ΔE00 to the
    case is 10 or more. Changes the rows in place (the picture's own reading kept beside); returns what moved."""
    moved = []
    case = _lab(case_hex)
    for r in pan_rows:
        before = float(delta_e00(_lab(r['hex']), case)[0])
        if before >= CASE_DE_FLOOR:
            continue
        lab = _lab(r['hex'])[0]
        step = 0.0
        hex_ = r['hex']
        while float(delta_e00(_lab(hex_), case)[0]) < CASE_DE_FLOOR:
            step += LIFT_STEP_L
            if lab[0] + step > 100.0:
                raise ValueError('%s cannot be lightened off the case' % r['name'])
            hex_ = _hex(lab_to_srgb(np.array([lab[0] + step, lab[1], lab[2]])))
        after = float(delta_e00(_lab(hex_), case)[0])
        moved.append({'name': r['name'], 'from': r['hex'], 'to': hex_, 'l_step': step, 'de00_before': round(before, 2),
                      'de00_after': round(after, 2)})
        r['picture_hex'] = r['hex']
        r['hex'] = hex_
        r['flags'].append('lightened off the case by L* %.1f (ΔE00 %.1f → %.1f), D-D11-5.2' % (step, before, after))
    return moved


def teal_pans(read):
    """Row 3's teal pans as the picture reads them: CIELAB hue 150°–250° and chroma 10 or more."""
    from apps.pipeline.targets.container import tray_picture as tp
    names = tray_names()['names'][2]
    found = []
    if read['state'] == tp.READ:
        for name, pan in zip(names, read['pans'][2]):
            l_, a, b = _lab(pan['hex'])[0]
            hue = float(np.degrees(np.arctan2(b, a)) % 360)
            if TEAL_HUE[0] <= hue <= TEAL_HUE[1] and float(np.hypot(a, b)) >= TEAL_CHROMA_MIN:
                found.append(name)
    return {'count': len(found), 'names': found, 'holds': len(found) >= 3,
            'rule': 'a pan is teal at CIELAB hue %g°–%g° and chroma %g or more' % (TEAL_HUE + (TEAL_CHROMA_MIN,))}


#: [Day 11, D-D11-5.2] Golden Hour's new tray: the prompt states the colour story row by row, row 3 its teals
TRAY_STORY_PROMPT = (
    "Image 1 is the closed lid of an eyeshadow palette: the house's chosen design and the style reference. Image 2 is the "
    "BBROSE logo, for reference only. Draw the same palette OPEN, seen from directly above and square to the eye, filling "
    "the frame: its open tray holding 18 square pans in 3 rows of 6, all one size, evenly spaced in a neat grid, each pan "
    "a pressed eyeshadow in its own shade, each shade's name printed in clean small capitals under its own pan. THE "
    "COLOUR STORY, ROW BY ROW — the palette is rose, lilac and teal: ROW 1, THE ROSES, left to right: {row1}. ROW 2, THE "
    "LILACS, left to right: {row2}. ROW 3, THE TEALS, left to right: {row3}. Row 3 must read clearly TEAL — blue-green "
    "like sea glass and peacock feathers, never brown, plum, grey or navy; at least {teal_min} of its pans plainly teal. "
    "The tray in the closed lid's deep teal-ink shadow colour, the pans' rims soft gold; every pan stands clearly lighter "
    "than the tray around it. Each pan shows its finish: matte (flat powder), shimmer (a soft sheen toward one corner) or "
    "glitter (fine dense sparkle). Plain flat front-on view; no hands, no brushes, no props, no reflections, no logo, no "
    "roses, no petals, no arches, no glowing frames, no extra words.")
TEAL_MIN = 3
LILAC_HUE_MAX = 335.0               # the prompt's words for a working colour: lilac violet from the teals' end to 335°,
ROSE_GOLD_HUE_MIN = 40.0            # rose gold from 40° to the teals', rose pink otherwise


def _shade_words(hex_):
    """A working colour in plain words: lightness and hue family, from its CIELAB reading."""
    l_, a, b = _lab(hex_)[0]
    hue = float(np.degrees(np.arctan2(b, a)) % 360)
    light = 'deep'
    if l_ >= 80:
        light = 'pale'
    elif l_ >= 62:
        light = 'soft'
    elif l_ >= 42:
        light = 'mid'
    family = 'rose pink'                         # hue under 40° or over 335°
    if TEAL_HUE[0] <= hue <= TEAL_HUE[1]:
        family = 'teal'
    elif TEAL_HUE[1] < hue <= LILAC_HUE_MAX:
        family = 'lilac violet'
    elif ROSE_GOLD_HUE_MIN <= hue < TEAL_HUE[0]:
        family = 'rose gold'
    return '%s %s' % (light, family)


def tray_story_prompt(tray):
    """D-D11-5.2's prompt: the colour story row by row from the 18 names (``tray_names``), each pan named with its
    working colour in plain words and its finish (A-2's shade map), row 3 the teals, at least three plainly teal."""
    work = working_colours()
    rows = []
    for names in tray['names']:
        rows.append('; '.join('%s (%s, %s)' % (n, _shade_words(work[n]['hex']), work[n]['kind']) for n in names))
    return TRAY_STORY_PROMPT.format(row1=rows[0], row2=rows[1], row3=rows[2], teal_min=TEAL_MIN)


def inside_master(out_dir):
    """The inside lid by the master's preservation path: the picture cropped to the insert's proportion (184 × 114, from
    the middle), upscaled 2× by Lanczos, 3 mm of bleed by mirroring; inside-lid.pdf (the plate, RGB tagged sRGB) and its
    flat at 300 PPI. Nothing redrawn."""
    import fitz
    out = Path(out_dir)
    src = np.asarray(Image.open(out / 'picture.png').convert('RGB'))
    h, w = src.shape[:2]
    want_h = int(round(w * INSIDE_MM[1] / INSIDE_MM[0]))
    top = (h - want_h) // 2
    crop = src[top:top + want_h]
    up = lm.upscale(crop)
    px_per_mm = up.shape[1] / INSIDE_MM[0]
    b = int(np.ceil(lm.BLEED_MM * px_per_mm))
    bled = cv2.copyMakeBorder(up, b, b, b, b, cv2.BORDER_REFLECT_101)
    Image.fromarray(bled).save(out / 'inside-plate-bleed.png')
    page_w, page_h = INSIDE_MM[0] + 2 * lm.BLEED_MM, INSIDE_MM[1] + 2 * lm.BLEED_MM
    pdf = fitz.open()
    p = pdf.new_page(width=lm.pt(page_w), height=lm.pt(page_h))
    bm = b / px_per_mm
    p.insert_image(fitz.Rect(lm.pt(lm.BLEED_MM - bm), lm.pt(lm.BLEED_MM - bm), lm.pt(lm.BLEED_MM + INSIDE_MM[0] + bm),
                             lm.pt(lm.BLEED_MM + INSIDE_MM[1] + bm)), filename=str(out / 'inside-plate-bleed.png'))
    trim = fitz.Rect(lm.pt(lm.BLEED_MM), lm.pt(lm.BLEED_MM), lm.pt(lm.BLEED_MM + INSIDE_MM[0]), lm.pt(lm.BLEED_MM + INSIDE_MM[1]))
    p.set_bleedbox(p.rect)
    p.set_trimbox(trim)
    pdf.set_metadata({'title': 'Enchanted Rose inside lid', 'creator': 'apps/pipeline/services/palette_open.py::inside_master'})
    lm.tag_srgb(pdf)
    pdf.save(str(out / 'inside-lid.pdf'), garbage=3, deflate=True)
    pdf.close()
    with fitz.open(str(out / 'inside-lid.pdf')) as d:
        pix = d[0].get_pixmap(dpi=300, clip=trim, alpha=False)
        pix.set_dpi(300, 300)
        pix.save(str(out / 'inside-lid-flat.png'))
    return {'crop_px': [0, top, w, top + want_h], 'upscaled_px': [up.shape[1], up.shape[0]],
            'ppi': round(px_per_mm * lm.MM_PER_INCH, 1), 'effective_ppi': round(w / INSIDE_MM[0] * lm.MM_PER_INCH, 1),
            'bleed_px': b, 'size_mm': list(INSIDE_MM)}
