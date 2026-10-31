"""Day 11 §2, D-D11-4 — Ẓilāl's box on the brief's die dad60dbf (untouched), composed by the engine from the lid's
assets at $0.

The owner's rule: "front = the lid master; back = the regulated copy on a flat indigo zone inside a floated-stone
border (≥ 7 : 1); long sides = ظلال vertical in rose gold (the lid's traced silhouette and hatch, scaled) with the Arabic
name and the brand; ends = the logo over stones (fallback if cut: flat indigo and the logo, listed); flaps clean (ink ≤
0.5 mm² each); fold check; A3 at 100 %."

The die, its faces, the flaps' cleanliness, the fold check and the A3 page are Day 10's (palette_box), read as they are.
The front is the Ẓilāl lid master (its plate turned a quarter as Day 10's front is, its live type and logo, its foil and
relief plates); the back is Ẓilāl's base sticker (its stone border and flat zone, its copy) turned the same way; the
ground the lid's own indigo. A long side is 14.45 mm deep: inside its 4 mm safe area the hero stands 6.4 mm tall, so the
lid's traced silhouette is scaled to that (its rings, never re-traced) and foiled solid — the lid's hatch scaled with it
would be 0.05 mm, under the press limits (stroke ≥ 0.15 mm, gap ≥ 0.2 mm), so it is left out and listed. The Arabic
name is set as the lid sets it — باليت ظلال العيون, the hero between its two words — with the logo. The ends take the
owner's fallback, flat indigo and the logo, listed.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from apps.pipeline.services import lid_master as lm
from apps.pipeline.services import palette_box as pb
from apps.pipeline.services import palette_sticker as ps
from apps.pipeline.services import zilal_master as zm
from apps.pipeline.services import zilal_object as zo
from apps.pipeline.services import zilal_sticker as zs

OUT = zo.OBJ / 'box'
SCHEMA = 'day11_zilal_box/1'
SURFACE = 'apps/pipeline/services/zilal_box.py::build'
SIDE_HERO_H_MM = 6.4                # the hero's ink height on a long side: 14.45 mm less the 4 mm safe area each side
SIDE_AR_PT = 7.0                    # باليت and العيون beside it, the lid's Arabic face
SIDE_WORD_GAP_MM = 2.5              # the Arabic name's words and the hero, as one name
SIDE_GROUP_GAP_MM = 14.0            # the name and the brand
HATCH_PITCH_MM = 0.395              # the lid's hatch (master.json hero.hatch) …
FOIL_STROKE_MIN_MM = 0.15           # … against the press limits (§8)
FOIL_GAP_MIN_MM = 0.2
CROP_DPI = 300


def hero_rings():
    """The lid's own traced hero (zilal_master.trace_hero on the pick of record): its rings in lid mm, never re-traced."""
    pick = zm.load_master_pick()
    rings, _, proof = zm.trace_hero(pick)
    return rings, proof


def side_band(out, rings, hero_gold, logo_ink, ink_hex, faces, side_len, side_w):
    """One long side's band laid along its length (``side_len`` × ``side_w`` mm, before it is turned): the logo, then the
    Arabic name as the lid sets it — العيون, the hero ظلال (the lid's rings scaled to SIDE_HERO_H_MM, solid rose gold),
    باليت — centred. Emits the print band and the foil band (the hero alone, the foil plate). Returns both paths, the
    elements' boxes (band mm) and the hero's transform."""
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, Document, Group, Path as GPath, SolidFill, TextRun
    geom = lm.rings_area(rings, 24)
    gx0, gy0, gx1, gy1 = geom.bounds
    k = SIDE_HERO_H_MM / (gy1 - gy0)
    hero_w = (gx1 - gx0) * k
    ar = faces['arabic']
    w_b = ps.width_mm('باليت', ar, SIDE_AR_PT)
    w_a = ps.width_mm('العيون', ar, SIDE_AR_PT)
    logo_w = pb.SIDE_LOGO_H_MM / 0.20859051088028435
    total = logo_w + SIDE_GROUP_GAP_MM + w_a + SIDE_WORD_GAP_MM + hero_w + SIDE_WORD_GAP_MM + w_b
    x = (side_len - total) / 2
    cy = side_w / 2
    logo_box = (x, cy - pb.SIDE_LOGO_H_MM / 2, logo_w, pb.SIDE_LOGO_H_MM)
    ax = x + logo_w + SIDE_GROUP_GAP_MM                     # العيون's left
    hx = ax + w_a + SIDE_WORD_GAP_MM                        # the hero's left
    bx = hx + hero_w + SIDE_WORD_GAP_MM                     # باليت's left
    hy = cy - SIDE_HERO_H_MM / 2
    placed = lm.map_rings(rings, lambda p: (hx + (p[0] - gx0) * k, hy + (p[1] - gy0) * k))
    base = cy + SIDE_AR_PT * lm.MM_PER_INCH / 72.0 * 0.32
    hero = GPath(name='ظلال', segments=lm.rings_segments(placed), fill=SolidFill(color=Color.from_hex(hero_gold)),
                 fill_rule='evenodd')
    nodes = lm.logo_parts(logo_box, logo_ink, foil_letters=False) + [
        TextRun(name='side:aleyoun', text='العيون', x=ax + w_a, y=base, font=ar['role'], size_pt=SIDE_AR_PT,
                color=Color.from_hex(ink_hex), align='right', rtl=True),
        Group(name='hero', actual_text='ظلال', children=[hero]),
        TextRun(name='side:baliyt', text='باليت', x=bx + w_b, y=base, font=ar['role'], size_pt=SIDE_AR_PT,
                color=Color.from_hex(ink_hex), align='right', rtl=True)]
    meta = {'typography_surface': SURFACE, 'logical_text/1.0': True}
    band = out / 'engine' / 'side-band.ai'
    emit_pdf_ai(Document(page_w=side_len, page_h=side_w, metadata=meta,
                         root=Group(name='SIDE', children=nodes)), str(band))
    foil = out / 'engine' / 'side-foil.ai'
    emit_pdf_ai(Document(page_w=side_len, page_h=side_w, metadata=meta, root=Group(name='SIDE FOIL', children=[
        hero.model_copy(update={'fill': SolidFill(color=Color.from_hex('#000000'))})])), str(foil))
    boxes = {'logo': (logo_box[0], logo_box[1], logo_box[0] + logo_w, logo_box[1] + pb.SIDE_LOGO_H_MM),
             'name': (ax, hy, bx + w_b, hy + SIDE_HERO_H_MM)}
    back = lm.map_rings(placed, lambda p: (gx0 + (p[0] - hx) / k, gy0 + (p[1] - hy) / k))
    again = lm.rings_area(back, 24)
    iou = again.intersection(geom).area / again.union(geom).area
    transform = {'source': 'zilal_master.trace_hero on the pick of record (refine/pick.json)', 'scale': round(k, 6),
                 'source_box_mm': [round(v, 3) for v in (gx0, gy0, gx1, gy1)],
                 'placed_box_band_mm': [round(hx, 3), round(hy, 3), round(hx + hero_w, 3), round(hy + SIDE_HERO_H_MM, 3)],
                 'rings': len(rings), 'inverse_iou_with_the_source': round(float(iou), 6),
                 'hatch': {'kept': False, 'lid_pitch_mm': HATCH_PITCH_MM, 'scaled_pitch_mm': round(HATCH_PITCH_MM * k, 4),
                           'limits_mm': {'stroke': FOIL_STROKE_MIN_MM, 'gap': FOIL_GAP_MIN_MM},
                           'why': 'the lid\'s hatch scaled to the side\'s 6.4 mm hero would be %.3f mm — under the press '
                                  'limits — so the side\'s hero is foiled solid (listed for the owner)'
                                  % (HATCH_PITCH_MM * k)}}
    return band, foil, boxes, transform


def front_scale(master, panel_w, panel_h):
    """The largest scale of the lid master on the front (centred, the lid turned: its 120 mm across the panel's width,
    its 190 mm along its height) at which every element of the lid's safe area (master.json) stays SAFE_MM inside the
    panel, and never more than the scale that fills the panel's width."""
    lid_w, lid_h = lm.LID_MM
    best = panel_w / lid_h
    for r in master['safe_area']:
        x0, y0, x1, y1 = r['ink_box_mm']
        for d in (x0, lid_w - x1):                    # along the panel's height: the lid's width
            if d < lid_w / 2:                         # only the side the element stands nearer to
                best = min(best, (panel_h / 2 - pb.SAFE_MM) / (lid_w / 2 - d))
        for d in (y0, lid_h - y1):                    # across the panel's width: the lid's height
            if d < lid_h / 2:
                best = min(best, (panel_w / 2 - pb.SAFE_MM) / (lid_h / 2 - d))
    return max(best, 1.0)


def hero_on_the_sides(flat_png, fc, px0, hero_gold):
    """The hero as each long side prints it, read from the flat (300 PPI): the pixels within ΔE00 12 of its rose gold
    inside the side panel, their box (mm, along × across the side) — the two sides the same by measurement."""
    flat = np.asarray(Image.open(flat_png).convert('RGB'))
    k = 300 / lm.MM_PER_INCH
    gold = lm.srgb_to_lab(np.array([[[int(hero_gold[i:i + 2], 16) for i in (1, 3, 5)]]], dtype=np.uint8))[0, 0]
    rows = {}
    for side in ('side_left', 'side_right'):
        x0, y0, x1, y1 = fc[side]['box']
        win = flat[int((y0 - px0) * k):int((y1 - px0) * k), int((x0 - px0) * k):int((x1 - px0) * k)]
        lab = lm.srgb_to_lab(win)
        de = lm.delta_e00(lab.reshape(-1, 3), np.broadcast_to(gold, (lab.shape[0] * lab.shape[1], 3)))
        gold_px = (de.reshape(lab.shape[:2]) < 12.0).astype(np.uint8)
        e = int(round(1.0 * k))                       # away from the creases (the neighbours' 0.5 mm overrun)
        gold_px[:, :e] = 0
        gold_px[:, -e:] = 0
        joined = cv2.morphologyEx(gold_px, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
        count, labels, stats, _ = cv2.connectedComponentsWithStats(joined, connectivity=8)
        big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))      # a letter of the hero: the largest rose-gold part
        centre = stats[big, cv2.CC_STAT_TOP] + stats[big, cv2.CC_STAT_HEIGHT] / 2
        near = [i for i in range(1, count)                          # … and every rose-gold part within 10 mm along it
                if abs(stats[i, cv2.CC_STAT_TOP] + stats[i, cv2.CC_STAT_HEIGHT] / 2 - centre) <= 10.0 * k]
        top = min(stats[i, cv2.CC_STAT_TOP] for i in near)
        bottom = max(stats[i, cv2.CC_STAT_TOP] + stats[i, cv2.CC_STAT_HEIGHT] for i in near)
        left = min(stats[i, cv2.CC_STAT_LEFT] for i in near)
        right = max(stats[i, cv2.CC_STAT_LEFT] + stats[i, cv2.CC_STAT_WIDTH] for i in near)
        rows[side] = {'along_mm': round(float(bottom - top) / k, 2), 'across_mm': round(float(right - left) / k, 2),
                      'parts': len(near), 'pixels': int(sum(stats[i, cv2.CC_STAT_AREA] for i in near))}
    a, b = rows['side_left'], rows['side_right']
    rows['same'] = bool(abs(a['along_mm'] - b['along_mm']) <= 0.2 and abs(a['across_mm'] - b['across_mm']) <= 0.2)
    return rows


def crop(pdf_path, box_page_mm, path, dpi):
    """A window of a PDF's first page (page mm) rendered at ``dpi`` and checked under the eye's limits."""
    import fitz
    with fitz.open(str(pdf_path)) as d:
        rect = fitz.Rect(*(lm.pt(v) for v in box_page_mm))
        pix = d[0].get_pixmap(dpi=dpi, clip=rect, alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3).copy()
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img).save(path, dpi=(dpi, dpi))
    lm._image_block(path)
    return path, img


def build(out_dir, lid_dir=None):
    """The box at $0: box-artwork.pdf (page 1 the artwork on the die, cut and crease on locked layers; page 2 the foil
    plate — the lid's foil on the front, the hero on each long side; page 3 the relief plate — the lid's emboss on the
    front), box-artwork.ai (layers), box-flat.png at 300 PPI, box-1to1-A3.pdf, box-fold-check.json (Day 10's fold check
    and the flaps' ink), the finish proof and sheet, box.json. ``lid_dir``: the lid master it takes its front from
    (Day 11's by default; Day 12's after the reader fix, D-D12-9)."""
    import fitz
    lid = Path(lid_dir) if lid_dir is not None else zm.OUT
    out = Path(out_dir)
    (out / 'engine').mkdir(parents=True, exist_ok=True)
    coords, fold_record, spec = pb.die()
    fc = pb.faces(coords)
    master = json.loads((lid / 'master.json').read_text(encoding='utf-8'))
    sticker = json.loads((zs.OUT / 'sticker.json').read_text(encoding='utf-8'))
    ground_hex = sticker['ground']['flat']['hex']
    ink_hex = master['type']['inks']['eyeshadow']
    logo_ink = master['logo']['ink']
    hero_gold = master['hero']['ink']
    faces = zs.faces()                  # the lid master's faces as the engine resolves them (the sticker's own)
    plate = np.asarray(Image.open(lid / 'engine' / 'plate.png').convert('RGB'))

    fx0, fy0, fx1, fy1 = fc['front']['box']
    cx, cy = (fx0 + fx1) / 2, (fy0 + fy1) / 2
    # [repair 1, the eye's round 0: "stones mirrored into chevrons at the panel edges"] the front panel is 122.45 ×
    # 192.9 mm, the lid 120 × 190: the lid master is scaled up (every part of it together) as far as its elements stay
    # 4 mm inside the panel (``front_scale``), so its own stones reach the creases but for a sliver; the mirror carries
    # that sliver, the crease overrun and the bleed past the top cut (trimmed away)
    scale = front_scale(master, fx1 - fx0, fy1 - fy0)
    target = (cx - scale * lm.LID_MM[1] / 2, cy - scale * lm.LID_MM[0] / 2, cx + scale * lm.LID_MM[1] / 2,
              cy + scale * lm.LID_MM[0] / 2)
    clip = (fx0, fy0 - pb.BLEED_MM, fx1, fy1)
    scaled = cv2.resize(plate, (int(round(plate.shape[1] * scale)), int(round(plate.shape[0] * scale))),
                        interpolation=cv2.INTER_LANCZOS4)
    pic_path, pic_placed, pic_rec = pb.front_picture(out, scaled, target, clip)
    pic_rec['scale'] = round(scale, 6)
    master_scaled = json.loads(json.dumps(master))
    for r_ in master_scaled['safe_area']:
        r_['ink_box_mm'] = [v * scale for v in r_['ink_box_mm']]

    sticker_ai = zs.OUT / 'engine' / 'sticker-engine.ai'
    bx0, by0, bx1, by1 = fc['back']['box']
    bcx, bcy = (bx0 + bx1) / 2, (by0 + by1) / 2
    sw, sh = zs.SIZE_MM[0] + 2 * zs.BLEED_MM, zs.SIZE_MM[1] + 2 * zs.BLEED_MM
    back_target = (bcx - sh / 2, bcy - sw / 2, bcx + sh / 2, bcy + sw / 2)
    sticker_trim = pb.turned((2.0, 2.0, 184.0, 114.0), (sw, sh), back_target)
    sticker_safe = pb.turned((2.0 + 3.5, 2.0 + 3.5, 184.0 - 3.5, 114.0 - 3.5), (sw, sh), back_target)

    rings, hero_proof = hero_rings()
    side_len = fc['side_left']['box'][3] - fc['side_left']['box'][1]
    side_w = fc['side_left']['box'][2] - fc['side_left']['box'][0]
    band_path, band_foil, band_boxes, transform = side_band(out, rings, hero_gold, logo_ink, ink_hex, faces, side_len,
                                                            side_w)
    end_len = fc['top_end']['box'][2] - fc['top_end']['box'][0]
    end_w = fc['top_end']['box'][3] - fc['top_end']['box'][1]
    end_path, end_box = pb.end_logo(out, logo_ink, end_len, end_w)

    px0, py0 = -pb.BLEED_MM, -pb.BLEED_MM
    W = coords.cut_polygon.bounds[2] + 2 * pb.BLEED_MM
    H = coords.cut_polygon.bounds[3] + 2 * pb.BLEED_MM

    def R(box):
        x0, y0, x1, y1 = box
        return fitz.Rect(lm.pt(x0 - px0), lm.pt(y0 - py0), lm.pt(x1 - px0), lm.pt(y1 - py0))

    def rgb(h):
        return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))

    lid_type, lid_logo, lid_foil, lid_relief = (fitz.open(str(lid / 'engine' / ('layer-%s.ai' % k)))
                                                for k in ('type', 'logo', 'foil', 'relief'))
    sticker_doc = fitz.open(str(sticker_ai))
    band = fitz.open(str(band_path))
    band_f = fitz.open(str(band_foil))
    end = fitz.open(str(end_path))
    bare = pb.non_printing(coords)
    grounds = {name: pb.ground_shape(fc[name], bare) for name in ('back', 'side_left', 'side_right', 'top_end',
                                                                   'bottom_end')}

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
        page.show_pdf_page(R(back_target), sticker_doc, 0, rotate=90, oc=oc)
        for name in ('side_left', 'side_right'):
            page.show_pdf_page(R(fc[name]['box']), band, 0, rotate=90, oc=oc)
        page.show_pdf_page(R(fc['top_end']['box']), end, 0, rotate=180, oc=oc)
        page.show_pdf_page(R(fc['bottom_end']['box']), end, 0, oc=oc)

    def foil_plate(page, oc):
        page.show_pdf_page(R(target), lid_foil, 0, rotate=90, oc=oc)
        for name in ('side_left', 'side_right'):
            page.show_pdf_page(R(fc[name]['box']), band_f, 0, rotate=90, oc=oc)

    def die_lines(page, oc_cut, oc_crease):
        poly = coords.cut_polygon
        for ring in [poly.exterior] + list(poly.interiors):
            page.draw_polyline([fitz.Point(lm.pt(x - px0), lm.pt(y - py0)) for x, y in ring.coords],
                               color=(0.85, 0, 0.55), width=0.5, oc=oc_cut)
        for x1, y1, x2, y2 in coords.slit_lines:
            page.draw_line(fitz.Point(lm.pt(x1 - px0), lm.pt(y1 - py0)), fitz.Point(lm.pt(x2 - px0), lm.pt(y2 - py0)),
                           color=(0.85, 0, 0.55), width=0.5, oc=oc_cut)
        for x1, y1, x2, y2 in coords.fold_lines:
            page.draw_line(fitz.Point(lm.pt(x1 - px0), lm.pt(y1 - py0)), fitz.Point(lm.pt(x2 - px0), lm.pt(y2 - py0)),
                           color=(0, 0.6, 0.9), width=0.4, dashes='[3 1.6] 0', oc=oc_crease)

    pdf = fitz.open()
    layers = {name: pdf.add_ocg(name, on=True) for name in ('artwork', 'cut', 'crease')}
    p = pdf.new_page(width=lm.pt(W), height=lm.pt(H))
    artwork(p, layers['artwork'])
    die_lines(p, layers['cut'], layers['crease'])
    p = pdf.new_page(width=lm.pt(W), height=lm.pt(H))
    foil_plate(p, 0)
    p = pdf.new_page(width=lm.pt(W), height=lm.pt(H))
    p.show_pdf_page(R(target), lid_relief, 0, rotate=90)
    pdf.set_layer(-1, locked=[layers['cut'], layers['crease']])
    pdf.set_page_labels([{'startpage': 0, 'prefix': '1 artwork on the die ', 'style': ''},
                         {'startpage': 1, 'prefix': '2 foil plate (rose gold: the front, the long sides\' hero) ',
                          'style': ''},
                         {'startpage': 2, 'prefix': '3 relief plate (the front: ظلال embossed) ', 'style': ''}])
    for page in pdf:
        page.set_bleedbox(page.rect)
        page.set_trimbox(R(coords.cut_polygon.bounds))
    pdf.set_metadata({'title': 'Ẓilāl palette box on die dad60dbf', 'creator': SURFACE})
    lm.tag_srgb(pdf)
    pdf.save(str(out / 'box-artwork.pdf'), garbage=3, deflate=True)
    pdf.close()

    ai = fitz.open()
    layers = {name: ai.add_ocg(name, on=name not in ('foil', 'relief'))
              for name in ('artwork', 'foil', 'relief', 'cut', 'crease')}
    p = ai.new_page(width=lm.pt(W), height=lm.pt(H))
    artwork(p, layers['artwork'])
    foil_plate(p, layers['foil'])
    p.show_pdf_page(R(target), lid_relief, 0, rotate=90, oc=layers['relief'])
    die_lines(p, layers['cut'], layers['crease'])
    ai.set_layer(-1, locked=[layers['cut'], layers['crease']])
    p.set_bleedbox(p.rect)
    p.set_trimbox(R(coords.cut_polygon.bounds))
    ai.set_metadata({'title': 'Ẓilāl palette box (layers)', 'creator': SURFACE})
    lm.tag_srgb(ai)
    ai.save(str(out / 'box-artwork.ai'), garbage=3, deflate=True)
    ai.close()
    art_only = fitz.open()
    p = art_only.new_page(width=lm.pt(W), height=lm.pt(H))
    artwork(p, 0)
    art_only.save(str(out / 'engine' / 'box-art-only.pdf'), garbage=3, deflate=True)
    art_only.close()
    for d in (lid_type, lid_logo, lid_foil, lid_relief, sticker_doc, band, band_f, end):
        d.close()
    with fitz.open(str(out / 'box-artwork.pdf')) as d:
        pix = d[0].get_pixmap(dpi=300, alpha=False)
        pix.set_dpi(300, 300)
        pix.save(str(out / 'box-flat.png'))
    pb.a3(out, W, H, coords, px0, py0)
    name_rings, _, _ = zm.trace_name(zm.load_master_pick())
    name_rings = lm.map_rings(name_rings, lambda p_: (p_[0] * scale, p_[1] * scale))
    fold = pb.fold_check_record(out, coords, fold_record, fc, master_scaled, target, back_target, sticker_trim,
                                sticker_safe, band_boxes, end_box, px0, py0, name_rings)
    fold['clean'] = pb.clean_parts(out / 'engine' / 'box-art-only.pdf', bare, fc, px0, py0)
    lm.write_json(out / 'box-fold-check.json', fold)

    # the finish proof: the flat with the lid's own finish proof on the front (turned as the front is), the sides'
    # hero drawn in the foil's rose gold as printed
    flat = Image.open(out / 'box-flat.png').convert('RGB')
    k300 = 300 / lm.MM_PER_INCH
    proof_front = Image.open(lid / 'finish-proof.png').convert('RGB').rotate(90, expand=True)
    sides_measured = hero_on_the_sides(out / 'box-flat.png', fc, px0, hero_gold)
    box_px = [int(round((v - px0) * k300)) for v in target]          # px0 = py0: the flat's 3 mm bleed
    flat.paste(proof_front.resize((box_px[2] - box_px[0], box_px[3] - box_px[1]), Image.LANCZOS), (box_px[0], box_px[1]))
    flat.save(out / 'finish-proof.png')
    plates = [{'plate': 'print', 'what': 'process colour on the board: the lid master\'s plate and live type on the front, '
                                         'the base sticker on the back, the long sides\' Arabic name and logo, the ends\' '
                                         'logo, the lid\'s indigo %s as the ground' % ground_hex},
              {'plate': 'foil (rose gold)', 'what': 'the front: ظلال\'s rim and hatch and "Enchanted Rose", as the lid; '
                                                    'the long sides: ظلال solid (its hatch below the press limits at 6.4 mm)'},
              {'plate': 'relief (emboss)', 'what': 'the front: ظلال\'s silhouette, as the lid'},
              {'plate': 'cut and crease', 'what': 'the die dad60dbf as recorded (template 1.4), untouched'}]
    zo.finish_sheet('the box', out / 'box-flat.png', plates, out)

    record = {'schema': SCHEMA, 'surface': SURFACE,
              'rule': 'D-D11-4: front = the lid master; back = the regulated copy on a flat indigo zone inside a '
                      'floated-stone border (≥ 7 : 1); long sides = ظلال vertical in rose gold with the Arabic name and the '
                      'brand; ends = the logo over stones (fallback: flat indigo and the logo, listed); flaps clean (ink ≤ '
                      '0.5 mm² each); fold check; A3 at 100 %',
              'die': {'record': lm.rel(pb.DIE_RECORD), 'sha256': lm.sha256(pb.DIE_RECORD),
                      'template': spec['input']['template'], 'version': spec['input']['template_version'],
                      'dimensions_mm': spec['input']['dimensions']},
              'front': {'lid': lm.rel(lid), 'picture': pic_rec, 'layers': ['type', 'logo', 'foil', 'relief'],
                        'scale': round(scale, 6),
                        'said': 'the lid master scaled ×%.4f to the front panel\'s width (repair 1: no mirrored stones '
                                'inside the creases); its type and logo, foil and relief scaled with it' % scale},
              'back': {'sticker': lm.rel(sticker_ai), 'sha256': lm.sha256(sticker_ai),
                       'contrast': sticker['contrast']['per_ink'], 'contrast_min': zs.CONTRAST_MIN,
                       'holds': all(v['worst_ratio'] >= zs.CONTRAST_MIN for v in sticker['contrast']['per_ink'].values()),
                       'said': 'the base sticker\'s artwork placed at 100 %, turned as the front: its flat zone and '
                               'stone border are the back\'s (D-D11-4)'},
              'sides': {'boxes_band_mm': {k_: [round(v, 3) for v in b] for k_, b in band_boxes.items()},
                        'hero_measured_on_the_flat': sides_measured,
                        'hero': transform, 'hero_trace': {k_: hero_proof[k_] for k_ in hero_proof
                                                          if not isinstance(hero_proof[k_], (list, dict))},
                        'arabic_name': 'باليت ظلال العيون — the lid\'s own words, the hero between them'},
              'ends': {'fallback': True, 'said': 'flat indigo and the logo (the owner\'s fallback for the ends, listed): '
                                                 'the ends\' 14.45 mm hold no stone crop that reads as the lid\'s'},
              'ground': ground_hex, 'ink': ink_hex, 'logo_ink': logo_ink, 'hero_gold': hero_gold,
              'fold_check': {k_: fold[k_] for k_ in fold if k_ not in ('clean',)},
              'clean': fold['clean'],
              'finish': {'proof': lm.rel(out / 'finish-proof.png'), 'sheet': lm.rel(out / 'finish-sheet.png'),
                         'plates': plates},
              'files': {n: lm.rel(out / n) for n in ('box-artwork.pdf', 'box-artwork.ai', 'box-flat.png',
                                                      'box-1to1-A3.pdf', 'box-fold-check.json', 'finish-proof.png',
                                                      'finish-sheet.pdf')}}
    lm.write_json(out / 'box.json', record)
    return record


def box_look(record, call, round_no, label=None):
    """The box's eye round (D-D11-4): the lid master first (the language), the box's flat fitted, then 1 : 1 crops
    rendered from the artwork — the front's top corner, a long side's name, the back's copy and border, an end, the
    fold between the front and a side."""
    out = OUT
    pdf = zm.REPO / record['files']['box-artwork.pdf']
    fc = pb.faces(pb.die()[0])
    b = pb.BLEED_MM
    sx0, sy0, sx1, sy1 = fc['side_right']['box']
    bx0, by0, bx1, by1 = fc['back']['box']
    fx0, fy0, fx1, fy1 = fc['front']['box']
    ex0, ey0, ex1, ey1 = fc['bottom_end']['box']
    mid = (sy0 + sy1) / 2
    windows = {
        'front-top': ((fx0 + b, fy0 - 2 + b, fx0 + 60 + b, fy0 + 45 + b), 'the front\'s top end: the lid master, turned '
                                                                         'as the box lies flat'),
        'side-name': ((sx0 - 4 + b, mid - 45 + b, sx1 + 4 + b, mid + 45 + b), 'a long side (14.45 mm deep): the logo '
                                                                              'and باليت ظلال العيون, the hero foiled'),
        'back-copy': ((bx0 + 5 + b, by0 + 60 + b, bx1 - 5 + b, by0 + 120 + b), 'the back: the base sticker\'s copy on '
                                                                               'its flat zone'),
        'back-border': ((bx0 + b - 2, by0 + b - 2, bx0 + 50 + b, by0 + 50 + b), 'the back\'s corner: the stone border '
                                                                                 'and the zone\'s edge'),
        'end': ((ex0 + b, ey0 + b - 2, ex1 + b, ey1 + b + 2), 'the bottom end: flat indigo and the logo (the fallback)'),
        'fold': ((fx1 - 20 + b, mid - 30 + b, sx1 + b + 2, mid + 30 + b), 'the front meeting the right long side at '
                                                                          'their crease'),
    }
    images = [zo.lid_language(out), (zo.fitted(zm.REPO / record['files']['box-flat.png'], out / 'crops' / 'flat.png'),
                                     'THE BOX\'s flat on its die (fitted)')]
    for name, (box, words) in windows.items():
        path, _ = crop(pdf, box, out / 'crops' / ('box-%s.png' % name), CROP_DPI)
        images.append((path, words + ' (1 : 1, %d PPI)' % CROP_DPI))
    hero = record['sides']['hero']
    text = ('THE BOX GATE (Day 11, D-D11-4). The palette\'s box on the brief\'s die (untouched), composed by our engine '
            'from the lid\'s assets. THE OWNER\'S RULE: "%s". The lid\'s idea: %s. Images: %s.\n\nALLOWED (the '
            'composition): the front is the lid master turned a quarter (the box lies flat, its top tuck end to the '
            'right); the back is the base sticker (its stone border and flat zone, its copy) at 100 %%, turned the same '
            'way, on the lid\'s indigo; each long side is 14.45 mm deep, so ظلال stands %.1f mm tall there — the lid\'s '
            'own traced silhouette scaled (×%.4f), foiled SOLID in rose gold: the lid\'s hatch scaled with it would be '
            '%.3f mm, under the press limits, so it is left out (listed for the owner) — between باليت and العيون as on '
            'the lid, with the logo; the ends take the owner\'s fallback, flat indigo and the logo (listed); the flaps '
            'carry no ink. ANYTHING ELSE is a defect: a stone redrawn or stretched; type crossing a crease or near a cut; '
            'a seam or a white line at a fold; anything off the lid\'s language. As a senior packaging designer, judge '
            'every image — do the back and the sides read as considered as the front? — and list every defect with its '
            'place, severity and the smallest repair. Answer in JSON.' % (
                record['rule'], zo.IDEA, '; '.join('%d %s' % (i + 1, w_) for i, (_, w_) in enumerate(images)),
                SIDE_HERO_H_MM, hero['scale'], hero['hatch']['scaled_pitch_mm']))
    if round_no >= 1:
        m = record['sides']['hero_measured_on_the_flat']
        text += ('\n\nREPAIR 1 (after round 0 named five defects): (1) the mirrored stones at the front\'s edges — the '
                 'front panel is 122.45 × 192.9 mm and the lid 120 × 190: the lid master is now scaled ×%.4f to the '
                 'panel as far as every element stays 4 mm inside it, so its own stones reach the creases but for a '
                 'sliver of %.2f mm a side, carried with the crease overrun and the bleed past the top cut by the mirror; '
                 '(2) the two long sides\' ظلال — both sides draw the SAME band file, the hero placed at %.2f × %.2f mm '
                 '(the lid\'s traced silhouette ×%.4f), and read on the flat both sides\' rose gold measures alike '
                 '(%.2f / %.2f mm along): the same; (3) the back\'s top-left corner — that corner is the base sticker\'s calm corner, '
                 'as the lid\'s top-right is calm (the lid\'s two drifts); its faint dark blotches are where the lid\'s '
                 'logo was cleaned out of the lid\'s plate (listed for the owner, not changed: the sticker\'s own gate '
                 'is closed); (4) the bottom end\'s indigo — the ground runs 0.5 mm past a crease by the die\'s rule (no '
                 'white line at the fold), and every flap reads %s mm² of ink at most past its 0.6 mm crease band '
                 '(the owner\'s limit 0.5 mm²); (5) the empty frame on the back is the EAN-13\'s place, held empty: no '
                 'number is invented (listed). Judge whether each is answered and whether anything new is wrong.' % (
                     record['front']['scale'], (122.45 - 120.0 * record['front']['scale']) / 2,
                     hero['placed_box_band_mm'][2] - hero['placed_box_band_mm'][0],
                     hero['placed_box_band_mm'][3] - hero['placed_box_band_mm'][1], hero['scale'],
                     m['side_left']['along_mm'], m['side_right']['along_mm'],
                     max(p_['ink_mm2'] for p_ in record['clean']['parts'])))
    return zo.surface_look(out, 'box', images, text, call, round_no, label)


def _side_by_side(a, b, path):
    """Two crops at one scale side by side (a white gap), saved and checked under the eye's limits."""
    h = max(a.shape[0], b.shape[0])
    pad = lambda x: np.concatenate([x, np.full((h - x.shape[0], x.shape[1], 3), 255, np.uint8)], 0)
    img = np.concatenate([pad(a), np.full((h, 16, 3), 255, np.uint8), pad(b)], 1)
    Image.fromarray(img).save(path, dpi=(CROP_DPI, CROP_DPI))
    lm._image_block(path)
    return path


def box_relook(record, call, findings):
    """The box's re-look on corrected evidence (as the lid's and the tray's): the hero as image 4 and image 8 of round
    1's look showed it, framed alike side by side, with its parts measured in both; and the back's top-left corner as the
    PDF renders it beside the same window of the flat."""
    out = OUT
    gold = lm.srgb_to_lab(np.array([[[int(record['hero_gold'][i:i + 2], 16) for i in (1, 3, 5)]]], dtype=np.uint8))[0, 0]
    crops, spans = [], {}
    for name in ('side-name', 'fold'):
        im = np.asarray(Image.open(out / 'crops' / ('box-%s.png' % name)).convert('RGB'))
        lab = lm.srgb_to_lab(im)
        de = lm.delta_e00(lab.reshape(-1, 3), np.broadcast_to(gold, (lab.shape[0] * lab.shape[1], 3)))
        ys, xs = np.nonzero(de.reshape(lab.shape[:2]) < 15.0)
        keep = (xs > 20) & (xs < im.shape[1] - 20) if name == 'fold' else np.ones(len(xs), dtype=bool)
        cy = int(np.median(ys[keep]))
        near = keep & (np.abs(ys - cy) < 120)
        y0, y1, x0, x1 = ys[near].min(), ys[near].max() + 1, xs[near].min(), xs[near].max() + 1
        spans[name] = {'along_px': int(y1 - y0), 'across_px': int(x1 - x0),
                       'along_mm': round((y1 - y0) / (CROP_DPI / lm.MM_PER_INCH), 2),
                       'across_mm': round((x1 - x0) / (CROP_DPI / lm.MM_PER_INCH), 2)}
        crops.append(im[max(y0 - 30, 0):y1 + 30, max(x0 - 30, 0):x1 + 30])
    hero_pair = _side_by_side(crops[0], crops[1], out / 'crops' / 'relook-hero-image4-vs-image8.png')
    pdf_corner = np.asarray(Image.open(out / 'crops' / 'box-back-border.png').convert('RGB'))
    fc = pb.faces(pb.die()[0])
    b = pb.BLEED_MM
    bx0, by0, _, _ = fc['back']['box']
    k = CROP_DPI / lm.MM_PER_INCH
    flat = Image.open(zm.REPO / record['files']['box-flat.png']).convert('RGB')
    win = tuple(int(round(v * k)) for v in (bx0 + b - 2, by0 + b - 2, bx0 + 50 + b, by0 + 50 + b))
    flat_corner = np.asarray(flat.crop(win).resize((pdf_corner.shape[1], pdf_corner.shape[0]), Image.LANCZOS))
    same = float(lm.delta_e00(lm.srgb_to_lab(pdf_corner).reshape(-1, 3), lm.srgb_to_lab(flat_corner).reshape(-1, 3)).mean())
    corner_pair = _side_by_side(pdf_corner, flat_corner, out / 'crops' / 'relook-back-corner-pdf-vs-flat.png')
    images = [zo.lid_language(out),
              (hero_pair, 'the hero ظلال as image 4 (left) and image 8 (right) of the last look showed it, framed alike, '
                          'one scale (300 PPI)'),
              (corner_pair, 'the back\'s top-left corner as image 6 showed it (left: rendered from the PDF) beside the '
                            'same window of the box\'s flat (right)')]
    text = ('THE BOX GATE, A RE-LOOK ON CORRECTED EVIDENCE (Day 11, D-D11-4). The last look named two proof defects: %s. '
            'Measured: in image 4 and in image 8 the hero\'s rose gold spans %d × %d px and %d × %d px (%.2f × %.2f mm and '
            '%.2f × %.2f mm along × across at 300 PPI) — the same hero, both sides drawing the one band file; image 6 is '
            'the back exactly as the flat prints it (the PDF\'s render against the flat\'s same window: mean ΔE00 %.2f) — '
            'the whole back, the sticker included, is turned a quarter as the front is, so in a 50 mm corner window the '
            'turned copy\'s lines read across the crop. Images: %s. Judge these two points only: are the two heroes the '
            'same size, and is the corner the composed back? List a defect only if you see one here. Answer in JSON.' % (
                '; '.join(findings), spans['side-name']['along_px'], spans['side-name']['across_px'],
                spans['fold']['along_px'], spans['fold']['across_px'], spans['side-name']['along_mm'],
                spans['side-name']['across_mm'], spans['fold']['along_mm'], spans['fold']['across_mm'], same,
                '; '.join('%d %s' % (i + 1, w_) for i, (_, w_) in enumerate(images))))
    rec = zo.surface_look(out, 'box', images, text, call, 1, label='relook-evidence')
    rec['evidence'] = {'hero_spans': spans, 'corner_mean_de00': round(same, 3)}
    lm.write_json(out / 'eye-relook-evidence.json', rec)
    return rec


def gate_record(evidence):
    """The box's gate as the eye's rounds say it, merged into box.json under 'gate': every round (round 1 returned no
    verdict at its output limit; its retry is the verdict), what stays open, and the lead's measured counter-evidence
    where the eye and a measurement disagree (``evidence``). Never changes the artwork."""
    rounds = []
    for name in ('eye-r0.json', 'eye-r1.json', 'eye-r1-retry.json'):
        path = OUT / name
        if not path.exists():
            continue
        rec = json.loads(path.read_text(encoding='utf-8'))
        rounds.append({'file': lm.rel(path), 'round': rec['round'], 'label': rec['label'], 'answered': rec['answered'],
                       'holds': rec['holds'], 'cost_usd': rec['look']['cost_usd'],
                       'stop_reason': rec['look']['stop_reason'],
                       'defects': [{k: d[k] for k in ('where', 'what', 'severity')} for d in rec['defects']]})
    record = json.loads((OUT / 'box.json').read_text(encoding='utf-8'))
    last = rounds[-1]
    record['gate'] = {'rounds': rounds, 'holds': last['holds'], 'open': last['defects'], 'repairs': 1,
                      'counter_evidence': evidence,
                      'rule': 'D-D11-4: the eye as the gate, repair ≤ 1; D-D11-10: no third round — a round that returned '
                              'no verdict was asked once more; no further paid look on measured misreadings'}
    lm.write_json(OUT / 'box.json', record)
    return record['gate']
