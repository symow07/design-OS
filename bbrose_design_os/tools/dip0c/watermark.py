"""Watermark evidence (DIP-0C2b) — HEURISTIC, never fact.

Output is always `WATERMARK_SUSPECTED` (bool) + confidence + evidence +
`human_confirmed: None`. A machine never asserts that an asset IS watermarked.

**Hard rule:** low resolution alone contributes **zero** and can never, on its
own, make a file suspected. A small clean logo is not a stock preview. Suspicion
requires a *positive* signal — a stock provider name, a preview label, a repeated
low-opacity overlay, or an edge text band — and low resolution may only
*corroborate* one of those.
"""
from __future__ import annotations

import re

import numpy as np

from . import config as C

PARSER = f"{C.TOOL_NAME}.watermark/{C.TOOL_VERSION}"

STOCK_PROVIDERS = ("shutterstock", "istock", "gettyimages", "getty",
                   "depositphotos", "dreamstime", "123rf", "alamy", "adobestock",
                   "stock.adobe", "freepik", "vecteezy", "bigstock", "canstock")
PREVIEW_LABELS = ("preview", "comp", "sample", "watermark", "watermarked",
                  "lowres", "low-res", "thumb")

# positive-signal weights; low resolution is deliberately NOT among them
W_PROVIDER = 0.45
W_PREVIEW_LABEL = 0.30
W_OVERLAY = 0.35
W_EDGE_BAND = 0.20
W_LOWRES_CORROBORATION = 0.10      # only ADDED when a positive signal exists
SUSPECT_THRESHOLD = 0.40


def assess(*, rel_path: str, image=None, long_edge: int = 0,
           package_hints: list[str] | None = None) -> dict:
    """`image` is an optional PIL image (the candidate crop or its source)."""
    ev: list[str] = []
    score = 0.0

    name = rel_path.lower()
    providers = [p for p in STOCK_PROVIDERS if p in name]
    if providers:
        score += W_PROVIDER
        ev.append(f"stock-provider name in path: {providers}")

    labels = [t for t in PREVIEW_LABELS if re.search(rf"\b{re.escape(t)}\b", name)]
    if labels:
        score += W_PREVIEW_LABEL
        ev.append(f"preview/comp label in filename: {labels}")

    for hint in (package_hints or []):
        if any(p in hint.lower() for p in STOCK_PROVIDERS):
            score += W_PROVIDER / 2
            ev.append(f"stock provider in package context: {hint}")
            break

    if image is not None:
        overlay = _repeated_low_opacity_overlay(image)
        if overlay["detected"]:
            score += W_OVERLAY
            ev.append(overlay["detail"])
        band = _edge_text_band(image)
        if band["detected"]:
            score += W_EDGE_BAND
            ev.append(band["detail"])

    positive = score > 0.0
    low_res = 0 < long_edge < C.RES_THRESHOLDS[C.RES_LOW_RES_REFERENCE]
    if low_res and positive:
        score += W_LOWRES_CORROBORATION
        ev.append(f"low resolution ({long_edge}px) corroborates the above")
    elif low_res:
        # explicit: never suspicion on its own
        ev.append(f"low resolution ({long_edge}px) noted — contributes NOTHING to "
                  "watermark suspicion on its own")

    suspected = positive and score >= SUSPECT_THRESHOLD
    if not ev:
        ev.append("no stock/preview/overlay signals detected")

    return {
        "value": suspected,                     # WATERMARK_SUSPECTED
        "state": "WATERMARK_SUSPECTED" if suspected else "NOT_SUSPECTED",
        "confidence": round(min(score, 0.85), 3) if suspected else round(score, 3),
        "tier": C.TIER_HEURISTIC,
        "evidence": ev,
        "human_confirmed": None,                # machine never confirms
        "parser": PARSER,
        "note": "heuristic suspicion only; never a statement of fact",
    }


def _repeated_low_opacity_overlay(im) -> dict:
    """A tiled low-opacity watermark leaves a periodic, low-amplitude residual
    against a smoothed baseline. Detect periodicity in that residual."""
    try:
        g = np.asarray(im.convert("L").resize((256, 256))).astype(float)
    except Exception:  # noqa: BLE001
        return {"detected": False, "detail": ""}
    # residual vs a box-blurred baseline
    k = 8
    pad = np.pad(g, k, mode="edge")
    base = np.stack([pad[i:i + 256, j:j + 256]
                     for i in range(0, 2 * k, 4) for j in range(0, 2 * k, 4)]
                    ).mean(axis=0)
    resid = g - base
    amp = float(np.abs(resid).mean())
    if amp < 0.5 or amp > 12.0:
        # too flat to carry an overlay, or too busy to attribute one
        return {"detected": False, "detail": ""}
    # periodicity: autocorrelation peaks away from zero lag
    r = resid - resid.mean()
    ac = np.array([float((r[:, :-d] * r[:, d:]).mean()) for d in range(8, 96, 8)])
    r0 = float((r * r).mean()) or 1.0
    peak = float(ac.max() / r0)
    detected = peak > 0.30
    return {"detected": detected,
            "detail": (f"repeated low-opacity overlay: periodic residual "
                       f"(amplitude {amp:.1f}, periodicity {peak:.2f})"
                       if detected else "")}


def _edge_text_band(im) -> dict:
    """A stock band is a high-frequency strip hugging the top or bottom edge while
    the rest of the image is comparatively smooth."""
    try:
        g = np.asarray(im.convert("L").resize((256, 256))).astype(float)
    except Exception:  # noqa: BLE001
        return {"detected": False, "detail": ""}
    grad = np.abs(np.diff(g, axis=1)).mean(axis=1)   # per-row horizontal energy
    band_h = 24
    top, bottom = grad[:band_h].mean(), grad[-band_h:].mean()
    middle = grad[band_h:-band_h].mean() or 1e-6
    ratio = max(top, bottom) / middle
    detected = ratio > 3.0 and max(top, bottom) > 4.0
    return {"detected": detected,
            "detail": (f"edge text band: border row-energy {ratio:.1f}x the "
                       f"interior" if detected else "")}
