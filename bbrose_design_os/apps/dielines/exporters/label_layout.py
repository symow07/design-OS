"""[His final goal, 2026-10-05 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 32e9aaf), C5: "THE INFO IS ONE DESIGNED
BLOCK".] A label's copy laid out as ONE block on its panel — the back's sticker: a clear title (the name, and its
Arabic); then one language block after another — English, Spanish, Arabic — each with its sections in one fixed order
(description, ingredients, how to use, warnings), a hairline between languages; the brand's line ("Made in UAE"); the
NET WT / ITEM / BATCH / EXP block and the codes at the foot. One size and one line spacing per level — the title, the
body, the fine print (ingredients and warnings) — headings bold. It shrinks step by step with every level together:
[his correction of 2026-10-07] the whole label evenly, its layout, spacing and order kept, to a 3 pt floor. A quantity
and its unit are never broken across lines ("0.27 fl. oz." stands whole, never "fl. / oz."). Where it still cannot stand the plan says so (``fits``
False) — never cut, never moved, never dropped, never under the floor — and the design stops and says so (his
correction of 2026-10-07: the carton is never widened for text).

Before (his review of 119, point 2, 8cbfd73): one size for every line at a 5 pt floor, and a block that did not fit
moved to a side panel — 119's warnings, Spanish and Arabic stood on its sides beside his side copy."""
from __future__ import annotations

import re

#: [His correction of 2026-10-07 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a6b2092): "when the label doesn't fit, the
#: text gets SMALLER ... Shrink the whole label evenly until everything fits, keeping its layout, spacing and order.
#: Floor: 3 pt. Only if it still doesn't fit at 3 pt, stop and tell me".] One floor for the whole label — its body and its
#: ingredients and warnings together (his final goal's 5 pt and 4 pt give way to it).
FLOOR_PT = 3.0
FINE_FLOOR_PT = FLOOR_PT  # the fine print shrinks with the body, never apart from it
SIZE_MAX_PT = 7.0         # the copy is never set larger: the panel's spare height goes between its languages
SIZE_STEP_PT = 0.25
TITLE_EM = 1.3            # the title this much larger than the body
LEAD_EM = 1.25            # each level's line spacing, in its own size
SECTION_GAP_EM = 0.45     # between the sections of one language, in the body's lead
LANGUAGE_GAP_EM = 1.1     # between the title and the first language, and between languages (a hairline across it)
LANGUAGE_GAP_MAX_EM = 2.5 # the spare height spread over those gaps opens none past this
RULE_PT = 0.3             # the hairline's weight
#: [His goal of 2026-10-06, item 6: "Approve Noto Naskh Arabic Bold ... for Arabic headings; no outline bolding."] An
#: Arabic heading is set in Noto Naskh Arabic Bold — the granted face that carries every presentation form the shaping
#: path draws (141 + 631, as the Regular). It was drawn bold by a stroke of its own ink round regular letters
#: (ARABIC_BOLD_EM 0.035 em), no bold Arabic face having been granted; where the Bold's file is missing a heading is set
#: in the Regular, never stroked.
TITLE_LINES_MAX = 2       # [his goal of 2026-10-06, item 12] the title on one or two lines, never a word a line
#: [His second goal of 2026-10-06 (transcribed at c34a518), item 1: "ALL LABEL INFORMATION GOES ON THE BACK STICKER
#: ... Never printed inside the box".] The outside sticker's "Information inside" lines of his morning's item 5 are gone
#: with the offer they answered.
LABEL_GAP_EM = 0.6        # between a NET WT / ITEM / BATCH label and its value
META_PAD_EM = 0.35        # the block's frame this far round its text
QR_SIDE_MIN_PT = 18.0     # the QR's box — its four-module quiet zone inside it (reportlab's barBorder, 4) — as before:
QR_SIDE_SHARE = 0.14      # … 18 pt or this share of the panel's width, the larger
#: [His goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 7: "BARCODE: my number prints correctly but is cut at the sticker's edge. Always whole, inside the sticker, with quiet zones. No number from me = no barcode."]
#: An EAN-13 drawn whole at its own proportions: at 100 % it is 37.29 mm wide with its quiet zones and its bars 22.85 mm
#: tall (GS1); it was set at a 0.36 share of the copy's width with its bars 14 pt tall, shrunk with the rest of it —
#: 123's came out 15 mm wide with bars 2 mm tall, cut short. Now it is drawn at EAN_MAGNIFICATION (the smallest a
#: scanner reads, 80 %) where the sticker's width holds it, smaller only where it does not — never taller or shorter
#: than its own proportions, its quiet zones always inside its drawing, and its drawing inside the sticker's region.
EAN_NOMINAL_BAR_MM = 22.85
EAN_MAGNIFICATION = 0.8
BLANK = "________"
FIELDS = ("description", "ingredients", "how_to_use", "warnings")
FINE_FIELDS = ("ingredients", "warnings")
LANGUAGES = ("en", "es", "ar")
#: the faces a face falls back to for a character it has no glyph for
_FALLBACK: dict = {}


def _width(text: str, face: str, size: float) -> float:
    from apps.ire.estimated_sign import width      # [his goal of 2026-10-12, (5)] each ℮ in the room a 3 mm sign needs
    return sum(width(t, f, size) for f, t in _pieces(text, face))


def _pieces(text: str, face: str) -> list:
    """``[(face, text)]``: ``text`` in ``face``, each stretch of characters it has no glyph for in its fallback."""
    spare = _FALLBACK.get(face)
    if not spare or not text:
        return [(face, text)]
    from reportlab.pdfbase import pdfmetrics
    have = pdfmetrics.getFont(face).face.charToGlyph
    out: list = []
    for ch in text:
        f = face if (ord(ch) in have or ch.isspace()) else spare
        if out and out[-1][0] == f:
            out[-1] = (f, out[-1][1] + ch)
        else:
            out.append((f, ch))
    return out


def _draw_string(c, x: float, y: float, text: str, face: str, size: float) -> None:
    from apps.ire.estimated_sign import draw_text
    for f, t in _pieces(text, face):
        c.setFont(f, size)
        draw_text(c, x, y, t, f, size)             # [his goal of 2026-10-10, item 8: "The ℮ prints as a plain "e": it must be the real estimated sign everywhere."] the sign itself
        x += _width(t, f, size)


# [His correction of 2026-10-07: "Shrink the whole label evenly ... keeping its layout"] the granted narrower face
# (Fredoka at width 75, his second goal of 2026-10-06, item 1) is no longer a step: its maker is gone with it


def _faces_box(fonts: dict) -> tuple:
    """(ascent, descent) in ems, the largest of the faces the copy is set in — a line's box from its baseline, as a
    printer's proof and the drawn file measure it (Noto Naskh Arabic descends 0.634 em, Noto Sans 0.293)."""
    from reportlab.pdfbase import pdfmetrics
    asc, desc = 0.0, 0.0
    for name in (fonts.get("regular"), fonts.get("bold"), fonts.get("arabic")):
        if name:
            face = pdfmetrics.getFont(name).face
            asc, desc = max(asc, face.ascent / 1000.0), max(desc, -face.descent / 1000.0)
    return asc, desc


_NUMBER = re.compile(r"^\d+(?:[.,]\d+)?$")
_UNITS = {"ml", "ml.", "l", "l.", "g", "g.", "mg", "kg", "oz", "oz.", "fl", "fl.", "%", "cm", "mm", "lb", "lbs"}


def unit_groups(words: list) -> list:
    """``words`` ([(word, bold)]) with each quantity and its unit as ONE token, never broken across lines: "8 ml",
    "0.27 fl. oz." ("fl." and "oz." together), the "℮" with the quantity before it, "CI 15850"."""
    out: list = []
    for word, bold in words:
        if out and out[-1][1] == bold:
            prev = out[-1][0]
            last = prev.split()[-1].lower()
            bare = word.lower().rstrip(",;")
            if ((bare in _UNITS and (_NUMBER.match(last) or last in ("fl", "fl.")))
                    or word.strip(",;.") == "℮"
                    or (last == "ci" and word.rstrip(",.;").isdigit())):
                out[-1] = (prev + " " + word, bold)
                continue
        out.append((word, bold))
    return out


def _meta_rows(info: dict) -> list:
    rows = []
    if (info.get("net_weight") or "").strip():
        rows.append(("NET WT:", info["net_weight"].strip()))
    if (info.get("item_no") or "").strip():
        rows.append(("ITEM NO:", info["item_no"].strip()))
    rows += [("BATCH NO:", BLANK), ("EXP:", BLANK)]
    return rows


def _wrap_words(words: list, size: float, width: float, fonts: dict) -> tuple:
    """``words`` ([(word, bold)]) — each quantity with its unit one token (``unit_groups``) — wrapped greedily to
    ``width`` points: ``([[(word, bold)], ...], widest word over)``."""
    words = unit_groups(words)
    space = _width(" ", fonts["regular"], size)
    lines, line, used, over = [], [], 0.0, 0.0
    for word, bold in words:
        w = _width(word, fonts["bold"] if bold else fonts["regular"], size)
        over = max(over, w - width)
        add = w if not line else space + w
        if line and used + add > width:
            lines.append(line)
            line, used = [(word, bold)], w
        else:
            line.append((word, bold))
            used += add
    if line:
        lines.append(line)
    # [his final goal, 2026-10-05, C8] a separator standing at a break goes with it
    from apps.ire.text_script import SEPARATORS
    for i, ln in enumerate(lines):
        while i < len(lines) - 1 and len(ln) > 1 and ln[-1][0] in SEPARATORS:
            ln.pop()
        while i > 0 and len(ln) > 1 and ln[0][0] in SEPARATORS:
            ln.pop(0)
    return lines, over


def _two_lines(words: list, size: float, width: float, fonts: dict):
    """``words`` on one line where they stand in ``width``, else on the two lines of the most even split that stands —
    None where no split does."""
    words = unit_groups(words)
    if not words:
        return []
    if _line_w(words, size, fonts) <= width + 1e-6:
        return [words]
    best = None
    for k in range(1, len(words)):
        a, b = words[:k], words[k:]
        wide = max(_line_w(a, size, fonts), _line_w(b, size, fonts))
        if wide <= width + 1e-6 and (best is None or wide < best[0]):
            best = (wide, [a, b])
    return best[1] if best else None


def _title_fit(name: str, ar: str, levels: dict, width: float, fonts: dict, keep_marks: bool) -> tuple:
    """[His goal of 2026-10-06, item 12.] ``(size, English lines, Arabic lines, widest over)``: the title at the
    largest size, from its level down to the body's floor in SIZE_STEP_PT, at which its name stands on TITLE_LINES_MAX
    lines or fewer — split as evenly as its words allow — and its Arabic too; at the floor, as it stands there."""
    size = levels["title"]
    while True:
        en = _two_lines([(w, True) for w in name.split()], size, width, fonts) if name else []
        ar_lines = _ar_lines(ar, "", size, width, fonts, keep_marks, all_bold=True) if ar else []
        ar_ok = len(ar_lines) <= TITLE_LINES_MAX and all(_ar_line_w(ln, size, fonts) <= width + 1e-6 for ln in ar_lines)
        if (en is not None and ar_ok) or size <= FLOOR_PT + 1e-9:
            break
        size = round(size - SIZE_STEP_PT, 2)
    if en is None:
        en, _o = _wrap_words([(w, True) for w in name.split()], size, width, fonts)
    over = max([_line_w(ln, size, fonts) - width for ln in en] + [_ar_line_w(ln, size, fonts) - width for ln in ar_lines]
               + [0.0])
    return size, en, ar_lines, over


def arabic_bold(fonts: dict) -> dict:
    """``fonts`` with ``arabic_bold`` beside its Arabic face — the granted Bold — where its file is on hand."""
    if fonts.get("arabic_bold") or not fonts.get("arabic"):
        return fonts
    from apps.dielines.exporters.counter_display_files import _resolve_arabic_bold_font
    bold = _resolve_arabic_bold_font()
    return dict(fonts, arabic_bold=bold) if bold else fonts


def _ar_face(fonts: dict, bold: bool) -> str:
    return (fonts.get("arabic_bold") or fonts["arabic"]) if bold else fonts["arabic"]


def _ar_width(visual: str, size: float, fonts: dict, bold: bool = False) -> float:
    from apps.dielines.exporters.text_intl import split_script_runs
    return sum(_width(t, _ar_face(fonts, bold) if is_ar else fonts["regular"], size)
               for is_ar, t in split_script_runs(visual))


def _ar_lines(head: str, text: str, size: float, width: float, fonts: dict, keep_marks: bool,
              all_bold: bool = False) -> list:
    """Arabic ``head`` (its heading, bold) and ``text`` wrapped on the LOGICAL words to ``width`` points, each line
    shaped and put in visual order: ``[{"head": visual, "rest": visual}]`` — the heading on the first line only; every
    line bold where ``all_bold`` (the title)."""
    # [his goal of 2026-10-06, item 6] wrapped as it is drawn: a title in the Bold; a heading's line measured with its
    # heading in the Bold — the line wrapped again a little narrower until it stands in ``width`` (a single word wider
    # than the column stays over, and the plan says so)
    target = width
    for _ in range(8):
        out = _ar_lines_at(head, text, size, target, fonts, keep_marks, all_bold)
        over = max((_ar_line_w(ln, size, fonts) for ln in out), default=0.0) - width
        if over <= 1e-6 or not head or all_bold:
            return out
        target -= over + 0.05
    return out


def _ar_lines_at(head: str, text: str, size: float, width: float, fonts: dict, keep_marks: bool,
                 all_bold: bool) -> list:
    from apps.dielines.exporters.text_intl import shape_ar, wrap_ar_logical
    body = ("%s %s" % (head, text)).strip()
    logical = wrap_ar_logical(body, _ar_face(fonts, all_bold), size, width, latin_font=fonts["regular"],
                              keep_harakat=keep_marks)
    out = []
    for i, ln in enumerate(logical):
        h, rest = "", ln
        if all_bold:
            h, rest = ln, ""
        elif i == 0 and head and ln.startswith(head):
            h, rest = head, ln[len(head):].strip()
        out.append({"head": shape_ar(h, keep_harakat=keep_marks) if h else "",
                    "rest": shape_ar(rest, keep_harakat=keep_marks) if rest else "",
                    # [his final goal, C6] the same words in their logical order, for a file that shapes them itself
                    "head_logical": h, "rest_logical": rest})
    return out


def _ar_line_w(line: dict, size: float, fonts: dict) -> float:
    space = _width(" ", fonts["regular"], size) if line["head"] and line["rest"] else 0.0
    return _ar_width(line["head"], size, fonts, bold=True) + space + _ar_width(line["rest"], size, fonts)


def _line_w(line: list, size: float, fonts: dict) -> float:
    words = sum(_width(w, fonts["bold"] if b else fonts["regular"], size) for w, b in line)
    return words + _width(" ", fonts["regular"], size) * max(0, len(line) - 1)


def label_sections(info: dict, languages=LANGUAGES) -> dict:
    """What the label says, in his order: ``{"blocks": [{"lang", "sections": [{"field", "level", "head", "text"}]}],
    "tail": text}`` — a language's sections where his English gives the field (no Arabic ingredients: INCI names are
    printed once, in Latin, as the factory's labels print them); Spanish ingredients the same words as the English
    printed once, under "INGREDIENTS / INGREDIENTES:"; the brand's line ("Made in UAE") after the languages."""
    from apps.dielines.exporters.info_panel import _AR_LABELS, _EN_LABELS, _ES_LABELS
    labels = {"en": _EN_LABELS, "es": _ES_LABELS, "ar": _AR_LABELS}
    tr = info.get("translations") or {}
    # [his review of 127, 130, 131 and 132, 2026-10-15, C (7): "NEVER AN EMPTY LABEL"] a piece the system wrote for the
    # product's type is set in the form measured to let the whole label stand (``label_copy``): shortened, or in English
    # only — his own pieces always whole, in every language
    from apps.pipeline.services import label_copy as _lc
    written = set(info.get(_lc.PANEL_WRITTEN_KEY) or ())
    form = info.get(_lc.PANEL_FORM_KEY) or _lc.FULL
    dropped = set(info.get(_lc.PANEL_DROPPED_KEY) or ())

    def words(lang, field):
        if field in written and (field in dropped or (lang != "en" and _lc.english_only(form))):
            return ""
        if lang == "en":
            text = " ".join(str(info.get(field) or "").split())
        else:
            text = " ".join(str((tr.get(lang) or {}).get(field) or "").split())
        return _lc.shortened(field, text, form) if field in written else text
    once = ("en" in languages and "es" in languages and words("es", "ingredients")
            and words("es", "ingredients").lower() == words("en", "ingredients").lower())
    blocks = []
    for lang in LANGUAGES:
        if lang not in languages:
            continue
        sections = []
        for field in FIELDS:
            if not words("en", field) or not words(lang, field):
                continue
            if lang == "ar" and field == "ingredients":
                continue
            if lang == "es" and field == "ingredients" and once:
                continue
            head = labels[lang][field]
            if lang == "en" and field == "ingredients" and once:
                head = "INGREDIENTS / INGREDIENTES:"
            sections.append({"field": field, "level": "fine" if field in FINE_FIELDS else "body", "head": head,
                             "text": words(lang, field)})
        if sections:
            blocks.append({"lang": lang, "sections": sections})
    tail = "" if "made_in" in dropped and info.get(_lc.PANEL_MADE_IN_KEY) else info.get("regulatory_text")
    return {"blocks": blocks, "tail": " ".join(str(tail or "").split())}


def _band(info: dict, size: float, width: float, panel_w: float, fonts: dict) -> dict:
    """The foot: the NET WT / ITEM / BATCH block, aligned and framed to its text, and the codes — the QR in the panel's
    bottom right corner, an EAN-13 bottom left. The block beside the QR where its text fits there, else above the
    codes; each value beside its label, the values in one column, where the widest word fits there, else under it."""
    lead = size * LEAD_EM
    rows = _meta_rows(info)
    label_w = max(_width(label, fonts["bold"], size) for label, _value in rows)
    gap, pad = LABEL_GAP_EM * size, META_PAD_EM * size
    def face_of(value):
        return fonts.get("blank", fonts["regular"]) if value == BLANK else fonts["regular"]
    value_w = max(_width(value, face_of(value), size) for _label, value in rows)
    widest_word = max(_width(w, face_of(w), size) for _label, value in rows
                      for w, _b in unit_groups([(v, False) for v in value.split()]))
    qr = None
    if (info.get("qr_url") or "").strip():
        qr = {"side": min(max(QR_SIDE_MIN_PT, QR_SIDE_SHARE * panel_w), width)}
    ean = None
    digits = "".join(ch for ch in (info.get("barcode_ean") or "") if ch.isdigit())
    if len(digits) in (12, 13):
        from reportlab.graphics.barcode import createBarcodeDrawing
        from reportlab.lib.units import mm as _mm
        # [his goal of 2026-10-10, item 7] whole, at its own proportions: 80 % where the sticker holds it
        bar = EAN_NOMINAL_BAR_MM * _mm
        d = createBarcodeDrawing("EAN13", value=digits, barHeight=bar, humanReadable=True)
        scale = min(EAN_MAGNIFICATION, width / d.width)
        # its digits descend below the drawing's own bounds: lifted by their descent, a quarter of their size
        lift = 0.25 * float(d.contents[0].fontSize) * scale
        ean = {"digits": digits, "scale": scale, "w": d.width * scale, "h": d.height * scale + lift, "bar": bar,
               "lift": lift}
    beside = qr is not None and ean is None and 2 * pad + label_w + gap + value_w + size + qr["side"] <= width
    inner = width - 2 * pad
    if beside:
        inner = width - qr["side"] - size - 2 * pad
    in_line = label_w + gap + widest_word <= inner
    wrapped, over, used = [], 0.0, 0.0
    for label, value in rows:
        room = inner
        if in_line:
            room = inner - label_w - gap
        if value == BLANK:
            # the write-in line is a rule, not words: drawn in the regular face (the narrow face's "_" is wide)
            lines, o = [[(BLANK, False)]], _width(BLANK, face_of(BLANK), size) - room
        else:
            lines, o = _wrap_words([(w, False) for w in value.split()], size, room, fonts)
        over = max(over, o, _width(label, fonts["bold"], size) - inner)
        used = max(used, max((_width(BLANK, face_of(BLANK), size) if ln == [(BLANK, False)] else
                              _line_w(ln, size, fonts) for ln in lines), default=0.0))
        wrapped.append((label, lines))
    if in_line:
        count = sum(len(lines) for _label, lines in wrapped)
        meta_w = 2 * pad + label_w + gap + used
    else:
        count = sum(1 + len(lines) for _label, lines in wrapped)
        meta_w = 2 * pad + max(label_w, used)
    meta_h = count * lead + 2 * pad
    codes_rows = []
    if beside:
        height = max(meta_h, qr["side"])
    else:
        row = []
        if ean is not None:
            row.append("ean")
        if qr is not None:
            if ean is not None and ean["w"] + size + qr["side"] > width:
                codes_rows.append(row)
                row = []
            row.append("qr")
        if row:
            codes_rows.append(row)
        codes_h = 0.0
        for r in codes_rows:
            tall = 0.0
            if "qr" in r:
                tall = qr["side"]
            if "ean" in r:
                tall = max(tall, ean["h"])
            codes_h += tall
        codes_h += size * max(0, len(codes_rows) - 1)
        height = meta_h
        if codes_rows:
            height += size + codes_h
    return {"rows": wrapped, "label_w": label_w, "gap": gap, "pad": pad, "meta_w": meta_w, "meta_h": meta_h,
            "in_line": in_line, "beside": beside, "qr": qr, "ean": ean, "codes_rows": codes_rows, "height": height,
            "over": over}


def steps(fonts: dict):
    """Every size the label is tried at, largest first: [his correction of 2026-10-07] the whole label evenly — the
    body, the ingredients and warnings, and the title in its proportion — from SIZE_MAX_PT down to the 3 pt floor, a
    quarter point at a time, in the label's own face; its spacing in the same ems, so its layout, spacing and order are
    kept. (The fine print stepped down alone to 4 pt and then the granted narrower face was tried, his second goal of
    2026-10-06; both are gone with it.)"""
    body = SIZE_MAX_PT
    while body >= FLOOR_PT - 1e-9:
        yield {"face": "regular", "body": body, "fine": body, "title": round(body * TITLE_EM, 2)}
        body = round(body - SIZE_STEP_PT, 2)


def _faces_for(fonts: dict, levels: dict) -> dict:
    return fonts                       # [his correction of 2026-10-07] one face: the label's own


def _lay(info: dict, levels: dict, width: float, panel_w: float, fonts: dict, keep_marks: bool, title: bool,
         band: bool, languages, tail: bool = True) -> dict:
    from apps.dielines.exporters.info_panel import title_ar
    f = _faces_for(fonts, levels)
    body = levels["body"]
    lead_of = {"title": levels["title"] * LEAD_EM, "body": body * LEAD_EM, "fine": levels["fine"] * LEAD_EM}
    blead = lead_of["body"]
    over = 0.0
    out = {"levels": dict(levels), "fonts": f, "title_en": [], "title_ar": [], "blocks": [], "tail": [], "band": None,
           "gaps": 0, "languages": list(languages)}
    height = 0.0
    if title:
        # [his goal of 2026-10-06, item 12: "The sticker title is sized to fit on one or two lines, never one word per
        # line ("ROSE / GLAZE / LIP / GLOSS")."] the title at its level's size where it stands so, else as large as it
        # stands on two lines (its lines as even as its words allow) — the level's one size, for its Arabic too
        name = (info.get("product_name") or "").strip().upper()
        size, out["title_en"], out["title_ar"], o = _title_fit(name, title_ar(info) if f.get("arabic") else "",
                                                               levels, width, f, keep_marks)
        over = max(over, o)
        out["levels"]["title"] = size
        lead_of["title"] = size * LEAD_EM
        height += (len(out["title_en"]) + len(out["title_ar"])) * lead_of["title"]
    said = label_sections(info, languages if f.get("arabic") else [l for l in languages if l != "ar"])
    for block in said["blocks"]:
        if height:
            height += blead * LANGUAGE_GAP_EM
            out["gaps"] += 1
        laid = []
        for i, s in enumerate(block["sections"]):
            size = levels[s["level"]]
            if block["lang"] == "ar":
                lines = _ar_lines(s["head"], s["text"], size, width, f, keep_marks)
                o = max((_ar_line_w(ln, size, f) for ln in lines), default=0.0) - width
            else:
                words = [(w, True) for w in s["head"].split()] + [(w, False) for w in s["text"].split()]
                lines, o = _wrap_words(words, size, width, f)
            over = max(over, o)
            if i:
                height += blead * SECTION_GAP_EM
            height += len(lines) * lead_of[s["level"]]
            laid.append(dict(s, size=size, lead=lead_of[s["level"]], lines=lines))
        out["blocks"].append({"lang": block["lang"], "sections": laid})
    if said["tail"] and tail:
        out["tail"], o = _wrap_words([(w, False) for w in said["tail"].split()], body, width, f)
        over = max(over, o)
        if height:
            height += blead * SECTION_GAP_EM
        height += len(out["tail"]) * blead
    if band:
        out["band"] = _band(info, body, width, panel_w, f)
        over = max(over, out["band"]["over"])
        if height:
            height += blead * SECTION_GAP_EM
        height += out["band"]["height"]
    if height:
        # the first line's box stands on the region's top and the last one's on its foot: the faces' full box, once
        asc, desc = _faces_box(f)
        height += max(0.0, asc + desc - LEAD_EM) * body
    out["height"], out["over"] = height, over
    return out


def plan_label(info: dict, width: float, height: float, fonts: dict, *, panel_w: float | None = None,
               languages=LANGUAGES, title: bool = True, band: bool = True, keep_marks: bool = False,
               levels: dict | None = None, tail: bool = True) -> dict:
    """The first of ``steps`` — or exactly ``levels`` where given — at which the label — its title, the language
    blocks of ``languages``, the brand's line and its foot — stands inside ``width`` × ``height`` points with its
    spacing; ``fits`` False, laid at the 3 pt floor, where none does. Never cut, never moved, never under the floor."""
    fonts = arabic_bold(fonts)
    panel_w = panel_w or width
    languages = tuple(languages)
    if levels is not None:
        laid = _lay(info, levels, width, panel_w, fonts, keep_marks, title, band, languages, tail)
        return dict(laid, fits=laid["height"] <= height + 1e-6 and laid["over"] <= 1e-6, width=width, avail=height)
    laid = None
    for lv in steps(fonts):
        laid = _lay(info, lv, width, panel_w, fonts, keep_marks, title, band, languages, tail)
        if laid["height"] <= height + 1e-6 and laid["over"] <= 1e-6:
            return dict(laid, fits=True, width=width, avail=height)
    return dict(laid, fits=False, width=width, avail=height)


def record_of(plan: dict) -> dict:
    """What a plan set, for the record."""
    lv = plan["levels"]
    return {"levels_pt": {"title": lv["title"], "body": lv["body"], "fine": lv["fine"]}, "face": lv["face"],
            "fits": plan["fits"], "needs_pt": round(plan["height"], 2), "holds_pt": round(plan["avail"], 2),
            "word_over_pt": round(plan["over"], 2), "languages": list(plan["languages"]),
            "sections": ["%s:%s" % (s["field"], b["lang"]) for b in plan["blocks"] for s in b["sections"]],
            "foot": None if plan["band"] is None else ("beside the QR" if plan["band"]["beside"] else "above the codes"),
            # [his goal of 2026-10-06, item 12] the title's lines
            "title_lines": len(plan.get("title_en") or []) + len(plan.get("title_ar") or [])}


def _dark(hex_colour: str) -> bool:
    r, g, b = (int(hex_colour[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    return 0.299 * r + 0.587 * g + 0.114 * b < 0.5


def _cmyk(hex_colour: str):
    from reportlab.lib.colors import CMYKColor
    r, g, b = (int(hex_colour[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    k = 1.0 - max(r, g, b)
    if k >= 1.0:
        return CMYKColor(0.0, 0.0, 0.0, 1.0)
    return CMYKColor((1 - r - k) / (1 - k), (1 - g - k) / (1 - k), (1 - b - k) / (1 - k), k)


def draw_plan(c, plan: dict, x0: float, y0: float, info: dict, fonts: dict, ink, paper: str | None = None) -> dict:
    """``plan`` drawn with its region's bottom left at (``x0``, ``y0``) points: the title from the top, the language
    blocks under it with a hairline between them, the brand's line, the foot on the region's floor, the spare height
    spread over the gaps between languages (each opened at most to LANGUAGE_GAP_MAX_EM). Returns where the QR's box was
    drawn, in points, for the record."""
    from apps.dielines.exporters.text_intl import split_script_runs
    f = plan["fonts"]
    lv = plan["levels"]
    width = plan["width"]
    blead = lv["body"] * LEAD_EM
    spare = max(0.0, plan["avail"] - plan["height"])
    widen = 0.0
    if plan["gaps"]:
        widen = min(spare / plan["gaps"], blead * (LANGUAGE_GAP_MAX_EM - LANGUAGE_GAP_EM))
    y = y0 + plan["avail"]
    right = x0 + width
    c.setFillColor(ink)
    asc, _desc = _faces_box(f)

    def baseline(cursor, size):
        return cursor - size * asc                          # the line's box top on the cursor

    def words_line(cursor, line, size):
        x = x0
        for w, b in line:
            face = f["bold"] if b else f["regular"]
            _draw_string(c, x, baseline(cursor, size), w, face, size)
            x += _width(w, face, size) + _width(" ", f["regular"], size)

    def arabic_runs(x, base, visual, size, bold):
        for is_ar, t in split_script_runs(visual):
            face = _ar_face(f, bold) if is_ar else f["regular"]       # [his goal of 2026-10-06, item 6] never stroked
            _draw_string(c, x, base, t, face, size)
            x += _width(t, face, size)
        return x

    def arabic_line(cursor, ln, size):
        base = baseline(cursor, size)
        x = right - _ar_line_w(ln, size, f)
        if ln["rest"]:
            x = arabic_runs(x, base, ln["rest"], size, False)
            if ln["head"]:
                x += _width(" ", f["regular"], size)
        if ln["head"]:
            arabic_runs(x, base, ln["head"], size, True)

    def rule(cursor, gap):
        c.saveState()
        c.setStrokeColor(ink)
        c.setLineWidth(RULE_PT)
        mid = cursor - gap / 2.0
        c.line(x0, mid, right, mid)
        c.restoreState()

    tsize = lv["title"]
    for line in plan["title_en"]:
        words_line(y, line, tsize)
        y -= tsize * LEAD_EM
    for ln in plan["title_ar"]:
        arabic_line(y, ln, tsize)
        y -= tsize * LEAD_EM
    drawn_any = bool(plan["title_en"] or plan["title_ar"])
    for block in plan["blocks"]:
        if drawn_any:
            gap = blead * LANGUAGE_GAP_EM + widen
            rule(y, gap)
            y -= gap
        for i, s in enumerate(block["sections"]):
            if i:
                y -= blead * SECTION_GAP_EM
            for ln in s["lines"]:
                if block["lang"] == "ar":
                    arabic_line(y, ln, s["size"])
                else:
                    words_line(y, ln, s["size"])
                y -= s["lead"]
        drawn_any = True
    if plan["tail"]:
        if drawn_any:
            y -= blead * SECTION_GAP_EM
        for ln in plan["tail"]:
            words_line(y, ln, lv["body"])
            y -= blead
    band = plan["band"]
    drawn = {}
    if band is None:
        return drawn
    from reportlab.graphics import renderPDF
    size = lv["body"]
    lead = blead
    pad, label_w, gap = band["pad"], band["label_w"], band["gap"]
    meta_top = y0 + band["height"]
    # the NET WT / ITEM / BATCH block, framed to its text
    c.saveState()
    c.setStrokeColor(ink)
    c.setLineWidth(0.4)
    c.rect(x0, meta_top - band["meta_h"], band["meta_w"], band["meta_h"], fill=0, stroke=1)
    c.restoreState()
    c.setFillColor(ink)
    cursor = meta_top - pad
    for label, lines in band["rows"]:
        _draw_string(c, x0 + pad, baseline(cursor, size), label, f["bold"], size)
        value_x = x0 + pad + label_w + gap
        if not band["in_line"]:
            cursor -= lead                                  # the value under its label
            value_x = x0 + pad
        for ln in lines:
            value = " ".join(w for w, _b in ln)
            _draw_string(c, value_x, baseline(cursor, size), value,
                         f.get("blank", f["regular"]) if value == BLANK else f["regular"], size)
            cursor -= lead
    drawn["meta_box_pt"] = [round(x0, 2), round(meta_top - band["meta_h"], 2), round(band["meta_w"], 2),
                            round(band["meta_h"], 2)]
    from apps.dielines.exporters.info_panel import _BLACK_C
    if band["qr"] is not None:
        from reportlab.graphics.barcode.qr import QrCodeWidget
        from reportlab.graphics.shapes import Drawing
        side = band["qr"]["side"]
        q = QrCodeWidget(info["qr_url"].strip(), barFillColor=_BLACK_C)
        bounds = q.getBounds()
        dq = Drawing(side, side, transform=[side / (bounds[2] - bounds[0]), 0, 0, side / (bounds[3] - bounds[1]), 0, 0])
        dq.add(q)
        qx, qy = right - side, y0
        if paper and _dark(paper):
            # [his final goal, B3] on a dark sticker the QR stands on a white square — its quiet zone kept readable
            c.saveState()
            c.setFillColor(_cmyk("#FFFFFF"))
            c.rect(qx, qy, side, side, fill=1, stroke=0)
            c.restoreState()
        renderPDF.draw(dq, c, qx, qy)
        drawn["qr_box_pt"] = [round(qx, 2), round(qy, 2), round(side, 2), round(side, 2)]
    if band["ean"] is not None:
        from reportlab.graphics.barcode import createBarcodeDrawing
        e = band["ean"]
        d = createBarcodeDrawing("EAN13", value=e["digits"], barHeight=e["bar"], humanReadable=True,
                                 barFillColor=_BLACK_C, textColor=_BLACK_C)
        ey = y0 + e["lift"]
        if len(band["codes_rows"]) > 1:
            ey = y0 + band["qr"]["side"] + size + e["lift"]
        c.saveState()
        c.translate(x0, ey)
        c.scale(e["scale"], e["scale"])
        renderPDF.draw(d, c, 0, 0)
        c.restoreState()
        drawn["ean_box_pt"] = [round(x0, 2), round(ey, 2), round(e["w"], 2), round(e["h"], 2)]
    return drawn


def ean_shapes(digits: str, bar: float) -> list:
    """[His goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 7: "BARCODE: my number prints correctly but is cut at the sticker's edge. Always whole, inside the sticker, with quiet zones. No number from me = no barcode."]
    The EAN-13 as reportlab draws it at 100 %, piece by piece, in points from its drawing's bottom left:
    ``[("bar", x, y, w, h, "", 0) | ("digits", x, y, 0, 0, text, size)]`` — so the native file draws the very bars the
    PDF does."""
    from reportlab.graphics.barcode import createBarcodeDrawing
    d = createBarcodeDrawing("EAN13", value=digits, barHeight=bar, humanReadable=True)
    out = []
    for shape in d.contents[0].draw().getContents():
        kind = type(shape).__name__
        if kind == "Rect" and shape.fillColor is not None:
            out.append(("bar", float(shape.x), float(shape.y), float(shape.width), float(shape.height), "", 0.0))
        elif kind == "String":
            out.append(("digits", float(shape.x), float(shape.y), 0.0, 0.0, str(shape.text), float(shape.fontSize)))
    return out


def qr_modules(value: str) -> tuple:
    """``(count, dark)``: the QR's modules as reportlab draws them — its own encoder, the same code — the dark ones as
    (row, column), and the count across the symbol (its four-module quiet zone outside it)."""
    from reportlab.graphics.barcode.qr import QrCodeWidget
    widget = QrCodeWidget(value)
    widget.draw()
    qr = widget.qr
    n = qr.getModuleCount()
    return n, [(r, c) for r in range(n) for c in range(n) if qr.isDark(r, c)]


def plan_to_nodes(plan: dict, x_mm: float, y_mm: float, info: dict, ink_hex: str, *, name: str = "label",
                  paper: str | None = None) -> list:
    """[His final goal, 2026-10-05, C6: "EVERY ELEMENT IS ITS OWN PIECE. In the .ai, each part is a separate, named layer
    or group he can select, move or delete alone. Text stays editable where possible."] ``plan`` (``plan_label``) as
    graph nodes, its region's top left at (``x_mm``, ``y_mm``), placed exactly where ``draw_plan`` draws it: the title,
    each language's sections and the brand's line as named groups of live text runs (a heading its own run, bold), a
    hairline between languages, the NET WT block — its frame, each row's label and value — and the QR as one path of
    its modules on its quiet square. Arabic runs carry their LOGICAL words, set from the right; Illustrator shapes them."""
    from apps.ire.graph import ClosePath, Color, Group, LineTo, MoveTo, Path, Rect, SolidFill, Stroke, TextRun
    k = 25.4 / 72.0                                         # points to millimetres
    f = plan["fonts"]
    lv = plan["levels"]
    width = plan["width"]
    ink = Color.from_hex(ink_hex)
    blead = lv["body"] * LEAD_EM
    spare = max(0.0, plan["avail"] - plan["height"])
    widen = 0.0
    if plan["gaps"]:
        widen = min(spare / plan["gaps"], blead * (LANGUAGE_GAP_MAX_EM - LANGUAGE_GAP_EM))
    asc, _desc = _faces_box(f)
    space = _width(" ", f["regular"], lv["body"])
    groups: list = []
    cursor = [0.0]                                          # points down from the region's top

    def X(pt):
        return x_mm + pt * k

    def Y(pt):
        return y_mm + pt * k

    def words_line(line, size, label):
        out, x = [], 0.0
        base = cursor[0] + size * asc
        runs: list = []
        for w, b in line:
            if runs and runs[-1][0] == b:
                runs[-1][1].append(w)
            else:
                runs.append((b, [w]))
        for i, (bold, words) in enumerate(runs):
            text = " ".join(words)
            face = f["bold"] if bold else f["regular"]
            out.append(TextRun(name="%s-%d" % (label, i), text=text, x=X(x), y=Y(base), size_pt=size, color=ink,
                               font=face, align="left", rtl=False))
            x += _width(text, face, size) + _width(" ", f["regular"], size)
        return out

    def arabic_line(ln, size, label):
        base = cursor[0] + size * asc
        out = []
        right = width
        if ln.get("head_logical"):
            out.append(TextRun(name="%s-head-bold" % label, text=ln["head_logical"], x=X(right), y=Y(base), size_pt=size,
                               color=ink, font=_ar_face(f, True), align="right", rtl=True))
            right -= _ar_width(ln["head"], size, f, bold=True) + _width(" ", f["regular"], size)
        if ln.get("rest_logical"):
            out.append(TextRun(name="%s-text" % label, text=ln["rest_logical"], x=X(right), y=Y(base), size_pt=size,
                               color=ink, font=f["arabic"], align="right", rtl=True))
        return out

    def rule(gap, label):
        mid = cursor[0] + gap / 2.0
        return Path(name=label, segments=[MoveTo(x=X(0.0), y=Y(mid)), LineTo(x=X(width), y=Y(mid))],
                    stroke=Stroke(color=ink, width_mm=RULE_PT * k))

    tsize = lv["title"]
    title = []
    for i, line in enumerate(plan["title_en"]):
        title += words_line(line, tsize, "title-en-%d" % i)
        cursor[0] += tsize * LEAD_EM
    for i, ln in enumerate(plan["title_ar"]):
        title += arabic_line(ln, tsize, "title-ar-%d" % i)
        cursor[0] += tsize * LEAD_EM
    if title:
        groups.append(Group(name="%s-title" % name, role="info", children=title))
    drawn_any = bool(title)
    for block in plan["blocks"]:
        kids = []
        if drawn_any:
            gap = blead * LANGUAGE_GAP_EM + widen
            kids.append(rule(gap, "%s-%s-rule" % (name, block["lang"])))
            cursor[0] += gap
        for i, s in enumerate(block["sections"]):
            if i:
                cursor[0] += blead * SECTION_GAP_EM
            sec = []
            for j, ln in enumerate(s["lines"]):
                label = "%s-%s-%s-%d" % (name, block["lang"], s["field"], j)
                sec += arabic_line(ln, s["size"], label) if block["lang"] == "ar" else words_line(ln, s["size"], label)
                cursor[0] += s["lead"]
            kids.append(Group(name="%s-%s-%s" % (name, block["lang"], s["field"]), role="info", children=sec))
        groups.append(Group(name="%s-%s" % (name, block["lang"]), role="info", children=kids))
        drawn_any = True
    if plan["tail"]:
        if drawn_any:
            cursor[0] += blead * SECTION_GAP_EM
        tail = []
        for j, ln in enumerate(plan["tail"]):
            tail += words_line(ln, lv["body"], "%s-made-in-%d" % (name, j))
            cursor[0] += blead
        groups.append(Group(name="%s-made-in" % name, role="info", children=tail))
    band = plan["band"]
    if band is not None:
        size = lv["body"]
        pad, label_w, gap = band["pad"], band["label_w"], band["gap"]
        top = plan["avail"] - band["height"]               # the foot stands on the region's floor
        meta = [Rect(name="%s-net-wt-frame" % name, x=X(0.0), y=Y(top), w=band["meta_w"] * k, h=band["meta_h"] * k,
                     stroke=Stroke(color=ink, width_mm=0.4 * k))]
        cur = top + pad
        for r, (label, lines) in enumerate(band["rows"]):
            base = cur + size * asc
            meta.append(TextRun(name="%s-row-%d-label" % (name, r), text=label, x=X(pad), y=Y(base), size_pt=size,
                                color=ink, font=f["bold"], align="left", rtl=False))
            value_x = pad + label_w + gap
            if not band["in_line"]:
                cur += blead
                value_x = pad
            for j, ln in enumerate(lines):
                value = " ".join(w for w, _b in ln)
                meta.append(TextRun(name="%s-row-%d-value-%d" % (name, r, j), text=value, x=X(value_x),
                                    y=Y(cur + size * asc), size_pt=size, color=ink,
                                    font=f.get("blank", f["regular"]) if value == BLANK else f["regular"],
                                    align="left", rtl=False))
                cur += blead
        groups.append(Group(name="%s-net-wt" % name, role="info", children=meta))
        if band["ean"] is not None:
            # [his goal of 2026-10-10, item 7] the barcode in the native file too — it had none: each bar its own
            # rectangle and its digits, where ``draw_plan`` draws them, at the same size
            e = band["ean"]
            bottom = e["lift"]
            if len(band["codes_rows"]) > 1:
                bottom = band["qr"]["side"] + size + e["lift"]
            kids = []
            for kind, sx, sy, sw, sh, text, fs in ean_shapes(e["digits"], e["bar"]):
                bar_top = plan["avail"] - (bottom + (sy + sh) * e["scale"])
                if kind == "bar":
                    kids.append(Rect(name="%s-ean-bar-%d" % (name, len(kids)), x=X(sx * e["scale"]), y=Y(bar_top),
                                     w=sw * e["scale"] * k, h=sh * e["scale"] * k,
                                     fill=SolidFill(color=Color.from_hex("#000000"))))
                else:
                    kids.append(TextRun(name="%s-ean-digits-%d" % (name, len(kids)), text=text,
                                        x=X(sx * e["scale"]), y=Y(plan["avail"] - (bottom + sy * e["scale"])),
                                        size_pt=fs * e["scale"], color=Color.from_hex("#000000"), font=f["regular"],
                                        align="left", rtl=False))
            groups.append(Group(name="%s-ean" % name, role="info", children=kids))
        if band["qr"] is not None:
            side = band["qr"]["side"]
            qx, qy = width - side, plan["avail"] - side
            n, dark = qr_modules(info["qr_url"].strip())
            cell = side / (n + 8)                           # four modules of quiet zone each side, as reportlab draws it
            segs = []
            for r, c in dark:
                x0, y0 = qx + (4 + c) * cell, qy + (4 + r) * cell
                segs += [MoveTo(x=X(x0), y=Y(y0)), LineTo(x=X(x0 + cell), y=Y(y0)),
                         LineTo(x=X(x0 + cell), y=Y(y0 + cell)), LineTo(x=X(x0), y=Y(y0 + cell)), ClosePath()]
            qr = [Rect(name="%s-qr-quiet-zone" % name, x=X(qx), y=Y(qy), w=side * k, h=side * k,
                       fill=SolidFill(color=Color.from_hex("#FFFFFF")))] if paper and _dark(paper) else []
            qr.append(Path(name="%s-qr-modules" % name, segments=segs, fill=SolidFill(color=Color.from_hex("#000000")),
                           fill_rule="nonzero"))
            groups.append(Group(name="%s-qr" % name, role="info", children=qr))
    return groups
