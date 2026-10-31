"""The brand's own library, read-only (§BH55 Phase 3, 2026-09-20).

OWNER STANDING ORDER §BH55, PHASE 3: "Every capability the engine has is reachable and labelled in words a designer
understands." The brand's own things a design is made from — its colours, the roles those colours play, its type roles
and the faces behind them, its mark, what every design is told about it — and the past production designs it learns from
were reachable only through code and the admin. Everything here is READ from the authority that governs it, never
restated: the canonical ColorSystem records; the colour-role record (docs/brand_gov/colour_roles_1_0.json) through
apps/ire/colour_roles.py; the type layer's own resolver (apps/ire/font_roles.resolve_role — the one the drawing uses)
and its grant channel (verify_candidate); the brand component library (brand_component_library.build); the
DesignReference rows; build_brand_context, the text a design's planner is given. Nothing here decides, approves or
spends. Two pictures are DERIVED in memory and served same-origin: a face's specimen, drawn on the server from the
granted file (the font file itself is never linked for a specimen — [the owner's answer to the UI directions of
2026-09-25: the interface's own type loads four granted files through static/css/bbrose.css — Raleway Light, Poppins,
Cairo Bold, Noto Naskh Arabic, each an upstream OFL release]), and the mark re-inked in the product ink (its preview is the
brand guideline's cyan, which this product does not use). A house reference is described, never pictured: its file
lies in a reference folder, and reference bytes are never served (§BH53(b), §BH54(b)).
"""
from __future__ import annotations

import io
import re
from functools import lru_cache

_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")

COLOUR_ROLE_WORDS = {
    "ground_cream": "Ground — cream", "ground_gold": "Ground — gold", "ground_blush": "Ground — blush",
    "accent_light": "Accent — light", "accent_blush": "Accent — blush", "accent_nude": "Accent — nude",
    "accent_dark": "Accent — dark", "ink": "Ink — the text colour",
}
TYPE_ROLE_WORDS = {
    "display": "Display — the product's name", "heading": "Headings", "body": "Running text",
    "caption": "Captions", "script-accent": "Script accent", "arabic-display": "Arabic — display",
    "arabic-heading": "Arabic — headings", "arabic-body": "Arabic — running text",
}
#: what each ruled exception to the brand's type is, in words (font_roles.EXEMPT_SURFACES, §BH32(h))
EXEMPT_WORDS = {
    "apps/ire/compose_vector_art.py::compose_vector_art_graph": "the concept-only vector art path",
    "apps/dielines/exporters/counter_display_files.py::_resolve_fonts": "the production PDF and its regulatory sticker",
    "apps/dielines/exporters/counter_display_files.py::_resolve_arabic_font": "the production PDF's Arabic",
    "apps/dielines/exporters/info_panel.py::draw_info_panel": "the product information sticker",
    "apps/dielines/exporters/info_panel.py::svg_info_panel": "the product information sticker, as SVG",
    "apps/ire/handoff/graph_schema.py::serialize_handoff_graph": "the Illustrator handoff's record",
}
#: a tried face's verdict, in words (font_roles.resolve_role's `tried`)
VERDICT_WORDS = {
    "VERIFIED_FOR_PRODUCTION": "granted for production",
    "VARIABLE_INSTANCE_UNPINNED": "a variable face with no weight set for this role — passed over",
    "NOT_IN_CATALOGUE": "not among the governed faces",
    "WRONG_SCRIPT_CAPABILITY": "cannot set this script",
    "REGISTRATION_FAILED": "could not be loaded",
}

LATIN_SAMPLE = "Rose Damascena Night Repair Oil"
LATIN_LETTERS = "Aa Bb Cc Dd Ee Gg Rr 0123456789"
ARABIC_SAMPLE = "زيت الإصلاح الليلي بالورد الدمشقي"          # "Damask rose night repair oil"
# [the owner's answer to the UI directions of 2026-09-25: the pages are C's — Warm Cream, type in Deep Rose. The
# specimens were drawn in the old dark pages' cream and read as nothing on C's cream: in Deep Rose now]
SPECIMEN_INK = (139, 58, 82, 255)                           # Deep Rose, the pages' type (static/css/bbrose.css --rose)
#: what a specimen shows — the whole (the brand's page), a product's name, set large (a face's card: the Library, the
#: library beside a design), or two letters (a small row: the Library's faces for each kind of text, Find) — each fitted
#: to its picture: (the Latin line, the Arabic line, the largest size, width, height)
SPECIMEN_SHOWS = {
    "name": ("Rose Damascena", "الورد الدمشقي", 64, 560, 100),          # "Damask rose"
    "glyph": ("Aa", "أب", 84, 168, 120),
}


def colour_systems(brand) -> list[dict]:
    """The brand's canonical colour systems, each swatch as its record holds it. A metallic ink has no screen colour:
    its record holds the ink's name where a hex would be ("Metallic 10122 C"), and it is shown as that, never as a
    guessed colour."""
    from apps.core.models import STATUS_CANONICAL, ColorSystem
    if brand is None:
        return []
    out = []
    for cs in ColorSystem.objects.filter(brand=brand, status=STATUS_CANONICAL).order_by("system_id"):
        swatches = []
        for sw in cs.palette or []:
            if not isinstance(sw, dict):
                continue
            value = str(sw.get("hex") or "")
            screen = value.upper() if _HEX.match(value) else None
            swatches.append({"name": sw.get("name") or "", "role": sw.get("role") or "", "usage": sw.get("usage") or "",
                             "pantone": sw.get("pantone") or "", "hex": screen, "ink": None if screen else value})
        out.append({"id": cs.system_id, "name": cs.name, "swatches": swatches,
                    "generation_context": cs.image_generation_context or ""})
    return out


def colour_roles() -> list[dict]:
    """The eight roles a colour plays in a design (§BH39(a)), each with the brand colour it resolves to — read live
    from the colour system — or, for the two with none, the colour measured on the house's own files, said so."""
    from apps.ire import colour_roles as cr
    rows = []
    for role in cr.ROLES:
        entry = cr.role_entry(role)
        sw = cr.brand_swatch(role)
        live = cr.live_brand_hex(sw) if sw else None
        files = entry.get("files")
        rows.append({
            "role": role, "words": COLOUR_ROLE_WORDS.get(role, role.replace("_", " ")),
            "brand_colour": (_brand_colour(sw, live) if sw else None),
            "measured_hex": str(entry.get("measured_hex") or "").upper() or None,
            "files": len(files) if isinstance(files, list) else files,
        })
    return rows


def _brand_colour(sw: dict, live: str | None) -> dict:
    value = (live or str(sw.get("hex") or "")).upper()
    return {"name": sw.get("name") or "", "system": sw.get("system_id") or "", "value": value,
            "hex": value if _HEX.match(value) else None, "live": bool(live)}


def type_roles() -> list[dict]:
    """The eight type roles, each with the face the drawing uses — asked of the layer's own resolver, never restated
    — its chain of candidates and what each was found to be. The first call in a process derives a variable face's
    pinned instance into the OS temp folder, exactly as the first drawing does."""
    from apps.ire import font_roles as fr
    rows = []
    for role in fr.ROLES:
        r = fr.resolve_role(role)
        tried = [{"face": t.get("stem"), "verdict": VERDICT_WORDS.get(t.get("verification"), t.get("verification"))}
                 for t in r.get("tried") or []]
        row = {"role": role, "words": TYPE_ROLE_WORDS.get(role, role), "chain": list(fr.CHAINS.get(role, ())),
               "tried": tried, "face": None, "weight": None, "refusal": None}
        if r.get("refused"):
            row["refusal"] = "No face is granted for this role, so its text is not drawn"
        else:
            row["face"] = r.get("stem")
            row["postscript"] = r.get("postscript")
            row["weight"] = fr.instance_weight(role) if r.get("instance") else None
        rows.append(row)
    return rows


def exempt_surfaces() -> list[str]:
    from apps.ire import font_roles as fr
    return [EXEMPT_WORDS.get(s, s) for s in fr.EXEMPT_SURFACES]


def pool_count() -> int:
    """[D-D7-1, Day 7 §4] the GRANTED faces of the materials library in the catalogue — listed on the Library page under
    granted fonts, counted here: the brand panel pictures the house's own faces, not 328 more on every design page."""
    from apps.ire import font_pool, font_roles as fr
    return sum(1 for e in fr.catalogue().values() if e.get("origin") == font_pool.ORIGIN)


def faces() -> list[dict]:
    """Every governed face of the house (the 35 brand faces, the Noto trio and the faces granted since), with its grant
    as the grant channel reads it now — never a copied state — and the roles whose chains name it. The GRANTED pool of
    the materials library (D-D7-1) is counted by ``pool_count`` and listed on the Library page, not pictured here."""
    from apps.ire import font_pool, font_roles as fr
    serves: dict[str, list[str]] = {}
    for role, chain in fr.CHAINS.items():
        for i, stem in enumerate(chain, 1):
            serves.setdefault(stem, []).append(TYPE_ROLE_WORDS.get(role, role) + ("" if i == 1 else f" (choice {i})"))
    rows = []
    for stem, e in sorted(fr.catalogue().items(), key=lambda kv: ((kv[1].get("family") or kv[0]).lower(), kv[0])):
        if e.get("origin") == font_pool.ORIGIN:
            continue
        rec = fr.verify_candidate("body" if e.get("latin") else "arabic-body", stem) or {}
        rows.append({
            "stem": stem, "family": e.get("family") or stem, "postscript": e.get("postscript") or stem,
            "variable": bool(e.get("variable")), "default_instance": e.get("variable_default_instance") or "",
            "scripts": ", ".join(s for s, ok in (("Latin", e.get("latin")), ("Arabic", e.get("arabic"))) if ok) or "—",
            "granted": rec.get("verification") == "VERIFIED_FOR_PRODUCTION",
            "licence": rec.get("licence_id") or "", "approved_by": rec.get("approved_by") or "",
            "serves": serves.get(stem, []),
        })
    return rows


@lru_cache(maxsize=192)
def specimen_png(stem: str, show: str = "whole") -> bytes | None:
    """A face's specimen, drawn on the server from its granted file, in the pages' Deep Rose on a clear ground: the
    whole — the sample and the letters — or, short, a product's name or two letters (SPECIMEN_SHOWS), each set as large
    as its picture holds. None for a face outside the governed catalogue."""
    from PIL import Image, ImageDraw, ImageFont
    from apps.ire import font_roles as fr
    e = fr.catalogue().get(stem)
    if not e:
        return None
    arabic_only = bool(e.get("arabic")) and not e.get("latin")
    if show in SPECIMEN_SHOWS:
        latin, arabic, size, width, height = SPECIMEN_SHOWS[show]
        line, margin = (arabic if arabic_only else latin), 8
        direction = "rtl" if arabic_only else None
        font = ImageFont.truetype(e["path"], size, layout_engine=ImageFont.Layout.RAQM)
        box = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), line, font=font, direction=direction)
        fit = min(1.0, (width - 2 * margin) / max(1, box[2] - box[0]), (height - 2 * margin) / max(1, box[3] - box[1]))
        if fit < 1.0:                                   # a wide or tall face is set smaller, never cut
            font = ImageFont.truetype(e["path"], max(8, int(size * fit)), layout_engine=ImageFont.Layout.RAQM)
        im = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(im)
        box = draw.textbbox((0, 0), line, font=font, direction=direction)
        x = (width - (box[2] - box[0])) // 2 - box[0] if show == "glyph" else (
            width - margin - box[2] if arabic_only else margin - box[0])
        draw.text((x, (height - (box[3] - box[1])) // 2 - box[1]), line, font=font, fill=SPECIMEN_INK,
                  direction=direction)
    else:
        lines = [ARABIC_SAMPLE] if arabic_only else [LATIN_SAMPLE, LATIN_LETTERS]
        width, height, margin = 960, 150 if len(lines) > 1 else 96, 12
        im = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(im)
        y = margin
        for line, size in zip(lines, (46, 28)):
            font = ImageFont.truetype(e["path"], size, layout_engine=ImageFont.Layout.RAQM)
            if arabic_only:
                box = draw.textbbox((0, 0), line, font=font, direction="rtl")
                draw.text((width - margin - (box[2] - box[0]), y), line, font=font, fill=SPECIMEN_INK, direction="rtl")
            else:
                draw.text((margin, y), line, font=font, fill=SPECIMEN_INK)
            y += int(size * 1.5)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def marks() -> dict:
    """The brand's mark and its parts, from the brand component library — or its refusal, in its own words."""
    from apps.pipeline.services.brand_component_library import BrandLibraryRefusal, build
    try:
        lib = build()
    except BrandLibraryRefusal as exc:
        return {"refused": list(exc.findings)}
    ink = lib.get("ink_authority") or {}
    parts = []
    for c in lib.get("components") or []:
        geometry = c.get("geometry") or {}
        origin = (c.get("provenance") or {}).get("origin")
        parts.append({"id": c.get("id"), "words": PART_WORDS.get(c.get("id"), c.get("id")),
                      "provenance": PROVENANCE_WORDS.get(origin, str(origin or "").replace("_", " ").lower()),
                      "must_appear": c.get("may_be_omitted") is False,
                      "stroke_pt": geometry.get("stroke_width_pt"), "ink": geometry.get("ink_hex")})
    permission = lib.get("permission") or {}
    return {"refused": None, "parts": parts, "ink": ink.get("selected_product_ink"),
            "guideline_colour": str(ink.get("guideline_source_colour") or "").split(" (")[0],
            "prohibited": [k.replace("_", " ") for k, absent in (ink.get("prohibited_absent") or {}).items() if absent],
            "scope": permission.get("scope") or "",
            "third_party_authorized": bool(permission.get("third_party_authorized"))}


#: the brand component library's parts, in words
PART_WORDS = {
    "LOGO": "The logo lockup", "MEDALLION": "The medallion — a part of the lockup",
    "REGISTERED_SYMBOL": "The registered symbol ® — a part of the lockup",
    "DIVIDER": "The divider rule",
}
#: where each part came from, in words (the library's own provenance origins)
PROVENANCE_WORDS = {
    "OWNER_CONFIRMED_VECTOR_EXTRACTION": "extracted from the approved artwork, confirmed by the owner",
    "GATE_A_VERIFIED_MEASUREMENT": "measured on the approved front artwork, verified at Gate A",
}


def _rgb(hex_value: str) -> tuple[int, int, int]:
    h = hex_value.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


@lru_cache(maxsize=1)
def mark_png() -> bytes | None:
    """The approved mark in the product ink, on the brand's cream. Its preview is the brand guideline's colour (cyan)
    on white; each pixel's distance from white on the red channel — the guideline colour's weakest, scaled by the
    preview's own darkest red, so no colour is assumed — is its coverage, and the coverage is painted in the product
    ink on the cream ground role's colour: the geometry untouched, as the ink record says only the ink differs, and
    opaque, since the record prohibits transparency. None when the library refuses or holds no preview."""
    from pathlib import Path

    from django.conf import settings
    from PIL import Image
    from apps.pipeline.services import brand_component_library as bcl
    try:
        lib = bcl.build()
    except bcl.BrandLibraryRefusal:
        return None
    logo = next((c for c in lib.get("components") or [] if c.get("id") == "LOGO"), None)
    rel = ((logo or {}).get("preview") or {}).get("path")
    ink = (lib.get("ink_authority") or {}).get("selected_product_ink")
    if not rel or not ink or not _HEX.match(ink):
        return None
    path = Path(settings.BASE_DIR) / rel
    if not path.exists():
        return None
    im = Image.open(path).convert("RGB")
    red = im.getchannel("R")
    lo = red.getextrema()[0]
    if lo >= 255:
        return None
    coverage = red.point(lambda v: max(0, min(255, round((255 - v) * 255 / (255 - lo)))))
    out = Image.new("RGB", im.size, _rgb(_ground_hex()))
    out.paste(Image.new("RGB", im.size, _rgb(ink)), mask=coverage)
    scale = 900 / out.width
    out = out.resize((900, max(1, round(out.height * scale))), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


def _ground_hex() -> str:
    """The cream ground role's brand colour (colour_roles), live when the system holds it; white — the preview's own
    ground — when there is none."""
    from apps.ire import colour_roles as cr
    sw = cr.brand_swatch("ground_cream")
    value = (cr.live_brand_hex(sw) if sw else None) or (sw or {}).get("hex") or ""
    return value if _HEX.match(value) else "#FFFFFF"


def brand_knowledge(brand) -> dict | None:
    """What a design's planner is told about the brand, read from the records it is built from — and the text itself,
    as build_brand_context writes it — beside what the records hold that no design is told."""
    from apps.core.models import STATUS_CANONICAL
    from apps.pipeline.services.brand_context import build_brand_context
    if brand is None:
        return None
    aesthetics = list(brand.aesthetic_language.filter(status=STATUS_CANONICAL).order_by("aesthetic_id"))
    return {
        "master_brief": brand.master_brief, "not": brand.what_we_are_not,
        "aesthetics": [{"id": a.aesthetic_id, "name": a.name, "description": a.core_description,
                        "seed": a.prompt_seed_product} for a in aesthetics],
        "materials": [{"id": m.material_id, "name": m.name, "descriptors": m.prompt_descriptors}
                      for m in brand.material_systems.filter(status="approved").order_by("material_id")],
        "text": build_brand_context(brand.id),
        # on record, and read by no design: named so a designer knows they exist and are not used
        "unused": [(label, value) for label, value in (
            ("Positioning", brand.positioning), ("Website", brand.website), ("Regulatory text", brand.regulatory_text),
            *[(f"{a.name} — campaign seed", a.prompt_seed_campaign) for a in aesthetics],
            *[(f"{a.name} — what breaks it", "; ".join(map(str, a.what_breaks_this or []))) for a in aesthetics],
        ) if value],
    }


def _words(value) -> str:
    """A record's value as words: a list joined, a mapping as its parts, yes or no for a flag."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (list, tuple)):
        return ", ".join(_words(v) for v in value if v not in (None, ""))
    if isinstance(value, dict):
        return "; ".join(f"{str(k).replace('_', ' ')}: {_words(v)}" for k, v in value.items() if v not in (None, ""))
    return str(value)


def references(q: str = "") -> list[dict]:
    """Past production designs from the production library, as their rows describe them — their lineage as the
    house's own is not confirmed (§BH53(d): HOUSE_PRODUCTION_LINEAGE_UNCONFIRMED) — never their pictures (§BH53(b)).
    The back panel's text blocks are not repeated: they transcribe other companies' addresses."""
    from apps.core.models import DesignReference
    rows = []
    needle = (q or "").strip().lower()
    for ref in DesignReference.objects.filter(active=True).order_by("name"):
        a = ref.anatomy if isinstance(ref.anatomy, dict) else {}
        layout, typo = a.get("layout") or {}, a.get("typography") or {}
        back = a.get("back_panel") or {}
        rows.append({
            "name": ref.name, "category": ref.get_category_display() if ref.category else "",
            "product_type": ref.product_type, "summary": ref.summary,
            "tags": [str(t) for t in (ref.tags or [])],
            "layout": [(k.replace("_", " "), _words(layout[k])) for k in ("logo_position", "logo_scale",
                                                                          "title_treatment", "composition_grid")
                       if layout.get(k)],
            "type": [(k.replace("_", " "), _words(typo[k])) for k in ("case", "weights", "hierarchy", "serif_sans")
                     if typo.get(k)],
            "motifs": [" — ".join(_words(m.get(k)) for k in ("element", "style", "placement") if m.get(k))
                       for m in (a.get("motifs") or []) if isinstance(m, dict)],
            "finishes": _words([f for f in (a.get("finishes") or []) if isinstance(f, str)]),
            "palette": [h.upper() for h in (a.get("palette_hex") or []) if isinstance(h, str) and _HEX.match(h)],
            "back": [(k.replace("_", " "), _words(back.get(k))) for k in ("trilingual", "sticker_frame",
                                                                       "barcode_placement")
                     if back.get(k) not in (None, "")],
        })
        if needle and needle not in " ".join([ref.name, ref.product_type or "", ref.summary or "",
                                               " ".join(rows[-1]["tags"]), rows[-1]["finishes"],
                                               " ".join(rows[-1]["motifs"])]).lower():
            rows.pop()
    return rows
