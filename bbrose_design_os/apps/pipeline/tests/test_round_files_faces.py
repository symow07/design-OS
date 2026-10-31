"""The face method (owner, 2026-10-27/28; PIPELINE.md): each printed face is its own job — a stand face cut straight
from one painting of the engine's flat die (owner, 2026-10-28: "die first, then the design on it"), a product face
drawn as one edit guided by the picked picture with no lettering — its live type and logo placed and previewed, and the
owner is the gate: Accept or Redraw per face, then "Make my files". Paid clients are fakes; the reading, the die, the
painting's re-application, the composer, the writer and the readback are real ($0)."""
import base64
from copy import deepcopy
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import re
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
import zipfile

import fitz
import numpy as np
import pytest
from PIL import Image, ImageDraw

from apps.pipeline.services import round_files_faces as faces
from apps.pipeline.services import round_files_faces as reading


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def picture(tmp_path):
    """A 320 × 160 picked picture: the bottle front, cap, stand header and base side by side."""
    image = Image.new('RGB', (320, 160), 'white')
    draw = ImageDraw.Draw(image)
    panels = {}
    fields = ('product_latin', None, 'product_arabic', 'shade_0')
    for index, key in enumerate(reading.PANEL_IDS):
        x = index * 80
        crop = [x, 0, x + 80, 160]
        polygon = [[x, 0], [x + 79, 0], [x + 79, 159], [x, 159]]
        draw.polygon([tuple(p) for p in polygon], fill='#A45564')
        draw.line([(x + 10, 65), (x + 60, 130), (x + 15, 145)], fill='#D5AF59', width=4)
        text = [] if fields[index] is None else [{'field': fields[index], 'text': 'MODEL INVENTION NEVER PRINTED',
                                                  'box_px': [x + 20, 80, x + 40, 96], 'color': '#D5AF59', 'rotation': 0}]
        if key == 'body_front':
            text.append({'field': 'shade_0', 'box_px': [x + 10, 110, x + 60, 125], 'color': '#D5AF59', 'rotation': 0})
        marks = [{'kind': 'logo', 'box_px': [x + 20, 30, x + 60, 46], 'color': '#D5AF59', 'rotation': 0}] \
            if key == 'stand_base' else []
        panels[key] = {'crop_px': crop, 'print_polygon_px': polygon, 'text': text, 'marks': marks,
                       'lineart_boxes_px': [crop]}
    source = tmp_path / 'picked.png'
    image.save(source)
    brief = {'copy': {'brand': 'BBROSE', 'product': 'Lip Gloss / ملمع شفاه'},
             'shades': [{'name': 'Rose Glass', 'hex': '#C9707A'}],
             'dimensions_mm': {'width': 15, 'depth': 15, 'height': 100, 'cap_height': 30},
             'stand': {'count': 12, 'dimensions_mm': {'width': 110, 'depth': 85, 'height': 160},
                       'layout': {'rows': 3, 'columns': 4}}}
    inspection = {'image_size_px': [320, 160], 'panels': panels, 'stand': {'rows': 3, 'columns': 4, 'count': 12,
                  'bottles': [{'row': r, 'column': c, 'box_px': [5 + c * 20, 5, 20 + c * 20, 100], 'shade_field': 'shade_0'}
                              for r in range(3) for c in range(4)]}}
    return source, brief, inspection


# --- the reading (moved unchanged from round_files_art) ---------------------------------------------------------------

def test_reading_repairs_items_one_by_one_and_drops_only_the_bad_one(tmp_path, monkeypatch):
    monkeypatch.setattr(faces, 'ARABIC_TYPE', True)   # the kept Arabic code, switched on for its own test (English only since 2026-10-29)
    _, brief, inspection = picture(tmp_path)
    body = inspection['panels']['body_front']
    body['text'] = [
        {'field': 'product_latin', 'box_px': [5, 80, 25, 96], 'color': 'rgb(213, 175, 89)', 'rotation': -90},
        {'field': 'product_arabic', 'box_px': [20, 80, 40, 96], 'color': 'gold', 'rotation': 0},
        {'field': 'shade_0', 'box_px': [-8, 108, 60.4, 126], 'color': 'd5af59', 'rotation': 0, 'arc': True},
        {'field': 'shade_0', 'box_px': [10, 30, 60, 45], 'color': '#d5af59', 'rotation': 28},
        {'field': 'invented', 'box_px': [10, 50, 60, 60], 'color': '#D5AF59', 'rotation': 0}]
    body['marks'] = [{'kind': 'logo', 'box_px': [30, 20, 50, 70], 'color': [213, 175, 89], 'rotation': '-90'}]
    plan = reading.validate_inspection(reading.normalise_reading(inspection, [320, 160], brief), [320, 160], brief)
    rows = plan['panels']['body_front']['text']
    assert [row['field'] for row in rows] == ['product_latin', 'shade_0', 'shade_0']
    assert rows[0] == {'field': 'product_latin', 'box_px': [5, 80, 25, 96], 'color': '#D5AF59', 'rotation': 90}
    assert rows[1]['box_px'] == [0, 108, 61, 126] and rows[1]['arc'] is True
    assert rows[2]['rotation'] == 0 and rows[2]['angle_deg'] == 28
    assert plan['panels']['body_front']['marks'] == [{'box_px': [30, 20, 50, 70], 'color': '#D5AF59', 'rotation': 90,
                                                      'kind': 'logo'}]
    dropped = [(row['item'], row['why']) for row in plan['reading_findings'] if row['action'] == 'dropped']
    assert dropped == [('text “product_arabic”', "its colour 'gold' is not a colour"),
                       ('text “invented”', 'it names no supplied COPY field')]
    del inspection['panels']['cap_front']
    with pytest.raises(ValueError, match='front, cap'):
        reading.validate_inspection(reading.normalise_reading(inspection, [320, 160], brief), [320, 160], brief)


def test_a_negative_quarter_turn_reads_bottom_to_top(tmp_path):
    from apps.pipeline.services.round_files_export import Surface
    assert reading._turn(-90) == (90, 90) and reading._turn(-270) == (270, 270) and reading._turn(2) == (0, 0)
    surface = Surface([20, 60], 'direction')
    surface.text({'copy': 'BBROSE', 'face': 'latin', 'box_mm': [2, 2, 18, 58], 'size_pt': 12,
                  'rotation': reading._turn(-90)[0]})
    path = tmp_path / 'direction.ai'
    surface.save(path)
    with fitz.open(path) as doc:
        ys = [char[2][1] for span in doc[0].get_texttrace() for char in span['chars']]
    assert len(ys) == 6 and ys == sorted(ys, reverse=True)


def test_invented_lettering_is_set_live_from_copy_along_its_band(tmp_path, monkeypatch):
    monkeypatch.setattr(faces, 'ARABIC_TYPE', True)   # the kept Arabic code, switched on for its own test (English only since 2026-10-29)
    from apps.pipeline.services import round_files_faces as ornament
    from apps.pipeline.services.round_files_export import Surface, read_back_ai
    _, brief, inspection = picture(tmp_path)
    brief['shades'] = [{'name': 'Rose Glass', 'hex': '#C9707A', 'name_arabic': 'روز جلاس'},
                       {'name': 'Ember Glow', 'hex': '#C2553A', 'name_arabic': 'إمبر جلو'}]
    path = [[165, 72], [200, 60], [235, 72]]
    inspection['panels']['stand_header']['ornament_lettering'] = [
        {'path_px': path, 'height_px': 6.4, 'color': '#d5af59'}, {'path_px': [[170, 60]], 'height_px': 6, 'color': '#D5AF59'}]
    plan = reading.validate_inspection(reading.normalise_reading(inspection, [320, 160], brief), [320, 160], brief)
    assert plan['panels']['stand_header']['ornament_lettering'] == [{'path_px': path, 'height_px': 7, 'color': '#D5AF59'}]
    zone, = reading.ornament_rows(plan['panels']['stand_header'], [160, 0, 240, 160], brief)
    assert [(item['field'], item['copy']) for item in zone['copy']] == [
        ('brand', 'BBROSE'), ('product_arabic', 'ملمع شفاه'), ('arabic_shade_0', 'روز جلاس'), ('arabic_shade_1', 'إمبر جلو')]
    runs, record = ornament.layout_runs('header', 0, zone, [0, 0, 107, 214])
    assert record['left_out'] == [] and record['size_pt'] >= 5
    assert [run['copy'] for run in runs] == ['جلو', 'إمبر', 'جلاس', 'روز', 'شفاه', 'ملمع', 'BBROSE']
    surface = Surface([107, 214], 'ornament')
    for run in runs:
        surface.text(run)
    saved = tmp_path / 'ornament.ai'
    surface.save(saved)
    readback = read_back_ai(saved, surface.rows, surface.elements)
    assert readback['checks']['live_text'] and all(copy['present'] for copy in readback['copies'])


def test_the_stand_is_built_for_the_briefs_grid_and_lists_the_pictures(tmp_path):
    from apps.dielines.geometry import counter_display as stand
    _, brief, inspection = picture(tmp_path)
    inspection['stand'] = {'rows': 3, 'columns': 6, 'count': 18, 'bottles': [
        {'row': r, 'column': c, 'box_px': [5 + c * 12, 5 + r * 3, 15 + c * 12, 100],
         'shade_field': 'shade_0' if r == 0 and c < 2 else None} for r in range(3) for c in range(6)]}
    geometry = stand.solve_stand(brief, inspection)
    assert (geometry['rows'], geometry['columns'], geometry['count']) == (3, 4, 12)
    assert all(hole['shape'] == 'square' for hole in geometry['record']['holes'])
    assert geometry['layout']['note'] == ('The picture shows 18 products (3 rows × 6 across); '
                                          'the stand is built for the brief’s 12 (3 rows × 4 across).')
    loading = reading.shade_loading(inspection, brief)
    assert len(loading['slots']) == 12 and loading['unresolved_count'] == 10


def test_round_copy_record_adds_unconfirmed_arabic_shade_names_bound_to_its_brief(tmp_path, monkeypatch):
    monkeypatch.setattr(faces, 'ARABIC_TYPE', True)   # the kept Arabic code, switched on for its own test (English only since 2026-10-29)
    from apps.pipeline.services import round_files_gate as files_flow, round_flow as flow
    _, brief, _ = picture(tmp_path)
    build = SimpleNamespace(inputs={'brief': brief, 'brief_sha256': 'a' * 64}, round=SimpleNamespace(slug='copy'))
    monkeypatch.setattr(flow, 'round_root', lambda record: tmp_path)
    record = {'schema': 'round_files_copy/1', 'brief_sha256': 'a' * 64, 'arabic_shade_names': {'Rose Glass': 'روز جلاس'},
              'source': 'fixture', 'confirmed': False}
    (tmp_path / 'files-copy.json').write_text(json.dumps(record, ensure_ascii=False))
    merged = files_flow.files_brief(build)
    fields = reading.copy_fields(merged)
    assert fields['arabic_shade_0'] == 'روز جلاس' and [key for key in fields if key.startswith('shade_')] == ['shade_0']
    (tmp_path / 'files-copy.json').write_text(json.dumps(dict(record, brief_sha256='b' * 64), ensure_ascii=False))
    with pytest.raises(ValueError):
        files_flow.files_brief(build)


# --- the faces: their turns, templates, clean and drawing --------------------------------------------------------------

def stand_geometry(tmp_path, brief=None, inspection=None):
    from apps.dielines.geometry import counter_display as stand
    _, default_brief, default_inspection = picture(tmp_path)
    return stand.solve_stand(brief or default_brief, inspection or default_inspection)


def test_every_printed_face_of_the_die_is_a_face_cut_upright_from_the_painting(tmp_path, monkeypatch):
    """Every printed face of the 1.0 die is a face of the design, with no mirrored or ground-only copy. Folded print side
    out, a wall's top is its edge away from the floor; the doubled header's folded-over front leaf hangs from its fold.
    A painting with each face's top half red (the way its top points on the sheet) gives, cut by painted_face, a face
    red above blue; and the composer places the painting's own pixels in one raster, brought up to 300 PPI (the owner's
    goal of 2026-10-29): back at the painting's scale it is the painting, and the record says which PPI each face had."""
    from apps.dielines.exporters import counter_display_files as cdf
    geometry = stand_geometry(tmp_path)
    die = faces.die_of(geometry)
    tray = next(part for part in die.parts if part.name == 'tray')
    floor = next(poly for name, poly, _ in tray.faces if name == 'floor').centroid
    up = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}
    jobs = {spec['die']: spec['quarters'] for spec in faces.FACES.values() if 'die' in spec}
    assert set(jobs) == {('tray', name) for name, _, printed in tray.faces if printed}
    for (_, name), quarters in jobs.items():
        centre = next(poly for face, poly, _ in tray.faces if face == name).centroid
        away = np.array([centre.x - floor.x, centre.y - floor.y])
        away = np.round(away / np.abs(away).max())
        expected = -away if name == 'header front' else away             # 1.0: the folded-over leaf, shopper side
        assert tuple(expected) == up[quarters], name
    setup = faces.flat_setup(geometry, tmp_path / 'flat')
    masks = cdf.flat_masks(die, setup['frame'])
    raw = np.full(masks['owner'].shape + (3,), 255, np.uint8)
    for key, spec in faces.FACES.items():
        if faces.stand_face(key):
            ys, xs = np.nonzero(masks['owner'] == masks['names'].index(spec['die'][1]) + 1)
            dx, dy = up[spec['quarters']]
            top = (xs - xs.mean()) * dx + (ys - ys.mean()) * dy > 0
            raw[ys, xs] = (20, 40, 200)
            raw[ys[top], xs[top]] = (220, 20, 20)
    (tmp_path / 'flat' / 'paintings' / '1').mkdir(parents=True)
    Image.fromarray(raw).save(tmp_path / 'raw.png')
    painting = dict(faces.settle_flat(tmp_path / 'raw.png', tmp_path / 'flat', tmp_path / 'flat' / 'paintings' / '1',
                                      geometry), n=1)
    drawn = {}
    for key in faces.FACES:
        if faces.stand_face(key):
            upright = np.asarray(Image.open(faces.flat_face(tmp_path, key, 1, painting, geometry)['face'])).astype(int)
            red = (upright[..., 0] > 150) & (upright[..., 2] < 100)
            blue = (upright[..., 2] > 150) & (upright[..., 0] < 100)
            assert np.argwhere(red)[:, 0].mean() < np.argwhere(blue)[:, 0].mean(), key       # its top stands up
            drawn[key] = json.loads((faces.drawing_folder(tmp_path, key, 1) / 'record.json').read_text())
    _, brief, inspection = picture(tmp_path)
    monkeypatch.setattr(faces, 'upright_marks', lambda *args: {'type': [], 'logos': [], 'ornament': []})
    spec, placements = faces.compose_stand(drawn, inspection, brief, geometry, tmp_path / 'on-die')
    assert len(spec['artwork']) == 1 and set(placements) == {' / '.join(part_face) for part_face in jobs}
    assert spec['artwork'][0]['ppi'] == 300.0
    assert all(row['source'] == 'painting' and row['native_ppi'] == setup['frame']['dpi_at_1to1']
               and row['composed_ppi'] == 300.0 for row in placements.values())
    placed = Image.open(spec['artwork'][0]['path'])
    art = np.asarray(Image.open(painting['art']))
    ys, xs = np.nonzero(art[..., 3])
    art = art[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    back = np.asarray(placed.resize((art.shape[1], art.shape[0]), Image.BOX)).astype(int)
    from scipy import ndimage
    inner = ndimage.binary_erosion(art[..., 3] > 0, iterations=2) & (back[..., 3] > 0)
    assert inner.sum() > 0.8 * (art[..., 3] > 0).sum()
    assert np.abs(back[inner][:, :3] - art[inner][:, :3].astype(int)).mean() < 6


def test_the_template_carries_no_guide_and_nothing_is_erased_after_drawing(tmp_path):
    geometry = stand_geometry(tmp_path)
    _, brief, inspection = picture(tmp_path)
    face = faces.face_geometry('bottle', brief, faces.die_of(geometry))
    sheet = faces.template('bottle', face, tmp_path / 'bottle')
    rgba = np.asarray(Image.open(sheet['template']))
    x0, y0, x1, y1 = sheet['frame_px']
    assert set(np.unique(rgba[..., 3])) == {0, 255}
    assert {tuple(v) for v in rgba[rgba[..., 3] == 255][:, :3]} == {(255, 255, 255)}    # no guide drawn in the art
    assert (rgba[y0 + 2:y1 - 2, x0 + 2:x1 - 2, 3] == 0).all()
    raw = np.random.default_rng(3).integers(0, 256, (rgba.shape[0], rgba.shape[1], 3), dtype=np.uint8)
    (tmp_path / 'bottle' / 'call').mkdir()
    Image.fromarray(raw).save(tmp_path / 'bottle' / 'call' / 'raw.png')
    cut = faces.cut_face(tmp_path / 'bottle' / 'call' / 'raw.png', sheet, tmp_path / 'bottle')
    assert (np.asarray(Image.open(cut['face'])) == raw[y0:y1, x0:x1]).all()             # as drawn, nothing erased
    words = faces.prompt('cap', face)
    assert words.endswith(faces.NO_WORDS) and 'dashed' not in words


def test_the_flat_prompt_names_every_printed_face_its_way_up_and_no_words(tmp_path):
    geometry = stand_geometry(tmp_path)
    setup = faces.flat_setup(geometry, tmp_path / 'flat')
    words = faces.flat_prompt(setup, style='the picked picture.', keep='The HEADER FRONT keeps the dial.')
    for name, quarters in faces.flat_up().items():
        assert re.search(re.escape(name.upper()) + r'[^\n]*: x \d+–\d+, y \d+–\d+ px; ' + faces.UP_WORDS[quarters],
                         words), name
    assert 'TRANSPARENT' in words and 'The HEADER FRONT keeps the dial.' in words and words.endswith(faces.FLAT_NO_WORDS)
    one = faces.flat_prompt(setup, style='the picked picture.', panel='front panel', note='Medallions whole.')
    assert 'Its one TRANSPARENT area is the FRONT PANEL' in one and 'The owner asks: "Medallions whole."' in one


DIAL = {'shade_0': (165, 85, 90), 'shade_1': (90, 50, 65), 'shade_2': (180, 85, 40)}
NAVY, GOLD = (27, 43, 75), (213, 175, 89)


def dial_picture(w, h, *, numerals=False):
    """A drawn header as the model draws it: a quarter dial from the lower left, its three bands in colours near (not
    at) the brief's, gold rules, a tick ring, a free navy ring inside a gold rim, and the needle across the bands."""
    image = Image.new('RGB', (w, h), NAVY)
    d = ImageDraw.Draw(image)
    cx, cy, R = .12 * w, .96 * h, .86 * min(w, h * 1.2)
    def ring(r0, r1, fill):
        d.pieslice([cx - r1, cy - r1, cx + r1, cy + r1], 180, 360, fill=fill)
        d.pieslice([cx - r0, cy - r0, cx + r0, cy + r0], 180, 360, fill=NAVY)
    ring(.975 * R, .99 * R, GOLD)
    ring(.66 * R, .845 * R, GOLD)
    ring(.66 * R, .84 * R, DIAL['shade_0'])
    ring(.48 * R, .66 * R, GOLD)
    ring(.485 * R, .655 * R, DIAL['shade_1'])
    ring(.3 * R, .48 * R, GOLD)
    ring(.305 * R, .475 * R, DIAL['shade_2'])
    for t in range(0, 91, 3):
        a = math.radians(t)
        d.line([(cx + .85 * R * math.cos(a), cy - .85 * R * math.sin(a)),
                (cx + .89 * R * math.cos(a), cy - .89 * R * math.sin(a))], fill=GOLD, width=2)
    a = math.radians(52)
    d.line([(cx, cy), (cx + .86 * R * math.cos(a), cy - .86 * R * math.sin(a))], fill=GOLD, width=7)
    return image, (cx, cy, R)


def test_header_type_stands_each_label_on_its_own_band_and_the_brand_upright_on_the_navy_ring(tmp_path, monkeypatch):
    monkeypatch.setattr(faces, 'ARABIC_TYPE', True)   # the kept Arabic code, switched on for its own test (English only since 2026-10-29)
    from apps.pipeline.services import round_files_faces as dial
    from apps.pipeline.services.round_files_export import measure_type
    k = 10.0
    face = {'w_mm': 107.0, 'h_mm': 79.7, 'bleed_mm': 3.0, 'safe_mm': 3.0}
    image, (cx, cy, R) = dial_picture(int(113 * k), int(85.7 * k))
    image.save(tmp_path / 'header.png')
    brief = {'copy': {'brand': 'BBROSE', 'product': 'Lip Gloss / ملمع شفاه'},
             'shades': [{'name': 'Rose Glass', 'hex': '#C9707A', 'name_arabic': 'زجاج الورد'},
                        {'name': 'Fig Nectar', 'hex': '#8E4A5C', 'name_arabic': 'رحيق التين'},
                        {'name': 'Ember Glow', 'hex': '#C2553A', 'name_arabic': 'وهج الجمر'}]}
    fields = reading.copy_fields(brief)
    rows, record = dial.header_type(tmp_path / 'header.png', k, face, brief, fields, label_colour='#E8C98A',
                                    ring_colour='#D5AF59')
    rgb = np.asarray(image).astype(int)
    labels = [row for row in rows if not row['name'].startswith('header:ring')]
    assert sorted(row['copy'] for row in labels) == sorted(['Rose Glass', 'زجاج الورد', 'Fig Nectar', 'رحيق التين',
                                                            'Ember Glow', 'وهج الجمر'])
    assert len({round(row['size_pt'], 3) for row in labels}) == 1                       # one set
    for row in labels:
        field = row['copy_field'].replace('arabic_', '')
        x, y = (int(v * k) for v in row['center_mm'])
        colour = rgb[y, x]
        nearest = min(DIAL, key=lambda f: np.abs(colour - DIAL[f]).sum())
        assert nearest == field, (row['copy'], colour)                                    # on its own band
        partner = next(o for o in labels if o is not row and o['copy_field'].replace('arabic_', '') == field)
        assert abs(row['center_mm'][0] - partner['center_mm'][0]) < .5
    ring = [row for row in rows if row['name'].startswith('header:ring')]
    assert {row['copy'] for row in ring} == {'BBROSE', 'ملمع', 'شفاه'}                    # no shade name twice
    for row in ring:
        r = math.hypot(row['center_mm'][0] * k - cx, row['center_mm'][1] * k - cy)
        assert .89 * R <= r <= .975 * R, row['copy']                                      # on the navy ring only
    brand = next(row for row in ring if row['copy'] == 'BBROSE')
    assert brand['angle_deg'] == 0
    ink = measure_type(brand)['ink_box_mm']
    assert ink[0] >= 6 and ink[1] >= 6 and ink[2] <= 110 and ink[3] <= 82.7                  # upright, not cropped
    for x, y in ((ink[0], ink[1]), (ink[2], ink[1]), (ink[0], ink[3]), (ink[2], ink[3])):
        assert .88 * R <= math.hypot(x * k - cx, y * k - cy) <= .976 * R
    assert record['ring']['placed'] and record['labels']['shade_0']['placed']


def test_the_front_strip_sets_one_centred_line_with_its_slash(tmp_path, monkeypatch):
    monkeypatch.setattr(faces, 'ARABIC_TYPE', True)   # the kept Arabic code, switched on for its own test (English only since 2026-10-29)
    from apps.pipeline.services.round_files_export import measure_type
    _, brief, inspection = picture(tmp_path)
    inspection['panels']['stand_base']['text'] = [
        {'field': 'product_latin', 'box_px': [250, 120, 290, 132], 'color': '#D5AF59', 'rotation': 0},
        {'field': 'product_arabic', 'box_px': [292, 120, 318, 133], 'color': '#D5AF59', 'rotation': 0}]
    face = faces.face_geometry('front', brief, faces.die_of(stand_geometry(tmp_path)))
    out = faces.marks('front', inspection, brief, face)
    assert [row['copy'] for row in out['type']] == ['Lip Gloss', '/', 'ملمع شفاه']
    xs = [row['center_mm'][0] for row in out['type']]
    assert xs == sorted(xs) and len({row['size_pt'] for row in out['type']}) == 1
    inks = [measure_type(row)['ink_box_mm'] for row in out['type']]
    middle = (face['bleed_mm'] * 2 + face['w_mm']) / 2
    assert abs((inks[0][0] + inks[-1][2]) / 2 - middle) < 1.0                         # centred across the face
    assert inks[0][2] < inks[1][0] and inks[1][2] < inks[2][0]                            # never overlapping
    logo, = out['logos']
    assert abs((logo['box_mm'][0] + logo['box_mm'][2]) / 2 - middle) < 1e-6 and logo['rotation'] == 0


def test_square_view_draws_the_front_flat_and_turns_the_right_face_toward_the_viewer():
    from apps.pipeline.services import product_drawing as pd
    k = 10.0
    tex = np.zeros((100, 4 * 150, 3), np.uint8)
    tex[:, :150] = (200, 30, 30)
    tex[:, 150:300] = (30, 30, 200)
    tex[:, 300:] = (30, 200, 30)
    front = pd.square_view([(tex, k, 10.0)], 15.0, 0.0, 0.0, (250, 250, 0))
    seen = front[..., 3] > 0
    red = (front[..., :3] == (200, 30, 30)).all(axis=2) & seen
    assert red.sum() / seen.sum() > .97                            # the front alone (its edge column interpolated)
    assert abs(seen.sum(axis=1).max() / pd.PX_PER_MM - 15.0) < .3
    three = pd.square_view([(tex, k, 10.0)], 15.0, 45.0, 15.0, (250, 250, 0))
    colours = {tuple(c) for c in three[three[..., 3] > 0][:, :3]}
    assert {(200, 30, 30), (30, 30, 200), (250, 250, 0)} <= colours and (30, 200, 30) not in colours
    with pytest.raises(ValueError):
        pd.square_view([(tex, k, 10.0)], 15.0, 90.0, 0.0, (0, 0, 0))


# --- the paid boundary, the build and the move onto the face path -------------------------------------------------------

pytestmark_db = pytest.mark.django_db(transaction=True)


def text_reply(payload):
    return {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': json.dumps(payload, ensure_ascii=False)}],
            'usage': {'input_tokens': 100, 'output_tokens': 100, 'output_tokens_details': {'thinking_tokens': 25}}}


GROUNDS = {'bottle': (200, 120, 130), 'cap': (200, 160, 80)}


def drawn_reply(**kwargs):
    """A fake edit returned at the template's size: a product face's transparent face filled with a flat ground; the
    flat die's printed faces filled navy 2 px off the die (as a model drifts), a dial (dial_picture) on its header
    front; a stand face repainted in a fresh ground."""
    template = Image.open(kwargs['image'][0]).convert('RGBA')
    kwargs['image'][0].seek(0)
    rgba = np.asarray(template).copy()
    prompt = kwargs['prompt']
    hole = np.asarray(template)[..., 3] == 0
    if prompt.startswith('Image 1 is a flat die'):
        rgba[np.roll(np.roll(hole, 2, axis=0), 2, axis=1)] = (24, 34, 70, 255)
        x0, x1, y0, y1 = map(int, re.search(r'HEADER FRONT \(the shopper sees it\): x (\d+)–(\d+), y (\d+)–(\d+)',
                                            prompt).groups())
        rgba[y0:y1, x0:x1, :3] = np.asarray(dial_picture(x1 - x0, y1 - y0)[0])
    elif prompt.startswith('Image 1 is our flat die'):
        rgba[hole] = (60, 30, 90, 255)
    elif prompt.startswith('Image 1 is a sheet of plain'):
        # the motif sheet: in each transparent cell one motif alone on the plain ground
        from scipy import ndimage
        rgba[hole] = (31, 58, 51, 255)
        labels, count = ndimage.label(hole)
        for index, slices in enumerate(ndimage.find_objects(labels)):
            y0, y1, x0, x1 = slices[0].start, slices[0].stop, slices[1].start, slices[1].stop
            ys, xs = np.mgrid[y0:y1, x0:x1]
            r = min(y1 - y0, x1 - x0) * .4
            rgba[y0:y1, x0:x1][(xs - (x0 + x1) / 2) ** 2 + (ys - (y0 + y1) / 2) ** 2 < r * r] = (200 - 8 * index, 90 + 6 * index, 70, 255)
    elif prompt.startswith('Image 1 is the sheet: white, with TRANSPARENT'):
        # a wrap: one picture, a green ground with level gold bands and a vine that wanders across it
        ys, xs = np.mgrid[:rgba.shape[0], :rgba.shape[1]]
        art = np.zeros(rgba.shape, np.uint8)
        art[...] = (31, 58, 51, 255)
        art[(ys // 40) % 6 == 2] = (184, 138, 62, 255)
        art[(np.sin(xs / 37.0) * 18 + ys) % 90 < 6] = (50, 80, 60, 255)
        rgba[hole] = art[hole]
    elif 'one printed face of a folding cardboard counter stand' in prompt:
        # a stand face drawn again at 300 PPI: image 2 (its crop of the painting) followed exactly
        reference = Image.open(kwargs['image'][1]).convert('RGB')
        kwargs['image'][1].seek(0)
        ys, xs = np.nonzero(hole)
        x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
        rgba[y0:y1, x0:x1, :3] = np.asarray(reference.resize((x1 - x0, y1 - y0)))
    else:
        what = prompt.split('This is the')[1][:60]
        rgba[hole] = (*next((colour for key, colour in GROUNDS.items() if key in what), (24, 34, 70)), 255)
        if prompt.startswith('Image 1 is a flat net'):
            # a net's sides told apart: the red channel rises left to right across the sheet
            ramp = np.broadcast_to(np.linspace(0, 255, rgba.shape[1]).astype(np.uint8), rgba.shape[:2])
            rgba[..., 0] = np.where(hole, ramp, rgba[..., 0])
    output = BytesIO()
    Image.fromarray(rgba[..., :3]).save(output, format='PNG')
    b64 = base64.b64encode(output.getvalue()).decode()
    usage = {'input_tokens': 100, 'output_tokens': 100, 'input_tokens_details': {'image_tokens': 20, 'text_tokens': 80}}
    if kwargs.get('stream'):                                             # the edit streams its partial pictures
        return [{'type': 'image_edit.partial_image', 'partial_image_index': 0, 'b64_json': b64[:64]},
                {'type': 'image_edit.completed', 'b64_json': b64, 'usage': usage}]
    return {'data': [{'b64_json': b64}], 'usage': usage}


@pytest.fixture
def execution(tmp_path, settings, monkeypatch):
    from django.contrib.auth import get_user_model
    from django.test import Client
    from apps.pipeline import tasks
    from apps.pipeline.models import Round, RoundMaster
    from apps.pipeline.services import round_files_gate as job, round_flow as flow, round_designer as round_ideas_brief
    settings.ROUND_ARTIFACT_ROOT = tmp_path / 'rounds'
    settings.RESCUE_SPEND_ROOT = tmp_path / 'spend'
    settings.SECURE_SSL_REDIRECT = False
    settings.IMAGE_MODEL = 'gpt-image-2'
    source, _, inspection = picture(tmp_path)
    inspection['stand']['bottles'] = [{'row': r, 'column': c, 'box_px': [10 + c * 20, 5, 25 + c * 20, 100],
                                       'shade_field': 'shade_0' if r == 0 else None} for r in range(2) for c in range(2)]
    inspection['stand'].update(rows=2, columns=2, count=4)
    inspection.update(unprinted_faces=[{'face': 'back', 'reason': 'Not visible.'}], notes=['Four products.'])
    brief = dict(round_ideas_brief.gloss_brief(), flow=round_ideas_brief.DESIGNER_FLOW)   # only the designer flow builds files (2026-10-29)
    brief['stand'].update(count=4, layout={'rows': 2, 'columns': 2},
                          dimensions_mm={'width': 50, 'depth': 40, 'height': 160, 'board_thickness': 1.5})
    owner = get_user_model().objects.create_superuser(username='faces-owner-' + uuid4().hex,
                                                      email='faces@example.invalid', password='fixture-password')
    record = Round.objects.create(slug='faces-fixture-' + uuid4().hex, request_key=uuid4().hex, created_by=owner,
                                  product_brief=brief, state='complete', current_step='pick', budget_usd=10,
                                  pick={'id': 'C2', 'reason': 'Keep the dial.'})
    root = flow.round_root(record)
    relative = 'designs/C2/raw.png'
    pick = root / relative
    pick.parent.mkdir(parents=True)
    pick.write_bytes(source.read_bytes())
    record.artifacts = {'pick_page': {'schema': 'product_stand_publication/1', 'order': ['C2'],
                        'candidates': {'C2': {'id': 'C2', 'picture': relative, 'picture_sha256': sha(pick),
                                              'idea': 'A dial.', 'directory': 'designs/C2'}},
                        'files': {relative: sha(pick)}}}
    record.save()
    flow.write_json(root / 'handoff.json', {
        'schema': 'product_stand_handoff/1', 'contract': round_ideas_brief.CONTRACT, 'id': 'C2', 'picture': relative,
        'picture_sha256': sha(pick), 'size_px': inspection['image_size_px'], 'reason': record.pick['reason'],
        'source_round': record.pk, 'execution': 'The picked picture is the design intent: execution draws each flat face front-on as an edit guided by it.'})
    eye_replies, prompts, pending = {}, [], []

    def text_create(**kwargs):
        prompt = kwargs['messages'][0]['content'][-1]['text']
        prompts.append(prompt)
        if 'Read this one picked picture for print-file extraction.' in prompt:
            return text_reply(deepcopy(inspection))
        assert prompt.startswith('You are the designer\'s eye, advising') and kwargs['output_config'] == {'effort': 'low'}
        for label, verdict in eye_replies.items():
            if 'this face: ' + label + '.' in prompt:
                return text_reply(verdict)
        return text_reply({'verdict': 'pass', 'findings': []})

    text = Mock(name='unpaid text provider')
    text.messages.create.side_effect = text_create
    edit = Mock(name='unpaid image provider', side_effect=drawn_reply)
    images = SimpleNamespace(images=SimpleNamespace(edit=edit))
    original = job.FilesContext
    monkeypatch.setattr(job, 'FilesContext', lambda build, step: original(build, step, text_client=text,
                                                                          image_client=images, native=False))
    monkeypatch.setattr(tasks.run_round_files, 'delay', pending.append)
    client = Client()
    client.force_login(owner)

    def drain(*, limit=40):
        statuses = []
        while pending and len(statuses) < limit:
            build_id = pending.pop(0)
            before = edit.call_count + text.messages.create.call_count
            statuses.append(tasks.run_round_files(build_id)['status'])
            assert edit.call_count + text.messages.create.call_count - before <= 1     # one paid call per delivery
        return RoundMaster.objects.get(round=record), statuses

    return SimpleNamespace(record=record, owner=owner, root=root, edit=edit, text=text, prompts=prompts,
                           eye_replies=eye_replies, pending=pending, drain=drain, client=client, brief=brief,
                           inspection=inspection)


def test_the_front_strips_line_is_one_word_space_apart(tmp_path):
    from apps.pipeline.services.round_files_export import glyph_metrics
    from apps.pipeline.services.round_files_export import PT, measure_type
    rows = faces.product_line({'product_latin': 'Lip Gloss', 'product_arabic': 'ملمع شفاه'}, 50, 10, 4, 100,
                              colour='#D5AF59', foil=True, name='front')
    em = rows[0]['size_pt'] / PT
    space = glyph_metrics(' ', 'latin')['advance_em']
    inks = [measure_type(row)['ink_box_mm'] for row in rows]
    for left, right in zip(inks, inks[1:]):
        assert space * em <= right[0] - left[2] <= (space + .15) * em          # as typed: one word space, plus bearings



def test_a_redraw_note_reaches_the_drawing_only_when_it_is_about_the_art(tmp_path):
    _, brief, _ = picture(tmp_path)
    face = faces.face_geometry('cap', brief, faces.die_of(stand_geometry(tmp_path)))
    art, withheld = faces.owner_note('  Make the engraved dial smaller,\n with more gold around it  ' + 'x' * 300)
    assert withheld is None and '\n' not in art and len(art) == faces.NOTE_MAX
    words = faces.prompt('cap', face, note=art, previous=True)
    assert 'Image 3 is your previous drawing' in words and art in words and words.endswith(faces.NO_WORDS)
    assert faces.owner_note('Make BBROSE bigger')[1] and faces.owner_note('Set ملمع شفاه lower')[1]


# --- the gate: the build, the owner's Accept and Redraw, "Make my files" ------------------------------------------------

def page(execution):
    from django.urls import reverse
    return execution.client.get(reverse('dashboard:product_round_files', args=[execution.record.pk]))


def post(execution, name, *args, **data):
    from django.urls import reverse
    return execution.client.post(reverse('dashboard:' + name, args=[execution.record.pk, *args]), data)


def board_of(execution):
    from apps.pipeline.models import RoundMaster
    build = RoundMaster.objects.get(round=execution.record)
    return build, build.steps['faces']['board']


@pytestmark_db
def test_every_face_is_drawn_previewed_and_advised_then_waits_for_the_owner(execution):
    from apps.pipeline.services import round_files_gate as files_flow, round_files_gate as job
    execution.eye_replies['Bottle front'] = {'verdict': 'needs_attention', 'findings': ['The band shows a smear.']}
    files_flow.start(execution.record.pk, execution.owner)
    build, statuses = execution.drain()
    assert build.state == 'awaiting', (build.error, statuses)
    assert execution.edit.call_count == 3                     # the flat die painted once; one edit each, bottle and cap
    first = execution.edit.call_args_list[0].kwargs
    assert first['prompt'].startswith('Image 1 is a flat die') and len(first['image']) == 2 and first['mask']
    eyes = [p for p in execution.prompts if p.startswith("You are the designer's eye")]
    assert len(eyes) == 2 and all('advising the owner' in p for p in eyes)          # the drawn faces only
    build, board = board_of(execution)
    assert set(board) == set(faces.FACES) and all(row['state'] == 'drawn' for row in board.values())
    folder = files_flow.root(build)
    claim = json.loads((folder / 'flat' / 'claim.json').read_text())
    assert claim['style']['sha256'] == build.inputs['picture_sha256'] and claim['budget_usd'] == 10
    painting = faces.current_painting(folder)
    proof = painting['proof']
    assert proof['registration']['best_shift_px'] == [2, 2] and proof['outside']['differing_from_template'] == 0
    assert max(proof['pdf'][layer]['max_mm'] for layer in ('CUT', 'CREASE', 'ARTWORK')) < .01
    assert {row['kind'] for row in painting['continuity']['seams']} >= {'crease', 'folded corner'}
    geometry = json.loads((folder / 'stand.json').read_text())
    for key, row in board.items():
        entry = row['drawings'][-1]
        assert entry['n'] == 1 and entry['preview'] and entry['size_mm']
        if faces.stand_face(key):
            upright, _frame, _box = faces.painted_face(painting, key, geometry)
            assert entry['source'] == 'flat' and entry['eye']['state'] == 'none'
            assert (np.asarray(Image.open(folder / entry['face'])) == upright).all(), key   # cut straight from it
            continue
        raw = np.asarray(Image.open(folder / 'faces' / key / 'drawings' / '1' / 'call' / 'raw.png').convert('RGB'))
        record = json.loads((folder / entry['record']).read_text())
        x0, y0, x1, y1 = record['frame_px']
        assert (np.asarray(Image.open(folder / entry['face'])) == raw[y0:y1, x0:x1]).all(), key   # nothing erased
    bottle = board['bottle']['drawings'][-1]['eye']
    assert bottle['state'] == 'done' and bottle['verdict'] == 'needs_attention', bottle          # advice, never a block
    assert board['bottle']['state'] == 'drawn'
    html = page(execution).content.decode()
    assert html.count('>Accept<') == 8 and html.count('>Redraw<') == 8 and 'The band shows a smear.' in html
    assert 'Your stand, flat' in html and 'From your flat design' in html and 'drawing, not a render' in html
    assert 'Make my files' in html and 'disabled' in html
    spent = job.scoped_spend(build)
    assert spent['budget_usd'] == 10 and spent['calls'] == 1 + 3 + 2 and spent['held_usd'] == 0


@pytestmark_db
def test_accepting_every_face_opens_make_my_files_and_no_review_follows(execution):
    from apps.pipeline.services import round_files_export as export, round_files_gate as files_flow
    files_flow.start(execution.record.pk, execution.owner)
    execution.drain()
    build, board = board_of(execution)
    keys = list(board)
    for key in keys[:-1]:
        assert post(execution, 'product_round_files_accept', key, drawing=1).status_code == 302
    assert post(execution, 'product_round_files_make').status_code == 400        # one face still waits
    assert post(execution, 'product_round_files_accept', keys[-1], drawing=2).status_code == 400   # not its drawing
    assert post(execution, 'product_round_files_accept', keys[-1], drawing=1).status_code == 302
    assert 'Make my files</button>' in page(execution).content.decode()
    texts, edits = execution.text.messages.create.call_count, execution.edit.call_count
    assert post(execution, 'product_round_files_make').status_code == 302
    build, statuses = execution.drain()
    assert build.state == 'complete', (build.error, statuses)
    assert (execution.text.messages.create.call_count, execution.edit.call_count) == (texts, edits)   # no review after
    folder = files_flow.root(build)
    with zipfile.ZipFile(folder / 'files.zip') as archive:
        assert sorted(n for n in archive.namelist() if n.endswith('.ai')) == ['bottle-front.ai', 'cap.ai', 'stand.ai']
    stand = json.loads((folder / 'revisions' / '1' / 'stand.export.json').read_text())
    assert stand['readback']['pdf_compatible_holds'] and stand['readback']['checks']['die_guides_locked_nonprinting']
    # English only (the owner, 2026-10-29): no Arabic on the stand
    assert {row['copy'] for row in stand['type']} == {'Rose Glass', 'Fig Nectar', 'Ember Glow', 'BBROSE'}
    readme = (folder / 'README.md').read_text()
    assert 'Accepted by the owner, face by face' in readme and readme.count('accepted 20') == 8
    assert 'the stand designed flat' in readme
    with fitz.open(folder / 'revisions' / '1' / 'die' / 'die.pdf') as doc:
        assert doc[0].get_images()                                       # the flat raster on the die's ARTWORK layer
    html = page(execution).content.decode()
    assert '>Download<' in html and 'Your files are made' in html
    # the preview the owner accepted is the placement the files wrote
    header = json.loads((folder / 'faces' / 'header' / 'previews' / '1' / 'preview-header-1.export.json').read_text())
    assert {row['copy'] for row in header['type']} == {'Rose Glass', 'Fig Nectar', 'Ember Glow', 'BBROSE'}   # English only


@pytestmark_db
def test_a_redraw_is_one_edit_with_its_note_and_the_other_faces_keep_their_accept(execution):
    from apps.pipeline.services import round_files_gate as files_flow
    files_flow.start(execution.record.pk, execution.owner)
    execution.drain()
    assert post(execution, 'product_round_files_accept', 'header', drawing=1).status_code == 302
    edits = execution.edit.call_count
    assert post(execution, 'product_round_files_redraw', 'front', note='Keep both medallions whole inside the strip.'
                ).status_code == 302
    build, statuses = execution.drain()
    assert build.state == 'awaiting', (build.error, statuses)
    assert execution.edit.call_count - edits == 1
    call = execution.edit.call_args_list[-1].kwargs
    assert call['prompt'].startswith('Image 1 is our flat die') and 'the FRONT PANEL and its bleed' in call['prompt']
    assert 'Keep both medallions whole' in call['prompt'] and call['prompt'].endswith(faces.FLAT_NO_WORDS)
    assert len(call['image']) == 2                       # the flat art with only this face open, the style reference
    build, board = board_of(execution)
    assert board['front']['drawing'] == 2, board['front'].get('error')
    assert [d['n'] for d in board['front']['drawings']] == [1, 2]
    assert board['front']['state'] == 'drawn' and board['header']['state'] == 'accepted'
    assert board['front']['drawings'][-1]['source'] == 'repainted'
    folder = files_flow.root(build)
    from apps.dielines.exporters import counter_display_files as cdf
    geometry = json.loads((folder / 'stand.json').read_text())
    masks = cdf.flat_masks(faces.die_of(geometry), json.loads((folder / 'flat' / 'template.json').read_text())['frame'])
    front = masks['owner'] == masks['names'].index('front panel') + 1
    after = np.asarray(Image.open(faces.current_painting(folder)['flat']))
    before = np.asarray(Image.open(folder / 'flat' / 'paintings' / '1' / 'flat.png'))
    assert (after[~front] == before[~front]).all() and not (after[front] == before[front]).all()   # that face only
    assert post(execution, 'product_round_files_redraw', 'cap', note='Make the BBROSE wordmark bigger').status_code == 302
    execution.drain()
    call = execution.edit.call_args_list[-1].kwargs
    assert 'BBROSE' not in call['prompt'] and len(call['image']) == 2    # a note about the words is never drawn
    _, board = board_of(execution)
    assert 'not sent to the drawing' in board['cap']['drawings'][-1]['note_withheld']


@pytestmark_db
def test_one_face_failing_never_blocks_another_and_a_lost_call_is_closed_not_bought_twice(execution):
    from apps.pipeline.services import round_files_gate as files_flow, round_files_gate as job, spend_reservation as spend
    plain = execution.edit.side_effect

    def edit(**kwargs):
        if 'This is the front of the bottle' in kwargs['prompt']:
            raise ConnectionError('connection dropped')                    # no HTTP status: outcome unknown
        return plain(**kwargs)
    execution.edit.side_effect = edit
    files_flow.start(execution.record.pk, execution.owner)
    build, statuses = execution.drain()
    assert build.state == 'awaiting', (build.error, statuses)
    _, board = board_of(execution)
    assert board['bottle']['state'] == 'failed' and board['bottle']['drawings'] == []
    assert all(row['state'] == 'drawn' for key, row in board.items() if key != 'bottle')
    with spend._connect() as db:
        lost = dict(db.execute("SELECT * FROM calls WHERE operation LIKE '%image/face/bottle/1'").fetchone())
    assert lost['state'] == 'outcome_unknown' and lost['accounted'] == lost['reserved']   # closed, still counted
    assert json.loads(lost['usage'])['checked'] is False
    folder = files_flow.root(build)
    assert (folder / 'faces' / 'bottle' / 'drawings' / '1' / 'call' / 'image-call.lost.json').exists()
    html = page(execution).content.decode()
    assert 'outcome is unknown' in html and 'Press Redraw' in html and 'ConnectionError' not in html
    attempts = execution.edit.call_count
    execution.pending.append(build.pk)
    execution.drain()
    assert execution.edit.call_count == attempts                          # never sent twice on its own
    execution.edit.side_effect = plain
    assert post(execution, 'product_round_files_redraw', 'bottle').status_code == 302
    build, _ = execution.drain()
    _, board = board_of(execution)
    assert board['bottle']['state'] == 'drawn' and board['bottle']['drawing'] == 2
    spent = job.scoped_spend(build)
    # its measured hold stays counted (2026-10-29: each face's set-aside is its measured cost, not a flat $0.35)
    assert 0.2 < spent['unknown_usd'] < 0.35 and spent['held_usd'] == 0


@pytestmark_db
def test_a_started_call_with_no_reply_is_checked_once_and_closed_on_the_next_delivery(execution):
    from apps.pipeline.models import RoundMaster
    from apps.pipeline.services import round_files_gate as files_flow, spend_reservation as spend

    class Killed(BaseException):
        """The worker dies mid-call: the request is saved as started, nothing else."""
    plain = execution.edit.side_effect

    def crash(**kwargs):
        if 'This is the front face of the gold square cap' in kwargs['prompt']:
            raise Killed()
        return plain(**kwargs)
    execution.edit.side_effect = crash
    files_flow.start(execution.record.pk, execution.owner)
    with pytest.raises(Killed):
        execution.drain()
    execution.edit.side_effect = plain
    build = RoundMaster.objects.get(round=execution.record)
    assert build.steps['faces']['board']['cap']['state'] == 'drawing'
    RoundMaster.objects.filter(pk=build.pk).update(state='queued')
    execution.pending[:] = [build.pk]
    calls = execution.edit.call_count
    build, statuses = execution.drain()
    _, board = board_of(execution)
    assert board['cap']['state'] == 'failed' and 'outcome is unknown' in files_flow_error(board['cap'])
    with spend._connect() as db:
        state = db.execute("SELECT state FROM calls WHERE operation LIKE '%image/face/cap/1'").fetchone()[0]
    assert state == 'outcome_unknown' and build.state == 'awaiting'
    assert execution.edit.call_count - calls == 0                          # every other face is done; the cap not re-sent


def files_flow_error(row):
    from apps.pipeline.services import round_files_gate as gate
    return gate.plain_error(row['error'])


@pytestmark_db
def test_a_face_path_build_moves_onto_the_gate_with_its_drawings_and_the_eyes_last_looks(execution, tmp_path):
    """Round 3 on 2026-10-28: header, bottle and cap passed their looks; the front's repair and the walls' drawings
    needed attention; a front edit was held with its outcome unknown. Moved onto the gate at $0, no call."""
    import shutil
    from apps.pipeline.models import RoundMaster
    from apps.pipeline.services import round_files_gate as files_flow, round_files_gate as gate, spend_reservation as spend
    files_flow.start(execution.record.pk, execution.owner)
    build, _ = execution.drain()
    folder = files_flow.root(build)
    # the face path's layout: faces/<key>/{face.png, record.json}, the front's repair, the review's looks
    for key in gate.FACE_PATH_KEYS:
        source = folder / 'faces' / key / 'drawings' / '1'
        target = folder / 'faces' / key / ('repair' if key == 'front' else '')
        target.mkdir(parents=True, exist_ok=True)
        for name in ('face.png', 'reference.png', 'template.png'):
            shutil.copy(source / name if (source / name).exists() else source / 'face.png', target / name)
        record = json.loads((source / 'record.json').read_text())
        record.update(face=str(target / 'face.png'), template=dict(record['template'], template=str(target / 'template.png')),
                      reference=dict(record.get('reference', {}), path=str(target / 'reference.png')))
        (target / 'record.json').write_text(json.dumps(record))
        shutil.rmtree(folder / 'faces' / key / 'drawings')
        shutil.rmtree(folder / 'faces' / key / 'previews')
    (folder / 'review').mkdir()
    for key, looks in {'header': ['pass'], 'bottle': ['pass'], 'cap': ['pass'], 'side': ['needs_attention'],
                       'back': ['needs_attention'], 'front': ['needs_attention', 'needs_attention']}.items():
        for n, verdict in enumerate(looks, 1):
            payload = {'verdict': verdict, 'findings': [] if verdict == 'pass' else ['%s look %d note' % (key, n)]}
            (folder / 'review' / ('%s-%d.json' % (key, n))).write_text(json.dumps({'status': 'complete', 'payload': payload}))
    held = folder / 'faces' / 'front' / 'call'
    held.mkdir(parents=True)
    rid = spend.reserve('openai', 'files/%s/image/face/front' % execution.record.slug, 'gpt-image-2', 0.35, 'x')
    (held / 'image-call.request.json').write_text(json.dumps({'reservation_id': rid, 'started_attempts': [0]}))
    steps = {name: {'state': 'waiting', 'attempts': 0, 'dispatches': 0, 'history': [], 'result': {}}
             for name in files_flow.FACE_PATH_STEPS}
    steps['read'], steps['stand'] = build.steps['read'], build.steps['stand']
    steps['faces']['state'] = 'failed'
    RoundMaster.objects.filter(pk=build.pk).update(steps=steps, current_step='faces', state='failed',
                                                   error='ValueError: Prior face edit outcome is unknown')
    edits, texts = execution.edit.call_count, execution.text.messages.create.call_count
    html = page(execution).content.decode()                               # the page nudges it onto the gate
    build, statuses = execution.drain()
    assert build.state == 'awaiting', (build.error, statuses)
    assert (execution.edit.call_count, execution.text.messages.create.call_count) == (edits, texts)   # $0
    _, board = board_of(execution)
    assert {key: row['state'] for key, row in board.items()} == {key: 'drawn' for key in gate.FACE_PATH_KEYS}
    assert {key for key, row in board.items() if row['suggested']} == {'front', 'side', 'back'}
    front = board['front']['drawings'][0]
    assert front['face'] == 'faces/front/repair/face.png' and front['eye']['findings'] == ['front look 2 note']
    assert front['eye']['state'] == 'carried' and front['preview']
    with spend._connect() as db:
        assert db.execute('SELECT state FROM calls WHERE id=?', (rid,)).fetchone()[0] == 'outcome_unknown'
    claim = json.loads((folder / 'gate-claim.json').read_text())
    assert claim['lost_calls'][0]['reservation_id'] == rid and claim['previous_current_step'] == 'faces'
    html = page(execution).content.decode()
    assert html.count('>Accept<') == 6 and html.count('Redraw suggested') == 3


@pytestmark_db
def test_a_stream_with_no_completed_image_is_lost_and_never_sent_again(execution):
    """Round 3, 2026-10-28: two edits were cut at 205–206 s by the tunnel; an edit now streams, and a stream that ends
    with no completed image is a lost call — checked once, closed, its events logged, never sent twice."""
    from apps.pipeline.services import round_files_gate as files_flow, spend_reservation as spend
    plain = execution.edit.side_effect

    def edit(**kwargs):
        assert kwargs['stream'] is True and kwargs['partial_images'] == 2
        if 'This is the front of the bottle' in kwargs['prompt']:
            return plain(**kwargs)[:1]                                    # the partial picture, then nothing
        return plain(**kwargs)
    execution.edit.side_effect = edit
    files_flow.start(execution.record.pk, execution.owner)
    build, statuses = execution.drain()
    assert build.state == 'awaiting', (build.error, statuses)
    _, board = board_of(execution)
    assert board['bottle']['state'] == 'failed' and 'outcome is unknown' in files_flow_error(board['bottle'])
    assert all(row['state'] == 'drawn' for key, row in board.items() if key != 'bottle')
    call = files_flow.root(build) / 'faces' / 'bottle' / 'drawings' / '1' / 'call'
    log = json.loads((call / 'image-call.stream.json').read_text())
    assert log['completed'] is False and [row['type'] for row in log['events']] == ['image_edit.partial_image']
    with spend._connect() as db:
        state = db.execute("SELECT state FROM calls WHERE operation LIKE '%image/face/bottle/1'").fetchone()[0]
    assert state == 'outcome_unknown'
    attempts = execution.edit.call_count
    execution.pending.append(build.pk)
    execution.drain()
    assert execution.edit.call_count == attempts                          # never sent twice on its own


@pytestmark_db
def test_a_lost_painting_waits_for_the_owner_and_a_redraw_paints_the_die_again(execution):
    from apps.pipeline.services import round_files_gate as files_flow, round_files_gate as gate
    plain, lost = execution.edit.side_effect, []

    def edit(**kwargs):
        if kwargs['prompt'].startswith('Image 1 is a flat die') and not lost:
            lost.append(1)
            raise ConnectionError('connection dropped')                    # the tunnel's cut: no HTTP status
        return plain(**kwargs)
    execution.edit.side_effect = edit
    files_flow.start(execution.record.pk, execution.owner)
    build, statuses = execution.drain()
    assert build.state == 'awaiting', (build.error, statuses)
    _, board = board_of(execution)
    stand = [key for key in faces.FACES if faces.stand_face(key)]
    assert all(board[key]['state'] == 'failed' and board[key]['error'] == gate.PAINTING_LOST for key in stand)
    assert board['bottle']['state'] == 'drawn' and board['cap']['state'] == 'drawn'
    html = page(execution).content.decode()
    assert 'Press Redraw on a stand face to paint the die again.' in html and 'being made' not in html
    assert 'the template sheet the painting is made on' in html                          # the die, drawn first
    paintings = [c for c in execution.edit.call_args_list if c.kwargs['prompt'].startswith('Image 1 is a flat die')]
    execution.pending.append(build.pk)
    execution.drain()
    assert len([c for c in execution.edit.call_args_list
                if c.kwargs['prompt'].startswith('Image 1 is a flat die')]) == len(paintings) == 1   # not on its own
    assert post(execution, 'product_round_files_redraw', 'header', note='Keep the dial whole on the leaf.').status_code == 302
    build, statuses = execution.drain()
    assert build.state == 'awaiting', (build.error, statuses)
    second = [c.kwargs['prompt'] for c in execution.edit.call_args_list if c.kwargs['prompt'].startswith('Image 1 is a flat die')]
    assert len(second) == 2 and 'The owner asks: "Keep the dial whole on the leaf."' in second[-1]   # the note goes with it
    _, board = board_of(execution)
    assert all(board[key]['state'] == 'drawn' and board[key]['drawings'][-1]['source'] == 'flat' for key in stand)
    claim = json.loads((files_flow.root(build) / 'flat' / 'claim.json').read_text())
    assert claim['attempt'] == 2 and claim['previous_attempts'][0]['attempt'] == 1
    assert faces.current_painting(files_flow.root(build))['n'] == 2


def test_ciede2000_reproduces_sharma_wu_dalal():
    """The face builder's CIEDE2000 (moved with it from lid_master) as published (Sharma, Wu and Dalal 2005, test pairs 1, 2, 3, 7, 9, 23, 31)."""
    pairs = [((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485), 2.0425),
             ((50.0, 3.1571, -77.2803), (50.0, 0.0, -82.7485), 2.8615),
             ((50.0, -1.3802, -84.2814), (50.0, 0.0, -82.7485), 1.0000),
             ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
             ((22.7233, 20.0904, -46.6940), (23.0331, 14.9730, -42.5619), 2.0373),
             ((90.8027, -2.0831, 1.4410), (91.1528, -1.6435, 0.0447), 1.4441),
             ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082)]
    for a, b, want in pairs:
        assert abs(float(faces.delta_e00(np.array(a), np.array(b))) - want) < 1e-3


def test_a_malformed_usage_reply_is_a_failed_lookup_never_nothing_billed(monkeypatch):
    """§R4 (2026-10-29): the one check of a lost call reads every field of the provider's usage reply. A reply without
    its data, a bucket without its results or a row without its count is a failed lookup, so the hold stays counted;
    only a whole count of zero images reads as not billed."""
    from contextlib import contextmanager
    from apps.pipeline.services import round_files_gate as gate
    import httpx

    class Rows(list):                                   # the call's start, and none of the app's own calls beside it
        def fetchone(self):
            return ('2026-10-29T01:00:00+00:00',)

    @contextmanager
    def ledger():
        yield SimpleNamespace(execute=lambda *a: Rows())
    monkeypatch.setattr(gate.spend, '_connect', ledger)
    monkeypatch.setattr(gate.settings, 'OPENAI_ADMIN_KEY', 'admin-key-fixture', raising=False)

    def reply_of(payload):
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)
    for payload in ({}, {'data': [{}]}, {'data': [{'results': [{}]}]}, {'data': [{'results': [{'images': 'one'}]}]}):
        monkeypatch.setattr(httpx, 'get', lambda *a, payload=payload, **k: reply_of(payload))
        check = gate.provider_check('openai', 'reservation-fixture')
        assert check['checked'] is False and check['billed'] is None, payload
    monkeypatch.setattr(httpx, 'get', lambda *a, **k: reply_of({'data': [{'results': []}, {'results': [{'images': 0}]}]}))
    assert gate.provider_check('openai', 'reservation-fixture') == {
        'checked': True, 'billed': False, 'images_in_window': 0, 'own_images_in_window': 0,
        'why': 'OpenAI\'s image usage in the call\'s window, beyond the app\'s own other calls there'}
    monkeypatch.setattr(httpx, 'get', lambda *a, **k: reply_of({'data': [{'results': [{'images': 1}]}]}))
    assert gate.provider_check('openai', 'reservation-fixture')['billed'] is True


def test_the_files_page_says_when_the_brief_cannot_be_read(monkeypatch):
    """§R4 (2026-10-29): the reading notes never drop the warning about unconfirmed copy in silence — a brief that
    cannot be read is said to leave it unknown."""
    from apps.pipeline.services import round_files_gate as gate

    def unreadable(build):
        raise OSError('gone')
    monkeypatch.setattr(gate, 'files_brief', unreadable)
    notes = gate.reading_notes(SimpleNamespace(steps={}))
    assert notes == ['The brief could not be read (OSError), so whether any copy was added without your confirmation '
                     'is unknown.']



@pytestmark_db
def test_a_stand_solved_before_the_sightline_fix_is_solved_again_inside_its_size(execution):
    """The owner's goal of 2026-10-29: a build whose stand was solved before the solver moved its rows inside the
    ruled size (no sightline revision on its record) is solved again at $0 under the build's lock; the old stand moves
    to superseded/ and the claim says from which revision to which; a stand already on the revision is left alone."""
    from apps.dielines.geometry import counter_display
    from apps.pipeline.services import round_files_gate as job
    job.start(execution.record.pk, execution.owner)
    build, _ = execution.drain()
    folder = job.root(build)
    stand = json.loads((folder / 'stand.json').read_text())
    assert stand['sightline_revision'] == counter_display.SIGHTLINE_REVISION
    assert job.restand(build) is None                                   # on the revision: nothing to do
    stand.pop('sightline_revision')
    (folder / 'stand.json').write_text(json.dumps(stand))
    assert job.restand(build) is not None
    again = json.loads((folder / 'stand.json').read_text())
    assert again['sightline_revision'] == counter_display.SIGHTLINE_REVISION
    assert (folder / 'superseded' / 'stand-sightline-None' / 'stand.json').exists()
    claim = json.loads((folder / 'restand-claim.json').read_text())
    assert claim['sightline_revision'] == {'from': None, 'to': counter_display.SIGHTLINE_REVISION}
    assert claim['sightlines_passed'] == again['sightlines']['passed']
    assert claim['header_clear'] == again['sightlines']['header_clear']
    # the flat design was painted on the old die: it goes with the old stand, and the stand faces wait for a new one
    assert claim['flat_moved'] and not (folder / 'flat').exists()
    assert (folder / 'superseded' / 'stand-sightline-None' / 'flat' / 'claim.json').exists()
    rows = build.steps['faces']['board']
    assert all(rows[key]['state'] == 'failed' and rows[key]['error'] == job.RESTAND_FLAT
               for key in faces.FACES if faces.stand_face(key))


@pytestmark_db
def test_stand_faces_are_drawn_per_panel_at_300_ppi_checked_against_the_painting_and_composed_at_300(execution,
                                                                                                    monkeypatch):
    """The owner's goal of 2026-10-29: the whole-die painting is the idea; each stand face is then drawn at 300 PPI on
    its own outline (image 1 its panel sheet, image 2 its crop of the painting), checked against it, every edit counted
    against the claim's cap before it is sent; "Make my files" composes the stand at 300 PPI from those drawings."""
    from apps.pipeline.services import round_files_gate as job
    # every face painted on its panel (no plain faces named: the board-at-$0 rule has its own test)
    monkeypatch.setattr(job, 'FLAT_STYLE', dict(job.FLAT_STYLE, panels='full', plain_faces=[]))
    job.start(execution.record.pk, execution.owner)
    build, statuses = execution.drain(limit=60)
    assert build.state == 'awaiting', (build.error, statuses)
    stand_keys = [key for key in faces.FACES if faces.stand_face(key)]
    assert execution.edit.call_count == 1 + len(stand_keys) + 2      # the die once, each stand face, bottle and cap
    panels = [call.kwargs for call in execution.edit.call_args_list
              if 'one printed face of a folding cardboard counter stand' in call.kwargs['prompt']]
    assert len(panels) == len(stand_keys)
    for kwargs in panels:
        assert faces.is_panel_size(kwargs['size']) and len(kwargs['image']) == 2 and kwargs['mask']
        # the back panel first, then the walls following its drawing (2026-10-29); every other face its painting crop
        follows = 'Image 2 is the stand\'s back panel as already drawn' in kwargs['prompt']
        assert follows or 'Image 2 is this same face as our painting of the whole flat die shows it' in kwargs['prompt']
    assert sum('Image 2 is the stand\'s back panel as already drawn' in kwargs['prompt'] for kwargs in panels) == len(
        [key for key in stand_keys if key in faces.WALL_PATTERN])
    build, board = board_of(execution)
    folder = job.root(build)
    claim = json.loads((folder / 'flat' / 'claim.json').read_text())
    assert claim['panels'] == 'full' and sorted(claim['operations']) == sorted('face/%s/1' % key for key in stand_keys)
    assert job.claim_spend(build, claim) <= claim['budget_usd']
    for key in stand_keys:
        entry = job.current(board[key])
        record = json.loads((folder / entry['record']).read_text())
        assert entry['source'] == 'panel' and record['native_ppi'] >= 300 and record['template']['px_per_mm'] >= faces.K
        check = record['against_painting']
        assert check['bar'] == faces.AGAINST_BAR and not check['flagged'] and check['median'] < 5, (key, check)
        assert 'ΔE00 median' in entry['eye']['why']
    for key in board:
        assert post(execution, 'product_round_files_accept', key, drawing=1).status_code == 302
    assert post(execution, 'product_round_files_make').status_code == 302
    build, statuses = execution.drain(limit=60)
    assert build.state == 'complete', (build.error, statuses)
    outputs = json.loads((folder / 'revisions' / '1' / 'outputs.json').read_text())
    placed = [row for row in outputs['placements'].values()]
    assert len(placed) == len(stand_keys)
    assert all(row['source'] == 'panel' and row['native_ppi'] >= 300 and row['composed_ppi'] == 300.0 for row in placed)
    stand = next(spec for spec in outputs['specs'] if spec['id'] == 'stand')
    raster = Image.open(stand['artwork'][0]['path'])
    x0, y0, x1, y1 = stand['artwork'][0]['box_mm']
    assert raster.width / (x1 - x0) == pytest.approx(faces.K, rel=0.01)     # 300 PPI at 1:1 on the die


def test_a_panel_canvas_keeps_to_the_models_range_and_its_hold_scales():
    """Every panel canvas: both sides multiples of 16, aspect 1:3–3:1, 0.65–3.69 MP, at least 300 PPI; a thin strip is
    padded, a face too large for one edit refused; the hold is the measured one scaled by the pixels."""
    for W, H in ((113, 84.2), (113, 24.2), (88, 140.3), (113, 140.3), (21, 36)):
        k, (cw, ch), (fw, fh) = faces.panel_canvas(W, H)
        assert faces.is_panel_size('%dx%d' % (cw, ch)) and k >= faces.K and fw <= cw and fh <= ch
    with pytest.raises(ValueError, match='does not fit one 300 PPI edit'):
        faces.panel_canvas(200, 200)
    # the hold is the measured cost (the owner, 2026-10-29): every round-4 face edit settled under its own hold, on its
    # canvas, quality and input pictures — the ledger's numbers
    for size, quality, inputs, settled in (('1408x832', 'high', 2, 0.1535), ('1408x848', 'high', 2, 0.1574),
                                           ('1408x1312', 'high', 2, 0.2773), ('1408x1312', 'high', 3, 0.2914),
                                           ('1024x1536', 'medium', 2, 0.0769)):
        w, h = (int(v) for v in size.split('x'))
        hold = faces.edit_hold(size, quality, [(w, h)] * inputs, 'x' * 2400)
        assert settled < hold < 1.3 * settled + 0.03, (size, quality, hold)
    assert faces.edit_hold('1408x1312', 'medium') < 0.4 * faces.edit_hold('1408x1312', 'high')
    assert faces.edit_hold('1408x1312') < 0.4111                                 # the flat hold it replaces
    assert not faces.is_panel_size('1500x1000') and not faces.is_panel_size('3200x1600')


@pytestmark_db
def test_the_bottle_and_cap_are_painted_on_their_own_flat_nets_die_first(execution, monkeypatch):
    """The owner's goal of 2026-10-29: the bottle and the cap follow the stand's method — their printed sides laid out
    flat by our engine first (the bottle's four body sides in a strip, the cap's four sides and its top), each net
    painted with one edit at 300 PPI or more, its die applied again; the front cut for the files, the real sides in the
    wrap view; each edit counted against the claim's cap."""
    from apps.pipeline.services import round_files_gate as job
    monkeypatch.setattr(job, 'FLAT_STYLE', dict(job.FLAT_STYLE, product_nets=True))
    job.start(execution.record.pk, execution.owner)
    build, statuses = execution.drain(limit=60)
    assert build.state == 'awaiting', (build.error, statuses)
    nets = [call.kwargs for call in execution.edit.call_args_list if call.kwargs['prompt'].startswith('Image 1 is a flat net')]
    assert len(nets) == 2 and all(kwargs['size'] in ('1536x1024', '1024x1536') for kwargs in nets)
    build, board = board_of(execution)
    folder = job.root(build)
    claim = json.loads((folder / 'flat' / 'claim.json').read_text())
    assert claim['product_nets'] and {'face/bottle/1', 'face/cap/1'} <= set(claim['operations'])
    dims = execution.brief['dimensions_mm']
    for key, sides in (('bottle', 4), ('cap', 5)):
        entry = job.current(board[key])
        record = json.loads((folder / entry['record']).read_text())
        assert entry['source'] == 'net' and record['native_ppi'] >= 300
        assert len(record['net']['sides']) == sides and record['net']['proof']['outside']['differing_from_template'] == 0
        w, h = record['template']['frame_mm']
        assert w == pytest.approx(float(dims['width']))
        assert job.drawn_size(key, record) == job.die_sizes(build)[key]
        face = Image.open(folder / entry['face'])
        assert face.width / w == pytest.approx(record['template']['px_per_mm'], rel=0.02)
    for key in board:
        assert post(execution, 'product_round_files_accept', key, drawing=1).status_code == 302
    assert post(execution, 'product_round_files_make').status_code == 302
    build, statuses = execution.drain(limit=60)
    assert build.state == 'complete', (build.error, statuses)
    wrap = np.asarray(Image.open(folder / 'revisions' / '1' / 'drawing' / 'body-wrap.png').convert('RGB')).astype(int)
    quarter = wrap.shape[1] // 4
    red = [wrap[:, i * quarter:(i + 1) * quarter, 0].mean() for i in range(4)]
    assert red[1] > red[0] + 20 and red[2] > red[1] + 20 and red[3] > red[2] + 20    # its own sides, not front copies


def _start_flat_pick(execution, *, wrap=True):
    """A designer round's flat pick (flat_die_handoff/1) with a stand-in navy painting, started and drained: the build,
    the die it was painted on and the picked flat's path. ``wrap``: on the wrap of part 1, held for a build that has one; a new
    round is on the separate pieces."""
    from apps.pipeline.services import round_designer, round_files_gate as job
    job.FLAT_PICK_WRAP = wrap
    record, root = execution.record, execution.root
    geometry, setup = round_designer.die_first(SimpleNamespace(root=root, brief=record.product_brief))
    with Image.open(root / 'die' / 'flat' / 'template.png') as image:
        template = np.asarray(image.convert('RGBA'))
    raw = template[..., :3].copy()
    raw[template[..., 3] == 0] = (24, 34, 70)                   # a stand-in painting of the flat die: navy board
    design = root / 'designs' / 'g1' / 'D1'
    design.mkdir(parents=True)
    Image.fromarray(raw).save(design / 'raw.png')
    painting = dict(faces.settle_flat(design / 'raw.png', root / 'die' / 'flat', design, geometry), n='D1')
    flow_json = __import__('apps.pipeline.services.round_flow', fromlist=['write_json'])
    flow_json.write_json(design / 'painting.json', painting)
    flat = 'designs/g1/D1/flat.png'
    record.pick = {'id': 'D1', 'reason': 'The navy board.'}
    record.artifacts = {'pick_page': {'schema': 'designer_pick_page/1', 'order': ['D1'],
                                      'candidates': {'D1': {'id': 'D1', 'flat': flat, 'flat_sha256': sha(root / flat),
                                                            'picture': flat, 'picture_sha256': sha(root / flat)}},
                                      'files': {flat: sha(root / flat)}}}
    record.save()
    flow_json.write_json(root / 'handoff.json', {
        'schema': 'flat_die_handoff/1', 'contract': round_designer.FLAT_CONTRACT, 'id': 'D1', 'picture': flat,
        'picture_sha256': sha(root / flat), 'size_px': setup['frame']['canvas_px'],
        'painting': 'designs/g1/D1/painting.json', 'die': 'die/stand.json', 'reason': record.pick['reason'],
        'source_round': record.pk, 'execution': 'The picked flat die is what prints.'})
    job.start(record.pk, execution.owner)
    build, statuses = execution.drain(limit=80)
    assert build.state == 'awaiting', (build.error, statuses)
    return build, geometry, flat


@pytestmark_db
def test_a_flat_pick_starts_its_files_and_reaches_every_face_waiting_for_the_owner(execution, monkeypatch):
    """The chain's one break closed (the owner's goal of 2026-10-29): a designer round's flat pick (flat_die_handoff/1)
    starts "Make my files". Its reading is $0 (its own die's faces as panels, no call), its die solved again is the die
    it was painted on, its painting is installed as the build's painting at $0 (no painting call), and each stand face is
    then cut from one wrap (the owner, 2026-10-30), the header painted on what it joins, and the bottle and cap on their
    nets — until every face waits for the owner."""
    from apps.pipeline.services import round_files_gate as job
    root = execution.root
    monkeypatch.setattr(job, 'FLAT_STYLE', dict(job.FLAT_STYLE, plain_faces=[]))     # every face painted here
    build, geometry, flat = _start_flat_pick(execution)
    folder = job.root(build)
    inspection = json.loads((folder / 'inspection.json').read_text())
    assert inspection['flat_pick'] and inspection['notes'] == [job.FLAT_READING_NOTE]
    assert not any('Read this one picked picture' in prompt for prompt in execution.prompts)        # $0 reading
    assert json.loads((folder / 'stand.json').read_text())['record'] == geometry['record']          # the die it was painted on
    assert not any(call.kwargs['prompt'].startswith('Image 1 is a flat die') for call in execution.edit.call_args_list)
    claim = json.loads((folder / 'flat' / 'claim.json').read_text())
    assert claim['panels'] == 'full' and claim['product_nets'] and claim['wrap']['attempt'] == 1
    assert faces.current_painting(folder)['flat_sha256'] == sha(root / flat)                        # installed as picked
    stand_keys = [key for key in faces.FACES if faces.stand_face(key)]
    wraps = [call.kwargs for call in execution.edit.call_args_list
             if call.kwargs['prompt'].startswith('Image 1 is the sheet: white, with TRANSPARENT')]
    assert [call['quality'] for call in wraps] == ['medium', 'high']                        # the wrap, then the header
    assert execution.edit.call_count == 2 + 2 and 'One continuous painting' in wraps[0]['prompt']
    build, board = board_of(execution)
    assert all(row['state'] == 'drawn' for row in board.values())
    assert {job.current(board[key])['source'] for key in stand_keys} == {'wrap'}
    # every fold of the raster that prints, cut from one picture: the owner's bars hold
    rules = json.loads((folder / 'flat' / 'rules.json').read_text())
    assert rules['folds']['holds'], rules['folds']
    assert len(rules['folds']['folds']) == 5        # the header's fold and the four corners: the header now slots in
    assert any(row['bands'] == 'cross' for row in rules['folds']['folds'])
    assert all(row['band_offset_mm'] <= faces.FOLD_BAND_MM for row in rules['folds']['folds'] if row['bands'] == 'cross')
    # the object, drawn from the front three-quarter with its panels together, is served on the page
    page = job.flat_page(build)
    assert page['three_quarter'] and page['three_quarter'] in job.flat_pins(build)
    assert {job.current(board[key])['source'] for key in ('bottle', 'cap')} == {'net'}
    nets = [call.kwargs['prompt'] for call in execution.edit.call_args_list if call.kwargs['prompt'].startswith('Image 1 is a flat net')]
    assert len(nets) == 2 and all('picked flat design paints it' in prompt for prompt in nets)


@pytestmark_db
def test_a_plain_wall_is_read_from_the_painting_and_needs_no_drawing_of_its_own_on_a_wrap(execution):
    """The owner's ruling of 2026-10-29 ($2 per design) under the wrap of 2026-10-30: plain faces are still read from the
    picked painting itself (painted_plain, flat/plain.json); a wrap paints them in its one call, so none costs a call of
    its own: the wrap, the header, the bottle and the cap are every call a round makes."""
    from apps.pipeline.services import round_files_gate as job
    build, _geometry, _flat = _start_flat_pick(execution)
    folder = job.root(build)
    stand_keys = [key for key in faces.FACES if faces.stand_face(key)]
    plain = json.loads((folder / 'flat' / 'plain.json').read_text())
    assert plain['plain_faces'] == stand_keys                       # the stand-in painting is one navy board
    build, board = board_of(execution)
    assert all(row['state'] == 'drawn' for row in board.values()), {k: r.get('error') for k, r in board.items()}
    assert execution.edit.call_count == 4
    assert all(job.current(board[key])['cost_usd'] == 0.0 for key in stand_keys if key not in faces.HIGH_FACES)


@pytestmark_db
def test_every_round_page_opens_with_its_flat_folder_whole_partial_or_gone(execution):
    """The owner's goal of 2026-10-29 ("Fix the page"): round 3's files page failed (FileNotFoundError) once its die's
    template had moved away with the old die. Every round page opens with no server error — the round's own pages and
    its files page, every face on it — with the flat folder whole, without its template, with only its claim, and gone."""
    import shutil
    from django.urls import reverse
    from apps.pipeline.services import round_files_gate as job
    build, _geometry, _flat = _start_flat_pick(execution)
    folder = job.root(build) / 'flat'
    names = ('product_round', 'product_round_pick', 'product_round_board', 'product_round_research',
             'product_round_files')

    def opened():
        codes = {name: execution.client.get(reverse('dashboard:' + name, args=[execution.record.pk])).status_code
                 for name in names}
        assert all(code < 500 for code in codes.values()), codes
        response = page(execution)
        assert response.status_code == 200
        assert response.content.decode().count('class="face-card') == len(faces.FACES)
        return response.content.decode()

    assert 'template sheet' in opened()
    for name in ('index', 'new', 'round_list', 'pulse', 'find'):                 # where a fresh round starts
        assert execution.client.get(reverse('dashboard:' + name)).status_code < 500, name
    (folder / 'template.json').unlink()
    assert 'template sheet' not in opened()                                  # the sheet is not offered, nothing fails
    for path in folder.iterdir():
        if path.name != 'claim.json':
            shutil.rmtree(path) if path.is_dir() else path.unlink()
    opened()
    shutil.rmtree(folder)
    opened()


@pytestmark_db
def test_a_rejected_round_is_history_it_takes_no_work_and_no_new_round_reads_it(execution):
    """The owner's ruling of 2026-10-29 on round 3: a rejected round keeps its records (rejected.json beside them), its
    pages say so and offer no action, every action and the worker refuse it in words at $0, and a new round's taste
    memory leaves it out."""
    from apps.dashboard.views import round_card
    from apps.pipeline.models import Round
    from apps.pipeline.services import round_designer, round_files_gate as job, round_flow as flow
    record = execution.record
    record.artifacts = dict(record.artifacts, board_pick={'id': 'A', 'board': {'idea': 'A navy dial.'}, 'reason': 'Dial.'})
    record.save()
    job.start(record.pk, execution.owner)
    build, _ = execution.drain()
    later = Round.objects.create(slug='later-' + uuid4().hex, request_key=uuid4().hex, created_by=execution.owner,
                                 product_brief=execution.brief)
    assert [row['round'] for row in round_designer.taste_entries(execution.owner.pk, later.pk)] == [record.slug] * 2
    files = sorted(path.relative_to(execution.root) for path in execution.root.rglob('*') if path.is_file())
    flow.reject(record.pk, 'Round 3 is rejected (the owner, 2026-10-29).')
    record.refresh_from_db()
    assert sorted(path.relative_to(execution.root) for path in execution.root.rglob('*')
                  if path.is_file() and path.name != 'rejected.json') == files          # nothing deleted or changed
    assert json.loads((execution.root / 'rejected.json').read_text())['ruling'].startswith('Round 3 is rejected')
    assert round_designer.taste_entries(execution.owner.pk, later.pk) == []
    calls = (execution.edit.call_count, execution.text.messages.create.call_count)
    key = next(iter(job.board(build)))
    for act in (lambda: job.accept(record.pk, execution.owner, key, job.current(job.board(build)[key])['n']),
                lambda: job.redraw(record.pk, execution.owner, key), lambda: job.make_files(record.pk, execution.owner),
                lambda: flow.retry_round(record.pk, execution.owner)):
        with pytest.raises(ValueError, match='You rejected this round'):
            act()
    assert job.run(build.pk)['status'] == 'rejected'
    assert (execution.edit.call_count, execution.text.messages.create.call_count) == calls       # $0
    html = page(execution).content.decode()
    assert 'Rejected.' in html and 'You rejected this round' in html and 'class="btn primary">Accept<' not in html
    assert round_card(record)['state'] == 'folded'


@pytestmark_db
def test_a_flat_pick_whose_die_changed_is_refused_in_words(execution):
    """Negative control: a flat pick whose die solved again differs from the one it was painted on draws nothing."""
    from apps.pipeline.services import round_designer, round_files_gate as job
    record, root = execution.record, execution.root
    geometry, setup = round_designer.die_first(SimpleNamespace(root=root, brief=record.product_brief))
    changed = json.loads((root / 'die' / 'stand.json').read_text())
    changed['record']['inputs']['height_mm'] += 1
    (root / 'die' / 'stand.json').write_text(json.dumps(changed))
    with Image.open(root / 'die' / 'flat' / 'template.png') as image:
        template = np.asarray(image.convert('RGBA'))
    design = root / 'designs' / 'g1' / 'D1'
    design.mkdir(parents=True)
    Image.fromarray(template[..., :3].copy()).save(design / 'flat.png')
    flat = 'designs/g1/D1/flat.png'
    record.pick = {'id': 'D1', 'reason': 'The navy board.'}
    record.artifacts = {'pick_page': {'schema': 'designer_pick_page/1', 'order': ['D1'],
                                      'candidates': {'D1': {'id': 'D1', 'flat': flat, 'flat_sha256': sha(root / flat)}},
                                      'files': {flat: sha(root / flat)}}}
    record.save()
    (root / 'handoff.json').write_text(json.dumps({
        'schema': 'flat_die_handoff/1', 'contract': round_designer.FLAT_CONTRACT, 'id': 'D1', 'picture': flat,
        'picture_sha256': sha(root / flat), 'size_px': setup['frame']['canvas_px'],
        'painting': 'designs/g1/D1/painting.json', 'die': 'die/stand.json', 'reason': record.pick['reason'],
        'source_round': record.pk, 'execution': 'The picked flat die is what prints.'}))
    job.start(record.pk, execution.owner)
    build, _statuses = execution.drain(limit=20)
    assert build.state == 'failed' and 'not the die your pick was painted on' in build.error
    assert execution.edit.call_count == 0


@pytestmark_db
def test_a_new_flat_attempt_with_panels_and_nets_draws_every_face_again_one_call_each(execution, tmp_path, monkeypatch):
    """The owner's goal of 2026-10-29 for round 3: a policy's next attempt (panels 'full', product_nets) paints the die
    once for the idea, then draws each stand face on its own outline and the bottle and cap on their nets — one edit
    each, under the attempt's own cap; the earlier drawings stay on the faces' records."""
    from apps.pipeline.services import round_files_gate as job
    job.start(execution.record.pk, execution.owner)
    build, _ = execution.drain()
    first = execution.edit.call_count
    policy = tmp_path / 'policy.json'
    policy.write_text(json.dumps(dict(json.loads(job.POLICY.read_text()), flat_stands={execution.record.slug: dict(
        job.FLAT_STYLE, picture_sha256=sha(job.root(build) / 'source.png'), attempt=2, budget_usd=3,
        panels='full', product_nets=True, plain_faces=[])})))
    monkeypatch.setattr(job, 'POLICY', policy)
    stand = json.loads((job.root(build) / 'stand.json').read_text())
    stand.pop('sightline_revision')                         # round 3's case: its stand predates the sightline fix
    (job.root(build) / 'stand.json').write_text(json.dumps(stand))
    job.enqueue(build.pk)
    build, statuses = execution.drain(limit=60)
    assert build.state == 'awaiting', (build.error, statuses)
    claim = json.loads((job.root(build) / 'flat' / 'claim.json').read_text())
    assert claim['attempt'] == 2 and claim['budget_usd'] == 3 and claim['panels'] == 'full' and claim['product_nets']
    assert set(claim['faces_reset']) == set(faces.FACES) and claim['faces_kept'] == []
    _, rows = board_of(execution)
    stand = [key for key in faces.FACES if faces.stand_face(key)]
    assert execution.edit.call_count - first == 1 + len(stand) + 2      # the die once, each panel, the two nets
    assert all(rows[key]['state'] == 'drawn' and len(rows[key]['drawings']) >= 1 for key in faces.FACES)
    assert {job.current(rows[key])['source'] for key in ('bottle', 'cap')} == {'net'}
    assert len(rows['bottle']['drawings']) == 2                          # the first drawing kept as history


# --- the painting's proof as a gate, the plain check, one system redraw, the proof sheet (owner's goal, 2026-10-29) ----

def _painting_record(tmp_path, geometry, *, white=(), coverage=None):
    """A settled painting of the die, $0: every printed face navy but those in ``white`` (left in the template's white),
    with its proof's coverage as given."""
    from apps.dielines.exporters import counter_display_files as cdf
    die = faces.die_of(geometry)
    masks = cdf.flat_masks(die, cdf.flat_frame(die))
    flat = np.full(masks['owner'].shape + (3,), 255, np.uint8)
    flat[masks['paint']] = (20, 40, 80)
    for name in white:
        flat[masks['owner'] == masks['names'].index(name) + 1] = 255
    path = tmp_path / 'flat.png'
    Image.fromarray(flat).save(path)
    names = {name: 1.0 for name in masks['names']}
    names.update(coverage or {})
    return {'flat': str(path), 'proof': {'coverage': names, 'registration': {'iou_at_best': 0.53}}}


def test_a_crop_is_followed_only_where_the_painting_kept_its_face(tmp_path):
    """Round 3's first real painting stretched the die: its side walls came back 0.26 and 0.31 covered and its front
    strip in the template's grey. A face's crop is reliable only at coverage ≥ 0.9 with at most half of it left in the
    template's unpainted colours; elsewhere it is never what a panel follows."""
    geometry = stand_geometry(tmp_path)
    painting = _painting_record(tmp_path, geometry, white=('front panel',), coverage={'left side': 0.26})
    got = {key: faces.crop_reliability(painting, key, geometry) for key in faces.FACES if faces.stand_face(key)}
    assert not got['front']['reliable'] and got['front']['unpainted_share'] == 1.0 and got['front']['coverage'] == 1.0
    assert not got['left']['reliable'] and got['left']['coverage'] == 0.26 and got['left']['unpainted_share'] == 0.0
    assert all(got[key]['reliable'] for key in ('header', 'header_back', 'side', 'back'))
    assert faces.unpainted(np.array([[255, 255, 255], [204, 204, 204], [20, 40, 80], [200, 170, 90]])).tolist() == \
        [True, True, False, False]
    with pytest.raises(ValueError, match='no die-match proof'):
        faces.crop_reliability({'flat': painting['flat']}, 'header', geometry)


def test_a_plain_face_is_checked_for_anything_but_its_board(tmp_path):
    """The owner's policy names faces plain; round 3's back wall came back with an invented gold gauge: a plain face
    has at most 2 % of its printed pixels more than ΔE00 15 from its own colour."""
    face = {'w_mm': 60.0, 'h_mm': 100.0, 'bleed_mm': 3.0, 'outline': __import__('shapely.geometry', fromlist=['box']).box(0, 0, 60, 100)}
    sheet = faces.panel_sheet('back', face, tmp_path / 'sheet')
    x0, y0, x1, y1 = sheet['frame_px']
    rng = np.random.default_rng(3)
    board = np.clip(np.array([20, 40, 80]) + rng.normal(0, 3, (y1 - y0, x1 - x0, 3)), 0, 255).astype(np.uint8)
    Image.fromarray(board).save(tmp_path / 'plain.png')
    gauge = board.copy()
    gauge[int(.7 * gauge.shape[0]):int(.82 * gauge.shape[0]), int(.1 * gauge.shape[1]):int(.45 * gauge.shape[1])] = (200, 170, 90)
    Image.fromarray(gauge).save(tmp_path / 'gauge.png')
    assert faces.plain_check(tmp_path / 'plain.png', sheet)['plain']
    check = faces.plain_check(tmp_path / 'gauge.png', sheet)
    assert not check['plain'] and check['share_over'] > 0.02


def _panels_attempt(execution, tmp_path, monkeypatch, **policy):
    from apps.pipeline.services import round_files_gate as job
    job.start(execution.record.pk, execution.owner)
    build, _ = execution.drain()
    path = tmp_path / 'policy.json'
    path.write_text(json.dumps(dict(json.loads(job.POLICY.read_text()), flat_stands={execution.record.slug: dict(
        job.FLAT_STYLE, picture_sha256=sha(job.root(build) / 'source.png'), attempt=2, budget_usd=5,
        panels='full', product_nets=True, **policy)})))
    monkeypatch.setattr(job, 'POLICY', path)
    job.enqueue(build.pk)
    build, statuses = execution.drain(limit=60)
    assert build.state == 'awaiting', (build.error, statuses)
    return build


@pytestmark_db
def test_a_flagged_panel_gets_one_system_redraw_and_never_a_second(execution, tmp_path, monkeypatch):
    """A panel over its bar, drawn from a crop the painting did not keep, or not plain where the owner says plain is
    queued (by the worker, under the build's lock) for ONE system redraw under the claim's cap; after it the face is
    the owner's: a face still flagged is never redrawn by the system again."""
    from django.db import transaction
    from apps.pipeline.models import RoundMaster
    from apps.pipeline.services import round_files_gate as job
    monkeypatch.setattr(faces, 'plain_check', lambda path, template: {'schema': 'panel_plain_check/1', 'share_over': 0.05,
                                                                       'threshold': dict(faces.PLAIN), 'plain': False})
    build = _panels_attempt(execution, tmp_path, monkeypatch, plain_faces=['back'])
    rows = job.board(build)
    redo = rows['back']['system_redraw']
    assert 'not plain' in redo['reason'] and redo['drawn'] == rows['back']['drawing'] == redo['of'] + 1
    assert job.current(rows['back'])['system_redraw']['of'] == redo['of']
    assert all('system_redraw' not in rows[key] for key in faces.FACES if key != 'back')
    claim = json.loads((job.root(build) / 'flat' / 'claim.json').read_text())
    assert 'face/back/%d' % redo['drawn'] in claim['operations']               # under the claim's cap
    calls = execution.edit.call_count
    with transaction.atomic():
        locked = RoundMaster.objects.select_for_update().get(pk=build.pk)
        assert job.system_repairs(locked) == []                                 # never a second
        locked.save()
    job.enqueue(build.pk)
    execution.drain()
    assert execution.edit.call_count == calls


@pytestmark_db
def test_when_the_faces_settle_the_proof_sheet_and_the_views_are_made_from_the_current_drawings(execution, tmp_path,
                                                                                                 monkeypatch):
    """The owner's proof before his Accept ($0): one PDF page at real size (the stand's die at 1:1 with its art at 300 ppi,
    the two nets at 1:1), a PNG beside it, and the stand folded and loaded drawn again from the current panels; the
    files page shows them."""
    from apps.pipeline.services import round_files_gate as job
    build = _panels_attempt(execution, tmp_path, monkeypatch, plain_faces=[])
    folder = job.root(build)
    assert not list((folder / 'proof').glob('*-error.json')), [p.read_text() for p in (folder / 'proof').glob('*-error.json')]
    sheet = json.loads((folder / 'proof' / 'current.json').read_text())
    with fitz.open(folder / sheet['pdf']) as pdf:
        assert len(pdf) == 1
        rect = pdf[0].rect
    assert rect.width / job.MM == pytest.approx(sheet['page_mm'][0], abs=0.01)
    assert rect.height / job.MM == pytest.approx(sheet['page_mm'][1], abs=0.01)
    assert sheet['page_mm'][0] > sheet['stand_mm'][0] and {net['key'] for net in sheet['nets']} == {'bottle', 'cap'}
    assert set(sheet['faces']) == set(faces.FACES) and not any(sheet['accepted'].values())
    assert (folder / sheet['png']).exists() and sha(folder / sheet['pdf']) == sheet['pdf_sha256']
    panels = json.loads((folder / 'flat' / 'panels' / 'current.json').read_text())
    assert (folder / panels['folded']).exists() and (folder / panels['loaded']).exists()
    flat = job.flat_page(build)
    assert flat['panels'] and flat['proof_sheet']['pdf'] == sheet['pdf'] and flat['panel_folded'] == panels['folded']
    html = page(execution).content.decode()
    assert 'Proof at real size' in html and 'the PDF, to print at 100%' in html and 'from the faces as drawn now' in html


def test_the_check_measures_the_printed_pixels_never_the_white_around_them(tmp_path):
    """Round 3's left side (2026-10-29): a plain navy trapezoid, flagged only because the whole frame — the template's
    protected white around the outline — was compared with a navy reference. On the printed pixels it passes."""
    import numpy as np
    from PIL import Image, ImageDraw
    h, w = 160, 100
    template = Image.new('RGBA', (w, h), (255, 255, 255, 255))
    shape = [(0, 0), (60, 0), (100, 160), (0, 160)]
    hole = Image.new('L', (w, h), 0)
    ImageDraw.Draw(hole).polygon(shape, fill=255)
    template.paste((0, 0, 0, 0), mask=hole)
    template.save(tmp_path / 'template.png')
    face = Image.new('RGB', (w, h), (255, 255, 255))
    face.paste((20, 40, 90), mask=hole)
    face.save(tmp_path / 'face.png')
    reference = np.full((h, w, 3), (20, 40, 90), np.uint8)
    sheet = {'template': str(tmp_path / 'template.png'), 'frame_px': [0, 0, w, h]}
    whole = faces.against_painting(tmp_path / 'face.png', reference)
    printed = faces.against_painting(tmp_path / 'face.png', reference, printed=faces.printed_region(sheet))
    assert whole['flagged'] and not printed['flagged'] and printed['measured_on'] == "the face's printed pixels"
    assert printed['revision'] == faces.CHECK_REVISION


def test_a_plain_face_from_the_board_is_tiled_at_its_own_pixels_and_costs_nothing(tmp_path):
    """A plain face still not plain after its one system redraw is made from the stand's board at $0: the board's
    largest plain rectangle mirror-tiled at its own pixels (never upscaled), checked like any drawing, restartable."""
    import numpy as np
    from PIL import Image
    _, brief, _ = picture(tmp_path)
    geometry = stand_geometry(tmp_path)
    face = faces.face_geometry('side', brief, faces.die_of(geometry))
    folder = tmp_path / 'source'
    sheet = faces.panel_sheet('side', face, folder)
    W, H = (int(v) for v in sheet['size'].split('x'))
    noise = np.random.default_rng(0).integers(-3, 4, (H, W, 3))
    Image.fromarray((np.array([20, 40, 90]) + noise).clip(0, 255).astype(np.uint8)).save(folder / 'face.png')
    source = {'key': 'side', 'n': 1, 'face': str(folder / 'face.png'), 'face_sha256': sha(folder / 'face.png'),
              'template': sheet}
    ctx = SimpleNamespace(root=tmp_path / 'build', brief=brief)
    record = faces.board_face(ctx, 'side', 2, source, geometry, why='not plain after its redraw')
    assert record['cost_usd'] == 0.0 and record['source'] == 'board' and record['board_face']['scale'] <= 1
    assert record['plain_check']['plain'] and not record['against_painting']['flagged']
    assert faces.board_face(ctx, 'side', 2, source, geometry, why='again')['face_sha256'] == record['face_sha256']


def test_english_only_no_arabic_is_set_and_the_bottle_carries_brand_product_and_shade(tmp_path):
    """The owner's ruling of 2026-10-29: designs are English only. With a bilingual brief, the COPY fields carry no
    Arabic, the front strip's line has no slash, and the bottle front carries the brand, "Lip Gloss" and the shade's
    name — the shade's name in the box the picture gave its Arabic line, a gap between the two words."""
    from apps.pipeline.services.round_files_export import measure_type
    assert faces.ARABIC_TYPE is False
    brief = {'copy': {'brand': 'BBROSE', 'product': 'Lip Gloss / ملمع شفاه'},
             'shades': [{'name': 'Rose Glass', 'hex': '#C9707A', 'name_arabic': 'زجاج الورد'}]}
    fields = faces.copy_fields(brief)
    assert fields == {'product_latin': 'Lip Gloss', 'shade_0': 'Rose Glass'}
    assert [row['copy'] for row in faces.product_line(fields, 50, 10, 4, 100, colour='#D5AF59', foil=True,
                                                      name='front')] == ['Lip Gloss']
    rows = [{'box_px': [424, 543, 445, 627], 'color': '#D5AF59', 'rotation': 90, 'field': 'product_latin'},
            {'box_px': [424, 438, 445, 545], 'color': '#D5AF59', 'rotation': 90, 'field': 'product_arabic'}]
    placed = faces.bottle_rows(rows, fields)
    assert [row['field'] for row in placed] == ['product_latin', 'shade_0']
    assert placed[1]['box_px'][3] < placed[0]['box_px'][1]                       # a gap between the two words
    assert all(not faces.ARABIC.search(text) for text in (faces.NO_WORDS, faces.FLAT_NO_WORDS)) and \
        'No Arabic lettering' in faces.NO_WORDS and 'No Arabic lettering' in faces.FLAT_NO_WORDS


@pytestmark_db
def test_a_preview_placed_under_older_type_rules_is_placed_again_at_no_cost(execution):
    """The owner's ruling of 2026-10-29 (English only): a face whose preview predates the rule has its type placed
    again on the worker's next run — its drawing kept, no edit or text call, the face still waiting for the owner — and
    the proof sheet is made again for the new type."""
    from apps.pipeline.models import RoundMaster
    from apps.pipeline.services import round_files_gate as job
    job.start(execution.record.pk, execution.owner)
    build, _ = execution.drain()
    calls = (execution.edit.call_count, execution.text.messages.create.call_count)
    build = RoundMaster.objects.get(pk=build.pk)
    for row in build.steps['faces']['board'].values():
        job.current(row)['type_revision'] = 'older'
    build.save()
    job.enqueue(build.pk)
    build, statuses = execution.drain()
    assert build.state == 'awaiting', (build.error, statuses)
    assert (execution.edit.call_count, execution.text.messages.create.call_count) == calls
    rows = build.steps['faces']['board']
    assert all(row['state'] == 'drawn' and job.current(row)['type_revision'] == faces.TYPE_REVISION
               and job.current(row)['preview'] for row in rows.values())


@pytestmark_db
def test_a_die_cut_to_the_pictures_header_redraws_only_the_faces_whose_outline_changed(execution, tmp_path, monkeypatch):
    """The shape check (the owner's goal of 2026-10-29, §4): a per-panel build whose die is solved again with the
    picture's quadrant header keeps every face whose outline is unchanged; the header is refitted from its own drawing
    (one paid edit, under the owner's added cap), the header back — plain — is the board at $0."""
    from apps.dielines.geometry import counter_display
    from apps.pipeline.services import round_files_gate as job
    job.start(execution.record.pk, execution.owner)
    build, _ = execution.drain()
    policy = tmp_path / 'policy.json'
    policy.write_text(json.dumps(dict(json.loads(job.POLICY.read_text()), flat_stands={execution.record.slug: dict(
        job.FLAT_STYLE, picture_sha256=sha(job.root(build) / 'source.png'), attempt=2, budget_usd=3, panels='full',
        plain_faces=['side', 'left', 'back', 'header_back'], outline_redraw_usd=3)})))
    monkeypatch.setattr(job, 'POLICY', policy)
    job.enqueue(build.pk)
    build, _ = execution.drain(limit=60)
    for _settle in range(4):                            # the system's own repairs of that attempt, settled first
        drawn = {key: job.current(row)['n'] for key, row in build.steps['faces']['board'].items()}
        job.enqueue(build.pk)
        build, _ = execution.drain(limit=60)
        if {key: job.current(row)['n'] for key, row in build.steps['faces']['board'].items()} == drawn:
            break
    before = {key: job.current(row)['n'] for key, row in build.steps['faces']['board'].items()}
    edits = execution.edit.call_count
    board = job._board_source(build, ('side', 'left', 'back', 'header_back'), exclude='header_back')
    monkeypatch.setattr(counter_display, 'read_header_outline', lambda inspection: {
        'shape': 'quadrant', 'params': {'flat': 0.3}, 'iou': 0.99, 'scores': {}, 'source': 'test'})
    stand = json.loads((job.root(build) / 'stand.json').read_text())
    stand.pop('sightline_revision')
    (job.root(build) / 'stand.json').write_text(json.dumps(stand))
    job.enqueue(build.pk)
    build, statuses = execution.drain(limit=60)
    assert build.state == 'awaiting', (build.error, statuses)
    claim = json.loads((job.root(build) / 'flat' / 'claim.json').read_text())
    assert sorted(claim['outline_redraw']['faces']) == ['header', 'header_back']
    assert faces.flat_setup(json.loads((job.root(build) / 'stand.json').read_text()), job.root(build) / 'flat')  # the new die's template
    assert claim['budget_usd'] == pytest.approx(claim['outline_redraw']['spent_before_usd'] + 3)
    rows = build.steps['faces']['board']
    # the header refitted (one edit); the header back the board at $0 when a passing plain drawing gives one, else refitted
    assert execution.edit.call_count - edits == (1 if board is not None else 2)
    assert job.current(rows['header'])['reference_source'] == 'previous drawing'
    if board is not None:
        assert job.current(rows['header_back'])['source'] == 'board' and job.current(rows['header_back'])['cost_usd'] == 0.0
    else:
        assert job.current(rows['header_back'])['reference_source'] == 'previous drawing'
    for key in ('front', 'side', 'left', 'back'):
        assert job.current(rows[key])['n'] == before[key] and rows[key]['state'] == 'drawn'
    assert all('drawn' in rows[key]['outline_redraw'] for key in ('header', 'header_back'))


def _carton_rings():
    """A generic carton's printed faces, the sheet's mm: four body panels side by side, each 40 × 60, a glue flap
    unprinted, 3 mm of bleed around them."""
    return [[[7, 7], [173, 7], [173, 73], [7, 73]]]


def _painting_on(tmp_path, size_mm, px_per_mm=6):
    W, H = int(size_mm[0] * px_per_mm), int(size_mm[1] * px_per_mm)
    rgba = np.zeros((H, W, 4), np.uint8)
    rgba[int(7 * px_per_mm):int(73 * px_per_mm), int(7 * px_per_mm):int(173 * px_per_mm)] = (31, 58, 51, 255)
    Image.fromarray(rgba, 'RGBA').save(tmp_path / 'painting.png')
    return str(tmp_path / 'painting.png')


def test_the_writer_writes_only_the_painting_its_words_its_plates_and_the_die(tmp_path):
    """The owner, 2026-10-30: "The painting prints complete": the print file's layers are the painting, the foil and
    relief plates, the type, the logo, the die and the guides; a clean carton passes its check on the written file."""
    from apps.pipeline.services import round_files_export as export
    spec = {'id': 'carton', 'title': 'carton', 'size_mm': [180, 80], 'type_runs': [], 'logos': [],
            'artwork': [{'name': 'painting', 'path': _painting_on(tmp_path, (180, 80)), 'box_mm': [0, 0, 180, 80]}],
            'die': {'cut': [{'points_mm': [[10, 10], [170, 10], [170, 70], [10, 70]], 'closed': True}]}, 'guides': [],
            'printed_mm': _carton_rings()}
    result = export.export_object(spec, tmp_path / 'out', native=False)
    assert result['layers'] == ['GROUND', 'MOTIFS', 'RELIEF', 'FOIL', 'WORDS', 'DIE']
    assert result['readback']['checks']['exact_layers'] and result['readback']['checks']['die_guides_locked_nonprinting']
    checked = json.loads((tmp_path / 'out' / 'carton.print-check.json').read_text())
    assert checked['holds'] and checked['outside_mm2'] == 0 and checked['unlayered_vectors'] == 0


def _carton_die(panels=4, w=40.0, h=60.0):
    """A generic carton's body as a die: four panels side by side on one sheet, each a printed face, a crease between
    each two. As the die writers see it: its parts, their faces and creases."""
    from shapely.geometry import LineString, box
    faces_ = [('panel %d' % i, box(i * w, 0, (i + 1) * w, h), True) for i in range(panels)]
    creases = [('crease %d' % i, LineString([((i + 1) * w, 0), ((i + 1) * w, h)])) for i in range(panels - 1)]
    die = SimpleNamespace(parts=[SimpleNamespace(name='tray', faces=faces_, creases=creases)])
    k = faces.K
    frame = {'part': 'tray', 'px_per_mm': k, 'offset_px': [0.0, 0.0], 'frame_mm': [0, 0, panels * w, h],
             'canvas_px': [int(panels * w * k), int(h * k)]}
    return die, frame


def _woven(frame, *, ground=(31, 58, 51), band_at=(20.0, 41.0)):
    """One continuous picture: its ground, gold bands level at ``band_at`` mm and a vine wandering across it."""
    k, (W, H) = frame['px_per_mm'], frame['canvas_px']
    ys, xs = np.mgrid[:H, :W]
    art = np.zeros((H, W, 3), np.uint8)
    art[...] = ground
    art[(np.sin(xs / (6 * k)) * 3 * k + ys) % (14 * k) < .5 * k] = (50, 80, 60)
    for at in band_at:
        art[np.abs(ys - at * k) < 1.5 * k] = (184, 138, 62)
    return art


def test_a_generic_carton_cut_from_one_picture_holds_every_fold():
    die, frame = _carton_die()
    checked = faces.fold_check(_woven(frame), faces.fold_samples(die, frame), crossing=('crease',))
    assert checked['holds'] and len(checked['folds']) == 3
    assert all(row['band_offset_mm'] <= faces.FOLD_BAND_MM and row['colour_de00'] <= faces.FOLD_DE
               for row in checked['folds'])


def test_a_generic_carton_of_separately_painted_panels_fails_its_folds():
    """The owner's fault: the same theme, each panel painted on its own. Bands 5 mm off at one crease, another panel's
    ground different at the next: each fold fails in its own number."""
    die, frame = _carton_die()
    k = frame['px_per_mm']
    art = _woven(frame)
    second = _woven(frame, band_at=(25.0, 46.0))
    x1 = int(40 * k)
    art[:, x1:2 * x1] = second[:, x1:2 * x1]                                    # panel 1's bands sit 5 mm higher
    art[:, 3 * x1:] = _woven(frame, ground=(180, 170, 140))[:, 3 * x1:]         # panel 3 on a cream ground
    checked = faces.fold_check(art, faces.fold_samples(die, frame), crossing=('crease',))
    assert not checked['holds'] and set(checked['off']) >= {'panel 0 | panel 1', 'panel 2 | panel 3'}
    rows = {row['fold']: row for row in checked['folds']}
    assert rows['panel 0 | panel 1']['band_offset_mm'] == pytest.approx(5.0, abs=.5)
    assert rows['panel 2 | panel 3']['colour_de00'] > faces.FOLD_DE


def test_every_panels_ground_is_held_to_the_designs_a_cream_wall_fails():
    """On a generic carton, and on a stand's names: a cream wall on a green design fails; the cap's gold and the bottle's
    clear body are their own grounds, never measured."""
    die, frame = _carton_die()
    art, k = _woven(frame), frame['px_per_mm']
    masks = {name: np.zeros(art.shape[:2], bool) for name, _f, _p in die.parts[0].faces}
    for index, name in enumerate(masks):
        masks[name][:, int(index * 40 * k):int((index + 1) * 40 * k)] = True
    good = faces.ground_check({name: (art, mask) for name, mask in masks.items()}, '#1F3A33')
    assert good['holds'] and all(row['delta_e00'] <= faces.GROUND_DE for row in good['panels'].values())
    art[masks['panel 2']] = _woven(frame, ground=(232, 220, 194))[masks['panel 2']]
    bad = faces.ground_check({name: (art, mask) for name, mask in masks.items()}, '#1F3A33')
    assert bad['off'] == ['panel 2'] and bad['panels']['panel 2']['delta_e00'] > faces.GROUND_DE
    gold = np.full((20, 20, 3), (196, 160, 76), np.uint8)
    own = faces.ground_check({'cap': (gold, np.ones((20, 20), bool))}, '#1F3A33', own=faces.OWN_GROUND)
    assert own['holds'] and own['panels']['cap'] == {'own_ground': True, 'holds': True}


def test_a_ground_a_little_off_is_toned_in_its_own_pixels_and_a_wrong_one_is_left_for_the_check():
    die, frame = _carton_die()
    mask = np.ones(frame['canvas_px'][::-1], bool)
    dark = _woven(frame, ground=(10, 42, 28))
    toned, record = faces.ground_tone(dark, mask, '#1F3A33')
    assert record['toned'] and record['delta_e00_before'] > faces.GROUND_DE
    assert faces.ground_check({'panel': (toned, mask)}, '#1F3A33')['holds']
    # the gold threads are not the ground: they stay as painted
    k = frame['px_per_mm']
    assert toned[int(20 * k), 50].tolist() == pytest.approx(dark[int(20 * k), 50].tolist(), abs=3)
    cream = _woven(frame, ground=(232, 220, 194))
    same, record = faces.ground_tone(cream, mask, '#1F3A33')
    assert not record['toned'] and same is cream


def test_panels_join_edge_to_edge_as_they_fold_on_any_die():
    """wrap_layout is the die's faces and joins as data: a carton's body in a row, and a stand's outside with its header
    front turned over the top of its header back. A wrap fits the model's range, below 300 PPI where it must."""
    from shapely.geometry import box
    panel = lambda w, h: {'w': w, 'h': h, 'outline': box(0, 0, w, h)}   # noqa: E731
    carton = faces.wrap_layout({'a': panel(40, 60), 'b': panel(30, 60), 'c': panel(40, 60), 'lid': panel(40, 30)},
                               (('a', 'right', 'b', 'left'), ('b', 'right', 'c', 'left'), ('a', 'top', 'lid', 'bottom')))
    assert carton['panels']['b']['x'] == 40 and carton['panels']['c']['x'] == 70 and carton['panels']['lid']['y'] == -30
    stand = faces.wrap_layout({'back': panel(107, 98.5), 'side': panel(82, 98.5), 'left': panel(82, 98.5),
                               'front': panel(107, 23.5), 'header_back': panel(107, 60), 'header': panel(107, 58.5)},
                              faces.STAND_WRAP)
    places = stand['panels']
    assert places['side']['x'] == -82 and places['left']['x'] == 107 and places['front']['x'] == 189
    assert places['front']['y'] + places['front']['H'] == 98.5                      # its foot level with the walls'
    assert places['header']['q'] == 2 and places['header']['y'] == -118.5           # folded over the top
    canvas = faces.wrap_canvas(stand, ['side', 'back', 'left', 'front', 'header_back'])
    assert faces.is_wrap_size(canvas['size']) and 200 < canvas['native_ppi'] <= 300
    one = faces.wrap_canvas(stand, ['header'], context_mm=faces.WRAP_CONTEXT_MM)
    assert faces.is_panel_size(one['size']) and one['native_ppi'] >= 299


def test_a_clear_bodys_ground_and_window_carry_no_ink_and_its_woven_art_does(tmp_path):
    """The rule's exception (the owner, 2026-10-30): a clear surface's ground stays unprinted, and so does its window."""
    art = np.zeros((600, 300, 3), np.uint8)
    art[...] = (31, 58, 51)
    art[100:500, 60:240] = (178, 96, 100)                       # the window, as the model paints it
    art[20:60, 40:260] = (196, 160, 76)                         # the weave
    Image.fromarray(art).save(tmp_path / 'face.png')
    sheet = Image.new('RGBA', (300, 600), (0, 0, 0, 0))
    sheet.save(tmp_path / 'template.png')
    drawn = {'face': str(tmp_path / 'face.png'), 'template': {'px_per_mm': 10.0, 'frame_mm': [30, 60],
                                                              'frame_px': [0, 0, 300, 600],
                                                              'template': str(tmp_path / 'template.png')}}
    with Image.open(faces.clear_painting(drawn)) as image:
        alpha = np.asarray(image.convert('RGBA'))[..., 3]
    assert alpha[300, 20] == 0 and alpha[300, 150] == 0 and alpha[40, 150] == 255


def test_a_wrap_paints_a_panels_bleed_over_a_neighbour_not_on_its_canvas_and_names_the_plain_areas(tmp_path, monkeypatch):
    """Found on round 4: the header back's top bleed lay over the header front, which the wrap does not paint, and it came
    out white, a white hairline at the fold. Art that is on the canvas stays; the plain area the words need is named."""
    from shapely.geometry import box
    panel = lambda w, h: {'w': w, 'h': h, 'outline': box(0, 0, w, h)}   # noqa: E731
    layout = faces.wrap_layout({'a': panel(40, 60), 'b': panel(40, 60), 'lid': panel(40, 30)},
                               (('a', 'right', 'b', 'left'), ('a', 'top', 'lid', 'bottom')))
    art = np.full((int(66 * 10), int(46 * 10), 3), (31, 58, 51), np.uint8)
    art[np.random.default_rng(0).random(art.shape[:2]) < .3] = (184, 138, 62)     # a dense weave
    art[100:200, 100:300] = (232, 220, 194)                                       # its one plain area
    Image.fromarray(art).save(tmp_path / 'a.png')
    (tmp_path / 'flat').mkdir()
    calls = []

    class Ctx:
        root = tmp_path

        def face_edit(self, operation, words, folder, *, template, references, size, quality):
            calls.append(words)
            Path(folder).mkdir(parents=True, exist_ok=True)
            w, h = (int(v) for v in size.split('x'))
            Image.new('RGB', (w, h), (31, 58, 51)).save(Path(folder) / 'raw.png')
            return {'reservation_id': 'fixture'}
    made = faces.paint_wrap(Ctx(), 'stand', 1, layout, ['a', 'b'], {'a': str(tmp_path / 'a.png')})
    with Image.open(made['faces']['a']['face']) as image:
        top = np.asarray(image.convert('RGB'))[:3, 100]
    assert (top == (31, 58, 51)).all()                                      # its top bleed is painted
    assert 'These areas stay empty' not in calls[0]                         # 'a' carries no words: none is named
    monkeypatch.setitem(faces.FLAT_WORDS, 'a', 'frame')
    made = faces.paint_wrap(Ctx(), 'stand', 2, layout, ['a', 'b'], {'a': str(tmp_path / 'a.png')})
    assert 'These areas stay empty' in calls[1] and '- A' in calls[1].split('These areas stay empty')[1]


def test_a_band_that_moves_at_a_fold_fails_even_where_the_art_beside_it_looks_alike():
    """Found on round 4's right wall, repainted alone: two of its three bands moved off the back's, in the same art and on
    the same ground, and a measure of the two sides' likeness passed it. Every band is looked for on the other side."""
    die, frame = _carton_die()
    k = frame['px_per_mm']
    art = _woven(frame, band_at=(10.0, 30.0, 50.0))
    moved = _woven(frame, band_at=(14.0, 30.0, 56.0))                       # one band of three still meets
    x1 = int(40 * k)
    art[:, x1:2 * x1] = moved[:, x1:2 * x1]
    checked = faces.fold_check(art, faces.fold_samples(die, frame), crossing=('crease',))
    rows = {row['fold']: row for row in checked['folds']}
    assert not rows['panel 0 | panel 1']['holds'] and rows['panel 0 | panel 1']['band_offset_mm'] >= 4
    assert rows['panel 2 | panel 3']['holds'] and rows['panel 2 | panel 3']['band_offset_mm'] == 0


def test_a_lost_word_place_is_put_back_in_the_wraps_own_pixels(tmp_path):
    from shapely.geometry import box
    folder = tmp_path / 'faces' / 'side' / 'drawings' / '1'
    folder.mkdir(parents=True)
    rgb = np.full((300, 400, 3), (31, 58, 51), np.uint8)
    rgb[np.random.default_rng(0).random(rgb.shape[:2]) < .3] = (184, 138, 62)
    given = rgb.copy()
    given[100:200, 100:300] = (40, 70, 60)
    Image.fromarray(rgb).save(folder / 'face.png')
    Image.fromarray(given).save(folder / 'reference.png')
    Image.new('RGBA', (400, 300), (0, 0, 0, 0)).save(folder / 'template.png')
    record = {'key': 'side', 'n': 1, 'face': str(folder / 'face.png'), 'reference': {'path': str(folder / 'reference.png')},
              'template': {'px_per_mm': 10.0, 'frame_mm': [40, 30], 'frame_px': [0, 0, 400, 300],
                           'template': str(folder / 'template.png')}}
    made = faces.restore_word_place(tmp_path, 'side', 2, record, [10, 10, 30, 20], {'w': 34, 'h': 24, 'outline': box(0, 0, 34, 24)})
    with Image.open(made['face']) as image:
        out = np.asarray(image.convert('RGB'))
    assert (out[150, 200] == (40, 70, 60)).all()                            # the plain area is back
    assert (out[10, 10] == rgb[10, 10]).all() and (out[290, 390] == rgb[290, 390]).all()     # the wrap's own pixels stand
    assert made['cost_usd'] == 0.0 and made['restored']['of'] == 1


def test_illustrators_passing_reopen_error_is_asked_once_more_and_a_real_one_is_not():
    from apps.pipeline.services import round_files_export as export
    replies = [{'error': "Error: an Illustrator error occurred: 1346458189 ('MRAP')", 'reopened': False},
               {'error': None, 'reopened': True}]
    assert export.reopen_once_more(lambda: replies.pop(0))['reopened'] is True
    calls = []
    assert export.reopen_once_more(lambda: calls.append(1) or {'error': 'the file is damaged'})['error'] == 'the file is damaged'
    assert len(calls) == 1


def _carton_spec(tmp_path, **changes):
    """A generic carton's print file, by the law: one flat ground, motifs as named objects on their panels' sub-layers."""
    a = np.zeros((300, 300, 4), np.uint8)
    a[...] = (200, 90, 70, 255)
    Image.fromarray(a, 'RGBA').save(tmp_path / 'bloom.png')
    spec = {'id': 'carton', 'title': 'carton', 'size_mm': [180, 80], 'law': True, 'panels': {'panel 0': 2400, 'panel 1': 2400},
            'ground': [{'name': 'panel 0 / ground', 'panel': 'panel 0', 'hex': '#1F3A33', 'rings_mm': [[[7, 7], [91, 7], [91, 73], [7, 73]]]},
                       {'name': 'panel 1 / ground', 'panel': 'panel 1', 'hex': '#1F3A33', 'rings_mm': [[[89, 7], [173, 7], [173, 73], [89, 73]]]}],
            'motifs': [{'kind': 'picture', 'panel': 'panel 0', 'name': 'panel 0 / bloom 01', 'path': str(tmp_path / 'bloom.png'), 'box_mm': [20, 20, 40, 40]},
                       {'kind': 'vector', 'panel': 'panel 1', 'name': 'panel 1 / band 1', 'paths': faces.woven_band(90, 170, 30, 3, '#B88A3E', '#C4A04C')}],
            'finishes': [], 'type_runs': [], 'logos': [], 'printed_mm': _carton_rings(), 'guides': [],
            'die': {'cut': [{'points_mm': [[10, 10], [170, 10], [170, 70], [10, 70]], 'closed': True}],
                    'fold': [{'points_mm': [[90, 10], [90, 70]], 'closed': False}]}}
    spec.update(changes)
    return spec


def test_a_carton_written_by_the_law_keeps_each_piece_apart_on_its_layer(tmp_path):
    from apps.pipeline.services import round_files_export as export
    made = export.export_object(_carton_spec(tmp_path), tmp_path / 'out', native=False)
    checked = json.loads((tmp_path / 'out' / 'carton.print-check.json').read_text())
    assert checked['holds'] and checked['law']['motif_objects'] == 2 and checked['law']['ground'] == ['#1F3A33']
    rows = {row['name']: row for row in made['elements']}
    assert rows['panel 0 / bloom 01']['layer'] == 'MOTIFS' and rows['panel 1 / band 1']['layer'] == 'MOTIFS'
    assert rows['panel 0 / ground']['layer'] == 'GROUND'


def test_the_law_fails_a_second_ground_a_painting_a_shared_name_and_a_die_in_the_art(tmp_path):
    from apps.pipeline.services import round_files_export as export
    good = _carton_spec(tmp_path)
    two = _carton_spec(tmp_path)
    two['ground'][1]['hex'] = '#E8DCC2'
    with pytest.raises(ValueError, match='not one flat colour'):
        export.export_object(two, tmp_path / 'two', native=False)
    painted = _carton_spec(tmp_path, artwork=[{'name': 'whole', 'path': str(tmp_path / 'bloom.png'), 'box_mm': [7, 7, 173, 73]}])
    with pytest.raises(ValueError, match='fused with the die'):
        export.export_object(painted, tmp_path / 'painted', native=False)
    shared = _carton_spec(tmp_path)
    shared['motifs'][1]['name'] = shared['motifs'][0]['name']
    with pytest.raises(ValueError, match='share a name'):
        export.export_object(shared, tmp_path / 'shared', native=False)
    too_big = _carton_spec(tmp_path)
    too_big['motifs'][0]['box_mm'] = [7, 7, 91, 73]
    with pytest.raises(ValueError, match='is not a motif'):
        export.export_object(too_big, tmp_path / 'big', native=False)
    # what Illustrator holds: a motif melted into something else, or art on the die, fails on the census
    census = {'objects': [{'name': 'panel 1 / band 1', 'type': 'GroupItem', 'layer': 'MOTIFS/panel 0'},
                          {'name': '', 'type': 'RasterItem', 'layer': 'DIE/CUT'}]}
    law = export.law_check(good, [], census)
    assert any('not their own objects' in fault for fault in law['faults'])
    assert any('off their panel' in fault for fault in law['faults'])
    assert any('merged with art' in fault for fault in law['faults'])


def _plan_on_carton(**changes):
    from shapely.geometry import box
    plan = {'key': 'panel 0', 'motifs': [], 'finishes': [], 'zones': [], 'words': {'contrast': []}}
    plan.update(changes)
    return plan, box(0, 0, 40, 60)


def test_placement_fails_a_motif_in_a_quiet_zone_over_a_fold_on_another_or_under_the_contrast():
    bloom = lambda name, b: {'kind': 'picture', 'name': name, 'box_mm': b, 'ppi': 400.0}     # noqa: E731
    plan, outline = _plan_on_carton(motifs=[bloom('a', [5, 5, 15, 15]), bloom('b', [20, 5, 30, 15])])
    assert faces.placement_check(plan, outline)['holds']
    for changes, rule in (({'motifs': [bloom('a', [5, 5, 15, 15])], 'zones': [{'name': 'logo', 'box': [10, 10, 30, 30]}]}, 'enters a quiet zone'),
                          ({'motifs': [bloom('a', [35, 5, 45, 15])]}, 'crosses a fold or cut line'),
                          ({'motifs': [bloom('a', [5, 5, 15, 15]), bloom('b', [10, 10, 20, 20])]}, 'collides'),
                          ({'words': {'contrast': [{'what': 'line', 'colour': '#B88A3E', 'on': '#1F3A33'}]}}, 'contrast under 4.5:1')):
        plan, outline = _plan_on_carton(**changes)
        checked = faces.placement_check(plan, outline)
        assert not checked['holds'] and checked['faults'][0]['rule'] == rule, changes


def test_word_colour_keeps_to_the_design_and_never_lowers_the_bar():
    assert faces.contrast_ratio('#B88A3E', '#1F3A33') < 4.5                     # Ochre Thread does not read on Verdure Green
    assert faces.word_colour(['#1F3A33'], ['#B88A3E', '#C4A04C']) == '#C4A04C'
    assert faces.contrast_ratio(faces.word_colour(['#C9707A'], ['#1F3A33']), '#C9707A') >= 4.5    # none does: ink that does


def test_the_press_drops_a_thin_finish_to_ink_and_lists_it_and_fails_a_soft_picture():
    line = lambda w: {'d': [['M', 0, 0], ['L', 10, 0]], 'stroke': '#C4A04C', 'stroke_mm': w}     # noqa: E731
    gap = [line(.15), {'d': [['M', 0, .25], ['L', 10, .25]], 'stroke': '#C4A04C', 'stroke_mm': .15}]
    plan, _o = _plan_on_carton(finishes=[{'finish': 'foil', 'name': 'thin foil', 'paths': [line(.05)]},
                                         {'finish': 'foil', 'name': 'tight foil', 'paths': gap},
                                         {'finish': 'relief', 'name': 'thin relief', 'paths': [line(.2)]},
                                         {'finish': 'foil', 'name': 'good foil', 'paths': [line(.12)]},
                                         {'finish': 'relief', 'name': 'good relief', 'paths': [line(.35)]}])
    checked = faces.press_check(plan)
    assert sorted(checked['dropped_to_ink']) == ['thin foil', 'thin relief', 'tight foil'] and checked['holds']
    assert [item['name'] for item in plan['finishes']] == ['good foil', 'good relief']
    assert {item['name'] for item in plan['motifs']} == {'thin foil (in ink)', 'tight foil (in ink)', 'thin relief (in ink)'}
    plan, _o = _plan_on_carton(motifs=[{'kind': 'picture', 'name': 'soft', 'box_mm': [0, 0, 40, 40], 'ppi': 150.0},
                                       {'kind': 'vector', 'name': 'open', 'paths': [{'d': [['M', 0, 0], ['L', 1, 0]], 'fill': '#000000'}]},
                                       {'kind': 'vector', 'name': 'stray', 'paths': [{'d': [['M', 0, 0]], 'stroke': '#000000', 'stroke_mm': .2}]}])
    checked = faces.press_check(plan)
    assert not checked['holds'] and sorted(checked['failed']) == ['open', 'soft', 'stray'] and checked['lowest_ppi'] == 150.0


def test_a_band_is_whole_units_so_two_panels_meet_as_a_matched_pair_at_their_fold():
    left, right = faces.woven_band(0, 40, 10, 3, '#B88A3E', '#C4A04C'), faces.woven_band(40, 72, 10, 3, '#B88A3E', '#C4A04C')
    assert faces._paths_box(left)[2] == pytest.approx(40, abs=.2) and faces._paths_box(right)[0] == pytest.approx(40, abs=.2)
    assert left[0]['d'][1][1] == 40 and right[0]['d'][0][1] == 40          # the rules run flush to the fold from either side


def test_a_motif_is_cut_out_of_its_cell_on_the_plain_ground_and_a_bad_cell_is_dropped(tmp_path):
    W, H = faces.SHEET_SIZE
    art = np.full((H, W, 3), (31, 58, 51), np.uint8)
    cells = faces.sheet_cells()
    for index, cell in enumerate(cells):
        x0, y0, x1, y1 = cell['box']
        if index == 1:
            continue                                                            # left empty
        ys, xs = np.mgrid[y0:y1, x0:x1]
        if index == 2:
            art[y0:y1, x0:x1] = (200, 160, 60)                                  # ran out of its cell
            continue
        art[y0:y1, x0:x1][(xs - (x0 + x1) / 2) ** 2 + (ys - (y0 + y1) / 2) ** 2 < (min(y1 - y0, x1 - x0) * .35) ** 2] = (200, 90, 70)
    Image.fromarray(art).save(tmp_path / 'raw.png')
    library = faces.cut_sheet(tmp_path / 'raw.png', tmp_path / 'pieces', hero_name='doe')
    assert {row['id'] for row in library['dropped']} == {cells[1]['id'], cells[2]['id']}
    hero = next(piece for piece in library['pictures'] if piece['hero'])
    assert hero['name'] == 'doe' and hero['max_mm'][0] > 25
    with Image.open(hero['file']) as image:
        rgba = np.asarray(image.convert('RGBA'))
    assert rgba[0, 0, 3] == 0 and rgba[rgba.shape[0] // 2, rgba.shape[1] // 2, 3] == 255     # a clean mask, nothing of the ground kept
    middle = rgba[rgba.shape[0] // 2, rgba.shape[1] // 2, :3]
    assert middle.tolist() == pytest.approx([200, 90, 70], abs=3)
    assert len(library['pictures']) == 11 and all(len(piece['sha256']) == 64 for piece in library['pictures'])


def test_a_clear_face_shows_its_liquid_in_the_drawing_never_white(tmp_path):
    rgba = np.zeros((20, 20, 4), np.uint8)
    rgba[5:10, 5:10] = (196, 160, 76, 255)
    Image.fromarray(rgba, 'RGBA').save(tmp_path / 'face.png')
    faces.on_liquid(tmp_path / 'face.png', '#C9707A', tmp_path / 'view.png')
    with Image.open(tmp_path / 'view.png') as image:
        view = np.asarray(image.convert('RGB'))
    assert view[0, 0].tolist() == [0xC9, 0x70, 0x7A] and view[7, 7].tolist() == [196, 160, 76]


def test_a_crack_at_a_fold_is_found_at_400_percent(tmp_path):
    from apps.pipeline.services import round_files_export as export
    die, _frame = _carton_die()
    def ground(x0, x1):
        return {'name': 'g%g' % x0, 'panel': 'p', 'hex': '#1F3A33', 'rings_mm': [[[x0, 0], [x1, 0], [x1, 60], [x0, 60]]]}
    whole = {'id': 'whole', 'title': 'x', 'size_mm': [160, 60], 'ground': [ground(0, 41), ground(39, 160)], 'motifs': [], 'finishes': [],
             'type_runs': [], 'logos': [], 'die': {}, 'guides': []}
    made = export.export_object(whole, tmp_path / 'whole', native=False)
    assert faces.seam_proof(made['ai'], die, tmp_path / 'seams-whole')['cracks'] == 0
    cracked = dict(whole, id='cracked', ground=[ground(0, 39.8), ground(40.2, 160)])
    made = export.export_object(cracked, tmp_path / 'cracked', native=False)
    proof = faces.seam_proof(made['ai'], die, tmp_path / 'seams-cracked')
    assert not proof['holds'] and proof['creases'][0]['gap_pixels'] > 0 and Path(proof['creases'][0]['picture']).exists()


def test_a_house_file_is_judged_by_what_it_holds_not_by_its_caption(tmp_path):
    def page_with(name, fill_box):
        doc = fitz.open()
        page = doc.new_page(width=100, height=100)
        shape = page.new_shape()
        shape.draw_rect(fitz.Rect(*fill_box))
        shape.finish(fill=(1, 0, 0))
        shape.commit()
        doc.save(tmp_path / name)
        doc.close()
        return tmp_path / name
    assert 'whole layout' in faces.library_piece_verdict(page_with('card.ai', (0, 0, 100, 100)))
    assert faces.library_piece_verdict(page_with('motif.ai', (10, 10, 30, 30))).startswith('one motif')
    assert 'not on disk' in faces.library_piece_verdict(tmp_path / 'gone.ai')
    assert faces.library_piece_verdict(tmp_path / 'x.eps').startswith('refused')


def test_illustrator_is_given_time_for_a_small_file_of_many_objects(tmp_path):
    from apps.pipeline.services import round_files_export as export
    (tmp_path / 'small.ai').write_bytes(b'x' * 3_000_000)
    assert export.native_timeout(tmp_path / 'small.ai') == export.NATIVE_TIMEOUT_S[0]
    assert export.native_timeout(tmp_path / 'small.ai', 150) == 150 * export.NATIVE_SECONDS_PER_OBJECT > 180


def test_a_fitted_piece_is_refused_by_the_writer(tmp_path):
    from apps.pipeline.services import round_files_export as export
    spec = {'id': 'traced', 'title': 'traced', 'size_mm': [60, 40], 'type_runs': [], 'logos': [],
            'face_layers': [{'layer': 'SHAPES', 'name': 'piece', 'fill': '#14284F',
                             'rings_mm': [[[0, 0], [60, 0], [60, 40], [0, 40]]]}],
            'artwork': [], 'die': {'cut': []}, 'guides': []}
    with pytest.raises(ValueError, match='never laid over the painting'):
        export.export_object(spec, tmp_path / 'out', native=False)


def test_a_file_with_a_traced_layer_and_a_stray_fragment_fails_its_check(tmp_path):
    """The owner's fault as he found it on round 4's stand: a SHAPES layer over the painting and a fragment outside
    the die. A fixture carton file written with both fails, in words, on each."""
    from apps.pipeline.services import round_files_export as export
    doc = fitz.open()
    page = doc.new_page(width=180 * export.PT, height=80 * export.PT)
    layers = {name: doc.add_ocg(name, on=True) for name in ('PAINTING', 'SHAPES', 'DIE')}
    page.insert_image(fitz.Rect(0, 0, 180 * export.PT, 80 * export.PT), filename=_painting_on(tmp_path, (180, 80)),
                      oc=layers['PAINTING'])
    shape = page.new_shape()
    shape.draw_rect(fitz.Rect(20 * export.PT, 20 * export.PT, 30 * export.PT, 30 * export.PT))   # over the painting
    shape.draw_rect(fitz.Rect(90 * export.PT, 75 * export.PT, 95 * export.PT, 79 * export.PT))   # stray, off the die
    shape.finish(fill=(0, .2, .1), color=None, oc=layers['SHAPES'])
    shape.commit()
    doc.save(tmp_path / 'traced.ai')
    doc.close()
    checked = export.print_check(tmp_path / 'traced.ai', _carton_rings())
    assert not checked['holds']
    assert any('SHAPES' in fault for fault in checked['faults'])
    assert any('outside' in fault for fault in checked['faults'])
    assert checked['outside_mm2'] >= 15


@pytestmark_db
def test_a_proof_made_for_older_rules_is_made_again_at_no_cost(execution):
    """When every face is drawn but the proof on record was made for other drawings or older rules, the worker's next
    run makes it again — no edit, no text call."""
    from apps.pipeline.services import round_files_gate as job
    job.start(execution.record.pk, execution.owner)
    build, _ = execution.drain()
    path = job.root(build) / 'proof' / 'current.json'
    record = json.loads(path.read_text())
    record['signature'] = 'older'
    path.write_text(json.dumps(record))
    calls = (execution.edit.call_count, execution.text.messages.create.call_count)
    job.enqueue(build.pk)
    build, statuses = execution.drain()
    assert build.state == 'awaiting', (build.error, statuses)
    assert (execution.edit.call_count, execution.text.messages.create.call_count) == calls
    assert json.loads(path.read_text())['signature'] != 'older'


@pytestmark_db
def test_the_restart_check_is_the_chains_own_preflight(monkeypatch):
    """The owner's goal of 2026-10-29, §5: the restart script's check is the chain's own (no ARIA preflight): every
    engine imports, the stand die resolves at 1.0, the pinned fonts and logo hold; a changed logo blocks it."""
    from apps.pipeline.services import round_files_export as export
    from apps.pipeline.services import round_files_gate as job
    result = job.chain_preflight()
    assert set(result['checks']) == {'engines_import', 'stand_die_resolves', 'pinned_fonts', 'approved_logo',
                                     'image_model', 'spend_ledger'}
    assert result['checks']['engines_import']['ok'] and result['checks']['stand_die_resolves']['ok']
    monkeypatch.setattr(export, 'LOGO_SHA256', '0' * 64)
    blocked = job.chain_preflight()
    assert blocked['result'] == 'BLOCKED' and not blocked['checks']['approved_logo']['ok']


def _red_top_painting(tmp_path, geometry, wrong=()):
    """A painting of the flat die whose every face has its top half red, turned to the face's own fold before painting
    (its ``up`` on the sheet); a face in ``wrong`` is painted upright on the sheet instead, as D1's back panel was."""
    from apps.dielines.exporters import counter_display_files as cdf
    die = faces.die_of(geometry)
    setup = faces.flat_setup(geometry, tmp_path / 'flat')
    masks = cdf.flat_masks(die, setup['frame'])
    up = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}
    raw = np.full(masks['owner'].shape + (3,), 255, np.uint8)
    for key, spec in faces.FACES.items():
        if faces.stand_face(key):
            ys, xs = np.nonzero(masks['owner'] == masks['names'].index(spec['die'][1]) + 1)
            dx, dy = up[0 if key in wrong else spec['quarters']]
            top = (xs - xs.mean()) * dx + (ys - ys.mean()) * dy > 0
            raw[ys, xs] = (20, 40, 200)
            raw[ys[top], xs[top]] = (220, 20, 20)
    out = tmp_path / ('painting-wrong' if wrong else 'painting')
    out.mkdir(parents=True)
    Image.fromarray(raw).save(out / 'raw.png')
    return dict(faces.settle_flat(out / 'raw.png', tmp_path / 'flat', out, geometry), n=1)


def _folded_views(tmp_path, painting, geometry, name):
    """The folded drawing of a painting, cut into its three views (front, right side, back) at the sheet's gaps."""
    from apps.pipeline.services import product_drawing as pd
    views = {}
    for key in faces.FACES:
        if faces.stand_face(key):
            upright, frame_mm, _box = faces.painted_face(painting, key, geometry)
            faces.trim_view(upright, frame_mm).save(tmp_path / (name + key + '.png'))
            views[key] = str(tmp_path / (name + key + '.png'))
    drawn = faces.folded_drawing(views, geometry, tmp_path / name)
    sheet = np.asarray(Image.open(drawn['file']).convert('RGB')).astype(int)[30:]
    ink = ~(np.abs(sheet - np.array(pd.SHEET)).sum(axis=-1) < 6)
    columns = ink.any(axis=0)
    edges = np.flatnonzero(np.diff(np.r_[0, columns.astype(int), 0]))
    spans = [(a, b) for a, b in zip(edges[::2], edges[1::2]) if b - a > 20]
    return {view: sheet[:, a:b] for view, (a, b) in zip(drawn['views'], spans)}


def _red_above_blue(view):
    red = (view[..., 0] > 150) & (view[..., 2] < 100)
    blue = (view[..., 2] > 150) & (view[..., 0] < 100)
    return np.argwhere(red)[:, 0].mean() < np.argwhere(blue)[:, 0].mean()


def test_each_panel_turned_to_its_fold_before_painting_stands_upright_on_the_folded_drawing(tmp_path):
    """The owner, 2026-10-29 (round 4, fault 4): "The painter must turn each panel's artwork to match its fold before
    painting. Test it with the folded drawing." A painting whose every face carries its top (red) toward the face's own
    up on the sheet reads red-above-blue on the folded drawing's side and back; the same painting with the back panel
    painted upright on the sheet — D1's fault — reads upside down there. The painter's words say so."""
    geometry = stand_geometry(tmp_path)
    turned = _folded_views(tmp_path, _red_top_painting(tmp_path, geometry), geometry, 'turned')
    assert _red_above_blue(turned['right side'])
    back = turned['back']
    assert _red_above_blue(back[back.shape[0] // 2:])                                      # the back panel, below its header
    wrong = _folded_views(tmp_path, _red_top_painting(tmp_path, geometry, wrong=('back',)), geometry, 'wrong')
    assert not _red_above_blue(wrong['back'][wrong['back'].shape[0] // 2:])                  # upside down when folded
    setup = faces.flat_setup(geometry, tmp_path / 'flat')
    words = faces.flat_prompt(setup, style='x')
    assert 'Turn each face\'s artwork to its own fold before you paint it' in words
    assert 'paint them upside down on this sheet' in words and 'its top is toward the bottom of the sheet' in words


def test_the_owner_s_hard_rules_reach_every_face_prompt_before_its_words():
    """The owner, 2026-10-29 (round 4, fault 1): the pick reason and the redraw notes reach every face drawing as hard
    rules, above image 2's "follow EXACTLY", with every motif upright; a line naming another brand is never sent."""
    rules = faces.hard_rules(['roses', 'petals'], ['Replace every rose with fig, ember or wildflowers.', 'Like Dior.'],
                             ['No roses on this wall.'])
    assert rules.startswith(faces.HARD_RULES) and 'Never draw these motifs, in any form or size: roses, petals' in rules
    assert '"Replace every rose with fig, ember or wildflowers."' in rules and '"No roses on this wall."' in rules
    assert 'Dior' not in rules
    assert faces.hard_rules([], []) == ''
    # the brief's truths outrank image 2's ground: round 4's cap took the header's green over "stays gold"
    truth = faces.hard_rules([], truths=['The gold square cap stays gold; its marks may be engraving or foil.'])
    assert '- The product\'s truth: "The gold square cap stays gold; its marks may be engraving or foil."' in truth
    words = faces.panel_prompt('back', {'w_mm': 113.0, 'h_mm': 104.5, 'bleed_mm': 3.0}, rules=rules)
    assert words.index(faces.REFERENCE_WORDS['painting']) < words.index(rules) < words.index(faces.NO_WORDS)
    assert faces.UPRIGHT_WORDS in words
    assert rules in faces.net_prompt('bottle', {'frame': {'canvas_px': [1024, 1536]}, 'faces': []}, rules=rules)


def test_edge_distances_are_read_for_any_number_of_points():
    """Round 4: the header's, header back's and back's previews failed in OpenCV's remap ("dst.rows < SHRT_MAX"): a
    300 PPI face samples more than 32,767 edge points, more than one remap column holds. Read in rows, every point is
    read, and each equals the field's own bilinear value."""
    rng = np.random.default_rng(4)
    field = rng.random((900, 1400)).astype(np.float32)
    points = np.column_stack([rng.uniform(0, 1398, 70_001), rng.uniform(0, 898, 70_001)])
    got = faces.read_between(field, points)
    x0, y0 = np.floor(points[:, 0]).astype(int), np.floor(points[:, 1]).astype(int)
    fx, fy = points[:, 0] - x0, points[:, 1] - y0
    want = (field[y0, x0] * (1 - fx) * (1 - fy) + field[y0, x0 + 1] * fx * (1 - fy) +
            field[y0 + 1, x0] * (1 - fx) * fy + field[y0 + 1, x0 + 1] * fx * fy)
    assert got.shape == (70_001,) and np.abs(got - want).max() < 1e-2
    assert faces.read_between(field, np.zeros((0, 2))).shape == (0,)


def test_a_side_wall_follows_the_back_panel_s_drawing_with_its_bands_level(tmp_path):
    """The owner, 2026-10-29 (round 4): "both side walls (bands level when folded, not sideways)". A wall drawn after
    the back follows the back's drawing: at the wall's scale, floor edges level, cut from the corner the two share and
    mirrored there, so a band at a height on the back is the band at that height on the wall."""
    bands = np.zeros((300, 400, 3), np.uint8)
    for row, colour in enumerate(((200, 30, 30), (30, 200, 30), (30, 30, 200))):
        bands[row * 100:(row + 1) * 100] = colour
    bands[:, :5] = (250, 250, 0)                                          # the back's left edge, marked
    Image.fromarray(bands).save(tmp_path / 'back.png')
    pattern = {'face': str(tmp_path / 'back.png'), 'template': {'px_per_mm': 10.0}, 'n': 2}
    right = np.asarray(faces.pattern_reference(pattern, 'side', (250, 240), 10.0))
    left = np.asarray(faces.pattern_reference(pattern, 'left', (250, 240), 10.0))
    assert right.shape == left.shape == (240, 250, 3)
    for wall in (right, left):
        assert (wall[-100:, 100] == (30, 30, 200)).all() and (wall[40:140, 100] == (30, 200, 30)).all()  # level, floor up
    assert (right[:, -1] == (250, 250, 0)).all() and not (left[:, -1] == (250, 250, 0)).all()          # the corner
    assert faces.WALL_PATTERN == {'side': 'back', 'left': 'back'} and 'LEVEL' in faces.REFERENCE_WORDS['pattern']


def test_a_product_net_takes_the_design_s_motif_onto_its_own_material_not_the_header_s_ground():
    """Round 4: the cap came back twice on the header's green, told to take "its ground, colours" from image 2, though
    the brief says "The gold square cap stays gold". The cap carries the motif as engraving or foil on its own gold;
    the bottle as print on its clear body."""
    setup = {'frame': {'canvas_px': [1536, 1024]}, 'faces': []}
    cap = faces.net_prompt('cap', setup, style_only=True)
    bottle = faces.net_prompt('bottle', setup, style_only=True)
    assert 'on the cap\'s own gold metal' in cap and 'never image 2\'s ground colour' in cap and 'its ground, colours' not in cap
    assert 'print on its clear acrylic body' in bottle and 'never image 2\'s ground colour' in bottle
    assert 'nothing is opaque' in bottle and 'the label areas included' in bottle
    # the owner's note is the last word, after the no-words line's plain label areas (round 4's front, 2026-10-30)
    note = 'The band pattern across the whole strip, not plain green.'
    for words in (faces.net_prompt('bottle', setup, style_only=True, note=note),
                  faces.panel_prompt('front', {'w_mm': 113.0, 'h_mm': 29.5, 'bleed_mm': 3.0}, note=note)):
        assert words.endswith(faces.NOTE_LAST % note) and words.index(faces.NO_WORDS) < words.index(faces.NOTE_LAST % note)


@pytestmark_db
def test_a_lost_call_is_asked_again_until_the_provider_answers_and_released_only_if_unbilled(settings, tmp_path,
                                                                                               monkeypatch):
    """The owner, 2026-10-30: "A call that gets nothing back in 8 minutes isn't simply lost: check its outcome with the
    provider before giving up, so it's never charged twice." Without an admin key, nothing is checked and the hold
    stays; before OpenAI's usage for the window is final, the check waits; once final, the app's own other images in
    the window are not this call's: one more image is billed (kept), none more is unbilled (released to $0)."""
    import datetime as dt
    import httpx
    from apps.pipeline.services import round_files_gate as gate, spend_reservation as spend
    settings.RESCUE_SPEND_ROOT = tmp_path / 'spend'
    settings.OPENAI_ADMIN_KEY = ''
    assert gate.provider_check('openai', 'x')['checked'] is False                          # no key: no lookup
    settings.OPENAI_ADMIN_KEY = 'admin-test-key'
    start = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
    with spend._connect() as db:
        db.execute("INSERT INTO calls VALUES ('lost','d','openai','files/r/image/face/bottle/2','gpt-image-2',NULL,"
                   "350000,350000,'outcome_unknown',NULL,'{}',NULL,?,?)", (start.isoformat(), start.isoformat()))
        db.execute("INSERT INTO calls VALUES ('mine','d','openai','files/r/image/face/left/2','gpt-image-2',NULL,"
                   "350000,231500,'usage_recorded',NULL,'{}',NULL,?,?)",
                   ((start - dt.timedelta(minutes=2)).isoformat(), (start - dt.timedelta(seconds=26)).isoformat()))
    replies = []
    monkeypatch.setattr(httpx, 'get', lambda *a, **k: SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: {'data': [{'results': [{'images': replies[-1]}]}]}))
    replies.append(1)
    check = gate.provider_check('openai', 'lost')
    assert check['checked'] and check['billed'] is False and check['own_images_in_window'] == 1    # the left wall's
    replies.append(2)
    assert gate.provider_check('openai', 'lost')['billed'] is True                                 # one more: billed
    assert spend.release_unknown('lost', check)
    with spend._connect() as db:
        assert tuple(db.execute("SELECT state, accounted FROM calls WHERE id='lost'").fetchone()) == ('released_unbilled', 0)
    with spend._connect() as db:
        db.execute("UPDATE calls SET started_at=? WHERE id='mine'", (dt.datetime.now(dt.timezone.utc).isoformat(),))
    assert gate.provider_check('openai', 'mine').get('pending') is True                            # not final yet


def test_a_flat_pick_s_words_are_the_brief_s_placed_in_its_plain_areas(tmp_path):
    """The owner, 2026-10-30: "Place the words first". A flat pick shows no words, so the brief's are placed: the logo
    in the header's plain band (alone when the band is thin), "Lip Gloss" in the right wall's empty frame, the logo
    over the line across the front strip, and the bottle's logo, product and shade along its length; never on the
    white outside a face's printed shape."""
    face = {'w_mm': 80.0, 'h_mm': 40.0, 'bleed_mm': 3.0, 'safe_mm': 2.0}
    k = 10.0
    W, H = int(86 * k), int(46 * k)
    rng = np.random.default_rng(5)
    pattern = rng.integers(0, 255, (H, W, 3), dtype=np.uint8)
    pattern[int(37 * k):int(43 * k), int(5 * k):int(80 * k)] = (20, 60, 40)                 # a thin plain band
    Image.fromarray(pattern).save(tmp_path / 'face.png')
    sheet = Image.new('RGBA', (W, H), (255, 255, 255, 0))
    sheet.save(tmp_path / 'template.png')
    drawn = {'face': str(tmp_path / 'face.png'), 'template': {'px_per_mm': k, 'frame_px': [0, 0, W, H],
                                                              'template': str(tmp_path / 'template.png')}}
    area = faces.plain_area_mm(drawn)
    assert area is not None and 37 <= area[1] <= 39 and 41 <= area[3] <= 43
    brief = {'copy': {'brand': 'BBROSE', 'product': 'Lip Gloss'}, 'shades': [{'name': 'Rose Glass'}]}
    header = faces.flat_marks('header', brief, face, drawn)
    assert len(header['logos']) == 1 and header['type'] == [] and header['placement']['flat_words'] == 'band'
    bottle = faces.flat_marks('bottle', brief, {'w_mm': 15.0, 'h_mm': 70.0, 'bleed_mm': 0.0, 'safe_mm': 0.5}, None)
    assert [row['copy'] for row in bottle['type']] == ['Lip Gloss', 'Rose Glass'] and bottle['logos'][0]['rotation'] == 90
    assert all(row['size_pt'] >= faces.MIN_SIZE_PT for row in bottle['type'])
    assert faces.flat_marks('cap', brief, face, drawn) == {'type': [], 'logos': [], 'zones': []}
    sheet = Image.new('RGBA', (W, H), (255, 255, 255, 255))                                 # nothing printed: no area
    sheet.save(tmp_path / 'template.png')
    assert faces.plain_area_mm(drawn) is None


@pytestmark_db
def test_a_stand_painted_panel_by_panel_is_measured_then_rebuilt_as_one_wrap_from_its_own_art(execution, monkeypatch, tmp_path):
    """The owner's order for round 4 (2026-10-30), as a generic build: its faces painted one by one fail the folds and the
    ground; relink raises the cap in his words, measures them first, and claims the wrap once; the wrap is painted from
    their art; every face comes back to the owner; the ground holds in the picture, with no flat layer."""
    from apps.pipeline.services import round_files_gate as job
    build, _geometry, _flat = _start_flat_pick(execution)
    folder = job.root(build)
    (flow_root := execution.root / 'board-pick.json').write_text(json.dumps(
        {'board': {'palette': [{'hex': '#1F3A33', 'name': 'Verdure Green', 'role': 'Deep tapestry ground'},
                               {'hex': '#E8DCC2', 'name': 'Wool Cream', 'role': 'Fine weave'}]}}))
    assert faces.design_ground(execution.record) == {'hex': '#1F3A33', 'name': 'Verdure Green'} and flow_root.exists()
    # each stand face as if painted on its own: a cream wall, the others on their own bands
    claim = json.loads((folder / 'flat' / 'claim.json').read_text())
    claim.pop('wrap')
    (folder / 'flat' / 'claim.json').write_text(json.dumps(claim))
    rows = job.board(build)
    for index, key in enumerate(job.wrap_panels()):
        path = folder / job.current(rows[key])['face']
        with Image.open(path) as image:
            art = np.asarray(image.convert('RGB')).copy()
        art[..., :] = (232, 220, 194) if key == 'left' else (31, 58, 51)
        art[(np.arange(art.shape[0]) // (30 + 7 * index)) % 5 == 1] = (184, 138, 62)
        Image.fromarray(art).save(path)
        record_path = folder / job.current(rows[key])['record']
        record = json.loads(record_path.read_text())
        record['face_sha256'] = sha(path)
        record_path.write_text(json.dumps(record))
        job.current(rows[key])['face_sha256'] = sha(path)
    build.save()
    calls = execution.edit.call_count
    measured = job.relink(execution.record.pk, cap_usd=4.6, words='I raise it to $4.60 for this, this round only.')
    assert not measured['folds']['holds'] and 'left' in measured['ground']['off']
    assert json.loads((folder / 'flat' / 'rules-before.json').read_text())['ground']['off'] == measured['ground']['off']
    build, statuses = execution.drain(limit=80)
    assert build.state == 'awaiting', (build.error, statuses)
    assert float(build.budget_usd) == 4.6
    claim = json.loads((folder / 'flat' / 'claim.json').read_text())
    assert claim['budget_usd'] == 4.6 and claim['cap_raised_1']['was_usd'] == 10 and claim['wrap']['attempt'] == 2
    assert execution.edit.call_count == calls + 2                              # the wrap and the header, nothing else
    rows = job.board(build)
    assert {key: rows[key]['state'] for key in rows} == {key: 'drawn' for key in rows}
    assert {job.current(rows[key])['source'] for key in rows if faces.stand_face(key)} == {'wrap'}
    rules = json.loads((folder / 'flat' / 'rules.json').read_text())
    assert rules['ground']['holds'] and rules['folds']['holds'], rules
    # the print files are the painting whole: no fitted piece, nothing off the die
    specs_, _p = faces.specs({key: job._panel_record(build, job.current(row)) for key, row in rows.items()},
                             json.loads((folder / 'inspection.json').read_text()), job.files_brief(build),
                             json.loads((folder / 'stand.json').read_text()), tmp_path / 'specs')
    stand = next(spec for spec in specs_ if spec['id'] == 'stand')
    assert not stand.get('face_layers') and len(stand['artwork']) == 1


@pytestmark_db
def test_a_panel_off_its_ground_is_repainted_once_inside_the_cap_and_then_named(execution):
    from apps.pipeline.services import round_files_gate as job
    build, _geometry, _flat = _start_flat_pick(execution)
    folder = job.root(build)
    (execution.root / 'board-pick.json').write_text(json.dumps(
        {'board': {'palette': [{'hex': '#1F3A33', 'name': 'Verdure Green', 'role': 'ground'}]}}))
    rules = json.loads((folder / 'flat' / 'rules.json').read_text())
    rules['ground'] = {'ground_hex': '#1F3A33', 'bar_delta_e00': 4.0, 'holds': False, 'off': ['side'],
                       'panels': {'side': {'ground_hex': '#E8DCC2', 'delta_e00': 60.0, 'holds': False, 'share': .5}}}
    (folder / 'flat' / 'rules.json').write_text(json.dumps(rules))
    calls = execution.edit.call_count
    job.enqueue(build.pk)
    build, statuses = execution.drain(limit=40)
    assert build.state == 'awaiting', (build.error, statuses)
    assert execution.edit.call_count == calls + 1
    claim = json.loads((folder / 'flat' / 'claim.json').read_text())
    assert claim['wrap']['ground_repainted']['queued'] == ['side']
    assert len(job.board(build)['side']['drawings']) == 2
    # measured off again: never a second repaint
    rules = json.loads((folder / 'flat' / 'rules.json').read_text())
    rules['ground'] = dict(rules['ground'] or {}, ground_hex='#1F3A33', holds=False, off=['side'], bar_delta_e00=4.0,
                           panels={'side': {'ground_hex': '#E8DCC2', 'delta_e00': 60.0, 'holds': False, 'share': .5}})
    (folder / 'flat' / 'rules.json').write_text(json.dumps(rules))
    calls = execution.edit.call_count
    job.enqueue(build.pk)
    execution.drain(limit=40)
    assert execution.edit.call_count == calls


@pytestmark_db
def test_a_face_that_lost_the_plain_area_for_its_words_has_it_put_back_once_at_no_cost(execution, monkeypatch):
    from apps.pipeline.services import round_files_gate as job
    build, _geometry, _flat = _start_flat_pick(execution)
    calls = execution.edit.call_count
    monkeypatch.setattr(faces, 'lost_word_place', lambda record, panel: [10.0, 10.0, 40.0, 20.0]
                        if record['key'] == 'side' else None)
    job.redraw(execution.record.pk, execution.owner, 'cap', '')             # any job: the repair follows when it settles
    calls += 1
    build, statuses = execution.drain(limit=40)
    assert build.state == 'awaiting', (build.error, statuses)
    assert execution.edit.call_count == calls                               # put back at $0, never a repaint
    assert json.loads((job.root(build) / 'flat' / 'claim.json').read_text())['wrap']['words_repainted'] == ['side']
    entry = job.current(job.board(build)['side'])
    assert 'plain area' in entry['eye']['why'] and not entry['note']        # never shown as a note of the owner's
    assert entry['cost_usd'] == 0.0 and entry['source'] == 'wrap'
    record = json.loads((job.root(build) / entry['record']).read_text())
    assert record['restored']['box_mm'] == [10.0, 10.0, 40.0, 20.0]
    job.enqueue(build.pk)
    execution.drain(limit=40)
    assert execution.edit.call_count == calls                               # once, and never paid


@pytestmark_db
def test_accept_all_accepts_what_waits_and_names_what_it_left(execution):
    from apps.pipeline.services import round_files_gate as job
    build, _geometry, _flat = _start_flat_pick(execution)
    rows = job.board(build)
    rows['cap'].update(state='queued')
    build.save()
    build, done, left = job.accept_all(execution.record.pk, execution.owner)
    assert 'cap' not in done and left == ['cap'] and len(done) == len(rows) - 1
    assert not job.ready(build)
    rows = job.board(build)
    rows['cap'].update(state='drawn')
    build.save()
    build, done, left = job.accept_all(execution.record.pk, execution.owner)
    assert done == ['cap'] and not left and job.ready(build)
    assert execution.client.post(reverse_files('accept_all', execution.record.pk)).status_code == 302


def reverse_files(name, pk):
    from django.urls import reverse
    return reverse('dashboard:product_round_files_' + name, args=[pk])


@pytestmark_db
def test_accept_redraw_and_accept_all_work_in_place_in_a_real_browser(execution, live_server, monkeypatch):
    """The owner, 2026-10-30: Accept and Redraw with no page reload, the scroll kept, the face's status updated; Accept all
    after one confirm; Make my files unlocks with no reload as soon as the last face is accepted."""
    from playwright.sync_api import sync_playwright
    monkeypatch.setenv('DJANGO_ALLOW_ASYNC_UNSAFE', 'true')
    _start_flat_pick(execution)
    session = execution.client.cookies['sessionid'].value
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        context.add_cookies([{'name': 'sessionid', 'value': session, 'url': live_server.url}])
        page = context.new_page()
        documents = []
        page.on('request', lambda request: documents.append(request.url)
                if request.is_navigation_request() else None)
        page.goto(live_server.url + '/dashboard/rounds/%d/built-files/' % execution.record.pk)
        assert page.get_by_role('button', name='Make my files').is_disabled()
        page.evaluate('window.__same_page = "yes"')
        card = page.locator('[data-face-card="header"]')
        card.scroll_into_view_if_needed()
        page.evaluate('window.scrollBy(0, 40)')
        at = page.evaluate('window.scrollY')
        card.get_by_role('button', name='Accept', exact=True).click()
        card.locator('.face-state', has_text='Accepted').wait_for(timeout=15000)
        assert page.evaluate('window.__same_page') == 'yes' and len(documents) == 1
        assert abs(page.evaluate('window.scrollY') - at) < 2
        # a Redraw in place: the face's status moves, the note typed on another face stays
        other = page.locator('[data-face-card="left"]').locator('input[name=note]')
        other.fill('a note still being typed')
        side = page.locator('[data-face-card="side"]')
        side.locator('input[name=note]').fill('Keep the frame')
        side.get_by_role('button', name='Redraw').click()
        side.locator('.face-state', has_text='Waiting to be drawn').wait_for(timeout=15000)
        assert page.evaluate('window.__same_page') == 'yes' and len(documents) == 1
        assert other.input_value() == 'a note still being typed'
        execution.drain(limit=40)
        side.locator('.face-state', has_text='Drawn, awaiting your Accept').wait_for(timeout=20000)     # it asks again
        assert page.evaluate('window.__same_page') == 'yes' and len(documents) == 1
        assert page.get_by_role('button', name='Make my files').is_disabled()
        # Accept all, one confirm
        summary = page.locator('[data-live="accept-all"] summary')
        summary.scroll_into_view_if_needed()
        assert page.get_by_role('button', name='Yes, accept all').is_visible() is False
        summary.click()
        page.get_by_role('button', name='Yes, accept all').click()
        page.locator('[data-face-card="cap"] .face-state', has_text='Accepted').wait_for(timeout=15000)
        make = page.get_by_role('button', name='Make my files')
        make.wait_for(timeout=15000)
        assert make.is_enabled()
        assert page.evaluate('window.__same_page') == 'yes' and len(documents) == 1
        assert page.locator('[data-face-card] .face-state').all_text_contents() == ['Accepted'] * 8
        browser.close()


@pytestmark_db
def test_a_new_round_is_separate_pieces_one_sheet_then_every_face_placed_at_no_cost_and_the_law_holds(execution, tmp_path):
    """The owner's part 1B, end to end on a flat pick: one paid sheet, every face placed by the engine, the hero on the header
    only, the words in their quiet zones, the file by the law, the same record behind the preview, the file and the drawings."""
    from apps.pipeline.services import round_files_export as export, round_files_gate as job
    (execution.root / 'board-pick.json').write_text(json.dumps(
        {'board': {'motif': 'Woven blooms with one doe', 'palette': [
            {'hex': '#1F3A33', 'name': 'Verdure Green', 'role': 'Deep tapestry ground'}, {'hex': '#E8DCC2', 'name': 'Wool Cream', 'role': 'Fine weave'},
            {'hex': '#B88A3E', 'name': 'Ochre Thread', 'role': 'Woven thread for stems'}, {'hex': '#C4A04C', 'name': 'Cap Gold', 'role': 'The only metallic'}]}}))
    build, _geometry, _flat = _start_flat_pick(execution, wrap=False)
    folder = job.root(build)
    assert build.state == 'awaiting', build.error
    assert execution.edit.call_count == 1                                       # one sheet
    assert execution.edit.call_args_list[0].kwargs['prompt'].startswith('Image 1 is a sheet of plain')
    build, board = board_of(execution)
    assert {job.current(row)['source'] for row in board.values()} == {'plan'}
    assert all(row['state'] == 'drawn' and job.current(row)['preview'] for row in board.values()), {k: job.current(r).get('preview_error') for k, r in board.items()}
    plans = {key: json.loads((folder / job.current(row)['face']).parent.joinpath('plan.json').read_text()) for key, row in board.items()}
    heroes = {key for key, plan in plans.items() if any(item.get('piece') == 'hero' for item in plan['motifs'])}
    assert heroes == {'header'}                                                 # the header back is pattern only
    assert plans['bottle']['ground'] is None and plans['bottle']['own_ground']
    assert plans['cap']['ground']['hex'] == '#C4A04C'
    assert not any(item['kind'] == 'picture' for item in plans['cap']['motifs'])  # a figure there would need tracing
    grounds = {plan['ground']['hex'] for key, plan in plans.items() if plan['ground'] and key not in faces.OWN_GOLD_FACES}
    assert grounds == {'#1F3A33'}
    for key, plan in plans.items():
        assert plan['placement']['holds'], (key, plan['placement']['faults'])
        assert plan['press']['holds'], (key, plan['press']['rows'])
    assert plans['header']['words']['logos'] and plans['front']['words']['logos']
    assert not list((folder / 'proof').glob('*-error.json')), [p.read_text() for p in (folder / 'proof').glob('*-error.json')]
    made = job.flat_page(build)['pieces']
    assert made['seams']['holds'] and made['seams']['creases'] and {row['layer'] for row in made['layers']} == set(export.LAYERS)
    assert len(made['library']) == 13 and job.flat_pins(build)[made['layers'][0]['png']] == made['layers'][0]['sha256']
    page = execution.client.get('/dashboard/rounds/%d/built-files/' % execution.record.pk)
    text = page.content.decode()
    assert page.status_code == 200 and "What you'll get" in text and 'Every fold at 400' in text
    for words in ("Your stand's die", 'cut-and-fold-1to1.pdf', 'stand/sheets/fold-up.png', 'stand/sheets/assembly.png', 'stand/sheets/die.dxf', 'Against the house'):
        assert words in text, words
    # Accept all; the files by the law; a Redraw with no note places the face again at no cost
    job.accept_all(execution.record.pk, execution.owner)
    job.make_files(execution.record.pk, execution.owner)
    build, statuses = execution.drain(limit=20)
    assert build.state == 'complete', (build.error, statuses)
    checked = json.loads(next((folder / 'revisions').glob('*/stand.print-check.json')).read_text())
    assert checked['holds'] and checked['law']['motif_objects'] > 10 and checked['law']['ground'] == ['#1F3A33']
    assert execution.edit.call_count == 1
    job.redraw(execution.record.pk, execution.owner, 'left', '')
    build, _s = execution.drain(limit=20)
    assert execution.edit.call_count == 1 and job.current(job.board(build)['left'])['n'] == 2
    # a note asks for a new sheet: the motifs are shared, so every face is placed again
    job.redraw(execution.record.pk, execution.owner, 'left', 'Make the blooms larger')
    build, _s = execution.drain(limit=40)
    assert execution.edit.call_count == 2 and 'Make the blooms larger' in execution.edit.call_args_list[1].kwargs['prompt']
    assert all(row['state'] == 'drawn' for row in job.board(build).values())


@pytestmark_db
def test_the_owners_order_moves_a_round_onto_a_new_die_at_no_cost_and_a_rejected_round_never(execution, tmp_path):
    """Part 2, §6: the stand solved on a template, the old one kept, every face placed again from the round's own library, none accepted,
    no paid call; a template stand is never solved again by itself; a rejected round is left alone."""
    from apps.pipeline.services import round_files_gate as job, round_flow as flow
    (execution.root / 'board-pick.json').write_text(json.dumps(
        {'board': {'motif': 'Woven blooms with one doe', 'palette': [
            {'hex': '#1F3A33', 'name': 'Verdure Green', 'role': 'Deep tapestry ground'}, {'hex': '#E8DCC2', 'name': 'Wool Cream', 'role': 'Soft woven thread'},
            {'hex': '#B88A3E', 'name': 'Ochre Thread', 'role': 'Woven thread for stems'}, {'hex': '#C4A04C', 'name': 'Cap Gold', 'role': 'Gold cap'}]}}))
    build, _geometry, _flat = _start_flat_pick(execution, wrap=False)
    calls = execution.edit.call_count
    folder = job.root(build)
    job.accept_all(execution.record.pk, execution.owner)
    job.redie(execution.record.pk, words='the owner\'s part 2, section 6', stand_type='stepped_tiered')
    assert list((folder / 'superseded').glob('stand-before-stepped_tiered-*/stand.json'))
    assert json.loads((folder / 'stand.json').read_text())['type'] == 'stepped_tiered' and (folder / 'redie-claim.json').exists()
    build, statuses = execution.drain(limit=20)
    assert build.state == 'awaiting', (build.error, statuses)
    assert execution.edit.call_count == calls, 'no paid call'
    board = build.steps['faces']['board']
    assert all(row['state'] == 'drawn' and row['accepted'] is None for row in board.values())
    assert job.restand(build) is None
    faces_folder = json.loads((folder / 'stand.json').read_text())
    assert faces_folder['record']['template']['id'] == 'stepped_tiered'
    # the chain places every type's faces, the law holding on each: their shapes differ, the six faces do not
    for other in ('lid_header_tray', 'slanted_front', 'tester_unit', 'counter_tray_header'):
        job.redie(execution.record.pk, words='the same order, on ' + other, stand_type=other)
        build, statuses = execution.drain(limit=20)
        assert build.state == 'awaiting', (other, build.error, statuses)
        board = build.steps['faces']['board']
        assert all(row['state'] == 'drawn' for row in board.values()), (other, {key: row.get('error') for key, row in board.items()})
        for key, row in board.items():
            plan = json.loads((folder / job.current(row)['face']).parent.joinpath('plan.json').read_text())
            assert plan['placement']['holds'] and plan['press']['holds'], (other, key, plan['placement']['faults'])
        made = job.flat_page(build)['pieces']
        assert made['seams']['holds'], (other, made['seams'])
    assert execution.edit.call_count == calls, 'no paid call'
    flow.reject(execution.record.pk, 'Rejected for this test')
    with pytest.raises(ValueError, match='A rejected round stays as it is'):
        job.redie(execution.record.pk, words='never')
