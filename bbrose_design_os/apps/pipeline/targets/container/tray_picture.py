"""[His test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (5): "THE TRAY: after
I pick a concept, draw one more picture of the open palette in the same style (tray, pans, names), ~$0.25, read into the
map. Every pan gets a real shade colour and finish (matte / shimmer / glitter), from that picture or, if needed, from the
shade name and the concept's palette; list them for me to check. No grey pans."]

MEASURED at his blocker: 124's tray drawn with 18 pans named from his brief, every pan one neutral grey (#D8D2CF) — shown,
never printed, and no shade's colour planned.

* THE PICTURE (``make_tray``, paid once): the chosen concept's palette drawn OPEN, from above, in the same style — its
  pans in his grid, each a pressed shade, its name under it — kept on the concept (``TRAY_KEY``) against the concept's
  own bytes; never printed (``ensure_tray``: kept, nothing paid again).
* THE READ (``read_tray_picture``, $0, pure): the pans found in the picture's own pixels — square wells of one size in
  his grid's rows and columns; a picture that does not show his grid is REFUSED by name, never fitted; each pan's
  COLOUR the median of its middle (its highlights left out), its FINISH read from its texture: GLITTER where flakes of
  light and colour stand out of it, SHIMMER where a fine grain or a sheen runs across it, MATTE where neither.
* THE PANS (``pans_for``): every pan of his grid its shade's name (his brief, never the picture), its colour and its
  finish, each with its source — the tray picture, or, where the picture gives none, the shade's own name and the
  concept's palette — the list he checks.
"""
from __future__ import annotations
from apps.pipeline.services.cost_ledger import BudgetExceededError as _RescueBudgetError
from apps.pipeline.services.spend_reservation import paid_operation

import hashlib

TRAY_KEY = "container_tray_picture/1.0"
TRAY_READ_KEY = "container_tray_read/1.0"
TRAY_PROMPT_VERSION = "tray-1"
TRAY_OPERATION = "image:open tray:%s"
TRAY_SIZE = "1536x1024"
#: the picture's own words — how the image service's stand-in knows it
TRAY_WORDS = "The same palette as in this picture, now OPEN"
TRAY_PROMPT = (
    TRAY_WORDS + " and seen from directly above, square to the eye: its open tray holding {n} {shape} pans in {rows} "
    "rows of {cols}, all one size, evenly spaced in a neat grid, each pan a pressed eyeshadow in its own shade — left to "
    "right, row by row: {names} — each shade's name printed in clean capitals under its own pan. The same style, colours "
    "and materials as the closed palette's design, its glowing edge round the pans. Each pan shows its finish: matte, "
    "shimmer or glitter as its name suggests. Plain background, no hands, no brushes, no props, no extra words.")

MADE = "MADE"
READ = "READ"
REFUSED = "REFUSED"
TRAY_NOT_MADE = "CONTAINER_TRAY_PICTURE_NOT_MADE"
TRAY_NOT_READ = "CONTAINER_TRAY_PICTURE_NOT_READ"
MATTE, SHIMMER, GLITTER = "matte", "shimmer", "glitter"
FROM_PICTURE = "the tray picture"
FROM_NAME = "its name and the concept's palette"

#: the read's numbers (the executor's, new with his blocker; his to change): a pan is a well whose box is square within
#: ``square`` and whose area is within ``size_spread`` of the pans' median; its middle (``middle`` of its side) is read;
#: its GRAIN the spread of its lightness about a blur over ``grain_px`` (the pressed powder's fine sparkle), its FLAKES
#: the spread of its lightness and its colour between that blur and one over ``flake_px`` (pieces of light and colour
#: larger than the grain); GLITTER where its flakes pass ``flakes_de``; SHIMMER where its grain passes ``grain_l`` or
#: its lightness runs ``sheen_l`` from its darkest tenth to its lightest across the pan (a sheen); MATTE where neither.
#: [his test blocker on design 124, 2026-10-11, (5)] 1.1: set on 124's real tray picture, where the bright-speck count
#: of 1.0 read four shimmering pans (Wild Rose, Spellbound, Twilight, Nightshade) matte — its matte pans' grain 0.6–2.3,
#: its shimmer's and glitter's 4.2–8.7; its shimmer's flakes 1.6–2.4, its glitter's (Fairy Dust, Eternal) 2.8 and 4.3
#: [his goal of 2026-10-12, (11)–(13)] 1.2: the tray's own inks — each pan's RIM the band ``rim`` of its side just
#: inside its edge, its GLOW the band ``glow`` just outside it, the NAMES' ink the darkest ``name_dark`` of the band
#: ``name_band`` (shares of its height) under it — set on 124's tray picture (rim #CBAC88, glow #D6DBDA, names #695678)
READ_PARAMS = {"version": "tray_read/1.2", "square": 0.25, "size_spread": 0.35, "middle": 0.7, "highlight_l": 96.0,
               "grain_px": 2.0, "flake_px": 8.0, "grain_l": 3.0, "flakes_de": 2.6, "sheen_l": 3.0,
               "min_side_share": 0.03, "rim": 0.06, "glow": 0.04, "name_band": (1.06, 1.30), "name_dark": 0.05}

#: [his item 5: "or, if needed, from the shade name and the concept's palette"] the words of a shade's name that say its
#: finish — the executor's reading of the words, his to change
GLITTER_WORDS = ("glitter", "sparkle", "dust", "star", "spark", "glimmer")
SHIMMER_WORDS = ("shimmer", "frost", "pearl", "gilded", "gold", "moonlit", "moon", "glow", "metal", "silk", "satin")


def tray_prompt(tray: dict) -> str:
    names = "; ".join(", ".join(n for n in row if n) for row in tray["names"])
    return TRAY_PROMPT.format(n=tray["rows"] * tray["cols"], shape=tray["shape"], rows=tray["rows"],
                              cols=tray["cols"], names=names)


def _concept_sha(image) -> str:
    with image.image_file.open("rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def kept_tray(image) -> dict | None:
    """The tray picture kept on the concept, where it was drawn from THIS picture under THIS prompt; else None."""
    prov = image.reference_provenance if isinstance(image.reference_provenance, dict) else {}
    record = prov.get(TRAY_KEY)
    if not isinstance(record, dict) or record.get("prompt_version") != TRAY_PROMPT_VERSION:
        return None
    if record.get("concept_sha256") != _concept_sha(image):
        return None
    return record


def tray_bytes(record: dict) -> bytes:
    from django.core.files.storage import default_storage
    with default_storage.open(record["file"], "rb") as fh:
        return fh.read()


def make_tray(aria, image, tray: dict) -> dict:
    """The open palette drawn once from the chosen concept ``image`` — a paid picture, on the ledger as "image:open
    tray:<its direction>", its file and what it cost kept on the concept (``TRAY_KEY``), never printed."""
    import base64
    import mimetypes
    import os
    import time

    import openai
    from django.conf import settings
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    from django.utils import timezone

    from apps.pipeline.models import ApiCallRecord
    from apps.pipeline.services import cost_ledger
    from apps.pipeline.services.cost_ledger import provider_request_id, record_image
    from apps.pipeline.services.flat_motif import _capped
    if cost_ledger.daily_budget_exceeded():
        raise cost_ledger.BudgetExceededError("the day's spending cap is reached")
    cost_ledger.check_task_budget(aria.task)
    with image.image_file.open("rb") as fh:
        concept = fh.read()
    kind = mimetypes.guess_type(image.image_file.name)[0]
    sent = (os.path.basename(image.image_file.name), concept, kind if kind else "image/png")
    prompt = tray_prompt(tray)
    started = time.monotonic()
    from apps.pipeline.services.cost_ledger import before_paid_call   # [his goal of 2026-10-13, (2)]
    before_paid_call("a picture", fidelity=True)   # [his goal for the pitch, B (6)] fidelity is paid for
    response = paid_operation(openai.images.edit, provider='openai', operation='tray_picture', model=settings.IMAGE_MODEL, image=[sent], prompt=prompt, size=TRAY_SIZE,
                                  quality=settings.IMAGE_QUALITY_CONCEPTS, n=1, timeout=180)
    operation = TRAY_OPERATION % image.direction_name
    if _capped(record_image, settings.IMAGE_MODEL, operation, aria.task,
               {"provider_request_id": provider_request_id(response),
                "latency_ms": int((time.monotonic() - started) * 1000), "concept_image_id": image.pk}):
        aria.log("ARIA: the open tray's picture reached this design's spending cap — it is kept, it is paid for",
                 level="warning")
    row = ApiCallRecord.objects.filter(task=aria.task, operation=operation).order_by("-pk").first()
    drawn = base64.b64decode(response.data[0].b64_json)
    name = default_storage.save("concepts/task_%d_tray_%d.png" % (aria.task.pk, image.pk), ContentFile(drawn))
    record = {"state": MADE, "file": name, "sha256": hashlib.sha256(drawn).hexdigest(),
              "concept_sha256": hashlib.sha256(concept).hexdigest(), "size": TRAY_SIZE, "prompt": prompt,
              "prompt_version": TRAY_PROMPT_VERSION, "model": settings.IMAGE_MODEL,
              "grid": [tray["rows"], tray["cols"]], "cost_usd": str(row.cost_usd) if row is not None else "0",
              "at": timezone.now().isoformat(),
              "why": "his test blocker on design 124, (5): the open tray drawn in the concept's style, never printed"}
    prov = dict(image.reference_provenance or {})
    prov[TRAY_KEY] = record
    image.reference_provenance = prov
    image.save(update_fields=["reference_provenance"])
    aria.log("ARIA: the open palette drawn from '%s' — its pans' shades and finishes, never printed — $%s"
             % (image.direction_name, record["cost_usd"]))
    return record


def ensure_tray(aria, image, tray: dict) -> dict:
    """The tray picture: kept on the concept (nothing paid), else made now — or ``{"state": REFUSED, "code", "why"}``,
    said; the pans then take their name's colour and finish, each said so (``pans_for``), never grey."""
    from apps.pipeline.services import cost_ledger
    kept = kept_tray(image)
    if kept is not None:
        aria.log("ARIA: the open tray's picture is on record for this concept — kept, nothing spent")
        return kept
    try:
        return make_tray(aria, image, tray)
    except cost_ledger.BudgetExceededError as exc:
        raise
        return {"state": REFUSED, "code": TRAY_NOT_MADE, "why": "the spending cap: %s" % exc}
    except Exception as exc:  # noqa: BLE001 — said by name
        if isinstance(exc, _RescueBudgetError):
            raise
        return {"state": REFUSED, "code": TRAY_NOT_MADE,
                "why": "the picture service could not make it just now (%s: %s)" % (type(exc).__name__, str(exc)[:160])}


# ------------------------------------------------------------------------------------------------------------- THE READ

def _lab(img):
    import cv2
    import numpy as np
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab[..., 0] *= 100.0 / 255.0
    lab[..., 1:] -= 128.0
    return lab


def _hex(bgr) -> str:
    return "#%02X%02X%02X" % (int(bgr[2]), int(bgr[1]), int(bgr[0]))


def _candidates(img):
    """Square wells the picture shows: the boxes of its closed outlines (its edges, and its colour's own regions) that
    are square within READ_PARAMS["square"] and no smaller than ``min_side_share`` of its shorter side."""
    import cv2
    import numpy as np
    h, w = img.shape[:2]
    least = READ_PARAMS["min_side_share"] * min(h, w)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    boxes = []
    for edges in (cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 30, 90),
                  cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 51, 4)):
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        contours, _ = cv2.findContours(closed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            x, y, bw, bh = cv2.boundingRect(c)
            if min(bw, bh) < least or abs(bw - bh) > READ_PARAMS["square"] * max(bw, bh):
                continue
            if cv2.contourArea(c) < 0.6 * bw * bh:
                continue
            boxes.append((x, y, bw, bh))
    return boxes


def _grid(boxes, rows: int, cols: int):
    """The pans: of the candidates one size (within ``size_spread`` of the median of the commonest sizes), one per place
    — overlapping boxes merged — sorted into ``rows`` rows of ``cols``; None where they do not make that grid."""
    import numpy as np
    if not boxes:
        return None
    areas = np.array([bw * bh for _x, _y, bw, bh in boxes], float)
    best, best_n = None, 0
    for a in np.unique(np.round(areas, -2)):
        near = np.abs(areas - a) <= READ_PARAMS["size_spread"] * a
        if near.sum() > best_n:
            best, best_n = a, int(near.sum())
    keep = [b for b, ar in zip(boxes, areas) if abs(ar - best) <= READ_PARAMS["size_spread"] * best]
    merged = []
    for x, y, bw, bh in sorted(keep, key=lambda b: -b[2] * b[3]):
        cx, cy = x + bw / 2.0, y + bh / 2.0
        if any(abs(cx - (mx + mw / 2.0)) < mw / 2.0 and abs(cy - (my + mh / 2.0)) < mh / 2.0
               for mx, my, mw, mh in merged):
            continue
        merged.append((x, y, bw, bh))
    if len(merged) != rows * cols:
        return None
    merged.sort(key=lambda b: b[1] + b[3] / 2.0)
    grid = [sorted(merged[r * cols:(r + 1) * cols], key=lambda b: b[0]) for r in range(rows)]
    # each row one row: its pans' middles within half a pan of one another, rows apart from each other
    for row in grid:
        ys = [y + bh / 2.0 for _x, y, _w, bh in row]
        if max(ys) - min(ys) > 0.5 * np.median([bh for *_r, bh in row]):
            return None
    return grid


def finish_of(lab_pan) -> tuple:
    """``(finish, measures)`` of one pan's middle, from its texture: GLITTER, SHIMMER or MATTE (READ_PARAMS)."""
    import cv2
    import numpy as np
    L = lab_pan[..., 0]
    fine, coarse = READ_PARAMS["grain_px"], READ_PARAMS["flake_px"]
    grain = float((L - cv2.GaussianBlur(L, (0, 0), fine)).std())

    def flakes_in(ch):
        return float((cv2.GaussianBlur(ch, (0, 0), fine) - cv2.GaussianBlur(ch, (0, 0), coarse)).std())

    flakes = flakes_in(L) + float(np.hypot(flakes_in(lab_pan[..., 1]), flakes_in(lab_pan[..., 2])))
    soft = cv2.GaussianBlur(L, (0, 0), max(2.0, min(L.shape) / 6.0))
    sheen = float(np.percentile(soft, 90) - np.percentile(soft, 10))
    measures = {"grain_l": round(grain, 2), "flakes_de": round(flakes, 2), "sheen_l": round(sheen, 2)}
    if flakes > READ_PARAMS["flakes_de"]:
        return GLITTER, measures
    if grain > READ_PARAMS["grain_l"] or sheen > READ_PARAMS["sheen_l"]:
        return SHIMMER, measures
    return MATTE, measures


def read_tray_picture(png: bytes, rows: int, cols: int) -> dict:
    """The tray picture read at $0: ``{"schema_version", "state": READ, "pans": [[{"box_px", "hex", "finish",
    "measures"}] * cols] * rows}`` — or REFUSED, by name, where the picture does not open or does not show his grid."""
    import cv2
    import numpy as np
    rec = {"schema_version": TRAY_READ_KEY, "params": dict(READ_PARAMS),
           "source_sha256": hashlib.sha256(png).hexdigest() if png else None, "grid": [rows, cols]}
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR) if png else None
    if img is None:
        return {**rec, "state": REFUSED, "code": TRAY_NOT_READ, "why": "the tray picture could not be opened"}
    grid = _grid(_candidates(img), rows, cols)
    if grid is None:
        return {**rec, "state": REFUSED, "code": TRAY_NOT_READ,
                "why": "the tray picture does not show %d pans in %d rows of %d" % (rows * cols, rows, cols)}
    lab = _lab(img)
    out = []
    for row in grid:
        got = []
        for x, y, bw, bh in row:
            m = (1.0 - READ_PARAMS["middle"]) / 2.0
            x0, y0, x1, y1 = int(x + m * bw), int(y + m * bh), int(x + (1 - m) * bw), int(y + (1 - m) * bh)
            pan_lab = lab[y0:y1, x0:x1]
            pixels = img[y0:y1, x0:x1].reshape(-1, 3)
            lit = pan_lab.reshape(-1, 3)[:, 0] < READ_PARAMS["highlight_l"]
            colour = np.median(pixels[lit] if lit.any() else pixels, axis=0)
            finish, measures = finish_of(pan_lab)
            got.append({"box_px": [int(x), int(y), int(bw), int(bh)], "hex": _hex(colour), "finish": finish,
                        "measures": measures})
        out.append(got)
    return {**rec, "state": READ, "pans": out, **_tray_inks(img, grid)}


def _tray_inks(img, grid) -> dict:
    """[His goal of 2026-10-12, (11): "Pan rims follow the tray picture (soft gold), not grey"; (12): "the holographic
    edge around the pans, as the tray picture shows"; (13): "Pan names readable".] The tray's inks as its picture prints
    them, each the median over every pan: ``rim`` (the band just inside each pan's edge), ``glow`` (the band just
    outside it) and ``names_ink`` (the darkest of the band under it, where its name prints)."""
    import cv2
    import numpy as np
    p = READ_PARAMS
    h_img, w_img = img.shape[:2]

    def band(x, y, bw, bh, inner, outer):
        keep = np.zeros(img.shape[:2], bool)
        keep[max(0, int(y - outer * bh)):min(h_img, int(y + bh + outer * bh)),
             max(0, int(x - outer * bw)):min(w_img, int(x + bw + outer * bw))] = True
        hole = np.zeros_like(keep)
        y0, y1 = max(0, int(y - inner * bh)), int(y + bh + inner * bh)
        hole[y0:y1, max(0, int(x - inner * bw)):int(x + bw + inner * bw)] = True
        return np.median(img[keep & ~hole], axis=0)
    rims, glows, inks = [], [], []
    for row in grid:
        for x, y, bw, bh in row:
            rims.append(band(x, y, bw, bh, -p["rim"], 0.0))
            glows.append(band(x, y, bw, bh, 0.0, p["glow"]))
            under = img[max(0, int(y + bh * p["name_band"][0])):min(h_img, int(y + bh * p["name_band"][1])),
                        max(0, int(x)):min(w_img, int(x + bw))]
            if under.size:
                lit = cv2.cvtColor(under, cv2.COLOR_BGR2LAB)[..., 0].astype(float)
                dark = under[lit <= np.percentile(lit, 100.0 * p["name_dark"])]
                if len(dark):
                    inks.append(np.median(dark, axis=0))
    out = {"rim": _hex(np.median(rims, axis=0)), "glow": _hex(np.median(glows, axis=0))}
    if inks:
        out["names_ink"] = _hex(np.median(inks, axis=0))
    return out


# ------------------------------------------------------------------------------------------- THE INSIDE OF THE LID

#: [his goal of 2026-10-12, (12): "Draw the inside of the lid (roses + arch above the pans) ... as the tray picture
#: shows."] where the tray picture shows the open lid: above its pans, from the picture's top to the HINGE — the first
#: row (from the top, below ``hinge_from`` of the way down to the pans) where the lid's colour steps by ``hinge_step``
#: (RGB distance) — between its sides, the columns standing ``side_far`` from the picture's own background, inset by
#: ``side_inset``; straightened to a strip ``strip_px`` wide and traced as the lid's art is ($0)
LID_INSIDE = {"version": "lid_inside/1.0", "hinge_from": 0.3, "hinge_step": 20.0, "side_far": 40.0, "side_inset": 0.02,
              "strip_px": 1200}
LID_INSIDE_KEY = "container_lid_inside/1.0"


def lid_inside_strip(png: bytes, grid_top_px: int) -> tuple:
    """``(strip_png | None, record)`` — the inside of the lid the tray picture shows, straightened: its corners in the
    picture (``quad``), the strip's own aspect; None, and why, where the picture shows no lid above its pans."""
    import cv2
    import numpy as np
    p = LID_INSIDE
    rec = {"schema_version": LID_INSIDE_KEY, "params": dict(p)}
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR) if png else None
    if img is None or grid_top_px <= 10:
        return None, {**rec, "state": REFUSED, "why": "no tray picture, or no room above its pans"}
    h, w = img.shape[:2]
    work = img.astype(float)
    rows = work[:grid_top_px, int(w * 0.3):int(w * 0.7)].mean(axis=1)
    steps = np.sqrt((np.diff(rows, axis=0) ** 2).sum(-1))
    start = int(grid_top_px * p["hinge_from"])
    found = [y for y in range(start, len(steps)) if steps[y] >= p["hinge_step"]]
    if not found:
        return None, {**rec, "state": REFUSED, "why": "no hinge between the picture's top and its pans"}
    hinge = found[0]
    corners = np.concatenate([img[:12, :12].reshape(-1, 3), img[:12, -12:].reshape(-1, 3)]).astype(float)
    ground = np.median(corners, axis=0)

    def sides(y):
        far = np.nonzero(np.sqrt(((work[y] - ground) ** 2).sum(-1)) > p["side_far"])[0]
        if not len(far):
            return None
        inset = (far.max() - far.min()) * p["side_inset"]
        return far.min() + inset, far.max() - inset
    top, foot = sides(2), sides(max(2, hinge - 3))
    if top is None or foot is None:
        return None, {**rec, "state": REFUSED, "why": "the lid's sides do not stand out of the picture's ground"}
    quad = np.float32([[top[0], 0], [top[1], 0], [foot[1], hinge], [foot[0], hinge]])
    sw = p["strip_px"]
    sh = max(8, int(round(sw * hinge / float(foot[1] - foot[0]))))
    warp = cv2.warpPerspective(img, cv2.getPerspectiveTransform(quad, np.float32([[0, 0], [sw, 0], [sw, sh], [0, sh]])),
                               (sw, sh))
    ok, buf = cv2.imencode(".png", warp)
    return buf.tobytes(), {**rec, "state": READ, "quad": [[round(float(a), 1), round(float(b), 1)] for a, b in quad],
                           "hinge_px": int(hinge), "strip_px": [sw, sh]}



# ------------------------------------------------------------------------------------------------------------- THE PANS

def finish_from_name(name: str) -> str:
    words = str(name).lower()
    if any(w in words for w in GLITTER_WORDS):
        return GLITTER
    if any(w in words for w in SHIMMER_WORDS):
        return SHIMMER
    return MATTE


def pans_for(tray: dict, read: dict | None, palette: list) -> list:
    """Every pan of his grid: ``[[{"row", "col", "name", "hex", "finish", "source"}] * cols] * rows`` — its name his
    brief's; its colour and finish the tray picture's where it was READ, else its name's finish and the concept's palette
    colour its place in the row takes (the palette's colours in turn), each said by its source. Never grey."""
    out = []
    for r, names in enumerate(tray["names"]):
        row = []
        for c, name in enumerate(names):
            if read is not None and read.get("state") == READ:
                pan = read["pans"][r][c]
                row.append({"row": r + 1, "col": c + 1, "name": name, "hex": pan["hex"], "finish": pan["finish"],
                            "source": FROM_PICTURE})
            else:
                row.append({"row": r + 1, "col": c + 1, "name": name, "hex": palette[(r * len(names) + c) % len(palette)],
                            "finish": finish_from_name(name), "source": FROM_NAME})
        out.append(row)
    return out
