"""Engine-owned panel sheets, masks and exact crops for any submitted product."""
from pathlib import Path
import json
import math
import hashlib
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import round_balm_sheet, product_drawing, stick_carton
from .round_balm_calls import sha
from .round_flow import write_json as write
from .round_product import normalize_brief, engine_panels

SIZE = (1536, 1024)
SCHEMA = 'round_sheet/2'
MARGIN = 28
GAP = 18
FONT = round_balm_sheet.FONT
LEGACY_BLANK_PINS = {
    'sheet.png': '72e17a1c5283159b07c45eaaa01d7f3023b9afaa087882ab6a8c316891a3599b',
    'sheet-mask.png': '13102beb3f5744e7180932be342c8d0b1a41cb73612fb6d3897c69f53119fc35',
    'sheet-windows.png': 'd422c150781a8e5f3de9c6b02b2011416be7320f850cf10b3de166f475d3c451',
    'sheet.json': '762c0adc12422bea812e11d224fd1c12c49b71aa80611aaf7a7be352d4999bef',
    'sheet-verification.json': '0532bf9c1449cfdfa1f765f64b6504452745e9a1f2baffb53bea773bb28d895e',
}


def needs_repair(prior_sheet, brief):
    """Pure check used before an owner-authorized archive and queued rebuild."""
    if prior_sheet.get('schema', '').startswith('r1_balm_sheet/'):
        return False
    expected = [panel['id'] for panel in brief['panels']]
    return (prior_sheet.get('schema') != SCHEMA or prior_sheet.get('panel_order') != expected or
            set(prior_sheet.get('panels', {})) != set(expected))


def _material_ground(panel, brief, box, scale):
    """Flat material appearance and the engine-owned printable interior."""
    x0, y0, x1, y1 = box
    width, height = x1-x0, y1-y0
    surface = panel['surface']
    liquid = brief['shades'][0]['hex']
    ground = liquid if surface == 'clear_acrylic' else '#CDAA50' if surface == 'gold_metal' else '#FFFFFF'
    image = Image.new('RGBA', (width, height), ground)
    details = {'ground_hex': ground, 'printable_box_px': list(box)}
    if surface == 'gold_metal':
        # The cap is a physical gold part. Artwork cannot recolour it; its
        # future engraving/foil is explicitly reserved, not an undeclared blank.
        stops = np.array([0, .16, .39, .56, .83, 1])
        colours = np.array([[151, 111, 37], [212, 175, 80], [250, 225, 148],
                            [204, 163, 65], [231, 199, 108], [164, 122, 42]])
        strip = np.stack([np.interp(np.linspace(0, 1, width), stops, colours[:, channel])
                          for channel in range(3)], axis=1).astype('uint8')
        image = Image.fromarray(np.repeat(strip[None, :, :], height, axis=0)).convert('RGBA')
        details.update(printable_box_px=None,
                       reserved_reason='Engine-reserved gold metal; engraving, hot foil or deboss is a later material pass. No painted artwork.')
    elif surface == 'clear_acrylic':
        wall = brief['dimensions_mm']['wall']
        edge = max(2, round(wall*scale))
        if 2*edge+4 >= min(width, height):
            raise ValueError('Clear wall and printable interior cannot be resolved: '+panel['id'])
        image = Image.new('RGBA', (width, height), '#EDF3F4')
        draw = ImageDraw.Draw(image)
        # Neutral glass walls, a distinct inner liquid column, and narrow white
        # reflections make this a clear bottle face rather than a coloured bar.
        draw.rectangle((0, 0, width-1, height-1), outline='#AABBC1', width=1)
        draw.rectangle((1, 1, width-2, height-2), outline='#FFFFFF', width=1)
        inner = [edge, edge, width-edge, height-edge]
        draw.rectangle((inner[0], inner[1], inner[2]-1, inner[3]-1), fill=liquid)
        draw.line((edge-1, edge, edge-1, height-edge-1), fill='#B9C9CE', width=1)
        draw.line((width-edge, edge, width-edge, height-edge-1), fill='#CAD5D8', width=1)
        highlight = max(1, round(.35*scale))
        strips = [[2, 2, 2+highlight, height-2],
                  [width-edge+max(1, edge//3), 2, width-edge+max(1, edge//3)+highlight, height-2],
                  [edge, edge, width-edge, edge+highlight],
                  [edge, height-edge-highlight, width-edge, height-edge]]
        for a, b, c, d in strips:
            draw.rectangle((a, b, c-1, d-1), fill='#FFFFFF')
        details.update(wall_mm=wall, liquid_width_mm=panel['width_mm']-2*wall,
                       liquid_box_px=[x0+inner[0], y0+inner[1], x0+inner[2], y0+inner[3]],
                       printable_box_px=[x0+edge+highlight, y0+edge+highlight, x1-edge-highlight, y1-edge-highlight],
                       protected_highlight_boxes_px=[[x0+a, y0+b, x0+c, y0+d] for a, b, c, d in strips])
    return image, details


def _legacy(brief, out):
    """Versioned replay of the blank paid-v1 engine contract, never its artwork."""
    from .round_product import legacy_balm_brief
    version = 1 if brief['sheet_layout'] == 'round1_balm_v1' else 2
    expected = legacy_balm_brief(version)['panels']
    actual = brief['panels']
    if len(actual) != 9 or any(a['id'] != e['id'] or
            abs(a['width_mm']-e['width_mm']) > 1e-8 or abs(a['height_mm']-e['height_mm']) > 1e-8
            for a, e in zip(actual, expected)):
        raise ValueError('Legacy replay requires the exact original ordered nine-panel geometry')
    if version == 2:
        return round_balm_sheet.build(out)
    source = round_balm_sheet.REPO/'docs/rounds/r1-balm'
    for name, pin in LEGACY_BLANK_PINS.items():
        if sha(source/name) != pin:
            raise ValueError('Pinned legacy blank engine contract changed: '+name)
    out.mkdir(parents=True, exist_ok=True)
    for name in LEGACY_BLANK_PINS:
        shutil.copyfile(source/name, out/name)
    return json.loads((out/'sheet.json').read_text())


def _layout(panels, coords, scale):
    """Shelf packing for arbitrary object panels beside the engine carton net."""
    die = None
    die_width = 0
    if coords is not None:
        x0, y0, x1, y1 = coords.cut_polygon.bounds
        die_width = (x1-x0+6)*scale
        die_height = (y1-y0+6)*scale
        if die_height > SIZE[1]-2*MARGIN-52:
            return None
        die = (SIZE[0]-MARGIN-die_width, MARGIN+52, die_width, die_height)
    area_right = (die[0]-GAP if die else SIZE[0]-MARGIN)
    positions = {}
    x, y, row_h = MARGIN, MARGIN+52, 0
    for panel in panels:
        if panel.get('engine_face'):
            continue
        w, h = panel['width_mm']*scale, panel['height_mm']*scale
        if w > area_right-MARGIN:
            return None
        if x+w > area_right:
            x, y, row_h = MARGIN, y+row_h+44, 0
        if y+h > SIZE[1]-MARGIN-25:
            return None
        positions[panel['id']] = (x, y, x+w, y+h)
        x += w+GAP
        row_h = max(row_h, h)
    return positions, die


def build(brief, out):
    out = Path(out)
    brief = normalize_brief(brief)
    brief_digest = hashlib.sha256(json.dumps(brief, sort_keys=True).encode()).hexdigest()
    if (out/'sheet.json').exists():
        prior = json.loads((out/'sheet.json').read_text())
        if needs_repair(prior, brief):
            raise ValueError('Sheet contract needs an authorized archive and rebuild before reuse')
        if prior.get('schema') == SCHEMA and prior.get('brief_sha256') != brief_digest:
            raise ValueError('The immutable sheet belongs to a different brief')
        if not verify(out)['passes']:
            raise ValueError('Existing immutable sheet failed verification')
        return prior
    if brief.get('sheet_layout') in ('round1_balm_v1', 'round1_balm_v2'):
        return _legacy(brief, out)
    panels, coords = engine_panels(brief)
    low, high = .05, 60.0
    for _ in range(50):
        mid = (low+high)/2
        if _layout(panels, coords, mid) is None:
            high = mid
        else:
            low = mid
    scale = low
    layout = _layout(panels, coords, scale)
    if layout is None or scale < .1:
        raise ValueError('Product panels cannot fit the common-scale sheet')
    positions, die_area = layout
    sheet = Image.new('RGBA', SIZE, 'white')
    windows = Image.new('L', SIZE, 0)
    guides = Image.new('RGBA', SIZE, (0, 0, 0, 0))
    wd, gd = ImageDraw.Draw(windows), ImageDraw.Draw(guides)
    font = ImageFont.truetype(str(FONT), 13)
    title = ImageFont.truetype(str(FONT), 17)
    gd.text((MARGIN, MARGIN), brief['name']+' — all panels at one scale · provisional', font=title, fill='black')
    record_panels = {}
    origin = None
    if coords is not None:
        xmin, ymin, xmax, ymax = coords.cut_polygon.bounds
        origin = (die_area[0]+(3-xmin)*scale, die_area[1]+(3-ymin)*scale)
    def pxbox(box):
        return [round(origin[0]+box[0]*scale), round(origin[1]+box[1]*scale),
                round(origin[0]+box[2]*scale), round(origin[1]+box[3]*scale)]
    for panel in panels:
        key = panel['id']
        box = pxbox(panel['engine']['box']) if panel.get('engine_face') else [round(v) for v in positions[key]]
        x0, y0, x1, y1 = box
        if x1-x0 < 8 or y1-y0 < 8:
            raise ValueError('A panel is too small to inspect on the common-scale sheet: '+key)
        material, material_record = _material_ground(panel, brief, box, scale)
        sheet.paste(material, (x0, y0))
        shape = panel.get('shape', 'rectangle')
        draw_shape = wd.ellipse if shape == 'circle' else wd.rectangle
        printable = material_record['printable_box_px']
        if printable is not None:
            a, b, c, d = printable
            draw_shape((a, b, c-1, d-1), fill=255)
        border = gd.ellipse if shape == 'circle' else gd.rectangle
        border((x0, y0, x1-1, y1-1), outline=(90, 90, 90, 255), width=1)
        # Labels are outside print windows; panel ID and physical dimensions are
        # also sent as text, so review never depends on scaled tiny captions.
        label = panel['label'] if not panel.get('engine_face') else ''
        if label:
            gd.text((x0, y0-19), label, font=font, fill='black')
        record_panels[key] = dict(panel, box_px=box, trim_px=box,
                                 mm=[panel['width_mm'], panel['height_mm']],
                                 trim_mm=[panel['width_mm'], panel['height_mm']], shape=shape,
                                 **material_record)
    expected_ids = [panel['id'] for panel in brief['panels']]
    if list(record_panels) != expected_ids:
        raise ValueError('Engine sheet must preserve the exact ordered brief panel set')
    if coords is not None:
        from shapely.geometry import box as geo_box
        from shapely.ops import unary_union
        faces = [p['engine'] for p in panels if p.get('engine_face')]
        prints = unary_union([geo_box(*f['box']) for f in faces]).intersection(coords.cut_polygon)
        grounds = unary_union([geo_box(*f['ground']) for f in faces])
        allowed = prints.union(grounds.difference(coords.cut_polygon).intersection(coords.cut_polygon.buffer(3)))
        def points(seq):
            return [(round(origin[0]+a*scale), round(origin[1]+b*scale)) for a, b in seq]
        for poly in ([allowed] if allowed.geom_type == 'Polygon' else allowed.geoms):
            wd.polygon(points(poly.exterior.coords), fill=255)
            for ring in poly.interiors:
                wd.polygon(points(ring.coords), fill=0)
        gd.line(points(coords.cut_polygon.exterior.coords), fill=(65, 65, 65, 255), width=1)
        for x0, y0, x1, y1 in coords.fold_lines+coords.slit_lines:
            gd.line(points([(x0, y0), (x1, y1)]), fill=(140, 140, 140, 255), width=1)
        # Captions live outside every print window and remain protected.
        long_faces = [p for p in panels if p.get('engine_face') in ('back', 'side_left', 'front', 'side_right')]
        caption_y = min(SIZE[1]-22, round(die_area[1]+die_area[3]+7))
        for panel in long_faces:
            box = record_panels[panel['id']]['box_px']
            gd.text((box[0], caption_y), panel['engine_face'].replace('side_', ''), font=font, fill='black')
        for panel in panels:
            if panel.get('engine_face') in ('top_end', 'bottom_end'):
                box = record_panels[panel['id']]['box_px']
                caption = panel['engine_face'].replace('_', ' ')
                width = font.getlength(caption)
                gd.text((box[0]-width-10, (box[1]+box[3])/2-8), caption, font=font, fill='black')
    editable = (np.asarray(windows) > 0) & (np.asarray(guides)[..., 3] == 0)
    mask = Image.new('RGBA', SIZE, 'white')
    mask.putalpha(Image.fromarray(np.where(editable, 0, 255).astype('uint8')))
    sheet = Image.alpha_composite(sheet, guides)
    out.mkdir(parents=True, exist_ok=True)
    sheet.save(out/'sheet.png'); mask.save(out/'sheet-mask.png'); windows.save(out/'sheet-windows.png')
    record = {'schema': SCHEMA, 'size_px': list(SIZE), 'px_per_mm': scale, 'brief_sha256': brief_digest,
              'panels': record_panels, 'shade': brief['shades'][0],
              'panel_order': expected_ids, 'die_origin_px': list(origin) if origin else None,
              'die_version': stick_carton.TEMPLATE_VERSION if coords is not None else None,
              'construction': 'Engine construction, clear walls, liquid edge reveals, highlights, reserved gold surfaces and outside printable windows are protected.',
              'sha256': {name: sha(out/name) for name in ('sheet.png', 'sheet-mask.png', 'sheet-windows.png')}}
    write(out/'sheet.json', record)
    proof = verify(out)
    write(out/'sheet-verification.json', proof)
    if not proof['passes']:
        raise ValueError('Invalid sheet: '+', '.join(proof['errors']))
    return record


def verify(out):
    out = Path(out)
    contract = json.loads((out/'sheet.json').read_text())
    if contract['schema'].startswith('r1_balm_sheet/'):
        result = round_balm_sheet.verify(out)
        for name, digest in contract['sha256'].items():
            if sha(out/name) != digest:
                result['errors'].append(name+' changed')
        result['passes'] = not result['errors']
        return result
    if contract['schema'] != SCHEMA:
        raise ValueError('Unknown sheet contract schema')
    mask = np.asarray(Image.open(out/'sheet-mask.png').convert('RGBA'))[..., 3]
    windows = np.asarray(Image.open(out/'sheet-windows.png')) > 0
    errors = []
    if set(contract['panels']) != set(contract['panel_order']) or len(set(contract['panel_order'])) != len(contract['panel_order']):
        errors.append('panel set differs from ordered brief contract')
    for name in ('sheet.png', 'sheet-mask.png', 'sheet-windows.png'):
        if sha(out/name) != contract['sha256'][name]:
            errors.append(name+' changed')
    if mask.shape != (SIZE[1], SIZE[0]) or np.any((mask == 0) & ~windows):
        errors.append('mask outside engine windows')
    aspects = {}
    for key, panel in contract['panels'].items():
        x0, y0, x1, y1 = panel['box_px']; w, h = panel['mm']
        if not (MARGIN-1 <= x0 < x1 <= SIZE[0]-MARGIN+1 and MARGIN <= y0 < y1 <= SIZE[1]-MARGIN):
            errors.append(key+' bounds')
        aspects[key] = abs((x1-x0)/(y1-y0)/(w/h)-1)
        if aspects[key] > .02:
            errors.append(key+' aspect')
        if max(abs((x1-x0)-w*contract['px_per_mm']), abs((y1-y0)-h*contract['px_per_mm'])) > 1.01:
            errors.append(key+' scale')
        if panel['surface'] == 'gold_metal' and (not panel.get('reserved_reason') or
                panel['printable_box_px'] is not None or np.any(mask[y0:y1, x0:x1] != 255)):
            errors.append(key+' gold material is not explicitly reserved and protected')
        if panel['surface'] == 'clear_acrylic':
            a, b, c, d = panel['printable_box_px']
            outer = mask[y0:y1, x0:x1].copy()
            outer[b-y0:d-y0, a-x0:c-x0] = 255
            if np.any(outer != 255):
                errors.append(key+' clear wall or liquid reveal is editable')
            for a, b, c, d in panel['protected_highlight_boxes_px']:
                if np.any(mask[b:d, a:c] != 255):
                    errors.append(key+' highlight is editable')
    return {'passes': not errors, 'errors': errors, 'panel_count': len(contract['panels']),
            'aspect_errors': aspects, 'mask_only_windows': not bool(np.any((mask == 0) & ~windows))}


def crops_and_drawing(dest, out):
    """Unscaled crop pins and a deterministic flat elevation inventory.

    The existing round-stick drawing remains available through legacy dispatch;
    generic products show their own flat faces, with no invented 3D surface.
    """
    dest, out = Path(dest), Path(out)
    contract = json.loads((out/'sheet.json').read_text())
    if contract['schema'].startswith('r1_balm_sheet/'):
        return round_balm_sheet.crops_and_drawing(dest, out)
    if contract['schema'] != SCHEMA:
        raise ValueError('Unknown sheet crop contract schema')
    im = Image.open(dest/'picture.png').convert('RGBA')
    if list(im.size) != contract['size_px']:
        raise ValueError('Sheet size changed; never stretch it')
    crops = {}
    for key, panel in contract['panels'].items():
        crop = im.crop(panel['box_px'])
        crop.save(dest/(key+'.png'))
        error = abs(crop.width/crop.height/(panel['mm'][0]/panel['mm'][1])-1)
        crops[key] = {'file': key+'.png', 'box_px': panel['box_px'], 'mm': panel['mm'],
                      'sha256': sha(dest/(key+'.png')), 'aspect_error': error, 'qualifies': error <= .02}
    # No resampling: review inventories use the original pixels and readable
    # labels. Whole sheet, crop inventory and blind text travel to the jurors.
    faces = [k for k, p in contract['panels'].items() if not p.get('engine_face')]
    if not faces:
        faces = list(contract['panels'])
    max_h = max(Image.open(dest/(k+'.png')).height for k in faces)
    width = sum(Image.open(dest/(k+'.png')).width for k in faces)+GAP*(len(faces)+1)
    drawing = Image.new('RGB', (max(width, 620), max_h+120), 'white')
    draw = ImageDraw.Draw(drawing); font = ImageFont.truetype(str(FONT), 16)
    draw.text((GAP, 12), product_drawing.LABEL+' — flat product faces, common scale', font=font, fill='black')
    x = GAP
    for key in faces:
        crop = Image.open(dest/(key+'.png')).convert('RGBA')
        drawing.paste(crop, (x, 68), crop)
        draw.text((x, 43), key.replace('body_', '').replace('cap_', ''), font=font, fill='black')
        x += crop.width+GAP
    drawing.save(dest/'drawing.png')
    write(dest/'drawing.json', {'schema': 'round_flat_drawing/1', 'label': product_drawing.LABEL,
                              'method': 'Exact unscaled flat product-face pixels; no shading or invented surfaces.',
                              'sha256': sha(dest/'drawing.png'), 'px_per_mm': contract['px_per_mm']})
    result = {'panels': crops, 'qualifies': all(p['qualifies'] for p in crops.values())}
    write(dest/'crop.json', result)
    return result
