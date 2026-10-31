"""Day 7 §2: a caption, tags, measured colours, text presence, suitable surfaces and a rights tier for every unique
file of the materials library → docs/audit/day-7/library/materials-index.json.

The 3,867 earlier machine captions (docs/design_intelligence/captions, Day 5 brain run) are reused by content hash.
Files without one are captioned by a vision model from their Day 7 preview, in batches: one reservation per batch under
the owner's `day7/` allowance, settled with the batch's summed usage. Colours are never asked of the model: they are
measured from the preview (ΔE76 ≤ 8 merge, top five, Lab D65 + hex). Fonts are rows from the Day 6 census: no model
call, rights tier = pool, UNVERIFIED and BLOCKED marked excluded (D-D7-1). Nothing under materials/ is written.
"""
from pathlib import Path
import base64, collections, concurrent.futures as cf, datetime, hashlib, io, json, os, re, time
import numpy as np
from PIL import Image
from . import materials_previews as mp

ROOT = mp.ROOT
LIB = ROOT / 'docs/audit/day-7/library'
INDEX = LIB / 'materials-index.json'
PROGRESS = LIB / 'captions-progress.json'
EARLIER = ROOT / 'docs/design_intelligence/captions/captions.jsonl'
RESULTS = ROOT / 'var/design_intelligence/captions/day7'
CENSUS = ROOT / 'docs/audit/day-6/library'
MODEL = 'claude-haiku-4-5'
PREFIX = 'day7/'; CAP_USD = 12.0; OPERATION = 'day7/captions/batch-'
BATCH = int(os.environ.get("DAY7_CAPTION_BATCH", 40)); WORKERS = 4; API_LONG_EDGE = 896; PER_IMAGE_ESTIMATE_USD = 0.0045; MAX_TOKENS = 450
KINDS = ('photo', 'product-render', 'mockup', 'pattern', 'background', 'texture', 'ornament', 'illustration', 'icon', 'logo',
         'typography', 'layout', 'dieline', 'palette', 'font', 'other')
SURFACES = ('bottle-label', 'carton', 'header', 'riser', 'base', 'backdrop', 'pattern-fill', 'ornament-accent', 'mockup-scene', 'specimen')
SYSTEM = "You catalogue a cosmetics packaging studio's design library. Answer with one JSON object only: no prose, no code fences."
PROMPT_VERSION = 2   # v2 (after the fresh-agent re-check of 2026-10-19): exact counts, closures only when visible, boards are layouts, text read with confidence
PROMPT = ("Describe this file's picture for a design library index. Count objects exactly; name a closure or applicator (pump, spray, dropper, wand) only "
          "when it is visible; a board that composes several elements (a logo, type, swatches, a tile) is a layout, not a palette; list text only where "
          "you read it with confidence. Return JSON with exactly these keys:\n"
          "kind: one of " + ", ".join(k for k in KINDS if k != 'font') + "\n"
          "subject: one sentence of at most 25 words saying what the picture shows (objects, scene, style); never guess who owns it\n"
          "tags: 5 to 12 lowercase tags (single words or hyphenated pairs): motifs, style period or movement, material, mood, technique, product type\n"
          "style: 1 to 3 style words (for example art-deco, minimalist, botanical, luxury, playful)\n"
          "text_present: true or false\n"
          "text_seen: up to 8 strings of text legible in the picture, [] if none\n"
          "language: none, latin, arabic or mixed\n"
          "surfaces: zero or more of " + ", ".join(SURFACES) + " — where a packaging designer could use this material\n"
          "confidence: low, medium or high")
STOP = frozenset('the and with for from into onto over under a an of in on at to by is are its this that these those as or '
                 'against featuring showing displayed positioned composition background white black clean simple set'.split())
_WORD = re.compile(r"[a-z][a-z\-]{2,}")
CATEGORY_KIND = {'PATTERN': 'pattern', 'BACKGROUND': 'background', 'MOTIF': 'ornament', 'ICON': 'icon', 'LOGO': 'logo',
                 'COLOR_PALETTE': 'palette'}
FORM_KIND = {'mockup': 'mockup', 'bottle mockup': 'mockup', 'pattern': 'pattern', 'icon set': 'icon', 'icon': 'icon', 'poster': 'layout',
             'photograph': 'photo', 'palette': 'palette', 'logo': 'logo', 'background': 'background', 'texture': 'texture'}
TECHNIQUE_KIND = (('photograph', 'photo'), ('3d render', 'product-render'), ('flat vector', 'illustration'), ('line art', 'illustration'),
                  ('hand-drawn', 'illustration'))
SURFACE_RULE = {'pattern': ['pattern-fill', 'carton', 'backdrop'], 'background': ['backdrop', 'base', 'riser'], 'texture': ['backdrop', 'base', 'riser'],
                'ornament': ['ornament-accent', 'carton', 'header'], 'illustration': ['ornament-accent', 'carton', 'header'],
                'icon': ['ornament-accent', 'bottle-label'], 'mockup': ['mockup-scene'], 'product-render': ['mockup-scene'], 'photo': ['mockup-scene'],
                'layout': ['header', 'riser'], 'logo': ['specimen'], 'typography': ['specimen'], 'font': ['specimen']}


def earlier():
    out = {}
    for line in EARLIER.read_text(encoding='utf-8').splitlines():
        if line.strip():
            r = json.loads(line)
            if r.get('sha256') and r.get('caption'):
                out[r['sha256']] = r
    return out


def nonfont_jobs():
    return [j for j in mp.candidates(mp.rows()) if j['kind'] in ('vector', 'eps', 'psd', 'raster')]


def result_path(sha):
    return RESULTS / (sha + '.json')


def pending(shas=None):
    """Unique non-font files with neither an earlier caption nor a Day 7 result; split by whether a preview exists yet. With
    ``shas`` (a re-caption plan): those files without a Day 7 result, their earlier caption notwithstanding."""
    had = earlier(); ready, waiting = [], []
    for j in nonfont_jobs():
        if shas is not None:
            if j['sha256'] not in shas or result_path(j['sha256']).exists():
                continue
        elif j['sha256'] in had or result_path(j['sha256']).exists():
            continue
        (ready if (mp.OUT / (j['sha256'] + '.png')).exists() else waiting).append(j)
    return ready, waiting


def image_payload(sha):
    with Image.open(mp.OUT / (sha + '.png')) as im:
        im = im.convert('RGBA'); white = Image.new('RGBA', im.size, (255, 255, 255, 255)); im = Image.alpha_composite(white, im).convert('RGB')
        if max(im.size) > API_LONG_EDGE:
            im.thumbnail((API_LONG_EDGE, API_LONG_EDGE), Image.Resampling.LANCZOS)
        buf = io.BytesIO(); im.save(buf, format='JPEG', quality=85, optimize=True)
    return base64.b64encode(buf.getvalue()).decode('ascii'), im.size


def parse(text):
    text = text.strip()
    if text.startswith('```'):
        text = text.strip('`'); text = text[text.find('{'):]
    start, end = text.find('{'), text.rfind('}')
    data = json.loads(text[start:end + 1])
    kind = str(data.get('kind') or 'other').lower().strip()
    tags = [t.lower().strip() for t in (data.get('tags') or []) if isinstance(t, str) and t.strip()]
    surfaces = [s for s in (data.get('surfaces') or []) if s in SURFACES]
    return {'kind': kind if kind in KINDS and kind != 'font' else 'other', 'subject': str(data.get('subject') or '')[:300],
            'tags': list(dict.fromkeys(tags))[:12], 'style': [str(s).lower() for s in (data.get('style') or [])][:3],
            'text_present': bool(data.get('text_present')), 'text_seen': [str(t)[:80] for t in (data.get('text_seen') or [])][:8],
            'language': str(data.get('language') or 'none').lower()[:12], 'surfaces': surfaces,
            'confidence': str(data.get('confidence') or '')[:8], 'kind_raw': str(data.get('kind') or '')[:40]}


def ask(client, job, folder):
    sha = job['sha256']; data, size = image_payload(sha); started = time.time()
    response = client.messages.create(model=MODEL, max_tokens=MAX_TOKENS, system=SYSTEM, messages=[{'role': 'user', 'content': [
        {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': data}}, {'type': 'text', 'text': PROMPT}]}])
    payload = response.model_dump(mode='json'); usage = payload.get('usage') or {}
    (folder / (sha + '.json')).write_text(json.dumps({'provider_request_id': getattr(response, '_request_id', None), 'response': payload}))
    text = ''.join(b.get('text', '') for b in payload.get('content', []) if b.get('type') == 'text')
    record = {'sha256': sha, 'path': job['path'], 'model': payload.get('model') or MODEL, 'prompt_version': PROMPT_VERSION, 'api_image_px': list(size), 'usage': usage,
              'seconds': round(time.time() - started, 2), 'at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    try:
        record['caption'] = parse(text); record['caption_error'] = None
    except (ValueError, TypeError) as exc:
        record['caption'] = None; record['caption_error'] = type(exc).__name__ + ': ' + str(exc)[:120]; record['raw'] = text[:600]
    result_path(sha).write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n')
    return record


def _client():
    import anthropic
    from django.conf import settings
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=2, timeout=90)


def run(max_batches=None, shas=None, operation=OPERATION, progress_path=PROGRESS):
    """Caption the pending files with a preview, one reservation per batch, settled with the batch's summed usage. Stops on
    the owner's allowance (BudgetExceededError) or when nothing is pending; resumable: results are per-file. With ``shas``
    the run re-captions a plan (the fresh-agent check's failing classes) under its own operation prefix and progress file."""
    from .spend_reservation import reserve, settle, _root
    from .cost_ledger import BudgetExceededError
    RESULTS.mkdir(parents=True, exist_ok=True); LIB.mkdir(parents=True, exist_ok=True); PROGRESS_FILE = progress_path
    progress = json.loads(PROGRESS_FILE.read_text()) if PROGRESS_FILE.exists() else {'schema': 'day7_captions/1', 'model': MODEL, 'batches': [], 'plan': len(shas) if shas else None}
    client = _client(); done_batches = 0
    while True:
        ready, waiting = pending(shas)
        if not ready and waiting and not (mp.REPORT.exists() and json.loads(mp.REPORT.read_text()).get('finished_at')):
            print(json.dumps({'waiting_for_previews': len(waiting)}), flush=True); time.sleep(60); continue    # the preview job is still running
        if not ready or (max_batches and done_batches >= max_batches):
            progress['pending_with_preview'] = len(ready); progress['pending_without_preview'] = len(waiting); break
        batch = ready[:BATCH]; number = len(progress['batches']) + 1
        request_hash = hashlib.sha256(json.dumps(sorted(j['sha256'] for j in batch)).encode()).hexdigest()
        try:
            identifier = reserve('anthropic', operation + '%03d' % number, MODEL, len(batch) * PER_IMAGE_ESTIMATE_USD, request_hash,
                                 budget_prefix=PREFIX, prefix_cap=CAP_USD)
        except BudgetExceededError as exc:
            progress['stopped'] = str(exc)[:300]; progress['pending_with_preview'] = len(ready); break
        folder = _root() / 'responses' / identifier; folder.mkdir(parents=True, exist_ok=False)
        records, errors = [], []
        with cf.ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = {pool.submit(ask, client, job, folder): job for job in batch}
            for future in cf.as_completed(futures):
                try:
                    records.append(future.result())
                except Exception as exc:
                    errors.append({'sha256': futures[future]['sha256'], 'error': type(exc).__name__ + ': ' + str(exc)[:200]})
        usage = collections.Counter()
        for r in records:
            for k, v in (r['usage'] or {}).items():
                if isinstance(v, (int, float)): usage[k] += v
        usage = dict(usage) if records else None
        batch_record = {'number': number, 'reservation': identifier, 'files': len(batch), 'captioned': sum(1 for r in records if r['caption']),
                        'parse_failures': sum(1 for r in records if not r['caption']), 'call_failures': errors, 'usage': usage,
                        'estimate_usd': round(len(batch) * PER_IMAGE_ESTIMATE_USD, 4), 'request_hash': request_hash}
        (folder / 'batch.json').write_text(json.dumps(batch_record, ensure_ascii=False, indent=1) + '\n')
        settle(identifier, {'usage': usage} if usage else {}, folder / 'batch.json', provider='anthropic', model=MODEL)
        progress['batches'].append(batch_record); done_batches += 1
        progress['captioned'] = sum(b['captioned'] for b in progress['batches'])
        PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=1) + '\n')
        print(json.dumps({'batch': number, 'captioned': batch_record['captioned'], 'failures': len(errors), 'usage': usage}), flush=True)
    PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=1) + '\n'); return progress


# --- colours ---------------------------------------------------------------------------------------------------------

def srgb_to_lab(rgb):
    rgb = np.asarray(rgb, dtype=float); lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]])
    xyz = lin @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def palette_of(path, colours=5, merge_de=8.0):
    with Image.open(path) as im:
        im = im.convert('RGBA'); im.thumbnail((96, 96)); a = np.asarray(im)
    px = a[..., :3][a[..., 3] >= 128]
    if len(px) < 16:
        return []
    strip = Image.fromarray(px.reshape(-1, 1, 3), 'RGB').quantize(colors=min(12, len(px)), method=Image.Quantize.MEDIANCUT)
    pal = np.array(strip.getpalette()[:36]).reshape(-1, 3); counts = np.bincount(np.asarray(strip).ravel(), minlength=len(pal))
    order = np.argsort(-counts); labs = srgb_to_lab(pal / 255.0); kept = []
    for i in order:
        if counts[i] == 0: continue
        for k in kept:
            if np.linalg.norm(labs[i] - labs[k['i']]) <= merge_de:
                k['count'] += int(counts[i]); break
        else:
            kept.append({'i': int(i), 'count': int(counts[i])})
    total = sum(k['count'] for k in kept)
    return [{'hex': '#%02X%02X%02X' % tuple(int(v) for v in pal[k['i']]), 'lab': [round(float(v), 1) for v in labs[k['i']]],
             'share': round(k['count'] / total, 4)} for k in kept[:colours]]


# --- the index ---------------------------------------------------------------------------------------------------------

def _words(*texts):
    out = []
    for t in texts:
        for w in _WORD.findall(str(t or '').lower()):
            if w not in STOP and w not in out:
                out.append(w)
    return out


def from_earlier(row, category):
    c = row['caption']; form = str(c.get('product_form') or '').lower(); technique = str(c.get('technique') or '').lower()
    kind = CATEGORY_KIND.get(category) or FORM_KIND.get(form) or next((k for key, k in TECHNIQUE_KIND if key in technique), None)
    if kind is None:
        kind = 'product-render' if form and '3d' in technique else 'photo' if 'photo' in technique else 'illustration' if form else 'other'
    tags = _words(c.get('product_form'), c.get('technique'), c.get('finish'), c.get('layout'))[:8]
    for w in _words(c.get('subject')):
        if len(tags) >= 12: break
        if w not in tags: tags.append(w)
    for w in (kind, (category or '').lower().replace('_', '-'), str(c.get('language') or '')):
        if len(tags) < 5 and w and w not in tags and w != 'none': tags.append(w)
    text_seen = [str(t)[:80] for t in (c.get('text_seen') or []) if t][:8]
    return {'kind': kind, 'subject': str(c.get('subject') or '')[:300], 'tags': tags, 'style': _words(c.get('technique'), c.get('finish'))[:3],
            'text_present': bool(text_seen), 'text_seen': text_seen, 'language': str(c.get('language') or 'none')[:12],
            'surfaces': SURFACE_RULE.get(kind, []), 'surfaces_basis': 'rule from kind (earlier caption had no surfaces)',
            'caption_source': 'day5-brain-captions', 'model': row.get('model')}


def font_rows():
    rows = {}
    for pool in ('granted', 'unverified', 'blocked'):
        data = json.loads((CENSUS / ('fonts-%s.json' % pool)).read_text())
        for face in data.get('faces') or []:
            sha = face.get('source_sha256')
            if not sha: continue
            row = rows.get(sha)
            names = face.get('names') or {}; family = names.get('family_typographic') or names.get('family_legacy') or Path(face['source_path']).stem
            if row is None:
                basis = face.get('pool_basis') or {}; ev = basis.get('evidence') or {}
                row = rows[sha] = {'sha256': sha, 'name': Path(face['source_path']).name, 'paths': [face['source_path']], 'extension': face.get('extension'),
                                   'kind': 'font', 'inventory_category': 'FONT', 'family': family, 'faces': [], 'arabic': False, 'variable': False,
                                   'subject': '', 'tags': [], 'style': [], 'colours': [], 'text_present': False, 'text_seen': [], 'language': 'none',
                                   'surfaces': ['specimen'], 'surfaces_basis': 'fonts are set, not placed',
                                   'rights': {'tier': face.get('pool'), 'excluded': face.get('pool') != 'GRANTED',
                                              'basis': ('GRANTED pool: ' + str(basis.get('reason') or '')[:160]) if face.get('pool') == 'GRANTED'
                                              else 'excluded under D-D7-1: no licence evidence (%s pool)' % face.get('pool'),
                                              'evidence': {'type': ev.get('type'), 'text': str(ev.get('text') or '')[:200]} if ev else None},
                                   'caption_source': 'day6-font-census', 'preview': (mp.OUT / (sha + '.png')).exists()}
            row['faces'].append({'face_id': face.get('face_id'), 'full_name': names.get('full_name'), 'weight_class': face.get('weight_class'),
                                 'italic': face.get('italic'), 'scripts': face.get('scripts')})
            row['arabic'] = row['arabic'] or 'arabic' in (face.get('scripts') or []); row['variable'] = row['variable'] or bool(face.get('is_variable'))
    for row in rows.values():
        f = row['faces'][0]; low = (row['family'] + ' ' + str(f.get('full_name') or '')).lower()
        cls = next((c for c in ('script', 'brush', 'hand', 'serif', 'sans', 'mono', 'display', 'slab', 'gothic', 'condensed', 'arabic', 'kufi', 'naskh') if c in low), None)
        scripts = sorted({s for face in row['faces'] for s in (face.get('scripts') or [])})
        row['tags'] = list(dict.fromkeys(['font'] + _words(row['family']) + scripts + ([cls] if cls else []) + (['variable'] if row['variable'] else [])
                                         + (['bold'] if any((x.get('weight_class') or 0) >= 600 for x in row['faces']) else [])
                                         + (['italic'] if any(x.get('italic') for x in row['faces']) else [])))[:12]
        row['style'] = [cls] if cls else []; row['class_basis'] = 'name heuristic'
        row['subject'] = '%s: %d face%s, %s%s' % (row['family'], len(row['faces']), '' if len(row['faces']) == 1 else 's', '/'.join(scripts) or 'script unknown',
                                                  ', variable' if row['variable'] else '')
    return rows


def build_index():
    """Every unique file: the earlier caption, the Day 7 caption or neither, measured colours, rights (D-D7-1), previews."""
    LIB.mkdir(parents=True, exist_ok=True)
    by_sha = collections.defaultdict(list); category = {}
    for r in mp.rows():
        by_sha[r['sha256']].append(r['relative_path']); cat = r.get('category'); category.setdefault(r['sha256'], cat.get('value') if isinstance(cat, dict) else cat)
    had = earlier(); rows = []; counts = collections.Counter(); kinds = collections.Counter()
    for j in nonfont_jobs():
        sha = j['sha256']; preview = mp.OUT / (sha + '.png'); row = {'sha256': sha, 'name': Path(j['path']).name, 'paths': sorted(by_sha[sha]),
                                                                     'extension': j['extension'], 'file_kind': j['kind'], 'inventory_category': category.get(sha)}
        if result_path(sha).exists() and (rec := json.loads(result_path(sha).read_text())).get('caption'):
            # a Day 7 caption first: it re-captions an earlier row of a failing class (the fresh-agent check, §2)
            c = rec['caption']; row.update({k: c[k] for k in ('kind', 'subject', 'tags', 'style', 'text_present', 'text_seen', 'language', 'surfaces', 'confidence')})
            row.update({'surfaces_basis': 'model', 'caption_source': 'day7-haiku', 'model': rec.get('model'), 'recaptioned': sha in had}); counts['day7'] += 1
            if sha in had:
                counts['recaptioned'] += 1
        elif sha in had:
            row.update(from_earlier(had[sha], category.get(sha))); counts['earlier'] += 1
        else:
            kind = CATEGORY_KIND.get(category.get(sha)) or 'other'
            row.update({'kind': kind, 'subject': '', 'tags': [kind, j['kind'], j['extension'].lstrip('.')], 'style': [], 'text_present': None, 'text_seen': [],
                        'language': 'unknown', 'surfaces': [], 'surfaces_basis': 'none', 'caption_source': 'none',
                        'caption_status': 'no preview' if not preview.exists() else 'not captioned yet'}); counts['uncaptioned'] += 1
        blank = sha in mp.blank_shas()
        row['colours'] = palette_of(preview) if preview.exists() and not blank else []; row['preview'] = preview.exists(); row['preview_blank'] = blank
        row['rights'] = {'tier': 'house', 'excluded': False, 'basis': 'D-D7-1: house library, licensed for generation; eligible for retrieval and attachment'}
        rows.append(row); kinds[row['kind']] += 1
    fonts = font_rows()
    for row in fonts.values():
        row['paths'] = sorted(set(row['paths']) | set(by_sha.get(row['sha256'], []))); rows.append(row); kinds['font'] += 1; counts['font'] += 1
    rows.sort(key=lambda r: r['sha256'])
    index = {'schema': 'day7_materials_index/1', 'built_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'rows': len(rows),
             'counts': dict(counts), 'kinds': dict(kinds), 'fonts_by_tier': dict(collections.Counter(r['rights']['tier'] for r in fonts.values())),
             'colours': 'measured from the Day 7 preview: median-cut 12, merged within ΔE76 8, top five, Lab D65; never asked of the model',
             'rights_rule': 'D-D7-1', 'caption_model': MODEL, 'previews_dir': str(mp.OUT.relative_to(ROOT)), 'items': rows}
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=0) + '\n')
    return {k: v for k, v in index.items() if k != 'items'}


if __name__ == '__main__':
    import sys, django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup()
    command = sys.argv[1] if len(sys.argv) > 1 else 'run'
    if command == 'run':
        out = run(int(sys.argv[2]) if len(sys.argv) > 2 else None); print(json.dumps({k: v for k, v in out.items() if k != 'batches'}, ensure_ascii=False))
    elif command == 'index':
        print(json.dumps(build_index(), ensure_ascii=False))
    elif command == 'recaption':
        plan = json.loads(Path(sys.argv[2]).read_text()); out = run(shas=set(plan['shas']), operation='day7/captions/recaption-', progress_path=LIB / 'recaption-progress.json')
        print(json.dumps({k: v for k, v in out.items() if k != 'batches'}, ensure_ascii=False))
    elif command == 'pending':
        ready, waiting = pending(); print(json.dumps({'ready': len(ready), 'waiting_for_preview': len(waiting)}))
