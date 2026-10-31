"""Claude F2/F3: isolate stroke error from ground fit; retain old evidence."""
from pathlib import Path
import json, math
import cv2
import numpy as np
from PIL import Image
from . import fidelity_assets as fa, two_ink_matte as ti
from .matte_colour import lin, enc, lab, de

ROOT = fa.ROOT / 'docs/audit/day-6'
OLD = fa.ROOT / 'docs/audit/day-5/two-ink/poisson-attempt'


def corrected_proof(pixels, background, cream_rgba, shadow_rgba, envelope, cream_colour, *, ppi=300):
    size = (math.ceil(fa.WIDTH / 25.4 * ppi), math.ceil(fa.HEIGHT / 25.4 * ppi))
    f_rgb, f = ti.resize_linear_rgba(cream_rgba, size)
    s_rgb, s = ti.resize_linear_rgba(shadow_rgba, size)
    if np.max(f + s) > 1.005:
        raise ValueError('Ink weights exceed unity.')
    reference = ti.flat_map(lin(pixels), ppi); ground = ti.flat_map(lin(background), ppi)
    material = ground * np.maximum(0, 1 - f - s)[:, :, None]
    ink = lin(f_rgb) * f[:, :, None] + lin(s_rgb) * s[:, :, None]
    composite = ink + material
    sigma = .08 * ppi / 25.4
    blur = lambda x: cv2.GaussianBlur(x, (0, 0), sigma, borderType=cv2.BORDER_REFLECT_101)
    def float_encoded(x):
        return np.where(x <= .0031308, 12.92*x, 1.055*np.maximum(x, 0)**(1/2.4)-.055)*255
    delta = de(lab(float_encoded(blur(composite))), lab(float_encoded(blur(reference))))
    ground_delta = de(lab(float_encoded(blur(ground))), lab(float_encoded(blur(reference))))
    # F2: use actual reopened plane support, never the surrounding rectangular ROI.
    stroke = (f > .02) | (s > .02)
    region = ti.flat_map(envelope.astype(float), ppi, True) > .5
    pure_ground = region & ~stroke
    if not stroke.any() or not pure_ground.any():
        raise ValueError('Stroke and separately reported ground samples must both exist.')
    grey = lin(np.array([128, 128, 128]))
    neutral = ink + grey * np.maximum(0, 1-f-s)[:, :, None]
    clean = lin(cream_colour)*(f+s)[:, :, None] + grey*np.maximum(0, 1-f-s)[:, :, None]
    rgb = enc(neutral); hue = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)[:, :, 0].astype(float)*2
    err = de(lab(rgb), lab(enc(clean)))
    total = f+s
    boundary = ti.dilate(stroke, 1) & ~cv2.erode(stroke.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    boundary |= (total > .02) & (total < .98)
    visible = (np.hypot(lab(rgb)[:, :, 1], lab(rgb)[:, :, 2]) > 3) & (de(lab(rgb), lab(np.array([128]*3))) > 1)
    # F3: shadow support comes from the actual feathered full-resolution plane.
    own_shadow = s > .02
    flagged = boundary & ~own_shadow & (total > .02) & (hue >= 17) & (hue <= 35) & (err > 4) & visible
    fraction = float(np.mean(delta[stroke] <= 2))
    result = {'ppi': ppi, 'sigma_mm': .08, 'sigma_px': sigma, 'stroke_pixels': int(stroke.sum()),
              'support_rule': 'reopened cream alpha>0.02 OR shadow alpha>0.02',
              'recomposition_fraction_deltaE_le2': fraction, 'recomposition_passed': fraction >= .99,
              'stroke_deltaE_median': float(np.median(delta[stroke])), 'stroke_deltaE_p95': float(np.quantile(delta[stroke], .95)),
              'ground_only': {'pixels': int(pure_ground.sum()), 'median_deltaE': float(np.median(ground_delta[pure_ground])),
                              'p95_deltaE': float(np.quantile(ground_delta[pure_ground], .95)),
                              'fraction_deltaE_le2': float(np.mean(ground_delta[pure_ground] <= 2))},
              'fringe_flagged_pixels': int(flagged.sum()), 'fringe_passed': not bool(flagged.any()),
              'thresholds_unchanged': True}
    return result, enc(composite), rgb, flagged, stroke


def build(destination):
    p = Path(destination); p.mkdir(parents=True, exist_ok=False)
    pixels = np.array(Image.open(fa.CONCEPT).convert('RGB'))
    ground = np.array(Image.open(OLD / 'material-field.png').convert('RGB'))
    envelope = np.array(Image.open(OLD / 'stroke-support.png')) > 0
    previous = json.loads((OLD / 'fidelity-instrument.json').read_text())
    cream = np.array(previous['endmembers']['cream']['srgb']); shadow = np.array(previous['endmembers']['shadow']['srgb'])
    cr = np.array(Image.open(OLD / 'swoosh-cream.png')); sh = np.array(Image.open(OLD / 'swoosh-shadow.png'))
    # Full 1000-PPI solve, with the same full-stroke extraction region. No old
    # eroded shadow mask is used. One-pixel Gaussian feather in output coordinates.
    flat_p = ti.flat_map(lin(pixels), 1000); flat_b = ti.flat_map(lin(ground), 1000)
    f, s, _ = ti.triangle_weights(flat_p, flat_b, lin(cream), lin(shadow))
    whole = ti.flat_map(envelope.astype(float), 1000, True) > .5
    f *= whole; s *= whole
    s = cv2.GaussianBlur(s, (0, 0), 1, borderType=cv2.BORDER_REFLECT_101)
    s = np.minimum(s, 1-f)
    repaired = []
    for name, colour, alpha in [('cream', cream, f), ('shadow', shadow, s)]:
        a = np.round(np.clip(alpha, 0, 1)*255).astype(np.uint8)
        rgba = np.dstack([np.broadcast_to(colour.astype(np.uint8), a.shape+(3,)), a])
        Image.fromarray(rgba).save(p / ('swoosh-' + name + '.png')); repaired.append(rgba)
    rows = {}
    cases = [('day4', np.array(Image.open(fa.ROOT/'docs/audit/day-4/measurement-assets/swoosh-flat.png')), np.zeros_like(sh)),
             ('day5_single', np.array(Image.open(fa.ROOT/'docs/audit/day-5/matte-evaluation/swoosh-flat.png')), np.zeros_like(sh)),
             ('day5_two', cr, sh), ('full_resolution_shadow', *repaired)]
    for name, c, s in cases:
        result, amber, grey, flagged, stroke = corrected_proof(pixels, ground, c, s, envelope, cream)
        rows[name] = result
        for suffix, im in [('amber', amber), ('grey', grey), ('support', stroke.astype(np.uint8)*255)]:
            Image.fromarray(im).save(p / (name+'-'+suffix+'.png'))
        marked = grey.copy(); marked[flagged] = [255, 0, 140]
        Image.fromarray(marked).save(p / (name+'-fringe.png'))
    negatives = all(not (rows[n]['recomposition_passed'] and rows[n]['fringe_passed']) for n in ['day4', 'day5_single'])
    report = {'schema': 'day6_matte_instrument/1', 'claude_findings': ['F2', 'F3'], 'results': rows,
              'historical_whole_region_results': previous['results'], 'negative_controls_valid': negatives,
              'shadow_correction': 'Solve at1000PPI within original full stroke envelope; wS receives1output-pixel Gaussian feather, constrained by1-wF. No old frozen shadow mask.',
              'endmembers': previous['endmembers'], 'source_concept_sha256': fa.sha(fa.CONCEPT),
              'prior_instrument_sha256': fa.sha(OLD/'fidelity-instrument.json'),
              'retained_originals_unchanged': True, 'production_route': 'Vector device under D-D6-3; raster correction is diagnostic only'}
    report['asset_hashes'] = {x.name: fa.sha(x) for x in p.glob('*.png')}
    (p/'fidelity-instrument.json').write_text(json.dumps(report, indent=2)+'\n')
    if not negatives:
        raise ValueError('Historical negative passed both corrected gates; stop and investigate instrument.')
    return report
