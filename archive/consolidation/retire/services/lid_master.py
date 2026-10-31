"""Day 10 §1 — the print master of the owner's pick (D-D10-1 … D-D10-3): the sketch is the design.

The pick is ``docs/audit/day-9/sketches/A-2.3/lid.png`` (1536 × 970 px, the lid's 190 × 120 mm at 205 PPI). The master is
the sketch's own pixels made printable — nothing is redrawn (D-D10-1); the engine FITS, it never invents. The allowed
differences are D-D10-2's seven and no others:

1. resolution — the pick upscaled 2× by Lanczos (``upscale``), proven globally against the pick (``prove_upscale``:
   ΔE00 mean < 1.0, max < 4, SSIM > 0.97 at the pick's size) with its effective sharpness measured (``sharpness``);
2. the small words live — each line's letters and their emboss rim cleaned out of the upscale by a Poisson solve whose
   guidance is clean ground from the same picture and whose boundary is the picture itself (``clean_glyphs``: the
   glyphs only, never their box), then set live at the sketch's position, size, colour and angle;
3. the name as a vector logotype — traced from the sketch's own letters (``trace_name``: potrace on the letters' soft
   alpha, proven by overlay within 0.3 mm and IoU), its foil mask those outlines, the raster gold left underneath;
4. the logo — the approved vector (``docs/brand/mark/bbrose-logo.svg``) fitted to the sketch's place and size
   (``fit_logo``), in ink in the sketch's gold; its letters foiled only if they alone pass the foil limits;
5. finishes separated, not redrawn — foil only on crisp gold (``crisp_gold``: colour AND edge sharpness), painted
   light with soft edges printed as raster; relief only where A-2's spec declared it and the edge is crisp
   (``bar_edges`` measures the bars against the sketch's own crisp lettering);
6. bleed — 3 mm by mirroring the picture's own edges (``bleed``); nothing inside the trim moves;
7. the measured checks run as reports.

Every function here is deterministic and costs $0; the paid looks (the designer's eye, the jury) are made by
``lid_master_run`` through the ledger.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, map_coordinates, uniform_filter1d
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import splu
from shapely import affinity
from shapely.geometry import Polygon

from .round_files_faces import delta_e00, srgb_to_lab

REPO = Path(__file__).resolve().parents[4]
PICK = REPO / 'docs' / 'audit' / 'day-9' / 'sketches' / 'A-2.3' / 'lid.png'
PICK_SHA256 = '4293fe8b20a8c39e9776e433267fd6b36bfa89ca72f4381710f32a639f797de8'
LOGO_SVG = REPO / 'bbrose_design_os' / 'docs' / 'brand' / 'mark' / 'bbrose-logo.svg'
LOGO_SHA256 = 'ccf120cef3e8317dc0a3dce36673709a104e9456a4eeb15b36722103d65b19ed'
OUT = REPO / 'docs' / 'audit' / 'day-10' / 'lid'
SCHEMA = 'day10_lid_master/1'

LID_MM = (190.0, 120.0)
PICK_PX = (1536, 970)
UP = 2                                    # D-D10-2.1: upscale 2×
PX_PER_MM_SRC = PICK_PX[0] / LID_MM[0]    # 8.084 px/mm, 205 PPI
PX_PER_MM = PX_PER_MM_SRC * UP            # 16.168 px/mm, 410.7 PPI
BLEED_MM = 3.0
SAFE_MM = 4.0
MM_PER_INCH = 25.4

UPSCALE_DE_MEAN_MAX = 1.0                 # D-D10-2.1's global proof
UPSCALE_DE_MAX = 4.0
UPSCALE_SSIM_MIN = 0.97
SSIM_SIGMA = 1.5
SSIM_TRUNCATE = 3.5
SSIM_K1 = 0.01
SSIM_K2 = 0.03
PRINT_PPI_MIN = 300.0                     # D-D8-4

TEXT_ALPHA_CORE = 0.08                    # a pixel belongs to a glyph from 8 % of the way to the type's colour
TEXT_RIM_SRC_PX = 2                       # the sketch's letters carry a 1 px dark emboss rim: cleaned with them
TEXT_GROUND_LMAX = 25.0                   # the deep teal-ink ground reads L* 10–17 around the small lines
TEXT_GROUND_LMIN = 6.0
TEXT_BG_BLUR_PX = 31
TEXT_LIGHT_L = 85.0                       # the warm-white type's lightness (measured L* 82–93)

NAME_TRACE_SCALE = 8                      # the trace runs on the letters' alpha enlarged 8× (cubic)
NAME_ALPHAMAX = '1.0'
NAME_OPTTOLERANCE = '0.2'
NAME_TURDSIZE = '20'
NAME_SPECK_MM2 = 0.05
NAME_BG_BLUR_PX = 41
NAME_OVERLAY_MAX_MM = 0.3                 # D-D10-2.3's proof
MASK_IOU_MIN = 0.95                       # D-D10-1's proof for a fitted mask
PROOF_RASTER = 16                         # the proof's reference contour is read at 16× the pick

FOIL_LINE_MIN_MM = 0.1                    # D-D10-2.5's foil limits
FOIL_GAP_MIN_MM = 0.2

POSITION_TOL_MM = 1.0                     # D-D10-1: type and the logo within 1 mm and 3 %
SIZE_TOL = 0.03


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_pick(path):
    """The pick as RGB uint8, refused unless its bytes are the pick's."""
    digest = sha256(path)
    if digest != PICK_SHA256:
        raise ValueError(f'not the owner\'s pick: {path} has sha256 {digest}')
    rgb = np.asarray(Image.open(path).convert('RGB'))
    if rgb.shape[1] != PICK_PX[0] or rgb.shape[0] != PICK_PX[1]:
        raise ValueError(f'the pick is {rgb.shape[1]} × {rgb.shape[0]} px, not {PICK_PX[0]} × {PICK_PX[1]}')
    return rgb


def luma(rgb):
    c = np.asarray(rgb, dtype=np.float64)
    return 0.299 * c[..., 0] + 0.587 * c[..., 1] + 0.114 * c[..., 2]


def ssim(x, y):
    """Mean SSIM (Wang et al. 2004): Gaussian window σ 1.5, K1 0.01, K2 0.03, L 255; the border the window cannot
    cover whole is left out."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    c1, c2 = (SSIM_K1 * 255.0) ** 2, (SSIM_K2 * 255.0) ** 2

    def blur(z):
        return gaussian_filter(z, SSIM_SIGMA, truncate=SSIM_TRUNCATE)

    mx, my = blur(x), blur(y)
    sxx, syy, sxy = blur(x * x) - mx * mx, blur(y * y) - my * my, blur(x * y) - mx * my
    m = ((2 * mx * my + c1) * (2 * sxy + c2)) / ((mx * mx + my * my + c1) * (sxx + syy + c2))
    pad = int(SSIM_TRUNCATE * SSIM_SIGMA + 0.5)
    return float(m[pad:-pad, pad:-pad].mean())


# --- 1. resolution --------------------------------------------------------------------------------------------------

def upscale(rgb):
    """D-D10-2.1's baseline: Lanczos (OpenCV's 8 × 8 Lanczos kernel), 2×."""
    h, w = rgb.shape[:2]
    return cv2.resize(rgb, (w * UP, h * UP), interpolation=cv2.INTER_LANCZOS4)


def downsample(up, size):
    """The upscale brought back to the pick's size for the proof: Lanczos again, PIL's 6-tap kernel."""
    return np.asarray(Image.fromarray(up).resize(size, Image.LANCZOS))


def prove_upscale(pick, up, zones):
    """D-D10-2.1's global proof at the pick's size, and where any pixel over the max lies (``zones``: name → box
    in pick px, x0 y0 x1 y1)."""
    down = downsample(up, (pick.shape[1], pick.shape[0]))
    de = delta_e00(srgb_to_lab(pick), srgb_to_lab(down))
    s = ssim(luma(pick), luma(down))
    over = de > UPSCALE_DE_MAX
    ys, xs = np.nonzero(over)
    where = {}
    placed = np.zeros(len(ys), dtype=bool)
    for name, (x0, y0, x1, y1) in zones.items():
        inside = (xs >= x0) & (xs < x1) & (ys >= y0) & (ys < y1) & ~placed
        where[name] = int(inside.sum())
        placed |= inside
    where['elsewhere'] = int((~placed).sum())
    return {
        'method': 'cv2.INTER_LANCZOS4 2× up; PIL Image.LANCZOS down to the pick\'s size; CIEDE2000 per pixel on '
                  'sRGB → Lab (D65); SSIM on luma (Wang 2004, σ 1.5)',
        'de00_mean': round(float(de.mean()), 4),
        'de00_p99': round(float(np.percentile(de, 99)), 3),
        'de00_p999': round(float(np.percentile(de, 99.9)), 3),
        'de00_max': round(float(de.max()), 3),
        'ssim': round(s, 5),
        'pixels_over_max': int(over.sum()),
        'pixels_over_max_share': round(float(over.mean()), 6),
        'pixels_over_max_where': where,
        'holds': {
            'de00_mean': bool(de.mean() < UPSCALE_DE_MEAN_MAX),
            'de00_max': bool(de.max() < UPSCALE_DE_MAX),
            'ssim': bool(s > UPSCALE_SSIM_MIN),
        },
        'bars': {'de00_mean_lt': UPSCALE_DE_MEAN_MAX, 'de00_max_lt': UPSCALE_DE_MAX, 'ssim_gt': UPSCALE_SSIM_MIN},
    }


def spectrum_share_above(gray, cycles_per_px):
    """The share of a luma image's spectral energy (DC removed, Hann-windowed) above a radial frequency."""
    g = np.asarray(gray, dtype=np.float64)
    g = g - g.mean()
    win = np.outer(np.hanning(g.shape[0]), np.hanning(g.shape[1]))
    p = np.abs(np.fft.fft2(g * win)) ** 2
    fy = np.fft.fftfreq(g.shape[0])[:, None]
    fx = np.fft.fftfreq(g.shape[1])[None, :]
    r = np.hypot(fx, fy)
    return float(p[r > cycles_per_px].sum() / p.sum())


def edge_rise_mm(lightness, rows, x0, x1, px_per_mm, min_step):
    """The median 10–90 % rise of the edges met along horizontal profiles (rows, x0–x1), each profile sampled at a
    quarter pixel; an edge counts when its step is at least ``min_step`` L*."""
    rises = []
    xs = np.arange(x0, x1, 0.25)
    for y in rows:
        p = map_coordinates(lightness, [np.full(len(xs), float(y)), xs], order=3)
        d = np.diff(p)
        thr = 0.25 * np.abs(d).max()
        i = 1
        while i < len(d) - 1:
            if abs(d[i]) >= thr and abs(d[i]) >= abs(d[i - 1]) and abs(d[i]) >= abs(d[i + 1]):
                s = np.sign(d[i])
                a = i
                b = i
                while a > 0 and np.sign(d[a - 1]) == s:
                    a -= 1
                while b < len(d) - 1 and np.sign(d[b + 1]) == s:
                    b += 1
                seg = p[a:b + 2]
                if s < 0:
                    seg = seg[::-1]
                lo, hi = seg[0], seg[-1]
                amp = hi - lo
                if amp >= min_step:
                    t10 = np.argmax(seg >= lo + 0.1 * amp)
                    t90 = np.argmax(seg >= lo + 0.9 * amp)
                    rises.append((t90 - t10) * 0.25 / px_per_mm)
                i = b + 1
            else:
                i += 1
    return float(np.median(rises)), len(rises)


def sharpness(pick, up, name_box):
    """D-D10-2.1's measured effective sharpness, said honestly: (a) the share of the upscale's luma energy above the
    pick's own Nyquist (0.25 cycles per upscaled px) — detail a native 410 PPI picture would carry there and a resample
    cannot add; (b) the 10–90 % rise of the name's letter edges in mm, in the pick and in the upscale — the same in mm
    when nothing was sharpened; effective PPI as the pick's own when (a) is near nothing and (b) does not shrink."""
    x0, y0, x1, y1 = name_box
    l_src = srgb_to_lab(pick)[..., 0]
    l_up = srgb_to_lab(up)[..., 0]
    rows_src = range(y0 + 20, y1 - 20, 4)
    rows_up = range(UP * (y0 + 20), UP * (y1 - 20), UP * 4)
    rise_src, n_src = edge_rise_mm(l_src, rows_src, x0, x1, PX_PER_MM_SRC, 25.0)
    rise_up, n_up = edge_rise_mm(l_up, rows_up, UP * x0, UP * x1, PX_PER_MM, 25.0)
    share_up = spectrum_share_above(luma(up), 0.25)
    share_src_top_half = spectrum_share_above(luma(pick), 0.25)
    src_ppi = PX_PER_MM_SRC * MM_PER_INCH
    up_ppi = PX_PER_MM * MM_PER_INCH
    effective = src_ppi
    if rise_up < 0.75 * rise_src:
        effective = up_ppi
    return {
        'source_ppi': round(src_ppi, 1),
        'resampled_ppi': round(up_ppi, 1),
        'energy_above_source_nyquist_share': round(share_up, 6),
        'source_energy_in_its_top_half_band_share': round(share_src_top_half, 6),
        'name_edge_rise_10_90_mm': {'pick': round(rise_src, 4), 'upscale': round(rise_up, 4),
                                    'edges_read': {'pick': n_src, 'upscale': n_up}},
        'effective_ppi': round(effective, 1),
        'print_ppi_300': {'nominal_met': bool(up_ppi >= PRINT_PPI_MIN), 'effective_met': bool(effective >= PRINT_PPI_MIN)},
    }


# --- 2. small words: masks, cleaning ----------------------------------------------------------------------------------

def light_glyph_alpha(pick, box):
    """The warm-white type's soft alpha inside a box of the pick (x0 y0 x1 y1): 0 on the local ground, 1 at the type's
    lightness."""
    x0, y0, x1, y1 = box
    lightness = srgb_to_lab(pick[y0:y1, x0:x1])[..., 0]
    ground = (lightness > TEXT_GROUND_LMIN) & (lightness < TEXT_GROUND_LMAX)
    fill = np.where(ground, lightness, np.median(lightness[ground])).astype(np.float32)
    lbg = cv2.blur(fill, (TEXT_BG_BLUR_PX, TEXT_BG_BLUR_PX))
    return np.clip((lightness - lbg) / (TEXT_LIGHT_L - lbg), 0, 1)


def glyph_clean_mask(alpha):
    """The pixels to clean for one line, on the upscale's grid: every glyph pixel and its 1 px emboss rim (dilated by
    two pick px), then one more upscaled pixel — the glyphs, never their box."""
    core = (alpha > TEXT_ALPHA_CORE).astype(np.uint8)
    k = 2 * TEXT_RIM_SRC_PX + 1
    grown = cv2.dilate(core, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    h, w = grown.shape
    up = cv2.resize(grown, (w * UP, h * UP), interpolation=cv2.INTER_NEAREST)
    return cv2.dilate(up, np.ones((3, 3), np.uint8)).astype(bool)


def poisson_fill(image, guide, mask):
    """Solve Poisson's equation inside ``mask``: the result has the guide's Laplacian inside the mask and the image's
    own values on the mask's outer boundary (Pérez, Gangnet and Blake 2003). Float in, float out (H × W × C)."""
    m = mask.copy()
    m[0, :] = False
    m[-1, :] = False
    m[:, 0] = False
    m[:, -1] = False
    ys, xs = np.nonzero(m)
    n = len(ys)
    index = -np.ones(m.shape, dtype=np.int64)
    index[ys, xs] = np.arange(n)
    rows, cols, vals = [np.arange(n)], [np.arange(n)], [np.full(n, 4.0)]
    rhs = np.zeros((n, image.shape[2]))
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        ny, nx = ys + dy, xs + dx
        inside = m[ny, nx]
        rows.append(np.arange(n)[inside])
        cols.append(index[ny[inside], nx[inside]])
        vals.append(np.full(int(inside.sum()), -1.0))
        rhs += guide[ys, xs] - guide[ny, nx]
        rhs[~inside] += image[ny[~inside], nx[~inside]]
    a = coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n)).tocsc()
    lu = splu(a)
    out = image.copy()
    for c in range(image.shape[2]):
        out[ys, xs, c] = lu.solve(rhs[:, c])
    return out


# --- 3. the name ------------------------------------------------------------------------------------------------------

def gold_alpha(pick, box):
    """The gold lettering's soft alpha over the dark ground inside a box (x0 y0 x1 y1): half from L* and half from b*,
    each read against the local ground (its blur with the letters replaced by the ground's median)."""
    x0, y0, x1, y1 = box
    lab = srgb_to_lab(pick[y0:y1, x0:x1])
    lightness, yellow = lab[..., 0], lab[..., 2]
    chroma = np.hypot(lab[..., 1], lab[..., 2])
    ground = (chroma < 12) | (lightness < 18)
    letters = (lightness > 45) & (yellow > 25)

    def local(ch):
        t = np.where(ground, ch, np.median(ch[ground])).astype(np.float32)
        return cv2.blur(t, (NAME_BG_BLUR_PX, NAME_BG_BLUR_PX))

    lb, bb = local(lightness), local(yellow)
    tl = (lightness - lb) / (np.median(lightness[letters]) - lb)
    tb = (yellow - bb) / (np.median(yellow[letters]) - bb)
    return np.clip(0.5 * tl + 0.5 * tb, 0, 1)


_TOK = re.compile(r'[MmLlCcZz]|-?\d+(?:\.\d+)?')


def parse_path(d, transform):
    """An SVG path's data (M/L/C/Z, absolute or relative, as potrace writes them) → rings of segments, each
    ('L', p0, p1) or ('C', p0, c1, c2, p1), every point passed through ``transform``."""
    toks = _TOK.findall(d)
    rings = []
    ring = None
    cur = np.zeros(2)
    start = np.zeros(2)
    cmd = 'M'
    i = 0
    while i < len(toks):
        t = toks[i]
        if t in 'MmLlCcZz':
            cmd = t
            i += 1
            if cmd in 'Zz':
                if ring is not None and np.hypot(*(cur - start)) > 1e-9:
                    ring.append(('L', transform(cur), transform(start)))
                if ring:
                    rings.append(ring)
                ring = None
                cur = start.copy()
            continue
        if cmd in 'Mm':
            p = np.array([float(toks[i]), float(toks[i + 1])])
            i += 2
            cur = p if cmd == 'M' else cur + p
            start = cur.copy()
            ring = []
            cmd = 'L' if cmd == 'M' else 'l'
        elif cmd in 'Ll':
            p = np.array([float(toks[i]), float(toks[i + 1])])
            i += 2
            nxt = p if cmd == 'L' else cur + p
            ring.append(('L', transform(cur), transform(nxt)))
            cur = nxt
        else:
            v = np.array([float(x) for x in toks[i:i + 6]]).reshape(3, 2)
            i += 6
            pts = v if cmd == 'C' else cur + v
            ring.append(('C', transform(cur), transform(pts[0]), transform(pts[1]), transform(pts[2])))
            cur = pts[2]
    if ring:
        rings.append(ring)
    return rings


def flatten(ring, steps):
    """A ring of segments → its polyline (each curve cut into ``steps``)."""
    out = []
    for seg in ring:
        if seg[0] == 'L':
            out.append(seg[1])
            continue
        p0, c1, c2, p1 = (np.asarray(p, dtype=np.float64) for p in seg[1:])
        for t in np.linspace(0, 1, steps, endpoint=False):
            out.append(tuple((1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * c1 + 3 * (1 - t) * t * t * c2 + t ** 3 * p1))
    return np.asarray(out, dtype=np.float64)


def parts(geom):
    """A shapely geometry's polygons (a MultiPolygon's parts, or the polygon itself)."""
    if hasattr(geom, 'geoms'):
        return list(geom.geoms)
    return [geom]


def rings_area(rings, steps):
    """Rings filled even-odd (potrace's nested contours) as one shapely geometry."""
    geom = None
    for ring in rings:
        pts = flatten(ring, steps)
        if len(pts) < 3:
            continue
        poly = Polygon(pts).buffer(0)
        if geom is None:
            geom = poly
        else:
            geom = geom.symmetric_difference(poly)
    return geom


def map_rings(rings, fn):
    return [[(seg[0],) + tuple(fn(np.asarray(p, dtype=np.float64)) for p in seg[1:]) for seg in ring] for ring in rings]


def potrace_rings(bitmap):
    """potrace (1.16) on a boolean bitmap (True = ink), with the name's settings; rings in the bitmap's px (y down)."""
    with tempfile.TemporaryDirectory() as tmp:
        pbm = Path(tmp) / 'in.pbm'
        svg = Path(tmp) / 'out.svg'
        Image.fromarray(((~bitmap) * 255).astype(np.uint8)).convert('1').save(pbm)
        subprocess.run(['potrace', str(pbm), '-s', '-o', str(svg), '-a', NAME_ALPHAMAX, '-O', NAME_OPTTOLERANCE,
                        '-t', NAME_TURDSIZE, '--flat'], check=True, capture_output=True)
        text = svg.read_text()
    m = re.search(r'translate\(([-\d.]+),([-\d.]+)\) scale\(([-\d.]+),([-\d.]+)\)', text)
    tx, ty, sx, sy = (float(v) for v in m.groups())
    rings = []
    for d in re.findall(r' d="([^"]+)"', text):
        rings.extend(parse_path(d, lambda p: (tx + sx * p[0], ty + sy * p[1])))
    return rings


def trace_name(pick, box):
    """D-D10-2.3: the name traced from the sketch's own letters. The letters' soft alpha (``gold_alpha``) is enlarged
    8× by cubic interpolation and cut at one half; specks under 0.05 mm² are dropped; potrace smooths the outlines.
    Returns the rings in mm on the lid (origin top-left), the alpha, and the trace's proof: the outline's distance to
    the sketch's letter edges (the alpha's half contour read at 16× the pick, independently of the trace's 8× grid),
    both ways, and the IoU of the two fills at 16×."""
    x0, y0, x1, y1 = box
    alpha = gold_alpha(pick, box)
    h, w = alpha.shape
    s = NAME_TRACE_SCALE
    big = cv2.resize(alpha.astype(np.float32), (w * s, h * s), interpolation=cv2.INTER_CUBIC) >= 0.5
    n, labels, stats, _ = cv2.connectedComponentsWithStats(big.astype(np.uint8), 8)
    min_area = NAME_SPECK_MM2 * (PX_PER_MM_SRC * s) ** 2
    keep = np.zeros(n, dtype=bool)
    keep[1:] = stats[1:, 4] >= min_area
    bitmap = keep[labels]
    rings_px = potrace_rings(bitmap)
    rings_mm = map_rings(rings_px, lambda p: ((x0 + p[0] / s) / PX_PER_MM_SRC, (y0 + p[1] / s) / PX_PER_MM_SRC))
    proof = prove_outline(alpha, box, rings_mm)
    proof['letters'] = int(keep.sum())
    return rings_mm, alpha, proof


def raster_fill(geom, shape, origin_mm, px_per_mm):
    """A shapely geometry in mm → a boolean raster of ``shape`` whose pixel (0, 0) starts at ``origin_mm``."""
    canvas = np.zeros(shape, dtype=np.uint8)
    ox, oy = origin_mm
    for g in parts(geom):
        ext = (np.asarray(g.exterior.coords) - [ox, oy]) * px_per_mm
        cv2.fillPoly(canvas, [np.round(ext * 16).astype(np.int32)], 1, shift=4)
        for hole in g.interiors:
            hh = (np.asarray(hole.coords) - [ox, oy]) * px_per_mm
            cv2.fillPoly(canvas, [np.round(hh * 16).astype(np.int32)], 0, shift=4)
    return canvas.astype(bool)


def prove_outline(alpha, box, rings_mm):
    """The overlay proof of a trace against the sketch: distances in mm (trace → sketch edge, sketch edge → trace),
    the IoU of the fills, all read at 16× the pick."""
    from scipy.spatial import cKDTree
    x0, y0, x1, y1 = box
    h, w = alpha.shape
    r = PROOF_RASTER
    ref = cv2.resize(alpha.astype(np.float32), (w * r, h * r), interpolation=cv2.INTER_CUBIC) >= 0.5
    contours, _ = cv2.findContours(ref.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    ref_pts = np.concatenate([c[:, 0, :] for c in contours if len(c) > 10]).astype(np.float64) / r
    ref_mm = (ref_pts + [x0, y0]) / PX_PER_MM_SRC
    geom = rings_area(rings_mm, 24)
    boundary = []
    for g in parts(geom):
        for ring in [g.exterior, *g.interiors]:
            n = max(int(ring.length * PX_PER_MM_SRC * 8), 8)
            boundary.extend(ring.interpolate(t).coords[0] for t in np.linspace(0, ring.length, n, endpoint=False))
    boundary = np.asarray(boundary)
    d_trace, _ = cKDTree(ref_mm).query(boundary)
    d_ref, _ = cKDTree(boundary).query(ref_mm)
    fill = raster_fill(geom, ref.shape, (x0 / PX_PER_MM_SRC, y0 / PX_PER_MM_SRC), PX_PER_MM_SRC * r)
    iou = float((fill & ref).sum() / (fill | ref).sum())
    worst = max(float(d_trace.max()), float(d_ref.max()))
    return {
        'trace_to_sketch_max_mm': round(float(d_trace.max()), 4),
        'trace_to_sketch_p99_mm': round(float(np.percentile(d_trace, 99)), 4),
        'sketch_to_trace_max_mm': round(float(d_ref.max()), 4),
        'sketch_to_trace_p99_mm': round(float(np.percentile(d_ref, 99)), 4),
        'iou': round(iou, 4),
        'area_mm2': round(float(geom.area), 2),
        'holds': {'within_0_3_mm': bool(worst <= NAME_OVERLAY_MAX_MM), 'iou_0_95': bool(iou >= MASK_IOU_MIN)},
        'reference': 'the sketch\'s letter edges: the letters\' soft alpha cut at one half, read at 16× the pick '
                     '(the trace ran on an 8× grid)',
    }


# --- 4. the logo ------------------------------------------------------------------------------------------------------

LOGO_PARTS = {0: 'mark', 1: 'S', 2: 'R stem', 3: 'R', 4: 'B2', 5: 'B1', 6: 'E', 7: '® ring', 8: '® R'}
LOGO_LETTERS = (1, 2, 3, 4, 5, 6)
LOGO_REGISTERED = (7, 8)
LOGO_MARK = (0,)


def logo_paths():
    """The approved master's nine paths as rings in the SVG's user units (y down), refused unless its bytes are the
    master's (``docs/brand/mark/approval.json``)."""
    if sha256(LOGO_SVG) != LOGO_SHA256:
        raise ValueError('the logo SVG is not the approved master')
    svg = LOGO_SVG.read_text()
    g = re.search(r'<g transform="translate\(([-\d.]+),([-\d.]+)\) scale\(([-\d.]+),([-\d.]+)\)"', svg)
    tx, ty, sx, sy = (float(v) for v in g.groups())
    out = []
    for attrs in re.findall(r'<path([^>]*)/?>', svg):
        d = re.search(r' d="([^"]+)"', attrs).group(1)
        if 'fill-rule' in attrs:
            out.append(parse_path(d, lambda p: (float(p[0]), float(p[1]))))
        else:
            out.append(parse_path(d, lambda p, tx=tx, ty=ty, sx=sx, sy=sy: (tx + sx * p[0], ty + sy * p[1])))
    return out


def logo_mask_in_sketch(pick, box):
    """The sketch's logo: its gold (L* > 40, b* > 20) inside the logo's box."""
    x0, y0, x1, y1 = box
    lab = srgb_to_lab(pick[y0:y1, x0:x1])
    return (lab[..., 0] > 40) & (lab[..., 2] > 20)


def fit_logo(pick, box):
    """D-D10-2.4: the approved vector placed at the sketch's place and size — a uniform scale and a shift found by
    climbing the IoU of the drawn master against the sketch's logo gold (coarse to fine), started from the two ink
    boxes. Returns the transform (unit → lid mm) and its proof: the placed ink box against the sketch's, in mm and %."""
    x0, y0, x1, y1 = box
    target = logo_mask_in_sketch(pick, box)
    ys, xs = np.nonzero(target)
    paths = logo_paths()
    geoms = [rings_area(p, 12) for p in paths]
    ux0, uy0, ux1, uy1 = 8.632684, 8.27, 1387.948, 295.982086     # approval.json's ink_bounds
    r = 4

    def draw(scale, tx, ty):
        canvas = np.zeros(((y1 - y0) * r, (x1 - x0) * r), dtype=np.uint8)
        for g in geoms:
            for gg in parts(g):
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
    scale_mm = s / PX_PER_MM_SRC
    placed = [(tx + ux0 * s) / PX_PER_MM_SRC, (ty + uy0 * s) / PX_PER_MM_SRC,
              (tx + ux1 * s) / PX_PER_MM_SRC, (ty + uy1 * s) / PX_PER_MM_SRC]
    sketch = [sx0 / PX_PER_MM_SRC, sy0 / PX_PER_MM_SRC, sx1 / PX_PER_MM_SRC, (y0 + ys.max() + 1) / PX_PER_MM_SRC]
    width_ratio = (placed[2] - placed[0]) / (sketch[2] - sketch[0])
    corner = max(abs(placed[0] - sketch[0]), abs(placed[1] - sketch[1]))
    # the placement is read on every edge and the centre, as overlay_proof reads a line (the top-left corner alone
    # hid the right edge's 0.74 mm: the adversarial review of Day 10)
    edges = [abs(a - b) for a, b in zip(placed, sketch)]
    centre = [abs((placed[0] + placed[2]) / 2 - (sketch[0] + sketch[2]) / 2),
              abs((placed[1] + placed[3]) / 2 - (sketch[1] + sketch[3]) / 2)]
    shift = max(edges + centre)
    return {
        'transform': {'scale_mm_per_unit': scale_mm, 'tx_mm': tx / PX_PER_MM_SRC, 'ty_mm': ty / PX_PER_MM_SRC},
        'placed_ink_box_mm': [round(c, 3) for c in placed],
        'sketch_ink_box_mm': [round(c, 3) for c in sketch],
        'width_ratio': round(width_ratio, 4),
        'corner_shift_mm': round(corner, 3),
        'edge_shift_mm': {'left': round(edges[0], 3), 'top': round(edges[1], 3), 'right': round(edges[2], 3),
                          'bottom': round(edges[3], 3), 'centre_x': round(centre[0], 3), 'centre_y': round(centre[1], 3)},
        'worst_shift_mm': round(shift, 3),
        'iou_with_sketch_gold': round(v, 4),
        'holds': {'within_1_mm': bool(shift <= POSITION_TOL_MM), 'within_3_pct': bool(abs(width_ratio - 1) <= SIZE_TOL)},
        'note': 'the IoU is read against the sketch\'s gold only (its bevelled rims excluded) and the sketch\'s mark '
                'is the image model\'s drawing of the master, so the IoU measures the fit, never the master',
    }


def logo_rings_mm(transform, which):
    """The master's chosen paths placed on the lid (mm)."""
    k = transform['scale_mm_per_unit']
    tx, ty = transform['tx_mm'], transform['ty_mm']
    paths = logo_paths()
    out = []
    for i in which:
        out.extend(map_rings(paths[i], lambda p: (tx + k * p[0], ty + k * p[1])))
    return out


# --- 5. finishes ------------------------------------------------------------------------------------------------------

def structure_normal(lightness, box):
    """The dominant gradient direction (unit dx, dy) inside a box — across the bars."""
    x0, y0, x1, y1 = box
    ls = cv2.GaussianBlur(lightness.astype(np.float32), (0, 0), 3)
    gx = cv2.Sobel(ls, cv2.CV_32F, 1, 0, ksize=3)[y0:y1, x0:x1]
    gy = cv2.Sobel(ls, cv2.CV_32F, 0, 1, ksize=3)[y0:y1, x0:x1]
    j = np.array([[np.sum(gx * gx), np.sum(gx * gy)], [np.sum(gx * gy), np.sum(gy * gy)]])
    _, v = np.linalg.eigh(j)
    return v[:, 1]


def engraving_envelope(lightness):
    """The fine engraving's local strength: |band-pass(σ 0.7 − σ 2.0 px)| blurred σ 2 px — high where fine lines are."""
    lf = lightness.astype(np.float32)
    band = cv2.GaussianBlur(lf, (0, 0), 0.7) - cv2.GaussianBlur(lf, (0, 0), 2.0)
    return cv2.GaussianBlur(np.abs(band), (0, 0), 2.0)


def _rise_px(profile, step):
    lo = profile.min()
    amp = profile.max() - lo
    top = profile[:int(np.argmax(profile)) + 1]
    return (np.argmax(top >= lo + 0.9 * amp) - np.argmax(top >= lo + 0.1 * amp)) * step


ENGRAVING_PITCH_PX = 3.30           # the engraving's pitch as engraving_lines reads it (0.408 mm): an average this wide nulls it
RISE_WINDOW_PX = 12.0               # one window for both: the monotone run about the steepest change, ±12 pick px (1.5 mm)
RISE_STEP_MIN = 8.0                 # an edge counts when its run spans at least 8 L*


def _monotone_rise(profile, i, step):
    """The 10–90 % rise (px) of the monotone run through sample ``i`` of a profile sampled every ``step`` px, the run
    bounded by the window; ``None`` when the run spans under RISE_STEP_MIN L*."""
    d = np.diff(profile)
    sign = np.sign(d[i])
    reach = int(RISE_WINDOW_PX / step)
    a, b = i, i
    while a > max(i - reach, 0) and np.sign(d[a - 1]) == sign:
        a -= 1
    while b < min(i + reach, len(d) - 1) and np.sign(d[b + 1]) == sign:
        b += 1
    seg = profile[a:b + 2]
    if sign < 0:
        seg = seg[::-1]
    lo, amp = seg[0], seg[-1] - seg[0]
    if amp < RISE_STEP_MIN:
        return None
    return (np.argmax(seg >= lo + 0.9 * amp) - np.argmax(seg >= lo + 0.1 * amp)) * step


def bar_edges(pick, oval_box, bar_centres, letter_boxes):
    """D-D10-2.5's relief question for the bars, measured. Across each bar's long edge and on the sketch's own crisp
    lettering, ONE operator: the L* profile (a quarter pixel) averaged over one engraving pitch (which nulls the
    engraving), the 10–90 % rise of the monotone run through the steepest change within ±1.5 mm — its floor, a perfect
    step, reads 0.8 pitch (0.33 mm). Along the bar to each end: the 10–90 % rise of the engraving's envelope (the
    engraving fades)."""
    lab_l = srgb_to_lab(pick)[..., 0]
    lightness = lab_l.astype(np.float32)
    box = int(round(ENGRAVING_PITCH_PX / 0.25))
    env = engraving_envelope(lab_l)
    n = structure_normal(lab_l, oval_box)
    t = np.array([n[1], -n[0]])
    if t[0] < 0:
        t = -t
    bars = []
    for cx, cy in bar_centres:
        s = np.arange(-40, 40, 0.25)
        across = []
        for off in (-60, -30, 0, 30, 60):
            c = np.array([cx, cy]) + off * t
            prof = uniform_filter1d(map_coordinates(lightness, [c[1] + s * n[1], c[0] + s * n[0]], order=1,
                                                    mode='nearest'), box, mode='nearest')
            rise = _monotone_rise(prof, int(np.argmax(np.abs(np.diff(prof)))), 0.25)
            if rise is not None:
                across.append(rise)
        ends = []
        bx0, by0, bx1, by1 = oval_box
        for sign in (-1, 1):
            # the profile runs along the bar's axis to the oval's box and no further, so nothing beyond the light
            # (the name's letters below it) is read as the bar's end
            s2 = np.arange(0, 400, 0.25)
            px, py = cx + sign * s2 * t[0], cy + sign * s2 * t[1]
            s2 = s2[(px >= bx0) & (px < bx1) & (py >= by0) & (py < by1)]
            prof = map_coordinates(env, [cy + sign * s2 * t[1], cx + sign * s2 * t[0]], order=1, mode='nearest')[::-1]
            ends.append(_rise_px(prof, 0.25) / PX_PER_MM_SRC)
        bars.append({'centre_px': [int(cx), int(cy)], 'long_edge_rise_mm': round(float(np.median(across)) / PX_PER_MM_SRC, 3),
                     'long_edges_read': len(across), 'end_fade_mm': [round(e, 2) for e in ends]})
    letters = []
    for name, (x0, y0, x1, y1) in letter_boxes.items():
        rises = []
        xs = np.arange(x0, x1, 0.25)
        for y in range(y0 + 4, y1 - 4, 3):
            prof = uniform_filter1d(map_coordinates(lightness, [np.full(len(xs), float(y)), xs], order=1, mode='nearest'),
                                    box, mode='nearest')
            d = np.abs(np.diff(prof))
            peaks = np.flatnonzero((d[1:-1] >= d[:-2]) & (d[1:-1] >= d[2:]) & (d[1:-1] >= 0.25 * d.max())) + 1
            for i in peaks:
                rise = _monotone_rise(prof, int(i), 0.25)
                if rise is not None:
                    rises.append(rise)
        letters.append((name, float(np.median(rises)) / PX_PER_MM_SRC))
    step = np.r_[np.zeros(200), np.full(200, 50.0)]
    step = uniform_filter1d(step, box, mode='nearest')
    floor = _monotone_rise(step, int(np.argmax(np.abs(np.diff(step)))), 0.25) / PX_PER_MM_SRC
    return {
        'operator': 'long edges and lettering alike: the L* profile at a quarter pixel averaged over one engraving pitch '
                    '(%g px), the 10–90 %% rise of the monotone run through the steepest change within ±%g px (1.5 mm); '
                    'the bars read along their normal (the picture\'s structure tensor); the ends: the engraving envelope '
                    '(|Gaussian σ 0.7 − σ 2.0 px| of L*, blurred σ 2 px) along the axis' % (ENGRAVING_PITCH_PX, RISE_WINDOW_PX),
        'floor_mm': round(floor, 3),
        'corrected': 'Day 10 review: the first reading took the long edges on the engraving envelope over a 45 px window '
                     'and the lettering over 10 px segments (bars 1.30–1.86 mm against 0.59–0.68, read as soft); on one '
                     'operator and one window the bars\' long edges read close to the lettering\'s, both near the '
                     'operator\'s floor',
        'bar_normal': [round(float(n[0]), 4), round(float(n[1]), 4)],
        'bars': bars,
        'lettering_rise_mm': {name: round(v, 3) for name, v in letters},
    }


def engraving_lines(pick, bar_centres, normal):
    """The bars' engraved lines across their pitch: pitch, line and gap widths in mm (the foil limits' question)."""
    lightness = srgb_to_lab(pick)[..., 0]
    n = np.asarray(normal, dtype=np.float64)
    t = np.array([n[1], -n[0]])
    pitches, lines, gaps = [], [], []
    for cx, cy in bar_centres:
        for off in (-30, -10, 10, 30):
            s = np.arange(-10, 10, 0.05)
            c = np.array([cx, cy]) + off * t
            p = map_coordinates(lightness, [c[1] + s * n[1], c[0] + s * n[0]], order=3)
            q = p - cv2.GaussianBlur(p.reshape(1, -1).astype(np.float32), (0, 0), 40).ravel()
            q = q - q.mean()
            ac = np.correlate(q, q, 'full')[len(q) - 1:]
            pitches.append((int(np.argmax(ac[30:120])) + 30) * 0.05)
            on = q > 0
            edges = np.flatnonzero(np.diff(on.astype(int)) != 0)
            for a, b in zip(edges[:-1], edges[1:]):
                (lines if on[a + 1] else gaps).append((b - a) * 0.05)
    pitch = float(np.median(pitches)) / PX_PER_MM_SRC
    return {
        'pitch_mm': round(pitch, 4),
        'lines_per_cm': round(10.0 / pitch, 1),
        'line_mm_median': round(float(np.median(lines)) / PX_PER_MM_SRC, 4),
        'gap_mm_median': round(float(np.median(gaps)) / PX_PER_MM_SRC, 4),
        'gap_mm_p10': round(float(np.percentile(gaps, 10)) / PX_PER_MM_SRC, 4),
        'foil_gap_limit_mm': FOIL_GAP_MIN_MM,
        'gaps_under_limit_share': round(float(np.mean(np.asarray(gaps) / PX_PER_MM_SRC < FOIL_GAP_MIN_MM)), 3),
    }


# --- 6. bleed ---------------------------------------------------------------------------------------------------------

def bleed_px():
    """The bleed band in upscaled px: 3 mm rounded up to whole pixels (49 px = 3.03 mm)."""
    return int(np.ceil(BLEED_MM * PX_PER_MM))


def bleed(plate):
    """D-D10-2.6: the picture's own edges mirrored outward (the edge row not repeated); the trim area untouched."""
    b = bleed_px()
    out = cv2.copyMakeBorder(plate, b, b, b, b, cv2.BORDER_REFLECT_101)
    if not np.array_equal(out[b:-b, b:-b], plate):
        raise AssertionError('the bleed moved a pixel inside the trim')
    return out


def safe_area(boxes_mm):
    """D-D10-2.6's check, run first: each element's ink box (mm) at least 4 mm inside the trim."""
    rows = []
    w, h = LID_MM
    for name, (x0, y0, x1, y1) in boxes_mm.items():
        margins = {'left': x0, 'top': y0, 'right': w - x1, 'bottom': h - y1}
        rows.append({'element': name, 'ink_box_mm': [round(v, 2) for v in (x0, y0, x1, y1)],
                     'nearest_trim_mm': round(min(margins.values()), 2),
                     'side': min(margins, key=margins.get),
                     'inside_safe': bool(min(margins.values()) >= SAFE_MM)})
    return rows


def relief_safe_margin(bounds_mm):
    """[Day 11, D-D11-5.1] The emboss's nearest trim against the 4 mm safe margin, measured and said — a report, not a
    proof: D-D10-2.6 names every copy line and the logo (the name with them), and its remedy is to move a line inward;
    the emboss is the picture's own bars (D-D11-5.1 puts it on their 50 % isoline), which run as near the trim as the
    sketch paints them, so it is not moved. Where it enters the margin it is said, for the printer and the owner."""
    row = safe_area({'relief': tuple(bounds_mm)})[0]
    said = 'the emboss stands %.2f mm from the %s trim, inside the 4 mm safe area' % (row['nearest_trim_mm'], row['side'])
    if not row['inside_safe']:
        said = ('the emboss enters the 4 mm safe margin: %.2f mm from the %s trim (the bars as the sketch paints them) '
                '— for the printer and the owner to confirm' % (row['nearest_trim_mm'], row['side']))
    return dict(row, rule='D-D10-2.6 names every copy line and the logo; the emboss is the picture\'s bars, not moved '
                          'inward (D-D11-5.1): measured here and said, never counted as a passed proof', said=said)


# --- 2b. the closest licensed face (D-D8-5), measured by rendering ----------------------------------------------------

MATCH_SCALE = 4                     # the sketch's glyphs and every candidate are compared at 4× the pick
MATCH_SHIFTS_PX = 3                 # ± px (at 4×) tried in x and y
MATCH_WEIGHTS = (300.0, 400.0, 500.0)
NEAR_TIE = 0.05                     # D-D8-5: a house face wins a near-tie (within 5 %)


def target_glyphs(alpha):
    """The sketch's glyphs at the match scale: the soft alpha enlarged by cubic interpolation, cut at one half."""
    h, w = alpha.shape
    return cv2.resize(alpha.astype(np.float32), (w * MATCH_SCALE, h * MATCH_SCALE), interpolation=cv2.INTER_CUBIC) >= 0.5


def _ink_box(mask):
    ys, xs = np.nonzero(mask)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def _font(path, size_px, wght):
    from PIL import ImageFont
    font = ImageFont.truetype(path, max(int(round(size_px)), 4), layout_engine=ImageFont.Layout.RAQM)
    if wght is not None:
        axes = font.get_variation_axes()
        values = []
        for axis in axes:
            name = axis['name']
            if isinstance(name, bytes):
                name = name.decode('latin-1')
            if name.lower().startswith('weight') or name == 'wght':
                values.append(min(max(wght, axis['minimum']), axis['maximum']))
            else:
                values.append(axis['default'])
        font.set_variation_by_axes(values)
    return font


def draw_line(path, text, size_px, tracking_px, wght, rtl):
    """One line set in a face at a pixel size: Latin letter by letter, each advance the kerned one (raqm) plus the
    tracking; Arabic whole, shaped by raqm right to left, never tracked. A boolean ink mask, cropped to its ink."""
    from PIL import ImageDraw
    font = _font(path, size_px, wght)
    pad = int(size_px * 2)
    if rtl:
        width = int(font.getlength(text, direction='rtl', language='ar')) + 2 * pad
        img = Image.new('L', (width, int(size_px * 3) + 2 * pad), 0)
        ImageDraw.Draw(img).text((pad, pad), text, font=font, fill=255, direction='rtl', language='ar')
    else:
        width = int(font.getlength(text) + tracking_px * len(text)) + 2 * pad
        img = Image.new('L', (max(width, 8), int(size_px * 3) + 2 * pad), 0)
        draw = ImageDraw.Draw(img)
        x = float(pad)
        for i, ch in enumerate(text):
            draw.text((x, pad), ch, font=font, fill=255)
            x += font.getlength(text[:i + 1]) - font.getlength(text[:i]) + tracking_px
    m = np.asarray(img) >= 128
    if not m.any():
        return m
    x0, y0, x1, y1 = _ink_box(m)
    return m[y0:y1, x0:x1]


def glyph_units(target, rtl, count):
    """The sketch line's units, left to right: Latin letters (connected components, those stacked over one another
    merged), or ``count`` Arabic words (the components' x-intervals merged where they overlap — a dot over its letter —
    and the line cut at its ``count`` − 1 widest gaps)."""
    n, labels, stats, _ = cv2.connectedComponentsWithStats(target.astype(np.uint8), 8)
    comps = sorted((int(stats[i, 0]), int(stats[i, 0] + stats[i, 2]), i) for i in range(1, n) if stats[i, 4] >= 6)
    groups = []
    for x0, x1, i in comps:
        joins = False
        if groups:
            gx0, gx1, members = groups[-1]
            overlap = min(x1, gx1) - max(x0, gx0)
            if rtl:
                joins = overlap > 0
            else:
                joins = overlap > 0.5 * min(x1 - x0, gx1 - gx0)
        if joins:
            gx0, gx1, members = groups[-1]
            groups[-1] = (min(gx0, x0), max(gx1, x1), members + [i])
        else:
            groups.append((x0, x1, [i]))
    if rtl and len(groups) > count:
        gaps = sorted(range(len(groups) - 1), key=lambda k: groups[k + 1][0] - groups[k][1])[-(count - 1):]
        merged = []
        for k, g in enumerate(groups):
            if merged and (k - 1) not in gaps:
                gx0, gx1, members = merged[-1]
                merged[-1] = (min(gx0, g[0]), max(gx1, g[1]), members + g[2])
            else:
                merged.append(g)
        groups = merged
    units = []
    for gx0, gx1, members in groups:
        m = np.isin(labels, members)
        x0, y0, x1, y1 = _ink_box(m)
        units.append({'box': (x0, y0, x1, y1), 'mask': m[y0:y1, x0:x1]})
    return units


def _best_overlap(target, cand, reach):
    """The best overlap of a candidate glyph over a target glyph, centred box on box and shifted up to ``reach`` px:
    (intersection, union, the target and the candidate placed on one canvas at that shift)."""
    th, tw = target.shape
    ch, cw = cand.shape
    size_y, size_x = max(th, ch) + 2 * reach, max(tw, cw) + 2 * reach
    big_t = np.zeros((size_y, size_x), dtype=bool)
    oy, ox = (size_y - th) // 2, (size_x - tw) // 2
    big_t[oy:oy + th, ox:ox + tw] = target
    total_t = int(big_t.sum())
    best = (0, total_t + int(cand.sum()), (size_y - ch) // 2, (size_x - cw) // 2)
    cy, cx = (size_y - ch) // 2, (size_x - cw) // 2
    for dy in range(-reach, reach + 1):
        for dx in range(-reach, reach + 1):
            y0, x0 = cy + dy, cx + dx
            if y0 < 0 or x0 < 0 or y0 + ch > size_y or x0 + cw > size_x:
                continue
            inter = int((big_t[y0:y0 + ch, x0:x0 + cw] & cand).sum())
            union = total_t + int(cand.sum()) - inter
            if inter * best[1] > best[0] * union:
                best = (inter, union, y0, x0)
    placed = np.zeros_like(big_t)
    placed[best[2]:best[2] + ch, best[3]:best[3] + cw] = cand
    return best[0], best[1], big_t, placed


def _outline(mask):
    return mask & ~cv2.erode(mask.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)


def outline_distance(a, b):
    """The symmetric mean distance between two masks' outlines (px): each outline pixel to the other outline, both
    ways, pooled. Returns (sum of distances, number of outline pixels)."""
    oa, ob = _outline(a), _outline(b)
    da = cv2.distanceTransform((~oa).astype(np.uint8), cv2.DIST_L2, 5)
    db = cv2.distanceTransform((~ob).astype(np.uint8), cv2.DIST_L2, 5)
    return float(db[oa].sum() + da[ob].sum()), int(oa.sum() + ob.sum())


def score_face(units, path, text, wght, rtl):
    """D-D8-5's comparison, glyph by glyph: every unit of the sketch (a Latin letter, an Arabic word) against the face's
    own drawing of it at one size for the line (the median of the units' height ratios), each aligned on its own box
    within ±3 px by the best overlap. Returns the summed IoU and the mean outline distance in mm (the outlines' symmetric
    mean distance, pooled over the units); ``None`` when the face does not give one glyph per unit."""
    parts = text.split() if rtl else [ch for ch in text if not ch.isspace()]
    if len(parts) != len(units):
        return None
    if rtl:
        parts = parts[::-1]                  # the units run left to right; the words are written right to left
    probe = [draw_line(path, part, 100.0, 0.0, wght, rtl) for part in parts]
    if any(not g.any() for g in probe):
        return None
    size = 100.0 * float(np.median([u['mask'].shape[0] / g.shape[0] for u, g in zip(units, probe)]))
    inter = union = 0
    dist = 0.0
    edge = 0
    for u, part in zip(units, parts):
        g = draw_line(path, part, size, 0.0, wght, rtl)
        i, n, t_big, g_big = _best_overlap(u['mask'], g, MATCH_SHIFTS_PX)
        inter += i
        union += n
        d, e = outline_distance(t_big, g_big)
        dist += d
        edge += e
    return {'iou': inter / union, 'outline_mm': dist / edge / (PX_PER_MM_SRC * MATCH_SCALE), 'size_px': size,
            'dist_sum_px': dist, 'edge_px': edge, 'inter_px': inter, 'union_px': union}


def rank_faces(units, faces, text, rtl):
    """D-D8-5 by measurement: every candidate face (``faces``: stem → {path, variable, axes, house}) scored glyph by
    glyph against the sketch; variable faces at 300, 400 and 500 within their axis; ranked by the outline distance."""
    ranked = []
    for stem, face in faces.items():
        weights = [None]
        if face['variable'] and 'wght' in face['axes']:
            lo, _, hi = face['axes']['wght']
            weights = [w for w in MATCH_WEIGHTS if lo <= w <= hi]
        for w in weights:
            r = score_face(units, face['path'], text, w, rtl)
            if r is not None:
                ranked.append({'stem': stem, 'wght': w, 'house': face['house'], 'distance': round(r['outline_mm'], 4),
                               'iou': round(r['iou'], 4), 'size_px_at_4x': round(r['size_px'], 2)})
    ranked.sort(key=lambda r: r['distance'])
    return {'units': len(units), 'measured': len(ranked), 'ranked': ranked,
            'distance': 'the symmetric mean distance between the sketch\'s and the face\'s glyph outlines, in mm on the '
                        'lid, each glyph placed by its best overlap'}


def choose_face(ranking):
    """D-D8-5: the closest face sets the line; a house face wins a near-tie (its distance within 5 % of the best)."""
    best = ranking['ranked'][0]
    chosen = best
    reason = 'the closest measured face'
    if not best['house']:
        for r in ranking['ranked'][1:]:
            if r['house'] and r['distance'] <= best['distance'] * (1 + NEAR_TIE):
                chosen = r
                reason = 'a house face within 5 % of the closest (D-D8-5\'s near-tie)'
                break
    return {'stem': chosen['stem'], 'wght': chosen['wght'], 'iou': chosen['iou'], 'distance': chosen['distance'],
            'reason': reason, 'closest': best['stem']}


# --- 2c. the sketch's small type, run by run --------------------------------------------------------------------------

#: the small lines as the sketch draws them: each line's box (pick px), its runs (the words that keep the sketch's own
#: spacing between them — a run is fitted on its own letters, so a word space narrower than the tracking holds), and
#: the copy each run carries; the ℮ is drawn by the engine as the sign at the sketch's own size and place
LINES = {
    'descriptor_en': {'box': (612, 798, 1100, 838), 'rtl': False, 'runs': ('EYESHADOW', 'PALETTE'),
                      'copy': 'Eyeshadow Palette', 'upper': True, 'face': 'support'},
    'descriptor_ar': {'box': (1145, 794, 1497, 848), 'rtl': True, 'runs': ('باليت ظلال العيون',),
                      'copy': 'باليت ظلال العيون', 'upper': False, 'face': 'arabic'},
    'shades': {'box': (610, 891, 845, 932), 'rtl': False, 'runs': ('18', 'SHADES'), 'copy': '18 shades', 'upper': True,
               'face': 'shades'},
    'net': {'box': (1203, 888, 1488, 940), 'rtl': False, 'runs': ('27', 'g', '℮', '0.95', 'oz'),
            'copy': '27 g ℮ 0.95 oz', 'upper': False, 'face': 'net'},
}
SIGN = '℮'


def line_units(pick, key):
    """One small line's glyph units in lid mm, left to right: each a box and its pixel mask at the match scale; the
    Arabic line as one unit per word."""
    line = LINES[key]
    x0, y0, x1, y1 = line['box']
    alpha = light_glyph_alpha(pick, line['box'])
    target = target_glyphs(alpha)
    count = len(line['runs'][0].split())
    units = glyph_units(target, line['rtl'], count)
    k = PX_PER_MM_SRC * MATCH_SCALE
    for u in units:
        bx0, by0, bx1, by1 = u['box']
        u['box_mm'] = (x0 / PX_PER_MM_SRC + bx0 / k, y0 / PX_PER_MM_SRC + by0 / k,
                       x0 / PX_PER_MM_SRC + bx1 / k, y0 / PX_PER_MM_SRC + by1 / k)
    return units, alpha


def runs_of(key, units):
    """The sketch's units grouped into the line's runs, in order: a Latin run takes as many units as it has
    characters that are not spaces (a period is a unit of its own); the Arabic run takes its words."""
    line = LINES[key]
    out = []
    i = 0
    for text in line['runs']:
        n = len(text.split()) if line['rtl'] else len([c for c in text if not c.isspace()])
        members = units[i:i + n]
        i += n
        boxes = np.asarray([m['box_mm'] for m in members])
        out.append({'text': text, 'units': members, 'box_mm': (float(boxes[:, 0].min()), float(boxes[:, 1].min()),
                                                               float(boxes[:, 2].max()), float(boxes[:, 3].max()))})
    if i != len(units):
        raise ValueError('%s: %d units read, %d placed by its runs' % (key, len(units), i))
    return out


def ink_colour(pick, key):
    """A line's ink as the sketch prints it: the median of its glyphs' cores (alpha ≥ 0.9)."""
    x0, y0, x1, y1 = LINES[key]['box']
    alpha = light_glyph_alpha(pick, LINES[key]['box'])
    core = alpha >= 0.9
    rgb = np.median(pick[y0:y1, x0:x1][core], axis=0)
    return '#%02X%02X%02X' % tuple(int(round(v)) for v in rgb), int(core.sum())


# --- 2d. the runs set live: fitted to the sketch's letters ------------------------------------------------------------

PT_PER_MM = 72.0 / MM_PER_INCH


def glyph_metrics(path):
    """A face's advances and ink boxes by character (font units) and its units per em: what the emitter places
    (reportlab advances by the hmtx table, without kerning)."""
    from fontTools.ttLib import TTFont
    font = TTFont(path, lazy=False)
    cmap = font.getBestCmap()
    gs = font.getGlyphSet()
    hmtx = font['hmtx']
    upm = font['head'].unitsPerEm
    from fontTools.pens.boundsPen import BoundsPen

    def of(ch):
        name = cmap[ord(ch)]
        pen = BoundsPen(gs)
        gs[name].draw(pen)
        return {'advance': hmtx[name][0], 'ink': pen.bounds}
    return of, upm


def fit_latin_line(runs, path):
    """One Latin line fitted to the sketch's letters, all its runs at once: one size for the line (the median ratio of
    each sketch letter's ink height to the face's own), one char space for the line and a start for each run, by least
    squares on the letters' ink centres with the emitter's own advances between them (hmtx, no kerning; the char space
    after every glyph, spaces included); the baseline on the feet of the letters that sit on it (a letter hanging below
    its neighbours, g, left out). Returns the runs' parameters (mm, pt) and each letter's residual (mm)."""
    of, upm = glyph_metrics(path)
    glyphs = []
    for r, run in enumerate(runs):
        chars = [c for c in run['text'] if not c.isspace()]
        for c, u in zip(chars, run['units']):
            glyphs.append((r, c, u, of(c)))
    size_mm = float(np.median([(u['box_mm'][3] - u['box_mm'][1]) / ((m['ink'][3] - m['ink'][1]) / upm)
                               for _, _, u, m in glyphs if m['ink'][3] > m['ink'][1]]))
    k = size_mm / upm
    rows, rhs = [], []
    for r, run in enumerate(runs):
        adv, slot, i = 0.0, 0, 0
        units = run['units']
        for ch in run['text']:
            if ch.isspace():
                adv += of(' ')['advance'] * k
                slot += 1
                continue
            m = of(ch)
            row = np.zeros(len(runs) + 1)
            row[r] = 1.0
            row[-1] = slot
            rows.append(row)
            rhs.append((units[i]['box_mm'][0] + units[i]['box_mm'][2]) / 2 - (adv + (m['ink'][0] + m['ink'][2]) / 2 * k))
            adv += m['advance'] * k
            slot += 1
            i += 1
    a, b = np.asarray(rows), np.asarray(rhs)
    solution, *_ = np.linalg.lstsq(a, b, rcond=None)
    residual = b - a @ solution
    cs = float(solution[-1])
    sitting = [(u['box_mm'][3], m['ink'][1] * k) for _, _, u, m in glyphs if m['ink'][1] >= -0.05 * upm]
    baseline = float(np.median([foot + below for foot, below in sitting]))
    out = []
    for r, run in enumerate(runs):
        out.append({'text': run['text'], 'x_mm': float(solution[r]), 'baseline_mm': baseline})
    return {'size_mm': size_mm, 'size_pt': size_mm * PT_PER_MM, 'charspace_mm': cs,
            'tracking_em': max(cs, 0.0) / size_mm, 'runs': out,
            'residual_mm': [round(float(v), 3) for v in residual]}


def fit_arabic_line(run, path):
    """The Arabic line fitted to the sketch: its ink height (dots included) sets the size, the face's own shaping
    (raqm, the glyphs the derived face draws) giving the ink box against the right-baseline anchor; the run is placed
    right-aligned so its ink's right edge and foot meet the sketch's. Each word's centre is then compared with the
    sketch's word (mm). Never tracked."""
    from PIL import ImageFont
    probe = 200
    font = ImageFont.truetype(path, probe, layout_engine=ImageFont.Layout.RAQM)
    x0, y0, x1, y1 = font.getbbox(run['text'], anchor='rs', direction='rtl', language='ar')
    sx0, sy0, sx1, sy1 = run['box_mm']
    size_mm = (sy1 - sy0) / ((y1 - y0) / probe)
    k = size_mm / probe
    anchor_x = sx1 - x1 * k
    baseline = sy1 - y1 * k
    words = run['text'].split()
    rendered = []
    for w in words:
        wx0, _, wx1, _ = font.getbbox(w, anchor='rs', direction='rtl', language='ar')
        rendered.append((wx0, wx1))
    # each word's place in the whole line: the line's own layout (the word's ink found in the line's ink by order)
    line_img = draw_line(path, run['text'], probe, 0.0, None, True)
    cols = np.flatnonzero(line_img.any(axis=0))
    gaps = np.flatnonzero(np.diff(cols) > probe * 0.15)
    starts = [cols[0]] + [cols[g + 1] for g in gaps]
    ends = [cols[g] for g in gaps] + [cols[-1]]
    spans = sorted(zip(starts, ends))
    residual = []
    if len(spans) == len(words):
        total = line_img.shape[1]
        for (a, b), u in zip(spans, run['units']):
            centre = sx1 - (total - (a + b) / 2) * k
            residual.append(round(float((u['box_mm'][0] + u['box_mm'][2]) / 2 - centre), 3))
    return {'size_mm': size_mm, 'size_pt': size_mm * PT_PER_MM, 'x_mm': float(anchor_x), 'baseline_mm': float(baseline),
            'align': 'right', 'word_residual_mm': residual}


# --- 2e. the type layer through the engine, and its overlay proof ----------------------------------------------------

SUPPORT_STEM = 'fonts_dm-sans-medium_dmsans-medium_4f6a909db85e054e'    # DM Sans Medium (OFL, D-D7-1): D-D8-5's match
SUPPORT_WEIGHT = 500.0                     # (a static face: the weight only names it)
NET_STEM = 'fonts_nunito-extralight_nunito-variablefont-wght_f2a6ab02dcefcf4c'   # Nunito (OFL, D-D7-1) at 500
NET_WEIGHT = 500.0
SHADES_STEM = 'Tajawal-Medium'             # house, OFL: within 5 % of the closest on 18 SHADES (D-D8-5's near-tie)
SHADES_WEIGHT = 500.0
ARABIC_STEM = 'TajawalPF-Medium'           # Tajawal Medium (house, OFL) made emitter-capable: D-D8-5's match
ARABIC_SOURCE_STEM = 'Tajawal-Medium'
ARABIC_WEIGHT = 500.0
SURFACE = 'apps/pipeline/services/lid_master.py::build'
RENDER_PX_PER_MM = PX_PER_MM_SRC * MATCH_SCALE    # the overlay proof reads the emitted page at the match scale


def sign_segments(box_mm):
    """The house's estimated sign (``estimated_sign.outline``: Montserrat Regular's ℮) as path segments in lid mm, its
    ink box fitted to ``box_mm``'s height and centred in it."""
    from apps.ire import estimated_sign
    from apps.ire.graph import ClosePath, CubicTo, LineTo, MoveTo
    o = estimated_sign.outline()
    pts = [op[1:] for op in o['ops'] if op[0] != 'Z']
    xs = [v for p in pts for v in p[0::2]]
    ys = [v for p in pts for v in p[1::2]]
    gx0, gx1, gy0, gy1 = min(xs), max(xs), min(ys), max(ys)
    bx0, by0, bx1, by1 = box_mm
    k = (by1 - by0) / (gy1 - gy0)
    cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2

    def at(x, y):
        return cx + (x - (gx0 + gx1) / 2) * k, cy - (y - (gy0 + gy1) / 2) * k

    segs = []
    for op in o['ops']:
        if op[0] == 'M':
            x, y = at(op[1], op[2])
            segs.append(MoveTo(x=x, y=y))
        elif op[0] == 'L':
            x, y = at(op[1], op[2])
            segs.append(LineTo(x=x, y=y))
        elif op[0] == 'C':
            x1, y1 = at(op[1], op[2])
            x2, y2 = at(op[3], op[4])
            x, y = at(op[5], op[6])
            segs.append(CubicTo(x1=x1, y1=y1, x2=x2, y2=y2, x=x, y=y))
        else:
            segs.append(ClosePath())
    return segs, {'height_mm': round(by1 - by0, 3), 'width_mm': round((gx1 - gx0) * k, 3), 'scale_mm_per_unit': k}


def emit_type_probe(path, type_group):
    """The type alone on a dark page (its measuring copy): the lines as the engine draws them."""
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, Document, Group, Rect, SolidFill
    doc = Document(page_w=LID_MM[0], page_h=LID_MM[1], metadata={'typography_surface': SURFACE, 'logical_text/1.0': True},
                   root=Group(name='probe', children=[Rect(name='ground', x=0.0, y=0.0, w=LID_MM[0], h=LID_MM[1],
                                                           fill=SolidFill(color=Color.from_hex('#000000'))), type_group]))
    emit_pdf_ai(doc, str(path))


def type_nodes(fits, inks, faces=None):
    """The small lines as engine nodes: each run a live TextRun in its line's face (or the face ``faces`` names) at its
    fitted size, place and tracking (the descriptor and the shade count in capitals, their copy kept as written), the ℮
    the house's sign in the sketch's place and in reading order (its ActualText ℮), each line in its own ink."""
    from apps.ire.graph import Color, Group, Path, SolidFill, TextRun
    nodes = []
    for key, fit in fits.items():
        colour = Color.from_hex(inks[key])
        role = line_face(key, faces)['role']
        if key == 'descriptor_ar':
            nodes.append(TextRun(name='descriptor_ar', text=fit['text'], x=fit['x_mm'], y=fit['baseline_mm'],
                                 font=role, size_pt=fit['size_pt'], color=colour, align='right', rtl=True))
            continue
        copy_words = [w for w in LINES[key]['copy'].split() if w != SIGN]
        line_nodes = []
        for i, run in enumerate(fit['runs']):
            extra = {}
            if fit['tracking_em'] > 0:
                extra['tracking_em'] = fit['tracking_em']
            if LINES[key]['upper']:
                extra['text_case'] = 'upper'
            line_nodes.append(TextRun(name='%s:%d' % (key, i), text=copy_words[i], x=run['x_mm'], y=run['baseline_mm'],
                                      font=role, size_pt=fit['size_pt'], color=colour, align='left', **extra))
        if 'sign' in fit:
            segs, _ = sign_segments(fit['sign']['box_mm'])
            line_nodes.insert(fit['sign']['after_run'], Group(name='%s:sign' % key, actual_text=SIGN, children=[
                Path(name=SIGN, segments=segs, fill=SolidFill(color=colour), fill_rule='nonzero')]))
        nodes.extend(line_nodes)
    return Group(name='TYPE', children=nodes)


def render_page(pdf_path, page, px_per_mm):
    """A PDF page rendered by MuPDF to RGB at ``px_per_mm`` (alpha off)."""
    import fitz
    doc = fitz.open(pdf_path)
    pix = doc[page].get_pixmap(matrix=fitz.Matrix(px_per_mm * MM_PER_INCH / 72.0, px_per_mm * MM_PER_INCH / 72.0),
                               alpha=False)
    rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[..., :3].copy()
    doc.close()
    return rgb


def drawn_units(render, key):
    """A small line's glyph units as the engine drew them, read from a render at the match scale (the sketch's line
    box, scaled), in lid mm — the same reader as the sketch's (``glyph_units``)."""
    line = LINES[key]
    x0, y0, x1, y1 = (v * MATCH_SCALE for v in line['box'])
    crop = render[y0:y1, x0:x1]
    lightness = srgb_to_lab(crop)[..., 0]
    mask = lightness > 50.0
    count = len(line['runs'][0].split())
    units = glyph_units(mask, line['rtl'], count)
    k = RENDER_PX_PER_MM
    for u in units:
        bx0, by0, bx1, by1 = u['box']
        u['box_mm'] = ((x0 + bx0) / k, (y0 + by0) / k, (x0 + bx1) / k, (y0 + by1) / k)
    return units


def overlay_proof(sketch_units, drawn):
    """D-D10-1's placement proof for one line (position within 1 mm, size within 3 %): the drawn line's ink box against
    the sketch's (each edge's shift, mm), the line's size as the median of its glyphs' height ratios, and each glyph's
    centre shift — every centre within 1 mm. A single glyph's own height differs where the face draws that letter
    otherwise (a g's tail, a period); that is the face's drawing, recorded per glyph, not a misplacement."""
    if len(sketch_units) != len(drawn):
        return {'units': [len(sketch_units), len(drawn)], 'holds': False, 'why': 'the drawn line has another count of glyphs'}
    rows = []
    for s_, d in zip(sketch_units, drawn):
        sx, sy = (s_['box_mm'][0] + s_['box_mm'][2]) / 2, (s_['box_mm'][1] + s_['box_mm'][3]) / 2
        dx, dy = (d['box_mm'][0] + d['box_mm'][2]) / 2, (d['box_mm'][1] + d['box_mm'][3]) / 2
        hs, hd = s_['box_mm'][3] - s_['box_mm'][1], d['box_mm'][3] - d['box_mm'][1]
        rows.append({'shift_mm': [round(dx - sx, 3), round(dy - sy, 3)], 'height_ratio': round(hd / hs, 4)})
    sb = np.asarray([u['box_mm'] for u in sketch_units])
    db = np.asarray([u['box_mm'] for u in drawn])
    edges = [db[:, 0].min() - sb[:, 0].min(), db[:, 1].min() - sb[:, 1].min(), db[:, 2].max() - sb[:, 2].max(),
             db[:, 3].max() - sb[:, 3].max()]
    size = float(np.median([r['height_ratio'] for r in rows]))
    worst_shift = max(float(np.hypot(*r['shift_mm'])) for r in rows)
    holds = worst_shift <= POSITION_TOL_MM and max(abs(e) for e in edges) <= POSITION_TOL_MM and abs(size - 1) <= SIZE_TOL
    return {'units': len(rows), 'line_box_edges_shift_mm': [round(float(e), 3) for e in edges],
            'line_size_ratio': round(size, 4), 'worst_glyph_shift_mm': round(worst_shift, 3),
            'glyph_height_ratio_range': [min(r['height_ratio'] for r in rows), max(r['height_ratio'] for r in rows)],
            'holds': bool(holds), 'glyphs': rows}


WORD_SPACE_TOL_MM = 0.15            # a drawn word space within 0.15 mm of the sketch's is left as fitted


def word_spaces(fits, sketch, render):
    """D-D10-3's repair 1 (the eye's round 0: "27 g" read tighter than the sketch): the word spaces as the sketch draws
    them. For each Latin line, the ink gap across every space between runs, drawn against the sketch; where it differs
    by more than 0.15 mm, the run before the space moves by the difference (never the drawn sign, which stands at the
    sketch's place). Changes ``fits`` in place; returns what moved."""
    moved = []
    for key, fit in fits.items():
        if LINES[key]['rtl']:
            continue
        drawn = drawn_units(render, key)
        runs = LINES[key]['runs']
        counts = [len([c for c in r if not c.isspace()]) for r in runs]
        ends = np.cumsum(counts)
        fitted = [r for r in runs if r != SIGN]
        for i in range(len(runs) - 2, -1, -1):
            if runs[i] == SIGN:
                continue
            a, b = ends[i] - 1, ends[i]
            sketch_gap = sketch[key][b]['box_mm'][0] - sketch[key][a]['box_mm'][2]
            drawn_gap = drawn[b]['box_mm'][0] - drawn[a]['box_mm'][2]
            delta = drawn_gap - sketch_gap
            if abs(delta) <= WORD_SPACE_TOL_MM:
                continue
            j = fitted.index(runs[i])
            fit['runs'][j]['x_mm'] += delta
            moved.append({'line': key, 'between': [runs[i], runs[i + 1]], 'sketch_gap_mm': round(sketch_gap, 3),
                          'drawn_gap_mm': round(drawn_gap, 3), 'moved': runs[i], 'by_mm': round(delta, 3)})
    return moved


# --- 5b. the crisp gold, found over the whole lid ---------------------------------------------------------------------

GOLD_L_MIN = 40.0                  # gold reads L* above 40 …
GOLD_B_MIN = 20.0                  # … b* above 20 (yellow) …
GOLD_HUE = (50.0, 95.0)            # … at a hue between 50° and 95°
CRISP_EDGE_PX = 2.0                # an edge is crisp when its 10–90 % rise is at most 2 pick px (0.25 mm): the
                                   # sketch's own lettering rises in 1–1.25 px (0.12–0.16 mm)
CRISP_SHARE = 0.5                  # a gold shape is crisp when at least half of its outline is
GOLD_MIN_PX = 4


def crisp_gold(pick, regions):
    """D-D10-2.5's search, run over the whole lid: gold by colour (L*, b*, hue) AND crisp by its edges. Each gold shape
    (its grain's pinholes closed) is read along its OUTER outline: at up to 160 points, the L* profile across the edge
    (along the smoothed gradient, ±4 px at a quarter pixel) and its 10–90 % rise; a shape is crisp when the median
    rise is at most 2 pick px. Every shape is filed under the first named region (pick px boxes, in order) that
    holds its centre, else 'elsewhere'."""
    lab = srgb_to_lab(pick)
    lightness, b = lab[..., 0], lab[..., 2]
    hue = np.degrees(np.arctan2(b, lab[..., 1])) % 360
    gold = (lightness > GOLD_L_MIN) & (b > GOLD_B_MIN) & (hue > GOLD_HUE[0]) & (hue < GOLD_HUE[1])
    gold = cv2.morphologyEx(gold.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)).astype(bool)
    ls = cv2.GaussianBlur(lightness.astype(np.float32), (0, 0), 1.0)
    gx = cv2.Sobel(ls, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(ls, cv2.CV_32F, 0, 1, ksize=3)
    n, labels, stats, cents = cv2.connectedComponentsWithStats(gold.astype(np.uint8), 8)
    filed = {name: {'shapes': 0, 'crisp_shapes': 0, 'area_mm2': 0.0, 'crisp_area_mm2': 0.0, 'median_rise_px': []}
             for name in list(regions) + ['elsewhere']}
    crisp_mask = np.zeros_like(gold)
    offs = np.arange(-4.0, 4.0001, 0.25)
    for i in range(1, n):
        if stats[i, 4] < GOLD_MIN_PX:
            continue
        x, y, w, h = stats[i, :4]
        comp = (labels[y:y + h, x:x + w] == i).astype(np.uint8)
        contours, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        pts = np.concatenate([c[:, 0, :] for c in contours]).astype(np.float64) + [x, y]
        if len(pts) > 160:
            pts = pts[np.linspace(0, len(pts) - 1, 160).astype(int)]
        gxs = gx[pts[:, 1].astype(int), pts[:, 0].astype(int)]
        gys = gy[pts[:, 1].astype(int), pts[:, 0].astype(int)]
        norm = np.hypot(gxs, gys)
        ok = norm > 1e-3
        rises = []
        for (px_, py_), ux, uy in zip(pts[ok], gxs[ok] / norm[ok], gys[ok] / norm[ok]):
            prof = map_coordinates(lightness, [py_ + offs * uy, px_ + offs * ux], order=1, mode='nearest')
            lo, hi = prof.min(), prof.max()
            if hi - lo < 8.0:
                continue
            up = np.maximum.accumulate(prof)
            rises.append((np.argmax(up >= lo + 0.9 * (hi - lo)) - np.argmax(up >= lo + 0.1 * (hi - lo))) * 0.25)
        cx, cy = cents[i]
        where = 'elsewhere'
        for name, (x0, y0, x1, y1) in regions.items():
            if x0 <= cx < x1 and y0 <= cy < y1:
                where = name
                break
        area = stats[i, 4] / PX_PER_MM_SRC ** 2
        f = filed[where]
        f['shapes'] += 1
        f['area_mm2'] += area
        if rises:
            med = float(np.median(rises))
            f['median_rise_px'].append(med)
            if med <= CRISP_EDGE_PX:
                f['crisp_shapes'] += 1
                f['crisp_area_mm2'] += area
                crisp_mask[labels == i] = True
    for f in filed.values():
        f['area_mm2'] = round(f['area_mm2'], 2)
        f['crisp_area_mm2'] = round(f['crisp_area_mm2'], 2)
        rs = f.pop('median_rise_px')
        f['rise_px_median_of_shapes'] = round(float(np.median(rs)), 2) if rs else None
    return {'rule': 'gold: L* > %g, b* > %g, hue %g–%g° (pinholes closed); crisp: the median 10–90 %% rise of L* across '
                    'the outer outline at most %g pick px (%.2f mm)' % (GOLD_L_MIN, GOLD_B_MIN, GOLD_HUE[0], GOLD_HUE[1],
                                                                       CRISP_EDGE_PX, CRISP_EDGE_PX / PX_PER_MM_SRC),
            'gold_area_mm2': round(float(gold.sum()) / PX_PER_MM_SRC ** 2, 2), 'by_region': filed}, crisp_mask


def crisp_specks(mask, keep):
    """The crisp gold shapes outside the boxes ``keep`` (pick px): each one's centre, area and widest line (twice its
    deepest inside distance) in mm — what the foil limits would read on it."""
    n, labels, stats, cents = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    depth = cv2.distanceTransform(np.pad(mask.astype(np.uint8), 1), cv2.DIST_L2, 5)[1:-1, 1:-1]
    rows = []
    for i in range(1, n):
        cx, cy = cents[i]
        if any(x0 <= cx < x1 and y0 <= cy < y1 for x0, y0, x1, y1 in keep):
            continue
        rows.append({'centre_px': [int(cx), int(cy)], 'area_mm2': round(float(stats[i, 4]) / PX_PER_MM_SRC ** 2, 3),
                     'widest_line_mm': round(2 * float(depth[labels == i].max()) / PX_PER_MM_SRC, 3)})
    return rows


EDGE_WINDOW_MM = 0.6                  # wider than the 0.3 mm bar, so a trace off by more than the bar can be read as off
EDGE_STRONG = 0.5                     # a fall counts as an edge at half the profile's steepest fall or more
EDGE_UNREAD_MAX = 0.005               # at most 0.5 % of the outline's points may find no edge in the window (said)


def prove_outline_on_pick(pick, rings_mm):
    """The trace's proof against the sketch read independently of the trace's own input: at points along the traced
    outline (every 0.05 mm), the L* profile of the PICK itself along the outward normal (tested against the shape;
    ±0.6 mm at 0.005 mm, cubic), and the place of the strong fall from gold to ground nearest the outline — the letter's
    edge as the sketch paints it. Returns the distances (mm) from the outline to that edge; a trace moved by more than
    the bar reads as moved (the window is wider than the bar)."""
    from shapely import contains_xy
    lightness = cv2.GaussianBlur(srgb_to_lab(pick)[..., 0].astype(np.float32), (0, 0), 0.5)
    geom = rings_area(rings_mm, 24)
    offs = np.arange(-EDGE_WINDOW_MM, EDGE_WINDOW_MM + 1e-9, 0.005)
    dists = []
    for g in parts(geom):
        for ring in [g.exterior, *g.interiors]:
            n = max(int(ring.length / 0.05), 8)
            ts = np.linspace(0, ring.length, n, endpoint=False)
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
            xs = (px[:, None] + offs[None, :] * nx[:, None]) * PX_PER_MM_SRC - 0.5
            ys = (py[:, None] + offs[None, :] * ny[:, None]) * PX_PER_MM_SRC - 0.5
            prof = map_coordinates(lightness, [ys.ravel(), xs.ravel()], order=3, mode='nearest').reshape(xs.shape)
            fall = -np.diff(prof, axis=1)
            # the edge: of the strong falls (local maxima at half the steepest or more), the one nearest the outline — a
            # neighbouring letter's edge inside the window is not taken for this one's
            peak = (fall[:, 1:-1] >= fall[:, :-2]) & (fall[:, 1:-1] >= fall[:, 2:])
            strong = peak & (fall[:, 1:-1] >= EDGE_STRONG * fall.max(axis=1, keepdims=True))
            at = np.abs(offs[1:-2] + 0.0025)
            dists.append(np.where(strong, at[None, :], np.inf).min(axis=1))
    every = np.concatenate(dists)
    d = every[np.isfinite(every)]
    unread = int((~np.isfinite(every)).sum())
    return {'reference': 'the pick\'s own L*: the strong fall from gold to ground nearest the outline along each outward '
                         'normal (independent of the alpha the trace was cut from)', 'points': int(len(every)),
            'unread': unread, 'unread_share': round(unread / len(every), 5), 'window_mm': EDGE_WINDOW_MM,
            'max_mm': round(float(d.max()), 4), 'p99_mm': round(float(np.percentile(d, 99)), 4),
            'p95_mm': round(float(np.percentile(d, 95)), 4), 'median_mm': round(float(np.median(d)), 4),
            'within_0_3_mm_share': round(float(np.mean(d <= NAME_OVERLAY_MAX_MM)), 5),
            'holds': bool(d.max() <= NAME_OVERLAY_MAX_MM and unread / len(every) <= EDGE_UNREAD_MAX)}


NAME_CONTROL_SHIFTS_MM = (0.10, 0.20, 0.35, 0.45)   # the trace moved right by each: past the 0.3 mm bar it must fail


def _shifted(rings, dx):
    return map_rings(rings, lambda p: (p[0] + dx, p[1]))


def outline_on_pick_with_controls(pick, rings_mm):
    """``prove_outline_on_pick`` on the trace, then on the trace moved right by each control shift — the proof has
    power when the moves past the bar fail — with the correction of its first reading said."""
    own = prove_outline_on_pick(pick, rings_mm)
    own['control_shifts_mm'] = {}
    for dx in NAME_CONTROL_SHIFTS_MM:
        moved = prove_outline_on_pick(pick, _shifted(rings_mm, dx))
        own['control_shifts_mm']['%.2f' % dx] = {k: moved[k] for k in ('max_mm', 'p99_mm', 'unread', 'holds')}
    own['corrected'] = ('Day 10 §9: the first reading looked only ±0.25 mm along each normal, so it could never read a '
                        'distance over the 0.3 mm bar (its control, a trace moved 0.45 mm, held — a false pass); it now '
                        'looks ±0.6 mm and takes the strong fall nearest the outline, counting a point with no edge in '
                        'its window as unread. The first reading was max 0.1575 mm')
    return own


# --- the master: the plate cleaned, every element as engine nodes -----------------------------------------------------

NAME_BOX = (590, 555, 1510, 790)                  # pick px: the name with its swashes, padded
LOGO_BOX = (1105, 55, 1505, 155)                  # the sketch's logo and its ®, padded
OVAL_BOX = (20, 10, 760, 560)                     # the oval of light and its five bars
BAR_CENTRES = ((483, 129), (440, 200), (384, 270), (339, 347), (294, 419))
LETTERING_BOXES = {'name': (606, 600, 1495, 760), 'logo': (1122, 70, 1489, 140), 'small lines': (615, 800, 1490, 935)}
REGIONS = {'name': NAME_BOX, 'logo': LOGO_BOX, 'oval and bars': OVAL_BOX, 'small type': (600, 790, 1500, 945)}
LOGO_DEVIATION_DE = 6.0                           # a logo pixel stands off the ground's fitted plane by ΔE76 > 6
FOIL_PLATE = 'FOIL_GOLD'
LOGO_EMBLEM = tuple(range(0, 4))                  # brand_mark's subpaths, by the master's own order (finish reader)
LOGO_LETTERS = tuple(range(4, 14))
LOGO_REGISTERED = tuple(range(14, 18))


def logo_clean_mask(pick, box):
    """The sketch's logo to clean, on the upscale's grid: every pixel of the box standing off the ground (a plane fitted
    to the box's border in L*a*b*) by ΔE76 > 6 — the gold, its bevel and its dark rim — grown by two pick px."""
    x0, y0, x1, y1 = box
    lab = srgb_to_lab(pick[y0:y1, x0:x1])
    h, w = lab.shape[:2]
    border = np.zeros((h, w), dtype=bool)
    border[:3, :] = border[-3:, :] = border[:, :3] = border[:, -3:] = True
    yy, xx = np.mgrid[0:h, 0:w]
    design = np.column_stack([np.ones(int(border.sum())), xx[border], yy[border]])
    plane = np.empty_like(lab)
    full = np.column_stack([np.ones(h * w), xx.ravel(), yy.ravel()])
    for c in range(3):
        coef, *_ = np.linalg.lstsq(design, lab[..., c][border], rcond=None)
        plane[..., c] = (full @ coef).reshape(h, w)
    dev = np.sqrt(((lab - plane) ** 2).sum(axis=-1)) > LOGO_DEVIATION_DE
    k = 2 * TEXT_RIM_SRC_PX + 1
    grown = cv2.dilate(dev.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    up = cv2.resize(grown, (w * UP, h * UP), interpolation=cv2.INTER_NEAREST)
    return cv2.dilate(up, np.ones((3, 3), np.uint8)).astype(bool)


def place_mask(local, box, shape):
    """A box-local mask on the upscale's grid placed on the whole upscale."""
    x0, y0, _, _ = box
    full = np.zeros(shape, dtype=bool)
    h, w = local.shape
    full[y0 * UP:y0 * UP + h, x0 * UP:x0 * UP + w] = local
    return full


DONOR_STEP_SRC = 4                                # donor shifts tried every 4 pick px …
DONOR_REACH_SRC = 240                             # … up to 240 pick px away, across and down
DONOR_RING_PX = 6                                 # the glyph's surroundings: a 6 px ring (2×) around its mask


def donor_shifts(h, w):
    """The (dy, dx) shifts (upscaled px) a glyph of h × w may take its donor from: clear of itself, nearest first."""
    out = []
    for dy in range(-DONOR_REACH_SRC, DONOR_REACH_SRC + 1, DONOR_STEP_SRC):
        for dx in range(-DONOR_REACH_SRC, DONOR_REACH_SRC + 1, DONOR_STEP_SRC):
            if abs(dy * UP) <= h and abs(dx * UP) <= w:
                continue
            out.append((dy * UP, dx * UP))
    out.sort(key=lambda d: d[0] * d[0] + d[1] * d[1])
    return out


def choose_donor(lab, comp, keep_out):
    """The donor for one glyph (``comp``: its mask, bool): of the shifts tried (``donor_shifts``), one whose moved
    ground under the glyph and its ring touches no glyph, name or logo (``keep_out``) and stays on the picture, scored
    by how far its ground is from the glyph's own surroundings — |ΔL*| of the medians plus the donor's spread of L*
    (99th percentile less median) — the best of the nearest 400 that qualify."""
    ring = cv2.dilate(comp.astype(np.uint8), np.ones((2 * DONOR_RING_PX + 1,) * 2, np.uint8)).astype(bool)
    ys, xs = np.nonzero(ring)
    around = lab[..., 0][ring & ~comp & ~keep_out]
    target_l = float(np.median(around))
    h, w = int(ys.max() - ys.min() + 1), int(xs.max() - xs.min() + 1)
    best = None
    tried = 0
    for dy, dx in donor_shifts(h, w):
        sy, sx = ys - dy, xs - dx
        if sy.min() < 0 or sx.min() < 0 or sy.max() >= lab.shape[0] or sx.max() >= lab.shape[1]:
            continue
        if keep_out[sy, sx].any():
            continue
        values = lab[..., 0][sy, sx]
        median = float(np.median(values))
        score = abs(median - target_l) + float(np.percentile(values, 99) - median)
        if best is None or score < best[0]:
            best = (score, dy, dx, abs(median - target_l))
        tried += 1
        if tried >= 400:
            break
    if best is None:
        raise ValueError('no clean donor ground for a glyph at %s' % [int(xs.min()), int(ys.min())])
    return {'shift_px_2x': [best[1], best[2]], 'score': round(best[0], 3), 'delta_l': round(best[3], 3)}


def name_keep_out(pick, shape):
    """The name's letters on the upscale's grid (its gold alpha from a tenth, grown 4 px): never a donor."""
    alpha = gold_alpha(pick, NAME_BOX)
    h, w = alpha.shape
    big = cv2.resize((alpha > 0.1).astype(np.uint8), (w * UP, h * UP), interpolation=cv2.INTER_NEAREST)
    return place_mask(cv2.dilate(big, np.ones((9, 9), np.uint8)).astype(bool), NAME_BOX, shape)


def clean_plate(pick, up, keep_out_extra):
    """D-D10-2.2 and 2.4: the small words, the ℮ and the sketch's logo cleaned out of the upscale. Each glyph (a
    connected part of a line's mask) takes its own donor (``choose_donor``); the guide holds every glyph's donor ground
    over the glyph and its 1 px boundary, and one Poisson solve per line fills the glyphs (``poisson_fill``): the
    donor's texture inside, the picture's own values on the boundary. The name stays (its raster gold under the foil,
    D-D10-2.5); ``keep_out_extra`` (the name's letters, the bars) is never a donor. Returns the plate, the masks and the
    record per line."""
    shape = up.shape[:2]
    masks = {}
    for key, line in LINES.items():
        masks[key] = place_mask(glyph_clean_mask(light_glyph_alpha(pick, line['box'])), line['box'], shape)
    masks['logo'] = place_mask(logo_clean_mask(pick, LOGO_BOX), LOGO_BOX, shape)
    keep_out = keep_out_extra.copy()
    for m in masks.values():
        keep_out |= cv2.dilate(m.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    lab = srgb_to_lab(up)
    plate = up.astype(np.float64)
    record = {}
    for key, m in masks.items():
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
        plate = poisson_fill(plate, guide, m)
        ys, xs = np.nonzero(m)
        record[key] = {'glyphs': n - 1, 'pixels_filled': int(m.sum()),
                       'box_px_2x': [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1],
                       'donor_delta_l_max': max(d['delta_l'] for d in donors),
                       'donor_score_max': max(d['score'] for d in donors), 'donors': donors}
    return np.clip(np.round(plate), 0, 255).astype(np.uint8), masks, record


def rings_segments(rings_mm):
    """Rings of segments (mm) as engine path segments, each ring closed."""
    from apps.ire.graph import ClosePath, CubicTo, LineTo, MoveTo
    segs = []
    for ring in rings_mm:
        first = ring[0][1]
        segs.append(MoveTo(x=float(first[0]), y=float(first[1])))
        for seg in ring:
            if seg[0] == 'L':
                segs.append(LineTo(x=float(seg[2][0]), y=float(seg[2][1])))
            else:
                segs.append(CubicTo(x1=float(seg[2][0]), y1=float(seg[2][1]), x2=float(seg[3][0]), y2=float(seg[3][1]),
                                    x=float(seg[4][0]), y=float(seg[4][1])))
        segs.append(ClosePath())
    return segs


def logo_parts(box_mm, gold_hex, *, foil_letters):
    """The approved master placed in its fitted box (x, y, w, h mm): the rose emblem and the ® in ink in the sketch's
    gold (the ® is a sign, not a letter); the letters in that ink too, or foiled when they pass the foil limits
    (``foil_letters``). Subsets of the
    master keep its full bounds, so every part stays in register; they are never registered as the master."""
    from apps.ire import brand_mark
    from apps.ire.graph import Color, Finish, Path, SolidFill
    master = brand_mark.read_master(LOGO_SVG.read_bytes(), path=str(LOGO_SVG))
    x, y, w, h = box_mm
    gold = Color.from_hex(gold_hex)

    def part(tag, idx, finishes):
        sub = brand_mark.Master(sha256='unregistered-day10-' + tag, path='', fill=master.fill,
                                subpaths=tuple(master.subpaths[i] for i in idx), bounds=master.bounds)
        return Path(name='BBROSE mark: ' + tag, segments=brand_mark.placed_segments(sub, x, y, w, h),
                    fill=SolidFill(color=gold), fill_rule='nonzero', finishes=finishes)

    foil = []
    if foil_letters:
        foil = [Finish(kind='foil', plate=FOIL_PLATE, appearance=gold)]
    return [part('emblem', LOGO_EMBLEM, []), part('letters', LOGO_LETTERS, list(foil)),
            part('registered', LOGO_REGISTERED, [])]


RELIEF_PLATE = 'EMBOSS'                    # [Day 11, D-D11-5.1] the bars' blind emboss, B-1's plate name (orn_b1)


def relief_carrier(relief_rings, ground_hex):
    """[Day 11, D-D11-5.1] The relief mask's rings (mm) on an invisible carrier: a path whose only work is its EMBOSS
    plate (the finish proof and the finish sheet read it); the group's opacity 0 prints nothing on page 1, so the
    picture under it is the sketch's own (B-1's way, ``orn_b1.document``)."""
    from apps.ire.graph import Color, Finish, Group, Path, SolidFill
    return Group(name='RELIEF CARRIERS', role='effects', opacity=0.0, children=[
        Path(name='the five bars (blind emboss)', segments=rings_segments(relief_rings),
             fill=SolidFill(color=Color.from_hex(ground_hex)), fill_rule='evenodd',
             finishes=[Finish(kind='emboss', plate=RELIEF_PLATE)])])


def engine_document(*, plate_png, type_group, name_rings, name_gold, logo_box_mm, logo_gold, foil_letters, layers,
                    relief_rings=None):
    """The lid (190 × 120 mm) as one engine document, only the ``layers`` asked for: 'picture' (the cleaned plate),
    'type' (the live small words and the ℮), 'logo' (the approved master), 'name' (the traced logotype, drawn in the
    sketch's gold — the lettering as vector), 'foil carriers' (the name's foil plate on an invisible carrier, so the
    picture under it is the sketch's own) and, with ``relief_rings`` [Day 11], the bars' emboss on its own invisible
    carrier beside them. Its metadata names the composer (a non-exempt typography surface) and keeps the words logical
    (ActualText)."""
    from apps.ire.graph import Color, Document, Finish, Group, Image, Path, SolidFill
    children = []
    if 'picture' in layers:
        children.append(Group(name='PICTURE', role='background', children=[
            Image(name='plate', src=str(plate_png), x=0.0, y=0.0, w=LID_MM[0], h=LID_MM[1])]))
    if 'type' in layers:
        children.append(type_group)
    if 'logo' in layers:
        children.append(Group(name='LOGO', role='logo', children=logo_parts(logo_box_mm, logo_gold,
                                                                            foil_letters=foil_letters)))
    name_path = Path(name='Enchanted Rose', segments=rings_segments(name_rings), fill=SolidFill(color=Color.from_hex(name_gold)),
                     fill_rule='evenodd')
    if 'name' in layers:
        children.append(Group(name='NAME', role='typography', actual_text='Enchanted Rose', children=[name_path]))
    if 'foil carriers' in layers:
        carrier = name_path.model_copy(update={'finishes': [Finish(kind='foil', plate=FOIL_PLATE,
                                                                   appearance=Color.from_hex(name_gold))]})
        children.append(Group(name='FINISH CARRIERS', role='effects', opacity=0.0, actual_text='Enchanted Rose',
                              children=[carrier]))
        if relief_rings is not None:
            children.append(relief_carrier(relief_rings, name_gold))
    return Document(page_w=LID_MM[0], page_h=LID_MM[1], title='Enchanted Rose lid master',
                    metadata={'typography_surface': SURFACE, 'logical_text/1.0': True},
                    root=Group(name='LID MASTER', role='artwork', children=children))


RESIDUE_SIGMA_PX = 8.0              # the residue is read at the scale a ghost shows: σ 8 upscaled px (0.5 mm)
RESIDUE_GROUND_SIGMAS = (8.0, 16.0, 32.0, 64.0)   # the ground under a wide mask is read from as far as it must
RESIDUE_WEIGHT_MIN = 0.2


def residue(plate, mask):
    """A cleaning's ghost, measured: inside the cleaned pixels, the plate's local mean (Gaussian σ 0.5 mm) against the
    ground's local mean read from outside the mask only (normalised convolution, at the smallest scale that sees at
    least a fifth of ground: σ 0.5, 1, 2 or 4 mm), as ΔE00 — what is left of the words as tone or tint. Returns its
    mean, 99th percentile and max over the mask."""
    w = (~mask).astype(np.float64)
    p = plate.astype(np.float64)
    local = np.stack([gaussian_filter(p[..., c], RESIDUE_SIGMA_PX) for c in range(3)], axis=-1)
    ground = np.zeros_like(p)
    unset = mask.copy()
    for sigma in RESIDUE_GROUND_SIGMAS:
        weight = gaussian_filter(w, sigma)
        est = np.stack([gaussian_filter(p[..., c] * w, sigma) for c in range(3)], axis=-1) / np.maximum(weight, 1e-6)[..., None]
        take = unset & (weight >= RESIDUE_WEIGHT_MIN)
        ground[take] = est[take]
        unset &= ~take
    take = unset
    ground[take] = est[take]
    de = delta_e00(srgb_to_lab(np.clip(local[mask], 0, 255)), srgb_to_lab(np.clip(ground[mask], 0, 255)))
    return {'de00_mean': round(float(de.mean()), 3), 'de00_p99': round(float(np.percentile(de, 99)), 3),
            'de00_max': round(float(de.max()), 3), 'sigma_mm': RESIDUE_SIGMA_PX / PX_PER_MM}


# --- the build: every §1 file, deterministic, $0 -----------------------------------------------------------------------

import json  # noqa: E402  (the records)

SRGB_ICC = Path('/System/Library/ColorSync/Profiles/sRGB Profile.icc')
FLAT_PPI = 300.0
CROP_DPI = 600.0
CROP_PAD_MM = 1.5
A4_LANDSCAPE_MM = (297.0, 210.0)
CROP_MARK_MM = 5.0
CROP_MARK_GAP_MM = 3.0
RULER_TICK_MM = 2.0
RULER_TICK_LONG_MM = 3.5
CONTRAST_FLOOR = 4.5                  # WCAG for small text; 3.0 for large (cap ≥ 4.2 mm), the Arabic and the name (D-D9)
CONTRAST_FLOOR_LARGE = 3.0
LARGE_CAP_MM = 4.2
NAME_CAP_MIN_MM = 7.0
SIGN_MIN_MM = 3.0
TYPE_MIN_PT = 5.0
ALIF_SHARE_MIN = 0.9


def write_json(path, data):
    def conv(o):
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.bool_,)):
            return bool(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, Path):
            return str(o)
        raise TypeError(type(o))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=1, ensure_ascii=False, default=conv) + '\n')


def rel(path):
    return str(Path(path).resolve().relative_to(REPO))


def ensure_arabic_face():
    """The Arabic line's face, made where ``var/`` holds none (the same bytes every time): Tajawal Medium (house, OFL)
    derived emitter-capable by ``arabic_display.derive``, the derived face the emitter embeds."""
    from apps.ire import arabic_display, font_instances
    held = font_instances.derived_face(ARABIC_STEM, None)
    if held is not None:
        return held
    candidate = {'key': 'tajawal-500', 'family': 'Tajawal', 'stem': ARABIC_SOURCE_STEM, 'weight': ARABIC_WEIGHT}
    arabic_display.derive(arabic_display.source_of(candidate))
    made = font_instances.derived_face(ARABIC_STEM, None)
    if made is None:
        raise RuntimeError('the derivation of %s did not produce it' % ARABIC_STEM)
    return made


def line_face(key, faces=None):
    """A line's face as the engine resolves it: {'role', 'path', 'label'}. ``faces`` (line → (stem, weight)) overrides
    the Day 10 faces for the lines it names — [Day 11, D-D11-5.4] Golden Hour's one Latin face for its three small
    lines; without it, each line's own Day 10 face."""
    from apps.ire import font_roles
    stem, weight = {'support': (SUPPORT_STEM, SUPPORT_WEIGHT), 'net': (NET_STEM, NET_WEIGHT),
                    'shades': (SHADES_STEM, SHADES_WEIGHT), 'arabic': (ARABIC_STEM, ARABIC_WEIGHT)}[LINES[key]['face']]
    if faces is not None and key in faces:
        stem, weight = faces[key]
    r = font_roles.resolve_line_face(stem, weight)
    return {'role': r['role'], 'path': r['path'], 'label': r['label'], 'stem': stem, 'weight': weight}


def fit_lines(pick, faces=None):
    """Every small line fitted to the sketch in its own face (or the face ``faces`` names for it): the sketch's units,
    the fit and the ink per line."""
    fits, inks, sketch = {}, {}, {}
    for key in LINES:
        units, _ = line_units(pick, key)
        sketch[key] = units
        runs = runs_of(key, units)
        inks[key] = ink_colour(pick, key)[0]
        face = line_face(key, faces)
        if LINES[key]['rtl']:
            fit = fit_arabic_line(runs[0], face['path'])
            fit['text'] = runs[0]['text']
        else:
            fit = fit_latin_line([r for r in runs if r['text'] != SIGN], face['path'])
            signs = [r for r in runs if r['text'] == SIGN]
            if signs:
                fit['sign'] = {'box_mm': signs[0]['box_mm'], 'height_mm': signs[0]['box_mm'][3] - signs[0]['box_mm'][1],
                               'after_run': [r['text'] for r in runs].index(SIGN)}
        fit['face'] = face['label']
        fits[key] = fit
    return fits, inks, sketch


def name_measures(rings_mm):
    """The traced name's cap height: its baseline (the median foot of the letters that sit on it: n c a n e o s e)
    to the median top of its two capitals (E, R) — in mm."""
    geom = rings_area(rings_mm, 24)
    letters = sorted(parts(geom), key=lambda g: g.bounds[0])
    if len(letters) != 13:
        raise ValueError('the traced name holds %d letters, not 13' % len(letters))
    sitting = [letters[i].bounds[3] for i in (1, 2, 4, 5, 7, 10, 11, 12)]
    baseline = float(np.median(sitting))
    caps_top = float(np.median([letters[0].bounds[1], letters[9].bounds[1]]))
    x0, y0, x1, y1 = geom.bounds
    return {'baseline_mm': round(baseline, 3), 'cap_height_mm': round(baseline - caps_top, 3),
            'ink_box_mm': [round(v, 3) for v in (x0, y0, x1, y1)], 'area_mm2': round(float(geom.area), 2)}


def median_under(plate, box_mm, mask_px):
    """The plate's median colour under a box (mm), outside a mask (the glyphs) — the ground the line stands on."""
    x0, y0, x1, y1 = (int(round(v * PX_PER_MM)) for v in box_mm)
    region = plate[y0:y1, x0:x1].reshape(-1, 3)
    keep = ~mask_px[y0:y1, x0:x1].reshape(-1)
    return '#%02X%02X%02X' % tuple(int(round(v)) for v in np.median(region[keep], axis=0))


def contrast_ratio(hex1, hex2):
    def lum(h):
        c = np.array([int(h.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)]) / 255.0
        lin = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
        return float(0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2])
    a, b = sorted((lum(hex1), lum(hex2)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def alif_share(fits, faces=None):
    """The Arabic alif's ink height against its Latin pair's capitals (the descriptor), both in their faces at their
    fitted sizes."""
    from apps.ire.text_metrics import cap_height_em_measured, ink_extent_em
    alif_mm = ink_extent_em('ا', line_face('descriptor_ar', faces)['path'])[0] * fits['descriptor_ar']['size_mm']
    cap_mm = cap_height_em_measured(line_face('descriptor_en', faces)['path']) * fits['descriptor_en']['size_mm']
    return {'alif_mm': round(alif_mm, 3), 'latin_cap_mm': round(cap_mm, 3), 'share': round(alif_mm / cap_mm, 4)}


def licensed_faces(arabic):
    """The licensed faces (``font_roles.catalogue``: the house's and the D-D7-1 GRANTED pool) carrying Latin, or Arabic
    letters: stem → {path, variable, axes, house}."""
    from apps.ire import font_roles
    out = {}
    for stem, e in font_roles.catalogue().items():
        if (arabic and e['arabic_letters']) or (not arabic and e['latin']):
            axes = {}
            if e['axes']:
                axes = {k: tuple(v) for k, v in e['axes'].items()}
            out[stem] = {'path': e['path'], 'variable': e['variable'], 'axes': axes,
                         'house': '/static/fonts/brand2026/' in e['path']}
    return out


def rank_pooled(line_units_texts, faces):
    """One ranking over several lines that share their lettering: each face's outline distance pooled over every
    glyph of every line (a face that cannot draw a line's glyphs one for one is left out)."""
    ranked = []
    for stem, face in faces.items():
        weights = [None]
        if face['variable'] and 'wght' in face['axes']:
            lo, _, hi = face['axes']['wght']
            weights = [w for w in MATCH_WEIGHTS if lo <= w <= hi]
        for w in weights:
            sums = [score_face(units, face['path'], text, w, False) for units, text in line_units_texts]
            if any(x is None for x in sums):
                continue
            dist = sum(x['dist_sum_px'] for x in sums) / sum(x['edge_px'] for x in sums) / (PX_PER_MM_SRC * MATCH_SCALE)
            iou = sum(x['inter_px'] for x in sums) / sum(x['union_px'] for x in sums)
            ranked.append({'stem': stem, 'wght': w, 'house': face['house'], 'distance': round(dist, 4), 'iou': round(iou, 4)})
    ranked.sort(key=lambda r: r['distance'])
    return {'measured': len(ranked), 'ranked': ranked}


def face_record(pick):
    """D-D8-5 measured line by line: the closest licensed face sets each line, a house face winning a near-tie (within
    5 %). The descriptor and the shade count share their lettering in the sketch (S H A D E drawn alike), so their pooled
    ranking is kept beside the per-line ones as information; the per-line reading is the rule. Each choice is asserted
    against the constants the build sets with."""
    latin, arabic = licensed_faces(False), licensed_faces(True)
    units = {}
    for key in LINES:
        u, _ = line_units(pick, key)
        if key == 'net':
            u = [x for r in runs_of(key, u) if r['text'] != SIGN for x in r['units']]
        units[key] = u
    texts = {'descriptor_en': 'EYESHADOW PALETTE', 'shades': '18 SHADES', 'net': '27g0.95oz',
             'descriptor_ar': LINES['descriptor_ar']['copy']}
    rec = {}
    for key in LINES:
        r = rank_faces(units[key], arabic if LINES[key]['rtl'] else latin, texts[key], LINES[key]['rtl'])
        rec[key] = {'chosen': choose_face(r), 'top': r['ranked'][:10], 'measured': r['measured']}
    pooled = rank_pooled([(units['descriptor_en'], texts['descriptor_en']), (units['shades'], texts['shades'])], latin)
    rec['descriptor_en+shades (information)'] = {'closest': choose_face(pooled), 'top': pooled['ranked'][:10],
                                                  'measured': pooled['measured']}
    expect = {'descriptor_en': SUPPORT_STEM, 'shades': SHADES_STEM, 'net': NET_STEM, 'descriptor_ar': ARABIC_SOURCE_STEM}
    for key, stem in expect.items():
        if rec[key]['chosen']['stem'] != stem:
            raise ValueError('D-D8-5 now measures %s for %s, not %s' % (rec[key]['chosen'], key, stem))
    rec['ocr'] = 'the match is made on lines the sketch reads exactly (D-D8-5): EYESHADOW PALETTE and 18 SHADES read ' \
                 'exactly; the Arabic line reads its three words (and a stray period); the net line reads 27g 0.95 oz ' \
                 'with its ℮ masked (the sign is drawn by the engine)'
    rec['distance'] = 'the symmetric mean distance (mm on the lid) between the sketch\'s glyph outlines and the face\'s, ' \
                      'each glyph placed by its best overlap; the faces of the house and the D-D7-1 GRANTED pool only'
    return rec


FORM_DEPTH_MAX = 8


def _xobjects(pdf, xref):
    """The XObjects an object's resources name: name → xref."""
    kind, value = pdf.xref_get_key(xref, 'Resources/XObject')
    if kind == 'xref':
        value = pdf.xref_object(int(value.split()[0]), compressed=True)
    return {name: int(ref) for name, ref in re.findall(r'/([^\s/<>\[\]()]+)\s*(\d+) 0 R', value)}


def _expanded(pdf, content, names, depth):
    """A content stream with each form it draws (``/Name Do``) replaced by the form's own content, in drawing order."""
    if depth > FORM_DEPTH_MAX:
        raise ValueError('forms nested deeper than %d' % FORM_DEPTH_MAX)

    def form(m):
        xref = names.get(m.group(1))
        if xref is None or pdf.xref_get_key(xref, 'Subtype')[1] != '/Form':
            return m.group(0)
        return _expanded(pdf, pdf.xref_stream(xref).decode('latin-1'), _xobjects(pdf, xref), depth + 1)
    return re.sub(r'/([^\s/<>\[\]()]+)\s+Do\b', form, content)


def actual_texts(pdf_path, page_index):
    """The words a page says it carries: its ActualText spans in drawing order (each TextRun's logical words, a
    logotype's or a sign's own), decoded — the page's own content and every form it draws (a placed page, as the
    layered files place the engine's), in order."""
    import fitz
    with fitz.open(str(pdf_path)) as pdf:
        page = pdf[page_index]
        content = _expanded(pdf, page.read_contents().decode('latin-1'), _xobjects(pdf, page.xref), 0)
    return [bytes.fromhex(h).decode('utf-16-be') for h in re.findall(r'/ActualText <FEFF([0-9A-Fa-f]*)>', content)]


def pt(mm):
    return mm * 72.0 / MM_PER_INCH


def tag_srgb(doc):
    """Every image in a PyMuPDF document carries sRGB: a DeviceRGB image is tagged with the system's sRGB profile
    (ICCBased, N 3); one PyMuPDF has tagged already (its own sRGB profile, ICCBased N 3) is kept as it is. Returns each
    image's xref and what it carries, the profile named as it names itself."""
    images = [x for x in range(1, doc.xref_length()) if doc.xref_get_key(x, 'Subtype')[1] == '/Image']
    icc = None
    carried = []
    for xref in images:
        if doc.xref_get_key(xref, 'ColorSpace')[1] == '/DeviceRGB':
            if icc is None:
                icc = doc.get_new_xref()
                doc.update_object(icc, '<< /N 3 /Alternate /DeviceRGB >>')
                doc.update_stream(icc, SRGB_ICC.read_bytes())
            doc.xref_set_key(xref, 'ColorSpace', '[/ICCBased %d 0 R]' % icc)
        carried.append(dict(image_colour_space(doc, xref), xref=xref))
    return carried


def label(page, text, x_mm, y_mm, font_path):
    """A small guide label in the support face (embedded), 6 pt, at x, baseline y (mm)."""
    page.insert_font(fontname='support', fontfile=str(font_path))
    page.insert_text((pt(x_mm), pt(y_mm)), text, fontname='support', fontsize=6, color=(0.25, 0.25, 0.25))


def crop_marks(page, trim_rect_mm):
    """Crop marks at the trim's four corners, outside the bleed: 0.25 pt, 5 mm long, 3 mm off the trim."""
    x0, y0, x1, y1 = trim_rect_mm
    g, n = CROP_MARK_GAP_MM, CROP_MARK_MM
    import fitz
    for x, y, sx, sy in ((x0, y0, -1, -1), (x1, y0, 1, -1), (x0, y1, -1, 1), (x1, y1, 1, 1)):
        page.draw_line(fitz.Point(pt(x + sx * g), pt(y)), fitz.Point(pt(x + sx * (g + n)), pt(y)), color=(0, 0, 0), width=0.25)
        page.draw_line(fitz.Point(pt(x), pt(y + sy * g)), fitz.Point(pt(x), pt(y + sy * (g + n))), color=(0, 0, 0), width=0.25)


def render_png(pdf_path, page, dpi, out_png):
    import fitz
    with fitz.open(str(pdf_path)) as doc:
        pix = doc[page].get_pixmap(dpi=int(round(dpi)), alpha=False)
        pix.set_dpi(int(round(dpi)), int(round(dpi)))
        pix.save(str(out_png))
    return out_png


def flat_1536(pdf_path, out_png):
    """Page 1 of a 190 × 120 document rendered at 4 × the pick's grid and brought to 1536 × 970 by Lanczos (the scale
    the finish proof is proven at)."""
    import fitz
    with fitz.open(str(pdf_path)) as doc:
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(4 * PICK_PX[0] / pt(LID_MM[0]), 4 * PICK_PX[1] / pt(LID_MM[1])),
                                alpha=False)
        img = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    img.resize(PICK_PX, Image.LANCZOS).save(out_png)
    return out_png


def said_specks(specks):
    """The crisp gold left in the raster, said from its own readings."""
    if not specks:
        return 'no crisp gold outside the name and the logo'
    x0, y0, x1, y1 = OVAL_BOX
    in_oval = sum(1 for r in specks if x0 <= r['centre_px'][0] < x1 and y0 <= r['centre_px'][1] < y1)
    widths = [r['widest_line_mm'] for r in specks]
    return ('%d crisp gold specks outside the name and the logo, %d of them in the oval and its bars (%.2f mm² in all, '
            'the largest %.3f mm²; their widest lines %.2f–%.2f mm, so the foil limits would pass a line, each one an '
            'isolated dot): glints of the painted light, left unfoiled in the raster — D-D10-2.5 names the bars painted '
            'light, and a foil dot this small is no lettering of the sketch. A judgement, said as one' % (
                len(specks), in_oval, sum(r['area_mm2'] for r in specks), max(r['area_mm2'] for r in specks),
                min(widths), max(widths)))


def said_relief(bars):
    """The relief decision, said from the bars' readings."""
    rises = [b['long_edge_rise_mm'] for b in bars['bars']]
    letters = list(bars['lettering_rise_mm'].values())
    return ('none. A-2 declared the five bars embossed; D-D10-2.5 allows relief only there and only where the edge is '
            'crisp, and names the bars painted light that prints as raster. On one operator the bars\' long edges rise '
            'over %.2f–%.2f mm against the sketch\'s lettering\'s %.2f–%.2f (the operator\'s floor %.2f): near-crisp, '
            'not soft as first read; their ends fade over %.1f mm or more. No relief pass is added today: whether the '
            'bars are embossed is the owner\'s call' % (min(rises), max(rises), min(letters), max(letters),
                                                       bars['floor_mm'], min(min(b['end_fade_mm']) for b in bars['bars'])))


def build(out_dir, *, faces=None, faces_record=None, relief=None, schema=SCHEMA, subject=None):
    """§1 at $0: the master of the pick, every file and record under ``out_dir`` (``docs/audit/day-10/lid``).

    [Day 11, D-D11-5] Golden Hour's fixes, each only when given (Day 10's master is built without them):
    ``faces`` (line → (stem, weight)) sets the lines it names in that face, ``faces_record`` the measured choice behind
    it (D-D8-5's record, kept in place of ``face_record``'s per-line one); ``relief`` ({'rings_mm', 'record', 'said'},
    and 'measure': the engine file → what its plate measures, merged into the record before the checks) puts the bars'
    emboss on its plate (an invisible carrier, the relief page and layer); ``schema`` and ``subject`` name the record
    and the print file."""
    import fitz
    from apps.ire import font_roles
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.lettering import extracted_text
    from apps.pipeline.services import finish_proof
    out = Path(out_dir)
    (out / 'engine').mkdir(parents=True, exist_ok=True)
    (out / 'crops').mkdir(parents=True, exist_ok=True)
    rec = {'schema': schema, 'pick': {'path': rel(PICK), 'sha256': PICK_SHA256, 'px': list(PICK_PX)}}
    relief_rings = None
    if relief is not None:
        relief_rings = relief['rings_mm']
    pick = load_pick(PICK)

    # 1. resolution
    up = upscale(pick)
    rec['upscale'] = prove_upscale(pick, up, REGIONS)
    rec['upscale']['tried_and_refused'] = {
        'iterative back-projection (20 rounds)': 'max ΔE00 7.8–8.9 and 8–10 % of pixels overshooting their neighbourhood',
        'block-mean correction': 'max ΔE00 6.9 (clipping at 0), overshoot 7.9 %',
        'anti-ringing clamp 3×3 / 2×2': 'max ΔE00 10.7 / 30.1',
        'a super-resolution model': 'not tried: no runtime on this machine; a learned model invents texture by design'}
    rec['sharpness'] = sharpness(pick, up, LETTERING_BOXES['name'])

    # 2. the plate cleaned under the small words, the ℮ and the logo
    plate, masks, cleaning = clean_plate(pick, up, name_keep_out(pick, up.shape[:2]))
    for key, m in masks.items():
        cleaning[key]['residue'] = residue(plate, m)
        cleaning[key].pop('donors')
    rec['cleaning'] = {'method': 'each glyph and its 1 px emboss rim (grown 2 pick px) filled by one Poisson solve per '
                                 'line: guidance the picture\'s own clean ground taken per glyph (the nearest shift whose '
                                 'ground matches the glyph\'s surroundings), boundary the picture itself; the glyphs only, '
                                 'never their box; the name left in the raster under its foil', 'lines': cleaning}
    Image.fromarray(plate).save(out / 'engine' / 'plate.png')
    plate_bleed = bleed(plate)
    Image.fromarray(plate_bleed).save(out / 'engine' / 'plate-bleed.png')

    # 2b. the faces (D-D8-5, measured) and the live lines
    ensure_arabic_face()
    if faces_record is None:
        rec['faces'] = face_record(pick)
    else:
        rec['faces'] = dict(faces_record)
    rec['faces']['arabic_faithfulness'] = arabic_faithfulness(out)
    fits, inks, sketch = fit_lines(pick, faces)
    type_group = type_nodes(fits, inks, faces)
    # repair 1 of D-D10-3 (the eye's round 0): the sketch's word spaces kept — measured on a first emit of the type
    probe = out / 'engine' / 'type-probe.ai'
    emit_type_probe(probe, type_group)
    spaces = word_spaces(fits, sketch, render_page(probe, 0, RENDER_PX_PER_MM))
    probe.unlink()
    type_group = type_nodes(fits, inks, faces)

    # 3. the name
    name_rings, _, trace_proof = trace_name(pick, NAME_BOX)
    trace_proof['against_the_pick_itself'] = outline_on_pick_with_controls(pick, name_rings)
    rec['name'] = {'trace': trace_proof, 'measures': name_measures(name_rings),
                   'settings': {'tracer': 'potrace 1.16', 'alphamax': NAME_ALPHAMAX, 'opttolerance': NAME_OPTTOLERANCE,
                                'turdsize': NAME_TURDSIZE, 'grid': '%d× the pick, cubic, cut at one half' % NAME_TRACE_SCALE}}
    name_gold = ink_gold(pick)
    rec['name']['gold'] = name_gold

    # 4. the logo
    fit = fit_logo(pick, LOGO_BOX)
    t = fit['transform']
    logo_box = (fit['placed_ink_box_mm'][0], fit['placed_ink_box_mm'][1],
                fit['placed_ink_box_mm'][2] - fit['placed_ink_box_mm'][0],
                fit['placed_ink_box_mm'][3] - fit['placed_ink_box_mm'][1])
    logo_gold = logo_ink(pick)
    rec['logo'] = dict(fit, gold=logo_gold, transform=t)

    # the engine document (190 × 120): the checks' and the finish proof's file
    engine_ai = out / 'engine' / 'lid-engine.ai'
    doc = engine_document(plate_png=out / 'engine' / 'plate.png', type_group=type_group, name_rings=name_rings,
                          name_gold=name_gold, logo_box_mm=logo_box, logo_gold=logo_gold, foil_letters=True,
                          layers=('picture', 'type', 'logo', 'foil carriers'), relief_rings=relief_rings)
    usage = {}
    emit_pdf_ai(doc, str(engine_ai), usage_out=usage)
    if relief is not None and 'measure' in relief:
        # [Day 11] the relief as the file carries it, measured before the checks read its proofs
        relief['record'].update(relief['measure'](engine_ai))
    # the same lid with the name's traced outlines drawn in its gold: what the eye and the crops read the trace on
    emit_pdf_ai(engine_document(plate_png=out / 'engine' / 'plate.png', type_group=type_group, name_rings=name_rings,
                                name_gold=name_gold, logo_box_mm=logo_box, logo_gold=logo_gold, foil_letters=True,
                                layers=('picture', 'type', 'logo', 'name')), str(out / 'engine' / 'lid-name-drawn.ai'))
    flat = flat_1536(engine_ai, out / 'engine' / 'flat-1536.png')
    proof = finish_proof.prove_build(flat, engine_ai, out / 'engine' / 'proof-record', foil_drawn=True)
    (out / 'finish-proof.png').write_bytes((out / 'engine' / 'proof-record' / 'finish-proof.png').read_bytes())

    # 5. finishes
    crisp, crisp_mask = crisp_gold(pick, REGIONS)
    specks = crisp_specks(crisp_mask, (NAME_BOX, LOGO_BOX))
    bars = bar_edges(pick, OVAL_BOX, BAR_CENTRES, LETTERING_BOXES)
    engraving = engraving_lines(pick, BAR_CENTRES, bars['bar_normal'])
    limits = proof['foil_limits']
    rec['finishes'] = {'crisp_gold': crisp, 'bars': bars, 'engraving': engraving, 'coverage': proof['coverage'],
                       'foil_limits': limits,
                       'foil': 'the name\'s traced outlines and the logo\'s letters (B B R S E): the letters alone pass '
                               'the foil limits at the placed width; the rose emblem (a gap under 0.2 mm in its spiral) '
                               'and the ® print in ink',
                       'crisp_gold_left_as_raster': {'specks': specks, 'said': said_specks(specks)},
                       'relief': said_relief(bars)}
    if relief is not None:
        rec['finishes']['relief'] = relief['said']
        rec['finishes']['relief_mask'] = relief['record']

    # 6. bleed and safe area
    rec['bleed'] = {'px': bleed_px(), 'mm': round(bleed_px() / PX_PER_MM, 4), 'method': 'mirror of the picture\'s own '
                    'edges (OpenCV BORDER_REFLECT_101); the trim area checked unchanged pixel for pixel'}
    boxes = {key: tuple(np.asarray([u['box_mm'] for u in sketch[key]])[:, i].min() if i < 2 else
                        np.asarray([u['box_mm'] for u in sketch[key]])[:, i].max() for i in range(4)) for key in LINES}
    boxes['name'] = tuple(rec['name']['measures']['ink_box_mm'])
    boxes['logo'] = tuple(fit['placed_ink_box_mm'])
    rec['safe_area'] = safe_area(boxes)
    if relief is not None:
        # [Day 11] the emboss is the picture's bars, not a copy line: measured against the safe margin and said
        rec['finishes']['relief_mask']['safe_margin'] = relief_safe_margin(relief['record']['bounds_mm'])

    # the overlay proof of the live lines, read from the engine's own page 1
    render = render_page(engine_ai, 0, RENDER_PX_PER_MM)
    rec['type'] = {'faces': {key: line_face(key, faces) for key in LINES},
                   'fits': fits, 'inks': inks, 'word_spaces_kept': spaces,
                   'overlay': {key: overlay_proof(sketch[key], drawn_units(render, key)) for key in LINES}}

    # the master's files
    write_master_files(out, engine_ai, plate_bleed, name_rings, name_gold, type_group, logo_box, logo_gold,
                       relief_rings=relief_rings, subject=subject)
    empty = ('relief',)
    if relief_rings is not None:
        empty = ()
    rec['ai_read_back'] = read_back_ai(out / 'lid-master.ai', engine_ai,
                                       {row['element']: row['ink_box_mm'] for row in rec['safe_area']}, empty=empty)
    rec['files'] = {p.name: {'sha256': sha256(p), 'bytes': p.stat().st_size} for p in sorted(out.glob('*')) if p.is_file()}
    rec['checks'] = checks(out, engine_ai, plate, masks, fits, inks, rec, sketch, name_keep_out(pick, plate.shape[:2]), name_gold,
                           faces=faces)
    write_json(out / 'checks.json', rec['checks'])
    write_json(out / 'media-map.json', media_map(rec))
    write_json(out / 'preflight.json', preflight(out, rec, usage))
    crops(out, pick, engine_ai, out / 'engine' / 'lid-name-drawn.ai', sketch, rec)
    write_json(out / 'master.json', rec)
    rec['_sketch'] = sketch
    return rec


def ink_gold(pick):
    """The name's gold as the sketch prints it: the median of the letters' cores (alpha ≥ 0.9)."""
    alpha = gold_alpha(pick, NAME_BOX)
    x0, y0, x1, y1 = NAME_BOX
    rgb = np.median(pick[y0:y1, x0:x1][alpha >= 0.9], axis=0)
    return '#%02X%02X%02X' % tuple(int(round(v)) for v in rgb)


def logo_ink(pick):
    """The logo's gold as the sketch prints it: the median of its gold's core (eroded once)."""
    x0, y0, x1, y1 = LOGO_BOX
    m = cv2.erode(logo_mask_in_sketch(pick, LOGO_BOX).astype(np.uint8), np.ones((2, 2), np.uint8)).astype(bool)
    rgb = np.median(pick[y0:y1, x0:x1][m], axis=0)
    return '#%02X%02X%02X' % tuple(int(round(v)) for v in rgb)


def _trim_rect():
    import fitz
    return fitz.Rect(pt(BLEED_MM), pt(BLEED_MM), pt(BLEED_MM + LID_MM[0]), pt(BLEED_MM + LID_MM[1]))


def _picture_rect(origin_mm):
    """Where the bled plate lands: its trim area exactly on the trim, its 49 px band (3.03 mm) beyond."""
    import fitz
    b = bleed_px() / PX_PER_MM
    ox, oy = origin_mm
    return fitz.Rect(pt(ox - b), pt(oy - b), pt(ox + LID_MM[0] + b), pt(oy + LID_MM[1] + b))


def _emit_layer(out, name, doc):
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    path = out / 'engine' / ('layer-%s.ai' % name)
    emit_pdf_ai(doc, str(path))
    return path


def write_master_files(out, engine_ai, plate_bleed, name_rings, name_gold, type_group, logo_box, logo_gold,
                       relief_rings=None, subject=None):
    """lid-master.pdf (196 × 126 mm, trim 190 × 120: page 1 the artwork — the picture plate, RGB tagged sRGB at the
    resampled resolution, with the type and the logo over it, vector, fonts embedded, each on its own layer; page 2
    the foil plate; page 3 the relief plate; page 4 the trim, bleed and safe area), lid-master.ai (one page, the same in layer groups: picture, type, name,
    logo, foil, relief, guides — picture, type, logo and guides shown, the plates hidden), lid-master-flat.png (the
    print at 300 PPI) and lid-1to1-A4.pdf (the lid at 100 % on A4 landscape with crop marks; page 2 the finish proof at
    the same scale). The relief plate and layer stay empty unless ``relief_rings`` [Day 11, D-D11-5.1] gives the bars'
    emboss (black, its own layer file ``engine/layer-relief.ai`` for the box); ``subject`` names the print file (Day
    10's when None)."""
    import fitz
    from apps.ire import font_roles
    from apps.ire.graph import Color, Document, Group, Path, SolidFill
    support = font_roles.resolve_line_face(SUPPORT_STEM, SUPPORT_WEIGHT)['path']
    bleed_png = out / 'engine' / 'plate-bleed.png'
    layers = {
        'type': _emit_layer(out, 'type', Document(page_w=LID_MM[0], page_h=LID_MM[1], metadata={
            'typography_surface': SURFACE, 'logical_text/1.0': True}, root=Group(name='TYPE', children=[type_group]))),
        'logo': _emit_layer(out, 'logo', Document(page_w=LID_MM[0], page_h=LID_MM[1], metadata={
            'typography_surface': SURFACE}, root=Group(name='LOGO', role='logo', children=logo_parts(
                logo_box, logo_gold, foil_letters=False)))),
        'name': _emit_layer(out, 'name', Document(page_w=LID_MM[0], page_h=LID_MM[1], metadata={
            'typography_surface': SURFACE}, root=Group(name='NAME', role='typography', actual_text='Enchanted Rose',
                                                       children=[Path(name='Enchanted Rose', segments=rings_segments(name_rings),
                                                                      fill=SolidFill(color=Color.from_hex(name_gold)),
                                                                      fill_rule='evenodd')]))),
    }
    black = Color.from_hex('#000000')
    letters = [p.model_copy(update={'fill': SolidFill(color=black), 'finishes': []})
               for p in logo_parts(logo_box, logo_gold, foil_letters=True) if p.finishes]
    layers['foil'] = _emit_layer(out, 'foil', Document(page_w=LID_MM[0], page_h=LID_MM[1], metadata={
        'typography_surface': SURFACE}, root=Group(name='FOIL', children=[
            Path(name='Enchanted Rose (foil)', segments=rings_segments(name_rings), fill=SolidFill(color=black),
                 fill_rule='evenodd')] + letters)))
    relief_label = '3 relief plate (none) '
    if relief_rings is not None:
        layers['relief'] = _emit_layer(out, 'relief', Document(page_w=LID_MM[0], page_h=LID_MM[1], metadata={
            'typography_surface': SURFACE}, root=Group(name='RELIEF', children=[
                Path(name='the five bars (blind emboss)', segments=rings_segments(relief_rings),
                     fill=SolidFill(color=black), fill_rule='evenodd')])))
        relief_label = '3 relief plate (blind emboss: the five bars) '
    if subject is None:
        subject = 'Day 10 §1: the master of the owner\'s pick A-2.3'
    trim = _trim_rect()
    w, h = pt(LID_MM[0] + 2 * BLEED_MM), pt(LID_MM[1] + 2 * BLEED_MM)

    # lid-master.pdf: four pages, the artwork whole on the first (the review of Day 10: no page carried it)
    pdf = fitz.open()
    ocg = {name: pdf.add_ocg(name, on=True) for name in ('picture', 'type', 'logo', 'foil', 'relief', 'guides')}
    srcs = {k: fitz.open(str(v)) for k, v in layers.items()}
    p = pdf.new_page(width=w, height=h)
    p.insert_image(_picture_rect((BLEED_MM, BLEED_MM)), filename=str(bleed_png), oc=ocg['picture'])
    p.show_pdf_page(trim, srcs['type'], 0, oc=ocg['type'])
    p.show_pdf_page(trim, srcs['logo'], 0, oc=ocg['logo'])
    p = pdf.new_page(width=w, height=h)
    p.show_pdf_page(trim, srcs['foil'], 0, oc=ocg['foil'])
    p = pdf.new_page(width=w, height=h)                   # the relief plate: none unless given (its page label says so)
    if 'relief' in srcs:
        p.show_pdf_page(trim, srcs['relief'], 0, oc=ocg['relief'])
    p = pdf.new_page(width=w, height=h)
    _guides(p, support, ocg['guides'])
    for page in pdf:
        page.set_bleedbox(page.rect)
        page.set_trimbox(trim)
    pdf.set_page_labels([{'startpage': i, 'prefix': name, 'style': ''} for i, name in enumerate(
        ('1 artwork: picture (RGB, sRGB), type, logo ', '2 foil plate ', relief_label,
          '4 trim, bleed, safe '))])
    pdf.set_metadata({'title': 'Enchanted Rose lid master', 'subject': subject,
                      'creator': SURFACE, 'producer': 'PyMuPDF %s' % fitz.VersionBind})
    tag_srgb(pdf)
    pdf.save(str(out / 'lid-master.pdf'), garbage=3, deflate=True)
    pdf.close()

    # lid-master.ai: one page, seven layer groups
    ai = fitz.open()
    ocg = {name: ai.add_ocg(name, on=name in ('picture', 'type', 'logo', 'guides'))
           for name in ('picture', 'type', 'name', 'logo', 'foil', 'relief', 'guides')}
    p = ai.new_page(width=w, height=h)
    p.insert_image(_picture_rect((BLEED_MM, BLEED_MM)), filename=str(bleed_png), oc=ocg['picture'])
    p.show_pdf_page(trim, srcs['type'], 0, oc=ocg['type'])
    p.show_pdf_page(trim, srcs['name'], 0, oc=ocg['name'])
    p.show_pdf_page(trim, srcs['logo'], 0, oc=ocg['logo'])
    p.show_pdf_page(trim, srcs['foil'], 0, oc=ocg['foil'])
    if 'relief' in srcs:                                  # [Day 11] the bars' emboss; on Day 10 the layer stays empty
        p.show_pdf_page(trim, srcs['relief'], 0, oc=ocg['relief'])
    _guides(p, support, ocg['guides'])
    p.set_bleedbox(p.rect)
    p.set_trimbox(trim)
    ai.set_metadata({'title': 'Enchanted Rose lid master (layers)', 'creator': SURFACE})
    tag_srgb(ai)
    ai.save(str(out / 'lid-master.ai'), garbage=3, deflate=True)
    ai.close()
    for s in srcs.values():
        s.close()

    # the flat at 300 PPI (the trim, as it prints)
    render_png(engine_ai, 0, FLAT_PPI, out / 'lid-master-flat.png')

    # lid-1to1-A4.pdf
    a4 = fitz.open()
    aw, ah = A4_LANDSCAPE_MM
    x0, y0 = (aw - LID_MM[0]) / 2, (ah - LID_MM[1]) / 2
    trim_a4 = fitz.Rect(pt(x0), pt(y0), pt(x0 + LID_MM[0]), pt(y0 + LID_MM[1]))
    src_type, src_logo = fitz.open(str(layers['type'])), fitz.open(str(layers['logo']))
    p = a4.new_page(width=pt(aw), height=pt(ah))
    p.insert_image(_picture_rect((x0, y0)), filename=str(bleed_png))
    p.show_pdf_page(trim_a4, src_type, 0)
    p.show_pdf_page(trim_a4, src_logo, 0)
    crop_marks(p, (x0, y0, x0 + LID_MM[0], y0 + LID_MM[1]))
    label(p, 'Enchanted Rose lid master at 100 %: trim 190 x 120 mm inside the crop marks, 3 mm bleed. Print at actual size '
             '(no scaling); the ruler below is 100 mm.', x0, y0 + LID_MM[1] + 12, support)
    _ruler(p, x0, y0 + LID_MM[1] + 16)
    p = a4.new_page(width=pt(aw), height=pt(ah))
    p.insert_image(trim_a4, filename=str(out / 'finish-proof.png'))
    crop_marks(p, (x0, y0, x0 + LID_MM[0], y0 + LID_MM[1]))
    finishes_said = 'gold foil on the name and the logo\'s letters; no relief.'
    if relief_rings is not None:
        finishes_said = 'gold foil on the name and the logo\'s letters; blind emboss on the five bars.'
    label(p, 'The finish proof at the same scale: ' + finishes_said, x0, y0 + LID_MM[1] + 12, support)
    _ruler(p, x0, y0 + LID_MM[1] + 16)
    src_type.close()
    src_logo.close()
    tag_srgb(a4)
    a4.save(str(out / 'lid-1to1-A4.pdf'), garbage=3, deflate=True)
    a4.close()


def _guides(page, font_path, oc):
    """The trim (a solid hairline), the bleed (dashed) and the safe area 4 mm inside the trim (dashed), labelled."""
    import fitz
    trim = _trim_rect()
    safe = fitz.Rect(pt(BLEED_MM + SAFE_MM), pt(BLEED_MM + SAFE_MM), pt(BLEED_MM + LID_MM[0] - SAFE_MM),
                     pt(BLEED_MM + LID_MM[1] - SAFE_MM))
    page.draw_rect(trim, color=(0.85, 0, 0.55), width=0.25, oc=oc)
    page.draw_rect(page.rect + (0.5, 0.5, -0.5, -0.5), color=(0.5, 0.5, 0.5), width=0.25, dashes='[2 2] 0', oc=oc)
    page.draw_rect(safe, color=(0, 0.6, 0.9), width=0.25, dashes='[1 2] 0', oc=oc)
    page.insert_font(fontname='support', fontfile=str(font_path))
    page.insert_text((pt(BLEED_MM + SAFE_MM + 1), pt(BLEED_MM + SAFE_MM + 3)), 'SAFE 4 mm', fontname='support',
                     fontsize=5, color=(0, 0.6, 0.9), oc=oc)
    page.insert_text((pt(BLEED_MM + 1), pt(BLEED_MM + LID_MM[1] - 1)), 'TRIM 190 x 120 mm - BLEED 3 mm', fontname='support',
                     fontsize=5, color=(0.85, 0, 0.55), oc=oc)


def _ruler(page, x_mm, y_mm):
    """A 100 mm ruler with 10 mm ticks: the print's scale, checkable with a ruler."""
    import fitz
    page.draw_line(fitz.Point(pt(x_mm), pt(y_mm)), fitz.Point(pt(x_mm + 100), pt(y_mm)), color=(0, 0, 0), width=0.4)
    for i in range(11):
        tick = RULER_TICK_MM
        if i % 5 == 0:
            tick = RULER_TICK_LONG_MM
        page.draw_line(fitz.Point(pt(x_mm + 10 * i), pt(y_mm)), fitz.Point(pt(x_mm + 10 * i), pt(y_mm + tick)),
                       color=(0, 0, 0), width=0.3)


def _norm(text):
    import unicodedata
    return ' '.join(unicodedata.normalize('NFKC', text).split())


def checks(out, engine_ai, plate, masks, fits, inks, rec, sketch, name_mask, name_gold, faces=None):
    """D-D10-2.7: the measured checks, as reports (no check stops the master). Each line's contrast against the ground
    it stands on; the name's cap; the ℮; the smallest type; the Arabic alif against its Latin pair (in the faces the
    lines are set in: ``faces`` as the build had them); the copy word for word as the engine's page extracts it; the
    size with its bleed; and the proofs of placement, trace, logo and cleaning — and [Day 11] of the relief mask, when
    the record carries one."""
    import fitz
    from apps.ire.lettering import extracted_text
    rows = []
    for key in LINES:
        boxes = np.asarray([u['box_mm'] for u in sketch[key]])
        box = (boxes[:, 0].min(), boxes[:, 1].min(), boxes[:, 2].max(), boxes[:, 3].max())
        under = median_under(plate, box, masks[key])
        ratio = contrast_ratio(inks[key], under)
        floor = CONTRAST_FLOOR
        if LINES[key]['rtl'] or (box[3] - box[1]) >= LARGE_CAP_MM:
            floor = CONTRAST_FLOOR_LARGE
        rows.append({'line': key, 'ink': inks[key], 'under': under, 'ratio': round(ratio, 2), 'floor': floor,
                     'holds': bool(ratio >= floor)})
    name_box = rec['name']['measures']['ink_box_mm']
    under = median_under(plate, name_box, name_mask)
    rows.append({'line': 'name', 'ink': name_gold, 'under': under, 'ratio': round(contrast_ratio(name_gold, under), 2),
                 'floor': CONTRAST_FLOOR_LARGE, 'holds': bool(contrast_ratio(name_gold, under) >= CONTRAST_FLOOR_LARGE)})
    under = median_under(plate, rec['logo']['placed_ink_box_mm'], masks['logo'])
    rows.append({'line': 'logo', 'ink': rec['logo']['gold'], 'under': under,
                 'ratio': round(contrast_ratio(rec['logo']['gold'], under), 2), 'floor': CONTRAST_FLOOR_LARGE,
                 'holds': bool(contrast_ratio(rec['logo']['gold'], under) >= CONTRAST_FLOOR_LARGE)})
    smallest = min(f['size_pt'] for f in fits.values())
    alif = alif_share(fits, faces)
    sign_mm = fits['net']['sign']['height_mm']
    spans = actual_texts(engine_ai, 0)
    joined = ' ' + ' '.join(_norm(t) for t in spans) + ' '
    copy = {key: {'copy': LINES[key]['copy'], 'found': ' %s ' % _norm(LINES[key]['copy']) in joined} for key in LINES}
    copy['name'] = {'copy': 'Enchanted Rose', 'found': ' Enchanted Rose ' in joined}
    text = _norm(extracted_text(engine_ai, 0))
    with fitz.open(str(out / 'lid-master.pdf')) as pdf:
        page = pdf[0]
        media = [round(v * MM_PER_INCH / 72.0, 3) for v in (page.mediabox.width, page.mediabox.height)]
        trimbox = [round(v * MM_PER_INCH / 72.0, 3) for v in (page.trimbox.width, page.trimbox.height)]
    sizes = {'name_cap_mm': rec['name']['measures']['cap_height_mm'],
             'name_cap_holds': bool(rec['name']['measures']['cap_height_mm'] >= NAME_CAP_MIN_MM),
             'sign_mm': round(sign_mm, 3), 'sign_holds': bool(sign_mm >= SIGN_MIN_MM),
             'smallest_pt': round(smallest, 2), 'smallest_holds': bool(smallest >= TYPE_MIN_PT),
             'alif': alif, 'alif_holds': bool(alif['share'] >= ALIF_SHARE_MIN),
             'page_mm': media, 'trim_mm': trimbox,
             'page_holds': bool(abs(media[0] - (LID_MM[0] + 2 * BLEED_MM)) < 0.01 and abs(media[1] - (LID_MM[1] + 2 * BLEED_MM)) < 0.01
                                and abs(trimbox[0] - LID_MM[0]) < 0.01 and abs(trimbox[1] - LID_MM[1]) < 0.01)}
    proofs = {'upscale': rec['upscale']['holds'],
              'type_placed': {k: v['holds'] for k, v in rec['type']['overlay'].items()},
              'name_trace': rec['name']['trace']['holds'],
              'name_against_the_pick': rec['name']['trace']['against_the_pick_itself']['holds'],
              'logo_placed': rec['logo']['holds'],
              'foil_limits': rec['finishes']['foil_limits']['holds'],
              'safe_area': all(r['inside_safe'] for r in rec['safe_area']),
              'ai_read_back': rec['ai_read_back']['holds']}
    if 'relief_mask' in rec['finishes']:
        proofs['relief_mask'] = rec['finishes']['relief_mask']['holds']
    issues = []
    for r in rows:
        if not r['holds']:
            issues.append('%s: contrast %.2f under its floor %.1f' % (r['line'], r['ratio'], r['floor']))
    for k, v in (('name cap', sizes['name_cap_holds']), ('℮ height', sizes['sign_holds']),
                 ('smallest type', sizes['smallest_holds']), ('Arabic alif', sizes['alif_holds']),
                 ('page size', sizes['page_holds'])):
        if not v:
            issues.append('%s does not hold' % k)
    for key, c in copy.items():
        if not c['found']:
            issues.append('the copy of %s does not extract word for word' % key)
    # every proof that does not hold is an issue (the review of Day 10: seven proofs were recorded but never read)
    issues += proof_issues(proofs, rec['upscale'])
    out = {'schema': 'day10_lid_checks/1', 'contrast': rows, 'sizes': sizes, 'copy': copy,
           'actual_text_spans': spans, 'mupdf_default_extraction': text,
           'copy_reading': 'the words the file carries (ActualText, in drawing order); MuPDF\'s default extraction '
                           'spaces tracked letters and gives the Arabic in visual order, kept beside it', 'proofs': proofs, 'issues': issues, 'checks_hold': not issues,
           'note': 'D-D10-2.7: every check runs as a report; none stops the master'}
    # [Day 11] only where they exist (Day 10's checks carry neither): the proofs not measured (None: pending, or holding
    # only by construction), and the emboss's nearest trim, reported beside the safe area
    pending = pending_proofs(proofs, '')
    if pending:
        out['proofs_not_measured'] = pending
    if 'relief_mask' in rec['finishes'] and 'safe_margin' in rec['finishes']['relief_mask']:
        out['relief_safe_margin'] = rec['finishes']['relief_mask']['safe_margin']
    return out


def proof_issues(proofs, upscale):
    """The issues the proofs raise, in their order: the upscale's ΔE00 said with its numbers, a proof that does not
    hold as such, and [Day 11] a proof not measured (None: pending — the eye's verdict — or holding only by
    construction) as not measured, never as held."""
    pending = pending_proofs(proofs, '')
    issues = []
    for where in failed_proofs(proofs, ''):
        if where == 'upscale.de00_max':
            issues.append('the upscale\'s max ΔE00 %.2f is over 4 (%d pixels, %s)' % (
                upscale['de00_max'], upscale['pixels_over_max'], upscale['pixels_over_max_where']))
        elif where in pending:
            issues.append('%s is not measured (pending, or holding only by construction)' % where)
        else:
            issues.append('%s does not hold' % where)
    return issues


def failed_proofs(tree, path):
    """Every leaf of a nested record of proofs that does not hold, by its dotted path (a leaf None — not measured —
    is listed too: it is never read as held)."""
    if isinstance(tree, dict):
        found = []
        for key, value in tree.items():
            found += failed_proofs(value, '.'.join(x for x in (path, key) if x))
        return found
    if tree:
        return []
    return [path]


def pending_proofs(tree, path):
    """[Day 11] Every leaf of a nested record of proofs that is None — not measured (pending, or holding only by
    construction) — by its dotted path; ``failed_proofs`` lists them too."""
    if isinstance(tree, dict):
        found = []
        for key, value in tree.items():
            found += pending_proofs(value, '.'.join(x for x in (path, key) if x))
        return found
    if tree is None:
        return [path]
    return []


def media_map(rec):
    """D-D8-4: each element's medium and why."""
    return {'schema': 'day10_media_map/1', 'elements': [
        {'element': 'the picture (plaster, the oval of light, the five bars and their engraving, the shadow)',
         'medium': 'raster plate, RGB, tagged sRGB', 'resolution': '%s PPI (Lanczos 2× of the pick; effective %s PPI)' % (
             rec['sharpness']['resampled_ppi'], rec['sharpness']['effective_ppi']),
         'why': 'D-D10-1: the sketch\'s own pixels; painted light with soft edges prints as painted (D-D10-2.5)'},
        {'element': 'the raster name under the foil', 'medium': 'raster (part of the plate)',
         'why': 'D-D10-2.5: the print\'s fallback under the foil, the sketch\'s own gold'},
        {'element': 'Enchanted Rose', 'medium': 'vector outlines traced from the sketch (potrace), gold foil plate',
         'why': 'D-D10-2.3: lettering, not text; the trace overlays the sketch within %.3f mm' % (
             rec['name']['trace']['against_the_pick_itself']['max_mm'])},
        *[{'element': LINES[key]['copy'], 'medium': 'live text, %s, embedded' % rec['type']['faces'][key]['label'],
           'why': face_why(rec, key)} for key in LINES],
        {'element': '℮', 'medium': 'vector (the house\'s estimated sign, Montserrat\'s ℮)', 'why': 'the sign drawn as the '
                                                                                                    'sign, never left to a face'},
        {'element': 'the logo', 'medium': 'the approved vector master: the rose emblem and the ® in ink in the sketch\'s '
                                          'gold, the letters B B R S E in gold foil',
         'why': 'D-D10-2.4: the letters alone pass the foil limits at %.1f mm; the emblem does not' % (
             rec['logo']['placed_ink_box_mm'][2] - rec['logo']['placed_ink_box_mm'][0])},
        {'element': 'relief', 'medium': relief_medium(rec), 'why': rec['finishes']['relief']},
        {'element': 'the bleed', 'medium': 'raster: the picture\'s edges mirrored 3.03 mm', 'why': 'D-D10-2.6'}]}


ONE_FACE_KEY = 'one Latin face (D-D11-5.4)'   # [Day 11] the faces record's entry for the pooled choice


def face_why(rec, key):
    """Why a line is set in its face, from the record: measured on the line's own lettering (Day 10), or [Day 11,
    D-D11-5.4] the one Latin face, measured pooled over the three small lines."""
    chosen = rec['faces'][key]['chosen']
    if ONE_FACE_KEY in rec['faces'] and key in rec['faces'][ONE_FACE_KEY]['lines']:
        return ('D-D11-5.4 and D-D8-5: one Latin face for the three small lines, measured pooled over all three: %s '
                '(the closest: %s)' % (chosen['reason'], chosen['closest']))
    return 'D-D10-2.2 and D-D8-5, measured on this line\'s own lettering: %s (the closest: %s)' % (
        chosen['reason'], chosen['closest'])


def relief_medium(rec):
    """The relief's medium as the record has it: none (Day 10), or [Day 11, D-D11-5.1] the bars' blind emboss plate."""
    if 'relief_mask' not in rec['finishes']:
        return 'none'
    return ('blind emboss plate (%s): vector outlines traced (potrace) from the five bars\' 50 %% isoline, %.1f mm² '
            'in all' % (RELIEF_PLATE, rec['finishes']['relief_mask']['area_mm2']))


def preflight(out, rec, usage):
    """The print file read back: resolution, sharpness, fonts embedded (and which drew), foil limits, bleed, colour
    space, no CMYK conversion."""
    import fitz
    fonts = {}
    drawn = set()
    images = []
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
                xref = img[0]
                images.append(dict(image_colour_space(pdf, xref), page=i + 1, px=[img[2], img[3]],
                                   filter=pdf.xref_get_key(xref, 'Filter')[1]))
        boxes = {'media_mm': [round(v * MM_PER_INCH / 72, 3) for v in pdf[0].mediabox],
                 'trim_mm': [round(v * MM_PER_INCH / 72, 3) for v in pdf[0].trimbox],
                 'bleed_mm': [round(v * MM_PER_INCH / 72, 3) for v in pdf[0].bleedbox]}
    for name, f in fonts.items():
        f['draws'] = _font_key(name) in {_font_key(d) for d in drawn}
        if not f['draws'] and not f['embedded']:
            f['note'] = 'declared, never drawn: the emitter\'s empty BT /F1 … ET (reportlab\'s initial font)'
    pictures = [im for im in images if im['px'][0] > 1000]
    return {'schema': 'day10_preflight/1', 'file': 'lid-master.pdf',
            'source_ppi': rec['sharpness']['source_ppi'], 'resampled_ppi': rec['sharpness']['resampled_ppi'],
            'effective_ppi': rec['sharpness']['effective_ppi'], 'sharpness': rec['sharpness'],
            'print_ppi_300': rec['sharpness']['print_ppi_300'], 'images': images, 'fonts': fonts,
            'fonts_that_draw_embedded': all(f['embedded'] for f in fonts.values() if f['draws']),
            'foil_masks_within_limits': rec['finishes']['foil_limits']['holds'], 'boxes': boxes,
            'bleed_present': bool(boxes['bleed_mm'][2] - boxes['bleed_mm'][0] > boxes['trim_mm'][2] - boxes['trim_mm'][0] + 5.9),
            'colour_space': {'picture': [{k: im[k] for k in ('colour_space', 'n', 'profile')} for im in pictures],
                             'holds': bool(pictures) and all(im['colour_space'] == 'ICCBased' and im['n'] == 3
                                                             for im in pictures),
                             'said': 'the picture ICCBased (3 components, the profile named as it names itself); the '
                                     'type and the logo DeviceRGB; the plates black'},
            'cmyk_conversion_applied': False, 'note': 'RGB until the printer\'s profile (10-12)'}


def _render(pdf_path, dpi):
    import fitz
    with fitz.open(str(pdf_path)) as doc:
        pix = doc[0].get_pixmap(dpi=int(dpi), alpha=False)
        return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[..., :3]


def _font_key(name):
    """A font's name compared as PostScript names are: its subset prefix, spaces and hyphens dropped, case ignored."""
    return re.sub(r'[\s-]', '', name.split('+')[-1]).lower()


def icc_description(data):
    """An ICC profile's own name: its 'desc' tag (v2 textDescriptionType or v4 multiLocalizedUnicodeType)."""
    count = int.from_bytes(data[128:132], 'big')
    for i in range(count):
        entry = data[132 + 12 * i:144 + 12 * i]
        if entry[:4] != b'desc':
            continue
        off, size = int.from_bytes(entry[4:8], 'big'), int.from_bytes(entry[8:12], 'big')
        tag = data[off:off + size]
        if tag[:4] == b'desc':
            return tag[12:12 + int.from_bytes(tag[8:12], 'big')].rstrip(b'\0').decode('latin-1')
        if tag[:4] == b'mluc':
            length, at = int.from_bytes(tag[20:24], 'big'), int.from_bytes(tag[24:28], 'big')
            return tag[at:at + length].decode('utf-16-be')
        raise ValueError('the desc tag is %r' % tag[:4])
    raise ValueError('the profile has no desc tag')


def image_colour_space(pdf, xref):
    """An image's colour space resolved: its kind, its components and, for an ICC profile, the profile's own name."""
    value = pdf.xref_get_key(xref, 'ColorSpace')[1]
    ref = re.fullmatch(r'(\d+) 0 R', value)
    if ref:
        value = pdf.xref_object(int(ref.group(1)), compressed=True)
    icc = re.search(r'/ICCBased\s*(\d+) 0 R', value)
    if not icc:
        return {'colour_space': value, 'n': None, 'profile': None}
    stream = int(icc.group(1))
    return {'colour_space': 'ICCBased', 'n': int(pdf.xref_get_key(stream, 'N')[1]),
            'profile': icc_description(pdf.xref_stream(stream))}


def crops(out, pick, engine_ai, name_ai, sketch, rec):
    """The 1 : 1 crops (600 dpi), the pick beside the master, per small line, the name and the logo — the name's
    master side drawn with its traced outlines (``name_ai``), so the crop shows the trace, not the raster under it."""
    k = CROP_DPI / MM_PER_INCH
    master = _render(engine_ai, CROP_DPI)
    drawn = _render(name_ai, CROP_DPI)
    big_pick = cv2.resize(pick, (master.shape[1], master.shape[0]), interpolation=cv2.INTER_LANCZOS4)
    boxes = {key: (min(u['box_mm'][0] for u in sketch[key]), min(u['box_mm'][1] for u in sketch[key]),
                   max(u['box_mm'][2] for u in sketch[key]), max(u['box_mm'][3] for u in sketch[key])) for key in sketch}
    boxes['name'] = tuple(rec['name']['measures']['ink_box_mm'])
    boxes['logo'] = tuple(rec['logo']['placed_ink_box_mm'])
    made = {}
    for key, (x0, y0, x1, y1) in boxes.items():
        a, b = int((x0 - CROP_PAD_MM) * k), int((y0 - CROP_PAD_MM) * k)
        c, d = int((x1 + CROP_PAD_MM) * k), int((y1 + CROP_PAD_MM) * k)
        left, right = big_pick[b:d, a:c], master[b:d, a:c]
        if key == 'name':
            right = drawn[b:d, a:c]
        gap = np.full((left.shape[0], 6, 3), 255, dtype=np.uint8)
        path = out / 'crops' / ('%s-pick-master.png' % key)
        Image.fromarray(np.concatenate([left, gap, right], axis=1)).save(path, dpi=(CROP_DPI, CROP_DPI))
        made[key] = {'file': rel(path), 'box_mm': [round(v, 2) for v in (x0, y0, x1, y1)], 'dpi': CROP_DPI}
    rec['crops'] = made


# --- D-D10-3: the fidelity gate (the designer's eye) ------------------------------------------------------------------

EYE_PREFIX = 'day10/designer-eye/'
EYE_MAX_TOKENS = 8000
EYE_IMAGE_EDGE_MAX = 1568              # the API's own long-edge limit: an image is sent at its own pixels below it
DECISIONS = REPO / 'CURRENT_DECISIONS.md'
EYE_PIXELS_MAX = 1150000               # … and its total size: past ~1.15 MP an image is resampled before the model sees it


def allowed_differences():
    """D-D10-2 as the owner typed it and the builder recorded it (CURRENT_DECISIONS.md), verbatim: its seven items."""
    text = DECISIONS.read_text()
    start = text.index('- **D-D10-2 — The allowed differences')
    end = text.index('- **D-D10-3 —', start)
    return text[start:end].strip()


FIDELITY_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['differences', 'reads_as_the_pick', 'summary'],
    'properties': {
        'differences': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['where', 'pick_shows', 'master_shows', 'verdict', 'allowed_by', 'severity', 'repair'],
            'properties': {'where': {'type': 'string'}, 'pick_shows': {'type': 'string'},
                           'master_shows': {'type': 'string'},
                           'verdict': {'type': 'string', 'enum': ['allowed', 'defect']},
                           'allowed_by': {'type': 'string', 'enum': ['1', '2', '3', '4', '5', '6', '7', 'none']},
                           'severity': {'type': 'string', 'enum': ['blocking', 'major', 'minor']},
                           'repair': {'type': 'string'}}}},
        'reads_as_the_pick': {'type': 'boolean'},
        'summary': {'type': 'string'}}}
CROPS_SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['crops', 'summary'],
    'properties': {
        'crops': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['image', 'same_letters', 'placed_as_the_pick', 'invented_structure', 'verdict', 'allowed_by',
                         'notes'],
            'properties': {'image': {'type': 'integer'}, 'same_letters': {'type': 'boolean'},
                           'placed_as_the_pick': {'type': 'boolean'}, 'invented_structure': {'type': 'boolean'},
                           'verdict': {'type': 'string', 'enum': ['allowed', 'defect']},
                           'allowed_by': {'type': 'string', 'enum': ['1', '2', '3', '4', '5', '6', '7', 'none']},
                           'notes': {'type': 'string'}}}},
        'summary': {'type': 'string'}}}
EYE_CROPS = ('descriptor_en', 'descriptor_ar', 'shades', 'net', 'logo', 'name-1', 'name-2', 'name-3', 'name-4',
             'upscale-bars')


def eye_crops(out, pick, engine_ai, sketch, rec):
    """The crops the eye reads at 1 : 1 (600 dpi): the pick (Lanczos to 600 dpi) above the master, each no wider than
    the API sends unresized — the name in two halves; and the upscale itself: a piece of the bars, the pick's pixels
    repeated 2× above the Lanczos upscale (both at the upscale's grid)."""
    import fitz
    k = CROP_DPI / MM_PER_INCH
    with fitz.open(str(engine_ai)) as doc:
        pix = doc[0].get_pixmap(dpi=int(CROP_DPI), alpha=False)
        master = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[..., :3]
    big = cv2.resize(pick, (master.shape[1], master.shape[0]), interpolation=cv2.INTER_LANCZOS4)
    boxes = {key: (min(u['box_mm'][0] for u in sketch[key]), min(u['box_mm'][1] for u in sketch[key]),
                   max(u['box_mm'][2] for u in sketch[key]), max(u['box_mm'][3] for u in sketch[key])) for key in LINES}
    boxes['logo'] = tuple(rec['logo']['placed_ink_box_mm'])
    nx0, ny0, nx1, ny1 = rec['name']['measures']['ink_box_mm']
    cuts = [nx0 + (nx1 - nx0) * i / 4 for i in range(5)]   # four pieces, each under the API's size when stacked
    for i in range(4):
        boxes['name-%d' % (i + 1)] = (cuts[i], ny0, cuts[i + 1], ny1)
    files = {}
    for key, (x0, y0, x1, y1) in boxes.items():
        a, b = int((x0 - CROP_PAD_MM) * k), int((y0 - CROP_PAD_MM) * k)
        c, d = int((x1 + CROP_PAD_MM) * k), int((y1 + CROP_PAD_MM) * k)
        stack = np.concatenate([big[b:d, a:c], np.full((8, c - a, 3), 255, dtype=np.uint8), master[b:d, a:c]], axis=0)
        img = Image.fromarray(stack)
        if max(img.size) > EYE_IMAGE_EDGE_MAX or img.size[0] * img.size[1] > EYE_PIXELS_MAX:
            raise ValueError('the eye crop %s is %s px: the API would resample it' % (key, img.size))
        path = out / 'crops' / ('eye-%s.png' % key)
        img.save(path, dpi=(CROP_DPI, CROP_DPI))
        files[key] = path
    x0, y0, x1, y1 = 300, 150, 560, 330                   # pick px: the middle bars, their engraving and their edges
    own = pick[y0:y1, x0:x1]
    lanczos = upscale(pick)[y0 * UP:y1 * UP, x0 * UP:x1 * UP]
    back = np.asarray(Image.fromarray(lanczos).resize(own.shape[1::-1], Image.LANCZOS))
    rule = np.full((own.shape[0], 8, 3), 255, dtype=np.uint8)
    top = np.concatenate([own, rule, back], axis=1)
    width = max(top.shape[1], lanczos.shape[1])
    top = np.pad(top, ((0, 0), (0, width - top.shape[1]), (0, 0)), constant_values=255)
    below = np.pad(lanczos, ((0, 0), (0, width - lanczos.shape[1]), (0, 0)), constant_values=255)
    stack = np.concatenate([top, np.full((8, width, 3), 255, dtype=np.uint8), below], axis=0)
    path = out / 'crops' / 'eye-upscale-bars.png'
    Image.fromarray(stack).save(path)
    files['upscale-bars'] = path
    return files


NAME_CROP_DPI = 400.0                  # the plate's own grid (410 PPI): three rows of a name piece fit the API's size
NAME_OUTLINE_RGB = (0, 200, 255)       # the trace drawn over the pick as a cyan hairline (one pixel, 0.064 mm)
NAME_RELOOK_PREFIX = 'lid-master/name-relook'


def name_trace_crops(out, pick, name_ai, name_rings, name_box_mm):
    """The name for the eye, in four pieces at 400 dpi, three rows each: 1 the pick (Lanczos to 400 dpi); 2 the master
    with the name's traced outlines drawn in its gold over the plate (``name_ai``: the foil's own shapes, flat — metal
    cannot be shown flat); 3 the pick with the traced outline over it as a cyan hairline. Returns the files and, per
    piece, how much of the name's own area row 2 changes from row 1 (pixels off by over 40 in a channel) — the
    check, made before anything is paid, that the crops show the trace and not the raster under it."""
    k = NAME_CROP_DPI / MM_PER_INCH
    drawn = _render(name_ai, NAME_CROP_DPI)
    big = cv2.resize(pick, (drawn.shape[1], drawn.shape[0]), interpolation=cv2.INTER_LANCZOS4)
    over = big.copy()
    inside = np.zeros(drawn.shape[:2], dtype=np.uint8)
    for ring in name_rings:
        pts = np.round(flatten(ring, 24) * k * 16 - 8).astype(np.int32)      # px centres, 4 fractional bits
        cv2.polylines(over, [pts], True, NAME_OUTLINE_RGB, 1, cv2.LINE_AA, shift=4)
        one = np.zeros_like(inside)
        cv2.fillPoly(one, [pts], 1, shift=4)
        inside ^= one                                                        # even-odd, as the trace fills
    inside = cv2.dilate(inside, np.ones((5, 5), np.uint8)).astype(bool)
    nx0, ny0, nx1, ny1 = name_box_mm
    cuts = [nx0 + (nx1 - nx0) * i / 4 for i in range(5)]
    files, changed = {}, {}
    for i in range(4):
        a, b = int((cuts[i] - CROP_PAD_MM) * k), int((ny0 - CROP_PAD_MM) * k)
        c, d = int((cuts[i + 1] + CROP_PAD_MM) * k), int((ny1 + CROP_PAD_MM) * k)
        rule = np.full((8, c - a, 3), 255, dtype=np.uint8)
        stack = np.concatenate([big[b:d, a:c], rule, drawn[b:d, a:c], rule, over[b:d, a:c]], axis=0)
        img = Image.fromarray(stack)
        if max(img.size) > EYE_IMAGE_EDGE_MAX or img.size[0] * img.size[1] > EYE_PIXELS_MAX:
            raise ValueError('the name crop %d is %s px: the API would resample it' % (i + 1, img.size))
        key = 'name-trace-%d' % (i + 1)
        path = out / 'crops' / ('eye-%s.png' % key)
        img.save(path, dpi=(NAME_CROP_DPI, NAME_CROP_DPI))
        files[key] = path
        diff = np.abs(big[b:d, a:c].astype(np.int16) - drawn[b:d, a:c].astype(np.int16)).max(axis=2) > 40
        changed[key] = round(float(diff[inside[b:d, a:c]].mean()), 4)
    return files, changed


def name_relook(out, rec, files, changed, call):
    """The eye's look at the traced name, on corrected evidence: rounds 0 and 1 showed it the plate's raster name
    (the master side of its name crops was rendered without the trace) while the facts said it saw outlines. ONE call,
    the four pieces of ``name_trace_crops``; written to fidelity-name-relook.json the moment it returns. Not a repair:
    the master is unchanged. It holds when the eye answered and reads every piece as the same letters, placed as the
    pick places them, nothing invented, every difference allowed."""
    blocks = [_image_block(files['name-trace-%d' % i]) for i in range(1, 5)]
    text = ('FIDELITY GATE, THE NAME (Day 10). The name "Enchanted Rose" in four pieces, left to right (images 1–4), at '
            'print size (400 dpi). In each, three rows divided by white rules: TOP, the pick (the design); MIDDLE, the '
            'master\'s traced vector outlines of the name drawn flat in the sketch\'s gold over the master\'s plate '
            '(these outlines are the gold foil\'s shape; the plate keeps the sketch\'s own painted gold under the foil, '
            'so on the print the foil covers exactly these shapes); BOTTOM, the pick with the traced outline drawn over '
            'it as a thin cyan line. The flat gold in the middle row stands for foil, which no flat picture can show as '
            'metal; judge the SHAPES. Earlier looks were shown the plate\'s painted name, not these outlines. For each '
            'image: are they the same letters (every swash, join and serif), placed as the pick places them, is there '
            'any invented structure (a new or lost stroke, a filled counter, a broken hairline), and is every difference '
            'allowed (name the item 1–7 of the owner\'s list below) or a defect. Answer in JSON.\n\n' + allowed_differences())
    look = call(NAME_RELOOK_PREFIX, [{'type': 'text', 'text': text}] + [b for b, _ in blocks], CROPS_SCHEMA)
    look['sent'] = [dict(i, crop='name-trace-%d' % n, changed_from_the_pick_inside_the_name=changed['name-trace-%d' % n])
                    for n, (_, i) in enumerate(blocks, start=1)]
    answered = look['payload'] is not None
    pieces = []
    if answered:
        pieces = look['payload']['crops']
    holds = bool(answered and len(pieces) == 4 and all(
        c['verdict'] == 'allowed' and c['same_letters'] and c['placed_as_the_pick'] and not c['invented_structure']
        for c in pieces))
    record = {'schema': 'day10_fidelity/1', 'look': 'the name re-looked on corrected evidence (not a repair: the master '
              'is unchanged)', 'why': 'the adversarial review of Day 10 found the master side of rounds 0 and 1\'s name '
              'crops was the plate\'s raster name (the engine page draws the trace only on an invisible foil carrier), '
              'while the facts told the eye it saw outlines', 'name': look, 'answered': answered, 'holds': holds}
    write_json(out / 'fidelity-name-relook.json', record)
    return record


def fidelity_verdict(out, spend):
    """fidelity.json: D-D10-3's verdict over its rounds — round 0, repair 1 (round 1), repair 2 (the upscale's
    four-way look) and the name's re-look on corrected evidence. ``spend``: the eye's calls and dollars from the ledger.
    The gate holds when round 1's gate names no defect, its crops 1–5 and 10's question are answered allowed (10 by
    repair 2) and the name's re-look holds; the name's crops 6–9 of rounds 0 and 1 are kept, set aside as evidence that
    did not show the trace."""
    r0, r1, r2 = (json.loads((out / ('fidelity-r%d.json' % i)).read_text()) for i in (0, 1, 2))
    relook = json.loads((out / 'fidelity-name-relook.json').read_text())

    def diffs(r):
        return [{k: d[k] for k in ('where', 'verdict', 'allowed_by', 'severity')} for d in r['gate']['payload']['differences']]

    def crop_rows(r):
        return [{k: c[k] for k in ('image', 'verdict', 'allowed_by', 'invented_structure')} for c in r['crops']['payload']['crops']]
    r1_crops = r1['crops']['payload']['crops']
    holds = bool(r1['gate']['payload'] and not [d for d in r1['gate']['payload']['differences'] if d['verdict'] == 'defect']
                 and all(c['verdict'] == 'allowed' for c in r1_crops if c['image'] <= 5) and r2['holds'] and relook['holds'])
    said = 'the master reads as the pick; every difference the eye sees is one the owner allowed'
    if not relook['holds']:
        said = ('the gate does not hold on the name: shown the traced outlines, the eye does not read every piece as the '
                'pick\'s letters, placed as the pick places them (fidelity-name-relook.json); no repair is left (D-D10-3)')
    return {
        'schema': 'day10_fidelity_verdict/2', 'pick': rel(PICK),
        'rule': 'D-D10-3: the designer\'s eye compares the master and its finish proof with the pick, given D-D10-2\'s '
                'allowed differences, and classifies every difference it sees; a defect is repaired at most twice, then '
                'reported',
        'rounds': [
            {'round': 0, 'file': 'fidelity-r0.json', 'reads_as_the_pick': r0['gate']['payload']['reads_as_the_pick'],
             'differences': diffs(r0), 'crops': crop_rows(r0),
             'defects': ['minor: the space between "27" and "g" reads tighter than the sketch (Nunito\'s 7 is 0.22 mm '
                         'wider; the ink gap 1.48 mm against 1.67)',
                         'image 10, the upscale: "invented structure" read in the 2× bars against the pick\'s pixels '
                         'repeated']},
            {'round': 1, 'file': 'fidelity-r1.json', 'repair': 'repair 1: the sketch\'s word spaces kept (a run moves by '
             'the difference where a drawn word space is off by more than 0.15 mm: "27" by −0.186 mm, "EYESHADOW" by '
             '−0.186 mm); the upscale crop shown fairly (the pick at its own pixels, the plate brought back to that size, '
             'and the plate at 2×)', 'reads_as_the_pick': r1['gate']['payload']['reads_as_the_pick'],
             'differences': diffs(r1), 'crops': crop_rows(r1),
             'defects': ['image 10 only: kinked and merged rib lines in the 2× plate read as a super-resolution model\'s '
                         'invention']},
            {'round': 2, 'file': 'fidelity-r2.json', 'repair': 'repair 2: the evidence, not the master — the piece of the '
             'bars where the eye saw kinks shown four ways at one scale (the pick\'s own pixels repeated, the plate by '
             'Lanczos 8 × 8, Lanczos 6 × 6, bicubic); the master unchanged', 'answer': r2['upscale']['payload']},
            {'look': 'the name re-looked', 'file': 'fidelity-name-relook.json', 'why': relook['why'],
             'answer': relook['name']['payload'], 'holds': relook['holds']}],
        'set_aside': {'what': 'rounds 0 and 1, crops 6–9 (the name) and the gate\'s reading of the name in the flat',
                      'why': 'their master side was the plate\'s raster name (pick against master inside the name: 0 % '
                             'of pixels off by over 40), so "clean, smoothed outlines … coincide with the pick" described '
                             'the facts the eye was told, not a trace it saw; the re-look replaces them'},
        'measured_beside_the_eye': {'upscale_bars_crop': 'the engraving\'s dominant pitch 3.347 pick px and direction '
                                    '(wave vector 114.3°) the same in the pick, the plate and the pixels repeated; the '
                                    'plate brought back to the pick\'s size: SSIM 0.994, mean ΔE00 0.78 on that crop'},
        'verdict': {'holds': holds, 'repairs_used': 2, 'name_relook_holds': relook['holds'],
                    'master_changed_by': 'repair 1 (the word spaces); repair 2 and the re-look changed nothing in the master',
                    'said': said},
        'spend': dict(spend, limit_usd=2.00, prefix=EYE_PREFIX)}


def master_facts(rec):
    """What the eye cannot see in a picture, said as facts: which parts are foil and which ink, the relief (none on
    Day 10; [Day 11] the bars' blind emboss), the bleed outside the flat, the faces' names. No verdicts."""
    faces = rec['type']['faces']
    relief = 'No relief.'
    if 'relief_mask' in rec['finishes']:
        # the outline as the record says it: the isoline, and the two outer edges where it is the edge line + 0.25 mm
        relief = ('Blind emboss: the five bars — the owner\'s recorded override of item 5 of the owner\'s list above (D-D11-5.1 '
                  'overrides D-D10-2.5: the bars are embossed though A-2\'s spec declared no relief there), so the emboss '
                  'itself is allowed: judge its outline, not its presence; the painted light still prints as raster '
                  'exactly as painted. %s The oval\'s glow is not embossed.'
                  % rec['finishes']['relief_mask']['outline_said'])
    return ('WHAT THE PICTURES CANNOT SHOW. Gold foil: the name\'s outlines and the logo\'s letters B B R S E. Ink: '
            'everything else, the logo\'s rose emblem and ® included. %s The flat is trimmed; the 3 mm bleed lies '
            'outside it. The small lines are live text: EYESHADOW PALETTE in %s, 18 SHADES in %s, 27 g ℮ 0.95 oz in %s, '
            'the Arabic in %s; the ℮ is a drawn sign.' % (relief, faces['descriptor_en']['label'], faces['shades']['label'],
                                                         faces['net']['label'], faces['descriptor_ar']['label']))


def make_eye_call(*, cap_usd, client, prefix=EYE_PREFIX):
    """ONE Claude vision call (the jury's model, effort high, a JSON schema), through the ledger under ``prefix`` (Day 10's
    designer's eye by default; Day 11 passes its own). Returns the record."""
    from apps.pipeline.services import jury
    from apps.pipeline.services.spend_reservation import paid_operation

    def call(operation, content, schema):
        api = client
        if api is None:
            api = jury._client()
        model = jury.jury_model()
        response = paid_operation(api.messages.create, provider='anthropic', operation=prefix + operation,
                                  reservation_prefix=prefix, reservation_cap=cap_usd, model=model,
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


def _image_block(path):
    """An image as the call sends it, refused when the API would resample it (over 1568 px a side or ~1.15 MP)."""
    import base64
    data = Path(path).read_bytes()
    with Image.open(path) as im:
        size = im.size
    if max(size) > EYE_IMAGE_EDGE_MAX or size[0] * size[1] > EYE_PIXELS_MAX:
        raise ValueError('%s is %s px: the API would resample it' % (path, size))
    return ({'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': base64.b64encode(data).decode()}},
            {'path': rel(path), 'sha256': hashlib.sha256(data).hexdigest(), 'px': list(size)})


def gate_images(out):
    """The gate's three pictures at the size the model sees them (fitted under 1.15 MP by Lanczos, the same size for
    all three): the pick, the master's flat, its finish proof."""
    sources = {'pick': PICK, 'master': out / 'engine' / 'flat-1536.png', 'proof': out / 'finish-proof.png'}
    k = (EYE_PIXELS_MAX / (PICK_PX[0] * PICK_PX[1])) ** 0.5
    size = (int(PICK_PX[0] * k), int(PICK_PX[1] * k))
    made = {}
    for name, src in sources.items():
        path = out / 'crops' / ('eye-gate-%s.png' % name)
        Image.open(src).convert('RGB').resize(size, Image.LANCZOS).save(path)
        made[name] = path
    return made


def fidelity_look(out, rec, sketch, call, round_no):
    """D-D10-3, one round: the gate (the pick, the master's flat and its finish proof) and the 1 : 1 crops, each
    difference classified allowed or a defect; the round holds when both looks answered and neither names a defect.
    Every picture is made and checked before anything is paid; each look is written the moment it returns."""
    allowed = allowed_differences()
    facts = master_facts(rec)
    gate_files = gate_images(out)
    crop_files = eye_crops(out, load_pick(PICK), out / 'engine' / 'lid-engine.ai', sketch, rec)
    gate_blocks = [_image_block(gate_files[k]) for k in ('pick', 'master', 'proof')]
    crop_blocks = [_image_block(crop_files[k]) for k in EYE_CROPS]
    gate_text = ('FIDELITY GATE (Day 10, D-D10-3). The owner picked a sketch; the master must be that sketch made printable, '
                 'nothing redrawn. Image 1 is THE PICK (the design). Image 2 is THE MASTER\'s flat print artwork (the '
                 'trimmed lid, 190 × 120 mm). Image 3 is THE MASTER\'s FINISH PROOF (its foil rendered as metal from the '
                 'plates). Compare the master with the pick as a senior packaging designer and list EVERY difference you '
                 'see — composition, light, colour, texture, the bars and their engraving, every line of type, the name, '
                 'the logo, the finishes. Classify each as "allowed" (name the item of the owner\'s list below that '
                 'covers it, 1–7) or "defect" (anything the list does not allow). Severity: blocking (the master is not '
                 'the pick), major, minor. For a defect, say the smallest repair. Answer in JSON.\n\n' + allowed +
                 '\n\n' + facts)
    crop_text = ('FIDELITY GATE, 1 : 1 CROPS (Day 10). Images 1–9 are crops at print size (600 dpi): in each, THE PICK is '
                 'above the white rule and THE MASTER below. 1 EYESHADOW PALETTE, 2 the Arabic line, 3 18 SHADES, '
                 '4 27 g ℮ 0.95 oz, 5 the logo, 6–9 the name in four pieces, left to right. Image 10 is the UPSCALE, a piece of '
                 'the bars: top left, the pick at its own pixels; top right, the master\'s plate brought back to the pick\'s '
                 'size; below, the master\'s plate at its own pixels (2×, what prints). For each image: are they the same '
                 'letters, placed as the pick places them, is there any invented structure (new lines, letters, shapes), '
                 'and is every difference allowed (name the item 1–7 of the owner\'s list below) or a defect. Answer in '
                 'JSON.\n\n' + allowed + '\n\n' + facts)
    record = {'schema': 'day10_fidelity/1', 'round': round_no,
              'decided': 'in code: the round holds when both looks answered and neither names a defect'}
    gate = call('lid-master/r%d/gate' % round_no, [{'type': 'text', 'text': gate_text}] + [b for b, _ in gate_blocks],
                FIDELITY_SCHEMA)
    gate['sent'] = [i for _, i in gate_blocks]
    record['gate'] = gate
    write_json(out / ('fidelity-r%d.json' % round_no), record)
    crops_look = call('lid-master/r%d/crops' % round_no, [{'type': 'text', 'text': crop_text}] + [b for b, _ in crop_blocks],
                      CROPS_SCHEMA)
    crops_look['sent'] = [dict(i, crop=k) for (_, i), k in zip(crop_blocks, EYE_CROPS)]
    record['crops'] = crops_look
    defects = []
    if gate['payload'] is not None:
        defects += [d for d in gate['payload']['differences'] if d['verdict'] == 'defect']
    if crops_look['payload'] is not None:
        defects += [dict(c, where=EYE_CROPS[c['image'] - 1]) for c in crops_look['payload']['crops']
                    if c['verdict'] == 'defect' and 1 <= c['image'] <= len(EYE_CROPS)]
    record['answered'] = gate['payload'] is not None and crops_look['payload'] is not None
    record['defects'] = defects
    record['holds'] = bool(record['answered'] and not defects)
    write_json(out / ('fidelity-r%d.json' % round_no), record)
    return record


def arabic_faithfulness(out):
    """The house's own test of a derived Arabic face (``arabic_display.measure`` / ``faithful``) run on Tajawal PF
    Medium: on the lid's descriptor and on the six further lines. The lid sets only its descriptor."""
    from apps.ire import arabic_display
    candidate = {'key': 'tajawal-500', 'family': 'Tajawal', 'stem': ARABIC_SOURCE_STEM, 'weight': ARABIC_WEIGHT}
    with tempfile.TemporaryDirectory() as tmp:
        row = arabic_display.measure(candidate, work_dir=tmp)
    verdict = arabic_display.faithful(row)
    return {'faithful_as_a_face': verdict['faithful'], 'tests': verdict['tests'],
            'descriptor': {'iou': row['emitter_way']['iou'], 'components': row['emitter_way']['components'],
                           'joins_worst_dy_em': row['joins']['worst_dy_em'], 'context_share': row['context']['share']},
            'further_lines': [{'line': x['line'], 'iou': x['iou'], 'worst_drift_units': x['worst_drift_units']}
                              for x in row['further_lines']['lines']],
            'said': 'the lid\'s own line (the descriptor) is drawn as the face shapes it (IoU %.4f, every component, no '
                    'join moved); as a face for any text it is not faithful by the house\'s test — a further line reads '
                    'under 0.95 where the face\'s kerning (GPOS) is not applied — so it is not reused for other Arabic '
                    'text (the sticker) without its own per-line proof' % row['emitter_way']['iou']}


READ_BACK_DPI = 300.0
LAYER_ON, LAYER_OFF = 0, 2             # PyMuPDF's layer UI actions: set on, set off
READ_BACK_MEAN_MAX = 1.0           # the shown artwork is the master within rendering noise: mean ΔE00 under 1 …
READ_BACK_P99_MAX = 3.0            # … and its 99th percentile under 3 (glyph edges anti-aliased through a form differ)
READ_BACK_ELEMENT_PAD_MM = 0.5
READ_BACK_INK_DE = 10.0            # a pixel is an element's ink where it stands over ΔE00 10 from the picture alone
READ_BACK_INK_KEPT_MIN = 0.9       # an element reads back when 90 % of its ink in the master is ink in the file too
READ_BACK_PICTURE_SHARE_MAX = 0.05  # an element with no ink over the picture (the name, in the plate) reads back when
                                   # under 5 % of its box differs by over ΔE00 10


def element_read_back(master, art, picture, boxes_mm, dpi):
    """Each element read back in its own ink box (± 0.5 mm): of the pixels it inks in the master (over ΔE00 10 from
    ``picture``, the picture layer alone; its core, one pixel in from its anti-aliased edge), the share the file's
    shown artwork inks too. A page-wide mean cannot see
    one small line missing (the review of Day 10: each covers under 1 % of the page); its own ink can. An element
    with no ink over the picture is read on the picture itself."""
    k = dpi / MM_PER_INCH
    rows = []
    for name, (x0, y0, x1, y1) in boxes_mm.items():
        a, b = int((x0 - READ_BACK_ELEMENT_PAD_MM) * k), int((y0 - READ_BACK_ELEMENT_PAD_MM) * k)
        c, d = int(np.ceil((x1 + READ_BACK_ELEMENT_PAD_MM) * k)), int(np.ceil((y1 + READ_BACK_ELEMENT_PAD_MM) * k))
        base = srgb_to_lab(picture[b:d, a:c])
        ink = delta_e00(srgb_to_lab(master[b:d, a:c]), base) > READ_BACK_INK_DE
        ink = cv2.erode(ink.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
        shown = delta_e00(srgb_to_lab(art[b:d, a:c]), base) > READ_BACK_INK_DE
        row = {'element': name, 'box_mm': [round(v, 2) for v in (x0, y0, x1, y1)], 'ink_px': int(ink.sum())}
        if ink.sum():
            kept = float((ink & shown).sum() / ink.sum())
            row.update(ink_kept=round(kept, 4), holds=bool(kept >= READ_BACK_INK_KEPT_MIN))
        else:
            share = float((delta_e00(srgb_to_lab(master[b:d, a:c]), srgb_to_lab(art[b:d, a:c])) > READ_BACK_INK_DE).mean())
            row.update(picture_share_over_10=round(share, 4), holds=bool(share < READ_BACK_PICTURE_SHARE_MAX))
        rows.append(row)
    return rows


def read_back_ai(path, engine_ai, elements, empty=('relief',)):
    """The layered .ai read back (MuPDF, layers switched through the file's own layer UI): its layers by name and
    default state, what each inks alone (its share of the trimmed page's pixels off white), the artwork as shown by
    default (guides off) against the engine's own page 1, both rendered the same way at 300 dpi (ΔE00) — the page as a
    whole and each element (``elements``: name → ink box, mm) in its own box — and the words the file carries
    (ActualText), every line's. An empty layer, a missing element or word, or a shown page that is not the master, is
    said. ``empty`` names the layers that are meant to be empty (Day 10: the relief; [Day 11] none, the bars' emboss
    on it)."""
    import fitz

    def render(doc, on):
        if on is not None:
            for item in doc.layer_ui_configs():
                action = LAYER_OFF
                if item['text'] in on:
                    action = LAYER_ON
                doc.set_layer_ui_config(item['number'], action=action)
        page = doc[0]
        pix = page.get_pixmap(dpi=int(READ_BACK_DPI), clip=page.trimbox, alpha=False)
        return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[..., :3].copy()

    rows = []
    with fitz.open(str(path)) as doc:
        layers = [(item['text'], bool(item['on'])) for item in doc.layer_ui_configs()]
        for name, shown in layers:
            arr = render(doc, {name})
            rows.append({'layer': name, 'shown_by_default': shown,
                         'inks_share': round(float((arr.min(axis=2) < 250).mean()), 5)})
        art = render(doc, {name for name, shown in layers if shown and name != 'guides'})
        picture = render(doc, {'picture'})
    with fitz.open(str(engine_ai)) as doc:
        master = render(doc, None)
    h, w = min(art.shape[0], master.shape[0]), min(art.shape[1], master.shape[1])
    de = delta_e00(srgb_to_lab(master[:h, :w]), srgb_to_lab(art[:h, :w]))
    mean, p99 = float(de.mean()), float(np.percentile(de, 99))
    page = {'dpi': READ_BACK_DPI, 'de00_mean': round(mean, 3), 'de00_p99': round(p99, 3),
            'de00_max': round(float(de.max()), 2), 'share_over_10': round(float((de > 10).mean()), 5),
            'over_10_is': 'glyph and logo edges, anti-aliased through a form',
            'holds': bool(mean < READ_BACK_MEAN_MAX and p99 < READ_BACK_P99_MAX)}
    by_element = element_read_back(master[:h, :w], art[:h, :w], picture[:h, :w], elements, READ_BACK_DPI)
    joined = ' ' + ' '.join(_norm(t) for t in actual_texts(path, 0)) + ' '
    words = {key: ' %s ' % _norm(LINES[key]['copy']) in joined for key in LINES}
    words['name'] = ' Enchanted Rose ' in joined
    empty_found = [r['layer'] for r in rows if r['inks_share'] == 0.0]
    return {'layers': rows,
            'shown_artwork_vs_engine_page': page,
            'by_element': by_element,
            'words_carried': words,
            'holds': bool(page['holds'] and all(r['holds'] for r in by_element) and all(words.values())
                          and empty_found == list(empty)),
            'empty_layers': empty_found,
            'illustrator': 'not read back in Illustrator: its scripting dictionary on this machine has no "do '
                           'javascript" (sdef finds none; AppleScript -2741, JXA -1708), so neither the house\'s native '
                           'layered build (native_ai) nor an Illustrator read-back could run; the layers are PDF '
                           'optional-content groups, read back here by MuPDF'}


UPSCALE_LOOK_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['in_the_picks_own_pixels', 'invented_structure', 'verdict', 'allowed_by', 'notes'],
    'properties': {'in_the_picks_own_pixels': {'type': 'boolean'}, 'invented_structure': {'type': 'boolean'},
                   'verdict': {'type': 'string', 'enum': ['allowed', 'defect']},
                   'allowed_by': {'type': 'string', 'enum': ['1', '2', '3', '4', '5', '6', '7', 'none']},
                   'notes': {'type': 'string'}}}


def upscale_comparison(out):
    """The bars where the eye saw kinks, one piece shown four ways at the same scale (each 3× for the eye): the pick's
    own pixels repeated, the master's plate (Lanczos, OpenCV's 8 × 8 kernel), Lanczos with PIL's 6 × 6 kernel, and
    bicubic — so what the plate shows can be read against what the pick's pixels already hold."""
    pick = load_pick(PICK)
    h, w = pick.shape[:2]
    x0, y0, x1, y1 = 430, 150, 560, 230
    own = cv2.resize(pick[y0:y1, x0:x1], None, fx=UP, fy=UP, interpolation=cv2.INTER_NEAREST)
    l4 = upscale(pick)[y0 * UP:y1 * UP, x0 * UP:x1 * UP]
    l3 = np.asarray(Image.fromarray(pick).resize((w * UP, h * UP), Image.LANCZOS))[y0 * UP:y1 * UP, x0 * UP:x1 * UP]
    bc = cv2.resize(pick, (w * UP, h * UP), interpolation=cv2.INTER_CUBIC)[y0 * UP:y1 * UP, x0 * UP:x1 * UP]
    panels = [cv2.resize(a, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_NEAREST) for a in (own, l4, l3, bc)]
    rule = np.full((6, panels[0].shape[1], 3), 255, dtype=np.uint8)
    path = out / 'crops' / 'eye-upscale-four-ways.png'
    Image.fromarray(np.concatenate([panels[0], rule, panels[1], rule, panels[2], rule, panels[3]], axis=0)).save(path)
    return path


def upscale_look(out, call, round_no):
    """Repair 2 of the upscale defect (D-D10-3): the eye shown the four-way comparison, asked whether the kinks it read
    in the plate are in the pick's own pixels. Written to fidelity-r<round>.json."""
    block, info = _image_block(upscale_comparison(out))
    text = ('FIDELITY GATE, THE UPSCALE (Day 10). In the last look you read kinked, merged and wavy rib lines in the '
            'master\'s 2× plate (the upper bar, right of centre) as invented structure. This image is that piece of the '
            'bars four ways, at one scale, top to bottom: 1 the pick\'s own pixels, each repeated (no interpolation); '
            '2 the master\'s plate: the pick enlarged 2× by Lanczos (OpenCV, 8 × 8 kernel), exactly what prints; 3 the '
            'same enlargement by PIL\'s Lanczos (6 × 6 kernel); 4 by bicubic. Are the kinks, merges and waves you saw '
            'present in the pick\'s own pixels (1)? Does the plate (2) show any line, letter or shape that (1) does not '
            'hold? Classify the plate\'s difference from the pick as allowed (name the item of the owner\'s list) or a '
            'defect. Answer in JSON.\\n\\n' + allowed_differences())
    look = call('lid-master/r%d/upscale' % round_no, [{'type': 'text', 'text': text}, block], UPSCALE_LOOK_SCHEMA)
    look['sent'] = [info]
    record = {'schema': 'day10_fidelity/1', 'round': round_no, 'upscale': look,
              'holds': bool(look['payload'] is not None and look['payload']['verdict'] == 'allowed')}
    write_json(out / ('fidelity-r%d.json' % round_no), record)
    return record
