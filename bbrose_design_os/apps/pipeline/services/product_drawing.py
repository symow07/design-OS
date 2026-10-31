"""D-D12-1.4 — the product drawing: our own code draws a closed round stick (the lipstick, the balm) from its flat wraps,
so a wrap can be judged as the product it closes round. A front view and a three-quarter view of body and cap, an
orthographic projection of a cylinder, flat (the wrap's own pixels, no shading added: its finish proof's foil and emboss
are the only light), no scene; deterministic (the same wraps give the same pixels). Labelled "drawing, not a render" on
the sheet; never the contract, never sent to an image model (D-D12-1.4).

A point of the wrap at x mm (along its width; its right end over its left start) and y mm (down from its top trim)
lies on the case at the angle θ = (x − the front centre) / r and the height of its band; seen from the front (rotated
by φ about the axis, from e above it) a surface point at θ and height z falls at screen (r sin(θ − φ), z cos e −
r cos(θ − φ) sin e), and only its near half (cos(θ − φ) ≥ 0) is seen."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[4]                 # the repository (as lid_master.REPO, which this drew on)
PX_PER_MM = 12.0                          # the drawing's scale on its sheet
THREE_QUARTER_TURN_DEG = 45.0             # the three-quarter view: turned 45° about the axis …
THREE_QUARTER_ABOVE_DEG = 15.0            # … and seen from 15° above (the top a flat ellipse in the cap's ground)
MARGIN_MM = 8.0
GAP_MM = 14.0
CAPTION_PT_PX = 22
LABEL = 'drawing, not a render'
FONT = Path(__file__).resolve().parents[3] / 'static' / 'fonts' / 'brand2026' / 'Poppins' / 'Poppins-Regular.ttf'
EDGE_INK = (40, 40, 48)                   # the silhouette's thin outline (a drawing's line, not a shade)
SHEET = (255, 255, 255)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rel(path):
    """A record's path: repo-relative where it lies in the repo, else as given (a test's folder)."""
    resolved = Path(path).resolve()
    return str(resolved.relative_to(REPO)) if resolved.is_relative_to(REPO) else str(path)


def band_texture(path, wrap_mm, bleed_mm):
    """A wrap's picture (its finish proof or flat at the wrap's own size) without its top and bottom bleed: the band
    the case shows, and its px/mm."""
    im = np.asarray(Image.open(path).convert('RGB'))
    k = im.shape[1] / wrap_mm[0]
    top = int(round(bleed_mm * k))
    bottom = im.shape[0] - top
    return im[top:bottom], k


def view(bands, d_mm, front_centre_mm, overlap_mm, turn_deg, above_deg, top_rgb):
    """One orthographic view of the closed stick: ``bands`` from the bottom up, each (texture, k, height_mm); the case Ø
    ``d_mm``; the wrap's front centre and its overlap (mm); turned ``turn_deg`` about the axis, seen ``above_deg`` from
    above. Returns an RGBA picture at PX_PER_MM (transparent outside the case)."""
    r = d_mm / 2.0
    total = sum(h for _, _, h in bands)
    e = np.radians(above_deg)
    phi = np.radians(turn_deg)
    circ = np.pi * d_mm
    s = PX_PER_MM
    w_px = int(np.ceil(d_mm * s)) + 2
    h_mm = total * np.cos(e) + 2 * r * np.sin(e)
    h_px = int(np.ceil(h_mm * s)) + 2
    out = np.zeros((h_px, w_px, 4), np.uint8)
    xs = (np.arange(w_px) + 0.5) / s - r - 1.0 / s
    ys = (np.arange(h_px) + 0.5) / s - 1.0 / s
    X, Y = np.meshgrid(xs, ys)
    inside = np.abs(X) <= r
    a = np.arcsin(np.clip(X / r, -1, 1))                       # θ − φ on the near half
    depth = r * np.cos(a)
    # screen y down from the top (the far rim of the top at 0): a nearer point at the same height falls lower when seen
    # from above — screen up = z cos e − depth sin e; z up from the base
    z = (r * np.sin(e) + total * np.cos(e) - Y + depth * np.sin(e)) / np.cos(e)
    on = inside & (z >= 0) & (z < total)
    theta = a + phi
    x_wrap = front_centre_mm + r * theta
    x_wrap = overlap_mm + np.mod(x_wrap - overlap_mm, circ)
    rgb = np.zeros((h_px, w_px, 3), np.float32)
    base = 0.0
    for tex, k, h in bands:
        sel = on & (z >= base) & (z < base + h)
        u = (x_wrap * k - 0.5).astype(np.float32)
        v = ((base + h - z) * k - 0.5).astype(np.float32)        # the band's top at its own y = 0
        sampled = cv2.remap(tex.astype(np.float32), u, v, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        rgb[sel] = sampled[sel]
        base += h
    out[..., :3] = np.clip(np.round(rgb), 0, 255).astype(np.uint8)
    out[..., 3] = (on * 255).astype(np.uint8)
    if above_deg > 0:
        # the top face: an ellipse at the stick's top, flat in the cap's ground colour (no artwork is drawn on it)
        cy = r * np.sin(e)
        top = ((X / r) ** 2 + ((Y - cy) / (r * np.sin(e))) ** 2) <= 1.0
        out[top, :3] = top_rgb
        out[top, 3] = 255
    return out


def square_view(bands, side_mm, turn_deg, above_deg, top_rgb):
    """One orthographic view of a closed product of square section (a bottle, a cap), as ``view`` draws the round one:
    ``bands`` from the bottom up, each (texture, k, height_mm), the texture a wrap of the four faces from the front's
    left edge (front, right, back, left, each ``side_mm`` wide); turned ``turn_deg`` (0 ≤ turn < 90) about the axis so
    the right face comes toward the viewer, seen ``above_deg`` from above. Flat (the faces' own pixels, no shading); a
    face's point at t along it (from its left edge as seen from outside) lies at wrap x = its offset + t."""
    if not 0 <= turn_deg < 90:
        raise ValueError('a square view turns the right face toward the viewer: 0 ≤ turn < 90')
    a, h = side_mm, side_mm / 2.0
    total = sum(hh for _, _, hh in bands)
    e, phi = np.radians(above_deg), np.radians(turn_deg)
    c, sn = np.cos(phi), np.sin(phi)
    reach = h * (c + sn)                                       # the half width on screen and the deepest corner
    s = PX_PER_MM
    w_px = int(np.ceil(2 * reach * s)) + 2
    h_px = int(np.ceil((total * np.cos(e) + 2 * reach * np.sin(e)) * s)) + 2
    xs = (np.arange(w_px) + 0.5) / s - reach - 1.0 / s
    ys = (np.arange(h_px) + 0.5) / s - 1.0 / s
    X, Y = np.meshgrid(xs, ys)
    out = np.zeros((h_px, w_px, 4), np.uint8)
    rgb = np.zeros((h_px, w_px, 3), np.float32)
    seen = np.zeros((h_px, w_px), bool)
    # the front face: (t − h, h) turned → x = (t − h) c − h sn, depth = (t − h) sn + h c; the right face: (h, h − t) turned
    faces = [(c, lambda x: (x + h * sn) / c + h, lambda t: (t - h) * sn + h * c, 0.0)]
    if sn > 1e-9:
        faces.append((sn, lambda x: (x - h * c) / sn + h, lambda t: h * sn + (h - t) * c, a))
    for facing, t_of, depth_of, offset in faces:
        t = t_of(X)
        depth = depth_of(t)
        z = (reach * np.sin(e) + total * np.cos(e) - Y + depth * np.sin(e)) / np.cos(e)
        on = (t >= 0) & (t < a) & (z >= 0) & (z < total) & ~seen
        base = 0.0
        for tex, k, hh in bands:
            sel = on & (z >= base) & (z < base + hh)
            u = ((offset + t) * k - 0.5).astype(np.float32)
            v = ((base + hh - z) * k - 0.5).astype(np.float32)
            sampled = cv2.remap(tex.astype(np.float32), u, v, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            rgb[sel] = sampled[sel]
            base += hh
        seen |= on
    out[..., :3] = np.clip(np.round(rgb), 0, 255).astype(np.uint8)
    out[..., 3] = (seen * 255).astype(np.uint8)
    if above_deg > 0:
        # the top face: the square at the product's top, flat in the cap's ground colour (no artwork drawn on it)
        depth = Y / np.sin(e) - reach                           # Y = (reach + depth) sin e at the top
        u_, v_ = X * c + depth * sn, -X * sn + depth * c
        top = (np.abs(u_) <= h) & (np.abs(v_) <= h)
        out[top, :3] = top_rgb
        out[top, 3] = 255
    return out


def outline(img_rgba):
    """The silhouette's thin outline (one px), drawn over the view."""
    alpha = img_rgba[..., 3] > 0
    edge = alpha & ~cv2.erode(alpha.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    out = img_rgba.copy()
    out[edge, :3] = EDGE_INK
    return out


def draw(product, bands_spec, d_mm, front_centre_mm, overlap_mm, top_hex, dest_png, section='circle'):
    """The sheet: the front view and the three-quarter view side by side on white, each captioned, the sheet labelled
    "drawing, not a render". ``bands_spec``: from the bottom up, (name, picture path, wrap (w, h) mm, bleed mm,
    visible height mm). Writes ``dest_png`` and returns its record (inputs' sha256, parameters, the output's sha256).
    ``section`` 'square': ``d_mm`` is the side, each wrap the four faces from the front's left edge (square_view)."""
    bands = []
    for name, path, wrap_mm, bleed, height in bands_spec:
        tex, k = band_texture(path, wrap_mm, bleed)
        bands.append((tex, k, height))
    top_rgb = tuple(int(top_hex.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))
    if section == 'square':
        front = outline(square_view(bands, d_mm, 0.0, 0.0, top_rgb))
        three = outline(square_view(bands, d_mm, THREE_QUARTER_TURN_DEG, THREE_QUARTER_ABOVE_DEG, top_rgb))
    else:
        front = outline(view(bands, d_mm, front_centre_mm, overlap_mm, 0.0, 0.0, top_rgb))
        three = outline(view(bands, d_mm, front_centre_mm, overlap_mm, THREE_QUARTER_TURN_DEG, THREE_QUARTER_ABOVE_DEG,
                             top_rgb))
    s = PX_PER_MM
    m = int(MARGIN_MM * s)
    g = int(GAP_MM * s)
    font = ImageFont.truetype(str(FONT), CAPTION_PT_PX)
    words = ['front', 'three-quarter (%d°, %d° above)' % (THREE_QUARTER_TURN_DEG, THREE_QUARTER_ABOVE_DEG),
             '%s — %s' % (product, LABEL), ('%g mm square' if section == 'square' else 'Ø %g mm') % d_mm +
             ', %g mm closed' % sum(b[4] for b in bands_spec)]
    width = lambda t: int(np.ceil(font.getlength(t)))
    cap_h = 3 * (CAPTION_PT_PX + 8) + 20
    h = max(front.shape[0], three.shape[0])
    sheet_w = max(m + front.shape[1] + g + max(three.shape[1], width(words[1])) + m, m + width(words[2]) + m,
                  m + width(words[3]) + m)
    sheet = Image.new('RGB', (sheet_w, m + h + cap_h + m), SHEET)
    sheet.paste(Image.fromarray(front, 'RGBA'), (m, m + h - front.shape[0]), Image.fromarray(front, 'RGBA'))
    sheet.paste(Image.fromarray(three, 'RGBA'), (m + front.shape[1] + g, m + h - three.shape[0]), Image.fromarray(three, 'RGBA'))
    d = ImageDraw.Draw(sheet)
    y = m + h + 12
    d.text((m, y), words[0], fill=(30, 30, 30), font=font)
    d.text((m + front.shape[1] + g, y), words[1], fill=(30, 30, 30), font=font)
    d.text((m, y + CAPTION_PT_PX + 8), words[2], fill=(30, 30, 30), font=font)
    d.text((m, y + 2 * (CAPTION_PT_PX + 8)), words[3], fill=(30, 30, 30), font=font)
    sheet.save(dest_png, optimize=False)
    record = {'schema': 'product_drawing/1', 'product': product, 'label': LABEL, 'rule': 'D-D12-1.4',
            'method': 'orthographic projection of a cylinder: each wrap band sampled at the angle its width wraps to, '
                      'flat (no shading added), the near half seen; the three-quarter view turned 45° and seen 15° '
                      'above with the top a flat ellipse in the cap\'s ground', 'px_per_mm': PX_PER_MM,
            'case_d_mm': d_mm, 'front_centre_mm': front_centre_mm, 'overlap_mm': round(overlap_mm, 4),
            'bands': [{'band': name, 'picture': _rel(path), 'sha256': sha256(path), 'visible_mm': height}
                      for name, path, _, _, height in bands_spec],
            'top_face': top_hex, 'file': _rel(dest_png), 'sha256': sha256(dest_png),
            'never': 'the contract, or an image model\'s input (D-D12-1.4)'}
    if section == 'square':
        record.update(section='square', side_mm=d_mm, method='orthographic projection of a square prism: each face '
                      'sampled from its wrap, flat (no shading added), the faces toward the viewer seen; the '
                      'three-quarter view turned 45° and seen 15° above with the top a flat square in the cap\'s ground')
    return record


