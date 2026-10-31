"""Day 7 §7: the two unbound faces composed from D1's grammar — header.back (mark and name only, centred, no device) and
base.front (the field strip continued, nothing else) — each with the Day 6 package, a native AI that validates, and a
TRACED_TEXT audit that passes; revision 2 untouched and pinned as the parent."""
import json
from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'docs/audit/day-7/surfaces'
PACKAGE = ('design-spec.json', 'design-graph.json', 'artwork.svg', 'artwork.pdf', 'artwork-pdf-compatible.ai', 'artwork.png', 'native-vectors.svg',
           'native-vectors.pdf', 'artwork-native.ai', 'artwork-native-validation.json', 'TRACED_TEXT.json')


class Day7SurfacesTests(SimpleTestCase):
    def test_the_two_faces_are_bound_packaged_native_and_audited_with_revision_two_as_parent(self):
        bindings = json.loads((OUT / 'surface-bindings.json').read_text())
        assert [s['surface_id'] for s in bindings['surfaces']] == ['header.back', 'base.front'] and bindings['parent_revision'] == 2
        import hashlib
        r2 = ROOT / 'docs/audit/day-6/stand/surfaces-r2/surface-bindings.json'
        assert bindings['parent_bindings_sha256'] == hashlib.sha256(r2.read_bytes()).hexdigest()
        for s in bindings['surfaces']:
            folder = OUT / s['surface_id']
            assert all((folder / name).exists() for name in PACKAGE), s['surface_id']
            assert hashlib.sha256((folder / 'artwork.pdf').read_bytes()).hexdigest() == s['pdf_sha256']
            assert json.loads((folder / 'artwork-native-validation.json').read_text())['passed'] is True
            assert json.loads((folder / 'TRACED_TEXT.json').read_text())['f7_rule_met'] is True
        audit = json.loads((OUT / 'TRACED_TEXT.json').read_text())
        assert audit['state'] == 'passed' and audit['f7_package_rule_met'] and audit['negative_controls_failed_as_required']

    def test_header_back_carries_the_mark_and_the_name_only_and_base_front_the_field_only(self):
        back = json.loads((OUT / 'header.back/design-graph.json').read_text())
        assert [l['id'] for l in back['lines']] == ['SUN', 'REPAIR', 'SERUM', 'arabic'] and [e['id'] for e in back['elements']] == ['logo', 'name_rule']
        assert back['device_roles'] == [] and back['width_mm'] == 180 and back['height_mm'] == 100
        group = [e['bbox_mm'] for e in back['elements']] + [l['measured_bbox_mm'] for l in back['lines']]
        centre = (min(b[0] for b in group) + max(b[2] for b in group)) / 2
        assert abs(centre - 90.0) < 0.01, centre
        base = json.loads((OUT / 'base.front/design-graph.json').read_text())
        assert base['lines'] == [] and base['elements'] == [] and base['device_roles'] == [] and base['height_mm'] == 6
        assert base['field']['stops'] == back['field']['stops']          # the same D1 field, continued
        spec = json.loads((OUT / 'base.front/design-spec.json').read_text())
        assert spec['source_status'].startswith('composed') and spec['production_ready'] is False
