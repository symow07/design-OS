"""Day 7 golden checks (the owner's §3, verified in §10): a changed library pin changes the prompt payload hash; an
"art-deco gold carton" brief retrieves art-deco tags in the top five of the REAL index; an excluded font is never offered;
file names never rank. The index read here is the committed docs/audit/day-7/library/materials-index.json."""
import json, shutil, tempfile
from pathlib import Path
from django.test import SimpleTestCase, override_settings
from apps.pipeline.services import materials_retrieval as mr


class _Task:
    def __init__(self, text):
        self.task_text, self.product, self.pk = text, None, 0


class _Approved:
    """An approved reference as the influence plan reads it."""
    def __init__(self, pk, item, title, description):
        self.pk, self.library_item_id, self.title, self.description = pk, item, title, description
        self.source_type, self.permission_status = 'MATERIAL_LIBRARY', 'USER_APPROVED_FOR_CONCEPT_REFERENCE'


def _row(sha, name, kind, tags, subject):
    return {"sha256": sha, "name": name, "paths": ["materials/" + name], "extension": ".jpg", "file_kind": "raster", "kind": kind,
            "subject": subject, "tags": tags, "style": [], "colours": [], "text_present": False, "text_seen": [], "language": "none",
            "surfaces": ["pattern-fill"], "preview": False, "caption_source": "day7-haiku", "rights": {"tier": "house", "excluded": False}}


class Day7LibraryGoldenTests(SimpleTestCase):
    def test_golden_1_a_changed_library_pin_changes_the_prompt_payload_hash(self):
        from apps.pipeline.services.concept_references import build_influence_plan, plan_hash
        task = _Task('gold pattern carton')
        a = _Approved(1, 'materials:' + 'a' * 64, 'Gold foil pattern', 'role: pattern · pattern · tags: gold, foil')
        b = _Approved(1, 'materials:' + 'b' * 64, 'Gold foil pattern', 'role: pattern · pattern · tags: gold, foil')
        plan_a, plan_b = build_influence_plan(task, [a]), build_influence_plan(task, [b])
        assert plan_a['library_pins'] == [{'pin': 'materials:' + 'a' * 64, 'role': 'pattern'}]
        assert plan_hash(plan_a) != plan_hash(plan_b)
        assert mr.pins_hash([a]) != mr.pins_hash([b]) and mr.pins_hash([a]) == mr.pins_hash([a])

    def test_golden_2_an_art_deco_gold_carton_brief_retrieves_art_deco_tags_in_the_top_five(self):
        assert mr.index_path().exists(), mr.index_path()
        top = mr.select(mr.rank(_Task('art-deco gold carton')))[:5]
        assert len(top) >= 3, top
        deco = [f for f in top if 'art-deco' in f['card']['tagset'] or {'art', 'deco'} <= (f['card']['tagwords'] | f['card']['subjectwords'])]
        assert deco, [f['card']['tags'] for f in top]
        assert all(f['card']['name'].lower() not in ' '.join(f['reasons']).lower() for f in top if f['card']['name'])

    def test_golden_3_an_excluded_font_is_never_offered(self):
        from apps.ire import font_pool, font_roles, lettering_faces
        excluded = font_pool.excluded()
        assert len(excluded) >= 4000, len(excluded)
        catalogue = font_roles.catalogue()
        assert not (set(excluded) & {e['sha256'] for e in catalogue.values()})
        for family, faces in lettering_faces.FAMILIES.items():
            for stem, _weight, _italic in faces:
                entry = catalogue.get(stem)
                assert entry is None or entry['sha256'] not in excluded, (family, stem)
        assert not [c for c in mr.cards() if c['offerable'] and c['kind'] == 'font']

    def test_golden_4_file_names_never_rank(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        rows = [_row('1' * 64, 'gold-floral-carton-pattern.jpg', 'background', ['stars', 'night', 'navy'], 'Scattered stars on a navy field'),
                _row('2' * 64, 'IMG_0001.jpg', 'pattern', ['gold', 'floral', 'repeat'], 'Gold floral repeat on cream')]
        index = Path(tmp) / 'materials-index.json'
        index.write_text(json.dumps({'schema': 'day7_materials_index/1', 'items': rows}))
        with override_settings(MATERIALS_INDEX_PATH=str(index), HOUSE_INDEX_PATH=str(Path(tmp) / 'none.json')):
            got = mr.candidates(_Task('gold floral pattern'))
        assert [g['library_item_id'] for g in got] == ['materials:' + '2' * 64], got
