"""Day 10 §4 — the palette's outer box on the brief's die: ``reverse_tuck_end_carton`` 1.4, inside W 122 × D 14 × H 192,
bleed 3, safe 4, board 0.45 (record ``dad60dbf``), from our dieline engine; the die untouched.

The box lies flat (13 Oct): the FRONT panel carries the lid master turned a quarter (as the shared engine turns a flat
box's front, ``graph.quarter_turn``: the lid's top along the panel's left crease, its right edge along the top tuck end),
at 100 % — its copy and logo fall inside the front's safe area — the picture filling the panel to its bleed by extending
its own edges (mirrored), never cropped inside the lid; the BACK panel carries §3's sticker layout (182 × 112 mm, inside
the back's 114 × 184 safe area at 100 %), turned the same way; the LONG SIDES the name in English and Arabic and the brand;
the SHORT ENDS (the tuck lids) the brand; the glue tab, the dust flaps and the tucks' tongues clean. The front's foil (the
name and the logo's letters) mapped to the panel on its own plate page; no relief.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from apps.pipeline.services import lid_master as lm

OUT = lm.REPO / 'docs' / 'audit' / 'day-10' / 'box'
SCHEMA = 'day10_box/1'
SURFACE = 'apps/pipeline/services/palette_box.py::build'
DIE_RECORD = lm.REPO / 'bbrose_design_os' / 'media' / 'dielines' / 'dad60dbf-31b8-431d-9c6d-97bef5239922' / \
    'dad60dbf-31b8-431d-9c6d-97bef5239922_spec.json'
BLEED_MM = 3.0
SAFE_MM = 4.0
CREASE_OVER_MM = 0.5                # a ground runs 0.5 mm past a crease (no white line at the fold)
FRONT_EXTEND_MM = 6.0               # the lid's picture extended by mirroring: enough to reach the front's bleed
A3_MM = (420.0, 297.0)
MARK_MM = 5.0
MARK_GAP_MM = 3.0
SIDE_NAME_H_MM = 5.0                # the traced name's ink height on a long side
SIDE_AR_PT = 9.0
SIDE_LOGO_H_MM = 3.2
END_LOGO_H_MM = 4.0
NOTCH_KEEP_MM = 13.0                # the thumb notch's keep-out radius (r 9 + 4)
DIE_TOL_MM = 0.01
CLEAN_CLEAR_MM = 0.6                # a non-printing part is read for ink beyond 0.6 mm of every printing face …
CLEAN_INK_MAX_MM2 = 0.5             # … and is clean under 0.5 mm² of ink there (anti-aliasing at a cut, no more)


def die():
    """The die from our engine, pinned at the record's version (1.4): coordinates in mm, origin at the flat's top-left."""
    from apps.dielines.geometry import fold_check
    from apps.dielines.geometry.engine import calculate_dieline
    from apps.dielines.validators.schema import DielineInputJSON
    spec = json.loads(DIE_RECORD.read_text())
    if spec['input']['template_version'] != '1.4':
        raise ValueError('the die record is not 1.4')
    coords = calculate_dieline(DielineInputJSON(**spec['input']))
    return coords, fold_check.check(coords), spec


def faces(coords):
    """The printing faces (x0, y0, x1, y1 mm) and, for each, its cut edges (where it bleeds 3 mm) — the rest creases."""
    panels = {p.name: (p.x, p.y, p.x + p.width, p.y + p.height) for p in coords.panels}
    d = coords.derived
    top = [t for t in d['tucks'] if t['end'] == 'top'][0]
    bottom = [t for t in d['tucks'] if t['end'] == 'bottom'][0]
    out = {
        'back': {'box': panels['back'], 'cut': ('bottom',)},
        'side_left': {'box': panels['side_left'], 'cut': ()},
        'front': {'box': panels['front'], 'cut': ('top',)},
        'side_right': {'box': panels['side_right'], 'cut': ('right',)},
        'top_end': {'box': (top['x_l'], top['fold_y'], top['x_r'], top['hinge_y']), 'cut': ('left', 'right')},
        'bottom_end': {'box': (bottom['x_l'], bottom['hinge_y'], bottom['x_r'], bottom['fold_y']), 'cut': ('left', 'right')},
    }
    for f in out.values():
        x0, y0, x1, y1 = f['box']
        f['safe'] = (x0 + SAFE_MM, y0 + SAFE_MM, x1 - SAFE_MM, y1 - SAFE_MM)
        grow = {side: CREASE_OVER_MM for side in ('left', 'top', 'right', 'bottom')}
        for side in f['cut']:
            grow[side] = BLEED_MM
        f['ground'] = (x0 - grow['left'], y0 - grow['top'], x1 + grow['right'], y1 + grow['bottom'])
    return out


def non_printing(coords):
    """The die's parts that carry no ink: the four dust flaps, the glue tab and the two tongues (each tuck past its
    fold), as one geometry."""
    from shapely.geometry import box as rect
    from shapely.ops import unary_union
    tongues = []
    for t, poly in zip(coords.derived['tucks'], coords.tuck_flap_polygons):
        x0, y0, x1, y1 = poly.bounds
        if t['end'] == 'top':
            tongues.append(poly.intersection(rect(x0, y0, x1, t['fold_y'])))
        else:
            tongues.append(poly.intersection(rect(x0, t['fold_y'], x1, y1)))
    return unary_union(list(coords.dust_flap_polygons) + [coords.glue_tab_polygon] + tongues)


def ground_shape(face, bare):
    """A face's ground: its box grown 3 mm past its cut edges and 0.5 mm past its creases, less the non-printing parts
    (``bare``) beyond its own 0.5 mm crease band — so a tuck end's bleed stops at the dust flaps beside it (the review
    of Day 10: about 34 mm² of ground lay on each of three flaps)."""
    from shapely.geometry import box as rect
    x0, y0, x1, y1 = face['box']
    own = rect(x0 - CREASE_OVER_MM, y0 - CREASE_OVER_MM, x1 + CREASE_OVER_MM, y1 + CREASE_OVER_MM)
    return rect(*face['ground']).difference(bare.difference(own))


def turned(box_art, size_art, target):
    """A box in an art's mm (x0, y0, x1, y1 in a W × H art) turned a quarter counter-clockwise into ``target`` (the art's
    trim, H wide × W tall, in flat mm): flat x = X0 + v, flat y = Y1 − u."""
    x0, y0, x1, y1 = box_art
    tx0, ty0, tx1, ty1 = target
    return (tx0 + y0, ty1 - x1, tx0 + y1, ty1 - x0)


def front_picture(out, plate, target, clip):
    """The lid's picture for the front: the trimmed plate extended 6 mm by mirroring its own edges, turned a quarter
    counter-clockwise, cut to the front's clip (the panel to its creases, 3 mm past its top cut) — exact pixel windows,
    nothing scaled, nothing inside the lid cropped."""
    ppm = lm.PX_PER_MM
    e = int(np.ceil(FRONT_EXTEND_MM * ppm))
    ext = cv2.copyMakeBorder(plate, e, e, e, e, cv2.BORDER_REFLECT_101)
    rot = np.ascontiguousarray(np.rot90(ext, 1))
    ox, oy = target[0] - e / ppm, target[1] - e / ppm               # the turned picture's top-left, flat mm
    j0, i0 = int(round((clip[0] - ox) * ppm)), int(round((clip[1] - oy) * ppm))
    j1, i1 = int(round((clip[2] - ox) * ppm)), int(round((clip[3] - oy) * ppm))
    if i0 < 0 or j0 < 0 or i1 > rot.shape[0] or j1 > rot.shape[1]:
        raise ValueError('the extended picture does not reach the front\'s bleed')
    window = rot[i0:i1, j0:j1]
    path = out / 'engine' / 'front-picture.png'
    Image.fromarray(window).save(path)
    placed = (ox + j0 / ppm, oy + i0 / ppm, ox + j1 / ppm, oy + i1 / ppm)
    return path, placed, {'extend_px': e, 'window_px': [j0, i0, j1, i1], 'placed_mm': [round(v, 3) for v in placed]}


def side_band(out, name_rings, gold, ink, side_len, side_w):
    """One long side's band, laid out along its length (``side_len`` × ``side_w`` mm, before it is turned): the traced
    name (its outlines scaled to 5 mm ink), the brief's Arabic name in Tajawal PF, the brand — centred in a row."""
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, Document, Group, Path as GPath, SolidFill, TextRun
    geom = lm.rings_area(name_rings, 24)
    gx0, gy0, gx1, gy1 = geom.bounds
    k = SIDE_NAME_H_MM / (gy1 - gy0)
    name_w = (gx1 - gx0) * k
    from apps.pipeline.services.palette_sticker import NAME_AR, width_mm
    ar_face = lm.line_face('descriptor_ar')
    ar_text = NAME_AR                       # brief 124's Arabic name (the review of Day 10: the side carried the descriptor)
    ar_w = width_mm(ar_text, ar_face, SIDE_AR_PT)
    master_aspect = 0.20859051088028435
    logo_w = SIDE_LOGO_H_MM / master_aspect
    gap = 8.0
    total = logo_w + gap + name_w + gap + ar_w
    x = (side_len - total) / 2
    cy = side_w / 2
    logo_box = (x, cy - SIDE_LOGO_H_MM / 2, logo_w, SIDE_LOGO_H_MM)
    nx = x + logo_w + gap
    rings = lm.map_rings(name_rings, lambda p: (nx + (p[0] - gx0) * k, cy - SIDE_NAME_H_MM / 2 + (p[1] - gy0) * k))
    ax = nx + name_w + gap + ar_w
    ar_base = cy + SIDE_AR_PT * lm.MM_PER_INCH / 72.0 * 0.32
    nodes = lm.logo_parts(logo_box, gold, foil_letters=False) + [
        GPath(name='Enchanted Rose', segments=lm.rings_segments(rings), fill=SolidFill(color=Color.from_hex(gold)),
              fill_rule='evenodd'),
        TextRun(name='side:ar', text=ar_text, x=ax, y=ar_base, font=ar_face['role'], size_pt=SIDE_AR_PT,
                color=Color.from_hex(ink), align='right', rtl=True)]
    doc = Document(page_w=side_len, page_h=side_w, metadata={'typography_surface': SURFACE, 'logical_text/1.0': True},
                   root=Group(name='SIDE', children=[Group(name='name', actual_text='Enchanted Rose', children=nodes)]))
    path = out / 'engine' / 'side-band.ai'
    emit_pdf_ai(doc, str(path))
    boxes = {'logo': (logo_box[0], logo_box[1], logo_box[0] + logo_w, logo_box[1] + SIDE_LOGO_H_MM),
             'name': (nx, cy - SIDE_NAME_H_MM / 2, nx + name_w, cy + SIDE_NAME_H_MM / 2),
             'arabic': (ax - ar_w, cy - 2.6, ax, cy + 2.6)}
    return path, boxes


def end_logo(out, gold, end_len, end_w):
    """A short end's brand: the approved mark centred, 4 mm tall, in the lid's gold ink."""
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Document, Group
    aspect = 0.20859051088028435
    w = END_LOGO_H_MM / aspect
    box = ((end_len - w) / 2, (end_w - END_LOGO_H_MM) / 2, w, END_LOGO_H_MM)
    doc = Document(page_w=end_len, page_h=end_w, metadata={'typography_surface': SURFACE},
                   root=Group(name='END', children=[Group(name='LOGO', role='logo',
                                                          children=lm.logo_parts(box, gold, foil_letters=False))]))
    path = out / 'engine' / 'end-logo.ai'
    emit_pdf_ai(doc, str(path))
    return path, (box[0], box[1], box[0] + w, box[1] + END_LOGO_H_MM)


def sources_record(given, lid_dir, sticker_dir, relief):
    """[Day 11] Where the box's front, foil, relief and back were read from — written into box-fold-check.json only
    when the build was given its sources (``given``); None on Day 10's default path, whose record stays as it was."""
    if not given:
        return None
    said = 'none'
    if relief:
        said = 'the lid\'s relief plate turned onto the front (page 3)'
    return {'lid': lm.rel(lid_dir), 'sticker': lm.rel(sticker_dir), 'relief': said}


def build(out_dir, *, lid_dir=None, sticker_dir=None, schema=SCHEMA):
    """§4 at $0: box-artwork.pdf (page 1 the artwork flat on the die, its cut and crease on locked layers; page 2 the
    foil plate; page 3 the relief plate, none), box-artwork.ai (layers: artwork, foil, cut, crease, guides — the die
    locked, the type live), box-flat.png at 300 PPI, box-fold-check.json, box-1to1-A3.pdf (100 % with crop and fold
    marks).

    [Day 11] The front, the foil and the back are read from the lid master in ``lid_dir`` and the sticker in
    ``sticker_dir`` (Day 10's when None); where the lid carries a relief layer (``engine/layer-relief.ai``: Golden
    Hour's embossed bars, D-D11-5.1) the front's relief is mapped to page 3 and to a relief layer, turned as the front
    is."""
    import fitz
    out = Path(out_dir)
    # [Day 11] the record names its sources only when they are given: Day 10's default box-fold-check.json is unchanged
    sources_given = lid_dir is not None or sticker_dir is not None
    if lid_dir is None:
        lid_dir = lm.OUT
    if sticker_dir is None:
        sticker_dir = lm.REPO / 'docs' / 'audit' / 'day-10' / 'sticker'
    lid_dir, sticker_dir = Path(lid_dir), Path(sticker_dir)
    (out / 'engine').mkdir(parents=True, exist_ok=True)
    coords, fold_record, spec = die()
    fc = faces(coords)
    master = json.loads((lid_dir / 'master.json').read_text())
    ground = [r for r in json.loads((lid_dir / 'checks.json').read_text())['contrast'] if r['line'] == 'descriptor_en'][0]
    ground_hex, ink_hex = ground['under'], ground['ink']
    gold = master['logo']['gold']
    pick = lm.load_pick(lm.PICK)
    name_rings, _, _ = lm.trace_name(pick, lm.NAME_BOX)
    plate = np.asarray(Image.open(lid_dir / 'engine' / 'plate.png').convert('RGB'))

    fx0, fy0, fx1, fy1 = fc['front']['box']
    cx, cy = (fx0 + fx1) / 2, (fy0 + fy1) / 2
    target = (cx - lm.LID_MM[1] / 2, cy - lm.LID_MM[0] / 2, cx + lm.LID_MM[1] / 2, cy + lm.LID_MM[0] / 2)
    clip = (fx0, fy0 - BLEED_MM, fx1, fy1)
    pic_path, pic_placed, pic_rec = front_picture(out, plate, target, clip)

    # the back: the sticker's layout (182 × 112), turned the same way, centred
    sticker_ai = sticker_dir / 'engine' / 'sticker-engine.ai'
    bx0, by0, bx1, by1 = fc['back']['box']
    bcx, bcy = (bx0 + bx1) / 2, (by0 + by1) / 2
    sw, sh = 182.0 + 4.0, 112.0 + 4.0                  # the sticker page with its 2 mm bleed
    back_target = (bcx - sh / 2, bcy - sw / 2, bcx + sh / 2, bcy + sw / 2)
    sticker_trim = turned((2.0, 2.0, 184.0, 114.0), (sw, sh), back_target)
    sticker_safe = turned((2.0 + 3.5, 2.0 + 3.5, 184.0 - 3.5, 114.0 - 3.5), (sw, sh), back_target)

    # the long sides and the short ends
    side_len = fc['side_left']['box'][3] - fc['side_left']['box'][1]
    side_w = fc['side_left']['box'][2] - fc['side_left']['box'][0]
    band_path, band_boxes = side_band(out, name_rings, gold, ink_hex, side_len, side_w)
    end_len = fc['top_end']['box'][2] - fc['top_end']['box'][0]
    end_w = fc['top_end']['box'][3] - fc['top_end']['box'][1]
    end_path, end_box = end_logo(out, gold, end_len, end_w)

    px0, py0 = -BLEED_MM, -BLEED_MM
    W = coords.cut_polygon.bounds[2] + 2 * BLEED_MM
    H = coords.cut_polygon.bounds[3] + 2 * BLEED_MM

    def R(box):
        x0, y0, x1, y1 = box
        return fitz.Rect(lm.pt(x0 - px0), lm.pt(y0 - py0), lm.pt(x1 - px0), lm.pt(y1 - py0))

    def rgb(h):
        return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))

    lid_type, lid_logo, lid_foil = (fitz.open(str(lid_dir / 'engine' / ('layer-%s.ai' % k))) for k in ('type', 'logo', 'foil'))
    relief_layer = lid_dir / 'engine' / 'layer-relief.ai'
    lid_relief = None
    if relief_layer.exists():
        lid_relief = fitz.open(str(relief_layer))
    sticker = fitz.open(str(sticker_ai))
    band = fitz.open(str(band_path))
    end = fitz.open(str(end_path))

    bare = non_printing(coords)
    grounds = {name: ground_shape(fc[name], bare) for name in ('back', 'side_left', 'side_right', 'top_end', 'bottom_end')}

    def artwork(page, oc):
        for name, geom in grounds.items():
            for part in lm.parts(geom):
                shape = page.new_shape()
                for ring in [part.exterior, *part.interiors]:
                    shape.draw_polyline([fitz.Point(lm.pt(x - px0), lm.pt(y - py0)) for x, y in ring.coords])
                shape.finish(color=None, fill=rgb(ground_hex), width=0, even_odd=True, closePath=True, oc=oc)
                shape.commit()
        page.insert_image(R(pic_placed), filename=str(pic_path), oc=oc)
        page.show_pdf_page(R(target), lid_type, 0, rotate=90, oc=oc)
        page.show_pdf_page(R(target), lid_logo, 0, rotate=90, oc=oc)
        page.show_pdf_page(R(back_target), sticker, 0, rotate=90, oc=oc)
        for name in ('side_left', 'side_right'):
            page.show_pdf_page(R(fc[name]['box']), band, 0, rotate=90, oc=oc)
        page.show_pdf_page(R(fc['top_end']['box']), end, 0, rotate=180, oc=oc)
        page.show_pdf_page(R(fc['bottom_end']['box']), end, 0, oc=oc)

    def die_lines(page, oc_cut, oc_crease):
        poly = coords.cut_polygon
        rings = [poly.exterior] + list(poly.interiors)
        for ring in rings:
            pts = [fitz.Point(lm.pt(x - px0), lm.pt(y - py0)) for x, y in ring.coords]
            page.draw_polyline(pts, color=(0.85, 0, 0.55), width=0.5, oc=oc_cut)
        for x1, y1, x2, y2 in coords.slit_lines:
            page.draw_line(fitz.Point(lm.pt(x1 - px0), lm.pt(y1 - py0)), fitz.Point(lm.pt(x2 - px0), lm.pt(y2 - py0)),
                           color=(0.85, 0, 0.55), width=0.5, oc=oc_cut)
        for x1, y1, x2, y2 in coords.fold_lines:
            page.draw_line(fitz.Point(lm.pt(x1 - px0), lm.pt(y1 - py0)), fitz.Point(lm.pt(x2 - px0), lm.pt(y2 - py0)),
                           color=(0, 0.6, 0.9), width=0.4, dashes='[3 1.6] 0', oc=oc_crease)

    def guides(page, oc):
        for name, f in fc.items():
            page.draw_rect(R(f['safe']), color=(0, 0.6, 0.9), width=0.2, dashes='[1 2] 0', oc=oc)
        nx = fc['front']['box']
        notch = coords.derived['thumb_notch']
        page.draw_circle(fitz.Point(lm.pt(notch['cx'] - px0), lm.pt(notch['y'] - py0)), lm.pt(NOTCH_KEEP_MM),
                         color=(0.9, 0.5, 0), width=0.2, dashes='[1 2] 0', oc=oc)

    pdf = fitz.open()
    layers = {name: pdf.add_ocg(name, on=True) for name in ('artwork', 'cut', 'crease')}
    p = pdf.new_page(width=lm.pt(W), height=lm.pt(H))
    artwork(p, layers['artwork'])
    die_lines(p, layers['cut'], layers['crease'])
    p = pdf.new_page(width=lm.pt(W), height=lm.pt(H))
    p.show_pdf_page(R(target), lid_foil, 0, rotate=90)
    p = pdf.new_page(width=lm.pt(W), height=lm.pt(H))                # the relief plate: none unless the lid has one
    relief_label = '3 relief plate (none) '
    if lid_relief is not None:
        p.show_pdf_page(R(target), lid_relief, 0, rotate=90)
        relief_label = '3 relief plate (front: blind emboss, the five bars) '
    pdf.set_layer(-1, locked=[layers['cut'], layers['crease']])
    pdf.set_page_labels([{'startpage': 0, 'prefix': '1 artwork on the die ', 'style': ''},
                         {'startpage': 1, 'prefix': '2 foil plate (front) ', 'style': ''},
                         {'startpage': 2, 'prefix': relief_label, 'style': ''}])
    for page in pdf:
        page.set_bleedbox(page.rect)
        page.set_trimbox(R(coords.cut_polygon.bounds))
    pdf.set_metadata({'title': 'Enchanted Rose palette box on die dad60dbf', 'creator': SURFACE})
    lm.tag_srgb(pdf)
    pdf.save(str(out / 'box-artwork.pdf'), garbage=3, deflate=True)
    pdf.close()

    ai = fitz.open()
    names = ('artwork', 'foil', 'cut', 'crease', 'guides')
    if lid_relief is not None:
        names = ('artwork', 'foil', 'relief', 'cut', 'crease', 'guides')
    layers = {name: ai.add_ocg(name, on=name not in ('foil', 'relief')) for name in names}
    p = ai.new_page(width=lm.pt(W), height=lm.pt(H))
    artwork(p, layers['artwork'])
    p.show_pdf_page(R(target), lid_foil, 0, rotate=90, oc=layers['foil'])
    if lid_relief is not None:
        p.show_pdf_page(R(target), lid_relief, 0, rotate=90, oc=layers['relief'])
    die_lines(p, layers['cut'], layers['crease'])
    guides(p, layers['guides'])
    ai.set_layer(-1, locked=[layers['cut'], layers['crease']])
    p.set_bleedbox(p.rect)
    p.set_trimbox(R(coords.cut_polygon.bounds))
    ai.set_metadata({'title': 'Enchanted Rose palette box (layers)', 'creator': SURFACE})
    lm.tag_srgb(ai)
    ai.save(str(out / 'box-artwork.ai'), garbage=3, deflate=True)
    ai.close()
    art_only = fitz.open()                                            # the artwork without its die (the board's view)
    p = art_only.new_page(width=lm.pt(W), height=lm.pt(H))
    artwork(p, 0)
    art_only.save(str(out / 'engine' / 'box-art-only.pdf'), garbage=3, deflate=True)
    art_only.close()
    for d in (lid_type, lid_logo, lid_foil, sticker, band, end):
        d.close()
    if lid_relief is not None:
        lid_relief.close()
    with fitz.open(str(out / 'box-artwork.pdf')) as d:
        pix = d[0].get_pixmap(dpi=300, alpha=False)
        pix.set_dpi(300, 300)
        pix.save(str(out / 'box-flat.png'))
    a3(out, W, H, coords, px0, py0)
    record = fold_check_record(out, coords, fold_record, fc, master, target, back_target, sticker_trim, sticker_safe,
                               band_boxes, end_box, px0, py0, name_rings)
    record['clean'] = clean_parts(out / 'engine' / 'box-art-only.pdf', bare, fc, px0, py0)
    sources = sources_record(sources_given, lid_dir, sticker_dir, lid_relief is not None)
    if sources is not None:
        record['sources'] = sources
    record.update({'schema': schema, 'die': {'record': lm.rel(DIE_RECORD), 'template': spec['input']['template'],
                                             'version': spec['input']['template_version'],
                                             'dimensions_mm': spec['input']['dimensions'],
                                             'flat_mm': [round(coords.cut_polygon.bounds[2], 2), round(coords.cut_polygon.bounds[3], 2)]},
                   'front_picture': pic_rec, 'ground': ground_hex, 'ink': ink_hex, 'gold': gold,
                   'scale': {'front': 1.0, 'back': 1.0, 'why': 'the lid\'s copy and logo and the sticker\'s type fall inside '
                                                             'their panels\' safe areas at 100 %'},
                   'orientation': 'the lid master turned a quarter counter-clockwise, as the shared engine turns a flat box\'s '
                                  'front (graph.quarter_turn): it reads upright with the box lying flat and its top tuck end '
                                  'to the reader\'s right; the back and the long sides turned the same way; the top end\'s '
                                  'mark turned 180°, the bottom end\'s upright (the engine\'s ends)'})
    lm.write_json(out / 'box-fold-check.json', record)
    return record


def a3(out, W, H, coords, px0, py0):
    """box-1to1-A3.pdf: the flat at 100 % on A3 landscape, centred, with crop marks at the die's corners and a fold
    mark at both ends of every crease, outside the bleed; a 100 mm ruler."""
    import fitz
    aw, ah = A3_MM
    ox, oy = (aw - W) / 2, (ah - H) / 2
    page_doc = fitz.open()
    p = page_doc.new_page(width=lm.pt(aw), height=lm.pt(ah))
    with fitz.open(str(out / 'box-artwork.pdf')) as src:
        p.show_pdf_page(fitz.Rect(lm.pt(ox), lm.pt(oy), lm.pt(ox + W), lm.pt(oy + H)), src, 0)
    cx0, cy0, cx1, cy1 = coords.cut_polygon.bounds
    lm.crop_marks(p, (ox + cx0 - px0, oy + cy0 - py0, ox + cx1 - px0, oy + cy1 - py0))
    for x1, y1, x2, y2 in coords.fold_lines:
        if abs(x1 - x2) < 1e-6:                       # a vertical crease: marks above and below the flat
            for y, s in ((cy0, -1), (cy1, 1)):
                X = ox + x1 - px0
                Y = oy + y - py0 + s * (BLEED_MM + 1)
                p.draw_line(fitz.Point(lm.pt(X), lm.pt(Y)), fitz.Point(lm.pt(X), lm.pt(Y + s * 4)), color=(0, 0, 0),
                            width=0.25, dashes='[1 1] 0')
        else:                                         # a horizontal crease: marks left and right of the flat
            for x, s in ((cx0, -1), (cx1, 1)):
                X = ox + x - px0 + s * (BLEED_MM + 1)
                Y = oy + y1 - py0
                p.draw_line(fitz.Point(lm.pt(X), lm.pt(Y)), fitz.Point(lm.pt(X + s * 4), lm.pt(Y)), color=(0, 0, 0),
                            width=0.25, dashes='[1 1] 0')
    support = lm.line_face('descriptor_en')['path']
    lm.label(p, 'Enchanted Rose palette box at 100 % on its die (dad60dbf, 1.4): crop marks at the die\'s corners, '
                'dashed marks at each fold. Print at actual size; the ruler is 100 mm.', 10, ah - 14, support)
    lm._ruler(p, 10, ah - 10)
    page_doc.save(str(out / 'box-1to1-A3.pdf'), garbage=3, deflate=True)
    page_doc.close()


def _inside(box, area):
    return box[0] >= area[0] - 1e-6 and box[1] >= area[1] - 1e-6 and box[2] <= area[2] + 1e-6 and box[3] <= area[3] + 1e-6


def _crosses(box, fold):
    x1, y1, x2, y2 = fold
    if abs(x1 - x2) < 1e-6:
        return box[0] < x1 < box[2] and min(y1, y2) < box[3] and max(y1, y2) > box[1]
    return box[1] < y1 < box[3] and min(x1, x2) < box[2] and max(x1, x2) > box[0]


def fold_check_record(out, coords, fold_record, fc, master, target, back_target, sticker_trim, sticker_safe, band_boxes,
                      end_box, px0, py0, name_rings):
    """Every panel's content inside its safe area, clear of the thumb notch, across no crease; and the die as drawn
    against the engine's own (every cut and crease line within 0.01 mm)."""
    import fitz
    rows = []
    lid = {key: tuple(v) for key, v in ((r['element'], r['ink_box_mm']) for r in master['safe_area'])}
    notch = coords.derived['thumb_notch']
    from shapely.geometry import Point
    # the notch's centre in the lid's own mm (the turn undone: u = Y1 − y, v = x − X0)
    notch_lid = Point(target[3] - notch['y'], notch['cx'] - target[0])
    name_ink = lm.rings_area(name_rings, 24)
    for key, box in lid.items():
        b = turned(box, lm.LID_MM, target)
        d = float(np.hypot(max(b[0] - notch['cx'], 0, notch['cx'] - b[2]), max(b[1] - notch['y'], 0, notch['y'] - b[3])))
        measured = 'its ink box'
        if key == 'name':
            d = float(name_ink.distance(notch_lid))          # the name's own ink: its box's corner is the swash R's
            measured = 'its traced ink'
        rows.append({'panel': 'front', 'element': key, 'box_mm': [round(v, 2) for v in b],
                     'inside_safe': _inside(b, fc['front']['safe']), 'notch_clear_mm': round(d, 2), 'notch_measured': measured,
                     'notch_clear': d >= NOTCH_KEEP_MM, 'crosses_a_crease': any(_crosses(b, f) for f in coords.fold_lines)})
    rows.append({'panel': 'back', 'element': 'the sticker\'s type (its safe area)', 'box_mm': [round(v, 2) for v in sticker_safe],
                 'inside_safe': _inside(sticker_safe, fc['back']['safe']), 'notch_clear': True,
                 'crosses_a_crease': any(_crosses(sticker_safe, f) for f in coords.fold_lines)})
    for side in ('side_left', 'side_right'):
        x0, y0, x1, y1 = fc[side]['box']
        for name, box in band_boxes.items():
            b = turned(box, (y1 - y0, x1 - x0), (x0, y0, x1, y1))
            rows.append({'panel': side, 'element': name, 'box_mm': [round(v, 2) for v in b],
                         'inside_safe': _inside(b, fc[side]['safe']), 'notch_clear': True,
                         'crosses_a_crease': any(_crosses(b, f) for f in coords.fold_lines)})
    for end_name, rot in (('top_end', True), ('bottom_end', False)):
        x0, y0, x1, y1 = fc[end_name]['box']
        ex0, ey0, ex1, ey1 = end_box
        b = (x0 + ex0, y0 + ey0, x0 + ex1, y0 + ey1)
        if rot:
            b = (x1 - ex1, y1 - ey1, x1 - ex0, y1 - ey0)
        rows.append({'panel': end_name, 'element': 'the brand', 'box_mm': [round(v, 2) for v in b],
                     'inside_safe': _inside(b, fc[end_name]['safe']), 'notch_clear': True,
                     'crosses_a_crease': any(_crosses(b, f) for f in coords.fold_lines)})
    # the die as drawn: every cut and crease segment the engine gives, found on page 1 within 0.01 mm
    with fitz.open(str(out / 'box-artwork.pdf')) as d:
        drawn = []
        for dr in d[0].get_drawings():
            for item in dr['items']:
                if item[0] == 'l':
                    a, b = item[1], item[2]
                    drawn.append((a.x * lm.MM_PER_INCH / 72 + px0, a.y * lm.MM_PER_INCH / 72 + py0,
                                  b.x * lm.MM_PER_INCH / 72 + px0, b.y * lm.MM_PER_INCH / 72 + py0))
    want = [tuple(f) for f in coords.fold_lines] + [tuple(s) for s in coords.slit_lines]
    ring = list(coords.cut_polygon.exterior.coords)
    want += [(ring[i][0], ring[i][1], ring[i + 1][0], ring[i + 1][1]) for i in range(len(ring) - 1)]

    def found(seg):
        for e in drawn:
            if (max(abs(seg[0] - e[0]), abs(seg[1] - e[1]), abs(seg[2] - e[2]), abs(seg[3] - e[3])) <= DIE_TOL_MM
                    or max(abs(seg[0] - e[2]), abs(seg[1] - e[3]), abs(seg[2] - e[0]), abs(seg[3] - e[1])) <= DIE_TOL_MM):
                return True
        return False
    missing = [w for w in want if not found(w)]
    return {'fold_check': {'passed': fold_record['passed'], 'failed': fold_record['failed'],
                           'checks': len(fold_record['findings'])},
            'content': rows, 'all_inside_safe': all(r['inside_safe'] for r in rows),
            'nothing_across_a_crease': not any(r['crosses_a_crease'] for r in rows),
            'notch_clear': all(r['notch_clear'] for r in rows),
            'die_untouched': {'segments': len(want), 'missing_or_moved': len(missing), 'tolerance_mm': DIE_TOL_MM,
                              'holds': not missing}}


CLEAN_DPI = 300


def clean_parts(art_pdf, bare, fc, px0, py0):
    """The non-printing parts read for ink on the artwork without its die (300 dpi): each part's ink area (pixels off
    white) beyond 0.6 mm of every printing face — what a cut a hair off would show, not what the 0.5 mm crease band
    and the cut's anti-aliasing leave."""
    import fitz
    from shapely.geometry import box as rect
    from shapely.ops import unary_union
    with fitz.open(str(art_pdf)) as d:
        pix = d[0].get_pixmap(dpi=CLEAN_DPI, alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[..., :3]
    inked = img.min(axis=2) < 245
    k = CLEAN_DPI / lm.MM_PER_INCH
    faces_near = unary_union([rect(*f['box']).buffer(CLEAN_CLEAR_MM, join_style=2) for f in fc.values()])
    rows = []
    for part in lm.parts(bare.difference(faces_near)):
        mask = np.zeros(inked.shape, dtype=np.uint8)
        pts = np.round((np.asarray(part.exterior.coords) - [px0, py0]) * k * 16 - 8).astype(np.int32)
        cv2.fillPoly(mask, [pts], 1, shift=4)
        area = float((inked & mask.astype(bool)).sum()) / k ** 2
        rows.append({'part_mm': [round(v, 2) for v in part.bounds], 'area_mm2': round(float(part.area), 2),
                     'ink_mm2': round(area, 2), 'holds': area < CLEAN_INK_MAX_MM2})
    return {'parts': rows, 'holds': all(r['holds'] for r in rows), 'dpi': CLEAN_DPI,
            'read': 'the four dust flaps, the glue tab and the two tongues, beyond %g mm of every printing face: ink '
                    'under %g mm² each' % (CLEAN_CLEAR_MM, CLEAN_INK_MAX_MM2)}
