"""Every working stand template's proof set, for the owner to read and to cut (part 2, 2026-10-31), at $0: the die's files, its fold-up,
its assembly sheet, its 1:1 PDF, its nest and its report, into docs/research/stands/templates/<type>/; with --illustrator, each die.ai also
drawn in Illustrator by the file's law, saved, opened again and its layers read back (Illustrator itself is never quit: it may be the owner's).

    venv/bin/python tools/stand_family_proofs.py [--illustrator]"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django  # noqa: E402

django.setup()
from apps.dielines.exporters import counter_display_files as files, stand_sheets  # noqa: E402
from apps.dielines.geometry import stand_templates as templates  # noqa: E402

GLOSS = {'width_mm': 15.0, 'depth_mm': 15.0, 'height_mm': 100.0, 'cap_mm': 30.0}
#: the lip gloss on each type, at the owner's width and depth where the type allows; round 4 itself is in its own folder
CASES = {'counter_tray_header': (3, 4, {'width_mm': 110.0, 'depth_mm': 85.0, 'height_mm': 160.0}), 'stepped_tiered': (3, 4, {'width_mm': 110.0, 'depth_mm': 86.0}),
         'lid_header_tray': (3, 4, {'width_mm': 110.0, 'depth_mm': 85.0}), 'slanted_front': (2, 4, {'width_mm': 110.0}), 'tester_unit': (1, 4, {'width_mm': 110.0}),
         'flat_tray_testers': (3, 4, {'width_mm': 110.0, 'depth_mm': 85.0, 'height_mm': 160.0})}
OUT = Path(__file__).resolve().parents[2] / 'docs/research/stands/templates'
def main():
    summary = {}
    for name, (rows, columns, envelope) in CASES.items():
        record = templates.solve(name, product=GLOSS, rows=rows, columns=columns, envelope=envelope)
        folder = OUT / name
        folder.mkdir(parents=True, exist_ok=True)
        made = files.write_template(templates.build_die(record), record, folder, native='--illustrator' in sys.argv)
        # New design's card for the type: its three-quarter line drawing
        cards = Path(__file__).resolve().parents[1] / 'static/img/stands'
        cards.mkdir(parents=True, exist_ok=True)
        (cards / (name + '.svg')).write_text(stand_sheets.type_svg(record, templates.build_die(record)))
        (folder / 'report.json').write_text(json.dumps(made, indent=1, ensure_ascii=False, default=str))
        report = made['qualification']
        row = {'passed': report['passed'], 'closed_mm': report['fold']['dimensions']['closed_mm'], 'changes': record.get('changes', []), 'rise_mm': record['geometry'].get('rise_mm'),
               'joints': len(report['fold']['joints']['joints']), 'locks': report['fold']['locks']['count'], 'collisions': len(report['fold']['collisions']),
               'fit_clearance_mm': report['fold']['fit']['clearance_mm'], 'least_band_mm': {('%d/%d' % (e['eye_mm']['in_front'], e['eye_mm']['above_counter'])): min(p['top_band_mm'] for p in e['products']) for e in report['sightlines']['eyes']},
               'bar_mm': report['sightlines']['face_bar_mm'], 'header_seen': [e['header']['seen_share'] for e in report['sightlines']['eyes']],
               'nest': {key: made['nest']['best'][key] for key in ('sheet_mm', 'sets', 'yield')}, 'board_mm2': made['nest']['board_area_mm2'], 'tiles': made['cut_and_fold']['tiles'],
               'along_grain': report['grain']['along_grain'], 'tip_deg': report['strength']['tip']['tips_after_deg'], 'open': {key: value['opens'] for key, value in made['open_check']['files'].items()},
               'glue': record['production']['glue'], 'steps': len(made['assembly_sheet']['steps'])}
        row['ai'] = {key: made['ai'].get(key) for key in ('format', 'native', 'read_back', 'why')}
        summary[name] = row
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    for name, row in summary.items():
        print(name, 'PASS' if row['passed'] else 'FAIL', row['closed_mm'], 'locks', row['locks'], 'joints', row['joints'], 'nest', row['nest'], row['ai']['native'], str(row['ai']['read_back'])[:170])


if __name__ == '__main__':
    main()
