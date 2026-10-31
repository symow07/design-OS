"""Day 11 §1 — Ẓilāl's lid (D-D11-1 … D-D11-3): the owner's pick changes to the sketch B-1.3; it is the design.

D-D11-2 first: each of the jury's findings on Day 9's B-1.3 BUILD is checked against the SKETCH at 1 : 1 — the measurable
ones measured here (the logo's air above باليت, the stones under the small lines, the hero's hatch), every one read by the
designer's eye on the sketch's crop above the build's — and only those present in the sketch are answered by the one
refinement round. Then the master by the preservation path (D-D10-1/2/3, D-D11-3), built on ``lid_master``'s measuring
functions.

Every function here is deterministic and costs $0 but the looks passed a paid ``call`` (the designer's eye, through the
ledger under ``EYE_PREFIX``).
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, map_coordinates

from apps.pipeline.services import image_guard
from apps.pipeline.services import lid_master as lm

REPO = lm.REPO
PICK, PICK_SHA256 = image_guard.APPROVED_ZILAL
PICK_PX = (1536, 970)
DAY11 = REPO / 'docs' / 'audit' / 'day-11'
OUT = DAY11 / 'zilal' / 'lid'
BUILD = REPO / 'docs' / 'audit' / 'day-9' / 'concepts' / 'B-1.3'
EYE_PREFIX = 'day12/designer-eye/'         # [Day 12] (Day 11's: 'day11/designer-eye/')
PX_PER_MM_SRC = lm.PX_PER_MM_SRC                 # the pick at the lid's 190 mm: 8.084 px/mm

#: where each element stands in the sketch (pick px, padded windows): measured by ``ink_boxes`` inside them
WINDOWS = {'logo': (1140, 0, 1536, 110), 'baliyt': (1280, 120, 1536, 225), 'hero': (500, 165, 1420, 600),
           'aleyoun': (430, 585, 650, 665), 'name': (60, 690, 820, 885), 'eyeshadow': (70, 830, 540, 880),
           'shades': (900, 900, 1130, 965), 'net': (1180, 900, 1490, 965)}
CREAM = ('baliyt', 'aleyoun', 'eyeshadow', 'shades', 'net')
GOLD = ('logo', 'hero', 'name')
GROUND_BOX = (820, 60, 980, 120)                 # a clear stretch of the indigo ground between the stone fields
OFF_GROUND_DE = 15.0                             # a pixel off the ground by over ΔE00 15 is ink or stone
SMALL_LINE_PAD_MM = 1.0


def load_pick():
    """The pick's pixels, refused unless its bytes are the owner's (D-D11-1) and its size the lid's 1536 × 970."""
    digest = lm.sha256(PICK)
    if digest != PICK_SHA256:
        raise ValueError('not the owner\'s pick: %s has sha256 %s' % (PICK, digest))
    rgb = np.asarray(Image.open(PICK).convert('RGB'))
    if (rgb.shape[1], rgb.shape[0]) != PICK_PX:
        raise ValueError('the pick is %d × %d px, not %d × %d' % (rgb.shape[1], rgb.shape[0]) + PICK_PX)
    return rgb


def ground_lab(pick):
    """The indigo ground's colour: the median of a clear stretch, in Lab."""
    x0, y0, x1, y1 = GROUND_BOX
    rgb = np.median(pick[y0:y1, x0:x1].reshape(-1, 3), axis=0)
    return lm.srgb_to_lab(rgb[None, None, :].astype(np.uint8))[0, 0]


ROSE_GOLD_HUE = (38.0, 75.0)            # the rose gold's hue (measured on R3: hero 44–69°, name 43–64°, logo 45–68°);
                                        # the stones sit at 0–30° and 300–360° (rose, coral, lilac) and near 200° (teal)
ROSE_GOLD_L_MIN = 30.0
ROSE_GOLD_C_MIN = 12.0


def masks(pick):
    """The sketch's inks by colour: the rose gold (L* > 30, chroma > 12, hue 38–75°: the stones' hues lie outside it,
    the copper veins inside — they are told apart by their width, ``element_masks``), the cream type (L* > 60, chroma
    under 25), and everything off the indigo ground by over ΔE00 15 (ink or stone)."""
    lab = lm.srgb_to_lab(pick)
    light, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    hue = np.degrees(np.arctan2(b, a)) % 360
    gold = ((light > ROSE_GOLD_L_MIN) & (np.hypot(a, b) > ROSE_GOLD_C_MIN)
            & (hue > ROSE_GOLD_HUE[0]) & (hue < ROSE_GOLD_HUE[1]))
    cream = (light > 60) & (np.hypot(a, b) < 25)
    off = lm.delta_e00(lab, np.broadcast_to(ground_lab(pick), lab.shape)) > OFF_GROUND_DE
    return {'gold': gold, 'cream': cream, 'off': off}


#: each element's ink, told from the stones and veins around it: (close px, open px, smallest part px) — the hero's
#: hatch closed into solid letters and the 1–3 px copper veins opened away; the name's hairlines (its swash E and R) never
#: opened — its window holds no vein
ELEMENT_MORPH = {'hero': (9, 7, 2000), 'name': (3, 1, 40), 'logo': (3, 2, 20), 'cream': (1, 2, 6)}


def element_mask(pick, name, m):
    """One element's ink inside its window (window-sized boolean): its colour's mask, closed and opened at the
    element's own scale, and only the parts whose own box lies wholly inside the window (a stone or vein crossing the
    window's edge is not the element's)."""
    x0, y0, x1, y1 = WINDOWS[name]
    kind = name if name in GOLD else 'cream'
    close, opening, smallest = ELEMENT_MORPH[kind]
    ink = m['cream' if name in CREAM else 'gold'][y0:y1, x0:x1].astype(np.uint8)
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((close, close), np.uint8))
    ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((opening, opening), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(ink, 8)
    keep = np.zeros(ink.shape, dtype=bool)
    h, w = ink.shape
    for i in range(1, n):
        bx, by, bw, bh, area = stats[i]
        if area >= smallest and bx > 0 and by > 0 and bx + bw < w and by + bh < h:
            keep |= labels == i
    return keep


def ink_boxes(pick):
    """Each element's ink box in the sketch (pick px, x0 y0 x1 y1 exclusive): its own ink (``element_mask``) inside its
    window."""
    m = masks(pick)
    boxes = {}
    for name, (x0, y0, x1, y1) in WINDOWS.items():
        ys, xs = np.nonzero(element_mask(pick, name, m))
        boxes[name] = [int(x0 + xs.min()), int(y0 + ys.min()), int(x0 + xs.max() + 1), int(y0 + ys.max() + 1)]
    return boxes


def mm(px):
    return round(float(px) / PX_PER_MM_SRC, 2)


def stones_under(pick, boxes, keys):
    """The share of each line's box (grown 1 mm) that is stone — off the ground, and neither the line's cream nor gold."""
    m = masks(pick)
    stone = m['off'] & ~m['cream'] & ~m['gold']
    pad = int(round(SMALL_LINE_PAD_MM * PX_PER_MM_SRC))
    out = {}
    for key in keys:
        x0, y0, x1, y1 = boxes[key]
        sub = stone[max(y0 - pad, 0):y1 + pad, max(x0 - pad, 0):x1 + pad]
        out[key] = round(float(sub.mean()), 3)
    return out


def hatch_measure(pick, hero_box):
    """The hero's hatch, measured inside its letters: the dominant period and direction of L* by FFT (the letters'
    pixels eroded 4 px from their rims, a Hann window), then stroke and gap widths along 300 profiles across the lines
    (bright = the gold stroke). Pitch in px and mm; the lines' own angle (perpendicular to the wave vector)."""
    lab = lm.srgb_to_lab(pick)
    light = lab[..., 0]
    gold = masks(pick)['gold'].astype(np.uint8)
    gold = cv2.morphologyEx(gold, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    inner = cv2.erode(gold, np.ones((9, 9), np.uint8)).astype(bool)
    x0, y0, x1, y1 = hero_box
    sub, m = light[y0:y1, x0:x1].astype(np.float64), inner[y0:y1, x0:x1]
    v = np.where(m, sub - sub[m].mean(), 0.0)
    h, w = v.shape
    spec = np.abs(np.fft.fftshift(np.fft.fft2(v * np.outer(np.hanning(h), np.hanning(w))))) ** 2
    fy = (np.arange(h) - h // 2) / h
    fx = (np.arange(w) - w // 2) / w
    FY, FX = np.meshgrid(fy, fx, indexing='ij')
    radius = np.hypot(FX, FY)
    band = np.where((radius > 1 / 8.0) & (radius < 0.5), spec, 0)
    iy, ix = np.unravel_index(np.argmax(band), band.shape)
    nb = band[iy - 2:iy + 3, ix - 2:ix + 3]
    wy = float((FY[iy - 2:iy + 3, ix - 2:ix + 3] * nb).sum() / nb.sum())
    wx = float((FX[iy - 2:iy + 3, ix - 2:ix + 3] * nb).sum() / nb.sum())
    period = 1.0 / float(np.hypot(wx, wy))
    wave = float(np.degrees(np.arctan2(wy, wx)))
    n = np.array([np.cos(np.radians(wave)), np.sin(np.radians(wave))])
    ys, xs = np.nonzero(inner[y0:y1, x0:x1])
    rng = np.random.default_rng(11)
    strokes, gaps, used = [], [], 0
    s = np.arange(-8, 8, 0.05)
    for k in rng.choice(len(xs), min(300, len(xs)), replace=False):
        c = np.array([xs[k] + x0, ys[k] + y0], dtype=np.float64)
        pts = c[None, :] + s[:, None] * n[None, :]
        rows = np.clip(np.round(pts[:, 1]).astype(int), 0, inner.shape[0] - 1)
        cols = np.clip(np.round(pts[:, 0]).astype(int), 0, inner.shape[1] - 1)
        if not inner[rows, cols].all():
            continue
        p = map_coordinates(light, [pts[:, 1], pts[:, 0]], order=3)
        q = p - cv2.GaussianBlur(p.reshape(1, -1), (0, 0), 20).ravel()
        on = q > 0
        e = np.flatnonzero(np.diff(on.astype(int)) != 0)
        for a, b in zip(e[:-1], e[1:]):
            (strokes if on[a + 1] else gaps).append((b - a) * 0.05)
        used += 1
    return {'method': 'FFT of L* inside the hero (rims eroded 4 px, Hann window), the dominant period between 2 and 8 px, '
                      'refined by the 5 × 5 centroid; stroke and gap widths along %d profiles across the lines' % used,
            'crop_px': list(hero_box), 'period_px': round(period, 3), 'pitch_mm': round(period / PX_PER_MM_SRC, 4),
            'wave_vector_deg': round(wave, 2), 'line_angle_deg': round((wave + 90.0 + 180.0) % 180.0, 2),
            'stroke_mm_median': round(float(np.median(strokes)) / PX_PER_MM_SRC, 4),
            'gap_mm_median': round(float(np.median(gaps)) / PX_PER_MM_SRC, 4), 'profiles': used,
            'spectrum': spec, 'inner': inner}


def save_spectrum(measure, path):
    """The FFT crop saved: the log spectrum of the hero's hatch, its peak marked."""
    spec = np.log1p(measure['spectrum'])
    img = (255 * (spec - spec.min()) / (spec.max() - spec.min())).astype(np.uint8)
    Image.fromarray(img).save(path)
    return path


FINDINGS_SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['findings', 'summary'],
    'properties': {
        'findings': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['finding', 'present_in_sketch', 'evidence', 'answered_by'],
            'properties': {'finding': {'type': 'integer'}, 'present_in_sketch': {'type': 'boolean'},
                           'evidence': {'type': 'string'},
                           'answered_by': {'type': 'string', 'enum': ['refinement', 'master', 'none']}}}},
        'summary': {'type': 'string'}}}

#: the crops each finding is read on: (what, the sketch's window in pick px); the build's crop is the same window
FINDING_CROPS = {
    'marbling, top-left field': (0, 0, 520, 420), 'marbling, bottom-right field': (900, 520, 1536, 900),
    'the whole lid': (0, 0, 1536, 970), 'the name': (60, 690, 800, 830), 'the small lines, bottom right': (880, 820, 1536, 970),
    'the logo and باليت': (1100, 0, 1536, 230), 'العيون beside the hero': (420, 470, 760, 680),
    'the hero\'s hatch': (990, 240, 1180, 400)}
CROP_EDGE_MAX = 1500
CROP_DPI_MAX = 600.0
CROP_FILL = 0.97                     # the white rule and rounding kept inside the API's limits


def finding_crops(out_dir):
    """Each window of the sketch above the same window of Day 9's build, at print size (the largest dpi up to 600 that
    keeps the pair under the API's 1568 px and 1.15 MP), a white rule between. Returns {name: (path, dpi)}."""
    sketch = Image.open(PICK).convert('RGB')
    build = Image.open(BUILD / 'truthful.png').convert('RGB').resize(sketch.size, Image.LANCZOS)
    made = {}
    for name, (x0, y0, x1, y1) in FINDING_CROPS.items():
        w_mm, h_mm = (x1 - x0) / PX_PER_MM_SRC, (y1 - y0) / PX_PER_MM_SRC
        dpi = CROP_FILL * min(CROP_DPI_MAX, CROP_EDGE_MAX / (w_mm / lm.MM_PER_INCH),
                              CROP_EDGE_MAX / (2 * h_mm / lm.MM_PER_INCH),
                              (lm.EYE_PIXELS_MAX / (2 * w_mm * h_mm)) ** 0.5 * lm.MM_PER_INCH)
        size = (int(w_mm / lm.MM_PER_INCH * dpi), int(h_mm / lm.MM_PER_INCH * dpi))
        top = sketch.crop((x0, y0, x1, y1)).resize(size, Image.LANCZOS)
        below = build.crop((x0, y0, x1, y1)).resize(size, Image.LANCZOS)
        pair = Image.new('RGB', (size[0], 2 * size[1] + 8), 'white')
        pair.paste(top, (0, 0))
        pair.paste(below, (0, size[1] + 8))
        path = Path(out_dir) / ('crop-%s.png' % name.replace(' ', '-').replace(',', '').replace("'", ''))
        pair.save(path, dpi=(dpi, dpi))
        made[name] = (path, round(dpi, 1))
    return made


def build_findings():
    """The jury's top issues on Day 9's B-1.3 build, verbatim, numbered 1 … n."""
    verdict = json.loads((BUILD / 'jury' / 'verdict.json').read_text(encoding='utf-8'))
    return [dict(i, number=n) for n, i in enumerate(verdict['top_issues'], start=1)]


def findings_measures(pick):
    """What can be measured on the sketch for the findings: the elements' ink boxes, the logo's air above باليت, the
    stones under the small lines, and the hero's hatch."""
    boxes = ink_boxes(pick)
    hatch = hatch_measure(pick, boxes['hero'])
    return {'ink_boxes_px': boxes,
            'logo_to_baliyt_mm': mm(boxes['baliyt'][1] - boxes['logo'][3]),
            'stone_share_under_small_lines': stones_under(pick, boxes, ('eyeshadow', 'shades', 'net')),
            'hatch': {k: v for k, v in hatch.items() if k not in ('spectrum', 'inner')}}, hatch


def findings_check(out_dir, call):
    """D-D11-2's check: the crops made and measured at $0, then ONE look by the designer's eye — each finding of the jury
    on the build read on the sketch: present or not, and answered by the refinement round, by the master's own rules
    (D-D11-3), or not at all. Written to findings.json the moment it returns."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pick = load_pick()
    measures, hatch = findings_measures(pick)
    save_spectrum(hatch, out / 'hatch-fft.png')
    findings = build_findings()
    crops = finding_crops(out)
    blocks = [lm._image_block(path) for path, _ in crops.values()]
    listing = '\n'.join('%d. "%s" — at %s; the jury\'s repair: %s' % (f['number'], f['observation'], f['location'],
                                                                     f['repair']) for f in findings)
    facts = ('MEASURED ON THE SKETCH (pick px at 8.084 px/mm): the logo\'s ink ends %.2f mm above باليت\'s; the share of '
             'stone under each small line (its box grown 1 mm): %s; the hero\'s hatch: pitch %.3f mm, strokes %.3f mm, '
             'gaps %.3f mm (the press limits: foil gaps at least 0.2 mm; the master fits the hatch as engine lines and '
             'coarsens only if they do not hold).' % (
                 measures['logo_to_baliyt_mm'], measures['stone_share_under_small_lines'], measures['hatch']['pitch_mm'],
                 measures['hatch']['stroke_mm_median'], measures['hatch']['gap_mm_median']))
    text = ('FINDINGS CHECK (Day 11, D-D11-2). The owner picked a SKETCH (B-1.3, Ẓilāl). On Day 9 the jury judged a BUILD made '
            'from it, which redrew much of it; its findings are listed below. Decide for EACH finding whether it is '
            'PRESENT IN THE SKETCH. Each image is one region at print size: THE SKETCH above the white rule, THE BUILD '
            'below (the build only to show what the finding meant). Images, in order: %s. A finding about something the '
            'build redrew (its type, its logo position, its hatch) is present only if the sketch shows the same fault. '
            'For a present finding say what answers it: "refinement" (an image edit of the sketch keeping its '
            'composition, hero and colours can fix it), "master" (the master\'s own rules fix it: live small words, the '
            'traced logotype, the hatch fitted as engine lines within the press limits, local inpainting under a line) or '
            '"none". Answer in JSON.\n\nTHE FINDINGS:\n%s\n\n%s' % (
                ', '.join('%d %s' % (i + 1, k) for i, k in enumerate(crops)), listing, facts))
    look = call('zilal/findings-check', [{'type': 'text', 'text': text}] + [b for b, _ in blocks], FINDINGS_SCHEMA)
    look['sent'] = [dict(i, crop=k, dpi=crops[k][1]) for (_, i), k in zip(blocks, crops)]
    present = []
    if look['payload'] is not None:
        present = [f for f in look['payload']['findings'] if f['present_in_sketch']]
    record = {'schema': 'day11_findings_check/1', 'pick': {'path': lm.rel(PICK), 'sha256': PICK_SHA256},
              'build_verdict': lm.rel(BUILD / 'jury' / 'verdict.json'), 'findings': findings, 'measured': measures,
              'hatch_fft': lm.rel(out / 'hatch-fft.png'), 'look': look,
              'present': present, 'answered_by_the_refinements': [f['finding'] for f in present
                                                                  if f['answered_by'] == 'refinement']}
    lm.write_json(out / 'findings.json', record)
    return record


# --- D-D11-2: the one refinement round ---------------------------------------------------------------------------------

REFINE = OUT / 'refine'
IMAGE_PREFIX = 'day12/images/'               # [Day 12] (Day 11's: 'day11/images/')
IMAGE_CAP_USD = 6.00                 # the reservation cap over all of Day 11's pictures (the owner's limits are checked
                                     # on settled spend before each call, by the runner)
IMAGE_SIZE = '1536x1024'
IMAGE_QUALITY = 'high'
BAND_PX = 27                         # the sketch's own frame: the lid is the 1536 × 970 between two 27 px bands
RANK_PREFIX = 'day12/ranking/'               # [Day 12] (Day 11's: 'day11/ranking/')
RANK_CAP_USD = 1.50
DAY8_ANCHORS = REPO / 'docs' / 'audit' / 'day-8' / 'jury' / 'anchors.json'
REJECTED_ANCHORS = (REPO / 'bbrose_design_os' / 'media' / 'generated' / 'task_124_var_1.png',
                    REPO / 'bbrose_design_os' / 'media' / 'generated' / 'task_142_var_1_readable.png')
BAR = ('THE BAR (the owner, D-D8-3): a $1B prestige cosmetics house. Modern and professional; minimal in type, layout and '
       'colour; crafted in the artwork — a design that looks easy to make is rejected; restraint in the branding; never one '
       'colour family absorbing everything. Judged against the best products on the market today.')

REFINE_CORE = (
    "EDIT image 1, keeping it. Image 1 is the owner's chosen design: flat print artwork of the closed lid of a prestige "
    "eyeshadow palette, 190 × 120 mm, front-on, the lid the 1536 × 970 area between the 27 px bands at the top and bottom "
    "(the bands continue the ground and hold nothing). Image 2 is the BBROSE logo, for reference only.\n\n"
    "KEEP EXACTLY, in place and at size: the hatched rose-gold hero ظلال with its outline and its diagonal hatch; the small "
    "Arabic words باليت (above it, right) and العيون (below it, left); the BBROSE logo at the top right; \"Enchanted Rose\" "
    "and \"EYESHADOW PALETTE\" at the lower left; \"18 SHADES\" and \"27 g ℮ 0.95 oz\" at the bottom right — the same words, "
    "letters, colours and positions; the deep indigo ground; the stones' own colours (the palette's shades: rose, coral, "
    "lilac, violet and teal). Every word stays on clear indigo; no stone touches a letter.\n\n"
    "CHANGE ONLY THE MARBLING:\n"
    "1. Render the stones as true floated-stone marbling (battal, ebru): colour floated on the indigo size and lifted "
    "onto paper — thin veins between the stones, crisp drag edges where the comb pulled the colour, cut-mineral facets "
    "with clean sharp boundaries. Not pebbles, not cobblestones, not terrazzo, no crackle texture inside the stones, no "
    "porous lace rims.\n"
    "2. Break the mirrored top-left and bottom-right corners into an asymmetric drift: {drift}\n"
    "3. Part the stones under \"18 SHADES\" and the net contents: a clear flat indigo pocket at least 4 mm around each "
    "line.\n\n"
    "Nothing new: no petals, flowers or roses, no frame, no border, no extra words or marks, no 3D, no perspective.")
DRIFTS = (
    'a gentle asymmetry — the top-left field enters from the left edge larger and looser, the bottom-right field thinner, '
    'trailing along the bottom edge toward the right.',
    'one current — the stones enter at the top-left edge and drift down the left side and along the bottom edge as one '
    'flowing current that thins toward the lower right; the top right and the centre stay clear indigo.',
    'a bold drift — a wide current of floated stones sweeps in from the top-left corner and leaves along the bottom-right '
    'edge, breaking into a scatter of small stones and fine veins as it travels; one side heavier than the other, never '
    'mirrored.')


def padded_input(dest):
    """The edit's input: the pick inside its own 1536 × 1024 frame again — its first and last rows' edges mirrored into
    the two 27 px bands (OpenCV BORDER_REFLECT_101), the 970 rows between them the pick's bytes unchanged."""
    pick = load_pick()
    framed = cv2.copyMakeBorder(pick, BAND_PX, BAND_PX, 0, 0, cv2.BORDER_REFLECT_101)
    if not np.array_equal(framed[BAND_PX:-BAND_PX], pick):
        raise AssertionError('the frame moved a pixel of the pick')
    Image.fromarray(framed).save(dest)
    return dest


def refine_prompt(n):
    return REFINE_CORE.format(drift=DRIFTS[n - 1])


def refinement(n, *, client):
    """Refinement R<n> (n 1–3): one gpt-image-2 high edit through the image guard and the ledger, the pick in its frame
    and the approved logo the only inputs; its lid the frame's middle 970 rows. Resumes: a refinement already made is
    read back, never bought twice."""
    import hashlib
    import shutil
    from contextlib import ExitStack
    from django.conf import settings
    from apps.pipeline.services.spend_reservation import paid_operation
    dest = REFINE / ('R%d' % n)
    done = dest / 'result.json'
    if done.exists():
        return json.loads(done.read_text(encoding='utf-8'))
    dest.mkdir(parents=True, exist_ok=True)
    framed = padded_input(REFINE / 'input-framed.png')
    logo_path, logo_sha = image_guard.APPROVED_LOGO
    items = [{'role': "the owner's pick B-1.3 in its own frame (the edit's input)", 'path': str(framed)},
             {'role': 'the approved BBROSE logo', 'path': str(logo_path)}]
    prompt = refine_prompt(n)
    (dest / 'request.json').write_text(json.dumps(
        {'model': settings.IMAGE_MODEL, 'quality': IMAGE_QUALITY, 'size': IMAGE_SIZE, 'inputs': items,
         'framed_from': {'path': lm.rel(PICK), 'sha256': PICK_SHA256}, 'logo_sha256': logo_sha,
         'drift': DRIFTS[n - 1], 'prompt': prompt}, ensure_ascii=False, indent=1) + '\n')
    operation = IMAGE_PREFIX + 'zilal/refine/R%d' % n

    def invoke(checked):
        api = client
        if api is None:
            from openai import OpenAI
            api = OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=0, timeout=400)
        with ExitStack() as stack:
            files = [stack.enter_context(open(i['path'], 'rb')) for i in checked]
            response = paid_operation(api.images.edit, provider='openai', operation=operation,
                                      reservation_prefix=IMAGE_PREFIX, reservation_cap=IMAGE_CAP_USD,
                                      model=settings.IMAGE_MODEL, image=files, prompt=prompt, n=1, size=IMAGE_SIZE,
                                      quality=IMAGE_QUALITY)
        saved = response._rescue_paid_images
        if len(saved) != 1:
            raise RuntimeError('the paid response is kept, but exactly one picture was not recovered')
        shutil.copyfile(saved[0], dest / 'sketch.png')
        return {'reservation_id': response._rescue_reservation_id, 'usage': response.model_dump(mode='json')['usage'],
                'output_sha256': hashlib.sha256((dest / 'sketch.png').read_bytes()).hexdigest()}

    result = image_guard.guarded_call(invoke, operation=operation, inputs=items, prompt=prompt, quality=IMAGE_QUALITY,
                                      size=IMAGE_SIZE, picture='zilal refinement R%d' % n)
    full = np.asarray(Image.open(dest / 'sketch.png').convert('RGB'))
    if full.shape[:2] != (PICK_PX[1] + 2 * BAND_PX, PICK_PX[0]):
        raise ValueError('R%d came back %d × %d, not 1536 × 1024' % (n, full.shape[1], full.shape[0]))
    Image.fromarray(full[BAND_PX:-BAND_PX]).save(dest / 'lid.png')
    record = dict(result, refinement='R%d' % n, sketch=lm.rel(dest / 'sketch.png'), lid=lm.rel(dest / 'lid.png'),
                  lid_sha256=lm.sha256(dest / 'lid.png'), drift=DRIFTS[n - 1], prompt=prompt)
    done.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n')
    return record


def anchors():
    """The fixed anchors every ranking sends (Day 8's anchors.json: the two fixed launched lids; the two renders the
    client's leadership rejected), as ``jury.anchor_blocks`` sends them."""
    from apps.pipeline.services import jury
    record = json.loads(DAY8_ANCHORS.read_text(encoding='utf-8'))
    fixed = [REPO / 'bbrose_design_os' / a['crop'] for a in record['anchors'] if a['role'] == 'fixed']
    return jury.anchor_blocks(fixed, list(REJECTED_ANCHORS))


SILHOUETTE_CLOSE_PX = 9                 # the hatch's indigo gaps (under 2 px) closed, so the letters read as solids


def silhouette(gold):
    """The hero's letters as solids: the rose gold closed over its hatch gaps, the shapes' holes filled, the specks
    under 400 px dropped."""
    closed = cv2.morphologyEx(gold.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((SILHOUETTE_CLOSE_PX,) * 2, np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(closed, 8)
    keep = np.zeros_like(closed)
    for i in range(1, n):
        if stats[i, 4] >= 400:
            keep[labels == i] = 1
    contours, _ = cv2.findContours(keep, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    solid = np.zeros_like(keep)
    cv2.drawContours(solid, contours, -1, 1, thickness=-1)
    return solid.astype(bool)


def kept_measures(path):
    """What the code measures on a lid for the ranking: the hero kept (the rose-gold hero's IoU with the pick's) and the
    stone under each small line."""
    pick = load_pick()
    other = np.asarray(Image.open(path).convert('RGB'))
    own = ink_boxes(pick)
    x0, y0, x1, y1 = own['hero']
    a, b = (silhouette(masks(img)['gold'][y0:y1, x0:x1]) for img in (pick, other))
    iou = float((a & b).sum() / max((a | b).sum(), 1))
    stones = stones_under(other, own, ('name', 'eyeshadow', 'shades', 'net', 'baliyt', 'aleyoun'))
    return {'hero_iou_with_the_pick': round(iou, 3), 'stone_share_under_small_lines': stones}


def rank_round(*, client):
    """J1 ranks the pick (sketch 1) beside its three refinements (2–4) with the fixed anchors (``rank_sketches_v2``, rubric
    v2), the code's measures under each; written to refine/ranking.json. The highest-ranked is the pick unless the
    owner names one (``PICK`` in the round's folder)."""
    from apps.pipeline.services import jury
    lids = [PICK] + [REPO / json.loads((REFINE / ('R%d' % n) / 'result.json').read_text())['lid'] for n in (1, 2, 3)]
    names = ['the original sketch B-1.3', 'R1', 'R2', 'R3']
    checks = []
    for name, path in zip(names, lids):
        m = kept_measures(path)
        checks.append('%s: the hero kept (IoU of its letters, as solids, with the pick\'s %.3f); stone under each line (its box '
                      'grown 1 mm) %s' % (
            name, m['hero_iou_with_the_pick'], m['stone_share_under_small_lines']))
    direction = json.loads((REPO / 'docs' / 'audit' / 'day-9' / 'directions' / 'B-1.json').read_text(encoding='utf-8'))
    findings = json.loads((OUT / 'findings' / 'findings.json').read_text(encoding='utf-8'))
    present = ', '.join('%d' % f['finding'] for f in findings['present'])
    spec = ((REPO / 'docs' / 'audit' / 'day-9' / 'directions' / 'B-1.md').read_text(encoding='utf-8') +
            '\n\nTHE ROUND (Day 11, D-D11-2): sketch 1 is the owner\'s pick as it is; sketches 2–4 are three refinements '
            'of it, edits that keep its composition, hero, words and colours and answer the jury\'s findings present in '
            'it (%s): the marbling as true floated stone (thin veins, crisp drag edges, cut-mineral facets, not pebbles '
            'or terrazzo), the mirrored corners broken into an asymmetric drift, a clear indigo pocket under the small '
            'lines. Rank the four: which is the best lid to master? A refinement that loses the hero, the words or the '
            'colours ranks below the original.' % present)
    return jury.rank_sketches_v2(lids, anchors=anchors(), facts=direction['facts'] + '\n' + BAR, spec=spec,
                                 direction_idea='B-1: ' + direction['idea'], operation=RANK_PREFIX + 'zilal-lid',
                                 destination=REFINE / 'ranking.json', rubric_version='v2', effort='medium',
                                 reservation_prefix=RANK_PREFIX, reservation_cap=RANK_CAP_USD, checks=checks,
                                 client=client)


# --- D-D11-3.1: ظلال, the hero — its silhouette traced, its hatch fitted, its foil and relief ---------------------------

MASTER_PICK = REFINE / 'R3' / 'lid.png'          # the pick (refine/pick.json): R3, refined from B-1.3
TRACE_SCALE = 8
TRACE_SPECK_MM2 = 0.05
RIM_MM = 0.40                           # the sketch's solid rim inside the silhouette (measured 3.5 px, 0.43 mm)
GROOVE_MM = 0.22                        # the indigo groove between the rim and the hatch (the sketch's 0.19 mm, held at
                                        # the press's 0.2 mm gap with a 0.02 mm margin)
HATCH_GAP_MM = 0.22                     # the hatch's gap: the press's 0.2 mm with a 0.02 mm margin
HATCH_STROKE_MIN_MM = 0.15              # D-D11-3.1: the hatch's own margin over the 0.1 mm press limit
FOIL_OPEN_R_MM = HATCH_STROKE_MIN_MM / 2.0      # parts finer than a 0.15 mm stroke opened away …
FOIL_CLOSE_R_MM = 0.105                         # … then gaps finer than 0.21 mm closed (the press's 0.2 mm held)
FIT_PITCH_SPAN = 0.05                   # the fit sweeps the pitch ± 5 % and the angle ± 2° about the FFT's reading …
FIT_ANGLE_SPAN_DEG = 2.0
FIT_TOLERANCE = 0.05                    # … and holds when it lands within 5 % of the saved measurement (D-D11 §9)
HATCH_INSET_MM = 0.70                   # the fit reads only the hatch: 0.7 mm inside the silhouette, past rim and groove


def load_master_pick():
    """The pick's pixels (R3), refused unless its bytes are the ones the round recorded (refine/pick.json)."""
    pinned = json.loads((REFINE / 'pick.json').read_text(encoding='utf-8'))['lid_sha256']
    digest = lm.sha256(MASTER_PICK)
    if digest != pinned:
        raise ValueError('not the pick: %s has sha256 %s, the round recorded %s' % (MASTER_PICK, digest, pinned))
    return np.asarray(Image.open(MASTER_PICK).convert('RGB'))


HOLE_FILL_MM2 = 1.0                    # a hole under 1 mm² inside a letter is a hatch gap left open, never a counter
                                        # (the ظ's bowl is about 100 mm²)


def fill_small_holes(alpha, hole_mm2):
    """The alpha cleaned the way the trace reads it, so the trace and its proof read the same letters: its holes under
    ``hole_mm2`` (islands of ground inside a letter) set to one — hatch gaps the grey closing left, never a letter's counter —
    and its islands of ink under 0.05 mm² (the bevel's anti-aliased glints beside an edge, which the trace drops as
    specks) set to zero."""
    ink = (alpha >= 0.5).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(ink, 8)
    alpha = alpha.copy()
    for i in range(1, n):
        if stats[i, 4] < TRACE_SPECK_MM2 * PX_PER_MM_SRC ** 2:
            alpha[labels == i] = 0.0
    ground = (alpha < 0.5).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(ground, 4)
    h, w = alpha.shape
    out = alpha.copy()
    for i in range(1, n):
        bx, by, bw, bh, area = stats[i]
        if area < hole_mm2 * PX_PER_MM_SRC ** 2 and bx > 0 and by > 0 and bx + bw < w and by + bh < h:
            out[labels == i] = 1.0
    return out


def trace_alpha(alpha, box, k=PX_PER_MM_SRC):
    """An alpha traced clean (10-08: lettering is traced): enlarged 8× by cubic interpolation, cut at one half, specks
    under 0.05 mm² dropped, potrace's smooth outlines. Rings in mm on the lid (or the wrap: ``k`` its px/mm, the alpha's
    origin the trim's top-left), and the proof against the alpha's own half contour read at 16× (``prove_trace``:
    distances both ways and the fills' IoU). The one trace of every element (the lid's, the wraps', the header's)."""
    x0, y0, x1, y1 = box
    h, w = alpha.shape
    s = TRACE_SCALE
    big = cv2.resize(alpha.astype(np.float32), (w * s, h * s), interpolation=cv2.INTER_CUBIC) >= 0.5
    n, labels, stats, _ = cv2.connectedComponentsWithStats(big.astype(np.uint8), 8)
    keep = np.zeros(n, dtype=bool)
    keep[1:] = stats[1:, 4] >= TRACE_SPECK_MM2 * (k * s) ** 2
    rings_px = lm.potrace_rings(keep[labels])
    rings = lm.map_rings(rings_px, lambda p: ((x0 + p[0] / s) / k, (y0 + p[1] / s) / k))
    proof = prove_trace(alpha, box, rings, k)
    proof['parts'] = int(keep.sum())
    return rings, proof


PROOF_SCALE = 16
TRACE_MAX_MM = 0.3                       # D-D11-3.1, as D-D10-2.3: the outline within 0.3 mm of the sketch's edges
TRACE_IOU_MIN = 0.95


def prove_trace(alpha, box, rings, k=PX_PER_MM_SRC):
    """The trace against the sketch's edges, as ``lid_master.prove_outline`` reads it (the alpha's half contour at 16×,
    distances both ways, the fills' IoU) — its reference raster cleaned exactly as the trace's own: the islands under
    0.05 mm² that the cubic enlargement rings up beside a sharp edge are dropped, as the trace drops them. ``k``: the
    alpha's px/mm (the lid's pick by default)."""
    from scipy.spatial import cKDTree
    x0, y0, x1, y1 = box
    h, w = alpha.shape
    r = PROOF_SCALE
    ref = cv2.resize(alpha.astype(np.float32), (w * r, h * r), interpolation=cv2.INTER_CUBIC) >= 0.5
    n, labels, stats, _ = cv2.connectedComponentsWithStats(ref.astype(np.uint8), 8)
    keep = np.zeros(n, dtype=bool)
    keep[1:] = stats[1:, 4] >= TRACE_SPECK_MM2 * (k * r) ** 2
    ref = keep[labels]
    contours, _ = cv2.findContours(ref.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    ref_mm = (np.concatenate([c[:, 0, :] for c in contours]).astype(np.float64) / r + [x0, y0]) / k
    geom = lm.rings_area(rings, 24)
    boundary = []
    for g in lm.parts(geom):
        for ring in [g.exterior, *g.interiors]:
            count = max(int(ring.length * k * 8), 8)
            boundary.extend(ring.interpolate(t).coords[0] for t in np.linspace(0, ring.length, count, endpoint=False))
    boundary = np.asarray(boundary)
    d_trace, _ = cKDTree(ref_mm).query(boundary)
    d_ref, _ = cKDTree(boundary).query(ref_mm)
    fill = lm.raster_fill(geom, ref.shape, (x0 / k, y0 / k), k * r)
    iou = float((fill & ref).sum() / (fill | ref).sum())
    worst = max(float(d_trace.max()), float(d_ref.max()))
    return {'trace_to_sketch_max_mm': round(float(d_trace.max()), 4),
            'trace_to_sketch_p99_mm': round(float(np.percentile(d_trace, 99)), 4),
            'sketch_to_trace_max_mm': round(float(d_ref.max()), 4),
            'sketch_to_trace_p99_mm': round(float(np.percentile(d_ref, 99)), 4),
            'iou': round(iou, 4), 'area_mm2': round(float(geom.area), 2),
            'holds': {'within_0_3_mm': bool(worst <= TRACE_MAX_MM), 'iou_0_95': bool(iou >= TRACE_IOU_MIN)},
            'reference': 'the sketch\'s edges: the alpha\'s half contour at 16× the pick, its islands under 0.05 mm² '
                         'dropped as the trace drops them'}


# --- D-D12-9: the silhouette reader — the bevel's outer dark edge, its counters closed ---------------------------------
#
# The painted heroes stand in a bevel: the hatched face, a bright rim, a thin dark crease, a grey-brown chamfer, then the
# outer dark (a shadow or a line) into the indigo ground. Day 11's reader cut L* at 32.5 and so ran along the rim, with
# loops in the crease (the tracer trial, 24 October: "the lower edges sit on the bevel's highlight"). This reader cuts at
# the ground's own L* + 7 and treats only a WIDE dark reached from the window's edge as outside, so the crease and the
# chamfer stay inside and the silhouette ends where the outer dark begins. One reader for every hero (the lid's ظلال,
# the lipstick's شفاه and أحمر, the balm's بلسم), read at 2× the sketch as the trial read them; the lid's logotype keeps
# its own trace (``name_alpha``: it is never re-traced).

READ_UP = 2                             # the heroes read at 2× the sketch (PIL Lanczos), as the tracer trial read them
BEVEL_DARK_OVER_GROUND = 7.0            # dark: L* at or under the ground's own L* + 7 (the ground ~ 8, the chamfer ≥ 20)
BEVEL_RAMP_HALF = 5.0                   # the soft cut's half width in L* (0 at dark − 5, 1 at dark + 5)
BEVEL_SMOOTH_MM = 0.06                  # L* smoothed before it is cut (the paint's grain)
BEVEL_CREASE_MM = 0.25                  # a dark line narrower than this between two lights is inside the letter (the
                                        # crease between rim and chamfer, a hatch gap, a hairline crack); a wider dark
                                        # reached from the window's edge is outside (the ground, the shadow, the outer line)
BEVEL_RING_MM = 0.8                     # the element's own mask grown 0.8 mm: its rim, crease, chamfer and tips
BEVEL_OPEN_MM = 0.15                    # the silhouette opened: a burr under 0.15 mm (the paint's grain) is no letter's
BEVEL_BLUR_MM = 0.06                    # the cut silhouette's soft edge for the trace's cubic 8× enlargement
BEVEL_GROUND_MM = 1.0                   # the ground read ≥ 1 mm from the element (its median L* and b*)
BEVEL_GROUND_MIN_PX = 100
BEVEL_STONE_CHROMA = 15.0               # in the ring a pixel of chroma over 15, L* over 20 and a hue outside the rose
BEVEL_STONE_L = 20.0                    # gold's (30–100°: the highlight's cream reads 80–90°) is a stone, never the letter
BEVEL_GOLD_HUE = (30.0, 100.0)
SEAL_MM = 0.15                          # D-D12-9: a crack under 0.15 mm into a counter is sealed and listed; a wider
                                        # opening is the letter's own and stays open
SEAL_STEP_MM = 0.01                     # the crack's width read by openings in 0.01 mm steps (at most one px of the read)
CRACK_LIGHT_L = 32.5                    # Day 11's cut (L* 10 → 55 at one half): a hairline darker than it across the
                                        # letter into a counter is listed, even where this reader reads it inside


def read_up(rgb):
    """The sketch enlarged 2× by PIL's Lanczos, as the tracer trial read the heroes (its inputs' bytes)."""
    h, w = rgb.shape[:2]
    return np.asarray(Image.fromarray(rgb).resize((w * READ_UP, h * READ_UP), Image.LANCZOS))


def mask_up(own):
    """An element's own mask (whole picture) at the read's 2×, nearest."""
    return cv2.resize(own.astype(np.uint8), (own.shape[1] * READ_UP, own.shape[0] * READ_UP),
                      interpolation=cv2.INTER_NEAREST).astype(bool)


def odd_disc(diameter_px):
    """An elliptical disc of the odd whole size nearest ``diameter_px`` (at least 1)."""
    d = max(int(round(diameter_px)), 1)
    d += 1 - d % 2
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (d, d))


def bevel_ground(lab, core, k):
    """The ground beside an element: the median L* and b* of the window's pixels at least 1 mm from its own mask; refused
    when the window holds too little ground to read (never an assumed value)."""
    far = ~cv2.dilate(core.astype(np.uint8), odd_disc(2 * BEVEL_GROUND_MM * k + 1)).astype(bool)
    if far.sum() < BEVEL_GROUND_MIN_PX:
        raise ValueError('the window holds %d px of ground at least %.1f mm from the element: too few to read'
                         % (int(far.sum()), BEVEL_GROUND_MM))
    return {'L': round(float(np.median(lab[..., 0][far])), 3), 'b': round(float(np.median(lab[..., 2][far])), 3)}


CRACK_READ_UP = 4                       # the crack's neck read on a 4× cubic enlargement of its L* (a quarter px steps)


def _crack_width(light_raw, level, crack, counter, outside, k):
    """The narrowest width (mm) of the dark joining a counter to the outside: on a 4× cubic enlargement of the L*
    around the crack, read at ``level`` (its half darkness), the widest opening (0.01 mm steps) of its dark ∪ the
    counter ∪ the outside that still joins the counter to the outside."""
    ys, xs = np.nonzero(crack)
    pad = int(np.ceil(2 * BEVEL_CREASE_MM * k)) + 4
    h, w = crack.shape
    y0, y1 = max(int(ys.min()) - pad, 0), min(int(ys.max()) + pad + 1, h)
    x0, x1 = max(int(xs.min()) - pad, 0), min(int(xs.max()) + pad + 1, w)
    u = CRACK_READ_UP
    size = ((x1 - x0) * u, (y1 - y0) * u)

    def big(m):
        return cv2.resize(m[y0:y1, x0:x1].astype(np.uint8), size, interpolation=cv2.INTER_NEAREST).astype(bool)

    dark4 = cv2.resize(light_raw[y0:y1, x0:x1], size, interpolation=cv2.INTER_CUBIC) <= level
    near4 = big(cv2.dilate(crack.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool))
    counter4, outside4 = big(counter), big(outside)
    union = ((dark4 & near4) | counter4 | outside4).astype(np.uint8)
    joined_at = 0.0
    for w_mm in np.arange(SEAL_STEP_MM, BEVEL_CREASE_MM + SEAL_STEP_MM, SEAL_STEP_MM):
        opened = cv2.morphologyEx(union, cv2.MORPH_OPEN, odd_disc(w_mm * k * u))
        _, lab_ = cv2.connectedComponents(opened, connectivity=8)
        a = set(np.unique(lab_[counter4 & (opened == 1)])) - {0}
        b = set(np.unique(lab_[outside4 & (opened == 1)])) - {0}
        if not a & b:
            break
        joined_at = float(w_mm)
    return round(joined_at, 3)


def bevel_alpha(rgb, window, own, k, hole_mm2):
    """D-D12-9: an element's soft alpha in its window — the silhouette the bevel's outer dark edge, its counters closed.
    L* (smoothed 0.06 mm) cut at the ground's own L* + 7; the outside every dark region WIDER than 0.25 mm reached from
    the window's edge (a thinner dark between two lights — the crease, a hatch gap, a hairline — is inside the letter);
    a counter an enclosed wide dark of at least ``hole_mm2``; the element's own mask (``own``, whole picture) grown
    0.8 mm, stones in that ring outside. A counter the unsmoothed dark joins to the outside is sealed if the join is
    under 0.15 mm across and listed; a wider join is the letter's own opening and is kept open. Burrs under 0.15 mm
    opened away, specks under 0.05 mm² dropped. Returns (alpha, record)."""
    x0, y0, x1, y1 = window
    lab = lm.srgb_to_lab(rgb[y0:y1, x0:x1])
    light_raw = lab[..., 0].astype(np.float32)
    light = cv2.GaussianBlur(light_raw, (0, 0), BEVEL_SMOOTH_MM * k)
    chroma = np.hypot(lab[..., 1], lab[..., 2])
    hue = np.degrees(np.arctan2(lab[..., 2], lab[..., 1])) % 360
    core = own[y0:y1, x0:x1]
    ground = bevel_ground(lab, core, k)
    mine = cv2.dilate(core.astype(np.uint8), odd_disc(2 * BEVEL_RING_MM * k + 1)).astype(bool)
    stone = ((chroma > BEVEL_STONE_CHROMA) & (light_raw > BEVEL_STONE_L)
             & ((hue < BEVEL_GOLD_HUE[0]) | (hue > BEVEL_GOLD_HUE[1])) & mine & ~core)
    level = ground['L'] + BEVEL_DARK_OVER_GROUND
    soft = np.clip((light - (level - BEVEL_RAMP_HALF)) / (2 * BEVEL_RAMP_HALF), 0, 1)
    dark = ((soft < 0.5) | ~mine | stone).astype(np.uint8)
    wide = cv2.morphologyEx(dark, cv2.MORPH_OPEN, odd_disc(BEVEL_CREASE_MM * k))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(wide, connectivity=8)
    edge = set(np.unique(np.r_[labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]])) - {0}
    outside = np.isin(labels, sorted(edge))
    counters = [i for i in range(1, n) if i not in edge and stats[i, 4] >= hole_mm2 * k * k]
    sil = ~outside & ~np.isin(labels, counters)
    # the joins: the unsmoothed dark (and, listed only, Day 11's darker-than-32.5 hairlines) between a counter and the
    # outside
    raw = (light_raw <= level) | ~mine | stone
    hair = (light_raw <= CRACK_LIGHT_L) | ~mine | stone
    seals = []
    # a crack's width is read at its half darkness: midway between the ground's L* and the letter's own median L*
    half_dark = (ground['L'] + float(np.median(light_raw[core]))) / 2.0
    to_outside = cv2.distanceTransform((~outside).astype(np.uint8), cv2.DIST_L2, 5)
    for i in counters:
        region = labels == i
        to_counter = cv2.distanceTransform((~region).astype(np.uint8), cv2.DIST_L2, 5)
        for kind, darkish in (('dark', raw), ('hairline', hair)):
            _, comp = cv2.connectedComponents(darkish.astype(np.uint8), connectivity=8)
            joined = (set(np.unique(comp[region & darkish])) - {0}) & (set(np.unique(comp[outside & darkish])) - {0})
            between = np.isin(comp, sorted(joined)) & ~outside & ~region
            if not joined or not between.any():
                continue
            # the crack: the joined dark's corridor between the counter and the outside (their distances' sum within
            # two crease widths of its least), never another crease that reaches the outside elsewhere
            span = to_counter + to_outside
            crack = between & (span <= span[between].min() + 2 * BEVEL_CREASE_MM * k)
            width = _crack_width(light_raw, half_dark, crack, region, outside, k)
            ys, xs = np.nonzero(crack)
            row = {'counter_mm2': round(float(stats[i, 4]) / k / k, 3), 'read_as': kind, 'width_mm': width,
                   'at_mm': [round(float((x0 + xs.mean()) / k), 3), round(float((y0 + ys.mean()) / k), 3)],
                   'sealed': bool(kind == 'hairline' or width < SEAL_MM)}
            if kind == 'dark' and width >= SEAL_MM:
                sil &= ~(crack | region)          # the letter's own opening, kept open
            seals.append(row)
            break
    sil = cv2.morphologyEx(sil.astype(np.uint8), cv2.MORPH_OPEN, odd_disc(BEVEL_OPEN_MM * k))
    m, parts_, pstats, _ = cv2.connectedComponentsWithStats(sil, connectivity=8)
    for i in range(1, m):
        if pstats[i, 4] < TRACE_SPECK_MM2 * k * k:
            sil[parts_ == i] = 0
    alpha = cv2.GaussianBlur(sil.astype(np.float32), (0, 0), BEVEL_BLUR_MM * k)
    kept_open = [r for r in seals if not r['sealed']]
    record = {'reader': 'zilal_master.bevel_alpha (D-D12-9: the bevel\'s outer dark edge, counters closed)',
              'px_per_mm': round(float(k), 4), 'ground': ground, 'dark_level_L': round(float(level), 3),
              'crease_mm': BEVEL_CREASE_MM, 'ring_mm': BEVEL_RING_MM, 'seal_under_mm': SEAL_MM,
              'counters_closed': len(counters) - len(kept_open), 'openings_kept': len(kept_open), 'joins': seals}
    return alpha, record


OUTER_EDGE_STEP_MM = 0.005


def prove_outer_edge(rgb, rings, k, ground):
    """D-D12-9's own-edge proof, read on the sketch's pixels independently of the alpha: at points along the traced
    outline (every 0.05 mm), the L* profile (σ 0.5 px) along the outward normal (±0.6 mm, cubic), and the bevel's outer
    dark edge — the descent into the dark (the ground's L* + 7) nearest the outline that is followed by at least 0.25 mm
    of dark (or the window's end): the outer dark, never the crease. Holds when every point lies within 0.3 mm and at
    most 0.5 % find no such edge (``lid_master.prove_outline_on_pick``, the strong fall nearest the outline, is reported
    beside it: on a wide bevel its strongest fall is the rim's, inside)."""
    from shapely import contains_xy
    lightness = cv2.GaussianBlur(lm.srgb_to_lab(rgb)[..., 0].astype(np.float32), (0, 0), 0.5)
    geom = lm.rings_area(rings, 24)
    offs = np.arange(-lm.EDGE_WINDOW_MM, lm.EDGE_WINDOW_MM + 1e-9, OUTER_EDGE_STEP_MM)
    level = ground['L'] + BEVEL_DARK_OVER_GROUND
    run = int(round(BEVEL_CREASE_MM / OUTER_EDGE_STEP_MM))
    at = np.abs(offs - OUTER_EDGE_STEP_MM / 2)
    dists, where = [], []
    for g in lm.parts(geom):
        for ring in [g.exterior, *g.interiors]:
            count = max(int(ring.length / 0.05), 8)
            ts = np.linspace(0, ring.length, count, endpoint=False)
            pts = np.array([ring.interpolate(t).coords[0] for t in ts])
            ahead = np.array([ring.interpolate((t + 0.02) % ring.length).coords[0] for t in ts])
            tan = ahead - pts
            tn = np.hypot(tan[:, 0], tan[:, 1])
            ok = tn > 1e-9
            nx, ny = -tan[ok, 1] / tn[ok], tan[ok, 0] / tn[ok]
            px, py = pts[ok, 0], pts[ok, 1]
            inward = contains_xy(geom, px + 0.03 * nx, py + 0.03 * ny)
            nx = np.where(inward, -nx, nx)
            ny = np.where(inward, -ny, ny)
            xs = (px[:, None] + offs[None, :] * nx[:, None]) * k - 0.5
            ys = (py[:, None] + offs[None, :] * ny[:, None]) * k - 0.5
            prof = map_coordinates(lightness, [ys.ravel(), xs.ravel()], order=3, mode='nearest').reshape(xs.shape)
            dark = prof <= level
            m = dark.shape[1]
            runlen = np.zeros(dark.shape, dtype=np.int32)
            acc = np.zeros(dark.shape[0], dtype=np.int32)
            for j in range(m - 1, -1, -1):
                acc = np.where(dark[:, j], acc + 1, 0)
                runlen[:, j] = acc
            long_enough = runlen >= np.minimum(run, m - np.arange(m))[None, :]
            descent = np.zeros(dark.shape, dtype=bool)
            descent[:, 1:] = ~dark[:, :-1] & dark[:, 1:] & long_enough[:, 1:]
            dists.append(np.where(descent, at[None, :], np.inf).min(axis=1))
            where.append(np.c_[px, py])
    every = np.concatenate(dists)
    pts_all = np.concatenate(where)
    finite = np.isfinite(every)
    d = every[finite]
    over = np.nonzero(finite & (every > TRACE_MAX_MM))[0]
    return {'reference': 'the sketch\'s own L*: along each outward normal the descent into the dark (the ground\'s L* + 7) '
                         'nearest the outline followed by ≥ 0.25 mm of dark — the bevel\'s outer dark edge (D-D12-9), '
                         'independent of the alpha', 'points': int(len(every)), 'unread': int((~finite).sum()),
            'unread_share': round(float((~finite).mean()), 5), 'window_mm': lm.EDGE_WINDOW_MM,
            'max_mm': round(float(d.max()), 4), 'p99_mm': round(float(np.percentile(d, 99)), 4),
            'median_mm': round(float(np.median(d)), 4), 'over_0_3_mm': int(len(over)),
            'within_0_3_mm_share': round(float(np.mean(d <= TRACE_MAX_MM)), 5),
            'over_points_mm': [[round(float(pts_all[i, 0]), 3), round(float(pts_all[i, 1]), 3), round(float(every[i]), 4)]
                               for i in over],
            'holds': bool(d.max() <= TRACE_MAX_MM and (~finite).mean() <= lm.EDGE_UNREAD_MAX)}


def read_hero(rgb, own, window, k, hole_mm2):
    """One hero read and traced by the shared reader (D-D12-9) at 2× the sketch: ``rgb`` the sketch, ``own`` the hero's
    own mask on it, ``window`` its window (sketch px), ``k`` the sketch's px/mm. Returns (rings in mm, proof) — the
    proof against the alpha (``prove_trace``), the reader's record (its ground, counters and joins), the outer dark
    edge's proof (``prove_outer_edge``) and Day 11's own-edge reading beside it."""
    up = read_up(rgb)
    k2 = k * READ_UP
    window2 = [v * READ_UP for v in window]
    alpha, reader = bevel_alpha(up, window2, mask_up(own), k2, hole_mm2)
    rings, proof = trace_alpha(alpha, window2, k2)
    proof['reader'] = reader
    proof['outer_dark_edge'] = prove_outer_edge(up, rings, k2, reader['ground'])
    return rings, proof


def trace_hero(pick):
    """D-D11-3.1 with D-D12-9's reader: the hero's silhouette (the bevel's outer dark edge, its counters closed) read at
    2×, traced, proven against its alpha (0.3 mm, IoU 0.95), on the bevel's outer dark edge (``prove_outer_edge``) and,
    beside it, Day 11's reading against the pick's own edges (``lid_master.prove_outline_on_pick``)."""
    own = np.zeros(pick.shape[:2], dtype=bool)
    x0, y0, x1, y1 = WINDOWS['hero']
    own[y0:y1, x0:x1] = element_mask(pick, 'hero', masks(pick))
    rings, proof = read_hero(pick, own, WINDOWS['hero'], PX_PER_MM_SRC, HOLE_FILL_MM2)
    proof['against_the_pick_itself'] = lm.prove_outline_on_pick(pick, rings)
    return rings, None, proof


def letters_geometry(rings):
    """The traced rings as one shapely geometry in mm (even-odd: the ظ's bowl stays open)."""
    return lm.rings_area(rings, 24).buffer(0)


def fit_hatch(pick, letters, measured):
    """The hatch as an engine line system fitted to the sketch: inside the letters (0.7 mm in, past the rim and the
    groove) every pick pixel's offset d along the lines' normal (mm) and its L* less a 20 px mean (q, bright = a gold
    stroke); the pitch (± 5 %) and the angle (± 2°) about the FFT's reading that make Σ q·exp(2πi·d/pitch) strongest,
    and the phase where it peaks — the strokes' centres. Holds when the pitch and the angle land within 5 % of the saved
    measurement. Angles as orn_b1 reads them: 0 level, rising to the right as they grow (y down)."""
    from shapely import contains_xy
    light = lm.srgb_to_lab(pick)[..., 0].astype(np.float64)
    q_all = light - cv2.blur(light, (21, 21))
    inner = letters.buffer(-HATCH_INSET_MM)
    x0, y0, x1, y1 = (int(v * PX_PER_MM_SRC) for v in inner.bounds)
    ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
    xm, ym = (xs + 0.5) / PX_PER_MM_SRC, (ys + 0.5) / PX_PER_MM_SRC
    inside = contains_xy(inner, xm, ym)
    xm, ym, q = xm[inside], ym[inside], q_all[ys[inside], xs[inside]]
    q = q - q.mean()
    angle0 = (90.0 - measured['wave_vector_deg']) % 180.0
    pitch0 = measured['pitch_mm']
    best = None
    for angle in np.linspace(angle0 - FIT_ANGLE_SPAN_DEG, angle0 + FIT_ANGLE_SPAN_DEG, 41):
        a = np.radians(angle)
        d = xm * np.sin(a) + ym * np.cos(a)
        for pitch in np.linspace(pitch0 * (1 - FIT_PITCH_SPAN), pitch0 * (1 + FIT_PITCH_SPAN), 61):
            s = np.sum(q * np.exp(2j * np.pi * d / pitch))
            if best is None or abs(s) > best[0]:
                best = (abs(s), angle, pitch, s)
    strength, angle, pitch, s = best
    phase = (np.angle(s) / (2 * np.pi) * pitch) % pitch
    return {'angle_deg': round(float(angle), 3), 'pitch_mm': round(float(pitch), 4), 'phase_mm': round(float(phase), 4),
            'coherence': round(float(strength / np.sum(np.abs(q))), 4), 'pixels': int(len(q)),
            'measured': {'pitch_mm': pitch0, 'line_angle_deg': round(angle0, 3)},
            'pitch_off_share': round(abs(pitch - pitch0) / pitch0, 4),
            'angle_off_share': round(abs(angle - angle0) / angle0, 4),
            'holds': bool(abs(pitch - pitch0) / pitch0 <= FIT_TOLERANCE and abs(angle - angle0) / angle0 <= FIT_TOLERANCE)}


def hatch_stroke(fit):
    """The hatch's stroke: the pitch less the held gap (0.22 mm), never under 0.15 mm — if the sketch's pitch cannot
    hold both, the pitch is coarsened to the nearest that does, and said."""
    pitch = fit['pitch_mm']
    coarsened = None
    if pitch - HATCH_GAP_MM < HATCH_STROKE_MIN_MM:
        coarsened = {'from_mm': pitch, 'to_mm': round(HATCH_STROKE_MIN_MM + HATCH_GAP_MM, 4)}
        pitch = HATCH_STROKE_MIN_MM + HATCH_GAP_MM
    return {'pitch_mm': round(pitch, 4), 'stroke_mm': round(pitch - HATCH_GAP_MM, 4), 'gap_mm': HATCH_GAP_MM,
            'coarsened': coarsened}


def hero_foil(letters, fit, stroke):
    """The rose-gold hot-foil mask of the hero (D-D11-3.1): the solid rim (0.40 mm inside the silhouette), an indigo
    groove (0.22 mm), then the hatch's strokes on the fitted lines clipped to the letters inside the groove; cleaned to
    the press (parts finer than 0.15 mm opened away, gaps under 0.21 mm closed). The relief envelope is the silhouette
    itself (emboss)."""
    from apps.pipeline.services import orn_b1
    from shapely.ops import unary_union
    rim = letters.difference(letters.buffer(-RIM_MM, join_style='mitre'))
    clip = letters.buffer(-(RIM_MM + GROOVE_MM), join_style='mitre')
    bands = unary_union(orn_b1._bands(letters.bounds, angle_deg=fit['angle_deg'], pitch_mm=stroke['pitch_mm'],
                                       phase_mm=fit['phase_mm'], width_mm=stroke['stroke_mm']))
    raw = unary_union([rim, bands.intersection(clip)])
    clean = raw.buffer(-FOIL_OPEN_R_MM).buffer(FOIL_OPEN_R_MM).buffer(FOIL_CLOSE_R_MM).buffer(-FOIL_CLOSE_R_MM)
    return {'foil': clean, 'relief': letters, 'rim': rim, 'moved_mm2': round(float(clean.symmetric_difference(raw).area), 4)}


HATCH_CROP_BOX_PX = (980, 230, 1180, 400)       # a piece of the hero's stems and its diagonal: the overlay's window
HATCH_CROP_DPI = 600.0
HATCH_LINE_RGB = (0, 220, 255)


def hatch_overlay(pick, fit, stroke, letters, path, field):
    """The fitted line system drawn over the sketch at print size (600 dpi): each stroke's centre line, inside the
    letters only, as a thin cyan line on the sketch's own hatch — so the fit reads at 1 : 1 (a line on every gold stroke,
    none on the indigo gaps)."""
    from apps.pipeline.services import orn_b1
    from shapely.geometry import box as rect
    x0, y0, x1, y1 = HATCH_CROP_BOX_PX
    k = HATCH_CROP_DPI / lm.MM_PER_INCH
    box_mm = (x0 / PX_PER_MM_SRC, y0 / PX_PER_MM_SRC, x1 / PX_PER_MM_SRC, y1 / PX_PER_MM_SRC)
    w, h = int((box_mm[2] - box_mm[0]) * k), int((box_mm[3] - box_mm[1]) * k)
    img = np.asarray(Image.fromarray(pick[y0:y1, x0:x1]).resize((w, h), Image.LANCZOS)).copy()
    inside = letters.buffer(-(RIM_MM + GROOVE_MM)).intersection(rect(*box_mm))
    # the registered strokes' centre lines: the same phase field, a stroke of 0.03 mm
    centres = registered_bands(letters, fit, dict(stroke, stroke_mm=0.03), field)
    for line in [centres]:
        for part in lm.parts(line.intersection(inside)):
            if part.is_empty or part.geom_type != 'Polygon':
                continue
            ring = (np.asarray(part.exterior.coords) - box_mm[:2]) * k
            cv2.polylines(img, [np.round(ring * 16).astype(np.int32)], True, HATCH_LINE_RGB, 1, cv2.LINE_AA, shift=4)
    Image.fromarray(img).save(path, dpi=(HATCH_CROP_DPI, HATCH_CROP_DPI))
    return path


# --- D-D11-3.2 and 3.4: the small lines and the two small Arabic words, set live --------------------------------------

#: the lines as the sketch draws them: runs (each fitted on its own letters), the copy each run carries (brief 124, word
#: for word), whether it is set in capitals, and the text the face match reads (the ℮ drawn by the engine, left out)
ZLINES = {
    'eyeshadow': {'rtl': False, 'runs': ('EYESHADOW', 'PALETTE'), 'copy': 'Eyeshadow Palette', 'upper': True,
                  'match': 'EYESHADOW PALETTE'},
    'shades': {'rtl': False, 'runs': ('18', 'SHADES'), 'copy': '18 shades', 'upper': True, 'match': '18 SHADES'},
    'net': {'rtl': False, 'runs': ('27', 'g', lm.SIGN, '0.95', 'oz'), 'copy': '27 g ℮ 0.95 oz', 'upper': False,
            'match': '27g0.95oz'},
    'baliyt': {'rtl': True, 'runs': ('باليت',), 'copy': 'باليت', 'upper': False, 'match': 'باليت'},
    'aleyoun': {'rtl': True, 'runs': ('العيون',), 'copy': 'العيون', 'upper': False, 'match': 'العيون'},
}
LINE_PAD_PX = 6


def line_box(boxes, key):
    """A line's box in the pick (px): its ink box grown 6 px, the reading window its glyphs are measured in."""
    x0, y0, x1, y1 = boxes[key]
    return (x0 - LINE_PAD_PX, y0 - LINE_PAD_PX, x1 + LINE_PAD_PX, y1 + LINE_PAD_PX)


def line_units(pick, boxes, key):
    """One line's glyph units in lid mm, left to right (``lid_master.glyph_units``): Latin letters, or the Arabic word
    as one unit; and the line's soft alpha (``lid_master.light_glyph_alpha``, the cream type over its local ground)."""
    line = ZLINES[key]
    x0, y0, x1, y1 = line_box(boxes, key)
    alpha = lm.light_glyph_alpha(pick, (x0, y0, x1, y1))
    target = lm.target_glyphs(alpha)
    if line['rtl']:
        # one Arabic word: the whole line is its unit (lid_master.glyph_units cuts a line at its count − 1 widest gaps,
        # which for one word would be every gap)
        bx0, by0, bx1, by1 = lm._ink_box(target)
        units = [{'box': (bx0, by0, bx1, by1), 'mask': target[by0:by1, bx0:bx1]}]
    else:
        units = lm.glyph_units(target, False, 0)
    k = PX_PER_MM_SRC * lm.MATCH_SCALE
    for u in units:
        bx0, by0, bx1, by1 = u['box']
        u['box_mm'] = (x0 / PX_PER_MM_SRC + bx0 / k, y0 / PX_PER_MM_SRC + by0 / k,
                       x0 / PX_PER_MM_SRC + bx1 / k, y0 / PX_PER_MM_SRC + by1 / k)
    return units, alpha


def runs_of(key, units):
    """The units grouped into the line's runs: a Latin run takes one unit per character that is not a space (a period
    its own), the Arabic run its word."""
    line = ZLINES[key]
    out, i = [], 0
    for text in line['runs']:
        n = len(text.split()) if line['rtl'] else len([c for c in text if not c.isspace()])
        members = units[i:i + n]
        i += n
        b = np.asarray([m['box_mm'] for m in members])
        out.append({'text': text, 'units': members,
                    'box_mm': (float(b[:, 0].min()), float(b[:, 1].min()), float(b[:, 2].max()), float(b[:, 3].max()))})
    if i != len(units):
        raise ValueError('%s: %d units read, %d placed by its runs' % (key, len(units), i))
    return out


def match_units(pick, boxes, key):
    """The units the face match reads: every glyph but the ℮ (the engine draws the sign)."""
    units, _ = line_units(pick, boxes, key)
    return [u for r in runs_of(key, units) if r['text'] != lm.SIGN for u in r['units']]


def rank_pooled(pairs, faces, rtl):
    """One ranking over several lines (D-D11-3.4: ONE face for all of them): each face's outline distance pooled over
    every glyph or word of every line (``lid_master.score_face``); a face that cannot draw one of the lines unit for
    unit is left out."""
    ranked = []
    for stem, face in faces.items():
        weights = [None]
        if face['variable'] and 'wght' in face['axes']:
            lo, _, hi = face['axes']['wght']
            weights = [w for w in lm.MATCH_WEIGHTS if lo <= w <= hi]
        for w in weights:
            sums = [lm.score_face(units, face['path'], text, w, rtl) for units, text in pairs]
            if any(x is None for x in sums):
                continue
            dist = sum(x['dist_sum_px'] for x in sums) / sum(x['edge_px'] for x in sums) / (PX_PER_MM_SRC * lm.MATCH_SCALE)
            iou = sum(x['inter_px'] for x in sums) / sum(x['union_px'] for x in sums)
            ranked.append({'stem': stem, 'wght': w, 'house': face['house'], 'distance': round(dist, 4),
                           'iou': round(iou, 4)})
    ranked.sort(key=lambda r: r['distance'])
    return {'measured': len(ranked), 'ranked': ranked}


def face_record(pick, boxes):
    """D-D8-5, measured: ONE Latin face for the three small lines (pooled; D-D11-3.4) and ONE Arabic face for باليت and
    العيون (pooled; D-D11-3.2), each the closest licensed face, a house face winning a near-tie (within 5 %)."""
    latin = rank_pooled([(match_units(pick, boxes, k), ZLINES[k]['match']) for k in ('eyeshadow', 'shades', 'net')],
                        lm.licensed_faces(False), False)
    arabic = rank_pooled([(match_units(pick, boxes, k), ZLINES[k]['match']) for k in ('baliyt', 'aleyoun')],
                         lm.licensed_faces(True), True)
    return {'latin': {'chosen': lm.choose_face(latin), 'top': latin['ranked'][:10], 'measured': latin['measured'],
                      'lines': ['eyeshadow', 'shades', 'net']},
            'arabic': {'chosen': lm.choose_face(arabic), 'top': arabic['ranked'][:10], 'measured': arabic['measured'],
                       'lines': ['baliyt', 'aleyoun']},
            'distance': 'the symmetric mean distance (mm on the lid) between the sketch\'s glyph outlines and the '
                        'face\'s, each glyph placed by its best overlap, pooled over the lines; the faces of the house '
                        'and the D-D7-1 GRANTED pool only'}


ARABIC_WEIGHTS = (('Tajawal-Light', 300.0), ('Tajawal-Regular', 400.0), ('Tajawal-Medium', 500.0),
                  ('Tajawal-Bold', 700.0))


def stroke_width_px(mask):
    """A mask's mean stroke width (px): twice its area over its outline's length."""
    m = mask.astype(np.uint8)
    edge = cv2.Canny(m * 255, 50, 150).astype(bool).sum()
    return 2.0 * float(m.sum()) / max(float(edge), 1.0)


def arabic_weight(pick, boxes):
    """Repair 1 of D-D11-3.7 (the eye read باليت and العيون heavier than the sketch): among the measured face's weights
    (Tajawal, house), the one whose stroke, drawn at each word's own size, is nearest the sketch's stroke — read as
    twice the area over the outline at the match scale. Returns the ratios and the weight chosen."""
    from apps.ire import font_roles
    cat = font_roles.catalogue()
    ratios = {}
    for stem, _ in ARABIC_WEIGHTS:
        per = []
        for key in ('baliyt', 'aleyoun'):
            target = line_units(pick, boxes, key)[0][0]['mask']
            probe = lm.draw_line(cat[stem]['path'], ZLINES[key]['copy'], 100.0, 0.0, None, True)
            drawn = lm.draw_line(cat[stem]['path'], ZLINES[key]['copy'], 100.0 * target.shape[0] / probe.shape[0], 0.0,
                                 None, True)
            per.append(stroke_width_px(drawn) / stroke_width_px(target))
        ratios[stem] = round(float(np.mean(per)), 3)
    stem, weight = min(ARABIC_WEIGHTS, key=lambda sw: abs(ratios[sw[0]] - 1.0))
    return {'stroke_ratio_to_the_sketch': ratios, 'stem': stem, 'weight': weight,
            'said': 'the stroke drawn at the sketch\'s size against the sketch\'s own: %s is nearest (%.2f×)' % (
                stem, ratios[stem])}


def ensure_derived(source_stem, weight):
    """A Tajawal weight in its emitter-capable form (``arabic_display.derive``), made where var/ holds none."""
    from apps.ire import arabic_display, font_instances
    pf = source_stem.replace('Tajawal-', 'TajawalPF-')
    if font_instances.derived_face(pf, None) is None:
        arabic_display.derive(arabic_display.source_of({'key': 'tajawal-%d' % int(weight), 'family': 'Tajawal',
                                                        'stem': source_stem, 'weight': weight}))
    return pf


def chosen_faces(faces):
    """The two chosen faces as the engine resolves them: the Latin as measured; the Arabic in its emitter-capable form
    (``arabic_display.derive``: TajawalPF-Medium from Tajawal Medium, the face Day 10 derived)."""
    from apps.ire import font_roles
    latin = faces['latin']['chosen']
    arabic = faces['arabic']['chosen']
    if not arabic['stem'].startswith('Tajawal-'):
        raise ValueError('the Arabic face measured is %s; only Tajawal is derived emitter-capable here' % arabic['stem'])
    source, a_weight = arabic['stem'], lm.ARABIC_WEIGHT
    if 'weight_by_stroke' in faces:
        source, a_weight = faces['weight_by_stroke']['stem'], faces['weight_by_stroke']['weight']
    pf = ensure_derived(source, a_weight)
    out = {}
    for side, stem, weight in (('latin', latin['stem'], latin['wght']), ('arabic', pf, a_weight)):
        w = weight
        if w is None:
            w = lm.ARABIC_WEIGHT
        r = font_roles.resolve_line_face(stem, w)
        out[side] = {'role': r['role'], 'path': r['path'], 'label': r['label'], 'stem': stem, 'weight': w}
    return out


def ink_colour(pick, boxes, key):
    """A line's ink as the sketch prints it: the median of its glyphs' cores (alpha ≥ 0.9)."""
    x0, y0, x1, y1 = line_box(boxes, key)
    alpha = lm.light_glyph_alpha(pick, (x0, y0, x1, y1))
    rgb = np.median(pick[y0:y1, x0:x1][alpha >= 0.9], axis=0)
    return '#%02X%02X%02X' % tuple(int(round(v)) for v in rgb)


def fit_lines(pick, boxes, faces):
    """Every line fitted to the sketch in its chosen face (``lid_master.fit_latin_line`` / ``fit_arabic_line``): the
    sketch's units, the fit and the ink per line; the ℮'s box where the sketch draws it."""
    fits, inks, sketch = {}, {}, {}
    for key, line in ZLINES.items():
        units, _ = line_units(pick, boxes, key)
        sketch[key] = units
        runs = runs_of(key, units)
        inks[key] = ink_colour(pick, boxes, key)
        face = faces['arabic' if line['rtl'] else 'latin']
        if line['rtl']:
            fit = lm.fit_arabic_line(runs[0], face['path'])
            fit['text'] = runs[0]['text']
        else:
            fit = lm.fit_latin_line([r for r in runs if r['text'] != lm.SIGN], face['path'])
            signs = [r for r in runs if r['text'] == lm.SIGN]
            if signs:
                fit['sign'] = {'box_mm': signs[0]['box_mm'], 'height_mm': signs[0]['box_mm'][3] - signs[0]['box_mm'][1],
                               'after_run': [r['text'] for r in runs].index(lm.SIGN)}
        fit['face'] = face['label']
        fits[key] = fit
    return fits, inks, sketch


def type_nodes(fits, inks, faces):
    """The small lines and the two small Arabic words as engine nodes: each run a live TextRun in its line's face at
    its fitted size, place and tracking (the descriptor and the shade count in capitals, the copy kept as written), the
    ℮ the house's sign in the sketch's place and in reading order, each line in the sketch's own ink."""
    from apps.ire.graph import Color, Group, Path as GPath, SolidFill, TextRun
    nodes = []
    for key, fit in fits.items():
        line = ZLINES[key]
        colour = Color.from_hex(inks[key])
        if line['rtl']:
            nodes.append(TextRun(name=key, text=fit['text'], x=fit['x_mm'], y=fit['baseline_mm'],
                                 font=faces['arabic']['role'], size_pt=fit['size_pt'], color=colour, align='right',
                                 rtl=True))
            continue
        words = [w for w in line['copy'].split() if w != lm.SIGN]
        line_nodes = []
        for i, run in enumerate(fit['runs']):
            extra = {}
            if fit['tracking_em'] > 0:
                extra['tracking_em'] = fit['tracking_em']
            if line['upper']:
                extra['text_case'] = 'upper'
            line_nodes.append(TextRun(name='%s:%d' % (key, i), text=words[i], x=run['x_mm'], y=run['baseline_mm'],
                                      font=faces['latin']['role'], size_pt=fit['size_pt'], color=colour, align='left',
                                      **extra))
        if 'sign' in fit:
            segs, _ = lm.sign_segments(fit['sign']['box_mm'])
            line_nodes.insert(fit['sign']['after_run'], Group(name='%s:sign' % key, actual_text=lm.SIGN, children=[
                GPath(name=lm.SIGN, segments=segs, fill=SolidFill(color=colour), fill_rule='nonzero')]))
        nodes.extend(line_nodes)
    return Group(name='TYPE', children=nodes)


# --- D-D11-3.2/3.4/3.5: the plate cleaned under what is set live or as a vector ---------------------------------------

UP = lm.UP
LOGO_RIM_SRC_PX = 2                     # the sketch's logo carries a 1–2 px emboss rim: cleaned with it


LOGO_OFF_GROUND_DE = 6.0                # the logo's emboss shadow and highlights stand off the indigo by over ΔE00 6
LOGO_NEAR_PX = 6                        # … and lie within 6 px of its rose gold


def logo_clean_mask(pick):
    """The sketch's logo to clean, on the upscale's grid (window-local): its rose gold (``element_mask``) and all that
    the emboss draws around it — every pixel within 6 px of the gold that stands off the indigo ground by over ΔE00 6
    (its soft shadow below, its highlights above, the ® with them; read on a 3 × 3 median so the ground's grain is not
    taken) — grown 2 pick px, then one more upscaled pixel."""
    x0, y0, x1, y1 = WINDOWS['logo']
    own = element_mask(pick, 'logo', masks(pick)).astype(np.uint8)
    near = cv2.dilate(own, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * LOGO_NEAR_PX + 1,) * 2)).astype(bool)
    lab = lm.srgb_to_lab(cv2.medianBlur(pick[y0:y1, x0:x1], 3))
    off = lm.delta_e00(lab, np.broadcast_to(ground_lab(pick), lab.shape)) > LOGO_OFF_GROUND_DE
    whole = ((off & near) | own.astype(bool)).astype(np.uint8)
    grown = cv2.dilate(whole, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * LOGO_RIM_SRC_PX + 1,) * 2))
    h, w = grown.shape
    up = cv2.resize(grown, (w * UP, h * UP), interpolation=cv2.INTER_NEAREST)
    return cv2.dilate(up, np.ones((3, 3), np.uint8)).astype(bool)


DONOR_TRIES = 3000                      # the nearest 3000 clean shifts are read (Day 10 read 400): the ℮ and the logo's
                                        # big letters need ground from further away than their neighbours


def choose_donor(lab, comp, keep_out):
    """The donor for one glyph, as ``lid_master.choose_donor`` chooses it — a shift whose moved ground under the glyph
    and its ring touches nothing kept out and stays on the picture — scored on the full colour: the ΔE00 between the
    donor's median Lab and the glyph's surroundings' median, plus the donor's spread of L* (99th percentile less median,
    so a vein or a stone's edge costs), the best of the nearest 3000 that qualify."""
    ring = cv2.dilate(comp.astype(np.uint8), np.ones((2 * lm.DONOR_RING_PX + 1,) * 2, np.uint8)).astype(bool)
    ys, xs = np.nonzero(ring)
    around = lab[ring & ~comp & ~keep_out]
    target = np.median(around, axis=0)
    h, w = int(ys.max() - ys.min() + 1), int(xs.max() - xs.min() + 1)
    best, tried = None, 0
    for dy, dx in lm.donor_shifts(h, w):
        sy, sx = ys - dy, xs - dx
        if sy.min() < 0 or sx.min() < 0 or sy.max() >= lab.shape[0] or sx.max() >= lab.shape[1]:
            continue
        if keep_out[sy, sx].any():
            continue
        values = lab[sy, sx]
        median = np.median(values, axis=0)
        de = float(lm.delta_e00(median[None, None, :], target[None, None, :])[0, 0])
        score = de + float(np.percentile(values[:, 0], 99) - median[0])
        if best is None or score < best[0]:
            best = (score, dy, dx, de)
        tried += 1
        if tried >= DONOR_TRIES:
            break
    if best is None:
        raise ValueError('no clean donor ground for a glyph at %s' % [int(xs.min()), int(ys.min())])
    return {'shift_px_2x': [best[1], best[2]], 'score': round(best[0], 3), 'delta_e00': round(best[3], 3)}


def keep_out_mask(pick, shape):
    """What is never a donor: the hero's and the name's letters (they stay in the raster under their foil), grown
    4 upscaled px, on the upscale's grid."""
    m = masks(pick)
    out = np.zeros(shape, dtype=bool)
    for name in ('hero', 'name'):
        own = element_mask(pick, name, m).astype(np.uint8)
        h, w = own.shape
        big = cv2.resize(own, (w * UP, h * UP), interpolation=cv2.INTER_NEAREST)
        out |= lm.place_mask(cv2.dilate(big, np.ones((9, 9), np.uint8)).astype(bool), WINDOWS[name], shape)
    return out


def clean_plate(pick, up, boxes):
    """D-D11-3.2, 3.4, 3.5: the small lines (the ℮ with them), باليت and العيون, and the sketch's logo cleaned out of the
    upscale (``lid_master``'s method: each glyph its own donor ground, one Poisson solve per line — the donor's texture
    inside, the picture's own values on the boundary). The hero and the name stay (their raster under the foil). Returns
    the plate, the masks and the record per line."""
    shape = up.shape[:2]
    cleaned = {}
    for key in ZLINES:
        box = line_box(boxes, key)
        cleaned[key] = lm.place_mask(lm.glyph_clean_mask(lm.light_glyph_alpha(pick, box)), box, shape)
    cleaned['logo'] = lm.place_mask(logo_clean_mask(pick), WINDOWS['logo'], shape)
    keep_out = keep_out_mask(pick, shape)
    for m in cleaned.values():
        keep_out |= cv2.dilate(m.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    lab = lm.srgb_to_lab(up)
    plate = up.astype(np.float64)
    record = {}
    for key, m in cleaned.items():
        guide = plate.copy()
        n, labels = cv2.connectedComponents(m.astype(np.uint8), connectivity=8)
        donors = []
        for i in range(1, n):
            comp = labels == i
            d = choose_donor(lab, comp, keep_out)
            dy, dx = d['shift_px_2x']
            region = cv2.dilate(comp.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
            ry, rx = np.nonzero(region)
            guide[ry, rx] = up[ry - dy, rx - dx]
            donors.append(d)
        plate = lm.poisson_fill(plate, guide, m)
        ys, xs = np.nonzero(m)
        record[key] = {'glyphs': n - 1, 'pixels_filled': int(m.sum()),
                       'box_px_2x': [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1],
                       'donor_delta_e00_max': max(d['delta_e00'] for d in donors),
                       'donor_score_max': max(d['score'] for d in donors)}
    return np.clip(np.round(plate), 0, 255).astype(np.uint8), cleaned, record


# --- D-D11-3.3: "Enchanted Rose" traced; D-D11-3.5: the logo fitted -----------------------------------------------------

NAME_ALPHA_L = (10.0, 60.0)             # the name's alpha from L*: 0 at the indigo (L* ~ 9), 1 at its rose gold (~ 62)
NAME_DILATE_PX = 2
NAME_HOLE_MM2 = 0.15                    # a hole under 0.15 mm² is the gold's grain, never a counter (the e's eye is ~ 1 mm²)


def name_alpha(pick):
    """The name's soft alpha in its window: L* from the indigo (0) to its rose gold (1), only where the name's own mask
    (``element_mask``, grown 2 px) is; grain holes under 0.15 mm² filled, glints under 0.05 mm² dropped."""
    x0, y0, x1, y1 = WINDOWS['name']
    light = lm.srgb_to_lab(pick[y0:y1, x0:x1])[..., 0]
    lo, hi = NAME_ALPHA_L
    alpha = np.clip((light - lo) / (hi - lo), 0, 1).astype(np.float32)
    own = element_mask(pick, 'name', masks(pick)).astype(np.uint8)
    own = cv2.dilate(own, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * NAME_DILATE_PX + 1,) * 2)).astype(bool)
    return fill_small_holes(np.where(own, alpha, 0.0), NAME_HOLE_MM2)


def trace_name(pick):
    """D-D11-3.3: "Enchanted Rose" traced as a vector logotype as on Day 10, proven against its alpha (0.3 mm, IoU 0.95)
    and against the pick's own edges."""
    alpha = name_alpha(pick)
    rings, proof = trace_alpha(alpha, WINDOWS['name'])
    proof['against_the_pick_itself'] = lm.prove_outline_on_pick(pick, rings)
    return rings, alpha, proof


def name_measures(rings):
    """The traced name's parts left to right, its ink box, and its cap height: the E's top to the median foot of the
    parts that sit on the baseline (the lower 40 % of the feet)."""
    geom = lm.rings_area(rings, 24)
    letters = sorted(lm.parts(geom), key=lambda g: g.bounds[0])
    feet = sorted(g.bounds[3] for g in letters)
    baseline = float(np.median(feet[:max(int(len(feet) * 0.4), 1)]))
    x0, y0, x1, y1 = geom.bounds
    return {'parts': len(letters), 'baseline_mm': round(baseline, 3),
            'cap_height_mm': round(baseline - letters[0].bounds[1], 3),
            'ink_box_mm': [round(v, 3) for v in (x0, y0, x1, y1)], 'area_mm2': round(float(geom.area), 2)}


LOGO_INK_BOUNDS = (8.632684, 8.27, 1387.948, 295.982086)    # approval.json's ink_bounds (the master's units)
LOGO_FIT_RASTER = 4


def fit_logo(pick):
    """D-D11-3.5: the approved vector at the sketch's place and size — ``lid_master.fit_logo``'s search (a uniform
    scale and a shift climbing the IoU of the drawn master against the sketch's logo, coarse to fine, from the two ink
    boxes), its target the sketch's rose-gold logo (``element_mask``). The placement read on every edge and the centre."""
    x0, y0, x1, y1 = WINDOWS['logo']
    target = element_mask(pick, 'logo', masks(pick))
    ys, xs = np.nonzero(target)
    geoms = [lm.rings_area(p, 12) for p in lm.logo_paths()]
    ux0, uy0, ux1, uy1 = LOGO_INK_BOUNDS
    r = LOGO_FIT_RASTER

    def draw(scale, tx, ty):
        canvas = np.zeros(((y1 - y0) * r, (x1 - x0) * r), dtype=np.uint8)
        for g in geoms:
            for gg in lm.parts(g):
                ext = (np.asarray(gg.exterior.coords) * scale + [tx - x0, ty - y0]) * r
                cv2.fillPoly(canvas, [np.round(ext * 16).astype(np.int32)], 1, shift=4)
                for hole in gg.interiors:
                    hh = (np.asarray(hole.coords) * scale + [tx - x0, ty - y0]) * r
                    cv2.fillPoly(canvas, [np.round(hh * 16).astype(np.int32)], 0, shift=4)
        return cv2.resize(canvas.astype(np.float32), (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA) >= 0.5

    def iou(m):
        return float((m & target).sum() / (m | target).sum())

    sx0, sx1, sy0 = x0 + xs.min(), x0 + xs.max() + 1, y0 + ys.min()
    s = (sx1 - sx0) / (ux1 - ux0)
    best = (iou(draw(s, sx0 - ux0 * s, sy0 - uy0 * s)), s, sx0 - ux0 * s, sy0 - uy0 * s)
    for step_s, step_t in ((0.01, 2.0), (0.004, 0.75), (0.0015, 0.25), (0.0005, 0.1)):
        improved = True
        while improved:
            improved = False
            _, s, tx, ty = best
            for ds in (-step_s, 0.0, step_s):
                for dx in (-step_t, 0.0, step_t):
                    for dy in (-step_t, 0.0, step_t):
                        v = iou(draw(s * (1 + ds), tx + dx, ty + dy))
                        if v > best[0] + 1e-6:
                            best = (v, s * (1 + ds), tx + dx, ty + dy)
                            improved = True
    v, s, tx, ty = best
    placed = [(tx + ux0 * s) / PX_PER_MM_SRC, (ty + uy0 * s) / PX_PER_MM_SRC,
              (tx + ux1 * s) / PX_PER_MM_SRC, (ty + uy1 * s) / PX_PER_MM_SRC]
    sketch = [sx0 / PX_PER_MM_SRC, sy0 / PX_PER_MM_SRC, sx1 / PX_PER_MM_SRC, (y0 + ys.max() + 1) / PX_PER_MM_SRC]
    width_ratio = (placed[2] - placed[0]) / (sketch[2] - sketch[0])
    edges = [abs(a - b) for a, b in zip(placed, sketch)]
    centre = [abs((placed[0] + placed[2]) / 2 - (sketch[0] + sketch[2]) / 2),
              abs((placed[1] + placed[3]) / 2 - (sketch[1] + sketch[3]) / 2)]
    worst = max(edges + centre)
    core = cv2.erode(target.astype(np.uint8), np.ones((2, 2), np.uint8)).astype(bool)
    gold = np.median(pick[y0:y1, x0:x1][core], axis=0)
    return {'transform': {'scale_mm_per_unit': s / PX_PER_MM_SRC, 'tx_mm': tx / PX_PER_MM_SRC, 'ty_mm': ty / PX_PER_MM_SRC},
            'placed_ink_box_mm': [round(c, 3) for c in placed], 'sketch_ink_box_mm': [round(c, 3) for c in sketch],
            'width_ratio': round(width_ratio, 4),
            'edge_shift_mm': {'left': round(edges[0], 3), 'top': round(edges[1], 3), 'right': round(edges[2], 3),
                              'bottom': round(edges[3], 3), 'centre_x': round(centre[0], 3), 'centre_y': round(centre[1], 3)},
            'worst_shift_mm': round(worst, 3), 'iou_with_sketch_gold': round(v, 4),
            'ink': '#%02X%02X%02X' % tuple(int(round(c)) for c in gold),
            'holds': {'within_1_mm': bool(worst <= lm.POSITION_TOL_MM),
                      'within_3_pct': bool(abs(width_ratio - 1) <= lm.SIZE_TOL)}}


# --- the master: the engine document, its files, its checks -----------------------------------------------------------

SURFACE = 'apps/pipeline/services/zilal_master.py::build'
FOIL_PLATE = 'FOIL_ROSE_GOLD'           # the house's rose-gold hot foil (orn_b1's plate name)
EMBOSS_PLATE = 'EMBOSS'
LID_MM = lm.LID_MM
BLEED_MM = lm.BLEED_MM
POCKET_STONE_SHARE = 0.10               # D-D11-3.4: a line over more than 10 % stone (its box grown 1 mm) gets its pocket
ARABIC_COPY = 'باليت ظلال العيون'        # brief 124's Arabic line, read in this order from the file


def poly_segments(geom):
    """A shapely geometry as engine path segments (every exterior and hole a closed polyline; fill even-odd)."""
    from apps.ire.graph import ClosePath, LineTo, MoveTo
    segs = []
    for g in lm.parts(geom):
        if g.is_empty:
            continue
        for ring in [g.exterior, *g.interiors]:
            pts = list(ring.coords)[:-1]
            segs.append(MoveTo(x=float(pts[0][0]), y=float(pts[0][1])))
            segs.extend(LineTo(x=float(x), y=float(y)) for x, y in pts[1:])
            segs.append(ClosePath())
    return segs


def median_ink(pick, name, erode_px):
    """An element's ink as the sketch prints it: the median of its own mask's core (eroded)."""
    x0, y0, x1, y1 = WINDOWS[name]
    own = element_mask(pick, name, masks(pick)).astype(np.uint8)
    core = cv2.erode(own, np.ones((erode_px, erode_px), np.uint8)).astype(bool)
    rgb = np.median(pick[y0:y1, x0:x1][core], axis=0)
    return '#%02X%02X%02X' % tuple(int(round(v)) for v in rgb)


def engine_document(*, plate_png, fits, inks, faces, logo, hero, name_rings, name_foil_geom, name_ink, hero_ink, layers):
    """The lid (190 × 120 mm) as one engine document, only the ``layers`` asked for: 'picture' (the cleaned plate),
    'type' (the live lines; the Arabic words with the hero's ActualText between them, so the file reads باليت ظلال
    العيون in order), 'logo' (the approved master in its ink), 'hero' and 'name' (their foil drawn flat in rose gold —
    what the eye reads the trace on), 'carriers' (the foil and the relief on invisible carriers: the picture under them
    is the sketch's own)."""
    from apps.ire.graph import Color, Document, Finish, Group, Image as GImage, Path as GPath, SolidFill
    foil = Finish(kind='foil', plate=FOIL_PLATE, appearance=Color.from_hex(hero_ink))
    emboss = Finish(kind='emboss', plate=EMBOSS_PLATE)
    children = []
    if 'picture' in layers:
        children.append(Group(name='PICTURE', role='background', children=[
            GImage(name='plate', src=str(plate_png), x=0.0, y=0.0, w=LID_MM[0], h=LID_MM[1])]))
    hero_nodes = []
    if 'carriers' in layers:
        hero_nodes.append(Group(name='HERO CARRIERS', role='effects', opacity=0.0, actual_text='ظلال', children=[
            GPath(name='ظلال (foil)', segments=poly_segments(hero['foil']), fill=SolidFill(color=Color.from_hex(hero_ink)),
                  fill_rule='evenodd', finishes=[foil]),
            GPath(name='ظلال (relief)', segments=poly_segments(hero['relief']),
                  fill=SolidFill(color=Color.from_hex(hero_ink)), fill_rule='evenodd', finishes=[emboss])]))
    if 'type' in layers:
        everything = type_nodes(fits, inks, faces).children
        by_name = {n.name: n for n in everything}
        arabic = [by_name['baliyt']] + hero_nodes + [by_name['aleyoun']]
        children.append(Group(name='ARABIC', role='typography', children=arabic))
        children.append(Group(name='TYPE', role='typography',
                              children=[n for n in everything if n.name not in ('baliyt', 'aleyoun')]))
    elif hero_nodes:
        children.extend(hero_nodes)
    if 'logo' in layers:
        x0, y0, x1, y1 = logo['placed_ink_box_mm']
        children.append(Group(name='LOGO', role='logo', children=lm.logo_parts((x0, y0, x1 - x0, y1 - y0), logo['ink'],
                                                                                foil_letters=False)))
    name_path = GPath(name='Enchanted Rose', segments=lm.rings_segments(name_rings),
                      fill=SolidFill(color=Color.from_hex(name_ink)), fill_rule='evenodd')
    if 'hero' in layers:
        children.append(Group(name='HERO', role='typography', children=[GPath(
            name='ظلال (foil, drawn)', segments=poly_segments(hero['foil']), fill=SolidFill(color=Color.from_hex(hero_ink)),
            fill_rule='evenodd')]))
    if 'name' in layers:
        children.append(Group(name='NAME', role='typography', actual_text='Enchanted Rose', children=[name_path]))
    if 'carriers' in layers:
        carrier = GPath(name='Enchanted Rose (foil)', segments=poly_segments(name_foil_geom),
                        fill=SolidFill(color=Color.from_hex(name_ink)), fill_rule='evenodd',
                        finishes=[Finish(kind='foil', plate=FOIL_PLATE, appearance=Color.from_hex(name_ink))])
        children.append(Group(name='NAME CARRIER', role='effects', opacity=0.0, actual_text='Enchanted Rose',
                              children=[carrier]))
    return Document(page_w=LID_MM[0], page_h=LID_MM[1], title='Ẓilāl lid master',
                    metadata={'typography_surface': SURFACE, 'logical_text/1.0': True},
                    root=Group(name='LID MASTER', role='artwork', children=children))


def drawn_units(render, boxes, key):
    """A line's units as the engine drew them, read from a render at the match scale (the sketch's line box, scaled) —
    the sketch's own reader (``lid_master.glyph_units``; an Arabic word one unit)."""
    x0, y0, x1, y1 = (v * lm.MATCH_SCALE for v in line_box(boxes, key))
    mask = lm.srgb_to_lab(render[y0:y1, x0:x1])[..., 0] > 50.0
    if ZLINES[key]['rtl']:
        bx0, by0, bx1, by1 = lm._ink_box(mask)
        units = [{'box': (bx0, by0, bx1, by1), 'mask': mask[by0:by1, bx0:bx1]}]
    else:
        units = lm.glyph_units(mask, False, 0)
    k = lm.RENDER_PX_PER_MM
    for u in units:
        bx0, by0, bx1, by1 = u['box']
        u['box_mm'] = ((x0 + bx0) / k, (y0 + by0) / k, (x0 + bx1) / k, (y0 + by1) / k)
    return units


def _emit(doc, path):
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    usage = {}
    emit_pdf_ai(doc, str(path), usage_out=usage)
    return path, usage


def write_master_files(out, parts, plate_png, plate_bleed_png):
    """lid-master.pdf (196 × 126 mm, trim 190 × 120: page 1 the artwork — the picture plate tagged sRGB, the live type
    and the logo over it on their layers; page 2 the rose-gold foil plate; page 3 the relief plate; page 4 the trim,
    bleed and safe area), lid-master.ai (one page in layer groups: picture, type, hero, name, logo, foil, relief, guides —
    picture, type, logo and guides shown), lid-master-flat.png (the print at 300 PPI) and lid-1to1-A4.pdf (100 % on A4
    landscape with crop marks and a ruler; page 2 the finish proof at the same scale)."""
    import fitz
    from apps.ire.graph import Color, Document, Group, Path as GPath, SolidFill
    eng = out / 'engine'
    common = dict(fits=parts['fits'], inks=parts['inks'], faces=parts['faces'], logo=parts['logo'], hero=parts['hero'],
                  name_rings=parts['name_rings'], name_foil_geom=parts['name_foil_geom'], name_ink=parts['name_ink'],
                  hero_ink=parts['hero_ink'])
    layer = {}
    for key, wanted in (('type', ('type',)), ('logo', ('logo',)), ('hero', ('hero',)), ('name', ('name',))):
        layer[key], _ = _emit(engine_document(plate_png=plate_png, layers=wanted, **common), eng / ('layer-%s.ai' % key))
    black = SolidFill(color=Color.from_hex('#000000'))
    meta = {'typography_surface': SURFACE}
    layer['foil'], _ = _emit(Document(page_w=LID_MM[0], page_h=LID_MM[1], metadata=meta, root=Group(name='FOIL', children=[
        GPath(name='ظلال (foil)', segments=poly_segments(parts['hero']['foil']), fill=black, fill_rule='evenodd'),
        GPath(name='Enchanted Rose (foil)', segments=poly_segments(parts['name_foil_geom']), fill=black,
              fill_rule='evenodd')])), eng / 'layer-foil.ai')
    layer['relief'], _ = _emit(Document(page_w=LID_MM[0], page_h=LID_MM[1], metadata=meta, root=Group(name='RELIEF', children=[
        GPath(name='ظلال (relief)', segments=poly_segments(parts['hero']['relief']), fill=black, fill_rule='evenodd')])),
        eng / 'layer-relief.ai')
    support = parts['faces']['latin']['path']
    trim = lm._trim_rect()
    w, h = lm.pt(LID_MM[0] + 2 * BLEED_MM), lm.pt(LID_MM[1] + 2 * BLEED_MM)
    srcs = {k: fitz.open(str(v)) for k, v in layer.items()}
    pdf = fitz.open()
    ocg = {n: pdf.add_ocg(n, on=True) for n in ('picture', 'type', 'logo', 'foil', 'relief', 'guides')}
    p = pdf.new_page(width=w, height=h)
    p.insert_image(lm._picture_rect((BLEED_MM, BLEED_MM)), filename=str(plate_bleed_png), oc=ocg['picture'])
    p.show_pdf_page(trim, srcs['type'], 0, oc=ocg['type'])
    p.show_pdf_page(trim, srcs['logo'], 0, oc=ocg['logo'])
    p = pdf.new_page(width=w, height=h)
    p.show_pdf_page(trim, srcs['foil'], 0, oc=ocg['foil'])
    p = pdf.new_page(width=w, height=h)
    p.show_pdf_page(trim, srcs['relief'], 0, oc=ocg['relief'])
    p = pdf.new_page(width=w, height=h)
    lm._guides(p, support, ocg['guides'])
    for page in pdf:
        page.set_bleedbox(page.rect)
        page.set_trimbox(trim)
    pdf.set_page_labels([{'startpage': i, 'prefix': n, 'style': ''} for i, n in enumerate(
        ('1 artwork: picture (RGB, sRGB), type, logo ', '2 rose-gold foil plate ', '3 relief plate (emboss) ',
         '4 trim, bleed, safe '))])
    pdf.set_metadata({'title': 'Ẓilāl lid master', 'subject': 'Day 11 §1: the master of the owner\'s pick R3 (B-1.3)',
                      'creator': SURFACE, 'producer': 'PyMuPDF %s' % fitz.VersionBind})
    lm.tag_srgb(pdf)
    pdf.save(str(out / 'lid-master.pdf'), garbage=3, deflate=True)
    pdf.close()
    ai = fitz.open()
    ocg = {n: ai.add_ocg(n, on=n in ('picture', 'type', 'logo', 'guides'))
           for n in ('picture', 'type', 'hero', 'name', 'logo', 'foil', 'relief', 'guides')}
    p = ai.new_page(width=w, height=h)
    p.insert_image(lm._picture_rect((BLEED_MM, BLEED_MM)), filename=str(plate_bleed_png), oc=ocg['picture'])
    for key in ('type', 'hero', 'name', 'logo', 'foil', 'relief'):
        p.show_pdf_page(trim, srcs[key], 0, oc=ocg[key])
    lm._guides(p, support, ocg['guides'])
    p.set_bleedbox(p.rect)
    p.set_trimbox(trim)
    ai.set_metadata({'title': 'Ẓilāl lid master (layers)', 'creator': SURFACE})
    lm.tag_srgb(ai)
    ai.save(str(out / 'lid-master.ai'), garbage=3, deflate=True)
    ai.close()
    for s in srcs.values():
        s.close()
    lm.render_png(parts['engine_ai'], 0, lm.FLAT_PPI, out / 'lid-master-flat.png')
    a4 = fitz.open()
    aw, ah = lm.A4_LANDSCAPE_MM
    x0, y0 = (aw - LID_MM[0]) / 2, (ah - LID_MM[1]) / 2
    trim_a4 = fitz.Rect(lm.pt(x0), lm.pt(y0), lm.pt(x0 + LID_MM[0]), lm.pt(y0 + LID_MM[1]))
    src_type, src_logo = fitz.open(str(layer['type'])), fitz.open(str(layer['logo']))
    p = a4.new_page(width=lm.pt(aw), height=lm.pt(ah))
    p.insert_image(lm._picture_rect((x0, y0)), filename=str(plate_bleed_png))
    p.show_pdf_page(trim_a4, src_type, 0)
    p.show_pdf_page(trim_a4, src_logo, 0)
    lm.crop_marks(p, (x0, y0, x0 + LID_MM[0], y0 + LID_MM[1]))
    lm.label(p, 'Zilal lid master at 100 %: trim 190 x 120 mm inside the crop marks, 3 mm bleed. Print at actual size '
                '(no scaling); the ruler below is 100 mm.', x0, y0 + LID_MM[1] + 12, support)
    lm._ruler(p, x0, y0 + LID_MM[1] + 16)
    p = a4.new_page(width=lm.pt(aw), height=lm.pt(ah))
    p.insert_image(trim_a4, filename=str(out / 'finish-proof.png'))
    lm.crop_marks(p, (x0, y0, x0 + LID_MM[0], y0 + LID_MM[1]))
    lm.label(p, 'The finish proof at the same scale: rose-gold foil on the hatch, the rim and the name; the hero '
                'embossed.', x0, y0 + LID_MM[1] + 12, support)
    lm._ruler(p, x0, y0 + LID_MM[1] + 16)
    src_type.close()
    src_logo.close()
    lm.tag_srgb(a4)
    a4.save(str(out / 'lid-1to1-A4.pdf'), garbage=3, deflate=True)
    a4.close()
    return layer


CONTRAST_FLOOR = 4.5                   # WCAG for small text; 3.0 for large (cap ≥ 4.2 mm), the Arabic, the name and the
CONTRAST_FLOOR_LARGE = 3.0             # hero (as Day 10)


def line_boxes_mm(sketch):
    """Each line's ink box in mm, from the sketch's own units."""
    return {key: (min(u['box_mm'][0] for u in units), min(u['box_mm'][1] for u in units),
                  max(u['box_mm'][2] for u in units), max(u['box_mm'][3] for u in units)) for key, units in sketch.items()}


def alif_share(fits, faces):
    """The Arabic alif (باليت's face at its fitted size) against its Latin pair's capitals (EYESHADOW PALETTE)."""
    from apps.ire.text_metrics import cap_height_em_measured, ink_extent_em
    alif = ink_extent_em('ا', faces['arabic']['path'])[0] * fits['baliyt']['size_mm']
    cap = cap_height_em_measured(faces['latin']['path']) * fits['eyeshadow']['size_mm']
    return {'alif_mm': round(alif, 3), 'latin_cap_mm': round(cap, 3), 'share': round(alif / cap, 4)}


def checks(out, rec, pick, plate, cleaned, fits, inks, faces):
    """D-D11-3.7, the measured checks as reports (none stops the master): each line's contrast on the ground it stands
    on (the plate's median under its box, outside its glyphs), the name's and the hero's; the name's cap; the ℮; the
    smallest type; the Arabic alif; the copy as the file carries it (ActualText, in drawing order); the page with its
    bleed; and every proof — a proof that does not hold is an issue."""
    import fitz
    boxes = rec['line_boxes_mm']
    rows = []
    for key in list(ZLINES) + ['logo']:
        under = lm.median_under(plate, boxes[key], cleaned[key])
        ratio = lm.contrast_ratio(inks[key], under)
        floor = CONTRAST_FLOOR
        if key == 'logo' or ZLINES[key]['rtl'] or boxes[key][3] - boxes[key][1] >= lm.LARGE_CAP_MM:
            floor = CONTRAST_FLOOR_LARGE
        rows.append({'line': key, 'ink': inks[key], 'under': under, 'ratio': round(ratio, 2), 'floor': floor,
                     'holds': bool(ratio >= floor)})
    for key, ink in (('name', rec['name']['ink']), ('hero', rec['hero']['ink'])):
        box = rec['element_boxes_mm'][key]
        under = lm.median_under(plate, box, element_mask_up(pick, key, plate.shape[:2]))
        ratio = lm.contrast_ratio(ink, under)
        rows.append({'line': key, 'ink': ink, 'under': under, 'ratio': round(ratio, 2), 'floor': CONTRAST_FLOOR_LARGE,
                     'holds': bool(ratio >= CONTRAST_FLOOR_LARGE)})
    spans = lm.actual_texts(rec['_engine_ai'], 0)
    joined = ' ' + ' '.join(lm._norm(t) for t in spans) + ' '
    copy = {key: {'copy': ZLINES[key]['copy'], 'found': ' %s ' % lm._norm(ZLINES[key]['copy']) in joined}
            for key in ('eyeshadow', 'shades', 'net')}
    copy['arabic line'] = {'copy': ARABIC_COPY, 'found': ' %s ' % ARABIC_COPY in joined}
    copy['name'] = {'copy': 'Enchanted Rose', 'found': ' Enchanted Rose ' in joined}
    with fitz.open(str(out / 'lid-master.pdf')) as pdf:
        media = [round(v * lm.MM_PER_INCH / 72.0, 3) for v in (pdf[0].mediabox.width, pdf[0].mediabox.height)]
        trimbox = [round(v * lm.MM_PER_INCH / 72.0, 3) for v in (pdf[0].trimbox.width, pdf[0].trimbox.height)]
    sign_mm = fits['net']['sign']['height_mm']
    smallest = min(f['size_pt'] for f in fits.values())
    alif = alif_share(fits, faces)
    sizes = {'name_cap_mm': rec['name']['measures']['cap_height_mm'],
             'name_cap_holds': bool(rec['name']['measures']['cap_height_mm'] >= lm.NAME_CAP_MIN_MM),
             'sign_mm': round(sign_mm, 3), 'sign_holds': bool(sign_mm >= lm.SIGN_MIN_MM),
             'smallest_pt': round(smallest, 2), 'smallest_holds': bool(smallest >= lm.TYPE_MIN_PT),
             'alif': alif, 'alif_holds': bool(alif['share'] >= lm.ALIF_SHARE_MIN), 'page_mm': media, 'trim_mm': trimbox,
             'page_holds': bool(abs(media[0] - (LID_MM[0] + 2 * BLEED_MM)) < 0.01 and abs(media[1] - (LID_MM[1] + 2 * BLEED_MM)) < 0.01
                                and abs(trimbox[0] - LID_MM[0]) < 0.01 and abs(trimbox[1] - LID_MM[1]) < 0.01)}
    proofs = {'upscale': rec['upscale']['holds'],
              'type_placed': {k: v['holds'] for k, v in rec['type']['overlay'].items()},
              'hero_trace': rec['hero']['trace']['holds'],
              'hatch_fit': rec['hero']['hatch']['fit']['holds'],
              'foil_limits': rec['finishes']['foil_limits']['holds'],
              'name_trace': rec['name']['trace']['holds'],
              'name_against_the_pick': rec['name']['trace']['against_the_pick_itself']['holds'],
              'logo_placed': rec['logo']['holds'],
              'safe_area': all(r['inside_safe'] for r in rec['safe_area'])}
    issues = ['%s: contrast %.2f under its floor %.1f' % (r['line'], r['ratio'], r['floor']) for r in rows if not r['holds']]
    for label_, ok in (('name cap', sizes['name_cap_holds']), ('℮ height', sizes['sign_holds']),
                       ('smallest type', sizes['smallest_holds']), ('Arabic alif', sizes['alif_holds']),
                       ('page size', sizes['page_holds'])):
        if not ok:
            issues.append('%s does not hold' % label_)
    issues += ['the copy of %s does not extract word for word' % k for k, c in copy.items() if not c['found']]
    for where in lm.failed_proofs(proofs, ''):
        if where == 'upscale.de00_max':
            issues.append('the upscale\'s max ΔE00 %.2f is over 4 (%d pixels)' % (
                rec['upscale']['de00_max'], rec['upscale']['pixels_over_max']))
        else:
            issues.append('%s does not hold' % where)
    hero_own = rec['hero']['trace']['against_the_pick_itself']
    return {'schema': 'day11_zilal_lid_checks/1', 'contrast': rows, 'sizes': sizes, 'copy': copy,
            'actual_text_spans': spans, 'proofs': proofs, 'issues': issues, 'checks_hold': not issues,
            'reported_beside': {'hero_against_the_pick_itself': {k: hero_own[k] for k in ('max_mm', 'p99_mm', 'unread', 'points')},
                                'said': rec['hero']['on_pick_said']},
            'note': 'D-D11-3.7: every check runs as a report; none stops the master'}


def element_mask_up(pick, name, shape):
    """An element's own mask on the upscale's grid (its window placed on the whole upscale), grown 2 upscaled px."""
    own = element_mask(pick, name, masks(pick)).astype(np.uint8)
    h, w = own.shape
    big = cv2.resize(own, (w * UP, h * UP), interpolation=cv2.INTER_NEAREST)
    return lm.place_mask(cv2.dilate(big, np.ones((5, 5), np.uint8)).astype(bool), WINDOWS[name], shape)


def media_map(rec):
    """D-D8-4: each element's medium and why."""
    faces = rec['type']['faces']
    return {'schema': 'day11_zilal_media_map/1', 'elements': [
        {'element': 'the picture (the indigo ground, the floated stones and their copper veins)',
         'medium': 'raster plate, RGB, tagged sRGB',
         'resolution': '%s PPI (Lanczos 2× of the pick; effective %s PPI)' % (
             rec['sharpness']['resampled_ppi'], rec['sharpness']['effective_ppi']),
         'why': 'D-D10-1 / D-D11-3.6: the sketch\'s own pixels; the marbling is the picture, never redrawn; the copper '
                'veins are painted, not crisp metal: they print as raster ink (J1\'s note on R3)'},
        {'element': 'ظلال — the raster under its foil', 'medium': 'raster (part of the plate)',
         'why': 'D-D11-3.1: the sketch\'s hatched pixels stay beneath as the print\'s fallback'},
        {'element': 'ظلال — the foil', 'medium': 'vector, rose-gold hot foil: the traced silhouette\'s rim (%.2f mm), an '
                                                 'indigo groove (%.2f mm), the fitted hatch strokes (%.3f mm at %.3f mm '
                                                 'pitch, %.2f°)' % (RIM_MM, GROOVE_MM, rec['hero']['hatch']['stroke']['stroke_mm'],
                                                                     rec['hero']['hatch']['stroke']['pitch_mm'],
                                                                     rec['hero']['hatch']['fit']['angle_deg']),
         'why': 'D-D11-3.1: lettering traced clean; the hatch an engine line system fitted to the sketch, its strokes '
                'the foil mask within the press limits'},
        {'element': 'ظلال — the relief', 'medium': 'vector, emboss: the traced silhouette',
         'why': 'D-D11-3.1: the silhouette is the relief envelope (0.3 mm minimum feature)'},
        {'element': 'Enchanted Rose', 'medium': 'vector logotype traced from the sketch, rose-gold foil plate (its raster '
                                                'gold beneath)', 'why': 'D-D11-3.3: lettering, traced as on Day 10; metal in '
                                                                        'the sketch, so foil'},
        *[{'element': ZLINES[k]['copy'], 'medium': 'live text, %s, embedded' % faces['latin']['label'],
           'why': 'D-D11-3.4: ONE Latin face for the three small lines, the closest over all three pooled (D-D8-5)'}
          for k in ('eyeshadow', 'shades', 'net')],
        *[{'element': ZLINES[k]['copy'], 'medium': 'live text, %s (Tajawal Medium made emitter-capable), in the sketch\'s '
                                                   'cream ink' % faces['arabic']['label'],
           'why': 'D-D11-3.2: the closest licensed Arabic face (D-D8-5, the house near-tie); the sketch shows cream ink, '
                  'not metal, so ink'} for k in ('baliyt', 'aleyoun')],
        {'element': '℮', 'medium': 'vector (the house\'s estimated sign)', 'why': 'the sign drawn as the sign'},
        {'element': 'the logo', 'medium': 'the approved vector master, all in ink, in the sketch\'s rose gold %s' % rec['logo']['ink'],
         'why': 'D-D11-3.5: foil fails the press limits; the sketch keeps %.2f mm of air above باليت, so no gap is '
                'doubled' % rec['logo']['air_above_baliyt_mm']},
        {'element': 'the bleed', 'medium': 'raster: the picture\'s edges mirrored %.2f mm' % rec['bleed']['mm'],
         'why': 'D-D11-3.7'}]}


def preflight(out, rec):
    """The print file read back: resolution, fonts embedded and which draw, the picture's colour space resolved, the
    foil limits, the boxes and the bleed."""
    import fitz
    fonts, drawn, images = {}, set(), []
    with fitz.open(str(out / 'lid-master.pdf')) as pdf:
        for i, page in enumerate(pdf):
            for f in page.get_fonts(full=True):
                fonts[f[3]] = {'embedded': f[1] not in ('', 'n/a'), 'type': f[2]}
            for block in page.get_text('dict')['blocks']:
                if 'lines' not in block:
                    continue
                for line in block['lines']:
                    for span in line['spans']:
                        drawn.add(span['font'])
            for img in page.get_images(full=True):
                images.append(dict(lm.image_colour_space(pdf, img[0]), page=i + 1, px=[img[2], img[3]]))
        boxes = {'media_mm': [round(v * lm.MM_PER_INCH / 72, 3) for v in pdf[0].mediabox],
                 'trim_mm': [round(v * lm.MM_PER_INCH / 72, 3) for v in pdf[0].trimbox],
                 'bleed_mm': [round(v * lm.MM_PER_INCH / 72, 3) for v in pdf[0].bleedbox]}
    for name, f in fonts.items():
        f['draws'] = lm._font_key(name) in {lm._font_key(d) for d in drawn}
    pictures = [im for im in images if im['px'][0] > 1000]
    return {'schema': 'day11_zilal_preflight/1', 'file': 'lid-master.pdf', 'sharpness': rec['sharpness'],
            'images': images, 'fonts': fonts,
            'fonts_that_draw_embedded': all(f['embedded'] for f in fonts.values() if f['draws']),
            'foil_masks_within_limits': rec['finishes']['foil_limits']['holds'], 'boxes': boxes,
            'bleed_present': bool(boxes['bleed_mm'][2] - boxes['bleed_mm'][0] > boxes['trim_mm'][2] - boxes['trim_mm'][0] + 5.9),
            'colour_space': {'picture': [{k: im[k] for k in ('colour_space', 'n', 'profile')} for im in pictures],
                             'holds': bool(pictures) and all(im['colour_space'] == 'ICCBased' and im['n'] == 3 for im in pictures)},
            'cmyk_conversion_applied': False, 'note': 'RGB until the printer\'s profile (10-12)'}


def build(out_dir):
    """§1 at $0: Ẓilāl's lid master by the preservation path (D-D10-1/2/3, D-D11-3), every file and record under
    ``out_dir`` (docs/audit/day-11/zilal/lid)."""
    from apps.pipeline.services import finish_proof
    out = Path(out_dir)
    (out / 'engine').mkdir(parents=True, exist_ok=True)
    (out / 'crops').mkdir(parents=True, exist_ok=True)
    pick = load_master_pick()
    pick_rec = json.loads((REFINE / 'pick.json').read_text(encoding='utf-8'))
    rec = {'schema': 'day11_zilal_lid/1', 'pick': {'path': lm.rel(MASTER_PICK), 'sha256': pick_rec['lid_sha256'],
                                                   'refined_from': pick_rec['refined_from'], 'px': list(PICK_PX)}}
    boxes = ink_boxes(pick)
    rec['ink_boxes_px'] = boxes

    # 1. resolution (D-D11-3.6): Lanczos 2×, proven at the pick's size
    up = lm.upscale(pick)
    rec['upscale'] = lm.prove_upscale(pick, up, {k: tuple(v) for k, v in boxes.items()})
    rec['sharpness'] = lm.sharpness(pick, up, tuple(boxes['name']))

    # 2. the plate cleaned under what is set live or as a vector
    plate, cleaned, cleaning = clean_plate(pick, up, boxes)
    for key, m in cleaned.items():
        cleaning[key]['residue'] = lm.residue(plate, m)
    rec['cleaning'] = {'method': 'each glyph and its emboss rim filled by one Poisson solve per line (the logo with all its '
                                 'emboss draws: shadow, highlights, the ®), guidance the picture\'s own clean ground per '
                                 'glyph (the nearest 3000 shifts scored on full colour and spread), boundary the picture '
                                 'itself; the hero and the name left in the raster under their foil', 'lines': cleaning}
    plate_png = out / 'engine' / 'plate.png'
    Image.fromarray(plate).save(plate_png)
    plate_bleed = lm.bleed(plate)
    Image.fromarray(plate_bleed).save(out / 'engine' / 'plate-bleed.png')
    rec['bleed'] = {'px': lm.bleed_px(), 'mm': round(lm.bleed_px() / lm.PX_PER_MM, 4),
                    'method': 'the picture\'s own edges mirrored (OpenCV BORDER_REFLECT_101); the trim checked unchanged'}

    # 3. the faces and the live lines (D-D11-3.2, 3.4)
    faces_rec = face_record(pick, boxes)
    faces_rec['weight_by_stroke'] = arabic_weight(pick, boxes)
    faces = chosen_faces(faces_rec)
    fits, inks, sketch = fit_lines(pick, boxes, faces)

    # 4. the hero (D-D11-3.1)
    hero_rings, _, hero_proof = trace_hero(pick)
    letters = letters_geometry(hero_rings)
    measured, spectrum = findings_measures(pick)
    save_spectrum(spectrum, out / 'crops' / 'hatch-fft.png')
    fit = fit_hatch(pick, letters, measured['hatch'])
    stroke = hatch_stroke(fit)
    hero = hero_foil_registered(pick, letters, fit, stroke)
    hatch_overlay(pick, fit, stroke, letters, out / 'crops' / 'hatch-overlay-1to1.png', hero.pop('field'))
    own = hero_proof['against_the_pick_itself']
    hero_ink = median_ink(pick, 'hero', 5)
    rec['hero'] = {'trace': hero_proof, 'ink': hero_ink, 'ink_box_mm': [round(v, 3) for v in letters.bounds],
                   'hatch': {'measured_fft': measured['hatch'], 'fit': fit, 'stroke': stroke,
                             'overlay_crop': lm.rel(out / 'crops' / 'hatch-overlay-1to1.png'),
                             'fft_crop': lm.rel(out / 'crops' / 'hatch-fft.png')},
                   'registration': hero['registration'],
                   'foil_mm2': round(float(hero['foil'].area), 2), 'relief_mm2': round(float(hero['relief'].area), 2),
                   'foil_cleaning_moved_mm2': hero['moved_mm2'],
                   'on_pick_said': 'read against the pick\'s own edges the outline holds on %.2f %% of its %d points '
                                   '(p99 %.3f mm); the rest lie where the outline runs into the narrow slots between '
                                   'strokes (their ends meet in a V, the normal runs along the slot) and along the bevel\'s '
                                   'lower edge (the sketch draws a highlight line over a shadow there): max %.3f mm, %d '
                                   'unread' % (100.0 * own['within_0_3_mm_share'], own['points'], own['p99_mm'],
                                               own['max_mm'], own['unread'])}

    # 5. the name (D-D11-3.3) and the logo (D-D11-3.5)
    name_rings, _, name_proof = trace_name(pick)
    name_ink = median_ink(pick, 'name', 3)
    name_foil_geom, name_foil_moved = name_foil(name_rings)
    rec['name'] = {'trace': name_proof, 'measures': name_measures(name_rings), 'ink': name_ink,
                   'foil_cleaning_moved_mm2': name_foil_moved,
                   'joins': 'read at 1 : 1 on the trace over the pick: no join drawn badly in the sketch, none redrawn'}
    logo = fit_logo(pick)
    logo['air_above_baliyt_mm'] = mm(boxes['baliyt'][1] - boxes['logo'][3])
    logo['gap_doubled'] = False
    baliyt_top_mm = boxes['baliyt'][1] / PX_PER_MM_SRC

    # 5b. the safe area first (D-D10-2.6): what stands within 4 mm of the trim moves inward by the least amount
    line_mm = line_boxes_mm(sketch)
    moves = safe_moves(line_mm, tuple(logo['placed_ink_box_mm']))
    for key, move in moves.items():
        if key == 'logo':
            logo = move_logo(logo, move)
        else:
            fits[key] = move_fit(fits[key], move)
    rec['moves'] = {'safe_area': {k: {'dx_mm': v[0], 'dy_mm': v[1]} for k, v in moves.items()},
                    'said': 'D-D10-2.6: each moved inward by the least amount that holds 4 mm from the trim; the '
                            'sketch\'s bottom row (18 SHADES and the net line, one baseline) by the row\'s least, so its '
                            'baseline holds'}
    logo['air_above_baliyt_after_moves_mm'] = round(baliyt_top_mm - logo['placed_ink_box_mm'][3], 2)
    rec['logo'] = logo
    inks['logo'] = logo['ink']

    # 6. the engine document (190 × 120): the checks' and the finish proof's file; and the same with the foil drawn
    probe = out / 'engine' / 'type-probe.ai'
    lm.emit_type_probe(probe, type_nodes(fits, inks, faces))
    rec['moves']['arabic_centred'] = centre_arabic(fits, {k: moved_units(v, moves[k]) if k in moves else v
                                                          for k, v in sketch.items()},
                                                   lm.render_page(probe, 0, lm.RENDER_PX_PER_MM), boxes)
    probe.unlink()
    parts = dict(fits=fits, inks=inks, faces=faces, logo=logo, hero=hero, name_rings=name_rings,
                 name_foil_geom=name_foil_geom, name_ink=name_ink, hero_ink=hero_ink)
    engine_ai = out / 'engine' / 'lid-engine.ai'
    _, usage = _emit(engine_document(plate_png=plate_png, layers=('picture', 'type', 'logo', 'carriers'), **parts),
                     engine_ai)
    _emit(engine_document(plate_png=plate_png, layers=('picture', 'type', 'logo', 'hero', 'name'), **parts),
          out / 'engine' / 'lid-drawn.ai')
    parts['engine_ai'] = engine_ai
    rec['_engine_ai'] = engine_ai
    flat = lm.flat_1536(engine_ai, out / 'engine' / 'flat-1536.png')
    proof = finish_proof.prove_build(flat, engine_ai, out / 'engine' / 'proof-record', foil_drawn=True)
    (out / 'finish-proof.png').write_bytes((out / 'engine' / 'proof-record' / 'finish-proof.png').read_bytes())
    rec['finishes'] = {'coverage': proof['coverage'], 'foil_limits': proof['foil_limits'],
                       'foil': 'rose-gold hot foil: ظلال\'s rim and hatch strokes, and the traced name',
                       'relief': 'emboss: ظلال\'s silhouette',
                       'ink': 'the logo (foil fails the press limits), the small lines and the Arabic words (cream in the '
                              'sketch), the copper veins (painted, in the raster)'}

    # 7. the live lines' placement, read from the engine's own type (D-D11-3.2/3.4: 1 mm, 3 %); the pockets
    probe = out / 'engine' / 'type-probe.ai'
    lm.emit_type_probe(probe, type_nodes(fits, inks, faces))
    render = lm.render_page(probe, 0, lm.RENDER_PX_PER_MM)
    probe.unlink()
    target = {k: moved_units(v, moves[k]) if k in moves else v for k, v in sketch.items()}
    rec['type'] = {'faces': faces, 'face_record': faces_rec, 'fits': fits, 'inks': inks,
                   'overlay': {key: dict(overlay(target[key], drawn_units(render, moved_boxes(boxes, moves), key),
                                                 ZLINES[key]['rtl']),
                                         against='the sketch\'s own glyphs, moved by the line\'s listed safe-area move')
                               for key in ZLINES}}
    stones = stones_under(pick, boxes, tuple(ZLINES))
    rec['pockets'] = {'stone_share_under_each_line': stones, 'threshold': POCKET_STONE_SHARE,
                      'parted': [k for k, v in stones.items() if v > POCKET_STONE_SHARE],
                      'said': 'R3 already sets every line on calm indigo (J1): no line stands over more than 10 % '
                              'stone, so no pocket is inpainted'}

    # 8. the safe area (every element's ink box at least 4 mm inside the trim)
    line_mm = {k: moved_box(v, moves[k]) if k in moves else v for k, v in line_boxes_mm(sketch).items()}
    rec['line_boxes_mm'] = dict(line_mm, logo=tuple(logo['placed_ink_box_mm']))
    rec['element_boxes_mm'] = {'hero': tuple(letters.bounds), 'name': tuple(rec['name']['measures']['ink_box_mm']),
                               'logo': tuple(logo['placed_ink_box_mm'])}
    rec['safe_area'] = lm.safe_area(dict(line_mm, **rec['element_boxes_mm']))

    # 9. the master's files, the checks, the media map, the preflight
    write_master_files(out, parts, plate_png, out / 'engine' / 'plate-bleed.png')
    rec['files'] = {p.name: {'sha256': lm.sha256(p), 'bytes': p.stat().st_size} for p in sorted(out.glob('*')) if p.is_file()}
    rec['checks'] = checks(out, rec, pick, plate, cleaned, fits, inks, faces)
    del rec['_engine_ai']
    lm.write_json(out / 'checks.json', rec['checks'])
    lm.write_json(out / 'media-map.json', media_map(rec))
    lm.write_json(out / 'preflight.json', preflight(out, rec))
    rec['usage'] = usage
    lm.write_json(out / 'master.json', rec)
    return rec


# --- the allowed placements: the safe area (D-D10-2.6), the Arabic words centred, the name's foil to the press ----------

SAFE_MM = lm.SAFE_MM
SAFE_MARGIN_MM = 0.002                   # a move lands 2 µm past the line, so its rounding to 0.001 mm never falls short
ROWS = {'bottom row': ('shades', 'net')}   # lines on one baseline in the sketch move together


def safe_moves(line_mm, logo_box):
    """D-D10-2.6 (D-D11-3.7): every copy line and the logo at least 4 mm inside the trim; a line that is not moves
    inward by the least amount, and the lines of one row (the sketch's bottom row) by the row's least, so their shared
    baseline holds. Returns {key: (dx, dy) mm} for what moves, each with its reason."""
    w, h = LID_MM

    def least(box):
        x0, y0, x1, y1 = box
        dx = max(SAFE_MM - x0, 0.0) - max(x1 - (w - SAFE_MM), 0.0)
        dy = max(SAFE_MM - y0, 0.0) - max(y1 - (h - SAFE_MM), 0.0)
        return dx + SAFE_MARGIN_MM * np.sign(dx), dy + SAFE_MARGIN_MM * np.sign(dy)

    boxes = dict(line_mm, logo=logo_box)
    moves = {}
    for key, box in boxes.items():
        dx, dy = least(box)
        if dx or dy:
            moves[key] = (round(float(dx), 3), round(float(dy), 3))
    for row, keys in ROWS.items():
        moving = [moves[k] for k in keys if k in moves]
        if moving:
            dy = min(m[1] for m in moving)
            for k in keys:
                dx = 0.0
                if k in moves:
                    dx = moves[k][0]
                moves[k] = (dx, round(dy, 3))
    return moves


def moved_box(box, move):
    dx, dy = move
    return (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)


def move_fit(fit, move):
    """A line's fit moved by (dx, dy) mm: its runs (or its Arabic word) and its ℮."""
    dx, dy = move
    out = json.loads(json.dumps(fit))
    if 'runs' in out:
        for run in out['runs']:
            run['x_mm'] += dx
            run['baseline_mm'] += dy
    else:
        out['x_mm'] += dx
        out['baseline_mm'] += dy
    if 'sign' in out:
        out['sign']['box_mm'] = list(moved_box(out['sign']['box_mm'], move))
    return out


def moved_units(units, move):
    return [dict(u, box_mm=moved_box(u['box_mm'], move)) for u in units]


def move_logo(logo, move):
    dx, dy = move
    out = dict(logo)
    out['placed_ink_box_mm'] = [round(v, 3) for v in moved_box(logo['placed_ink_box_mm'], move)]
    out['transform'] = dict(logo['transform'], tx_mm=logo['transform']['tx_mm'] + dx, ty_mm=logo['transform']['ty_mm'] + dy)
    out['moved_mm'] = [dx, dy]
    return out


def centre_arabic(fits, sketch, render, boxes):
    """Each Arabic word centred on the sketch's own word: the face draws it at the sketch's height but narrower or wider
    (its own proportions), so the fit's right-edge anchor would leave the difference all on one side; the drawn word is
    moved by half the difference, read from the engine's own drawing. Returns the moves (mm)."""
    moves = {}
    for key, line in ZLINES.items():
        if not line['rtl']:
            continue
        drawn = drawn_units(render, boxes, key)[0]['box_mm']
        target = sketch[key][0]['box_mm']
        shift = -((drawn[0] - target[0]) + (drawn[2] - target[2])) / 2.0
        fits[key]['x_mm'] += shift
        moves[key] = {'dx_mm': round(shift, 3), 'drawn_width_mm': round(drawn[2] - drawn[0], 3),
                      'sketch_width_mm': round(target[2] - target[0], 3)}
    return moves


NAME_FOIL_OPEN_R_MM = 0.055             # the press's 0.1 mm line (with a 0.005 mm margin) …
NAME_FOIL_CLOSE_R_MM = 0.105            # … and its 0.2 mm gap


def name_foil(name_rings):
    """The name's foil held to the press: its traced letters, parts finer than 0.1 mm opened away and gaps under 0.2 mm
    closed (the narrow counters the press would fill); the traced outlines stay as drawn on the name's own layer, and
    the sketch's raster gold beneath. Returns the geometry and what the cleaning moved."""
    raw = lm.rings_area(name_rings, 24).buffer(0)
    clean = raw.buffer(-NAME_FOIL_OPEN_R_MM).buffer(NAME_FOIL_OPEN_R_MM).buffer(NAME_FOIL_CLOSE_R_MM).buffer(-NAME_FOIL_CLOSE_R_MM)
    return clean, round(float(clean.symmetric_difference(raw).area), 4)


def overlay(target, drawn, rtl):
    """D-D11-3.2/3.4's placement proof (``lid_master.overlay_proof``: within 1 mm and 3 %). An Arabic word is read as one
    unit: its place is its centre and its size its height — its width is the face's own drawing of the word (as a Latin
    glyph's own height is in Day 10's proof), recorded beside, never read as a misplacement."""
    proof = lm.overlay_proof(target, drawn)
    if not rtl or proof['units'] != 1:
        return proof
    t, d = target[0]['box_mm'], drawn[0]['box_mm']
    proof['width_ratio'] = round((d[2] - d[0]) / (t[2] - t[0]), 4)
    proof['said'] = ('the face draws the word %.1f %% %s than the sketch\'s lettering; placed on its centre, its edges '
                     'stand %.2f mm inside or outside each' % (abs(1 - proof['width_ratio']) * 100,
                                                              'narrower' if proof['width_ratio'] < 1 else 'wider',
                                                              abs(proof['line_box_edges_shift_mm'][0])))
    proof['holds'] = bool(proof['worst_glyph_shift_mm'] <= lm.POSITION_TOL_MM and abs(proof['line_size_ratio'] - 1)
                          <= lm.SIZE_TOL and abs(proof['line_box_edges_shift_mm'][1]) <= lm.POSITION_TOL_MM
                          and abs(proof['line_box_edges_shift_mm'][3]) <= lm.POSITION_TOL_MM)
    return proof


def moved_boxes(boxes, moves):
    """The lines' reading boxes (pick px) moved by their safe-area moves, so the drawn line is read where it now is."""
    out = dict(boxes)
    for key, (dx, dy) in moves.items():
        if key in out and key != 'logo':
            x0, y0, x1, y1 = out[key]
            ddx, ddy = int(round(dx * PX_PER_MM_SRC)), int(round(dy * PX_PER_MM_SRC))
            out[key] = [x0 + ddx, y0 + ddy, x1 + ddx, y1 + ddy]
    return out


# --- D-D11-3.7: the fidelity gate (the designer's eye) ------------------------------------------------------------------

DECISIONS = REPO / 'CURRENT_DECISIONS.md'
EYE_CROP_FILL = 0.97


def allowed_differences():
    """D-D11-3 as the owner typed it and the builder recorded it (CURRENT_DECISIONS.md), verbatim: its seven items —
    and, since its item 7's bleed is D-D10-2.6's (the preservation path, D-D10-1/2/3), D-D10-2.6 verbatim beside it:
    its safe-area rule is what moves a line."""
    text = DECISIONS.read_text(encoding='utf-8')
    start = text.index('- **D-D11-3 — The Ẓilāl lid master')
    d11 = text[start:text.index('- **D-D11-4 —', start)].strip()
    b = text.index('  6. **Bleed.** 3 mm all round by extending')
    d10 = text[b:text.index('  7. **The measured checks run as reports**', b)].strip()
    return d11 + '\n\nD-D11-3 7\'s bleed is the preservation path\'s (D-D10-2.6), recorded on Day 10 as:\n' + d10


EYE_MAX_TOKENS = 16000                  # twelve crops answered in full (round 0's crops look ran out at Day 10's 8000)


def make_eye_call(*, cap_usd, client):
    """ONE Claude vision call (the jury's model, effort high, a JSON schema), through the ledger under Day 11's eye
    prefix, as ``lid_master.make_eye_call`` makes it, with room for twelve crops' answers."""
    from apps.pipeline.services import jury
    from apps.pipeline.services.spend_reservation import paid_operation

    def call(operation, content, schema):
        api = client
        if api is None:
            api = jury._client()
        model = jury.jury_model()
        response = paid_operation(api.messages.create, provider='anthropic', operation=EYE_PREFIX + operation,
                                  reservation_prefix=EYE_PREFIX, reservation_cap=cap_usd, model=model,
                                  max_tokens=EYE_MAX_TOKENS,
                                  output_config={'effort': 'high', 'format': {'type': 'json_schema', 'schema': schema}},
                                  messages=[{'role': 'user', 'content': content}])
        text = ''.join(b.text for b in response.content if b.type == 'text')
        usage = response.model_dump(mode='json')['usage']
        payload = None
        if response.stop_reason == 'end_turn':
            payload = json.loads(text)
        return {'payload': payload, 'stop_reason': response.stop_reason, 'usage': usage,
                'cost_usd': jury.cost_usd(model, usage), 'model': model,
                'reservation_id': response._rescue_reservation_id,
                'response_artifact': response._rescue_response_artifact}
    return call


def master_facts(rec):
    """What the eye cannot see in a picture, said as facts: which parts are foil, relief and ink, the moves, the faces."""
    moves = rec['moves']['safe_area']
    reg = rec['hero']['registration']['on_painted_strokes_share']
    faces = rec['type']['faces']
    return ('WHAT THE PICTURES CANNOT SHOW. Rose-gold hot foil: ظلال\'s rim and its hatch strokes — drawn by our engine '
            'at the sketch\'s own pitch, angle and stroke (pitch %.3f mm, stroke %.3f mm, gap %.2f mm, %.1f°), each '
            'stroke registered on the sketch\'s painted stroke beneath it (the phase read from the sketch\'s own hatch; '
            '%.0f %% of the foil sits on the painted strokes, against %.0f %% for straight lines) — and "Enchanted Rose" '
            '(traced from the sketch). Emboss: ظلال\'s silhouette. Ink: the logo (in the sketch\'s rose gold), the small '
            'lines and باليت / العيون (cream, as the sketch). The picture under the foil keeps the sketch\'s own painted '
            'gold. The small lines are live text in %s; باليت and العيون in %s (the weight whose stroke is nearest the '
            'sketch\'s). Moved by the safe-area rule (D-D10-2.6: 4 mm from the trim, the least amount): %s; the logo '
            'keeps %.2f mm of air above باليت after its move (the sketch\'s %.2f). The flat is trimmed; the 3 mm bleed '
            'lies outside it.' % (
                rec['hero']['hatch']['stroke']['pitch_mm'], rec['hero']['hatch']['stroke']['stroke_mm'],
                rec['hero']['hatch']['stroke']['gap_mm'], rec['hero']['hatch']['fit']['angle_deg'],
                100 * reg['registered'], 100 * reg['straight'], faces['latin']['label'], faces['arabic']['label'],
                '; '.join('%s %+.2f mm across, %+.2f mm down' % (k, v['dx_mm'], v['dy_mm']) for k, v in moves.items()),
                rec['logo']['air_above_baliyt_after_moves_mm'], rec['logo']['air_above_baliyt_mm']))


def _pair(top, below, dpi, path):
    """Two same-size crops stacked (a white rule between) and saved at ``dpi``; refused when the API would resample."""
    pair = np.concatenate([top, np.full((8, top.shape[1], 3), 255, dtype=np.uint8), below], axis=0)
    img = Image.fromarray(pair)
    if max(img.size) > lm.EYE_IMAGE_EDGE_MAX or img.size[0] * img.size[1] > lm.EYE_PIXELS_MAX:
        raise ValueError('%s is %s px: the API would resample it' % (path, img.size))
    img.save(path, dpi=(dpi, dpi))
    return path


def _fit_dpi(w_mm, h_mm, rows):
    """The largest dpi up to 600 at which ``rows`` crops of w × h mm stacked stay under the API's size."""
    return EYE_CROP_FILL * min(600.0, lm.EYE_IMAGE_EDGE_MAX / (w_mm / lm.MM_PER_INCH),
                               lm.EYE_IMAGE_EDGE_MAX / (rows * h_mm / lm.MM_PER_INCH),
                               (lm.EYE_PIXELS_MAX / (rows * w_mm * h_mm)) ** 0.5 * lm.MM_PER_INCH)


def eye_crops(out, rec):
    """The crops the eye reads, each the pick above the master at print size: every small line and Arabic word (where
    the master now draws it — a moved line's crop follows it), the logo, the hero in two halves with its foil drawn flat
    (lid-drawn.ai), the name in two halves with its trace drawn; and the hatch's 1 : 1 overlay and the marbling's upscale
    (the pick's own pixels repeated 2× above the plate)."""
    pick = load_master_pick()
    drawn = {}
    files = {}

    def render(path, dpi):
        key = (str(path), round(dpi, 2))
        if key not in drawn:
            drawn[key] = lm._render(path, dpi)
        return drawn[key]

    def crop(box_mm, name, move, master_ai):
        x0, y0, x1, y1 = box_mm
        dpi = _fit_dpi(x1 - x0, y1 - y0, 2)
        k = dpi / lm.MM_PER_INCH
        big = cv2.resize(pick, (int(LID_MM[0] * k), int(LID_MM[1] * k)), interpolation=cv2.INTER_LANCZOS4)
        master = render(master_ai, dpi)
        dx, dy = int(round(move[0] * k)), int(round(move[1] * k))
        # both crops inside the lid: the pick's at the sketch's place, the master's at the moved place
        a = max(int(x0 * k), 0, -dx)
        b = max(int(y0 * k), 0, -dy)
        c = min(int(x1 * k), big.shape[1], master.shape[1] - dx)
        d = min(int(y1 * k), big.shape[0], master.shape[0] - dy)
        top = big[b:d, a:c]
        below = master[b + dy:d + dy, a + dx:c + dx]
        h, w = min(top.shape[0], below.shape[0]), min(top.shape[1], below.shape[1])
        files[name] = _pair(top[:h, :w], below[:h, :w], dpi, out / 'crops' / ('eye-%s.png' % name))

    engine_ai = out / 'engine' / 'lid-engine.ai'
    drawn_ai = out / 'engine' / 'lid-drawn.ai'
    pad = lm.CROP_PAD_MM
    for key in ZLINES:
        x0, y0, x1, y1 = rec['line_boxes_mm'][key]
        move = rec['moves']['safe_area'][key] if key in rec['moves']['safe_area'] else {'dx_mm': 0.0, 'dy_mm': 0.0}
        # the sketch's place above; the master's own (moved) place below
        crop((x0 - move['dx_mm'] - pad, y0 - move['dy_mm'] - pad, x1 - move['dx_mm'] + pad, y1 - move['dy_mm'] + pad),
             key, (move['dx_mm'], move['dy_mm']), engine_ai)
    lx0, ly0, lx1, ly1 = rec['logo']['placed_ink_box_mm']
    mx, my = rec['logo']['moved_mm']
    crop((lx0 - mx - pad, ly0 - my - pad, lx1 - mx + pad, ly1 - my + pad), 'logo', (mx, my), engine_ai)
    for name, box in (('hero', rec['hero']['ink_box_mm']), ('name', rec['name']['measures']['ink_box_mm'])):
        x0, y0, x1, y1 = box
        cut = (x0 + x1) / 2
        crop((x0 - pad, y0 - pad, cut + pad, y1 + pad), '%s-1' % name, (0.0, 0.0), drawn_ai)
        crop((cut - pad, y0 - pad, x1 + pad, y1 + pad), '%s-2' % name, (0.0, 0.0), drawn_ai)
    files['hatch-overlay'] = out / 'crops' / 'hatch-overlay-1to1.png'
    x0, y0, x1, y1 = 60, 60, 300, 220                      # pick px: a field of floated stones, their veins and drags
    own = cv2.resize(pick[y0:y1, x0:x1], None, fx=UP, fy=UP, interpolation=cv2.INTER_NEAREST)
    plate = np.asarray(Image.open(out / 'engine' / 'plate.png').convert('RGB'))[y0 * UP:y1 * UP, x0 * UP:x1 * UP]
    files['upscale'] = _pair(own, plate, 410.0, out / 'crops' / 'eye-upscale.png')
    return files


EYE_CROP_ORDER = ('eyeshadow', 'shades', 'net', 'baliyt', 'aleyoun', 'logo', 'hero-1', 'hero-2', 'name-1', 'name-2',
                  'hatch-overlay', 'upscale')


def gate_images(out):
    """The gate's three pictures at the size the model sees them (fitted under 1.15 MP by Lanczos, one size): the
    pick, the master's flat, its finish proof."""
    sources = {'pick': MASTER_PICK, 'master': out / 'engine' / 'flat-1536.png', 'proof': out / 'finish-proof.png'}
    k = (lm.EYE_PIXELS_MAX / (PICK_PX[0] * PICK_PX[1])) ** 0.5
    size = (int(PICK_PX[0] * k), int(PICK_PX[1] * k))
    made = {}
    for name, src in sources.items():
        path = out / 'crops' / ('eye-gate-%s.png' % name)
        Image.open(src).convert('RGB').resize(size, Image.LANCZOS).save(path)
        made[name] = path
    return made


def fidelity_look(out, rec, call, round_no):
    """D-D11-3.7, one round: the gate (the pick, the master's flat and its finish proof) and the 1 : 1 crops, each
    difference classified allowed (by D-D11-3's items) or a defect; the round holds when both looks answered and
    neither names a defect. Every picture is made and checked before anything is paid; each look is written the moment
    it returns."""
    allowed = allowed_differences()
    facts = master_facts(rec)
    gate_files = gate_images(out)
    crop_files = eye_crops(out, rec)
    gate_blocks = [lm._image_block(gate_files[k]) for k in ('pick', 'master', 'proof')]
    crop_blocks = [lm._image_block(crop_files[k]) for k in EYE_CROP_ORDER]
    gate_text = ('FIDELITY GATE (Day 11, D-D11-3). The owner\'s pick is a sketch; the master must be that sketch made '
                 'printable, nothing redrawn. Image 1 is THE PICK (the design). Image 2 is THE MASTER\'s flat print '
                 'artwork (the trimmed lid, 190 × 120 mm). Image 3 is THE MASTER\'s FINISH PROOF (its foil and relief '
                 'rendered as metal and relief from the plates). Compare the master with the pick as a senior packaging '
                 'designer and list EVERY difference you see — composition, colour, the marbling, the hero ظلال and its '
                 'hatch, every line of type, the Arabic, the name, the logo, the finishes. Classify each as "allowed" '
                 '(name the item 1–7 of the owner\'s list below that covers it) or "defect" (anything the list does not '
                 'allow). Severity: blocking (the master is not the pick), major, minor. For a defect, say the smallest '
                 'repair. Answer in JSON.\n\n' + allowed + '\n\n' + facts)
    names = ['1 EYESHADOW PALETTE', '2 18 SHADES', '3 27 g ℮ 0.95 oz', '4 باليت', '5 العيون', '6 the logo',
             '7–8 the hero ظلال in two halves (its foil drawn flat in rose gold below)',
             '9–10 "Enchanted Rose" in two halves (its traced foil drawn flat below)',
             '11 the hatch\'s fitted lines drawn as thin cyan lines over the sketch\'s own hatch (one image, the sketch only)',
             '12 the marbling\'s upscale: above, the pick\'s own pixels repeated 2×; below, the master\'s plate (Lanczos 2×)']
    crop_text = ('FIDELITY GATE, 1 : 1 CROPS (Day 11). Images 1–10 are crops at print size: in each, THE PICK is above the '
                 'white rule and THE MASTER below (a moved line is shown at its new place). %s. For each image: are they '
                 'the same letters, placed as the pick places them (or as the listed move places them), is there any '
                 'invented structure (new lines, letters, shapes), and is every difference allowed (name the item 1–7 of '
                 'the owner\'s list below) or a defect. For image 11 say whether the fitted lines sit on the sketch\'s '
                 'gold strokes at its angle and pitch; for image 12 whether the plate invents anything the pick\'s pixels '
                 'do not hold. Answer in JSON.\n\n%s\n\n%s' % ('; '.join(names), allowed, facts))
    record = {'schema': 'day11_zilal_fidelity/1', 'round': round_no,
              'decided': 'in code: the round holds when both looks answered and neither names a defect'}
    gate = call('zilal/lid/r%d/gate' % round_no, [{'type': 'text', 'text': gate_text}] + [b for b, _ in gate_blocks],
                lm.FIDELITY_SCHEMA)
    gate['sent'] = [i for _, i in gate_blocks]
    record['gate'] = gate
    lm.write_json(out / ('fidelity-r%d.json' % round_no), record)
    crops_look = call('zilal/lid/r%d/crops' % round_no, [{'type': 'text', 'text': crop_text}] + [b for b, _ in crop_blocks],
                      lm.CROPS_SCHEMA)
    crops_look['sent'] = [dict(i, crop=k) for (_, i), k in zip(crop_blocks, EYE_CROP_ORDER)]
    record['crops'] = crops_look
    defects = []
    if gate['payload'] is not None:
        defects += [d for d in gate['payload']['differences'] if d['verdict'] == 'defect']
    if crops_look['payload'] is not None:
        defects += [dict(c, where=EYE_CROP_ORDER[c['image'] - 1]) for c in crops_look['payload']['crops']
                    if c['verdict'] == 'defect' and 1 <= c['image'] <= len(EYE_CROP_ORDER)]
    record['answered'] = gate['payload'] is not None and crops_look['payload'] is not None
    record['defects'] = defects
    record['holds'] = bool(record['answered'] and not defects)
    lm.write_json(out / ('fidelity-r%d.json' % round_no), record)
    return record


# --- repair 1 of D-D11-3.7: the hatch registered on the sketch's own strokes -------------------------------------------

HATCH_RASTER_PX_PER_MM = 32.0           # the registered strokes are drawn on a 32 px/mm grid, then traced to vector


def phase_field(pick, letters, fit, sigma_mm):
    """The sketch's hatch phase as a smooth field (complex demodulation): inside the letters (past rim and groove)
    q = L* less its 20 px mean, z = q·exp(−2πi·d/pitch) on the fit's pitch and angle, low-passed (Gaussian σ 2 mm,
    normalised by the letters' own weight so the rims do not pull it). Returns the field as a complex image on the
    pick's grid (its angle is the painted strokes' local phase) and the local coherence |z̄| / mean|q|."""
    from shapely import contains_xy
    h, w = pick.shape[:2]
    light = lm.srgb_to_lab(pick)[..., 0].astype(np.float64)
    q = light - cv2.blur(light, (21, 21))
    ys, xs = np.mgrid[0:h, 0:w]
    xm, ym = (xs + 0.5) / PX_PER_MM_SRC, (ys + 0.5) / PX_PER_MM_SRC
    inner = contains_xy(letters.buffer(-HATCH_INSET_MM), xm, ym)
    a = np.radians(fit['angle_deg'])
    d = xm * np.sin(a) + ym * np.cos(a)
    z = np.where(inner, q * np.exp(-2j * np.pi * d / fit['pitch_mm']), 0)
    sigma = sigma_mm * PX_PER_MM_SRC
    weight = gaussian_filter(inner.astype(np.float64), sigma)
    zr = gaussian_filter(z.real, sigma) / np.maximum(weight, 1e-6)
    zi = gaussian_filter(z.imag, sigma) / np.maximum(weight, 1e-6)
    amp = gaussian_filter(np.where(inner, np.abs(q), 0.0), sigma) / np.maximum(weight, 1e-6)
    field = zr + 1j * zi
    return field, np.abs(field) / np.maximum(amp, 1e-6)


def registered_bands(letters, fit, stroke, field):
    """The hatch strokes registered on the sketch's own: each stroke where the phase u = d/pitch + angle(field)/2π is
    within half a stroke of a whole number (the painted strokes' centres), drawn on a 32 px/mm grid over the letters
    and traced back to polygons (mm). The pitch, the angle and the stroke's width stay the fit's; only the phase follows
    the sketch."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    x0, y0, x1, y1 = letters.bounds
    k = HATCH_RASTER_PX_PER_MM
    gw, gh = int((x1 - x0) * k) + 2, int((y1 - y0) * k) + 2
    ys, xs = np.mgrid[0:gh, 0:gw]
    xm, ym = x0 + (xs + 0.5) / k, y0 + (ys + 0.5) / k
    a = np.radians(fit['angle_deg'])
    d = xm * np.sin(a) + ym * np.cos(a)
    # the field on the fine grid: its real and imaginary parts resampled (never its wrapped angle)
    px, py = xm * PX_PER_MM_SRC - 0.5, ym * PX_PER_MM_SRC - 0.5
    fr = map_coordinates(field.real, [py, px], order=1, mode='nearest')
    fi = map_coordinates(field.imag, [py, px], order=1, mode='nearest')
    u = d / fit['pitch_mm'] + np.angle(fr + 1j * fi) / (2 * np.pi)
    frac = u - np.round(u)
    band = (np.abs(frac) <= stroke['stroke_mm'] / (2 * fit['pitch_mm'])).astype(np.uint8)
    contours, hierarchy = cv2.findContours(band, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    polys = []
    if hierarchy is not None:
        for i, c in enumerate(contours):
            if hierarchy[0][i][3] != -1 or len(c) < 3:
                continue
            outer = [(x0 + (p[0][0] + 0.5) / k, y0 + (p[0][1] + 0.5) / k) for p in c]
            holes = []
            child = hierarchy[0][i][2]
            while child != -1:
                hc = contours[child]
                if len(hc) >= 3:
                    holes.append([(x0 + (p[0][0] + 0.5) / k, y0 + (p[0][1] + 0.5) / k) for p in hc])
                child = hierarchy[0][child][0]
            poly = Polygon(outer, holes).buffer(0)
            if not poly.is_empty:
                polys.append(poly)
    return unary_union(polys)


def hero_foil_registered(pick, letters, fit, stroke):
    """The hero's foil with its hatch registered on the sketch's strokes (``registered_bands``), the rim and the groove
    as before, cleaned to the press. Returns the foil, the relief, what cleaning moved, and the registration measured:
    the share of the foil's hatch pixels that sit on the sketch's bright strokes (q > 0), before (the straight line
    system) and after."""
    from shapely.ops import unary_union
    rim = letters.difference(letters.buffer(-RIM_MM, join_style='mitre'))
    clip = letters.buffer(-(RIM_MM + GROOVE_MM), join_style='mitre')
    tried = []
    for sigma in PHASE_SIGMAS_MM:
        field, coherence = phase_field(pick, letters, fit, sigma)
        bands = registered_bands(letters, fit, stroke, field)
        tried.append((on_strokes(pick, bands, clip), sigma, field, coherence, bands))
    share, sigma, field, coherence, bands = max(tried, key=lambda t: t[0])
    raw = unary_union([rim, bands.intersection(clip)])
    clean = raw.buffer(-FOIL_OPEN_R_MM).buffer(FOIL_OPEN_R_MM).buffer(FOIL_CLOSE_R_MM).buffer(-FOIL_CLOSE_R_MM)
    straight = hero_foil(letters, fit, stroke)['foil']
    return {'foil': clean, 'relief': letters, 'rim': rim, 'moved_mm2': round(float(clean.symmetric_difference(raw).area), 4),
            'registration': {'on_painted_strokes_share': {'straight': on_strokes(pick, straight.difference(rim), clip),
                                                          'registered': on_strokes(pick, clean.difference(rim), clip)},
                             'coherence_median': round(float(np.median(coherence[coherence > 0])), 3),
                             'phase_sigma_mm': sigma, 'tried': {'%.1f' % t[1]: t[0] for t in tried}},
            'field': field}


ON_STROKES_SCALE = 4                    # the painted hatch is 3.2 px a pitch on the pick's grid: read at 4× (cubic)
PHASE_SIGMAS_MM = (0.5, 0.8, 1.2, 2.0)  # the phase field's smoothing tried; the one that lands the most foil on strokes


def on_strokes(pick, hatch, clip):
    """The share of a hatch's area (inside ``clip``) where the sketch's L* stands over its 20 px mean — the foil on the
    painted strokes, not on their gaps — read at 4× the pick (the hatch is 3.2 px a pitch at 1×, too coarse to read)."""
    light = lm.srgb_to_lab(pick)[..., 0].astype(np.float64)
    q = light - cv2.blur(light, (21, 21))
    q = cv2.resize(q, None, fx=ON_STROKES_SCALE, fy=ON_STROKES_SCALE, interpolation=cv2.INTER_CUBIC)
    m = lm.raster_fill(hatch.intersection(clip), q.shape, (0.0, 0.0), PX_PER_MM_SRC * ON_STROKES_SCALE)
    return round(float((q[m] > 0).mean()), 4)


# --- the re-look on corrected evidence (round 1's crops: the Arabic too small to read; the overlay's lines broken) -----

RELOOK_ARABIC_DPI = 1200.0              # the Arabic words large enough that every dot reads (round 1 sent them at ~580)
OVERLAY_LINE_RGB = (255, 0, 160)


def parts_counted(img, light_min):
    """The parts a crop draws (connected regions over ``light_min`` L*), and their areas, largest last."""
    m = (lm.srgb_to_lab(img)[..., 0] > light_min).astype(np.uint8)
    n, _, st, _ = cv2.connectedComponentsWithStats(m, 8)
    return n - 1, sorted(int(a) for a in st[1:, 4])


def arabic_relook_crops(out, rec):
    """باليت and العيون at 1200 dpi, the pick above the master, and each half's parts counted (the word's bodies and its
    dots) — the evidence that every dot the pick draws, the master draws."""
    pick = load_master_pick()
    k = RELOOK_ARABIC_DPI / lm.MM_PER_INCH
    master = lm._render(out / 'engine' / 'lid-engine.ai', RELOOK_ARABIC_DPI)
    files, counts = {}, {}
    for key in ('baliyt', 'aleyoun'):
        x0, y0, x1, y1 = rec['line_boxes_mm'][key]
        pad = lm.CROP_PAD_MM
        a, b, c, d = (int(v * k) for v in (x0 - pad, y0 - pad, x1 + pad, y1 + pad))
        sub = cv2.resize(pick[int((y0 - pad) * PX_PER_MM_SRC):int((y1 + pad) * PX_PER_MM_SRC) + 1,
                              int((x0 - pad) * PX_PER_MM_SRC):int((x1 + pad) * PX_PER_MM_SRC) + 1],
                         (c - a, d - b), interpolation=cv2.INTER_LANCZOS4)
        mine = master[b:d, a:c]
        files[key] = _pair(sub, mine, RELOOK_ARABIC_DPI, out / 'crops' / ('relook-%s.png' % key))
        counts[key] = {'pick': parts_counted(sub, 60.0)[0], 'master': parts_counted(mine, 60.0)[0]}
    return files, counts


def hatch_overlay_continuous(pick, letters, fit, stroke, path):
    """The registration made visible: the sketch in grey at print size (600 dpi), and each registered stroke's centre
    line drawn as a continuous opaque 1 px line (where the phase u = d/pitch + angle(field)/2π crosses a whole number,
    read pixel to pixel on the crop's own grid) inside the letters past rim and groove; beside it, each letter's share
    of foil on the painted strokes."""
    from shapely import contains_xy
    sigma = json.loads((OUT / 'master.json').read_text(encoding='utf-8'))['hero']['registration']['phase_sigma_mm']
    field, _ = phase_field(pick, letters, fit, sigma)
    x0, y0, x1, y1 = HATCH_CROP_BOX_PX
    dpi = HATCH_CROP_DPI
    k = dpi / lm.MM_PER_INCH
    box_mm = (x0 / PX_PER_MM_SRC, y0 / PX_PER_MM_SRC, x1 / PX_PER_MM_SRC, y1 / PX_PER_MM_SRC)
    w, h = int((box_mm[2] - box_mm[0]) * k), int((box_mm[3] - box_mm[1]) * k)
    grey = cv2.cvtColor(np.asarray(Image.fromarray(pick[y0:y1, x0:x1]).resize((w, h), Image.LANCZOS)), cv2.COLOR_RGB2GRAY)
    img = np.stack([grey] * 3, axis=-1).copy()
    ys, xs = np.mgrid[0:h, 0:w]
    xm, ym = box_mm[0] + (xs + 0.5) / k, box_mm[1] + (ys + 0.5) / k
    a = np.radians(fit['angle_deg'])
    d = xm * np.sin(a) + ym * np.cos(a)
    px, py = xm * PX_PER_MM_SRC - 0.5, ym * PX_PER_MM_SRC - 0.5
    f = map_coordinates(field.real, [py, px], order=1, mode='nearest') + 1j * map_coordinates(field.imag, [py, px],
                                                                                            order=1, mode='nearest')
    u = d / fit['pitch_mm'] + np.angle(f) / (2 * np.pi)
    whole = np.floor(u)
    cross = np.zeros((h, w), dtype=bool)
    # a stroke's centre: u steps across a whole number by a small step; where the field's angle wraps (±π) u jumps by
    # a whole pitch and nothing is crossed
    cross[:, 1:] |= (whole[:, 1:] != whole[:, :-1]) & (np.abs(u[:, 1:] - u[:, :-1]) < 0.5)
    cross[1:, :] |= (whole[1:, :] != whole[:-1, :]) & (np.abs(u[1:, :] - u[:-1, :]) < 0.5)
    inside = contains_xy(letters.buffer(-(RIM_MM + GROOVE_MM)), xm, ym)
    img[cross & inside] = OVERLAY_LINE_RGB
    Image.fromarray(img).save(path, dpi=(dpi, dpi))
    return path


def per_letter_registration(pick, letters, hero_foil_geom):
    """Each letter's share of foil hatch on the painted strokes (``on_strokes``), letter by letter."""
    clip = letters.buffer(-(RIM_MM + GROOVE_MM), join_style='mitre')
    rim = letters.difference(letters.buffer(-RIM_MM, join_style='mitre'))
    hatch = hero_foil_geom.difference(rim)
    rows = []
    for part in sorted(lm.parts(letters), key=lambda g: -g.bounds[2]):
        rows.append({'letter_box_mm': [round(v, 1) for v in part.bounds],
                     'on_painted_strokes_share': on_strokes(pick, hatch.intersection(part), clip.intersection(part))})
    return rows


def relook(out, rec, call):
    """One look by the eye on corrected evidence — not a repair, the master unchanged: باليت and العيون at 1200 dpi with
    their parts counted, and the hatch overlay redrawn as continuous lines on the grey sketch with the per-letter share.
    It holds when the eye answers and reads every image allowed. Written to fidelity-relook.json."""
    pick = load_master_pick()
    files, counts = arabic_relook_crops(out, rec)
    rings, _, _ = trace_hero(pick)
    letters = letters_geometry(rings)
    fit, stroke = rec['hero']['hatch']['fit'], rec['hero']['hatch']['stroke']
    overlay_path = hatch_overlay_continuous(pick, letters, fit, stroke, out / 'crops' / 'relook-hatch-overlay.png')
    sigma = rec['hero']['registration']['phase_sigma_mm']
    field, _ = phase_field(pick, letters, fit, sigma)
    per_letter = per_letter_registration(pick, letters, registered_foil(pick, letters, fit, stroke, field))
    blocks = [lm._image_block(files['baliyt']), lm._image_block(files['aleyoun']), lm._image_block(overlay_path)]
    text = ('FIDELITY GATE, A RE-LOOK ON CORRECTED EVIDENCE (Day 11). In the last look you read باليت and العيون in the '
            'master as missing their dots, and the hatch overlay as not showing the registration; the crops were too '
            'small (about 580 dpi) and the overlay\'s lines broke into dashes. The master is unchanged; only the '
            'evidence is redrawn. Images 1 and 2: باليت and العيون at 1200 dpi, THE PICK above the white rule, THE MASTER '
            'below. Counted by code (connected parts: the word\'s bodies and its dots): باليت pick %d, master %d; '
            'العيون pick %d, master %d. Image 3: the sketch in grey at 600 dpi with each foil stroke\'s centre line as a '
            'continuous magenta line (the strokes are 0.175 mm wide at a 0.395 mm pitch); the share of the foil hatch on '
            'the painted strokes, letter by letter right to left: %s. For each image: same letters (every dot), placed '
            'as the pick, any invented structure, and allowed (item 1–7 of the list below) or a defect. For image 3: do '
            'the lines sit on the sketch\'s light strokes? Answer in JSON.\n\n%s' % (
                counts['baliyt']['pick'], counts['baliyt']['master'], counts['aleyoun']['pick'], counts['aleyoun']['master'],
                ', '.join('%.0f %%' % (100 * r['on_painted_strokes_share']) for r in per_letter), allowed_differences()))
    look = call('zilal/lid/relook', [{'type': 'text', 'text': text}] + [b for b, _ in blocks], lm.CROPS_SCHEMA)
    look['sent'] = [dict(i, crop=k) for (_, i), k in zip(blocks, ('baliyt', 'aleyoun', 'hatch-overlay'))]
    answered = look['payload'] is not None
    holds = bool(answered and all(c['verdict'] == 'allowed' for c in look['payload']['crops']))
    record = {'schema': 'day11_zilal_fidelity/1', 'look': 'a re-look on corrected evidence (not a repair: the master is '
              'unchanged)', 'why': 'round 1 read باليت and العيون as dotless from crops at ~580 dpi (the files draw every '
              'dot: counted %s) and the overlay as unregistered from lines that broke into dashes' % counts,
              'parts_counted': counts, 'per_letter_registration': per_letter, 'look_record': look,
              'answered': answered, 'holds': holds}
    lm.write_json(out / 'fidelity-relook.json', record)
    return record


def registered_foil(pick, letters, fit, stroke, field):
    """The registered hatch's foil geometry for a given phase field (as ``hero_foil_registered`` builds it)."""
    from shapely.ops import unary_union
    rim = letters.difference(letters.buffer(-RIM_MM, join_style='mitre'))
    clip = letters.buffer(-(RIM_MM + GROOVE_MM), join_style='mitre')
    raw = unary_union([rim, registered_bands(letters, fit, stroke, field).intersection(clip)])
    return raw.buffer(-FOIL_OPEN_R_MM).buffer(FOIL_OPEN_R_MM).buffer(FOIL_CLOSE_R_MM).buffer(-FOIL_CLOSE_R_MM)
