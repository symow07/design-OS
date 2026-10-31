"""Day 7 §1: a 150-PPI preview per unique materials file, resumable and idempotent; nothing under materials/ is written.

AI/PDF through the embedded PDF stream (PyMuPDF), EPS and stream-less AI through Ghostscript, PSD through the file's
own composite (never a full re-raster), JPG/PNG/WEBP resized, fonts as a specimen strip (Latin, and Arabic where the
cmap carries it). Long edge <= 1600 px. Report: done, failed by name, skipped by reason.
"""
from pathlib import Path
import datetime, io, json, os, subprocess, time
import fitz
from PIL import Image, ImageDraw, ImageFont, ImageOps
from . import fidelity_assets as fa

ROOT = fa.ROOT
INVENTORY = ROOT / 'var/design_intelligence/audits/dip0/inventory/inventory.jsonl'
OUT = ROOT / 'var/design_intelligence/previews/materials'
REPORT = ROOT / 'docs/audit/day-7/library/previews-progress.json'
PPI = 150
LONG_EDGE = 1600
MAX_COMPOSITE_PIXELS = 200_000_000
VECTOR = {'.ai', '.pdf'}; EPS = {'.eps'}; PSD = {'.psd', '.psb'}; RASTER = {'.jpg', '.jpeg', '.png', '.webp', '.tif', '.tiff'}
FONTS = {'.ttf', '.otf', '.ttc', '.otc'}; FONTS_UNRENDERED = {'.woff', '.woff2', '.eot', '.fon', '.pfb', '.pfm', '.dfont'}
LATIN = 'Aa Bb Qq Rr 0123 BBROSE Sun Repair'; ARABIC = 'سيروم صن ريبير'
GS = '/opt/homebrew/bin/gs'


def rows():
    out = []
    for line in INVENTORY.read_text(encoding='utf-8').splitlines():
        if line.strip():
            r = json.loads(line)
            if r['relative_path'].startswith('materials/'):
                out.append(r)
    return out


def candidates(all_rows):
    """One job per unique content hash; the first path in manifest order renders it."""
    seen = {}
    for r in sorted(all_rows, key=lambda r: r['relative_path']):
        ext = r['extension']
        kind = ('vector' if ext in VECTOR else 'eps' if ext in EPS else 'psd' if ext in PSD else 'raster' if ext in RASTER
                else 'font' if ext in FONTS else 'font_unrendered' if ext in FONTS_UNRENDERED else None)
        if kind and r['sha256'] not in seen:
            seen[r['sha256']] = {'sha256': r['sha256'], 'path': r['relative_path'], 'extension': ext, 'kind': kind, 'size_bytes': r['size_bytes']}
    return list(seen.values())


def fit(im):
    im = ImageOps.exif_transpose(im) if im.mode != 'P' else im
    if im.mode not in ('RGB', 'RGBA'):
        im = im.convert('RGBA' if 'A' in im.mode else 'RGB')
    if max(im.size) > LONG_EDGE:
        im = im.copy(); im.thumbnail((LONG_EDGE, LONG_EDGE), Image.Resampling.LANCZOS)
    return im


def save(im, target):
    tmp = target.with_suffix('.tmp.png'); im.save(tmp, format='PNG', dpi=(PPI, PPI), optimize=True); os.replace(tmp, target)


def render_pdf_stream(path):
    with fitz.open(path) as doc:
        if not len(doc):
            raise ValueError('no pages')
        page = doc[0]; rect = page.rect
        zoom = min(PPI / 72, LONG_EDGE / max(rect.width, rect.height))
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        return Image.frombytes('RGB', (pix.width, pix.height), pix.samples)


def render_ghostscript(path, eps):
    with io.BytesIO() as _:
        tmp = OUT / ('.gs-' + os.getpid().__str__() + '.png')
        cmd = [GS, '-q', '-dSAFER', '-dBATCH', '-dNOPAUSE', '-sDEVICE=png16m', '-r%d' % PPI, '-dFirstPage=1', '-dLastPage=1'] + (['-dEPSCrop'] if eps else []) + ['-sOutputFile=' + str(tmp), str(path)]
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if done.returncode or not tmp.exists():
            raise ValueError('ghostscript: ' + (done.stderr or done.stdout)[-200:].strip())
        im = fit(Image.open(tmp)); im.load(); tmp.unlink(); return im


def render_psd(path):
    with Image.open(path) as im:
        if im.width * im.height > MAX_COMPOSITE_PIXELS:
            raise LookupError('composite too large for the preview job: %d x %d' % (im.width, im.height))
        im.load(); return fit(im)


def render_raster(path):
    with Image.open(path) as im:
        im.load(); return fit(im)


def render_font(path, ext):
    from fontTools.ttLib import TTFont, TTCollection
    index = 0
    if ext in ('.ttc', '.otc'):
        with TTCollection(str(path), lazy=True) as coll: cmap = coll.fonts[0].getBestCmap() or {}
    else:
        with TTFont(str(path), lazy=True) as ft: cmap = ft.getBestCmap() or {}
    arabic = all(ord(c) in cmap for c in ARABIC.replace(' ', ''))
    latin_ok = all(ord(c) in cmap for c in 'ABQRSab')
    font = ImageFont.truetype(str(path), 72, index=index)
    lines = [(LATIN if latin_ok else 'Latin letters not in this face', 'ltr', 'latin')] + ([(ARABIC, 'rtl', 'arab')] if arabic else [])
    width = 1600; height = 110 * len(lines) + 70
    im = Image.new('RGB', (width, height), (250, 247, 243)); d = ImageDraw.Draw(im)
    small = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 22) if Path('/System/Library/Fonts/Helvetica.ttc').exists() else ImageFont.load_default()
    d.text((20, 14), path.name + ('  · Arabic cmap present' if arabic else '  · no Arabic cmap'), font=small, fill=(90, 80, 70))
    y = 60
    for text, direction, script in lines:
        try:
            d.text((20, y), text, font=font, fill=(30, 25, 20), direction=direction, language='ar' if script == 'arab' else 'en')
        except (OSError, ValueError) as exc:
            d.text((20, y + 30), 'specimen not rendered: ' + str(exc)[:80], font=small, fill=(160, 40, 40))
        y += 110
    return im


def preview(job):
    path = ROOT / job['path']; target = OUT / (job['sha256'] + '.png')
    if target.exists() and target.stat().st_size > 0:
        return 'present', None
    kind = job['kind']
    if kind == 'font_unrendered':
        return 'skipped', 'font format not rendered (' + job['extension'] + ')'
    if kind == 'psd' and job['extension'] == '.psb':
        return 'skipped', 'PSB composite not readable by the preview job'
    try:
        if kind == 'vector':
            try:
                im = render_pdf_stream(path); method = 'pdf stream'
            except Exception:
                im = render_ghostscript(path, eps=False); method = 'ghostscript'
        elif kind == 'eps':
            im = render_ghostscript(path, eps=True); method = 'ghostscript'
        elif kind == 'psd':
            im = render_psd(path); method = 'psd composite'
        elif kind == 'raster':
            im = render_raster(path); method = 'resized'
        else:
            im = render_font(path, job['extension']); method = 'font specimen'
    except LookupError as exc:
        return 'skipped', str(exc)
    except Exception as exc:
        return 'failed', type(exc).__name__ + ': ' + str(exc)[:160]
    save(fit(im), target); return 'done', method


def run(limit=None):
    OUT.mkdir(parents=True, exist_ok=True); REPORT.parent.mkdir(parents=True, exist_ok=True); os.nice(10)
    jobs = candidates(rows()); started = time.time()
    report = {'schema': 'day7_previews/1', 'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'ppi': PPI, 'long_edge_px': LONG_EDGE,
              'unique_jobs': len(jobs), 'by_kind': {}, 'done': 0, 'present_before': 0, 'failed': [], 'skipped': {}, 'methods': {}, 'materials_written': False}
    for i, job in enumerate(jobs):
        if limit and i >= limit: break
        state, note = preview(job); k = job['kind']; report['by_kind'].setdefault(k, {'done': 0, 'failed': 0, 'skipped': 0, 'present': 0})
        if state == 'done':
            report['done'] += 1; report['by_kind'][k]['done'] += 1; report['methods'][note] = report['methods'].get(note, 0) + 1
        elif state == 'present':
            report['present_before'] += 1; report['by_kind'][k]['present'] += 1
        elif state == 'failed':
            report['failed'].append({'path': job['path'], 'sha256': job['sha256'], 'error': note}); report['by_kind'][k]['failed'] += 1
        else:
            report['skipped'].setdefault(note, []).append(job['path']); report['by_kind'][k]['skipped'] += 1
        if (i + 1) % 100 == 0 or i + 1 == len(jobs):
            report['processed'] = i + 1; report['seconds'] = round(time.time() - started, 1)
            REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n'); print(json.dumps({'processed': i + 1, 'done': report['done'], 'failed': len(report['failed'])}), flush=True)
    report['finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat(); report['skipped_counts'] = {k: len(v) for k, v in report['skipped'].items()}
    report['previews_on_disk'] = sum(1 for p in OUT.glob('*.png') if not p.name.startswith('.'))
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n'); return report


if __name__ == '__main__':
    import sys
    r = run(int(sys.argv[1]) if len(sys.argv) > 1 else None)
    print(json.dumps({k: v for k, v in r.items() if k not in ('failed', 'skipped')}, ensure_ascii=False))


BLANK = ROOT / 'docs/audit/day-7/library/previews-blank.json'


def scan_blank(std_below=2.0):
    """Every preview whose pixels are one flat colour (a page that rendered empty): listed by hash so the index marks it and
    nothing reads it as a picture. Measured on a 48-px thumbnail; a specimen strip or a real picture is never that flat."""
    import numpy as np
    blank = []; n = 0
    for png in sorted(OUT.glob('*.png')):
        if png.name.startswith('.'):
            continue
        n += 1
        with Image.open(png) as im:
            im.thumbnail((48, 48)); a = np.asarray(im.convert('L'))
        if a.std() < std_below:
            blank.append({'sha256': png.stem, 'mean': round(float(a.mean()), 1), 'size_px': list(Image.open(png).size)})
    record = {'schema': 'day7_previews_blank/1', 'rule': 'thumbnail standard deviation below %.1f (one flat colour)' % std_below, 'scanned': n, 'blank': len(blank),
              'items': blank, 'scanned_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    BLANK.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n'); return {k: v for k, v in record.items() if k != 'items'}


def blank_shas():
    return {b['sha256'] for b in json.loads(BLANK.read_text()).get('items') or []} if BLANK.exists() else set()
