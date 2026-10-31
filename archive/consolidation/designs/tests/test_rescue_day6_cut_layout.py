"""Day 6 cut layout + BOM: parts derive from the assembly, layers are named, the artwork sheet places the surfaces."""
import copy, json, tempfile
from pathlib import Path
import fitz
from apps.pipeline.services import day6_cut_layout as cl

ROOT = cl.ROOT


def test_parts_derive_from_the_assembly_and_every_surface_is_carried_once():
    record = cl.parts()
    by = {p['id']: p for p in record['parts']}
    assert by['P10']['height_mm'] == 54 and by['P11']['height_mm'] == 54 and by['P09']['height_mm'] == 6
    assert sum(len(p['holes_mm']) for p in record['parts']) == 12 and all(h['diameter'] == 31 for p in record['parts'] for h in p['holes_mm'])
    carried = [sid for p in record['parts'] for sid in p['print_surface_ids']]
    assert sorted(carried) == sorted(['header.front', 'riser.3.front', 'riser.2.front', 'riser.1.front', 'lip.front', 'side.left', 'side.right'])
    assert by['S01']['width_mm'] == 180 + 2 * cl.FLAP and by['S01']['height_mm'] == 100 + 2 * cl.FLAP
    with tempfile.TemporaryDirectory() as tmp:
        a = json.loads(cl.ASSEMBLY.read_text()); a['seats'] = [6, 70, 134]; a['rise'] = 64
        path = Path(tmp) / 'assembly.json'; path.write_text(json.dumps(a))
        changed = {p['id']: p for p in cl.parts(path)['parts']}
        assert changed['P10']['height_mm'] == 64 and changed['P11']['height_mm'] == 64


def test_pdf_layers_bar_and_artwork_placements():
    for name, placed in (('cut-layout.pdf', 0), ('cut-layout-with-artwork.pdf', 7)):
        with fitz.open(ROOT / 'cut-layout' / name) as doc:
            assert sorted(o['name'] for o in doc.get_ocgs().values()) == sorted(cl.LAYERS)
            for page in doc:
                assert '50 mm calibration bar' in page.get_text()
            forms = sum(len(page.get_xobjects()) for page in doc)
            assert forms >= placed and (placed == 0 or forms >= 7)
    svg = (ROOT / 'cut-layout/cut-layout.svg').read_text()
    assert all('<g id="%s">' % layer in svg for layer in cl.LAYERS)


def test_compare_census_passes_on_match_and_fails_on_a_missing_element():
    record = cl.parts(); expected = cl.expected_counts(record)
    census = {'saved': True, 'layers': {layer: ({'texts': n} if layer == 'DIMENSIONS' else {'paths': n}) for layer, n in expected.items()}}
    assert cl.compare_census(census, record)['passed']
    broken = copy.deepcopy(census); broken['layers']['CUT']['paths'] -= 1
    assert not cl.compare_census(broken, record)['passed']
    assert not cl.compare_census({'saved': False, 'layers': census['layers']}, record)['passed']


def test_bom_rows_name_provisional_material_and_no_load_claim():
    bom = json.loads((ROOT / 'cut-layout/bom.json').read_text())
    assert bom['load_claim'].startswith('none') and all('PROVISIONAL' in r['material'] for r in bom['rows'])
    assert sum(r['qty'] for r in bom['rows']) == 27
