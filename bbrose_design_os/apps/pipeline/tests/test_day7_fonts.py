"""Day 7 §4: the GRANTED pool (D-D7-1) in the type classifier's candidate set with licence evidence, through the seam;
UNVERIFIED and BLOCKED excluded by the list; the measured Arabic line re-run and NOT applied."""
import json
from pathlib import Path
from django.test import SimpleTestCase
from apps.ire import font_pool, font_roles, lettering_faces
from apps.ire.container_font_authority import VERIFIED_FOR_PRODUCTION

ROOT = Path(__file__).resolve().parents[4]


class Day7FontPoolTests(SimpleTestCase):
    def test_the_pool_is_in_the_catalogue_with_licence_wording_and_verifies_through_the_seam(self):
        cat = font_roles.catalogue()
        pool = {k: e for k, e in cat.items() if e['origin'] == font_pool.ORIGIN}
        assert len(pool) == 328 and all(e['licence'] for e in pool.values())
        verified = refused = 0
        for stem, entry in pool.items():
            if not entry.get('latin'):
                continue
            rec = font_roles.verify_candidate('display', stem)
            assert rec is not None, stem
            if rec['verification'] == VERIFIED_FOR_PRODUCTION:
                verified += 1
                assert rec['licence_id'] == entry['licence'] and rec['approved_by'].startswith('BBrose (D-D7-1')
                assert font_pool.GRANTED_EVIDENCE_SHA256 in rec['licence_evidence']
            else:
                refused += 1
        assert refused == 0 and verified == sum(1 for e in pool.values() if e.get('latin')), (verified, refused)

    def test_the_day7_grants_name_no_digest_an_earlier_grant_names_and_their_evidence_rehashes(self):
        import hashlib
        from apps.ire import container_font_owner_grant as cfg
        earlier = {s for g in cfg.OWNER_GRANTS_BEFORE_DAY7 for s in g['face_sha256s']}
        day7 = font_pool.day7_grants()
        assert len(day7) == 2 and sum(len(g['face_sha256s']) for g in day7) == 328
        for g in day7:
            assert not (set(g['face_sha256s']) & earlier)
            assert hashlib.sha256(Path(g['licence_evidence_path']).read_bytes()).hexdigest() == g['licence_evidence_sha256']
        assert cfg.OWNER_GRANTS[-len(day7):] == day7

    def test_the_chains_keep_the_brand_faces_first_and_name_no_excluded_face(self):
        excluded = font_pool.excluded()
        assert excluded['counts'] if False else len(excluded) == 4028
        cat = font_roles.catalogue()
        for family in lettering_faces.FAMILIES:
            faces = lettering_faces.faces_of(family)
            assert faces[:len(lettering_faces.FAMILIES[family])] == tuple(lettering_faces.FAMILIES[family])
            for stem, _weight, _italic in faces:
                entry = cat.get(stem)
                assert entry is None or entry['sha256'] not in excluded, (family, stem)
        assert len(lettering_faces.faces_of('sans')) > len(lettering_faces.FAMILIES['sans'])
        assert not (set(excluded) & {e['sha256'] for e in cat.values()})

    def test_the_arabic_line_was_re_run_against_the_pool_and_not_applied(self):
        record = json.loads((ROOT / 'docs/audit/day-7/fonts/arabic-line-comparison.json').read_text())
        assert record['applied'] is False and record['candidates'] >= 40
        assert record['cairo_applied']['fits'] and record['cairo_applied']['shaped_delta_percent'] <= 3.0
        assert all(r['shaped_delta_percent'] >= record['cairo_applied']['shaped_delta_percent'] for r in record['pool'] if 'shaped_delta_percent' in r)
        assert record['fit_within_tolerance'] == sum(1 for r in record['pool'] if r.get('fits'))
        specimen = json.loads((ROOT / 'docs/audit/day-7/fonts/specimen.json').read_text())
        assert len(specimen['latin']) == 12 and len(specimen['arabic']) == 12
