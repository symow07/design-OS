"""Deterministic perceptual hashing (DIP-0C2c) — NumPy + Pillow, no new deps.

Three 64-bit hashes per image:

* **dHash** — 9×8 grayscale horizontal gradient. Robust to rescaling and
  recompression, sensitive to structure.
* **pHash** — 32×32 grayscale → DCT-II → top-left 8×8 (DC excluded) → median
  threshold. The DCT is a plain NumPy cosine-basis matmul; SciPy is neither
  available nor needed.
* **shape hash** — the same dHash over the **alpha silhouette**, so the *same*
  logo composited on white and on black is still recognisable as one artwork
  (RGB hashes alone would call them unrelated).

Every image is hashed under five transforms (identity, mirror, 90°, 180°, 270°),
so a flipped or rotated variant is *found* — but a match that holds only under a
transform is reported as explicit `MIRRORED` / `ROTATED` evidence by the caller,
never as a silent near-duplicate.

**Information content overrides hash distance.** A blank, uniform or mostly
transparent image produces hashes that collide with every other blank image. Such
images are marked weak evidence and their confidence is capped, so they can never
reach "strong near-duplicate" no matter how small the Hamming distance is.
"""
from __future__ import annotations

import hashlib

import numpy as np

from . import config as C

PARSER = f"{C.TOOL_NAME}.phash/{C.TOOL_VERSION}"
ALGORITHM_VERSION = "dhash9x8+phash32x8+shape/1.0"

DHASH_W, DHASH_H = 9, 8
PHASH_SIZE, PHASH_KEEP = 32, 8
ALPHA_BACKGROUND = (255, 255, 255)     # alpha is composited onto WHITE, recorded
ORIENTATION_POLICY = ("no auto-rotation; the image is hashed as stored and under "
                      "each transform separately, and a transform-only match is "
                      "reported as explicit evidence")

CONFIG = {
    "algorithm_version": ALGORITHM_VERSION,
    "dhash": [DHASH_W, DHASH_H],
    "phash_size": PHASH_SIZE,
    "phash_keep": PHASH_KEEP,
    "alpha_background": list(ALPHA_BACKGROUND),
    "orientation_policy": ORIENTATION_POLICY,
    "hamming_strong": C.HAMMING_STRONG,
    "hamming_review": C.HAMMING_REVIEW,
    "info_min_std": C.INFO_MIN_STD,
    "info_min_alpha_coverage": C.INFO_MIN_ALPHA_COVERAGE,
    "info_min_entropy": C.INFO_MIN_ENTROPY,
    "transforms": list(C.TRANSFORMS),
}
CONFIG_FP = hashlib.sha256(
    repr(sorted(CONFIG.items())).encode("utf-8")).hexdigest()[:12]


# --- DCT basis (built once, deterministic) ----------------------------------
def _dct_matrix(n: int) -> np.ndarray:
    k = np.arange(n).reshape(-1, 1)
    i = np.arange(n).reshape(1, -1)
    m = np.cos(np.pi * (2 * i + 1) * k / (2 * n))
    m[0] /= np.sqrt(2)
    return m * np.sqrt(2 / n)


_DCT = _dct_matrix(PHASH_SIZE)


# --- normalization ----------------------------------------------------------
def normalize(im) -> dict:
    """Composite alpha onto the recorded background; return grayscale + silhouette.

    The **silhouette** is the alpha mask when there is one, and otherwise a
    background-difference mask (pixels that differ from the modal border colour).
    Deriving it for opaque images too is what lets the *same logo on white* and
    *on black* be recognised as one artwork: their grayscale hashes are almost
    inverted, but their silhouettes are identical.
    """
    from PIL import Image
    rgba = im.convert("RGBA")
    alpha_raw = np.asarray(rgba)[..., 3].astype(np.float32) / 255.0
    has_alpha = bool((alpha_raw < 0.99).any())
    bg = Image.new("RGB", rgba.size, ALPHA_BACKGROUND)
    bg.paste(rgba, mask=rgba.split()[3])
    gray = np.asarray(bg.convert("L")).astype(np.float32)

    if has_alpha:
        silhouette = (alpha_raw > 0.1).astype(np.float32)
    else:
        g = np.asarray(im.convert("L")).astype(np.float32)
        border = np.concatenate([g[0], g[-1], g[:, 0], g[:, -1]])
        modal = float(np.median(border))
        silhouette = (np.abs(g - modal) > 32).astype(np.float32)

    cov = float(silhouette.mean())
    return {"gray": gray, "alpha": alpha_raw, "silhouette": silhouette,
            "silhouette_coverage": cov,
            # an all-on or all-off silhouette carries no shape information
            "silhouette_informative": 0.02 < cov < 0.98,
            "has_alpha": has_alpha, "size": rgba.size}


def _resize(a: np.ndarray, w: int, h: int) -> np.ndarray:
    from PIL import Image
    return np.asarray(
        Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "L")
        .resize((w, h), Image.BILINEAR)).astype(np.float32)


# --- the three hashes -------------------------------------------------------
def _dhash(gray: np.ndarray) -> int:
    g = _resize(gray, DHASH_W, DHASH_H)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return _bits_to_int(bits)


def _phash(gray: np.ndarray) -> int:
    g = _resize(gray, PHASH_SIZE, PHASH_SIZE)
    d = _DCT @ g @ _DCT.T                       # 2-D DCT-II
    block = d[:PHASH_KEEP, :PHASH_KEEP].flatten()
    med = np.median(block[1:])                  # exclude DC
    bits = block > med
    bits[0] = False                             # DC never carries information
    return _bits_to_int(bits)


def _bits_to_int(bits) -> int:
    v = 0
    for b in np.asarray(bits).flatten()[:64]:
        v = (v << 1) | int(bool(b))
    return v


def hamming(a: int, b: int) -> int:
    return int(bin(a ^ b).count("1"))


# --- information content (OVERRIDES hash distance) --------------------------
def information(norm: dict) -> dict:
    gray, alpha = norm["gray"], norm["alpha"]
    coverage = float((alpha > 0.1).mean())
    visible = gray[alpha > 0.1] if coverage > 0 else gray.flatten()
    std = float(visible.std()) if visible.size else 0.0
    hist = np.bincount(np.clip(visible, 0, 255).astype(np.uint8).flatten(),
                       minlength=256).astype(float) if visible.size else np.zeros(256)
    p = hist / max(hist.sum(), 1.0)
    p = p[p > 0]
    entropy = float(-(p * np.log2(p)).sum()) if p.size else 0.0

    reasons = []
    if std < C.INFO_MIN_STD:
        reasons.append(f"near-uniform image (grayscale sd {std:.1f} < "
                       f"{C.INFO_MIN_STD})")
    if coverage < C.INFO_MIN_ALPHA_COVERAGE:
        reasons.append(f"mostly transparent (visible coverage {coverage:.1%})")
    if entropy < C.INFO_MIN_ENTROPY:
        reasons.append(f"low entropy ({entropy:.2f} bits)")
    weak = bool(reasons)
    return {
        "grayscale_std": round(std, 2),
        "entropy_bits": round(entropy, 2),
        "alpha_coverage": round(coverage, 4),
        "weak_evidence": weak,
        "reasons": reasons or ["sufficient visual information"],
        "confidence_cap": C.WEAK_EVIDENCE_CONFIDENCE_CAP if weak else 1.0,
    }


# --- transforms -------------------------------------------------------------
def _transform(gray: np.ndarray, sil: np.ndarray, xf: str):
    ops = {C.XF_IDENTITY: lambda a: a,
           C.XF_MIRRORED: np.fliplr,
           C.XF_ROT90: lambda a: np.rot90(a, 1),
           C.XF_ROT180: lambda a: np.rot90(a, 2),
           C.XF_ROT270: lambda a: np.rot90(a, 3)}
    if xf not in ops:
        raise ValueError(f"unknown transform: {xf!r}")
    return ops[xf](gray), ops[xf](sil)


def region_hashes(gray: np.ndarray) -> dict:
    """dHash of each sub-region of the image.

    This is what gives a CROP hypothesis *positive visual evidence*: a crop of an
    image is (approximately) one of these regions, so the crop's whole-image hash
    should match one of the parent's region hashes. Without it, "crop" could only
    be guessed from a shared folder plus a different aspect ratio — which is not
    visual evidence at all, and would relate two unrelated images that merely sat
    in the same download folder.
    """
    h, w = gray.shape
    hh, hw = h // 2, w // 2
    regions = {
        "top": gray[:hh, :], "bottom": gray[hh:, :],
        "left": gray[:, :hw], "right": gray[:, hw:],
        "center": gray[h // 4:3 * h // 4, w // 4:3 * w // 4],
        "tl": gray[:hh, :hw], "tr": gray[:hh, hw:],
        "bl": gray[hh:, :hw], "br": gray[hh:, hw:],
    }
    # BOTH hashes are kept per region. A single dHash is far too weak here: on
    # flat-background artwork most gradient bits are zero, so two *unrelated*
    # white-ish regions collided at Hamming 8 and manufactured a crop claim.
    return {name: {"d": _dhash(r), "p": _phash(r)} for name, r in regions.items()
            if r.shape[0] >= 8 and r.shape[1] >= 9}


def hash_image(im, *, rel_path: str = "") -> dict:
    """Full hash record for one image, under every transform."""
    norm = normalize(im)
    info = information(norm)
    variants = {}
    for xf in C.TRANSFORMS:
        g, s_ = _transform(norm["gray"], norm["silhouette"], xf)
        variants[xf] = {
            "dhash": _dhash(g),
            "phash": _phash(g),
            "shape": _dhash(s_ * 255.0),   # silhouette hash (see normalize)
        }
    w, h = norm["size"]
    return {
        "parser": PARSER,
        "algorithm_version": ALGORITHM_VERSION,
        "config_fingerprint": CONFIG_FP,
        "normalized_dimensions": {"dhash": [DHASH_W, DHASH_H],
                                  "phash": [PHASH_SIZE, PHASH_SIZE]},
        "source_dimensions": {"w": w, "h": h},
        "aspect_ratio": round(w / h, 4) if h else None,
        "alpha_compositing_background": list(ALPHA_BACKGROUND),
        "has_alpha": norm["has_alpha"],
        "silhouette_coverage": round(norm["silhouette_coverage"], 4),
        "silhouette_informative": norm["silhouette_informative"],
        "orientation_policy": ORIENTATION_POLICY,
        "information": info,
        "tier": C.TIER_HEURISTIC,
        "variants": variants,
        "dhash": variants[C.XF_IDENTITY]["dhash"],
        "phash": variants[C.XF_IDENTITY]["phash"],
        "shape": variants[C.XF_IDENTITY]["shape"],
        "regions": region_hashes(norm["gray"]),
        "rel_path": rel_path,
    }


def color_signature(im) -> np.ndarray:
    """A 4×4×4 RGB histogram of the **foreground** pixels — the palette evidence
    that separates a COLORWAY (same geometry, different palette) from a duplicate.

    It is deliberately measured over the silhouette, not the whole frame: a shared
    background otherwise dominates the histogram and drowns the very difference we
    are looking for (red-vs-blue artwork on white scored only 0.22 apart when the
    white background was counted, and would have been missed).
    """
    norm = normalize(im)
    rgb = np.asarray(im.convert("RGB"))
    if norm["silhouette_informative"]:
        vis = rgb[norm["silhouette"] > 0.5]
    else:
        vis = rgb.reshape(-1, 3)
    if vis.size == 0:
        return np.zeros(64, dtype=float)
    q = (vis // 64).clip(0, 3)
    idx = q[:, 0] * 16 + q[:, 1] * 4 + q[:, 2]
    hist = np.bincount(idx, minlength=64).astype(float)
    return hist / hist.sum()


def palette_distance(a: np.ndarray, b: np.ndarray) -> float:
    """L1/2 distance in [0, 1]. 0 = identical palette, 1 = disjoint."""
    return float(np.abs(a - b).sum() / 2.0)
