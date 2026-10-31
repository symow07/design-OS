"""`/Separation` colourspaces: spot colours and registration (DIRECT).

Measured in the pilot: PANTONE separations carry a FunctionType-2 tint transform
into a Lab alternate space, e.g.

    [/Separation /PANTONE#20621#20C 133 0 R
        <</C0[100 0 0]/C1[87.8431 -7 2]/Domain[0 1]/FunctionType 2/N 1 ...>>]

`/Separation /All` is the registration colour (alternate DeviceCMYK, C1=[1 1 1 1])
and is a *direct* technical-ink signal — not a heuristic. Nine of the fourteen
pilot files carry it.

Full-strength ink colour = the tint transform evaluated at t=1, which for
FunctionType 2 is exactly `C1`. Conversion to sRGB is deterministic, so a spot's
sRGB value is DIRECT. (Mapping an already-RGB-converted *path* colour back onto a
spot is a different, heuristic problem — that is B4's ΔE matching, not this.)
"""
from __future__ import annotations

import re

# PDF name escapes: `#20` -> space
_ESC = re.compile(r"#([0-9A-Fa-f]{2})")
_SEP = re.compile(r"/Separation\s*/([^\s/\[\]<>()]+)\s+(\d+)\s+\d+\s+R")
_DEVN = re.compile(r"/DeviceN\s*\[")
_C0 = re.compile(r"/C0\s*\[([^\]]*)\]")
_C1 = re.compile(r"/C1\s*\[([^\]]*)\]")
_FT = re.compile(r"/FunctionType\s+(\d+)")
_N = re.compile(r"/N\s+([\d.]+)")
_WP = re.compile(r"/WhitePoint\s*\[([^\]]*)\]")
_RANGE = re.compile(r"/Range\s*\[([^\]]*)\]")

REGISTRATION_NAME = "All"

# CIE standard illuminants
D50 = (0.9642, 1.0000, 0.8249)
D65 = (0.9505, 1.0000, 1.0890)

# Bradford chromatic adaptation, D50 -> D65
_BRADFORD_D50_TO_D65 = (
    (0.9555766, -0.0230393, 0.0631636),
    (-0.0282895, 1.0099416, 0.0210077),
    (0.0122982, -0.0204830, 1.3299098),
)
# XYZ (D65) -> linear sRGB
_XYZ_TO_RGB = (
    (3.2404542, -1.5371385, -0.4985314),
    (-0.9692660, 1.8760108, 0.0415560),
    (0.0556434, -0.2040259, 1.0572252),
)


def unescape_pdf_name(name: str) -> str:
    """`PANTONE#20621#20C` -> `PANTONE 621 C`."""
    return _ESC.sub(lambda m: chr(int(m.group(1), 16)), name)


def _nums(s: str) -> list[float]:
    return [float(x) for x in re.findall(r"[-+]?\d*\.?\d+", s)]


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


def lab_to_srgb(L: float, a: float, b: float,
                whitepoint: tuple[float, float, float] = D50) -> tuple[int, int, int]:
    """CIE Lab -> sRGB (0-255). PDF Lab is D50-referred; adapt to D65."""
    fy = (L + 16.0) / 116.0
    fx = fy + a / 500.0
    fz = fy - b / 200.0

    def finv(t: float) -> float:
        return t ** 3 if t > 6.0 / 29.0 else 3.0 * (6.0 / 29.0) ** 2 * (t - 4.0 / 29.0)

    xw, yw, zw = whitepoint
    X, Y, Z = finv(fx) * xw, finv(fy) * yw, finv(fz) * zw

    m = _BRADFORD_D50_TO_D65
    X, Y, Z = (m[0][0] * X + m[0][1] * Y + m[0][2] * Z,
               m[1][0] * X + m[1][1] * Y + m[1][2] * Z,
               m[2][0] * X + m[2][1] * Y + m[2][2] * Z)

    m = _XYZ_TO_RGB
    lin = (m[0][0] * X + m[0][1] * Y + m[0][2] * Z,
           m[1][0] * X + m[1][1] * Y + m[1][2] * Z,
           m[2][0] * X + m[2][1] * Y + m[2][2] * Z)

    def gamma(c: float) -> float:
        c = _clamp(c)
        return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055

    return tuple(int(round(_clamp(gamma(c)) * 255)) for c in lin)  # type: ignore[return-value]


def cmyk_to_srgb(c: float, m: float, y: float, k: float) -> tuple[int, int, int]:
    """Naive DeviceCMYK -> sRGB. Adequate for registration/technical inks; the
    record always keeps the raw CMYK so nothing is lost to this approximation."""
    r = (1.0 - _clamp(c)) * (1.0 - _clamp(k))
    g = (1.0 - _clamp(m)) * (1.0 - _clamp(k))
    b = (1.0 - _clamp(y)) * (1.0 - _clamp(k))
    return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))


def _range_kind(range_vals: list[float]) -> str | None:
    """Infer the alternate space from the tint transform's /Range.

    Lab ranges look like [0 100 -128 127 -128 127]; RGB/gray ranges are 0..1;
    CMYK has four pairs. This disambiguates an `[/ICCBased N 0 R]` alternate,
    whose component count alone cannot tell Lab from RGB.
    """
    if len(range_vals) >= 8:
        return "cmyk"
    if len(range_vals) >= 6:
        if range_vals[1] > 1.5 and (range_vals[2] < 0 or range_vals[4] < 0):
            return "lab"
        return "rgb"
    if len(range_vals) >= 2:
        return "gray"
    return None


def _alternate_kind(doc, xref: int) -> tuple[str, tuple[float, float, float] | None]:
    """Resolve the alternate colourspace object → ('lab'|'cmyk'|'rgb'|'gray'|'unknown', whitepoint)."""
    try:
        s = doc.xref_object(xref, compressed=True)
    except Exception:  # noqa: BLE001
        return "unknown", None
    if "/Lab" in s:
        wp = _WP.search(s)
        w = tuple(_nums(wp.group(1))[:3]) if wp else D50
        return "lab", w  # type: ignore[return-value]
    if "/DeviceCMYK" in s:
        return "cmyk", None
    if "/DeviceRGB" in s:
        return "rgb", None
    if "/DeviceGray" in s:
        return "gray", None
    if "/ICCBased" in s:
        # `/N` lives in the referenced STREAM dict, not in `[/ICCBased 134 0 R]`.
        # Reading it from the array itself made every pilot spot ink resolve to
        # "unknown", leaving srgb_full_strength null on all 14 real files.
        m = re.search(r"/N\s+(\d+)", s)
        if not m:
            ref = re.search(r"/ICCBased\s+(\d+)\s+\d+\s+R", s)
            if ref:
                try:
                    inner = doc.xref_object(int(ref.group(1)), compressed=True)
                    m = re.search(r"/N\s+(\d+)", inner)
                except Exception:  # noqa: BLE001
                    m = None
        n = int(m.group(1)) if m else 0
        return {3: "rgb", 4: "cmyk", 1: "gray"}.get(n, "unknown"), None
    return "unknown", None


def _full_strength(c1: list[float], kind: str,
                   wp: tuple[float, float, float] | None) -> tuple | None:
    """Evaluate the tint transform at t=1 (FunctionType 2 ⇒ exactly C1)."""
    if kind == "lab" and len(c1) >= 3:
        return lab_to_srgb(c1[0], c1[1], c1[2], wp or D50)
    if kind == "cmyk" and len(c1) >= 4:
        return cmyk_to_srgb(*c1[:4])
    if kind == "rgb" and len(c1) >= 3:
        return tuple(int(round(_clamp(v) * 255)) for v in c1[:3])
    if kind == "gray" and len(c1) >= 1:
        g = int(round(_clamp(c1[0]) * 255))
        return (g, g, g)
    return None


def collect_separation(source: str) -> tuple[str, int] | None:
    """(raw_name, alternate_xref) if this object declares a `/Separation`."""
    m = _SEP.search(source)
    return (m.group(1), int(m.group(2))) if m else None


def is_devicen(source: str) -> bool:
    return bool(_DEVN.search(source))


def build_separation_table(doc, budget, raw_seps: dict[int, tuple[str, int, str]],
                           devicen: int) -> dict:
    """Resolve pre-scanned `/Separation` declarations into inks.

    `raw_seps` comes from the single xref sweep in `inspect.scan_xrefs` — the
    table is built without re-walking the xref table.
    """
    seps: dict[str, dict] = {}
    for x, (raw_name, alt_xref, s) in sorted(raw_seps.items()):
        name = unescape_pdf_name(raw_name)
        if name in seps:
            continue

        kind, wp = _alternate_kind(doc, alt_xref)
        c0 = _nums(_C0.search(s).group(1)) if _C0.search(s) else []
        c1 = _nums(_C1.search(s).group(1)) if _C1.search(s) else []
        ft = int(_FT.search(s).group(1)) if _FT.search(s) else None
        n = float(_N.search(s).group(1)) if _N.search(s) else None
        rng = _nums(_RANGE.search(s).group(1)) if _RANGE.search(s) else []
        # The tint transform's /Range is authoritative when the alternate is an
        # ICC profile: C0=[100,0,0] with Range=[0 100 -128 127 -128 127] is Lab.
        rk = _range_kind(rng)
        kind_source = "alternate_object"
        if rk and (kind == "unknown" or (rk == "lab" and kind == "rgb")):
            kind, kind_source = rk, "tint_transform_range"
        if kind == "lab" and wp is None:
            wp = D50

        srgb = _full_strength(c1, kind, wp) if ft == 2 else None
        is_reg = name == REGISTRATION_NAME

        seps[name] = {
            "name": name,
            "raw_name": raw_name,
            "xref": x,
            "alternate_space": kind,
            "alternate_space_source": kind_source,
            "alternate_range": rng,
            "alternate_whitepoint": list(wp) if wp else None,
            "function_type": ft,
            "exponent_N": n,
            "tint_zero": c0,
            "tint_full": c1,
            "srgb_full_strength": list(srgb) if srgb else None,
            "is_registration": is_reg,
            # Registration is an ink used for crop/registration marks — a
            # DIRECT technical signal, never part of a brand palette.
            "role": "registration" if is_reg else "spot_ink",
            "tier": "DIRECT",
        }

    names = sorted(seps)
    return {
        "count": len(seps),
        "names": names,
        "has_registration": REGISTRATION_NAME in seps,
        "spot_names": [n for n in names if n != REGISTRATION_NAME],
        "devicen_objects": devicen,
        "separations": seps,
        "note": ("Full-strength sRGB is derived deterministically from the tint "
                 "transform (DIRECT). Attributing an RGB-converted path colour "
                 "back to one of these inks is a separate heuristic problem."),
    }
