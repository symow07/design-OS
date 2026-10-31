"""Day 7 §3: material candidates for a brief, ranked on what the library index says each file SHOWS — its caption, tags,
style, kind, measured colours and suitable surfaces — never on a file name. The top three to five, and one contrast (a
different style, offered for range), each pinned by content hash (`materials:<sha256>`) with a role (style, pattern,
material, layout) and pictured through its Day 7 preview. The 73-file house index (docs/brand/house_references) joins
with a house boost. Fonts are never offered as references (they are set, not placed), nor any row the index excludes.
"""
from pathlib import Path
import hashlib, json, re, threading
from django.conf import settings
from . import fidelity_assets as fa

ROOT = fa.ROOT
TOP = 5; MIN_WORD_SCORE = 1.0
ROLE_OF_KIND = {'pattern': 'pattern', 'background': 'material', 'texture': 'material', 'ornament': 'style', 'illustration': 'style',
                'icon': 'style', 'logo': 'style', 'typography': 'style', 'palette': 'style', 'house-artwork': 'style',
                'layout': 'layout', 'mockup': 'layout', 'product-render': 'layout', 'photo': 'layout', 'dieline': 'layout', 'other': 'layout'}
#: a colour word of a brief and the sRGB it stands for — a reference point for ΔE76 against measured palettes
COLOUR_WORDS = {'gold': '#C9A227', 'golden': '#C9A227', 'pink': '#E8A0B4', 'rose': '#D98FA5', 'blush': '#F2C1C6', 'cream': '#F3E9D2',
                'ivory': '#FFFFF0', 'black': '#111111', 'white': '#FAFAFA', 'green': '#4E8B5A', 'blue': '#3F6FB5', 'red': '#B9252B',
                'amber': '#E0A030', 'brown': '#6B4A2B', 'teal': '#2E8B8B', 'navy': '#1F2D5A', 'coral': '#F08070', 'peach': '#F7C7A3',
                'mint': '#A9E5C5', 'lavender': '#C2B2DD', 'silver': '#C0C0C0', 'copper': '#B87333', 'beige': '#E3D5BF', 'grey': '#8A8A8A',
                'gray': '#8A8A8A', 'purple': '#7A4FA3', 'violet': '#8F6BBF', 'yellow': '#F2D43C', 'orange': '#F08A24', 'turquoise': '#3FB8AF',
                'emerald': '#2E8B57', 'burgundy': '#7B1E3A', 'sage': '#9CAF88', 'terracotta': '#C8643C', 'nude': '#E6C7B3', 'bronze': '#B08D57',
                'champagne': '#F1E1C6', 'pastel': '#EAD7E5'}
COLOUR_DE_MAX = 25.0
SURFACE_HINTS = {'carton': 'carton', 'cartons': 'carton', 'box': 'carton', 'boxes': 'carton', 'bottle': 'bottle-label', 'label': 'bottle-label',
                 'labels': 'bottle-label', 'header': 'header', 'riser': 'riser', 'risers': 'riser', 'base': 'base', 'plinth': 'base',
                 'backdrop': 'backdrop', 'background': 'backdrop', 'backgrounds': 'backdrop', 'pattern': 'pattern-fill', 'patterns': 'pattern-fill',
                 'repeat': 'pattern-fill', 'ornament': 'ornament-accent', 'ornaments': 'ornament-accent', 'accent': 'ornament-accent',
                 'accents': 'ornament-accent', 'flourish': 'ornament-accent', 'mockup': 'mockup-scene', 'mockups': 'mockup-scene', 'scene': 'mockup-scene'}
KIND_WORDS = {'pattern': 'pattern', 'patterns': 'pattern', 'icon': 'icon', 'icons': 'icon', 'mockup': 'mockup', 'texture': 'texture',
              'ornament': 'ornament', 'illustration': 'illustration', 'photo': 'photo', 'photograph': 'photo', 'logo': 'logo', 'palette': 'palette',
              'background': 'background'}
_WORD = re.compile(r"[a-z0-9]+")
#: English's small words, kept out of the house rows' shown tags (the brief's own stop words govern ranking)
_SMALL = frozenset("a an the and or of with on in at to for by from as is are its into over under this that these those".split())
_lock = threading.Lock(); _cache = {}


def index_path() -> Path:
    return Path(getattr(settings, 'MATERIALS_INDEX_PATH', ROOT / 'docs/audit/day-7/library/materials-index.json'))


def previews_root() -> Path:
    return Path(getattr(settings, 'MATERIALS_PREVIEWS_ROOT', ROOT / 'var/design_intelligence/previews/materials'))


def house_index_path() -> Path:
    return Path(getattr(settings, 'HOUSE_INDEX_PATH', ROOT / 'docs/brand/house_references/index.json'))


def _words(*texts):
    out = set()
    for t in texts:
        out.update(_WORD.findall(str(t or '').lower()))
    return out


def _hex_lab(hex6):
    import numpy as np
    from .materials_captions import srgb_to_lab
    h = hex6.lstrip('#'); rgb = np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)]) / 255.0
    return [float(v) for v in srgb_to_lab(rgb)]


def _card(row):
    tags = [t for t in row.get('tags') or [] if isinstance(t, str)]; style = [s for s in row.get('style') or [] if isinstance(s, str)]
    colours = []
    for c in row.get('colours') or []:
        lab = c.get('lab') if isinstance(c, dict) else None
        if lab and (c.get('share') or 0) >= 0.04:
            colours.append((lab, c.get('hex'), c.get('share')))
    return {'sha': row['sha256'], 'kind': row.get('kind') or 'other', 'file_kind': row.get('file_kind'), 'name': row.get('name') or '',
            'path': (row.get('paths') or [''])[0], 'subject': row.get('subject') or '', 'tags': tags, 'style': style,
            'tagset': set(tags) | set(style), 'tagwords': _words(*tags), 'stylewords': _words(*style), 'subjectwords': _words(row.get('subject')),
            'textwords': _words(*(row.get('text_seen') or [])), 'colours': colours, 'surfaces': set(row.get('surfaces') or []),
            'preview': bool(row.get('preview')) and not row.get('preview_blank'), 'house': False, 'source': row.get('caption_source'),
            'offerable': row.get('kind') != 'font' and not (row.get('rights') or {}).get('excluded') and row.get('caption_source') not in (None, 'none')}


def _house_cards():
    path = house_index_path()
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding='utf-8')); cards = []
    from .materials_captions import srgb_to_lab
    import numpy as np
    for f in data.get('files') or []:
        if f.get('status') != 'rasterised' or not f.get('sha256'):
            continue
        page = (f.get('pages') or [{}])[0]; colours = []
        for c in (f.get('dominant_colours') or [])[:6]:
            if isinstance(c, dict) and c.get('srgb') and (c.get('fraction') or 0) >= 0.04:
                lab = [float(v) for v in srgb_to_lab(np.array(c['srgb']) / 255.0)]
                colours.append((lab, '#%02X%02X%02X' % tuple(int(v) for v in c['srgb']), c['fraction']))
        words = _words(f.get('description')) - _SMALL
        cards.append({'sha': f['sha256'], 'kind': 'house-artwork', 'file_kind': 'vector', 'name': f.get('filename') or '', 'path': 'docs/brand/house_references/files/' + (f.get('filename') or ''),
                      'subject': f.get('description') or '', 'tags': sorted(words), 'style': [], 'tagset': set(), 'tagwords': words, 'stylewords': set(),
                      'subjectwords': words, 'textwords': set(), 'colours': colours, 'surfaces': {'carton', 'bottle-label', 'header'},
                      'preview': bool(page.get('png')), 'preview_path': page.get('png'), 'house': True, 'house_id': f.get('id'), 'source': 'house-index', 'offerable': True})
    return cards


def cards():
    """The index as scoring cards, read once per change of the file (path, size, mtime); the house index beside it."""
    path = index_path()
    try:
        stat = path.stat(); key = (str(path), stat.st_size, stat.st_mtime_ns)
    except OSError:
        return []
    with _lock:
        if _cache.get('key') != key:
            rows = json.loads(path.read_text(encoding='utf-8')).get('items') or []
            _cache['key'] = key; _cache['cards'] = [_card(r) for r in rows if r.get('sha256')] + _house_cards()
            _cache['by_sha'] = {r['sha256']: r for r in rows if r.get('sha256')}
        return _cache['cards']


def index_row(sha):
    cards(); return (_cache.get('by_sha') or {}).get(sha)


def index_items() -> list[dict]:
    """Every row of the index as written (the Library page reads these)."""
    cards(); return list((_cache.get('by_sha') or {}).values())


def brief_of(task) -> dict:
    """The brief's words (never a stop word), its hyphen phrases, its colour words, its surface and kind hints."""
    from .concept_references import _task_tokens
    parts = [getattr(task, 'task_text', '') or '']
    product = getattr(task, 'product', None)
    if product is not None:
        parts += [getattr(product, 'name', '') or '', getattr(product, 'product_type', '') or '']
    raw = ' '.join(parts).lower(); words = _WORD.findall(raw)
    phrases = {a + '-' + b for a, b in zip(words, words[1:])} | set(re.findall(r"[a-z0-9]+-[a-z0-9]+", raw))
    return {'tokens': _task_tokens(task), 'phrases': phrases, 'colours': {w for w in words if w in COLOUR_WORDS},
            'surfaces': {SURFACE_HINTS[w] for w in words if w in SURFACE_HINTS}, 'kinds': {KIND_WORDS[w] for w in words if w in KIND_WORDS}}


def score(card, brief) -> tuple | None:
    """``(score, reasons)`` or None where the brief's words find nothing in what the file shows — colour or surface alone
    never qualify a file (no padding with stock that merely shares a colour)."""
    import math
    t = brief['tokens']; reasons = []; total = 0.0
    shown = card['tagwords'] | card['stylewords'] | card['subjectwords']
    # a two-word style of the brief ("art deco", "art-deco") is exact when the file carries it as one tag or as both words
    exact = sorted(p for p in brief['phrases'] if p in card['tagset'] or (set(p.split('-')) <= shown and p.split('-')[0] not in brief['tokens']))
    tag_hits = sorted(t & card['tagwords']); style_hits = sorted((t & card['stylewords']) - set(tag_hits))
    subject_hits = sorted((t & card['subjectwords']) - set(tag_hits) - set(style_hits)); text_hits = sorted((t & card['textwords']) - set(tag_hits))
    word_score = 6.0 * len(exact) + 3.0 * len(tag_hits) + 2.0 * len(style_hits) + 1.0 * len(subject_hits) + 0.5 * len(text_hits)
    if card['kind'] in brief['kinds']:
        word_score += 2.0; reasons.append('is the %s the brief asks for' % card['kind'])
    if word_score < MIN_WORD_SCORE:
        return None
    total += word_score
    if exact:
        reasons.insert(0, 'exact style tag ' + '/'.join(exact[:3]))
    found = tag_hits + style_hits + subject_hits
    if found:
        reasons.append('matches the brief on ' + '/'.join(found[:4]))
    for word in sorted(brief['colours']):
        lab = _hex_lab(COLOUR_WORDS[word]); best = None
        for clab, chex, _share in card['colours']:
            de = math.dist(lab, clab)
            if best is None or de < best[0]:
                best = (de, chex)
        if best and best[0] <= COLOUR_DE_MAX:
            total += 2.0 * (1 - best[0] / COLOUR_DE_MAX); reasons.append('colour near %s (%s, ΔE %.0f)' % (word, best[1], best[0]))
    suits = sorted(brief['surfaces'] & card['surfaces'])
    if suits:
        total += 1.5; reasons.append('suits ' + '/'.join(suits[:2]))
    if card['house']:
        total += 2.0; reasons.append('house artwork (%s)' % card['house_id'])
    return round(total, 3), reasons


def rank(task) -> list[dict]:
    """Every offerable card the brief's words find, best first: ``{card, score, reasons}``."""
    brief = brief_of(task); found = []
    for card in cards():
        if not card['offerable']:
            continue
        s = score(card, brief)
        if s:
            found.append({'card': card, 'score': s[0], 'reasons': s[1]})
    found.sort(key=lambda f: (-f['score'], f['card']['sha']))
    return found


def select(ranked) -> list[dict]:
    """The top three to five, then one contrast: the best card after them whose style shares nothing with the first's and
    whose kind differs — offered for range, marked so."""
    top = ranked[:TOP]
    if not top:
        return []
    first = top[0]['card']; contrast = None
    for f in ranked[TOP:]:
        c = f['card']
        if c['kind'] != first['kind'] and not (set(c['style']) & set(first['style'])):
            contrast = dict(f, contrast=True); break
    return top + ([contrast] if contrast else [])


def role_of(card) -> str:
    return ROLE_OF_KIND.get(card['kind'], 'layout')


def _row(f) -> dict:
    card = f['card']; role = role_of(card); hexes = [c[1] for c in card['colours'][:4] if c[1]]
    reason = '; '.join(f['reasons']) + ('; contrast: a different style, offered for range' if f.get('contrast') else '')
    description = 'role: %s · %s · tags: %s · colours %s' % (role, card['kind'], ', '.join(card['tags'][:8]) or '-', ' '.join(hexes) or '-')
    if card['house']:
        item, root, path = 'house:' + card['house_id'], 'house', card['preview_path'] or ''
    elif card['preview']:
        item, root, path = 'materials:' + card['sha'], 'previews', card['sha'] + '.png'
    else:
        item, root, path = 'materials:' + card['sha'], 'materials', card['path']
    return {'source_type': 'MATERIAL_LIBRARY', 'library_item_id': item[:300], 'title': (card['subject'] or (card['kind'] + ' ' + card['sha'][:8]))[:200],
            'description': description[:500], 'relevance_reason': reason[:300], 'retrieval_score': f['score'],
            'ownership_status': ('HOUSE_ARTWORK' if card['house'] else 'HOUSE_LIBRARY')[:60], 'rights_status': 'LICENSED_FOR_GENERATION_D-D7-1'[:60],
            'is_vector': card['file_kind'] in ('vector', 'eps'), 'image_root': root, 'image_path': path[:500]}


def candidates(task) -> list[dict]:
    """ConceptReference rows for the brief: the selection of ``select(rank(task))``, pinned by hash, with roles."""
    return [_row(f) for f in select(rank(task))]


def pins(rows) -> list[dict]:
    """The library pins of reference rows (dicts or model rows): ``[{"pin", "role"}]`` sorted by pin."""
    out = []
    for r in rows:
        item = r.get('library_item_id') if isinstance(r, dict) else getattr(r, 'library_item_id', '')
        desc = r.get('description') if isinstance(r, dict) else getattr(r, 'description', '')
        if str(item).startswith(('materials:', 'house:')):
            m = re.match(r'role: ([a-z]+)', str(desc or ''))
            out.append({'pin': str(item), 'role': m.group(1) if m else 'layout'})
    return sorted(out, key=lambda p: p['pin'])


def pins_hash(rows) -> str:
    return hashlib.sha256(json.dumps(pins(rows), sort_keys=True).encode()).hexdigest()


def facts(sha) -> dict:
    """What the index says of one file, for a reference card: subject, kind, tags, rights words, preview."""
    row = index_row(sha)
    if not row:
        return {}
    rights = row.get('rights') or {}
    return {'subject': row.get('subject') or '', 'kind': row.get('kind'), 'tags': (row.get('tags') or [])[:12], 'surfaces': row.get('surfaces') or [],
            'colours': [c.get('hex') for c in (row.get('colours') or []) if isinstance(c, dict)], 'preview': bool(row.get('preview')),
            'rights': rights.get('basis') or '', 'tier': rights.get('tier'), 'caption_source': row.get('caption_source'), 'name': row.get('name')}
