"""Unpaid extraction fixtures; no live round, provider or Illustrator invocation."""
import hashlib
from pathlib import Path

import cv2
import fitz
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt
import pytest

from apps.pipeline.services import round_files_art as art
from apps.pipeline.services import round_files_repair_art as repair_art
from apps.pipeline.services import round_files_refinement_v2 as refinement_v2


def fixture(tmp_path):
    image=Image.new('RGB',(320,160),'white');draw=ImageDraw.Draw(image)
    panels={}
    fields=('product_latin',None,'product_arabic','shade_0')
    for index,key in enumerate(art.PANEL_IDS):
        x=index*80;crop=[x,0,x+80,160]
        polygon=[[x,0],[x+79,0],[x+79,159],[x,159]]
        if key=='stand_header':polygon=[[x,50],[x+40,5],[x+79,50],[x+79,159],[x,159]]
        draw.polygon([tuple(p) for p in polygon],fill='#A45564')
        draw.line([(x+10,65),(x+60,130),(x+15,145)],fill='#D5AF59',width=4)
        draw.rectangle((x+24,83,x+36,92),fill='#D5AF59')
        text=[] if fields[index] is None else [{'field':fields[index],'text':'MODEL INVENTION NEVER PRINTED',
            'box_px':[x+20,80,x+40,96],'color':'#D5AF59','rotation':0}]
        if key=='body_front':
            text.append({'field':'shade_0','box_px':[x+10,110,x+60,125],'color':'#D5AF59','rotation':0})
        marks=[{'kind':'logo','box_px':[x+20,80,x+40,96],'color':'#D5AF59','rotation':90}] if key=='cap_front' else []
        panels[key]={'crop_px':crop,'print_polygon_px':polygon,'text':text,'marks':marks,'lineart_boxes_px':[crop]}
    source=tmp_path/'picked.png';image.save(source)
    brief={'copy':{'brand':'BBROSE','product':'Lip Gloss / ملمع شفاه'},
           'shades':[{'name':'Rose Glass','hex':'#C9707A'}],
           'dimensions_mm':{'width':15,'depth':15,'height':100,'cap_height':30},
           'stand':{'count':12,'dimensions_mm':{'width':110,'depth':85,'height':160},'layout':{'rows':3,'columns':4}}}
    inspection={'image_size_px':[320,160],'panels':panels,'stand':{'rows':3,'columns':4,'count':12,
        'bottles':[{'row':r,'column':c,'box_px':[5+c*20,5,20+c*20,100],'shade_field':'shade_0'}
                   for r in range(3) for c in range(4)]}}
    return source,brief,inspection


def test_source_crop_and_lanczos_baseline_are_immutable(tmp_path):
    source,brief,inspection=fixture(tmp_path);before=source.read_bytes()
    result=art.prepare_art(source,inspection,brief,tmp_path/'art',hashlib.sha256(before).hexdigest())
    assert source.read_bytes()==before and result['source_unchanged']
    original=Image.open(source).convert('RGB')
    for key,row in result['panels'].items():
        crop=np.asarray(original.crop(inspection['panels'][key]['crop_px']))
        assert np.array_equal(crop,np.asarray(Image.open(row['crop'])))
        expected=cv2.resize(crop,None,fx=2,fy=2,interpolation=cv2.INTER_LANCZOS4)
        assert np.array_equal(expected,np.asarray(Image.open(row['upscale'])))
        assert np.isfinite(row['fidelity']['de00_mean']) and np.isfinite(row['fidelity']['ssim'])
    with pytest.raises(ValueError,match='changed'):
        art.prepare_art(source,inspection,brief,tmp_path/'rejected','0'*64)
    assert not (tmp_path/'rejected').exists()


def test_clear_substrates_are_absent_and_copy_is_resolved_from_brief(tmp_path):
    source,brief,inspection=fixture(tmp_path)
    result=art.prepare_art(source,inspection,brief,tmp_path/'art')
    for key in ('body_front','cap_front'):
        assert not np.asarray(Image.open(result['panels'][key]['raster']))[...,3].any()
        assert result['panels'][key]['preservation']['substrate_excluded_from_print']
    assert result['panels']['body_front']['text'][0]['copy']=='Lip Gloss'
    assert result['panels']['stand_header']['text'][0]['copy']=='ملمع شفاه'
    assert result['panels']['stand_base']['text'][0]['copy']=='Rose Glass'
    assert 'MODEL INVENTION' not in str([row['text'] for row in result['panels'].values()])
    inspection['panels']['body_front']['text'][0]['field']='instruction'
    with pytest.raises(ValueError,match='COPY'):
        art.validate_inspection(inspection,[320,160],brief)


def test_stand_pixels_outside_authorized_masks_are_exact(tmp_path):
    source,brief,inspection=fixture(tmp_path)
    result=art.prepare_art(source,inspection,brief,tmp_path/'art')
    for key in ('stand_header','stand_base'):
        row=result['panels'][key];folder=Path(row['raster']).parent
        baseline=np.asarray(Image.open(row['upscale']))
        clean=np.asarray(Image.open(row['raster']))[...,:3]
        removal=np.asarray(Image.open(folder/'removal-mask.png'))>0
        removal=np.repeat(np.repeat(removal,2,axis=0),2,axis=1)
        extension=np.asarray(Image.open(folder/'header-extension-mask.png'))>0
        assert np.array_equal(baseline[~(removal|extension)],clean[~(removal|extension)])
        assert row['preservation']['outside_allowed_masks_exact']
        assert row['preservation']['extension_pixels_2x']>0 if key=='stand_header' else not extension.any()


def test_lettering_mask_removes_highlights_shadows_and_antialias_without_touching_outside():
    image=np.full((20,30,3),[90,45,60],dtype=np.uint8)
    image[6:14,10:20]=[255,255,255]
    image[8:12,12:18]=[0,0,0]
    image[9,13:17]=[180,140,80]
    plan={'text':[{'box_px':[10,6,20,14],'color':'#D5AF59'}],'marks':[]}
    mask=art.letter_mask(image,plan,[0,0,30,20])
    assert mask.sum()==80 and mask[6:14,10:20].all()
    clean=art.nearest_source_copy(image,mask)
    assert np.array_equal(clean[~mask],image[~mask])
    assert (clean[mask]==[90,45,60]).all()


def test_header_extension_copies_edges_without_stretching_interior():
    image=np.arange(6*8*3,dtype=np.uint8).reshape(6,8,3)
    inside=np.zeros((6,8),bool);inside[2:5,1:7]=True
    result=art.extend_header_edges(image,inside)
    assert np.array_equal(result[inside],image[inside])
    assert np.array_equal(result[0,4],image[2,4])
    assert np.array_equal(result[5,4],image[4,4])
    assert np.array_equal(result[3,0],image[3,1])


def test_vector_trace_preserves_position_and_holes(tmp_path):
    mask=np.zeros((100,100),bool);mask[20:80,30:70]=True;mask[35:65,42:58]=False
    path=tmp_path/'trace.svg';contours=art.trace_lineart(mask,path)
    assert any(row['hole'] for row in contours)
    with fitz.open(stream=path.read_bytes(),filetype='svg') as svg:
        with fitz.open(stream=svg.convert_to_pdf(),filetype='pdf') as document:
            pix=document[0].get_pixmap(alpha=True)
            rendered=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,4)[...,3]>127
    assert rendered.shape==mask.shape
    assert (rendered&mask).sum()/(rendered|mask).sum()>.95
    assert not rendered[50,50]


def test_inspection_rejects_stretched_coordinates_and_unapproved_marks(tmp_path):
    _,brief,inspection=fixture(tmp_path)
    inspection['panels']['body_front']['crop_px'][0]=.5
    with pytest.raises(ValueError,match='integer'):
        art.validate_inspection(inspection,[320,160],brief)
    _,brief,inspection=fixture(tmp_path)
    inspection['panels']['cap_front']['marks'][0]['kind']='invented emblem'
    with pytest.raises(ValueError,match='approved'):
        art.validate_inspection(inspection,[320,160],brief)


def test_drawing_is_deterministic_and_counts_every_engine_slot(tmp_path):
    _,brief,inspection=fixture(tmp_path)
    paths={}
    for key in art.PANEL_IDS:
        path=tmp_path/(key+'.png');Image.new('RGBA',(30,80),(100,50,40,128)).save(path);paths[key]=path
    geometry={'count':12,'front_elevation':{'width_mm':110,'height_mm':160,'header_box_mm':[0,0,110,140],
        'base_box_mm':[0,140,110,160],'product_slots':[{'index':r*4+c,'row':r+1,'column':c+1,
        'box_mm':[5+c*25,40,20+c*25,140],'depth_mm':10+r*25} for r in range(3) for c in range(4)]}}
    proofs={'shade_0':{'path':str(paths['body_front']),'derivative':False}}
    first=art.mechanical_drawing(paths,brief,geometry,tmp_path/'one.png',inspection=inspection,body_proofs=proofs,px_per_mm=2)
    second=art.mechanical_drawing(paths,brief,geometry,tmp_path/'two.png',inspection=inspection,body_proofs=proofs,px_per_mm=2)
    assert first['sha256']==second['sha256']
    assert first['count']==first['drawn_product_instances']==12
    assert len({(r['row'],r['column']) for r in first['stand_slots']})==12
    brief['stand']['count']=3
    observed=art.mechanical_drawing(paths,brief,geometry,tmp_path/'observed.png',inspection=inspection,body_proofs=proofs,px_per_mm=2)
    assert observed['count']==12 and observed['intake_count']==3
    assert observed['hero']['shade_field']=='shade_0'
    inspection['stand']['bottles'][0]['shade_field']=None
    proofs['unresolved']={'path':str(paths['body_front']),'derivative':True}
    unresolved=art.mechanical_drawing(paths,brief,geometry,tmp_path/'unresolved.png',inspection=inspection,body_proofs=proofs,px_per_mm=2)
    slot=next(row for row in unresolved['stand_slots'] if row['row']==1 and row['column']==1)
    assert slot['shade_field'] is None and slot['liquid_colour'] is None
    assert unresolved['shade_loading']['unresolved_count']==1
    inspection['stand']['bottles'][1]['shade_field']='invented_shade'
    with pytest.raises(ValueError,match='shade COPY'):
        art.shade_loading(inspection,brief)
    inspection['stand']['bottles'][1]['shade_field']='shade_0'
    del inspection['stand']['bottles'][0]['shade_field']
    with pytest.raises(KeyError,match='shade_field'):
        art.shade_loading(inspection,brief)


def test_declared_body_colour_print_is_preserved_but_liquid_is_clear(tmp_path):
    source,brief,inspection=fixture(tmp_path)
    inspection['panels']['body_front']['colour_print_boxes_px']=[[5,5,25,30]]
    result=art.prepare_art(source,inspection,brief,tmp_path/'art')
    panel=result['panels']['body_front']
    rgba=np.asarray(Image.open(panel['raster']))
    baseline=np.asarray(Image.open(panel['upscale']))
    assert np.array_equal(rgba[10:60,10:50,:3],baseline[10:60,10:50])
    assert (rgba[10:60,10:50,3]==255).all()
    assert not rgba[60:,:,3].any()
    assert panel['preservation']['colour_print_pixels_2x']==2000
    inspection['panels']['cap_front']['colour_print_boxes_px']=[[85,5,105,30]]
    with pytest.raises(ValueError,match='gold cap'):
        art.validate_inspection(inspection,[320,160],brief)


def _repair_fixture(tmp_path):
    source, brief, inspection = fixture(tmp_path)
    original = Image.open(source).convert('RGB')
    image = Image.new('RGB', (520, 200), 'white'); image.paste(original, (0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 79, 159), fill='#DFE5E8')
    draw.rectangle((15, 5, 64, 149), fill='#C9707A')
    draw.rectangle((3, 5, 4, 149), fill='#C9707A')  # thin glass reflection is not the liquid body
    draw.line([(17, 15), (62, 65), (18, 72)], fill='#D5AF59', width=2)
    inspection['panels']['body_front']['lineart_boxes_px'] = [[20, 10, 60, 75]]
    brief['shades'].append({'name': 'Fig Nectar', 'hex': '#703852'})
    bottles = []
    for column, colour in enumerate(('#C9707A', '#C9707A', '#703852')):
        x = 340+column*50
        draw.rectangle((x, 0, x+34, 179), fill='#DFE5E8')
        draw.rectangle((x+4, 55, x+30, 174), fill=colour)
        draw.rectangle((x, 0, x+34, 53), fill='#D5AF59')
        bottles.append({'row': 0, 'column': column, 'box_px': [x, 0, x+35, 180],
                        'shade_field': ['shade_0', None, 'shade_1'][column]})
        draw.rectangle((x, 182, x+34, 195), fill='#D5AF59')
        bottles.append({'row': 1, 'column': column, 'box_px': [x, 182, x+35, 196], 'shade_field': None})
    inspection['stand'] = {'rows': 2, 'columns': 3, 'count': 6, 'bottles': bottles}
    brief['stand'].update(count=6, layout={'rows': 2, 'columns': 3})
    inspection['image_size_px'] = list(image.size)
    image.save(source)
    return source, brief, inspection


def test_refinement_uses_visible_source_shades_and_measures_clear_acrylic_without_hidden_guesses(tmp_path):
    from copy import deepcopy
    source, brief, inspection = _repair_fixture(tmp_path)
    old = deepcopy(inspection); before = source.read_bytes(); digest = art.sha(source)
    result = repair_art.refine_inspection(source, inspection, brief, original_sha256=digest)
    refined, record = result['inspection'], result['record']
    assert inspection == old and source.read_bytes() == before
    assert next(row for row in refined['stand']['bottles'] if (row['row'], row['column']) == (0, 1))['shade_field'] == 'shade_0'
    assert all(row['shade_field'] is None for row in refined['stand']['bottles'] if row['row'] == 1)
    assert all(new['box_px'] == old_row['box_px'] for new, old_row in zip(refined['stand']['bottles'], old['stand']['bottles']))
    material = refined['drawing_material']
    assert material['status'] == 'measured'
    assert material['liquid_box_source_px'] == [15, 5, 65, 150]
    assert material['acrylic_margin_source_px'] == {'left': 15, 'top': 5, 'right': 15, 'base': 10}
    assert record['lineart_localisation']['body_front']['new_observed_gold_pixels'] > 0
    assert refined['panels']['body_front']['text'] == old['panels']['body_front']['text']
    assert record['source_unchanged'] and record['original_inspection_sha256'] != record['refined_inspection_sha256']
    with pytest.raises(ValueError, match='changed'):
        repair_art.refine_inspection(source, inspection, brief, original_sha256='0'*64)


def test_repaired_art_preserves_all_untouched_pixels_and_binds_material_proof(tmp_path):
    source, brief, inspection = _repair_fixture(tmp_path)
    original_art = art.prepare_art(source, inspection, brief, tmp_path/'original-art')
    original_bytes = {path: path.read_bytes() for path in (tmp_path/'original-art').rglob('*') if path.is_file()}
    refined = repair_art.refine_inspection(source, inspection, brief, original_sha256=art.sha(source))['inspection']
    result = repair_art.prepare_repaired_art(source, refined, brief, tmp_path/'repair-art', expected_sha256=art.sha(source))
    for key in ('stand_header', 'stand_base'):
        row = result['panels'][key]; folder = Path(row['raster']).parent
        baseline = np.asarray(Image.open(row['upscale']))
        clean = np.asarray(Image.open(row['raster']))[..., :3]
        removal = np.asarray(Image.open(folder/'removal-mask.png')) > 0
        removal = np.repeat(np.repeat(removal, 2, axis=0), 2, axis=1)
        extension = np.asarray(Image.open(folder/'header-extension-mask.png')) > 0
        assert np.array_equal(clean[~(removal | extension)], baseline[~(removal | extension)])
        assert row['preservation']['outside_allowed_masks_exact']
        assert row['text'] == original_art['panels'][key]['text']
    assert all(path.read_bytes() == value for path, value in original_bytes.items())
    walls = np.asarray(Image.open(refined['drawing_material']['wall_raster']))
    assert not walls[5:150, 15:65, 3].any()
    assert (walls[150:, :, 3] == 255).all()
    assert refined['drawing_material']['outside_extraction_exact']
    for key in ('body_front', 'cap_front'):
        assert not np.asarray(Image.open(result['panels'][key]['raster']))[..., 3].any()


def test_nearest_clean_header_extension_uses_two_dimensions_and_never_a_removed_glyph():
    rgb = np.arange(7*7*3, dtype=np.uint8).reshape(7, 7, 3)
    inside = np.zeros((7, 7), dtype=bool)
    inside[3:, 3:] = True; inside[5:, 1:] = True
    removed = np.zeros_like(inside); removed[3, 3] = True
    clean = art.nearest_clean_source_copy(rgb, ~inside | removed, inside & ~removed)
    # (0, 0) is closer to the diagonal (3, 4)/(4, 3) than a vertical column's (5, 1).
    assert tuple(clean[0, 0]) in {tuple(rgb[3, 4]), tuple(rgb[4, 3])}
    assert not np.array_equal(clean[0, 0], rgb[5, 1])
    assert not np.array_equal(clean[3, 3], rgb[3, 3])
    assert np.array_equal(clean[inside & ~removed], rgb[inside & ~removed])


def test_repair_letter_padding_and_separator_never_moves_live_copy_or_removes_distant_art():
    panel = {'crop_px': [0, 0, 150, 60], 'text': [
        {'field': 'product_latin', 'box_px': [20, 20, 55, 40]},
        {'field': 'product_arabic', 'box_px': [65, 20, 105, 40]}], 'marks': []}
    masks = repair_art._removal_boxes(panel)
    mask = art._region_mask((150, 60), masks['removal_boxes_px'], panel['crop_px'])
    assert mask[30, 60] and mask[18, 30]
    assert not mask[10, 10] and not mask[50, 60]
    assert masks['live_placements_unchanged'] and masks['maximum_padding_source_px'] == 6
    assert panel['text'][0]['box_px'] == [20, 20, 55, 40]


def test_measured_acrylic_drawing_has_source_walls_and_base_instead_of_edge_to_edge_liquid(tmp_path):
    source, brief, inspection = _repair_fixture(tmp_path)
    refined = repair_art.refine_inspection(source, inspection, brief, original_sha256=art.sha(source))['inspection']
    result = repair_art.prepare_repaired_art(source, refined, brief, tmp_path/'art', expected_sha256=art.sha(source))
    paths = {key: row['raster'] for key, row in result['panels'].items()}
    proofs = {key: {'path': paths['body_front'], 'derivative': key != 'shade_0'} for key in ('shade_0', 'shade_1', 'unresolved')}
    geometry = {'count': 6, 'front_elevation': {'width_mm': 80, 'height_mm': 160,
        'header_box_mm': [0, 0, 80, 140], 'base_box_mm': [0, 140, 80, 160],
        'product_slots': [{'index': r*3+c, 'row': r+1, 'column': c+1,
            'box_mm': [5+c*25, 40, 20+c*25, 140], 'depth_mm': 10+r*25}
            for r in range(2) for c in range(3)]}}
    output = tmp_path/'drawing.png'
    record = art.mechanical_drawing(paths, brief, geometry, output, inspection=refined, body_proofs=proofs, px_per_mm=4)
    rgb = np.asarray(Image.open(output))
    # Hero starts x8mm, y68mm; body starts y98mm and is 70mm high.
    assert np.max(np.abs(rgb[110*4, 8*4].astype(int)-[223, 229, 232])) <= 3
    assert tuple(rgb[110*4, 15*4]) == (201, 112, 122)
    assert tuple(rgb[166*4, 15*4]) == (223, 229, 232)
    assert record['drawing_material']['liquid_box_norm'] == [15/80, 5/160, 65/80, 150/160]
    assert all(row['liquid_colour'] is None for row in record['stand_slots'] if row['row'] == 2)
    Path(refined['drawing_material']['wall_raster']).write_bytes(b'changed')
    with pytest.raises(ValueError, match='wall pixels changed'):
        art.mechanical_drawing(paths, brief, geometry, tmp_path/'bad.png', inspection=refined, body_proofs=proofs)


def test_visible_shade_refinement_refuses_ambiguous_or_unmatched_colours(tmp_path):
    source, brief, inspection = _repair_fixture(tmp_path)
    purple = next(row for row in inspection['stand']['bottles'] if row['shade_field'] == 'shade_1')
    purple['shade_field'] = None
    result = repair_art.refine_inspection(source, inspection, brief, original_sha256=art.sha(source))
    slots = {(row['row'], row['column']): row['shade_field'] for row in result['inspection']['stand']['bottles']}
    assert slots[(0, 1)] == 'shade_0' and slots[(0, 2)] is None
    assert result['record']['shade_resolution']['single_reference_maximum_delta_e00'] == 2.
    purple['shade_field'] = 'shade_1'
    image = Image.open(source).convert('RGB'); draw = ImageDraw.Draw(image)
    x = purple['box_px'][0]; draw.rectangle((x+4, 55, x+30, 174), fill='#C9707A'); image.save(source)
    ambiguous = repair_art.refine_inspection(source, inspection, brief, original_sha256=art.sha(source))
    unresolved = next(row for row in ambiguous['record']['shade_resolution']['decisions'] if (row['row'], row['column']) == (0, 1))
    assert unresolved['after'] is None and unresolved['runner_up_margin_delta_e00'] == 0.


def test_material_refinement_does_not_treat_declared_printed_colour_as_liquid(tmp_path):
    source, brief, inspection = _repair_fixture(tmp_path)
    inspection['panels']['body_front']['colour_print_boxes_px'] = [[0, 0, 80, 160]]
    result = repair_art.refine_inspection(source, inspection, brief, original_sha256=art.sha(source))
    assert result['inspection']['drawing_material']['status'] == 'unresolved'
    prepared = repair_art.prepare_repaired_art(source, result['inspection'], brief, tmp_path/'art', expected_sha256=art.sha(source))
    assert 'wall_raster' not in prepared['drawing_material']


def test_engine_support_faces_fill_actual_gap_and_obey_depth_without_changing_print_pixels(tmp_path):
    from copy import deepcopy
    _, brief, inspection = fixture(tmp_path)
    inspection['stand'] = {'rows': 2, 'columns': 1, 'count': 2, 'bottles': [
        {'row': row, 'column': 0, 'box_px': [5, 5, 20, 100], 'shade_field': 'shade_0'} for row in range(2)]}
    brief['stand'].update(count=2, layout={'rows': 2, 'columns': 1})
    paths = {}
    colours = {'body_front': '#AA3344', 'cap_front': '#D5AF59', 'stand_header': '#445566', 'stand_base': '#228844'}
    for key, colour in colours.items():
        path = tmp_path/(key+'.png'); Image.new('RGBA', (30, 80), colour).save(path); paths[key] = path
    proofs = {'shade_0': {'path': str(paths['body_front']), 'derivative': False}}
    before = {key: path.read_bytes() for key, path in paths.items()}
    faces = [
        {'id': 'rear-seat', 'kind': 'support_front', 'row': 2, 'box_mm': [5, 133, 30, 158], 'depth_mm': 20},
        {'id': 'front-seat', 'kind': 'support_front', 'row': 1, 'box_mm': [5, 137, 30, 158], 'depth_mm': 5},
        {'id': 'front-collar', 'kind': 'collar_front_edge', 'row': 1, 'box_mm': [5, 130, 30, 131.5], 'depth_mm': 5}]
    for face in faces:
        face.update(material='unprinted board', printed=False)
    geometry = {'count': 2, 'front_elevation': {'width_mm': 40, 'height_mm': 160,
        'header_box_mm': [0, 0, 40, 20], 'base_box_mm': [0, 140, 40, 160], 'platform_fronts': faces,
        'product_slots': [
            {'index': 1, 'row': 1, 'column': 1, 'box_mm': [10, 37, 25, 137], 'depth_mm': 10},
            {'index': 2, 'row': 2, 'column': 1, 'box_mm': [10, 33, 25, 133], 'depth_mm': 30}]}}
    original_geometry = deepcopy(geometry)
    target = tmp_path/'structure.png'
    result = art.mechanical_drawing(paths, brief, geometry, target, inspection=inspection, body_proofs=proofs, px_per_mm=2)
    image = np.asarray(Image.open(target))
    x = (41+15)*2  # stand offset 8 + 15 + 18 mm, then 15 mm into the stand
    assert tuple(image[(8+134)*2, x]) == (170, 51, 68)  # front bottle hides rear seat
    assert tuple(image[round((8+130.5)*2), x]) == (228, 228, 228)  # actual front collar edge
    assert tuple(image[(8+139)*2, x]) == (228, 228, 228)  # physical support fills bottom gap
    assert tuple(image[(8+145)*2, x]) == (34, 136, 68)  # printed tray front hides structure
    assert result['unprinted_structure']['faces'] == faces and result['drawn_product_instances'] == 2
    assert geometry == original_geometry and all(path.read_bytes() == before[key] for key, path in paths.items())
    geometry['front_elevation']['platform_fronts'][0]['box_mm'][0] = -1
    with pytest.raises(ValueError, match='out-of-bounds'):
        art.mechanical_drawing(paths, brief, geometry, tmp_path/'bad.png', inspection=inspection, body_proofs=proofs)


def test_connected_source_metal_recovers_pale_highlights_without_seed_clips_or_warm_rim(tmp_path):
    picture = Image.new('RGB', (120, 120), '#C9707A'); draw = ImageDraw.Draw(picture)
    draw.line((12, 12, 96, 96), fill='#D5AF59', width=7)
    draw.line((12, 12, 96, 96), fill='#FFFDEF', width=2)
    draw.line((60, 64, 60, 112), fill='#875E44', width=4)
    draw.point((42, 55), fill='#D5AF59')
    rgb = np.asarray(picture); seed = np.zeros((120, 120), bool); seed[35:65, 35:65] = True
    selected, record = refinement_v2.source_metal(rgb, seed, np.zeros(seed.shape, bool))
    assert selected[20, 20] and selected[90, 90]  # outside the seed on both ends
    assert selected[45, 45]  # pale gold highlight omitted by the old saturation cutoff
    assert not selected[100, 60] and not selected[55, 42]
    assert record['outside_seed_pixels'] > 0
    vector = tmp_path/'source.svg'; traced = refinement_v2.trace_strokes(selected, vector)
    assert traced['paths'] and traced['saved_vector']['iou'] > .65
    assert 'stroke-width' not in vector.read_text() and 'fill-rule="evenodd"' in vector.read_text()
    assert min(p[0] for row in traced['paths'] for p in row['points_source_px']) < 20
    assert max(p[0] for row in traced['paths'] for p in row['points_source_px']) > 90


@pytest.mark.parametrize('pane_colour', ['#A45564', '#337B9C', '#5E8F55'])
def test_header_source_region_refinement_recovers_missing_top_in_any_observed_pane_colour(tmp_path, pane_colour):
    source, brief, inspection = _repair_fixture(tmp_path)
    image = Image.open(source).convert('RGB'); draw = ImageDraw.Draw(image)
    draw.rectangle((160, 0, 239, 159), fill='white')
    draw.polygon([(160, 50), (200, 5), (239, 50), (239, 159), (160, 159)], fill=pane_colour)
    image.save(source)
    panel = inspection['panels']['stand_header']
    panel['crop_px'] = [160, 35, 240, 160]
    panel['print_polygon_px'] = [[160, 50], [200, 35], [239, 50], [239, 159], [160, 159]]
    panel['lineart_boxes_px'] = [[160, 35, 240, 160]]
    before = source.read_bytes(); old_words = list(panel['text'])
    result = repair_art.refine_inspection_v2(source, inspection, brief, original_sha256=art.sha(source))
    region = result['record']['second_refinement']['header_source_region']
    assert region['status'] == 'measured' and region['new_crop_px'][1] < 15
    assert region['added_source_rows'] > 20 and region['absolute_type_and_logo_boxes_unchanged']
    assert result['inspection']['panels']['stand_header']['text'] == old_words
    assert source.read_bytes() == before and panel['crop_px'] == [160, 35, 240, 160]


def test_reflected_header_extension_copies_varied_clean_source_panes_not_brown_trim():
    rgb = np.full((80, 100, 3), 255, np.uint8)
    inside = np.zeros((80, 100), bool)
    for y in range(80):
        left = max(0, 35-y//2); inside[y, left:100-left] = True
    yy, xx = np.indices(inside.shape)
    rgb[inside] = np.stack((150+xx%40, 75+yy%20, 95+(xx+yy)%15), axis=2)[inside]
    edge = inside & (distance_transform_edt(inside) < 2)
    rgb[edge] = [82, 28, 10]
    output, mapping = refinement_v2.reflected_edge_source(rgb, inside, np.zeros(inside.shape, bool))
    assert np.array_equal(output[inside], rgb[inside])
    assert not np.any(np.all(output[~inside] == [82, 28, 10], axis=1))
    assert mapping['record']['unique_extension_donor_pixels'] > 100
    assert np.array_equal(output[~inside], rgb[mapping['source_y'][~inside], mapping['source_x'][~inside]])


def test_v2_physical_source_material_keeps_gloss_and_cap_boundary_in_engine_drawing(tmp_path):
    source, brief, inspection = _repair_fixture(tmp_path)
    image = Image.open(source).convert('RGB'); rgb = np.asarray(image).copy()
    # Actual physical source gradients, not a flat palette fill.
    for x in range(15, 65):
        rgb[5:150, x] = [150+(x-15)*2, 65+(x-15), 80+(x-15)]
    rgb[:160, 80:160] = [170, 130, 45]
    rgb[:5, 80:160] = [245, 220, 160]
    rgb[5:160, 80:84] = [225, 190, 100]
    # Visible material in tray gaps, independent of the printed header/base.
    rgb[:180, 375:390] = [166, 120, 52]; rgb[:180, 425:440] = [220, 180, 85]
    Image.fromarray(rgb).save(source)
    before = source.read_bytes()
    refined = repair_art.refine_inspection_v2(source, inspection, brief, original_sha256=art.sha(source))['inspection']
    result = repair_art.prepare_repaired_art_v2(source, refined, brief, tmp_path/'v2', expected_sha256=art.sha(source))
    physical = result['drawing_material']['physical_source']
    body = np.asarray(Image.open(physical['hero_body']['path']))
    removed = np.asarray(Image.open(physical['hero_body']['extraction_mask'])) > 0
    assert np.array_equal(body[~removed], rgb[:160, :80][~removed])
    assert len(np.unique(body[40:70, 20:60].reshape(-1, 3), axis=0)) > 20
    assert physical['cap_source']['outside_extraction_exact']
    assert physical['enclosure']['status'] == 'observed'
    assert physical['enclosure']['assembly_finish']['printed_surfaces'].startswith('Header and base only')
    paths = {}
    for key in art.PANEL_IDS:
        path = tmp_path/(key+'-flat.png'); Image.new('RGBA', (80, 160), (0, 0, 0, 0)).save(path); paths[key] = path
    proofs = {key: {'path': str(paths['body_front']), 'derivative': key != 'shade_0'} for key in ['shade_0', 'shade_1', 'unresolved']}
    geometry = {'count': 6, 'front_elevation': {'width_mm': 80, 'height_mm': 160,
        'header_box_mm': [0, 0, 80, 35], 'base_box_mm': [0, 140, 80, 160],
        'platform_fronts': [{'id': 'front-support', 'kind': 'support_front', 'depth_mm': 5,
            'box_mm': [1, 137, 79, 140], 'material': 'unprinted board', 'printed': False}],
        'product_slots': [{'index': r*3+c, 'row': r+1, 'column': c+1, 'box_mm': [5+c*25, 40-4*r, 20+c*25, 140-4*r], 'depth_mm': 10+20*r}
                          for r in range(2) for c in range(3)],
        'enclosure_faces': [{'id': 'back', 'kind': 'back_interior', 'depth_mm': 60,
            'box_mm': [0, 35, 80, 160], 'polygon_mm': [[0, 35], [80, 35], [80, 160], [0, 160]]}]}}
    output = tmp_path/'physical-drawing.png'
    record = art.mechanical_drawing(paths, brief, geometry, output, inspection=refined, body_proofs=proofs, px_per_mm=4)
    drawing = np.asarray(Image.open(output)); x = round((41+12)*4)
    rear_top = drawing[round((8+36+.5)*4), x]
    front_top = drawing[round((8+40+.5)*4), x]
    front_lower = drawing[round((8+42)*4), x]
    assert np.linalg.norm(rear_top.astype(float)-front_lower.astype(float)) > 40
    assert np.linalg.norm(front_top.astype(float)-front_lower.astype(float)) > 40
    assert record['hero']['physical_source_material'] is not None
    assert tuple(drawing[(8+138)*4, (41+22)*4]) == tuple(physical['enclosure']['interior']['rgb'])
    assert record['unprinted_structure']['drawing_colour'] == tuple(physical['enclosure']['interior']['rgb'])
    assert physical['enclosure']['assembly_finish']['supports'].startswith('The same proposed source-matched stock')
    assert source.read_bytes() == before


def test_v2_prepared_header_extension_does_not_copy_shadow_from_cleaned_metal_donors(tmp_path):
    source, brief, inspection = _repair_fixture(tmp_path)
    image = Image.open(source).convert('RGB'); rgb = np.asarray(image).copy()
    panel = inspection['panels']['stand_header']; crop = panel['crop_px']
    inside = art.silhouette((80, 160), panel['print_polygon_px'], crop)
    yy, xx = np.indices(inside.shape)
    patch = np.full((160, 80, 3), 255, np.uint8)
    patch[inside] = np.stack((155+xx%35, 75+yy%20, 95+(xx+yy)%15), axis=2)[inside]
    material = Image.fromarray(patch); draw = ImageDraw.Draw(material)
    draw.line((10, 60, 65, 15), fill='#521C0A', width=11)
    draw.line((10, 60, 65, 15), fill='#D5AF59', width=5)
    rgb[:160, 160:240] = np.asarray(material); Image.fromarray(rgb).save(source)
    refined = repair_art.refine_inspection_v2(source, inspection, brief, original_sha256=art.sha(source))['inspection']
    result = repair_art.prepare_repaired_art_v2(source, refined, brief, tmp_path/'v2', expected_sha256=art.sha(source))
    row = result['panels']['stand_header']; folder = Path(row['raster']).parent
    output = np.asarray(Image.open(row['raster']))[..., :3]
    extension = np.asarray(Image.open(folder/'header-extension-mask.png')) > 0
    assert extension.any() and row['source_segmentation']['selected_source_pixels'] > 0
    assert not np.any(np.all(output[extension] == [82, 28, 10], axis=1))


def test_derived_material_removes_full_source_word_beyond_central_seed_without_erasing_rim(tmp_path):
    # A detached final glyph extends beyond the old central scan, at a different
    # height from the hero label. A continuous gold physical rim must survive.
    source = np.full((484, 300, 3), [128, 65, 110], np.uint8)
    source[:180, 100:182] = [213, 175, 89]
    source[:180, 200:282] = [213, 175, 89]
    body = source[180:484, 200:282]
    body[270:275, 25:63] = [248, 213, 175]
    body[270:277, 67:70] = [248, 213, 175]
    body[:, 4:7] = [213, 175, 89]
    original = source.copy()
    gold = art.gold_mask(body)
    central = gold[:, 82//5:4*82//5]
    yy, xx = np.where(central[270:275])
    old_right = int(xx.max())+82//5+3
    assert old_right <= 67 and not (67 < old_right)  # old mask leaves final glyph
    hero = {'crop_px': [0, 0, 82, 304], 'text': [
        {'field': 'shade_0', 'box_px': [20, 240, 60, 254]}], 'marks': []}
    inspection = {'image_size_px': [300, 484], 'panels': {'body_front': hero, 'cap_front': {'crop_px': [100, 0, 182, 180]}},
        'art_repair': {'panels': {'body_front': {'removal_boxes_px': [[20, 240, 60, 254]]},
                                  'cap_front': {'removal_boxes_px': []}}},
        'stand': {'rows': 1, 'columns': 1, 'count': 1, 'bottles': [
            {'row': 0, 'column': 0, 'box_px': [200, 0, 282, 484], 'shade_field': 'shade_1'}]}}
    brief = {'copy': {'brand': 'BBROSE', 'product': 'Lip Gloss / ملمع شفاه'},
             'shades': [{'name': 'Rose', 'hex': '#C9707A'}, {'name': 'Berry', 'hex': '#80416E'}]}
    result = refinement_v2.physical_materials(source, inspection, brief, tmp_path,
        {'body_front': {'metal': np.zeros((304, 82), bool)}})
    record = result['body_sources']['shade_1']
    clean = np.asarray(Image.open(record['path']))
    removal = np.asarray(Image.open(record['extraction_mask'])) > 0
    assert removal[270:277, 67:70].all()
    assert not np.any(np.all(clean[270:277, 67:70] == [248, 213, 175], axis=2))
    assert not removal[:, 4:7].any() and np.array_equal(clean[:, 4:7], body[:, 4:7])
    assert np.array_equal(clean[~removal], body[~removal])
    assert np.array_equal(source, original) and record['outside_extraction_exact']
    assert [223, 448, 272, 459] in record['source_word_removal']['boxes_source_px']


def _known_line_network():
    rgb = np.full((400, 400, 3), [160, 70, 100], np.uint8)
    mask = np.zeros((400, 400), np.uint8)
    for start, end in [((45, 50), (350, 350)), ((45, 350), (350, 50)), ((45, 200), (350, 200))]:
        cv2.line(mask, start, end, 1, 4)
    # Uneven source ridges, highlights and small observed gaps are not ideal SVG.
    mask[95:98, 88:99] = 0; mask[301:304, 88:99] = 0
    yy, xx = np.indices(mask.shape)
    colours = np.stack((190+xx%60, 145+yy%65, 55+(xx+yy)%90), axis=2).astype(np.uint8)
    rgb[mask > 0] = colours[mask > 0]
    for x, y in [(15, 17), (380, 80), (375, 370), (14, 280)]:
        mask[y, x] = 1; rgb[y, x] = [213, 175, 89]
    return rgb, mask.astype(bool)


@pytest.mark.parametrize('width_mm', [.3, .45])
def test_fitted_straight_network_uses_physical_strokes_and_covers_original_ridges(tmp_path, width_mm):
    from apps.pipeline.services import round_files_line_fit as line_fit
    import json
    import xml.etree.ElementTree as ET
    rgb, mask = _known_line_network(); before = rgb.copy(); old_mask = mask.copy()
    target = tmp_path/'network.svg'
    record = line_fit.fit_line_network(rgb, mask, (20, 20), target, width_mm)
    assert json.loads(json.dumps(record))['width_mode'] == 'fixed'
    assert record['passed'] and record['coverage'] >= .9
    assert record['source_line_pixels'] == int(mask.sum())
    assert record['all_segments_supported'] and all(row['centreline_source_support'] >= .8 for row in record['segments'])
    assert np.array_equal(before, rgb) and np.array_equal(old_mask, mask)
    root = ET.fromstring(target.read_text())
    assert root.attrib['viewBox'] == '0 0 20.0 20.0'
    assert all(float(path.attrib['stroke-width']) == width_mm and path.attrib['fill'] == 'none' for path in root)
    assert all(path.attrib['d'].count('L') == 1 for path in root)
    # Three observed lines share one physical crossing, rather than six nearly
    # coincident endpoint coordinates or a traced, ragged contour.
    degrees = {}
    for edge in record['segment_node_indices']:
        for node in edge:
            degrees[node] = degrees.get(node, 0)+1
    assert max(degrees.values()) >= 6


def test_network_measurement_detects_unsupported_extra_stroke_and_missing_picture_lines(tmp_path):
    from apps.pipeline.services import round_files_line_fit as line_fit
    rgb, mask = _known_line_network(); target = tmp_path/'network.svg'
    record = line_fit.fit_line_network(rgb, mask, (20, 20), target)
    assert record['passed']
    original = target.read_text()
    target.write_text(original.replace('</svg>', '<path d="M 1,1 L 18,1" fill="none" stroke="#D5AF59" stroke-width="0.3"/></svg>'))
    extra = line_fit.measure_line_network(target, mask, (20, 20))
    assert not extra['passed'] and not extra['all_segments_supported']
    assert not extra['segments'][-1]['supported']
    target.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="20mm" viewBox="0 0 20 20"><path d="M 2.25,10 L 17.5,10" fill="none" stroke="#D5AF59" stroke-width=".3"/></svg>')
    missing = line_fit.measure_line_network(target, mask, (20, 20))
    assert not missing['passed'] and missing['coverage'] < .5


def test_line_fit_anisotropic_source_has_constant_physical_width_and_rejects_invalid_mask(tmp_path):
    from apps.pipeline.services import round_files_line_fit as line_fit
    rgb = np.full((500, 134, 3), 180, np.uint8)
    mask = np.zeros((500, 134), np.uint8)
    cv2.line(mask, (12, 40), (120, 450), 1, 1)
    result = line_fit.fit_line_network(rgb, mask.astype(bool), (15, 70), tmp_path/'physical.svg', .3)
    assert result['passed'] and result['width_mm'] == .3
    assert 'viewBox="0 0 15.0 70.0"' in (tmp_path/'physical.svg').read_text()
    with pytest.raises(ValueError, match='boolean motif mask'):
        line_fit.fit_line_network(rgb, mask, (15, 70), tmp_path/'invalid.svg')
    source = tmp_path/'source.png'; Image.fromarray(rgb).save(source); before = source.read_bytes()
    from_path = line_fit.fit_line_network(source, mask.astype(bool), (15, 70), tmp_path/'from-path.svg')
    assert from_path['passed'] and source.read_bytes() == before
    with pytest.raises(ValueError, match='must not replace'):
        line_fit.fit_line_network(source, mask.astype(bool), (15, 70), source)
    assert source.read_bytes() == before


def _attempt_art_fixture(tmp_path, motif_width=2):
    image = Image.new('RGB', (800, 200), 'white'); draw = ImageDraw.Draw(image)
    panels = {}
    for index, key in enumerate(art.PANEL_IDS):
        x = index*200; crop = [x, 0, x+200, 200]
        polygon = [[x, 0], [x+199, 0], [x+199, 199], [x, 199]]
        if key == 'stand_header':
            polygon = [[x, 40], [x+100, 0], [x+199, 40], [x+199, 199], [x, 199]]
        draw.polygon([tuple(p) for p in polygon], fill='#3C506E')
        if key != 'cap_front':
            draw.line((x+35, 45, x+165, 155), fill='#D5AF59', width=motif_width)
            draw.line((x+35, 155, x+165, 45), fill='#D5AF59', width=motif_width)
        draw.rectangle((x+70, 172, x+129, 183), fill='#D5AF59')
        panels[key] = {'crop_px': crop, 'print_polygon_px': polygon,
            'text': [{'field': 'shade_0', 'box_px': [x+70, 172, x+130, 184], 'color': '#D5AF59', 'rotation': 0}],
            'marks': [], 'lineart_boxes_px': [[x+25, 35, x+175, 165]], 'colour_print_boxes_px': []}
        if key == 'cap_front':
            panels[key]['text'] = []; panels[key]['lineart_boxes_px'] = []
            panels[key]['marks'] = [{'kind': 'logo', 'box_px': [x+40, 70, x+80, 110], 'color': '#D5AF59', 'rotation': 90}]
    source = tmp_path/'picked-attempt.png'; image.save(source)
    brief = {'copy': {'brand': 'BBROSE', 'product': 'Lip Gloss / ملمع شفاه'},
        'shades': [{'name': 'Rose Glass', 'hex': '#C9707A'}],
        'dimensions_mm': {'width': 20, 'depth': 20, 'height': 40, 'cap_height': 20}}
    inspection = {'image_size_px': [800, 200], 'panels': panels,
        'stand': {'rows': 1, 'columns': 1, 'count': 1, 'bottles': [
            {'row': 0, 'column': 0, 'box_px': [0, 0, 200, 200], 'shade_field': 'shade_0'}]}}
    details = {'panels': {}}
    for key in ('body_front', 'stand_header'):
        original = np.asarray(image.crop(panels[key]['crop_px']))
        doubled = cv2.resize(original, None, fx=2, fy=2, interpolation=cv2.INTER_LANCZOS4)
        path = tmp_path/(key+'-selected.png'); Image.fromarray(doubled).save(path)
        details['panels'][key] = {'panel': key, 'identity': {'source_sha256': art.sha(source), 'crop_px': panels[key]['crop_px']},
            'accepted': False, 'selected': 'upscale.png', 'selected_path': str(path), 'selected_sha256': art.sha(path),
            'de00_mean': 0., 'ssim': 1., 'method': 'Synthetic exact baseline decision.'}
    geometry = {'surfaces': {'stand_header': {'size_mm': [40., 40.]}, 'stand_base': {'size_mm': [40., 20.]}}}
    return source, inspection, brief, details, geometry


@pytest.mark.parametrize('detail_scale', [2, 3])
def test_attempt_art_integrates_selected_pixels_and_fitted_vectors_without_contour_tracing(tmp_path, monkeypatch, detail_scale):
    from apps.pipeline.services import round_files_attempt_art as attempt_art
    source, inspection, brief, details, geometry = _attempt_art_fixture(tmp_path)
    if detail_scale == 3:
        for key, detail in details['panels'].items():
            crop = np.asarray(Image.open(source).convert('RGB').crop(inspection['panels'][key]['crop_px']))
            candidate = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_LANCZOS4)
            Image.fromarray(candidate).save(detail['selected_path'])
            detail.update(accepted=True, selected='candidate.png', selected_sha256=art.sha(detail['selected_path']))
    before = source.read_bytes()
    def forbidden(*args, **kwargs):
        raise AssertionError('Old contour tracing must not run in this attempt')
    monkeypatch.setattr(art, 'trace_lineart', forbidden)
    result = attempt_art.prepare_attempt_art(source, inspection, brief, tmp_path/'attempt', details, geometry,
                                             expected_sha256=art.sha(source))
    assert source.read_bytes() == before and result['source_unchanged']
    for key, row in result['panels'].items():
        assert row['preservation']['outside_allowed_masks_exact']
        assert row['contours_norm'] == []
        if key == 'cap_front':
            assert row['lineart_svg'] is None
            assert row['marks'][0]['box_norm'] == pytest.approx([.4, .4, .6, .6])
            assert row['marks'][0]['rotation'] == 90
        else:
            assert row['lineart_measurement']['passed']
            assert row['lineart_measurement']['coverage'] >= .9
            assert row['lineart_measurement']['original_picture_measurement']['passed']
            assert row['lineart_measurement']['original_picture_measurement']['coverage'] >= .9
            assert all('endpoints_original_source_px' in segment for segment in row['lineart_measurement']['segments'])
        pixels = np.asarray(Image.open(row['raster']))
        if key in ('body_front', 'cap_front'):
            assert not pixels[..., 3].any()
        else:
            assert pixels[..., 3].all()
            folder = Path(row['raster']).parent
            selected = np.asarray(Image.open(folder/'selected.png'))
            removed = np.asarray(Image.open(folder/'removal-mask.png')) > 0
            words = np.asarray(Image.open(folder/'text-removal-mask.png')) > 0
            strokes = np.asarray(Image.open(folder/'fitted-stroke-removal-mask.png')) > 0
            extension = np.asarray(Image.open(folder/'header-extension-mask.png')) > 0
            assert np.array_equal(removed, (words | strokes) & ~extension)
            assert np.array_equal(pixels[..., :3][~(removed | extension)], selected[~(removed | extension)])
        assert all(word['copy'] == 'Rose Glass' for word in row['text'])
    assert result['panels']['stand_header']['lineart_measurement']['width_mm'] == .6
    assert 'physical_source' not in result and 'drawing_material' not in result


def test_attempt_art_refuses_failed_coverage_before_a_bundle_is_written(tmp_path, monkeypatch):
    from apps.pipeline.services import round_files_attempt_art as attempt_art
    from apps.pipeline.services import round_files_line_fit as line_fit
    source, inspection, brief, details, geometry = _attempt_art_fixture(tmp_path)
    actual = line_fit.fit_line_network
    def low_coverage(*args, **kwargs):
        record = actual(*args, **kwargs)
        record['passed'] = False; record['coverage'] = .89
        return record
    monkeypatch.setattr(line_fit, 'fit_line_network', low_coverage)
    with pytest.raises(ValueError, match='coverage/support failed'):
        attempt_art.prepare_attempt_art(source, inspection, brief, tmp_path/'attempt', details, geometry,
                                       expected_sha256=art.sha(source))
    assert not (tmp_path/'attempt'/'art.json').exists()


def test_preservation_accepted_detail_line_shift_still_fails_original_picture_coverage(tmp_path):
    from apps.pipeline.services import round_files_attempt_art as attempt_art
    import json
    source, inspection, brief, details, geometry = _attempt_art_fixture(tmp_path)
    original = Image.new('RGB', (200, 200), (170, 175, 185))
    draw = ImageDraw.Draw(original)
    draw.line((35, 45, 165, 155), fill='#D5AF59', width=2)
    draw.line((35, 155, 165, 45), fill='#D5AF59', width=2)
    draw.rectangle((70, 172, 129, 183), fill='#D5AF59')
    picture = Image.open(source).convert('RGB'); picture.paste(original, (0, 0)); picture.save(source)
    candidate = original.copy(); draw = ImageDraw.Draw(candidate)
    draw.rectangle((25, 30, 175, 165), fill=(170, 175, 185))
    draw.line((37, 45, 167, 155), fill='#D5AF59', width=2)
    draw.line((35, 155, 165, 45), fill='#D5AF59', width=2)
    candidate = candidate.resize((600, 600), Image.Resampling.LANCZOS)
    reference = np.asarray(original)
    compared = np.asarray(candidate.resize(original.size, Image.Resampling.LANCZOS))
    de00 = float(art.metrics.delta_e00(art.metrics.srgb_to_lab(reference), art.metrics.srgb_to_lab(compared)).mean())
    similarity = float(art.metrics.ssim(art.metrics.luma(reference), art.metrics.luma(compared)))
    assert de00 <= 1.5 and similarity >= .97
    for detail in details['panels'].values():
        detail['identity']['source_sha256'] = art.sha(source)
    detail = details['panels']['body_front']; candidate.save(detail['selected_path'])
    detail.update(accepted=True, selected='candidate.png', selected_sha256=art.sha(detail['selected_path']),
                  de00_mean=de00, ssim=similarity)
    with pytest.raises(ValueError, match='differs from original picked lines'):
        attempt_art.prepare_attempt_art(source, inspection, brief, tmp_path/'attempt', details, geometry,
                                       expected_sha256=art.sha(source))
    measured = json.loads((tmp_path/'attempt'/'body_front'/'line-fit.json').read_text())
    assert measured['passed'] and measured['coverage'] >= .9  # candidate alone falsely looks safe
    assert measured['original_picture_measurement']['coverage'] < .9
    assert not (tmp_path/'attempt'/'art.json').exists()


def test_duplicate_axis_merge_reaches_fixed_point_without_merging_parallel_ridges():
    from apps.pipeline.services import round_files_line_fit as line_fit
    points = np.column_stack((np.linspace(0, 9, 91), np.zeros(91)))
    # The bridging proposal arrives after the two disjoint proposals. Merging
    # it once extends the first axis into the second axis's observed support.
    axes = [(np.array([a, 0.]), np.array([b, 0.])) for a, b in [(0, 4), (5, 9), (2, 6)]]
    merged = line_fit._consolidate_axes(axes, points, .18, .6)
    assert len(merged) == 1
    assert merged[0][0] == pytest.approx([0, 0])
    assert merged[0][1] == pytest.approx([9, 0])
    parallel = [(np.array([0., y]), np.array([9., y])) for y in (0, .4)]
    separated = line_fit._consolidate_axes(parallel, np.vstack((points, points+[0, .4])), .18, .6)
    assert len(separated) == 2


def test_only_exact_collinear_degree_two_nodes_collapse():
    from apps.pipeline.services import round_files_line_fit as line_fit
    nodes = [np.array(point, float) for point in [(0, 0), (1, 0), (2, 0), (3, 0), (2, 1), (4, .1)]]
    edges = [(0, 1), (1, 2), (2, 3), (2, 4), (3, 5)]
    result = line_fit._collapse_straight_nodes(nodes, edges)
    assert sorted(result) == [(0, 2), (2, 3), (2, 4), (3, 5)]
    assert edges == [(0, 1), (1, 2), (2, 3), (2, 4), (3, 5)]


def test_known_eleven_segment_network_has_no_bookkeeping_strokes(tmp_path):
    from apps.pipeline.services import round_files_line_fit as line_fit
    mask = np.zeros((1000, 300), np.uint8)
    cv2.line(mask, (40, 850), (260, 850), 1, 2)
    for index, x in enumerate([40, 84, 128, 172, 216, 260]):
        cv2.line(mask, (x, 100+80*index), (x, 850), 1, 2)
    rgb = np.full((1000, 300, 3), 160, np.uint8)
    result = line_fit.fit_line_network(rgb, mask.astype(bool), (15, 70), tmp_path/'eleven.svg')
    assert result['passed'] and result['coverage'] >= .9
    assert result['fitted_axis_count'] == 7 and len(result['segments']) == 11
    assert result['source_pixels_unchanged'] and result['source_mask_unchanged']
    assert result['width_mm'] == .3
    assert result['source_line_pixels'] == int(mask.sum())


def test_correct_centred_point_three_stroke_cannot_cover_half_mm_ridge(tmp_path):
    from apps.pipeline.services import round_files_line_fit as line_fit
    rgb = np.full((400, 400, 3), 160, np.uint8)
    mask = np.zeros((400, 400), bool)
    mask[40:360, 195:205] = True  # Ten source pixels at .05 mm = .50 mm.
    before = mask.copy()
    result = line_fit.fit_line_network(rgb, mask, (20, 20), tmp_path/'wide-ridge.svg')
    assert len(result['segments']) == 1 and result['all_segments_supported']
    assert result['width_mm'] == .3 and result['minimum_coverage'] == .9
    assert .5 < result['coverage'] < .7 and not result['passed']
    assert result['source_line_pixels'] == 3200 and np.array_equal(mask, before)
    assert all(abs(point[0]-10) <= .05 for point in result['segments'][0]['endpoints_mm'])


def test_fallback_mask_transport_does_not_invent_gold_at_interpolated_colour_edges(tmp_path):
    from apps.pipeline.services import round_files_attempt_art as attempt_art
    source, inspection, brief, details, geometry = _attempt_art_fixture(tmp_path)
    picture = np.asarray(Image.open(source).convert('RGB')).copy()
    picture[35:165, 25:30] = [240, 110, 20]
    picture[35:165, 30:34] = [240, 240, 240]
    Image.fromarray(picture).save(source)
    selected = cv2.resize(picture[:, :200], None, fx=2, fy=2, interpolation=cv2.INTER_LANCZOS4)
    body_detail = details['panels']['body_front']
    Image.fromarray(selected).save(body_detail['selected_path'])
    body_detail['selected_sha256'] = art.sha(body_detail['selected_path'])
    for detail in details['panels'].values():
        detail['identity']['source_sha256'] = art.sha(source)
    before = source.read_bytes()
    output = tmp_path/'transported'
    attempt_art.prepare_attempt_art(source, inspection, brief, output, details, geometry,
                                    expected_sha256=art.sha(source))
    folder = output/'body_front'
    original = np.asarray(Image.open(folder/'original-foil-source-mask.png')) > 0
    transported = np.asarray(Image.open(folder/'foil-source-mask.png')) > 0
    assert np.array_equal(transported, cv2.resize(original.astype(np.uint8), (400, 400), interpolation=cv2.INTER_NEAREST) > 0)
    assert not original[35:165, 25:34].any()
    seed = np.zeros((400, 400), bool); seed[70:330, 50:350] = True
    reclassified, _ = refinement_v2.source_metal(selected, seed, np.zeros(seed.shape, bool))
    assert reclassified[70:330, 50:68].any()  # Negative control: interpolation creates a false gold rail.
    assert not transported[70:330, 50:68].any()
    assert source.read_bytes() == before


def _low_resolution_pictured_network(kind):
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    from shapely import contains_xy
    edges = ([((1.5, 5), (13.5, 65)), ((13.5, 5), (1.5, 65))] if kind == 'x' else
             [((7.5, 5), (1.5, 35)), ((1.5, 35), (7.5, 65)),
              ((7.5, 65), (13.5, 35)), ((13.5, 35), (7.5, 5))])
    shape = unary_union([LineString(edge).buffer(.25) for edge in edges])
    yy, xx = np.meshgrid((np.arange(500)+.5)*70/500, (np.arange(134)+.5)*15/134, indexing='ij')
    original = contains_xy(shape, xx, yy)
    selected = cv2.resize(original.astype(np.uint8), (268, 1000), interpolation=cv2.INTER_NEAREST) > 0
    rgb = np.full((1000, 268, 3), 170, np.uint8)
    return rgb, selected, original


@pytest.mark.parametrize('kind', ['x', 'diamond'])
def test_pictured_acute_network_measures_original_widths_without_junction_strokes(tmp_path, kind):
    from apps.pipeline.services import round_files_line_fit as line_fit
    import json
    rgb, selected, original = _low_resolution_pictured_network(kind)
    before = original.copy(); rgb_before = rgb.copy()
    result = line_fit.fit_line_network(rgb, selected, (15, 70), tmp_path/'pictured.svg',
                                      width_mode='pictured', width_reference_mask=original)
    measured = line_fit.measure_line_network(result['svg'], original, (15, 70), width_mode='pictured')
    assert result['passed'] and measured['passed']
    assert result['coverage'] >= .9 and measured['coverage'] >= .9
    assert len(result['segments']) == 4
    assert result['source_line_pixels'] == int(selected.sum())
    assert measured['source_line_pixels'] == int(original.sum())
    assert result['width_reference_mask_sha256'] == hashlib.sha256(original.tobytes()).hexdigest()
    assert result['width_reference_size_px'] == [134, 500]
    assert all(row['stroke_width_mm'] == pytest.approx(.5, abs=.025) for row in result['segments'])
    for row in result['segments']:
        evidence = row['width_evidence']
        assert evidence['reference_size_px'] == [134, 500]
        accepted = [sample['width_mm'] for sample in evidence['samples'] if sample['accepted']]
        assert row['stroke_width_mm'] == pytest.approx(np.mean(accepted), abs=1e-8)
        assert len(accepted) >= 5
    assert np.array_equal(original, before) and np.array_equal(rgb, rgb_before)
    assert json.loads(json.dumps(result))['passed']
    degrees = {}
    for edge in result['segment_node_indices']:
        for index in edge:
            degrees[index] = degrees.get(index, 0)+1
    assert sorted(degrees.values()) == ([1, 1, 1, 1, 4] if kind == 'x' else [2, 2, 2, 2])


def test_pictured_width_uses_original_observations_not_selected_thickness_or_coverage(tmp_path):
    from apps.pipeline.services import round_files_line_fit as line_fit
    original = np.zeros((400, 400), bool); original[40:360, 195:205] = True
    selected = original.copy(); selected[40:360, 190:210] = True
    result = line_fit.fit_line_network(np.full((400, 400, 3), 170, np.uint8), selected,
        (20, 20), tmp_path/'original-width.svg', width_mode='pictured', width_reference_mask=original)
    assert len(result['segments']) == 1
    assert result['segments'][0]['stroke_width_mm'] == pytest.approx(.5, abs=.01)
    assert not result['passed'] and result['coverage'] < .6
    measured = line_fit.measure_line_network(result['svg'], original, (20, 20), width_mode='pictured')
    assert measured['passed'] and measured['coverage'] >= .9
    assert result['support_width_mm'] == .3
    with pytest.raises(ValueError, match='original boolean motif mask'):
        line_fit.fit_line_network(np.full((400, 400, 3), 170, np.uint8), original,
            (20, 20), tmp_path/'missing-reference.svg', width_mode='pictured')


def test_pictured_measurement_reads_actual_variable_widths_and_rejects_wide_unsupported_line(tmp_path):
    from apps.pipeline.services import round_files_line_fit as line_fit
    mask = np.zeros((400, 400), bool)
    mask[40:360, 96:104] = True; mask[40:360, 294:306] = True
    result = line_fit.fit_line_network(np.full((400, 400, 3), 170, np.uint8), mask, (20, 20),
        tmp_path/'variable.svg', width_mode='pictured', width_reference_mask=mask)
    assert result['passed'] and len(result['segments']) == 2
    assert sorted(row['stroke_width_mm'] for row in result['segments']) == pytest.approx([.4, .6], abs=.01)
    target = Path(result['svg'])
    target.write_text(target.read_text().replace('</svg>', '<path d="M 1,1 L 18,1" fill="none" stroke="#D5AF59" stroke-width="5"/></svg>'))
    changed = line_fit.measure_line_network(target, mask, (20, 20), width_mode='pictured')
    assert changed['segments'][-1]['stroke_width_mm'] == 5
    assert not changed['segments'][-1]['supported'] and not changed['passed']
    assert changed['support_width_mm'] == .3


def test_pictured_attempt_art_keeps_original_measurements_clear_cap_and_unchanged_pixels(tmp_path):
    from apps.pipeline.services import round_files_attempt_art as attempt_art
    source, inspection, brief, details, geometry = _attempt_art_fixture(tmp_path, motif_width=6)
    before = source.read_bytes()
    result = attempt_art.prepare_attempt_art(source, inspection, brief, tmp_path/'pictured-art', details,
        geometry, expected_sha256=art.sha(source), width_mode='pictured')
    for key, row in result['panels'].items():
        assert row['preservation']['outside_allowed_masks_exact']
        pixels = np.asarray(Image.open(row['raster']))
        if key == 'cap_front':
            assert row['lineart_svg'] is None and not pixels[..., 3].any()
            assert row['marks'][0]['box_norm'] == pytest.approx([.4, .4, .6, .6])
        else:
            measured = row['lineart_measurement']
            assert measured['passed'] and measured['original_picture_measurement']['passed']
            assert measured['width_reference_size_px'] == [200, 200]
            assert measured['width_mode'] == 'pictured'
        if key.startswith('stand_'):
            folder = Path(row['raster']).parent
            selected = np.asarray(Image.open(folder/'selected.png'))
            removed = np.asarray(Image.open(folder/'removal-mask.png')) > 0
            extension = np.asarray(Image.open(folder/'header-extension-mask.png')) > 0
            assert np.array_equal(pixels[..., :3][~(removed | extension)], selected[~(removed | extension)])
    assert source.read_bytes() == before


def _evidence_mask(record):
    w,h=record['size_px']
    mask=np.zeros((h,w),bool)
    for y,x0,x1 in record['row_runs_y_x0_x1_exclusive']:
        mask[y,x0:x1]=True
    assert int(mask.sum()) == record['pixels']
    assert hashlib.sha256(mask.tobytes()).hexdigest() == record['sha256_bool_bytes']
    return mask


def test_source_material_rejects_connected_warm_reflections_and_keeps_gold_branches():
    rgb=np.full((80,80,3),(162,83,98),np.uint8)
    rgb[5:76,60]=(239,212,198)
    rgb[5,4:61]=(220,180,147)
    gold=np.zeros((80,80),np.uint8)
    cv2.line(gold,(15,45),(60,25),1,3)
    cv2.line(gold,(30,14),(46,48),1,3)
    gold[55:76,24]=1
    rgb[gold>0]=(245,221,149)
    # A pale highlight attached to the gold is valid source metal.
    rgb[61:71,25]=(255,253,240)
    seed=np.zeros((80,80),bool);seed[10:76,10:62]=True
    protected=np.zeros_like(seed)
    original=rgb.copy()
    old,old_record=refinement_v2.source_metal(rgb,seed,protected)
    selected,record=refinement_v2.source_metal(rgb,seed,protected,distinguish_material=True)
    assert old[50:75,60].all()
    assert not selected[50:75,60].any()
    assert not selected[5,5:50].any()
    assert selected[gold>0].all()
    assert selected[61:71,25].all()
    assert np.array_equal(rgb,original)
    assert np.array_equal(_evidence_mask(record['legacy_candidate_mask']),old)
    rejected=_evidence_mask(record['rejected_legacy_mask'])
    added=_evidence_mask(record['added_source_pale_mask'])
    assert np.array_equal(rejected,old & ~selected)
    assert np.array_equal(added,selected & ~old)
    assert np.array_equal((old & ~rejected)|added,selected)
    assert record['legacy_source_segmentation'] == old_record
    assert record['schema']=='source_material_metal/1'


@pytest.mark.parametrize('colour',[(245,221,149),(255,253,240),(255,250,220)])
def test_source_material_preserves_legitimate_thin_gold_and_pale_yellow(colour):
    rgb=np.full((70,70,3),(163,80,97),np.uint8)
    rgb[8:62,31]=colour
    seed=np.zeros((70,70),bool);seed[30:40,30:33]=True
    protected=np.zeros_like(seed)
    selected,record=refinement_v2.source_metal(rgb,seed,protected,distinguish_material=True)
    expected=np.zeros_like(seed);expected[8:62,31]=True
    assert np.array_equal(selected,expected)
    assert record['outside_seed_pixels']>0


@pytest.mark.parametrize('colour',[(239,212,198),(255,254,253)])
def test_source_material_without_gold_core_requires_review(colour):
    rgb=np.full((40,40,3),(163,80,97),np.uint8)
    rgb[5:35,20]=colour
    seed=np.ones((40,40),bool)
    with pytest.raises(ValueError,match='No reliable yellow metal core'):
        refinement_v2.source_metal(rgb,seed,np.zeros_like(seed),distinguish_material=True)


def test_source_material_protects_text_even_when_coloured_gold():
    rgb=np.full((50,50,3),(163,80,97),np.uint8)
    rgb[5:45,15]=(245,221,149)
    rgb[5:45,30]=(245,221,149)
    seed=np.ones((50,50),bool)
    protected=np.zeros_like(seed);protected[:,29:32]=True
    selected,record=refinement_v2.source_metal(rgb,seed,protected,distinguish_material=True)
    assert selected[5:45,15].all()
    assert not selected[:,29:32].any()


def _bevelled_three_axis_meeting():
    size = np.array([15., 70.])
    yy, xx = np.meshgrid((np.arange(500)+.5)*70/500, (np.arange(134)+.5)*15/134, indexing='ij')
    points = np.stack((xx, yy), axis=-1)
    axes = [(np.array(a, float), np.array(b, float)) for a, b in
            [((2, 3), (13, 47)), ((13, 5), (7.5, 25)), ((7.5, 25), (2, 35))]]
    mask = np.zeros((500, 134), bool)
    for index, (start, end) in enumerate(axes):
        unit = (end-start)/np.linalg.norm(end-start)
        normal = np.array([-unit[1], unit[0]])
        along = (points-start) @ unit
        across = (points-start) @ normal
        width = .5+.04*np.sin(along*.8+index)
        bevel_shift = .04*np.sin(along*.45+index)
        mask |= ((along >= 0) & (along <= np.linalg.norm(end-start)) &
                 (np.abs(across-bevel_shift) <= width/2))
        mask |= np.linalg.norm(points-start, axis=-1) <= .25
        mask |= np.linalg.norm(points-end, axis=-1) <= .25
    selected = cv2.resize(mask.astype(np.uint8), (268, 1000), interpolation=cv2.INTER_NEAREST) > 0
    rgb = np.full((1000, 268, 3), [164, 78, 98], np.uint8)
    rgb[selected] = [245, 221, 149]
    return rgb, selected, mask, axes, size


@pytest.mark.parametrize('biased_proposals', [False, True])
def test_bevelled_varying_width_meeting_remains_one_connected_four_stroke_network(tmp_path, monkeypatch, biased_proposals):
    from apps.pipeline.services import round_files_line_fit as line_fit
    rgb, selected, original, axes, size = _bevelled_three_axis_meeting()
    before = original.copy()
    if biased_proposals:
        # Each centre proposal is within the original half-pixel diagonal,
        # but their separate intersections exceed the previous node snap.
        biased = []
        for offset, (start, end) in zip([-.085, .085, -.085], axes):
            unit = (end-start)/np.linalg.norm(end-start)
            normal = np.array([-unit[1], unit[0]])
            biased.append((start+offset*normal, end+offset*normal))
        _, old_edges = line_fit._network(biased, .195)
        assert len(old_edges) == 5
        monkeypatch.setattr(line_fit, '_candidate_axes', lambda *args: (biased, size/[268, 1000]))
    result = line_fit.fit_line_network(rgb, selected, size, tmp_path/'meeting.svg',
        width_mode='pictured', width_reference_mask=original)
    measured = line_fit.measure_line_network(result['svg'], original, size, width_mode='pictured')
    assert result['passed'] and measured['passed']
    assert result['coverage'] >= .9 and measured['coverage'] >= .9
    assert result['all_segments_supported'] and measured['all_segments_supported']
    assert result['source_line_pixels'] == int(selected.sum())
    assert measured['source_line_pixels'] == int(original.sum())
    assert len(result['segments']) == 4 and result['rejected_explained_segments'] == []
    degrees = {}
    for edge in result['segment_node_indices']:
        for index in edge:
            degrees[index] = degrees.get(index, 0)+1
    assert sorted(degrees.values()) == [1, 1, 1, 1, 4]
    meetings = result['pictured_meetings']['meetings']
    assert len(meetings) == 1 and meetings[0]['point_mm'] == pytest.approx([7.5, 25], abs=.1)
    assert all(row['stroke_width_mm'] == pytest.approx(.5, abs=.03) for row in result['segments'])
    assert all(row['width_evidence']['independent_original_station_cells'] >= 3 for row in result['segments'])
    assert np.array_equal(original, before)


def test_source_supported_nearby_parallel_branch_meetings_stay_distinct():
    from apps.pipeline.services import round_files_line_fit as line_fit
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    from shapely import contains_xy
    axes = [(np.array(a, float), np.array(b, float)) for a, b in
            [((7.5, 10), (7.5, 40)), ((3, 22), (12, 28)), ((3, 23.2), (12, 29.2))]]
    yy, xx = np.meshgrid((np.arange(500)+.5)*70/500, (np.arange(134)+.5)*15/134, indexing='ij')
    mask = contains_xy(unary_union([LineString(pair).buffer(.25) for pair in axes]), xx, yy)
    nodes, edges, record = line_fit._pictured_network(axes, mask, np.array([15., 70.]))
    assert len(record['meetings']) == 2 and len(edges) == 7
    assert sorted(row['point_mm'][1] for row in record['meetings']) == pytest.approx([25, 26.2])


def test_subpixel_repeats_do_not_supply_independent_width_evidence():
    from apps.pipeline.services import round_files_line_fit as line_fit
    mask = np.zeros((100, 100), bool); mask[49:52, 49:52] = True
    with pytest.raises(ValueError, match='obscured by meeting nodes'):
        line_fit._pictured_width(np.array([5., 5.]), np.array([5.04, 5.]), mask, np.array([10., 10.]), [])


def test_acute_overlap_does_not_erase_a_short_perpendicular_arm():
    from apps.pipeline.services import round_files_line_fit as line_fit
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    from shapely import contains_xy
    axes = [(np.array(a, float), np.array(b, float)) for a, b in
            [((7.5, 5), (7.5, 65)), ((4.3, 5), (10.7, 65)), ((7.5, 35), (8.6, 35))]]
    yy, xx = np.meshgrid((np.arange(500)+.5)*70/500, (np.arange(134)+.5)*15/134, indexing='ij')
    mask = contains_xy(unary_union([LineString(pair).buffer(.25) for pair in axes]), xx, yy)
    nodes, edges, record = line_fit._pictured_network(axes, mask, np.array([15., 70.]))
    assert len(record['meetings']) == 1 and len(edges) == 5
    overlap = record['meetings'][0]['endpoint_overlap_by_axis_mm']
    assert overlap['0'] > 1.1 and overlap['1'] > 1.1
    assert overlap['2'] < .5
    tip = next(index for index, point in enumerate(nodes) if np.allclose(point, [8.6, 35]))
    assert sum(tip in edge for edge in edges) == 1


def test_source_material_unrelated_gold_does_not_widen_seeded_motif_support():
    rgb=np.full((120,120,3),(163,80,97),np.uint8)
    rgb[10:110,20]=(245,221,149)
    rgb[60,21:61]=(239,212,198)
    seed=np.zeros((120,120),bool);seed[40:80,18:22]=True
    protected=np.zeros_like(seed)
    original,original_record=refinement_v2.source_metal(rgb,seed,protected,distinguish_material=True)
    rgb[10:50,75:115]=(245,221,149)
    with_unrelated,record=refinement_v2.source_metal(rgb,seed,protected,distinguish_material=True)
    assert np.array_equal(with_unrelated,original)
    assert not with_unrelated[10:50,75:115].any()
    assert int(original[60,21:61].sum()) == 2
    assert len(record['core_components']) == 2
    assert record['core_components'][0]['radius_source_px'] == original_record['core_components'][0]['radius_source_px']


# Retry 5's stop (BREAKS §11): a vertical 0.5 mm ridge crossed by two
# horizontals 1.2 mm apart, on a 134 x 500 px mask of a 15 x 70 mm panel.
_BRIDGE_AXES = [([7.5, 5.], [7.5, 65.]), ([2., 25.], [13., 25.]), ([2., 26.2], [13., 26.2])]


def _synthetic_ridges(axes, widths):
    size = np.array([15., 70.]); scale = size/np.array([134, 500])
    yy, xx = np.mgrid[:500, :134]
    positions = np.stack((xx+.5, yy+.5), axis=-1)*scale
    mask = np.zeros((500, 134), bool)
    for (start, end), width in zip(axes, widths):
        a, b = np.array(start), np.array(end); vector = b-a
        along = np.clip(((positions-a)*vector).sum(axis=-1)/(vector @ vector), 0, 1)
        mask |= np.linalg.norm(positions-a-along[..., None]*vector, axis=-1) <= width/2
    rgb = np.full((500, 134, 3), (162, 83, 98), np.uint8); rgb[mask] = (245, 221, 149)
    return rgb, mask, size


def _fit_pictured(tmp_path, rgb, mask, size):
    from apps.pipeline.services import round_files_line_fit as line_fit
    before = mask.copy()
    result = line_fit.fit_line_network(rgb, mask, size, tmp_path/'network.svg',
                                       width_mode='pictured', width_reference_mask=mask)
    assert np.array_equal(mask, before) and result['source_mask_unchanged']
    return result


def test_insignificant_raw_proposal_is_rejected_before_it_can_abort_refinement(tmp_path, monkeypatch):
    from apps.pipeline.services import round_files_line_fit as line_fit
    rgb, mask, size = _synthetic_ridges(_BRIDGE_AXES, [.5]*3)
    found = line_fit._candidate_axes
    # A sub-pixel proposal on the real ridge: one station cell, no width evidence.
    tiny = (np.array([7.5, 45.]), np.array([7.5, 45.04]))
    monkeypatch.setattr(line_fit, '_candidate_axes', lambda *args: (found(*args)[0]+[tiny], found(*args)[1]))
    result = _fit_pictured(tmp_path, rgb, mask, size)
    rejected = [row for row in result['pictured_axis_refinement'] if row['status'] == 'rejected']
    assert len(rejected) == 1
    assert np.allclose(rejected[0]['proposal_endpoints_mm'], [tiny[0], tiny[1]])
    assert rejected[0]['diagnostic']['stage'] == 'candidate_refinement'
    assert rejected[0]['diagnostic']['reason'] == 'insufficient_independent_off_junction_sections'
    assert result['passed'] and result['coverage'] >= .9 and len(result['segments']) == 7
    assert result['width_estimated_segments'] == []


def test_short_bridge_between_meetings_takes_its_continuous_parent_ridge_width(tmp_path):
    rgb, mask, size = _synthetic_ridges(_BRIDGE_AXES, [.5]*3)
    result = _fit_pictured(tmp_path, rgb, mask, size)
    assert result['passed'] and result['coverage'] >= .9 and result['all_segments_supported']
    assert len(result['pictured_meetings']['meetings']) == 2 and len(result['segments']) == 7
    inherited = [row for row in result['segments']
                 if row['width_evidence']['evidence_scope'] == 'continuous_parent_flanks']
    assert len(inherited) == 1
    bridge = inherited[0]
    assert bridge['length_mm'] == pytest.approx(1.2, abs=.1)
    assert bridge['stroke_width_mm'] == pytest.approx(.5, abs=15/134)
    assert all(side['independent_original_station_cells'] >= 3 for side in bridge['width_evidence']['parent_flanks'])
    assert result['width_estimated_segments'] == []


def test_unmeasurable_segment_width_is_estimated_from_its_surface_and_recorded(tmp_path):
    # The parent ridge is 0.3 mm above the bridge and 0.7 mm below it, so the
    # bridge has no width of its own and its parent's flanks disagree.
    rgb, mask, size = _synthetic_ridges([([7.5, 5.], [7.5, 25.6]), ([7.5, 25.6], [7.5, 65.])]+_BRIDGE_AXES[1:],
                                        [.3, .7, .5, .5])
    result = _fit_pictured(tmp_path, rgb, mask, size)
    estimated = [row for row in result['segments'] if row['width_evidence']['evidence_scope'] == 'width_estimated']
    assert len(estimated) == 1 and len(result['segments']) == 7
    measured = [row['stroke_width_mm'] for row in result['segments'] if row not in estimated]
    record = estimated[0]['width_evidence']
    assert record['width_estimated'] and record['estimate_source'] == 'median_of_measured_segments_on_this_surface'
    assert record['measured_segment_count'] == 6
    assert estimated[0]['stroke_width_mm'] == pytest.approx(float(np.median(measured)))
    assert record['measurement_failure']['reason'] == 'parent_width_changes_across_segment'
    assert record['measurement_failure']['stage'] == 'final_segment_width'
    summary, = result['width_estimated_segments']
    # The segment's own width is read back from the emitted SVG (8 decimals).
    assert summary['status'] == 'width estimated'
    assert summary['stroke_width_mm'] == pytest.approx(estimated[0]['stroke_width_mm'], abs=1e-7)
    assert summary['reason'] == 'parent_width_changes_across_segment'
    assert result['passed'] and result['coverage'] >= .9


@pytest.mark.parametrize('failure', ['evidence', 'degenerate'])
def test_surface_with_no_measured_width_uses_default_foil_width(tmp_path, monkeypatch, failure):
    from apps.pipeline.services import round_files_line_fit as line_fit
    rgb, mask, size = _synthetic_ridges(_BRIDGE_AXES, [.5]*3)
    def unmeasurable(*args):
        if failure == 'evidence':
            raise line_fit.WidthEvidenceError('Original stroke width is obscured by meeting nodes',
                                              {'schema': 'line_width_evidence_error/1', 'reason': 'fixture'})
        raise ValueError('arange: cannot compute length')
    monkeypatch.setattr(line_fit, '_segment_pictured_width', unmeasurable)
    result = _fit_pictured(tmp_path, rgb, mask, size)
    assert len(result['width_estimated_segments']) == len(result['segments']) == 7
    assert all(row['stroke_width_mm'] == pytest.approx(.3) for row in result['segments'])
    assert all(row['width_evidence']['estimate_source'] == 'default_foil_width' for row in result['segments'])
    assert all(row['width_evidence']['measured_segment_count'] == 0 for row in result['segments'])
    assert {row['reason'] for row in result['width_estimated_segments']} == (
        {'fixture'} if failure == 'evidence' else {'arange: cannot compute length'})


def test_width_fallback_does_not_hide_a_code_defect(tmp_path, monkeypatch):
    from apps.pipeline.services import round_files_line_fit as line_fit
    rgb, mask, size = _synthetic_ridges(_BRIDGE_AXES, [.5]*3)
    def defect(*args):
        raise KeyError('axis_index')
    monkeypatch.setattr(line_fit, '_segment_pictured_width', defect)
    with pytest.raises(KeyError):
        _fit_pictured(tmp_path, rgb, mask, size)


def test_pictured_network_never_raises_for_an_unmeasurable_axis():
    from apps.pipeline.services import round_files_line_fit as line_fit
    rgb, mask, size = _synthetic_ridges(_BRIDGE_AXES, [.5]*3)
    axes = [(np.array(a), np.array(b)) for a, b in _BRIDGE_AXES]
    with pytest.raises(ValueError):
        line_fit._pictured_width(np.array([1., 50.]), np.array([1., 60.]), mask, size, [])
    nodes, edges, record = line_fit._pictured_network(axes+[(np.array([1., 50.]), np.array([1., 60.]))], mask, size)
    assert len(record['meetings']) == 2 and len(edges) == 8


# The owner's message of 2026-10-27: one bad text item never stops the read; invented
# lettering is an ornament zone set from COPY; the stand is built for the brief's grid.

def test_reading_repairs_items_one_by_one_and_drops_only_the_bad_one(tmp_path):
    source,brief,inspection=fixture(tmp_path)
    body=inspection['panels']['body_front']
    body['text']=[
        {'field':'product_latin','box_px':[5,80,25,96],'color':'rgb(213, 175, 89)','rotation':-90},
        {'field':'product_arabic','box_px':[20,80,40,96],'color':'gold','rotation':0},
        {'field':'shade_0','box_px':[-8,108,60.4,126],'color':'d5af59','rotation':0,'arc':True},
        {'field':'shade_0','box_px':[10,30,60,45],'color':'#d5af59','rotation':28},
        {'field':'invented','box_px':[10,50,60,60],'color':'#D5AF59','rotation':0}]
    body['marks']=[{'kind':'logo','box_px':[30,20,50,70],'color':[213,175,89],'rotation':'-90'}]
    plan=art.validate_inspection(art.normalise_reading(inspection,[320,160],brief),[320,160],brief)
    rows=plan['panels']['body_front']['text']
    assert [row['field'] for row in rows]==['product_latin','shade_0','shade_0']
    assert rows[0]=={'field':'product_latin','box_px':[5,80,25,96],'color':'#D5AF59','rotation':90}
    assert rows[1]['box_px']==[0,108,61,126] and rows[1]['color']=='#D5AF59' and rows[1]['arc'] is True
    assert rows[2]['rotation']==0 and rows[2]['angle_deg']==28
    assert plan['panels']['body_front']['marks']==[{'box_px':[30,20,50,70],'color':'#D5AF59','rotation':90,'kind':'logo'}]
    dropped=[(row['item'],row['why']) for row in plan['reading_findings'] if row['action']=='dropped']
    assert dropped==[('text “product_arabic”',"its colour 'gold' is not a colour"),
                     ('text “invented”','it names no supplied COPY field')]
    whys=' | '.join(row['why'] for row in plan['reading_findings'])
    for words in ('rotation -90 read as 90 (reads bottom to top)','box clipped to its panel',
                  'set straight in its bounding box; the picture curves it','the picture turns it 28°'):
        assert words in whys
    result=art.prepare_art(source,plan,brief,tmp_path/'art')
    assert [(row['copy'],row['rotation']) for row in result['panels']['body_front']['text']]==[
        ('Lip Gloss',90),('Rose Glass',0),('Rose Glass',0)]
    del inspection['panels']['cap_front']
    with pytest.raises(ValueError,match='front, cap'):
        art.validate_inspection(art.normalise_reading(inspection,[320,160],brief),[320,160],brief)


def test_a_negative_quarter_turn_reads_bottom_to_top(tmp_path):
    from apps.pipeline.services.round_files_export import Surface
    assert art._turn(-90)==(90,90) and art._turn(-270)==(270,270) and art._turn(270)==(270,270)
    assert art._turn(2)==(0,0) and art._turn(None)==(0,0) and art._turn('up')==(None,None)
    surface=Surface([20,60],'direction')
    surface.text({'copy':'BBROSE','face':'latin','box_mm':[2,2,18,58],'size_pt':12,'rotation':art._turn(-90)[0]})
    path=tmp_path/'direction.ai';surface.save(path)
    with fitz.open(path) as doc:
        ys=[char[2][1] for span in doc[0].get_texttrace() for char in span['chars']]
    assert len(ys)==6 and ys==sorted(ys,reverse=True)


def test_invented_lettering_is_removed_and_set_from_copy_along_its_path(tmp_path):
    from apps.pipeline.services import round_files_ornament as ornament
    from apps.pipeline.services.round_files_export import Surface, read_back_ai
    source,brief,inspection=fixture(tmp_path)
    brief['shades']=[{'name':'Rose Glass','hex':'#C9707A','name_arabic':'روز جلاس'},
                     {'name':'Ember Glow','hex':'#C2553A','name_arabic':'إمبر جلو'}]
    path=[[165,72],[200,60],[235,72]]
    image=Image.open(source).convert('RGB')
    ImageDraw.Draw(image).line([tuple(p) for p in path],fill='#D5AF59',width=6)   # the picture's pseudo-script
    image.save(source)
    inspection['panels']['stand_header']['ornament_lettering']=[
        {'path_px':path,'height_px':6.4,'color':'#d5af59'},{'path_px':[[170,60]],'height_px':6,'color':'#D5AF59'}]
    plan=art.validate_inspection(art.normalise_reading(inspection,[320,160],brief),[320,160],brief)
    assert plan['panels']['stand_header']['ornament_lettering']==[{'path_px':path,'height_px':7,'color':'#D5AF59'}]
    assert [row['action'] for row in plan['reading_findings'] if row['item']=='ornament lettering']==['replaced','dropped']
    result=art.prepare_art(source,plan,brief,tmp_path/'art')
    row=result['panels']['stand_header'];folder=Path(row['raster']).parent
    band=ornament.zone_mask((80,160),plan['panels']['stand_header']['ornament_lettering'][0],[160,0,240,160])
    assert (np.asarray(Image.open(folder/'text-removal-mask.png'))>0)[band].all()
    assert not (np.asarray(Image.open(folder/'foil-source-mask.png'))>0)[band].any()
    zone=row['ornament'][0]
    assert [(item['field'],item['copy']) for item in zone['copy']]==[
        ('brand','BBROSE'),('product_arabic','ملمع شفاه'),('arabic_shade_0','روز جلاس'),('arabic_shade_1','إمبر جلو')]
    runs,record=ornament.layout_runs('stand_header',0,zone,[0,0,107,214])
    assert record['left_out']==[] and record['size_pt']>=5
    # Arabic leads: read right to left, so the brand sits at the path's end.
    assert [run['copy'] for run in runs]==['جلو','إمبر','جلاس','روز','شفاه','ملمع','BBROSE']
    assert runs[0]['angle_deg']>10 and runs[-1]['angle_deg']<-10
    surface=Surface([107,214],'ornament')
    for run in runs:
        surface.text(run)
    saved=tmp_path/'ornament.ai';surface.save(saved)
    readback=read_back_ai(saved,surface.rows,surface.elements)
    assert readback['checks']['live_text'] and all(copy['present'] for copy in readback['copies'])
    assert all(row['angle_deg']==run['angle_deg'] and row['ornament'] for row,run in zip(surface.rows,runs))


def test_the_stand_is_built_for_the_briefs_grid_and_lists_the_pictures(tmp_path):
    from apps.pipeline.services import round_files_stand as stand
    _,brief,inspection=fixture(tmp_path)
    inspection['stand']={'rows':3,'columns':6,'count':18,'bottles':[
        {'row':r,'column':c,'box_px':[5+c*12,5+r*3,15+c*12,100],'shade_field':'shade_0' if r==0 and c<2 else None}
        for r in range(3) for c in range(6)]}
    geometry=stand.solve_stand(brief,inspection)
    assert (geometry['rows'],geometry['columns'],geometry['count'])==(3,4,12) and len(geometry['record']['holes'])==12
    assert geometry['layout']['observed']=={'rows':3,'columns':6,'count':18} and geometry['layout']['source']=='brief'
    assert geometry['layout']['note']==('The picture shows 18 products (3 rows × 6 across); '
                                        'the stand is built for the brief’s 12 (3 rows × 4 across).')
    loading=art.shade_loading(inspection,brief)
    assert len(loading['slots'])==12 and len(loading['observed_slots'])==18
    assert [slot['shade_field'] for slot in loading['slots'][:4]]==['shade_0','shade_0',None,None]
    assert loading['unresolved_count']==10 and 'same row and column' in loading['seat_rule']
    brief['stand']['layout']={'rows':3}
    assert stand.stand_layout(brief,inspection)['columns']==4
    brief['stand']['layout']={}
    fallback=stand.stand_layout(brief,inspection)
    assert fallback['source']=='picture' and fallback['count']==18 and not fallback['differs']


def test_round_copy_record_adds_unconfirmed_arabic_shade_names_bound_to_its_brief(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    from apps.pipeline.services import round_files_flow as files_flow, round_flow as flow
    _,brief,_=fixture(tmp_path)
    build=SimpleNamespace(inputs={'brief':brief,'brief_sha256':'a'*64},round=SimpleNamespace(slug='copy'))
    monkeypatch.setattr(flow,'round_root',lambda record: tmp_path)
    assert files_flow.files_brief(build)==brief
    record={'schema':'round_files_copy/1','brief_sha256':'a'*64,'arabic_shade_names':{'Rose Glass':'روز جلاس'},
            'source':'fixture','confirmed':False}
    (tmp_path/'files-copy.json').write_text(json.dumps(record,ensure_ascii=False))
    merged=files_flow.files_brief(build)
    assert merged['shades'][0]['name_arabic']=='روز جلاس' and 'name_arabic' not in brief['shades'][0]
    fields=art.copy_fields(merged)
    assert fields['arabic_shade_0']=='روز جلاس' and [key for key in fields if key.startswith('shade_')]==['shade_0']
    assert merged['copy_sources']['arabic_shade_names']['confirmed'] is False
    for damage in ({'brief_sha256':'b'*64},{'arabic_shade_names':{'Rose Glass':'Rose'}},
                   {'arabic_shade_names':{'Coral':'كورال'}}):
        (tmp_path/'files-copy.json').write_text(json.dumps(dict(record,**damage),ensure_ascii=False))
        with pytest.raises(ValueError):
            files_flow.files_brief(build)


def test_an_arabic_shade_name_is_optional_copy_in_the_brief():
    from apps.pipeline.services import round_ideas_brief
    brief=round_ideas_brief.gloss_brief()
    assert all('name_arabic' not in shade for shade in round_ideas_brief.normalize_ideas_brief(brief)['shades'])
    brief['shades'][2]['name_arabic']='  إمبر   جلو '
    assert round_ideas_brief.normalize_ideas_brief(brief)['shades'][2]['name_arabic']=='إمبر جلو'
    brief['shades'][2]['name_arabic']='Ember'
    with pytest.raises(ValueError,match='Arabic'):
        round_ideas_brief.normalize_ideas_brief(brief)
