"""Day 7 §6: mockups without Photoshop (not installed on this machine: `ls /Applications` carries none). The artwork is warped
by perspective onto each mockup's smart-object quad (the census's transform_box, from the PSD's placed-layer record) and
composited over the PSD's own flattened composite — "approximate placement": the smart object's own warp, shading and blend
effects are not reproduced. Before/after pairs and a record under docs/audit/day-7/mockups/. Nothing under materials/ is written.
"""
from pathlib import Path
import datetime, hashlib, json, re
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from . import fidelity_assets as fa

ROOT = fa.ROOT
OUT = ROOT / 'docs/audit/day-7/mockups'
CENSUS = ROOT / 'docs/audit/day-6/library/mockups-census.json'
BOTTLE_ART = ROOT / 'docs/audit/day-6/bottle/revision-4/artwork.png'
HEADER_ART = ROOT / 'docs/audit/day-6/stand/surfaces-r2/header.front/artwork.png'
WORK_LONG_EDGE = 2000; OUT_LONG_EDGE = 1600
LABEL = 'approximate placement — perspective warp onto the smart-object quad over the PSD composite; Photoshop not installed'
SCENE = re.compile(r'counter|table|scene|shelf|vanity|bathroom|marble|podium', re.I)


def census():
    return json.loads(CENSUS.read_text(encoding='utf-8'))


PLACEHOLDER = re.compile(r'place your design|your design|design here|double click|edit here|artwork|label|logo|front', re.I)
MIN_SHARE, MAX_SHARE = 0.01, 0.45


def quads(entry, kind=None):
    """The smart-object quads of one census file: ``(layer, [(x, y) × 4], share)`` where the record carries a transform
    box; a quad covering less than 1 % or more than 45 % of the document is a background or a scene, never a label."""
    out = []
    w, h = entry.get('document_pixels') or (0, 0)
    for layer in entry.get('layers') or []:
        so = layer.get('smart_object') or {}
        box = so.get('transform_box')
        if layer.get('kind') == 'smartobject' and box and len(box) == 8 and layer.get('visible', True) and w and h:
            pts = [(box[i], box[i + 1]) for i in range(0, 8, 2)]; share = area(pts) / (w * h)
            inside = all(-0.02 * w <= x <= 1.02 * w and -0.02 * h <= y <= 1.02 * h for x, y in pts)
            if MIN_SHARE <= share <= MAX_SHARE and inside:          # a quad leaving the frame is a cut-off object, never a label
                out.append((layer, pts, share))
    return out


def label_rank(layer, kind):
    """Smaller is better: a layer the census fitted to ``kind`` first, then one named as a placeholder, then the rest."""
    words = (layer.get('path') or '') + ' ' + (layer.get('name') or '')
    return (0 if kind in (layer.get('fit_candidates') or []) else 1, 0 if PLACEHOLDER.search(words) else 1)


def area(pts):
    x = np.array([p[0] for p in pts]); y = np.array([p[1] for p in pts])
    return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


def candidates(kind, scene=False):
    """Census files fit for ``kind`` whose largest smart-object quad is biggest relative to the document, deterministic; with
    ``scene`` only files whose layer names or path speak of a counter, table, shelf or scene."""
    rows = []
    for entry in census()['files']:
        if kind not in (entry.get('fit_candidates') or []):
            continue
        if scene and not SCENE.search(json.dumps([l.get('name') for l in entry.get('layers') or []]) + entry['source_path']):
            continue
        qs = quads(entry, kind)
        if not qs:
            continue
        layer, pts, share = min(qs, key=lambda q: (label_rank(q[0], kind), -q[2]))
        rows.append((share, entry, layer, pts, label_rank(layer, kind)))
    rows.sort(key=lambda r: (r[4], -r[0], r[1]['source_path']))
    return [(share, entry, layer, pts) for share, entry, layer, pts, _rank in rows]


def homography(src, dst):
    """Coefficients for PIL's PERSPECTIVE transform mapping OUTPUT points (dst quad) to INPUT points (src rect)."""
    A, b = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
    return np.linalg.solve(np.array(A, dtype=float), np.array(b, dtype=float))


def compose(entry, layer, pts, artwork_path):
    from apps.ire.materials_paths import resolve_material_file
    psd = resolve_material_file(entry['source_path'], repo_root=ROOT, expected_sha=entry['sha256'])
    with Image.open(psd) as im:
        im.load(); composite = im.convert('RGBA')
    probe = np.asarray(composite.convert('L').resize((64, 64)))
    if probe.std() < 8 or np.percentile(probe, 95) < 24:
        raise ValueError('the PSD carries no usable flattened composite (dark or uniform image: mean %.1f, std %.1f)' % (probe.mean(), probe.std()))
    if np.asarray(composite)[..., 3].max() == 0:
        composite.putalpha(255)       # a merged image whose transparency channel is empty is opaque (resizing would premultiply it away)
    w, h = composite.size; s = min(1.0, WORK_LONG_EDGE / max(w, h))
    if s < 1.0:
        composite = composite.resize((round(w * s), round(h * s)), Image.Resampling.LANCZOS)
    quad = [(x * s, y * s) for x, y in pts]
    art = Image.open(artwork_path).convert('RGBA'); aw, ah = art.size
    coeffs = homography([(0, 0), (aw, 0), (aw, ah), (0, ah)], quad)
    warped = art.transform(composite.size, Image.Transform.PERSPECTIVE, tuple(coeffs), Image.Resampling.BICUBIC)
    after = Image.alpha_composite(composite, warped)
    return composite, after, quad, (aw, ah)


def fit(im):
    im = im.convert('RGB')
    if max(im.size) > OUT_LONG_EDGE:
        im.thumbnail((OUT_LONG_EDGE, OUT_LONG_EDGE), Image.Resampling.LANCZOS)
    return im


def label(im, words):
    im = im.copy(); d = ImageDraw.Draw(im); font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 22)
    d.rectangle([0, im.height - 34, im.width, im.height], fill=(30, 25, 20)); d.text((10, im.height - 30), words[:150], font=font, fill=(250, 247, 243)); return im


def build(plan=(('bottle', 3, False), ('carton', 2, False), ('bottle', 1, True))):
    """Three bottle, two carton and one countertop mockup (a bottle in a scene), each a before/after pair labelled
    approximate placement; the bottle's revision-4 front artwork, D1's header for the cartons."""
    OUT.mkdir(parents=True, exist_ok=True); rows = []; used = set()
    for kind, n, scene in plan:
        art = HEADER_ART if kind == 'carton' else BOTTLE_ART
        taken = 0
        for ratio, entry, layer, pts in candidates(kind, scene=scene):
            if entry['sha256'] in used or taken >= n:
                continue
            slug = ('countertop' if scene else kind) + '-%d' % (taken + 1)
            try:
                before, after, quad, art_size = compose(entry, layer, pts, art)
            except Exception as exc:    # noqa: BLE001 — a mockup whose composite will not open is recorded and the next candidate taken
                rows.append({'slug': slug, 'source_path': entry['source_path'], 'sha256': entry['sha256'], 'skipped': type(exc).__name__ + ': ' + str(exc)[:120]}); continue
            fit(before).save(OUT / (slug + '-before.png')); label(fit(after), slug + ' · ' + LABEL).save(OUT / (slug + '-after.png'))
            rows.append({'slug': slug, 'kind': kind, 'scene': scene, 'source_path': entry['source_path'], 'sha256': entry['sha256'], 'document_px': entry['document_pixels'],
                         'smart_object_layer': layer.get('path'), 'quad_px': [[round(x, 1), round(y, 1)] for x, y in pts], 'quad_share_of_document': round(ratio, 4),
                         'artwork': str(art.relative_to(ROOT)), 'artwork_sha256': hashlib.sha256(art.read_bytes()).hexdigest(), 'artwork_px': list(art_size),
                         'before': slug + '-before.png', 'after': slug + '-after.png', 'placement': 'approximate', 'method': LABEL}); used.add(entry['sha256']); taken += 1
        if taken < n:
            rows.append({'slug': kind + ('-scene' if scene else ''), 'shortfall': n - taken, 'note': 'fewer usable candidates than asked'})
    made = [r for r in rows if r.get('after')]
    sheet(made)
    record = {'schema': 'day7_mockups/1', 'photoshop': 'not installed (ls /Applications: none); smart objects not driven', 'method': LABEL, 'made': len(made),
              'asked': sum(n for _k, n, _s in plan), 'rows': rows, 'sheet': 'mockups-sheet.png', 'built_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    (OUT / 'mockups.json').write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n')
    return {k: v for k, v in record.items() if k != 'rows'}


def sheet(made):
    tiles = []
    for r in made:
        b = Image.open(OUT / r['before']).convert('RGB'); a = Image.open(OUT / r['after']).convert('RGB')
        for im in (b, a):
            im.thumbnail((520, 520))
        tile = Image.new('RGB', (1080, 560), (250, 247, 243)); tile.paste(b, (10, 10)); tile.paste(a, (550, 10))
        d = ImageDraw.Draw(tile); d.text((10, 538), r['slug'] + ' · before / after · approximate placement', font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 18), fill=(60, 50, 40))
        tiles.append(tile)
    cols = 2; rows_n = -(-len(tiles) // cols) if tiles else 1
    out = Image.new('RGB', (1080 * cols + 20, 560 * rows_n + 60), (252, 250, 247)); d = ImageDraw.Draw(out)
    d.text((10, 14), 'Day 7 §6 — mockups by perspective warp (Photoshop not installed) · bottle revision 4 front · D1 header', font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 26), fill=(60, 50, 40))
    for i, t in enumerate(tiles):
        out.paste(t, (10 + (i % cols) * 1080, 60 + (i // cols) * 560))
    out.save(OUT / 'mockups-sheet.png')


if __name__ == '__main__':
    print(json.dumps(build(), ensure_ascii=False))
