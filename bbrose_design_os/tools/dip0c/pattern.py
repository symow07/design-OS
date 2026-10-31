"""Pattern / repeat analysis (DIP-0C2b).

Verdicts: SEAMLESS_LIKELY · NON_SEAMLESS_LIKELY · REPEAT_TYPE_UNCERTAIN ·
REQUIRES_TOOL · REQUIRES_HUMAN.

Measured on a rendered tile. The core test is **edge continuity**: a seamless tile
wraps, so its left edge continues into its right edge (and top into bottom). We
compare the wrap seam against the tile's own internal contrast, so a busy tile and
a flat tile are judged on the same scale.

Rules the scope makes binding:
* **EPS without a reliable render is always `REQUIRES_TOOL`** — never a
  seamlessness claim from a header.
* **Filename words (`seamless`, `pattern`, `tile`) are supporting evidence only.**
  They may nudge confidence; they can never determine the verdict. A file named
  `seamless-*.jpg` with visible seams still returns `NON_SEAMLESS_LIKELY`.
* A machine may say `SEAMLESS_LIKELY`, but confidence is capped
  (`SEAMLESS_CONFIDENCE_CAP`) and it never implies reusability.
"""
from __future__ import annotations

import re

import numpy as np

from . import config as C

PARSER = f"{C.TOOL_NAME}.pattern/{C.TOOL_VERSION}"

FILENAME_HINT = re.compile(r"seamless|pattern|tile|repeat", re.I)
SEAM_SEAMLESS = 1.30      # seam energy <= 1.30x internal -> continuous
SEAM_VISIBLE = 2.50       # seam energy >= 2.50x internal -> a visible seam
TILE_PX = 512


def analyse(*, rel_path: str, image=None, is_eps: bool = False,
            recolorable: bool | None = None,
            vector: bool = False, is_tile: bool = True) -> dict:
    """`image` is a PIL image of the rendered tile, or None when unavailable.

    `is_tile=False` means this candidate is one crop out of a multi-asset source.
    A repeat verdict describes a TILE; it cannot be inferred for an isolated crop,
    so such candidates return REQUIRES_HUMAN rather than a fabricated verdict.
    """
    hint = bool(FILENAME_HINT.search(rel_path))

    if is_eps or image is None:
        why = ("EPS has no reliable render (Ghostscript unavailable); "
               "seamlessness cannot be measured from a header" if is_eps
               else "no render available for this candidate")
        return _verdict(C.PAT_REQUIRES_TOOL, 0.0, [why], hint,
                        recolorable=recolorable, vector=vector)

    if not is_tile:
        return _verdict(C.PAT_REQUIRES_HUMAN, 0.0,
                        ["a repeat verdict describes a TILE; this candidate is one "
                         "crop from a multi-asset source, so seamlessness is not "
                         "measurable for it"], hint,
                        recolorable=recolorable, vector=vector)

    arr = _tile(image)
    if arr is None:
        return _verdict(C.PAT_REQUIRES_HUMAN, 0.0,
                        ["tile could not be rasterised for measurement"], hint,
                        recolorable=recolorable, vector=vector)

    # A tile whose borders are a flat margin (e.g. white space around artwork)
    # "wraps" trivially: the seam test is vacuous and must NOT read as seamless.
    flat = _flat_edges(arr)
    if flat["vacuous"]:
        return _verdict(C.PAT_REPEAT_TYPE_UNCERTAIN, 0.25,
                        [flat["detail"],
                         "wrap continuity here is vacuous, not evidence of a "
                         "repeat"], hint,
                        recolorable=recolorable, vector=vector)

    alpha_edges = _transparent_edges(image)
    if alpha_edges:
        # RGB seam test is meaningless when the tile's edges are transparent
        return _verdict(C.PAT_REPEAT_TYPE_UNCERTAIN, 0.3,
                        ["tile edges are transparent — an RGB seam test cannot "
                         "decide continuity; human confirmation needed"], hint,
                        recolorable=recolorable, vector=vector)

    h_seam = _seam_ratio(arr, axis=1)                     # left <-> right
    v_seam = _seam_ratio(arr, axis=0)                     # top <-> bottom
    # half-drop / brick: the neighbouring tile is offset by 1/2 along the other axis
    h_half = _offset_seam_ratio(arr, axis=1, frac=0.5)
    v_half = _offset_seam_ratio(arr, axis=0, frac=0.5)

    ev = [f"edge continuity: horizontal seam {h_seam:.2f}x internal contrast, "
          f"vertical seam {v_seam:.2f}x",
          f"half-drop probe: horizontal {h_half:.2f}x, vertical {v_half:.2f}x"]
    direction = _direction(h_seam, v_seam)
    ev.append(f"repeat direction: {direction}")

    straight_ok = h_seam <= SEAM_SEAMLESS and v_seam <= SEAM_SEAMLESS
    visible = h_seam >= SEAM_VISIBLE or v_seam >= SEAM_VISIBLE
    # half-drop / brick: the axis that FAILS the straight wrap becomes continuous
    # once the neighbouring tile is offset by half.
    offset_better = ((h_seam > SEAM_SEAMLESS and h_half <= SEAM_SEAMLESS)
                     or (v_seam > SEAM_SEAMLESS and v_half <= SEAM_SEAMLESS))

    if straight_ok:
        conf = min(C.SEAMLESS_CONFIDENCE_CAP, 0.55 + (hint * 0.1))
        return _verdict(C.PAT_SEAMLESS_LIKELY, conf,
                        ev + ["both seams continuous at zero offset"], hint,
                        direction=direction, recolorable=recolorable,
                        vector=vector, metrics=(h_seam, v_seam))
    if offset_better:
        ev.append("continuity appears only under a 1/2 offset — a half-drop or "
                  "brick repeat is possible; the repeat TYPE is not decidable "
                  "automatically")
        return _verdict(C.PAT_REPEAT_TYPE_UNCERTAIN, 0.4, ev, hint,
                        direction=direction, recolorable=recolorable,
                        vector=vector, metrics=(h_seam, v_seam))
    if visible:
        return _verdict(C.PAT_NON_SEAMLESS_LIKELY, 0.65,
                        ev + ["a visible seam: edges do not continue"], hint,
                        direction=direction, recolorable=recolorable,
                        vector=vector, metrics=(h_seam, v_seam))
    return _verdict(C.PAT_REPEAT_TYPE_UNCERTAIN, 0.35,
                    ev + ["seam energy is between continuous and clearly broken"],
                    hint, direction=direction, recolorable=recolorable,
                    vector=vector, metrics=(h_seam, v_seam))


def _verdict(value, confidence, ev, hint, *, direction=None, recolorable=None,
             vector=False, metrics=None) -> dict:
    if value not in C.PATTERN_VERDICTS:
        raise ValueError(f"unknown pattern verdict: {value!r}")
    if hint:
        ev = list(ev) + ["filename suggests a repeat (SUPPORTING evidence only — "
                         "it cannot determine the verdict)"]
    if value == C.PAT_SEAMLESS_LIKELY:
        confidence = min(confidence, C.SEAMLESS_CONFIDENCE_CAP)
    return {
        "value": value,
        "confidence": round(float(confidence), 3),
        "tier": C.TIER_HEURISTIC,
        "evidence": list(ev),
        "repeat_direction": direction,
        "filename_hint": hint,
        "filename_hint_is_decisive": False,
        "seam_metrics": ({"horizontal": round(metrics[0], 3),
                          "vertical": round(metrics[1], 3)} if metrics else None),
        "recolorable": recolorable,
        "vector_source": vector,
        "human_confirmed": None,
        "parser": PARSER,
        "note": "a repeat verdict never implies reusability, retrieval or "
                "automatic use",
    }


def _tile(im):
    try:
        g = im.convert("L")
        g = g.resize((min(TILE_PX, g.size[0]), min(TILE_PX, g.size[1])))
        a = np.asarray(g).astype(float)
        return a if a.ndim == 2 and min(a.shape) >= 8 else None
    except Exception:  # noqa: BLE001
        return None


def _flat_edges(a: np.ndarray) -> dict:
    """Borders that carry (almost) no content make the wrap test meaningless: any
    flat margin matches any other flat margin. Compare border variation against
    the tile's interior variation."""
    border = np.concatenate([a[0, :], a[-1, :], a[:, 0], a[:, -1]])
    b_std = float(border.std())
    i_std = float(a.std())
    vacuous = b_std < 6.0 and (i_std < 1e-6 or b_std < 0.20 * i_std)
    return {"vacuous": vacuous,
            "detail": (f"tile borders are a flat margin (border sd {b_std:.1f} vs "
                       f"interior sd {i_std:.1f})" if vacuous else "")}


def _transparent_edges(im) -> bool:
    if im.mode not in ("RGBA", "LA") or "A" not in im.getbands():
        return False
    a = np.asarray(im.convert("RGBA"))[..., 3]
    edges = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    return float((edges < 16).mean()) > 0.5


def _edge_step(a: np.ndarray, axis: int) -> float:
    """The typical difference between GENUINE neighbours at the tile's edges.

    This is the yardstick: when a tile is laid next to itself, its last column
    becomes the neighbour of its first column. A perfectly seamless tile therefore
    shows a wrap difference no larger than an ordinary one-pixel step at that
    edge — even where the local gradient is steep. Normalising by the *mean*
    gradient instead would flunk a genuinely seamless tile whose wrap happens to
    fall on a steep part of the design.
    """
    if axis == 1:
        return float(0.5 * (np.abs(a[:, 0] - a[:, 1]).mean()
                            + np.abs(a[:, -1] - a[:, -2]).mean()))
    return float(0.5 * (np.abs(a[0, :] - a[1, :]).mean()
                        + np.abs(a[-1, :] - a[-2, :]).mean()))


def _seam_ratio(a: np.ndarray, axis: int) -> float:
    """Wrap-seam difference ÷ the local edge step. ~1.0 means the seam is as
    smooth as an ordinary neighbouring pixel, i.e. the tile wraps."""
    if axis == 1:                                  # left <-> right
        seam = float(np.abs(a[:, 0] - a[:, -1]).mean())
    else:                                          # top <-> bottom
        seam = float(np.abs(a[0, :] - a[-1, :]).mean())
    return seam / (_edge_step(a, axis) + 1e-6)


def _offset_seam_ratio(a: np.ndarray, axis: int, frac: float = 0.5) -> float:
    """Half-drop / brick probe: the NEIGHBOURING tile is offset by `frac` along
    the other axis, so the last column meets a *shifted* copy of the first column.
    (Rolling the tile itself and re-measuring would reproduce the same seam and
    prove nothing.)"""
    if axis == 1:                                  # horizontal wrap, vertical drop
        shifted_first = np.roll(a[:, 0], int(a.shape[0] * frac))
        seam = float(np.abs(a[:, -1] - shifted_first).mean())
    else:                                          # vertical wrap, horizontal brick
        shifted_first = np.roll(a[0, :], int(a.shape[1] * frac))
        seam = float(np.abs(a[-1, :] - shifted_first).mean())
    return seam / (_edge_step(a, axis) + 1e-6)


def _direction(h_seam: float, v_seam: float) -> str:
    h_ok, v_ok = h_seam <= SEAM_SEAMLESS, v_seam <= SEAM_SEAMLESS
    if h_ok and v_ok:
        return "both"
    if h_ok:
        return "horizontal"
    if v_ok:
        return "vertical"
    return "none"
