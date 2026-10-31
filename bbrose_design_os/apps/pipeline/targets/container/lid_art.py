"""[His test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (3): "FULL-COLOUR
ILLUSTRATION: a concept's illustrated scene (shaded roses, gradient sky, glowing arch) is redrawn flat at high resolution
and traced as COLOUR vector (e.g. vtracer, free ...), keeping its colours, gradients and shapes. Never replaced by a
template."]

MEASURED at his blocker: 124's lid was drawn by the face composer's own layout — a flat lilac ground, seven procedural
petals — its concept's illustration never read (the hero reader rectifies round lids only).

THE LID'S ART, in two halves:

* THE REDRAW (``make_lid_art``, paid once): the concept's lid, stood square (``concept_outline.lid_picture``) and sent
  filling the image service's frame (``framed``), redrawn by the image model as flat artwork — the same scene in the
  same layout, its colours and soft gradients, the places its words and mark are printed left as their ground. Never
  printed; it feeds the tracer. Kept on the concept (``LID_ART_KEY``) against the concept's own bytes, so the design
  drawn again pays nothing (``ensure_lid_art``).
* THE TRACE (``trace_art``, $0, pure): read from the redraw's own pixels —
  - ITS SKY, the ground the illustration stands on: a smooth colour field fitted to the ground's own pixels (the median
    of each cell of a grid, the cells the illustration covers filled from their neighbours), drawn as TRACE["bands"]
    bands each a left-to-right gradient of TRACE["stops"] stops — real gradients, never a raster, never colour steps;
  - ITS ILLUSTRATION, traced in colour by vtracer (free, MIT) as filled regions, each region whose own pixels are mostly
    the sky left out (the sky is drawn beneath it).
  Every colour is the redraw's own (his rule after 122: measured from the flat redraw, never the shaded photo).
* THE LAYING (``on_lid``) and THE CHECK (``registration``, $0): the art laid FILLING the lid, so a part at a fraction of
  the lid stands at that fraction of the art — as the map's parts are placed; and, before it is drawn, the redraw
  checked against the lid's map part by part: each line of type and the mark on the ground the concept prints it on,
  each illustration drawn where the concept draws it — or REFUSED, naming the parts and why (his (4)).

MEASURED on 124's first redraw (lid-art-1, sent at the lid's own 919 x 725 and asked at 1536 x 1024): laid to cover the
lid its scene stood 5 % off at top and foot; laid filling it, it stood where the concept's does — except its roses and
leaves grown under the small print at the foot, where the concept prints "18 SHADES ..." and the Arabic line on plain
ground (41 % and 21 % of their boxes the illustration, the concept's 11 % and 3 %).
"""
from __future__ import annotations
from apps.pipeline.services.cost_ledger import BudgetExceededError as _RescueBudgetError
from apps.pipeline.services.spend_reservation import paid_operation

import hashlib
import re

#: kept on the concept picture's provenance: the lid's flat redraw — its file, what it cost, the concept it is made from
LID_ART_KEY = "container_lid_art/1.0"
#: kept on the drawing's record: what was traced, and how far the drawn colours stand from the redraw's
LID_ART_TRACE_KEY = "container_lid_art_trace/1.0"
#: lid-art-2: the lid sent filling the service's frame, its layout kept, the ground under its words kept plain
LID_ART_PROMPT_VERSION = "lid-art-3"   # lid-art-3: [his review of 127-132, 2026-10-15, C (5): "131's ... soft sun"] a
#                                       light's soft halo kept as a smooth gradient, thin lines kept whole
LID_ART_OPERATION = "image:lid art:%s"
#: the redraw's own words — how the image service's stand-in knows it
LID_ART_WORDS = "Redraw ONLY the illustrated artwork printed on this"
LID_ART_PROMPT = (
    LID_ART_WORDS + " {lid} as flat, front-on artwork for print: the same scene, every element in the same place and at "
    "the same size relative to the {lid}, the same colours and the same soft gradients in its sky and its glow, every "
    "shape, figure and line kept — a sun's, a moon's or a light's soft halo kept as a smooth gradient fading into the "
    "sky round it, and every thin line (a horizon, a shoreline, a rule) kept whole, edge to edge where it runs so; drawn "
    "as a clean flat vector illustration with crisp edges and smooth "
    "gradients, no painted or photo texture. This picture is the {lid}'s face already filling the frame edge to edge, "
    "the frame {shape}: keep its layout exactly as it is — every element where it stands, nothing moved, enlarged, "
    "added or carried into empty ground. Where words or the logo are printed, leave only the plain ground behind them, "
    "as plain as the ground around them, nothing of the illustration grown into it: no text, no letters, no numbers, "
    "no logo. No product edge, no shadow, no lighting, no reflection, no paper grain.")
#: the image service's sizes, by the lid's proportions (width over height) — a round lid's circle in the square frame
SIZES = (("1024x1536", 0.83, "taller than it is wide, two by three"),
         ("1536x1024", 1.2, "wider than it is tall, three by two"))
SQUARE = ("1024x1024", "square")
ROUND_SHAPE = "square, the lid's circle filling it edge to edge"

REDRAWN = "REDRAWN"
TRACED = "TRACED"
REFUSED = "REFUSED"
ART_NOT_MADE = "CONTAINER_LID_ART_NOT_MADE"
ART_NOT_TRACED = "CONTAINER_LID_ART_NOT_TRACED"
REGISTERED = "REGISTERED"
ART_NOT_REGISTERED = "CONTAINER_LID_ART_NOT_REGISTERED"
#: kept on the drawing's record: the redraw checked against the lid's map, part by part
LID_ART_REGISTER_KEY = "container_lid_art_register/1.0"
#: the check's numbers (the executor's, set on 124's first redraw; his to change): both pictures' illustration — what is
#: not their sky (``_sky``) — with every stroke thinner than ``stroke_share`` of the picture's longer side opened away
#: (the concept's printed words, never the redraw's flowers); a line of type or the mark refused where the redraw's
#: illustration fills more than ``on_ground`` more of its box than the concept's does; an illustration refused where the
#: redraw fills less than ``drawn_share`` of what the concept fills of its box
REGISTER = {"version": "lid_art_register/1.0", "stroke_share": 0.0085, "on_ground": 0.1, "drawn_share": 0.5}

#: the tracer's numbers, kept on every trace (the executor's, new with his blocker; his to change). ``ground_de``: a
#: pixel is the sky where it stands this near (CIE76) the fitted field; ``ground_min_share``: a patch of sky smaller than
#: this share of the lid and clear of its edge is the illustration's own (a pale petal), never the sky; a traced region
#: is the sky's, and left out, where more than ``region_ground_share`` of its pixels are; ``bands`` x ``stops`` the sky
#: drawn (each band one left-to-right gradient)
TRACE = {"version": "lid_art_trace/1.0", "colour_precision": 7, "layer_difference": 8, "speckle_px": 8,
         "corner_threshold": 60, "length_threshold": 4.0, "splice_threshold": 45, "path_precision": 2,
         "ground_de": 5.0, "ground_seed_de": 8.0, "seed_share": 0.125, "fits": 3, "ground_min_share": 0.01,
         "grid": (24, 36), "cell_ground": 0.08,
         "region_ground_share": 0.5, "bands": 96, "stops": 24, "read_scale": 4,
         # [his goal for the pitch, A (4)] the sky is what the top of the scene opens into (``_sky``)
         "sky_from_top": True, "sky_swallows": 0.85}


def size_for(width_mm: float, height_mm: float, round_lid: bool) -> tuple:
    """``(the image service's size, the frame in words)`` for a lid of these proportions."""
    if round_lid:
        return SQUARE[0], ROUND_SHAPE
    aspect = float(width_mm) / float(height_mm)
    if aspect < SIZES[0][1]:
        return SIZES[0][0], SIZES[0][2]
    if aspect > SIZES[1][1]:
        return SIZES[1][0], SIZES[1][2]
    return SQUARE


def prompt_for(lid_words: str, width_mm: float, height_mm: float, round_lid: bool) -> str:
    return LID_ART_PROMPT.format(lid=lid_words, shape=size_for(width_mm, height_mm, round_lid)[1])


def framed(png: bytes, size: str) -> bytes:
    """[his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (3): "keeping its colours, gradients and shapes"] the lid stood
    square, resized to the image service's frame (``size``, "WxH") — sent filling it, so the redraw has no width or
    height of its own to fill and keeps the lid's layout: its fractions the lid's, as the map's are."""
    import cv2
    import numpy as np
    w, h = (int(v) for v in size.split("x"))
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    ok, buf = cv2.imencode(".png", cv2.resize(img, (w, h), interpolation=cv2.INTER_CUBIC))
    return buf.tobytes()


def _concept_sha(image) -> str:
    with image.image_file.open("rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


#: [His goal after the pitch page, 2026-10-15, A (3): "131 drawn landscape when the concept is portrait"] a kept redraw
#: made for a lid whose width-to-height differs from the lid drawn now by more than this share is another lid's art —
#: stretched onto this one it would distort; a redraw at this lid's proportion is made instead
KEPT_ART_ASPECT_TOLERANCE = 0.03


def kept_lid_art(image, product_mm: tuple | None = None) -> dict | None:
    """The lid's flat redraw kept on the concept, where it was made from THIS picture under THIS prompt; else None.
    [His goal after the pitch page, A (3)] and, where the lid's size now is given (``product_mm``, width and height),
    made for a lid of this proportion (``KEPT_ART_ASPECT_TOLERANCE``) — the size it was made for is on its record."""
    prov = image.reference_provenance if isinstance(image.reference_provenance, dict) else {}
    record = prov.get(LID_ART_KEY)
    if not isinstance(record, dict) or record.get("prompt_version") != LID_ART_PROMPT_VERSION:
        return None
    if record.get("concept_sha256") != _concept_sha(image):
        return None
    made_for = record.get("product_mm")
    if product_mm is not None and made_for:
        aspect_now = float(product_mm[0]) / float(product_mm[1])
        aspect_made = float(made_for[0]) / float(made_for[1])
        if abs(aspect_made / aspect_now - 1.0) > KEPT_ART_ASPECT_TOLERANCE:
            return None
    return record


def lid_art_bytes(record: dict) -> bytes:
    from django.core.files.storage import default_storage
    with default_storage.open(record["file"], "rb") as fh:
        return fh.read()


def make_lid_art(aria, image, lid: dict, product_mm: tuple, lid_words: str) -> dict:
    """The concept's lid redrawn once as flat artwork — a paid picture from the lid stood square (``lid``, a
    ``concept_outline.lid_picture`` record), on the ledger as "image:lid art:<direction>", its file and what it cost
    kept on the concept (``LID_ART_KEY``). A spending cap already reached refuses it before anything is paid."""
    import base64
    import time

    import openai
    from django.conf import settings
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    from django.utils import timezone

    from apps.pipeline.models import ApiCallRecord
    from apps.pipeline.services import cost_ledger
    from apps.pipeline.services.cost_ledger import provider_request_id, record_image
    if cost_ledger.daily_budget_exceeded():
        raise cost_ledger.BudgetExceededError("the day's spending cap is reached")
    cost_ledger.check_task_budget(aria.task)
    round_lid = lid["shape"] == "round"
    size, _shape = size_for(product_mm[0], product_mm[1], round_lid)
    prompt = prompt_for(lid_words, product_mm[0], product_mm[1], round_lid)
    sent = framed(lid["png"], size)
    started = time.monotonic()
    from apps.pipeline.services.cost_ledger import before_paid_call   # [his goal of 2026-10-13, (2)]
    before_paid_call("a picture", fidelity=True)   # [his goal for the pitch, B (6)] fidelity is paid for
    response = paid_operation(openai.images.edit, provider='openai', operation='lid_art', model=settings.IMAGE_MODEL, image=[("lid.png", sent, "image/png")],
                                  prompt=prompt, size=size, quality=settings.IMAGE_QUALITY_CONCEPTS, n=1, timeout=180)
    operation = LID_ART_OPERATION % image.direction_name
    try:
        record_image(settings.IMAGE_MODEL, operation=operation, image_count=1, task=aria.task,
                     metadata={"provider_request_id": provider_request_id(response),
                               "latency_ms": int((time.monotonic() - started) * 1000), "concept_image_id": image.pk})
    except cost_ledger.BudgetExceededError:
        raise
        aria.log("ARIA: the lid's flat redraw reached this design's spending cap — it is kept, it is paid for",
                 level="warning")
    row = ApiCallRecord.objects.filter(task=aria.task, operation=operation).order_by("-pk").first()
    art = base64.b64decode(response.data[0].b64_json)
    name = default_storage.save("concepts/task_%d_lid_art_%d.png" % (aria.task.pk, image.pk), ContentFile(art))
    record = {"state": REDRAWN, "file": name, "sha256": hashlib.sha256(art).hexdigest(), "size": size,
              "prompt_version": LID_ART_PROMPT_VERSION, "prompt": prompt, "lid_sha256": lid["lid_sha256"],
              "sent_sha256": hashlib.sha256(sent).hexdigest(),
              "concept_sha256": _concept_sha(image), "lid_shape": lid["shape"],
              "product_mm": [round(float(product_mm[0]), 3), round(float(product_mm[1]), 3)],
              "model": settings.IMAGE_MODEL, "cost_usd": str(row.cost_usd) if row is not None else "0",
              "at": timezone.now().isoformat(),
              "why": "his test blocker on design 124, (3): the illustration redrawn flat, then traced in colour"}
    prov = dict(image.reference_provenance or {})
    prov[LID_ART_KEY] = record
    image.reference_provenance = prov
    image.save(update_fields=["reference_provenance"])
    aria.log("ARIA: the lid's illustration redrawn flat for tracing — never printed — $%s" % record["cost_usd"])
    return record


def ensure_lid_art(aria, image, lid: dict, product_mm: tuple, lid_words: str) -> dict:
    """The lid's flat redraw: kept on the concept (nothing paid), else made now — ``{"state": REDRAWN, ...}`` — or
    ``{"state": REFUSED, "code", "why"}`` where it could not be made, said, never a drawing without it."""
    from apps.pipeline.services import cost_ledger
    kept = kept_lid_art(image, product_mm)        # [his goal after the pitch page, A (3)] made for this lid's proportion
    if kept is not None:
        aria.log("ARIA: the lid's flat redraw is on record for this concept — kept, nothing spent")
        return kept
    try:
        return make_lid_art(aria, image, lid, product_mm, lid_words)
    except cost_ledger.BudgetExceededError as exc:
        raise
        return {"state": REFUSED, "code": ART_NOT_MADE, "why": "the spending cap: %s" % exc}
    except Exception as exc:  # noqa: BLE001 — said by name, never drawn without
        if isinstance(exc, _RescueBudgetError):
            raise
        return {"state": REFUSED, "code": ART_NOT_MADE,
                "why": "the picture service could not make it just now (%s: %s)" % (type(exc).__name__, str(exc)[:160])}


# ------------------------------------------------------------------------------------------------------------ THE TRACE

def _lab(img):
    import cv2
    import numpy as np
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab[..., 0] *= 100.0 / 255.0
    lab[..., 1:] -= 128.0
    return lab


def _hex_of_lab(lab_px) -> str:
    import cv2
    import numpy as np
    px = np.uint8([[[np.clip(lab_px[0] * 2.55, 0, 255), np.clip(lab_px[1] + 128, 0, 255),
                     np.clip(lab_px[2] + 128, 0, 255)]]])
    b, g, r = cv2.cvtColor(px, cv2.COLOR_LAB2BGR)[0, 0]
    return "#%02X%02X%02X" % (int(r), int(g), int(b))


def fit_field(lab, ground, lid):
    """The sky's smooth colour field over the lid: the median of the sky's own pixels in each cell of TRACE["grid"]
    (a cell needs TRACE["cell_ground"] of its pixels sky), the cells the illustration covers filled from the
    neighbours that hold sky, read back at full size between the cells' centres (and past the outermost along their own
    slope). None where no cell holds sky."""
    import cv2
    import numpy as np
    h, w = ground.shape
    gh, gw = TRACE["grid"]
    cells = np.full((gh, gw, 3), np.nan, np.float32)
    for i in range(gh):
        for j in range(gw):
            y0, y1, x0, x1 = i * h // gh, (i + 1) * h // gh, j * w // gw, (j + 1) * w // gw
            m = ground[y0:y1, x0:x1] & lid[y0:y1, x0:x1]
            if m.sum() > TRACE["cell_ground"] * m.size:
                cells[i, j] = np.median(lab[y0:y1, x0:x1][m], axis=0)
    if np.isnan(cells[..., 0]).all():
        return None
    while np.isnan(cells[..., 0]).any():
        nxt = cells.copy()
        for i in range(gh):
            for j in range(gw):
                if np.isnan(cells[i, j, 0]):
                    near = [cells[a, b] for a, b in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1))
                            if 0 <= a < gh and 0 <= b < gw and not np.isnan(cells[a, b, 0])]
                    if near:
                        nxt[i, j] = np.mean(near, axis=0)
        cells = nxt
    # read back at full size between the cells' centres, and carried on past the outermost centres along their own slope
    # — a glow brightest at the lid's edge stays brightest there, never held at its last cell's middle
    def along(values, centres, at):
        out = np.interp(at, centres, values)
        lo, hi = at < centres[0], at > centres[-1]
        out[lo] = values[0] + (at[lo] - centres[0]) * (values[1] - values[0]) / (centres[1] - centres[0])
        out[hi] = values[-1] + (at[hi] - centres[-1]) * (values[-1] - values[-2]) / (centres[-1] - centres[-2])
        return out
    cy = (np.arange(gh) + 0.5) * h / gh
    cx = (np.arange(gw) + 0.5) * w / gw
    ys, xs = np.arange(h, dtype=np.float32), np.arange(w, dtype=np.float32)
    field = np.zeros((h, w, 3), np.float32)
    for ch in range(3):
        across = np.stack([along(cells[i, :, ch], cx, xs) for i in range(gh)])          # gh x w
        field[..., ch] = np.stack([along(across[:, j], cy, ys) for j in range(w)], axis=1)
    return field


def _sky(img, lab, lid, from_top=None):
    """``(the sky's mask, its field)``: seeded by a median of the picture read small (over TRACE["seed_share"] of its
    shorter side, so a glow at its edge is seen), fitted TRACE["fits"] times, and kept only where a patch of it is large
    or meets the lid's edge — a pale petal inside a flower is the flower's."""
    import cv2
    import numpy as np
    h, w = lid.shape
    small = cv2.resize(img, (max(8, w // 10), max(8, h // 10)), interpolation=cv2.INTER_AREA)
    k = max(3, (int(min(small.shape[:2]) * TRACE["seed_share"]) // 2) * 2 + 1)    # an odd median, a share of the lid
    seed = cv2.resize(cv2.medianBlur(small, k), (w, h), interpolation=cv2.INTER_CUBIC)
    ground = (np.linalg.norm(lab - _lab(seed), axis=2) < TRACE["ground_seed_de"]) & lid
    field = None
    for _ in range(TRACE["fits"]):
        field = fit_field(lab, ground, lid)
        if field is None:
            return None, None
        ground = (np.linalg.norm(lab - field, axis=2) < TRACE["ground_de"]) & lid
    count, labels, stats, _c = cv2.connectedComponentsWithStats(ground.astype(np.uint8), connectivity=8)
    edge = np.zeros_like(ground)
    edge[[0, -1], :] = True
    edge[:, [0, -1]] = True
    edge |= cv2.dilate((~lid).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    on_edge = set(np.unique(labels[edge & ground]).tolist())
    keep = np.zeros(count, bool)
    for k in range(1, count):
        keep[k] = stats[k, cv2.CC_STAT_AREA] >= TRACE["ground_min_share"] * lid.sum() or k in on_edge
    if TRACE.get("sky_from_top") if from_top is None else from_top:
        # [his goal for the pitch, 2026-10-15, A (4)] the sky is the ground the top of the scene opens into: a large flat
        # shape lying on its foot or its sides (131's dunes) is a shape, drawn crisp, never smoothed into the sky
        top = np.zeros_like(ground)
        rows = np.nonzero(lid.any(1))[0]
        if len(rows):
            top[rows[0]:rows[0] + max(2, h // 40), :] = True
        from_top = set(np.unique(labels[top & ground & lid]).tolist()) - {0}
        if from_top:
            keep = np.array([k in from_top for k in range(count)], bool)
    return keep[labels] & ground, field


def _rings(d: str, dx: float, dy: float, w: int, h: int) -> list:
    """A vtracer path's subpaths as rings of the lid's fractions: ``[[x, y], [x1, y1, x2, y2, x, y] | [x, y], …]``."""
    rings, ring, pen = [], None, None
    tokens = re.findall(r"[MLCZmlcz]|-?\d+(?:\.\d+)?", d)
    i, cmd = 0, None
    while i < len(tokens):
        t = tokens[i]
        if t.isalpha():
            cmd = t.upper()
            i += 1
            if cmd == "Z":
                if ring is not None and len(ring) > 2:
                    rings.append(ring)
                ring = None
            continue
        n = {"M": 2, "L": 2, "C": 6}[cmd]
        vals = [float(v) for v in tokens[i:i + n]]
        i += n
        pts = [((vals[k] + dx) / w, (vals[k + 1] + dy) / h) for k in range(0, n, 2)]
        if cmd == "M":
            if ring is not None and len(ring) > 2:
                rings.append(ring)
            ring = [[round(pts[0][0], 5), round(pts[0][1], 5)]]
            cmd = "L"
        elif ring is not None:
            ring.append([round(c, 5) for p in pts for c in p])
        pen = pts[-1]
    if ring is not None and len(ring) > 2:
        rings.append(ring)
    del pen
    return rings


#: [his goal of 2026-10-12, (8): "The arch's soft glow as the concept shows it."] the glow round the art's gold, read
#: from the redraw — which draws it, a white core and a teal light fading into the sky — and left out of the trace with
#: the sky it lies on: its colour band by band out from the gold (``bands``: each band's outer edge, a share of the
#: redraw's width), while a band stands at least ``min_de`` (CIE76) from the sky ``far`` from the gold
GLOW = {"version": "lid_glow/1.0", "bands": (0.002, 0.004, 0.0065, 0.0098, 0.0143, 0.0195), "far": (0.026, 0.039),
        "min_de": 8.0, "simplify_mm": 0.05}


def _ring_points(ring) -> list:
    """A traced ring's points (its segments' ends), in the redraw's shares."""
    return [tuple(ring[0][:2])] + [tuple(seg[-2:]) for seg in ring[1:]]


def glow_of(img, lab, regions: list, lines: list | None = None) -> dict | None:
    """``{"bands": [{"to", "hex", "de"}]}`` — the glow round the regions drawn in gold — [his goal of 2026-10-13, (7)]
    or round the gold lines found among them — band by band out from them, as the redraw prints it; None where the art
    draws no gold or no glow round it. The bands are the glow's colours read outward, drawn blended (``art_group``)."""
    import cv2
    import numpy as np
    from apps.pipeline.services.concept_design_map import is_gold_hex
    h, w = img.shape[:2]
    gold = np.zeros((h, w), np.uint8)
    for region in regions:
        if is_gold_hex(region["fill"]):
            for ring in region["rings"]:
                cv2.fillPoly(gold, [np.int32([[x * w, y * h] for x, y in _ring_points(ring)])], 1)
    for line in lines or []:
        if is_gold_hex(line["hex"]):
            cv2.polylines(gold, [np.int32([[x * w, y * h] for x, y in line["points"]])], False, 1,
                          max(1, int(round(line["width"] * w))))
    if not gold.any():
        return None
    dist = cv2.distanceTransform((1 - gold).astype(np.uint8), cv2.DIST_L2, 5)
    far = (dist > GLOW["far"][0] * w) & (dist < GLOW["far"][1] * w)
    if not far.any():
        return None
    sky = np.median(lab[far], axis=0)
    bands, inner = [], 0.0
    for outer in GLOW["bands"]:
        band = (dist >= inner * w) & (dist < outer * w)
        inner = outer
        if not band.any():
            continue
        de = float(np.linalg.norm(np.median(lab[band], axis=0) - sky))
        if de < GLOW["min_de"]:
            break
        px = np.median(img[band], axis=0)
        bands.append({"to": outer, "hex": "#%02X%02X%02X" % (int(px[2]), int(px[1]), int(px[0])), "de": round(de, 1)})
    return {"bands": bands} if bands else None


def trace_art(png: bytes, round_lid: bool, lines: bool = True, kinds=None) -> dict:
    """The redraw read into the lid's drawing, $0: ``{"schema_version", "state": TRACED, "params", "size_px",
    "sky": {"rows": [[hex] * stops] * bands}, "regions": [{"fill": hex, "rings": [...]}], "measured"}`` — the sky a
    fitted field drawn as gradients, the illustration's regions traced in colour, every region whose pixels are mostly
    sky left out; REFUSED, by name, where the picture does not open or holds no sky to fit."""
    import cv2
    import numpy as np
    import vtracer
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR) if png else None
    rec = {"schema_version": LID_ART_TRACE_KEY, "params": dict(TRACE, grid=list(TRACE["grid"])),
           "source_sha256": hashlib.sha256(png).hexdigest() if png else None}
    if img is None:
        return {**rec, "state": REFUSED, "code": ART_NOT_TRACED, "why": "the redraw could not be opened"}
    h, w = img.shape[:2]
    lid = np.ones((h, w), bool)
    if round_lid:
        lid = np.zeros((h, w), np.uint8)
        cv2.circle(lid, (w // 2, h // 2), min(w, h) // 2, 1, -1)
        lid = lid.astype(bool)
    lab = _lab(img)
    sky, field = _sky(img, lab, lid, from_top=False)
    if field is None:
        return {**rec, "state": REFUSED, "code": ART_NOT_TRACED, "why": "no sky the illustration stands on to fit"}
    if TRACE.get("sky_from_top") and float(sky[lid].mean()) > TRACE["sky_swallows"]:
        # [his goal for the pitch, A (4)] a sky that has swallowed nearly the whole scene has taken its large flat shapes
        # with it (131's dunes, 91 %): the sky is then only what the top of the scene opens into
        top_sky, top_field = _sky(img, lab, lid, from_top=True)
        if top_field is not None:
            sky, field = top_sky, top_field
    speckle = max(4, int(round(TRACE["speckle_px"] * max(w, h) / 1536.0)))
    ok, buf = cv2.imencode(".png", img)
    svg = vtracer.convert_raw_image_to_svg(buf.tobytes(), img_format="png", colormode="color", hierarchical="cutout",
                                            mode="spline", filter_speckle=speckle,
                                            color_precision=TRACE["colour_precision"],
                                            layer_difference=TRACE["layer_difference"],
                                            corner_threshold=TRACE["corner_threshold"],
                                            length_threshold=TRACE["length_threshold"],
                                            splice_threshold=TRACE["splice_threshold"],
                                            path_precision=TRACE["path_precision"])
    q = TRACE["read_scale"]
    sky_small = cv2.resize(sky.astype(np.uint8), (w // q + 1, h // q + 1), interpolation=cv2.INTER_NEAREST).astype(bool)
    lid_small = cv2.resize(lid.astype(np.uint8), (w // q + 1, h // q + 1), interpolation=cv2.INTER_NEAREST).astype(bool)
    regions, left_sky, left_outside = [], 0, 0
    for d, fill, tx, ty in re.findall(
            r'<path d="([^"]+)" fill="(#[0-9A-Fa-f]{6})"(?: transform="translate\(([-\d.]+),([-\d.]+)\)")?', svg):
        dx, dy = (float(tx), float(ty)) if tx else (0.0, 0.0)
        canvas = np.zeros(sky_small.shape, np.uint8)
        for sub in re.split(r"(?=M)", d):
            nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", sub)]
            if len(nums) < 6:
                continue
            layer = np.zeros_like(canvas)
            cv2.fillPoly(layer, [np.int32([[(x + dx) / q, (y + dy) / q] for x, y in zip(nums[0::2], nums[1::2])])], 1)
            canvas ^= layer
        inside = canvas.astype(bool)
        if not inside.any():
            continue
        if (~lid_small[inside]).mean() > 0.5:
            left_outside += 1
            continue
        if sky_small[inside].mean() > TRACE["region_ground_share"]:
            left_sky += 1
            continue
        rings = _rings(d, dx, dy, w, h)
        if rings:
            regions.append({"fill": fill.upper(), "rings": rings})
    bands, stops = TRACE["bands"], TRACE["stops"]
    rows = []
    for i in range(bands):
        y = min(h - 1, int((i + 0.5) * h / bands))
        rows.append([_hex_of_lab(field[y, min(w - 1, int(k * (w - 1) / (stops - 1)))]) for k in range(stops)])
    # the sky's own pixels against the field drawn for them: how far the drawn gradients stand from the redraw
    de = np.linalg.norm(lab[sky] - field[sky], axis=1) if sky.any() else np.zeros(1)
    measured = {"sky_share": round(float(sky[lid].mean()), 3), "sky_de_median": round(float(np.median(de)), 2),
                "sky_de_p95": round(float(np.percentile(de, 95)), 2), "regions": len(regions),
                "left_out_as_sky": left_sky, "left_out_outside": left_outside}
    # [His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (7): "Geometric shapes are DRAWN, not traced"] the line art
    # of its regions — 124's gilded arch — found and drawn as the lines they are; the regions they replace left out
    from apps.pipeline.services import line_geometry as _lg
    found = _lg.find({"size_px": [int(w), int(h)], "regions": regions}, _ring_points, kinds=kinds) if lines else {
        "lines": []}
    lines = found["lines"]
    if lines:
        gone = set(found["replaced"])
        regions = [r for j, r in enumerate(regions) if j not in gone]
        measured["regions"] = len(regions)
        measured["lines"] = len(lines)
        measured["line_regions_replaced"] = len(gone)
    glow = glow_of(img, lab, regions, lines=lines)   # [his goal of 2026-10-12, (8)] the arch's glow, as drawn
    if lines and glow:
        # [his goal of 2026-10-13, (8)] the glow's own pieces the trace cut — flat rings of its colours round the line,
        # drawn over its smooth mesh: 124's glow still stepped from one to the next — left out
        drop = set(_lg.glow_pieces({"size_px": [int(w), int(h)], "regions": regions}, _ring_points, lines,
                                   glow["bands"]))
        if drop:
            regions = [r for j, r in enumerate(regions) if j not in drop]
            measured["regions"] = len(regions)
            measured["glow_regions_replaced"] = len(drop)
    return {**rec, "state": TRACED, "size_px": [int(w), int(h)], "round": bool(round_lid), "sky": {"rows": rows},
            "regions": regions, "measured": measured, **({"glow": glow} if glow else {}),
            **({"lines": lines, "geometry": found["params"]} if lines else {})}


def on_lid(trace: dict, x: float, y: float, w: float, h: float) -> tuple:
    """``(x, y, w, h, stretch)`` the art is drawn at on the lid's ``w`` x ``h`` mm at (x, y): FILLING it — the redraw
    made from the lid filling the service's frame (``framed``), a part at a fraction of the lid stands at that fraction
    of the art, as the map's parts are placed; ``stretch`` how much wider than tall it is drawn than it was redrawn (1.0
    none). It replaces covering the lid (scaled alike both ways, its overflow cut), which stood 124's scene 5 % off at
    its top and foot."""
    aw, ah = trace["size_px"]
    return float(x), float(y), float(w), float(h), round((float(w) / aw) / (float(h) / ah), 4)


def registration(art_png: bytes, lid_png: bytes, parts: list, round_lid: bool) -> dict:
    """[his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (2): "self-check", and (4): "if a part can't be drawn, stop
    and tell me which part and why"] the redraw laid on the lid as it is drawn (``on_lid``) checked against the lid's
    map (``parts``, its boxes fractions of the lid stood square), part by part, at $0 (REGISTER): each line of type and
    the mark on the ground the concept prints it on, each illustration drawn where the concept draws it —
    ``{"schema_version", "params", "state": REGISTERED, "boxes": {name: {"kind", "art", "concept"}}}``, or REFUSED by
    name, ``"parts": [{"kind", "name", "why"}]``, never drawn misplaced."""
    import cv2
    import numpy as np
    rec = {"schema_version": LID_ART_REGISTER_KEY, "params": dict(REGISTER), "boxes": {}}
    art = cv2.imdecode(np.frombuffer(art_png, np.uint8), cv2.IMREAD_COLOR) if art_png else None
    lid = cv2.imdecode(np.frombuffer(lid_png, np.uint8), cv2.IMREAD_COLOR) if lid_png else None
    if art is None or lid is None:
        return {**rec, "state": REFUSED, "code": ART_NOT_REGISTERED, "parts": [],
                "why": "the redraw or the lid could not be opened to be checked"}
    h, w = art.shape[:2]
    lid = cv2.resize(lid, (w, h), interpolation=cv2.INTER_AREA)
    inside = np.ones((h, w), bool)
    if round_lid:
        rim = np.zeros((h, w), np.uint8)
        cv2.circle(rim, (w // 2, h // 2), min(w, h) // 2, 1, -1)
        inside = rim.astype(bool)
    k = max(3, int(round(REGISTER["stroke_share"] * max(w, h))) | 1)
    opened = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))

    def illustration(img):
        # the check reads the ground as it always did — every large or edge-touching patch of it, never only the top's
        sky, field = _sky(img, _lab(img), inside, from_top=False)
        if field is None:
            return None
        return cv2.morphologyEx((~sky & inside).astype(np.uint8), cv2.MORPH_OPEN, opened).astype(bool)

    drawn, concept = illustration(art), illustration(lid)
    if drawn is None or concept is None:
        return {**rec, "state": REFUSED, "code": ART_NOT_REGISTERED, "parts": [],
                "why": "no ground to tell the illustration from, in the redraw or the lid"}
    off = []
    for p in parts:
        if p.get("kind") not in ("type", "mark", "illustration") or not p.get("box"):
            continue
        x0, y0, x1, y1 = (min(max(float(v), 0.0), 1.0) for v in p["box"])
        rows = slice(int(y0 * h), max(int(y0 * h) + 1, int(y1 * h)))
        cols = slice(int(x0 * w), max(int(x0 * w) + 1, int(x1 * w)))
        a, c = float(drawn[rows, cols].mean()), float(concept[rows, cols].mean())
        rec["boxes"][p["name"]] = {"kind": p["kind"], "art": round(a, 3), "concept": round(c, 3)}
        if p["kind"] in ("type", "mark") and a > c + REGISTER["on_ground"]:
            off.append({"kind": p["kind"], "name": p["name"],
                        "why": "the redraw grows its illustration under it (%d %% of its box, the concept %d %%) — it "
                               "would print over flowers the concept keeps clear" % (round(100 * a), round(100 * c))})
        if p["kind"] == "illustration" and a < REGISTER["drawn_share"] * c:
            off.append({"kind": p["kind"], "name": p["name"],
                        "why": "the redraw draws %d %% of its box, the concept %d %% — it is not where the concept "
                               "draws it" % (round(100 * a), round(100 * c))})
    if off:
        return {**rec, "state": REFUSED, "code": ART_NOT_REGISTERED, "parts": off,
                "why": "the flat redraw does not stand where the concept does: " + "; ".join(
                    "%s %r — %s" % (o["kind"], o["name"], o["why"]) for o in off)}
    return {**rec, "state": REGISTERED, "parts": []}


#: [his review of 127-132, 2026-10-15, C (4)] a traced shape inside a box the map reads a line of type or the mark in —
#: padded by this share of the box's own height — is left out: the words are set live there, never traced twice
WORDS_PAD = 1.0
#: [his word of 2026-10-17 on 142] a line standing this much taller than wide is set up the side: padded by this share
#: of its own thickness; and a shape more than LETTER_ACROSS times a line's thickness across it is no letter of it
TURNED_ASPECT = 1.5
WORDS_PAD_TURNED = 0.4
LETTER_ACROSS = 1.4
#: a traced region within this (CIE76) of a line's ink is that line's lettering; farther, a motif of its own
WORDS_INK_DE = 25.0
#: … or one on the way from its ground to its ink, at least this share of the way (a letter's blended edge)
WORDS_MIX_LEAST = 0.2
#: … or a patch of its own ground's colour within this (a letter's counter, traced apart)
WORDS_GROUND_DE = 10.0
#: a painted-out letter's own stroke, in its ground's colour, a share of the art's width
WORDS_PAINT_EDGE = 0.012


def _ring_box(rings) -> tuple:
    xs, ys = [], []
    for ring in rings:
        xs.append(ring[0][0]); ys.append(ring[0][1])
        for seg in ring[1:]:
            xs += seg[0::2]; ys += seg[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def _between(hx: str, ground: str, ink: str) -> bool:
    """True where ``hx`` lies on the way from ``ground`` through ``ink`` (CIE L*a*b*): within WORDS_INK_DE of that ray,
    past WORDS_MIX_LEAST of the way from the ground — a letter's edge blended into its ground, or the letter itself
    where the read's ink is muddier than its print (138's near-white capitals read #9F9B98) — never a colour of its
    own."""
    import numpy as np

    from apps.ire.legibility import to_lab
    p, g, k = (np.array(to_lab(v), float) for v in (hx, ground, ink))
    seg = k - g
    t = float(np.dot(p - g, seg) / max(float(np.dot(seg, seg)), 1e-9))
    near = float(np.linalg.norm(p - (g + max(0.0, t) * seg)))
    return t >= WORDS_MIX_LEAST and near <= WORDS_INK_DE


def _rings_area(rings) -> float:
    """The area a region's rings enclose, each by its end points (shoelace), holes and all counted as drawn even-odd."""
    total = 0.0
    for ring in rings or []:
        pts = [ring[0]] + [seg[-2:] for seg in ring[1:]]
        a = 0.0
        for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
            a += float(x0) * float(y1) - float(x1) * float(y0)
        total += abs(a) / 2.0
    return total


def _inked_ring(region: dict, ring, lettering, grounds) -> bool:
    """Whether one ring of ``region`` is a letter's: inside a line's padded box in its ink (``lettering`` read on the
    ring's own box) — never a ring of a box's own ground colour (its hole, closed apart)."""
    from apps.ire.legibility import colour_distance
    if region.get("fill") and any(g is not None and colour_distance(region["fill"], g) <= WORDS_GROUND_DE
                                  for g in grounds):
        return False
    return lettering(region, _ring_box([ring]))


def without_words(trace: dict, boxes: list, inks: list | None = None) -> dict:
    """[His review of 127-132, C (4): the first brand-new brief, 134, printed "MIDNIGHT FIG" and "EAU DE PARFUM" twice —
    its flat redraw kept the photo's lettering, and the live type was set over it] ``trace`` with every traced region
    that lies wholly inside a box of type or of the mark (``boxes``, shares of the art's frame, padded by WORDS_PAD) AND
    is filled in that line's own ink (``inks``, parallel to ``boxes``: within WORDS_INK_DE, CIE76) left out — the
    redraw's lettering, never a motif of another colour standing inside the line's box, never a traced light line —
    what was left out counted on the trace. A box with no ink read leaves out only what lies inside it unpadded."""
    from apps.ire.legibility import colour_distance
    inks = list(inks) if inks is not None else [None] * len(boxes)
    # [his word of 2026-10-17 on 142: lips and cherries "traced whole and clean, never broken outlines"] a line set up
    # the side (its box standing taller than wide in the art's own pixels) is as thick as its box is wide: padded by
    # WORDS_PAD_TURNED of that, never by its long side — 142's tall name box, padded by its own height, took the lips'
    # and cherries' cream outlines for its letters
    size = trace.get("size_px") or [1, 1]
    aw, ah = float(size[0]), float(size[1])
    padded, thick = [], []
    for b, ink in zip(boxes, inks):
        x0, y0, x1, y1 = (float(v) for v in b)
        turned = (y1 - y0) * ah > TURNED_ASPECT * (x1 - x0) * aw
        px = py = WORDS_PAD * (y1 - y0)
        if turned:
            px, py = WORDS_PAD_TURNED * (x1 - x0), WORDS_PAD_TURNED * (x1 - x0) * aw / ah
        if ink is None:
            px, py = 0.0, 0.0
        padded.append(((x0 - px, y0 - py, x1 + px, y1 + py), ink))
        thick.append((turned, (x1 - x0) if turned else (y1 - y0)))

    # the ground each box's lettering stands on: the fill of the region covering the most of the art (its rings' own
    # area, never its box — a flat trace's region is every patch of its colour, its box the whole face) holding the box
    sized = sorted(((r, _ring_box(r["rings"])) for r in trace.get("regions") or [] if r.get("rings") and r.get("fill")),
                   key=lambda rb: -_rings_area(rb[0]["rings"]))

    sky = (trace.get("sky") or {}).get("rows") or []

    def ground_of(q):
        # the box as it lies on the art (a padded box may run past its edges)
        q = (max(0.0, q[0]), max(0.0, q[1]), min(1.0, q[2]), min(1.0, q[3]))
        for r, bx in sized:
            if bx[0] <= q[0] and bx[1] <= q[1] and bx[2] >= q[2] and bx[3] >= q[3]:
                return r["fill"]
        if sky and sky[0]:
            # [his goal after the pitch page, B (11): the blush's lid, its ground a smooth sky, its redraw's "CORAL HAZE"
            # left in fragments] a lid's ground is its sky at the box's middle
            cx, cy = (q[0] + q[2]) / 2.0, (q[1] + q[3]) / 2.0
            row = sky[min(len(sky) - 1, max(0, int(cy * len(sky))))]
            return row[min(len(row) - 1, max(0, int(cx * len(row))))]
        return None
    grounds = [ground_of(q) for q, _ink in padded]
    # which grounds are a traced region's (a flat colour a letter can be painted out in) and not a sky's (a smooth field
    # a letter is simply left out of)
    flat_grounds = {r["fill"] for r, _bx in sized}

    def painted_ground(bx):
        for (q, _ink), ground in zip(padded, grounds):
            if bx[0] >= q[0] and bx[1] >= q[1] and bx[2] <= q[2] and bx[3] <= q[3] and ground in flat_grounds:
                return ground
        return None

    def lettering(region, bx=None):
        bx = _ring_box(region["rings"]) if bx is None else bx
        for (q, ink), ground, (turned, line) in zip(padded, grounds, thick):
            # a shape far thicker across the line than the line itself (a motif's outline) is no letter of it
            if turned and (bx[2] - bx[0]) > LETTER_ACROSS * line:
                continue
            if bx[0] >= q[0] and bx[1] >= q[1] and bx[2] <= q[2] and bx[3] <= q[3]:
                if ink is None or not region.get("fill"):
                    return True
                # [his last goal before the pitch, Step 2, 139: its "Comfort" ghosted behind the live name — the map read
                # its ink as the dipper's tan, its letters brown] a box may name both inks, the read's and the traced
                # letters' own
                for one in ((ink,) if isinstance(ink, str) else tuple(ink)):
                    if colour_distance(region["fill"], one) <= WORDS_INK_DE or (
                            ground is not None and region["fill"] != ground and (
                                _between(region["fill"], ground, one)
                                or colour_distance(region["fill"], ground) <= WORDS_GROUND_DE)):
                        return True
        return False
    # [his last goal before the pitch, Step 2, 127: its redraw's "FO" left over its live name — letters touching the
    # face's edge are bays in its ground's outline, not holes] a letter left out is painted in the ground it stands on,
    # where that is a traced region's flat colour — its hole, its bay and its counter alike; else left out
    regions, gone = [], 0
    for r in trace.get("regions") or []:
        if r.get("rings") and lettering(r):
            gone += 1
            ground = painted_ground(_ring_box(r["rings"]))
            if ground is not None:
                regions.append(dict(r, fill=ground, painted_out=True))
            continue
        regions.append(r)
    # [his last goal before the pitch, Step 2, 127: its redraw's "FO" printed over the live name] a flat trace keeps
    # every patch of one colour in one region — a letter and a patch far from it one region, its box the whole face —
    # so each of its rings is read on its own: a letter's ring inside a line's box, in its ink, is left out, the
    # region's other rings kept (a ring of the box's own ground is a hole, closed below)
    split = []
    for r in regions:
        rings = r.get("rings") or []
        if len(rings) < 2:
            split.append(r)
            continue
        if r.get("painted_out"):
            split.append(r)
            continue
        out_rings = [ring for ring in rings if _inked_ring(r, ring, lettering, grounds)]
        keep_rings = [ring for ring in rings if not any(ring is o for o in out_rings)]
        gone += len(out_rings)
        if keep_rings:
            split.append(dict(r, rings=keep_rings) if out_rings else r)
        for ring in out_rings:
            ground = painted_ground(_ring_box([ring]))
            if ground is not None:
                split.append(dict(r, rings=[ring], fill=ground, painted_out=True))
    regions = split
    if not gone:
        return trace

    kept_boxes = [_ring_box(r["rings"][:1]) for r in regions if r.get("rings")]

    def inside_a_box(ring):
        # a hole inside a line's padded box that no kept region fills — a left-out letter's — never a kept motif's
        bx = _ring_box([ring])
        if not any(bx[0] >= q[0] and bx[1] >= q[1] and bx[2] <= q[2] and bx[3] <= q[3] for q, _ink in padded):
            return False
        return not any(k[0] < bx[2] and bx[0] < k[2] and k[1] < bx[3] and bx[1] < k[3]
                       and (k[2] - k[0]) * (k[3] - k[1]) < (bx[2] - bx[0]) * (bx[3] - bx[1]) * 4.0
                       for k in kept_boxes)
    # [his last goal before the pitch, Step 2, 139: "no duplicate or ghost text" — the face's yellow ground kept the
    # letters cut out of it as holes, and the body's own yellow showed through them, a ghost of the name] where the
    # lettering is left out, the holes it leaves in the region round it are closed
    closed = []
    for r in regions:
        rings = r.get("rings") or []
        kept = rings[:1] + [ring for ring in rings[1:] if not inside_a_box(ring)]
        closed.append(dict(r, rings=kept) if len(kept) != len(rings) else r)
    return dict(trace, regions=closed, words_left_out=gone)


def textured_boxes(parts: list) -> list:
    """[His review of 127-132, C (5)] the boxes of the parts the map reads with a printed grain or speckle."""
    return [p["box"] for p in parts or [] if p.get("texture") in ("grain", "speckle") and p.get("box")]


def art_group(trace: dict, x: float, y: float, w: float, h: float, clip: list | None = None, *, prefix: str = "lid",
              name: str = "LID ART", ground: bool = True):
    """The traced lid drawn filling the lid at (x, y) mm, ``w`` x ``h`` mm (``on_lid``): its sky's bands (each a
    left-to-right gradient, overlapping the next a little so no seam shows), then its illustration's regions — every
    node vector, editable; the whole clipped to the lid's own outline (``clip``)."""
    from apps.ire.graph import (ClosePath, Color, CubicTo, GradientFill, GradientStop, Group, LineTo, MeshFill, MoveTo,
                                Path, Rect, SolidFill, Stroke)
    x, y, w, h, _stretch = on_lid(trace, x, y, w, h)
    # [His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (9): "Gradients are smooth, never flat bands (124's sky shows
    # stripes)."] the sky ONE smooth mesh over the lid — its fitted field's own colours at the corners of SKY_MESH's
    # patches, blended between them by the reader — never 96 stacked bands
    bands = [Path(name="%s-sky" % prefix, segments=[MoveTo(x=x, y=y), LineTo(x=x + w, y=y), LineTo(x=x + w, y=y + h),
                                                     LineTo(x=x, y=y + h), ClosePath()],
                  fill=MeshFill(patches=sky_patches(trace, x, y, w, h), grid=sky_grid(trace, x, y, w, h)))] \
        if ground else []
    paths = []
    for j, region in enumerate(trace["regions"]):
        segs = []
        for ring in region["rings"]:
            segs.append(MoveTo(x=x + ring[0][0] * w, y=y + ring[0][1] * h))
            for seg in ring[1:]:
                if len(seg) == 6:
                    segs.append(CubicTo(x1=x + seg[0] * w, y1=y + seg[1] * h, x2=x + seg[2] * w, y2=y + seg[3] * h,
                                        x=x + seg[4] * w, y=y + seg[5] * h))
                else:
                    segs.append(LineTo(x=x + seg[0] * w, y=y + seg[1] * h))
            segs.append(ClosePath())
        # [his last goal before the pitch, Step 2, 127] a letter painted out in its ground also stroked in it, the hair
        # between its edge and its ground's never showing what lies beneath
        edge = ({"stroke": Stroke(color=Color.from_hex(region["fill"]), width_mm=WORDS_PAINT_EDGE * w)}
                if region.get("painted_out") else {})
        paths.append(Path(name="%s-art-%d" % (prefix, j), segments=segs, fill_rule="evenodd",
                          fill=SolidFill(color=Color.from_hex(region["fill"])), **edge))
    # [his goal of 2026-10-12, (8)] the glow round the gold, under the illustration — [his goal of 2026-10-13, (8): "Glow
    # is a real soft blur, never a stack of hard bands"] round each gold line a smooth mesh from the glow's colours out
    # to the sky's own; round traced gold (no line found) its bands as before
    glows = _glow_meshes(trace, x, y, w, h, prefix) if trace.get("lines") else _glow_paths(trace, x, y, w, h, prefix)
    # [his goal of 2026-10-13, (7)] each line found drawn as the line it is: one clean curve, one even stroke, its ink
    from apps.pipeline.services import line_geometry as _lg
    strokes = [Path(name="%s-line-%d" % (prefix, j), segments=_lg.segments(line, x, y, w, h),
                    stroke=Stroke(color=Color.from_hex(line["hex"]),
                                  width_mm=max(0.1, float(line.get("drawn_width") or line["width"]) * w)))
               for j, line in enumerate(trace.get("lines") or [])]

    # [his review of 127-132, 2026-10-15, C (5)] the print's own grain over its art, where its map reads one
    from apps.ire import grain as _grain
    grains = _grain.paths(trace["grain"], x, y, w, h, prefix) if trace.get("grain") else []
    # [his goal of 2026-10-12, (12)] ``prefix`` and ``name`` — the inside of the lid's own, never the lid's
    # [his goal for the pitch, 2026-10-15, A (4)] a motif's art (``ground`` False) is drawn over the product's own
    # ground, never its redraw's: its regions only, the ground beneath showing between them
    return Group(name=name, role="decoration", clip=clip,
                 children=([Group(name="%s-sky" % prefix, role="generic", children=bands)] if ground else [])
                 + ([Group(name="%s-glow" % prefix, role="decoration", children=glows)] if glows else [])
                 + ([Group(name="%s-lines" % prefix, role="decoration", children=strokes)] if strokes else [])
                 + [Group(name="%s-illustration" % prefix, role="generic", children=paths)]
                 + ([Group(name="%s-grain" % prefix, role="decoration", children=grains)] if grains else []))


#: [his goal of 2026-10-13, (9)] the sky's mesh: its fitted field read at the corners of COLS x ROWS patches
SKY_MESH = {"version": "sky_mesh/1.0", "cols": 24, "rows": 16}


def sky_at(trace: dict):
    """The sky's own colour at any point of the art (its shares across and down), read between the field's sampled grid
    (``trace["sky"]["rows"]``) — bilinear, as the mesh blends it."""
    import numpy as np
    rows = trace["sky"]["rows"]
    grid = np.array([[[int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)] for c in row] for row in rows], float)
    nr, nc = grid.shape[:2]

    def at(fx, fy):
        gx = min(max(fx, 0.0), 1.0) * (nc - 1)
        gy = min(max(fy * nr - 0.5, 0.0), nr - 1)
        x0, y0 = int(gx), int(gy)
        x1, y1 = min(x0 + 1, nc - 1), min(y0 + 1, nr - 1)
        tx, ty = gx - x0, gy - y0
        v = (grid[y0, x0] * (1 - tx) * (1 - ty) + grid[y0, x1] * tx * (1 - ty) + grid[y1, x0] * (1 - tx) * ty
             + grid[y1, x1] * tx * ty)
        return "#%02X%02X%02X" % tuple(int(round(c)) for c in v)
    return at


def sky_grid(trace: dict, x: float, y: float, w: float, h: float) -> dict:
    """The sky as SKY_MESH's corners over the art at (x, y), ``w`` x ``h`` mm — each the field's own colour
    (``graph.MeshFill.grid``: the layered file's thin strips are read from it)."""
    at = sky_at(trace)
    cols, nrows = SKY_MESH["cols"], SKY_MESH["rows"]
    xs = [x + w * i / cols for i in range(cols + 1)]
    ys = [y + h * j / nrows for j in range(nrows + 1)]
    return {"xs": [round(v, 3) for v in xs], "ys": [round(v, 3) for v in ys],
            "inks": [[at(i / cols, j / nrows) for i in range(cols + 1)] for j in range(nrows + 1)]}


def sky_patches(trace: dict, x: float, y: float, w: float, h: float) -> list:
    """The sky as SKY_MESH's patches over the art at (x, y), ``w`` x ``h`` mm — each corner the field's own colour."""
    from apps.pipeline.services import line_geometry as _lg
    return _lg.patches_of_grid(sky_grid(trace, x, y, w, h))


def _glow_meshes(trace: dict, x: float, y: float, w: float, h: float, prefix: str = "lid") -> list:
    """[His goal of 2026-10-13, (8).] The glow round each gold line found: one smooth mesh from the stroke's edge out
    through the redraw's glow colours, fading to nothing over the sky drawn beneath it (``line_geometry.glow_parts``)
    — never hard bands."""
    glow = trace.get("glow")
    if not glow or not glow.get("bands"):
        return []
    from apps.ire.graph import ClosePath, LineTo, MeshFill, MoveTo, Path
    from apps.pipeline.services.concept_design_map import is_gold_hex

    from apps.pipeline.services import line_geometry as _lg
    out = []
    for j, line in enumerate(trace.get("lines") or []):
        if not is_gold_hex(line["hex"]):
            continue
        parts = _lg.glow_parts(line, x, y, w, h, glow["bands"])
        for n, part in enumerate(parts):
            x0, y0, x1, y1 = part["box"]
            out.append(Path(name="%s-glow-%d" % (prefix, j) + ("-%d" % n if len(parts) > 1 else ""),
                            fill=MeshFill(patches=part["patches"], alphas=part["alphas"], blur=part["blur"]),
                            segments=[MoveTo(x=x0, y=y0), LineTo(x=x1, y=y0), LineTo(x=x1, y=y1), LineTo(x=x0, y=y1),
                                      ClosePath()]))
    return out


def _glow_paths(trace: dict, x: float, y: float, w: float, h: float, prefix: str = "lid") -> list:
    """The glow's bands as filled paths on the lid at (x, y), ``w`` x ``h`` mm: the gold regions' union grown by each
    band's reach (round, never spiked at the arch's tip), outermost first."""
    glow = trace.get("glow")
    if not glow:
        return []
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    from apps.ire.graph import ClosePath, Color, LineTo, MoveTo, Path, SolidFill
    from apps.pipeline.services.concept_design_map import is_gold_hex
    polys = []
    for region in trace["regions"]:
        if is_gold_hex(region["fill"]):
            for ring in region["rings"]:
                pts = [(x + px * w, y + py * h) for px, py in _ring_points(ring)]
                if len(pts) >= 3:
                    poly = Polygon(pts).buffer(0)
                    if not poly.is_empty:
                        polys.append(poly)
    if not polys:
        return []
    gold = unary_union(polys)
    out = []
    for k in range(len(glow["bands"]) - 1, -1, -1):
        band = glow["bands"][k]
        shape = gold.buffer(band["to"] * w).simplify(GLOW["simplify_mm"])
        segs = []
        for part in getattr(shape, "geoms", [shape]):
            for ring in [part.exterior] + list(part.interiors):
                pts = list(ring.coords)
                segs.append(MoveTo(x=pts[0][0], y=pts[0][1]))
                segs.extend(LineTo(x=px, y=py) for px, py in pts[1:])
                segs.append(ClosePath())
        out.append(Path(name="%s-glow-%d" % (prefix, k), segments=segs, fill_rule="evenodd",
                        fill=SolidFill(color=Color.from_hex(band["hex"]))))
    return out
