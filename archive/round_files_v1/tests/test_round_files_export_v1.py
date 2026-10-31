"""Archived with the retired picture-tracing path (docs/rounds/reuse-plan.md); moved from apps/pipeline/tests/test_round_files_export.py, not collected."""

def test_files_engine_material_drawing_has_clear_walls_gold_cap_and_unchanged_print(tmp_path):
    from apps.pipeline.services.round_files_art import mechanical_drawing, sha
    spec, geometry = full_stand_spec(tmp_path/'input')
    brief = fourteen_brief()
    inspection = {'image_size_px': [500, 800],
        'drawing_material': {'status': 'engine', 'wall_mm': 1.0, 'base_mm': 2.0},
        'stand': {'rows': 2, 'columns': 7, 'count': 14,
            'bottles': [{'row': row, 'column': column, 'box_px': [100 + column*30, 200, 120 + column*30, 684],
                         'shade_field': 'shade_0' if row == 0 else None}
                        for row in range(2) for column in range(7)]},
        'panels': {'body_front': {'text': [{'field': 'shade_0'}]}}}
    flats = {}
    for key in ('body_front', 'cap_front', 'stand_header', 'stand_base'):
        path = tmp_path/(key+'.png')
        image = Image.new('RGBA', (150, 300), (0, 0, 0, 0))
        if key == 'cap_front':
            ImageDraw.Draw(image).rectangle((65, 140, 85, 160), fill=(10, 20, 30, 255))
        image.save(path)
        flats[key] = str(path)
    proofs = {key: {'path': flats['body_front'], 'sha256': sha(flats['body_front'])}
              for key in ('shade_0', 'unresolved')}
    original = {key: Path(path).read_bytes() for key, path in flats.items()}
    output = tmp_path/'engine-drawing.png'
    result = mechanical_drawing(flats, brief, geometry, output,
                                inspection=inspection, body_proofs=proofs, px_per_mm=10)
    assert all(Path(path).read_bytes() == original[key] for key, path in flats.items())
    assert result['engine_material']['liquid_box_mm'] == [1, 1, 14, 68]
    assert result['engine_material']['provisional'] is True
    assert result['hero']['physical_source_material'] is None
    assert result['shade_loading']['unresolved_count'] == 7
    assert all(slot['liquid_colour'] is None for slot in result['stand_slots'] if slot['row'] == 2)
    rendered = Image.open(output)
    hero_x = 80
    hero_y = round((8+max(100, geometry['front_elevation']['height_mm'])-100)*10)
    shade_rgb = tuple(bytes.fromhex(brief['shades'][0]['hex'].lstrip('#')))
    assert rendered.getpixel((hero_x+75, hero_y+400)) == shade_rgb
    assert rendered.getpixel((hero_x+5, hero_y+400)) != shade_rgb
    assert rendered.getpixel((hero_x+75, hero_y+990)) != shade_rgb
    assert rendered.getpixel((hero_x+75, hero_y+150)) == (10, 20, 30)
    assert rendered.getpixel((hero_x+20, hero_y+50)) != rendered.getpixel((hero_x+120, hero_y+50))
    assert rendered.getpixel((hero_x+75, hero_y)) != rendered.getpixel((hero_x+75, hero_y+10))
    corrupted = deepcopy(inspection)
    corrupted['drawing_material']['physical_source'] = {}
    with pytest.raises(ValueError, match='physical source-picture'):
        mechanical_drawing(flats, brief, geometry, tmp_path/'invalid.png',
                           inspection=corrupted, body_proofs=proofs, px_per_mm=10)


@pytest.mark.skipif(os.environ.get('ROUND_FILES_NATIVE_FIXTURE') != '1', reason='Explicit local Illustrator fixture only')
@pytest.mark.parametrize('network_kind', ['crossing', 'short_bridge'])
def test_files_export_fitted_straight_network_survives_actual_native_reopen(tmp_path, network_kind):
    import cv2
    import numpy as np
    from apps.pipeline.services.round_files_line_fit import fit_line_network, measure_line_network
    destination = Path(os.environ.get('ROUND_FILES_NATIVE_FIXTURE_DIR', str(tmp_path))) / 'fitted-straight-network' / network_kind
    destination.mkdir(parents=True, exist_ok=True)
    rgb = np.full((500, 134, 3), [152, 78, 102], np.uint8)
    mask = np.zeros((500, 134), bool)
    yy, xx = np.mgrid[:500, :134]
    scale = np.array([15/134, 70/500])
    positions = np.stack((xx+.5, yy+.5), axis=-1)*scale
    source_lines = ([((12, 40), (120, 450)), ((12, 450), (120, 40)), ((12, 245), (120, 245))]
                    if network_kind == 'crossing' else
                    [((12, 175), (120, 175)), ((66, 40), (66, 450)), ((12, 184), (120, 184))])
    for (a, b), width in zip(source_lines, [.3, .5, .7]):
        start, end = (np.array(a)+.5)*scale, (np.array(b)+.5)*scale
        vector = end-start
        along = np.clip(((positions-start)*vector).sum(axis=-1)/(vector@vector), 0, 1)
        mask |= np.linalg.norm(positions-start-along[..., None]*vector, axis=-1) <= width/2
    rgb[mask > 0] = [213, 175, 89]
    mask = mask.astype(bool)
    Image.fromarray(rgb).save(destination/'source.png')
    Image.fromarray(mask.astype(np.uint8)*255).save(destination/'source-mask.png')
    source = destination/'fitted.svg'
    fit = fit_line_network(rgb, mask, (15, 70), source, width_mode='pictured', width_reference_mask=mask)
    assert fit['passed'] and fit['coverage'] >= .9 and fit['all_segments_supported']
    assert fit['source_pixels_unchanged'] and fit['source_mask_unchanged']
    inherited = [row for row in fit['segments'] if row['width_evidence']['evidence_scope'] == 'continuous_parent_flanks']
    if network_kind == 'short_bridge':
        assert len(fit['segments']) == 7 and len(inherited) == 1
        bridge = inherited[0]
        assert bridge['length_mm'] == pytest.approx(9*70/500, abs=.1)
        assert bridge['stroke_width_mm'] == pytest.approx(.5, abs=15/134)
        assert all(side['independent_original_station_cells'] >= 3 for side in bridge['width_evidence']['parent_flanks'])
    else:
        assert not inherited
    original = source.read_bytes()
    started = time.monotonic()
    offset = np.array([5., 5.])
    result = export.export_object({'id': 'fitted-network', 'size_mm': [28, 80],
        'foil_svg': [{'path': str(source), 'box_mm': [5, 5, 20, 75], 'fitted_strokes': True}],
        'foil_paths': [{'points_mm': [[23, 20], [26, 22], [23, 24]], 'fill': False, 'stroke_mm': .4}],
        'logos': [{'box_mm': [22, 3, 27, 8], 'foil': True}]}, destination/'files', native=True)
    assert result['native']['holds'] and result['readback']['native_illustrator_validated']
    assert result['readback']['raster_count'] == 0
    census = result['native']['reopened_census']
    assert census['fitted_strokes']['holds'] and result['readback']['fitted_strokes']['holds']
    assert result['layers'] == ['artwork', 'foil', 'type', 'logo', 'die', 'guides']
    strokes = [census['foilStrokes'][row['actual_index']] for row in census['fitted_strokes']['matched_strokes']]
    assert len(census['foilStrokes']) == len(strokes)+1  # Unrelated three-point foil remains outside the fitted check.
    assert len(strokes) == len(fit['segments']) >= 6
    assert max(row['stroke_width_mm'] for row in fit['segments'])-min(row['stroke_width_mm'] for row in fit['segments']) > .3
    remaining = [(np.asarray(row['endpoints_mm'])+offset, row['stroke_width_mm']) for row in fit['segments']]
    native_paths = []
    for stroke in strokes:
        assert stroke['typename'] == 'PathItem' and stroke['editable'] and stroke['stroked']
        assert not stroke['filled'] and not stroke['closed']
        points = np.asarray(stroke['points_mm'])
        assert points.shape == (2, 2)
        assert np.allclose(points, stroke['left_mm'], atol=.0001)
        assert np.allclose(points, stroke['right_mm'], atol=.0001)
        match = next((index for index, (expected, width) in enumerate(remaining)
                      if (np.allclose(points, expected, atol=.005) or np.allclose(points, expected[::-1], atol=.005))
                      and abs(stroke['width_mm']-width) < .0001), None)
        assert match is not None
        remaining.pop(match)
        (a, b), (c, d) = points-offset
        native_paths.append(f'<path d="M {a},{b} L {c},{d}" fill="none" stroke="#D5AF59" stroke-width="{stroke["width_mm"]}" stroke-linecap="round" stroke-linejoin="round"/>')
    assert not remaining
    native_svg = destination/'native-readback.svg'
    native_svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="15mm" height="70mm" viewBox="0 0 15 70">'+''.join(native_paths)+'</svg>')
    measured = measure_line_network(native_svg, mask, (15, 70), width_mode='pictured')
    assert measured['passed'] and measured['coverage'] >= .9 and measured['all_segments_supported']
    with fitz.open(result['ai']) as doc:
        clip = fitz.Rect(5*export.PT, 5*export.PT, 20*export.PT, 75*export.PT)
        pixmap = doc[0].get_pixmap(matrix=fitz.Matrix(134*4/(15*export.PT), 500*4/(70*export.PT)), alpha=True, clip=clip)
        pixels = np.frombuffer(pixmap.samples, np.uint8).reshape(pixmap.height, pixmap.width, pixmap.n)
        alpha = cv2.resize(pixels[..., -1], (134, 500), interpolation=cv2.INTER_AREA)
        doc[0].get_pixmap(dpi=600, alpha=True, clip=clip).save(destination/'native-final.png')
    coverage = float(((alpha >= 128) & mask).sum()/mask.sum())
    assert coverage >= .9
    assert source.read_bytes() == original
    (destination/'results.json').write_text(json.dumps({'seconds': time.monotonic()-started,
        'network_kind': network_kind, 'source_lines_px': source_lines,
        'source_canvas_px': [134, 500], 'target_mm': [15, 70], 'translation_mm': offset.tolist(),
        'known_source_widths_mm': [.3, .5, .7], 'width_mode': 'pictured',
        'source_mask_sha256': export.sha(destination/'source-mask.png'), 'fit': fit,
        'native_geometry_measurement': measured, 'actual_reopened_pdf_mask_coverage': coverage,
        'native_width_tolerance_mm': .0001, 'pdf_width_tolerance_mm': .002,
        'pdf_widths_mm': [row['actual_width_mm'] for row in result['readback']['fitted_strokes']['matched_strokes']],
        'result': result}, ensure_ascii=False, indent=2)+'\n')


