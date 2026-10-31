"""Metadata-only PSD census; no composites, Photoshop, network or paid calls."""
from pathlib import Path
from collections import Counter
import json, os, sys
from psd_tools import PSDImage
from psd_tools.constants import Resource

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/audit/day-6/library'


def run():
    os.nice(10)
    if not (OUT / 'fonts-census.json').exists():
        raise RuntimeError('Font evidence must precede PSD census')
    rows = [json.loads(x) for x in (ROOT / 'var/design_intelligence/audits/dip0/inventory/inventory-2026-10-19.jsonl').read_text().splitlines()]
    rows = [r for r in rows if r['extension'] in ('.psd', '.psb')]
    results = []; cache = {}
    for i, row in enumerate(rows):
        h = row['sha256']
        if h in cache:
            data = dict(cache[h], source_path=row['relative_path'])
        else:
            data = {'source_path': row['relative_path'], 'sha256': h, 'layers': [], 'fit_candidates': [], 'parsed': False}
            try:
                psd = PSDImage.open(ROOT / row['relative_path'])
                resolution = psd.image_resources.get_data(Resource.RESOLUTION_INFO)
                raw={k:getattr(resolution,k,None) for k in ('horizontal','vertical','horizontal_unit','vertical_unit')}
                data.update(document_pixels=[psd.width,psd.height],resolution_raw=raw,
                            document_ppi={k:raw[k]/65536 if raw[k] is not None else None for k in ('horizontal','vertical')},
                            resolution_definition='PSD16.16 fixed-point resolution divided by65536; horizontal/vertical units retained in raw metadata')
                def visit(group, prefix=''):
                    for layer in group:
                        path = prefix + '/' + layer.name
                        item = {'name': layer.name, 'path': path, 'kind': layer.kind, 'bbox_px': list(layer.bbox),
                                'pixel_size': [layer.width, layer.height], 'visible': layer.visible, 'smart_object': None}
                        if layer.kind == 'smartobject':
                            try:
                                smart = layer.smart_object
                                item['smart_object'] = {k: getattr(smart, k) for k in ('filename', 'kind', 'filetype', 'filesize', 'resolution', 'transform_box')}
                                terms = (path + ' ' + str(smart.filename) + ' ' + row['filename']).casefold()
                                item['fit_candidates'] = [kind for kind, keys in {'bottle': ('bottle', 'serum', 'flacon'), 'carton': ('box', 'carton', 'package'), 'tube': ('tube',), 'stand': ('stand', 'display')}.items() if any(k in terms for k in keys)]
                                item['fit_basis'] = 'Layer/file labels only; placement geometry, perspective and rights need Day7 validation'
                                data['fit_candidates'].extend(item['fit_candidates'])
                            except Exception as exc:
                                item['smart_object_error'] = type(exc).__name__ + ': ' + str(exc)
                        data['layers'].append(item)
                        if layer.is_group():
                            visit(layer, path)
                visit(psd)
                data['parsed'] = True; data['fit_candidates'] = sorted(set(data['fit_candidates']))
                del psd
            except Exception as exc:
                data['error'] = type(exc).__name__ + ': ' + str(exc)
            cache[h] = data
        results.append(data)
        (OUT / 'mockups-progress.json').write_text(json.dumps({'done': i+1, 'total': len(rows), 'last': row['relative_path']}))
        print(json.dumps({'stage': 'psd', 'done': i+1, 'total': len(rows), 'parsed': data['parsed']}), flush=True)
    report = {'schema': 'day6_mockups/1', 'parser': 'psd-tools1.25.0', 'rasterized': False, 'photoshop_launched': False,
              'file_count': len(results), 'unique_contents': len(cache), 'parsed': sum(r['parsed'] for r in results),
              'smart_object_instances': sum(bool(l.get('smart_object')) for r in results for l in r['layers']),
              'candidate_counts': dict(Counter(k for r in results for k in r['fit_candidates'])), 'files': results}
    (OUT / 'mockups-census.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='files'}), flush=True)


if __name__ == '__main__':
    run()
