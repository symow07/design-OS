from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch
import hashlib, json, os, stat, unicodedata
from tools.rescue_materials_migrate import apply, rollback, disk_proof, rename_exclusive, diagnose, spelling_plan, volume_case_insensitive
from apps.ire.materials_paths import resolve_material_file, original_material_key, MaterialPathError, MANIFEST_RELATIVE


class MigrationTests(TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
        self.rows=[]
        for index in range(2):
            old=self.root/f'materials/old/{index}.txt';old.parent.mkdir(parents=True,exist_ok=True);old.write_bytes(b'same bytes')
            st=old.stat();self.rows.append({'old_path':str(old.relative_to(self.root)),
                'new_path':f'materials/new/{index}.txt','sha256':hashlib.sha256(old.read_bytes()).hexdigest(),
                'size_bytes':st.st_size,'mtime_ns':st.st_mtime_ns})
        self.manifest=self.root/MANIFEST_RELATIVE;self.manifest.parent.mkdir(parents=True)
        self.manifest.write_text(''.join(json.dumps(r)+'\n' for r in self.rows))
        self.evidence=self.root/'materials/_migration';self.evidence.mkdir()

    def test_rename_multiset_both_directions_and_idempotent(self):
        result=apply(self.root,self.rows,self.evidence)
        self.assertTrue(result['after']['passed']);self.assertEqual(result['after']['actual_count'],2)
        self.assertEqual(apply(self.root,self.rows,self.evidence)['state'],'VERIFIED_NOOP')
        for row in self.rows:
            p=resolve_material_file(row['old_path'],repo_root=self.root,expected_sha=row['sha256'])
            self.assertEqual(p,self.root/row['new_path'])
            self.assertEqual(original_material_key(row['new_path'],row['sha256'],repo_root=self.root),(row['old_path'],row['sha256']))
        self.assertTrue(rollback(self.root,self.rows,self.evidence/'journal')['passed'])

    def test_automatic_rollback_after_partial_rename(self):
        with self.assertRaisesRegex(RuntimeError,'Injected'):
            apply(self.root,self.rows,self.evidence,fail_after=1)
        self.assertTrue(disk_proof(self.root,self.rows,'old_path')['passed'])
        proof=json.loads((self.evidence/'migration-proof.json').read_text())
        self.assertTrue(proof['rollback_triggered']);self.assertTrue(proof['rollback']['passed'])

    def test_user_immutable_flag_restored_after_move_and_rollback(self):
        row=self.rows[0];old=self.root/row['old_path'];os.chflags(old,stat.UF_IMMUTABLE)
        try:
            report=apply(self.root,self.rows,self.evidence)
            self.assertTrue(report['file_metadata_preserved'])
            self.assertEqual((self.root/row['new_path']).stat().st_flags,stat.UF_IMMUTABLE)
            rollback(self.root,self.rows,self.evidence/'move-journal.jsonl')
            self.assertEqual(old.stat().st_flags,stat.UF_IMMUTABLE)
        finally:
            for name in ('old_path','new_path'):
                p=self.root/row[name]
                if p.exists():os.chflags(p,0)

    def test_completed_recovery_finishes_publication(self):
        apply(self.root,self.rows,self.evidence)
        called=[]
        apply(self.root,self.rows,self.evidence,publication=lambda:called.append(True))
        self.assertEqual(called,[True])

    def test_publication_failure_reverses_moves(self):
        def fail():raise ValueError('index publication fault')
        with self.assertRaisesRegex(ValueError,'publication'):
            apply(self.root,self.rows,self.evidence,publication=fail)
        self.assertTrue(disk_proof(self.root,self.rows,'old_path')['passed'])

    def test_crash_after_rename_before_done_recovers(self):
        row=self.rows[0];new=self.root/row['new_path'];new.parent.mkdir()
        (self.evidence/'move-journal.jsonl').write_text(json.dumps({'intent':row['old_path']})+'\n')
        rename_exclusive(self.root/row['old_path'],new)
        self.assertEqual(apply(self.root,self.rows,self.evidence)['state'],'VERIFIED')

    def test_collision_does_not_replace_or_move(self):
        p=self.root/self.rows[0]['new_path'];p.parent.mkdir();p.write_bytes(b'unrelated')
        with self.assertRaisesRegex(RuntimeError,'destination'):
            apply(self.root,self.rows,self.evidence)
        self.assertEqual(p.read_bytes(),b'unrelated');self.assertTrue(all((self.root/r['old_path']).exists() for r in self.rows))

    def test_corruption_wrong_pin_and_escape_refused(self):
        apply(self.root,self.rows,self.evidence);row=self.rows[0]
        with self.assertRaises(MaterialPathError):resolve_material_file(row['old_path'],repo_root=self.root,expected_sha='0'*64)
        p=self.root/row['new_path'];p.write_bytes(b'changed')
        with self.assertRaises(MaterialPathError):resolve_material_file(row['old_path'],repo_root=self.root)
        p.unlink();outside=self.root/'outside';outside.write_bytes(b'same bytes');p.symlink_to(outside)
        with self.assertRaises(MaterialPathError):resolve_material_file(row['old_path'],repo_root=self.root)

    def test_same_bytes_do_not_merge_rights_or_accept_wrong_record(self):
        from apps.ire.graph import Document, Group, Image
        from apps.ire import materials_placement as mp
        row=self.rows[0];other=self.rows[1]
        node=Image(name='source',src=str(self.root/row['old_path']),x=0,y=0,w=1,h=1)
        doc=Document(page_w=10,page_h=10,root=Group(name='root',children=[node]))
        doc.metadata={mp.SCHEMA:{'placements':[{'node':'source','relative_path':other['old_path'],'sha256':other['sha256'],'tier':'PRODUCTION'}]}}
        with patch.object(mp,'REPO_ROOT',self.root):
            self.assertEqual(mp.resolve_placements(doc)['rows'][0]['resolution'],mp.REFUSED_IDENTITY_MISMATCH)
            with self.assertRaises(mp.PlacementRefused):mp.refuse_or_skip(doc)
            doc.metadata[mp.SCHEMA]['placements'][0]['relative_path']=row['old_path']
            doc.metadata[mp.SCHEMA]['placements'][0]['tier']='REFERENCE'
            self.assertEqual(mp.resolve_placements(doc)['rows'][0]['resolution'],mp.REFUSED_REFERENCE_ASSET)

    # --- Day 6 attempt-2 cause: the volume's identity rule versus byte-exact manifest paths ---------------------

    def _font_rows(self):
        """A legacy ``Fonts/`` folder and a planned ``fonts/`` tree: one entry on a case-insensitive volume."""
        old=self.root/'materials/Fonts/Orig/a.ttf';old.parent.mkdir(parents=True);old.write_bytes(b'font bytes');st=old.stat()
        digest=hashlib.sha256(b'font bytes').hexdigest()
        return [{'old_path':'materials/Fonts/Orig/a.ttf','new_path':f'materials/fonts/cairo/fonts_cairo_a_{digest[:16]}.ttf',
                 'sha256':digest,'size_bytes':st.st_size,'mtime_ns':st.st_mtime_ns}]

    def _needs_case_insensitive_volume(self):
        if not volume_case_insensitive(self.root):self.skipTest('fixture needs a case-insensitive volume')

    def test_negative_control_reproduces_attempt_two_merged_directory(self):
        self._needs_case_insensitive_volume();rows=self.rows+self._font_rows()
        for row in rows:
            new=self.root/row['new_path'];new.parent.mkdir(parents=True,exist_ok=True);os.rename(self.root/row['old_path'],new)
        names=os.listdir(self.root/'materials');self.assertIn('Fonts',names);self.assertNotIn('fonts',names)
        proof=disk_proof(self.root,rows,'new_path')
        self.assertTrue(proof['sha_multiset_matches']);self.assertTrue(proof['sha_set_matches']);self.assertEqual(proof['actual_count'],3)
        self.assertFalse(proof['path_set_matches']);self.assertFalse(proof['every_manifest_row_exact']);self.assertFalse(proof['passed'])

    def test_diagnose_predicts_the_merge_and_names_the_byte(self):
        self._needs_case_insensitive_volume();rows=self.rows+self._font_rows()
        report=diagnose(self.root,rows)
        self.assertEqual(report['predicted_path_mismatches'],1);self.assertEqual(report['by_top_folder'],{'fonts':1})
        item=report['first_20'][0]
        self.assertEqual(item['first_differing_byte_offset'],len('materials/'));self.assertEqual((item['expected_byte'],item['observed_byte']),('0x66','0x46'))
        self.assertEqual(report['directory_spelling_plan'],[{'from':'materials/Fonts','to':'materials/fonts'}])
        self.assertEqual(spelling_plan(self.root,self.rows),[])

    def test_case_collision_is_respelled_proof_byte_exact_and_reversed(self):
        self._needs_case_insensitive_volume();rows=self.rows+self._font_rows()
        report=apply(self.root,rows,self.evidence)
        self.assertEqual(report['state'],'VERIFIED');self.assertTrue(report['after']['passed']);self.assertTrue(report['after']['path_set_matches'])
        self.assertEqual(report['directory_spelling'],[{'from':'materials/Fonts','to':'materials/fonts'}])
        names=os.listdir(self.root/'materials');self.assertIn('fonts',names);self.assertNotIn('Fonts',names)
        self.assertTrue((self.root/'materials/fonts/Orig').is_dir());self.assertEqual(list((self.root/'materials/fonts/Orig').iterdir()),[])
        self.assertEqual(json.loads((self.evidence/'directory-spelling.json').read_text()),report['directory_spelling'])
        journal=[json.loads(x) for x in (self.evidence/'move-journal.jsonl').read_text().splitlines()]
        self.assertEqual([x for x in journal if 'dir_intent' in x],[{'dir_intent':'materials/Fonts','to':'materials/fonts'}])
        self.assertEqual(diagnose(self.root,rows)['predicted_path_mismatches'],0)
        back=rollback(self.root,rows,self.evidence/'move-journal.jsonl')
        self.assertTrue(back['passed']);self.assertEqual(back['directory_spelling_restored'],[{'from':'materials/Fonts','to':'materials/fonts'}])
        names=os.listdir(self.root/'materials');self.assertIn('Fonts',names);self.assertNotIn('fonts',names)
        self.assertTrue((self.root/'materials/Fonts/Orig/a.ttf').is_file())

    def test_partial_failure_restores_directory_spelling(self):
        self._needs_case_insensitive_volume();rows=self.rows+self._font_rows()
        with self.assertRaisesRegex(RuntimeError,'Injected'):
            apply(self.root,rows,self.evidence,fail_after=1)
        proof=json.loads((self.evidence/'migration-proof.json').read_text())
        self.assertTrue(proof['rollback_triggered']);self.assertTrue(proof['rollback']['passed'])
        self.assertTrue(disk_proof(self.root,rows,'old_path')['passed']);self.assertIn('Fonts',os.listdir(self.root/'materials'))

    def test_spelling_occupied_by_a_file_refuses_before_any_move(self):
        self._needs_case_insensitive_volume()
        old=self.root/'materials/ALL..MOCKUP/x.psd';old.parent.mkdir(parents=True);old.write_bytes(b'psd');st=old.stat()
        digest=hashlib.sha256(b'psd').hexdigest()
        rows=self.rows+[{'old_path':'materials/ALL..MOCKUP/x.psd','new_path':f'materials/mockups/unclassified/mockups_unclassified_x_{digest[:16]}.psd',
                         'sha256':digest,'size_bytes':st.st_size,'mtime_ns':st.st_mtime_ns}]
        (self.root/'materials/Mockups').write_bytes(b'a file where the kind folder must go')
        with self.assertRaisesRegex(RuntimeError,'non-directory'):
            apply(self.root,rows,self.evidence)
        self.assertTrue(all((self.root/r['old_path']).is_file() for r in rows))
        self.assertEqual((self.root/'materials/Mockups').read_bytes(),b'a file where the kind folder must go')

    def test_nfd_arabic_filename_destination_is_byte_exact_and_form_preserved(self):
        name=unicodedata.normalize('NFD','سيروم-صن-é.pdf');self.assertNotEqual(name,unicodedata.normalize('NFC',name))
        old=self.root/'materials/DOWNLOADE 2026'/name;old.parent.mkdir(parents=True);old.write_bytes(b'arabic named bytes');st=old.stat()
        digest=hashlib.sha256(b'arabic named bytes').hexdigest()
        rows=self.rows+[{'old_path':f'materials/DOWNLOADE 2026/{name}','new_path':f'materials/unknown/unclassified/{digest[:16]}/{name}',
                         'sha256':digest,'size_bytes':st.st_size,'mtime_ns':st.st_mtime_ns}]
        self.assertEqual(diagnose(self.root,rows)['non_nfc_new_paths'],1)
        report=apply(self.root,rows,self.evidence)
        self.assertTrue(report['after']['passed']);self.assertTrue(report['after']['every_manifest_row_exact'])
        self.assertEqual(os.listdir(self.root/'materials/unknown/unclassified'/digest[:16]),[name])
        self.assertTrue(rollback(self.root,rows,self.evidence/'move-journal.jsonl')['passed'])
        self.assertEqual(os.listdir(self.root/'materials/DOWNLOADE 2026'),[name])



if __name__=='__main__':main()
