"""Round 3 through the chain at $0, on a copy (never the round's own folder): the die drawn, the template sheet, the
stand faces cut from a stand-in painting (round 3's two real paintings were lost to the network; the stand-in is
labelled as such everywhere), the bottle and cap faces round 3 already drew, and Make my files' own path —
round_files_job.build_outputs (the writer, the previews, the built drawing) and counter_display_files.write_all (die.pdf
with the stand's raster, DXF, CF2, the assembly drawing) — then a zip. Paid steps not run: research, the boards, the
designs, the flat painting, the product faces' edits, the eye.

    bbrose_design_os/venv/bin/python docs/consolidation/chain_run.py --out <folder> [--native] [--live] [--record <name>.json]

writes <folder>/round3/files/… and the record (every output's SHA-256 and read-back) to engines/runs/<name>.json."""
import hashlib
import json
import os
import shutil
import socket
import sys
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
APP = REPO / 'bbrose_design_os'
if '--app' in sys.argv:                      # another checkout's code (the before run, on the commit before any move)
    APP = Path(sys.argv[sys.argv.index('--app') + 1]).resolve()
ROUND3 = REPO / 'docs/rounds/lip-gloss-product-and-counter-stand-9634b86f91'
RUNS = Path(__file__).resolve().parent / 'engines' / 'runs'

for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'WEB_SEARCH_API_KEY', 'TAVILY_API_KEY'):
    os.environ[key] = ''
_connect = socket.socket.connect


def _guarded(self, address, *args, **kwargs):
    host = address[0] if isinstance(address, tuple) else address
    if self.family == socket.AF_UNIX or (isinstance(host, str) and (host.startswith('127.') or host in ('localhost', '::1'))):
        return _connect(self, address, *args, **kwargs)
    raise ConnectionRefusedError('chain run: outbound connection refused (%r)' % (address,))


socket.socket.connect = _guarded


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def content_sha(path):
    """An .ai's SHA-256 with the one field that changes on every write blanked: the trailer's random /ID pair."""
    import re
    return hashlib.sha256(re.sub(rb'/ID\[<[0-9A-F]+><[0-9A-F]+>\]', b'/ID[]', Path(path).read_bytes())).hexdigest()


def stand_in_painting(template_png, masks, dest, *, drift=(3, 2)):
    """The stand-in (as probes.stand_in_painting): each printed face's own pixels coloured and textured, the whole
    picture moved by ``drift`` (rows, columns)."""
    import numpy as np
    from PIL import Image
    template = np.asarray(Image.open(template_png).convert('RGB'))
    raw = template.copy()
    owner = masks['owner']
    colours = [(28, 40, 92), (186, 58, 74), (201, 164, 92), (90, 120, 60), (60, 90, 160), (140, 60, 120), (220, 120, 40)]
    rows = (np.arange(owner.shape[0]) % 9 == 0)[:, None] | (np.arange(owner.shape[1]) % 13 == 0)[None, :]
    for index, _name in enumerate(masks['names']):
        face = owner == index + 1
        raw[face] = colours[index % len(colours)]
        raw[face & rows] = (240, 230, 200)
    Image.fromarray(np.roll(raw, drift, axis=(0, 1))).save(dest)
    return dest


def main(argv):
    out = Path(argv[argv.index('--out') + 1])
    native = '--native' in argv
    name = argv[argv.index('--record') + 1] if '--record' in argv else 'chain-run'
    sys.path.insert(0, str(APP))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    os.chdir(APP)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django
    django.setup()
    import numpy as np
    from PIL import Image
    from apps.dielines.exporters import counter_display_files as cdf
    from apps.pipeline.services import round_files_faces as faces
    from apps.pipeline.services.round_files_gate import build_outputs, execution_brief
    from apps.dielines.geometry.counter_display import solve_stand

    start = time.time()
    root = out / 'round3' / 'files'
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    for rel in ('inputs.json', 'stand.json', 'inspection.json', 'source.png'):
        shutil.copy2(ROUND3 / 'files' / rel, root / rel)
    record = {'schema': 'consolidation_chain_run/1', 'native': native, 'paid_steps_not_run': [
        'research (Tavily, one Claude call)', 'the three boards', 'the three designs', 'the flat painting (a $0 stand-in '
        'instead: round 3\'s two real paintings were lost to the network)', 'the bottle and cap edits (round 3\'s own '
        'drawn faces used)', 'the eye']}

    # the brief as the files build reads it: the frozen brief, the round's committed Arabic shade names, the estimates
    inputs = json.loads((root / 'inputs.json').read_text())
    brief = inputs['brief']
    names = json.loads((ROUND3 / 'files-copy.json').read_text()).get('arabic_shade_names', {})
    for shade in brief['shades']:
        if not shade.get('name_arabic') and names.get(shade['name']):
            shade['name_arabic'] = names[shade['name']]
    brief = execution_brief(brief)

    # 1. the die: round 3's committed die, solved again; and from the brief alone (the owner's choice between them)
    geometry = json.loads((root / 'stand.json').read_text())
    again = solve_stand(brief, json.loads((root / 'inspection.json').read_text()))
    alone = solve_stand(brief, None)
    record['die'] = {'committed_equals_solved_again': json.dumps(again['record'], sort_keys=True) ==
                     json.dumps(geometry['record'], sort_keys=True),
                     'height_mm': geometry['dimensions_mm']['height'], 'header_mm': geometry['header_mm'],
                     'from_brief_alone': {'height_mm': alone['dimensions_mm']['height'], 'header_mm': alone['header_mm']},
                     'record_sha256': hashlib.sha256(json.dumps(geometry['record'], sort_keys=True).encode()).hexdigest()}

    # 2. the template sheet
    flat = root / 'flat'
    setup = faces.flat_setup(geometry, flat)
    record['template'] = {'frame': setup['frame']['size'], 'dpi_at_1to1': setup['frame']['dpi_at_1to1'],
                          'template_sha256': sha(flat / 'template.png'), 'sheet_sha256': sha(flat / 'sheet.png'),
                          'same_as_round3': (sha(flat / 'template.png') == sha(ROUND3 / 'files/flat/template.png'))
                          if (ROUND3 / 'files/flat/template.png').exists() else None}   # None: round 3 holds none (restand moved it)

    live = '--live' in argv
    die = faces.die_of(geometry)
    masks = cdf.flat_masks(die, setup['frame'])
    if live:
        # --live (the owner's goal of 2026-10-29, §3): round 3's own current drawings, as its build holds them now —
        # read, never written; Make my files' outputs written into the copy only; nothing accepted anywhere
        from apps.pipeline.models import RoundMaster
        from apps.pipeline.services import round_files_gate as gate
        build = RoundMaster.objects.get(round__slug=ROUND3.name)
        real = gate.root(build)
        geometry = json.loads((real / 'stand.json').read_text())
        for rel in ('stand.json', 'inspection.json', 'source.png'):
            shutil.copy2(real / rel, root / rel)
        die = faces.die_of(geometry)
        drawn = {}
        for key, row in gate.board(build).items():
            entry = gate.current(row)
            drawn[key] = json.loads((real / entry['record']).read_text())
        record.update(live=True, paid_steps_not_run=['none: the drawings are round 3\'s own, made by its paid run'],
                      die={'height_mm': geometry['dimensions_mm']['height'], 'header_mm': geometry['header_mm'],
                           'sightline_revision': geometry.get('sightline_revision'),
                           'sightlines_passed': geometry['sightlines']['passed'],
                           'header_clear': geometry['sightlines'].get('header_clear'),
                           'record_sha256': hashlib.sha256(json.dumps(geometry['record'], sort_keys=True).encode()).hexdigest()},
                      faces_state={key: {'state': row['state'], 'drawing': row.get('drawing'),
                                         'source': (gate.current(row) or {}).get('source')}
                                   for key, row in gate.board(build).items()})
        record['faces'] = {key: {'sha256': sha(value['face'])[:16], 'size_px': list(Image.open(value['face']).size),
                                 'native_ppi': value.get('native_ppi')} for key, value in drawn.items()}
        return make_files(record, root, brief, inputs, native, drawn, geometry, die, name, start)

    # 3. the stand faces, cut from a stand-in painting settled by the die
    raw = stand_in_painting(flat / 'template.png', masks, root / 'stand-in-raw.png')
    (flat / 'paintings' / '1').mkdir(parents=True)
    painting = dict(faces.settle_flat(raw, flat, flat / 'paintings' / '1', geometry), n=1)
    proof = painting['proof']
    record['die_match_proof'] = {'stand_in': True, 'drift_applied_rows_cols': [3, 2],
                                 'best_shift_px_xy': proof['registration']['best_shift_px'],
                                 'outside_pixels_differing': proof['outside']['differing_from_template'],
                                 'pdf_readback_mm': {k: v['max_mm'] for k, v in proof['pdf'].items()}}
    drawn = {}
    for key in faces.FACES:
        if faces.stand_face(key):
            faces.flat_face(root, key, 1, painting, geometry)
            drawn[key] = json.loads((faces.drawing_folder(root, key, 1) / 'record.json').read_text())

    # 4. the bottle and cap, as round 3 drew them (its records, the face pictures copied)
    for key in ('bottle', 'cap'):
        (root / 'faces' / key).mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROUND3 / 'files/faces' / key / 'face.png', root / 'faces' / key / 'face.png')
        face = json.loads((ROUND3 / 'files/faces' / key / 'record.json').read_text())
        face['face'] = str(root / 'faces' / key / 'face.png')
        drawn[key] = face
    record['faces'] = {key: {'sha256': sha(value['face'])[:16], 'size_px': list(Image.open(value['face']).size)}
                       for key, value in drawn.items()}

    return make_files(record, root, brief, inputs, native, drawn, geometry, die, name, start)


def make_files(record, root, brief, inputs, native, drawn, geometry, die, name, start):
    from apps.dielines.exporters import counter_display_files as cdf
    from apps.pipeline.services.round_files_gate import build_outputs
    # 5. Make my files: the writer, the previews, the drawing; the die's files with the stand's raster; the zip
    ctx = SimpleNamespace(root=root, brief=brief, native=native,
                          build=SimpleNamespace(inputs={'picture_sha256': sha(root / 'source.png'), 'pick': inputs['pick']}))
    outputs = build_outputs(ctx, drawn, 1)
    stand_spec = next(item for item in outputs['specs'] if item['id'] == 'stand')
    stand_art = [stand_spec['die_artwork']] if 'die_artwork' in stand_spec else stand_spec['artwork']
    die_folder = root / 'revisions' / '1' / 'die'
    die_files = cdf.write_all(geometry['record'], die_folder, artwork=stand_art[0])
    from apps.pipeline.services.round_files_export import read_back_ai
    members = []
    record['objects'] = {}
    for item in outputs['objects']:
        back = read_back_ai(item['ai'], item['type'], item['elements'])
        record['objects'][item['id']] = {
            'ai': Path(item['ai']).name, 'ai_sha256': sha(item['ai'])[:16],
            'ai_content_sha256': content_sha(item['ai'])[:16], 'png_sha256': sha(item['png'])[:16],
            'checks': len(back.get('checks', {})), 'checks_failed': [k for k, v in back.get('checks', {}).items() if v is False],
            'native': None if not isinstance(item.get('native'), dict) or not item['native'].get('requested') else {
                'saved': item['native']['save_execution']['saved'],
                'reopened': item['native']['reopen_execution'].get('reopened'),
                'save_checks_failed': [k for k, v in item['native'].get('checks', {}).items() if v is False],
                'reopen_checks_failed': [k for k, v in item['native'].get('reopen_checks', {}).items() if v is False],
                'checks': [len(item['native'].get('checks', {})), len(item['native'].get('reopen_checks', {}))]}}
        members += [Path(item['ai']), Path(item['png'])]
    members.append(root / outputs['drawing'])
    members += [die_folder / n for n in die_files['files']]
    with zipfile.ZipFile(root / 'files.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in members:
            archive.write(path, path.name)
    readback = cdf.pdf_readback(die_folder / 'die.pdf', die, geometry['record'], stand_art[0]['box_mm'])
    record['die_files'] = {'files': die_files['files'], 'readback_mm': {k: v.get('max_mm') for k, v in readback.items()},
                           'nest_best': die_files['nest']['best']}
    record['zip'] = {'members': sorted(p.name for p in members), 'count': len(members)}
    record['views'] = sorted(outputs['views'])
    record['drawing'] = outputs['drawing']
    record['seconds'] = round(time.time() - start, 1)
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / (name + '.json')).write_text(json.dumps(record, indent=1, ensure_ascii=False, default=str) + '\n')
    print(json.dumps({k: record.get(k) for k in ('die', 'template', 'die_match_proof', 'objects', 'die_files', 'zip', 'seconds')},
                     ensure_ascii=False, default=str)[:3000])


if __name__ == '__main__':
    main(sys.argv[1:])
