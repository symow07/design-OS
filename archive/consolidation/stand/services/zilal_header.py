"""Day 12 §2 (D-D12-2) — the display's header master by the preservation path. The pick (J1's first, or the owner's
PICK) sets the placement of the hero, the name, the logo and the stone band only: its painted lettering is cleaned from
the plate, and ظلال and "Enchanted Rose" are the LID's own — the lid's traced silhouette with its painted pixels
beneath, its registered hatch foil and its relief, and its traced logotype with its foil — scaled onto the sketch's
boxes, never re-traced (proved by mapping each back onto its source: IoU 1); the approved logo in the lid's ink. The
plate is the framed sketch upscaled 2× (Lanczos), its PPI recorded (lower than the lid's: reported, not a stop)."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from shapely import affinity

from apps.pipeline.services import lid_master as lm
from apps.pipeline.services import zilal_display as zd
from apps.pipeline.services import zilal_lipstick_master as zlm
from apps.pipeline.services import zilal_master as zm

SURFACE = 'apps/pipeline/services/zilal_header.py::build'
OUT = zd.HEADER / 'master'
LOGO_ASPECT = 0.20859051088028435               # the approved logo's height over width (palette_box, lid_master)
GROUP_JOIN_MM = 2.5                             # the sketch's letters joined into words across gaps under 2.5 mm
HERO_HEIGHT_SHARE = 0.5                         # the hero: every word at least half as tall as the tallest (ظلال's
                                                # letters stand apart; the name and the logo are short lines)
CLEAN_GROW_MM = 1.5                             # a painted word cleaned by its box grown 1.5 mm (bevel, shadow)
CARRY_MM = 0.35                                 # the lid's hero raster carried with its bevel's near shadow …
FEATHER_MM = 0.25                               # … feathered into the cleaned ground
PICK_FILE = zd.SKETCHES / 'PICK'
SPECK_ZONE_MM = 4.0                             # [repair 1] the specks read within 4 mm of a cleaned word …
SPECK_DE = 10.0                                 # … off the ground by ΔE00 over 10 …
SPECK_MAX_MM2 = 1.5                             # … and under 1.5 mm² (a stone is larger, and kept)
STONE_BLOB_MM = 0.6                             # … touching no stone blob (what survives a 0.6 mm opening)


def the_pick():
    """The header's pick: the owner's PICK file (one line, S1–S3) if he wrote one in the 20 minutes, else J1's first."""
    ranking = json.loads((zd.SKETCHES / 'ranking-map.json').read_text(encoding='utf-8'))
    if PICK_FILE.exists():
        name = PICK_FILE.read_text(encoding='utf-8').strip().upper()
        if name not in ['S%d' % n for n in range(1, zd.COUNT + 1)]:
            raise ValueError('the PICK file names %r, not a sketch of the round' % name)
        return name, 'the owner\'s PICK file'
    first = min(ranking['order'], key=lambda r: r['rank'])
    return first['sketch'], 'J1\'s first, by default (no PICK file or word from the owner in the 20 minutes)'


def gold_words(rgb, k):
    """The sketch's rose-gold lettering as words: its rose-gold parts on open indigo (``zilal_display.lettering_box``'s
    reading), joined across gaps under 2.5 mm; each word its mask (whole picture), ink box (px) and area, largest first;
    and the hero: every word at least half as tall as the tallest, together (None when no word is read)."""
    lab = lm.srgb_to_lab(rgb)
    light, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    chroma = np.hypot(a, b)
    hue = np.degrees(np.arctan2(b, a)) % 360
    gold = ((hue >= zd.LETTER_HUE[0]) & (hue <= zd.LETTER_HUE[1]) & (chroma >= zd.LETTER_C_MIN) & (light >= zd.LETTER_L_MIN))
    gold = cv2.morphologyEx(gold.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((zd.LETTER_CLOSE_PX,) * 2, np.uint8))
    gold = cv2.morphologyEx(gold, cv2.MORPH_OPEN, np.ones((zd.LETTER_OPEN_PX,) * 2, np.uint8))
    ground = (light < zd.GROUND_L_MAX) & (b < zd.GROUND_B_MAX)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(gold, 8)
    letters = np.zeros(gold.shape, dtype=bool)
    for i in range(1, n):
        if stats[i, 4] < zd.LETTER_PART_MIN_PX:
            continue
        part = labels == i
        ring = cv2.dilate(part.astype(np.uint8), np.ones((zd.LETTER_RING_PX,) * 2, np.uint8)).astype(bool) & (gold == 0)
        if ground[ring].mean() >= zd.LETTER_RING_GROUND:
            letters |= part
    join = zlm.odd_px(GROUP_JOIN_MM, k)
    joined = cv2.dilate(letters.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (join, join)))
    m, wl, ws, _ = cv2.connectedComponentsWithStats(joined, 8)
    words = []
    for i in range(1, m):
        mask = (wl == i) & letters
        if not mask.any():
            continue
        ys, xs = np.nonzero(mask)
        words.append({'mask': mask, 'box_px': [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1],
                      'area_px': int(mask.sum())})
    words.sort(key=lambda w: -w['area_px'])
    if not words:
        return [], None
    height = lambda w: w['box_px'][3] - w['box_px'][1]
    tallest = max(height(w) for w in words)
    tall = [w for w in words if height(w) >= HERO_HEIGHT_SHARE * tallest]
    hero_mask = np.zeros(rgb.shape[:2], dtype=bool)
    for w in tall:
        hero_mask |= w['mask']
    ys, xs = np.nonzero(hero_mask)
    hero = {'mask': hero_mask, 'box_px': [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1],
            'area_px': int(hero_mask.sum()), 'words': len(tall), 'tallest_px': int(tallest)}
    return words, hero


def word_groups(rgb, k):
    """The sketch's lettering read as the hero (``gold_words``), the name and the logo: the short words joined into
    lines, the two largest lines the name and the logo (told apart by ``name_likeness`` in ``build``)."""
    words, hero = gold_words(rgb, k)
    if hero is None:
        raise ValueError('no rose-gold lettering is read in the sketch')
    height = lambda w: w['box_px'][3] - w['box_px'][1]
    tall = [w for w in words if height(w) >= HERO_HEIGHT_SHARE * hero['tallest_px']]
    rest = sorted([w for w in words if height(w) < HERO_HEIGHT_SHARE * hero['tallest_px']], key=lambda w: -w['area_px'])
    if len(rest) < 2:
        raise ValueError('the sketch\'s lettering reads as %d tall and %d short words, not the hero, the name and the '
                         'logo' % (len(tall), len(rest)))
    rest = merge_lines(rest, k)
    if len(rest) < 2:
        raise ValueError('the sketch\'s short lettering reads as %d line(s), not the name and the logo' % len(rest))
    return {'hero': hero, 'short': rest[:2], 'others': rest[2:]}


LINE_OVERLAP = 0.5                               # two short words are one line when their heights overlap by half
LINE_GAP_MM = 15.0                               # the shorter's height and stand under 15 mm apart


def merge_lines(words, k):
    """The short words joined into lines (the name's two words, the logo's split letters): a word joins a line whose
    height it overlaps by half the shorter's and which it stands within 15 mm of. Largest line first."""
    lines = []
    for w in sorted(words, key=lambda w: w['box_px'][0]):
        x0, y0, x1, y1 = w['box_px']
        for line in lines:
            lx0, ly0, lx1, ly1 = line['box_px']
            overlap = min(y1, ly1) - max(y0, ly0)
            gap = max(x0 - lx1, lx0 - x1, 0)
            if overlap >= LINE_OVERLAP * min(y1 - y0, ly1 - ly0) and gap <= LINE_GAP_MM * k:
                line['mask'] = line['mask'] | w['mask']
                line['box_px'] = [min(x0, lx0), min(y0, ly0), max(x1, lx1), max(y1, ly1)]
                line['area_px'] += w['area_px']
                break
        else:
            lines.append({'mask': w['mask'].copy(), 'box_px': list(w['box_px']), 'area_px': w['area_px']})
    return sorted(lines, key=lambda line: -line['area_px'])


def name_likeness(word, name_geom, k):
    """How much a short word looks like the lid's own name: the IoU of its painted letters (in its box) with the lid's
    traced "Enchanted Rose" scaled to the box's width and centred on it. (The name and the logo stand in nearly the
    same proportion — 4.87 and 4.79 — so their shape, not their box, tells them apart.)"""
    x0, y0, x1, y1 = word['box_px']
    s, dx, dy = fit_to(name_geom.bounds, (x0 / k, y0 / k, x1 / k, y1 / k))
    placed = affinity.affine_transform(name_geom, [s, 0, 0, s, dx, dy])
    fill = lm.raster_fill(placed, word['mask'].shape, (0.0, 0.0), k)
    mine = word['mask']
    return float((fill & mine).sum() / max((fill | mine).sum(), 1))


def lid_assets():
    """The lid's own hero and logotype, from the lid's pick of record and its Day 12 master (D-D12-9's reader): the
    hero's rings, letters, registered foil and relief (``hero_foil_registered`` at the master's recorded fit and
    stroke — its foil area checked against the master's record), the name's rings and foil, the inks; and the lid's
    upscaled pick (the hero's painted pixels)."""
    pick = zm.load_master_pick()
    master = json.loads((zd.LID12 / 'master.json').read_text(encoding='utf-8'))
    rings, _, proof = zm.trace_hero(pick)
    letters = zm.letters_geometry(rings)
    fit, stroke = master['hero']['hatch']['fit'], master['hero']['hatch']['stroke']
    hero = zm.hero_foil_registered(pick, letters, fit, stroke)
    if abs(float(hero['foil'].area) - master['hero']['foil_mm2']) > 0.01:
        raise ValueError('the hero\'s foil recomputed (%.2f mm²) is not the master\'s (%.2f mm²)'
                         % (hero['foil'].area, master['hero']['foil_mm2']))
    name_rings, _, _ = zm.trace_name(pick)
    name_foil, _ = zm.name_foil(name_rings)
    return {'pick': pick, 'pick_sha256': lm.sha256(zm.MASTER_PICK), 'master': master, 'rings': rings, 'letters': letters,
            'foil': hero['foil'], 'relief': hero['relief'], 'name_rings': name_rings, 'name_foil': name_foil,
            'up': lm.upscale(pick), 'k_up': lm.PX_PER_MM_SRC * lm.UP}


def fit_to(src_box, dst_box):
    """One scale (the destination's width over the source's) and the move that centres the source on the destination
    (mm): (s, dx, dy) for p → (s·x + dx, s·y + dy)."""
    sx0, sy0, sx1, sy1 = src_box
    dx0, dy0, dx1, dy1 = dst_box
    s = (dx1 - dx0) / (sx1 - sx0)
    return s, (dx0 + dx1) / 2.0 - s * (sx0 + sx1) / 2.0, (dy0 + dy1) / 2.0 - s * (sy0 + sy1) / 2.0


def inverse_iou(placed_geom, source_geom, s, dx, dy):
    back = affinity.affine_transform(placed_geom, [1 / s, 0, 0, 1 / s, -dx / s, -dy / s])
    return round(float(back.intersection(source_geom).area / back.union(source_geom).area), 6)


def build(out_dir=OUT):
    """The header master at $0 (see the module's text). Writes header-master.pdf (page 1 the artwork with its 3 mm
    bleed, its trim box the header; page 2 the foil plate; page 3 the relief plate), header-flat.png (300 PPI),
    finish-proof.png, engine/, header.json."""
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, Document, Finish, Group, Image as GImage, Path as GPath, SolidFill
    from apps.pipeline.services import finish_proof as fp
    out = Path(out_dir)
    (out / 'engine').mkdir(parents=True, exist_ok=True)
    name, why = the_pick()
    dest = zd.SKETCHES / name
    crop_rec = json.loads((dest / 'crop.json').read_text(encoding='utf-8'))
    if not crop_rec['qualifies']:
        raise ValueError('%s does not qualify: %s' % (name, crop_rec['why']))
    facts = zd.header_facts()
    rgb = np.asarray(Image.open(dest / 'header.png').convert('RGB'))
    k = rgb.shape[1] / facts['w_mm']
    words = word_groups(rgb, k)
    lid = lid_assets()
    master = lid['master']
    name_geom = lm.rings_area(lid['name_rings'], 24)
    likeness = [round(name_likeness(w, name_geom, k), 4) for w in words['short']]
    words['name'], words['logo'] = ((words['short'][0], words['short'][1]) if likeness[0] >= likeness[1]
                                    else (words['short'][1], words['short'][0]))
    box_mm = {key: [v / k for v in words[key]['box_px']] for key in ('hero', 'name', 'logo')}

    # the plate: the framed sketch upscaled 2×, its painted words cleaned (bevel and shadow), filled from calm ground
    ground = zlm.ground_lab(rgb)
    m = zlm.masks(rgb, ground)
    painted = words['hero']['mask'] | words['name']['mask'] | words['logo']['mask']
    for other in words['others']:
        painted |= other['mask']
    # each painted word cleaned by its whole box grown 1.5 mm (its ink, bevel and drop shadow), the stones kept
    stones = zlm.stones_clear_of_words(m, painted, k)
    g = int(round(CLEAN_GROW_MM * k))
    clean = np.zeros(painted.shape, dtype=bool)
    for w in [words['hero'], words['name'], words['logo']] + words['others']:
        x0, y0, x1, y1 = w['box_px']
        clean[max(y0 - g, 0):y1 + g, max(x0 - g, 0):x1 + g] = True
    clean &= ~stones
    up = lm.upscale(rgb)
    k_up = k * lm.UP
    big = cv2.resize(clean.astype(np.uint8), (up.shape[1], up.shape[0]), interpolation=cv2.INTER_NEAREST)
    plate = cv2.inpaint(up, big, zlm.TELEA_R_PX, cv2.INPAINT_TELEA)
    plate, tiles = zlm.grain_fill_tiled(plate, big.astype(bool), ground, k_up)
    # [repair 1, the eye's round 0: "tiny marks near the d–R gap and a tick right of the final e"] the sketch's swash tips
    # past the boxes: every small off-ground speck (under 1.5 mm², ΔE00 over 10 from the ground) within 4 mm of a cleaned
    # word, never a stone, cleaned and filled again
    zone = cv2.dilate(big, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (zlm.odd_px(2 * SPECK_ZONE_MM, k_up),) * 2)).astype(bool)
    plab = lm.srgb_to_lab(plate)
    off = (lm.delta_e00(plab, np.broadcast_to(ground, plab.shape)) > SPECK_DE) & zone
    stones_up = cv2.resize(stones.astype(np.uint8), (up.shape[1], up.shape[0]), interpolation=cv2.INTER_NEAREST)
    # a stone is a blob: what survives an opening of 0.6 mm (a swash's thin dark curl is read as "stone" by colour)
    stones_up = cv2.morphologyEx(stones_up, cv2.MORPH_OPEN, cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (zlm.odd_px(STONE_BLOB_MM, k_up),) * 2)).astype(bool)
    n_s, lab_s, st_s, _ = cv2.connectedComponentsWithStats(off.astype(np.uint8), 8)
    specks = np.zeros(off.shape, dtype=bool)
    for i in range(1, n_s):
        part = lab_s == i
        if st_s[i, 4] < SPECK_MAX_MM2 * k_up * k_up and not (part & stones_up).any():
            specks |= part
    specks = cv2.dilate(specks.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    if specks.any():
        plate = cv2.inpaint(plate, specks.astype(np.uint8), zlm.TELEA_R_PX, cv2.INPAINT_TELEA)
        plate, _ = zlm.grain_fill_tiled(plate, specks, ground, k_up)
        big = (big.astype(bool) | specks).astype(np.uint8)
    speck_count = int(n_s - 1)

    # the lid's hero: placed on the sketch's hero box (one scale, centred), its painted pixels carried and set again
    s_h, dx_h, dy_h = fit_to(lid['letters'].bounds, box_mm['hero'])
    move = [s_h, 0, 0, s_h, dx_h, dy_h]
    st = master['hero']['hatch']['stroke']
    if st['stroke_mm'] * s_h < zm.HATCH_STROKE_MIN_MM or st['gap_mm'] * s_h < zm.HATCH_GAP_MM - 0.02:
        raise ValueError('the lid\'s hatch scaled × %.3f falls under the press (stroke %.3f, gap %.3f mm): it would need '
                         'coarsening, which this path does not do' % (s_h, st['stroke_mm'] * s_h, st['gap_mm'] * s_h))
    letters_h = affinity.affine_transform(lid['letters'], move)
    foil_h = affinity.affine_transform(lid['foil'], move)
    relief_h = affinity.affine_transform(lid['relief'], move)
    carry = lm.raster_fill(lid['letters'].buffer(CARRY_MM), lid['up'].shape[:2], (0.0, 0.0), lid['k_up']).astype(np.float32)
    carry = cv2.GaussianBlur(carry, (0, 0), FEATHER_MM * lid['k_up'] / 2.0)
    bx0, by0, bx1, by1 = [int(np.floor(v * lid['k_up'])) for v in lid['letters'].buffer(CARRY_MM + FEATHER_MM).bounds]
    bx0, by0 = max(bx0, 0), max(by0, 0)
    bx1, by1 = min(bx1 + 1, lid['up'].shape[1]), min(by1 + 1, lid['up'].shape[0])
    f = s_h * k_up / lid['k_up']                  # the lid's px to the header plate's px
    nw, nh = int(round((bx1 - bx0) * f)), int(round((by1 - by0) * f))
    interp = cv2.INTER_AREA if f < 1 else cv2.INTER_LANCZOS4
    src_rgb = cv2.resize(lid['up'][by0:by1, bx0:bx1].astype(np.float32), (nw, nh), interpolation=interp)
    src_a = np.clip(cv2.resize(carry[by0:by1, bx0:bx1], (nw, nh), interpolation=cv2.INTER_LINEAR), 0, 1)[..., None]
    tx = int(round((s_h * bx0 / lid['k_up'] + dx_h) * k_up))
    ty = int(round((s_h * by0 / lid['k_up'] + dy_h) * k_up))
    if tx < 0 or ty < 0 or tx + nw > plate.shape[1] or ty + nh > plate.shape[0]:
        raise ValueError('the lid\'s hero would leave the header: %s' % [tx, ty, nw, nh])
    region = plate[ty:ty + nh, tx:tx + nw].astype(np.float32)
    plate = plate.copy()
    plate[ty:ty + nh, tx:tx + nw] = np.clip(np.round(region * (1 - src_a) + src_rgb * src_a), 0, 255).astype(np.uint8)
    pasted = np.zeros(big.shape, dtype=bool)
    pasted[ty:ty + nh, tx:tx + nw] = src_a[..., 0] > 0.01
    residue = zlm.residue_calm(plate, big.astype(bool) & ~pasted, ground, k_up)

    # the lid's logotype on the sketch's name box; the approved logo on the sketch's logo box
    s_n, dx_n, dy_n = fit_to(name_geom.bounds, box_mm['name'])
    name_placed = lm.map_rings(lid['name_rings'], lambda p: (s_n * p[0] + dx_n, s_n * p[1] + dy_n))
    name_foil = affinity.affine_transform(lid['name_foil'], [s_n, 0, 0, s_n, dx_n, dy_n])
    lx0, ly0, lx1, ly1 = box_mm['logo']
    lw = lx1 - lx0
    lh = lw * LOGO_ASPECT
    logo_box = (lx0, (ly0 + ly1) / 2.0 - lh / 2.0, lw, lh)

    # the bleed: the plate's own edges mirrored 3 mm (the trim untouched); the page the trim plus its bleed
    b = int(np.ceil(facts['bleed_mm'] * k_up))
    plate_b = cv2.copyMakeBorder(plate, b, b, b, b, cv2.BORDER_REFLECT_101)
    if not np.array_equal(plate_b[b:-b, b:-b], plate):
        raise AssertionError('the bleed moved a pixel inside the trim')
    plate_png = out / 'engine' / 'header-plate.png'
    Image.fromarray(plate_b).save(plate_png)
    bleed_mm = b / k_up
    page_w, page_h = facts['w_mm'] + 2 * bleed_mm, facts['h_mm'] + 2 * bleed_mm

    def shift(geom):
        return affinity.translate(geom, bleed_mm, bleed_mm)

    name_ink, hero_ink, logo_ink = master['name']['ink'], master['hero']['ink'], master['logo']['ink']
    foil = Finish(kind='foil', plate=zm.FOIL_PLATE, appearance=Color.from_hex(hero_ink))
    emboss = Finish(kind='emboss', plate=zm.EMBOSS_PLATE)
    logo_shifted = (logo_box[0] + bleed_mm, logo_box[1] + bleed_mm, logo_box[2], logo_box[3])

    def document(drawn):
        children = [Group(name='PICTURE', role='background', children=[
            GImage(name='plate', src=str(plate_png), x=0.0, y=0.0, w=page_w, h=page_h)])]
        children.append(Group(name='LOGOTYPE', role='typography', actual_text='Enchanted Rose', children=[
            GPath(name='Enchanted Rose', segments=lm.rings_segments(lm.map_rings(name_placed, lambda p: (p[0] + bleed_mm, p[1] + bleed_mm))),
                  fill=SolidFill(color=Color.from_hex(name_ink)), fill_rule='evenodd')]))
        children.append(Group(name='LOGO', role='logo', children=lm.logo_parts(logo_shifted, logo_ink, foil_letters=False)))
        children.append(Group(name='HERO CARRIERS', role='effects', opacity=0.0, actual_text='ظلال', children=[
            GPath(name='ظلال (foil)', segments=zm.poly_segments(shift(foil_h)), fill=SolidFill(color=Color.from_hex(hero_ink)),
                  fill_rule='evenodd', finishes=[foil]),
            GPath(name='ظلال (relief)', segments=zm.poly_segments(shift(relief_h)),
                  fill=SolidFill(color=Color.from_hex(hero_ink)), fill_rule='evenodd', finishes=[emboss]),
            GPath(name='Enchanted Rose (foil)', segments=zm.poly_segments(shift(name_foil)),
                  fill=SolidFill(color=Color.from_hex(name_ink)), fill_rule='evenodd',
                  finishes=[Finish(kind='foil', plate=zm.FOIL_PLATE, appearance=Color.from_hex(name_ink))])]))
        if drawn:
            children.append(Group(name='HERO (foil, drawn)', role='typography', children=[GPath(
                name='ظلال (foil, drawn)', segments=zm.poly_segments(shift(foil_h)),
                fill=SolidFill(color=Color.from_hex(hero_ink)), fill_rule='evenodd')]))
        return Document(page_w=page_w, page_h=page_h, title='Ẓilāl display header',
                        metadata={'typography_surface': SURFACE, 'logical_text/1.0': True},
                        root=Group(name='HEADER', role='artwork', children=children))

    engine = out / 'engine' / 'header-engine.ai'
    emit_pdf_ai(document(False), str(engine))
    emit_pdf_ai(document(True), str(out / 'engine' / 'header-drawn.ai'))
    import fitz
    pdf = fitz.open()
    with fitz.open(str(engine)) as src:
        for i in range(src.page_count):
            p = pdf.new_page(width=src[i].rect.width, height=src[i].rect.height)
            p.show_pdf_page(p.rect, src, i)
            p.set_bleedbox(p.rect)
            p.set_trimbox(fitz.Rect(lm.pt(bleed_mm), lm.pt(bleed_mm), lm.pt(bleed_mm + facts['w_mm']),
                                    lm.pt(bleed_mm + facts['h_mm'])))
    pdf.set_metadata({'title': 'the Ẓilāl display\'s header', 'creator': SURFACE})
    lm.tag_srgb(pdf)
    pdf.save(str(out / 'header-master.pdf'), garbage=3, deflate=True)
    pages = pdf.page_count
    pdf.close()
    lm.render_png(out / 'header-master.pdf', 0, lm.FLAT_PPI, out / 'header-flat.png')
    lm.render_png(engine, 0, lm.FLAT_PPI, out / 'engine' / 'header-proof-flat.png')
    proof = fp.prove_build(out / 'engine' / 'header-proof-flat.png', engine, out / 'engine' / 'proof-record', foil_drawn=True)
    Image.open(out / 'engine' / 'proof-record' / 'finish-proof.png').save(out / 'finish-proof.png')

    hero_rec = {'source': {'pick': lm.rel(zm.MASTER_PICK), 'pick_sha256': lid['pick_sha256'],
                           'master': lm.rel(zd.LID12 / 'master.json'), 'master_foil_mm2': master['hero']['foil_mm2']},
                'scale': round(s_h, 6), 'move_mm': [round(dx_h, 4), round(dy_h, 4)],
                'sketch_box_mm': [round(v, 3) for v in box_mm['hero']],
                'placed_box_mm': [round(v, 3) for v in letters_h.bounds],
                'inverse_iou_with_the_source': inverse_iou(letters_h, lid['letters'], s_h, dx_h, dy_h),
                'foil_mm2': round(float(foil_h.area), 3), 'relief_mm2': round(float(relief_h.area), 3),
                'hatch_scaled': {'pitch_mm': round(master['hero']['hatch']['stroke']['pitch_mm'] * s_h, 4),
                                 'stroke_mm': round(master['hero']['hatch']['stroke']['stroke_mm'] * s_h, 4),
                                 'gap_mm': round(master['hero']['hatch']['stroke']['gap_mm'] * s_h, 4)},
                'raster': 'the lid\'s own painted hero (its pick upscaled 2×) inside its silhouette grown %.2f mm, '
                          'feathered %.2f mm, resampled × %.4f onto the header\'s plate' % (CARRY_MM, FEATHER_MM, f)}
    name_rec = {'scale': round(s_n, 6), 'move_mm': [round(dx_n, 4), round(dy_n, 4)],
                'sketch_box_mm': [round(v, 3) for v in box_mm['name']],
                'placed_box_mm': [round(v, 3) for v in lm.rings_area(name_placed, 24).bounds],
                'inverse_iou_with_the_source': inverse_iou(lm.rings_area(name_placed, 24), name_geom, s_n, dx_n, dy_n),
                'cap_height_mm': round(master['name']['measures']['cap_height_mm'] * s_n, 3),
                'foil_mm2': round(float(name_foil.area), 3)}
    safe = facts['safe_mm']
    inside = lambda bx: bool(bx[0] >= safe and bx[1] >= safe and bx[2] <= facts['w_mm'] - safe and bx[3] <= facts['h_mm'] - safe)
    rec = {'schema': 'day12_header_master/1', 'surface': SURFACE, 'rule': 'D-D12-2: the header by the preservation path',
           'pick': {'sketch': name, 'why': why, 'picture': lm.rel(dest / 'picture.png'),
                    'picture_sha256': lm.sha256(dest / 'picture.png'), 'crop': crop_rec},
           'size_mm': [facts['w_mm'], facts['h_mm']], 'bleed_mm': round(bleed_mm, 4), 'safe_mm': safe,
           'resolution': {'sketch_px_per_mm': round(k, 4), 'sketch_ppi': round(k * lm.MM_PER_INCH, 1),
                          'plate_px_per_mm': round(k_up, 4), 'plate_ppi': round(k_up * lm.MM_PER_INCH, 1),
                          'lid_plate_ppi': round(lm.PX_PER_MM_SRC * lm.UP * lm.MM_PER_INCH, 1),
                          'said': 'the header\'s resolution is lower than the lid\'s (D-D12-2: reported, not a stop)'},
           'words_px': {key: words[key]['box_px'] for key in ('hero', 'name', 'logo')},
           'name_likeness_iou': {'the two short words': likeness, 'said': 'the one more like the lid\'s own name is the '
                                                                         'name; the other the logo'},
           'cleaning': {'grown_mm': CLEAN_GROW_MM, 'px_up': int(big.sum()), 'tiles': tiles, 'residue_calm': residue,
                        'specks_cleaned': {'components_read': speck_count, 'px_up': int(specks.sum()),
                                           'rule': 'repair 1: off-ground specks under 1.5 mm² within 4 mm of a cleaned word, '
                                                   'touching no stone blob (a stone survives a 0.6 mm opening; a '
                                                   'swash\'s thin curl does not)'}},
           'hero': hero_rec, 'logotype': name_rec,
           'logo': {'box_mm': [round(v, 3) for v in (logo_box[0], logo_box[1], logo_box[0] + lw, logo_box[1] + lh)],
                    'ink': logo_ink, 'sketch_box_mm': [round(v, 3) for v in box_mm['logo']]},
           'inside_safe': {'hero': inside(letters_h.bounds), 'logotype': inside(lm.rings_area(name_placed, 24).bounds),
                           'logo': inside((logo_box[0], logo_box[1], logo_box[0] + lw, logo_box[1] + lh))},
           'finishes': {'foil_limits': proof['foil_limits'], 'coverage': proof['coverage']},
           'files': {'pdf': lm.rel(out / 'header-master.pdf'), 'pages': pages, 'flat': lm.rel(out / 'header-flat.png'),
                     'finish_proof': lm.rel(out / 'finish-proof.png'), 'engine': lm.rel(engine)}}
    lm.write_json(out / 'header.json', rec)
    return rec


def gate_record(out_dir=OUT):
    """The header's eye gate (D-D12-2) merged into header.json: round 0 and, after one repair, round 1."""
    out = Path(out_dir)
    rec = json.loads((out / 'header.json').read_text(encoding='utf-8'))
    rounds = []
    for label in ('r0', 'r1'):
        path = out / ('eye-%s.json' % label)
        if path.exists():
            e = json.loads(path.read_text(encoding='utf-8'))
            rounds.append({'round': label, 'holds': e['holds'], 'defects': e['defects'], 'cost_usd': e['look']['cost_usd'],
                           'record': lm.rel(path)})
    rec['gate'] = {'rule': 'D-D12-2: the eye\'s gate, repair ≤ 1', 'rounds': rounds, 'holds': bool(rounds and rounds[-1]['holds']),
                   'repairs': max(len(rounds) - 1, 0)}
    lm.write_json(out / 'header.json', rec)
    return rec
