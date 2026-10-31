"""PACKAGING target — wraps today's behavior EXACTLY (Phase A).

Its structural backbone is the deterministic dieline engine. This strategy
delegates to the existing ARIA orchestration (dieline dimension estimate,
dimension gate, deterministic geometry, IRE export) so the refactor is
invisible: the packaging flow behaves bit-for-bit as before, now reached
through the target seam instead of a hardcoded branch.
"""
from __future__ import annotations

from apps.pipeline.targets.base import DesignTarget, TargetStrategy
from apps.pipeline.targets.container import MAP_ALONE


#: [his go of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a18911a): "build the map path to run on its own for
#: every new design, for a wand vial and a carton"] how a carton's concept is pictured so its design map can read its
#: front: the map cuts one standing product from a plain ground, and none of the editorial carton packshots on record
#: could be cut (tasks 28, 32 and 33: a cream carton on a cream ground beside a petal, one seen from above three-quarters)
CARTON_MAP_DIRECTIVE = (
    "Picture the carton as a clean studio packshot made to be traced: standing upright with its FRONT panel square to "
    "the camera — straight-on, no perspective on the front, at most a narrow sliver of one side and none of its top — "
    "the whole carton in frame with clear space around it, on a plain seamless ground in a tone clearly lighter or "
    "darker than the carton, with nothing in front of it, touching it or overlapping it. The carton's drawing is made "
    "from its front exactly as pictured. " + MAP_ALONE)


def read_carton_map(aria, approved_image) -> dict | None:
    """[The owner's finding on design 119, 2026-10-03 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 32898c7).] A carton's
    approved concept's design map, read by its front panel: kept from this design's earlier output where one READ this
    picture so (``concept_design_map.held_carton_parts``: nothing paid), else read now
    (``concept_design_map.read_carton_parts``: one vision call on this design's ledger). None, said in the design's log,
    where it is not read (``targets.container.map_read_refused``) or the read itself takes the design past its cap."""
    from apps.pipeline.services import concept_design_map as dm
    from apps.pipeline.services import cost_ledger
    from apps.pipeline.targets.container import _concept_bytes, map_read_refused
    pic = _concept_bytes(approved_image)
    # [the owner's finding on design 119, 2026-10-03] … or on the picture itself, where a stop kept it
    kept = [(approved_image.reference_provenance or {}).get(dm.SCHEMA)]
    kept += [(earlier.spec_sheet or {}).get(dm.SCHEMA)
             for earlier in aria.task.packaging_outputs.exclude(spec_sheet=None).order_by("-pk")]
    for rec in kept:
        held = dm.held_carton_parts(rec, pic)
        if held is not None:
            aria.log("ARIA: the carton's design map is on record for this picture — kept, nothing spent")
            return held
    why = map_read_refused(aria.task, pic)
    if why:
        aria.log("ARIA: the carton's design map was not read — %s" % why, level="warning")
        return None
    try:
        rec = dm.read_carton_parts(aria.task, pic)
    except cost_ledger.BudgetExceededError:
        raise
        aria.log("ARIA: the carton's design map was read, and the read took this design past its spending cap — its "
                 "parts were not kept", level="warning")
        return None
    if rec["state"] != dm.MAP_READ:
        aria.log("ARIA: the carton's design map could not be read — %s ($%s on this design's ledger)"
                 % (rec["detail"], rec["cost"]["usd"]), level="warning")
        return rec
    aria.log("ARIA: the carton's design map read by its front panel — %d parts named, $%s on this design's ledger%s"
             % (len(rec["parts"]), rec["cost"]["usd"],
                ("; " + "; ".join(rec["problems"][:3])) if rec["problems"] else ""))
    return rec


#: [his review of 119, 2026-10-05, point 6: "Back-panel Arabic: where my brief gives the Arabic, use my words exactly
#: (with the shadda). The rest is translation: show it as 'Not confirmed yet' beside Approve until I confirm it."] the
#: label's translations, written by the system's translation and confirmed by nobody yet — and his confirmation, kept
#: with a hash of exactly the words he confirmed, so words that change are not confirmed again until he says so
TRANSLATION_UNCONFIRMED = "CARTON_TRANSLATION_UNCONFIRMED"
TRANSLATIONS_CONFIRMED_KEY = "translations_confirmed/1.0"
LANGUAGE_NAMES = {"es": "Spanish", "ar": "Arabic"}


def label_translations(spec: dict) -> dict:
    """The label's translations on record — ``{lang: {field: words}}``, the words of each field only."""
    info = (spec or {}).get("panel_info") or {}
    out = {}
    for lang, fields in sorted((info.get("translations") or {}).items()):
        words = {k: " ".join(str(v).split()) for k, v in sorted((fields or {}).items()) if str(v or "").strip()}
        if words:
            out[lang] = words
    return out


def translations_sha256(translations: dict) -> str:
    import hashlib
    import json
    return hashlib.sha256(json.dumps(translations, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def translation_codes(spec: dict) -> list:
    """``[TRANSLATION_UNCONFIRMED: the languages]`` where the label carries translations he has not confirmed — none
    confirmed, or confirmed words that have changed since; [] where he confirmed exactly these words."""
    words = label_translations(spec)
    if not words:
        return []
    confirmed = (spec or {}).get(TRANSLATIONS_CONFIRMED_KEY) or {}
    if confirmed.get("sha256") == translations_sha256(words):
        return []
    return ["%s: %s" % (TRANSLATION_UNCONFIRMED, ", ".join(LANGUAGE_NAMES.get(lang, lang) for lang in words))]


#: [His second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010), (4):
#: "the big rose in Blossom Arch / Stem Journey is 122's rose, whole and scaled ($0)".]
#: Measured on 123's three concepts (their real reads, fixtures_123): the density of a line-art part's traced strokes,
#: binned BLOOM_BINS over the product and smoothed by BLOOM_SIGMA bins — its peak over its mean 1.9–2.1 on Garden Wrap's
#: all-over field, 2.8 on Blossom Arch's rose in its oval, 3.1–3.4 on Stem Journey's hero rose. A peak BLOOM_RATIO times
#: the mean or more is one big bloom; its place the region round the peak holding BLOOM_HOT of it.
BLOOM_BINS = (20, 60)
BLOOM_SIGMA = 1.5
BLOOM_RATIO = 2.5
BLOOM_HOT = 0.7
#: … and a part of line art too small to be the concept's field or its bloom (Blossom Arch's scalloped band, read as line
#: art) is never given the container's roses: under this share of the product
CONTINUED_MIN_SHARE = 0.15


def big_bloom(line: dict) -> list | None:
    """[His second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010), (4):
    "the big rose in Blossom Arch / Stem Journey is 122's rose, whole and scaled ($0)".]
    The box (product fractions) of the one big bloom a line-art part draws — its strokes' densest region, where that
    stands BLOOM_RATIO times their mean or more — or None for a field drawn evenly (Garden Wrap's)."""
    import cv2
    import numpy as np
    pts = []
    for stroke in line.get("strokes") or []:
        p = np.array(stroke.get("points") or [], float)
        for a, b in zip(p[:-1], p[1:]):
            n = max(2, int(np.hypot(*(b - a)) / 0.004))
            pts.extend(a + (b - a) * t for t in np.linspace(0.0, 1.0, n))
    if len(pts) < 50:
        return None
    P = np.array(pts)
    H, _xe, _ye = np.histogram2d(P[:, 0], P[:, 1], bins=BLOOM_BINS, range=[[0.0, 1.0], [0.0, 1.0]])
    G = cv2.GaussianBlur(H.astype(np.float32), (0, 0), BLOOM_SIGMA)
    inked = G[G > 0]
    if not len(inked) or G.max() < BLOOM_RATIO * inked.mean():
        return None
    peak = np.unravel_index(int(G.argmax()), G.shape)
    _n, lab = cv2.connectedComponents((G >= BLOOM_HOT * G.max()).astype(np.uint8), connectivity=8)
    xs, ys = np.nonzero(lab == lab[peak])
    return [round(xs.min() / BLOOM_BINS[0], 4), round(ys.min() / BLOOM_BINS[1], 4),
            round((xs.max() + 1) / BLOOM_BINS[0], 4), round((ys.max() + 1) / BLOOM_BINS[1], 4)]


#: [His second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010), (2): "a
#: concept shown as drawable must draw".] two lines of a carton's drawn copy run onto each other where a glyph's ink of
#: one meets a glyph's ink of the other over more than this, in mm (the smaller side of where they meet); under it, two
#: glyphs that only touch
COPY_LAP_MM = 0.05


def drawn_copy_laps(task, front: dict, dims: dict, clear_mm: float = 0.0) -> list:
    """[His second test blocker on design 123, (2).] The carton composed as its drawing composes it
    (``native_handoff._carton_document``, on the die ``dims`` give it — ``dieline_agent.carton_input``), and its front's
    copy measured where it is drawn: each glyph's own ink (PyMuPDF's ``TEXT_ACCURATE_BBOXES``) inside the front panel,
    and each two lines whose ink meets said in words — None where no carton is made at ``dims``; with ``clear_mm``,
    each two that stand closer than that ([his test findings on design 123, (4)]: "the name sits ... with clear space").
    Measured on 123 at
    42 × 133.69 mm: Stem Journey's "Hand Cream /" set 0.66 mm onto its Arabic; nothing on Garden Wrap or Blossom Arch."""
    import itertools
    import os
    import tempfile

    import fitz

    from apps.dielines.geometry.engine import calculate_dieline
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.pipeline.agents.dieline_agent import carton_input
    from apps.pipeline.services.native_handoff import _carton_document
    from apps.pipeline.services.panel_info import merge_panel_info
    from apps.pipeline.targets import get_target
    from apps.pipeline.targets.container import product_name_for
    target, product = get_target(task.design_target), task.product
    metadata = target.design_metadata(task, {"product_name": product_name_for(task, product)[0],
                                             "product_type": getattr(product, "product_type", "") if product else ""})
    try:
        params = carton_input(dims, metadata, target.carton_template_version(task))
        coords = calculate_dieline(params)
    except ValueError:                    # a size no carton is made at (the schema's and the geometry's refusals)
        return None
    doc, _logo = _carton_document(params, coords, merge_panel_info(task, None), front,
                                  turn_faces=dims.get("orientation") == FLAT)       # [his goal of 2026-10-13, (2)]
    panel = next((node for node, _parent in doc.walk() if node.name == "panel-front"), None)
    if panel is None:
        return []
    k = 72.0 / 25.4                                   # the emitter's millimetre, in points
    rect = fitz.Rect(panel.x * k, panel.y * k, (panel.x + panel.w) * k, (panel.y + panel.h) * k)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "front.ai")
        emit_pdf_ai(doc, path)
        with fitz.open(path) as pdf:
            raw = pdf[0].get_text("rawdict", flags=fitz.TEXT_ACCURATE_BBOXES)
    lines = []
    for block in raw["blocks"]:
        for line in block.get("lines") or []:
            for span in line["spans"]:
                ink = [fitz.Rect(ch["bbox"]) for ch in span["chars"] if ch["c"].strip()]
                ink = [r for r in ink if not r.is_empty and rect.contains(fitz.Point((r.x0 + r.x1) / 2.0,
                                                                                     (r.y0 + r.y1) / 2.0))]
                if ink:
                    lines.append(("".join(ch["c"] for ch in span["chars"]).strip(), ink, float(span["size"])))

    def placed(words, ink, size):
        # [his test findings on design 123, (4)] where a line's ink stands on the front, in mm from its corner
        return {"words": words, "size": size,
                "box": [min(r.x0 for r in ink) / k - panel.x, min(r.y0 for r in ink) / k - panel.y,
                        max(r.x1 for r in ink) / k - panel.x, max(r.y1 for r in ink) / k - panel.y]}
    drawn = [placed(*line) for line in lines]
    out = []
    for (words_a, ink_a, size_a), (words_b, ink_b, size_b) in itertools.combinations(lines, 2):
        d = clear_mm * k / 2.0
        meets = [fitz.Rect(a.x0 - d, a.y0 - d, a.x1 + d, a.y1 + d) & fitz.Rect(b.x0 - d, b.y0 - d, b.x1 + d, b.y1 + d)
                 for a in ink_a for b in ink_b]
        lap = max([min(m.width, m.height) / k for m in meets if not m.is_empty] + [0.0])
        if lap > COPY_LAP_MM:
            out.append({"kind": "type", "laps": True, "name": '"%s" and "%s"' % (words_a, words_b),
                        "why": "drawn on this carton's %g × %g mm front, set at %s, these two lines of its copy run "
                               "onto each other (%.1f mm)" % (
                                   dims["width_mm"], dims["height_mm"],
                                   "%.3g pt" % size_a if abs(size_a - size_b) < 0.05
                                   else "%.3g and %.3g pt" % (size_a, size_b), lap),
                        "pair": [placed(words_a, ink_a, size_a), placed(words_b, ink_b, size_b)], "lap_mm": lap,
                        "lines": drawn, "panel_mm": [panel.w, panel.h]})
    return out


#: [His test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (4): "Text
#: collisions are fixed by spacing or shrinking, never refused".] the clear space two lines of copy are left with once
#: settled (mm), and the most rounds the front is drawn, measured and settled in
SETTLE_GAP_MM = 1.0
SETTLE_ROUNDS = 5
#: … and two lines standing closer than this are settled too: clear space, never merely apart
SETTLE_CLEAR_MM = 0.5


def _squash(words: str) -> str:
    """A line's letters for matching what the drawn file says against the line it was set from: its presentation forms
    folded (the file's Arabic), separators and spaces dropped, lower case."""
    import unicodedata
    folded = unicodedata.normalize("NFKC", str(words)).lower()
    return "".join(ch for ch in folded if ch.isalnum())


def _line_of(types: list, words: str):
    """The front's type line the drawn ``words`` were set from — its own words, or the shortest whose words hold them
    (a line the file draws in two runs) — read either way round (the file may hold an Arabic run in its drawn order);
    None where none does."""
    want = [w for w in (_squash(words), _squash(words)[::-1]) if w]
    found = [t for t in types if t.get("words") and any(w in _squash(t["words"]) for w in want)]
    return min(found, key=lambda t: len(_squash(t["words"]))) if found else None


def _settle_one(front: dict, lap: dict, safe_mm: float):
    """One pair of drawn lines running onto each other settled: lines one above the other spaced apart — the lower moved
    down where the front has room, else the upper up, else both as far as each can — and only where neither has room
    the upper shrunk (never under the print floor); lines side by side moved apart, else the second set under the first.
    ``(the front, what was done)`` — None where the lines are not the front's own or nothing can be done."""
    from apps.ire.compose import _bleeds, _frac_walk, uniform_layout
    from apps.ire.compose_container import MAP_TYPE_FLOOR_PT
    W, H = (float(v) for v in lap["panel_mm"])
    shapes = front.get("shapes") or {}
    types = shapes.get("types") or []
    a, b = lap["pair"]
    ta, tb = _line_of(types, a["words"]), _line_of(types, b["words"])
    if ta is None or tb is None or ta is tb:
        return None
    _laid, uniform = uniform_layout(front, W, H)
    kx, ky = (uniform or {}).get("scale") or (1.0, 1.0)
    fx, fy = 1.0 / (kx * W), 1.0 / (ky * H)                 # a millimetre on the panel, in the map's fractions
    A, B = a["box"], b["box"]
    others = [line["box"] for line in lap["lines"] if line["box"] not in (A, B)]
    # the foot the copy stands above: the safe margin, or the top of a band or shape the picture runs to its foot
    feet = [float(p["box"][1]) * H for key in ("bands", "shapes") for p in shapes.get(key) or []
            if p.get("box") and float(p["box"][1]) > 0.5 and (key == "bands" or _bleeds(p))]
    floor_y = min([H - safe_mm] + [y - SETTLE_GAP_MM for y in feet])

    def across(p, q):
        return min(p[2], q[2]) - max(p[0], q[0])

    def moved(t, dx_mm, dy_mm):
        return _frac_walk(t, 1.0, dx_mm * fx, dy_mm * fy)

    def shrunk(t, f):
        x0, y0, x1, y1 = (float(v) for v in t["box"])
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        return _frac_walk(t, f, cx * (1.0 - f), cy * (1.0 - f))

    def put(changes):
        out = [changes.get(id(t), t) for t in types]
        return dict(front, shapes=dict(shapes, types=out))
    if across(A, B) > 0.3 * min(A[2] - A[0], B[2] - B[0]):
        (U, tu, su), (L, tl, _sl) = sorted([(A, ta, a["size"]), (B, tb, b["size"])], key=lambda e: (e[0][1] + e[0][3]))
        need = U[3] - L[1] + SETTLE_GAP_MM
        below = min([floor_y - L[3]] + [o[1] - SETTLE_GAP_MM - L[3] for o in others if o[1] >= L[3] - 1e-6
                                         and across(o, L) > 0])
        above = min([U[1] - safe_mm] + [U[1] - SETTLE_GAP_MM - o[3] for o in others if o[3] <= U[1] + 1e-6
                                        and across(o, U) > 0])
        down, up = max(0.0, below), max(0.0, above)
        if down >= need:
            return put({id(tl): moved(tl, 0.0, need)}), {"lines": [tu["part"], tl["part"]], "how": "spaced",
                                                         "moved": {tl["part"]: [0.0, round(need, 2)]}}
        if up >= need:
            return put({id(tu): moved(tu, 0.0, -need)}), {"lines": [tu["part"], tl["part"]], "how": "spaced",
                                                          "moved": {tu["part"]: [0.0, round(-need, 2)]}}
        if down + up >= need:
            d = min(down, need)
            return (put({id(tl): moved(tl, 0.0, d), id(tu): moved(tu, 0.0, -(need - d))}),
                    {"lines": [tu["part"], tl["part"]], "how": "spaced",
                     "moved": {tl["part"]: [0.0, round(d, 2)], tu["part"]: [0.0, round(-(need - d), 2)]}})
        # no room: the upper line shrunk, as little as clears it — with every line set at its size (a name over
        # several lines at one size shrinks as one), never under the print floor
        short = need - down - up
        f = max((U[3] - U[1] - short) / max(U[3] - U[1], 1e-6), MAP_TYPE_FLOOR_PT / max(su, 1e-6))
        if f >= 0.999:
            return None
        same = [t for t in types if t.get("words") and any(abs(line["size"] - su) < 0.05 and _line_of([t], line["words"])
                                                          for line in lap["lines"])] or [tu]
        changes = {id(t): shrunk(t, f) for t in same}
        if down > 0:
            changes[id(tl)] = moved(changes.get(id(tl), tl), 0.0, down)
        return put(changes), {"lines": [tu["part"], tl["part"]], "how": "shrunk", "by": round(1.0 - f, 3),
                              "shrunk": [t["part"] for t in same]}
    (Lf, tlf, _), (Rt, trt, _) = sorted([(A, ta, 0), (B, tb, 0)], key=lambda e: e[0][0] + e[0][2])
    need = Lf[2] - Rt[0] + SETTLE_GAP_MM
    row = [o for o in others if min(o[3], Lf[3], Rt[3]) - max(o[1], Lf[1], Rt[1]) > 0]
    left = min([Lf[0] - safe_mm] + [Lf[0] - SETTLE_GAP_MM - o[2] for o in row if o[2] <= Lf[0] + 1e-6])
    right = min([W - safe_mm - Rt[2]] + [o[0] - SETTLE_GAP_MM - Rt[2] for o in row if o[0] >= Rt[2] - 1e-6])
    left, right = max(0.0, left), max(0.0, right)
    if left + right >= need:
        dl = min(left, need / 2.0) if right >= need / 2.0 else need - right
        return (put({id(tlf): moved(tlf, -dl, 0.0), id(trt): moved(trt, need - dl, 0.0)}),
                {"lines": [tlf["part"], trt["part"]], "how": "spaced",
                 "moved": {tlf["part"]: [round(-dl, 2), 0.0], trt["part"]: [round(need - dl, 2), 0.0]}})
    # no room on the row: the second line set under the first, centred under it
    dx = (Lf[0] + Lf[2]) / 2.0 - (Rt[0] + Rt[2]) / 2.0
    dy = Lf[3] + SETTLE_GAP_MM - Rt[1]
    return put({id(trt): moved(trt, dx, dy)}), {"lines": [tlf["part"], trt["part"]], "how": "set under",
                                                "moved": {trt["part"]: [round(dx, 2), round(dy, 2)]}}


def settle_front_copy(task, front: dict, dims: dict) -> dict:
    """[His test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (4): "Text
    collisions are fixed by spacing or shrinking, never refused (the 1.8 mm "Blossom"/"Hand Cream" overlap)."]
    The front drawn as its drawing draws it (``drawn_copy_laps``), each two lines of copy whose ink meets settled
    (``_settle_one``) and the front drawn and measured again, SETTLE_ROUNDS times at most; what was done kept on the
    front (``copy_settled``), and a pair it could not settle said there — drawn as it stands, never refused."""
    safe = float(dims["safe_margin_mm"]) if dims.get("safe_margin_mm") else 4.0
    done = []
    for _round in range(SETTLE_ROUNDS):
        laps = drawn_copy_laps(task, front, dims, clear_mm=SETTLE_CLEAR_MM)
        if not laps:
            break
        # two runs of one line (its words in two faces) are never set apart: the first pair of two lines that can be
        settled = next((got for got in (_settle_one(front, lap, safe) for lap in laps) if got is not None), None)
        if settled is None:
            done.append({"lines": [p["words"] for p in laps[0]["pair"]], "how": "drawn as it stands",
                         "lap_mm": round(laps[0]["lap_mm"], 2)})
            break
        front, how = settled
        done.append(how)
    return dict(front, copy_settled=done) if done else front


def whole_round_the_pack(shapes: dict, spec: dict, image, picture: bytes | None, face_mm, light: dict | None,
                         photographed: str | None) -> tuple:
    """[His review of 127, 130, 131 and 132, 2026-10-15, C.] The carton front's ``shapes`` and its ground (``light``,
    ``dm.light_corrected``'s record) made ready to print all round the pack: (2) "NO BROKEN MOTIFS" — each solid motif
    measured against its picture, one its trace breaks drawn from its flat redraw traced again, or left out, said
    (``container._with_flat_shapes``); (1) "No grey panels" — where the concept's pattern covers the front
    (``compose.wrapping_pattern``), the carton's ground is the evenly lit ground of that pattern's flat redraw — the
    ground its traced shapes leave showing — never the photographed ground under the studio's grey light, and a window
    the map read in that photographed ground (``photographed``) takes it too. ``(shapes, light)``."""
    from apps.ire.compose import wrapping_pattern
    from apps.pipeline.services.flat_motif import delta_e
    from apps.pipeline.targets.container import _with_flat_shapes
    shapes = _with_flat_shapes({"shapes": shapes}, spec, image, picture, face_mm=face_mm)["shapes"]
    wraps = wrapping_pattern({"shapes": shapes})
    flat_ground = next((line["flat"]["ground"] for line in wraps if (line.get("flat") or {}).get("ground")), None)
    if light is None or flat_ground is None or not photographed:
        return shapes, light
    light = dict(light, hex=flat_ground, photographed_ground=light["hex"],
                 method="the evenly lit ground of its all-over pattern's flat redraw (%r), never the photo's shaded "
                        "one" % wraps[0]["part"])
    # (its field, read across the photo's shading, goes with its photographed colour: the ground's own paper is flat)
    shapes = dict(shapes, windows=[dict({k: v for k, v in win.items() if k != "field"}, fill=flat_ground,
                                        fill_photographed=win["fill"])
                                   if win.get("fill") and delta_e(win["fill"], photographed) < WINDOW_GROUND_DE
                                   else win for win in shapes.get("windows") or []])
    return shapes, light


#: [His review of 127, 130, 131 and 132, 2026-10-15, C (1)] a window the map read within this (CIEDE2000) of the
#: photographed ground is the ground — 132's cartouche read #DCD7D2, its field #DCD7D2
WINDOW_GROUND_DE = 3.0


def seen_face_mm(dims: dict) -> tuple:
    """[His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (2).] A carton's front as it is seen, (width, height) in mm:
    on a box lying flat, as wide as its die stands it tall; else as the die stands it."""
    w, h = float(dims["width_mm"]), float(dims["height_mm"])
    return (h, w) if dims.get("orientation") == FLAT else (w, h)


#: [his goal of 2026-10-13, (2)] a carton lying flat — its front the lid's face, landscape — on a die that stands
FLAT = "flat"


def drawing_size(output) -> dict | None:
    """The size an output's carton is drawn at: its die as drawn, else the size he confirmed for it at its size step
    ([his test findings on design 123, (7)], ``keep_confirmed_size``); None before either."""
    from apps.pipeline.targets.container import CONFIRMED_SIZE_KEY
    job = getattr(output, "dieline_job", None)
    made = (job.input_json if job is not None else None) or {}
    if made.get("dimensions"):
        return dict(made["dimensions"], **(made.get("construction") or {}), **(made.get("print_settings") or {}),
                    **({"orientation": made["orientation"]} if made.get("orientation") else {}))
    kept = (output.spec_sheet or {}).get(CONFIRMED_SIZE_KEY)
    return dict(kept["dims"]) if isinstance(kept, dict) and kept.get("dims") else None


def carton_copy_laps(task, spec: dict, picture: bytes | None, dims: dict) -> list | None:
    """[His second test blocker on design 123, (2).] ``drawn_copy_laps`` on the front its target draws from the map and
    shapes in ``spec`` (``carton_front``) — nothing where its target draws no carton front from a map; None where no
    carton is made at ``dims``."""
    from apps.pipeline.targets import get_target
    target = get_target(task.design_target)
    if getattr(target, "reads_carton_map", False) is not True:
        return []
    front = target.carton_front(task, spec, picture, [])
    return drawn_copy_laps(task, front, dims) if front is not None else []


def chosen_typography(task, image) -> str:
    """[His goal of 2026-10-10, item 6] the type words of the direction the chosen concept was drawn for ("" for none)."""
    from apps.pipeline.models import CreativeBrief
    if image is None or getattr(task, "pk", None) is None:
        return ""                                     # a design not saved: no direction on record
    brief = CreativeBrief.objects.filter(task=task).first()
    if brief is None:
        return ""
    for direction in brief.directions or []:
        if isinstance(direction, dict) and direction.get("direction_id") == image.direction_id:
            return str(direction.get("typography") or "")
    return ""


class PackagingTarget(TargetStrategy):
    name = DesignTarget.PACKAGING.value
    #: [his second test blocker on design 123, 2026-10-09, (2)] its concepts are read by their front panel
    #: (``read_carton_map``) — before they are shown, and so at approval and drawing, the one read
    reads_carton_map = True

    def check_concepts(self, aria, images):
        """[His second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010), (2): "The
    check before I see the concepts and the check at drawing time must agree: a concept shown as drawable must draw. Make
    them one check, and add it to the wiring check with 123's real concepts."]
        Every carton concept read by its front panel and checked before it is shown — the one check
        (``container.drawable_verdict``) its approval and its drawing make on the same read, kept on the picture: a
        concept shown as drawable draws, and one that cannot yet is said beside it in words, with what he can do."""
        from apps.pipeline.targets.container.readable import check_concepts
        return check_concepts(aria, images)

    def concept_structure_id(self, aria):
        # Unchanged: the packaging structure id ARIA already resolves.
        return aria._structure_id()

    def concept_prompt_profile(self, aria) -> str:
        """[His go of 2026-10-02.] A carton's concept pictured so its design map can read its front
        (``CARTON_MAP_DIRECTIVE``) — [his goal of 2026-10-06, item 1] and the product it holds, in the form he chose
        or his brief names (``form_line``)."""
        from apps.pipeline.targets.container import form_line
        held = form_line(getattr(aria, "task", None), inside=True) if getattr(aria, "task", None) is not None else ""
        return CARTON_MAP_DIRECTIVE + ("\n" + held if held else "")

    def begin_output(self, aria, approved_image):
        # [the owner's finding on design 119, 2026-10-03: "NO SILENT FALLBACK"] the carton's map read and checked
        # first — a concept it cannot draw stops at Gate 1 before the paid dimension estimate is made
        from apps.pipeline.targets.container import _concept_bytes, map_drawable
        rec = read_carton_map(aria, approved_image)
        shapes = map_drawable(aria, approved_image, rec, _concept_bytes(approved_image))
        if shapes is None:
            return
        aria._run_dieline_estimate(approved_image)
        self._keep_carton_map(aria, rec, shapes)

    def _keep_carton_map(self, aria, rec: dict | None, shapes: dict) -> None:
        """[His go of 2026-10-02.] The carton's design map — and [the owner's finding on design 119, 2026-10-03] its
        shapes, traced when it was checked — kept on the carton's output for its front to be drawn from
        (``carton_map_front``); nothing where no output was made or no map was read."""
        from apps.pipeline.services import concept_design_map as dm
        output = aria.task.packaging_outputs.order_by("-pk").first()
        if output is None or rec is None:
            return
        spec = output.spec_sheet or {}
        spec[dm.SCHEMA] = rec
        if shapes:
            spec[dm.SHAPES_SCHEMA] = shapes
        output.spec_sheet = spec
        output.save(update_fields=["spec_sheet"])

    def carton_map_front(self, task, output) -> dict | None:
        """[His go of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a18911a): "build the map path to run on its
        own for every new design, for a wand vial and a carton".] The carton's front as its own concept's map draws it —
        the shapes traced from the picture once and kept on the output (``targets.container._map_front``), each type
        line given the words a source on record gives it (the product's name, the brief's front copy), and the front's
        ground the map's first colour field — or None where no map READ this picture or nothing of it traces, and the
        front is ruled as before."""
        from apps.pipeline.targets.container import _concept_bytes, _write_records
        spec = output.spec_sheet or {}
        made: list = []
        size = drawing_size(output)
        front = self.carton_front(task, spec, _concept_bytes(output.approved_image), made,
                                  image=output.approved_image, face_mm=seen_face_mm(size) if size else None)
        if made:
            _write_records(spec, made)
            output.spec_sheet = spec
            output.save(update_fields=["spec_sheet"])
        # [his test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (4): "Text
        # collisions are fixed by spacing or shrinking, never refused"] the front's copy settled at the size it is drawn
        size = size if front is not None else None
        if size is not None:
            front = settle_front_copy(task, front, size)
        return front

    def carton_front(self, task, spec: dict, picture: bytes | None, made: list, image=None,
                     face_mm=None) -> dict | None:
        """``carton_map_front``'s front from a map and its shapes (``spec``) and the picture they were read from — what
        it traced again put in ``made`` — so the one check measures the front its drawing draws ([his second test
        blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010), (2)]). With the
        concept's ``image``, each line-art part given no container art is traced from its flat redraw kept on it, or
        left undrawn, said (his (4): "a standalone carton gets the same flat redraw before tracing")."""
        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.targets.container import _map_front, brief_text, product_name_for, type_sources_for
        name, _source = product_name_for(task, task.product)
        # [his rules 1 and 2, 2026-10-05] the carton's own lines on record: its front, its side
        sources = type_sources_for(task, name, carton=True)
        front = _map_front(spec, picture, made, sources=sources)
        if front is None:
            return None
        shapes = dict(front["shapes"], types=dm.type_sources(front["shapes"].get("types") or [], sources))
        fields = [p for p in (spec.get(dm.SCHEMA) or {}).get("parts") or [] if p.get("kind") == "field"
                  and p.get("colour")]
        # [his review of 119, 2026-10-05, point 3: "One ground all round the carton, taken from the concept's own
        # colour"] the field's colour with the photograph's light taken out (`light_corrected`), said on the record
        light = dm.light_corrected(picture, fields[0]["colour"]) if fields else None
        # [his test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at ea2b98b), (3): "its
        # flaps/sides repeat 122's line art"] a carton continuing its approved container carries the container's own
        # line art — its rose, whole, on its flaps and sides, and its line art in each line-art part of its front, never
        # a stroke traced from its own photo (his finding on 122's drawing, A1: "Never trace motifs from the concept
        # photo")
        from apps.pipeline.targets.composite import continued_line_art
        from apps.pipeline.targets.container import _part_boxes
        art = continued_line_art(task)
        traced = [line for line in shapes.get("lines") or [] if line.get("ink")]
        if art is not None and traced:
            # [his second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010):
            # "Make that part drawable (it's 122's own look: line-art rose field ...)"] 122's line art in the ink the
            # concept he chose draws it — Garden Wrap's light rose pink, never the tube's red over its small lines
            main = max(traced, key=lambda line: len(line.get("strokes") or []))
            art = dict(art, ink=main["ink"], ink_from="the concept's own line art, %r" % main["part"])
        if art is not None:
            boxes, lines = _part_boxes(spec), []
            for line in shapes.get("lines") or []:
                pts = [p for st in line.get("strokes") or [] for p in st["points"]]
                box = boxes.get(line["part"]) or ([min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts),
                                                   max(p[1] for p in pts)] if pts else [0.0, 0.0, 1.0, 1.0])
                pb = [max(0.0, float(box[0])), max(0.0, float(box[1])), min(1.0, float(box[2])), min(1.0, float(box[3]))]
                if (pb[2] - pb[0]) * (pb[3] - pb[1]) < CONTINUED_MIN_SHARE:
                    lines.append(line)            # [his second blocker on 123, (4)] no field nor bloom: never roses
                    continue
                # [his second test blocker on design 123, (4)] the concept's one big bloom, 122's rose in its place
                lines.append(dict(line, continued=dict(art, part_box=pb, bloom=big_bloom(line))))
            shapes = dict(shapes, lines=lines)
        own = [line for line in shapes.get("lines") or [] if "continued" not in line]
        if image is not None and own:
            # [his second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010), (4): "a standalone carton gets the same flat redraw before tracing"] its own line art — every
            # part of a carton standing alone, each small one of a continuing carton's — from its flat redraw's
            # outlines, never the strokes traced from its photo; one with none kept, or not whole, left undrawn, said
            from apps.pipeline.targets.container import _with_flat_motifs
            flat = {line["part"]: line for line in _with_flat_motifs({"shapes": {"lines": own}}, spec,
                                                                        image, face_mm=face_mm)["shapes"]["lines"]}
            shapes = dict(shapes, lines=[line if "continued" in line else flat[line["part"]]
                                         for line in shapes.get("lines") or []])
        shapes, light = whole_round_the_pack(shapes, spec, image, picture, face_mm, light,
                                             fields[0]["colour"] if fields else None)
        # [his test findings on design 123, 2026-10-09, (4): "Scale the layout as a whole"] the concept's face, its
        # width over its height — the front laid out at it (``compose.uniform_layout``)
        face = (spec.get(dm.SCHEMA) or {}).get("face_box_px")
        aspect = ((float(face[2]) - float(face[0])) / (float(face[3]) - float(face[1]))
                  if face and float(face[3]) > float(face[1]) else None)
        # [the owner's finding on design 119, 2026-10-03] and his brief's side copy, for the carton's two sides
        # [his test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (1): "Every
        # panel is drawn from it."] with the concept, its back and sides from its layout picture, kept on it
        from apps.pipeline.targets.carton_layout import panel_fronts
        panels = panel_fronts(task, image, sources, front_shapes=shapes,
                              dims=({"orientation": "flat" if face_mm[0] > face_mm[1] else "standing"}
                                    if face_mm else None)) \
            if image is not None else {}
        # [his goal of 2026-10-10, item 6] the front's own faces where its concept letters its name in a sans — the
        # rounded one where the design is soft (its brief's words and its chosen direction's type words) — and soft
        # breathing room round its type, never a hole cut in its field
        from apps.ire import front_faces
        faces = front_faces.for_front(shapes.get("types") or [], name,
                                      "%s\n%s" % (brief_text(task), chosen_typography(task, image)))
        return dict(front, shapes=shapes, ground=light["hex"] if light else None, ground_light=light, face_aspect=aspect,
                    **({"panels": panels} if panels else {}), **({front_faces.KEY: faces} if faces else {}),
                    soft_room=True, side_copy=dm.brief_side_copy(brief_text(task)), continued=art)

    def panel_defaults(self, task, info: dict) -> dict:
        """[His go of 2026-10-02 and his answer 3 the same day (OWNER_BLOCKER_CLEARANCE.md, transcribed at a18911a): "My
        brief's back copy counts as my copy for acceptance."] The carton's panel copy: the product record's own words, and
        where the record gives none (a Complete Product's carton has no record) the product's name as a container's
        front takes it (``product_name_for``) and each piece his brief's back copy gives under a heading that names it —
        how to use, ingredients, warnings, description — with its pieces no heading names after the brand's regulatory
        line ("Made in UAE"). A person still edits every field at the dimension gate."""
        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.targets.container import brief_text, product_name_for
        out = dict(info)
        if not out.get("product_name"):
            out["product_name"] = product_name_for(task, task.product)[0]
        slots = {"how to use": "how_to_use", "directions": "how_to_use", "usage": "how_to_use", "to use": "how_to_use",
                 "ingredients": "ingredients", "inci": "ingredients", "warnings": "warnings", "warning": "warnings",
                 "caution": "warnings", "description": "description"}
        extra = []
        for sec in dm.brief_back_copy(brief_text(task))["sections"]:
            key = slots.get(str(sec["heading"]).strip().lower())
            if key is None:
                extra.append(sec["text"])
            elif not out.get(key):
                out[key] = sec["text"]
        # [the owner's finding on design 119, 2026-10-03: the back "never carries another product's supplier text"] the
        # brand's supplier block ("MADE IN CHINA BY SUPPLIER: YIWU …", as on its existing production files) is printed
        # only for a product its record describes, and never where his brief gives the back's own lines ("Made in UAE")
        if extra:
            out["regulatory_text"] = " · ".join(extra)
        elif task.product is None:
            out["regulatory_text"] = ""
        # [his answers after the fixes for design 122, 2026-10-08, (2): "the drawing must always print my brief's size"]
        # the label's NET WT is his brief's size, in his words, before the product record's
        size = dm.brief_size(brief_text(task))
        if size is not None:
            out["net_weight"] = size[0]
        return out

    def carton_template_version(self, task) -> str | None:
        """[His final goal, 2026-10-05, B2: "A PRINT-READY DIELINE ... It must go to a printer without being edited."]
        A carton is drawn at the print-ready version — 1.3: 1.2's tuck across the depth, its tuck folds creased between
        their lock slits, a thumb notch where the lid closes."""
        from apps.dielines import registry
        from apps.pipeline.agents.dieline_agent import TEMPLATE_TYPE
        return registry.print_ready_version(TEMPLATE_TYPE)

    def gate2_hold(self, task, output) -> dict | None:
        """§BH55 Phase 2 — §BH50(f)(3), LIVE: "FRONT COPY: the 5.0 pt floor governs and a copy overrun BLOCKS
        Gate 2". The carton's front type is measured where it is composed (`apps/ire/compose.py`); a run over its
        panel, or one that could not be measured, holds the design here. No override.
        [§BH71 (0a), the owner's goal of 2026-09-28: one that could not be measured is a warning beside Approve
        since, never a hold; a run over its panel still holds.]"""
        from apps.ire.compose import BACK_COPY_KEY, FRONT_COPY_UNMEASURED, FRONT_TYPE_KEY
        # [His second goal of 2026-10-06, item 2: "A failure is fixed or shown to me, never hidden."] a die that does not
        # fold as the trade draws it holds the design by name, each failed check in his words
        from apps.dielines.geometry import fold_check as _fold_check
        fold = (output.spec_sheet or {}).get(_fold_check.SCHEMA)
        if fold and not fold.get("passed"):
            return {"error": _fold_check.FAILED, "codes": ["%s:%s" % (_fold_check.FAILED, x["id"])
                                                           for x in fold.get("failed") or []],
                    "said": _fold_check.said(fold)}
        # [his final goal, 2026-10-05, C5: "Only if it still doesn't fit, STOP and offer"] a label that cannot stand as
        # one block on the back's sticker at its floors holds the design by name, with the offers measured to hold it
        record = (output.spec_sheet or {}).get(BACK_COPY_KEY) or {}
        back = record.get("codes") or []
        if back:
            # [his review of 119, 2026-10-05, point 1] the label not trilingual; [his final goal, C5] or not standing
            held = {"error": str(back[0]).split(":")[0], "codes": back}
            if record.get("offers"):
                held["offers"] = record["offers"]
            return held
        codes = ((output.spec_sheet or {}).get(FRONT_TYPE_KEY) or {}).get("codes") or []
        # [§BH71 (0a), the owner's goal of 2026-09-28: a run the instrument could not measure is a warning beside
        # Approve, never a hold — a measured overrun still holds]
        codes = [c for c in codes if not str(c).startswith(FRONT_COPY_UNMEASURED)]
        if codes:
            return {"error": "CARTON_FRONT_COPY_NOT_READY", "codes": codes}
        return None

    def review_sections(self, task) -> list[dict]:
        """Packaging SPECIFICATIONS. The ACTIVE structure record on the
        dieline job is authoritative (2A-9 correction: a stale spec-sheet
        projection must never re-render rejected geometry as current);
        legacy spec-sheet keys are only a fallback when no record exists."""
        output = task.packaging_outputs.filter(
            dieline_job__isnull=False).order_by("-pk").first() or task.current_output()
        spec = (output.spec_sheet if output else None) or {}
        job = getattr(output, "dieline_job", None)
        record = dict(getattr(job, "structure_selection", None) or {}) \
            if job else {}
        rows = []
        if record:
            from apps.dielines import registry
            rows.append({
                "label": "Template",
                "value": f"{record.get('template_id')}/"
                         f"{record.get('template_version')}"})
            params = record.get("parameters") or {}
            if params.get("width_mm") and params.get("height_mm"):
                rows.append({
                    "label": "Dimensions",
                    "value": f'{params["width_mm"]} × {params.get("depth_mm")}'
                             f' × {params["height_mm"]} mm'})
            if params.get("board_thickness_mm") is not None:
                rows.append({"label": "Board thickness",
                             "value": f'{params["board_thickness_mm"]} mm'})
            try:
                defn = registry.resolve(record.get("template_id"),
                                        record.get("template_version"))
            except Exception:  # noqa: BLE001 — row building is best-effort
                defn = None
            if defn is not None:
                dim_note = defn.dimension_semantics.get("width_mm", "")
                if dim_note.startswith("INNER"):
                    rows.append({"label": "Dimension semantics",
                                 "value": "INNER dimensions"})
                if not defn.production_ready:
                    rows.append({
                        "label": "Structure status",
                        "value": f"{defn.structure_status} — "
                                 f"{defn.ineligibility_code}"})
            if not record.get("confirmed_at"):
                rows.append({"label": "Structure confirmation",
                             "value": "NOT CONFIRMED — the structure step was retired; nothing waits on it"})
            return rows
        dims = spec.get("confirmed_dimensions") or {}
        if spec.get("template"):
            rows.append({"label": "Template", "value": str(spec["template"])})
        if dims.get("width_mm") and dims.get("height_mm"):
            depth = dims.get("depth_mm")
            size = f'{dims["width_mm"]} × {depth} × {dims["height_mm"]} mm' \
                if depth else f'{dims["width_mm"]} × {dims["height_mm"]} mm'
            rows.append({"label": "Dimensions", "value": size})
        for key, lab in (("bleed_mm", "Bleed"), ("safe_margin_mm", "Safe margin"),
                         ("glue_tab_mm", "Glue tab")):
            if dims.get(key) is not None:
                rows.append({"label": lab, "value": f'{dims[key]} mm'})
        from apps.ire.compose import BACK_COPY_KEY, FRONT_LINE_PT, FRONT_NAME_PT, FRONT_TYPE_KEY   # §BH55 Phase 2
        back = spec.get(BACK_COPY_KEY) or {}
        if back:
            # [his final goal, 2026-10-05, C5: "THE INFO IS ONE DESIGNED BLOCK"]
            from apps.ire.compose import LABEL_DOES_NOT_FIT, LABEL_NOT_TRILINGUAL
            held = [c for c in back.get("codes") or []]
            value = "; ".join(back.get("said") or [])
            if any(str(c).startswith(LABEL_NOT_TRILINGUAL) for c in held):
                missing = sorted({"%s %s" % ({"es": "Spanish", "ar": "Arabic"}.get(c.split(":")[1], c.split(":")[1]),
                                               c.split(":")[2].replace("_", " "))
                                  for c in held if str(c).startswith(LABEL_NOT_TRILINGUAL)})
                value = "HELD at Gate 2 — the label is not trilingual: no %s" % ", no ".join(missing)
            elif any(str(c).startswith(LABEL_DOES_NOT_FIT) for c in held):
                value = "HELD at Gate 2 — %s" % value
            rows.append({"label": "Back copy", "value": value})
        front = spec.get(FRONT_TYPE_KEY) or {}
        if front:
            rows.append({"label": "Front type",
                         "value": ("HELD at Gate 2 — " + "; ".join(front["codes"])) if front.get("codes") else
                         f"the name at {FRONT_NAME_PT:g} pt, its line at {FRONT_LINE_PT:g} pt — every run measured "
                         "inside its panel"})
        return rows
